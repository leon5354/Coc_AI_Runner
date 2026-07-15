"""Regression: non-ASCII character names must not collide into one id (crashed the sidebar).
Run: python test_id_collision.py"""
import tempfile
from pathlib import Path

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core.engine import Engine, new_game               # noqa: E402
from core.game_state import CharacterState, GameState  # noqa: E402


class Mock:
    def chat(self, *a, **k): return "ok"


CAMP = Path("data/campaigns/the_haunting.yaml")

# new_game gives every character a distinct id even with identical / non-ASCII names
state = new_game(CAMP)
extra = [{"name": "午夜"}, {"name": "午夜"}, {"name": "!!!"}, {"name": "!!!"}]
# splice in colliding ai_party by hand (simulating a Chinese campaign)
from core.engine import _character_from_sheet, unique_id  # noqa: E402
for p in extra:
    c = _character_from_sheet(p["name"], {"stats": {}}, controller="ai")
    c.id = unique_id({ch.id for ch in state.characters}, c.id)
    state.characters.append(c)
ids = [c.id for c in state.characters]
assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"

# a pre-fix save with colliding ids gets repaired on load (Engine.__init__)
broken = GameState(campaign_file=str(CAMP), rule_system="coc7e", scene_id="briefing",
                   visited_scenes=["briefing"], active_character_id="char",
                   characters=[CharacterState(id="char", name="午夜"),
                               CharacterState(id="char", name="重播"),
                               CharacterState(id="char", name="X")],
                   messages=[])
eng = Engine(broken, llm=Mock())
rids = [c.id for c in eng.state.characters]
assert len(rids) == len(set(rids)), f"repair failed: {rids}"
assert eng.state.active_character_id in rids
assert eng.state.get_character(eng.state.active_character_id) is not None

print("test_id_collision: all checks passed")
