// Scene art, drawn entirely in code: a kit is a little painter that lays out silhouette layers
// on a 1600x900 stage. Same seed, same picture; a new scene gets its own variation.
export type Layer = { d: string; depth: number; tone: number; blur?: number; light?: number; hole?: boolean }
export type Glow = { x: number; y: number; r: number; flicker?: boolean; color?: string; o?: number }
export type Art = { layers: Layer[]; glows: Glow[]; fx: string; moon?: [number, number]; outdoors: boolean }

export type Rng = () => number
export function rng(seed: number): Rng {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
export function hash(s: string) {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  return h >>> 0
}

const W = 1600, H = 900
const f = (n: number) => n.toFixed(1)
const rect = (x: number, y: number, w: number, h: number) => `M${f(x)} ${f(y)}h${f(w)}v${f(h)}h${f(-w)}z`
const poly = (...p: number[]) => {
  let d = `M${f(p[0])} ${f(p[1])}`
  for (let i = 2; i < p.length; i += 2) d += `L${f(p[i])} ${f(p[i + 1])}`
  return d + "z"
}
const circle = (x: number, y: number, r: number) => `M${f(x - r)} ${f(y)}a${f(r)} ${f(r)} 0 1 0 ${f(r * 2)} 0a${f(r)} ${f(r)} 0 1 0 ${f(-r * 2)} 0z`
/** A doorway shape: straight sides with a round top. */
const arch = (x: number, y: number, w: number, h: number) =>
  `M${f(x)} ${f(y + h)}V${f(y + w / 2)}a${f(w / 2)} ${f(w / 2)} 0 0 1 ${f(w)} 0V${f(y + h)}z`
/** A pointed gothic window. */
const gothic = (x: number, y: number, w: number, h: number) =>
  `M${f(x)} ${f(y + h)}V${f(y + w * 0.7)}Q${f(x)} ${f(y + w * 0.1)} ${f(x + w / 2)} ${f(y)}Q${f(x + w)} ${f(y + w * 0.1)} ${f(x + w)} ${f(y + w * 0.7)}V${f(y + h)}z`
const full = rect(0, 0, W, H)

function ridge(r: Rng, y: number, amp: number, step = 60) {
  let d = `M0 ${H}L0 ${f(y)}`
  let h = y
  for (let x = step; x <= W + step; x += step) {
    h += (r() - 0.5) * amp
    h = Math.max(y - amp * 1.4, Math.min(y + amp, h))
    d += `L${x} ${f(h)}`
  }
  return d + `L${W + step} ${H}z`
}

function pine(r: Rng, x: number, base: number, h: number) {
  const w = h * 0.3, tiers = 8
  let d = `M${f(x - 5)} ${f(base)}L${f(x - 5)} ${f(base - h * 0.14)}`
  for (let i = 0; i < tiers; i++) {
    const t = i / tiers, y = base - h * (0.14 + t * 0.8), s = w * (1 - t) + 3
    d += `L${f(x - s - r() * 7)} ${f(y)}L${f(x - s * 0.35)} ${f(y - h * 0.03)}`
  }
  d += `L${f(x)} ${f(base - h)}`
  for (let i = tiers - 1; i >= 0; i--) {
    const t = i / tiers, y = base - h * (0.14 + t * 0.8), s = w * (1 - t) + 3
    d += `L${f(x + s * 0.35)} ${f(y - h * 0.03)}L${f(x + s + r() * 7)} ${f(y)}`
  }
  return d + `L${f(x + 5)} ${f(base - h * 0.14)}L${f(x + 5)} ${f(base)}z`
}

function books(r: Rng, x: number, y: number, w: number, h: number) {
  let d = "", cx = x + 4
  while (cx < x + w - 10) {
    const bw = 7 + r() * 12, bh = h * (0.68 + r() * 0.3)
    if (r() > 0.1) d += rect(cx, y + h - bh, bw, bh)
    cx += bw + 1.5
  }
  return d
}

function shelf(r: Rng, x: number, y: number, w: number, h: number, rows: number) {
  let frame = rect(x, y, w, 14) + rect(x, y, 14, h) + rect(x + w - 14, y, 14, h)
  let spines = ""
  const rh = h / rows
  for (let i = 0; i < rows; i++) {
    frame += rect(x, y + (i + 1) * rh - 8, w, 8)
    spines += books(r, x + 14, y + i * rh + 12, w - 28, rh - 22)
  }
  return { frame, spines }
}

function floorboards(y: number, n = 9) {
  let d = ""
  for (let i = 0; i <= n; i++) {
    const t = i / n
    d += poly(W * t - 1, y, W * t + 1, y, W * (t * 1.9 - 0.45) + 3, H, W * (t * 1.9 - 0.45) - 3, H)
  }
  return d
}

const candle = (x: number, y: number, h = 40) => rect(x - 5, y - h, 10, h) + rect(x - 16, y, 32, 5)

// --- interiors ---

function office(r: Rng): Art {
  const s1 = shelf(r, 90, 170, 330, 560, 5)
  return {
    outdoors: true, fx: "dust", moon: [1120, 300],
    layers: [
      { d: full + rect(960, 170, 330, 390), depth: 0.04, tone: 0.28, hole: true },
      { d: rect(1120, 170, 10, 390) + rect(960, 360, 330, 10) + rect(940, 150, 370, 22) + rect(940, 556, 370, 22), depth: 0.05, tone: 0.5 },
      { d: s1.frame, depth: 0.09, tone: 0.55 },
      { d: s1.spines, depth: 0.09, tone: 0.42 },
      { d: rect(0, 760, W, 140), depth: 0.1, tone: 0.5 },
      { d: floorboards(760), depth: 0.1, tone: 0.62 },
      { d: rect(470, 640, 800, 26) + rect(490, 666, 24, 170) + rect(1226, 666, 24, 170) + rect(1020, 666, 190, 120), depth: 0.2, tone: 0.82 },
      { d: rect(612, 626, 70, 14) + rect(640, 540, 12, 90) + poly(590, 545, 702, 545, 672, 490, 620, 490), depth: 0.2, tone: 0.9 },
      { d: rect(760, 612, 130, 28) + rect(800, 600, 90, 12) + rect(930, 600, 46, 40), depth: 0.2, tone: 0.86 },
      { d: `M210 900V600Q210 540 300 540Q390 540 390 600V740H440V900H380V800H230V900z`, depth: 0.36, tone: 1, blur: 2 },
    ],
    glows: [{ x: 646, y: 560, r: 300, flicker: true, o: 0.8 }, { x: 1120, y: 360, r: 260, o: 0.45 }],
  }
}

function library(r: Rng): Art {
  const layers: Layer[] = [{ d: full, depth: 0.03, tone: 0.2 }]
  for (const [x, w, y, tone] of [[640, 320, 200, 0.34], [300, 340, 150, 0.42], [960, 340, 150, 0.42], [-40, 360, 80, 0.6], [1280, 360, 80, 0.6]] as const) {
    const s = shelf(r, x, y, w, 760 - y, 6)
    layers.push({ d: s.frame, depth: 0.05 + tone * 0.12, tone }, { d: s.spines, depth: 0.05 + tone * 0.12, tone: tone - 0.1 })
  }
  layers.push(
    { d: rect(0, 760, W, 140), depth: 0.12, tone: 0.55 },
    { d: rect(420, 690, 760, 24) + rect(450, 714, 22, 120) + rect(1130, 714, 22, 120), depth: 0.24, tone: 0.85 },
    { d: books(r, 560, 640, 180, 50) + rect(850, 680, 120, 10), depth: 0.24, tone: 0.92 },
    { d: rect(1060, 660, 60, 12) + rect(1086, 600, 8, 60) + poly(1050, 604, 1130, 604, 1108, 560, 1072, 560), depth: 0.24, tone: 0.92 },
  )
  return { layers, outdoors: false, fx: "dust", glows: [{ x: 1090, y: 620, r: 340, flicker: true, o: 0.8 }, { x: 800, y: 300, r: 420, o: 0.2 }] }
}

function corridor(r: Rng): Art {
  const vx = 800, vy = 430
  const layers: Layer[] = [
    { d: poly(0, 0, W, 0, vx + 90, vy - 90, vx - 90, vy - 90), depth: 0.05, tone: 0.3 },
    { d: poly(0, H, W, H, vx + 90, vy + 120, vx - 90, vy + 120), depth: 0.05, tone: 0.4 },
    { d: poly(0, 0, vx - 90, vy - 90, vx - 90, vy + 120, 0, H), depth: 0.06, tone: 0.5 },
    { d: poly(W, 0, vx + 90, vy - 90, vx + 90, vy + 120, W, H), depth: 0.06, tone: 0.5 },
  ]
  let doors = "", lamps = ""
  for (let i = 0; i < 4; i++) {
    const a = 0.12 + i * 0.2, b = a + 0.1
    const X = (t: number) => t * (vx - 90), T = (t: number) => t * (vy - 90), B = (t: number) => H - t * (H - vy - 120)
    doors += poly(X(a), T(a) + 90 * (1 - a), X(b), T(b) + 90 * (1 - b), X(b), B(b), X(a), B(a))
    doors += poly(W - X(a), T(a) + 90 * (1 - a), W - X(b), T(b) + 90 * (1 - b), W - X(b), B(b), W - X(a), B(a))
    const ly = T(a) * 0.9, lw = 120 * (1 - a)
    lamps += rect(vx - lw / 2, ly * 0.8 + 14, lw, 10 * (1 - a))
  }
  layers.push({ d: doors, depth: 0.1, tone: 0.78 }, { d: lamps, depth: 0.08, tone: 0, light: 0.9 },
    { d: rect(vx - 40, vy - 70, 80, 180), depth: 0.02, tone: 0, light: 0.35 },
    { d: `M${vx - 12} ${vy + 110}v-92q12 -26 24 0v92z`, depth: 0.02, tone: 1 },
    { d: rect(120, 700, 260, 16) + rect(140, 716, 12, 90) + rect(350, 716, 12, 90) + `M130 700q20 -60 90 -56l150 10q10 20 0 46z`, depth: 0.3, tone: 1, blur: 2 })
  void r
  return { layers, outdoors: false, fx: "dust", glows: [{ x: vx, y: 240, r: 340, flicker: true, o: 0.55 }, { x: vx, y: vy, r: 170, o: 0.6 }] }
}

function hall(r: Rng): Art {
  let steps = ""
  for (let i = 0; i < 9; i++) steps += rect(860 + i * 62, 740 - i * 52, W, 54)
  let rails = ""
  for (let i = 0; i < 9; i++) rails += rect(868 + i * 62, 620 - i * 52, 8, 124)
  const frames = rect(170, 250, 150, 200) + rect(390, 300, 110, 150)
  return {
    outdoors: false, fx: "dust",
    layers: [
      { d: full + arch(560, 280, 210, 480), depth: 0.04, tone: 0.3, hole: true },
      { d: frames, depth: 0.07, tone: 0.52 },
      { d: rect(182, 262, 126, 176) + rect(400, 310, 90, 130), depth: 0.07, tone: 0.32 },
      { d: `M214 438q6-90 30-94q-20-44 2-54q24 8 8 54q24 6 30 94z`, depth: 0.07, tone: 0.6 },
      { d: rect(0, 755, W, 145), depth: 0.1, tone: 0.5 },
      { d: floorboards(755), depth: 0.1, tone: 0.62 },
      { d: steps, depth: 0.16, tone: 0.72 },
      { d: rails + poly(860, 618, 1420, 150, 1420, 164, 860, 632), depth: 0.18, tone: 0.9 },
      { d: rect(674 + r() * 8, 0, 4, 120) + circle(676, 150, 42), depth: 0.2, tone: 0.9 },
      { d: rect(80, 640, 240, 170) + rect(100, 810, 18, 40) + rect(290, 810, 18, 40) + rect(180, 560, 44, 80) + circle(202, 540, 34), depth: 0.3, tone: 1, blur: 1 },
    ],
    glows: [{ x: 676, y: 190, r: 300, flicker: true, o: 0.5 }, { x: 665, y: 520, r: 200, o: 0.55, color: "#ffb070" }],
  }
}

function attic(r: Rng): Art {
  let beams = ""
  for (let i = -3; i <= 3; i++) {
    if (!i) continue
    const x = 800 + i * 210
    beams += poly(800 + i * 26 - 10, 40, 800 + i * 26 + 10, 40, x + 40, 760, x - 40, 760)
  }
  return {
    outdoors: true, fx: "dust", moon: [800, 330],
    layers: [
      { d: full + circle(800, 330, 135), depth: 0.03, tone: 0.3, hole: true },
      { d: rect(792, 195, 16, 270) + rect(665, 322, 270, 16), depth: 0.04, tone: 0.55 },
      { d: `M0 0H800L0 620z M1600 0H800L1600 620z`, depth: 0.1, tone: 0.72 },
      { d: beams, depth: 0.14, tone: 0.8 },
      { d: rect(0, 760, W, 140), depth: 0.1, tone: 0.55 },
      { d: floorboards(760, 7), depth: 0.1, tone: 0.68 },
      { d: rect(170, 640, 220, 130) + `M170 640q110 -66 220 0z` + rect(420, 690, 130, 80), depth: 0.24, tone: 0.92 },
      { d: `M1090 760q-20 -180 40 -270q18 -24 40 0q60 90 40 270z`, depth: 0.2, tone: 0.84 },
      { d: rect(1320, 620, 170, 150) + rect(1350, 540, 110, 80) + rect(200 + r() * 10, 0, 3, 300), depth: 0.3, tone: 1, blur: 2 },
    ],
    glows: [{ x: 800, y: 340, r: 300, o: 0.7 }, { x: 800, y: 780, r: 260, o: 0.18 }],
  }
}

function cellar(r: Rng): Art {
  const layers: Layer[] = [{ d: full, depth: 0.02, tone: 0.16 }]
  for (const [w, tone] of [[300, 0.34], [520, 0.5], [820, 0.66], [1240, 0.84]] as const) {
    const h = w * 1.05, x = 800 - w / 2, y = 780 - h
    let stones = ""
    for (let i = 0; i < 40; i++) {
      const sx = r() * W, sy = r() * H
      if (sx > x - 60 && sx < x + w + 10 && sy > y - 40) continue   // only on the wall, never in the opening
      stones += rect(sx, sy, 34 + r() * 50, 12 + r() * 10)
    }
    layers.push({ d: full + arch(x, y, w, h + 200), depth: 0.04 + tone * 0.14, tone, hole: true })
    if (tone > 0.6) layers.push({ d: stones, depth: 0.04 + tone * 0.14, tone: Math.min(1, tone + 0.05) })
  }
  layers.push(
    { d: poly(0, 900, 1600, 900, 1600, 800, 0, 800), depth: 0.2, tone: 0.72 },
    { d: candle(470, 770) + candle(1130, 770) + candle(560, 760, 26), depth: 0.22, tone: 0.95 },
    { d: `M700 800q0 -100 100 -120q100 20 100 120z` + rect(650, 800, 300, 24), depth: 0.16, tone: 0.9 },
  )
  return { layers, outdoors: false, fx: "fog", glows: [
    { x: 470, y: 720, r: 170, flicker: true, o: 0.75, color: "#ffb070" }, { x: 1130, y: 720, r: 170, flicker: true, o: 0.75, color: "#ffb070" },
    { x: 800, y: 500, r: 300, o: 0.4 }] }
}

function livingroom(): Art {
  let bars = ""
  for (let i = 0; i < 2; i++) bars += rect(1080 + i * 110, 170, 8, 300)
  return {
    outdoors: true, fx: "rain", moon: undefined,
    layers: [
      { d: full + rect(1000, 170, 330, 300), depth: 0.03, tone: 0.28, hole: true },
      { d: bars + rect(1000, 310, 330, 8) + rect(980, 150, 370, 22) + rect(980, 466, 370, 22), depth: 0.04, tone: 0.5 },
      { d: `M960 120H1020Q1000 320 1030 520H950z M1380 120H1320Q1340 320 1310 520H1390z`, depth: 0.06, tone: 0.62 },
      { d: rect(0, 720, W, 180), depth: 0.1, tone: 0.5 },
      { d: rect(330, 470, 360, 280) + rect(380, 750, 30, 30) + rect(610, 750, 30, 30), depth: 0.16, tone: 0.82 },
      { d: rect(366, 498, 240, 196), depth: 0.16, tone: 0, light: 0.95 },
      { d: rect(622, 520, 40, 40) + rect(622, 590, 40, 16) + rect(622, 620, 40, 16) + poly(460, 470, 400, 370, 412, 366, 480, 470) + poly(540, 470, 610, 380, 622, 386, 560, 470), depth: 0.16, tone: 0.92 },
      { d: `M820 900V700Q820 620 900 620H1320Q1400 620 1400 700V900z M760 900V760Q760 720 800 720Q840 720 840 760V900z M1380 900V760Q1380 720 1420 720Q1460 720 1460 760V900z`, depth: 0.3, tone: 1, blur: 2 },
    ],
    glows: [{ x: 486, y: 596, r: 420, flicker: true, o: 0.75, color: "#9fd0ff" }],
  }
}

function bedroom(r: Rng): Art {
  return {
    outdoors: true, fx: "dust", moon: [340, 280],
    layers: [
      { d: full + rect(200, 140, 300, 360), depth: 0.03, tone: 0.28, hole: true },
      { d: rect(345, 140, 8, 360) + rect(200, 310, 300, 8), depth: 0.04, tone: 0.5 },
      { d: `M170 110H260Q230 330 270 540H160z M530 110H440Q470 330 430 540H540z`, depth: 0.06, tone: 0.62 },
      { d: rect(0, 730, W, 170), depth: 0.1, tone: 0.5 },
      { d: rect(780, 410, 620, 26) + rect(780, 410, 26, 330) + rect(1374, 410, 26, 330), depth: 0.14, tone: 0.72 },
      { d: `M740 900V640Q740 590 800 590H1380Q1440 590 1440 640V900z`, depth: 0.2, tone: 0.84 },
      { d: `M830 600q0 -60 80 -60h100q60 0 60 60z M1110 600q0 -60 80 -60h100q60 0 60 60z`, depth: 0.2, tone: 0.92 },
      { d: rect(600, 610, 110, 130) + rect(640, 540, 30, 70) + poly(610, 545, 700, 545, 680, 490, 630, 490), depth: 0.22, tone: 0.92 },
      { d: rect(1450 + r(), 200, 110, 540), depth: 0.3, tone: 1, blur: 3 },
    ],
    glows: [{ x: 655, y: 530, r: 260, flicker: true, o: 0.65, color: "#ffb070" }, { x: 350, y: 320, r: 280, o: 0.45 }],
  }
}

function elevator(r: Rng): Art {
  let panels = ""
  for (let i = 0; i < 3; i++) panels += rect(40 + i * 150, 120 + i * 10, 120, 610 - i * 24) + rect(W - 160 - i * 150, 120 + i * 10, 120, 610 - i * 24)
  let rivets = ""
  for (let i = 0; i < 26; i++) rivets += circle(r() > 0.5 ? 30 + r() * 440 : 1130 + r() * 440, 90 + r() * 700, 3)
  return {
    outdoors: false, fx: "dust",
    layers: [
      { d: full, depth: 0.02, tone: 0.3 },
      { d: panels, depth: 0.06, tone: 0.46 },
      { d: rivets, depth: 0.06, tone: 0.7 },
      { d: rect(792, 180, 16, 600), depth: 0.05, tone: 0, light: 0.9 },
      { d: rect(520, 170, 272, 610) + rect(808, 170, 272, 610), depth: 0.07, tone: 0.62 },
      { d: rect(500, 150, 600, 22) + rect(500, 150, 22, 640) + rect(1078, 150, 22, 640), depth: 0.08, tone: 0.8 },
      { d: rect(690, 74, 220, 56), depth: 0.08, tone: 0.95 },
      { d: rect(704, 88, 192, 28), depth: 0.08, tone: 0, light: 0.8 },
      { d: rect(1130, 380, 56, 170), depth: 0.1, tone: 0.86 },
      { d: circle(1158, 410, 9) + circle(1158, 440, 9) + circle(1158, 470, 9) + circle(1158, 500, 9), depth: 0.1, tone: 0, light: 0.55 },
      { d: rect(0, 790, W, 110), depth: 0.1, tone: 0.72 },
      { d: rect(0, 0, W, 60) + poly(0, 0, 1600, 0, 1540, 60, 60, 60), depth: 0.12, tone: 0.84 },
      { d: rect(0, 540, 470, 14) + rect(1130, 610, 470, 14), depth: 0.16, tone: 0.95 },
    ],
    glows: [{ x: 800, y: 480, r: 300, flicker: true, o: 0.5 }, { x: 800, y: 100, r: 220, flicker: true, o: 0.65, color: "#ffc080" }],
  }
}

function abyss(r: Rng): Art {
  const layers: Layer[] = []
  for (const [rx, tone] of [[230, 0.22], [420, 0.4], [640, 0.6], [960, 0.8]] as const) {
    const ry = rx * 0.34, cy = 560 + rx * 0.2
    layers.push({ d: `M0 900V${f(cy - ry * 1.4)}H1600V900z M${f(800 - rx)} ${f(cy)}a${f(rx)} ${f(ry)} 0 1 0 ${f(rx * 2)} 0a${f(rx)} ${f(ry)} 0 1 0 ${f(-rx * 2)} 0z`, depth: 0.03 + tone * 0.16, tone, hole: true })
  }
  let shards = ""
  for (let i = 0; i < 9; i++) {
    const x = r() * W, y = 80 + r() * 330, w = 30 + r() * 90
    shards += poly(x - w, y, x + w * 0.2, y - w * 0.5, x + w, y + 6, x + w * 0.2, y + w * 1.6)
  }
  layers.push({ d: shards, depth: 0.24, tone: 0.86 })
  return { layers, outdoors: true, fx: "spores", glows: [{ x: 800, y: 640, r: 360, flicker: true, o: 0.8 }], moon: undefined }
}

function forest(r: Rng, text: string): Art {
  const snowy = /snow|frost|ice|winter|雪|霜|冰|寒/i.test(text)
  const camp = /camp|tent|營/i.test(text), ritual = /ritual|altar|stones?|儀式|祭/i.test(text)
  const row = (n: number, base: number, h: number) => {
    let d = ""
    for (let i = 0; i < n; i++) d += pine(r, (i + r()) * (W / n), base + r() * 20, h * (0.7 + r() * 0.5))
    return d
  }
  const layers: Layer[] = [
    { d: ridge(r, 470, 70), depth: 0.03, tone: 0.16 },
    { d: row(24, 610, 150), depth: 0.05, tone: 0.28, blur: 1 },
    { d: ridge(r, 590, 40), depth: 0.07, tone: 0.34 },
    { d: row(15, 720, 300), depth: 0.1, tone: 0.5 },
    { d: ridge(r, 720, 30), depth: 0.13, tone: snowy ? 0.42 : 0.66 },
  ]
  const glows: Glow[] = []
  if (camp) {
    layers.push({ d: poly(520, 760, 700, 590, 880, 760) + poly(680, 760, 700, 650, 720, 760), depth: 0.17, tone: 0.86 },
      { d: `M1040 760l36 -14l40 10l-16 8z M1076 756q-20 -40 2 -74q10 26 22 34q10 18 -4 40z`, depth: 0.17, tone: 0.92 })
    glows.push({ x: 1080, y: 720, r: 260, flicker: true, o: 0.9, color: "#ffa050" })
  }
  if (ritual) {
    for (const [x, h] of [[520, 210], [660, 280], [800, 320], [940, 280], [1080, 210]] as const)
      layers.push({ d: poly(x - 40, 770, x - 26, 770 - h, x + 22, 770 - h - 16, x + 42, 770), depth: 0.17, tone: 0.84 })
    glows.push({ x: 800, y: 640, r: 420, flicker: true, o: 0.75 })
  }
  layers.push({ d: pine(r, 90, 960, 860) + pine(r, 1520, 960, 780), depth: 0.34, tone: 1, blur: 3 })
  return { layers, glows, fx: snowy ? "snow" : "fog", moon: [1180, 170], outdoors: true }
}

function lab(r: Rng): Art {
  let pipes = rect(0, 96, W, 22) + rect(0, 140, W, 12)
  for (let i = 0; i < 6; i++) pipes += rect(120 + i * 260, 96, 34, 60)
  let tanks = "", liquid = "", ribs = ""
  for (const x of [120, 340, 1110, 1330]) {
    tanks += rect(x - 8, 210, 176, 26) + rect(x - 8, 640, 176, 90) + rect(x, 236, 8, 404) + rect(x + 152, 236, 8, 404)
    liquid += rect(x + 8, 250 + r() * 60, 144, 390)
    ribs += `M${x + 80} 640q-34 -90 -12 -170q-24 -30 12 -64q36 34 12 64q22 80 -12 170z`
  }
  return {
    outdoors: false, fx: "sparks",
    layers: [
      { d: full, depth: 0.03, tone: 0.28 },
      { d: pipes, depth: 0.08, tone: 0.6 },
      { d: rect(0, 730, W, 170), depth: 0.1, tone: 0.5 },
      { d: floorboards(730, 12), depth: 0.1, tone: 0.6 },
      { d: liquid, depth: 0.12, tone: 0, light: 0.42 },
      { d: ribs, depth: 0.12, tone: 0.92 },
      { d: tanks, depth: 0.12, tone: 0.86 },
      { d: rect(640, 330, 320, 210), depth: 0.1, tone: 0.82 },
      { d: rect(656, 346, 288, 178), depth: 0.1, tone: 0, light: 0.6 },
      { d: rect(600, 620, 400, 22) + rect(620, 642, 20, 120) + rect(960, 642, 20, 120), depth: 0.22, tone: 0.96 },
    ],
    glows: [{ x: 800, y: 440, r: 340, flicker: true, o: 0.55 }, { x: 240, y: 420, r: 280, o: 0.5 }, { x: 1370, y: 420, r: 280, o: 0.5 }],
  }
}

function chapel(): Art {
  let panes = "", pews = ""
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2
    panes += rect(800 + Math.cos(a) * 90 - 26, 300 + Math.sin(a) * 90 - 20, 52, 40)
  }
  for (let i = 0; i < 4; i++) {
    const y = 640 + i * 62, w = 280 + i * 46
    pews += rect(620 - w, y, w, 44) + rect(980, y, w, 44)
  }
  let side = ""
  for (const x of [90, 330, 1130, 1370]) side += gothic(x, 200, 150, 460)
  return {
    outdoors: false, fx: "embers",
    layers: [
      { d: full + circle(800, 300, 170) + side, depth: 0.03, tone: 0.32, hole: true },
      { d: panes, depth: 0.03, tone: 0, light: 0.32 },
      { d: `M0 900V40H1600V900H1440V160Q1440 60 1340 40H260Q160 60 160 160V900z`, depth: 0.14, tone: 0.72 },
      { d: rect(700, 580, 200, 60) + rect(740, 640, 120, 150) + rect(794, 430, 12, 150) + rect(760, 470, 80, 12), depth: 0.1, tone: 0.82 },
      { d: pews, depth: 0.2, tone: 0.92 },
      { d: candle(690, 580, 30) + candle(910, 580, 30), depth: 0.1, tone: 0.95 },
    ],
    glows: [{ x: 800, y: 300, r: 420, o: 0.5 }, { x: 730, y: 260, r: 190, o: 0.5, color: "#d8344a" }, { x: 870, y: 270, r: 190, o: 0.5, color: "#3a7ae0" }, { x: 800, y: 370, r: 170, o: 0.45, color: "#e0b040" }, { x: 690, y: 548, r: 130, flicker: true, o: 0.8, color: "#ffb070" }, { x: 910, y: 548, r: 130, flicker: true, o: 0.8, color: "#ffb070" }],
    moon: undefined,
  }
}

