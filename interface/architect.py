"""Scenario Architect tab: brainstorm with the Scripter, then generate a validated campaign."""
import re

import streamlit as st

import rules
from core.campaign import CAMPAIGNS_DIR


def _slug(title: str) -> str:
    """Filename-safe slug that keeps CJK characters (Chinese titles were collapsing to 'generated')."""
    s = re.sub(r"[^\w]+", "_", title.lower(), flags=re.UNICODE).strip("_")[:40]
    if not s:
        from datetime import datetime
        s = "generated_" + datetime.now().strftime("%m%d_%H%M")
    return s


def render_architect():
    if "architect_history" not in st.session_state:
        st.session_state.architect_history = []

    st.caption("Brainstorm a scenario with the Scripter, then generate a playable campaign file.")

    for m in st.session_state.architect_history:
        with st.chat_message(m["role"], avatar="🏗️" if m["role"] == "assistant" else "🕵️"):
            st.markdown(m["content"])

    from agents.lore import DEFAULT_SETTING, SETTING_WIKIS
    c1, c2 = st.columns([1, 1])
    system_name = c1.selectbox("Rule system", rules.available_systems(),
                               index=rules.available_systems().index("coc7e"))
    setting_keys = list(SETTING_WIKIS)
    default_setting = DEFAULT_SETTING.get(system_name, "generic")
    setting = c2.selectbox(
        "Setting / IP", setting_keys,
        index=setting_keys.index(default_setting) if default_setting in setting_keys else 0,
        format_func=lambda k: SETTING_WIKIS[k][0],
        help="Pick a real setting to ground the plot in its official wiki canon (fetched once at "
             "generation and baked into the campaign). 'Generic / homebrew' skips lore lookup. "
             "Generated campaigns of trademarked settings are for personal play only.")
    generate = st.button("⚒️ Generate campaign", type="primary",
                         disabled=not st.session_state.architect_history,
                         width="stretch")

    with st.expander("🧩 Minigame coverage by setting"):
        from core import minigames_catalog
        st.caption("Which keeper-invokable minigames fit each setting (from the catalog — "
                   "the keeper is only offered the ✓ ones).")
        names = {k: v[0] for k, v in SETTING_WIKIS.items()}
        header = "| Minigame | " + " | ".join(names.values()) + " |"
        sep = "|---" * (len(names) + 1) + "|"
        rows = ["| " + " | ".join(r) + " |" for r in minigames_catalog.coverage_rows(names)]
        st.markdown("\n".join([header, sep] + rows))

    prompt = st.chat_input("Describe the scenario you want...")
    if prompt:
        st.session_state.architect_history.append({"role": "user", "content": prompt})
        try:
            from agents.scripter import Scripter
            with st.spinner("The Scripter ponders..."):
                reply = Scripter().chat(st.session_state.architect_history)
        except (ValueError, ImportError) as e:
            st.error(f"LLM setup failed: {e}")
            return
        st.session_state.architect_history.append({"role": "assistant", "content": reply})
        st.rerun()

    if generate:
        from agents.scripter import Scripter
        context = "\n".join(f"{m['role']}: {m['content']}" for m in st.session_state.architect_history)
        spin = ("Consulting the archives, then drafting blueprints..." if setting != "generic"
                else "The Architect drafts blueprints... (this can take a minute)")
        with st.spinner(spin):
            yaml_text, err = Scripter().generate_campaign(context, rule_system=system_name,
                                                          setting=setting)
        if err:
            st.error(err)
            return
        import yaml as yaml_mod
        title = yaml_mod.safe_load(yaml_text).get("title", "generated")
        out = CAMPAIGNS_DIR / f"{_slug(title)}.yaml"
        out.write_text(yaml_text, encoding="utf-8")
        st.success(f"Campaign saved: **{out.name}** — validated and ready in the Play tab "
                   f"(pick it in the sidebar and press Start).")
        with st.expander("View generated YAML"):
            st.code(yaml_text, language="yaml")
