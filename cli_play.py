"""Terminal REPL over the engine — dev/test harness.
Usage: python cli_play.py [campaign.yaml] [--mock]
Commands: /roll  /negotiate <text>  /switch <char_id> human|ai  /chars  /log  /quit
--mock uses a scripted fake LLM (no API key needed) to exercise the whole loop offline.
"""
import sys
from pathlib import Path

from core import campaign as campaign_mod
from core.engine import Engine, new_game
from core.game_state import GameState, save_exists

CAMPAIGNS = Path("data/campaigns")


class MockLLM:
    """Scripted keeper responses that exercise roll gate, stress, clue, transition — offline."""
    def __init__(self):
        self.n = 0

    SCRIPT = [
        # 1: plain narration
        'Knott slides the folder across the desk. "Find out what is wrong with my house."\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 2: roll request for the player
        'You leaf through the tenant letters. The handwriting deteriorates page by page...\n\n'
        '```json\n{"roll_request": {"character": "player", "skill": "library use", "difficulty": "regular",'
        ' "reason": "reading the letters"}, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 3: outcome — clue + stress event
        'The pattern leaps out at you: every family describes the same thin man. Your hands tremble.\n\n'
        '```json\n{"roll_request": null, "stress_check": {"character": "player", "event_id": null,'
        ' "loss": "0/1d2"}, "hp_change": null, "clues_discovered": ["tenant_letters"],'
        ' "scene_transition": null, "characters_act": []}\n```',
        # 4: scene transition
        'You pocket the key and head for Marsh Lane. The house waits at the dead end.\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": "house_ground", "characters_act": []}\n```',
        # 5: minigame — hidden writing on a paper found in the parlor
        'Between two floorboards you find a folded sheet of paper. It appears completely blank — '
        'yet it smells faintly of lemon. Perhaps heat would tell another story.\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": [],'
        ' "minigame": {"type": "burn_reveal", "hidden_text": "HE COUNTS US WHILE WE SLEEP",'
        ' "context": "A blank sheet of paper that smells of lemon juice"}}\n```',
        # 6: aftermath
        'The words sear themselves into your mind as the paper curls and blackens. '
        'Somewhere above you, a floorboard creaks — slowly, deliberately.\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 7: an item and a wound
        'A loose board gives way. Your hand closes on cold iron as something rakes your wrist from below.\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": {"character": "", "amount": "-1d3"},'
        ' "inventory_change": {"character": "", "add": ["Rusty iron key"], "remove": []},'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 8: a companion rolls on their own
        'Professor Vale crouches over the symbols, muttering. Can he read them in time?\n\n'
        '```json\n{"roll_request": {"character": "prof_warren_vale", "skill": "Occult", "difficulty": "regular",'
        ' "reason": "reading the symbols"}, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 9: outcome of the companion roll
        'He looks up, pale. "It is a binding. And it has already broken."\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
        # 10: the end
        'Fire takes the old timbers. By dawn the house on Marsh Lane is ash, and the counting has stopped.\n\n'
        '```json\n{"roll_request": null, "stress_check": null, "hp_change": null, "ending": "destroyed",'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```',
    ]

    def chat(self, messages, system_prompt=None, **kw):
        # Non-keeper callers get their own canned reply (and don't advance the keeper script).
        from agents.researcher import SYSTEM_PROMPT as ARCHIVIST
        from core.engine import ITEM_PROMPT
        from core.keeper import OOC_PROMPT
        from core.memory import CHARACTER_MEMORY_PROMPT, SUMMARIZE_PROMPT
        sp = system_prompt or ""
        if "\nSAY:" in sp:        # companion, talk mode
            return 'THOUGHT: That writing was meant for someone.\nSAY: "Stay close. I don\'t like this house."'
        if "\nACTION:" in sp:     # companion, act mode
            return 'THOUGHT: Someone has to watch the stairs.\nACTION: I raise the lamp toward the stairs. "Did you hear that?"'
        if sp.startswith(OOC_PROMPT):
            return "(mock) Out of character: you can search the parlor, question Knott again, or head upstairs."
        if sp.startswith(ARCHIVIST):
            return "(mock) A yellowed clipping: 'MARSH LANE TENANTS FLEE — THIRD FAMILY IN TWO YEARS.'"
        if sp == ITEM_PROMPT:
            return "(mock) Worn from use, heavier than it looks."
        if sp == SUMMARIZE_PROMPT:
            return "STORY: (mock) The investigators took Knott's case and entered the house on Marsh Lane."
        if sp == CHARACTER_MEMORY_PROMPT:
            return "MEMORY:\n(mock) I followed them into that house. I wish I hadn't."
        out = self.SCRIPT[min(self.n, len(self.SCRIPT) - 1)]
        self.n += 1
        return out


def pick_campaign():
    files = campaign_mod.list_campaigns()
    if not files:
        sys.exit("No valid campaigns in data/campaigns/")
    return files[0]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mock = "--mock" in sys.argv
    camp_path = Path(args[0]) if args else pick_campaign()

    save = save_exists(camp_path)
    if save and input(f"Resume save {save.name}? [Y/n] ").strip().lower() != "n":
        state = GameState.load(save)
    else:
        state = new_game(camp_path)

    engine = Engine(state, llm=MockLLM() if mock else None)
    print(f"\n=== {engine.campaign.title} [{engine.system.label}] ===\n")
    print(state.messages[-1]["content"], "\n")

    while True:
        if state.pending_roll:
            pr = state.pending_roll
            print(f"[ROLL PENDING] {pr['skill']} (target {pr['target']}, {pr['difficulty']}) — {pr['reason']}")
            print("  /roll to roll, or /negotiate <argument>")
        try:
            raw = input(f"{state.active_character().name}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaved. Goodbye.")
            break
        if not raw:
            continue

        if raw == "/quit":
            state.save()
            print("Saved. Goodbye.")
            break
        elif raw == "/chars":
            for c in state.characters:
                print(f"  {c.id}: {c.name} [{c.controller}] HP {c.hp}/{c.max_hp} "
                      f"Stress {c.stress}/{c.max_stress} ({c.status})")
        elif raw == "/log":
            for line in state.dice_log[-15:]:
                print(" ", line)
        elif raw.startswith("/switch"):
            parts = raw.split()
            if len(parts) == 3 and parts[2] in ("human", "ai"):
                engine.set_controller(parts[1], parts[2])
                print(f"  {parts[1]} is now {parts[2]}-controlled")
            else:
                print("  usage: /switch <char_id> human|ai")
        elif raw == "/roll":
            if state.pending_roll:
                result = engine.resolve_roll()
                print(f"\n🎲 {result.detail}\n")
                print(state.messages[-1]["content"], "\n")
            else:
                print("  nothing pending")
        elif raw.startswith("/negotiate"):
            if state.pending_roll:
                engine.negotiate_roll(raw[len("/negotiate"):].strip())
                print("\n" + state.messages[-1]["content"], "\n")
            else:
                print("  nothing pending")
        elif raw.startswith("/"):
            print("  commands: /roll /negotiate <text> /switch <id> human|ai /chars /log /quit")
        else:
            if state.pending_roll:
                print("  a roll is pending — /roll or /negotiate first")
                continue
            engine.submit_action(state.active_character_id, raw)
            # print everything the turn produced (keeper + companions)
            for m in _new_messages_since_input(state):
                tag = f"[{m['name']}] " if m.get("name") else ""
                print(f"\n{tag}{m['content']}")
            print()


def _new_messages_since_input(state):
    out = []
    for m in reversed(state.messages):
        if m["role"] == "player":
            break
        out.append(m)
    return list(reversed(out))


if __name__ == "__main__":
    main()