function cloister(r: Rng): Art {
  let arcade = ""
  for (let i = 0; i < 6; i++) arcade += arch(40 + i * 262, 230, 220, 500)
  let vines = ""
  for (let i = 0; i < 22; i++) {
    const x = r() * W, y = r() * 300
    vines += `M${f(x)} ${f(y)}q${f(30 - r() * 60)} ${f(60 + r() * 80)} ${f(10 - r() * 20)} ${f(140 + r() * 180)}q-6 8 -10 0q${f(10 - r() * 30)} -100 -12 -300z`
  }
  return {
    outdoors: true, fx: "spores", moon: [1000, 200],
    layers: [
      { d: ridge(r, 520, 50), depth: 0.03, tone: 0.2 },
      { d: full + arcade, depth: 0.08, tone: 0.62, hole: true },
      { d: vines, depth: 0.12, tone: 0.84 },
      { d: rect(0, 730, W, 170), depth: 0.1, tone: 0.56 },
      { d: `M640 800q0 -50 160 -50q160 0 160 50v30H640z` + rect(780, 640, 40, 120) + `M730 640q70 -44 140 0z`, depth: 0.2, tone: 0.92 },
      { d: `M0 900V680Q120 620 220 720T340 900z M1600 900V650Q1460 620 1380 730T1240 900z`, depth: 0.32, tone: 1, blur: 2 },
    ],
    glows: [{ x: 800, y: 640, r: 280, flicker: true, o: 0.5 }],
  }
}

