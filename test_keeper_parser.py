"""Offline parser tests for keeper.parse_response. Run: python test_keeper_parser.py"""
from core.keeper import Control, parse_response

# 1. clean fenced block
text = '''The door creaks open.

```json
{"roll_request": {"character": "player", "skill": "Spot Hidden", "difficulty": "regular", "reason": "x"},
 "stress_check": null, "hp_change": null, "clues_discovered": [], "scene_transition": null, "characters_act": []}
```'''
n, c = parse_response(text)
assert n == "The door creaks open."
assert c.roll_request["skill"] == "Spot Hidden"

# 2. missing fence, bare trailing json
text = 'You find the journal.\n\n{"clues_discovered": ["corwin_journal"], "scene_transition": null}'
n, c = parse_response(text)
assert n == "You find the journal."
assert c.clues_discovered == ["corwin_journal"] and c.roll_request is None

# 3. prose only — degrades to empty control
n, c = parse_response("The rain hammers the windows. What do you do?")
assert c == Control.empty() and "rain" in n

# 4. malformed json in fence -> fallback finds nothing -> empty control, prose kept
text = 'Something moves.\n\n```json\n{"roll_request": {broken}\n```'
n, c = parse_response(text)
assert c == Control.empty() and "Something moves." in n

# 5. legacy token stripped
n, c = parse_response("Please roll Spot Hidden. [ROLL_REQUIRED]")
assert "[ROLL_REQUIRED]" not in n and c == Control.empty()

# 6. extra/unknown keys ignored, wrong-typed fields ignored
text = '''Done.
```json
{"roll_request": "not a dict", "clues_discovered": ["a", 5, "b"], "scene_transition": 3,
 "mystery_key": true, "characters_act": ["vale"]}
```'''
n, c = parse_response(text)
assert c.roll_request is None and c.clues_discovered == ["a", "b"]
assert c.scene_transition is None and c.characters_act == ["vale"]

# 7. json object embedded mid-prose with a later trailing one — takes the last fence
text = '''First: ```json
{"clues_discovered": ["early"]}
``` more prose ```json
{"clues_discovered": ["late"]}
```'''
n, c = parse_response(text)
assert c.clues_discovered == ["late"]

# 8. empty / None input
n, c = parse_response("")
assert n == "" and c == Control.empty()

# 9. minigame: valid type accepted, unknown type dropped
text = '''The paper smells of lemon.
```json
{"minigame": {"type": "burn_reveal", "hidden_text": "SECRET", "context": "a blank page"}}
```'''
n, c = parse_response(text)
assert c.minigame == {"type": "burn_reveal", "hidden_text": "SECRET", "context": "a blank page"}
n, c = parse_response('X\n```json\n{"minigame": {"type": "tetris"}}\n```')
assert c.minigame is None

print("test_keeper_parser: all checks passed")
