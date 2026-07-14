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
    ]

    def chat(self, messages, system_prompt=None, **kw):
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