function wreck(r: Rng): Art {
  let spires = ""
  for (const [x, h, w] of [[1120, 300, 46], [1190, 380, 56], [1260, 300, 46], [1050, 220, 36], [1330, 220, 36]] as const)
    spires += poly(x - w, 600, x - w, 600 - h * 0.7, x, 600 - h, x + w, 600 - h * 0.7, x + w, 600)
  return {
    outdoors: true, fx: "embers", moon: [420, 170],
    layers: [
      { d: ridge(r, 590, 60), depth: 0.03, tone: 0.2 },
      { d: spires + rect(1000, 520, 380, 90), depth: 0.04, tone: 0.3 },
      { d: ridge(r, 660, 50), depth: 0.07, tone: 0.42 },
      { d: ridge(r, 740, 40), depth: 0.12, tone: 0.66 },
      { d: `M170 780L300 560L700 470L1000 560L880 780z M300 560L240 400L340 380L420 530z M640 480L720 350L800 370L770 510z`, depth: 0.17, tone: 0.86 },
      { d: rect(420, 560, 40, 18) + rect(500, 544, 40, 18) + rect(580, 528, 40, 18), depth: 0.17, tone: 0, light: 0.5 },
      { d: `M0 900V800Q300 740 620 830T1200 800T1600 840V900z`, depth: 0.24, tone: 1 },
    ],
    glows: [{ x: 620, y: 620, r: 340, flicker: true, o: 0.75, color: "#ff8a4a" }, { x: 1180, y: 480, r: 220, o: 0.3 }],
  }
}

