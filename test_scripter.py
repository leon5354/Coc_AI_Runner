"""Offline scripter test: generation + repair round-trip against the real validator.
Run: python test_scripter.py"""
import json

import yaml

from agents.scripter import Scripter

GOOD = {
    "schema_version": 2, "rule_system": "coc7e",
    "title": "Test Manor", "introduction": "A test intro.", "plot_outline": "Truth.",
    "endings": [{"outcome": "done", "description": "d"}],
    "ai_party": [],
    "scenes": [
        {"id": "start", "name": "Start", "description": "A room.",
         "clues": [{"id": "c1", "description": "d", "skill": "Spot Hidden",
                    "difficulty": "regular", "reveals": "r"}],
         "items": [], "stress_events": [{"id": "e1", "trigger": "t", "loss": "0/1d4"}],
         "exits": [{"to": "end", "condition": "go"}]},
        {"id": "end", "name": "End", "description": "Another room.",
         "clues": [], "items": [], "stress_events": [], "exits": []},
    ],
}
BAD = dict(GOOD, scenes=[dict(GOOD["scenes"][0], exits=[{"to": "nowhere", "condition": "x"}]),
                         GOOD["scenes"][1]])


class StubClient:
    """First call returns invalid campaign, repair call returns the good one."""
    def __init__(self):
        self.calls = 0

    def get_completion(self, prompt, system_prompt=None, json_mode=False, max_tokens=None, **kw):
        self.calls += 1
        return json.dumps(BAD if self.calls == 1 else GOOD)


s = Scripter.__new__(Scripter)   # skip __init__ (no API key needed)
s.client = StubClient()

yaml_text, err = s.generate_campaign("test notes")
assert err is None, err
assert s.client.calls == 2, "repair round-trip should have fired"
data = yaml.safe_load(yaml_text)
assert data["title"] == "Test Manor" and data["scenes"][0]["exits"][0]["to"] == "end"

# both calls bad -> readable error, no crash
s.client = StubClient()
s.client.get_completion = lambda *a, **k: json.dumps(BAD)
yaml_text, err = s.generate_campaign("test notes")
assert yaml_text is None and "nowhere" in err

print("test_scripter: all checks passed")
