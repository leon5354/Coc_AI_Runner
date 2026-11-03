"""Web API over core.engine. Run: uvicorn server.app:app --port 8000  (serves web/dist at /).

Turns stream as NDJSON: one JSON line per beat ({label, game}), then {done, game}. The engine's
keeper_steps() generator already yields per beat, so each line is one thing happening at the table.
"""
import json
import os
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import rules  # noqa: E402
from core import campaign as campaign_mod  # noqa: E402
from core import game_state  # noqa: E402
from core import minigames_catalog as mc  # noqa: E402
from core.engine import Engine, new_game  # noqa: E402
from core.game_state import GameState, save_exists, slugify, unique_id  # noqa: E402
from core.keeper import LANGUAGE_LABELS  # noqa: E402
from core.llm_client import MAIN_MODELS, PROVIDERS, UTIL_MODELS  # noqa: E402

app = FastAPI(title="AI TTRPG Runner")
AUDIO = ROOT / "data" / "audio"   # optional BGM: drop .mp3/.ogg/.wav files here

# ponytail: one game per server process (local play). Rooms/sessions arrive with online multiplayer.
ENGINE: Engine | None = None
BUSY = threading.Lock()   # one turn at a time; a second request while a turn runs gets 409
LLM_CFG = {
    "provider": os.getenv("LLM_PROVIDER", "openrouter"),
    "model": os.getenv("LLM_MODEL", "x-ai/grok-4.20"),
    "util_provider": os.getenv("UTILITY_PROVIDER") or os.getenv("LLM_PROVIDER", "openrouter"),
    "util_model": os.getenv("UTILITY_MODEL", ""),
}


def mock() -> bool:
    return os.getenv("MOCK_LLM") == "1"


if mock():   # scripted test games must never overwrite real saves
    game_state.SAVES_DIR = game_state.SAVES_DIR / "mock"


def make_llms():
    if mock():   # offline dev mode: scripted keeper, no API key
        from cli_play import MockLLM
        m = MockLLM()
        return m, m
    from core.llm_client import LLMClient
    main = LLMClient(provider=LLM_CFG["provider"], model_name=LLM_CFG["model"])
    util = (LLMClient(provider=LLM_CFG["util_provider"], model_name=LLM_CFG["util_model"])
            if LLM_CFG["util_model"] else None)
    return main, util


def engine() -> Engine:
    if ENGINE is None:
        raise HTTPException(409, "No game running — start a campaign first.")
    return ENGINE


def game_view():
    if ENGINE is None:
        return None
    e, s = ENGINE, ENGINE.state
    scene = e.campaign.scene(s.scene_id) or {}
    return {
        "state": asdict(s),
        "title": e.campaign.title,
        "campaign": Path(s.campaign_file).stem,
        "scene_name": scene.get("name", "?"),
        "mood": e.campaign.mood(s.scene_id),
        "dice_spec": e.system.dice_spec(),
        "has_stress": e.system.has_stress,
        "can_undo": e._undo_snapshot is not None,
    }


def _line(obj) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _claim():
    if not BUSY.acquire(blocking=False):
        raise HTTPException(409, "A turn is already in progress.")


def _begin(fn, *args):
    """Claim BUSY and run an instant begin_* step; release again if it blows up."""
    _claim()
    try:
        return fn(*args)
    except Exception:
        BUSY.release()
        raise


def stream_turn(gen, label: str, extra: dict = None):
    """Drive a keeper_steps/talk_steps generator, one NDJSON line per beat. Caller holds BUSY."""
    def run():
        try:
            yield _line({"label": label, "game": game_view(), **(extra or {})})
            for nxt in gen:
                yield _line({"label": nxt, "game": game_view()})
            yield _line({"done": True, "game": game_view()})
        except Exception as e:   # LLM/network failure: state is saved per beat, so nothing is lost
            yield _line({"done": True, "error": f"{type(e).__name__}: {e}", "game": game_view()})
        finally:
            BUSY.release()
    return StreamingResponse(run(), media_type="application/x-ndjson")


def _guarded(fn):
    """Run a quick (non-streaming) engine call under BUSY."""
    _claim()
    try:
        return fn()
    finally:
        BUSY.release()


# ---------- meta / setup ----------