function street(r: Rng): Art {
  const row = (base: number, min: number, max: number, wmin: number) => {
    let d = `M0 ${H}`, x = 0
    while (x < W + 100) {
      const w = wmin + r() * 110, h = min + r() * (max - min)
      d += `L${f(x)} ${f(base - h)}L${f(x + w)} ${f(base - h)}`
      x += w
    }
    return d + `L${W + 100} ${H}z`
  }
  let windows = ""
  for (let i = 0; i < 30; i++) windows += rect(r() * W, 300 + r() * 320, 14, 22)
  return {
    outdoors: true, fx: "rain", moon: [1240, 160],
    layers: [
      { d: row(640, 160, 380, 70), depth: 0.04, tone: 0.3 },
      { d: windows, depth: 0.05, tone: 0, light: 0.4 },
      { d: row(720, 180, 300, 130), depth: 0.09, tone: 0.55 },
      { d: rect(0, 720, W, 180), depth: 0.12, tone: 0.72 },
      { d: rect(300, 300, 10, 440) + rect(300, 300, 90, 8) + rect(1240, 340, 10, 400) + rect(1160, 340, 90, 8), depth: 0.2, tone: 0.95 },
    ],
    glows: [{ x: 386, y: 330, r: 240, flicker: true, o: 0.75, color: "#ffc27a" }, { x: 1164, y: 370, r: 200, o: 0.6, color: "#ffc27a" }],
  }
}

