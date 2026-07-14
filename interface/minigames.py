"""Keeper-invokable minigames. Each render_* returns a result string once finished, else None.
The engine feeds that string back to the keeper as MINIGAME RESULT.
render_frozen() draws a static snapshot of a finished minigame (the "freeze-frame")."""
import random

import streamlit as st

# Skins let the surface match the current location/era (keeper picks via payload["skin"]).
SKINS = {
    "parchment": {"bg": "linear-gradient(160deg,#efe3c2,#d9c795 90%)", "ink": "#3a2b16",
                  "hot": "#58230a", "font": "Georgia, serif"},
    "modern":    {"bg": "linear-gradient(160deg,#f8f8f6,#e4e4de 90%)", "ink": "#222",
                  "hot": "#b3541e", "font": "'Courier New', monospace"},
    "stone":     {"bg": "linear-gradient(160deg,#4a4a48,#2e2e2c 90%)", "ink": "#9a9a90",
                  "hot": "#d8c690", "font": "Georgia, serif"},
    "chalk":     {"bg": "linear-gradient(160deg,#233329,#16211b 90%)", "ink": "#3d5245",
                  "hot": "#e8e6d8", "font": "'Comic Sans MS', cursive"},
}

# --- burn reveal: move the flame over the surface; hidden writing chars fade in ---

_BURN_HTML = """
<div class="paper-wrap">
  <div class="paper" id="paper"></div>
  <div class="flame" id="flame">🕯️</div>
  <div class="hint">Move the candle across the surface…</div>
</div>
"""

_BURN_CSS = """
.paper-wrap { position: relative; padding: 8px 0 4px; cursor: none; }
.paper {
  min-height: 150px; padding: 26px 30px; border-radius: 3px;
  box-shadow: 0 4px 14px rgba(0,0,0,.45);
  font-size: 1.15em; line-height: 1.9; letter-spacing: .06em;
  user-select: none;
}
.paper span { opacity: 0; transition: opacity 1.4s ease, text-shadow 1.4s ease; }
.paper span.hot { opacity: 1; }
.flame { position: absolute; font-size: 1.7em; pointer-events: none; display: none;
         filter: drop-shadow(0 0 10px rgba(255,150,30,.9)); transform: translate(-50%, -85%); }
.hint { text-align: center; font-size: .8em; opacity: .6; padding-top: 6px;
        color: var(--st-text-color, #ccc); font-family: sans-serif; }
"""

_BURN_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const paper = parentElement.querySelector("#paper")
  const flame = parentElement.querySelector("#flame")
  const wrap = parentElement.querySelector(".paper-wrap")
  if (!paper || paper.dataset.built) return
  paper.dataset.built = "1"

  const skin = (data && data.skin) || {}
  paper.style.background = skin.bg || ""
  paper.style.color = skin.ink || "#3a2b16"
  paper.style.fontFamily = skin.font || "Georgia, serif"
  const hotColor = skin.hot || "#58230a"

  const text = (data && data.text) || ""
  const spans = []
  for (const ch of text) {
    const s = document.createElement("span")
    s.textContent = ch
    paper.appendChild(s)
    spans.push(s)
  }
  let revealed = 0, done = false

  wrap.onmousemove = (e) => {
    const wr = wrap.getBoundingClientRect()
    flame.style.display = "block"
    flame.style.left = (e.clientX - wr.left) + "px"
    flame.style.top = (e.clientY - wr.top) + "px"
    for (const s of spans) {
      if (s.classList.contains("hot")) continue
      const r = s.getBoundingClientRect()
      const dx = e.clientX - (r.left + r.width / 2)
      const dy = e.clientY - (r.top + r.height / 2)
      if (dx * dx + dy * dy < 2600) {
        s.classList.add("hot")
        s.style.color = hotColor
        s.style.textShadow = `0 0 6px ${hotColor}66`
        revealed++
      }
    }
    if (!done && text.length > 0 && revealed >= spans.length * 0.85) {
      done = true
      for (const s of spans) { s.classList.add("hot"); s.style.color = hotColor }
      setTriggerValue("revealed", true)
    }
  }
  wrap.onmouseleave = () => { flame.style.display = "none" }
}
"""

_burn_component = st.components.v2.component(
    "burn_reveal", html=_BURN_HTML, css=_BURN_CSS, js=_BURN_JS)


def render_burn_reveal(payload: dict, key: str):
    st.markdown(f"### 🕯️ {payload.get('context', 'A suspicious blank surface...')}")
    skin = SKINS.get(payload.get("skin", "parchment"), SKINS["parchment"])
    result = _burn_component(data={"text": payload.get("hidden_text", ""), "skin": skin},
                             key=key, on_revealed_change=lambda: None)
    if result.revealed or st.button("Expose the whole surface to the heat", key=f"{key}_skip"):
        return f"The heat reveals hidden writing: \"{payload.get('hidden_text', '')}\""
    return None


# --- seance: the planchette spells the message letter by letter ---

_SEANCE_HTML = """
<div class="board">
  <div class="spelled" id="spelled"></div>
  <div class="planchette" id="pl">☩</div>
