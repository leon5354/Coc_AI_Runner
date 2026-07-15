"""The player character must come from the campaign (setting-appropriate), not the generic
fallback sheet. Run: python test_protagonist.py"""
import tempfile
from pathlib import Path

import yaml

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core import campaign as campaign_mod   # noqa: E402
from core.engine import new_game            # noqa: E402

CAMP = Path("data/campaigns/the_haunting.yaml")

# campaign-defined protagonist is used (name, skills, inventory all from the campaign)
st = new_game(CAMP)
p = st.characters[0]
assert p.controller == "human" and p.player_label == "Player 1"
assert p.name == "Eleanor Ash", p.name
assert "revolver" in " ".join(p.inventory).lower()
assert p.skills.get("Persuade") == 45
assert "childhood" in p.backstory.lower()

# a campaign WITHOUT a protagonist block falls back to protagonist.yaml (still works)
data = yaml.safe_load(CAMP.read_text(encoding="utf-8"))
data.pop("protagonist")
tmp = game_state.SAVES_DIR / "noproto.yaml"
tmp.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
st2 = new_game(tmp)
assert st2.characters[0].name == "Player"   # generic fallback sheet
assert st2.characters[0].skills   # has some skills

# the campaign exposes the protagonist for validation/use
camp = campaign_mod.load(CAMP)
assert camp.protagonist and camp.protagonist["name"] == "Eleanor Ash"

print("test_protagonist: all checks passed")
