# AI TTRPG Runner

*(GitHub repo name `Coc_AI_Runner` for history's sake — the project outgrew Call of Cthulhu.)*

An LLM-driven tabletop RPG runner with a fully stateful AI Keeper (GM), real dice mechanics,
character memory, and pluggable rule systems. It started as a Call of Cthulhu tool; it now
runs **Call of Cthulhu 7e, Dungeons & Dragons 5e, Warhammer Fantasy Roleplay, or a generic
d100 system** — pick one per campaign. Streamlit UI, works with Google Gemini, OpenRouter
(Grok, Claude, Gemini, Qwen, etc.), or local Ollama.

The goal: a Keeper that actually remembers the plot, dice that respect your character sheet,
companions who feel like real players instead of a chatbot improvising a novel, and enough
atmosphere (mood-lit backgrounds, ambient sound, minigames) that a solo session still feels
like a table.

## Supported systems

| System | Mechanic | Stress/sanity | Notes |
|---|---|---|---|
| **Call of Cthulhu 7e** | d100 roll-under, crit/extreme/hard/regular/fumble tiers | Sanity | Bonus/penalty dice |
| **D&D 5e** | d20 + modifier vs DC | none | Advantage/disadvantage |
| **Warhammer Fantasy RP** | d100 roll-under, degrees of success | Resolve (corruption/terror) | Doubles crit/fumble |
| **Basic d100** | d100 roll-under | none | Minimal generic system, good starting point for homebrew |

Adding a system is one file in `rules/` implementing the `RuleSystem` interface — see
`ARCHITECTURE.md` for the contract.

## Features

**The Keeper**
- **Stateful** — every LLM call carries the full game state: current scene, clues, character
  sheets, exits, a rolling story summary, and recent chat history. The host follows the plot
  and remembers what happened, across sessions.
- **Real dice** — rolls resolve server-side against your actual skill values and the active
  rule system's tiers, with an animated 3D dice tumble in the UI.
- **Consequences** — HP and stress/sanity actually change from roll outcomes and scripted
  events; status changes (unconscious, insane) apply automatically.
- **Roll gate + negotiation** — the game pauses on a requested roll; roll, or argue for a
  different skill before committing.
- **Live, beat-by-beat turns** — a turn unfolds on screen as it happens (your line → Keeper →
  a companion's roll → the Keeper's outcome), not dumped all at once after the fact.
- **God mode** — toggle the Keeper and companions to play along with you and never block your
  intent; turn it off for an impartial host and companions with their own will.

**Characters**
- **Setting-appropriate protagonist** — a generated campaign writes you a character that fits
  its world (a Warhammer inquisitor doesn't carry a smartphone), not a generic fallback sheet.
- **Character memory** — AI companions keep a first-person memory of what they've personally
  lived through and private opinions of the other characters, both persisting across the whole
  session (not just a short rolling window). Visible in the sidebar "🧠 Inner life" viewer.
- **Companion voice** — "player" style (default): companions speak and act like real people at
  a table — brief intent plus dialogue, never narrating their own involuntary reactions or
  putting words in other characters' mouths. "cinematic" style: richer novelistic prose for
  solo storytellers who want it. The Keeper itself is barred from voicing companions who are
  playing as real players — it hands them their turn instead of inventing their lines.
- **Humans and AI as peers** — every character has a Human/AI toggle, switchable mid-game. Add
  extra characters anytime (hotseat multiplayer). Edit any character's background/personality/
  inventory at any time.
- **AI party modes** — `solo` (companions are narrated NPCs), `keeper` (they act when the
  Keeper calls on them), `active` (they act every turn).
- **Talk & Ask the Keeper** — converse with companions without spending a turn or rolling dice
  ("Talk"), or ask an out-of-character question that changes nothing in the game ("Ask the
  Keeper") — for rules questions, recaps, or planning without touching the story.

**World & content**
- **Real setting lore** — for licensed settings (Cthulhu Mythos, Forgotten Realms, Warhammer),
  the Scenario Architect fetches a few pages from the official wiki at generation time,
  compresses them into a canon brief, and bakes it into the campaign file. Play needs zero
  live lookups; personal/hobby use only (these settings are trademarked).
- **Scenario Architect** — brainstorm with an AI, pick a rule system and setting, then generate
  a validated campaign YAML guaranteed to load and play — plot, NPCs, escalation beats,
  per-scene Keeper notes, and a matching protagonist, all in one pass.
- **Keeper minigames** — optional dramatic devices the Keeper can invoke when the fiction calls
  for it, filtered to fit the campaign's setting: reveal hidden writing by candlelight, solve a
  cipher, crack a combination lock or activate a glyph sequence, draw tarot omens, gamble in a
  dice duel, or watch a séance spell out a message. Attempts/difficulty are Keeper-configurable
  per instance, not hardcoded. Surfaces are re-skinned to match the setting (parchment / modern
  / stone / chalk).
- **Researcher** — an in-fiction Archivist that produces diegetic handouts (clippings, journal
  pages), optionally seeded by a web search.
- **Language selector** — force English, 繁體中文, or 廣東話 (narration in 書面語, dialogue in
  spoken Cantonese) regardless of what you type; or auto-detect.
- **Atmosphere** — the background shifts with each scene's mood, a red vignette closes in as
  sanity/resolve frays, and browser-synthesized ambience (drone, heartbeat, dice clatter) plays
  with one click. Drop audio files into `data/audio/` for your own background music.

**Everyday usability**
- **In-app model switcher** — sidebar LLM settings; a cheap "utility model" tier for background
  tasks (memory compaction, lore fetch) keeps token spend down without dumbing down the Keeper.
- **Undo & export** — rewind the last turn (one step); download the session transcript as
  Markdown.
- **Autosave** — every turn, roll, and minigame outcome saves automatically and survives a
  restart mid-roll.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # then fill in your provider + API key
streamlit run interface/app.py
```

Or on Windows, just double-click `run_app.bat` — it sets up the venv on first run.

Pick a campaign in the sidebar and press **Start**. Saves are automatic
(`data/saves/<campaign>.save.json`) and survive restarts — even mid-roll.

No API key? Set `MOCK_LLM=1` in `.env` to play a short scripted demo offline, or run the
terminal client: `python cli_play.py --mock`.

## Architecture

```
rules/        pluggable rule systems: base interface, coc7e, dnd5e, wfrp, basic_d100
core/
  campaign.py         campaign YAML schema v2: load + validation
  game_state.py        GameState/CharacterState dataclasses + JSON saves
  keeper.py            LLM context assembly, output parsing, character-authority rules
  engine.py             UI-agnostic turn loop: roll gate, effects, live beat-by-beat turns,
                         talk/OOC channels, party turns
  memory.py             rolling story summary + per-character memory compaction
  minigames_catalog.py  single source of truth for minigame types per setting
  llm_client.py         provider abstraction (google / openrouter / ollama)
agents/       player_agent (AI companions), researcher, scripter, lore (real-setting canon)
interface/    app.py (Streamlit), dice.py, minigames.py, atmosphere.py, architect.py
cli_play.py   terminal REPL (dev harness)
```

See `ARCHITECTURE.md` for the full module map, data flow, and the contracts that must stay
in sync, and `LOG.md` for the detailed development history.

Campaigns are YAML files in `data/campaigns/` — see `the_haunting.yaml` for the schema
(scenes with ids, clues with skill/difficulty/reveals, stress_events, exits, an optional
`protagonist` block, and an optional `canon` block for setting lore).

## Tests

All offline, no API key needed:

```bash
python test_rules.py
python test_keeper_parser.py
python test_engine.py
python test_party_modes.py
python test_memory.py
python test_scripter.py
python test_memory_character.py
python test_id_collision.py
python test_new_systems.py
python test_minigame_catalog.py
python test_authority.py
python test_protagonist.py
```

`python -m core.campaign <file>` validates a campaign file; `python cli_play.py --mock` plays
a full session offline against a scripted Keeper.
