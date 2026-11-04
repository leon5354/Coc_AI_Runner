"""Every mechanic, proven. Odds are compared with exact rulebook maths over many rolls, and each
engine effect is driven through a real keeper turn. Run: python test_mechanics.py"""
import json
import random
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest import mock

import rules
from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core.engine import Engine, new_game  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.llm_client import LLMError  # noqa: E402

random.seed(1926)
N = 40000
coc, dnd, wfrp, basic = (rules.get_system(s) for s in ("coc7e", "dnd5e", "wfrp", "basic_d100"))


def rate(system, skill, diff, bonus=0, penalty=0, field="success"):
    rolls = [system.skill_check(skill, diff, bonus, penalty) for _ in range(N)]
    return 100 * sum(getattr(r, field) for r in rolls) / N


def near(got, want, tol=1.0, what=""):
    assert abs(got - want) <= tol, f"{what}: got {got:.2f}%, want {want:.2f}%"


# --- Call of Cthulhu 7e: regular / hard / extreme, tiers, fumble rule ---
near(rate(coc, 50, "regular"), 50, what="coc regular 50")
near(rate(coc, 50, "hard"), 25, what="coc hard 50")
near(rate(coc, 50, "extreme"), 10, what="coc extreme 50")
near(rate(coc, 80, "regular"), 80, what="coc regular 80")
near(rate(coc, 30, "regular"), 30, what="coc regular 30")


def coc_exact(skill, tens_dice, best):
    """Exact chance of d100 <= skill with extra tens dice, by counting every outcome."""
    hits = total = 0
    for u in range(10):
        pools = [[]]
        for _ in range(tens_dice):
            pools = [p + [t * 10] for p in pools for t in range(10)]
        for p in pools:
            vals = [(t + u) or 100 for t in p]
            total += 1
            hits += (min(vals) if best else max(vals)) <= skill
    return 100 * hits / total


near(rate(coc, 50, "regular", bonus=1), coc_exact(50, 2, True), what="coc 1 bonus die")
near(rate(coc, 50, "regular", bonus=2), coc_exact(50, 3, True), what="coc 2 bonus dice")
near(rate(coc, 50, "regular", penalty=1), coc_exact(50, 2, False), what="coc 1 penalty die")
near(rate(coc, 50, "regular", penalty=2), coc_exact(50, 3, False), what="coc 2 penalty dice")
near(rate(coc, 50, "regular", bonus=1, penalty=1), 50, what="coc bonus cancels penalty")

# 00 + 0 is 100, the worst roll: a bonus die must escape it, a penalty die must fall into it
with mock.patch("rules.coc7e.random.randint", side_effect=[0, 0, 3]):   # units 0, tens 00 and 30
    assert coc.skill_check(50, "regular", bonus_dice=1).roll == 30
with mock.patch("rules.coc7e.random.randint", side_effect=[0, 0, 3]):
    assert coc.skill_check(50, "regular", penalty_dice=1).roll == 100

r = coc.skill_check(60, "regular", bonus_dice=2)
kept = [d for d in r.dice if d["die"] == "d100" and d["kept"]]
assert len([d for d in r.dice if d["die"] == "d100"]) == 3 and len(kept) == 1, r.dice
assert (kept[0]["value"] + r.dice[-1]["value"]) % 100 == r.roll % 100

# --- D&D 5e: d20 + modifier vs DC, advantage, natural 1 and 20 ---
near(rate(dnd, 3, "medium"), 45, what="dnd +3 DC15")                      # needs 12+
near(rate(dnd, 3, "medium", bonus=1), 100 * (1 - .55 ** 2), what="dnd advantage")
near(rate(dnd, 3, "medium", penalty=1), 100 * .45 ** 2, what="dnd disadvantage")
near(rate(dnd, -5, "very_hard"), 5, what="nat 20 always hits")
near(rate(dnd, 30, "easy"), 95, what="nat 1 always misses")
r = dnd.skill_check(2, "hard", bonus_dice=1)
assert len(r.dice) == 2 and sum(d["kept"] for d in r.dice) == 1 and r.roll in [d["value"] for d in r.dice]

# --- Warhammer: target modifiers, SL, auto results, doubles ---
near(rate(wfrp, 40, "average"), 60, what="wfrp average +20")
near(rate(wfrp, 40, "challenging"), 40, what="wfrp challenging +0")
near(rate(wfrp, 40, "hard"), 20, what="wfrp hard -20")
near(rate(wfrp, 40, "easy"), 80, what="wfrp easy +40")
near(rate(wfrp, 40, "challenging", bonus=1), 50, what="wfrp bonus +10")
near(rate(wfrp, 1, "hard"), 5, what="wfrp 01-05 always succeed")
near(rate(wfrp, 200, "easy"), 95, what="wfrp 96-100 always fail")
with mock.patch("rules.wfrp.random.randint", return_value=33):
    r = wfrp.skill_check(45, "average")          # target 65
    assert r.success and r.tier == "Critical Success" and "SL +3" in r.detail, r.detail
