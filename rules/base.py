"""Rule system interface. Concrete systems live beside this file and register in __init__.py."""
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RollResult:
    roll: int
    target: int
    tier: str          # system-specific, e.g. "Critical Success" .. "Fumble"
    success: bool
    detail: str        # human-readable line for the dice log


_DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def parse_dice(expr) -> int:
    """Roll a dice expression like '2d6+1', '1d4', or a plain int. Raises ValueError on garbage."""
    if isinstance(expr, int):
        return expr
    s = str(expr).strip()
    if s.isdigit():
        return int(s)
    m = _DICE_RE.match(s)
    if not m:
        raise ValueError(f"Unparseable dice expression: {expr!r}")
    num = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    return sum(random.randint(1, sides) for _ in range(num)) + mod


def validate_dice(expr) -> bool:
    """True if parse_dice would accept expr (without rolling)."""
    if isinstance(expr, int):
        return True
    s = str(expr).strip()
    return s.isdigit() or bool(_DICE_RE.match(s))


class RuleSystem(ABC):
    name: str = "base"
    label: str = "Base"
    difficulty_levels: list = ["regular"]
    has_stress: bool = False   # True if the system has a sanity/stress mechanic

    @abstractmethod
    def skill_check(self, skill_value: int, difficulty: str = "regular",
                    bonus_dice: int = 0, penalty_dice: int = 0) -> RollResult:
        ...

    def stress_check(self, current: int, loss_expr: str):
        """Sanity/stress mechanic. Returns (new_value, log_line) or None if the system has none."""
        return None

    def validate_loss_expr(self, loss_expr) -> bool:
        """True if loss_expr is valid for this system's stress mechanic."""
        return False

    @abstractmethod
    def keeper_rules_prompt(self) -> str:
        """System-specific GM instruction block injected into the keeper system prompt."""
        ...

    @abstractmethod
    def character_sheet_defaults(self) -> dict:
        """Default stats for a new character: {HP, Stress, Skills: {...}}. Stress may be 0/absent."""
        ...

    def dice_spec(self) -> dict:
        return {"kind": "single", "sides": 100}

    def default_skill_target(self) -> int:
        return 50
