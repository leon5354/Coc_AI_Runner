import { useState } from "react"
import Markdown from "react-markdown"
import * as api from "./api"
import type { Ctx } from "./App"

type Msg = { role: "user" | "assistant"; content: string }

export default function Architect({ ctx, onError }: { ctx: Ctx; onError: (e: string) => void }) {
  const { meta } = ctx
  const [history, setHistory] = useState<Msg[]>([])
  const [text, setText] = useState("")
  const [system, setSystem] = useState(meta.rule_systems.includes("coc7e") ? "coc7e" : meta.rule_systems[0])
  const [setting, setSetting] = useState(meta.default_setting[system] ?? "generic")
  const [working, setWorking] = useState("")
  const [made, setMade] = useState<{ file: string; yaml: string } | null>(null)

  async function guard(label: string, fn: () => Promise<void>) {
    onError("")
    setWorking(label)
    try { await fn() } catch (e) { onError((e as Error).message) } finally { setWorking("") }
  }

  function chat() {
    const t = text.trim()
    if (!t || working) return
    const next: Msg[] = [...history, { role: "user", content: t }]
    setHistory(next)
    setText("")
    guard("The Scripter ponders…", async () => {
      const { reply } = await api.send<{ reply: string }>("/api/architect/chat", { history: next })
      setHistory([...next, { role: "assistant", content: reply }])
    })
  }

  function generate() {
    guard(setting !== "generic" ? "Consulting the archives, then drafting blueprints…"
      : "The Architect drafts blueprints… (this can take a minute)", async () => {
      setMade(await api.send("/api/architect/generate", { history, rule_system: system, setting }))
      await ctx.refreshMeta()
    })
  }

  return (
    <div className="architect">
      <p className="muted">Brainstorm a scenario with the Scripter, then generate a playable campaign file.</p>
      <div className="transcript">
        {history.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "player" : "keeper"}`}>
            <span className="av">{m.role === "user" ? "🕵️" : "🏗️"}</span><div><Markdown>{m.content}</Markdown></div>
          </div>
        ))}
        {working && <div className="thinking"><span className="spinner" /> {working}</div>}
      </div>

      <div className="row">
        <label className="grow">Rule system
          <select value={system} onChange={(e) => {
            setSystem(e.target.value)
            setSetting(meta.default_setting[e.target.value] ?? "generic")
          }}>{meta.rule_systems.map((r) => <option key={r}>{r}</option>)}</select>
        </label>
        <label className="grow" title="A real setting grounds the plot in its official wiki canon (fetched once, baked into the campaign). Trademarked settings: personal play only.">
          Setting / IP
          <select value={setting} onChange={(e) => setSetting(e.target.value)}>
            {Object.entries(meta.settings).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <button className="primary wide" disabled={!history.length || !!working} onClick={generate}>⚒️ Generate campaign</button>

      {made && (
        <div className="success">
          Campaign saved: <b>{made.file}</b> — validated and ready. Pick it in the sidebar and press Start.
          <details><summary>View generated YAML</summary><pre>{made.yaml}</pre></details>
        </div>
      )}

      <details>
        <summary>🧩 Minigame coverage by setting</summary>
        <table>
          <thead><tr><th>Minigame</th>{Object.values(meta.settings).map((s) => <th key={s}>{s}</th>)}</tr></thead>
          <tbody>{meta.coverage.map((r) => <tr key={r[0]}>{r.map((c, i) => <td key={i}>{c}</td>)}</tr>)}</tbody>
        </table>
      </details>

      <form className="row" onSubmit={(e) => { e.preventDefault(); chat() }}>
        <textarea className="grow" rows={2} value={text} placeholder="Describe the scenario you want…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chat() } }} />
        <button type="submit" className="primary" disabled={!text.trim() || !!working}>Send</button>
      </form>
    </div>
  )
}
