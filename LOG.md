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

**Live-turn + character-background pass (same day):**
- Turns were computed all at once then dumped into the transcript. Split the turn loop into a
  generator (`engine.keeper_steps()`): each `next()` does ONE beat (keeper reply / one companion's
  turn / one auto-roll) and yields the next beat's label; `app.advance_turn()` runs one beat per
  rerun. You now watch it unfold: your line → Keeper → 🎲 companion's roll → Keeper's outcome.
  Blocking wrappers (`submit_action` etc.) still drain the generator for CLI/tests.
- AI/companion rolls now appear in the transcript as a `dice` role message (were dice-log only).
- Character backgrounds: the Keeper never saw them. `build_state_block` now includes each
  character's personality + background, and is told to tie the horror to their history.
  Protagonist backstory folds in occupation/age + the campaign's `protagonist_hints`.
  New sidebar "📖 Character backgrounds" editor (name/personality/background/inventory, any
  character, any time) via `engine.update_character`; add-character gained a background field.
- New `test_live_turn.py`: asserts beats arrive separately (transcript grows between yields),
  AI rolls are their own beat, human rolls still gate, and backgrounds reach the prompt.

**Protagonist + player-mode investigation (2026-07-15):**
- BUG: the player character was ALWAYS the generic `data/agents/protagonist.yaml` ("Player", CoC
  skills, Notebook/Flashlight/Smartphone) regardless of the generated campaign — a Warhammer game
  still gave you a smartphone. The scripter generated `ai_party` but never a protagonist.
- Fix: scripter now emits a `protagonist` block (name/occupation/personality/backstory/stats/
  inventory) matching the setting + rule system (new `stat_note` tells it d20 modifiers vs 0-100
  percentages); `campaign.protagonist` property; `new_game` uses the campaign's protagonist and
  only falls back to protagonist.yaml when absent. Sample `the_haunting.yaml` gains a protagonist
  (Eleanor Ash). `test_protagonist.py` covers it. Tests that hardcoded "player"/"Player" now read
  the protagonist id/name dynamically.
- Player mode was NOT broken: the save confirmed `companion_style: player` and the code selects
  the player register correctly (proved deterministically). The cinematic feel came from (a) a
  stale cached engine — editing files needs a **Restart** to rebuild `st.session_state.engine`,
  the Keeper instance especially — and (b) the Keeper RE-narrating companion actions in prose.
  Fixed (b): the companion wrap-up now tells the Keeper not to repeat/re-quote/expand what the
  companions already said (extra-tight in player mode) — only add the world's reaction + rolls.

**Known state:** all offline tests pass; live-LLM play verified with OpenRouter (beat-by-beat
sequencing confirmed in-browser: Keeper reply on screen while the companion was still thinking).

**Crash fix + memory/talk + IP/lore pass (same day):**
- CRASH FIX: non-ASCII character names (e.g. Chinese) all slugged to "char" → duplicate Streamlit
  widget keys → app crashed on load. `slugify` now keeps unicode word chars; `unique_id()` dedupes;
  `Engine._repair_character_ids()` fixes old broken saves on load. Regression: `test_id_collision.py`.
- Character memory (feels "real"): per-character `memory_summary` (first-person chronicle) +
  `relationships` (private opinions), distilled by the cheap util model only when `private_thoughts`
  overflow `THOUGHT_WINDOW` (12). All persist on CharacterState. Sidebar "🧠 Inner life" viewer.
