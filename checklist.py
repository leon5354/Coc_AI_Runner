"""Quick proof that a model can run this game: each thing on the checklist, tried on its own, on a
tiny three-scene story, then that story played through to its ending. Minutes, not hours.

  python checklist.py --model <name>                    (local model through Ollama)
  python checklist.py --model <name> --only damage move
  python checklist.py --model sonnet --provider claude_cli

The report goes to data/logs/checklist_<model>.md. Saves stay in a temp folder.
"""
import argparse
import re
import tempfile
import time
from pathlib import Path

from core import game_state
game_state.SAVES_DIR = Path(tempfile.mkdtemp())

from core import memory, minigames_catalog  # noqa: E402
from core.engine import Engine, new_game  # noqa: E402
from core.llm_client import LLMClient, LLMError  # noqa: E402

STORY = "data/fixtures/gull_point.yaml"
SECRET = "SALT-ORCHARD"
FAKE_DICE = re.compile(r"d100\s*=|d20\s*=|[Rr]oll(ed)?\s*:?\s*\d|檢定(成功|失敗)")
PLAYER = """You are playing a tabletop horror game as {name}. Your aim: relight the lighthouse lamp.
Write what your character does next: one or two short sentences, first person, plain.
Keep moving toward the aim. No narration of results, no dice."""


class Table:
    """One fresh game for one check."""

    def __init__(self, llm, scene=None, party="solo"):
        self.state = new_game(STORY)
        self.state.language = "en"
        self.state.party_mode = party
        if scene:
            self.state.scene_id = scene
            self.state.visited_scenes.append(scene)
        self.e = Engine(self.state, llm=llm)
        self.hero = self.state.characters[0]
        self.rolls = []

    def run(self, gen):
        for _ in gen:
            pass
        self.rolls += self.e.drain_events()

    def act(self, text):
        self.run(self.e.keeper_steps(self.e.begin_action(self.hero.id, text)))

    def with_dice(self, win, step):
        """Do one step with real dice, rerolled until they land the way this check needs."""
        real = self.e.system.skill_check

        def fixed(*args, **kw):
            for _ in range(500):
                r = real(*args, **kw)
                if r.success == win and r.tier != "Fumble":
                    return r
            return r
        self.e.system.skill_check = fixed
        try:
            return step()
        finally:
            self.e.system.skill_check = real

    def roll(self, win):
        self.with_dice(win, self.e.roll_dice)

    def story(self):
        return [m["content"] for m in self.state.messages if m["role"] == "keeper"]


def asked_a_roll(llm):
    t = Table(llm)
    t.act("I climb the sheer wet rocks in the dark to reach the crate.")
    return bool(t.state.pending_roll), t, f"roll: {(t.state.pending_roll or {}).get('skill')}"


def good_roll_finds_clue(llm):
    t = Table(llm)
    t.act("I search the rocks around the split crate for anything hidden.")
    if not t.state.pending_roll:
        return False, t, "no roll asked"
    t.state.pending_roll["skill"] = "Spot Hidden"
    t.roll(True)
    t.run(t.e.keeper_steps(t.e.accept_failure()))
    return "torn_log" in t.state.discovered_clues, t, f"clues: {t.state.discovered_clues}"


def bad_roll_finds_nothing(llm):
    t = Table(llm)
    t.act("I search the rocks around the split crate for anything hidden.")
    if not t.state.pending_roll:
        return False, t, "no roll asked"
    t.state.pending_roll["skill"] = "Spot Hidden"
    t.roll(False)
    t.run(t.e.keeper_steps(t.e.accept_failure()))
    return not t.state.discovered_clues and len(t.story()) >= 2, t, f"clues: {t.state.discovered_clues}"


