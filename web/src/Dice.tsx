// CSS 3D dice (ported from interface/dice.py). Cosmetic only: the server already rolled.
// ponytail: stylized d10 bipyramid for every system; real per-die 3D physics is Phase 2.
import { Fragment, useEffect, useState } from "react"
import type { DiceResult } from "./api"

export const TIER_COLORS: Record<string, string> = {
  "Critical Success": "#ffd700", "Extreme Success": "#2ecc71", "Hard Success": "#1abc9c",
  "Regular Success": "#aaaaaa", "Success": "#2ecc71", "Failure": "#e74c3c", "Fumble": "#8b0000",
}

function facesFor(roll: number, kind: string) {
  if (kind === "d100_two_d10") {
    const tens = roll === 100 ? 0 : Math.floor((roll % 100) / 10)
    const units = roll === 100 ? 0 : roll % 10
    return [{ final: `${tens}0`, pad: 2 }, { final: String(units), pad: 1 }]
  }
  return [{ final: String(roll), pad: 1 }]
}

export function DiceRoll({ roll, tier, detail, spec }: DiceResult) {
  const faces = facesFor(roll, spec.kind)
  const color = TIER_COLORS[tier] ?? "#aaaaaa"
  const [shown, setShown] = useState(faces.map((f) => f.final))
  const [settled, setSettled] = useState(false)

  useEffect(() => {
    const spin = setInterval(() => setShown(faces.map((f) =>
      String(Math.floor(Math.random() * 10) * (f.pad > 1 ? 10 : 1)).padStart(f.pad, "0"))), 80)
    const settle = setTimeout(() => { clearInterval(spin); setShown(faces.map((f) => f.final)); setSettled(true) }, 1600)
    return () => { clearInterval(spin); clearTimeout(settle) }
  }, [])

  return (
    <div className="dice-stage">
      <div className="dice">
        {faces.map((_, n) => (
          <div className="die-scene" key={n}>
            <div className={settled ? "solid settling" : "solid"}>
              {[0, 1, 2, 3, 4].map((i) => (
                <Fragment key={i}>
                  <div className="face up" style={{ transform: `rotateY(${i * 72}deg) translateZ(16px) rotateX(28deg)` }} />
                  <div className="face down" style={{ transform: `rotateY(${i * 72 + 36}deg) translateZ(16px) rotateX(152deg)` }} />
                </Fragment>
              ))}
            </div>
            <div className="badge" style={settled ? { textShadow: `0 0 14px ${color}`, boxShadow: `0 0 22px ${color}55` } : {}}>
              {shown[n]}
            </div>
          </div>
        ))}
      </div>
      <div className="banner" style={{ opacity: settled ? 1 : 0, color, textShadow: `0 0 8px ${color}` }}>{detail}</div>
    </div>
  )
}
