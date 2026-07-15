"""Single source of truth for minigames: which exist, which settings they fit, and the
contract text the keeper sees. The UI renderer table and the keeper prompt both derive
from this, so adding a minigame here is step 1 of exactly 2 (step 2: its renderer).

settings: "*" = fits everywhere; otherwise list of setting keys (see agents/lore.SETTING_WIKIS).
sample: payload used by the in-app "Minigame tester" (and manual QA) — keep it playable.
"""

CATALOG = {
    "burn_reveal": {
        "label": "Hidden writing (heat reveal)",
        "settings": ["*"],
        "contract": '''{"type": "burn_reveal", "hidden_text": "<the secret message>", "context": "<what the players hold>", "skin": "<REQUIRED — see skins>", "difficulty": "normal", "pages": null}
    — a suspicious surface held to heat/light reveals hidden writing.
    skin is REQUIRED and must match the CURRENT location/era: "parchment" (period paper/scrolls),
    "modern" (printout, receipt, dataslate, phone note), "stone" (engraving, tomb slab, bulkhead),
    "chalk" (blackboard, school, chapel wall). Do NOT default to parchment in a modern or
    industrial location. difficulty OPTIONAL: "easy" | "normal" | "hard" (hard = small flame,
    more coverage needed). pages OPTIONAL: a LIST of strings for a multi-page document (diary,
    dossier) revealed page by page — use it for bigger finds; omit for a single surface.''',
        "sample": {"type": "burn_reveal", "context": "A blank sheet that smells of lemon juice",
                   "hidden_text": "HE COUNTS US WHILE WE SLEEP", "skin": "parchment",
                   "difficulty": "normal",
                   "pages": ["HE COUNTS US WHILE WE SLEEP", "DO NOT LET HIM FINISH"]},
    },
    "cipher": {
        "label": "Cipher / riddle",
        "settings": ["*"],
        "contract": '''{"type": "cipher", "ciphertext": "<encoded text shown>", "solution": "<the answer word/phrase>", "hint": "<one cryptic hint>", "attempts": 3, "hint_after": 1}
    — a coded note, inscription, or riddle the players must solve themselves. attempts/hint_after
    are OPTIONAL: set attempts (how many tries) and hint_after (misses before the hint shows) to
    match how deadly this puzzle should be. Omit them for the defaults (3 tries, hint after 1 miss).''',
        "sample": {"type": "cipher", "ciphertext": "GSRH DZB", "solution": "this way",
                   "hint": "The alphabet, reflected in a mirror.", "attempts": 3},
    },
    "combination_lock": {
        "label": "Combination lock / keypad",
        "settings": ["generic", "cthulhu", "warhammer_40k"],   # dials, safes, keypads, cogitator locks
        "contract": '''{"type": "combination_lock", "code": "<3-6 digits>", "clue": "<in-fiction hint pointing to the digits>", "attempts": 4}
    — a safe, padlock, keypad, or cogitator-sealed hatch with positional feedback.
    attempts is OPTIONAL (default 4).''',
        "sample": {"type": "combination_lock", "code": "1925",
                   "clue": "The year carved into the cornerstone.", "attempts": 4},
    },
    "glyph_sequence": {
        "label": "Glyph ritual sequence",
        "settings": ["generic", "cthulhu", "forgotten_realms", "warhammer_fantasy", "warhammer_40k"],
        "contract": '''{"type": "glyph_sequence", "sequence": ["<glyph/word>", "..."], "decoys": ["<wrong glyph>", "..."], "clue": "<in-fiction hint to the correct order>", "attempts": 3}
    — an arcane lock, ward, or ritual: the players must activate 3-5 glyphs in the right order.
    sequence = the correct glyphs IN ORDER (short evocative names, e.g. "burning eye", "serpent");
    decoys = 2-4 wrong glyphs mixed in. attempts OPTIONAL (default 3). Perfect for sealed doors,
    summoning circles, machine-spirit rites.''',
        "sample": {"type": "glyph_sequence", "sequence": ["burning eye", "serpent", "hollow moon"],
                   "decoys": ["broken crown", "weeping tree"],
                   "clue": "First it watches, then it crawls, then it dreams.", "attempts": 3},
    },
    "wire_cut": {
        "label": "Cut the right wire (one shot)",
        "settings": ["generic", "cthulhu", "warhammer_40k"],
        "contract": '''{"type": "wire_cut", "wires": ["red", "blue", "green", "yellow"], "correct": "blue", "clue": "<in-fiction hint>", "consequence": "<what happens on a wrong cut>"}
    — a bomb, trap, machine, or ritual apparatus with ONE chance: cut/pull the right line.
    3-5 wires; exactly one correct. High tension, no retries — use for climaxes. The clue should
    be earnable from earlier scenes.''',
        "sample": {"type": "wire_cut", "wires": ["red", "blue", "green", "yellow"], "correct": "green",
                   "clue": "The maintenance log said: trust the colour of the fields it once watered.",
                   "consequence": "the charge detonates"},
    },
    "memory_echo": {
        "label": "Memory echo (repeat the pattern)",
        "settings": ["*"],
        "contract": '''{"type": "memory_echo", "context": "<what is flashing/sounding>", "length": 4, "attempts": 2}
    — sigils flare / tones sound in a sequence the player must watch and repeat from memory
    (possession echoes, machine rites, spirit knocking, security panels). length OPTIONAL
    (3=easy, 4=normal, 5-6=hard, default 4); attempts OPTIONAL (default 2).''',
        "sample": {"type": "memory_echo", "context": "Four sigils flare on the vault door, one by one",
                   "length": 4, "attempts": 2},
    },
    "dice_duel": {
        "label": "Dice duel (gambling)",
        "settings": ["*"],
        "contract": '''{"type": "dice_duel", "opponent": "<NPC name>", "stakes": "<what winning/losing means>", "rounds": 3}
    — a tavern game of chance against an NPC: liar's dice, crown & anchor, knucklebones. Best of
    `rounds` (OPTIONAL, default 3); each round the player chooses to play bold or steady. You will
    be told who won; narrate the stakes accordingly.''',
        "sample": {"type": "dice_duel", "opponent": "One-Eyed Sal",
                   "stakes": "the cellar key vs your torch", "rounds": 3},
    },
    "seance": {
        "label": "Séance / spirit board",
        "settings": ["generic", "cthulhu", "forgotten_realms", "warhammer_fantasy", "warhammer_40k"],
        "contract": '''{"type": "seance", "message": "<what the spirit spells out>"}
    — a séance/ouija/planchette moment (or speak-with-dead rite, astropathic echo); the message
    is spelled out letter by letter.''',
        "sample": {"type": "seance", "message": "BELOW THE ALTAR"},
    },
    "tarot_draw": {
        "label": "Tarot / omen draw",
        "settings": ["*"],
        "contract": '''{"type": "tarot_draw", "context": "<why the cards are being read>"}
    — a fortune-teller/omen moment; the game draws 3 random cards and you MUST weave their
    listed meanings into what comes next.''',
        "sample": {"type": "tarot_draw", "context": "The refugee woman insists on reading your fate"},
    },
}

