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
assert "glyph_sequence" in cat.for_setting("forgotten_realms")
assert "glyph_sequence" in cat.for_setting("warhammer_40k")
assert "seance" not in cat.for_setting("warhammer_40k")
for universal in ("burn_reveal", "cipher", "tarot_draw", "dice_duel"):
    for s in ("generic", "cthulhu", "forgotten_realms", "warhammer_fantasy", "warhammer_40k", "???"):
        assert universal in cat.for_setting(s), (universal, s)
# unknown setting -> only universal games
assert all("*" in cat.CATALOG[g]["settings"] for g in cat.for_setting("no_such_setting"))

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
for t in ("glyph_sequence", "dice_duel"):
    n, ctrl = parse_response(f'X\n```json\n{{"minigame": {{"type": "{t}"}}}}\n```')
    assert ctrl.minigame == {"type": t}, t

# --- coverage table shape ---
names = {"generic": "G", "cthulhu": "C"}
rows = cat.coverage_rows(names)
assert len(rows) == len(cat.CATALOG) and all(len(r) == 3 for r in rows)
assert all(v in ("✓", "—") for r in rows for v in r[1:])

print("test_minigame_catalog: all checks passed")