with mock.patch("rules.wfrp.random.randint", return_value=77):
    r = wfrp.skill_check(45, "average")
    assert not r.success and r.tier == "Fumble" and "SL -1" in r.detail, r.detail

# --- Basic d100 ---
near(rate(basic, 50, "regular"), 50, what="basic 50")
near(rate(basic, 1, "regular"), 5, what="basic crit floor")
near(rate(basic, 100, "regular"), 95, what="basic fumble ceiling")
near(rate(basic, 50, "regular", bonus=1), 60, what="basic bonus")

# --- percentile dice always add back up to the roll ---
for sys_ in (coc, wfrp, basic):
    for _ in range(3000):
        r = sys_.skill_check(50, "regular")
        kept = [d["value"] for d in r.dice if d["kept"]]
        assert (sum(kept) or 100) == r.roll, (r.roll, r.dice)

# --- sanity / resolve checks ---
for s in (coc, wfrp):
    with mock.patch(f"{s.__module__}.random.randint", return_value=10):
        assert s.stress_check(50, "1/5")[0] == 49       # passed: success loss
    with mock.patch(f"{s.__module__}.random.randint", return_value=90):
        assert s.stress_check(50, "1/5")[0] == 45       # failed: failure loss
    with mock.patch(f"{s.__module__}.random.randint", return_value=90):
        assert s.stress_check(3, "1/5")[0] == 0         # never below zero
    assert s.validate_loss_expr("0/1d4") and s.validate_loss_expr("1d6") and not s.validate_loss_expr("lots")
assert dnd.stress_check(50, "1/5") is None and basic.stress_check(50, "1/5") is None

# --- chance + preview shown on the dice table ---
assert coc.roll_preview(60, "hard") == "d100 under 30" and coc.roll_preview(60, "extreme") == "d100 under 12"
assert dnd.roll_preview(3, "hard") == "d20 +3 vs DC 20"
assert wfrp.roll_preview(40, "average") == "d100 under 60"
assert abs(coc.chance(50, "hard") - 25) <= 4 and abs(dnd.chance(3, "medium") - 45) <= 4


# --- engine effects, driven through real keeper turns ---

def ctrl(text="The story moves.", **fields):
    return f"{text}\n\n```json\n{json.dumps(fields, ensure_ascii=False)}\n```"


class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)

    def chat(self, *a, **k):
        return self.replies.pop(0) if self.replies else ctrl("Quiet.")


def fresh(*replies):
    state = new_game("data/campaigns/the_haunting.yaml")
    state.party_mode = "solo"
    llm = Scripted(*replies)
    return Engine(state, llm=llm), state, state.characters[0]


e, st, hero = fresh(ctrl(hp_change={"character": "", "amount": "-1d6"}))
hp = hero.hp
e.submit_action(hero.id, "I fight.")
assert hp - 6 <= hero.hp <= hp - 1, "dice damage rolled by the engine"

e, st, hero = fresh(ctrl(hp_change={"character": "", "amount": "a lot"}))
hp = hero.hp
e.submit_action(hero.id, "x")
assert hero.hp == hp and any("unreadable" in l for l in st.dice_log)

e, st, hero = fresh(ctrl(hp_change={"amount": -99}), ctrl(hp_change={"amount": "+1d4"}),
                    ctrl(hp_change={"amount": -99}), ctrl(hp_change={"amount": -1}))
e.submit_action(hero.id, "hit")
assert hero.hp == 0 and hero.status == "unconscious"
e.submit_action(hero.id, "heal")
assert hero.hp > 0 and hero.status == "active", "healing wakes you"
e.submit_action(hero.id, "hit")
assert hero.status == "unconscious"
e.submit_action(hero.id, "hit")
assert hero.status == "dead", "damage while down kills"

e, st, hero = fresh(ctrl(hp_change={"amount": 50}))
hero.hp = 1
e.submit_action(hero.id, "rest")
assert hero.hp == hero.max_hp, "healing is capped"

e, st, hero = fresh(ctrl(stress_check={"loss": "500/500"}))
e.submit_action(hero.id, "look")
assert hero.stress == 0 and hero.status == "insane"
assert any(ev["kind"] == "stress" for ev in e.drain_events()), "sanity roll shown on the dice table"

