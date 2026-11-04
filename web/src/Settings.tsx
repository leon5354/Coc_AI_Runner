// Settings: which brain runs the game, how the table plays, and test tools.
import { useEffect, useState } from "react"
import { setUiPref, t, uiPref } from "./i18n"
import * as api from "./api"
import type { Brains, Game } from "./api"
import type { Ctx } from "./App"
import { AmbienceButton } from "./Atmosphere"

function Seg<T extends string>({ options, value, onChange, labels }: {
  options: T[]; value: T; onChange: (v: T) => void; labels?: Record<string, string>
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o} className={o === value ? "on" : ""} onClick={() => o !== value && onChange(o)}>{labels?.[o] ?? o}</button>
      ))}
    </div>
  )
}

function Local({ ctx, brains, reload, use }: { ctx: Ctx; brains: Brains; reload: () => void; use: (p: string, m: string) => void }) {
  const [pull, setPull] = useState("")
  const [status, setStatus] = useState("")
  const { ollama, gpu } = brains
  const active = ctx.meta.llm.provider === "ollama" ? ctx.meta.llm.model : ""

  async function add() {
    if (!pull.trim()) return
    setStatus("Starting…")
    try {
      await api.stream<{ status?: string; percent?: number | null; done?: boolean; error?: string | boolean }>(
        "/api/llm/pull", { name: pull }, (l) => {
          if (l.error) setStatus(`Failed: ${l.status ?? l.error}`)
          else if (l.done) { setStatus("Installed."); setPull(""); reload() }
          else setStatus(`${l.status ?? ""}${l.percent != null ? ` ${l.percent}%` : ""}`)
        })
    } catch (e) { setStatus((e as Error).message) }
  }

  async function remove(name: string) {
    if (!confirm(`Delete ${name} from this PC? You would have to download it again.`)) return
    await ctx.call(async () => { await api.send("/api/llm/remove", { name }); return ctx.game })
    reload()
  }

  if (!ollama.installed) return <p className="muted">Install <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a> to run a model on your GPU.</p>
  return (
    <>
      <p className="muted">{gpu ? `${gpu.name}, ${gpu.gb} GB. ` : ""}{ollama.running ? "Free, private, no key. Pick a model smaller than your GPU memory." : "Starting Ollama… reopen Settings in a moment."}</p>
      {ollama.models.map((m) => (
        <div key={m.name} className={m.name === active ? "model on" : "model"}>
          <span title={m.name}>{m.name.split("/").pop()}</span><i>{m.gb} GB</i>
          <button disabled={m.name === active} onClick={() => use("ollama", m.name)}>{t(m.name === active ? "In use" : "Use")}</button>
          <button onClick={() => remove(m.name)}>{t("Remove")}</button>
        </div>
      ))}
      <div className="row">
        <input className="grow" value={pull} onChange={(e) => setPull(e.target.value)}
          placeholder="Paste a Hugging Face GGUF link, e.g. hf.co/user/model-GGUF:Q4_K_M" />
        <button onClick={add}>{t("Add model")}</button>
      </div>
      {status && <p className="small muted">{status}</p>}
    </>
  )
}

function Brain({ ctx }: { ctx: Ctx }) {
  const { meta } = ctx
  const [brains, setBrains] = useState<Brains | null>(null)
  const [claude, setClaude] = useState(meta.llm.provider === "claude_cli" ? meta.llm.model : "sonnet")
  const [prov, setProv] = useState("openrouter")
  const [model, setModel] = useState(meta.main_models[0])
  const [util, setUtil] = useState(meta.llm.util_model)
  const reload = () => api.get<Brains>("/api/llm/options").then(setBrains).catch(() => {})
  useEffect(() => { reload() }, [])

  const use = (provider: string, m: string, utilModel = "") => ctx.call(async () => {
    await api.send("/api/llm", { provider, model: m, util_model: utilModel })
    await ctx.refreshMeta()
    return ctx.game
  })

  if (meta.mock) return <p className="warn">Demo mode: a scripted Keeper is running. Start without --mock to use a real AI.</p>
  if (!brains) return <p className="muted">{t("Looking at what this PC can run…")}</p>
  const using = meta.llm.provider
  return (
    <>
      <div className={using === "ollama" ? "brain on" : "brain"}>
        <h3>🖥 This PC <em>free</em></h3>
        <Local ctx={ctx} brains={brains} reload={reload} use={use} />
        {using === "ollama" && brains.ollama.models.length > 1 && (
          <label>{t("Small model for summaries (optional)")}
            <select value={util} onChange={(e) => { setUtil(e.target.value); use("ollama", meta.llm.model, e.target.value) }}>
              <option value="">{t("Same as the Keeper")}</option>
              {brains.ollama.models.map((m) => <option key={m.name} value={m.name}>{m.name.split("/").pop()}</option>)}
            </select>
          </label>
        )}
      </div>
      <div className={using === "claude_cli" ? "brain on" : "brain"}>
        <h3>✦ Claude plan <em>no key</em></h3>
        {!brains.claude.installed ? <p className="muted">Needs Claude Code installed.</p>
          : !brains.claude.logged_in ? <p className="muted">Not logged in. Run <code>claude auth login</code> in a terminal once, then reopen Settings.</p>
            : <>
              <p className="muted">Uses your Claude subscription limits, not an API bill.</p>
              <div className="row">
                <select className="grow" value={claude} onChange={(e) => setClaude(e.target.value)}>
                  {meta.claude_models.map((m) => <option key={m}>{m}</option>)}
                </select>
                <button onClick={() => use("claude_cli", claude)}>{t("Use")}</button>
              </div>
            </>}
      </div>
      <div className={["openrouter", "google"].includes(using) ? "brain on" : "brain"}>
        <h3>🔑 Online API <em>pay per use</em></h3>
        <p className="muted">
          {brains.keys.openrouter ? "OpenRouter is connected. " : <><a href="/api/llm/openrouter/login">Sign in with OpenRouter</a>, or add a key to .env. </>}
          Signing in only saves pasting a key: playing still spends your credits.
        </p>
        <div className="row">
          <select value={prov} onChange={(e) => setProv(e.target.value)}><option>openrouter</option><option>google</option></select>
          <input className="grow" list="models" value={model} onChange={(e) => setModel(e.target.value)} />
          <datalist id="models">{meta.main_models.map((m) => <option key={m} value={m} />)}</datalist>
          <button onClick={() => use(prov, model)}>{t("Use")}</button>
        </div>
      </div>
    </>
  )
}

