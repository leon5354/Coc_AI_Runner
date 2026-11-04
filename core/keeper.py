"""The Keeper (GM): assembles full-context LLM calls and parses hybrid prose+JSON responses."""
import json
import re
from dataclasses import dataclass, field

from core import minigames_catalog
from core.llm_client import check_llm

CONTROL_KEYS = {"roll_request", "stress_check", "hp_change", "clues_discovered",
                "scene_transition", "characters_act", "minigame", "inventory_change", "ending"}

MINIGAME_TYPES = minigames_catalog.types()

RECENT_WINDOW = 20  # messages sent verbatim


@dataclass
class Partial:
    """Narration so far, while the Keeper is still talking. Not a beat of its own."""
    text: str


@dataclass
class Control:
    roll_request: dict = None      # {character, skill, difficulty, reason, bonus?, penalty?}
    stress_check: dict = None      # {character, event_id, loss}
    hp_change: dict = None         # {character, amount, reason}
    clues_discovered: list = field(default_factory=list)
    scene_transition: str = None
    characters_act: list = field(default_factory=list)
    minigame: dict = None          # {type, ...payload}
    inventory_change: dict = None  # {character, add: [..], remove: [..]}
    ending: str = None             # outcome of the campaign ending just reached

    @classmethod
    def empty(cls):
        return cls()


OUTPUT_CONTRACT = '''=== OUTPUT FORMAT (MANDATORY) ===
Write your narrative as normal prose. Then end EVERY response with exactly one fenced json block:

```json
{"roll_request": null, "stress_check": null, "hp_change": null, "inventory_change": null,
 "clues_discovered": [], "scene_transition": null, "characters_act": [], "minigame": null, "ending": null}
```

Field meanings (use null / [] when not applicable this turn):
- roll_request: ask a character to roll. {"character": "<id>", "skill": "<skill name>", "difficulty": "<level>", "reason": "<why>"}
  When you request a roll, END the narrative at the moment of tension — the outcome comes after the roll.
- stress_check: a character faces horror. {"character": "<id>", "event_id": "<scripted event id or null>", "loss": "<expr like 0/1d4>"}
  Optional in roll_request: "bonus": 1 (favourable) or "penalty": 1 (unfavourable), up to 2.
- hp_change: physical harm or healing. {"character": "<id>", "amount": "<dice or number>", "reason": "..."}
  Prefer dice so the engine rolls it: "-1d6", "-1d8+1"; healing "+1d4"; or a plain number like -2.
- inventory_change: items gained or lost in the fiction. {"character": "<id>", "add": ["<item>"], "remove": ["<item>"]}
  Use it whenever someone picks up, is handed, uses up, or loses something that matters.
- clues_discovered: list of scripted clue ids the characters just uncovered.
- scene_transition: the scripted scene id the party moves to (must be one of the listed exits), else null.
- characters_act: ids of AI-controlled companions who should act next turn (only when their action matters).
- minigame: an OPTIONAL dramatic device. Use SPARINGLY (at most once per scene), only when the fiction
  naturally calls for it, and NEVER together with roll_request. One of:
  {minigame_contract}
  After the minigame you will receive a MINIGAME RESULT message; continue the story from it.
- ending: when the story truly concludes, the outcome name of the ending reached (from the
  campaign's possible endings). Write the closing narration in the same message. Otherwise null.

Worked example:
The floorboards groan as you kneel. Something glints between them — but the light is failing fast.

```json
{"roll_request": {"character": "player", "skill": "Spot Hidden", "difficulty": "regular", "reason": "searching the parlor floor"},
 "stress_check": null, "hp_change": null, "clues_discovered": [], "scene_transition": null, "characters_act": []}
```'''

