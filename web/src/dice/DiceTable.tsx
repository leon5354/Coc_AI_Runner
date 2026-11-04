// Full-screen dice moment: grab the dice, flick them, watch them land on the server's number.
import { useEffect, useRef, useState } from "react"
import type { RollEvent } from "../api"
import { DiceScene, unlockAudio, type DieSpec } from "./table"

export const TIER_COLORS: Record<string, string> = {
  "Critical Success": "#ffd700", "Extreme Success": "#4be08a", "Hard Success": "#35d6b8",
  "Regular Success": "#c8d0da", "Success": "#4be08a", "Failure": "#e8604f", "Fumble": "#ff2a2a",
}

const prefs = () => { try { return localStorage.getItem("dice.fast") === "1" } catch { return false } }

export type TableProps = {
  title: string
  subtitle?: string
  preset: DieSpec[]                 // dice lying on the table before the throw
  auto?: boolean                    // nobody throws by hand: AI companion and sanity rolls
  onThrow: () => Promise<RollEvent> // the server's result, or a ready one for auto rolls
  onDone: () => void
  onCancel?: () => void             // walk away before throwing
}

function resultName(ev: RollEvent) {
  if (ev.kind === "free") return ""
  if (ev.kind === "stress") return ev.success ? "Held firm" : "Shaken"
  return ev.tier
}

export default function DiceTable({ title, subtitle, preset, auto, onThrow, onDone, onCancel }: TableProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const scene = useRef<DiceScene | null>(null)
  const thrown = useRef(false)
  const trail = useRef<{ x: number; y: number; t: number }[]>([])
  const [phase, setPhase] = useState<"ready" | "held" | "rolling" | "result">("ready")
  const [result, setResult] = useState<RollEvent | null>(null)
  const closeTimer = useRef(0)

  async function go(swipe?: { vx: number; vz: number }) {
    if (thrown.current) return
    thrown.current = true
    setPhase("rolling")
    let ev: RollEvent
    try { ev = await onThrow() } catch { onDone(); return }
    const s = scene.current
    if (s) {
      const same = ev.dice.length === s.dice.length && ev.dice.every((d, i) => d.die === s.dice[i].spec.die)
      if (!same) s.setDice(ev.dice as DieSpec[])
      s.dice.forEach((d, i) => { d.spec = ev.dice[i] as DieSpec })
      await s.throwDice(ev.dice.map((d) => d.value), swipe)
      s.settled = true
      s.celebrate(TIER_COLORS[ev.kind === "stress" ? (ev.success ? "Success" : "Failure") : ev.tier] ?? "#c9a96e",
                  ev.dice.map((d) => d.kept))
    }
    setResult(ev)
    setPhase("result")
    closeTimer.current = window.setTimeout(onDone, auto ? 1700 : 2800)
  }

  useEffect(() => {
    if (!prefs()) {
      try {
        scene.current = new DiceScene(canvas.current!)
        ;(window as unknown as { __dice: DiceScene }).__dice = scene.current   // for the browser tests
        scene.current.setDice(preset)
      } catch { scene.current = null }   // no WebGL: the result still shows, just without dice
    }
    if (auto || !scene.current) { if (auto) go() }
    return () => { clearTimeout(closeTimer.current); scene.current?.dispose() }
  }, [])

  const ndc = (e: React.PointerEvent) => {
    const r = canvas.current!.getBoundingClientRect()
    return { x: ((e.clientX - r.left) / r.width) * 2 - 1, y: -(((e.clientY - r.top) / r.height) * 2 - 1) }
  }

  function down(e: React.PointerEvent) {
    if (phase === "result") { clearTimeout(closeTimer.current); onDone(); return }
    if (auto || thrown.current || !scene.current) return
    unlockAudio()
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
    const p = ndc(e)
    scene.current.grab(p.x, p.y)
    trail.current = [{ x: e.clientX, y: e.clientY, t: performance.now() }]
    setPhase("held")
  }

  function move(e: React.PointerEvent) {
    if (phase !== "held") return
    const p = ndc(e)
    scene.current?.grab(p.x, p.y)
    trail.current.push({ x: e.clientX, y: e.clientY, t: performance.now() })
    if (trail.current.length > 12) trail.current.shift()
  }

  function up(e: React.PointerEvent) {
    if (phase !== "held") return
    const now = performance.now()
    const recent = trail.current.filter((p) => now - p.t < 130)
    const first = recent[0] ?? { x: e.clientX, y: e.clientY, t: now - 100 }
    const dt = Math.max((now - first.t) / 1000, 0.02)
    const b = scene.current!.bounds
    const k = (b.w * 2) / canvas.current!.clientWidth    // screen pixels to table units
    go({ vx: ((e.clientX - first.x) / dt) * k, vz: ((e.clientY - first.y) / dt) * k })
  }

  const ev = result
  const color = ev ? TIER_COLORS[ev.kind === "stress" ? (ev.success ? "Success" : "Failure") : ev.tier] ?? "#ecd28a" : "#ecd28a"

  return (
    <div className={`dice-table ${ev?.tier === "Fumble" ? "fumble" : ""} ${ev?.tier === "Critical Success" ? "crit" : ""}`}
      onPointerDown={down} onPointerMove={move} onPointerUp={up}>
      <canvas ref={canvas} />
      <div className="dt-title">
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {ev && (
        <div className="dt-result" style={{ color }}>
          <div className="dt-number">{ev.roll}</div>
          <div className="dt-tier" style={{ textShadow: `0 0 24px ${color}` }}>{resultName(ev)}</div>
          <p>{ev.detail}</p>
        </div>
      )}
      <div className="dt-foot" onPointerDown={(e) => e.stopPropagation()}>
        {!auto && phase === "ready" && <>
          <span>Press and hold to grab the dice, then flick and let go</span>
          <button className="primary" onClick={() => { unlockAudio(); go() }}>Just throw</button>
          {onCancel && <button onClick={onCancel}>Back</button>}
        </>}
        {phase === "held" && <span>Let go to throw!</span>}
        {phase === "result" && <span>Click to continue</span>}
      </div>
    </div>
  )
}
