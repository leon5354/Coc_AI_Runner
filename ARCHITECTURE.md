# Architecture reference

One-page map for humans and AI assistants. Update when contracts change.

AI TTRPG Runner (repo name `Coc_AI_Runner` for history) — multi-system tabletop RPG engine.
Supported rule systems: CoC 7e, D&D 5e, Warhammer Fantasy RP, basic d100 (see `rules/`).

## Data flow (one player turn)

```
Web UI (web/src, React)  →  POST /api/game/act  →  server/app.py
  → Engine.begin_action + keeper_steps(text)     core/engine.py
      → Keeper.respond(state, text)              core/keeper.py
          builds: system prompt (role + rules + language + god mode + campaign brief)
                + state block (scene, clues, exits, party, STORY SO FAR summary)
                + last 20 messages verbatim
          ← LLM returns prose + trailing ```json control block
      → parse_response → (narrative, Control)
      → effects applied in order: clues → stress → hp → scene transition
      → roll_request? human char → state.pending_roll (UI gate)
                      AI char    → auto-rolled via rules.get_system()
      → minigame?     → state.pending_minigame (UI gate)
      → companion turns (party_mode: solo | keeper | active; each companion's own
        agent supplies its dialogue — the Keeper defers to characters_act rather
        than voicing them, except in solo mode or companion_style="cinematic")
  → memory.maybe_compact (>30 msgs → oldest 10 into state.summary, uses util_llm)
    (each AI character's own private_thoughts also compact independently into
     memory_summary + relationships when they overflow — see core/memory.py)
  → state.save() → data/saves/<campaign>.save.json
