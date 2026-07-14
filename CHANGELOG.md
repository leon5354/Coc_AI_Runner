# Changelog

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
