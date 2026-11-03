import { useEffect, useState } from "react"
import * as api from "./api"
import type { DiceResult, Game, Meta, Payload } from "./api"
import Architect from "./Architect"
import { Backdrop } from "./Atmosphere"
import Play from "./Play"
import Sidebar from "./Sidebar"

export type Ctx = {
  meta: Meta
  game: Game | null
  busy: string                                   // label of the beat in flight, "" when idle
  /** Quick action that returns the new game view. */
  call: (fn: () => Promise<Game | null>) => Promise<void>
  /** Streamed turn: one beat per line. */
  turn: (path: string, body?: unknown) => Promise<void>
  refreshMeta: () => Promise<void>
}

export type FinishedMinigame = { payload: Payload; result: string }

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [game, setGame] = useState<Game | null>(null)
  const [busy, setBusy] = useState("")
  const [error, setError] = useState("")
  const [dice, setDice] = useState<(DiceResult & { key: number }) | null>(null)
  const [tab, setTab] = useState<"play" | "architect">("play")
  const [menuOpen, setMenuOpen] = useState(false)
  const [lastMinigame, setLastMinigame] = useState<FinishedMinigame | null>(null)

  const refreshMeta = () => api.get<Meta>("/api/meta").then(setMeta)
  useEffect(() => {
    refreshMeta().catch((e) => setError(`Can't reach the server: ${e.message}`))
    api.get<Game | null>("/api/game").then(setGame).catch(() => {})
  }, [])

  async function call(fn: () => Promise<Game | null>) {
    setError("")
    try { setGame(await fn()) } catch (e) { setError((e as Error).message) }
  }

  async function turn(path: string, body: unknown = {}) {
    setError("")
    setDice(null)
    setBusy("…")
    try {
      await api.stream(path, body, (line) => {
        if (line.dice) setDice({ ...line.dice, key: Date.now() })
        if (line.game) setGame(line.game)
        if (line.error) setError(line.error)
        setBusy(line.done ? "" : line.label || "…")
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy("")
    }
  }

  if (!meta) {
    return <div className="boot">{error || "Opening the case files…"}</div>
  }

  const ctx: Ctx = { meta, game, busy, call, turn, refreshMeta }
  const active = game && (game.state.characters.find((c) => c.id === game.state.active_character_id)
    ?? game.state.characters[0])
  const stress = active ? active.stress / Math.max(active.max_stress, 1) : 1

  return (
    <>
      <Backdrop mood={game?.mood ?? "night"} stress={stress} />
      <div className="layout">
        <button className="menu-btn" onClick={() => setMenuOpen(!menuOpen)}>☰</button>
        <aside className={menuOpen ? "sidebar open" : "sidebar"}>
          <Sidebar ctx={ctx} stress={stress} />
        </aside>
        <main>
          <nav className="tabs">
            <button className={tab === "play" ? "on" : ""} onClick={() => setTab("play")}>🎲 Play</button>
            <button className={tab === "architect" ? "on" : ""} onClick={() => setTab("architect")}>
              🏗️ Scenario Architect
            </button>
          </nav>
          {error && <div className="error" onClick={() => setError("")}>{error}</div>}
          {tab === "play"
            ? <Play ctx={ctx} dice={dice} lastMinigame={lastMinigame} onMinigameDone={setLastMinigame} />
            : <Architect ctx={ctx} onError={setError} />}
        </main>
      </div>
    </>
  )
}