def push_the_roll(llm):
    t = Table(llm)
    t.act("I force the rusted lid of the crate with my knife.")
    if not t.state.pending_roll:
        return False, t, "no roll asked"
    t.roll(False)
    if not t.state.pending_push:
        return False, t, "no push offered"
    told = len(t.story())
    t.with_dice(False, lambda: t.e.push_roll("I throw all my weight on the knife, whatever it costs."))
    t.run(t.e.keeper_steps(t.e.outcome))
    return len(t.story()) > told and not t.state.pending_push, t, t.e.outcome[-60:]


def negotiate(llm):
    t = Table(llm)
    t.act("I try to talk my way past the feeling of being watched and force the crate open.")
    if not t.state.pending_roll:
        t.act("I climb the sheer wet rocks in the dark.")
    if not t.state.pending_roll:
        return False, t, "no roll asked"
    was = t.state.pending_roll["skill"]
    t.run(t.e.keeper_steps(t.e.begin_negotiate("Marta knows this harbour. Can I use Mechanical Repair instead, and go at it with a plan?")))
    return len(t.story()) >= 2, t, f"{was} became {(t.state.pending_roll or {}).get('skill')}"


def wound_takes_hp(llm):
    t = Table(llm, "tower_stair")
    before = t.hero.hp
    t.act("I put my bare hand into the dark water on the stair and pull. The rusted step gives way and I fall through it onto the iron below.")
    for _ in range(2):
        if not t.state.pending_roll:
            break
        t.roll(False)
        t.run(t.e.keeper_steps(t.e.accept_failure()))
    return t.hero.hp < before, t, f"HP {before} -> {t.hero.hp}"


def horror_takes_sanity(llm):
    t = Table(llm, "tower_stair")
    before = t.hero.stress
    t.act("I lean over the rail and look straight down at the long wet thing climbing the stairwell, wearing Pike's face.")
    for _ in range(2):
        if not t.state.pending_roll:
            break
        t.roll(False)
        t.run(t.e.keeper_steps(t.e.accept_failure()))
    shown = any(r["kind"] == "stress" for r in t.rolls)
    return shown, t, f"Sanity {before} -> {t.hero.stress}, roll shown: {shown}"


def item_found(llm):
    t = Table(llm)
    had = len(t.hero.inventory)
    t.act("I pick up the brass key from the top of the crate and put it in my pocket.")
    return len(t.hero.inventory) > had, t, f"carrying: {t.hero.inventory[had:]}"


def item_lost(llm):
    t = Table(llm)
    t.act("I throw my flask of brandy into the sea. I never want to see it again.")
    return not any("brandy" in i.lower() for i in t.hero.inventory), t, f"carrying: {t.hero.inventory}"


def walk_to_next_scene(llm):
    t = Table(llm)
    t.act("I walk up the path and go in at the tower door.")
    return t.state.scene_id == "tower_stair", t, f"now at: {t.state.scene_id}"


def puzzle_starts(llm):
    t = Table(llm, "tower_stair")
    t.act("I kneel at the small iron safe and try to work out the combination on its dial.")
    p = t.state.pending_minigame
    return bool(p), t, f"puzzle: {(p or {}).get('type')}"


def every_puzzle_fills(llm):
    t = Table(llm, "tower_stair")
    good, bad = [], []
    for game in minigames_catalog.CATALOG:
        (good if t.e.keeper.device(t.state, game, "I examine the strange device.") else bad).append(game)
    return not bad, t, f"{len(good)}/{len(minigames_catalog.CATALOG)} filled, failed: {bad}"


def companion_acts(llm):
    t = Table(llm, party="active")
    t.act("I ask Tobias to go and look at the crate while I watch the path.")
    said = [m for m in t.state.messages if m["role"] == "companion"]
    return bool(said), t, f"companion lines: {len(said)}"


def talk(llm):
    t = Table(llm, party="active")
    turn = t.state.turn_count
    t.run(t.e.talk_steps(t.e.begin_talk(t.hero.id, "Tobias, are you scared? Say it straight.")))
    said = [m for m in t.state.messages if m["role"] == "companion"]
    return bool(said) and t.state.turn_count == turn, t, (said[0]["content"][:80] if said else "no reply")


