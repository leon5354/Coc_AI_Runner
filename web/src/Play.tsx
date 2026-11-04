// The game screen: story on the left, the scene's art on the right, party down the side.
import { useEffect, useRef, useState } from "react"
import Markdown from "react-markdown"
import * as api from "./api"
import type { Character, Game, Message } from "./api"
import type { Ctx, FinishedMinigame } from "./App"
import { Portrait } from "./art/Portrait"
import type { DieSpec } from "./dice/table"
import { FrozenMinigame, Minigame } from "./minigames"
import Panel, { Bar } from "./Panel"
import { brainName } from "./Title"

function Line({ m, chars }: { m: Message; chars: Character[] }) {
  const c = m.content
  if (m.role === "player" && c.startsWith("ROLL RESULT:")) return null   // legacy saves
  if (m.role === "dice") return <div className="msg dice"><span className="die-mark">🎲</span><b>{c}</b></div>
  if (m.role === "ooc") {
    return <div className="msg ooc"><div><div className="who">{m.name ?? "OOC"} · out of character</div><Markdown>{c}</Markdown></div></div>
  }
  if (m.role === "player" && c.startsWith("MINIGAME RESULT:")) {
    return <div className="msg minigame"><span className="die-mark">🧩</span><i>{c.slice("MINIGAME RESULT:".length).trim()}</i></div>
  }
  const ch = chars.find((x) => x.name === m.name)
  return (
    <div className={`msg ${m.role}`}>
      {ch && <Portrait name={ch.name} about={`${ch.personality} ${ch.backstory}`} size={38} ratio={ch.stress / Math.max(ch.max_stress, 1)} />}
      <div>{m.name && <div className="who">{m.name}</div>}<Markdown>{c}</Markdown></div>
    </div>
  )
}

function RollGate({ ctx, game }: { ctx: Ctx; game: Game }) {
  const pr = game.state.pending_roll!
  const who = game.state.characters.find((c) => c.id === pr.character_id)
  const [arg, setArg] = useState("")
  const mod = (pr.bonus ?? 0) - (pr.penalty ?? 0)
  return (
    <div className="gate">
      <div className="gate-head">
        <div className="grow">
          <h3>{who?.name} must roll <b>{pr.skill}</b></h3>
          <p className="muted">{game.roll_preview?.need} · {pr.difficulty}{mod > 0 ? " · bonus" : mod < 0 ? " · penalty" : ""} · about {game.roll_preview?.chance}%{pr.reason ? ` · ${pr.reason}` : ""}</p>
        </div>
        <button className="primary big" disabled={!!ctx.busy} onClick={ctx.rollPending}>🎲 Pick up the dice</button>
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (arg.trim()) ctx.turn("/api/game/negotiate", { text: arg.trim() }) }}>
        <input className="grow" value={arg} onChange={(e) => setArg(e.target.value)} disabled={!!ctx.busy}
          placeholder="…or argue for a different approach" />
        <button type="submit" disabled={!!ctx.busy || !arg.trim()}>Negotiate</button>
      </form>
    </div>
  )
}

const MODES = { act: "Act", talk: "Talk", ooc: "Ask the Keeper" } as const
type Mode = keyof typeof MODES

