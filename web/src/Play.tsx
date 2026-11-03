import { useEffect, useRef, useState } from "react"
import Markdown from "react-markdown"
import * as api from "./api"
import type { DiceResult, Game, Message } from "./api"
import type { Ctx, FinishedMinigame } from "./App"
import { DiceRoll } from "./Dice"
import { FrozenMinigame, Minigame } from "./minigames"

const AVATARS: Record<string, string> = { keeper: "🐙", player: "🕵️", companion: "🎭", researcher: "📚" }

function Line({ m }: { m: Message }) {
  const c = m.content
  if (m.role === "player" && c.startsWith("ROLL RESULT:")) return null   // legacy saves
  if (m.role === "dice") return <div className="msg dice"><span className="av">🎲</span><b>{c}</b></div>
  if (m.role === "ooc") {
    return (
      <div className="msg ooc"><span className="av">💭</span>
        <div><div className="who">{m.name ?? "OOC"} · out of character</div><Markdown>{c}</Markdown></div>
      </div>
    )
  }
  if (m.role === "player" && c.startsWith("MINIGAME RESULT:")) {
    return (
      <div className="msg minigame"><span className="av">🧩</span>
        <div><div className="who">Minigame</div><i>{c.slice("MINIGAME RESULT:".length).trim()}</i></div>
      </div>
    )
  }
  return (
    <div className={`msg ${m.role}`}><span className="av">{AVATARS[m.role] ?? "❔"}</span>
      <div>{m.name && <div className="who">{m.name}</div>}<Markdown>{c}</Markdown></div>
    </div>
  )
}

function RollGate({ ctx, game }: { ctx: Ctx; game: Game }) {
  const pr = game.state.pending_roll!
  const who = game.state.characters.find((c) => c.id === pr.character_id)
  const [arg, setArg] = useState("")
  return (
    <div className="gate">
      <h3>🎲 {who?.name} must roll <b>{pr.skill}</b> <span className="muted">(target {pr.target}, {pr.difficulty})</span></h3>
      {pr.reason && <p className="muted">{pr.reason}</p>}
      <div className="row">
        <button className="primary big" disabled={!!ctx.busy} onClick={() => ctx.turn("/api/game/roll")}>
          Roll the dice
        </button>
        <form className="grow row" onSubmit={(e) => {
          e.preventDefault()
          if (arg.trim()) ctx.turn("/api/game/negotiate", { text: arg.trim() })
        }}>
          <input className="grow" value={arg} onChange={(e) => setArg(e.target.value)} disabled={!!ctx.busy}
            placeholder="…or argue for a different approach (e.g. Fast Talk — he's distracted)" />
          <button type="submit" disabled={!!ctx.busy}>Negotiate</button>
        </form>
      </div>
    </div>
  )
}

const MODES = { act: "🎬 Act", talk: "💬 Talk", ooc: "❓ Ask the Keeper" } as const
type Mode = keyof typeof MODES