function hills(r: Rng): Art {
  return {
    outdoors: true, fx: "fog", moon: [1100, 210],
    layers: [
      { d: ridge(r, 500, 80), depth: 0.03, tone: 0.2 },
      { d: ridge(r, 600, 60), depth: 0.07, tone: 0.42 },
      { d: ridge(r, 720, 40), depth: 0.13, tone: 0.7 },
      { d: `M360 760V560q-40 -30 -90 -40l6 -8q50 6 82 30q-8 -60 -46 -90l8 -6q46 34 54 86q16 -40 58 -60l4 8q-42 22 -52 74V760z`, depth: 0.2, tone: 0.96 },
      { d: ridge(r, 820, 24), depth: 0.3, tone: 1 },
    ],
    glows: [],
  }
}

function tavern(r: Rng): Art {
  let bottles = ""
  for (let i = 0; i < 22; i++) {
    const x = 180 + i * 17 + r() * 6, y = 330 + (i % 2) * 110, h = 34 + r() * 24
    bottles += rect(x, y - h, 11, h) + rect(x + 3, y - h - 12, 5, 12)
  }
  let stools = ""
  for (const x of [240, 400, 560]) stools += rect(x, 640, 70, 14) + rect(x + 8, 654, 10, 150) + rect(x + 52, 654, 10, 150)
  return {
    outdoors: false, fx: "embers",
    layers: [
      { d: full, depth: 0.03, tone: 0.3 },
      { d: rect(150, 330, 460, 10) + rect(150, 440, 460, 10), depth: 0.06, tone: 0.55 },
      { d: bottles, depth: 0.06, tone: 0.62 },
      { d: rect(960, 250, 380, 520) + rect(930, 230, 440, 34), depth: 0.08, tone: 0.62 },
      { d: arch(1030, 480, 240, 290), depth: 0.08, tone: 0, light: 0.95 },
      { d: `M1090 770l40-90l26 60l24-100l34 130z`, depth: 0.08, tone: 0.95 },
      { d: rect(0, 770, W, 130), depth: 0.1, tone: 0.55 },
      { d: floorboards(770), depth: 0.1, tone: 0.65 },
      { d: rect(120, 540, 620, 30) + rect(140, 570, 580, 220), depth: 0.14, tone: 0.82 },
      { d: stools, depth: 0.2, tone: 0.95 },
      { d: rect(820, 0, 4, 170) + poly(790, 170, 854, 170, 842, 220, 802, 220), depth: 0.2, tone: 0.9 },
    ],
    glows: [{ x: 1150, y: 640, r: 620, flicker: true, o: 1, color: "#ff9a4a" }, { x: 822, y: 220, r: 420, flicker: true, o: 0.8, color: "#ffc27a" }, { x: 380, y: 400, r: 320, o: 0.35, color: "#ffc27a" }],
  }
}

