"""Streamlit UI — thin layer over core.engine. All game logic lives in the engine."""
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
ROOT = CURRENT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from core import campaign as campaign_mod
from core.engine import Engine, new_game
from core.game_state import GameState, save_exists
from interface.dice import render_dice_roll

st.set_page_config(page_title="AI TTRPG Runner", page_icon="🐙", layout="wide")

ROLE_AVATARS = {"keeper": "🐙", "player": "🕵️", "companion": "🎭", "researcher": "📚"}


def get_engine() -> Engine | None:
    return st.session_state.get("engine")


# Curated OpenRouter picks (price/value for narrative play, July 2026) — free text still allowed.
MAIN_MODELS = ["x-ai/grok-4.20", "x-ai/grok-4.5", "anthropic/claude-sonnet-5",
               "google/gemini-3.5-flash", "qwen/qwen3.7-max", "minimax/minimax-m3"]
UTIL_MODELS = ["google/gemini-3.1-flash-lite", "qwen/qwen3.7-plus", "minimax/minimax-m3",
               "tencent/hy3", "stepfun/step-3.7-flash"]
CUSTOM = "custom..."


def make_llms():
    """Build (main, utility) LLM clients from in-app choices (session) or .env defaults."""
    if os.getenv("MOCK_LLM") == "1":   # offline dev mode: scripted keeper, no API key
        from cli_play import MockLLM
        m = MockLLM()
        return m, m
    from core.llm_client import LLMClient
    cfg = st.session_state.get("llm_cfg")
    main = LLMClient(provider=cfg["provider"], model_name=cfg["model"]) if cfg else LLMClient()
    ucfg = st.session_state.get("util_cfg")
    if ucfg:
        util = LLMClient(provider=ucfg["provider"], model_name=ucfg["model"])
    elif os.getenv("UTILITY_MODEL"):
        util = LLMClient(provider=os.getenv("UTILITY_PROVIDER") or None,
                         model_name=os.getenv("UTILITY_MODEL"))
    else:
        util = None
    return main, util


def start_game(campaign_path, resume: bool):
    save = save_exists(campaign_path)
    try:
        state = GameState.load(save) if (resume and save) else new_game(campaign_path)
    except (FileNotFoundError, OSError) as e:
        st.session_state.engine = None
        st.session_state.setup_error = f"Could not load this campaign or save: {e}\nTry Restart."
        return
    try:
        main, util = make_llms()
        st.session_state.engine = Engine(state, llm=main, util_llm=util)
        st.session_state.pop("setup_error", None)
    except (ValueError, ImportError) as e:
        st.session_state.engine = None
        st.session_state.setup_error = (
            f"LLM setup failed: {e}\n\nCopy .env.example to .env and fill in your provider + API key."
        )
        return
    for k in ("last_roll", "last_minigame", "turn_gen", "turn_label"):
        st.session_state.pop(k, None)


