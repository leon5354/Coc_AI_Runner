"""Offline self-checks for the rules package. Run: python test_rules.py"""
import rules
from rules.base import parse_dice, validate_dice
from rules.coc7e import classify, d100

coc = rules.get_system("coc7e")
basic = rules.get_system("basic_d100")

# tier boundaries (skill 60: extreme <=12, hard <=30, regular <=60)
assert classify(1, 60) == "Critical Success"
assert classify(12, 60) == "Extreme Success"
assert classify(13, 60) == "Hard Success"
assert classify(30, 60) == "Hard Success"
assert classify(31, 60) == "Regular Success"
assert classify(60, 60) == "Regular Success"
assert classify(61, 60) == "Failure"
assert classify(96, 40) == "Fumble"      # 96+ fumbles when skill < 50
assert classify(96, 60) == "Failure"     # ...but not at skill >= 50
assert classify(100, 90) == "Fumble"

# difficulty gating
r = coc.skill_check(60, "extreme")
assert r.success == (r.roll <= 12 or r.roll == 1) and r.roll >= 1

# d100 range incl. bonus/penalty dice
for _ in range(500):
    assert 1 <= d100() <= 100
    assert 1 <= d100(bonus_dice=2) <= 100
    assert 1 <= d100(penalty_dice=2) <= 100

# dice expressions
assert validate_dice("1d4") and validate_dice("2d6+1") and validate_dice("0") and validate_dice(5)
assert not validate_dice("banana") and not validate_dice("d")
for _ in range(100):
    assert 1 <= parse_dice("1d4") <= 4
    assert 3 <= parse_dice("2d6+1") <= 13
assert parse_dice("0") == 0 and parse_dice(7) == 7

# sanity / stress
assert coc.validate_loss_expr("0/1d4") and coc.validate_loss_expr("1d6") and coc.validate_loss_expr("5")
assert not coc.validate_loss_expr("x/y")
new, line = coc.stress_check(50, "1d4/1d8")
assert 42 <= new <= 50 and "SAN" in line
new, _ = coc.stress_check(0, "1d100")   # can't go below 0
assert new == 0
assert basic.stress_check(50, "1d4") is None   # no stress mechanic

# registry
assert rules.available_systems() == ["basic_d100", "coc7e"]
try:
    rules.get_system("nope")
    raise AssertionError("should have raised")
except KeyError:
    pass

print("test_rules: all checks passed")
