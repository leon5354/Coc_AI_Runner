"""Canonical campaign schema (v2): load + validate. One schema for the scripter and the engine."""
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

import rules

CAMPAIGNS_DIR = Path(__file__).resolve().parent.parent / "data" / "campaigns"


VALID_MOODS = {"daylight", "dusk", "night", "unearthly"}


class CampaignValidationError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("Campaign validation failed:\n- " + "\n- ".join(problems))


@dataclass
class Campaign:
    data: dict
    path: str = ""

    @property
    def title(self): return self.data.get("title", "Untitled")
    @property
    def rule_system(self): return self.data.get("rule_system", "coc7e")
    @property
    def introduction(self): return self.data.get("introduction", "")
    @property
    def plot_outline(self): return self.data.get("plot_outline", "")
    @property
    def endings(self): return self.data.get("endings", [])
    @property
    def ai_party(self): return self.data.get("ai_party", []) or []
    @property
    def protagonist(self): return self.data.get("protagonist") or None
    @property
    def scenes(self): return self.data.get("scenes", [])

    def scene(self, scene_id: str):
        for s in self.scenes:
            if s.get("id") == scene_id:
                return s
        return None

    def first_scene_id(self) -> str:
        return self.scenes[0]["id"] if self.scenes else ""

    def all_clue_ids(self) -> set:
        return {c["id"] for s in self.scenes for c in s.get("clues", [])}

    def clue(self, clue_id: str):
        for s in self.scenes:
            for c in s.get("clues", []):
                if c.get("id") == clue_id:
                    return c
        return None


def validate(data: dict) -> list:
    """Returns a list of ALL problems (empty = valid)."""
    problems = []
    if not isinstance(data, dict):
        return ["Campaign root must be a mapping"]

    sys_name = data.get("rule_system", "coc7e")
    try:
        system = rules.get_system(sys_name)
    except KeyError:
        problems.append(f"Unknown rule_system {sys_name!r} (available: {rules.available_systems()})")
        system = None

    for key in ("title", "introduction"):
        if not data.get(key):
            problems.append(f"Missing required field: {key}")

    scenes = data.get("scenes") or []
    if not scenes:
        problems.append("Campaign has no scenes")

    scene_ids, clue_ids, event_ids = [], [], []
    for i, s in enumerate(scenes):
        sid = s.get("id")
        label = f"scene[{i}]" + (f" ({sid})" if sid else "")
        if not sid:
            problems.append(f"{label}: missing id")
        elif sid in scene_ids:
            problems.append(f"{label}: duplicate scene id {sid!r}")
        scene_ids.append(sid)
        if not s.get("description"):
            problems.append(f"{label}: missing description")
        if s.get("mood") and s["mood"] not in VALID_MOODS:
            problems.append(f"{label}: mood {s['mood']!r} not in {sorted(VALID_MOODS)}")

        for c in s.get("clues") or []:
            cid = c.get("id")
            if not cid:
                problems.append(f"{label}: clue missing id")
            elif cid in clue_ids:
                problems.append(f"{label}: duplicate clue id {cid!r}")
            clue_ids.append(cid)
            if system and c.get("difficulty") and c["difficulty"] not in system.difficulty_levels:
                problems.append(f"{label}/clue {cid}: difficulty {c['difficulty']!r} not in {system.difficulty_levels}")

        for ev in s.get("stress_events") or []:
            eid = ev.get("id")
            if not eid:
                problems.append(f"{label}: stress_event missing id")
            elif eid in event_ids:
                problems.append(f"{label}: duplicate stress_event id {eid!r}")
            event_ids.append(eid)
            loss = ev.get("loss")
            # systems without a stress mechanic simply ignore stress_events at runtime
            if system and system.has_stress and loss is not None and not system.validate_loss_expr(loss):
                problems.append(f"{label}/event {eid}: unparseable loss {loss!r}")

    for i, s in enumerate(scenes):
        for ex in s.get("exits") or []:
            to = ex.get("to")
            if to not in scene_ids:
                problems.append(f"scene[{i}] ({s.get('id')}): exit to unknown scene {to!r}")

    for j, p in enumerate(data.get("ai_party") or []):
        if not p.get("name"):
            problems.append(f"ai_party[{j}]: missing name")

    return problems


def load(path) -> Campaign:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = validate(data)
    if problems:
        raise CampaignValidationError(problems)
    return Campaign(data=data, path=str(path))


def list_campaigns() -> list:
    """Paths of loadable campaign files (invalid ones are skipped silently)."""
    if not CAMPAIGNS_DIR.exists():
        return []
    return sorted(p for p in CAMPAIGNS_DIR.glob("*.yaml") if not validate(yaml.safe_load(p.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else CAMPAIGNS_DIR / "the_haunting.yaml"
    try:
        c = load(target)
    except CampaignValidationError as e:
        print(e)
        sys.exit(1)
    print(f"OK: {c.title!r} [{c.rule_system}] — {len(c.scenes)} scenes, "
          f"{len(c.all_clue_ids())} clues, {len(c.ai_party)} AI party members")
    for s in c.scenes:
        exits = ", ".join(e["to"] for e in s.get("exits", []))
        print(f"  - {s['id']}: {s['name']} (exits: {exits or 'none'})")