def render_sidebar(engine: Engine | None):
    with st.sidebar:
        st.title("🐙 AI TTRPG Runner")
        cfg = st.session_state.get("llm_cfg") or {
            "provider": os.getenv("LLM_PROVIDER", "openrouter"),
            "model": os.getenv("LLM_MODEL", "x-ai/grok-4.20"),
        }
        st.caption(("🎭 MOCK MODE — " if os.getenv("MOCK_LLM") == "1" else "")
                   + f"LLM: {cfg['provider']} / {cfg['model']}")

        with st.expander("🧠 LLM settings"):
            providers = ["openrouter", "google", "ollama"]
            prov = st.selectbox("Provider", providers,
                                index=providers.index(cfg["provider"]) if cfg["provider"] in providers else 0)
            opts = MAIN_MODELS + [CUSTOM]
            pick = st.selectbox("Keeper model", opts,
                                index=opts.index(cfg["model"]) if cfg["model"] in opts else len(opts) - 1)
            model = st.text_input("Custom model id", value=cfg["model"]) if pick == CUSTOM else pick

            ucfg = st.session_state.get("util_cfg")
            uopts = ["(same as keeper)"] + UTIL_MODELS + [CUSTOM]
            ucur = ucfg["model"] if ucfg else "(same as keeper)"
            upick = st.selectbox("Utility model (summaries & lore — cheap)", uopts,
                                 index=uopts.index(ucur) if ucur in uopts else len(uopts) - 1)
            umodel = st.text_input("Custom utility model id",
                                   value=ucur if ucfg else "") if upick == CUSTOM else upick

            if st.button("Apply", key="apply_llm"):
                if engine and os.getenv("MOCK_LLM") != "1":
                    try:
                        from core.llm_client import LLMClient
                        main = LLMClient(provider=prov, model_name=model.strip())
                        util = None if umodel == "(same as keeper)" else \
                            LLMClient(provider=prov, model_name=umodel.strip())
                        engine.set_llm(main, util)
                    except (ValueError, ImportError) as e:
                        st.error(str(e))
                        st.stop()
                st.session_state.llm_cfg = {"provider": prov, "model": model.strip()}
                if umodel == "(same as keeper)":
                    st.session_state.pop("util_cfg", None)
                else:
                    st.session_state.util_cfg = {"provider": prov, "model": umodel.strip()}
                st.rerun()

        campaigns = campaign_mod.list_campaigns()
        if not campaigns:
            st.error("No valid campaigns in data/campaigns/")
            return
        names = [p.stem for p in campaigns]
        idx = st.selectbox("Campaign", range(len(names)), format_func=lambda i: names[i])
        chosen = campaigns[idx]

        c1, c2 = st.columns(2)
        has_save = save_exists(chosen) is not None
        if c1.button("▶ Resume" if has_save else "▶ Start", width="stretch"):
            start_game(chosen, resume=True)
            st.rerun()
        if c2.button("🔄 Restart", width="stretch"):
            save = save_exists(chosen)
            if save:
                save.unlink()
            start_game(chosen, resume=False)
            st.rerun()

        if not engine:
            return
        state = engine.state
        st.divider()

        from core.keeper import LANGUAGE_LABELS
        langs = list(LANGUAGE_LABELS)
        lang = st.segmented_control("Language", langs,
                                    format_func=LANGUAGE_LABELS.get,
                                    default=state.language if state.language in langs else "auto",
                                    key="lang_pick")
        if lang and lang != state.language:
            state.language = lang
            state.save()

        god = st.toggle("😇 God mode", value=state.god_mode,
                        help="ON: the Keeper and companions play along with whatever you steer "
                             "toward — never blocking your intent, biasing fate your way. "
                             "OFF: impartial Keeper, companions with their own will.")
        if god != state.god_mode:
            state.god_mode = god
            state.save()

        mode = st.radio("AI party mode", ["solo", "keeper", "active"],
                        index=["solo", "keeper", "active"].index(state.party_mode),
                        help="solo: AI companions are narrated NPCs. keeper: they act when the "
                             "Keeper calls on them. active: they act every turn.",
                        horizontal=True)
        if mode != state.party_mode:
            state.party_mode = mode
            state.save()

        styles = {"player": "🎭 Player", "cinematic": "🎬 Cinematic"}
        cur = state.companion_style if state.companion_style in styles else "player"
        style = st.segmented_control(
            "Companion voice", list(styles), format_func=styles.get, default=cur,
            key="companion_style_pick",
            help="Player: AI companions talk like people at a table — intent + dialogue, concise. "
                 "Cinematic: richer novelistic prose.")
        if style and style != state.companion_style:
            state.companion_style = style
            state.save()

        st.subheader("Party")
        for ch in state.characters:
            status = "" if ch.status == "active" else f" — {ch.status.upper()}"
            st.markdown(f"**{ch.name}**{status}"
                        + (f" · _{ch.player_label}_" if ch.player_label else ""))
            st.progress(max(ch.hp, 0) / max(ch.max_hp, 1), text=f"HP {ch.hp}/{ch.max_hp}")
            if ch.max_stress > 1:
                st.progress(max(ch.stress, 0) / ch.max_stress, text=f"Mind {ch.stress}/{ch.max_stress}")
            is_ai = st.toggle("AI-controlled", value=(ch.controller == "ai"), key=f"ctl_{ch.id}")
            want = "ai" if is_ai else "human"
            if want != ch.controller:
                engine.set_controller(ch.id, want)
                st.rerun()

        ai_chars = [c for c in state.characters if c.controller == "ai"]
        if ai_chars:
            with st.expander("🧠 Inner life"):
                who = st.selectbox("Character", [c.id for c in ai_chars], key="mind_char",
                                   format_func=lambda i: state.get_character(i).name)
                ch = state.get_character(who)
                st.caption("What they privately remember — this is what they act from.")
                if ch.memory_summary:
                    st.markdown(f"**Their memory**\n\n{ch.memory_summary}")
                else:
                    st.caption("_No distilled memory yet — it forms as they live through more._")
                if ch.relationships:
                    st.markdown("**What they think of the others**")
                    for k, v in ch.relationships.items():
                        st.markdown(f"- **{k}**: {v}")
                if ch.private_thoughts:
                    st.markdown("**Recent thoughts**")
                    for t in reversed(ch.private_thoughts[-6:]):
                        st.markdown(f"- _{t}_")

        with st.expander("📖 Character backgrounds"):
            ids = [c.id for c in state.characters]
            eid = st.selectbox("Character", ids, key="edit_char",
                               format_func=lambda i: state.get_character(i).name)
            ch = state.get_character(eid)
            with st.form(f"edit_{eid}"):
                nm = st.text_input("Name", value=ch.name)
                lbl = st.text_input("Player label", value=ch.player_label)
                pers = st.text_area("Personality", value=ch.personality, height=80,
                                    help="Temperament and quirks. Drives how an AI character acts.")
                back = st.text_area("Background story", value=ch.backstory, height=140,
                                    help="History, occupation, secrets, why they're here. The Keeper "
                                         "weaves this into the story.")
                inv = st.text_area("Inventory (one per line)", value="\n".join(ch.inventory), height=80)
                if st.form_submit_button("Save background"):
                    engine.update_character(eid, name=nm.strip() or ch.name, player_label=lbl.strip(),
                                            personality=pers.strip(), backstory=back.strip(),
                                            inventory=inv.splitlines())
                    st.rerun()

        with st.expander("➕ Add character"):
            with st.form("add_char", clear_on_submit=True):
                nm = st.text_input("Name")
                lbl = st.text_input("Player label (e.g. Player 2)", value="")
                ctl = st.radio("Controlled by", ["human", "ai"], horizontal=True)
                pers = st.text_input("Personality", value="")
                back = st.text_area("Background story", value="", height=100)
                if st.form_submit_button("Add") and nm.strip():
                    engine.add_character(nm.strip(), controller=ctl, personality=pers,
                                         backstory=back.strip(), player_label=lbl.strip())
                    st.rerun()

        from interface.atmosphere import render_ambience, render_bgm_picker, scene_mood
        active = state.active_character() or state.characters[0]
        render_ambience(scene_mood(engine.campaign, state.scene_id),
                        active.stress / max(active.max_stress, 1),
                        dice_nonce=len(state.dice_log))
        render_bgm_picker()

        with st.expander("🎲 Dice log"):
            for line in reversed(state.dice_log[-25:]):
                st.caption(line)

        with st.expander("🧪 Minigame tester"):
            from core import minigames_catalog as mc
            st.caption("Launch any minigame directly (no Keeper) to try it out. The result is "
                       "fed back into the story like a real one.")
            busy = state.pending_minigame is not None
            for g in sorted(mc.types()):
                if st.button(mc.CATALOG[g]["label"], key=f"mg_test_{g}",
                             disabled=busy, width="stretch"):
                    engine.launch_minigame(mc.sample(g))
                    st.rerun()

        c1, c2 = st.columns(2)
        if c1.button("↩ Undo turn", width="stretch",
                     help="Rewind to before the last action / roll / minigame (one step)"):
            if engine.undo():
                for k in ("last_roll", "turn_gen", "turn_label"):
                    st.session_state.pop(k, None)   # an in-flight turn would hold a stale state
                st.rerun()
        c2.download_button("📜 Export", data=_transcript_md(engine),
                           file_name=f"{engine.campaign.title}.md",
                           mime="text/markdown", width="stretch",
                           help="Download the full session transcript as Markdown")


