import { lazy, Suspense, useEffect, useRef, useState } from "react"
import * as api from "./api"
import type { Game, Meta, Payload, PendingRoll, RollEvent, TurnLine } from "./api"
import Architect from "./Architect"
import { SceneArt } from "./art/SceneArt"
import { Vignette } from "./Atmosphere"
import { pickLang } from "./i18n"
import type { TableProps } from "./dice/DiceTable"
import type { DieSpec } from "./dice/table"
import Play from "./Play"
import Settings from "./Settings"
import Title from "./Title"

const DiceTable = lazy(() => import("./dice/DiceTable"))

export type FinishedMinigame = { payload: Payload; result: string }
type Screen = "title" | "play" | "architect"

export type Ctx = {
  meta: Meta
  game: Game | null
  busy: string                                   // label of the beat in flight, "" when idle
  partial: string                                // the Keeper's words so far, while they arrive
  /** Quick action that returns the new game view. */
  call: (fn: () => Promise<Game | null>, label?: string) => Promise<void>
  /** Streamed turn: one beat per line. */
  turn: (path: string, body?: unknown) => Promise<void>
  refreshMeta: () => Promise<void>
  setError: (e: string) => void
  draft: string
  setDraft: (s: string) => void
  recap: boolean
  setRecap: (v: boolean) => void
  go: (s: Screen) => void
  openSettings: () => void
  /** Open the dice table for the pending roll, or for pushing a failed one (with the player's reason). */
  rollPending: (pushWhy?: string) => void
  /** Open the dice table for loose dice. */
  freeRoll: (expr: string, preset: DieSpec[]) => void
}