e, st, hero = fresh(ctrl(stress_check={"loss": "6/6", "event_id": "evt"}))
e.submit_action(hero.id, "look")
assert any("madness" in l for l in st.dice_log) and "evt" in st.triggered_events

# inventory: gain, lose (loose name match), no duplicates, give, drop, inspect once
e, st, hero = fresh(ctrl(inventory_change={"add": ["Rusty Key", "Rusty Key"], "remove": ["torch"]}))
torch = [i for i in hero.inventory if "torch" in i.lower()][0]
e.submit_action(hero.id, "search")
assert hero.inventory.count("Rusty Key") == 1 and torch not in hero.inventory
vale = st.characters[1]
assert e.give_item(hero.id, vale.id, "Rusty Key") and "Rusty Key" in vale.inventory
assert not e.give_item(hero.id, vale.id, "Rusty Key"), "can't give what you don't have"
assert e.drop_item(vale.id, "rusty key") and "Rusty Key" not in vale.inventory
e.util_llm = Scripted("Heavy brass, warm to the touch.")
item = hero.inventory[0]
assert e.inspect_item(hero.id, item) == "Heavy brass, warm to the touch."
assert e.inspect_item(hero.id, item) == "Heavy brass, warm to the touch.", "cached, no second call"

# clues + scenes: unknown ids are ignored, not trusted
camp = e.campaign
real_clue = sorted(camp.all_clue_ids())[0]
e, st, hero = fresh(ctrl(clues_discovered=[real_clue, "made_up"]), ctrl(scene_transition="nowhere"))
e.submit_action(hero.id, "search")
assert st.discovered_clues == [real_clue]
start = st.scene_id
e.submit_action(hero.id, "go")
assert st.scene_id == start, "unknown scene ignored"
exit_to = camp.scene(start)["exits"][0]["to"]
e, st, hero = fresh(ctrl(scene_transition=exit_to))
e.submit_action(hero.id, "go")
assert st.scene_id == exit_to and exit_to in st.visited_scenes

# bonus dice: stored on the gate, used by the roll, and shown; AI companions use them too
hero_id = st.characters[0].id
e, st, hero = fresh(ctrl(roll_request={"character": hero_id, "skill": "Spot Hidden", "difficulty": "hard",
                                       "advantage": True}), ctrl("It works out."))
e.submit_action(hero.id, "look")
assert st.pending_roll["bonus"] == 1 and st.pending_roll["difficulty"] == "hard"
assert "d100 under" in e.roll_preview()["need"] and 0 <= e.roll_preview()["chance"] <= 100
e.resolve_roll()
ev = e.drain_events()[0]
assert ev["kind"] == "skill" and len([d for d in ev["dice"] if d["die"] == "d100"]) == 2, ev
assert st.stats["rolls"] == 1

e, st, hero = fresh(ctrl(roll_request={"character": "prof_warren_vale", "skill": "Occult", "penalty": 2}), ctrl("Done."))
st.party_mode = "keeper"
e.submit_action(hero.id, "Professor, read it.")
ev = e.drain_events()[0]
assert ev["who"] == st.characters[1].name and len([d for d in ev["dice"] if d["die"] == "d100"]) == 3

# local models get a referee ruling before the story: it can call a roll or a move by itself
class LocalModel(Scripted):
    provider = "ollama"

    def __init__(self, ruling, *replies):
        super().__init__(*replies)
        self.ruling, self.prompts = ruling, []

    def get_completion(self, prompt, **k):
        self.prompts.append(prompt)
        return self.ruling

    def chat(self, messages, **k):
        self.prompts.append(messages[-1]["content"])
        return super().chat()


llm = LocalModel('{"roll": "Spot Hidden", "difficulty": "hard", "bonus": 1, "move_to": null}', "You crouch. Something glints.")
e, st, hero = fresh()
e.set_llm(llm)
e.submit_action(hero.id, "I search the floor.")
assert st.pending_roll["skill"] == "Spot Hidden" and st.pending_roll["difficulty"] == "hard" and st.pending_roll["bonus"] == 1
assert "Spot Hidden roll" in llm.prompts[-1] and "STOP" in llm.prompts[-1], "narrate up to the tension only"
n = len(llm.prompts)
e.resolve_roll()
assert not any("Player's action" in p for p in llm.prompts[n:]), "no referee on a roll outcome"

e, st, hero = fresh()
target = camp.scene(st.scene_id)["exits"][0]["to"]
e.set_llm(LocalModel('{"roll": null, "move_to": "%s"}' % target, "You set off."))
e.submit_action(hero.id, "I go.")
assert st.scene_id == target

