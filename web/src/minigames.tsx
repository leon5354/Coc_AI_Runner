// Keeper-invokable minigames (ported from interface/minigames.py). Each game calls done(result)
// once; the result string goes back to the Keeper as MINIGAME RESULT.
// GAMES must cover exactly core/minigames_catalog.py — test_minigame_catalog.py checks it.
// ponytail: answers (cipher solution, lock code, correct wire) live in the payload the browser
// gets. Fine for local play; check guesses server-side once players share a room online.
import { useEffect, useRef, useState, type ReactNode } from "react"
import { t } from "./i18n"
import type { Payload } from "./api"

type Props = { p: Payload; done: (result: string) => void }

export const SKINS: Record<string, { bg: string; ink: string; hot: string; font: string }> = {
  parchment: { bg: "linear-gradient(160deg,#efe3c2,#d9c795 90%)", ink: "#3a2b16", hot: "#58230a", font: "Georgia, serif" },
  modern: { bg: "linear-gradient(160deg,#f8f8f6,#e4e4de 90%)", ink: "#222", hot: "#b3541e", font: "'Courier New', monospace" },
  stone: { bg: "linear-gradient(160deg,#4a4a48,#2e2e2c 90%)", ink: "#9a9a90", hot: "#d8c690", font: "Georgia, serif" },
  chalk: { bg: "linear-gradient(160deg,#233329,#16211b 90%)", ink: "#3d5245", hot: "#e8e6d8", font: "'Comic Sans MS', cursive" },
}

const num = (v: unknown, d: number) => (Number.isFinite(Number(v)) && v !== null && v !== "" ? Number(v) : d)

function Clue({ text }: { text?: string }) {
  return text ? <p className="muted">🧩 {text}</p> : null
}

// --- burn reveal: hold the flame over the surface; hidden writing warms into view ---

function BurnReveal({ p, done }: Props) {
  const skin = SKINS[p.skin] ?? SKINS.parchment
  const pages: string[] = (p.pages ?? []).map(String).filter((s: string) => s.trim())
  const all = pages.length ? pages : [String(p.hidden_text ?? "")]
  const full = pages.length ? pages.join(" / ") : String(p.hidden_text ?? "")
  const result = `The heat reveals hidden writing: "${full}"`
  const paper = useRef<HTMLDivElement>(null)
  const flame = useRef<HTMLDivElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [label, setLabel] = useState("")

  useEffect(() => {
    // Heat model: nothing reveals on contact — the flame warms whatever it LINGERS over.
    // r2 = reach, ratePerSec = heat/s at the core, need = fraction of the page to finish.
    // Rates are 3x the Streamlit numbers: that version never advanced lastTs, so each 40ms tick
    // counted as 0.12s. Same dwell feel, but now a fast sweep no longer adds extra heat.
    const diff = ({
      easy: { r2: 4600, ratePerSec: 0.9, need: 0.72 },
      normal: { r2: 2900, ratePerSec: 0.48, need: 0.82 },
      hard: { r2: 1500, ratePerSec: 0.27, need: 0.9 },
    } as Record<string, { r2: number; ratePerSec: number; need: number }>)[p.difficulty ?? "normal"]
      ?? { r2: 2900, ratePerSec: 0.48, need: 0.82 }
    const el = paper.current!, w = wrap.current!, fl = flame.current!
    let pageIdx = 0, spans: HTMLSpanElement[] = [], heat: number[] = [], pageDone = false
    let cx = -1, cy = -1, active = false, lastTs = 0
    let pageTimer: number | undefined

    function loadPage(i: number) {
      el.innerHTML = ""
      spans = []; heat = []; pageDone = false
      for (const ch of all[i]) {
        const s = document.createElement("span")
        s.textContent = ch
        el.appendChild(s)
        spans.push(s); heat.push(0)
      }
      setLabel(all.length > 1 ? `page ${i + 1} / ${all.length}` : "")
    }
    loadPage(0)

    function step() {
      if (pageDone || !active) { lastTs = 0; return }
      const now = performance.now()
      if (!lastTs) { lastTs = now; return }
      const dt = Math.min(120, now - lastTs) / 1000
      lastTs = now
      let warm = 0
      for (let i = 0; i < spans.length; i++) {
        if (heat[i] < 1) {
          const r = spans[i].getBoundingClientRect()
          const dx = cx - (r.left + r.width / 2), dy = cy - (r.top + r.height / 2)
          const d2 = dx * dx + dy * dy
          if (d2 < diff.r2) {
            heat[i] = Math.min(1, heat[i] + (1 - d2 / diff.r2) * diff.ratePerSec * dt)
            const h = heat[i]
            spans[i].style.opacity = String(Math.pow(h, 0.7))
            spans[i].style.color = skin.hot
            spans[i].style.textShadow = `0 0 ${1 + h * 7}px ${skin.hot}${h > 0.5 ? "88" : "44"}`
          }
        }
        if (heat[i] >= 0.9) warm++
      }
      if (spans.length && warm >= spans.length * diff.need) {
        pageDone = true
        for (const s of spans) { s.style.opacity = "1"; s.style.color = skin.hot }
        if (pageIdx + 1 < all.length) pageTimer = window.setTimeout(() => { pageIdx++; loadPage(pageIdx) }, 1600)
        else done(result)
      }
    }

    const move = (e: PointerEvent) => {
      const wr = w.getBoundingClientRect()
      cx = e.clientX; cy = e.clientY; active = true
      fl.style.display = "block"
      fl.style.left = `${e.clientX - wr.left}px`
      fl.style.top = `${e.clientY - wr.top}px`
      step()
    }
    const leave = () => { active = false; fl.style.display = "none" }
    w.addEventListener("pointermove", move)
    w.addEventListener("pointerleave", leave)
    const timer = window.setInterval(step, 40)   // keep warming while the flame holds still
    return () => {
      clearInterval(timer); clearTimeout(pageTimer)
      w.removeEventListener("pointermove", move); w.removeEventListener("pointerleave", leave)
    }
  }, [])

  return (
    <>
      <h3>🕯️ {p.context || "A suspicious blank surface..."}</h3>
      <div className="paper-wrap" ref={wrap}>
        <div className="paper" ref={paper} style={{ background: skin.bg, color: skin.ink, fontFamily: skin.font }} />
        <div className="flame" ref={flame}>🕯️</div>
        <div className="hint">{t("Move the candle across the surface…")} {label}</div>
      </div>
      <button onClick={() => done(result)}>{t("Expose the whole surface to the heat")}</button>
    </>
  )
}

