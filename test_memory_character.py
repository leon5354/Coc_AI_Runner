"""Character memory + talk/OOC tests. Run: python test_memory_character.py"""
import tempfile
from pathlib import Path

from core import game_state

game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core import memory                                    # noqa: E402
from core.engine import Engine, new_game                   # noqa: E402
from core.game_state import GameState                      # noqa: E402

CAMP = Path("data/campaigns/the_haunting.yaml")

NARRATE = ('Quiet.\n```json\n{"roll_request": null, "stress_check": null, "hp_change": null,'
           ' "clues_discovered": [], "scene_transition": null, "characters_act": []}\n```')


class Mock:
    """Keeper returns NARRATE; agents emit THOUGHT/SAY; the memory distiller returns a chronicle."""
    def __init__(self):
        self.ooc_calls = 0
        self.distil_calls = 0
        self.agent_calls = 0

    def chat(self, messages, system_prompt=None, **kw):
        sp = system_prompt or ""
        if sp.startswith("You are the KEEPER, stepping OUT"):
            self.ooc_calls += 1
            return "Spot Hidden is your eye for detail. You still haven't searched the cellar."
        if sp.startswith("You are the KEEPER"):
            return NARRATE
        if sp.startswith("You maintain ONE character's private memory"):
            self.distil_calls += 1
            return ("MEMORY:\nI found the deed myself, and the scratched-out name has not left me.\n\n"
                    "RELATIONSHIPS:\nPlayer: Reckless, but the only one who listens to me.\n"
                    "Mr. Knott: He is lying, and badly.")
        self.agent_calls += 1
        return 'THOUGHT: This house is wrong.\nSAY: "We should not be here after dark."'


# --- overflowing thoughts distil into a personal memory instead of being dropped ---
state = new_game(CAMP)
vale = state.get_character("prof_warren_vale")
vale.private_thoughts = [f"thought {i}" for i in range(memory.THOUGHT_WINDOW + 3)]
mock = Mock()
assert memory.compact_character(vale, mock) is True
assert mock.distil_calls == 1
assert len(vale.private_thoughts) == memory.THOUGHT_WINDOW, "recent thoughts kept verbatim"
assert "scratched-out name" in vale.memory_summary, "older thoughts became personal memory"
assert vale.relationships["Player"].startswith("Reckless")
assert "lying" in vale.relationships["Mr. Knott"]
# nothing to do when under the window
assert memory.compact_character(vale, mock) is False and mock.distil_calls == 1

# memory survives a save/load round-trip
state.save()
reloaded = GameState.load(state.save_path())
rv = reloaded.get_character("prof_warren_vale")
assert "scratched-out name" in rv.memory_summary and rv.relationships["Player"]

# the character's memory is actually put in front of the model
from agents.player_agent import PlayerAgent                # noqa: E402
captured = {}


class Capture(Mock):
    def chat(self, messages, system_prompt=None, **kw):
        if system_prompt and system_prompt.startswith("You are Prof"):
            captured["sp"] = system_prompt
        return super().chat(messages, system_prompt=system_prompt, **kw)


cap = Capture()
engine = Engine(state, llm=cap)
PlayerAgent(cap, cap).take_turn(vale, state, engine.campaign, mode="talk")
assert "scratched-out name" in captured["sp"], "their memory must reach their own prompt"
assert "Reckless" in captured["sp"], "their opinions must reach their own prompt"
assert "CONVERSATION, not an action scene" in captured["sp"], "talk mode must be signalled"

# --- Talk: companions reply, no turn spent, no keeper call, no dice ---
state = new_game(CAMP)
state.party_mode = "keeper"          # talk ignores party_mode gating (only solo silences them)
mock = Mock()
engine = Engine(state, llm=mock)
turns_before, dice_before = state.turn_count, len(state.dice_log)
responders = engine.begin_talk("player", "Vale, what do you make of the deed?")
assert [c.id for c in responders] == ["prof_warren_vale"]
list(engine.talk_steps(responders))
assert state.turn_count == turns_before, "talking must not spend a turn"
assert len(state.dice_log) == dice_before, "talking must not roll dice"
assert state.pending_roll is None
assert not any(m["role"] == "keeper" for m in state.messages[-2:]), "keeper must not narrate a talk"
assert state.messages[-1]["role"] == "companion" and "after dark" in state.messages[-1]["content"]

# solo mode: nobody answers
state = new_game(CAMP)
state.party_mode = "solo"
engine = Engine(state, llm=Mock())
assert engine.begin_talk("player", "Anyone there?") == []

# --- OOC: keeper answers, nothing in the world changes ---
state = new_game(CAMP)
mock = Mock()
engine = Engine(state, llm=mock)
before = (state.turn_count, state.scene_id, len(state.dice_log), list(state.discovered_clues))
answer = engine.ask_keeper_ooc("What does Spot Hidden do?")
assert mock.ooc_calls == 1 and "Spot Hidden" in answer
assert (state.turn_count, state.scene_id, len(state.dice_log), state.discovered_clues) == before
assert state.pending_roll is None
ooc = [m for m in state.messages if m["role"] == "ooc"]
assert len(ooc) == 2 and ooc[0]["name"] == "You" and ooc[1]["name"] == "Keeper"

# OOC is flagged as table talk when the keeper next reads history
from core.keeper import build_messages                     # noqa: E402
msgs = build_messages(state, engine.campaign, engine.system, "I open the door.")
assert any("OUT OF CHARACTER" in m["content"] for m in msgs), "OOC must be marked in keeper context"

state.save_path().unlink(missing_ok=True)
print("test_memory_character: all checks passed")
