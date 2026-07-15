"""Catalog ⟷ renderers ⟷ keeper contract stay in sync. Run: python test_minigame_catalog.py"""
from core import minigames_catalog as cat
from core.campaign import Campaign
from core.keeper import MINIGAME_TYPES, build_system_prompt, parse_response
from interface.minigames import ICONS, RENDERERS
import rules

# --- parity: every catalog game has a renderer + icon, and vice versa ---
assert set(RENDERERS) == cat.types(), (set(RENDERERS) ^ cat.types())
assert set(ICONS) == cat.types()
assert MINIGAME_TYPES == cat.types()

# --- setting filtering ---
assert "combination_lock" in cat.for_setting("cthulhu")
assert "combination_lock" not in cat.for_setting("forgotten_realms")   # no dial safes in Faerûn
assert "combination_lock" in cat.for_setting("warhammer_40k")          # keypads/cogitator locks
assert "glyph_sequence" in cat.for_setting("forgotten_realms")
assert "glyph_sequence" in cat.for_setting("warhammer_40k")
assert "seance" in cat.for_setting("warhammer_40k")                    # astropathic echo
assert "wire_cut" in cat.for_setting("warhammer_40k")
assert "wire_cut" not in cat.for_setting("forgotten_realms")           # no bombs in Faerûn
for universal in ("burn_reveal", "cipher", "tarot_draw", "dice_duel", "memory_echo"):
    for s in ("generic", "cthulhu", "forgotten_realms", "warhammer_fantasy", "warhammer_40k", "???"):
        assert universal in cat.for_setting(s), (universal, s)
# unknown setting -> only universal games
assert all("*" in cat.CATALOG[g]["settings"] for g in cat.for_setting("no_such_setting"))

# --- every game ships a playable sample for the in-app tester ---
for g in cat.types():
    s = cat.sample(g)
    assert s.get("type") == g, g
    assert s is not cat.CATALOG[g]["sample"], "sample() must return a copy"

# --- contract leads with the device menu + variety nudge ---
blk = cat.contract_block("cthulhu")
assert blk.startswith("AVAILABLE DEVICES") and "never use the same type twice in a row" in blk

# --- default skins cover every known setting ---
for s in cat.RULE_DEFAULT_SETTING.values():
    assert s in cat.DEFAULT_SKIN, s

# --- resolve_setting: explicit beats rule-system fallback ---
c1 = Campaign(data={"rule_system": "dnd5e", "scenes": []})
assert cat.resolve_setting(c1) == "forgotten_realms"
c2 = Campaign(data={"rule_system": "dnd5e", "setting": "warhammer_fantasy", "scenes": []})
assert cat.resolve_setting(c2) == "warhammer_fantasy"

# --- keeper prompt only offers fitting minigames ---
dnd = rules.get_system("dnd5e")
camp = Campaign(data={"rule_system": "dnd5e", "title": "T", "plot_outline": "P",
                      "endings": [], "scenes": []})
sp = build_system_prompt(camp, dnd)
assert '"type": "glyph_sequence"' in sp
assert '"type": "combination_lock"' not in sp
assert "{minigame_contract}" not in sp          # placeholder actually replaced
coc = rules.get_system("coc7e")
camp_coc = Campaign(data={"rule_system": "coc7e", "title": "T", "plot_outline": "P",
                          "endings": [], "scenes": []})
sp_coc = build_system_prompt(camp_coc, coc)
assert '"type": "combination_lock"' in sp_coc

# --- parser accepts the new types ---
for t in ("glyph_sequence", "dice_duel", "wire_cut", "memory_echo"):
    n, ctrl = parse_response(f'X\n```json\n{{"minigame": {{"type": "{t}"}}}}\n```')
    assert ctrl.minigame == {"type": t}, t

# --- engine.launch_minigame: unique keys + setting-default skin ---
import tempfile
from pathlib import Path
from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())
from core.engine import Engine, new_game


class _M:
    def chat(self, *a, **k): return "ok"


st = new_game("data/campaigns/the_haunting.yaml")
eng = Engine(st, llm=_M())
eng.launch_minigame({"type": "burn_reveal", "hidden_text": "x"})
k1 = st.minigame_count
assert st.pending_minigame["skin"] == "parchment"     # cthulhu default injected
st.pending_minigame = None
eng.launch_minigame({"type": "burn_reveal", "hidden_text": "y", "skin": "chalk"})
assert st.minigame_count == k1 + 1                    # unique widget key per launch
assert st.pending_minigame["skin"] == "chalk"         # explicit skin respected
st.save_path().unlink(missing_ok=True)

# --- coverage table shape ---
names = {"generic": "G", "cthulhu": "C"}
rows = cat.coverage_rows(names)
assert len(rows) == len(cat.CATALOG) and all(len(r) == 3 for r in rows)
assert all(v in ("✓", "—") for r in rows for v in r[1:])

print("test_minigame_catalog: all checks passed")