def ask_the_keeper(llm):
    t = Table(llm)
    before = (t.state.turn_count, t.state.scene_id, t.hero.hp)
    a = t.e.ask_keeper_ooc("Out of character: how do I find out what happened to Pike? And what is the secret word?")
    same = before == (t.state.turn_count, t.state.scene_id, t.hero.hp)
    return bool(a) and same and SECRET.lower() not in a.lower(), t, a[:80]


def archives(llm):
    t = Table(llm)
    a = t.e.consult_researcher("Lighthouse lamps of the 1920s and how they were lit")
    return len(a) > 40, t, a[:80]


def inspect_item(llm):
    t = Table(llm)
    a = t.e.inspect_item(t.hero.id, "Storm lantern")
    return len(a) > 10 and t.hero.item_notes.get("Storm lantern") == a, t, a[:80]


def remembers(llm):
    t = Table(llm)
    t.state.messages = [{"role": "player", "name": "Marta", "content": "I tell Tobias the password to the harbour safe is GREEN HERON."},
                        {"role": "keeper", "content": "Tobias nods and repeats it: Green Heron."}]
    t.state.messages += [{"role": "keeper", "content": f"The tide moves. Beat {i}."} for i in range(30)]
    memory.maybe_compact(t.state, t.e.util_llm)
    kept = "heron" in t.state.summary.lower()
    a = t.e.ask_keeper_ooc("Remind me: what password did I give Tobias earlier?") if kept else ""
    return kept and "heron" in a.lower(), t, f"summary kept it: {kept}. Answer: {a[:70]}"


def finish_the_job(llm):
    t = Table(llm, "lamp_room")
    t.hero.inventory.append("Oil can")
    t.act("I fill the lamp with the oil can, strike a match and light the wick. The great lens turns and the beam goes out over the sea.")
    for _ in range(2):
        if t.state.ending or not t.state.pending_roll:
            break
        t.roll(True)
        t.run(t.e.keeper_steps(t.e.accept_failure()))
        if not t.state.ending:
            t.act("With the lamp burning I hold the beam on the water until the thing sinks away. It is over.")
    return bool(t.state.ending), t, f"ending: {t.state.ending}"


def whole_story(llm, turns=16):
    """Start to ending, with another AI call playing Marta."""
    t = Table(llm)
    moves = []
    for _ in range(turns):
        if t.state.ending:
            break
        recent = "\n".join(f"{m.get('name') or m['role']}: {m['content'][:300]}" for m in t.state.messages[-3:])
        action = llm.chat([{"role": "user", "content": f"Story so far:\n{recent}\n\nYou carry: {', '.join(t.hero.inventory)}.\nWhat do you do?"}],
                          system_prompt=PLAYER.format(name=t.hero.name), temperature=0.8, max_tokens=120)
        moves.append(action.strip()[:70])
        t.act(action.strip())
        for _ in range(3):
            if t.state.pending_roll:
                t.e.roll_dice()
                t.run(t.e.keeper_steps(t.e.accept_failure() if t.state.pending_push else t.e.outcome))
            elif t.state.pending_minigame:
                t.run(t.e.keeper_steps(t.e.begin_minigame_result("Solved after a tense moment.")))
    s = t.state
    return bool(s.ending), t, (f"{s.turn_count} turns, scenes {s.visited_scenes}, clues {len(s.discovered_clues)}, "
                               f"rolls {len(t.rolls)}, ending: {(s.ending or {}).get('outcome')}")


