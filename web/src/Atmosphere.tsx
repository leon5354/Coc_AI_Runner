// Sanity vignette and procedural WebAudio ambience (no audio assets).
import { useEffect, useRef, useState } from "react"

const DRONES: Record<string, number> = { daylight: 110, dusk: 82, night: 55, unearthly: 66 }

/** A red vignette that closes in as sanity drops. */
export function Vignette({ stress }: { stress: number }) {
  const v = Math.min(0.55, Math.max(0, 1 - stress) * 0.55)
  return <div className="vignette" style={{
    background: `radial-gradient(ellipse at center, transparent 55%, rgba(110,0,0,${v.toFixed(2)}) 100%)`,
  }} />
}

type Engine = ReturnType<typeof makeEngine>

function makeEngine() {
  const ctx = new AudioContext()
  const master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination)

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
  let hb: number | undefined
  function thump(t: number) {
    const o = ctx.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(52, t)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0, t)
    g.gain.linearRampToValueAtTime(0.5, t + 0.02)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.22)
    o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.3)
  }
  function setHeartbeat(bpm: number) {
    clearInterval(hb); hb = undefined
    if (bpm) hb = window.setInterval(() => { const t = ctx.currentTime; thump(t); thump(t + 0.28) }, 60000 / bpm)
  }

  // dice clatter: short bandpassed noise bursts
  function clatter() {
    for (let i = 0; i < 6; i++) {
      const t = ctx.currentTime + i * (0.05 + Math.random() * 0.06)
      const buf = ctx.createBuffer(1, ctx.sampleRate * 0.04, ctx.sampleRate)
      const d = buf.getChannelData(0)
      for (let j = 0; j < d.length; j++) d[j] = (Math.random() * 2 - 1) * (1 - j / d.length)
      const src = ctx.createBufferSource(); src.buffer = buf
      const bp = ctx.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1800 + Math.random() * 2500
      const g = ctx.createGain(); g.gain.value = 0.25
      src.connect(bp); bp.connect(g); g.connect(master); src.start(t)
    }
  }
  return { ctx, master, o1, o2, filt, setHeartbeat, clatter }
}

/** Click once to enable (browsers only allow audio after a user gesture). */
export function AmbienceButton({ mood, stress, diceNonce }: { mood: string; stress: number; diceNonce: number }) {
  const eng = useRef<Engine | null>(null)
  const lastDice = useRef(diceNonce)
  const [on, setOn] = useState(false)

  useEffect(() => {
    const e = eng.current
    if (!e || !on) return
    const t = e.ctx.currentTime + 2
    const drone = DRONES[mood] ?? 55
    e.o1.frequency.linearRampToValueAtTime(drone, t)
    e.o2.frequency.linearRampToValueAtTime(drone * 1.012, t)
    e.filt.frequency.linearRampToValueAtTime(120 + stress * 120, t)
    e.setHeartbeat(stress < 0.6 ? Math.round(45 + (0.6 - stress) * 120) : 0)
    if (diceNonce > lastDice.current) e.clatter()
    lastDice.current = diceNonce
  }, [mood, stress, diceNonce, on])

  useEffect(() => () => { eng.current?.setHeartbeat(0); eng.current?.ctx.close() }, [])

  function toggle() {
    if (!eng.current) eng.current = makeEngine()
    const e = eng.current
    if (!on) {
      e.ctx.resume()
      e.master.gain.linearRampToValueAtTime(1, e.ctx.currentTime + 1.5)
      lastDice.current = diceNonce
    } else {
      e.master.gain.linearRampToValueAtTime(0, e.ctx.currentTime + 0.5)
      e.setHeartbeat(0)
    }
    setOn(!on)
  }

  return <button className={on ? "amb on" : "amb"} onClick={toggle}>{on ? "🔊 Sound on" : "🔇 Turn on sound"}</button>
}
