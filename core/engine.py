"""UI-agnostic game engine: the turn loop, roll gate, effect application, saves."""
from dataclasses import asdict
from pathlib import Path

import yaml

import rules
from core import campaign as campaign_mod
from core import memory
from core.game_state import CharacterState, GameState, slugify
from core.keeper import Keeper
from core.llm_client import LLMClient

PROTAGONIST_YAML = Path(__file__).resolve().parent.parent / "data" / "agents" / "protagonist.yaml"
MAX_KEEPER_CYCLES = 3  # bound on chained auto-rolls in one turn


def _character_from_sheet(name, sheet, controller="human", personality="", backstory="", player_label=""):
    stats = sheet.get("stats", sheet)
    hp = int(stats.get("HP", 10))
    stress = int(stats.get("Stress", stats.get("Sanity", 50)))
    return CharacterState(
        id=slugify(name), name=name, controller=controller, player_label=player_label,
        hp=hp, max_hp=hp, stress=stress, max_stress=max(stress, 1),
        skills={k: int(v) for k, v in (stats.get("Skills") or {}).items()},
        inventory=list(sheet.get("inventory", [])),
        personality=personality, backstory=backstory,
    )


def _protagonist_backstory(proto: dict, camp) -> str:
    """Fold the sheet's flavour fields + the campaign's hook into one backstory blurb."""
    bits = []
    if proto.get("occupation"):
        age = f", age {proto['age']}" if proto.get("age") else ""
        bits.append(f"{proto['occupation']}{age}.")
    if proto.get("background"):
        bits.append(proto["background"].strip())
    if camp.data.get("protagonist_hints"):
        bits.append(camp.data["protagonist_hints"].strip())
    return " ".join(bits)


def new_game(campaign_path, protagonist_path=PROTAGONIST_YAML) -> GameState:
    camp = campaign_mod.load(campaign_path)
    proto = yaml.safe_load(Path(protagonist_path).read_text(encoding="utf-8"))
    chars = [_character_from_sheet(proto.get("name", "Player"), proto,
                                   personality=proto.get("personality", ""),
                                   backstory=_protagonist_backstory(proto, camp),
                                   player_label="Player 1")]
    for p in camp.ai_party:
        chars.append(_character_from_sheet(p["name"], p, controller="ai",
                                           personality=p.get("personality", ""),
                                           backstory=p.get("backstory", "")))
    state = GameState(
        campaign_file=str(campaign_path), rule_system=camp.rule_system,
        scene_id=camp.first_scene_id(), visited_scenes=[camp.first_scene_id()],
        characters=chars, active_character_id=chars[0].id,
        messages=[{"role": "keeper", "content": camp.introduction.strip()}],
    )
    return state


