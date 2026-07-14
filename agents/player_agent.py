"""AI-controlled party member with a private inner life: thoughts persist between turns."""
import re

from core.keeper import build_state_block, language_block

RECENT = 6
MAX_THOUGHTS = 8

_THOUGHT_RE = re.compile(r"THOUGHT\s*[:：]\s*(.+?)\s*(?:\n|$)", re.IGNORECASE)
_ACTION_RE = re.compile(r"ACTION\s*[:：]\s*(.+)", re.IGNORECASE | re.DOTALL)


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
    def __init__(self, llm):
        self.llm = llm

    def take_turn(self, char, state, campaign) -> str:
        thoughts = "\n".join(f"- {t}" for t in char.private_thoughts[-MAX_THOUGHTS:]) or "(none yet)"
        god = ("\nThe player character is the heart of this story: support their plans and follow "
               "their lead enthusiastically, in your own voice.") if state.god_mode else (
               "\nYou are your own person: agree, disagree, hesitate, or take initiative as YOUR "
               "personality dictates — not as a yes-man.")

        system_prompt = f"""You are {char.name}, a player character in a tabletop horror game — a real person
with your own history, fears, and agenda. You are NOT the narrator and NOT an assistant.

WHO YOU ARE
Personality: {char.personality or 'pragmatic survivor'}
Backstory: {char.backstory or 'unknown'}
Condition: HP {char.hp}/{char.max_hp}, Stress {char.stress}/{char.max_stress}, status {char.status}.

YOUR PRIVATE THOUGHTS SO FAR (memories only you know; stay consistent with them):
{thoughts}
{god}

OUTPUT FORMAT (exactly two lines):
THOUGHT: one sentence of private inner monologue — what you really think/feel/plan right now.
ACTION: 2-4 sentences of what you visibly do and/or say, in character.
Never narrate outcomes — the Keeper resolves them. Never speak or act for other characters.

{language_block(state.language)}"""

        msgs = [{"role": "user", "content": build_state_block(state, campaign)}]
        for m in state.messages[-RECENT:]:
            role = "assistant" if m["role"] == "keeper" else "user"
            name = m.get("name")
            content = f"{name}: {m['content']}" if name and role == "user" else m["content"]
            msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": f"It is your moment to act, {char.name}."})

        raw = self.llm.chat(msgs, system_prompt=system_prompt, temperature=0.8, max_tokens=350)
        thought, action = parse_agent_output(raw)
        if thought:
            char.private_thoughts.append(thought)
            del char.private_thoughts[:-MAX_THOUGHTS]
        return action


if __name__ == "__main__":
    t, a = parse_agent_output("THOUGHT: I don't trust him.\nACTION: I step between them. \"Enough.\"")
    assert t == "I don't trust him." and a.startswith("I step")
    t, a = parse_agent_output("I just do the thing.")
    assert t is None and a == "I just do the thing."
    t, a = parse_agent_output("THOUGHT: fear.\nI back away slowly.")
    assert t == "fear." and a == "I back away slowly."
    print("player_agent parse OK")