function Composer({ ctx, game }: { ctx: Ctx; game: Game }) {
  const st = game.state
  const humans = st.characters.filter((c) => c.controller === "human")
  const [mode, setMode] = useState<Mode>("act")
  const [text, setText] = useState("")
  const [acting, setActing] = useState("")
  const [research, setResearch] = useState({ q: "", web: false })
  if (!humans.length) return <div className="warn-box">No human-controlled characters — flip one to human in the sidebar.</div>
  const who = humans.find((c) => c.id === acting)
    ?? humans.find((c) => c.id === st.active_character_id) ?? humans[0]

  async function submit() {
    const t = text.trim()
    if (!t || ctx.busy) return
    setText("")
    if (mode === "act") await ctx.turn("/api/game/act", { character_id: who.id, text: t })
    else if (mode === "talk") await ctx.turn("/api/game/talk", { character_id: who.id, text: t })
    else await ctx.call(() => api.send<Game>("/api/game/ooc", { question: t }))
  }

  const placeholder = {
    act: `What does ${who.name} do?`,
    talk: `What does ${who.name} say? (no turn spent)`,
    ooc: "Ask the Keeper anything — rules, a recap, your options…",
  }[mode]

  return (
    <div className="composer">
      <details>
        <summary>📚 Consult the Archives</summary>
        <form className="row" onSubmit={(e) => {
          e.preventDefault()
          if (research.q.trim()) {
            ctx.call(() => api.send<Game>("/api/game/research", { query: research.q.trim(), web: research.web }))
            setResearch({ q: "", web: false })
          }
        }}>
          <input className="grow" value={research.q} placeholder="Elias Corwin, 1835, grave robbery…"
            onChange={(e) => setResearch({ ...research, q: e.target.value })} />
          <label className="toggle"><input type="checkbox" checked={research.web}
            onChange={(e) => setResearch({ ...research, web: e.target.checked })} />web</label>
          <button type="submit">Research</button>
        </form>
      </details>
      <div className="row">
        <div className="seg" title="Act: commit to an action. Talk: speak without spending a turn. Ask the Keeper: out of character.">
          {(Object.keys(MODES) as Mode[]).map((m) => (
            <button key={m} className={m === mode ? "on" : ""} onClick={() => setMode(m)}>{MODES[m]}</button>
          ))}
        </div>
        {humans.length > 1 && (
          <select value={who.id} onChange={(e) => setActing(e.target.value)} title="Acting as">
            {humans.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <textarea className="grow" rows={2} value={text} placeholder={placeholder} disabled={!!ctx.busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() } }} />
        <button type="submit" className="primary" disabled={!!ctx.busy || !text.trim()}>Send</button>
      </form>
    </div>
  )
}

export default function Play({ ctx, dice, lastMinigame, onMinigameDone }: {
  ctx: Ctx
  dice: (DiceResult & { key: number }) | null
  lastMinigame: FinishedMinigame | null
  onMinigameDone: (m: FinishedMinigame) => void
}) {
  const { game } = ctx
  const end = useRef<HTMLDivElement>(null)
  const count = game ? game.state.messages_archive.length + game.state.messages.length : 0
  // braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as cleanup
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }) }, [count, ctx.busy, dice?.key])

  if (!game) return <div className="info">Pick a campaign in the sidebar and press Start.</div>
  const st = game.state
  const active = st.characters.find((c) => c.id === st.active_character_id) ?? st.characters[0]
  const ratio = active.stress / Math.max(active.max_stress, 1)

  return (
    <div className="play">
      <header>
        <h2>{game.title}</h2>
        <div className="pills">
          <span className="pill violet">📍 {game.scene_name}</span>
          <span className="pill blue">⏱ turn {st.turn_count}</span>
          <span className="pill">🎭 {active.name}'s move</span>
          {st.pending_roll && <span className="pill red">🎲 roll pending</span>}
          {st.pending_minigame && <span className="pill orange">🧩 minigame</span>}
          {st.god_mode && <span className="pill green">😇 god mode</span>}
          {game.has_stress && ratio < 0.4 &&
            <span className="pill red">🧠 {active.stress}/{active.max_stress} — fraying</span>}
        </div>
      </header>

      {st.summary && <details className="summary"><summary>📖 The story so far</summary><Markdown>{st.summary}</Markdown></details>}

      <div className="transcript">
        {[...st.messages_archive, ...st.messages].map((m, i) => <Line key={i} m={m} />)}
        {dice && <DiceRoll key={dice.key} roll={dice.roll} tier={dice.tier} detail={dice.detail} spec={dice.spec} />}
        {ctx.busy && <div className="thinking"><span className="spinner" /> {ctx.busy}</div>}
        <div ref={end} />
      </div>

      {st.pending_roll ? <RollGate ctx={ctx} game={game} />
        : st.pending_minigame ? (
          <div className="gate">
            <Minigame key={st.minigame_count} payload={st.pending_minigame} disabled={!!ctx.busy}
              onResult={(result) => {
                onMinigameDone({ payload: st.pending_minigame!, result })
                ctx.turn("/api/game/minigame", { result })
              }} />
          </div>
        ) : <>
          {lastMinigame && <details><summary>🧩 Last minigame result</summary><FrozenMinigame {...lastMinigame} /></details>}
          <Composer ctx={ctx} game={game} />
        </>}
    </div>
  )
}
