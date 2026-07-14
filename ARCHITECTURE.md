# Architecture reference

One-page map for humans and AI assistants. Update when contracts change.

## Data flow (one player turn)

```
Streamlit UI (interface/app.py)
  → Engine.submit_action(char_id, text)          core/engine.py
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
      → companion turns (party_mode: solo | keeper | active)
  → memory.maybe_compact (>30 msgs → oldest 10 into state.summary, uses util_llm)
  → state.save() → data/saves/<campaign>.save.json
```

## Modules

| File | Role | Key contract |
|---|---|---|
| `core/engine.py` | UI-agnostic orchestrator | **Live turns**: `begin_action/begin_negotiate/begin_minigame_result` (instant) + `keeper_steps()` generator — each `next()` = ONE beat (keeper reply, one companion, one auto-roll), yields the next beat's label. Blocking wrappers `submit_action/resolve_roll/negotiate_roll/resolve_minigame` drain it (CLI/tests). Also `roll_dice`, `undo`, `update_character`, `set_llm(main, util)` |
| `core/keeper.py` | Prompt assembly + parsing | `Control` dataclass; `MINIGAME_TYPES`; hybrid prose+json contract; `LANGUAGE_BLOCKS` (auto/en/zh/yue); `GOD_MODE_BLOCK` |
| `core/game_state.py` | All runtime state | `GameState`/`CharacterState` dataclasses; JSON save per campaign; `pending_roll`/`pending_minigame` survive reload |
| `core/campaign.py` | Schema v2 load + validate | `validate()` returns ALL problems; optional fields: `tone`, `npcs`, `escalation`, scene `keeper_notes` |
| `core/memory.py` | Rolling summary | compact >30 msgs; per-character arc lines; hard facts live in state block, not summary |
| `core/llm_client.py` | Provider abstraction | `chat(messages, system_prompt)`; openrouter/google/ollama; call log → `data/logs/llm.log` |
| `rules/` | Pluggable rule systems | `RuleSystem` ABC; registry in `__init__`; `coc7e` (has_stress) + `basic_d100` |
| `agents/player_agent.py` | AI party members | THOUGHT/ACTION output; private_thoughts persist on `CharacterState` |
| `agents/researcher.py` | Diegetic lore handouts | uses `util_llm`; optional DDG web flavor |
| `agents/scripter.py` | Campaign generator | schema v2 JSON via json_mode; validate + one repair round-trip |
| `interface/app.py` | Streamlit shell | thin; all logic in engine; `MOCK_LLM=1` env = offline scripted keeper |
| `interface/dice.py` | 3D dice (CCv2) | cosmetic; server rolls first |
| `interface/minigames.py` | Keeper-invokable minigames | `RENDERERS` dict; skins (parchment/modern/stone/chalk); `render_frozen` freeze-frame |
| `interface/atmosphere.py` | Mood backgrounds + sound | scene `mood:` (daylight/dusk/night/unearthly, fallback = scene position); sanity vignette; WebAudio drone/heartbeat/dice-clatter (no assets); BGM from `data/audio/` |
| `cli_play.py` | Terminal REPL + `MockLLM` | scripted responses exercising every control path |

## Contracts to keep in sync

1. **Keeper output contract** (`keeper.py OUTPUT_CONTRACT`) ⟷ `Control` fields ⟷ `engine._apply_effects`.
2. **Minigame types**: `keeper.MINIGAME_TYPES` ⟷ `minigames.RENDERERS` ⟷ contract text.
3. **Campaign schema**: `campaign.validate` ⟷ `scripter.ARCHITECT_INSTRUCTION_TEMPLATE` ⟷ sample `the_haunting.yaml`.
4. **Save format**: `GameState` fields — add with defaults only (old saves must keep loading).
5. **Live turn loop**: `engine.keeper_steps()` yields ⟷ `app.advance_turn()` runs one beat per
   rerun. Any new LLM work inside a turn must `yield` a label, or it will block the UI.
   Message roles the transcript renders: `keeper`, `player`, `companion`, `dice`, `researcher`.

## Tests (all offline, no API)

`python test_rules.py · test_keeper_parser.py · test_engine.py · test_party_modes.py · test_memory.py · test_scripter.py`
plus `python -m core.campaign <file>` to validate a campaign, `python cli_play.py --mock` to play offline.

## Env

`.env`: `LLM_PROVIDER/LLM_MODEL` (main), `UTILITY_PROVIDER/UTILITY_MODEL` (cheap tasks),
`OPENROUTER_API_KEY`/`GOOGLE_API_KEY`, `MOCK_LLM=1` (offline), `SCRIPTER_PROVIDER/SCRIPTER_MODEL`.
