"""D&D 5e + WFRP rule systems, and the lore canon plumbing. Run: python test_new_systems.py"""
import rules
from rules.dnd5e import DC

# --- registry ---
assert set(rules.available_systems()) >= {"coc7e", "dnd5e", "wfrp", "basic_d100"}

# --- D&D 5e: d20 + mod vs DC, no stress ---
dnd = rules.get_system("dnd5e")
assert dnd.has_stress is False
assert dnd.stress_check(10, "1d4") is None          # no sanity mechanic
seen_tiers = set()
for _ in range(3000):
    r = dnd.skill_check(5, "medium")                # +5 vs DC 15 -> need d20>=10
    assert 1 <= r.roll <= 20 and r.target == 15
    if r.roll == 20:
        assert r.tier == "Critical Success" and r.success
    elif r.roll == 1:
        assert r.tier == "Fumble" and not r.success
    else:
        assert r.success == (r.roll + 5 >= 15)
    seen_tiers.add(r.tier)
assert {"Success", "Failure", "Critical Success", "Fumble"} <= seen_tiers
# advantage keeps the better of two d20 -> higher success rate than disadvantage
adv = sum(dnd.skill_check(0, "hard", bonus_dice=1).success for _ in range(4000))
dis = sum(dnd.skill_check(0, "hard", penalty_dice=1).success for _ in range(4000))
assert adv > dis, (adv, dis)
assert DC["easy"] < DC["hard"]

# --- WFRP: d100 roll-under, has a Resolve/stress mechanic ---
wf = rules.get_system("wfrp")
assert wf.has_stress is True
for diff in wf.difficulty_levels:
    r = wf.skill_check(45, diff)
    assert 1 <= r.roll <= 100
    if r.roll != 100 and r.roll % 11 != 0:
        assert r.success == (r.roll <= r.target)
# easy makes the target higher (easier) than hard
easy_t = wf.skill_check(45, "easy").target
hard_t = wf.skill_check(45, "hard").target
assert easy_t > hard_t
# stress erodes Resolve and never goes below 0
assert wf.validate_loss_expr("0/1d10") and not wf.validate_loss_expr("x")
new, line = wf.stress_check(40, "1d10/1d10")
assert 30 <= new <= 39 and "Resolve" in line
assert wf.stress_check(0, "1d100")[0] == 0

# --- lore: term extraction + graceful no-wiki path (no network) ---
from agents import lore
assert lore._concept_terms("A haunting at Miskatonic University with a cursed tome")[0] == "Miskatonic University"
assert lore.DEFAULT_SETTING["dnd5e"] == "forgotten_realms"


class _MockLLM:
    def chat(self, *a, **k): return "A canon brief."


assert lore.fetch_canon("generic", "anything", _MockLLM()) == ""     # generic -> no lookup
assert lore.fetch_pages("generic", ["x"]) == []

# scripter bakes setting/canon into the YAML when a fetcher returns canon
import yaml
from agents import scripter as scripter_mod


class FakeScripter(scripter_mod.Scripter):
    def __init__(self):
        pass   # skip real LLMClient
    class _C:
        def get_completion(self, *a, **k):
            return ('{"schema_version":2,"rule_system":"dnd5e","title":"T","introduction":"I",'
                    '"plot_outline":"P","scenes":[{"id":"s1","name":"S","description":"D",'
                    '"clues":[],"items":[],"stress_events":[],"exits":[]}]}')
    client = _C()


import agents.lore as _lore
_orig = _lore.fetch_canon
_lore.fetch_canon = lambda setting, concept, llm, **k: "FR canon: Waterdeep, the Sword Coast."
try:
    text, err = FakeScripter().generate_campaign("a heist in Waterdeep", rule_system="dnd5e",
                                                  setting="forgotten_realms")
finally:
    _lore.fetch_canon = _orig
assert err is None, err
data = yaml.safe_load(text)
assert data["setting"] == "forgotten_realms" and "Waterdeep" in data["canon"]

# keeper puts canon into its brief
from core.keeper import build_system_prompt
from core.campaign import Campaign
camp = Campaign(data={"title": "T", "plot_outline": "P", "canon": "Waterdeep is a city.",
                      "endings": [], "scenes": []})
sp = build_system_prompt(camp, dnd)
assert "Waterdeep is a city." in sp and "stay faithful" in sp.lower()

print("test_new_systems: all checks passed")
