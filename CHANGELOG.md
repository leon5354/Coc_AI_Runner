# Changelog

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
