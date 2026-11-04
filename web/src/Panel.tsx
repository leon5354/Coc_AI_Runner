// 狀態欄 / 物品欄: the character panel. One place to look at a character, their skills, what they
// carry, and everything the party has found.
import { useEffect, useMemo, useState } from "react"
import Markdown from "react-markdown"
import * as api from "./api"
import type { Character, Game } from "./api"
import type { Ctx } from "./App"
import { itemIcon } from "./art/itemIcon"
import { Portrait } from "./art/Portrait"

type Tab = "status" | "skills" | "items" | "journal"
const TABS: Record<Tab, string> = { status: "狀態 Status", skills: "技能 Skills", items: "物品 Items", journal: "手記 Journal" }
const CJK = /[㐀-鿿]/

export function Bar({ value, max, label, kind }: { value: number; max: number; label: string; kind: string }) {
  return (
    <div className={`bar ${kind}`}>
      <div style={{ width: `${(100 * Math.max(value, 0)) / Math.max(max, 1)}%` }} />
      <span>{label}</span>
    </div>
  )
}

function Status({ ctx, game, ch }: { ctx: Ctx; game: Game; ch: Character }) {
  const toForm = (c: Character) => ({ name: c.name, player_label: c.player_label, personality: c.personality, backstory: c.backstory })
  const [editing, setEditing] = useState(false)
  const [f, setF] = useState(toForm(ch))
  useEffect(() => { setF(toForm(ch)); setEditing(false) }, [ch.id])
  const set = (k: keyof ReturnType<typeof toForm>) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const patch = (body: object) => ctx.call(() => api.send<Game>(`/api/game/characters/${ch.id}`, body, "PATCH"))

  return (
    <div className="status-tab">
      <div className="status-head">
        <Portrait name={ch.name} about={`${ch.personality} ${ch.backstory}`} size={132}
          ratio={ch.stress / Math.max(ch.max_stress, 1)} down={ch.status !== "active"} />
        <div className="grow">
          <h2>{ch.name}</h2>
          <p className="muted">{ch.controller === "ai" ? "AI companion" : ch.player_label || "Player"}
            {ch.status !== "active" && <b className="danger"> · {ch.status.toUpperCase()}</b>}</p>
          <Bar kind="hp" value={ch.hp} max={ch.max_hp} label={`HP ${ch.hp} / ${ch.max_hp}`} />
          {game.has_stress && <Bar kind="mind" value={ch.stress} max={ch.max_stress} label={`${game.stress_name} ${ch.stress} / ${ch.max_stress}`} />}
          <label className="toggle">
            <input type="checkbox" checked={ch.controller === "ai"} onChange={(e) => patch({ controller: e.target.checked ? "ai" : "human" })} />
            Played by AI
          </label>
        </div>
      </div>
      {editing ? (
        <form onSubmit={(e) => { e.preventDefault(); patch({ ...f, name: f.name.trim() || ch.name }); setEditing(false) }}>
          <label>Name</label><input value={f.name} onChange={set("name")} />
          <label>Player label</label><input value={f.player_label} onChange={set("player_label")} />
          <label>Personality</label><textarea rows={3} value={f.personality} onChange={set("personality")} />
          <label>Background</label><textarea rows={6} value={f.backstory} onChange={set("backstory")} />
          <div className="row"><button type="submit" className="primary">Save</button><button type="button" onClick={() => setEditing(false)}>Cancel</button></div>
        </form>
      ) : <>
        {ch.personality && <><h4>Personality</h4><p>{ch.personality}</p></>}
        {ch.backstory && <><h4>Background</h4><p>{ch.backstory}</p></>}
        <button onClick={() => setEditing(true)}>Edit</button>
      </>}
      {ch.controller === "ai" && <details>
        <summary>🧠 What they privately think</summary>
        {ch.memory_summary ? <p>{ch.memory_summary}</p> : <p className="muted">Their memory forms as they live through more.</p>}
        <ul>{Object.entries(ch.relationships).map(([k, v]) => <li key={k}><b>{k}</b>: {v}</li>)}</ul>
        <ul>{ch.private_thoughts.slice(-6).reverse().map((t, i) => <li key={i}><i>{t}</i></li>)}</ul>
      </details>}
    </div>
  )
}

