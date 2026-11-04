"""Play a campaign end to end with a real AI, nobody at the keyboard, and report what worked.
Another AI call plays the human. Rolls, minigames and everything else go through the real engine.

  python playtest.py data/campaigns/the_haunting.yaml --turns 8 --provider ollama --model <name>
  python playtest.py ... --provider claude_cli --model sonnet

Saves stay in a temp folder. The report goes to data/logs/playtest_<campaign>.md.
"""
import argparse
import re
import tempfile
import time
from pathlib import Path

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core.engine import Engine, new_game  # noqa: E402
from core.keeper import LANGUAGE_LABELS, language_block  # noqa: E402
from core.llm_client import LLMClient, LLMError  # noqa: E402

PLAYER = """You are playing a tabletop horror game as {name}. {about}
Write what your character does next: one or two short sentences, first person, plain, in the same
language as the story. Try to move the story on: investigate, go somewhere, use something you
carry, or confront someone. No narration of results, no dice."""

FAKE_DICE = re.compile(r"d100\s*=|d20\s*=|[Rr]oll(ed)?\s*:?\s*\d|檢定(成功|失敗)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign")
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", required=True)
    ap.add_argument("--language", default="auto", choices=list(LANGUAGE_LABELS))
    a = ap.parse_args()

    state = new_game(a.campaign)
    state.language = a.language
    llm = LLMClient(provider=a.provider, model_name=a.model)
    e = Engine(state, llm=llm)
    camp_ids = {s["id"] for s in e.campaign.scenes} | e.campaign.all_clue_ids()
    lines = [f"# Playtest: {e.campaign.title} ({e.system.label}, {a.provider}/{a.model})", ""]
    seen = {"rolls": 0, "bonus": 0, "stress": 0, "hp": 0, "clues": 0, "scenes": 0, "items": 0, "minigames": 0,
            "companions": 0, "no_control": 0, "leaked_ids": 0, "fake_dice": 0, "errors": 0}
    timings = []

    def check(from_msg):
        for m in state.messages[from_msg:]:
            if m["role"] == "keeper":
                c = m["content"]
                seen["fake_dice"] += bool(FAKE_DICE.search(c))
                seen["leaked_ids"] += any(re.search(rf"(?<![\w]){re.escape(i)}(?![\w])", c) for i in camp_ids if "_" in i)
                seen["no_control"] += "```" in c or '"roll_request"' in c
            lines.append(f"**[{m['role']}{' ' + m['name'] if m.get('name') else ''}]** {m['content']}\n")

    def run(gen):
        t = time.time()
        try:
            for _ in gen:
                pass
        except LLMError as err:
            seen["errors"] += 1
            lines.append(f"> AI ERROR: {err}\n")
        timings.append(time.time() - t)
        for ev in e.drain_events():
            seen["stress" if ev["kind"] == "stress" else "rolls"] += 1
            lines.append(f"> DICE {ev['who']} {ev['label']}: {ev['detail']}\n")

    for turn in range(a.turns):
        if state.ending:
            break
        before = (len(state.messages), state.scene_id, len(state.discovered_clues), len(state.dice_log))
        items = sum(len(c.inventory) for c in state.characters)
        hero = state.characters[0]
        recent = "\n".join(f"{m.get('name') or m['role']}: {m['content'][:400]}" for m in state.messages[-4:])
        prompt = [{"role": "user", "content": f"Story so far:\n{recent}\n\nYou carry: {', '.join(hero.inventory)}.\nWhat do you do?"}]
        action = llm.chat(prompt, system_prompt=PLAYER.format(name=hero.name, about=hero.personality)
                          + "\n" + language_block(state.language), temperature=0.9, max_tokens=120)
        if action.startswith("[SYSTEM ERROR]"):
            seen["errors"] += 1
            lines.append(f"> PLAYER AI ERROR: {action}\n")
            continue
        print(f"turn {turn + 1}: {action[:70]!r}".encode("ascii", "replace").decode(), flush=True)
        run(e.keeper_steps(e.begin_action(hero.id, action.strip())))
        for _ in range(3):      # clear any gates this action raised
            if state.pending_roll:
                seen["bonus"] += bool(state.pending_roll.get("bonus") or state.pending_roll.get("penalty"))
                e.roll_dice()
                run(e.keeper_steps("Narrate the outcome of the roll above."))
            elif state.pending_minigame:
                seen["minigames"] += 1
                run(e.keeper_steps(e.begin_minigame_result("The player solved it after a tense moment.")))
        check(before[0])
        seen["scenes"] += state.scene_id != before[1]
        seen["clues"] += len(state.discovered_clues) - before[2]
        seen["items"] += sum(len(c.inventory) for c in state.characters) != items
        seen["hp"] += sum("HP" in l for l in state.dice_log[before[3]:])
        seen["companions"] += sum(m["role"] == "companion" for m in state.messages[before[0]:])

    summary = [f"turns {state.turn_count}, seconds per beat {sum(timings) / max(len(timings), 1):.0f}, "
               f"ended: {state.ending}", str(seen), f"warnings: {[l for l in state.dice_log if l.startswith('[warn')]}"]
    lines = lines[:2] + summary + [""] + lines[2:]
    out = Path("data/logs") / f"playtest_{Path(a.campaign).stem}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(summary).encode("ascii", "replace").decode())
    print(f"report: {out}")


if __name__ == "__main__":
    main()