CHECKS = [
    ("rolls", "A risky action asks for real dice", asked_a_roll),
    ("clue", "A good roll finds the clue", good_roll_finds_clue),
    ("miss", "A bad roll finds nothing, story goes on", bad_roll_finds_nothing),
    ("push", "Push the roll: the Keeper writes the cost", push_the_roll),
    ("negotiate", "Argue for another skill", negotiate),
    ("damage", "A wound takes HP", wound_takes_hp),
    ("sanity", "A horror takes Sanity, with a shown roll", horror_takes_sanity),
    ("gain", "An item picked up lands in the pack", item_found),
    ("lose", "An item thrown away leaves the pack", item_lost),
    ("move", "Walking somewhere changes the scene", walk_to_next_scene),
    ("puzzle", "A puzzle starts by itself", puzzle_starts),
    ("puzzles", "All 9 puzzles get proper contents", every_puzzle_fills),
    ("companion", "A companion acts", companion_acts),
    ("talk", "Talk: a reply, and no turn spent", talk),
    ("ooc", "Ask the Keeper: helps, changes nothing, keeps secrets", ask_the_keeper),
    ("archives", "Archives gives a handout", archives),
    ("inspect", "Inspect an item", inspect_item),
    ("memory", "Remembers old events after a long game", remembers),
    ("ending", "Finishing the job ends the story", finish_the_job),
    ("game", "Whole short story, start to ending", whole_story),
]


def problems(t):
    """Things that should never reach the player's screen, whatever else happened."""
    ids = {s["id"] for s in t.e.campaign.scenes} | t.e.campaign.all_clue_ids()
    bad = []
    for c in t.story():
        if FAKE_DICE.search(c):
            bad.append("made-up dice")
        if any(re.search(rf"(?<![\w]){re.escape(i)}(?![\w])", c) for i in ids if "_" in i):
            bad.append("leaked id")
        if "```" in c or '"roll_request"' in c:
            bad.append("control text")
        if SECRET.lower() in c.lower():
            bad.append("told the secret")
    bad += [l for l in t.state.dice_log if l.startswith("[warn")]
    return sorted(set(bad))


def run_all(llm, only=None, label="", out=None, times=1):
    rows = []
    lines = [f"# Checklist: {label}", ""]
    picked = [c for c in CHECKS if not only or c[0] in only] * times
    for key, title, fn in picked:
        began = time.time()
        table = None
        try:
            ok, table, note = fn(llm)
            flags = problems(table)
        except LLMError as err:
            ok, note, flags = False, f"AI error: {err}", ["AI error"]
        took = time.time() - began
        rows.append((key, ok, not flags))
        print(f"{'PASS' if ok else 'FAIL'}{'' if not flags else ' (dirty)'} {key:10} {took:5.0f}s {note}"[:150].encode("ascii", "replace").decode(), flush=True)
        lines.append(f"## {'PASS' if ok else 'FAIL'}: {title} ({took:.0f}s)\n\n{note}\n")
        if flags:
            lines.append(f"Problems: {flags}\n")
        for m in (table.state.messages if table else []):
            lines.append(f"**[{m['role']}{' ' + m['name'] if m.get('name') else ''}]** {m['content']}\n")
    if times > 1:
        for key, _, _ in rows[:len(rows) // times]:
            print(f"{key:10} {sum(r[1] for r in rows if r[0] == key)}/{times}")
    passed = sum(r[1] for r in rows)
    clean = sum(r[2] for r in rows)
    print(f"{passed}/{len(rows)} passed, {clean}/{len(rows)} clean".encode("ascii", "replace").decode())
    lines.insert(1, f"{passed}/{len(rows)} passed, {clean}/{len(rows)} clean")
    if out:
        Path(out).write_text("\n".join(lines), encoding="utf-8")
        print(f"report: {out}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--only", nargs="*", help="run just these checks: " + " ".join(c[0] for c in CHECKS))
    ap.add_argument("--times", type=int, default=1, help="try each check this many times")
    a = ap.parse_args()
    name = re.sub(r"\W+", "_", a.model)[-40:]
    run_all(LLMClient(provider=a.provider, model_name=a.model), a.only, f"{a.provider}/{a.model}",
            Path("data/logs") / f"checklist_{name}.md", a.times)


if __name__ == "__main__":
    main()