function ship(r: Rng): Art {
  let rails = ""
  for (let i = 0; i < 16; i++) rails += rect(i * 110, 700, 12, 130)
  return {
    outdoors: true, fx: "fog", moon: [420, 210],
    layers: [
      { d: ridge(r, 560, 26, 40), depth: 0.03, tone: 0.34 },
      { d: ridge(r, 610, 30, 50), depth: 0.05, tone: 0.5 },
      { d: rect(1000, 40, 26, 700) + rect(830, 120, 370, 12), depth: 0.14, tone: 0.86 },
      { d: `M846 134Q1010 330 846 520L1186 520Q1090 330 1186 134z`, depth: 0.14, tone: 0.7 },
      { d: poly(1010, 44, 1016, 40, 1570, 700, 1558, 704) + poly(1008, 44, 1014, 48, 572, 704, 556, 700), depth: 0.14, tone: 0.92 },
      { d: rect(0, 690, W, 16) + rails, depth: 0.2, tone: 0.95 },
      { d: rect(0, 800, W, 100), depth: 0.2, tone: 1 },
    ],
    glows: [{ x: 420, y: 540, r: 300, o: 0.3 }],
  }
}

function mine(r: Rng): Art {
  const layers: Layer[] = [{ d: full, depth: 0.02, tone: 0.2 }]
  for (const [w, h, tone] of [[300, 260, 0.36], [520, 430, 0.5], [800, 620, 0.68], [1240, 860, 0.9]] as const) {
    const x = 800 - w / 2, y = 760 - h, t = w * 0.05
    layers.push({ d: full + poly(x + 30, y + 30, x + w - 30, y + 30, x + w, 900, x, 900), depth: 0.04 + tone * 0.16, tone: tone * 0.8, hole: true },
      { d: rect(x, y, t, h + 140) + rect(x + w - t, y, t, h + 140) + poly(x - 20, y, x + w + 20, y, x + w + 20, y + t, x - 20, y + t), depth: 0.04 + tone * 0.16, tone })
  }
  let ties = ""
  for (let i = 0; i < 7; i++) {
    const t = i / 7, y = 640 + t * t * 260, w = 80 + t * 420
    ties += rect(800 - w, y, w * 2, 6 + t * 12)
  }
  layers.push({ d: ties + poly(760, 620, 776, 620, 500, 900, 440, 900) + poly(824, 620, 840, 620, 1160, 900, 1100, 900), depth: 0.2, tone: 0.92 },
    { d: rect(1020 + r() * 10, 330, 8, 60), depth: 0.18, tone: 0.9 })
  return { layers, outdoors: false, fx: "dust", glows: [{ x: 1024, y: 400, r: 460, flicker: true, o: 1, color: "#ffb070" }, { x: 800, y: 560, r: 340, o: 0.6 }, { x: 560, y: 420, r: 260, flicker: true, o: 0.6, color: "#ffb070" }] }
}

function castle(): Art {
  let far = "", near = ""
  for (const [x, w, y] of [[620, 34, 300], [946, 34, 300], [520, 50, 240], [1030, 50, 240]] as const) far += rect(x, y, w, 790 - y)
  for (const x of [150, 1370]) near += rect(x, 40, 90, 860)
  let banners = ""
  for (const x of [330, 1200]) banners += `M${x} 110h90v300l-45 -46l-45 46z`
  return {
    outdoors: false, fx: "embers",
    layers: [
      { d: full + gothic(690, 150, 220, 330), depth: 0.03, tone: 0.3, hole: true },
      { d: poly(560, 790, 1040, 790, 1500, 900, 100, 900), depth: 0.08, tone: 0.5 },
      { d: poly(740, 790, 860, 790, 1010, 900, 590, 900), depth: 0.08, tone: 0, light: 0.14 },
      { d: far, depth: 0.08, tone: 0.56 },
      { d: `M740 790V620Q740 590 770 590V520Q800 490 830 520V590Q860 590 860 620V790z`, depth: 0.1, tone: 0.82 },
      { d: banners, depth: 0.16, tone: 0.74 },
      { d: near + rect(0, 0, W, 44), depth: 0.3, tone: 1 },
    ],
    glows: [{ x: 800, y: 300, r: 340, o: 0.55 }, { x: 300, y: 520, r: 200, flicker: true, o: 0.5, color: "#ffa050" }, { x: 1300, y: 520, r: 200, flicker: true, o: 0.5, color: "#ffa050" }],
  }
}

function desert(r: Rng): Art {
  const dune = (y: number, a: number) => `M0 900V${f(y)}C400 ${f(y - a)} 700 ${f(y + a)} 1000 ${f(y - a * 0.3)}S1400 ${f(y + a * 0.5)} 1600 ${f(y - a * 0.4)}V900z`
  let columns = ""
  for (const [x, h] of [[980, 300], [1090, 230], [1200, 340], [1320, 160]] as const) columns += rect(x, 680 - h, 56, h) + rect(x - 8, 680 - h, 72, 16)
  return {
    outdoors: true, fx: "dust", moon: [340, 190],
    layers: [
      { d: dune(560, 40), depth: 0.03, tone: 0.2 },
      { d: columns + rect(960, 330, 310, 30), depth: 0.07, tone: 0.5 },
      { d: dune(650 + r() * 20, 50), depth: 0.09, tone: 0.46 },
      { d: dune(770, 60), depth: 0.16, tone: 0.76 },
      { d: poly(160, 900, 200, 690, 250, 660, 300, 720, 360, 900), depth: 0.3, tone: 1, blur: 2 },
    ],
    glows: [{ x: 340, y: 560, r: 340, o: 0.3 }],
  }
}