// --- seance: the planchette spells the message letter by letter ---

function Seance({ p, done }: Props) {
  const msg = String(p.message ?? "").toUpperCase()
  const [n, setN] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setN((x) => Math.min(x + 1, msg.length)), 380)
    return () => clearInterval(t)
  }, [])
  return (
    <>
      <h3>🕯️ {t("The planchette begins to move...")}</h3>
      <div className="board">
        <div className="spelled">{msg.slice(0, n)}</div>
        <div className="planchette">☩</div>
      </div>
      <button onClick={() => done(`The spirit spelled out: "${p.message ?? ""}"`)}>{t("It stops.")}</button>
    </>
  )
}

// --- cipher: N attempts, optional hint ---

function Cipher({ p, done }: Props) {
  const [attempts, setAttempts] = useState(0)
  const [guess, setGuess] = useState("")
  const [err, setErr] = useState("")
  const solution = String(p.solution ?? "").trim().toLowerCase()
  const max = Math.max(1, num(p.attempts, 3))
  const hintAfter = num(p.hint_after, 1)

  function tryIt() {
    const g = guess.trim()
    if (!g) return
    setGuess("")
    if (g.toLowerCase() === solution) return done(`The player SOLVED the cipher — the answer was "${p.solution}"`)
    const a = attempts + 1
    setAttempts(a)
    if (a >= max) return done(`The player FAILED to solve the cipher after ${max} attempts (the answer was "${p.solution}" — do not reveal it unless the fiction allows)`)
    setErr(`Wrong. ${max - a} attempt(s) left.`)
  }

  return (
    <>
      <h3>🔏 {t("A cipher blocks the way")}</h3>
      <pre className="cipher">{p.ciphertext}</pre>
      {attempts >= hintAfter && p.hint && <p className="muted">💡 Hint: {p.hint}</p>}
      <form className="row" onSubmit={(e) => { e.preventDefault(); tryIt() }}>
        <input className="grow" value={guess} onChange={(e) => setGuess(e.target.value)} placeholder={t("Your answer")} autoFocus />
        <button type="submit" className="primary">{t("Try it")}</button>
      </form>
      {err && <p className="danger">{err}</p>}
      {p.allow_giveup !== false && <button onClick={() => done("The player gave up on the cipher unsolved")}>{t("Give up")}</button>}
    </>
  )
}

// --- combination lock: feedback on digits in the right place ---