```

`engine.keeper_steps()` is a generator — each `next()` advances ONE beat (a keeper reply, one
companion's turn, one auto-roll) so the UI can redraw between them instead of dumping a whole
turn at once. `Talk` and `Ask the Keeper` are separate, lighter flows that don't run this loop:
they never spend a turn, roll dice, or change scene/plot state.

## Modules

| File | Role | Key contract |
|---|---|---|
| `core/engine.py` | UI-agnostic orchestrator | **Live turns**: `begin_action/begin_negotiate/begin_minigame_result` (instant) + `keeper_steps()` generator — each `next()` = ONE beat (keeper reply, one companion, one auto-roll), yields the next beat's label. Blocking wrappers `submit_action/resolve_roll/negotiate_roll/resolve_minigame` drain it (CLI/tests). Also `roll_dice`, `undo`, `update_character`, `set_llm(main, util)`, `begin_talk/talk_steps` (converse, no turn), `ask_keeper_ooc` (out-of-character Q&A, changes nothing), `_repair_character_ids()` (fixes pre-fix saves with colliding ids) |
| `core/keeper.py` | Prompt assembly + parsing | `Control` dataclass; `MINIGAME_TYPES` (derived from `minigames_catalog`); hybrid prose+json contract; `LANGUAGE_BLOCKS` (auto/en/zh/yue); `GOD_MODE_BLOCK`; `character_authority_clause(state)` builds the dynamic "who may I voice" rule (humans always protected; AI companions protected too in `companion_style="player"` + non-solo party — Keeper must use `characters_act` instead of inventing their lines; Keeper may voice them as NPCs only in solo mode or `companion_style="cinematic"`) |
| Local-model helpers | Referee and bookkeeper | In `core/keeper.py`, Ollama only. `referee()` asks before the story: roll, move, puzzle, ending. `device()` fills a puzzle's contents. `bookkeep()` asks after the story: HP and items. All JSON mode, all ignored if the answer is unusable. Stronger models do this themselves through the control block |
| `core/game_state.py` | All runtime state | `GameState`/`CharacterState` dataclasses; JSON save per campaign; `pending_roll`/`pending_minigame` survive reload; `CharacterState.memory_summary`/`relationships`/`private_thoughts` (per-character memory); `GameState.companion_style` (player/cinematic); `slugify()` keeps unicode, `unique_id()` guarantees no id collisions |
| `core/campaign.py` | Schema v2 load + validate | `validate()` returns ALL problems; optional fields: `tone`, `npcs`, `escalation`, `canon`, scene `keeper_notes`/`mood`; `Campaign.protagonist` property (setting-appropriate player character, falls back to `data/agents/protagonist.yaml` when absent) |
| `core/memory.py` | Rolling summary + character memory | story summary: compact >30 msgs, per-character arc lines, hard facts live in state block not summary; `compact_character()`: folds an AI character's overflowing `private_thoughts` into first-person `memory_summary` + `relationships`, using the cheap `util_llm` |
| `core/minigames_catalog.py` | Minigame source of truth | type → label, per-setting fit (`"*"` or setting keys), keeper contract text; `keeper.py` derives from it and `web/src/minigames.tsx` must match — `test_minigame_catalog.py` enforces parity |
| `core/llm_client.py` | Provider abstraction | `chat()` and `stream()`; ollama (native API, sets `num_ctx`), claude_cli (headless `claude -p`, plan login, no tools), openrouter, google. Failures raise `LLMError` through `check_llm`, so they never enter the story. Call log → `data/logs/llm.log` |
| `rules/` | Pluggable rule systems | `RuleSystem` ABC; registry in `__init__`; `coc7e`/`wfrp` (`has_stress=True`) + `dnd5e`/`basic_d100` (`has_stress=False`). `skill_value` semantics are per-system (0-100 for d100 systems, d20 modifier for dnd5e) — a campaign's sheets must match its `rule_system` |
| `agents/lore.py` | Real-setting canon fetch | `SETTING_WIKIS` (MediaWiki api.php per IP: Cthulhu Mythos, Forgotten Realms, Warhammer Fantasy, Warhammer 40k); `fetch_canon(setting, concept, llm)` at GENERATION only, baked into campaign `canon:`; extracts→parse-HTML fallback; degrades to "" on any failure. Trademarked settings: personal/hobby use only |
| `agents/player_agent.py` | AI party members | THOUGHT/ACTION (or THOUGHT/SAY in talk mode) output; `PlayerAgent.take_turn(char, state, campaign, mode)`; prompt built from the character's `memory_summary` + `relationships` + recent `private_thoughts`, not just their static sheet; register controlled by `state.companion_style` (player = table voice, no self-narration of involuntary detail or others' reactions; cinematic = richer prose) |
| `agents/researcher.py` | Diegetic lore handouts | uses `util_llm`; optional DDG web flavor |
| `agents/scripter.py` | Campaign generator | schema v2 JSON via json_mode; validate + one repair round-trip; generates a setting-appropriate `protagonist` block (not just `ai_party`) with stats matching the rule system's conventions; optional lore fetch via `agents/lore.py` baked into `canon:` |
| `server/app.py` | FastAPI web API | One `ENGINE` per process + `BUSY` lock (409 while a turn runs). Turn endpoints (`act/talk/roll/negotiate/minigame`) stream NDJSON: `{partial}` while the Keeper types, `{label, game, dice}` per beat, then `{done, game, dice}` (or with `error`). `dice` = rolls to show. `game_view()` = `asdict(state)` + scene, mood, roll preview, clues, map, can_undo. `/api/llm/*` lists what this PC can run, adds/removes Ollama models, signs in to OpenRouter. `MOCK_LLM=1` → scripted keeper and saves under `data/saves/mock/`. Serves `web/dist` at `/` and `data/audio` at `/api/audio`. `python -m server [--mock]` runs it (localhost only) |
| `web/src/` | React frontend | `api.ts` (types mirror `game_state.py`, NDJSON reader), `App.tsx` (state + `turn()`/`call()`), `Play.tsx`, `Sidebar.tsx`, `Dice.tsx`, `Atmosphere.tsx`, `minigames.tsx` (`GAMES` registry), `Architect.tsx`. Markdown via react-markdown (no raw HTML — LLM text is untrusted) |
| `web/src/dice/` | 3D dice | `shapes.ts` builds every die from its convex hull. `table.ts`: on a throw, the whole physics run is simulated first (retrying if a die lands cocked), the die is reprinted so the landing face shows the server's number, then the recording plays back. `DiceTable.tsx` is the full-screen moment. The server always rolls; `readTops()` lets tests prove the die agrees |
| `web/src/art/` | Art made by code | `kits.ts`: one painter per kind of place, picked from the scene's `art:` field or its words (EN + ZH). `SceneArt.tsx`: WebGL sky/fog, SVG silhouettes with parallax, canvas weather. `Portrait.tsx`: rim-lit silhouettes from the character sheet. `itemIcon.tsx`: icon from the item's name |
| `playtest.py` | Real-AI playtest | Another AI plays the human; writes a report to `data/logs/` |
| `cli_play.py` | Terminal REPL + `MockLLM` | scripted responses exercising every control path, through to an ending |

## Contracts to keep in sync

1. **Keeper output contract** (`keeper.py OUTPUT_CONTRACT`) ⟷ `Control` fields ⟷ `engine._apply_effects`.
2. **Minigame types**: `core/minigames_catalog.py` is the single source of truth (type, label,
   per-setting fit, keeper contract text). `keeper.MINIGAME_TYPES` and the prompt's minigame
   section derive from it (filtered by the campaign's setting); `web/src/minigames.tsx` `GAMES`
   must cover exactly the catalog —
   `test_minigame_catalog.py` enforces parity. To add a minigame: 1 catalog entry + 1 web
   game, done.
3. **Campaign schema**: `campaign.validate` ⟷ `scripter.ARCHITECT_INSTRUCTION_TEMPLATE` ⟷ sample `the_haunting.yaml`.
4. **Save format**: `GameState`/`CharacterState` fields — add with defaults only (old saves must
   keep loading). New character ids must go through `unique_id()`, never assigned directly.
5. **Live turn loop**: `engine.keeper_steps()` yields ⟷ `server.stream_turn()` sends one NDJSON
   line per beat. Any new LLM work inside a turn must `yield` a label, or it will block the UI.
   Message roles the transcript renders: `keeper`, `player`, `companion`, `dice`, `researcher`,
   `ooc`.
6. **Character authority**: `keeper.character_authority_clause(state)` ⟷ `state.companion_style`
   ⟷ `state.party_mode`. If you add a new way for an AI character to act autonomously, it must
   also be covered by this clause or the Keeper will speak for it. `test_authority.py` covers
   the mode matrix.
7. **Dice events**: every roll the player should see goes through `engine.events`
   (`_record_roll`, stress checks) and is drained per beat by the server. `RollResult.dice` lists
   the physical dice; kept dice must add back up to the roll. `test_mechanics.py` enforces it.
8. **Saves**: `GameState.slot` names each save. "" is the campaign's first; new games get a dated
   slot. `saves_of()` lists them, `save_path_of()` finds one.
9. **Clues**: a successful roll with a scene clue's skill finds that clue (`_outcome_prompt`). The
   Keeper can also award clues through `clues_discovered`.
10. **Protagonist**: `Campaign.protagonist` ⟷ `scripter.ARCHITECT_INSTRUCTION_TEMPLATE`'s
   `protagonist` block ⟷ `engine.new_game()`'s fallback to `data/agents/protagonist.yaml`. A
   campaign without a protagonist block must still produce a playable (generic) character.

## Tests (all offline, no API)

```
test_rules.py test_keeper_parser.py test_engine.py test_party_modes.py test_memory.py
test_scripter.py test_memory_character.py test_id_collision.py test_new_systems.py
test_minigame_catalog.py test_authority.py test_protagonist.py test_server.py test_mechanics.py
test_live_turn.py test_roll_chain.py        (python test_all.py runs them all)
```

`python -m core.campaign <file>` validates a campaign file; `python cli_play.py --mock` plays
a full session offline against a scripted Keeper.

## Env

`data/settings.json` (the brain picked in the app) wins over `.env`.
`.env`: `LLM_PROVIDER/LLM_MODEL` (main), `UTILITY_PROVIDER/UTILITY_MODEL` (cheap tasks),
`OPENROUTER_API_KEY`/`GOOGLE_API_KEY`, `MOCK_LLM=1` (offline), `SCRIPTER_PROVIDER/SCRIPTER_MODEL`.