function train(r: Rng): Art {
  let wins = "", seats = "", racks = ""
  for (let i = 0; i < 4; i++) {
    const x = 90 + i * 380
    wins += rect(x, 230, 280, 230)
    seats += `M${x - 20} 900V620Q${x - 20} 590 ${x + 10} 590H${x + 70}Q${x + 100} 590 ${x + 100} 620V760H${x + 250}V900z`
    racks += rect(x - 30, 170, 340, 10)
  }
  return {
    outdoors: true, fx: "rain", moon: [860, 330],
    layers: [
      { d: full + wins, depth: 0.04, tone: 0.42, hole: true },
      { d: rect(0, 0, W, 130) + rect(0, 760, W, 140), depth: 0.05, tone: 0.56 },
      { d: racks, depth: 0.08, tone: 0.8 },
      { d: seats, depth: 0.16, tone: 0.92 },
      { d: rect(r() * 4 + 780, 60, 40, 24), depth: 0.06, tone: 0, light: 0.8 },
    ],
    glows: [{ x: 800, y: 80, r: 460, flicker: true, o: 0.45 }],
  }
}

function shore(r: Rng): Art {
  return {
    outdoors: true, fx: "fog", moon: [360, 180],
    layers: [
      { d: ridge(r, 590, 18, 40), depth: 0.03, tone: 0.34 },
      { d: ridge(r, 640, 22, 50), depth: 0.05, tone: 0.5 },
      { d: `M1100 900L1130 700L1240 640L1420 690L1600 620V900z`, depth: 0.1, tone: 0.78 },
      { d: poly(1250, 660, 1270, 300, 1340, 300, 1362, 660) + rect(1250, 270, 112, 30) + poly(1262, 270, 1306, 214, 1350, 270), depth: 0.1, tone: 0.84 },
      { d: rect(1278, 232, 56, 38), depth: 0.1, tone: 0, light: 0.95 },
      { d: `M0 900V780Q240 730 520 800T1000 840T1400 900z`, depth: 0.22, tone: 1 },
    ],
    glows: [{ x: 1306, y: 250, r: 300, flicker: true, o: 0.8 }, { x: 360, y: 640, r: 280, o: 0.3 }],
  }
}

function deadTree(r: Rng, x: number, base: number, h: number) {
  let d = poly(x - 14, base, x - 5, base - h, x + 5, base - h, x + 16, base)
  for (let i = 0; i < 6; i++) {
    const y = base - h * (0.4 + r() * 0.58), s = i % 2 ? 1 : -1, l = h * (0.16 + r() * 0.24), k = 0.3 + r() * 0.5
    d += poly(x, y - 3, x, y + 4, x + s * l, y - l * k)                                   // a branch, thin at the tip
    d += poly(x + s * l * 0.5, y - l * k * 0.5, x + s * l * 0.56, y - l * k * 0.4,        // and a twig off it
              x + s * l * 0.8, y - l * k * 1.5)
  }
  return d
}

function swamp(r: Rng): Art {
  return {
    outdoors: true, fx: "spores", moon: [1100, 180],
    layers: [
      { d: ridge(r, 560, 30), depth: 0.03, tone: 0.24 },
      { d: deadTree(r, 300, 660, 250) + deadTree(r, 980, 650, 200) + deadTree(r, 1260, 650, 280), depth: 0.08, tone: 0.5 },
      { d: rect(0, 650, W, 250), depth: 0.1, tone: 0.42 },
      { d: rect(0, 680, W, 4) + rect(200, 720, 420, 3) + rect(880, 760, 520, 3), depth: 0.1, tone: 0, light: 0.14 },
      { d: deadTree(r, 620, 830, 460) + `M0 900V800Q160 760 320 820T640 860V900z M1100 900Q1300 790 1600 780V900z`, depth: 0.22, tone: 0.96 },
    ],
    glows: [{ x: 820, y: 690, r: 200, flicker: true, o: 0.5 }, { x: 460, y: 720, r: 120, flicker: true, o: 0.45 }],
  }
}

function graveyard(r: Rng): Art {
  let stones = "", far = "", fence = rect(0, 610, W, 7)
  for (let i = 0; i < 12; i++) far += arch(40 + i * 134 + r() * 40, 590 + r() * 26, 44, 90)
  for (let i = 0; i < 7; i++) stones += arch(60 + i * 226 + r() * 60, 680 + r() * 50, 90, 200)
  stones += rect(778, 540, 22, 200) + rect(738, 590, 102, 20)
  for (let i = 0; i < 30; i++) fence += poly(i * 56, 680, i * 56 + 6, 590, i * 56 + 12, 680)
  return {
    outdoors: true, fx: "fog", moon: [1180, 170],
    layers: [
      { d: ridge(r, 540, 40), depth: 0.03, tone: 0.24 },
      { d: fence, depth: 0.06, tone: 0.5 },
      { d: far, depth: 0.08, tone: 0.56 },
      { d: ridge(r, 720, 16), depth: 0.1, tone: 0.66 },
      { d: stones, depth: 0.16, tone: 0.86 },
      { d: deadTree(r, 1460, 920, 760), depth: 0.3, tone: 1, blur: 2 },
    ],
    glows: [],
  }
}

function mansion(r: Rng): Art {
  let lit = ""
  for (const [x, y] of [[640, 410], [950, 410], [790, 540]] as const) if (r() > 0.25) lit += rect(x, y, 44, 76)
  return {
    outdoors: true, fx: "fog", moon: [330, 170],
    layers: [
      { d: ridge(r, 620, 40), depth: 0.03, tone: 0.24 },
      { d: deadTree(r, 240, 720, 340) + deadTree(r, 1390, 720, 390), depth: 0.06, tone: 0.5 },
      { d: `M500 720V360L560 250L620 360H980L1040 250L1100 360V720z M700 360L800 190L900 360z` + rect(1000, 190, 44, 90), depth: 0.1, tone: 0.8 },
      { d: lit, depth: 0.1, tone: 0, light: 0.8 },
      { d: arch(760, 590, 80, 130), depth: 0.1, tone: 1 },
      { d: `M0 900V730Q400 690 800 720T1600 700V900z`, depth: 0.16, tone: 0.92 },
    ],
    glows: lit ? [{ x: 800, y: 480, r: 260, flicker: true, o: 0.4, color: "#ffc27a" }] : [],
  }
}

