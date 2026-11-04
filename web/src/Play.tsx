// The game screen: story on the left, the scene's art on the right, party down the side.
import { useEffect, useMemo, useRef, useState } from "react"
import { t } from "./i18n"
import Markdown from "react-markdown"
import * as api from "./api"
import type { Character, Game, Message } from "./api"
import type { Ctx, FinishedMinigame } from "./App"
import { AmbienceButton } from "./Atmosphere"
import { readSky, sceneWeather } from "./art/kits"
import { mindOf, Portrait } from "./art/Portrait"
import type { DieSpec } from "./dice/table"
import { FrozenMinigame, Minigame } from "./minigames"
import Panel, { Bar } from "./Panel"
import { brainName } from "./Title"

const named = (text: string, name: string) => text.includes(name) || text.includes(name.split(" ").pop() ?? name)

function Line({ m, chars, npcs }: { m: Message; chars: Character[]; npcs: Game["npcs"] }) {
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
      {ch && <Portrait name={ch.name} about={`${ch.personality} ${ch.backstory}`} size={38} ratio={mindOf(ch)} />}
      <div>
        {m.name && <div className="who">{m.name}</div>}
        <Markdown>{c}</Markdown>
        {m.role === "keeper" && npcs.filter((n) => named(c, n.name)).map((n) => (
          <span className="npc-chip" key={n.name} title={n.role}><Portrait name={n.name} about={n.role} size={26} />{n.name}</span>
        ))}
      </div>
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
          <h3>{who?.name} {t("must roll")} <b>{pr.skill}</b></h3>
          <p className="muted">{game.roll_preview?.need} · {t(pr.difficulty)}{mod > 0 ? ` · ${t("bonus")}` : mod < 0 ? ` · ${t("penalty")}` : ""} · {t("about")} {game.roll_preview?.chance}%{pr.reason ? ` · ${pr.reason}` : ""}</p>
        </div>
        <button className="primary big" disabled={!!ctx.busy} onClick={() => ctx.rollPending()}>{t("🎲 Pick up the dice")}</button>
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (arg.trim()) ctx.turn("/api/game/negotiate", { text: arg.trim() }) }}>
        <input className="grow" value={arg} onChange={(e) => setArg(e.target.value)} disabled={!!ctx.busy}
          placeholder={t("…or argue for a different approach")} />
        <button type="submit" disabled={!!ctx.busy || !arg.trim()}>{t("Negotiate")}</button>
      </form>
    </div>
  )
}