CONDUCT_REST = """- Prioritize player agency: let them try anything; consequences, not refusals.
- MATURE THEMES: this is adult horror. Do not sanitize violence, madness, or dread.
- Describe scenes with visceral sensory detail (smell, sound, touch).
- NEVER expose internal ids (clue ids, scene ids, event ids) in the narrative — they belong
  only in the json control block. In prose, describe things naturally.
- DICE ARE NOT YOURS TO ROLL. You never roll dice, and you NEVER write a die number, a d100/d20
  value, a target number, a degree of success, or a "success/failure" verdict in your prose —
  the game engine rolls the real dice, not you. Writing "d100=47" or "檢定成功" yourself is a
  hallucination and is forbidden. Do NOT invent "hidden" or "background" rolls either.
- When an action's outcome is UNCERTAIN and CONSEQUENTIAL — an attack or any combat, resisting
  corruption/temptation/fear, forcing something, a key skill or willpower check, anything with
  real stakes — you MUST put a roll_request in the control block and END your narration at the
  moment of tension, without stating whether it worked. The engine rolls, then sends you a
  "ROLL RESULT: ..." message; ONLY THEN do you narrate the outcome. If in doubt, request the roll.
- End narration with a hook or "What do you do?" unless a roll is pending.
- One roll at a time. After a ROLL RESULT message, narrate the outcome vividly — success with
  flair, failure with complication, fumble with disaster — then STOP and hand the scene back to
  the player. Do NOT chain another roll_request onto a roll outcome unless the failure itself
  physically forces a new immediate danger, and never more than one such follow-up. One player
  action = one roll."""


def character_authority_clause(state) -> str:
    """Who the Keeper may vs must-not speak/act for — the core 'don't play other players' rule.
    Human characters are always off-limits. AI companions are off-limits too when they play as
    real players (player companion_style + they act on their own turns); the Keeper voices them
    as NPCs only in solo mode or cinematic style."""
    if state is None:
        return "- NEVER decide, speak, or act for a HUMAN-controlled character. Narrate the world, then stop."
    humans = [c.name for c in state.characters if c.controller == "human"]
    ai = [c.name for c in state.characters if c.controller == "ai"]
    treat_ai_as_players = (getattr(state, "companion_style", "player") == "player"
                           and state.party_mode != "solo")
    protected = humans + (ai if treat_ai_as_players else [])
    npc_companions = [n for n in ai if n not in protected]

    lines = []
    if protected:
        lines.append(f"- NEVER decide, speak, or act for these PLAYER characters: {', '.join(protected)}. "
                     "They are controlled by their own players. You may narrate the RESULT of an action a "
                     "player has ALREADY declared, but never invent their dialogue, decisions, or feelings.")
    if treat_ai_as_players and ai:
        lines.append(f"- The companions {', '.join(ai)} are AI PLAYERS this session — NOT NPCs you voice. "
                     "In your narration give them ZERO dialogue, ZERO invented actions, AND ZERO described "
                     "inner states — do not describe their feelings, thoughts, breathing, heartbeat, "
                     "expressions, blushing, trembling, or any emotional or bodily reaction. You cannot see "
                     "inside them and their body is theirs to portray, not yours. Refer to them only by what "
                     "the world and your own NPCs do TO or AROUND them. If you want one to react, speak, or "
                     "act, DO NOT write it — put their exact id in \"characters_act\" and stop; their own "
                     "player then takes a turn. Voicing or puppeteering them is the single worst mistake you can make.")
    if npc_companions:
        lines.append(f"- You MAY voice these companions as NPCs (speak and act for them naturally): "
                     f"{', '.join(npc_companions)}.")
    return "\n".join(lines)


def build_conduct(state) -> str:
    return "=== RULES OF CONDUCT ===\n" + character_authority_clause(state) + "\n" + CONDUCT_REST

LANGUAGE_BLOCKS = {
    "auto": """=== LANGUAGE (STRICT) ===
Detect and mirror the player's input language:
- English input -> respond in English.
- Chinese/Cantonese input -> respond in Traditional Chinese (繁體中文);
  narration in written Chinese (書面語), NPC dialogue in colloquial Cantonese (廣東話口語).""",
    "en": """=== LANGUAGE (STRICT) ===
Respond ONLY in English, regardless of the language the player writes in.""",
    "zh": """=== LANGUAGE (STRICT) ===
Respond ONLY in Traditional Chinese (繁體中文), regardless of the language the player writes in.
Both narration and NPC dialogue use standard written Chinese (書面語).""",
    "yue": """=== LANGUAGE (STRICT) ===
Respond ONLY in Traditional Chinese (繁體中文), regardless of the language the player writes in.
Narration (story/environment): formal written Chinese (書面語).
ALL spoken dialogue (NPCs and characters): colloquial Cantonese (廣東話口語).
Example dialogue: 「你做咩喺度行嚟行去呀？快啲走啦！」""",
}

LANGUAGE_LABELS = {"auto": "Auto-detect", "en": "English", "zh": "繁體中文", "yue": "廣東話"}