function Skills({ ctx, game, ch, close }: { ctx: Ctx; game: Game; ch: Character; close: () => void }) {
  const [q, setQ] = useState("")
  const dnd = game.state.rule_system === "dnd5e"
  const coc = game.state.rule_system === "coc7e"
  const rows = Object.entries(ch.skills).filter(([k]) => k.toLowerCase().includes(q.toLowerCase())).sort((a, b) => b[1] - a[1])
  return (
    <div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a skill…" />
      <p className="muted small">Click a skill to try it. The Keeper decides if it needs a roll.</p>
      <div className="skills">
        {rows.map(([name, v]) => (
          <button key={name} className="skill" onClick={() => {
            ctx.setDraft(CJK.test(name + ch.name) ? `我嘗試運用${name}：` : `I try to use ${name}: `)
            close()
          }}>
            <span className="grow">{name}</span>
            {coc && <i className="muted small">½ {v >> 1} · ⅕ {Math.floor(v / 5)}</i>}
            <b>{dnd ? (v >= 0 ? `+${v}` : v) : v}</b>
            {!dnd && <em style={{ width: `${Math.min(100, v)}%` }} />}
          </button>
        ))}
      </div>
    </div>
  )
}

function Items({ ctx, game, ch, close }: { ctx: Ctx; game: Game; ch: Character; close: () => void }) {
  const [pick, setPick] = useState<string | null>(null)
  const [looking, setLooking] = useState(false)
  const item = pick && ch.inventory.includes(pick) ? pick : null
  const others = game.state.characters.filter((c) => c.id !== ch.id)
  const slots = Math.max(12, Math.ceil((ch.inventory.length + 1) / 4) * 4)
  const Icon = item ? itemIcon(item) : null

  async function inspect() {
    if (!item) return
    setLooking(true)
    await ctx.call(async () => (await api.send<{ game: Game }>("/api/game/items/inspect", { character_id: ch.id, item })).game)
    setLooking(false)
  }

  return (
    <div className="items-tab">
      <div className="grid">
        {Array.from({ length: slots }, (_, i) => {
          const it = ch.inventory[i]
          if (!it) return <div key={i} className="slot empty" />
          const I = itemIcon(it)
          return (
            <button key={it} className={it === item ? "slot on" : "slot"} title={it} onClick={() => setPick(it)}>
              <I size={36} /><span>{it}</span>
            </button>
          )
        })}
      </div>
      <div className="item-detail">
        {item && Icon ? <>
          <Icon size={64} className="item-big" />
          <h3>{item}</h3>
          <p className="muted">{ch.item_notes[item] || (looking ? "Turning it over in your hands…" : "You haven't looked at it closely.")}</p>
          <div className="row">
            <button className="primary" onClick={() => { ctx.setDraft(CJK.test(item) ? `我使用${item}：` : `I use the ${item}: `); close() }}>Use</button>
            <button disabled={!!ch.item_notes[item] || looking || !!ctx.busy} onClick={inspect}>Inspect</button>
            <button onClick={() => { if (confirm(`Drop ${item}? It will be gone.`)) ctx.call(() => api.send("/api/game/items/drop", { character_id: ch.id, item })) }}>Drop</button>
          </div>
          {others.length > 0 && <div className="row">
            <span className="muted small">Give to</span>
            {others.map((o) => <button key={o.id} onClick={() => ctx.call(() => api.send("/api/game/items/give", { character_id: ch.id, to: o.id, item }))}>{o.name}</button>)}
          </div>}
        </> : <p className="muted">{ch.inventory.length ? "Click an item to look at it." : "Nothing carried."}</p>}
      </div>
    </div>
  )
}

