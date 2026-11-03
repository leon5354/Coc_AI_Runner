import { useEffect, useState } from "react"
import * as api from "./api"
import type { Character, Game } from "./api"
import type { Ctx } from "./App"
import { AmbienceButton } from "./Atmosphere"

const CUSTOM = "custom..."
const SAME = "(same as keeper)"

function Seg<T extends string>({ options, value, onChange, labels }: {
  options: T[]; value: T; onChange: (v: T) => void; labels?: Record<string, string>
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o} className={o === value ? "on" : ""} onClick={() => o !== value && onChange(o)}>
          {labels?.[o] ?? o}
        </button>
      ))}
    </div>
  )
}

function Bar({ value, max, label, kind }: { value: number; max: number; label: string; kind: string }) {
  return (
    <div className={`bar ${kind}`}>
      <div style={{ width: `${(100 * Math.max(value, 0)) / Math.max(max, 1)}%` }} />
      <span>{label}</span>
    </div>
  )
}

function LLMSettings({ ctx }: { ctx: Ctx }) {
  const { meta } = ctx
  const [prov, setProv] = useState(meta.llm.provider)
  const [pick, setPick] = useState(meta.main_models.includes(meta.llm.model) ? meta.llm.model : CUSTOM)
  const [custom, setCustom] = useState(meta.llm.model)
  const cur = meta.llm.util_model || SAME
  const [upick, setUpick] = useState([SAME, ...meta.util_models].includes(cur) ? cur : CUSTOM)
  const [ucustom, setUcustom] = useState(meta.llm.util_model)

  async function apply() {
    const model = pick === CUSTOM ? custom : pick
    const util = upick === SAME ? "" : upick === CUSTOM ? ucustom : upick
    await ctx.call(async () => {
      await api.send("/api/llm", { provider: prov, model, util_model: util })
      await ctx.refreshMeta()
      return ctx.game
    })
  }

  return (
    <details>
      <summary>🧠 LLM settings</summary>
      <label>Provider</label>
      <select value={prov} onChange={(e) => setProv(e.target.value)}>
        {meta.providers.map((p) => <option key={p}>{p}</option>)}
      </select>
      <label>Keeper model</label>
      <select value={pick} onChange={(e) => setPick(e.target.value)}>
        {[...meta.main_models, CUSTOM].map((m) => <option key={m}>{m}</option>)}
      </select>
      {pick === CUSTOM && <input value={custom} onChange={(e) => setCustom(e.target.value)} />}
      <label>Utility model (summaries & lore — cheap)</label>
      <select value={upick} onChange={(e) => setUpick(e.target.value)}>
        {[SAME, ...meta.util_models, CUSTOM].map((m) => <option key={m}>{m}</option>)}
      </select>
      {upick === CUSTOM && <input value={ucustom} onChange={(e) => setUcustom(e.target.value)} />}
      <button onClick={apply}>Apply</button>
    </details>
  )
}

function CampaignPicker({ ctx }: { ctx: Ctx }) {
  const { meta, game } = ctx
  const [file, setFile] = useState(game ? `${game.campaign}.yaml` : meta.campaigns[0]?.file ?? "")
  useEffect(() => { if (game) setFile(`${game.campaign}.yaml`) }, [game?.campaign])
  if (!meta.campaigns.length) return <div className="error">No valid campaigns in data/campaigns/</div>
  const chosen = meta.campaigns.find((c) => c.file === file)

  async function start(restart: boolean) {
    if (restart && chosen?.has_save &&
        !confirm(`Restart "${chosen.name}"? This deletes its save.`)) return
    await ctx.call(() => api.send<Game>("/api/game/start", { file, restart }))
    await ctx.refreshMeta()
  }

  return (
    <>
      <label>Campaign</label>
      <select value={file} onChange={(e) => setFile(e.target.value)}>
        {meta.campaigns.map((c) => <option key={c.file} value={c.file}>{c.name}</option>)}
      </select>
      <div className="row">
        <button className="primary" disabled={!!ctx.busy} onClick={() => start(false)}>
          ▶ {chosen?.has_save ? "Resume" : "Start"}
        </button>
        <button disabled={!!ctx.busy} onClick={() => start(true)}>🔄 Restart</button>
      </div>
    </>
  )
}