def language_block(language: str) -> str:
    return LANGUAGE_BLOCKS.get(language, LANGUAGE_BLOCKS["auto"])


GOD_MODE_BLOCK = """=== GOD MODE (ACTIVE) ===
The player is favored by the narrative itself. Overrides normal conduct where they conflict:
- NEVER block, refuse, or deflect the player's stated intent. Accommodate it, then weave
  consequences and story around it. "Yes, and..." is your only valid opening move.
- Bias outcomes in the player's favor; call for rolls only when the drama makes failure fun.
- NPCs and companions are receptive and cooperative with whatever direction the player takes,
  while keeping their voices. The world bends; it does not break the player's fantasy."""


def build_system_prompt(campaign, system, language: str = "auto", god_mode: bool = False,
                        state=None) -> str:
    setting = minigames_catalog.resolve_setting(campaign)
    contract = OUTPUT_CONTRACT.replace("{minigame_contract}",
                                       minigames_catalog.contract_block(setting))
    endings = "\n".join(f"- {e.get('outcome')}: {e.get('description')}" for e in campaign.endings)
    brief = [f"Title: {campaign.title}",
             f"The truth: {campaign.plot_outline}"]
    if campaign.data.get("canon"):
        brief.append("Setting canon (stay faithful to this established world):\n"
                     + campaign.data["canon"])
    if campaign.data.get("tone"):
        brief.append(f"Tone: {campaign.data['tone']}")
    npcs = campaign.data.get("npcs") or []
    if npcs:
        brief.append("Key NPCs (roleplay them consistently):")
        for n in npcs:
            brief.append(f"  - {n.get('name')}: {n.get('role', '')}. Motivation: {n.get('motivation', '')}. "
                         f"Secret: {n.get('secret', 'none')}. Voice: {n.get('voice', '')}")
    escalation = campaign.data.get("escalation") or []
    if escalation:
        brief.append("Escalation clock (advance these beats as the story stalls or time passes):")
        for i, beat in enumerate(escalation, 1):
            brief.append(f"  {i}. {beat}")
    brief.append(f"Possible endings:\n{endings}")

    return f"""You are the KEEPER (Game Master) running a tabletop horror scenario.

{system.keeper_rules_prompt()}

{language_block(language)}

{build_conduct(state)}

{GOD_MODE_BLOCK if god_mode else ""}

{contract}

=== CAMPAIGN BRIEF (KEEPER EYES ONLY) ===
{chr(10).join(brief)}"""


def build_state_block(state, campaign, nudge: bool = False) -> str:
    scene = campaign.scene(state.scene_id) or {}
    lines = [f"=== GAME STATE (turn {state.turn_count}) ==="]
    lines.append(f"Current scene: {scene.get('id')} — {scene.get('name')}")
    lines.append(f"Scene description: {scene.get('description', '').strip()}")

    undiscovered = [c for c in scene.get("clues", []) if c["id"] not in state.discovered_clues]
    if undiscovered:
        lines.append("Undiscovered clues in this scene (do NOT reveal contents until discovered):")
        for c in undiscovered:
            lines.append(f"  - id={c['id']}: {c['description']} (skill: {c.get('skill')}, difficulty: {c.get('difficulty', 'regular')})")

    pending_events = [e for e in scene.get("stress_events", []) if e["id"] not in state.triggered_events]
    if pending_events:
        lines.append("Untriggered stress events in this scene:")
        for e in pending_events:
            lines.append(f"  - id={e['id']}: {e.get('trigger')} (loss: {e.get('loss')})")

    if scene.get("keeper_notes"):
        lines.append(f"Keeper notes for this scene (private): {scene['keeper_notes']}")

    exits = scene.get("exits", [])
    if exits:
        lines.append("Exits: " + "; ".join(f"{x['to']} ({x.get('condition', '')})" for x in exits))

    if state.discovered_clues:
        lines.append("Clues discovered so far:")
        for cid in state.discovered_clues:
            clue = campaign.clue(cid)
            if clue:
                lines.append(f"  - {cid}: {clue.get('reveals', '').strip()}")

    lines.append(f"Party (party_mode={state.party_mode}):")
    for ch in state.characters:
        skills = ", ".join(f"{k} {v}" for k, v in sorted(ch.skills.items(), key=lambda kv: -kv[1])[:6])
        inv = ", ".join(ch.inventory) or "nothing"
        lines.append(f"  - id={ch.id} {ch.name} [{ch.controller}-controlled, {ch.status}] "
                     f"HP {ch.hp}/{ch.max_hp}{f', Stress {ch.stress}/{ch.max_stress}' if ch.max_stress > 1 else ''}; "
                     f"skills: {skills}; carrying: {inv}")
        if ch.personality:
            lines.append(f"      personality: {ch.personality}")
        if ch.backstory:
            lines.append(f"      background: {ch.backstory}")
    lines.append("Use each character's background and personality: tie the horror to their history, "
                 "have NPCs react to who they are, and let their past surface in what they notice.")

    if state.summary:
        lines.append("=== STORY SO FAR ===")
        lines.append(state.summary)

    if nudge:
        lines.append("REMINDER: end your response with the mandatory ```json control block.")

    return "\n".join(lines)


