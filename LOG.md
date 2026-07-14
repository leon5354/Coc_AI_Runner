# Session log

## 2026-07-14 — Full core rebuild + polish pass

**Rebuild (from the old barely-working version):**
- Root causes fixed: stateless keeper (no history/state in prompt), coin-flip dice (hardcoded 50),
  SAN/HP never mutating, dead researcher, generator/loader schema mismatch.
- New: engine turn loop, schema-v2 campaigns, rules package (coc7e + basic_d100), rolling-summary
  memory, hybrid prose+JSON keeper contract, human/AI toggle per character, animated dice,
  minigames, researcher handouts, scripter with validate+repair.

**Polish pass (same day, user feedback):**
- FIX: `MOCK_LLM=1` left in `.env` made the Play tab use the scripted fake keeper while the
  Architect tab used the real API — "campaign not mounted" mystery. Removed; mock is opt-in.
- FIX: Chinese campaign titles slugged to `generated.yaml` (ASCII-only regex) — now CJK-safe.
- FIX: `basic_d100` campaigns failed validation on stress_events ("unparseable loss '0/1d4'") —
  no-stress systems now ignore stress_events instead of failing; scripter told to emit `[]`.
- Language selector (auto/en/繁中/廣東話) wired through keeper, companions, researcher.
- God mode toggle (keeper + companions play along, never block; off = impartial).
- AI companions: THOUGHT/ACTION output; private thoughts persist per character (inner life).
- Memory summary now keeps one line per character (per-player arcs).
- Utility-model tier: cheap model for summaries/handouts; curated OpenRouter picker
  (grok-4.5, claude-sonnet-5, gemini-3.5-flash, qwen3.7, minimax-m3; utility: gemini-3.1-flash-lite etc).
- Richer AI-facing plots: `tone`, `npcs` (voice/motivation/secret), `escalation` beats,
  per-scene `keeper_notes`; scripter instructed to write for an AI GM.
- 3D dice (CSS preserve-3d bipyramid); minigames +combination_lock +tarot_draw; location skins
  (parchment/modern/stone/chalk); freeze-frame card of the last minigame.
- LLM call log → `data/logs/llm.log` (model, ~tokens in/out, latency).
- Docs: ARCHITECTURE.md (module map + contracts).

**Atmosphere pass (same day):**
- Scene-mood backgrounds (`mood:` per scene, else escalates by scene position) + red sanity
  vignette that closes in as the active character's mind frays.
- Procedural WebAudio ambience (drone tuned per mood, heartbeat under 60% sanity, dice clatter) —
  zero audio assets; one-click enable in sidebar. Optional real BGM from `data/audio/*.mp3|ogg|wav`.
- Status strip badges in the play tab: location, turn, whose move, roll/minigame pending,
  god mode, fraying-mind warning. "📖 The story so far" recap expander once a summary exists.
- Gotcha learned: multi-line f-string HTML in st.markdown gets indented lines parsed as a
  markdown code block — emit single-line HTML. Lazily-imported modules may need a server restart.

**Known state:** all offline tests pass; live-LLM play verified with OpenRouter.
