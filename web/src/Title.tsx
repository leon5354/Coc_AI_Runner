// The front door: campaigns as cards over their own art.
import { useState } from "react"
import { t } from "./i18n"
import * as api from "./api"
import type { Game, Hero } from "./api"
import type { Ctx } from "./App"
import { SceneArt } from "./art/SceneArt"
import Creator from "./Creator"

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
  const [creating, setCreating] = useState(false)
  const noBrain = !meta.mock && meta.llm.provider === "ollama" && !meta.llm.model

  async function start(body: { slot?: string; new?: boolean; hero?: Hero }) {
    if (noBrain) { ctx.openSettings(); return }
    setCreating(false)
    try {
      const g = await api.send<Game>("/api/game/start", { file: chosen.file, ...body })
      await ctx.call(async () => g)
      await ctx.refreshMeta()
      ctx.setRecap(g.state.turn_count > 0)      // coming back to a game in progress
      ctx.go("play")
    } catch (e) { ctx.setError((e as Error).message) }
  }

  async function remove(slot: string) {
    if (!confirm(t("Delete this save? It can't be brought back."))) return
    await ctx.call(async () => {
      await api.send("/api/game/saves/delete", { file: chosen.file, slot })
      await ctx.refreshMeta()
      return api.get<Game | null>("/api/game")
    })
  }

  if (!chosen) return <div className="boot">No valid campaigns in data/campaigns/</div>

  return (
    <div className="title-screen">
      <SceneArt key={chosen.file} name={chosen.scene_name} text={chosen.scene_text} art={chosen.scene_art} mood={chosen.mood} />
      <div className="title-shade" />
      <header className="title-top">
        <h1>AI TTRPG Runner</h1>
        <div className="row">
          <button onClick={() => ctx.go("architect")}>{t("New scenario")}</button>
          <button onClick={ctx.openSettings}>{t("⚙ Settings")}</button>
        </div>
      </header>
      <section className="title-cards">
        {meta.campaigns.map((c) => (
          <button key={c.file} className={c.file === chosen.file ? "card-c on" : "card-c"} onClick={() => setFile(c.file)}>
            <b>{c.title}</b>
            <span>{c.system}{c.saves.length ? ` · ${t("saved game")}` : ""}</span>
          </button>
        ))}
      </section>
      {creating && <Creator campaign={chosen} onClose={() => setCreating(false)} onStart={(hero) => start({ new: true, hero })} />}
      <section className="title-main">
        <h2>{chosen.title}</h2>
        <p className="title-sys">{chosen.system}</p>
        <p className="title-intro">{chosen.intro}{chosen.intro.length >= 220 ? "…" : ""}</p>
        {chosen.saves.map((s) => (
          <div className="save-row" key={s.slot}>
            <span className="grow">{s.scene} · {t("turn {n}", { n: s.turn })}{s.ended ? ` · ${t("finished")}` : ""}<i> · {new Date(s.when * 1000).toLocaleString()}</i></span>
            <button className="primary" onClick={() => start({ slot: s.slot })}>{t("Continue")}</button>
            <button title={t("Delete this save")} onClick={() => remove(s.slot)}>🗑</button>
          </div>
        ))}
        <div className="row">
          <button className={chosen.saves.length ? "big" : "primary big"} onClick={() => (noBrain ? ctx.openSettings() : setCreating(true))}>{t("New game")}</button>
        </div>
        <p className="title-brain" onClick={ctx.openSettings}>🧠 {brainName(ctx)}</p>
      </section>
    </div>
  )
}
