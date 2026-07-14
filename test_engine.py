"""Offline end-to-end engine test using the scripted MockLLM. Run: python test_engine.py"""
from pathlib import Path

from cli_play import MockLLM
from core.engine import Engine, new_game
from core.game_state import GameState

CAMP = Path("data/campaigns/the_haunting.yaml")

import tempfile

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())  # keep test saves away from real ones

state = new_game(CAMP)
assert state.scene_id == "briefing"
assert [c.id for c in state.characters] == ["player", "prof_warren_vale"]
assert state.characters[0].controller == "human" and state.characters[1].controller == "ai"
state.party_mode = "solo"   # keep the mock script deterministic

engine = Engine(state, llm=MockLLM())

# turn 1: plain narration
engine.submit_action("player", "I ask Knott about the house.")
assert state.pending_roll is None
assert state.messages[-1]["role"] == "keeper" and "folder" in state.messages[-1]["content"]

# turn 2: keeper requests a roll -> gate blocks for human char
engine.submit_action("player", "I read the tenant letters carefully.")
pr = state.pending_roll
assert pr is not None and pr["character_id"] == "player"
assert pr["skill"] == "Library Use" and pr["target"] == 50   # coerced 'library use' -> sheet skill
assert pr["difficulty"] == "regular"

# save/reload mid-roll: pending_roll survives
state.save()
reloaded = GameState.load(state.save_path())
assert reloaded.pending_roll == pr

# turn 3: resolve -> clue discovered + stress check applied
old_stress = state.characters[0].stress
result = engine.resolve_roll()
assert result is not None and 1 <= result.roll <= 100
assert state.pending_roll is None
assert "tenant_letters" in state.discovered_clues
assert 0 <= old_stress - state.characters[0].stress <= 2      # 0/1d2 loss
assert any("Library Use" in line for line in state.dice_log)
assert any("SAN roll" in line for line in state.dice_log)

# turn 4: scene transition validated against exits
engine.submit_action("player", "I take the key and go to the house.")
assert state.scene_id == "house_ground"
assert state.visited_scenes == ["briefing", "house_ground"]

# turn 5: minigame gate (mock step 5) then resolution feeds keeper (mock step 6)
engine.submit_action("player", "I search between the floorboards.")
assert state.pending_minigame is not None and state.pending_minigame["type"] == "burn_reveal"
engine.resolve_minigame('The heat reveals hidden writing: "HE COUNTS US WHILE WE SLEEP"')
assert state.pending_minigame is None
assert "floorboard creaks" in state.messages[-1]["content"]
assert any("minigame" in line for line in state.dice_log)

# undo: rewind to before the minigame resolution
assert engine.undo() is True
state = engine.state
assert state.pending_minigame is not None and state.pending_minigame["type"] == "burn_reveal"
assert engine.undo() is False        # single level only
state.pending_minigame = None

# language persists through save/load
state.language = "yue"
state.save()
assert GameState.load(state.save_path()).language == "yue"

# controller switching
engine.set_controller("player", "ai")
assert state.get_character("player").controller == "ai"
engine.set_controller("player", "human")

# add character with system defaults
c = engine.add_character("Second Player", controller="human", player_label="Player 2")
assert c.id == "second_player" and c.skills.get("Spot Hidden") == 45

# state block sanity: undiscovered clue reveals are withheld, discovered ones shown
from core.keeper import build_state_block
block = build_state_block(state, engine.campaign)
assert "tenant_letters" in block and "thin man" in block          # discovered clue reveal shown
assert "scratched_floor" in block and "radiating" not in block     # undiscovered reveal withheld

state.save_path().unlink()
print("test_engine: all checks passed")