# fallback setting per rule system, when a campaign doesn't declare `setting:`
RULE_DEFAULT_SETTING = {"coc7e": "cthulhu", "dnd5e": "forgotten_realms",
                        "wfrp": "warhammer_fantasy", "basic_d100": "generic"}

# skin applied to burn_reveal when the keeper forgets to pick one, per setting
DEFAULT_SKIN = {"cthulhu": "parchment", "forgotten_realms": "parchment",
                "warhammer_fantasy": "stone", "warhammer_40k": "modern", "generic": "modern"}


def types() -> set:
    return set(CATALOG)


def fits(game: str, setting: str) -> bool:
    tags = CATALOG[game]["settings"]
    return "*" in tags or setting in tags


def for_setting(setting: str) -> list:
    """Minigame type names that suit this setting (unknown setting -> universal games only)."""
    return [g for g in CATALOG if fits(g, setting)]


def contract_block(setting: str) -> str:
    """The keeper-contract text for the minigames that fit this setting, led by a compact menu."""
    games = for_setting(setting)
    menu = ("AVAILABLE DEVICES (vary them — never use the same type twice in a row, and prefer "
            "one you have not used yet this session): " + ", ".join(games))
    return menu + "\n  " + "\n  ".join(CATALOG[g]["contract"] for g in games)


def sample(game: str) -> dict:
    return dict(CATALOG[game]["sample"])


def resolve_setting(campaign) -> str:
    return campaign.data.get("setting") or RULE_DEFAULT_SETTING.get(campaign.rule_system, "generic")


def coverage_rows(settings: dict) -> list:
    """[(label, ✓/— per setting...)] for a progress table. `settings` = {key: display_name}."""
    rows = []
    for g, meta in CATALOG.items():
        rows.append([meta["label"]] + ["✓" if fits(g, s) else "—" for s in settings])
    return rows
