"""The Keeper can't chain endless rolls off one player action. Run: python test_roll_chain.py"""
import tempfile
from pathlib import Path

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core.engine import Engine, new_game   # noqa: E402

ROLL = ('The danger mounts.\n```json\n{"roll_request": {"character": "player", "skill": "Dodge",'
        ' "difficulty": "regular", "reason": "again"}, "stress_check": null, "hp_change": null,'
        ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```')


class AlwaysRoll:
    def chat(self, *a, **k): return ROLL


st = new_game("data/campaigns/the_haunting.yaml")
st.party_mode = "solo"
eng = Engine(st, llm=AlwaysRoll())
pid = st.characters[0].id

eng.submit_action(pid, "I run for the door.")
assert st.pending_roll is not None and st.rolls_since_action == 1   # roll 1 gates

eng.resolve_roll()
assert st.pending_roll is not None and st.rolls_since_action == 2   # keeper chains roll 2

eng.resolve_roll()   # keeper asks for roll 3 -> guard declines it
assert st.pending_roll is None, "third chained roll must be blocked"
assert any("guard" in line for line in st.dice_log)

# a fresh player action resets the budget
eng.submit_action(pid, "I catch my breath and look around.")
assert st.pending_roll is not None and st.rolls_since_action == 1

st.save_path().unlink(missing_ok=True)
print("test_roll_chain: all checks passed")