def build_messages(state, campaign, system, user_input: str, nudge: bool = False) -> list:
    msgs = [{"role": "user", "content": build_state_block(state, campaign, nudge)}]
    for m in state.messages[-RECENT_WINDOW:]:
        role = "assistant" if m["role"] == "keeper" else "user"
        name = m.get("name")
        content = f"{name}: {m['content']}" if name and role == "user" else m["content"]
        if m["role"] == "ooc":
            content = f"[OUT OF CHARACTER — table talk, not story events] {content}"
        msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_input})
    return msgs


OOC_PROMPT = """You are the KEEPER, stepping OUT of the fiction to answer the player directly,
as a friendly game master at the table would.

- Answer their question plainly and briefly (rules, a recap of what they know, what their
  options are, what a skill does, who an NPC was).
- You may remind them of facts their character would know.
- Do NOT advance the story, do NOT narrate events, do NOT ask for rolls, and do NOT reveal
  secrets they have not discovered — hint at what they could pursue instead.
- NEVER roll dice or write a die result here. If they ask about dice, explain that real rolls
  happen in normal play: when their action needs a check you request one, and they roll it with
  the 3D dice tool — you cannot roll for them and you never make up numbers.
- No JSON block. Just talk to them."""


# where the control block starts, even if the model forgets the fence or changes the key order
_HIDE_RE = re.compile(r'```|\{\s*"?[a-z_]*"?\s*:?\s*$|\{\s*"(?:' + "|".join(sorted(CONTROL_KEYS)) + r')"')
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _last_balanced_json(text: str):
    """Find the last balanced {...} at/near the end of text that mentions a known key."""
    end = text.rfind("}")
    while end != -1:
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    candidate = text[start:end + 1]
                    if any(k in candidate for k in CONTROL_KEYS):
                        try:
                            return json.loads(candidate), start
                        except json.JSONDecodeError:
                            break
                    break
        end = text.rfind("}", 0, max(end - 1, 0)) if end > 0 else -1
    return None, -1


def parse_response(text: str):
    """Returns (narrative, Control). Never raises — malformed control degrades to pure narration."""
    if not text:
        return "", Control.empty()

    data, narrative = None, text
    fences = _FENCE_RE.findall(text)
    if fences:
        try:
            data = json.loads(fences[-1])
            narrative = _FENCE_RE.sub("", text).strip()
        except json.JSONDecodeError:
            data = None
    if data is None:
        data, start = _last_balanced_json(text)
        if data is not None:
            narrative = text[:start].strip()

    narrative = narrative.replace("[ROLL_REQUIRED]", "").strip()
    narrative = re.sub(r"\s*```\w*\s*$", "", narrative)   # a fence the model opened and never used
    if not isinstance(data, dict):
        return narrative, Control.empty()

    mg = data.get("minigame")
    if not (isinstance(mg, dict) and mg.get("type") in MINIGAME_TYPES):
        mg = None

    ctrl = Control(
        roll_request=data.get("roll_request") if isinstance(data.get("roll_request"), dict) else None,
        stress_check=data.get("stress_check") if isinstance(data.get("stress_check"), dict) else None,
        hp_change=data.get("hp_change") if isinstance(data.get("hp_change"), dict) else None,
        clues_discovered=[c for c in data.get("clues_discovered") or [] if isinstance(c, str)],
        scene_transition=data.get("scene_transition") if isinstance(data.get("scene_transition"), str) else None,
        characters_act=[c for c in data.get("characters_act") or [] if isinstance(c, str)],
        minigame=mg,
        inventory_change=data.get("inventory_change") if isinstance(data.get("inventory_change"), dict) else None,
        ending=data.get("ending") if isinstance(data.get("ending"), str) and data.get("ending") else None,
    )
    return narrative, ctrl