function SceneMap({ game }: { game: Game }) {
  // lay scenes out by how many steps they are from the start
  const layout = useMemo(() => {
    const nodes = game.map
    const depth = new Map<string, number>([[nodes[0]?.id, 0]])
    const queue = nodes[0] ? [nodes[0]] : []
    while (queue.length) {
      const n = queue.shift()!
      for (const to of n.exits) {
        const next = nodes.find((x) => x.id === to)
        if (next && !depth.has(to)) { depth.set(to, depth.get(n.id)! + 1); queue.push(next) }
      }
    }
    const rows = new Map<number, string[]>()
    nodes.forEach((n) => { const d = depth.get(n.id) ?? 0; rows.set(d, [...(rows.get(d) ?? []), n.id]) })
    const pos = new Map<string, [number, number]>()
    rows.forEach((ids, d) => ids.forEach((id, i) => pos.set(id, [(100 * (i + 1)) / (ids.length + 1), 34 + d * 66])))
    return { pos, h: (Math.max(0, ...rows.keys()) + 1) * 66 + 10 }
  }, [game.map])

  return (
    <svg viewBox={`0 0 100 ${layout.h / 3.4}`} className="scene-map" style={{ aspectRatio: `340 / ${layout.h}` }}>
      {game.map.flatMap((n) => n.exits.filter((to) => layout.pos.has(to) && layout.pos.has(n.id)).map((to) => {
        const [x1, y1] = layout.pos.get(n.id)!, [x2, y2] = layout.pos.get(to)!
        return <line key={n.id + to} x1={x1} y1={y1 / 3.4} x2={x2} y2={y2 / 3.4} />
      }))}
      {game.map.filter((n) => layout.pos.has(n.id)).map((n) => {
        const [x, y] = layout.pos.get(n.id)!
        return (
          <g key={n.id} className={n.id === game.state.scene_id ? "here" : n.visited ? "seen" : "unknown"}>
            <circle cx={x} cy={y / 3.4} r="2.6" />
            <text x={x} y={y / 3.4 + 6.4}>{n.name}</text>
          </g>
        )
      })}
    </svg>
  )
}

function Journal({ game }: { game: Game }) {
  return (
    <div>
      <h4>Clues {game.clues.length} / {game.clues_total}</h4>
      {game.clues.length === 0 && <p className="muted">Nothing found yet.</p>}
      {game.clues.map((c) => (
        <details key={c.id}><summary>🔎 {c.name}</summary><p>{c.text}</p></details>
      ))}
      <h4>Places</h4>
      <SceneMap game={game} />
      {game.state.summary && <><h4>The story so far</h4><Markdown>{game.state.summary}</Markdown></>}
    </div>
  )
}

export default function Panel({ ctx, game, who, tab: first, onClose }: {
  ctx: Ctx; game: Game; who: string; tab?: Tab; onClose: () => void
}) {
  const [tab, setTab] = useState<Tab>(first ?? "status")
  const [id, setId] = useState(who)
  const chars = game.state.characters
  const ch = chars.find((c) => c.id === id) ?? chars[0]

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    addEventListener("keydown", esc)
    return () => removeEventListener("keydown", esc)
  }, [])

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <header>
          <div className="panel-party">
            {chars.map((c) => (
              <button key={c.id} className={c.id === ch.id ? "on" : ""} title={c.name} onClick={() => setId(c.id)}>
                <Portrait name={c.name} about={`${c.personality} ${c.backstory}`} size={42} ratio={c.stress / Math.max(c.max_stress, 1)} down={c.status !== "active"} />
              </button>
            ))}
          </div>
          <button onClick={onClose}>✕</button>
        </header>
        <nav className="tabs">
          {(Object.keys(TABS) as Tab[]).map((t) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{TABS[t]}</button>)}
        </nav>
        {tab === "status" && <Status ctx={ctx} game={game} ch={ch} />}
        {tab === "skills" && <Skills ctx={ctx} game={game} ch={ch} close={onClose} />}
        {tab === "items" && <Items ctx={ctx} game={game} ch={ch} close={onClose} />}
        {tab === "journal" && <Journal game={game} />}
      </div>
    </div>
  )
}
