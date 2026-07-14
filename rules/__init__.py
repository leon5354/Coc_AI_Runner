from rules.base import RuleSystem
from rules.basic_d100 import BasicD100
from rules.coc7e import CoC7e

_SYSTEMS = {cls.name: cls for cls in (CoC7e, BasicD100)}


def get_system(name: str) -> RuleSystem:
    if name not in _SYSTEMS:
        raise KeyError(f"Unknown rule system {name!r}. Available: {sorted(_SYSTEMS)}")
    return _SYSTEMS[name]()


def available_systems() -> list:
    return sorted(_SYSTEMS)
