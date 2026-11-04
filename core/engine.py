"""UI-agnostic game engine: the turn loop, roll gate, effect application, saves."""
import re
from dataclasses import asdict
from types import SimpleNamespace
from pathlib import Path

import yaml

import rules
from core import campaign as campaign_mod
from core import memory
from core.game_state import CharacterState, GameState, slugify, unique_id
from core.keeper import Keeper
from core.llm_client import LLMClient, check_llm
from rules.base import parse_dice, validate_dice

PROTAGONIST_YAML = Path(__file__).resolve().parent.parent / "data" / "agents" / "protagonist.yaml"
MAX_KEEPER_CYCLES = 3  # bound on chained auto-rolls in one turn
OUTCOME = "Narrate the outcome of the roll above."

ITEM_PROMPT = """You describe one item from a tabletop horror game, as the character holding it
would notice it. Two short sentences of concrete physical detail, plain text only. Never invent
plot facts or clues. Use the language given in the request."""


def _roll_mod(req: dict, *keys) -> int:
    """Read a bonus/penalty count from a roll_request, tolerating LLM spellings. 0-2."""
    for k in keys:
        v = req.get(k)
        if v is True:
            return 1
        try:
            if v:
                return max(0, min(2, abs(int(v))))
        except (TypeError, ValueError):
            pass
    return 0


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
    if proto.get("backstory") or proto.get("background"):
        bits.append((proto.get("backstory") or proto.get("background")).strip())
    if camp.data.get("protagonist_hints"):
        bits.append(camp.data["protagonist_hints"].strip())
    return " ".join(bits)


def hero_sheet(campaign_path, protagonist_path=PROTAGONIST_YAML) -> dict:
    """The campaign's own protagonist (setting-appropriate), else the generic fallback sheet."""
    return campaign_mod.load(campaign_path).protagonist or yaml.safe_load(Path(protagonist_path).read_text(encoding="utf-8"))


