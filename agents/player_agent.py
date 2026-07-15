"""AI party member with a persistent inner life.

Memory layers (cheapest first):
  private_thoughts  — verbatim inner monologue, rolling window (core.memory.THOUGHT_WINDOW)
  memory_summary    — their own first-person chronicle; overflowing thoughts distil into it
  relationships     — what they privately think of each other person, and why
All three persist on CharacterState, so they survive saves and never silently vanish.
"""
import re

from core import memory
from core.keeper import build_state_block, language_block

RECENT = 10

_THOUGHT_RE = re.compile(r"THOUGHT\s*[:：]\s*(.+?)\s*(?:\n|$)", re.IGNORECASE)
_ACTION_RE = re.compile(r"(?:ACTION|SAY)\s*[:：]\s*(.+)", re.IGNORECASE | re.DOTALL)


def parse_agent_output(text: str):
    """Split 'THOUGHT: ... ACTION: ...' output. Returns (thought|None, action)."""
    text = (text or "").strip()
    thought_m = _THOUGHT_RE.search(text)
    action_m = _ACTION_RE.search(text)
    thought = thought_m.group(1).strip() if thought_m else None
    if action_m:
        action = action_m.group(1).strip()
    elif thought_m:
        action = text[thought_m.end():].strip() or text
    else:
        action = text
    return thought, action


class PlayerAgent:
    def __init__(self, llm, util_llm=None):
        self.llm = llm
        self.util_llm = util_llm or llm   # cheap model distils long-term memory

    def _system_prompt(self, char, state, mode):
        thoughts = "\n".join(f"- {t}" for t in char.private_thoughts) or "(nothing recent)"
        rels = "\n".join(f"- {k}: {v}" for k, v in char.relationships.items()) or "(no strong opinions yet)"
        god = ("\nThe player character is the heart of this story: support their plans and follow "
               "their lead enthusiastically, in your own voice.") if state.god_mode else (
               "\nYou are your own person: agree, disagree, hesitate, or take initiative as YOUR "
               "personality dictates — not as a yes-man.")

        # What NOT to do — the difference between "a player" and "a novelist" (both styles obey this).
        boundary = """You are one player among several. You control ONLY yourself. Therefore:
- NEVER narrate anything that happens to your body against your will (bleeding, trembling,
  fainting, going pale), NEVER describe your own face/expression from outside, and NEVER state
  the RESULT of what you attempt — the Keeper decides and narrates all of that.
- NEVER describe what the room does, what other characters do, feel, or how they react.
- Don't reuse the same nervous gesture or mannerism you used last turn; vary yourself."""

        if mode == "talk":
            task = f"""This is CONVERSATION, not an action scene. Nobody is rolling dice.
{boundary}
OUTPUT FORMAT (exactly two lines):
THOUGHT: one sentence of private inner monologue — what you really think right now.
SAY: only the words you speak out loud, in your own voice (1-3 sentences). Ask, argue, refuse,
or share a memory. Quote just your speech — no stage directions, no advancing the plot."""
        elif state.companion_style == "cinematic":
            task = f"""{boundary}
OUTPUT FORMAT (exactly two lines):
THOUGHT: one sentence of private inner monologue — what you really think/feel/plan right now.
ACTION: 2-3 vivid sentences of what you deliberately do and say, in character (evocative prose
is welcome), but only YOUR own chosen actions and words — never the outcome or others."""
        else:  # "player" — authentic tabletop register (default)
            task = f"""{boundary}
Speak like a real player at the table, NOT like a novelist writing a scene.
OUTPUT FORMAT (exactly two lines):
THOUGHT: one sentence of private inner monologue — what you really think/feel/plan right now.
ACTION: first person, brief and plain. Say what you TRY to do, and quote what you SAY out loud —
usually one short sentence of action plus your spoken line. No purple prose, no self-narration
of involuntary detail. Example shape: I check the panel and mutter, "呢度唔對路." """

        return f"""You are {char.name}, a player character in a tabletop horror game — a real person
with your own history, fears, and agenda. You are NOT the narrator and NOT an assistant.

WHO YOU ARE
Personality: {char.personality or 'pragmatic survivor'}
History: {char.backstory or 'unknown'}
Condition: HP {char.hp}/{char.max_hp}, Stress {char.stress}/{char.max_stress}, status {char.status}.

WHAT I HAVE LIVED THROUGH (my own memory, in my words):
{char.memory_summary or '(this is still early for me)'}

WHAT I THINK OF THE OTHERS (private):
{rels}

MY RECENT PRIVATE THOUGHTS (only I know these — stay consistent with them):
{thoughts}
{god}

Speak and act from that memory: refer back to what YOU saw and did, hold the grudges and
loyalties above, and let your history colour what you notice.

{task}

{language_block(state.language)}"""

    def take_turn(self, char, state, campaign, mode: str = "act") -> str:
        """mode 'act' = a turn in the scene; 'talk' = conversation, no plot advance."""
        msgs = [{"role": "user", "content": build_state_block(state, campaign)}]
        for m in state.messages[-RECENT:]:
            role = "assistant" if m["role"] == "keeper" else "user"
            name = m.get("name")
            content = f"{name}: {m['content']}" if name and role == "user" else m["content"]
            msgs.append({"role": role, "content": content})
        cue = (f"Respond to what was just said, {char.name}." if mode == "talk"
               else f"It is your moment to act, {char.name}.")
        msgs.append({"role": "user", "content": cue})

        raw = self.llm.chat(msgs, system_prompt=self._system_prompt(char, state, mode),
                            temperature=0.8, max_tokens=350)
        thought, action = parse_agent_output(raw)
        if thought:
            char.private_thoughts.append(thought)
            memory.compact_character(char, self.util_llm)   # distils only when it overflows
        return action


if __name__ == "__main__":
    t, a = parse_agent_output("THOUGHT: I don't trust him.\nACTION: I step between them. \"Enough.\"")
    assert t == "I don't trust him." and a.startswith("I step")
    t, a = parse_agent_output("THOUGHT: He's lying.\nSAY: \"You saw it too, didn't you?\"")
    assert t == "He's lying." and a.startswith('"You saw it')
    t, a = parse_agent_output("I just do the thing.")
    assert t is None and a == "I just do the thing."
    t, a = parse_agent_output("THOUGHT: fear.\nI back away slowly.")
    assert t == "fear." and a == "I back away slowly."

    # register: player style forbids self-narration & purple prose; cinematic allows prose; both
    # keep the "control only yourself" boundary.
    from types import SimpleNamespace
    base = dict(personality="", backstory="", hp=9, max_hp=9, stress=50, max_stress=50,
                status="active", memory_summary="", relationships={}, private_thoughts=[], name="Vale")
    ch = SimpleNamespace(**base)
    agent = PlayerAgent(llm=None)
    player_sp = agent._system_prompt(ch, SimpleNamespace(god_mode=False, companion_style="player",
                                                         language="auto"), "act")
    cine_sp = agent._system_prompt(ch, SimpleNamespace(god_mode=False, companion_style="cinematic",
                                                       language="auto"), "act")
    assert "real player at the table" in player_sp and "purple prose" in player_sp
    assert "novelist" in player_sp and "novelist" not in cine_sp   # only player warns off prose
    assert "evocative prose" in cine_sp
    for sp in (player_sp, cine_sp):
        assert "against your will" in sp and "how they react" in sp  # boundary in both
    print("player_agent parse OK")