function PushGate({ ctx, game }: { ctx: Ctx; game: Game }) {
  const p = game.state.pending_push!
  const who = game.state.characters.find((c) => c.id === p.character_id)
  const [why, setWhy] = useState("")
  const afford = who && p.luck_cost <= who.luck
  return (
    <div className="gate">
      <div className="gate-head">
        <div className="grow">
          <h3>{who?.name} {t("failed")} <b>{p.skill}</b></h3>
          <p className="muted">{t("Rolled {roll}, needed {need} or less. You have {luck} Luck.", { roll: p.roll, need: p.need, luck: who?.luck ?? 0 })}</p>
        </div>
        <button disabled={!!ctx.busy} onClick={() => ctx.turn("/api/game/accept")}>{t("Accept it")}</button>
        <button disabled={!!ctx.busy || !afford} title={t("Spend Luck to turn this into a bare success")}
          onClick={() => ctx.turn("/api/game/luck")}>🍀 {t("Spend {n} Luck", { n: p.luck_cost })}</button>
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (why.trim()) ctx.rollPending(why.trim()) }}>
        <input className="grow" value={why} onChange={(e) => setWhy(e.target.value)} disabled={!!ctx.busy}
          placeholder={t("Or push it: how do you try harder? Failing again will cost you.")} />
        <button type="submit" className="primary" disabled={!!ctx.busy || !why.trim()}>{t("Push the roll")}</button>
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

  if (!humans.length) return <div className="warn-box">{t("Nobody at the table can act. Undo the last turn, or switch a companion to a human player in their panel.")}</div>
  const who = humans.find((c) => c.id === acting) ?? humans.find((c) => c.id === st.active_character_id) ?? humans[0]

  async function submit() {
    const t = text.trim()
    if (!t || ctx.busy) return
    ctx.setDraft("")
    if (mode === "act") await ctx.turn("/api/game/act", { character_id: who.id, text: t })
    else if (mode === "talk") await ctx.turn("/api/game/talk", { character_id: who.id, text: t })
    else await ctx.call(() => api.send<Game>("/api/game/ooc", { question: t }), "The Keeper leans back…")
  }

  const placeholder = { act: t("What does {name} do?", { name: who.name }), talk: t("What does {name} say? No turn spent.", { name: who.name }),
    ooc: t("Ask anything: rules, a recap, your options…") }[mode]

  return (
    <div className="composer">
      {research.open && (
        <form className="row" onSubmit={(e) => {
          e.preventDefault()
          if (research.q.trim()) ctx.call(() => api.send<Game>("/api/game/research", { query: research.q.trim(), web: research.web }), "Dust rises from old shelves…")
          setResearch({ open: false, q: "", web: false })
        }}>
          <input className="grow" autoFocus value={research.q} placeholder={t("Look something up in the archives…")} onChange={(e) => setResearch({ ...research, q: e.target.value })} />
          <label className="toggle"><input type="checkbox" checked={research.web} onChange={(e) => setResearch({ ...research, web: e.target.checked })} />{t("web")}</label>
          <button type="submit">{t("Search")}</button>
        </form>
      )}
      <div className="row composer-modes">
        <div className="seg">
          {(Object.keys(MODES) as Mode[]).map((m) => <button key={m} className={m === mode ? "on" : ""} onClick={() => setMode(m)}>{t(MODES[m])}</button>)}
        </div>
        <button onClick={() => setResearch({ ...research, open: !research.open })}>{t("📚 Archives")}</button>
        {humans.length > 1 && (
          <select value={who.id} onChange={(e) => setActing(e.target.value)} title={t("Acting as")}>
            {humans.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <textarea ref={box} className="grow" rows={2} value={text} placeholder={placeholder} disabled={!!ctx.busy}
          onChange={(e) => ctx.setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() } }} />
        <button type="submit" className="primary" disabled={!!ctx.busy || !text.trim()}>{t("Send")}</button>
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
        <span>{t("How many")}</span>
        <button onClick={() => setN(Math.max(1, n - 1))}>−</button><b>{n}</b><button onClick={() => setN(Math.min(die === "d100" ? 2 : 6, n + 1))}>+</button>
        <span>{t("Modifier")}</span>
        <button onClick={() => setMod(mod - 1)}>−</button><b>{mod}</b><button onClick={() => setMod(mod + 1)}>+</button>
      </div>
      <button className="primary" disabled={!!ctx.busy} onClick={() => { close(); ctx.freeRoll(expr, preset) }}>{t("Roll {expr}", { expr })}</button>
    </div>
  )
}