function PartyMember({ ctx, ch }: { ctx: Ctx; ch: Character }) {
  return (
    <div className="member">
      <div>
        <b>{ch.name}</b>
        {ch.status !== "active" && <span className="danger"> — {ch.status.toUpperCase()}</span>}
        {ch.player_label && <i className="muted"> · {ch.player_label}</i>}
      </div>
      <Bar kind="hp" value={ch.hp} max={ch.max_hp} label={`HP ${ch.hp}/${ch.max_hp}`} />
      {ch.max_stress > 1 &&
        <Bar kind="mind" value={ch.stress} max={ch.max_stress} label={`Mind ${ch.stress}/${ch.max_stress}`} />}
      <label className="toggle">
        <input type="checkbox" checked={ch.controller === "ai"}
          onChange={(e) => ctx.call(() => api.send(`/api/game/characters/${ch.id}`,
            { controller: e.target.checked ? "ai" : "human" }, "PATCH"))} />
        AI-controlled
      </label>
    </div>
  )
}

function InnerLife({ chars }: { chars: Character[] }) {
  const [who, setWho] = useState(chars[0].id)
  const ch = chars.find((c) => c.id === who) ?? chars[0]
  return (
    <details>
      <summary>🧠 Inner life</summary>
      <select value={ch.id} onChange={(e) => setWho(e.target.value)}>
        {chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <p className="muted">What they privately remember — this is what they act from.</p>
      {ch.memory_summary ? <><b>Their memory</b><p>{ch.memory_summary}</p></>
        : <p className="muted"><i>No distilled memory yet — it forms as they live through more.</i></p>}
      {Object.keys(ch.relationships).length > 0 && <>
        <b>What they think of the others</b>
        <ul>{Object.entries(ch.relationships).map(([k, v]) => <li key={k}><b>{k}</b>: {v}</li>)}</ul>
      </>}
      {ch.private_thoughts.length > 0 && <>
        <b>Recent thoughts</b>
        <ul>{ch.private_thoughts.slice(-6).reverse().map((t, i) => <li key={i}><i>{t}</i></li>)}</ul>
      </>}
    </details>
  )
}

function EditCharacter({ ctx, chars }: { ctx: Ctx; chars: Character[] }) {
  const toForm = (c: Character) => ({ name: c.name, player_label: c.player_label,
    personality: c.personality, backstory: c.backstory, inventory: c.inventory.join("\n") })
  const [who, setWho] = useState(chars[0].id)
  const ch = chars.find((c) => c.id === who) ?? chars[0]
  const [f, setF] = useState(toForm(ch))
  useEffect(() => { setF(toForm(ch)) }, [ch.id])
  const set = (k: keyof ReturnType<typeof toForm>) =>
    (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  return (
    <details>
      <summary>📖 Character backgrounds</summary>
      <select value={ch.id} onChange={(e) => setWho(e.target.value)}>
        {chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <form onSubmit={(e) => {
        e.preventDefault()
        ctx.call(() => api.send(`/api/game/characters/${ch.id}`, {
          name: f.name.trim() || ch.name, player_label: f.player_label.trim(),
          personality: f.personality.trim(), backstory: f.backstory.trim(),
          inventory: f.inventory.split("\n"),
        }, "PATCH"))
      }}>
        <label>Name</label><input value={f.name} onChange={set("name")} />
        <label>Player label</label><input value={f.player_label} onChange={set("player_label")} />
        <label>Personality</label>
        <textarea rows={3} value={f.personality} onChange={set("personality")} />
        <label>Background story</label>
        <textarea rows={5} value={f.backstory} onChange={set("backstory")} />
        <label>Inventory (one per line)</label>
        <textarea rows={3} value={f.inventory} onChange={set("inventory")} />
        <button type="submit">Save background</button>
      </form>
    </details>
  )
}

function AddCharacter({ ctx }: { ctx: Ctx }) {
  const blank = { name: "", player_label: "", controller: "human", personality: "", backstory: "" }
  const [f, setF] = useState(blank)
  const set = (k: keyof typeof blank) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  return (
    <details>
      <summary>➕ Add character</summary>
      <form onSubmit={async (e) => {
        e.preventDefault()
        if (!f.name.trim()) return
        await ctx.call(() => api.send("/api/game/characters", f))
        setF(blank)
      }}>
        <label>Name</label><input value={f.name} onChange={set("name")} />
        <label>Player label (e.g. Player 2)</label>
        <input value={f.player_label} onChange={set("player_label")} />
        <Seg options={["human", "ai"]} value={f.controller as "human" | "ai"}
          onChange={(v) => setF({ ...f, controller: v })} />
        <label>Personality</label><input value={f.personality} onChange={set("personality")} />
        <label>Background story</label>
        <textarea rows={4} value={f.backstory} onChange={set("backstory")} />
        <button type="submit">Add</button>
      </form>
    </details>
  )
}

export default function Sidebar({ ctx, stress }: { ctx: Ctx; stress: number }) {
  const { meta, game } = ctx
  const st = game?.state
  const patch = (body: object) => ctx.call(() => api.send("/api/game/settings", body, "PATCH"))

  return (
    <>
      <h1>🐙 AI TTRPG Runner</h1>
      <p className="muted small">
        {meta.mock && <b className="warn">🎭 MOCK MODE — </b>}LLM: {meta.llm.provider} / {meta.llm.model}
      </p>
      <LLMSettings ctx={ctx} />
      <CampaignPicker ctx={ctx} />
      {st && game && <>
        <hr />
        <label>Language</label>
        <Seg options={Object.keys(meta.languages)} value={st.language} labels={meta.languages}
          onChange={(v) => patch({ language: v })} />
        <label className="toggle" title="ON: the Keeper and companions play along with whatever you
steer toward. OFF: impartial Keeper, companions with their own will.">
          <input type="checkbox" checked={st.god_mode}
            onChange={(e) => patch({ god_mode: e.target.checked })} />
          😇 God mode
        </label>
        <label title="solo: AI companions are narrated NPCs. keeper: they act when the Keeper calls
on them. active: they act every turn.">AI party mode</label>
        <Seg options={["solo", "keeper", "active"]} value={st.party_mode}
          onChange={(v) => patch({ party_mode: v })} />
        <label title="Player: companions talk like people at a table. Cinematic: richer prose.">
          Companion voice
        </label>
        <Seg options={["player", "cinematic"]} value={st.companion_style}
          labels={{ player: "🎭 Player", cinematic: "🎬 Cinematic" }}
          onChange={(v) => patch({ companion_style: v })} />

        <h2>Party</h2>
        {st.characters.map((ch) => <PartyMember key={ch.id} ctx={ctx} ch={ch} />)}
        {st.characters.some((c) => c.controller === "ai") &&
          <InnerLife chars={st.characters.filter((c) => c.controller === "ai")} />}
        <EditCharacter ctx={ctx} chars={st.characters} />
        <AddCharacter ctx={ctx} />

        <AmbienceButton mood={game.mood} stress={stress} diceNonce={st.dice_log.length} />
        {meta.audio.length > 0 && <details>
          <summary>🎵 Background music</summary>
          <BgmPicker tracks={meta.audio} />
        </details>}

        <details>
          <summary>🎲 Dice log</summary>
          {st.dice_log.slice(-25).reverse().map((l, i) => <p key={i} className="muted small">{l}</p>)}
        </details>
        <details>
          <summary>🧪 Minigame tester</summary>
          <p className="muted small">Launch any minigame directly (no Keeper). The result is fed back
            into the story like a real one.</p>
          {Object.entries(meta.minigames).map(([type, label]) => (
            <button key={type} className="wide" disabled={!!st.pending_minigame || !!ctx.busy}
              onClick={() => ctx.call(() => api.send("/api/game/minigame/launch", { type }))}>
              {label}
            </button>
          ))}
        </details>
        <div className="row">
          <button disabled={!game.can_undo || !!ctx.busy} title="Rewind the last action / roll / minigame"
            onClick={() => ctx.call(() => api.send("/api/game/undo"))}>↩ Undo turn</button>
          <a className="button" href="/api/game/export" download={`${game.title}.md`}>📜 Export</a>
        </div>
      </>}
    </>
  )
}

function BgmPicker({ tracks }: { tracks: string[] }) {
  const [pick, setPick] = useState("")
  return (
    <>
      <select value={pick} onChange={(e) => setPick(e.target.value)}>
        <option value="">(off)</option>
        {tracks.map((t) => <option key={t}>{t}</option>)}
      </select>
      {pick && <audio src={`/api/audio/${encodeURIComponent(pick)}`} controls loop autoPlay />}
    </>
  )
}
