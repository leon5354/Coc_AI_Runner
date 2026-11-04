// Make your character before a new game: the campaign's hero is the starting point.
import { useEffect, useState } from "react"
import * as api from "./api"
import type { Campaign, Hero } from "./api"
import { Portrait } from "./art/Portrait"
import { t } from "./i18n"

export default function Creator({ campaign, onStart, onClose }: {
  campaign: Campaign; onStart: (hero: Hero) => void; onClose: () => void
}) {
  const [h, setH] = useState<Hero | null>(null)
  const [base, setBase] = useState(0)
  useEffect(() => {
    api.get<Hero>(`/api/campaign/hero?file=${encodeURIComponent(campaign.file)}`).then((d) => {
      setH(d)
      setBase(Object.values(d.skills).reduce((a, b) => a + b, 0))
    })
  }, [campaign.file])
  if (!h) return null

  const small = Math.max(...Object.values(h.skills)) <= 20      // modifiers, as in D&D
  const step = small ? 1 : 5
  const left = base - Object.values(h.skills).reduce((a, b) => a + b, 0)
  const set = (k: "name" | "personality" | "backstory") => (e: { target: { value: string } }) => setH({ ...h, [k]: e.target.value })
  const change = (skill: string, by: number) => {
    const v = h.skills[skill] + by
    if (v < 0 || v > (small ? 15 : 99) || left - by < 0) return
    setH({ ...h, skills: { ...h.skills, [skill]: v } })
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal creator" onClick={(e) => e.stopPropagation()}>
        <header><h2>{t("Your character")}</h2><button onClick={onClose}>✕</button></header>
        <div className="status-head">
          <Portrait name={h.name || "?"} about={`${h.personality} ${h.backstory}`} size={112} />
          <div className="grow">
            <label>{t("Name")}</label><input value={h.name} onChange={set("name")} />
            <label>{t("Personality")}</label><input value={h.personality} onChange={set("personality")} />
          </div>
        </div>
        <label>{t("Background")}</label>
        <textarea rows={4} value={h.backstory} onChange={set("backstory")} />
        <h4>{t("Skills")} · {t("{n} points left", { n: left })}</h4>
        <div className="skills">
          {Object.entries(h.skills).map(([name, v]) => (
            <div key={name} className="skill-edit">
              <span className="grow">{name}</span>
              <button type="button" onClick={() => change(name, -step)}>−</button>
              <b>{v}</b>
              <button type="button" disabled={left < step} onClick={() => change(name, step)}>+</button>
            </div>
          ))}
        </div>
        {h.inventory.length > 0 && <p className="muted small">{t("You carry")}: {h.inventory.join("、")}</p>}
        <div className="row">
          <button className="primary big" disabled={!h.name.trim()} onClick={() => onStart(h)}>{t("Begin")}</button>
        </div>
      </div>
    </div>
  )
}