function PartyRail({ game, open }: { game: Game; open: (id: string, tab?: "items") => void }) {
  return (
    <aside className="rail">
      {game.state.characters.map((c) => (
        <button key={c.id} className={c.id === game.state.active_character_id ? "rail-c on" : "rail-c"} onClick={() => open(c.id)} title={c.name}>
          <Portrait name={c.name} about={`${c.personality} ${c.backstory}`} size={62} ratio={mindOf(c)} down={c.status !== "active"} />
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
        <div><b>{st.turn_count}</b><span>{t("turns")}</span></div>
        <div><b>{st.stats.rolls ?? 0}</b><span>{t("rolls")}</span></div>
        <div><b>{st.stats.crits ?? 0}</b><span>{t("criticals")}</span></div>
        <div><b>{st.stats.fumbles ?? 0}</b><span>{t("fumbles")}</span></div>
        <div><b>{game.clues.length}/{game.clues_total}</b><span>{t("clues")}</span></div>
        <div><b>{st.visited_scenes.length}</b><span>{t("places")}</span></div>
      </div>
      <p className="muted">{st.characters.map((c) => `${c.name}: ${c.status}`).join(" · ")}</p>
      <div className="row">
        <a className="button" href="/api/game/export" download={`${game.title}.md`}>{t("📜 Keep the story")}</a>
        <button disabled={!game.can_undo} onClick={() => ctx.call(() => api.send("/api/game/undo"))}>{t("↩ Undo the ending")}</button>
        <button className="primary" onClick={() => ctx.go("title")}>{t("Back to the title")}</button>
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

  const told = game?.state.messages.findLast((m) => m.role === "keeper")?.content ?? ""
  const base = useMemo(() => (game ? sceneWeather(game.scene_name, game.scene_text, game.scene_art) : "fog"), [game?.state.scene_id])
  const fx = readSky(told).weather || base

  if (!game) return <div className="info"><button onClick={() => ctx.go("title")}>{t("Pick a campaign")}</button></div>
  const st = game.state
  const chars = st.characters
  const lead = chars.find((c) => c.id === st.active_character_id) ?? chars[0]

  return (
    <div className="game">
      <header className="topbar">
        <button onClick={() => ctx.go("title")} title={t("Back to the title")}>☰</button>
        <div className="grow topbar-title"><b>{game.title}</b><span>{game.scene_name} · {t("turn {n}", { n: st.turn_count })}</span></div>
        <div className="topbar-tools">
          <AmbienceButton mood={game.mood} stress={lead.stress / Math.max(lead.max_stress, 1)} diceNonce={st.dice_log.length} fx={fx} />
          <button disabled={!game.can_undo || !!ctx.busy} title={t("Rewind the last turn")} onClick={() => ctx.call(() => api.send("/api/game/undo"))}>↩</button>
          <button onClick={() => setTray(!tray)} title={t("Roll any dice")}>🎲</button>
          <button onClick={() => setPanel({ who: lead.id, tab: "items" })} title={t("狀態欄 / 物品欄 — status and items")}>🎒</button>
          <button onClick={() => setPanel({ who: lead.id, tab: "journal" })} title={t("Clues and places")}>📖</button>
          <button onClick={ctx.openSettings} title={`Settings. Keeper: ${brainName(ctx)}`}>⚙</button>
        </div>
        {tray && <DiceTray ctx={ctx} close={() => setTray(false)} />}
      </header>

      <div className="play-body">
        <PartyRail game={game} open={(who, tab) => setPanel({ who, tab })} />
        <section className="story">
          <div className="transcript">
            {[...st.messages_archive, ...st.messages].map((m, i) => <Line key={i} m={m} chars={chars} npcs={game.npcs} />)}
            {ctx.partial && <div className="msg keeper"><div><Markdown>{ctx.partial}</Markdown></div></div>}
            {ctx.busy && !ctx.partial && <div className="thinking"><span className="spinner" /> {ctx.busy}</div>}
            <div ref={end} />
          </div>
          {st.pending_push ? <PushGate ctx={ctx} game={game} />
            : st.pending_roll ? <RollGate ctx={ctx} game={game} />
            : st.pending_minigame ? (
              <div className="gate">
                <Minigame key={st.minigame_count} payload={st.pending_minigame} disabled={!!ctx.busy}
                  onResult={(result) => {
                    onMinigameDone({ payload: st.pending_minigame!, result })
                    ctx.turn("/api/game/minigame", { result })
                  }} />
              </div>
            ) : !st.ending && <>
              {lastMinigame && <details className="last-mg"><summary>{t("🧩 Last minigame")}</summary><FrozenMinigame {...lastMinigame} /></details>}
              <Composer ctx={ctx} game={game} />
            </>}
        </section>
      </div>

      {card && !ctx.recap && <div className="scene-card" key={card}><span>{card}</span></div>}
      {ctx.recap && (
        <div className="modal-back" onClick={() => ctx.setRecap(false)}>
          <div className="modal recap">
            <h2>{t("The story so far")}</h2>
            <p className="muted">{game.scene_name} · {t("turn {n}", { n: st.turn_count })}</p>
            {st.summary ? <Markdown>{st.summary}</Markdown>
              : st.messages.filter((m) => m.role === "keeper").slice(-2).map((m, i) => <Markdown key={i}>{m.content}</Markdown>)}
            <button className="primary" onClick={() => ctx.setRecap(false)}>{t("Continue")}</button>
          </div>
        </div>
      )}
      {st.ending && !ctx.busy && <Ending ctx={ctx} game={game} />}
      {panel && <Panel ctx={ctx} game={game} who={panel.who} tab={panel.tab} onClose={() => setPanel(null)} />}
    </div>
  )
}
