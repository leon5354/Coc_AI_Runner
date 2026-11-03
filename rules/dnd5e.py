"""Dungeons & Dragons 5e — d20 + modifier vs DC, with advantage/disadvantage."""
import random

from rules.base import RollResult, RuleSystem

# difficulty label -> DC (Difficulty Class)
DC = {"easy": 10, "medium": 15, "hard": 20, "very_hard": 25}


class DnD5e(RuleSystem):
    name = "dnd5e"
    label = "D&D 5e"
    difficulty_levels = ["easy", "medium", "hard", "very_hard"]
    has_stress = False   # no sanity mechanic

    def skill_check(self, skill_value: int, difficulty: str = "medium",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        difficulty = difficulty if difficulty in DC else "medium"
        dc = DC[difficulty]
        net = bonus_dice - penalty_dice     # >0 advantage, <0 disadvantage
        rolls = [random.randint(1, 20) for _ in range(1 + abs(net))]
        d20 = max(rolls) if net > 0 else (min(rolls) if net < 0 else rolls[0])
        total = d20 + skill_value
        if d20 == 20:
            tier, success = "Critical Success", True
        elif d20 == 1:
            tier, success = "Fumble", False
        else:
            success = total >= dc
            tier = "Success" if success else "Failure"
        adv = " (advantage)" if net > 0 else (" (disadvantage)" if net < 0 else "")
        detail = f"d20={d20}{adv} {skill_value:+d} = {total} vs DC {dc} ({difficulty}) -> {tier}"
        kept = rolls.index(d20)
        dice = [{"die": "d20", "value": r, "kept": i == kept} for i, r in enumerate(rolls)]
        return RollResult(roll=d20, target=dc, tier=tier, success=success, detail=detail, dice=dice)

    def roll_preview(self, skill_value: int, difficulty: str) -> str:
        return f"d20 {skill_value:+d} vs DC {DC.get(difficulty, 15)}"

    def keeper_rules_prompt(self) -> str:
        return """=== RULE SYSTEM: Dungeons & Dragons 5e ===
- Ability/skill checks are d20 + the character's modifier vs a Difficulty Class (DC).
- Difficulties map to DC: easy=10, medium=15, hard=20, very_hard=25. Pick one per check.
- If the player describes an action without a skill, choose the fitting ability/skill.
- Advantage: add "bonus": 1 to roll_request (the engine rolls two d20, keeps the best).
  Disadvantage: add "penalty": 1 (keeps the worst). Only call for rolls on uncertain, meaningful actions.
- Natural 20 is a critical success, natural 1 an automatic failure.
- There is no sanity mechanic — never request stress_check. Harm is hp_change (Hit Points)."""

    def character_sheet_defaults(self) -> dict:
        return {
            "HP": 12, "Stress": 0,
            "Skills": {  # total modifiers (ability + proficiency)
                "Athletics": 3, "Acrobatics": 2, "Perception": 4, "Investigation": 3,
                "Insight": 3, "Persuasion": 2, "Deception": 1, "Stealth": 3,
                "Arcana": 2, "History": 2, "Survival": 2, "Intimidation": 1,
            },
        }

    def dice_spec(self) -> dict:
        return {"kind": "single", "sides": 20}

    def default_skill_target(self) -> int:
        return 2   # a modest +2 modifier for an unlisted skill