- Talk vs Act vs Ask-the-Keeper: `engine.begin_talk/talk_steps` (converse, no turn/dice/plot),
  `engine.ask_keeper_ooc` (OOC Q&A, changes nothing; tagged so keeper won't treat it as story).
  Play-tab segmented control picks the mode. New `ooc` message role.
- Minigame difficulty is host-set: cipher `attempts`/`hint_after`/`allow_giveup`, lock `attempts`
  (all optional in the keeper contract; sensible defaults).
- New rule systems: `dnd5e` (d20+mod vs DC, advantage/disadvantage via bonus/penalty dice, no
  stress) and `wfrp` (d100 roll-under + SL, doubles crit/fumble, Resolve stress pool). NOTE:
  `skill_value` is a d20 modifier for dnd5e vs 0-100 for d100 systems.
- Real-IP lore: `agents/lore.py` fetches official-wiki canon (Fandom/Lexicanum MediaWiki) at
  GENERATION time, bakes it into campaign `canon:`; keeper reads it in the brief; play needs no
  lookups. Architect tab has a Setting/IP picker. Live-verified vs Forgotten Realms / Cthulhu /
  Warhammer wikis (extracts prop absent on Fandom → action=parse HTML fallback). Trademarked
  settings = personal play only.
- Tests: `test_new_systems.py`, `test_memory_character.py`, `test_id_collision.py`.

**Minigame catalog pass (same day):**
- `core/minigames_catalog.py` = single source of truth: type → label, per-setting fit ("*" or
  setting keys), keeper contract text. Keeper's minigame contract is now built per campaign
  setting (e.g. no combination locks offered in Forgotten Realms; glyph rituals are).
- New minigames: `glyph_sequence` (activate sigils in order — arcane locks/wards for the fantasy
  IPs; wrong glyph resets, host-set attempts) and `dice_duel` (best-of-N tavern gamble vs an NPC,
  bold d10 / steady d6+2 choice each round; universal).
- Progress tracking: "🧩 Minigame coverage by setting" table in the Architect tab, generated
  from the catalog (never stale). `test_minigame_catalog.py` enforces catalog ⟷ renderers ⟷
  keeper parity and setting filtering.

**Companion register fix (same day):**
- Problem from live Cantonese play: AI companions wrote novelistic third-person prose
  (self-narrating involuntary detail — "搓手指直至指節出血" — and repeating the same tic every
  turn), not like real tabletop players.
- Rewrote `player_agent` act-mode guidance: a shared BOUNDARY (control only yourself — never
  narrate your involuntary body, others' reactions, the room, or the outcome; vary mannerisms)
  plus two registers via new `GameState.companion_style`: "player" (default — brief intent +
  quoted dialogue, table voice) and "cinematic" (opt-in richer prose). Sidebar "Companion voice"
  toggle. Talk-mode SAY tightened to speech-only.
- Live A/B on grok-4.20 confirmed: player = one action + a line; cinematic = the old prose.

**Keeper authority split (same day):**
- Problem: the Keeper was ventriloquizing AI companions — inventing their dialogue/actions in its
  narration before those companions' own agents had a turn (GM speaking for other players).
- `keeper.character_authority_clause(state)` builds the "who may I voice" rule dynamically:
  human characters always off-limits; AI companions off-limits too in PLAYER style + non-solo
  party (they're real players — the Keeper must hand them the turn via `characters_act`, not
  voice them); the Keeper MAY voice AI companions as NPCs only in solo mode or cinematic style.
  `CONDUCT` split into dynamic clause + `CONDUCT_REST`; `build_system_prompt(..., state=)`.
- `test_authority.py` covers the matrix. Live check: player mode cut the ventriloquism (Keeper
  now often defers via characters_act); not 100% — prompt-level only, since real NPCs share the
  dialogue channel and can't be regex-stripped. Cinematic unchanged (Keeper authors companions).

**Protagonist per-campaign + dice-honesty pass (2026-07-15):**
- Setting-appropriate protagonist wired end to end: scripter emits a `protagonist` block with
  stats matching the rule system (new `stat_note`: d20 modifiers vs 0-100); `Campaign.protagonist`;
  `new_game` prefers it, falls back to protagonist.yaml. Sample the_haunting gained Eleanor Ash.
  Patched the live 深淵的蜜語 (wfrp Slaanesh) campaign + its save so the player is 審判官艾德里安·
  凱爾 with 40k gear/skills instead of the generic CoC "Player" (kept id=player so progress + refs
  survive; Resume to load). `test_protagonist.py`.
- Authority clause strengthened: in player mode the Keeper is now explicitly barred from narrating
  a protected companion's feelings/breathing/expressions/trembling (not just their dialogue) —
  grok was reading body-language as "environment". Cinematic/solo untouched (verified: cinematic =
  Keeper voices companions as before; player = restrained).
- DICE HONESTY FIX: in a long cinematic combat the Keeper stopped emitting roll_request and began
  hand-waving outcomes — even writing fake "d100=47 → 成功" in prose (a hallucination; it cannot
  roll). Added a hard CONDUCT rule: the Keeper never rolls, never writes a die value/target/verdict,
  never invents "hidden" rolls; consequential uncertain actions MUST emit roll_request and end at
  the tension. OOC prompt likewise refuses to fake dice. Live grok-4.20 check: fabricated dice gone
  (0/3 trials faked); real Weapon Skill roll_request fires for genuine attacks. Note: still model-
  dependent — it may skip a roll it judges a foregone conclusion (e.g. striking an intangible
  illusion), which is a defensible GM call, not the old fakery.

**Docs rebrand (2026-07-15):** README/ARCHITECTURE/CHANGELOG rewritten as "AI TTRPG Runner"
(multi-system: CoC 7e / D&D 5e / WFRP / basic d100). Repo name/local path/remote left as-is.

**Minigame overhaul + roll-chain guard (2026-07-15):**
- BUG (theme never switched / games seemed dead): the minigame widget key was `mg_{turn_count}`,
  which repeats when a minigame fires outside submit_action — the OLD CCv2 component (old skin,
  old text, dataset.built guard) was reused. New `GameState.minigame_count` increments per launch
  via `engine.launch_minigame()`, which also injects a per-setting default skin
  (`minigames_catalog.DEFAULT_SKIN`) when the keeper omits one. Contract now marks skin REQUIRED.
- Keeper minigame contract now leads with an AVAILABLE DEVICES menu + "vary, never repeat twice
  in a row" — addresses the host always picking burn/cipher.
- burn_reveal upgrades: `difficulty` (easy/normal/hard → flame radius + coverage) and `pages`
  (multi-page documents, revealed page by page, page counter in-component).
- New minigames: `wire_cut` (one-shot wire choice, native) and `memory_echo` (Simon-style CCv2
  sigil pattern). combination_lock now fits 40k (keypads); seance fits 40k (astropathic echo).
- 🧪 Minigame tester (sidebar): one button per game launches its catalog `sample` through the
  real engine — QA without begging the keeper. All 9 games verified in-browser end-to-end
  (burn multi-page + skin, cipher solve, lock open, duel, glyph order, echo board, séance
  spelling, tarot draw, wire cut) with keeper narration after each.
- NEW FINDING from that testing: the dice-honesty rule made grok CHAIN roll_requests off roll
  outcomes (3+ consecutive Dodge gates without player input). Two-layer fix: CONDUCT now says
  one player action = one roll (max one forced follow-up), and an engine chain guard
  (`GameState.rolls_since_action`, reset on action/negotiate/minigame result) hard-declines a
  3rd consecutive roll with a dice-log note. `test_roll_chain.py`.
- Gotcha (again): Streamlit does NOT reliably hot-reload imported core modules — restart the
  server after editing engine/keeper, not just Resume.

**Authority clause strengthened (2026-07-15, follow-up):**
- Live WFRP/40k session: companions themselves were fine in player mode, but the KEEPER still
  narrated their inner states ("breathing quickened", "eyes betrayed unease"). The clause forbade
  their dialogue/decisions but grok read body-language as environment. Extended the player-mode
  clause to forbid ZERO described inner states — feelings, thoughts, breathing, heartbeat,
  expressions, blushing, trembling — the Keeper may only describe what the world/NPCs do around
  them. Also diagnosed the user's confusion: their earlier elevator save was `companion_style:
  cinematic` (novels are correct there); the Slaanesh save is `player` and companions were already
  restrained. Two-and-a-half campaigns predate the protagonist fix (generic "Player"/CoC sheet);
  fixed the WFRP one's campaign + live save to the intended Inquisitor (Cool 65, bolt pistol).
