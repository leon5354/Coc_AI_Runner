"""Offline web-API test: full mock session over HTTP (start, act, roll gate, minigame, undo).
Run: python test_server.py"""
import json
import os
import tempfile
from pathlib import Path

os.environ["MOCK_LLM"] = "1"

from core import game_state  # noqa: E402
game_state.SAVES_DIR = Path(tempfile.mkdtemp())  # keep test saves away from real ones

from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402

assert game_state.SAVES_DIR.name == "mock"   # mock games never touch real saves
c = TestClient(app)


def turn(path, body=None):
    """POST a streamed turn; return the parsed NDJSON lines."""
    r = c.post(path, json=body or {})
    assert r.status_code == 200, (path, r.status_code, r.text)
    lines = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert lines[-1].get("done"), lines[-1]
    assert not lines[-1].get("error"), lines[-1]["error"]
    return lines


meta = c.get("/api/meta").json()
assert meta["mock"] is True
assert any(x["file"] == "the_haunting.yaml" for x in meta["campaigns"])
assert "burn_reveal" in meta["minigames"]

assert c.get("/api/game").json() is None
assert c.post("/api/game/act", json={"text": "hi"}).status_code == 409   # no game yet
assert c.post("/api/game/start", json={"file": "../.env"}).status_code == 404   # no path tricks

g = c.post("/api/game/start", json={"file": "the_haunting.yaml", "restart": True}).json()
pid = g["state"]["characters"][0]["id"]
assert g["title"] and g["scene_name"] and g["mood"] in {"daylight", "dusk", "night", "unearthly"}
assert g["can_undo"] is False

# turn 1: plain narration, streamed as beats
lines = turn("/api/game/act", {"character_id": pid, "text": "I ask Knott about the house."})
assert lines[0]["label"]                        # first beat arrives before the keeper answers
assert lines[-1]["game"]["state"]["messages"][-1]["role"] == "keeper"

# turn 2: keeper requests a roll -> gate
lines = turn("/api/game/act", {"character_id": pid, "text": "I read the tenant letters."})
pr = lines[-1]["game"]["state"]["pending_roll"]
assert pr and pr["skill"] == "Library Use"
assert c.post("/api/game/act", json={"character_id": pid, "text": "x"}).status_code == 409  # gated

# roll: dice result rides on the first line, keeper outcome after (clue + stress applied)
lines = turn("/api/game/roll")
assert "dice" in lines[0] and lines[0]["dice"]["roll"] >= 1
st = lines[-1]["game"]["state"]
assert st["pending_roll"] is None
assert any(m["role"] == "dice" for m in st["messages"])
assert c.post("/api/game/roll").status_code == 409   # nothing pending now
assert c.get("/api/game").json()["can_undo"] is True

# settings + validation
g = c.patch("/api/game/settings", json={"language": "en", "party_mode": "solo"}).json()
assert g["state"]["language"] == "en" and g["state"]["party_mode"] == "solo"
assert c.patch("/api/game/settings", json={"party_mode": "chaos"}).status_code == 400

# minigame tester -> gate -> result feeds the keeper
g = c.post("/api/game/minigame/launch", json={"type": "cipher"}).json()
assert g["state"]["pending_minigame"]["type"] == "cipher"
assert c.post("/api/game/minigame/launch", json={"type": "cipher"}).status_code == 409
lines = turn("/api/game/minigame", {"result": "The player SOLVED the cipher"})
assert lines[-1]["game"]["state"]["pending_minigame"] is None

# characters: edit, flip to AI, add
g = c.patch(f"/api/game/characters/{pid}", json={"backstory": "A tired archivist."}).json()
assert g["state"]["characters"][0]["backstory"] == "A tired archivist."
g = c.post("/api/game/characters", json={"name": "Mina", "controller": "human"}).json()
assert any(ch["name"] == "Mina" for ch in g["state"]["characters"])
mina = [ch for ch in g["state"]["characters"] if ch["name"] == "Mina"][0]["id"]
g = c.patch(f"/api/game/characters/{mina}", json={"controller": "ai"}).json()
assert [ch for ch in g["state"]["characters"] if ch["id"] == mina][0]["controller"] == "ai"

# undo rewinds one step; export is markdown
n = len(c.get("/api/game").json()["state"]["messages"])
turn("/api/game/act", {"character_id": pid, "text": "I wait."})
assert len(c.get("/api/game").json()["state"]["messages"]) > n
assert c.post("/api/game/undo").status_code == 200
assert len(c.get("/api/game").json()["state"]["messages"]) == n
assert c.get("/api/game/export").text.startswith("# ")

# talk: the mock gives companions their own voice, never the keeper's script + JSON
c.patch("/api/game/settings", json={"party_mode": "keeper"})
lines = turn("/api/game/talk", {"character_id": pid, "text": "Professor?"})
last = lines[-1]["game"]["state"]["messages"][-1]
assert last["role"] == "companion" and "```" not in last["content"], last
c.post("/api/game/undo")

# resume: a fresh start without restart picks up the save
g = c.post("/api/game/start", json={"file": "the_haunting.yaml"}).json()
assert len(g["state"]["messages"]) == n

print("test_server: all checks passed")