// a little of the unexpected, so two rooms of the same kind differ
function props(r: Rng, outdoors: boolean): Layer | null {
  if (r() < 0.3) return null
  const x = r() < 0.5 ? 40 + r() * 240 : 1320 + r() * 220
  const y = 900
  const pick = Math.floor(r() * 4)
  const indoor = [
    rect(x, y - 150, 170, 150) + rect(x + 30, y - 240, 110, 90),                           // crates
    `M${f(x)} ${y}V${y - 140}Q${f(x)} ${y - 200} ${f(x + 60)} ${y - 200}Q${f(x + 120)} ${y - 200} ${f(x + 120)} ${y - 140}V${y}z`,   // barrel
    rect(x, y - 110, 130, 14) + rect(x + 8, y - 96, 12, 96) + rect(x + 110, y - 96, 12, 96) + rect(x + 110, y - 230, 12, 130),       // chair
    rect(x, y - 70, 170, 70) + rect(x + 14, y - 120, 140, 50) + rect(x + 34, y - 160, 90, 40),   // heaped books or boxes
  ]
  const outside = [
    `M${f(x)} ${y}Q${f(x + 30)} ${y - 150} ${f(x + 120)} ${y - 160}Q${f(x + 240)} ${y - 120} ${f(x + 250)} ${y}z`,   // boulder
    deadTree(r, x + 80, y + 20, 420),
    rect(x, y - 150, 16, 150) + rect(x + 120, y - 130, 16, 130) + poly(x - 20, y - 120, x + 160, y - 96, x + 160, y - 84, x - 20, y - 108),  // broken fence
    pine(r, x + 80, y + 40, 520),
  ]
  return { d: (outdoors ? outside : indoor)[pick], depth: 0.36, tone: 1, blur: 3 }
}

/** Weather and light the words ask for, in either language. */
export function readSky(text: string) {
  return {
    weather: /blizzard|snow|雪/i.test(text) ? "snow" : /rain|storm|downpour|雨|暴風/i.test(text) ? "rain"
      : /\bfog\b|mist|霧/i.test(text) ? "fog" : /smoke|ember|\bash\b|灰燼|濃煙|火星/i.test(text) ? "embers" : "",
    lightning: /lightning|thunder|雷|閃電/i.test(text),
    dark: /lights? (go|goes|went) out|pitch[- ]black|plunged into darkness|燈.{0,3}(滅|熄)|一片漆黑|陷入黑暗/i.test(text),
  }
}

// --- choosing a kit from the scene's own words ---

const KITS: Record<string, { words: RegExp; paint: (r: Rng, text: string) => Art }> = {
  train: { words: /\btrain\b|carriage|subway|railway|火車|車廂|地鐵|列車/i, paint: train },
  tavern: { words: /tavern|\binn\b|\bbar\b|pub\b|酒館|酒吧|酒舖|客棧/i, paint: tavern },
  ship: { words: /\bship\b|\bdeck\b|\bboat\b|vessel|甲板|船/i, paint: ship },
  mine: { words: /\bmine\b|mineshaft|tunnel|cave\b|caves\b|礦|隧道|洞穴|山洞/i, paint: mine },
  castle: { words: /castle|throne|keep\b|palace|fortress|城堡|王座|宮殿|要塞/i, paint: castle },
  desert: { words: /desert|dune|oasis|sands?\b|沙漠|沙丘|綠洲/i, paint: desert },
  shore: { words: /lighthouse|\bshore\b|beach|coast|cliff|燈塔|海邊|海灘|海岸|懸崖/i, paint: shore },
  swamp: { words: /swamp|marsh\b|bog\b|fen\b|沼澤|泥沼/i, paint: swamp },
  graveyard: { words: /graveyard|cemetery|grave\b|tombstone|墓園|墳場|墓地/i, paint: graveyard },
  mansion: { words: /outside the (house|manor)|mansion gate|front gate|estate|莊園|別墅|大宅外/i, paint: mansion },
  elevator: { words: /elevator|lift|電梯|升降機|𨋢/i, paint: elevator },
  abyss: { words: /abyss|void|pit|深淵|虛空|最終/i, paint: abyss },
  living: { words: /living room|television|sofa|couch|客廳|電視|螢幕|沙發|screen/i, paint: livingroom },
  bedroom: { words: /bedroom|bed|臥室|睡房|床|套房/i, paint: bedroom },
  attic: { words: /attic|閣樓|天台/i, paint: attic },
  cellar: { words: /cellar|crypt|catacomb|tomb|basement|sewer|地下|墓|地窖|地牢/i, paint: cellar },
  library: { words: /library|archive|records|athenaeum|圖書|檔案|書庫/i, paint: library },
  asylum: { words: /asylum|ward|hospital|corridor|hallway|sanatorium|走廊|迴廊走|醫院|病房|療養|保管庫/i, paint: corridor },
  lab: { words: /lab\b|laborator|factory|engine room|實驗|測試室|控制|機房|大堂/i, paint: lab },
  chapel: { words: /chapel|church|cathedral|monastery|shrine|altar room|禮拜|教堂|修道|神殿|符文|降神|占卜/i, paint: chapel },
  garden: { words: /garden|cloister|courtyard|花園|庭院/i, paint: cloister },
  wreck: { words: /crash|wreck|lander|battlefield|ruin|墜|殘骸|廢墟|戰場/i, paint: wreck },
  forest: { words: /forest|wood|pine|trail|camp|clearing|snow|林|樹|徑|營|雪|霜|空地/i, paint: forest },
  street: { words: /street|alley|city|town|harbou?r|docks|街|巷|城|鎮|碼頭/i, paint: street },
  hall: { words: /ground floor|manor|mansion|parlou?r|屋|宅|大廳|玄關|room|室|廳/i, paint: hall },
  office: { words: /office|study|desk|辦公|書房|事務所/i, paint: office },
}

export function chooseKit(name: string, text: string, art?: string) {
  if (art && KITS[art]) return art
  let best = "", score = 0
  for (const [k, kit] of Object.entries(KITS)) {
    const s = (kit.words.test(name) ? 3 : 0) + (kit.words.test(text) ? 1 : 0)
    if (s > score) { best = k; score = s }
  }
  return best
}

export function paintScene(name: string, text: string, art?: string): Art {
  const kit = chooseKit(name, text, art)
  const r = rng(hash(name + text))
  const picture = kit ? KITS[kit].paint(r, name + text) : hills(r)
  const extra = props(r, picture.outdoors)
  if (extra) picture.layers.push(extra)
  const sky = readSky(`${name} ${text}`)
  if (sky.weather) picture.fx = sky.weather
  return picture
}
