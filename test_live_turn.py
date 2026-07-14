"""Live-turn tests: a turn arrives as separate beats, and character backgrounds reach the Keeper.
Run: python test_live_turn.py"""
import tempfile
from pathlib import Path

from core import game_state

game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core.engine import Engine, new_game          # noqa: E402  (after SAVES_DIR redirect)
from core.keeper import build_state_block         # noqa: E402

CAMP = Path("data/campaigns/the_haunting.yaml")

CALL_VALE = ('The professor leans in.\n```json\n{"roll_request": null, "stress_check": null,'
             ' "hp_change": null, "clues_discovered": [], "scene_transition": null,'
             ' "characters_act": ["prof_warren_vale"]}\n```')
ROLL_VALE = ('Vale reaches for the ledger.\n```json\n{"roll_request": {"character":'
             ' "prof_warren_vale", "skill": "Library Use", "difficulty": "regular",'
             ' "reason": "reading"}, "stress_check": null, "hp_change": null,'
             ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```')
NARRATE = ('All is quiet.\n```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
           ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```')


class ScriptMock:
    def __init__(self, keeper_script):
        self.keeper_script = keeper_script
        self.keeper_calls = 0

    def chat(self, messages, system_prompt=None, **kw):
        if system_prompt and system_prompt.startswith("You are the KEEPER"):
            out = self.keeper_script[min(self.keeper_calls, len(self.keeper_script) - 1)]
            self.keeper_calls += 1
            return out
        return "I examine the shelves and mutter about provenance."


# --- a companion turn arrives as SEPARATE beats, not all at once ---
state = new_game(CAMP)
state.party_mode = "keeper"
engine = Engine(state, llm=ScriptMock([CALL_VALE, NARRATE]))

engine.begin_action("player", "Ask Vale for help.")
# the player's message must be visible BEFORE any LLM work happens
assert state.messages[-1]["role"] == "player", "player message must land before the keeper runs"
msgs_at_start = len(state.messages)

gen = engine.keeper_steps("Ask Vale for help.")
snapshots = []
while True:
    try:
        label = next(gen)
    except StopIteration:
        break
    snapshots.append((label, len(state.messages)))

assert len(snapshots) >= 2, f"expected multiple beats, got {snapshots}"
# the transcript grew between beats — that is what makes it feel live
counts = [n for _, n in snapshots]
assert counts == sorted(counts) and counts[-1] > msgs_at_start
assert any("Vale" in label for label, _ in snapshots), f"no companion beat label: {snapshots}"
roles = [m["role"] for m in state.messages]
assert "keeper" in roles and "companion" in roles

# --- an AI character's roll is its own beat, and lands in the transcript as a dice message ---
state = new_game(CAMP)
state.party_mode = "solo"
state.get_character("prof_warren_vale").controller = "ai"
engine = Engine(state, llm=ScriptMock([ROLL_VALE, NARRATE]))
labels = list(engine.keeper_steps(engine.begin_action("player", "Vale, check the ledger.")))
assert any("rolls" in l for l in labels), f"AI roll should be its own beat: {labels}"
dice_msgs = [m for m in state.messages if m["role"] == "dice"]
assert dice_msgs and "Library Use" in dice_msgs[0]["content"], "AI roll must show in the transcript"
assert state.pending_roll is None  # AI rolls never gate the UI

# --- human rolls still gate, and roll_dice() lands the dice before the keeper speaks ---
state = new_game(CAMP)
engine = Engine(state, llm=ScriptMock([
    ('Look closer.\n```json\n{"roll_request": {"character": "player", "skill": "Spot Hidden",'
     ' "difficulty": "regular", "reason": "searching"}}\n```'), NARRATE]))
engine.submit_action("player", "I search the desk.")
assert state.pending_roll is not None, "human roll must gate"
before = len(state.messages)
result = engine.roll_dice()
assert result is not None and state.pending_roll is None
assert state.messages[-1]["role"] == "dice", "dice must be in the transcript before the keeper narrates"
assert len(state.messages) == before + 1, "roll_dice must not call the keeper"

# --- character background reaches the Keeper's prompt ---
state = new_game(CAMP)
engine = Engine(state, llm=ScriptMock([NARRATE]))
block = build_state_block(state, engine.campaign)
assert "background:" in block
assert "occult after a" in block, "protagonist background must be in the keeper's state block"
assert "Investigator / Analyst" in block, "occupation must be folded into the background"
assert "discreet inquiry agent" in block, "campaign protagonist_hints must be folded in"
assert "Miskatonic folklore lecturer" in block, "companion backstory must be in the state block"

# --- backgrounds are editable and persist ---
engine.update_character("player", backstory="Ex-priest who lost the faith.", personality="Grim.")
assert state.get_character("player").backstory == "Ex-priest who lost the faith."
assert "Ex-priest" in build_state_block(state, engine.campaign)
c = engine.add_character("Nurse Adler", controller="ai", backstory="Field medic, war-shaken.")
assert c.backstory == "Field medic, war-shaken."
assert "war-shaken" in build_state_block(state, engine.campaign)

print("test_live_turn: all checks passed")