/** What changed between two views, in words, for the little pop-ups. */
function changes(a: Game | null, b: Game | null) {
  if (!a || !b || a.campaign !== b.campaign) return []
  const out: { text: string; kind: string }[] = []
  for (const ch of b.state.characters) {
    const old = a.state.characters.find((c) => c.id === ch.id)
    if (!old) continue
    if (ch.hp < old.hp) out.push({ text: `${ch.name} −${old.hp - ch.hp} HP`, kind: "bad" })
    if (ch.hp > old.hp) out.push({ text: `${ch.name} +${ch.hp - old.hp} HP`, kind: "good" })
    if (ch.stress < old.stress) out.push({ text: `${ch.name} −${old.stress - ch.stress} ${b.stress_name}`, kind: "bad" })
    if (ch.status !== old.status) out.push({ text: `${ch.name}: ${ch.status}`, kind: "bad" })
    for (const it of ch.inventory) if (!old.inventory.includes(it)) out.push({ text: `＋ ${it}`, kind: "good" })
    for (const it of old.inventory) if (!ch.inventory.includes(it)) out.push({ text: `－ ${it}`, kind: "bad" })
  }
  for (const c of b.clues) if (!a.clues.some((x) => x.id === c.id)) out.push({ text: `🔎 Clue: ${c.name}`, kind: "good" })
  return out
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [game, setGameRaw] = useState<Game | null>(null)
  const [busy, setBusy] = useState("")
  const [partial, setPartial] = useState("")
  const [error, setError] = useState("")
  const [screen, setScreen] = useState<Screen>("title")
  const [settings, setSettings] = useState(false)
  const [draft, setDraft] = useState("")
  const [recap, setRecap] = useState(false)
  const [lastMinigame, setLastMinigame] = useState<FinishedMinigame | null>(null)
  const [table, setTable] = useState<(TableProps & { id: number }) | null>(null)
  const [toasts, setToasts] = useState<{ id: number; text: string; kind: string }[]>([])
  const gameRef = useRef<Game | null>(null)
  const throwWaiter = useRef<((ev: RollEvent) => void) | null>(null)
  const landed = useRef<(() => void) | null>(null)

  function setGame(g: Game | null) {
    const news = changes(gameRef.current, g).map((t, i) => ({ ...t, id: Date.now() + i + Math.random() }))
    gameRef.current = g
    setGameRaw(g)
    if (news.length) {
      setToasts((t) => [...t, ...news])
      setTimeout(() => setToasts((t) => t.filter((x) => !news.some((n) => n.id === x.id))), 4200)
    }
  }

  const refreshMeta = () => api.get<Meta>("/api/meta").then(setMeta)
  useEffect(() => {
    refreshMeta().catch((e) => setError(`Can't reach the server: ${e.message}`))
    api.get<Game | null>("/api/game").then((g) => { if (g) { setGame(g); setScreen("play") } }).catch(() => {})
  }, [])

  async function call(fn: () => Promise<Game | null>, label = "") {
    setError("")
    if (label) setBusy(label)
    try { setGame(await fn()) } catch (e) { setError((e as Error).message) } finally { if (label) setBusy("") }
  }

  /** Show one roll on the table and wait for it to land. */
  function showDice(ev: RollEvent) {
    return new Promise<void>((done) => {
      landed.current = done
      if (throwWaiter.current) {        // the player already has the dice in hand
        throwWaiter.current(ev)
        throwWaiter.current = null
        return
      }
      const who = ev.who ? `${ev.who} — ` : ""
      setTable({
        id: Date.now(), auto: true, title: `${who}${ev.label}`, preset: ev.dice as DieSpec[],
        onThrow: () => Promise.resolve(ev), onDone: closeTable,
      })
    })
  }

  function closeTable() {
    setTable(null)
    landed.current?.()
    landed.current = null
  }

  async function handle(line: TurnLine) {
    if (line.partial !== undefined) { setPartial(line.partial); return }
    setPartial("")
    const events = line.dice ?? []
    for (const ev of events.filter((e) => e.kind !== "stress")) await showDice(ev)  // dice land first
    if (line.game) setGame(line.game)
    for (const ev of events.filter((e) => e.kind === "stress")) await showDice(ev)  // sanity after the horror is read
    if (line.error) setError(line.error)
    setBusy(line.done ? "" : line.label || "…")
  }

  async function turn(path: string, body: unknown = {}) {
    setError("")
    setBusy("…")
    let queue = Promise.resolve()
    try {
      await api.stream(path, body, (line: TurnLine) => { queue = queue.then(() => handle(line)) })
      await queue
    } catch (e) {
      setError((e as Error).message)
      throwWaiter.current = null
      closeTable()
    } finally {
      setBusy("")
    }
  }

  function presetDice(g: Game, pr: PendingRoll): DieSpec[] {
    const net = Math.abs((pr.bonus ?? 0) - (pr.penalty ?? 0))
    if (g.dice_spec.kind === "d100_two_d10") {
      const tens = g.state.rule_system === "coc7e" ? 1 + net : 1
      return [...Array.from({ length: tens }, () => ({ die: "d100" as const })), { die: "d10" }]
    }
    return Array.from({ length: 1 + net }, () => ({ die: "d20" as const }))
  }

  function rollPending(pushWhy?: string) {
    const g = gameRef.current
    const pr = g && (pushWhy ? g.state.pending_push : g.state.pending_roll)
    if (!g || !pr) return
    const who = g.state.characters.find((c) => c.id === pr.character_id)
    const extra = (pr.bonus ?? 0) > (pr.penalty ?? 0) ? " · bonus" : (pr.penalty ?? 0) > (pr.bonus ?? 0) ? " · penalty" : ""
    setTable({
      id: Date.now(), title: `${who?.name} — ${pr.skill}${pushWhy ? " (pushed)" : ""}`,
      subtitle: pushWhy ? "Fail this and something terrible happens"
        : `${g.roll_preview?.need} (${pr.difficulty})${extra} · about ${g.roll_preview?.chance}% chance`,
      preset: presetDice(g, pr),
      onThrow: () => new Promise<RollEvent>((resolve) => {
        throwWaiter.current = resolve
        if (pushWhy) turn("/api/game/push", { text: pushWhy })
        else turn("/api/game/roll")
      }),
      onDone: closeTable,
      onCancel: () => setTable(null),
    })
  }

  function freeRoll(expr: string, preset: DieSpec[]) {
    setTable({
      id: Date.now(), title: expr, preset, onDone: closeTable, onCancel: () => setTable(null),
      onThrow: async () => {
        const r = await api.send<{ dice: RollEvent; game: Game }>("/api/game/free_roll", { expr })
        setGame(r.game)
        return r.dice
      },
    })
  }

  if (!meta) return <div className="boot">{error || "Opening the case files…"}</div>

  pickLang(game?.state.language, screen === "title" ? undefined : game?.title)
  const ctx: Ctx = {
    meta, game, busy, partial, call, turn, refreshMeta, setError, draft, setDraft, recap, setRecap, go: setScreen,
    openSettings: () => setSettings(true), rollPending, freeRoll,
  }
  const active = game && (game.state.characters.find((c) => c.id === game.state.active_character_id)
    ?? game.state.characters[0])
  const stress = active && game?.has_stress ? active.stress / Math.max(active.max_stress, 1) : 1

  return (
    <>
      {screen === "play" && game && (
        <SceneArt key={game.state.scene_id} name={game.scene_name} text={game.scene_text} art={game.scene_art} mood={game.mood}
          story={game.state.messages.findLast((m) => m.role === "keeper")?.content} />
      )}
      {screen === "play" && <Vignette stress={stress} />}
      {screen === "title" && <Title ctx={ctx} />}
      {screen === "play" && <Play ctx={ctx} lastMinigame={lastMinigame} onMinigameDone={setLastMinigame} />}
      {screen === "architect" && <Architect ctx={ctx} onError={setError} />}
      {settings && <Settings ctx={ctx} onClose={() => setSettings(false)} />}
      {error && <div className="error floating" onClick={() => setError("")}>{error}</div>}
      <div className="toasts">{toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}</div>
      {table && <Suspense fallback={null}><DiceTable key={table.id} {...table} /></Suspense>}
    </>
  )
}