def _transcript_md(engine) -> str:
    state = engine.state
    lines = [f"# {engine.campaign.title}", ""]
    for m in state.messages_archive + state.messages:
        who = m.get("name") or m["role"].capitalize()
        lines.append(f"**{who}:** {m['content']}\n")
    if state.dice_log:
        lines += ["---", "## Dice log", ""] + [f"- {l}" for l in state.dice_log]
    return "\n".join(lines)


def render_transcript(state):
    for m in state.messages_archive + state.messages:
        content = m["content"]
        if m["role"] == "player" and content.startswith("ROLL RESULT:"):
            continue  # legacy saves: superseded by the "dice" role below
        if m["role"] == "dice":
            with st.chat_message("assistant", avatar="🎲"):
                st.markdown(f"**{content}**")
            continue
        if m["role"] == "ooc":   # table talk — outside the fiction
            with st.chat_message("assistant", avatar="💭"):
                st.caption(f"{m.get('name', 'OOC')} · out of character")
                st.markdown(f":gray[{content}]")
            continue
        if m["role"] == "player" and content.startswith("MINIGAME RESULT:"):
            with st.chat_message("player", avatar="🧩"):
                st.caption("Minigame")
                st.markdown(f"*{content[len('MINIGAME RESULT:'):].strip()}*")
            continue
        with st.chat_message(m["role"], avatar=ROLE_AVATARS.get(m["role"], "❔")):
            if m.get("name"):
                st.caption(m["name"])
            st.markdown(content)


