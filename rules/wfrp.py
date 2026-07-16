"""Warhammer Fantasy Roleplay (4e-flavoured) — d100 roll-under with degrees of success,
plus a Resolve pool that erodes with corruption/terror (mapped onto the stress mechanic)."""
import random

from rules.base import RollResult, RuleSystem, parse_dice, validate_dice

# difficulty label -> modifier applied to the target number
DIFF_MOD = {"easy": +40, "average": +20, "challenging": 0, "hard": -20}


class WFRP(RuleSystem):
    name = "wfrp"
    label = "Warhammer Fantasy RP"
    difficulty_levels = ["easy", "average", "challenging", "hard"]
    has_stress = True    # Resolve / corruption

    def skill_check(self, skill_value: int, difficulty: str = "average",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        difficulty = difficulty if difficulty in DIFF_MOD else "average"
        target = max(3, min(97, skill_value + DIFF_MOD[difficulty] + 10 * (bonus_dice - penalty_dice)))
        roll = random.randint(1, 100)
        success = roll <= target
        sl = (target - roll) // 10   # degrees of success (positive) / failure (negative)
        doubles = roll % 11 == 0     # 11,22,...,99 (and 100 handled below)
        if roll == 100:
            tier, success = "Fumble", False
        elif doubles and success:
            tier = "Critical Success"
        elif doubles and not success:
            tier = "Fumble"
        elif success:
            tier = "Success"
        else:
            tier = "Failure"
        detail = f"d100={roll} vs {target} ({difficulty}) -> {tier} (SL {sl:+d})"
        return RollResult(roll=roll, target=target, tier=tier, success=success, detail=detail)

    def stress_check(self, current: int, loss_expr: str):
        """A Cool/Resolve test against corruption or terror. loss_expr like '0/1d10' or '1d6'."""
        loss_expr = str(loss_expr).strip()
        on_success, on_fail = (loss_expr.split("/", 1) if "/" in loss_expr else ("0", loss_expr))
        roll = random.randint(1, 100)
        passed = roll <= current
        loss = parse_dice(on_success if passed else on_fail)
        new = max(0, current - loss)
        line = (f"Resolve test d100={roll} vs {current} -> "
                f"{'held' if passed else 'shaken'}, lost {loss} Resolve ({current} -> {new})")
        return new, line

    def validate_loss_expr(self, loss_expr) -> bool:
        parts = str(loss_expr).strip().split("/")
        return 1 <= len(parts) <= 2 and all(validate_dice(p) for p in parts)

    def keeper_rules_prompt(self) -> str:
        return """=== RULE SYSTEM: Warhammer Fantasy Roleplay ===
- Skill tests are d100 roll-under a target (characteristic + skill). Difficulties modify the
  target: easy +40, average +20, challenging +0, hard -20. Pick one per test.
- Success Level (SL) = (target - roll)/10; higher is better. Doubles on a success are a
  critical, doubles on a failure a fumble; 100 always fumbles.
- Resolve/corruption: the grim world erodes the mind. Request stress_check when a character
  faces terror, the warp, or moral horror. Loss like "0/1d10" (success/failure). At 0 Resolve
  a character breaks (gains a psychosis).
- The Old World is dangerous and unfair — reward cunning, punish recklessness."""

    def character_sheet_defaults(self) -> dict:
        return {
            "HP": 12, "Stress": 40,   # Wounds, Resolve
            "Skills": {
                "Weapon Skill": 45, "Ballistic Skill": 35, "Perception": 40, "Charm": 30,
                "Stealth": 35, "Cool": 40, "Intuition": 35, "Lore": 25, "Athletics": 35,
                "Intimidate": 30,
            },
        }

    def dice_spec(self) -> dict:
        return {"kind": "d100_two_d10"}

    def default_skill_target(self) -> int:
        return 30