class Engine:
    def __init__(self, state: GameState, llm: LLMClient = None, util_llm: LLMClient = None):
        self.state = state
        self.campaign = campaign_mod.load(state.campaign_file)
        self.system = rules.get_system(state.rule_system)
        self.llm = llm or LLMClient()
        self.util_llm = util_llm or self.llm   # cheap model for summaries/handouts, else main
        self.keeper = Keeper(self.llm, self.campaign, self.system)
        self._researcher = None
        self._undo_snapshot = None

    # ---------- public API ----------
    def set_llm(self, llm, util_llm=None):
        """Swap the LLM client(s) mid-session (model switcher)."""
        self.llm = llm
        self.util_llm = util_llm or llm
        self.keeper.llm = llm
        self._researcher = None

    def undo(self) -> bool:
        """Restore the state to before the last turn. Single level."""
        if not self._undo_snapshot:
            return False
        self.state = GameState.from_dict(self._undo_snapshot)
        self._undo_snapshot = None
        self.state.save()
        return True

    def _take_snapshot(self):
        self._undo_snapshot = asdict(self.state)

    # Turns run in two halves so a UI can redraw between beats (live play):
    #   begin_*()  — instant, records the player's move
    #   keeper_steps() — generator; each next() does ONE unit of work (a keeper reply,
    #                    one companion's turn, one auto-roll) and yields the label of the
    #                    next unit. Drain it for a blocking turn (CLI, tests).

    def begin_action(self, character_id: str, text: str) -> str:
        self._take_snapshot()
        char = self.state.get_character(character_id)
        if char:
            self.state.active_character_id = character_id
        self.state.turn_count += 1
        self.state.messages.append({"role": "player", "name": char.name if char else None, "content": text})
        self.state.save()
        return text

    def keeper_steps(self, input_text: str):
        """Generator: advances the turn one beat at a time. Yields a label for the next beat."""
        yield from self._keeper_cycle_steps(input_text)
        self._finish_turn()

    def roll_dice(self):
        """Roll the pending check for a human character. Returns the RollResult (no keeper call)."""
        pr = self.state.pending_roll
        if not pr:
            return None
        self._take_snapshot()
        char = self.state.get_character(pr["character_id"])
        result = self.system.skill_check(pr["target"], pr.get("difficulty", "regular"))
        line = f"{char.name} — {pr['skill']}: {result.detail}"
        self.state.dice_log.append(line)
        self.state.pending_roll = None
        self.state.messages.append({"role": "dice", "name": char.name, "content": line})
        self.state.save()
        return result

    def begin_negotiate(self, text: str) -> str:
        """Player argues for a different skill/approach instead of rolling."""
        self._take_snapshot()
        char = self.state.get_character(self.state.pending_roll["character_id"]) if self.state.pending_roll else None
        self.state.pending_roll = None
        self.state.messages.append({"role": "player", "name": char.name if char else None, "content": text})
        self.state.save()
        return f"(The player negotiates the pending roll instead of rolling): {text}"

    def begin_minigame_result(self, result_text: str) -> str:
        """Record the outcome of a minigame; the keeper picks up from it."""
        self._take_snapshot()
        self.state.pending_minigame = None
        self.state.dice_log.append(f"[minigame] {result_text}")
        self.state.messages.append({"role": "player", "content": f"MINIGAME RESULT: {result_text}"})
        self.state.save()
        return f"MINIGAME RESULT: {result_text}. Continue the story from this."

    # --- blocking wrappers (CLI / tests): run the whole turn at once ---
    def submit_action(self, character_id: str, text: str):
        for _ in self.keeper_steps(self.begin_action(character_id, text)):
            pass

    def resolve_roll(self):
        result = self.roll_dice()
        if result is None:
            return None
        for _ in self.keeper_steps("Narrate the outcome of the roll above."):
            pass
        return result

    def negotiate_roll(self, text: str):
        for _ in self.keeper_steps(self.begin_negotiate(text)):
            pass

    def resolve_minigame(self, result_text: str):
        for _ in self.keeper_steps(self.begin_minigame_result(result_text)):
            pass

    def set_controller(self, character_id: str, controller: str):
        char = self.state.get_character(character_id)
        if char and controller in ("human", "ai"):
            char.controller = controller
            self.state.save()

    def update_character(self, character_id: str, **fields):
        """Edit a character's flavour/identity (name, personality, backstory, player_label)."""
        char = self.state.get_character(character_id)
        if not char:
            return None
        for key in ("name", "personality", "backstory", "player_label"):
            if key in fields and fields[key] is not None:
                setattr(char, key, fields[key])
        if "inventory" in fields and fields["inventory"] is not None:
            char.inventory = [i.strip() for i in fields["inventory"] if i.strip()]
        self.state.save()
        return char

    def add_character(self, name: str, controller: str = "human", sheet: dict = None,
                      personality: str = "", backstory: str = "", player_label: str = ""):
        sheet = sheet or {"stats": self.system.character_sheet_defaults()}
        char = _character_from_sheet(name, sheet, controller=controller, personality=personality,
                                     backstory=backstory, player_label=player_label)
        base, n = char.id, 2
        while self.state.get_character(char.id):
            char.id = f"{base}_{n}"; n += 1
        self.state.characters.append(char)
        self.state.dice_log.append(f"{char.name} joins the party ({controller}-controlled).")
        self.state.save()
        return char

    def consult_researcher(self, query: str, use_web: bool = False) -> str:
        from agents.researcher import Researcher
        if self._researcher is None:
            self._researcher = Researcher(self.util_llm)
        handout = self._researcher.consult(query, self.state, self.campaign, use_web=use_web)
        self.state.messages.append({"role": "researcher", "name": "Archives", "content": handout})
        self.state.save()
        return handout

    # ---------- internals ----------
    def _keeper_cycle_steps(self, input_text: str, allow_companions: bool = True):
        """Keeper turns until no auto-resolvable roll remains. Yields between beats.
        Sets pending_roll / pending_minigame and returns when it needs the player."""
        actors_requested = []
        for _ in range(MAX_KEEPER_CYCLES):
            narrative, ctrl = self.keeper.respond(self.state, input_text)
            if narrative:
                self.state.messages.append({"role": "keeper", "content": narrative})
            self._apply_effects(ctrl)
            actors_requested.extend(ctrl.characters_act)
            self.state.save()

            if ctrl.minigame and not ctrl.roll_request:
                self.state.pending_minigame = ctrl.minigame
                self.state.save()
                return  # gate: wait for the player to play it out

            if not ctrl.roll_request:
                break
            char, skill, target = self._resolve_roll_target(ctrl.roll_request)
            difficulty = ctrl.roll_request.get("difficulty", "regular")
            if char.controller == "human" and char.status == "active":
                self.state.pending_roll = {
                    "character_id": char.id, "skill": skill, "target": target,
                    "difficulty": difficulty, "reason": ctrl.roll_request.get("reason", ""),
                }
                self.state.save()
                return  # gate: wait for the human to roll

            yield f"🎲 {char.name} rolls {skill}…"
            result = self.system.skill_check(target, difficulty)
            line = f"{char.name} — {skill}: {result.detail}"
            self.state.dice_log.append(line)
            self.state.messages.append({"role": "dice", "name": char.name, "content": line})
            self.state.save()
            yield "The Keeper narrates the outcome…"
            input_text = "Narrate the outcome of the roll above."

        if allow_companions and not self.state.pending_roll and not self.state.pending_minigame:
            yield from self._companion_turns_steps(actors_requested)

    def _resolve_roll_target(self, roll_request):
        """Map the keeper's requested character/skill onto real state; coerce loosely, never fail."""
        char = self.state.get_character(roll_request.get("character", "")) or self.state.active_character() \
            or self.state.characters[0]
        want = (roll_request.get("skill") or "").strip()
        for k in char.skills:
            if k.lower() == want.lower():
                return char, k, char.skills[k]
        for k in char.skills:
            if want.lower() in k.lower() or k.lower() in want.lower():
                return char, k, char.skills[k]
        return char, want or "Luck", self.system.default_skill_target()

    def _apply_effects(self, ctrl):
        st = self.state
        for cid in ctrl.clues_discovered:
            if cid in self.campaign.all_clue_ids() and cid not in st.discovered_clues:
                st.discovered_clues.append(cid)
            elif cid not in self.campaign.all_clue_ids():
                st.dice_log.append(f"[warn] keeper referenced unknown clue id {cid!r} — ignored")

        if ctrl.stress_check:
            char = st.get_character(ctrl.stress_check.get("character", "")) or st.active_character()
            loss_expr = ctrl.stress_check.get("loss", "0/1d4")
            if char and self.system.validate_loss_expr(loss_expr):
                outcome = self.system.stress_check(char.stress, loss_expr)
                if outcome:
                    new, line = outcome
                    lost = char.stress - new
                    char.stress = new
                    st.dice_log.append(f"{char.name} — {line}")
                    if new == 0:
                        char.status = "insane"
                        st.dice_log.append(f"{char.name} has lost their mind entirely.")
                    elif lost >= 5:
                        st.dice_log.append(f"{char.name} suffers a bout of madness (lost {lost} in one blow).")
            eid = ctrl.stress_check.get("event_id")
            if eid and eid not in st.triggered_events:
                st.triggered_events.append(eid)

        if ctrl.hp_change:
            char = st.get_character(ctrl.hp_change.get("character", "")) or st.active_character()
            try:
                amount = int(ctrl.hp_change.get("amount", 0))
            except (TypeError, ValueError):
                amount = 0
            if char and amount:
                char.hp = max(0, min(char.max_hp, char.hp + amount))
                st.dice_log.append(f"{char.name} HP {'+' if amount > 0 else ''}{amount} -> {char.hp}/{char.max_hp}")
                if char.hp == 0 and char.status == "active":
                    char.status = "unconscious"
                    st.dice_log.append(f"{char.name} collapses.")

        if ctrl.scene_transition:
            scene = self.campaign.scene(st.scene_id) or {}
            valid = {x["to"] for x in scene.get("exits", [])}
            if ctrl.scene_transition in valid:
                st.scene_id = ctrl.scene_transition
                if ctrl.scene_transition not in st.visited_scenes:
                    st.visited_scenes.append(ctrl.scene_transition)
            elif self.campaign.scene(ctrl.scene_transition):
                st.dice_log.append(f"[warn] keeper jumped to non-exit scene {ctrl.scene_transition!r} — allowed")
                st.scene_id = ctrl.scene_transition
                if ctrl.scene_transition not in st.visited_scenes:
                    st.visited_scenes.append(ctrl.scene_transition)
            else:
                st.dice_log.append(f"[warn] keeper referenced unknown scene {ctrl.scene_transition!r} — ignored")

    def _companion_turns_steps(self, requested_ids):
        st = self.state
        if st.party_mode == "solo":
            return
        ai_chars = st.ai_characters()
        if st.party_mode == "keeper":
            actors = [c for c in ai_chars if c.id in requested_ids or c.name in requested_ids]
        else:  # active
            actors = ai_chars
        if not actors:
            return
        from agents.player_agent import PlayerAgent
        agent = PlayerAgent(self.llm)
        actions = []
        for char in actors:
            yield f"🎭 {char.name} decides what to do…"
            action = agent.take_turn(char, st, self.campaign)
            st.messages.append({"role": "companion", "name": char.name, "content": action})
            st.save()
            actions.append(f"{char.name}: {action}")
        yield "The Keeper resolves the party's actions…"
        wrap = "COMPANION ACTIONS this turn:\n" + "\n".join(actions) + \
               "\nResolve these actions briefly (auto-roll any checks yourself via roll_request)."
        yield from self._keeper_cycle_steps(wrap, allow_companions=False)

    def _finish_turn(self):
        if not self.state.pending_roll and not self.state.pending_minigame:
            memory.maybe_compact(self.state, self.util_llm)
        self.state.save()