def new_game(campaign_path, protagonist_path=PROTAGONIST_YAML, hero: dict = None) -> GameState:
    camp = campaign_mod.load(campaign_path)
    proto = hero_sheet(campaign_path, protagonist_path)
    chars = [_character_from_sheet(proto.get("name", "Player"), proto,
                                   personality=proto.get("personality", ""),
                                   backstory=_protagonist_backstory(proto, camp),
                                   player_label="Player 1")]
    for p in camp.ai_party:
        c = _character_from_sheet(p["name"], p, controller="ai",
                                  personality=p.get("personality", ""),
                                  backstory=p.get("backstory", ""))
        c.id = unique_id({ch.id for ch in chars}, c.id)   # never collide (widget keys need it)
        chars.append(c)
    if hero:     # the player's own take on the character
        c = chars[0]
        c.name = str(hero.get("name") or c.name).strip()
        c.id = unique_id({ch.id for ch in chars[1:]}, slugify(c.name))
        c.personality = str(hero.get("personality", c.personality))
        c.backstory = str(hero.get("backstory", c.backstory))
        wanted = {k: int(v) for k, v in (hero.get("skills") or {}).items() if k in c.skills}
        if sum({**c.skills, **wanted}.values()) <= sum(c.skills.values()):      # no free points
            c.skills.update(wanted)
    system = rules.get_system(camp.rule_system)
    if not system.has_stress:   # no sanity track: nothing to show or report
        for c in chars:
            c.stress, c.max_stress = 0, 1
    if system.can_push:
        sheets = [proto] + list(camp.ai_party)
        for c, sheet in zip(chars, sheets):
            c.luck = int(sheet.get("stats", sheet).get("Luck", 50))
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
        self.events = []               # dice to show the player; the UI drains these per beat
        self.outcome = OUTCOME         # what to ask the keeper after the last human roll
        self._player_acted = False     # the next keeper call answers a free action: get a ruling first
        self.failed_skill = ""         # the dice just said no to this skill, so its clue stays hidden
        self._repair_character_ids()   # fix pre-fix saves with colliding ids (e.g. non-ASCII names)

    def _repair_character_ids(self):
        seen, remap = set(), {}
        for ch in self.state.characters:
            fixed = unique_id(seen, ch.id or slugify(ch.name))
            if fixed != ch.id:
                remap[ch.id] = fixed
                ch.id = fixed
            seen.add(fixed)
        if remap:
            if self.state.active_character_id in remap:
                self.state.active_character_id = remap[self.state.active_character_id]
            if self.state.pending_roll and self.state.pending_roll.get("character_id") in remap:
                self.state.pending_roll["character_id"] = remap[self.state.pending_roll["character_id"]]
            self.state.save()

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

    def drain_events(self) -> list:
        out, self.events = self.events, []
        return out

    def _outcome_prompt(self, skill, result) -> str:
        """A success with a scene clue's skill finds that clue: the dice decide, not the model's memory."""
        if not result.success:
            self.failed_skill = skill.lower()
            return f"{OUTCOME} The attempt failed, so it reveals no clue."
        self.failed_skill = ""
        scene = self.campaign.scene(self.state.scene_id) or {}
        for c in scene.get("clues", []):
            if c["id"] not in self.state.discovered_clues and (c.get("skill") or "").lower() == skill.lower():
                self.state.discovered_clues.append(c["id"])
                return f"{OUTCOME} This success uncovers a clue. Reveal it in the story now: {str(c.get('reveals', '')).strip()}"
        return OUTCOME

    def _record_roll(self, who, label, result, kind="skill"):
        """Count a roll for the end screen and queue it for the dice table."""
        s = self.state.stats
        s["rolls"] = s.get("rolls", 0) + 1
        if result.tier == "Critical Success":
            s["crits"] = s.get("crits", 0) + 1
        elif result.tier == "Fumble":
            s["fumbles"] = s.get("fumbles", 0) + 1
        self.events.append({"kind": kind, "who": who, "label": label, "roll": result.roll,
                            "tier": result.tier, "success": result.success, "detail": result.detail,
                            "dice": result.dice})

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
        self.state.rolls_since_action = 0
        self.failed_skill = ""
        self.state.messages.append({"role": "player", "name": char.name if char else None, "content": text})
        self.state.save()
        self._player_acted = True
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
        result = self.system.skill_check(pr["target"], pr.get("difficulty", "regular"),
                                         pr.get("bonus", 0), pr.get("penalty", 0))
        line = f"{char.name} — {pr['skill']}: {result.detail}"
        self.state.dice_log.append(line)
        self.state.pending_roll = None
        self._record_roll(char.name, pr["skill"], result)
        self.outcome = self._outcome_prompt(pr["skill"], result)
        if not result.success and result.tier != "Fumble" and self.system.can_push:
            need = self.system.need(pr["target"], pr.get("difficulty", "regular"))
            self.state.pending_push = {**pr, "roll": result.roll, "need": need, "luck_cost": result.roll - need}
        self.state.messages.append({"role": "dice", "name": char.name, "content": line})
        self.state.save()
        return result

    def accept_failure(self) -> str:
        """Take the failed roll as it stands. Returns what to ask the keeper."""
        self.state.pending_push = None
        self.state.save()
        return self.outcome

    def spend_luck(self):
        """Buy a failed roll up to a bare success, point for point. Returns the keeper prompt, or None."""
        p = self.state.pending_push
        char = self.state.get_character(p["character_id"]) if p else None
        if not char or p["luck_cost"] > char.luck:
            return None
        self._take_snapshot()
        char.luck -= p["luck_cost"]
        line = f"{char.name} — {p['skill']}: spent {p['luck_cost']} Luck ({p['roll']} becomes {p['need']}) -> Success"
        self.state.dice_log.append(line)
        self.state.messages.append({"role": "dice", "name": char.name, "content": line})
        self.state.pending_push = None
        self.state.save()
        won = SimpleNamespace(success=True)
        return self._outcome_prompt(p["skill"], won)

    def push_roll(self, text: str):
        """Try harder: one more roll, and failing it must cost something. Returns the RollResult."""
        p = self.state.pending_push
        if not p:
            return None
        self._take_snapshot()
        char = self.state.get_character(p["character_id"])
        self.state.messages.append({"role": "player", "name": char.name, "content": text})
        result = self.system.skill_check(p["target"], p.get("difficulty", "regular"),
                                         p.get("bonus", 0), p.get("penalty", 0))
        line = f"{char.name} — {p['skill']} (pushed): {result.detail}"
        self.state.dice_log.append(line)
        self.state.messages.append({"role": "dice", "name": char.name, "content": line})
        self.state.pending_push = None
        self._record_roll(char.name, f"{p['skill']} (pushed)", result)
        self.outcome = self._outcome_prompt(p["skill"], result)
        if not result.success:
            self.outcome += " This was a PUSHED roll and it failed: something seriously bad happens now."
        self.state.save()
        return result

    def begin_talk(self, character_id: str, text: str) -> list:
        """Say something in character WITHOUT committing to an action.
        Costs no turn, triggers no rolls, no scene changes. Returns the AI characters who may reply."""
        self._take_snapshot()
        char = self.state.get_character(character_id)
        if char:
            self.state.active_character_id = character_id
        self.state.messages.append({"role": "player", "name": char.name if char else None,
                                    "content": text})
        self.state.save()
        if self.state.party_mode == "solo":
            return []
        return [c for c in self.state.ai_characters() if c.status == "active"]

    def talk_steps(self, responders):
        """Generator: each AI companion answers conversationally, one beat at a time."""
        if not responders:
            self._finish_turn()
            return
        from agents.player_agent import PlayerAgent
        agent = PlayerAgent(self.llm, self.util_llm)
        for char in responders:
            yield f"💬 {char.name} answers…"
            reply = agent.take_turn(char, self.state, self.campaign, mode="talk")
            self.state.messages.append({"role": "companion", "name": char.name, "content": reply})
            self.state.save()
        self._finish_turn()

    def ask_keeper_ooc(self, question: str) -> str:
        """Out-of-character question to the Keeper (rules, recap, clarification).
        Changes nothing in the game — no rolls, no effects, no turn."""
        self.state.messages.append({"role": "ooc", "name": "You", "content": question})
        answer = self.keeper.answer_ooc(self.state, question)
        self.state.messages.append({"role": "ooc", "name": "Keeper", "content": answer})
        self.state.save()
        return answer

    def begin_negotiate(self, text: str) -> str:
        """Player argues for a different skill/approach instead of rolling."""
        self._take_snapshot()
        self.state.rolls_since_action = 0
        char = self.state.get_character(self.state.pending_roll["character_id"]) if self.state.pending_roll else None
        self.state.pending_roll = None
        self.state.messages.append({"role": "player", "name": char.name if char else None, "content": text})
        self.state.save()
        return f"(The player negotiates the pending roll instead of rolling): {text}"

    def launch_minigame(self, payload: dict):
        """Set the minigame gate: unique widget key + setting-appropriate default skin."""
        from core import minigames_catalog as mc
        payload = dict(payload)
        if payload.get("type") == "burn_reveal" and not payload.get("skin"):
            payload["skin"] = mc.DEFAULT_SKIN.get(mc.resolve_setting(self.campaign), "modern")
        self.state.minigame_count += 1
        self.state.pending_minigame = payload
        self.state.save()

    def begin_minigame_result(self, result_text: str) -> str:
        """Record the outcome of a minigame; the keeper picks up from it."""
        self._take_snapshot()
        self.state.rolls_since_action = 0
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
        for _ in self.keeper_steps(self.accept_failure()):
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
        char.id = unique_id({c.id for c in self.state.characters}, char.id)
        self.state.characters.append(char)
        self.state.dice_log.append(f"{char.name} joins the party ({controller}-controlled).")
        self.state.save()
        return char

    def transcript_md(self) -> str:
        """Full session transcript as Markdown (export)."""
        st = self.state
        lines = [f"# {self.campaign.title}", ""]
        for m in st.messages_archive + st.messages:
            who = m.get("name") or m["role"].capitalize()
            lines.append(f"**{who}:** {m['content']}\n")
        if st.dice_log:
            lines += ["---", "## Dice log", ""] + [f"- {l}" for l in st.dice_log]
        return "\n".join(lines)

    def roll_preview(self) -> dict:
        """What the pending roll needs, for the dice table."""
        pr = self.state.pending_roll
        if not pr:
            return None
        return {"need": self.system.roll_preview(pr["target"], pr.get("difficulty", "regular")),
                "chance": self.system.chance(pr["target"], pr.get("difficulty", "regular"),
                                             pr.get("bonus", 0), pr.get("penalty", 0))}

    def free_roll(self, expr: str):
        """Player rolls loose dice ('2d6+1') from the tray. Logged, changes nothing else."""
        m = re.fullmatch(r"\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*", expr or "", re.I)
        if not m or not validate_dice(expr):
            return None
        n, sides, mod = int(m[1] or 1), int(m[2]), int((m[3] or "0").replace(" ", ""))
        if not (1 <= n <= 8 and sides in (4, 6, 8, 10, 12, 20, 100)):
            return None
        vals = [parse_dice(f"1d{sides}") for _ in range(n)]
        total = sum(vals) + mod
        line = f"Free roll {expr.strip()}: {vals} = {total}"
        self.state.dice_log.append(line)
        self.state.save()
        dice = []
        for v in vals:
            if sides == 100:
                dice += [{"die": "d100", "value": (v % 100) // 10 * 10, "kept": True},
                         {"die": "d10", "value": v % 10, "kept": True}]
            else:
                dice.append({"die": f"d{sides}", "value": v, "kept": True})
        event = {"kind": "free", "who": "", "label": expr.strip(), "roll": total, "tier": "",
                 "success": True, "detail": line, "dice": dice}
        return event

    # --- inventory ---
    def _find_item(self, char, name: str):
        want = (name or "").strip().lower()
        for it in char.inventory:
            if it.lower() == want:
                return it
        for it in char.inventory:
            if want and (want in it.lower() or it.lower() in want):
                return it
        return None

    def give_item(self, from_id: str, to_id: str, item: str) -> bool:
        a, b = self.state.get_character(from_id), self.state.get_character(to_id)
        found = self._find_item(a, item) if a else None
        if not (found and b):
            return False
        a.inventory.remove(found)
        b.inventory.append(found)
        if found in a.item_notes:
            b.item_notes[found] = a.item_notes.pop(found)
        self.state.dice_log.append(f"[item] {a.name} gives {found} to {b.name}")
        self.state.save()
        return True

    def drop_item(self, char_id: str, item: str) -> bool:
        ch = self.state.get_character(char_id)
        found = self._find_item(ch, item) if ch else None
        if not found:
            return False
        ch.inventory.remove(found)
        ch.item_notes.pop(found, None)
        self.state.dice_log.append(f"[item] {ch.name} drops {found}")
        self.state.save()
        return True

    def inspect_item(self, char_id: str, item: str) -> str:
        """Describe an item once (cheap model), remembered after that. Costs no turn."""
        ch = self.state.get_character(char_id)
        found = self._find_item(ch, item) if ch else None
        if not found:
            return ""
        if found not in ch.item_notes:
            lang = {"zh": "Traditional Chinese", "yue": "Cantonese written in Traditional Chinese",
                    "en": "English"}.get(self.state.language, "the same language as the item's name")
            note = check_llm(self.util_llm.chat(
                [{"role": "user", "content": f"Setting: {self.campaign.title}. Holder: {ch.name}. "
                                             f"Item: {found}. Language: {lang}."}],
                system_prompt=ITEM_PROMPT, temperature=0.6, max_tokens=120))
            ch.item_notes[found] = (note or "").strip()
            self.state.save()
        return ch.item_notes[found]

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
            rule, self._player_acted = self._player_acted, False
            narrative, ctrl = yield from self.keeper.respond_steps(self.state, input_text, rule=rule)
            if self.keeper.local:
                self.keeper.bookkeep(self.state, narrative, ctrl, self.util_llm)
            if narrative:
                self.state.messages.append({"role": "keeper", "content": narrative})
            self._apply_effects(ctrl)
            actors_requested.extend(ctrl.characters_act)
            self.state.save()
            if self.state.ending:
                return

            if ctrl.minigame and not ctrl.roll_request:
                self.launch_minigame(ctrl.minigame)
                return  # gate: wait for the player to play it out

            if not ctrl.roll_request:
                break
            char, skill, target = self._resolve_roll_target(ctrl.roll_request)
            difficulty = ctrl.roll_request.get("difficulty") or "regular"
            bonus = _roll_mod(ctrl.roll_request, "bonus", "bonus_dice", "advantage")
            penalty = _roll_mod(ctrl.roll_request, "penalty", "penalty_dice", "disadvantage")
            if char.controller == "human" and char.status == "active":
                if self.state.rolls_since_action >= 2:
                    # chain guard: one player action shouldn't spiral into endless keeper rolls
                    self.state.dice_log.append(
                        f"[guard] keeper wanted a 3rd consecutive roll ({skill}) — declined, "
                        "narration stands")
                    self.state.save()
                    break
                self.state.rolls_since_action += 1
                self.state.pending_roll = {
                    "character_id": char.id, "skill": skill, "target": target,
                    "difficulty": difficulty, "reason": ctrl.roll_request.get("reason", ""),
                    "bonus": bonus, "penalty": penalty,
                }
                self.state.save()
                return  # gate: wait for the human to roll

            yield f"🎲 {char.name} rolls {skill}…"
            result = self.system.skill_check(target, difficulty, bonus, penalty)
            line = f"{char.name} — {skill}: {result.detail}"
            self.state.dice_log.append(line)
            self.state.messages.append({"role": "dice", "name": char.name, "content": line})
            self._record_roll(char.name, skill, result)
            self.state.save()
            yield "The Keeper narrates the outcome…"
            input_text = self._outcome_prompt(skill, result)

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
                skill = (self.campaign.clue(cid).get("skill") or "").lower()
                if not self.failed_skill or skill != self.failed_skill:
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
                    roll = self.system.last_stress
                    self.events.append({"kind": "stress", "who": char.name, "label": "Mind",
                                        "roll": roll["roll"], "success": roll["passed"],
                                        "tier": "Success" if roll["passed"] else "Failure",
                                        "detail": line, "dice": roll["dice"]})
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
            raw = str(ctrl.hp_change.get("amount", 0)).replace(" ", "")
            sign = -1 if raw.startswith("-") else 1
            try:
                amount = sign * parse_dice(raw.lstrip("+-"))   # "-1d6" rolled here, "-3" taken as is
            except ValueError:
                amount = 0
                st.dice_log.append(f"[warn] keeper sent unreadable hp amount {raw!r} — ignored")
            if char and amount:
                was_down = char.hp == 0
                char.hp = max(0, min(char.max_hp, char.hp + amount))
                st.dice_log.append(f"{char.name} HP {'+' if amount > 0 else ''}{amount} -> {char.hp}/{char.max_hp}")
                if char.hp == 0 and char.status == "active":
                    char.status = "unconscious"
                    st.dice_log.append(f"{char.name} collapses.")
                elif char.hp == 0 and was_down and amount < 0 and char.status == "unconscious":
                    char.status = "dead"
                    st.dice_log.append(f"{char.name} dies.")
                elif char.hp > 0 and char.status == "unconscious":
                    char.status = "active"
                    st.dice_log.append(f"{char.name} comes to.")

        if ctrl.inventory_change:
            ic = ctrl.inventory_change
            char = st.get_character(ic.get("character", "")) or st.active_character()
            if char:
                for it in ic.get("add") or []:
                    name = it.get("name") if isinstance(it, dict) else it
                    if name and str(name) not in char.inventory:
                        char.inventory.append(str(name))
                        st.dice_log.append(f"[item] {char.name} gains {name}")
                for it in ic.get("remove") or []:
                    found = self._find_item(char, str(it))
                    if found:
                        char.inventory.remove(found)
                        st.dice_log.append(f"[item] {char.name} loses {found}")

        before = st.scene_id
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

        if st.scene_id != before:
            st.stats["scene_since"] = st.turn_count     # pacing: how long the party has been here

        if ctrl.ending and not st.ending:
            known = {e.get("outcome"): e.get("description", "") for e in self.campaign.endings}
            st.ending = {"outcome": ctrl.ending, "description": known.get(ctrl.ending, "")}

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
        agent = PlayerAgent(self.llm, self.util_llm)
        actions = []
        for char in actors:
            yield f"🎭 {char.name} decides what to do…"
            action = agent.take_turn(char, st, self.campaign)
            st.messages.append({"role": "companion", "name": char.name, "content": action})
            st.save()
            actions.append(f"{char.name}: {action}")
        yield "The Keeper resolves the party's actions…"
        wrap = ("COMPANION ACTIONS this turn (the players have ALREADY read these — do not repeat, "
                "re-quote, or re-narrate them):\n" + "\n".join(actions) +
                "\nOnly add the WORLD'S reaction and any consequences, and call a roll "
                "(roll_request) if a companion attempted something uncertain.")
        if st.companion_style == "player":
            wrap += (" Keep it tight — 1-3 sentences. Do NOT expand their actions into prose or add "
                     "dialogue for them; they are players who speak for themselves.")
        yield from self._keeper_cycle_steps(wrap, allow_companions=False)

    def _finish_turn(self):
        if not self.state.pending_roll and not self.state.pending_minigame and not self.state.ending:
            memory.maybe_compact(self.state, self.util_llm)
        self.state.save()
