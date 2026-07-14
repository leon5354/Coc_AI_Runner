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

    c1, c2 = st.columns([1, 1])
    system_name = c1.selectbox("Rule system", rules.available_systems(),
                               index=rules.available_systems().index("coc7e"))
    generate = c2.button("⚒️ Generate campaign", type="primary",
                         disabled=not st.session_state.architect_history,
                         width="stretch")

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
        with st.spinner("The Architect drafts blueprints... (this can take a minute)"):
            yaml_text, err = Scripter().generate_campaign(context, rule_system=system_name)
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