function CombinationLock({ p, done }: Props) {
  const code = String(p.code ?? "").trim()
  const max = num(p.attempts, 4)
  const [attempts, setAttempts] = useState(0)
  const [guess, setGuess] = useState("")
  const [err, setErr] = useState("")

  function turn() {
    const g = guess.trim()
    if (!g) return
    setGuess("")
    if (g === code) return done(`The player OPENED the lock (code ${code}) on attempt ${attempts + 1}`)
    const a = attempts + 1
    setAttempts(a)
    if (a >= max) return done(`The lock JAMMED after ${max} failed attempts — it will not open by dial anymore (the code was ${code}; do not reveal it)`)
    const right = [...g].filter((ch, i) => ch === code[i]).length
    setErr(`The dial resists. ${right}/${code.length} digits clicked into place. ${max - a} attempt(s) left.`)
  }

  return (
    <>
      <h3>🔒 {t("A combination lock")}</h3>
      <Clue text={p.clue} />
      <form className="row" onSubmit={(e) => { e.preventDefault(); turn() }}>
        <input className="grow dial" value={guess} maxLength={code.length} inputMode="numeric" autoFocus
          placeholder={`Enter ${code.length} digits`} onChange={(e) => setGuess(e.target.value)} />
        <button type="submit" className="primary">{t("Turn the dial")}</button>
      </form>
      {err && <p className="danger">{err}</p>}
      <button onClick={() => done("The player stepped away from the lock without opening it")}>{t("Step away")}</button>
    </>
  )
}

// --- tarot draw: three cards; the keeper must weave the omens in ---

const TAROT_DECK: [string, string][] = [
  ["The Tower", "sudden catastrophe; a structure — literal or of belief — collapses"],
  ["The Moon", "illusion and hidden enemies; nothing seen tonight is what it appears"],
  ["Death", "an irreversible transformation approaches; something must end"],
  ["The Hanged Man", "sacrifice; progress only through surrendering something dear"],
  ["The Hermit", "a solitary figure holds the answer; seek the one who withdrew"],
  ["Wheel of Fortune", "fate turns; an unlikely coincidence will decide everything"],
  ["The High Priestess", "secret knowledge; a text or whisper holds the key"],
  ["The Devil", "bondage; someone here is already owned by another will"],
  ["The Star", "one genuine hope; a small light survives if protected"],
  ["Judgement", "the past rises; something buried refuses to stay buried"],
  ["The Fool", "a reckless step; innocence walks into the abyss smiling"],
  ["The Lovers", "a choice between two paths; loyalty will be tested"],
]

function shuffled<T>(xs: T[]): T[] {
  const a = [...xs]
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]] }
  return a
}

function TarotDraw({ p, done }: Props) {
  const [cards, setCards] = useState<[string, string][] | null>(null)
  return (
    <>
      <h3>🃏 {p.context || "The cards are laid out..."}</h3>
      {!cards ? <button className="primary" onClick={() => setCards(shuffled(TAROT_DECK).slice(0, 3))}>{t("Draw three cards")}</button> : <>
        <div className="cards">
          {cards.map(([name, meaning]) => <div className="card" key={name}><b>{name}</b><p className="muted">{meaning}</p></div>)}
        </div>
        <button className="primary" onClick={() => done("The cards drawn: " + cards.map(([n, m]) => `${n} (${m})`).join("; ") + ". Weave these omens into what follows.")}>
          {t("Accept the omen")}
        </button>
      </>}
    </>
  )
}

// --- glyph sequence: activate the sigils in the right order ---

function GlyphSequence({ p, done }: Props) {
  const sequence: string[] = (p.sequence ?? []).map(String)
  const max = Math.max(1, num(p.attempts, 3))
  const [pool] = useState(() => shuffled([...sequence, ...(p.decoys ?? []).map(String)]))
  const [picked, setPicked] = useState<string[]>([])
  const [attempts, setAttempts] = useState(0)
  useEffect(() => { if (!sequence.length) done("(glyph_sequence had no sequence — skipped)") }, [])

  function press(g: string) {
    if (g === sequence[picked.length]) {
      const next = [...picked, g]
      setPicked(next)
      if (next.length === sequence.length) done(`The player activated the glyphs in the CORRECT order (${sequence.join(" -> ")}) — the ward opens`)
      return
    }
    const a = attempts + 1
    setPicked([]); setAttempts(a)
    if (a >= max) done(`The player FAILED the glyph sequence after ${max} attempts — the ward flares and seals itself (correct order was ${sequence.join(" -> ")}; do not reveal it)`)
  }

  return (
    <>
      <h3>✴️ {t("Arcane glyphs await the correct order")}</h3>
      <Clue text={p.clue} />
      <p><b>{t("Activated:")}</b> {picked.length ? picked.join(" → ") : <i>none</i>} ({picked.length}/{sequence.length})</p>
      <div className="glyphs">
        {pool.map((g, i) => <button key={i} disabled={picked.includes(g)} onClick={() => press(g)}>{g}</button>)}
      </div>
      <p className="muted">A wrong glyph resets the sequence. {max - attempts} attempt(s) before the ward seals.</p>
      <button onClick={() => done("The player stepped away from the glyphs without completing the sequence")}>{t("Step back from the glyphs")}</button>
    </>
  )
}

