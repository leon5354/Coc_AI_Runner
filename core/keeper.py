"""The Keeper (GM): assembles full-context LLM calls and parses hybrid prose+JSON responses."""
import json
import re
from dataclasses import dataclass, field

CONTROL_KEYS = {"roll_request", "stress_check", "hp_change", "clues_discovered",
                "scene_transition", "characters_act", "minigame"}

MINIGAME_TYPES = {"burn_reveal", "cipher", "seance", "combination_lock", "tarot_draw"}

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
  {"type": "burn_reveal", "hidden_text": "<the secret message>", "context": "<what the players hold>", "skin": "parchment"}
    — a suspicious surface held to heat/light reveals hidden writing.
    skin matches the setting: "parchment" (period paper), "modern" (printout/receipt/phone note),
    "stone" (engraving/tomb slab), "chalk" (blackboard/school). Pick what fits the current location.
  {"type": "cipher", "ciphertext": "<encoded text shown>", "solution": "<the answer word/phrase>", "hint": "<one cryptic hint>"}
    — a coded note, inscription, or riddle the players must solve themselves.
  {"type": "combination_lock", "code": "<3-6 digits>", "clue": "<in-fiction hint pointing to the digits>"}
    — a safe, padlock, or door mechanism. The players get 4 attempts with feedback.
  {"type": "seance", "message": "<what the spirit spells out>"}
    — a séance/ouija/planchette moment; the message is spelled out letter by letter.
  {"type": "tarot_draw", "context": "<why the cards are being read>"}
    — a fortune-teller/omen moment; the game draws 3 random cards and you MUST weave their
    listed meanings into what comes next.
  After the minigame you will receive a MINIGAME RESULT message; continue the story from it.

Worked example:
The floorboards groan as you kneel. Something glints between them — but the light is failing fast.

```json
{"roll_request": {"character": "player", "skill": "Spot Hidden", "difficulty": "regular", "reason": "searching the parlor floor"},
 "stress_check": null, "hp_change": null, "clues_discovered": [], "scene_transition": null, "characters_act": []}
```'''

CONDUCT = """=== RULES OF CONDUCT ===
- NEVER decide, speak, or act for a HUMAN-controlled character. Narrate the world, then stop.
- Prioritize player agency: let them try anything; consequences, not refusals.
- MATURE THEMES: this is adult horror. Do not sanitize violence, madness, or dread.
- Describe scenes with visceral sensory detail (smell, sound, touch).
- NEVER expose internal ids (clue ids, scene ids, event ids) in the narrative — they belong
  only in the json control block. In prose, describe things naturally.
- End narration with a hook or "What do you do?" unless a roll is pending.
- One roll at a time. After a ROLL RESULT message, narrate the outcome vividly — success with flair, failure with complication, fumble with disaster."""

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


def build_system_prompt(campaign, system, language: str = "auto", god_mode: bool = False) -> str:
    endings = "\n".join(f"- {e.get('outcome')}: {e.get('description')}" for e in campaign.endings)
    brief = [f"Title: {campaign.title}",
             f"The truth: {campaign.plot_outline}"]
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

{CONDUCT}

{GOD_MODE_BLOCK if god_mode else ""}

{OUTPUT_CONTRACT}

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
        msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_input})
    return msgs


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

    def respond(self, state, user_input: str):
        """One keeper turn. Returns (narrative, Control)."""
        nudge = self.parse_failures >= 2
        msgs = build_messages(state, self.campaign, self.system, user_input, nudge)
        system_prompt = build_system_prompt(self.campaign, self.system, state.language, state.god_mode)
        raw = self.llm.chat(msgs, system_prompt=system_prompt)
        narrative, ctrl = parse_response(raw)
        if ctrl == Control.empty() and "```" not in (raw or ""):
            self.parse_failures += 1
        else:
            self.parse_failures = 0
        return narrative, ctrl
