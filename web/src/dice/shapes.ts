// Polyhedral dice geometry. Each die is just a point cloud: faces come from its convex hull, so
// d4..d20 share one code path and physics + rendering always agree.
export type V3 = [number, number, number]
export type DieType = "d4" | "d6" | "d8" | "d10" | "d12" | "d20" | "d100"
export type Face = { verts: number[]; normal: V3; center: V3; up: V3; right: V3; radius: number }
export type Shape = { verts: V3[]; faces: Face[]; opposite: number[]; values: number[]; type: DieType }

const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
const cross = (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
const len = (a: V3) => Math.sqrt(dot(a, a))
const norm = (a: V3): V3 => { const l = len(a); return [a[0] / l, a[1] / l, a[2] / l] }
const scale = (a: V3, s: number): V3 => [a[0] * s, a[1] * s, a[2] * s]

const G = (1 + Math.sqrt(5)) / 2

function points(type: DieType): V3[] {
  if (type === "d4") return [[1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]]
  if (type === "d6") {
    const p: V3[] = []
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) p.push([x, y, z])
    return p
  }
  if (type === "d8") return [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
  if (type === "d10" || type === "d100") {
    // Pentagonal trapezohedron: ring height h is the value that makes each kite exactly flat.
    const c = Math.cos(Math.PI / 5)
    const h = (1 - c) / (1 + c)
    const p: V3[] = []
    for (let i = 0; i < 10; i++) {
      const a = (i * Math.PI) / 5
      p.push([Math.cos(a), i % 2 ? h : -h, Math.sin(a)])
    }
    p.push([0, 1, 0], [0, -1, 0])
    return p
  }
  if (type === "d12") {
    const p: V3[] = []
    const r = 1 / G
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) p.push([x, y, z])
    for (const a of [-r, r]) for (const b of [-G, G]) p.push([0, a, b], [a, b, 0], [b, 0, a])
    return p
  }
  const p: V3[] = []   // d20
  for (const a of [-1, 1]) for (const b of [-G, G]) p.push([0, a, b], [a, b, 0], [b, 0, a])
  return p
}

function hull(V: V3[]): { verts: number[]; normal: V3 }[] {
  const found = new Map<string, { verts: number[]; normal: V3 }>()
  const eps = 1e-6
  for (let i = 0; i < V.length; i++) for (let j = i + 1; j < V.length; j++) for (let k = j + 1; k < V.length; k++) {
    const raw = cross(sub(V[j], V[i]), sub(V[k], V[i]))
    if (len(raw) < eps) continue
    let n = norm(raw)
    let d = dot(n, V[i])
    const sides = V.map((p) => dot(n, p) - d)
    const above = sides.some((s) => s > eps), below = sides.some((s) => s < -eps)
    if (above && below) continue
    if (above) { n = scale(n, -1); d = -d }
    const members = V.map((_, m) => m).filter((m) => Math.abs(dot(n, V[m]) - d) < eps)
    found.set(members.join(), { verts: members, normal: n })
  }
  return [...found.values()]
}

function sizeOf(type: DieType) {
  return { d4: 1.25, d6: 1.12, d8: 1.05, d10: 1.02, d100: 1.02, d12: 1.08, d20: 1.12 }[type] * 0.85
}

export function faceCount(type: DieType) { return { d4: 4, d6: 6, d8: 8, d10: 10, d100: 10, d12: 12, d20: 20 }[type] }

const cache = new Map<DieType, Omit<Shape, "values">>()

function build(type: DieType) {
  if (cache.has(type)) return cache.get(type)!
  const raw = points(type)
  const r = Math.max(...raw.map(len))
  const verts = raw.map((p) => scale(p, sizeOf(type) / r))
  const faces: Face[] = hull(verts).map(({ verts: vs, normal }) => {
    const center = scale(vs.reduce<V3>((s, i) => [s[0] + verts[i][0], s[1] + verts[i][1], s[2] + verts[i][2]], [0, 0, 0]), 1 / vs.length)
    const a = norm(sub(verts[vs[0]], center)), b = cross(normal, a)
    const sorted = [...vs].sort((p, q) => {
      const P = sub(verts[p], center), Q = sub(verts[q], center)
      return Math.atan2(dot(P, b), dot(P, a)) - Math.atan2(dot(Q, b), dot(Q, a))
    })
    // "up" for the printed number: a corner, except d6 (an edge) and d10 (the long kite tip)
    let up: V3
    if (type === "d6") {
      const mid = scale([verts[sorted[0]][0] + verts[sorted[1]][0], verts[sorted[0]][1] + verts[sorted[1]][1], verts[sorted[0]][2] + verts[sorted[1]][2]], 0.5)
      up = norm(sub(mid, center))
    } else if (type === "d10" || type === "d100") {
      const tip = sorted.reduce((best, i) => (len(sub(verts[i], center)) > len(sub(verts[best], center)) ? i : best), sorted[0])
      up = norm(sub(verts[tip], center))
    } else {
      up = norm(sub(verts[sorted[0]], center))
    }
    const radius = Math.max(...sorted.map((i) => len(sub(verts[i], center))))
    return { verts: sorted, normal, center, up, right: cross(up, normal), radius }
  })
  const opposite = faces.map((f) => {
    let best = -1, low = 2
    faces.forEach((g, j) => { const c = dot(f.normal, g.normal); if (c < low) { low = c; best = j } })
    return best
  })
  const shape = { verts, faces, opposite, type }
  cache.set(type, shape)
  return shape
}

const shuffle = <T,>(a: T[]) => {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]] }
  return a
}

/** A die with printed values. Opposite faces add up the way real dice do. d4 values sit on vertices. */
export function makeShape(type: DieType): Shape {
  const s = build(type)
  const n = faceCount(type)
  if (type === "d4") return { ...s, values: shuffle([1, 2, 3, 4]) }
  const low = type === "d10" ? 0 : type === "d100" ? 0 : 1
  const step = type === "d100" ? 10 : 1
  const nums = Array.from({ length: n }, (_, i) => low + i * step)
  const values = new Array(n).fill(-1)
  const pairs = shuffle(Array.from({ length: n / 2 }, (_, i) => i))
  s.faces.forEach((_, f) => {
    if (values[f] >= 0) return
    const p = pairs.pop()!
    const flip = Math.random() < 0.5
    values[f] = nums[flip ? p : n - 1 - p]
    values[s.opposite[f]] = nums[flip ? n - 1 - p : p]
  })
  return { ...s, values }
}

/** Reprint a die so the given face/vertex shows `value`, keeping the opposite-faces rule. */
export function reprint(shape: Shape, top: number, value: number) {
  const v = shape.values
  const from = v.indexOf(value)
  if (from < 0 || from === top) return
  ;[v[from], v[top]] = [v[top], v[from]]
  if (shape.type === "d4") return
  const a = shape.opposite[from], b = shape.opposite[top]
  if (a !== top && b !== from) [v[a], v[b]] = [v[b], v[a]]
}

export function label(type: DieType, value: number) {
  if (type === "d100") return String(value).padStart(2, "0")
  return String(value)
}