export default function Settings({ ctx, onClose }: { ctx: Ctx; onClose: () => void }) {
  const { meta, game } = ctx
  const st = game?.state
  const patch = (body: object) => ctx.call(() => api.send<Game>("/api/game/settings", body, "PATCH"))
  const [fast, setFast] = useState(() => { try { return localStorage.getItem("dice.fast") === "1" } catch { return false } })
  const setFastDice = (v: boolean) => { setFast(v); try { localStorage.setItem("dice.fast", v ? "1" : "0") } catch { /* private window */ } }
  const [who, setWho] = useState({ name: "", controller: "human", backstory: "" })
  const [ui, setUi] = useState(uiPref())

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header><h2>{t("Settings")}</h2><button onClick={onClose}>✕</button></header>
        <h3>{t("Who is the Keeper?")}</h3>
        <Brain ctx={ctx} />
        <label>{t("Interface")}</label>
        <Seg options={["auto", "en", "zh"]} value={ui} labels={{ auto: "Auto", en: "English", zh: "繁體中文" }}
          onChange={(v) => { setUiPref(v); setUi(v); ctx.refreshMeta() }} />
        <h3>{t("Sound and dice")}</h3>
        <div className="row">
          <AmbienceButton mood={game?.mood ?? "night"} stress={1} diceNonce={st?.dice_log.length ?? 0} />
          <label className="toggle"><input type="checkbox" checked={fast} onChange={(e) => setFastDice(e.target.checked)} /> {t("Skip the 3D dice")}</label>
        </div>
        {meta.audio.length > 0 && <Music tracks={meta.audio} />}
        {st && game && <>
          <h3>{t("This game")}</h3>
          <label>{t("Language")}</label>
          <Seg options={Object.keys(meta.languages)} value={st.language} labels={meta.languages} onChange={(v) => patch({ language: v })} />
          <label>{t("AI companions")}</label>
          <Seg options={["solo", "keeper", "active"]} value={st.party_mode}
            labels={{ solo: t("Narrated by Keeper"), keeper: t("Act when called"), active: t("Act every turn") }} onChange={(v) => patch({ party_mode: v })} />
          <label>{t("Companion voice")}</label>
          <Seg options={["player", "cinematic"]} value={st.companion_style}
            labels={{ player: t("Like a player"), cinematic: t("Like a novel") }} onChange={(v) => patch({ companion_style: v })} />
          <label className="toggle" title="The Keeper and companions play along with you, biasing fate your way.">
            <input type="checkbox" checked={st.god_mode} onChange={(e) => patch({ god_mode: e.target.checked })} /> {t("😇 God mode")}
          </label>
          <details>
            <summary>{t("➕ Add a character")}</summary>
            <form onSubmit={async (e) => {
              e.preventDefault()
              if (!who.name.trim()) return
              await ctx.call(() => api.send("/api/game/characters", who))
              setWho({ name: "", controller: "human", backstory: "" })
            }}>
              <label>{t("Name")}</label><input value={who.name} onChange={(e) => setWho({ ...who, name: e.target.value })} />
              <label>{t("Played by")}</label>
              <Seg options={["human", "ai"]} value={who.controller as "human" | "ai"} onChange={(v) => setWho({ ...who, controller: v })} />
              <label>{t("Background")}</label>
              <textarea rows={3} value={who.backstory} onChange={(e) => setWho({ ...who, backstory: e.target.value })} />
              <button type="submit">{t("Add")}</button>
            </form>
          </details>
          <details>
            <summary>{t("🧪 Try a minigame")}</summary>
            <div className="row">
              {Object.entries(meta.minigames).map(([type, label]) => (
                <button key={type} disabled={!!st.pending_minigame || !!ctx.busy}
                  onClick={() => { onClose(); ctx.call(() => api.send("/api/game/minigame/launch", { type })) }}>{label}</button>
              ))}
            </div>
          </details>
          <details>
            <summary>{t("🎲 Dice log")}</summary>
            {st.dice_log.slice(-40).reverse().map((l, i) => <p key={i} className="muted small">{l}</p>)}
          </details>
          <div className="row">
            <a className="button" href="/api/game/export" download={`${game.title}.md`}>{t("📜 Export story")}</a>
          </div>
        </>}
      </div>
    </div>
  )
}

function Music({ tracks }: { tracks: string[] }) {
  const [pick, setPick] = useState("")
  return (
    <>
      <label>{t("Background music")}</label>
      <select value={pick} onChange={(e) => setPick(e.target.value)}>
        <option value="">{t("Off")}</option>
        {tracks.map((t) => <option key={t}>{t}</option>)}
      </select>
      {pick && <audio src={`/api/audio/${encodeURIComponent(pick)}`} controls loop autoPlay />}
    </>
  )
}