@app.get("/api/meta")
def meta():
    from agents.lore import DEFAULT_SETTING, SETTING_WIKIS
    camps = [{"file": p.name, "name": p.stem, "has_save": save_exists(p) is not None}
             for p in campaign_mod.list_campaigns()]
    return {
        "mock": mock(),
        "llm": LLM_CFG,
        "providers": PROVIDERS, "main_models": MAIN_MODELS, "util_models": UTIL_MODELS,
        "languages": LANGUAGE_LABELS,
        "campaigns": camps,
        "rule_systems": rules.available_systems(),
        "settings": {k: v[0] for k, v in SETTING_WIKIS.items()},
        "default_setting": DEFAULT_SETTING,
        "minigames": {g: mc.CATALOG[g]["label"] for g in sorted(mc.types())},
        "coverage": mc.coverage_rows({k: v[0] for k, v in SETTING_WIKIS.items()}),
        "audio": sorted(p.name for p in AUDIO.iterdir() if p.suffix.lower() in (".mp3", ".ogg", ".wav"))
        if AUDIO.exists() else [],
    }


class LLMIn(BaseModel):
    provider: str
    model: str
    util_model: str = ""


@app.post("/api/llm")
def set_llm(body: LLMIn):
    cfg = {"provider": body.provider, "model": body.model.strip(),
           "util_provider": body.provider, "util_model": body.util_model.strip()}
    if ENGINE and not mock():
        from core.llm_client import LLMClient
        try:
            main = LLMClient(provider=cfg["provider"], model_name=cfg["model"])
            util = (LLMClient(provider=cfg["provider"], model_name=cfg["util_model"])
                    if cfg["util_model"] else None)
        except (ValueError, ImportError) as e:
            raise HTTPException(400, str(e))
        _guarded(lambda: ENGINE.set_llm(main, util))
    LLM_CFG.update(cfg)
    return LLM_CFG


def _campaign_path(file: str) -> Path:
    path = (campaign_mod.CAMPAIGNS_DIR / file).resolve()
    if path.parent != campaign_mod.CAMPAIGNS_DIR.resolve() or not path.exists():
        raise HTTPException(404, f"No campaign {file!r}")   # also blocks ../ path tricks
    return path


class StartIn(BaseModel):
    file: str
    restart: bool = False


@app.post("/api/game/start")
def start(body: StartIn):
    path = _campaign_path(body.file)

    def go():
        global ENGINE
        save = save_exists(path)
        if body.restart and save:
            save.unlink()
            save = None
        try:
            state = GameState.load(save) if save else new_game(path)
            main, util = make_llms()
        except (ValueError, ImportError) as e:
            raise HTTPException(400, f"LLM setup failed: {e}. Copy .env.example to .env and fill "
                                     "in your provider + API key.")
        except (OSError, campaign_mod.CampaignValidationError) as e:
            raise HTTPException(400, f"Could not load this campaign or save: {e}")
        ENGINE = Engine(state, llm=main, util_llm=util)
    _guarded(go)
    return game_view()


@app.get("/api/game")
def game():
    return game_view()


class SettingsIn(BaseModel):
    language: str | None = None
    god_mode: bool | None = None
    party_mode: str | None = None
    companion_style: str | None = None


@app.patch("/api/game/settings")
def settings(body: SettingsIn):
    e = engine()
    allowed = {"language": set(LANGUAGE_LABELS), "party_mode": {"solo", "keeper", "active"},
               "companion_style": {"player", "cinematic"}, "god_mode": {True, False}}
    for k, v in body.model_dump(exclude_none=True).items():
        if v not in allowed[k]:
            raise HTTPException(400, f"Bad {k}: {v!r}")
        setattr(e.state, k, v)
    e.state.save()
    return game_view()


# ---------- turns (streamed) ----------

def _not_gated(e: Engine):
    if e.state.pending_roll or e.state.pending_minigame:
        raise HTTPException(409, "Resolve the pending roll or minigame first.")


class TextIn(BaseModel):
    text: str
    character_id: str = ""


@app.post("/api/game/act")
def act(body: TextIn):
    e = engine()
    if not body.text.strip():
        raise HTTPException(400, "Say what you do.")
    _not_gated(e)
    _begin(e.begin_action, body.character_id, body.text.strip())
    return stream_turn(e.keeper_steps(body.text.strip()), "The Keeper considers…")


@app.post("/api/game/talk")
def talk(body: TextIn):
    e = engine()
    if not body.text.strip():
        raise HTTPException(400, "Say something.")
    _not_gated(e)
    responders = _begin(e.begin_talk, body.character_id, body.text.strip())
    label = f"💬 {responders[0].name} answers…" if responders else "…"
    return stream_turn(e.talk_steps(responders), label)


@app.post("/api/game/roll")
def roll():
    e = engine()
    result = _begin(e.roll_dice)   # roll first — the dice land before the Keeper speaks
    if result is None:
        BUSY.release()
        raise HTTPException(409, "No roll is pending.")
    dice = {"roll": result.roll, "tier": result.tier, "detail": result.detail,
            "spec": e.system.dice_spec()}
    return stream_turn(e.keeper_steps("Narrate the outcome of the roll above."),
                       "The Keeper narrates the outcome…", extra={"dice": dice})