function Composer({ ctx, game }: { ctx: Ctx; game: Game }) {
  const st = game.state
  const humans = st.characters.filter((c) => c.controller === "human" && c.status === "active")
  const [mode, setMode] = useState<Mode>("act")
  const [acting, setActing] = useState("")
  const [research, setResearch] = useState({ open: false, q: "", web: false })
  const box = useRef<HTMLTextAreaElement>(null)
  const text = ctx.draft
  useEffect(() => { if (text) box.current?.focus() }, [text.length > 0])

  if (!humans.length) return <div className="warn-box">Nobody at the table can act. Undo the last turn, or switch a companion to a human player in their panel.</div>
  const who = humans.find((c) => c.id === acting) ?? humans.find((c) => c.id === st.active_character_id) ?? humans[0]

  async function submit() {
    const t = text.trim()
    if (!t || ctx.busy) return
    ctx.setDraft("")
    if (mode === "act") await ctx.turn("/api/game/act", { character_id: who.id, text: t })
    else if (mode === "talk") await ctx.turn("/api/game/talk", { character_id: who.id, text: t })
    else await ctx.call(() => api.send<Game>("/api/game/ooc", { question: t }))
  }

  const placeholder = { act: `What does ${who.name} do?`, talk: `What does ${who.name} say? No turn spent.`, ooc: "Ask anything: rules, a recap, your options…" }[mode]

  return (
    <div className="composer">
      {research.open && (
        <form className="row" onSubmit={(e) => {
          e.preventDefault()
          if (research.q.trim()) ctx.call(() => api.send<Game>("/api/game/research", { query: research.q.trim(), web: research.web }))
          setResearch({ open: false, q: "", web: false })
        }}>
          <input className="grow" autoFocus value={research.q} placeholder="Look something up in the archives…" onChange={(e) => setResearch({ ...research, q: e.target.value })} />
          <label className="toggle"><input type="checkbox" checked={research.web} onChange={(e) => setResearch({ ...research, web: e.target.checked })} />web</label>
          <button type="submit">Search</button>
        </form>
      )}
      <div className="row composer-modes">
        <div className="seg">
          {(Object.keys(MODES) as Mode[]).map((m) => <button key={m} className={m === mode ? "on" : ""} onClick={() => setMode(m)}>{MODES[m]}</button>)}
        </div>
        <button onClick={() => setResearch({ ...research, open: !research.open })}>📚 Archives</button>
        {humans.length > 1 && (
          <select value={who.id} onChange={(e) => setActing(e.target.value)} title="Acting as">
            {humans.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <textarea ref={box} className="grow" rows={2} value={text} placeholder={placeholder} disabled={!!ctx.busy}
          onChange={(e) => ctx.setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() } }} />
        <button type="submit" className="primary" disabled={!!ctx.busy || !text.trim()}>Send</button>
      </form>
    </div>
  )
}

const TRAY = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"] as const

function DiceTray({ ctx, close }: { ctx: Ctx; close: () => void }) {
  const [die, setDie] = useState<(typeof TRAY)[number]>("d6")
  const [n, setN] = useState(2)
  const [mod, setMod] = useState(0)
  const expr = `${n}${die}${mod ? (mod > 0 ? `+${mod}` : mod) : ""}`
  const preset: DieSpec[] = Array.from({ length: n }, () => (die === "d100" ? [{ die: "d100" as const }, { die: "d10" as const }] : [{ die }])).flat()
  return (
    <div className="tray" onClick={(e) => e.stopPropagation()}>
      <div className="seg">{TRAY.map((d) => <button key={d} className={d === die ? "on" : ""} onClick={() => setDie(d)}>{d}</button>)}</div>
      <div className="row">
        <span>How many</span>
        <button onClick={() => setN(Math.max(1, n - 1))}>−</button><b>{n}</b><button onClick={() => setN(Math.min(die === "d100" ? 2 : 6, n + 1))}>+</button>
        <span>Add</span>
        <button onClick={() => setMod(mod - 1)}>−</button><b>{mod}</b><button onClick={() => setMod(mod + 1)}>+</button>
      </div>
      <button className="primary" disabled={!!ctx.busy} onClick={() => { close(); ctx.freeRoll(expr, preset) }}>Roll {expr}</button>
    </div>
  )
}

function PartyRail({ game, open }: { game: Game; open: (id: string, tab?: "items") => void }) {
  return (
    <aside className="rail">
      {game.state.characters.map((c) => (
        <button key={c.id} className={c.id === game.state.active_character_id ? "rail-c on" : "rail-c"} onClick={() => open(c.id)} title={`${c.name}: status and items`}>
          <Portrait name={c.name} about={`${c.personality} ${c.backstory}`} size={62} ratio={c.stress / Math.max(c.max_stress, 1)} down={c.status !== "active"} />
          <span className="rail-name">{c.name}</span>
          <Bar kind="hp" value={c.hp} max={c.max_hp} label={`${c.hp}`} />
          {game.has_stress && <Bar kind="mind" value={c.stress} max={c.max_stress} label={`${c.stress}`} />}
          {c.status !== "active" && <em className="danger">{c.status}</em>}
        </button>
      ))}
    </aside>
  )
}

function Ending({ ctx, game }: { ctx: Ctx; game: Game }) {
  const st = game.state
  const e = st.ending!
  return (
    <div className="ending">
      <h1>{game.title}</h1>
      <h2>{e.outcome}</h2>
      {e.description && <p>{e.description}</p>}
      <div className="end-stats">
        <div><b>{st.turn_count}</b><span>turns</span></div>
        <div><b>{st.stats.rolls ?? 0}</b><span>rolls</span></div>
        <div><b>{st.stats.crits ?? 0}</b><span>criticals</span></div>
        <div><b>{st.stats.fumbles ?? 0}</b><span>fumbles</span></div>
        <div><b>{game.clues.length}/{game.clues_total}</b><span>clues</span></div>
        <div><b>{st.visited_scenes.length}</b><span>places</span></div>
      </div>
      <p className="muted">{st.characters.map((c) => `${c.name}: ${c.status}`).join(" · ")}</p>
      <div className="row">
        <a className="button" href="/api/game/export" download={`${game.title}.md`}>📜 Keep the story</a>
        <button disabled={!game.can_undo} onClick={() => ctx.call(() => api.send("/api/game/undo"))}>↩ Undo the ending</button>
        <button className="primary" onClick={() => ctx.go("title")}>Back to the title</button>
      </div>
    </div>
  )
}

export default function Play({ ctx, lastMinigame, onMinigameDone }: {
  ctx: Ctx; lastMinigame: FinishedMinigame | null; onMinigameDone: (m: FinishedMinigame) => void
}) {
  const { game } = ctx
  const end = useRef<HTMLDivElement>(null)
  const [panel, setPanel] = useState<{ who: string; tab?: "items" | "journal" } | null>(null)
  const [tray, setTray] = useState(false)
  const [card, setCard] = useState(game?.scene_name ?? "")
  const count = game ? game.state.messages_archive.length + game.state.messages.length : 0
  // braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as cleanup
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }) }, [count, ctx.busy, ctx.partial.length >> 6])
  useEffect(() => {
    if (!game) return
    setCard(game.scene_name)
    const t = setTimeout(() => setCard(""), 3200)
    return () => clearTimeout(t)
  }, [game?.state.scene_id])

  if (!game) return <div className="info"><button onClick={() => ctx.go("title")}>Pick a campaign</button></div>
  const st = game.state
  const chars = st.characters
  const lead = chars.find((c) => c.id === st.active_character_id) ?? chars[0]

  return (
    <div className="game">
      <header className="topbar">
        <button onClick={() => ctx.go("title")} title="Back to the title">☰</button>
        <div className="grow topbar-title"><b>{game.title}</b><span>{game.scene_name} · turn {st.turn_count}</span></div>
        <div className="topbar-tools">
          <button disabled={!game.can_undo || !!ctx.busy} title="Rewind the last turn" onClick={() => ctx.call(() => api.send("/api/game/undo"))}>↩</button>
          <button onClick={() => setTray(!tray)} title="Roll any dice">🎲</button>
          <button onClick={() => setPanel({ who: lead.id, tab: "items" })} title="狀態欄 / 物品欄 — status and items">🎒</button>
          <button onClick={() => setPanel({ who: lead.id, tab: "journal" })} title="Clues and places">📖</button>
          <button onClick={ctx.openSettings} title={`Settings. Keeper: ${brainName(ctx)}`}>⚙</button>
        </div>
        {tray && <DiceTray ctx={ctx} close={() => setTray(false)} />}
      </header>

      <div className="play-body">
        <PartyRail game={game} open={(who, tab) => setPanel({ who, tab })} />
        <section className="story">
          <div className="transcript">
            {[...st.messages_archive, ...st.messages].map((m, i) => <Line key={i} m={m} chars={chars} />)}
            {ctx.partial && <div className="msg keeper"><div><Markdown>{ctx.partial}</Markdown></div></div>}
            {ctx.busy && !ctx.partial && <div className="thinking"><span className="spinner" /> {ctx.busy}</div>}
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
            ) : !st.ending && <>
              {lastMinigame && <details className="last-mg"><summary>🧩 Last minigame</summary><FrozenMinigame {...lastMinigame} /></details>}
              <Composer ctx={ctx} game={game} />
            </>}
        </section>
      </div>

      {card && <div className="scene-card" key={card}><span>{card}</span></div>}
      {st.ending && !ctx.busy && <Ending ctx={ctx} game={game} />}
      {panel && <Panel ctx={ctx} game={game} who={panel.who} tab={panel.tab} onClose={() => setPanel(null)} />}
    </div>
  )
}
