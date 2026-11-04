"""Game state dataclasses + JSON persistence. Single source of truth for a running session."""
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

SAVES_DIR = Path(__file__).resolve().parent.parent / "data" / "saves"


def slugify(name: str) -> str:
    # Keep unicode word chars so non-ASCII names (e.g. 中文名) get distinct ids, not all "char".
    s = re.sub(r"[^\w]+", "_", (name or "").strip().lower(), flags=re.UNICODE).strip("_")
    return s or "char"


def unique_id(existing_ids, base: str) -> str:
    """Return base, or base_2/base_3/... so ids never collide (widget keys depend on this)."""
    if base not in existing_ids:
        return base
    n = 2
    while f"{base}_{n}" in existing_ids:
        n += 1
    return f"{base}_{n}"


@dataclass
class CharacterState:
    id: str
    name: str
    controller: str = "human"        # "human" | "ai"
    player_label: str = ""           # e.g. "Leo" / "Player 2"
    hp: int = 10
    max_hp: int = 10
    stress: int = 50                 # SAN in CoC; 0/ignored if system has no stress mechanic
    max_stress: int = 50
    skills: dict = field(default_factory=dict)
    inventory: list = field(default_factory=list)
    personality: str = ""            # used when AI-controlled
    backstory: str = ""
    status: str = "active"           # active | unconscious | insane | dead
    # --- inner life (AI-controlled characters) ---
    private_thoughts: list = field(default_factory=list)  # recent inner monologue, rolling window
    memory_summary: str = ""         # their own chronicle: what THEY lived through, in their voice
    relationships: dict = field(default_factory=dict)  # name -> what they privately think of them
    item_notes: dict = field(default_factory=dict)     # item name -> description, filled on inspect
    luck: int = 0                    # spendable Luck, in systems that have it


@dataclass
class GameState:
    schema_version: int = 2
    campaign_file: str = ""
    slot: str = ""                   # "" is the first save; further games of a campaign get their own
    rule_system: str = "coc7e"
    scene_id: str = ""
    visited_scenes: list = field(default_factory=list)
    discovered_clues: list = field(default_factory=list)
    triggered_events: list = field(default_factory=list)
    characters: list = field(default_factory=list)   # list[CharacterState], order = turn order
    active_character_id: str = ""
    party_mode: str = "keeper"       # solo | keeper | active (governs AI characters only)
    language: str = "auto"           # auto | en | zh | yue
    god_mode: bool = False           # keeper & companions play along with the player, never block
    companion_style: str = "player"  # player (table register: intent+dialogue) | cinematic (prose)
    turn_count: int = 0
    summary: str = ""
    messages: list = field(default_factory=list)         # [{role, name?, content}] sent to LLM (recent)
    messages_archive: list = field(default_factory=list)  # compacted out, UI-only
    pending_roll: dict = None        # {character_id, skill, target, difficulty, reason}
    pending_minigame: dict = None    # {type, ...payload} set by the keeper's control block
    pending_push: dict = None        # a failed roll waiting: accept, push, or spend Luck
    minigame_count: int = 0          # total minigames launched — gives each a unique widget key
    rolls_since_action: int = 0      # human rolls since the player last acted (chain guard)
    dice_log: list = field(default_factory=list)
    ending: dict = None              # {outcome, description} once the story concludes
    stats: dict = field(default_factory=dict)  # rolls/crits/fumbles counters for the end screen

    # --- lookups ---
    def get_character(self, char_id: str):
        for c in self.characters:
            if c.id == char_id:
                return c
        return None

    def active_character(self):
        return self.get_character(self.active_character_id)

    def human_characters(self):
        return [c for c in self.characters if c.controller == "human"]

    def ai_characters(self):
        return [c for c in self.characters if c.controller == "ai" and c.status == "active"]

    # --- persistence ---
    def save_path(self) -> Path:
        stem = Path(self.campaign_file).stem or "game"
        return SAVES_DIR / (f"{stem}.{self.slot}.save.json" if self.slot else f"{stem}.save.json")

    def save(self):
        SAVES_DIR.mkdir(parents=True, exist_ok=True)
        self.save_path().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2),
                                    encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        data = dict(data)
        data["characters"] = [CharacterState(**c) for c in data.get("characters", [])]
        return cls(**data)

    @classmethod
    def load(cls, path) -> "GameState":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def saves_of(campaign_file) -> list:
    """[{slot, turn, scene_id, when}] for this campaign's saves, newest first."""
    stem = Path(campaign_file).stem
    out = []
    for p in sorted(SAVES_DIR.glob(f"{stem}*.save.json"), key=lambda f: -f.stat().st_mtime):
        slot = p.name[len(stem):-len(".save.json")].lstrip(".")
        if p.name[len(stem):][:1] not in (".",):       # another campaign whose name starts the same
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"slot": slot, "turn": d.get("turn_count", 0), "scene_id": d.get("scene_id", ""),
                    "when": int(p.stat().st_mtime), "ended": bool(d.get("ending"))})
    return out


def save_path_of(campaign_file, slot: str = "") -> Path:
    return GameState(campaign_file=str(campaign_file), slot=slot).save_path()


def save_exists(campaign_file) -> Path | None:
    p = SAVES_DIR / f"{Path(campaign_file).stem}.save.json"
    return p if p.exists() else None


if __name__ == "__main__":
    # self-check: save/load round-trip
    st = GameState(campaign_file="demo.yaml", scene_id="s1",
                   characters=[CharacterState(id="hero", name="Hero", skills={"Spot Hidden": 70})],
                   active_character_id="hero", pending_roll={"character_id": "hero", "skill": "Spot Hidden",
                                                             "target": 70, "difficulty": "regular", "reason": "x"})
    st.save()
    st2 = GameState.load(st.save_path())
    assert asdict(st) == asdict(st2), "round-trip mismatch"
    st.save_path().unlink()
    print("GameState save/load round-trip OK")