def start_turn(gen, label: str):
    """Hand a keeper_steps generator to the live loop; the UI advances it one beat per rerun."""
    st.session_state.turn_gen = gen
    st.session_state.turn_label = label
    st.rerun()


def advance_turn(engine: Engine) -> bool:
    """Run ONE beat of the in-flight turn, then rerun so the new message is visible.
    Returns True if a turn is in flight (caller should stop rendering input widgets)."""
    gen = st.session_state.get("turn_gen")
    if gen is None:
        return False
    with st.spinner(st.session_state.get("turn_label", "…")):
        try:
            st.session_state.turn_label = next(gen)
        except StopIteration:
            st.session_state.pop("turn_gen", None)
            st.session_state.pop("turn_label", None)
    st.rerun()
    return True  # unreachable; st.rerun() raises


def render_roll_gate(engine: Engine):
    state = engine.state
    pr = state.pending_roll
    char = state.get_character(pr["character_id"])
    with st.container(border=True):
        st.markdown(f"### 🎲 {char.name} must roll **{pr['skill']}** "
                    f"(target {pr['target']}, {pr['difficulty']})")
        if pr.get("reason"):
            st.caption(pr["reason"])
        c1, c2 = st.columns([1, 2])
        if c1.button("Roll the dice", type="primary", width="stretch"):
            result = engine.roll_dice()          # roll first — the dice land before the Keeper speaks
            st.session_state.last_roll = {
                "roll": result.roll, "tier": result.tier, "detail": result.detail,
                "spec": engine.system.dice_spec(),
            }
            start_turn(engine.keeper_steps("Narrate the outcome of the roll above."),
                       "The Keeper narrates the outcome…")
        with c2.form("negotiate", clear_on_submit=True):
            arg = st.text_input("...or argue for a different approach",
                                placeholder="e.g. I'd use Fast Talk instead — he's distracted")
            if st.form_submit_button("Negotiate") and arg.strip():
                start_turn(engine.keeper_steps(engine.begin_negotiate(arg.strip())),
                           "The Keeper considers…")


