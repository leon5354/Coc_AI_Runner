"""Atmosphere layer: scene-mood backgrounds, sanity vignette, procedural WebAudio ambience.

Sound is synthesized in the browser (drone + heartbeat + dice clatter) — no audio assets.
Real BGM: drop .mp3/.ogg/.wav files into data/audio/ and pick them in the sidebar.
"""
from pathlib import Path

import streamlit as st

AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"

# Scene moods — campaign scenes may declare `mood:`; otherwise we escalate by scene position.
MOODS = {
    "daylight":  {"bg": "linear-gradient(180deg,#1c1e26 0%,#232630 100%)", "drone": 110},
    "dusk":      {"bg": "linear-gradient(180deg,#161226 0%,#251a33 100%)", "drone": 82},
    "night":     {"bg": "linear-gradient(180deg,#0b0e16 0%,#121826 100%)", "drone": 55},
    "unearthly": {"bg": "linear-gradient(180deg,#0c140f 0%,#1a2418 100%)", "drone": 66},
}
_ESCALATION = ["daylight", "dusk", "night", "unearthly"]


def scene_mood(campaign, scene_id: str) -> str:
    scene = campaign.scene(scene_id) or {}
    if scene.get("mood") in MOODS:
        return scene["mood"]
    ids = [s["id"] for s in campaign.scenes]
    idx = ids.index(scene_id) if scene_id in ids else 0
    return _ESCALATION[min(len(_ESCALATION) - 1,
                           idx * len(_ESCALATION) // max(len(ids), 1))]


def inject_scene_style(mood: str, stress_ratio: float):
    """Background gradient per mood + a red vignette that closes in as sanity drops."""
    m = MOODS.get(mood, MOODS["night"])
    vig = min(0.55, max(0.0, 1.0 - stress_ratio) * 0.55)
    css = (f'<style>[data-testid="stApp"] {{ background: {m["bg"]} fixed !important; }} '
           f'[data-testid="stHeader"] {{ background: transparent !important; }}</style>')
    overlay = (f'<div style="position:fixed;inset:0;pointer-events:none;z-index:1;'
               f'background:radial-gradient(ellipse at center, transparent 55%, '
               f'rgba(110,0,0,{vig:.2f}) 100%);"></div>')
    st.markdown(css + overlay, unsafe_allow_html=True)


# --- procedural ambience: drone + heartbeat + dice clatter (WebAudio, no assets) ---

_AMB_HTML = """
<button id="amb" class="amb-btn">🔇 enable sound</button>
"""

_AMB_CSS = """
.amb-btn { width: 100%; padding: 6px 10px; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--st-border-color, #444);
  background: var(--st-secondary-background-color, #1c1e26);
  color: var(--st-text-color, #ddd); font-size: 0.9em; }
.amb-btn.on { border-color: #7fae8a; color: #a8d8b0; }
"""

_AMB_JS = """
const stores = new WeakMap()

function makeEngine() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)()
  const master = ctx.createGain(); master.gain.value = 0.0; master.connect(ctx.destination)

  // drone: two detuned saws through a dark lowpass, slowly breathing
  const filt = ctx.createBiquadFilter(); filt.type = "lowpass"; filt.frequency.value = 160; filt.Q.value = 4
  const dGain = ctx.createGain(); dGain.gain.value = 0.05
  filt.connect(dGain); dGain.connect(master)
  const o1 = ctx.createOscillator(); o1.type = "sawtooth"; o1.frequency.value = 55; o1.connect(filt); o1.start()
  const o2 = ctx.createOscillator(); o2.type = "sawtooth"; o2.frequency.value = 55.7; o2.connect(filt); o2.start()
  const lfo = ctx.createOscillator(); lfo.frequency.value = 0.07
  const lfoG = ctx.createGain(); lfoG.gain.value = 0.02
  lfo.connect(lfoG); lfoG.connect(dGain.gain); lfo.start()

  // heartbeat: two low thumps, interval set by stress
  let hbTimer = null
  function thump(t) {
    const o = ctx.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(52, t)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0, t)
    g.gain.linearRampToValueAtTime(0.5, t + 0.02)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.22)
    o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.3)
  }
  function setHeartbeat(bpm) {
    if (hbTimer) { clearInterval(hbTimer); hbTimer = null }
    if (!bpm) return
    hbTimer = setInterval(() => {
      const t = ctx.currentTime
      thump(t); thump(t + 0.28)
    }, 60000 / bpm)
  }

  // dice clatter: short bandpassed noise bursts
  function clatter() {
    for (let i = 0; i < 6; i++) {
      const t = ctx.currentTime + i * (0.05 + Math.random() * 0.06)
      const len = 0.04
      const buf = ctx.createBuffer(1, ctx.sampleRate * len, ctx.sampleRate)
      const d = buf.getChannelData(0)
      for (let j = 0; j < d.length; j++) d[j] = (Math.random() * 2 - 1) * (1 - j / d.length)
      const src = ctx.createBufferSource(); src.buffer = buf
      const bp = ctx.createBiquadFilter(); bp.type = "bandpass"
      bp.frequency.value = 1800 + Math.random() * 2500
      const g = ctx.createGain(); g.gain.value = 0.25
      src.connect(bp); bp.connect(g); g.connect(master); src.start(t)
    }
  }

  return { ctx, master, o1, o2, filt, setHeartbeat, clatter, lastDice: -1, on: false }
}

export default function (component) {
  const { data, parentElement } = component
  const btn = parentElement.querySelector("#amb")
  if (!btn) return
  let eng = stores.get(parentElement)

  function apply() {
    if (!eng || !eng.on) return
    const drone = (data && data.drone) || 55
    const stress = (data && data.stress) ?? 1.0
    eng.o1.frequency.linearRampToValueAtTime(drone, eng.ctx.currentTime + 2)
    eng.o2.frequency.linearRampToValueAtTime(drone * 1.012, eng.ctx.currentTime + 2)
    eng.filt.frequency.linearRampToValueAtTime(120 + stress * 120, eng.ctx.currentTime + 2)
    eng.setHeartbeat(stress < 0.6 ? Math.round(45 + (0.6 - stress) * 120) : 0)
    const nonce = (data && data.dice_nonce) || 0
    if (eng.lastDice >= 0 && nonce > eng.lastDice) eng.clatter()
    eng.lastDice = nonce
  }

  btn.onclick = () => {
    if (!eng) { eng = makeEngine(); stores.set(parentElement, eng) }
    eng.on = !eng.on
    if (eng.on) {
      eng.ctx.resume()
      eng.master.gain.linearRampToValueAtTime(1.0, eng.ctx.currentTime + 1.5)
      btn.textContent = "🔊 sound on"; btn.classList.add("on")
      eng.lastDice = (data && data.dice_nonce) || 0
      apply()
    } else {
      eng.master.gain.linearRampToValueAtTime(0.0, eng.ctx.currentTime + 0.5)
      eng.setHeartbeat(0)
      btn.textContent = "🔇 enable sound"; btn.classList.remove("on")
    }
  }

  if (eng && eng.on) { btn.textContent = "🔊 sound on"; btn.classList.add("on") }
  apply()
}
"""

_ambience = st.components.v2.component("ambience", html=_AMB_HTML, css=_AMB_CSS, js=_AMB_JS)


def render_ambience(mood: str, stress_ratio: float, dice_nonce: int):
    """One persistent widget in the sidebar; click once to enable audio (browser gesture rule)."""
    m = MOODS.get(mood, MOODS["night"])
    try:
        _ambience(data={"drone": m["drone"], "stress": round(stress_ratio, 2),
                        "dice_nonce": dice_nonce}, key="ambience_audio")
    except Exception:
        pass  # ponytail: sound is garnish — never break the game for it


def render_bgm_picker():
    """Optional real music: any audio files the user drops into data/audio/."""
    if not AUDIO_DIR.exists():
        return
    files = sorted(p for p in AUDIO_DIR.iterdir() if p.suffix.lower() in (".mp3", ".ogg", ".wav"))
    if not files:
        return
    with st.expander("🎵 Background music"):
        names = ["(off)"] + [p.name for p in files]
        pick = st.selectbox("Track", names, label_visibility="collapsed")
        if pick != "(off)":
            st.audio(str(AUDIO_DIR / pick), loop=True, autoplay=True)
