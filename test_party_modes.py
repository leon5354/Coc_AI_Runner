"""Offline party-mode tests: solo = zero agent calls; keeper = only named companions act.
Run: python test_party_modes.py"""
from pathlib import Path

from core.engine import Engine, new_game

CAMP = Path("data/campaigns/the_haunting.yaml")

NARRATE = ('All is quiet.\n```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
           ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```')
CALL_VALE = ('The professor leans in.\n```json\n{"roll_request": null, "stress_check": null,'
             ' "hp_change": null, "clues_discovered": [], "scene_transition": null,'
             ' "characters_act": ["prof_warren_vale"]}\n```')


class CountingMock:
    """Counts keeper calls vs companion-agent calls (distinguished by system prompt)."""
    def __init__(self, keeper_script):
        self.keeper_script = keeper_script
        self.keeper_calls = 0
        self.agent_calls = 0

    def chat(self, messages, system_prompt=None, **kw):
        if system_prompt and system_prompt.startswith("You are the KEEPER"):
            out = self.keeper_script[min(self.keeper_calls, len(self.keeper_script) - 1)]
            self.keeper_calls += 1
            return out
        self.agent_calls += 1
        return "I examine the shelves and mutter about provenance."


import tempfile

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())  # keep test saves away from real ones


# solo: companion agent never called even when the keeper names it
state = new_game(CAMP); state.party_mode = "solo"
mock = CountingMock([CALL_VALE])
Engine(state, llm=mock).submit_action("player", "Look around.")
assert mock.agent_calls == 0, "solo mode must make zero agent calls"

# keeper mode, keeper does NOT name anyone: no agent calls
state = new_game(CAMP); state.party_mode = "keeper"
mock = CountingMock([NARRATE])
Engine(state, llm=mock).submit_action("player", "Look around.")
assert mock.agent_calls == 0

# keeper mode, keeper names Vale: exactly one agent call + one wrap-up keeper call
state = new_game(CAMP); state.party_mode = "keeper"
mock = CountingMock([CALL_VALE, NARRATE])
Engine(state, llm=mock).submit_action("player", "Ask Vale for help.")
assert mock.agent_calls == 1, f"expected 1 agent call, got {mock.agent_calls}"
assert mock.keeper_calls == 2, f"expected wrap-up keeper call, got {mock.keeper_calls}"
assert any(m["role"] == "companion" and m["name"] == "Prof. Warren Vale" for m in state.messages)

# active mode: every AI character acts each turn
state = new_game(CAMP); state.party_mode = "active"
mock = CountingMock([NARRATE, NARRATE])
Engine(state, llm=mock).submit_action("player", "Look around.")
assert mock.agent_calls == 1  # one AI char in this campaign

state.save_path().unlink(missing_ok=True)
print("test_party_modes: all checks passed")
