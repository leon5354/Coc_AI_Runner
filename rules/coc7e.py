"""Call of Cthulhu 7th Edition rules — port of the old core/rules.py plus bonus/penalty dice."""
import random

from rules.base import RollResult, RuleSystem, parse_dice, percentile_dice, validate_dice

TIER_ORDER = ["Fumble", "Failure", "Regular Success", "Hard Success", "Extreme Success", "Critical Success"]
DIFFICULTY_MIN_TIER = {"regular": "Regular Success", "hard": "Hard Success", "extreme": "Extreme Success"}


def d100_dice(bonus_dice: int = 0, penalty_dice: int = 0):
    """CoC 7e d100: tens die + units die; bonus/penalty dice add tens dice, take best/worst.
    Returns (result, dice). 00 + 0 means 100, the WORST result, so compare totals, not tens."""
    net = bonus_dice - penalty_dice
    units = random.randint(0, 9)
    tens_pool = [random.randint(0, 9) * 10 for _ in range(1 + abs(net))]
    total = lambda t: t + units or 100
    kept = (min if net > 0 else max)(tens_pool, key=total)
    dice = [{"die": "d100", "value": t, "kept": i == tens_pool.index(kept)}
            for i, t in enumerate(tens_pool)]
    return total(kept), dice + [{"die": "d10", "value": units, "kept": True}]


def d100(bonus_dice: int = 0, penalty_dice: int = 0) -> int:
    return d100_dice(bonus_dice, penalty_dice)[0]


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
    can_push = True

    def skill_check(self, skill_value: int, difficulty: str = "regular",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        difficulty = difficulty if difficulty in DIFFICULTY_MIN_TIER else "regular"
        roll, dice = d100_dice(bonus_dice, penalty_dice)
        tier = classify(roll, skill_value)
        needed = DIFFICULTY_MIN_TIER[difficulty]
        success = TIER_ORDER.index(tier) >= TIER_ORDER.index(needed) and tier != "Fumble"
        detail = f"d100={roll} vs skill {skill_value} ({difficulty}) -> {tier}" \
                 + ("" if success else f" (needed {needed})")
        return RollResult(roll=roll, target=skill_value, tier=tier, success=success, detail=detail,
                          dice=dice)

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
        self.last_stress = {"roll": roll, "passed": passed, "dice": percentile_dice(roll)}
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
- Good position or preparation: add "bonus": 1 to roll_request. Bad position: "penalty": 1 (max 2).
- Sanity: request a stress_check when a character witnesses something horrific. Use standard
  loss expressions like "0/1d4" (success loss / failure loss), "1/1d6", "1d4/1d8". Escalate with the horror.
- A player may PUSH a failed roll by trying harder. A pushed roll that fails again must cost them
  something serious: injury, a lost item, a terrible discovery, the enemy arriving.
- Fumbles (96-100 vs skill under 50, or 100) mean disaster; Critical (01) means an exceptional boon.
- Be fair but unforgiving. The cosmos does not care about the investigators."""

    def need(self, skill_value: int, difficulty: str) -> int:
        return {"hard": skill_value // 2, "extreme": skill_value // 5}.get(difficulty, skill_value)

    def roll_preview(self, skill_value: int, difficulty: str) -> str:
        return f"d100 under {self.need(skill_value, difficulty)}"

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
