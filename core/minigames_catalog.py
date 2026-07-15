"""Single source of truth for minigames: which exist, which settings they fit, and the
contract text the keeper sees. The UI renderer table and the keeper prompt both derive
from this, so adding a minigame here is step 1 of exactly 2 (step 2: its renderer).

settings: "*" = fits everywhere; otherwise list of setting keys (see agents/lore.SETTING_WIKIS).
"""

CATALOG = {
    "burn_reveal": {
        "label": "Hidden writing (heat reveal)",
        "settings": ["*"],
        "contract": '''{"type": "burn_reveal", "hidden_text": "<the secret message>", "context": "<what the players hold>", "skin": "parchment"}
    — a suspicious surface held to heat/light reveals hidden writing.
    skin matches the setting: "parchment" (period paper), "modern" (printout/receipt/phone note),
    "stone" (engraving/tomb slab), "chalk" (blackboard/school). Pick what fits the current location.''',
    },
    "cipher": {
        "label": "Cipher / riddle",
        "settings": ["*"],
        "contract": '''{"type": "cipher", "ciphertext": "<encoded text shown>", "solution": "<the answer word/phrase>", "hint": "<one cryptic hint>", "attempts": 3, "hint_after": 1}
    — a coded note, inscription, or riddle the players must solve themselves. attempts/hint_after
    are OPTIONAL: set attempts (how many tries) and hint_after (misses before the hint shows) to
    match how deadly this puzzle should be. Omit them for the defaults (3 tries, hint after 1 miss).''',
    },
    "combination_lock": {
        "label": "Combination lock",
        "settings": ["generic", "cthulhu"],   # dials & safes: modern-ish eras
        "contract": '''{"type": "combination_lock", "code": "<3-6 digits>", "clue": "<in-fiction hint pointing to the digits>", "attempts": 4}
    — a safe, padlock, or door mechanism with positional feedback. attempts is OPTIONAL (default 4).''',
    },
    "glyph_sequence": {
        "label": "Glyph ritual sequence",
        "settings": ["generic", "cthulhu", "forgotten_realms", "warhammer_fantasy", "warhammer_40k"],
        "contract": '''{"type": "glyph_sequence", "sequence": ["<glyph/word>", "..."], "decoys": ["<wrong glyph>", "..."], "clue": "<in-fiction hint to the correct order>", "attempts": 3}
    — an arcane lock, ward, or ritual: the players must activate 3-5 glyphs in the right order.
    sequence = the correct glyphs IN ORDER (short evocative names, e.g. "burning eye", "serpent");
    decoys = 2-4 wrong glyphs mixed in. attempts OPTIONAL (default 3). Perfect for sealed doors,
    summoning circles, machine-spirit rites.''',
    },
    "dice_duel": {
        "label": "Dice duel (gambling)",
        "settings": ["*"],
        "contract": '''{"type": "dice_duel", "opponent": "<NPC name>", "stakes": "<what winning/losing means>", "rounds": 3}
    — a tavern game of chance against an NPC: liar's dice, crown & anchor, knucklebones. Best of
    `rounds` (OPTIONAL, default 3); each round the player chooses to play bold or steady. You will
    be told who won; narrate the stakes accordingly.''',
    },
    "seance": {
        "label": "Séance / spirit board",
        "settings": ["generic", "cthulhu", "forgotten_realms", "warhammer_fantasy"],
        "contract": '''{"type": "seance", "message": "<what the spirit spells out>"}
    — a séance/ouija/planchette moment (or speak-with-dead rite); the message is spelled out
    letter by letter.''',
    },
    "tarot_draw": {
        "label": "Tarot / omen draw",
        "settings": ["*"],
        "contract": '''{"type": "tarot_draw", "context": "<why the cards are being read>"}
    — a fortune-teller/omen moment; the game draws 3 random cards and you MUST weave their
    listed meanings into what comes next.''',
    },
}

# fallback setting per rule system, when a campaign doesn't declare `setting:`
RULE_DEFAULT_SETTING = {"coc7e": "cthulhu", "dnd5e": "forgotten_realms",
                        "wfrp": "warhammer_fantasy", "basic_d100": "generic"}


def types() -> set:
    return set(CATALOG)


def fits(game: str, setting: str) -> bool:
    tags = CATALOG[game]["settings"]
    return "*" in tags or setting in tags


def for_setting(setting: str) -> list:
    """Minigame type names that suit this setting (unknown setting -> universal games only)."""
    return [g for g in CATALOG if fits(g, setting)]


def contract_block(setting: str) -> str:
    """The keeper-contract text for the minigames that fit this setting."""
    return "\n  ".join(CATALOG[g]["contract"] for g in for_setting(setting))


def resolve_setting(campaign) -> str:
    return campaign.data.get("setting") or RULE_DEFAULT_SETTING.get(campaign.rule_system, "generic")


def coverage_rows(settings: dict) -> list:
    """[(label, ✓/— per setting...)] for a progress table. `settings` = {key: display_name}."""
    rows = []
    for g, meta in CATALOG.items():
        rows.append([meta["label"]] + ["✓" if fits(g, s) else "—" for s in settings])
    return rows
