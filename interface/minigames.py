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
  <div class="hint">Move the candle across the surface… <span id="pagelabel"></span></div>
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
  const pageLabel = parentElement.querySelector("#pagelabel")
  if (!paper || paper.dataset.built) return
  paper.dataset.built = "1"

  const skin = (data && data.skin) || {}
  paper.style.background = skin.bg || ""
  paper.style.color = skin.ink || "#3a2b16"
  paper.style.fontFamily = skin.font || "Georgia, serif"
  const hotColor = skin.hot || "#58230a"

  // difficulty: flame radius^2 and coverage needed to finish a page
  const diff = { easy:   { r2: 4200, need: 0.75 },
                 normal: { r2: 2600, need: 0.85 },
                 hard:   { r2: 1100, need: 0.93 } }[(data && data.difficulty) || "normal"]
             || { r2: 2600, need: 0.85 }

  const pages = (data && data.pages && data.pages.length) ? data.pages : [(data && data.text) || ""]
  let pageIdx = 0, spans = [], revealed = 0, pageDone = false

  function loadPage(i) {
    paper.innerHTML = ""
    spans = []; revealed = 0; pageDone = false
    for (const ch of pages[i]) {
      const s = document.createElement("span")
      s.textContent = ch
      paper.appendChild(s)
      spans.push(s)
    }
    if (pageLabel) pageLabel.textContent = pages.length > 1 ? `page ${i + 1} / ${pages.length}` : ""
  }
  loadPage(0)

  wrap.onmousemove = (e) => {
    const wr = wrap.getBoundingClientRect()
    flame.style.display = "block"
    flame.style.left = (e.clientX - wr.left) + "px"
    flame.style.top = (e.clientY - wr.top) + "px"
    if (pageDone) return
    for (const s of spans) {
      if (s.classList.contains("hot")) continue
      const r = s.getBoundingClientRect()
      const dx = e.clientX - (r.left + r.width / 2)
      const dy = e.clientY - (r.top + r.height / 2)
      if (dx * dx + dy * dy < diff.r2) {
        s.classList.add("hot")
        s.style.color = hotColor
        s.style.textShadow = `0 0 6px ${hotColor}66`
        revealed++
      }
    }
    if (spans.length > 0 && revealed >= spans.length * diff.need) {
      pageDone = true
      for (const s of spans) { s.classList.add("hot"); s.style.color = hotColor }
      if (pageIdx + 1 < pages.length) {
        setTimeout(() => { pageIdx++; loadPage(pageIdx) }, 1200)   // char the page, turn to next
      } else {
        setTriggerValue("revealed", true)
      }
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
    pages = [str(p) for p in payload.get("pages") or [] if str(p).strip()]
    full_text = " / ".join(pages) if pages else payload.get("hidden_text", "")
    result = _burn_component(
        data={"text": payload.get("hidden_text", ""), "pages": pages, "skin": skin,
              "difficulty": payload.get("difficulty", "normal")},
        key=key, on_revealed_change=lambda: None)
    if result.revealed or st.button("Expose the whole surface to the heat", key=f"{key}_skip"):
        return f"The heat reveals hidden writing: \"{full_text}\""
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
    max_attempts = max(1, int(payload.get("attempts", 3)))          # host-configurable
    hint_after = int(payload.get("hint_after", 1))                  # show hint after N misses
    allow_giveup = payload.get("allow_giveup", True)

    if attempts >= hint_after and payload.get("hint"):
        st.caption(f"💡 Hint: {payload['hint']}")

    with st.form(f"{key}_form", clear_on_submit=True):
        guess = st.text_input("Your answer", key=f"{key}_guess")
        submitted = st.form_submit_button("Try it")
    if submitted and guess.strip():
        if guess.strip().lower() == solution:
            st.session_state.pop(attempts_key, None)
            return f"The player SOLVED the cipher — the answer was \"{payload.get('solution')}\""
        st.session_state[attempts_key] = attempts + 1
        if st.session_state[attempts_key] >= max_attempts:
            st.session_state.pop(attempts_key, None)
            return (f"The player FAILED to solve the cipher after {max_attempts} attempts "
                    f"(the answer was \"{payload.get('solution')}\" — do not reveal it unless the fiction allows)")
        st.error(f"Wrong. {max_attempts - st.session_state[attempts_key]} attempt(s) left.")
    if allow_giveup and st.button("Give up", key=f"{key}_giveup"):
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


# --- glyph sequence: activate the sigils in the right order ---

def render_glyph_sequence(payload: dict, key: str):
    sequence = [str(g) for g in payload.get("sequence") or []]
    decoys = [str(g) for g in payload.get("decoys") or []]
    if not sequence:
        return "(glyph_sequence had no sequence — skipped)"
    max_attempts = max(1, int(payload.get("attempts", 3)))

    st.markdown("### ✴️ Arcane glyphs await the correct order")
    if payload.get("clue"):
        st.caption(f"🧩 {payload['clue']}")

    shuffled_key, picked_key, attempts_key = f"{key}_glyphs", f"{key}_picked", f"{key}_gattempts"
    if shuffled_key not in st.session_state:
        pool = sequence + decoys
        random.shuffle(pool)
        st.session_state[shuffled_key] = pool
        st.session_state[picked_key] = []
        st.session_state[attempts_key] = 0
    picked = st.session_state[picked_key]

    st.markdown("**Activated:** " + (" → ".join(f"`{g}`" for g in picked) or "_none_")
                + f" ({len(picked)}/{len(sequence)})")
    cols = st.columns(min(4, max(2, len(st.session_state[shuffled_key]))))
    for i, glyph in enumerate(st.session_state[shuffled_key]):
        if cols[i % len(cols)].button(glyph, key=f"{key}_g{i}", disabled=glyph in picked):
            if glyph == sequence[len(picked)]:
                picked.append(glyph)
                if len(picked) == len(sequence):
                    for k in (shuffled_key, picked_key, attempts_key):
                        st.session_state.pop(k, None)
                    return (f"The player activated the glyphs in the CORRECT order "
                            f"({' -> '.join(sequence)}) — the ward opens")
                st.rerun()
            else:
                st.session_state[picked_key] = []
                st.session_state[attempts_key] += 1
                if st.session_state[attempts_key] >= max_attempts:
                    for k in (shuffled_key, picked_key, attempts_key):
                        st.session_state.pop(k, None)
                    return (f"The player FAILED the glyph sequence after {max_attempts} attempts — "
                            f"the ward flares and seals itself (correct order was "
                            f"{' -> '.join(sequence)}; do not reveal it)")
                st.rerun()
    left = max_attempts - st.session_state.get(attempts_key, 0)
    st.caption(f"A wrong glyph resets the sequence. {left} attempt(s) before the ward seals.")
    if st.button("Step back from the glyphs", key=f"{key}_gquit"):
        for k in (shuffled_key, picked_key, attempts_key):
            st.session_state.pop(k, None)
        return "The player stepped away from the glyphs without completing the sequence"
    return None


# --- dice duel: best-of-N gamble against an NPC ---

def render_dice_duel(payload: dict, key: str):
    opponent = payload.get("opponent", "the stranger")
    rounds = max(1, int(payload.get("rounds", 3)))
    st.markdown(f"### 🎲 Dice duel against **{opponent}**")
    if payload.get("stakes"):
        st.caption(f"💰 Stakes: {payload['stakes']}")

    log_key = f"{key}_duel"
    log = st.session_state.setdefault(log_key, [])   # [(you, them, outcome_str)]
    you = sum(1 for r in log if r[0] > r[1])
    them = sum(1 for r in log if r[1] > r[0])

    for i, (a, b, line) in enumerate(log, 1):
        st.markdown(f"- Round {i}: you **{a}** vs {opponent} **{b}** — {line}")

    need = rounds // 2 + 1
    if you >= need or them >= need or len(log) >= rounds:
        st.session_state.pop(log_key, None)
        if you == them:
            return f"The dice duel with {opponent} ended in a DRAW ({you}-{them})"
        return (f"The player {'WON' if you > them else 'LOST'} the dice duel against {opponent} "
                f"({you}-{them}). Stakes: {payload.get('stakes', 'as agreed')}")

    st.markdown(f"**Round {len(log) + 1} of {rounds}** — score {you}-{them}. Choose your play:")
    c1, c2 = st.columns(2)
    choice = None
    if c1.button("🔥 Bold (d10 — swing big)", key=f"{key}_bold", width="stretch"):
        choice = ("bold", random.randint(1, 10))
    if c2.button("🛡️ Steady (d6+2 — play safe)", key=f"{key}_steady", width="stretch"):
        choice = ("steady", random.randint(1, 6) + 2)
    if choice:
        their = random.randint(1, 10) if random.random() < 0.5 else random.randint(1, 6) + 2
        line = "you take the round" if choice[1] > their else \
               ("they take it" if their > choice[1] else "dead even — no point")
        log.append((choice[1], their, f"{choice[0]} play; {line}"))
        st.rerun()
    return None


# --- wire cut: one chance, choose the right line ---

_WIRE_COLORS = {"red": "#d9534f", "blue": "#4a7fd4", "green": "#4faf6b", "yellow": "#d4b74a",
                "black": "#555", "white": "#ddd", "purple": "#9a6bd4", "orange": "#d4854a"}


def render_wire_cut(payload: dict, key: str):
    wires = [str(w).lower() for w in payload.get("wires") or []]
    correct = str(payload.get("correct", "")).lower()
    if not wires or correct not in wires:
        return "(wire_cut had no valid wires — skipped)"
    st.markdown("### ✂️ One cut. Choose.")
    if payload.get("clue"):
        st.caption(f"🧩 {payload['clue']}")
    st.markdown(
        "<div style='display:flex;gap:6px;margin:6px 0 14px'>" +
        "".join(f"<div style='flex:1;height:10px;border-radius:5px;background:"
                f"{_WIRE_COLORS.get(w, '#888')}'></div>" for w in wires) +
        "</div>", unsafe_allow_html=True)
    cols = st.columns(len(wires))
    for col, w in zip(cols, wires):
        if col.button(f"✂️ {w}", key=f"{key}_wire_{w}", width="stretch"):
            if w == correct:
                return f"The player cut the {w} wire — CORRECT. The device goes quiet."
            return (f"The player cut the {w} wire — WRONG (the correct one was {correct}). "
                    f"Consequence: {payload.get('consequence', 'the mechanism triggers')}")
    if st.button("Back away without cutting", key=f"{key}_wire_quit"):
        return "The player backed away without cutting any wire"
    return None


# --- memory echo: watch the pattern flash, repeat it (Simon) ---

_ECHO_HTML = """
<div class="echo-board">
  <div class="echo-status" id="status">Watch…</div>
  <div class="echo-grid" id="grid"></div>
</div>
"""

_ECHO_CSS = """
.echo-board { text-align: center; padding: 8px 0; font-family: Georgia, serif; }
.echo-status { color: var(--st-text-color, #ccc); opacity: .75; margin-bottom: 10px; font-size: .9em; }
.echo-grid { display: flex; gap: 14px; justify-content: center; }
.sigil { width: 64px; height: 64px; border-radius: 12px; display: flex; align-items: center;
  justify-content: center; font-size: 1.8em; cursor: pointer; user-select: none;
  background: #1c1a24; border: 1px solid #4a3a5a; color: #8a7fa6;
  transition: all .15s ease; }
.sigil.lit { background: #3d2f5c; color: #e8d8ff; border-color: #a88fd4;
  box-shadow: 0 0 22px rgba(168,143,212,.6); transform: scale(1.12); }
.sigil.dead { opacity: .35; cursor: default; }
"""

_ECHO_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const grid = parentElement.querySelector("#grid")
  const status = parentElement.querySelector("#status")
  if (!grid || grid.dataset.built) return
  grid.dataset.built = "1"

  const SYMBOLS = ["🜏", "☿", "🜍", "🝓", "🜚", "⚸"]
  const length = Math.min(6, Math.max(3, (data && data.length) || 4))
  const maxAttempts = Math.max(1, (data && data.attempts) || 2)
  const cells = SYMBOLS.slice(0, 4)
  const seq = Array.from({length}, () => Math.floor(Math.random() * cells.length))

  const els = cells.map((sym) => {
    const d = document.createElement("div")
    d.className = "sigil"; d.textContent = sym
    grid.appendChild(d)
    return d
  })

  let accepting = false, pos = 0, attempts = 0
  function flash(i, ms) {
    els[i].classList.add("lit")
    setTimeout(() => els[i].classList.remove("lit"), ms)
  }
  function playback() {
    accepting = false; pos = 0
    status.textContent = "Watch…"
    seq.forEach((s, n) => setTimeout(() => flash(s, 420), 650 * (n + 1)))
    setTimeout(() => { accepting = true; status.textContent = "Repeat the sequence." },
               650 * (seq.length + 1))
  }
  els.forEach((el, i) => {
    el.onclick = () => {
      if (!accepting) return
      flash(i, 200)
      if (i === seq[pos]) {
        pos++
        if (pos >= seq.length) {
          accepting = false
          status.textContent = "The pattern answers."
          setTriggerValue("done", "success")
        }
      } else {
        attempts++
        if (attempts >= maxAttempts) {
          accepting = false
          els.forEach(e => e.classList.add("dead"))
          status.textContent = "The pattern fades, unanswered."
          setTriggerValue("done", "failure")
        } else {
          status.textContent = "Wrong — it begins again…"
          setTimeout(playback, 900)
        }
      }
    }
  })
  setTimeout(playback, 400)
}
"""

_echo_component = st.components.v2.component("memory_echo", html=_ECHO_HTML, css=_ECHO_CSS, js=_ECHO_JS)


def render_memory_echo(payload: dict, key: str):
    st.markdown(f"### ✨ {payload.get('context', 'A pattern flashes — remember it.')}")
    result = _echo_component(
        data={"length": int(payload.get("length", 4)), "attempts": int(payload.get("attempts", 2))},
        key=key, on_done_change=lambda: None)
    if result.done == "success":
        return "The player repeated the pattern PERFECTLY — the mechanism yields"
    if result.done == "failure":
        return "The player FAILED to repeat the pattern — the echo fades and the way stays shut"
    if st.button("Step away from the pattern", key=f"{key}_echo_quit"):
        return "The player stepped away without answering the pattern"
    return None


RENDERERS = {"burn_reveal": render_burn_reveal, "cipher": render_cipher, "seance": render_seance,
             "combination_lock": render_combination_lock, "tarot_draw": render_tarot_draw,
             "glyph_sequence": render_glyph_sequence, "dice_duel": render_dice_duel,
             "wire_cut": render_wire_cut, "memory_echo": render_memory_echo}

ICONS = {"burn_reveal": "🕯️", "cipher": "🔏", "seance": "☩",
         "combination_lock": "🔒", "tarot_draw": "🃏",
         "glyph_sequence": "✴️", "dice_duel": "🎲",
         "wire_cut": "✂️", "memory_echo": "✨"}


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