@app.post("/api/game/negotiate")
def negotiate(body: TextIn):
    e = engine()
    if not e.state.pending_roll or not body.text.strip():
        raise HTTPException(409, "Nothing to negotiate.")
    text = _begin(e.begin_negotiate, body.text.strip())
    return stream_turn(e.keeper_steps(text), "The Keeper considers…")


class MinigameIn(BaseModel):
    result: str


@app.post("/api/game/minigame")
def minigame_result(body: MinigameIn):
    e = engine()
    if not e.state.pending_minigame:
        raise HTTPException(409, "No minigame is running.")
    text = _begin(e.begin_minigame_result, body.result)
    return stream_turn(e.keeper_steps(text), "The Keeper watches…")


# ---------- quick actions ----------

class LaunchIn(BaseModel):
    type: str


@app.post("/api/game/minigame/launch")
def launch_minigame(body: LaunchIn):
    """Minigame tester: launch a catalog sample directly, no Keeper."""
    e = engine()
    if body.type not in mc.types():
        raise HTTPException(400, f"Unknown minigame {body.type!r}")
    if e.state.pending_minigame:
        raise HTTPException(409, "A minigame is already running.")
    _guarded(lambda: e.launch_minigame(mc.sample(body.type)))
    return game_view()


class QuestionIn(BaseModel):
    question: str


@app.post("/api/game/ooc")
def ooc(body: QuestionIn):
    e = engine()
    _guarded(lambda: e.ask_keeper_ooc(body.question.strip()))
    return game_view()


class ResearchIn(BaseModel):
    query: str
    web: bool = False


@app.post("/api/game/research")
def research(body: ResearchIn):
    e = engine()
    _guarded(lambda: e.consult_researcher(body.query.strip(), use_web=body.web))
    return game_view()


@app.post("/api/game/undo")
def undo():
    e = engine()
    if not _guarded(e.undo):
        raise HTTPException(409, "Nothing to undo.")
    return game_view()


class CharacterIn(BaseModel):
    name: str | None = None
    player_label: str | None = None
    personality: str | None = None
    backstory: str | None = None
    inventory: list[str] | None = None
    controller: str | None = None


@app.patch("/api/game/characters/{char_id}")
def edit_character(char_id: str, body: CharacterIn):
    e = engine()
    if not e.state.get_character(char_id):
        raise HTTPException(404, "No such character.")

    def go():
        if body.controller:
            e.set_controller(char_id, body.controller)
        e.update_character(char_id, **body.model_dump(exclude={"controller"}))
    _guarded(go)
    return game_view()


@app.post("/api/game/characters")
def add_character(body: CharacterIn):
    e = engine()
    if not (body.name or "").strip():
        raise HTTPException(400, "A name is required.")
    _guarded(lambda: e.add_character(body.name.strip(), controller=body.controller or "human",
                                     personality=body.personality or "",
                                     backstory=(body.backstory or "").strip(),
                                     player_label=(body.player_label or "").strip()))
    return game_view()


@app.get("/api/game/export", response_class=PlainTextResponse)
def export():
    return engine().transcript_md()


# ---------- scenario architect ----------

class ArchitectChatIn(BaseModel):
    history: list[dict]


@app.post("/api/architect/chat")
def architect_chat(body: ArchitectChatIn):
    from agents.scripter import Scripter
    try:
        return {"reply": Scripter().chat(body.history)}
    except (ValueError, ImportError) as e:
        raise HTTPException(400, f"LLM setup failed: {e}")


class ArchitectGenIn(BaseModel):
    history: list[dict]
    rule_system: str = "coc7e"
    setting: str = "generic"


@app.post("/api/architect/generate")
def architect_generate(body: ArchitectGenIn):
    from agents.scripter import Scripter
    context = "\n".join(f"{m['role']}: {m['content']}" for m in body.history)
    try:
        text, err = Scripter().generate_campaign(context, rule_system=body.rule_system,
                                                 setting=body.setting)
    except (ValueError, ImportError) as e:
        raise HTTPException(400, f"LLM setup failed: {e}")
    if err:
        raise HTTPException(422, err)
    title = yaml.safe_load(text).get("title", "generated")
    taken = {p.stem for p in campaign_mod.CAMPAIGNS_DIR.glob("*.yaml")}
    stem = unique_id(taken, slugify(title)[:40])   # never overwrite an existing campaign
    out = campaign_mod.CAMPAIGNS_DIR / f"{stem}.yaml"
    out.write_text(text, encoding="utf-8")
    return {"file": out.name, "yaml": text}


if AUDIO.exists():
    app.mount("/api/audio", StaticFiles(directory=AUDIO), name="audio")

# Built frontend (npm run build). Dev mode uses Vite on :5173 with /api proxied here instead.
DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