</div>
"""

_SEANCE_CSS = """
.board { position: relative; min-height: 130px; border-radius: 8px; padding: 24px;
  background: radial-gradient(ellipse at center, #241a10, #0d0a06 85%);
  border: 1px solid #4a3a22; font-family: Georgia, serif; text-align: center; }
.spelled { font-size: 1.7em; letter-spacing: .35em; color: #d8c690; min-height: 1.5em;
  text-shadow: 0 0 12px rgba(216,198,144,.5); }
.planchette { font-size: 1.6em; color: #8a7550; margin-top: 14px;
  animation: drift 2.2s ease-in-out infinite alternate; }
@keyframes drift { from { transform: translateX(-28px) rotate(-7deg); }
                   to   { transform: translateX(28px) rotate(7deg); } }
"""

_SEANCE_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const el = parentElement.querySelector("#spelled")
  if (!el || el.dataset.started) return
  el.dataset.started = "1"
  const msg = ((data && data.message) || "").toUpperCase()
  let i = 0
  const t = setInterval(() => {
    el.textContent = msg.slice(0, ++i)
    if (i >= msg.length) { clearInterval(t); setTriggerValue("finished", true) }
  }, 380)
  return () => clearInterval(t)
}
"""

_seance_component = st.components.v2.component(
    "seance_board", html=_SEANCE_HTML, css=_SEANCE_CSS, js=_SEANCE_JS)


def render_seance(payload: dict, key: str):
    st.markdown("### 🕯️ The planchette begins to move...")
    _seance_component(data={"message": payload.get("message", "")}, key=key,
                      on_finished_change=lambda: None)
    if st.button("It stops.", key=f"{key}_done"):
        return f"The spirit spelled out: \"{payload.get('message', '')}\""
    return None


# --- cipher: native widgets, 3 attempts ---

def render_cipher(payload: dict, key: str):
    st.markdown("### 🔏 A cipher blocks the way")
    st.code(payload.get("ciphertext", ""), language=None)
    attempts_key = f"{key}_attempts"
    attempts = st.session_state.setdefault(attempts_key, 0)
    solution = (payload.get("solution") or "").strip().lower()

    if attempts >= 1 and payload.get("hint"):
        st.caption(f"💡 Hint: {payload['hint']}")

    with st.form(f"{key}_form", clear_on_submit=True):
        guess = st.text_input("Your answer", key=f"{key}_guess")
        submitted = st.form_submit_button("Try it")
    if submitted and guess.strip():
        if guess.strip().lower() == solution:
            st.session_state.pop(attempts_key, None)
            return f"The player SOLVED the cipher — the answer was \"{payload.get('solution')}\""
        st.session_state[attempts_key] = attempts + 1
        if st.session_state[attempts_key] >= 3:
            st.session_state.pop(attempts_key, None)
            return ("The player FAILED to solve the cipher after 3 attempts "
                    f"(the answer was \"{payload.get('solution')}\" — do not reveal it unless the fiction allows)")
        st.error(f"Wrong. {3 - st.session_state[attempts_key]} attempt(s) left.")
    if st.button("Give up", key=f"{key}_giveup"):
        st.session_state.pop(attempts_key, None)
        return "The player gave up on the cipher unsolved"
    return None


# --- combination lock: guess the digits, feedback on correct positions, 4 attempts ---

def render_combination_lock(payload: dict, key: str):
    code = str(payload.get("code", "")).strip()
    st.markdown("### 🔒 A combination lock")
    if payload.get("clue"):
        st.caption(f"🧩 {payload['clue']}")
    attempts_key = f"{key}_lock_attempts"
    attempts = st.session_state.setdefault(attempts_key, 0)
    max_attempts = int(payload.get("attempts", 4))

    with st.form(f"{key}_lock_form", clear_on_submit=True):
        guess = st.text_input(f"Enter {len(code)} digits", max_chars=len(code), key=f"{key}_lock_guess")
        submitted = st.form_submit_button("Turn the dial")
    if submitted and guess.strip():
        guess = guess.strip()
        if guess == code:
            st.session_state.pop(attempts_key, None)
            return f"The player OPENED the lock (code {code}) on attempt {attempts + 1}"
        st.session_state[attempts_key] = attempts + 1
        if st.session_state[attempts_key] >= max_attempts:
            st.session_state.pop(attempts_key, None)
            return (f"The lock JAMMED after {max_attempts} failed attempts — it will not open by dial "
                    f"anymore (the code was {code}; do not reveal it)")
        correct = sum(1 for a, b in zip(guess, code) if a == b)
        st.error(f"The dial resists. {correct}/{len(code)} digits clicked into place. "
                 f"{max_attempts - st.session_state[attempts_key]} attempt(s) left.")
    if st.button("Step away", key=f"{key}_lock_giveup"):
        st.session_state.pop(attempts_key, None)
        return "The player stepped away from the lock without opening it"
    return None


# --- tarot draw: three cards, keeper must weave the omens in ---

TAROT_DECK = [
    ("The Tower", "sudden catastrophe; a structure — literal or of belief — collapses"),
    ("The Moon", "illusion and hidden enemies; nothing seen tonight is what it appears"),
    ("Death", "an irreversible transformation approaches; something must end"),
    ("The Hanged Man", "sacrifice; progress only through surrendering something dear"),
    ("The Hermit", "a solitary figure holds the answer; seek the one who withdrew"),
    ("Wheel of Fortune", "fate turns; an unlikely coincidence will decide everything"),
    ("The High Priestess", "secret knowledge; a text or whisper holds the key"),
    ("The Devil", "bondage; someone here is already owned by another will"),
    ("The Star", "one genuine hope; a small light survives if protected"),
    ("Judgement", "the past rises; something buried refuses to stay buried"),
    ("The Fool", "a reckless step; innocence walks into the abyss smiling"),
    ("The Lovers", "a choice between two paths; loyalty will be tested"),
]


def render_tarot_draw(payload: dict, key: str):
    st.markdown(f"### 🃏 {payload.get('context', 'The cards are laid out...')}")
    drawn_key = f"{key}_tarot"
    if drawn_key not in st.session_state:
        if st.button("Draw three cards", key=f"{key}_draw", type="primary"):
            st.session_state[drawn_key] = random.sample(TAROT_DECK, 3)
            st.rerun()
        return None
    cards = st.session_state[drawn_key]
    cols = st.columns(3)
    for col, (name, meaning) in zip(cols, cards):
        with col, st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(meaning)
    if st.button("Accept the omen", key=f"{key}_accept"):
        st.session_state.pop(drawn_key, None)
        return ("The cards drawn: " + "; ".join(f"{n} ({m})" for n, m in cards)
                + ". Weave these omens into what follows.")
    return None


RENDERERS = {"burn_reveal": render_burn_reveal, "cipher": render_cipher, "seance": render_seance,
             "combination_lock": render_combination_lock, "tarot_draw": render_tarot_draw}

ICONS = {"burn_reveal": "🕯️", "cipher": "🔏", "seance": "☩",
         "combination_lock": "🔒", "tarot_draw": "🃏"}


def render_minigame(payload: dict, key: str):
    """Dispatch. Returns result string once the minigame concludes, else None."""
    renderer = RENDERERS.get(payload.get("type"))
    if renderer is None:
        return f"(unsupported minigame type {payload.get('type')!r} — skipped)"
    with st.container(border=True):
        return renderer(payload, key)


def render_frozen(record: dict):
    """Static freeze-frame of a finished minigame: {payload, result}."""
    payload, result = record.get("payload", {}), record.get("result", "")
    icon = ICONS.get(payload.get("type"), "🧩")
    with st.container(border=True):
        st.markdown(f"{icon} **{payload.get('context') or payload.get('type', 'minigame')}**")
        if payload.get("type") == "burn_reveal":
            skin = SKINS.get(payload.get("skin", "parchment"), SKINS["parchment"])
            st.markdown(
                f"<div style='background:{skin['bg']};color:{skin['hot']};padding:18px 24px;"
                f"border-radius:3px;font-family:{skin['font']};letter-spacing:.06em;'>"
                f"{payload.get('hidden_text', '')}</div>", unsafe_allow_html=True)
        elif payload.get("type") == "cipher":
            st.code(payload.get("ciphertext", ""), language=None)
        st.caption(result)
