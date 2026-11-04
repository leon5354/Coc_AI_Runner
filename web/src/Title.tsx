// The front door: campaigns as cards over their own art.
import { useState } from "react"
import * as api from "./api"
import type { Game } from "./api"
import type { Ctx } from "./App"
import { SceneArt } from "./art/SceneArt"

export function brainName(ctx: Ctx) {
  const { mock, llm } = ctx.meta
  if (mock) return "Demo Keeper (scripted)"
  if (llm.provider === "ollama") return llm.model ? `This PC · ${llm.model.split("/").pop()?.split(":")[0]}` : "No model picked yet"
  if (llm.provider === "claude_cli") return `Claude plan · ${llm.model}`
  return `${llm.provider} · ${llm.model}`
}

export default function Title({ ctx }: { ctx: Ctx }) {
  const { meta, game } = ctx
  const [file, setFile] = useState(game ? `${game.campaign}.yaml` : meta.campaigns[0]?.file ?? "")
  const chosen = meta.campaigns.find((c) => c.file === file) ?? meta.campaigns[0]
  const noBrain = !meta.mock && meta.llm.provider === "ollama" && !meta.llm.model

  async function start(restart: boolean) {
    if (noBrain) { ctx.openSettings(); return }
    if (restart && chosen.has_save && !confirm(`Start "${chosen.title}" over? This deletes its save.`)) return
    try {
      const g = await api.send<Game>("/api/game/start", { file: chosen.file, restart })
      await ctx.call(async () => g)
      await ctx.refreshMeta()
      ctx.go("play")
    } catch (e) { ctx.setError((e as Error).message) }
  }

  if (!chosen) return <div className="boot">No valid campaigns in data/campaigns/</div>

  return (
    <div className="title-screen">
      <SceneArt key={chosen.file} name={chosen.scene_name} text={chosen.scene_text} art={chosen.scene_art} mood={chosen.mood} />
      <div className="title-shade" />
      <header className="title-top">
        <h1>AI TTRPG Runner</h1>
        <div className="row">
          <button onClick={() => ctx.go("architect")}>New scenario</button>
          <button onClick={ctx.openSettings}>⚙ Settings</button>
        </div>
      </header>
      <section className="title-cards">
        {meta.campaigns.map((c) => (
          <button key={c.file} className={c.file === chosen.file ? "card-c on" : "card-c"} onClick={() => setFile(c.file)}>
            <b>{c.title}</b>
            <span>{c.system}{c.has_save ? " · saved game" : ""}</span>
          </button>
        ))}
      </section>
      <section className="title-main">
        <h2>{chosen.title}</h2>
        <p className="title-sys">{chosen.system}</p>
        <p className="title-intro">{chosen.intro}{chosen.intro.length >= 220 ? "…" : ""}</p>
        <div className="row">
          <button className="primary big" onClick={() => start(false)}>
            {game && `${game.campaign}.yaml` === chosen.file ? "Continue" : chosen.has_save ? "Resume" : "Begin"}
          </button>
          {chosen.has_save && <button className="big" onClick={() => start(true)}>Start over</button>}
        </div>
        <p className="title-brain" onClick={ctx.openSettings}>🧠 {brainName(ctx)}</p>
      </section>
    </div>
  )
}