def render_play_tab(engine: Engine | None):
    if err := st.session_state.get("setup_error"):
        st.error(err)
    if not engine:
        if not st.session_state.get("setup_error"):
            st.info("Pick a campaign in the sidebar and press Start.")
        return
    state = engine.state
    from interface.atmosphere import inject_scene_style, scene_mood
    active = state.active_character() or state.characters[0]
    stress_ratio = active.stress / max(active.max_stress, 1)
    mood = scene_mood(engine.campaign, state.scene_id)
    inject_scene_style(mood, stress_ratio)

    st.subheader(engine.campaign.title)
    scene = engine.campaign.scene(state.scene_id) or {}
    pills = [f":violet-badge[📍 {scene.get('name', '?')}]",
             f":blue-badge[⏱ turn {state.turn_count}]",
             f":gray-badge[🎭 {active.name}'s move]"]
    if state.pending_roll:
        pills.append(":red-badge[🎲 roll pending]")
    if state.pending_minigame:
        pills.append(":orange-badge[🧩 minigame]")
    if state.god_mode:
        pills.append(":green-badge[😇 god mode]")
    if stress_ratio < 0.4:
        pills.append(f":red-badge[🧠 {active.stress}/{active.max_stress} — fraying]")
    st.markdown(" ".join(pills))

    if state.summary:
        with st.expander("📖 The story so far", expanded=False):
            st.markdown(state.summary)

    render_transcript(state)

    if "last_roll" in st.session_state:
        lr = st.session_state.pop("last_roll")
        render_dice_roll(lr["roll"], lr["tier"], lr["detail"], lr["spec"],
                         key=f"dice_{len(state.dice_log)}")

    # A turn is in flight: run one beat, then rerun so the new message appears. Live play.
    advance_turn(engine)

    if state.pending_roll:
        render_roll_gate(engine)
        return

    if state.pending_minigame:
        from interface.minigames import render_minigame
        payload = state.pending_minigame
        result = render_minigame(payload, key=f"mg_{state.minigame_count}")
        if result:
            st.session_state.last_minigame = {"payload": payload, "result": result}
            start_turn(engine.keeper_steps(engine.begin_minigame_result(result)),
                       "The Keeper watches…")
        return

    if "last_minigame" in st.session_state:
        with st.expander("🧩 Last minigame result", expanded=False):
            from interface.minigames import render_frozen
            render_frozen(st.session_state.last_minigame)

    humans = state.human_characters()
    if not humans:
        st.warning("No human-controlled characters — flip one to human in the sidebar.")
        return
    if len(humans) > 1:
        ids = [c.id for c in humans]
        default = state.active_character_id if state.active_character_id in ids else ids[0]
        acting = st.selectbox("Acting as", ids, index=ids.index(default),
                              format_func=lambda i: state.get_character(i).name)
    else:
        acting = humans[0].id

    with st.expander("📚 Consult the Archives"):
        with st.form("research", clear_on_submit=True):
            q = st.text_input("Research query", placeholder="Elias Corwin, 1835, grave robbery...")
            web = st.checkbox("Also search the web for flavor", value=False)
            if st.form_submit_button("Research") and q.strip():
                with st.spinner("Dust rises from old shelves..."):
                    engine.consult_researcher(q.strip(), use_web=web)
                st.rerun()

    modes = {"🎬 Act": "act", "💬 Talk": "talk", "❓ Ask the Keeper": "ooc"}
    picked = st.segmented_control(
        "Mode", list(modes), default="🎬 Act", key="input_mode", label_visibility="collapsed",
        help="Act: commit to an action — the Keeper narrates, dice may be called. "
             "Talk: speak to the party without spending a turn — no dice, no plot advance. "
             "Ask the Keeper: an out-of-character question; changes nothing in the game.")
    mode = modes.get(picked or "🎬 Act", "act")
    name = state.get_character(acting).name

    placeholder = {"act": f"What does {name} do?",
                   "talk": f"What does {name} say? (no turn spent)",
                   "ooc": "Ask the Keeper anything — rules, a recap, your options…"}[mode]
    prompt = st.chat_input(placeholder)
    if prompt:
        if mode == "act":
            start_turn(engine.keeper_steps(engine.begin_action(acting, prompt)),
                       "The Keeper considers…")
        elif mode == "talk":
            responders = engine.begin_talk(acting, prompt)
            start_turn(engine.talk_steps(responders),
                       f"💬 {responders[0].name} answers…" if responders else "…")
        else:
            with st.spinner("The Keeper leans back…"):
                engine.ask_keeper_ooc(prompt)
            st.rerun()


def render_architect_tab():
    try:
        from interface.architect import render_architect
        render_architect()
    except ImportError:
        st.info("Scenario Architect is being rebuilt — coming in the next phase.")


engine = get_engine()
render_sidebar(engine)
tab_play, tab_architect = st.tabs(["🎲 Play", "🏗️ Scenario Architect"])
with tab_play:
    render_play_tab(get_engine())
with tab_architect:
    render_architect_tab()