e, st, hero = fresh()
e.set_llm(LocalModel('{"roll": "null", "move_to": "the moon"}', "Nothing happens."))
start = st.scene_id
e.submit_action(hero.id, "I wait.")
assert st.pending_roll is None and st.scene_id == start, "bad rulings are ignored"

e, st, hero = fresh()
e.set_llm(LocalModel("not json at all", "It's quiet."))
e.submit_action(hero.id, "I wait.")
assert st.messages[-1]["content"] == "It's quiet.", "a broken referee never stops the turn"

# the referee can start a puzzle; its contents are asked for separately, once per scene
class PuzzleModel(LocalModel):
    def get_completion(self, prompt, **k):
        return self.ruling if "Player's action" in prompt else self.payload


llm = PuzzleModel('{"roll": null, "device": "cipher"}', "A line of symbols.", "More symbols.")
llm.payload = '{"ciphertext": "GSRH", "solution": "this"}'
e, st, hero = fresh()
e.set_llm(llm)
e.submit_action(hero.id, "I read the wall.")
assert st.pending_minigame["type"] == "cipher" and st.pending_minigame["solution"] == "this"
assert "Do not solve it" in llm.prompts[-1]
e.resolve_minigame("The player SOLVED the cipher")
e.submit_action(hero.id, "I read the next wall.")
assert st.pending_minigame is None, "one device per scene"

llm = PuzzleModel('{"roll": null, "device": "cipher"}', "Nothing.")
llm.payload = '{"ciphertext": "GSRH"}'            # no solution: not playable
e, st, hero = fresh()
e.set_llm(llm)
e.submit_action(hero.id, "I read the wall.")
assert st.pending_minigame is None, "a half-made puzzle never starts"

llm = PuzzleModel('{"roll": null, "device": "nonsense"}', "Nothing.")
e, st, hero = fresh()
e.set_llm(llm)
e.submit_action(hero.id, "I read the wall.")
assert st.pending_minigame is None

# a success with the skill of a clue here finds that clue, even if the model forgets
clue = camp.scene(st.scene_id if False else camp.first_scene_id())["clues"][0]
e, st, hero = fresh(ctrl(roll_request={"character": hero_id, "skill": clue["skill"]}), ctrl("You find it."))
hero.skills[clue["skill"]] = 99
e.submit_action(hero.id, "I look.")
with mock.patch("rules.coc7e.random.randint", side_effect=[0, 5]):      # d100 = 50: a success
    e.resolve_roll()
assert clue["id"] in st.discovered_clues

# keeper asks for a roll AND a dead/insane hero: never a gate for someone who can't act
e, st, hero = fresh(ctrl(roll_request={"character": hero_id, "skill": "Dodge"}), ctrl("It ends badly."))
hero.status = "unconscious"
e.submit_action(hero.id, "x")
assert st.pending_roll is None

# an LLM failure stops the turn and writes nothing into the story; undo gets you back
e, st, hero = fresh("[SYSTEM ERROR] The connection to beyond falters... (API Error: boom)")
before = len(st.messages)
try:
    e.submit_action(hero.id, "I act.")
    raise AssertionError("LLM failure must raise")
except LLMError:
    pass
assert not any("SYSTEM ERROR" in m["content"] for m in st.messages)
assert e.undo() and len(e.state.messages) == before

# endings
outcome = camp.endings[0]["outcome"]
e, st, hero = fresh(ctrl("And so it ends.", ending=outcome, roll_request={"character": hero_id, "skill": "Dodge"}))
e.submit_action(hero.id, "finish it")
assert st.ending["outcome"] == outcome and st.ending["description"] and st.pending_roll is None

# free dice tray
e, st, hero = fresh()
ev = e.free_roll("3d6+2")
assert 5 <= ev["roll"] <= 20 and len(ev["dice"]) == 3 and "Free roll" in st.dice_log[-1]
assert len(e.free_roll("d100")["dice"]) == 2
assert e.free_roll("9d6") is None and e.free_roll("1d7") is None and e.free_roll("banana") is None

# saves: mid-roll resume keeps the bonus; old saves without the new fields still load
e, st, hero = fresh(ctrl(roll_request={"character": hero_id, "skill": "Dodge", "bonus": 2}))
e.submit_action(hero.id, "duck")
st.save()
back = GameState.load(st.save_path())
assert back.pending_roll["bonus"] == 2 and asdict(back) == asdict(st)
old = asdict(st)
for k in ("ending", "stats"):
    old.pop(k)
for c in old["characters"]:
    c.pop("item_notes")
assert GameState.from_dict(old).ending is None

print("test_mechanics: all checks passed")
