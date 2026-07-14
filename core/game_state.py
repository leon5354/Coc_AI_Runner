"""Game state dataclasses + JSON persistence. Single source of truth for a running session."""
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

SAVES_DIR = Path(__file__).resolve().parent.parent / "data" / "saves"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "char"


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
    private_thoughts: list = field(default_factory=list)  # AI character's inner monologue (last N)


@dataclass
class GameState:
    schema_version: int = 2
    campaign_file: str = ""
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
    turn_count: int = 0
    summary: str = ""
    messages: list = field(default_factory=list)         # [{role, name?, content}] sent to LLM (recent)
    messages_archive: list = field(default_factory=list)  # compacted out, UI-only
    pending_roll: dict = None        # {character_id, skill, target, difficulty, reason}
    pending_minigame: dict = None    # {type, ...payload} set by the keeper's control block
    dice_log: list = field(default_factory=list)

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
        return SAVES_DIR / f"{stem}.save.json"

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