// --- dice duel: best-of-N gamble against an NPC ---

const d = (n: number) => 1 + Math.floor(Math.random() * n)

function DiceDuel({ p, done }: Props) {
  const opponent = p.opponent || "the stranger"
  const rounds = Math.max(1, num(p.rounds, 3))
  const [log, setLog] = useState<[number, number, string][]>([])
  const you = log.filter(([a, b]) => a > b).length
  const them = log.filter(([a, b]) => b > a).length
  const need = Math.floor(rounds / 2) + 1
  const over = you >= need || them >= need || log.length >= rounds

  useEffect(() => {
    if (!over) return
    if (you === them) done(`The dice duel with ${opponent} ended in a DRAW (${you}-${them})`)
    else done(`The player ${you > them ? "WON" : "LOST"} the dice duel against ${opponent} (${you}-${them}). Stakes: ${p.stakes || "as agreed"}`)
  }, [over])

  function play(kind: "bold" | "steady") {
    const mine = kind === "bold" ? d(10) : d(6) + 2
    const theirs = Math.random() < 0.5 ? d(10) : d(6) + 2
    const line = mine > theirs ? "you take the round" : theirs > mine ? "they take it" : "dead even — no point"
    setLog([...log, [mine, theirs, `${kind} play; ${line}`]])
  }

  return (
    <>
      <h3>🎲 Dice duel against <b>{opponent}</b></h3>
      {p.stakes && <p className="muted">💰 Stakes: {p.stakes}</p>}
      <ul>{log.map(([a, b, l], i) => <li key={i}>Round {i + 1}: you <b>{a}</b> vs {opponent} <b>{b}</b> — {l}</li>)}</ul>
      {!over && <>
        <p><b>Round {log.length + 1} of {rounds}</b> — score {you}-{them}. Choose your play:</p>
        <div className="row">
          <button className="grow" onClick={() => play("bold")}>{t("🔥 Bold (d10 — swing big)")}</button>
          <button className="grow" onClick={() => play("steady")}>{t("🛡️ Steady (d6+2 — play safe)")}</button>
        </div>
      </>}
    </>
  )
}

// --- wire cut: one chance, choose the right line ---

const WIRE_COLORS: Record<string, string> = {
  red: "#d9534f", blue: "#4a7fd4", green: "#4faf6b", yellow: "#d4b74a",
  black: "#555", white: "#ddd", purple: "#9a6bd4", orange: "#d4854a",
}

function WireCut({ p, done }: Props) {
  const wires: string[] = (p.wires ?? []).map((w: unknown) => String(w).toLowerCase())
  const correct = String(p.correct ?? "").toLowerCase()
  useEffect(() => { if (!wires.length || !wires.includes(correct)) done("(wire_cut had no valid wires — skipped)") }, [])
  return (
    <>
      <h3>✂️ {t("One cut. Choose.")}</h3>
      <Clue text={p.clue} />
      <div className="wires">{wires.map((w) => <div key={w} style={{ background: WIRE_COLORS[w] ?? "#888" }} />)}</div>
      <div className="row">
        {wires.map((w) => (
          <button key={w} className="grow" onClick={() => done(w === correct
            ? `The player cut the ${w} wire — CORRECT. The device goes quiet.`
            : `The player cut the ${w} wire — WRONG (the correct one was ${correct}). Consequence: ${p.consequence || "the mechanism triggers"}`)}>
            ✂️ {w}
          </button>
        ))}
      </div>
      <button onClick={() => done("The player backed away without cutting any wire")}>{t("Back away without cutting")}</button>
    </>
  )
}

// --- memory echo: watch the pattern flash, repeat it ---

const SIGILS = ["🜏", "☿", "🜍", "🝓"]