REFEREE_PROMPT = """You are the rules referee of a tabletop game. You never tell the story.
Read what the player just did and answer with JSON only:
{"roll": "<skill from the list, or null>", "difficulty": "<level>", "bonus": 0, "penalty": 0,
 "move_to": "<exit id, or null>", "device": "<puzzle device, or null>", "ending": "<outcome, or null>"}
Call a roll whenever the outcome is uncertain and failing would matter: searching for something
hidden, fighting, sneaking, persuading or lying, resisting, forcing, climbing, reading something
dangerous. No roll for plain talk or a safe, simple action.
Use bonus 1 for a clear advantage and penalty 1 for a clear disadvantage. Otherwise 0.
Set move_to only when the player clearly goes to that place now.
Set device only when this moment clearly is one of the puzzle devices, or the keeper notes ask for
it now: for example a coded text, a keypad or dial, blank paper near heat. Usually null. A device
replaces the roll, so leave roll null when you set it.
Set ending only if endings are listed and the player's action truly decides how the story ends."""

DEVICE_PROMPT = """You prepare one puzzle for a tabletop game. Answer with JSON only, using the same
keys as the example, with new content that fits this story and scene. Keep it short. Write the
player-facing text in the same language as the story."""

# what a device can't work without; everything else has a sensible default
DEVICE_NEEDS = {"hidden_text", "ciphertext", "solution", "code", "sequence", "wires", "correct", "message"}

# History holds the narration without its json, so weaker models copy that and drop the block.
LOCAL_REMINDER = "\n\n(Keep this reply under 130 words, or 220 Chinese characters. End it with the ```json control block.)"


