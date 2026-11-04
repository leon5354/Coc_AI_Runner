# Changelog

## [Unreleased] - Web app
### Added
- **Web app**: a FastAPI server (`server/`) wraps the engine; a React + TypeScript frontend
  (`web/`) replaces Streamlit's redraw-on-every-click UI. Everything carries over: live
  beat-by-beat turns, roll gate + negotiation, all 9 minigames, dice, mood backgrounds, sanity
  vignette, ambience, party/inner-life/character editing, minigame tester, undo, export, and
  the Scenario Architect. Works on phones.
- `test_server.py`: a full mock session over HTTP, offline.
- **3D dice**: real physics, grab and flick. d4 to d100, bonus dice shown, companion and sanity
  rolls shown too, loose dice tray. The server's number always lands face up.
- **Art made by code**: 26 kinds of place with sky, fog, parallax, random props, and weather and
  light that follow the story. Portraits.
  No image files and no image AI.
- **Character panel (狀態欄 / 物品欄)**: status, skills, inventory with icons, journal with clues
  and a map that fills in. Items can be inspected, used, given and dropped.
- **Title screen, ending screen, scene title cards, pop-ups** for HP, sanity, items and clues.
- **No-key brains**: Ollama with add/remove from Hugging Face links, Claude plan through the
  `claude` command, OpenRouter sign-in. The choice is remembered.
- **Live typing**: the Keeper's words appear as they are written.
- **Referee for local models**: before each story beat, a small rules question decides rolls,
  scene moves and puzzles, so smaller models can't skip the game.
- **Push and Luck** for Call of Cthulhu.
- **Chinese interface**, following the game's language or set in Settings.
- **A D&D sample campaign**, The Drowned Bell.
- **Keeper tools**: items, endings, bonus/penalty dice, damage as dice ("-1d6").
- **`test_mechanics.py`, `test_all.py`, `playtest.py`, GOAL.md**.
### Fixed
- Bonus/penalty dice and advantage were never applied to any roll.
- CoC: 00 + 0 ignored bonus/penalty dice. WFRP: no automatic 01-05 / 96-100, wrong Success Levels.
- Damage written as "-1d6" was silently dropped. Healing never woke an unconscious hero.
- AI failures were written into the story as narration.
- Ollama cut off the Keeper's prompt (context 4096) and thinking models returned empty text.
- A success now finds the scene's real clue, so models can't skip the campaign's clues.
### Removed
- The Streamlit UI. The web app replaced all of it.
### Changed
- Mock mode saves to `data/saves/mock/` so test games never overwrite real saves.
- Restart asks before deleting a save.
### Fixed
- Candle (burn reveal) heat was tied to how many ticks fired, not time — a fast sweep warmed
  ink faster than holding still. Now time-based, same overall speed (web version).

## [4.0.0] - 2026-07-15 (Multi-System TRPG)
Grew from a Call of Cthulhu-only tool into a general tabletop RPG engine.
### Added
- **New rule systems**: D&D 5e (d20 + modifier vs DC, advantage/disadvantage) and Warhammer
  Fantasy RP (d100 + degrees of success, Resolve/corruption pool), alongside CoC 7e and
  basic d100. One file per system in `rules/`.
- **Real setting lore**: for licensed settings (Cthulhu Mythos, Forgotten Realms, Warhammer),
  the Scenario Architect fetches official-wiki pages at generation time and bakes a canon
  brief into the campaign file — no live lookups during play.
- **Character memory**: AI companions keep a first-person memory of what they've personally
  lived through and private opinions of other characters, persisting across the whole session.
- **Setting-appropriate protagonist**: the Scenario Architect now generates the player's own
  character to fit the setting and rule system, instead of always falling back to a generic
  Call of Cthulhu sheet.
- **Live, beat-by-beat turns**: a turn unfolds on screen as it happens instead of appearing
  all at once after the fact.
- **Talk & Ask the Keeper**: converse with companions or ask out-of-character questions
  without spending a turn, rolling dice, or advancing the plot.
- **Companion voice modes**: "player" (default — companions act like real tabletop players,
  concise intent + dialogue) vs "cinematic" (richer prose) — with the Keeper barred from
  inventing dialogue for companions playing as real players.
- Minigame catalog is setting-aware (new: glyph sequence, dice duel) with host-configurable
  attempts/hints instead of hardcoded difficulty.
### Fixed
- Non-ASCII character names (e.g. Chinese) could collapse to duplicate ids and crash the UI.
- Campaigns for systems without a sanity/stress mechanic failed validation on stress events.

## [3.0.0] - 2026-07-14 (Core Rebuild)
### Changed
- **Keeper rebuilt**: every LLM call now includes full game state (scene, clues, sheets,
  exits), a rolling story summary, and the last 20 messages — fixes "host forgets the plot".
- **Real dice**: rolls resolve through the rule system against actual skill values; the old
  hardcoded 50% coin-flip is gone. Animated dice in the UI.
- **SAN/HP mutate**: stress checks and hp changes from the keeper's control block are applied
  to characters, with status changes (unconscious/insane).
- **Structured keeper output**: prose + trailing JSON control block replaces the fragile
  `[ROLL_REQUIRED]` token (with fallback parsing, never crashes).
- **Unified characters**: protagonist/companions merged into one list; any character can be
  toggled Human/AI mid-game; add characters anytime (hotseat multiplayer).
- **Pluggable rule systems**: new `rules/` package (coc7e + basic_d100); campaigns declare
  `rule_system`.
- **One campaign schema (v2)**: shared by the Scenario Architect and the engine; generated
  campaigns are validated (with one auto-repair round) before saving.
- **Researcher works**: produces diegetic handouts grounded in discovered clues.
### Removed
- chromadb/RAG, dead memory system, duplicate stale UI, dead config.yaml, old flat campaign.


## [2.3.0] - 2026-02-17 (Protagonist Update)
### Added
- **Sanity Filters:** Text style changes based on Investigator Sanity (Low = Unreliable/Paranoid).
- **Inner Monologue:** Automatic italicized thoughts for the Protagonist reflecting their mental state.
- **Manual Turn Pacing:** Added "▶ Continue" button to control AI companion turns one by one.
- **Deep Scripter:** Agents now research real-world lore/history during generation to flesh out backstories.
- **Flashback Mechanic:** Keeper can trigger traumatic memories on failed rolls.

### Changed
- **Pacing:** Strict 1-Agent-Per-Turn limit enforced in UI.
- **Memory:** Shared `_memory.json` persists narrative context alongside save files.
- **Prompts:** Optimized Scripter and Player Agent prompts for "Hero Mode" immersion.

## [2.2.0] - 2026-02-17 (Initial Fork)
- Created `Miskatonic_AI_V2_2` directory.
- Migrated core logic to new `MemorySystem`.
- Updated `Keeper` to use `google.genai` SDK.