function MemoryEcho({ p, done }: Props) {
  const length = Math.min(6, Math.max(3, num(p.length, 4)))
  const maxAttempts = Math.max(1, num(p.attempts, 2))
  const [seq] = useState(() => Array.from({ length }, () => Math.floor(Math.random() * SIGILS.length)))
  const [lit, setLit] = useState<number | null>(null)
  const [status, setStatus] = useState(t("Watch…"))
  const [dead, setDead] = useState(false)
  const s = useRef({ accepting: false, pos: 0, attempts: 0, timers: [] as number[] })
  const later = (fn: () => void, ms: number) => { s.current.timers.push(window.setTimeout(fn, ms)) }
  const flash = (i: number, ms: number) => { setLit(i); later(() => setLit((l) => (l === i ? null : l)), ms) }

  function playback() {
    s.current.accepting = false; s.current.pos = 0
    setStatus(t("Watch…"))
    seq.forEach((x, n) => later(() => flash(x, 420), 650 * (n + 1)))
    later(() => { s.current.accepting = true; setStatus(t("Repeat the sequence.")) }, 650 * (seq.length + 1))
  }
  useEffect(() => { later(playback, 400); return () => s.current.timers.forEach(clearTimeout) }, [])

  function press(i: number) {
    const st = s.current
    if (!st.accepting) return
    flash(i, 200)
    if (i === seq[st.pos]) {
      st.pos++
      if (st.pos >= seq.length) {
        st.accepting = false
        setStatus(t("The pattern answers."))
        later(() => done("The player repeated the pattern PERFECTLY — the mechanism yields"), 700)
      }
    } else if (++st.attempts >= maxAttempts) {
      st.accepting = false
      setDead(true)
      setStatus(t("The pattern fades, unanswered."))
      later(() => done("The player FAILED to repeat the pattern — the echo fades and the way stays shut"), 900)
    } else {
      setStatus(t("Wrong — it begins again…"))
      later(playback, 900)
    }
  }

  return (
    <>
      <h3>✨ {p.context || "A pattern flashes — remember it."}</h3>
      <div className="echo">
        <div className="muted">{status}</div>
        <div className="echo-grid">
          {SIGILS.map((sym, i) => (
            <div key={i} className={`sigil${lit === i ? " lit" : ""}${dead ? " dead" : ""}`} onClick={() => press(i)}>{sym}</div>
          ))}
        </div>
      </div>
      <button onClick={() => done("The player stepped away without answering the pattern")}>{t("Step away from the pattern")}</button>
    </>
  )
}

export const GAMES: Record<string, (props: Props) => ReactNode> = {
  burn_reveal: BurnReveal,
  cipher: Cipher,
  seance: Seance,
  combination_lock: CombinationLock,
  tarot_draw: TarotDraw,
  glyph_sequence: GlyphSequence,
  dice_duel: DiceDuel,
  wire_cut: WireCut,
  memory_echo: MemoryEcho,
}

const ICONS: Record<string, string> = {
  burn_reveal: "🕯️", cipher: "🔏", seance: "☩", combination_lock: "🔒", tarot_draw: "🃏",
  glyph_sequence: "✴️", dice_duel: "🎲", wire_cut: "✂️", memory_echo: "✨",
}

function Unsupported({ p, done }: Props) {
  useEffect(() => { done(`(unsupported minigame type ${JSON.stringify(p.type)} — skipped)`) }, [])
  return null
}

/** Host: renders the game and makes sure it reports exactly once. Remount (key) per minigame. */
export function Minigame({ payload, onResult, disabled }: {
  payload: Payload; onResult: (result: string) => void; disabled?: boolean
}) {
  const sent = useRef(false)
  const done = (r: string) => { if (!sent.current) { sent.current = true; onResult(r) } }
  const G = GAMES[payload.type] ?? Unsupported
  return <fieldset className="minigame" disabled={disabled}><G p={payload} done={done} /></fieldset>
}

/** Static freeze-frame of a finished minigame. */
export function FrozenMinigame({ payload, result }: { payload: Payload; result: string }) {
  const skin = SKINS[payload.skin] ?? SKINS.parchment
  return (
    <div className="frozen">
      <div>{ICONS[payload.type] ?? "🧩"} <b>{payload.context || payload.type}</b></div>
      {payload.type === "burn_reveal" && (
        <div className="paper" style={{ background: skin.bg, color: skin.hot, fontFamily: skin.font }}>
          {(payload.pages ?? []).length ? payload.pages.join(" / ") : payload.hidden_text}
        </div>
      )}
      {payload.type === "cipher" && <pre className="cipher">{payload.ciphertext}</pre>}
      <p className="muted">{result}</p>
    </div>
  )
}
