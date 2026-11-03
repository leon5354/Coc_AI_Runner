"""Minimal generic d100 system — proves the rule-system seam. No stress mechanic."""
import random

from rules.base import RollResult, RuleSystem, percentile_dice


class BasicD100(RuleSystem):
    name = "basic_d100"
    label = "Basic d100"
    difficulty_levels = ["regular"]

    def skill_check(self, skill_value: int, difficulty: str = "regular",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        target = skill_value + 10 * (bonus_dice - penalty_dice)
        roll = random.randint(1, 100)
        if roll <= 5:
            tier, success = "Critical Success", True
        elif roll >= 96:
            tier, success = "Fumble", False
        elif roll <= target:
            tier, success = "Success", True
        else:
            tier, success = "Failure", False
        detail = f"d100={roll} vs skill {target} -> {tier}"
        return RollResult(roll=roll, target=target, tier=tier, success=success, detail=detail,
                          dice=percentile_dice(roll))

    def dice_spec(self) -> dict:
        return {"kind": "d100_two_d10"}

    def keeper_rules_prompt(self) -> str:
        return """=== RULE SYSTEM: Basic d100 ===
- Skill checks are d100 roll-under: <= skill succeeds. 01-05 critical, 96-100 fumble.
- Only difficulty "regular" exists. There is no sanity/stress mechanic — never request stress_check.
- Request rolls only for uncertain, consequential actions."""

    def character_sheet_defaults(self) -> dict:
        return {
            "HP": 10, "Stress": 0,
            "Skills": {"Perception": 50, "Athletics": 50, "Persuasion": 40,
                       "Knowledge": 40, "Combat": 40, "Stealth": 40},
        }
