# AI TTRPG Runner (v3)

An LLM-driven tabletop RPG runner with a fully stateful AI Keeper (GM), real dice mechanics,
and pluggable rule systems — Call of Cthulhu 7e out of the box. Streamlit UI, works with
Google Gemini, OpenRouter (Grok etc.), or local Ollama.

## Features

- **Stateful Keeper** — every LLM call carries the full game state: current scene, clues,
  character sheets, exits, a rolling story summary, and recent chat history. The host follows
  the plot and remembers what happened.
- **Real dice** — d100 rolls resolved server-side against your actual skill values
  (CoC 7e crit/extreme/hard/regular/fumble tiers), with an animated dice tumble in the UI.
- **Consequences** — Sanity and HP actually change from roll outcomes and scripted events.
- **Roll gate + negotiation** — the game pauses on a requested roll; roll, or argue for a
  different skill.
- **Humans and AI as peers** — every character has a Human/AI toggle, switchable mid-game.
  Add extra characters anytime (hotseat multiplayer).
- **AI party modes** — `solo` (companions are narrated NPCs), `keeper` (they act when the
  Keeper calls on them), `active` (they act every turn).
- **Pluggable rule systems** — `rules/` registry; CoC 7e and a generic d100 system included.
- **Researcher** — an in-fiction Archivist that produces diegetic handouts (clippings,
  journal pages), optionally seeded by a web search.
- **Scenario Architect** — brainstorm with an AI, then generate a validated campaign YAML
  that is guaranteed to load and play.
- **Language selector** — force English, 繁體中文, or 廣東話 (narration in 書面語, dialogue in
  spoken Cantonese) regardless of what you type; or auto-detect.
- **In-app model switcher** — sidebar LLM settings; defaults to OpenRouter `x-ai/grok-4.20`,
  swap provider/model mid-session.
- **Keeper minigames** — optional dramatic devices the Keeper can invoke when the fiction
  calls for it: hold a paper to a flame to reveal hidden writing (move the candle yourself),
  solve a cipher, crack a combination lock, draw tarot omens, or watch a séance spell out a
  message. Surfaces skin themselves to the setting (parchment / modern / stone / chalk).
- **God mode** — toggle the Keeper and companions to play along with you and never block
  your intent; turn it off for an impartial host and companions with their own will.
- **Atmosphere** — the background shifts with each scene's mood, a red vignette closes in as
  sanity frays, and browser-synthesized ambience (drone, heartbeat, dice clatter) plays with
  one click. Drop audio files into `data/audio/` for your own background music.
- **Undo & export** — rewind the last turn (one step); download the session transcript
  as Markdown.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # then fill in your provider + API key
streamlit run interface/app.py
```

Pick a campaign in the sidebar and press **Start**. Saves are automatic
(`data/saves/<campaign>.save.json`) and survive restarts — even mid-roll.

No API key? Set `MOCK_LLM=1` in `.env` to play a short scripted demo offline, or run the
terminal client: `python cli_play.py --mock`.

## Architecture

```
rules/        pluggable rule systems (base interface, coc7e, basic_d100)
core/
  campaign.py    campaign YAML schema v2: load + validation
  game_state.py  GameState dataclasses + JSON saves
  keeper.py      LLM context assembly + hybrid prose/JSON output parsing
  engine.py      UI-agnostic turn loop: roll gate, effects, party turns
  memory.py      rolling summary compaction
  llm_client.py  provider abstraction (google / openrouter / ollama)
agents/       player_agent (AI companions), researcher, scripter
interface/    app.py (Streamlit), dice.py, minigames.py, atmosphere.py, architect.py
cli_play.py   terminal REPL (dev harness)
```

See `ARCHITECTURE.md` for the module map and the contracts that must stay in sync, and
`LOG.md` for the change history.

Campaigns are YAML files in `data/campaigns/` (see `the_haunting.yaml` for the schema:
scenes with ids, clues with skill/difficulty/reveals, stress_events, exits).

## Tests

All offline, no API key needed:

```bash
python test_rules.py
python test_keeper_parser.py
python test_engine.py
python test_party_modes.py
python test_memory.py
python test_scripter.py
```
