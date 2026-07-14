"""Call of Cthulhu 7th Edition rules — port of the old core/rules.py plus bonus/penalty dice."""
import random

from rules.base import RollResult, RuleSystem, parse_dice, validate_dice

TIER_ORDER = ["Fumble", "Failure", "Regular Success", "Hard Success", "Extreme Success", "Critical Success"]
DIFFICULTY_MIN_TIER = {"regular": "Regular Success", "hard": "Hard Success", "extreme": "Extreme Success"}


def d100(bonus_dice: int = 0, penalty_dice: int = 0) -> int:
    """CoC 7e d100: tens die + units die; bonus/penalty dice add tens dice, take best/worst."""
    net = bonus_dice - penalty_dice
    units = random.randint(0, 9)
    tens_pool = [random.randint(0, 9) * 10 for _ in range(1 + abs(net))]
    tens = min(tens_pool) if net > 0 else max(tens_pool)
    val = tens + units
    return 100 if val == 0 else val


def classify(roll: int, skill: int) -> str:
    if roll == 1:
        return "Critical Success"
    if roll == 100 or (roll >= 96 and skill < 50):
        return "Fumble"
    if roll <= skill:
        if roll <= skill // 5:
            return "Extreme Success"
        if roll <= skill // 2:
            return "Hard Success"
        return "Regular Success"
    return "Failure"


class CoC7e(RuleSystem):
    name = "coc7e"
    label = "Call of Cthulhu 7e"
    difficulty_levels = ["regular", "hard", "extreme"]
    has_stress = True

    def skill_check(self, skill_value: int, difficulty: str = "regular",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        difficulty = difficulty if difficulty in DIFFICULTY_MIN_TIER else "regular"
        roll = d100(bonus_dice, penalty_dice)
        tier = classify(roll, skill_value)
        needed = DIFFICULTY_MIN_TIER[difficulty]
        success = TIER_ORDER.index(tier) >= TIER_ORDER.index(needed) and tier != "Fumble"
        detail = f"d100={roll} vs skill {skill_value} ({difficulty}) -> {tier}" \
                 + ("" if success else f" (needed {needed})")
        return RollResult(roll=roll, target=skill_value, tier=tier, success=success, detail=detail)

    def stress_check(self, current: int, loss_expr: str):
        """CoC Sanity roll. loss_expr: '1d4', '5', or 'success/fail' form '0/1d4'."""
        loss_expr = str(loss_expr).strip()
        if "/" in loss_expr:
            on_success, on_fail = loss_expr.split("/", 1)
        else:
            on_success, on_fail = "0", loss_expr
        roll = random.randint(1, 100)
        passed = roll <= current
        loss = parse_dice(on_success if passed else on_fail)
        new = max(0, current - loss)
        line = (f"SAN roll d100={roll} vs {current} -> "
                f"{'Success' if passed else 'Failure'}, lost {loss} SAN ({current} -> {new})")
        return new, line

    def validate_loss_expr(self, loss_expr) -> bool:
        parts = str(loss_expr).strip().split("/")
        return 1 <= len(parts) <= 2 and all(validate_dice(p) for p in parts)

    def keeper_rules_prompt(self) -> str:
        return """=== RULE SYSTEM: Call of Cthulhu 7th Edition ===
- Skill checks are d100 roll-under. Difficulties: regular (<= skill), hard (<= half), extreme (<= fifth).
- If the player describes an action without naming a skill, YOU pick the most fitting skill and difficulty.
- Request rolls ONLY for uncertain, consequential actions. Trivial actions just succeed.
- Sanity: request a stress_check when a character witnesses something horrific. Use standard
  loss expressions like "0/1d4" (success loss / failure loss), "1/1d6", "1d4/1d8". Escalate with the horror.
- Fumbles (96-100 vs skill under 50, or 100) mean disaster; Critical (01) means an exceptional boon.
- Be fair but unforgiving. The cosmos does not care about the investigators."""

    def character_sheet_defaults(self) -> dict:
        return {
            "HP": 10, "Stress": 50,
            "Skills": {
                "Spot Hidden": 45, "Listen": 40, "Library Use": 40, "Psychology": 30,
                "Occult": 20, "First Aid": 30, "Brawl": 40, "Dodge": 35,
                "Persuade": 30, "Fast Talk": 30, "Stealth": 30, "Athletics": 35,
            },
        }

    def dice_spec(self) -> dict:
        return {"kind": "d100_two_d10"}

    def default_skill_target(self) -> int:
        return 50