class Keeper:
    def __init__(self, llm_client, campaign, system):
        self.llm = llm_client
        self.campaign = campaign
        self.system = system
        self.parse_failures = 0

    def answer_ooc(self, state, question: str) -> str:
        """Answer a table question out of character. Never touches game state."""
        msgs = build_messages(state, self.campaign, self.system, question)
        system_prompt = (OOC_PROMPT + "\n\n" + language_block(state.language)
                         + f"\n\n=== WHAT YOU KNOW (KEEPER EYES ONLY — do not spoil) ===\n"
                           f"{self.campaign.plot_outline}")
        return check_llm(self.llm.chat(msgs, system_prompt=system_prompt, temperature=0.5,
                                       max_tokens=600)) or ""

    @property
    def local(self) -> bool:
        return getattr(self.llm, "provider", "") == "ollama"

    def referee(self, state, action: str):
        """Ask one plain rules question before the story is written. Models that lose track of the
        rules while narrating answer this reliably. Returns a ruling dict, or None to carry on without."""
        ch = state.active_character() or state.characters[0]
        scene = self.campaign.scene(state.scene_id) or {}
        clues = [f"{c.get('skill')}: {c.get('description')}" for c in scene.get("clues", [])
                 if c["id"] not in state.discovered_clues]
        exits = [f"{x['to']} ({x.get('condition', '')})" for x in scene.get("exits", [])]
        prompt = (f"Player's action: {action}\n"
                  f"Scene: {scene.get('name')}. {str(scene.get('description', '')).strip()[:300]}\n"
                  f"Skills of {ch.name}: {', '.join(ch.skills)}\n"
                  f"Difficulty levels: {', '.join(self.system.difficulty_levels)}\n"
                  f"Things to find here: {'; '.join(clues) or 'nothing special'}\n"
                  f"Exits: {'; '.join(exits) or 'none'}\n"
                  f"Puzzle devices: {', '.join(minigames_catalog.for_setting(minigames_catalog.resolve_setting(self.campaign)))}\n"
                  f"Keeper notes: {str(scene.get('keeper_notes', '')).strip()[:300]}")
        if not scene.get("exits"):        # the last scene: the story can end here
            prompt += "\nEndings: " + "; ".join(f"{e.get('outcome')} ({e.get('description')})" for e in self.campaign.endings)
        try:
            data = json.loads(self.llm.get_completion(prompt, system_prompt=REFEREE_PROMPT, temperature=0.1,
                                                      max_tokens=120, json_mode=True))
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def device(self, state, game: str, action: str):
        """Ask for a device's contents as its own small job. Returns the payload, or None."""
        sample = minigames_catalog.sample(game)
        scene = self.campaign.scene(state.scene_id) or {}
        told = next((m["content"] for m in reversed(state.messages) if m["role"] == "keeper"), "")
        prompt = (f"Device: {game}. {minigames_catalog.CATALOG[game]['contract']}\n"
                  f"Example: {json.dumps(sample, ensure_ascii=False)}\n"
                  f"Scene: {scene.get('name')}. Keeper notes: {scene.get('keeper_notes', '')}\n"
                  f"Story so far: {told[-500:]}\nThe player: {action}")
        try:
            data = json.loads(self.llm.get_completion(prompt, system_prompt=DEVICE_PROMPT, temperature=0.5,
                                                      max_tokens=500, json_mode=True))
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict) or not all(data.get(k) for k in DEVICE_NEEDS & set(sample)):
            return None
        return {**data, "type": game}

    def respond_steps(self, state, user_input: str, rule: bool = False):
        """One keeper turn, as a generator: yields Partial text, returns (narrative, Control).
        rule=True: the player just acted, so a local model gets a referee ruling first."""
        ruling = self.referee(state, user_input) if rule and self.local else None
        roll = (ruling or {}).get("roll")
        roll = roll if isinstance(roll, str) and roll.lower() not in ("", "null", "none") else None
        move = (ruling or {}).get("move_to")
        exits = {x["to"] for x in (self.campaign.scene(state.scene_id) or {}).get("exits", [])}
        move = move if move in exits and not roll else None
        game = (ruling or {}).get("device")
        fits = minigames_catalog.for_setting(minigames_catalog.resolve_setting(self.campaign))
        puzzle = None
        if game in fits and state.stats.get("device_scene") != state.scene_id:   # one per scene at most
            puzzle = self.device(state, game, user_input)
        if puzzle:
            roll = move = None
        ending = (ruling or {}).get("ending")
        ending = ending if ending in {e.get("outcome") for e in self.campaign.endings} and not exits else None
        if ending:
            roll = move = puzzle = None
        nudge = self.parse_failures >= 2
        msgs = build_messages(state, self.campaign, self.system, user_input, nudge)
        if self.local:
            if roll:
                msgs[-1]["content"] += (f"\n\n(The rules call for a {roll} roll. Narrate only up to the moment "
                                        "of tension, then STOP. Do not say how it turns out.)")
            elif move:
                msgs[-1]["content"] += f"\n\n(The party now moves to: {(self.campaign.scene(move) or {}).get('name')}. Describe arriving there.)"
            elif ending:
                told = next(e for e in self.campaign.endings if e.get("outcome") == ending)
                msgs[-1]["content"] += f"\n\n(The story ends now: {told.get('description')} Write the closing scene.)"
            elif puzzle:
                msgs[-1]["content"] += ("\n\n(A puzzle is about to start. Lead up to it in 1-3 sentences and STOP. "
                                        "Do not solve it, and do not give the answer.)")
            msgs[-1]["content"] += LOCAL_REMINDER
        system_prompt = build_system_prompt(self.campaign, self.system, state.language,
                                             state.god_mode, state=state)
        if hasattr(self.llm, "stream"):
            raw = ""
            for piece in self.llm.stream(msgs, system_prompt=system_prompt):
                raw += piece
                shown = _HIDE_RE.split(raw, 1)[0]
                yield Partial(shown.replace("[ROLL_REQUIRED]", ""))
        else:
            raw = check_llm(self.llm.chat(msgs, system_prompt=system_prompt))
        narrative, ctrl = parse_response(raw)
        if roll and not ctrl.roll_request:
            ctrl.roll_request = {"character": state.active_character_id, "skill": roll,
                                 "difficulty": ruling.get("difficulty"), "reason": "",
                                 "bonus": ruling.get("bonus"), "penalty": ruling.get("penalty")}
        if move and not ctrl.scene_transition:
            ctrl.scene_transition = move
        if ending:
            ctrl.ending, ctrl.roll_request, ctrl.minigame = ending, None, None
        if puzzle:
            ctrl.minigame, ctrl.roll_request = ctrl.minigame or puzzle, None
            state.stats["device_scene"] = state.scene_id
        if ctrl == Control.empty() and "```" not in (raw or ""):
            self.parse_failures += 1
        else:
            self.parse_failures = 0
        return narrative, ctrl
