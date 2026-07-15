"""The Keeper (GM): assembles full-context LLM calls and parses hybrid prose+JSON responses."""
import json
import re
from dataclasses import dataclass, field

from core import minigames_catalog

CONTROL_KEYS = {"roll_request", "stress_check", "hp_change", "clues_discovered",
                "scene_transition", "characters_act", "minigame"}

MINIGAME_TYPES = minigames_catalog.types()

RECENT_WINDOW = 20  # messages sent verbatim


@dataclass
class Control:
    roll_request: dict = None      # {character, skill, difficulty, reason}
    stress_check: dict = None      # {character, event_id, loss}
    hp_change: dict = None         # {character, amount, reason}
    clues_discovered: list = field(default_factory=list)
    scene_transition: str = None
    characters_act: list = field(default_factory=list)
    minigame: dict = None          # {type, ...payload}

    @classmethod
    def empty(cls):
        return cls()


OUTPUT_CONTRACT = '''=== OUTPUT FORMAT (MANDATORY) ===
Write your narrative as normal prose. Then end EVERY response with exactly one fenced json block:

```json
{"roll_request": null, "stress_check": null, "hp_change": null,
 "clues_discovered": [], "scene_transition": null, "characters_act": [], "minigame": null}
```

Field meanings (use null / [] when not applicable this turn):
- roll_request: ask a character to roll. {"character": "<id>", "skill": "<skill name>", "difficulty": "<level>", "reason": "<why>"}
  When you request a roll, END the narrative at the moment of tension — the outcome comes after the roll.
- stress_check: a character faces horror. {"character": "<id>", "event_id": "<scripted event id or null>", "loss": "<expr like 0/1d4>"}
- hp_change: physical harm or healing. {"character": "<id>", "amount": <negative for damage>, "reason": "..."}
- clues_discovered: list of scripted clue ids the characters just uncovered.
- scene_transition: the scripted scene id the party moves to (must be one of the listed exits), else null.
- characters_act: ids of AI-controlled companions who should act next turn (only when their action matters).
- minigame: an OPTIONAL dramatic device. Use SPARINGLY (at most once per scene), only when the fiction
  naturally calls for it, and NEVER together with roll_request. One of:
  {minigame_contract}
  After the minigame you will receive a MINIGAME RESULT message; continue the story from it.

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
- One roll at a time. After a ROLL RESULT message, narrate the outcome vividly — success with flair, failure with complication, fumble with disaster."""


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
                     f"HP {ch.hp}/{ch.max_hp}, Stress {ch.stress}/{ch.max_stress}; skills: {skills}; carrying: {inv}")
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
    )
    return narrative, ctrl


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
        return self.llm.chat(msgs, system_prompt=system_prompt, temperature=0.5, max_tokens=600) or ""

    def respond(self, state, user_input: str):
        """One keeper turn. Returns (narrative, Control)."""
        nudge = self.parse_failures >= 2
        msgs = build_messages(state, self.campaign, self.system, user_input, nudge)
        system_prompt = build_system_prompt(self.campaign, self.system, state.language,
                                             state.god_mode, state=state)
        raw = self.llm.chat(msgs, system_prompt=system_prompt)
        narrative, ctrl = parse_response(raw)
        if ctrl == Control.empty() and "```" not in (raw or ""):
            self.parse_failures += 1
        else:
            self.parse_failures = 0
        return narrative, ctrl
