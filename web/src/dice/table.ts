// The dice table: three.js for looks, cannon-es for physics.
// The trick that keeps dice honest AND physical: the whole throw is simulated first, in a few
// milliseconds. We see which face ends up on top, reprint the die so that face shows the number
// the server rolled, then play the recording back. Real tumbling, server's number, every time.
import * as CANNON from "cannon-es"
import * as THREE from "three"
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js"
import { label, makeShape, reprint, type DieType, type Shape } from "./shapes"

export type DieSpec = { die: DieType; value?: number; kept?: boolean }

const STYLE: Record<string, { base: string; ink: string }> = {
  dark: { base: "#17141d", ink: "#ecd28a" },
  blood: { base: "#4a0f16", ink: "#f4dfa8" },
}
const FONT: Record<DieType, number> = { d4: 46, d6: 130, d8: 92, d10: 74, d100: 60, d12: 96, d20: 66 }

// --- face textures (one per printed number, shared between dice) ---

const textures = new Map<string, THREE.CanvasTexture>()
const backgrounds = new Map<string, HTMLCanvasElement>()

function background(style: string) {
  if (backgrounds.has(style)) return backgrounds.get(style)!
  const c = document.createElement("canvas")
  c.width = c.height = 256
  const g = c.getContext("2d")!
  g.fillStyle = STYLE[style].base
  g.fillRect(0, 0, 256, 256)
  // resin swirls, so the faces catch light unevenly
  for (let i = 0; i < 26; i++) {
    g.strokeStyle = `rgba(255,${200 + i},${150 + i * 2},${0.015 + Math.random() * 0.035})`
    g.lineWidth = 2 + Math.random() * 16
    g.beginPath()
    g.moveTo(Math.random() * 256, Math.random() * 256)
    g.bezierCurveTo(Math.random() * 256, Math.random() * 256, Math.random() * 256, Math.random() * 256, Math.random() * 256, Math.random() * 256)
    g.stroke()
  }
  backgrounds.set(style, c)
  return c
}

function texture(key: string, style: string, draw: (g: CanvasRenderingContext2D) => void) {
  const id = `${style}|${key}`
  if (textures.has(id)) return textures.get(id)!
  const c = document.createElement("canvas")
  c.width = c.height = 256
  const g = c.getContext("2d")!
  g.drawImage(background(style), 0, 0)
  g.fillStyle = STYLE[style].ink
  g.shadowColor = "rgba(0,0,0,.6)"
  g.shadowBlur = 5
  g.textAlign = "center"
  g.textBaseline = "middle"
  draw(g)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 8
  textures.set(id, t)
  return t
}

function numberTexture(type: DieType, value: number, style: string) {
  const text = label(type, value)
  return texture(`${type}:${text}`, style, (g) => {
    g.font = `bold ${FONT[type]}px Georgia, serif`
    const y = type === "d10" || type === "d100" ? 150 : type === "d8" || type === "d20" ? 142 : 132   // optical centre
    g.fillText(text, 128, y)
    if (["d10", "d12", "d20"].includes(type) && (text === "6" || text === "9")) {
      g.fillRect(128 - FONT[type] * 0.22, y + FONT[type] * 0.42, FONT[type] * 0.44, 5)
    }
  })
}

function cornerTexture(type: DieType, labels: number[], style: string) {
  return texture(`${type}:${labels.join()}`, style, (g) => {
    g.font = `bold ${FONT[type]}px Georgia, serif`
    labels.forEach((n, i) => {
      g.save()
      g.translate(128, 128)
      g.rotate((-i * 2 * Math.PI) / 3)
      g.fillText(String(n), 0, -62)
      g.restore()
    })
  })
}

type Die = { spec: DieSpec; shape: Shape; mesh: THREE.Mesh; style: string; materials: THREE.MeshPhysicalMaterial[] }

function printFaces(d: Die) {
  const { shape, materials, style } = d
  shape.faces.forEach((f, i) => {
    materials[i].map = shape.type === "d4"
      ? cornerTexture("d4", f.verts.map((v) => shape.values[v]), style)
      : numberTexture(shape.type, shape.values[i], style)
    materials[i].needsUpdate = true
  })
}

function buildDie(spec: DieSpec, style: string, gold: THREE.Color): Die {
  const shape = makeShape(spec.die)
  const pos: number[] = [], nor: number[] = [], uv: number[] = []
  const geo = new THREE.BufferGeometry()
  let start = 0
  shape.faces.forEach((f, i) => {
    const r = f.radius * 1.03
    const push = (v: number) => {
      const p = shape.verts[v]
      pos.push(...p); nor.push(...f.normal)
      const d = [p[0] - f.center[0], p[1] - f.center[1], p[2] - f.center[2]]
      uv.push(0.5 + (d[0] * f.right[0] + d[1] * f.right[1] + d[2] * f.right[2]) / (2 * r),
              0.5 + (d[0] * f.up[0] + d[1] * f.up[1] + d[2] * f.up[2]) / (2 * r))
    }
    for (let t = 1; t < f.verts.length - 1; t++) { push(f.verts[0]); push(f.verts[t]); push(f.verts[t + 1]) }
    geo.addGroup(start, (f.verts.length - 2) * 3, i)
    start += (f.verts.length - 2) * 3
  })
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3))
  geo.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3))
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2))
  const materials = shape.faces.map(() => new THREE.MeshPhysicalMaterial({
    roughness: 0.42, metalness: 0, clearcoat: 0.7, clearcoatRoughness: 0.2, envMapIntensity: 0.32,
  }))
  const mesh = new THREE.Mesh(geo, materials)
  mesh.castShadow = true
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 5),
    new THREE.LineBasicMaterial({ color: gold, transparent: true, opacity: 0.4 })))
  const die = { spec, shape, mesh, style, materials }
  printFaces(die)
  return die
}

// --- clatter, timed to the real collisions ---

let audio: AudioContext | null = null

export function unlockAudio() {
  try { audio ??= new AudioContext(); audio.resume() } catch { /* no audio, no problem */ }
}

function clack(speed: number) {
  if (!audio || audio.state !== "running") return
  const gain = Math.min(0.5, (speed / 22) * 0.5)
  if (gain < 0.02) return
  const buf = audio.createBuffer(1, audio.sampleRate * 0.03, audio.sampleRate)
  const d = buf.getChannelData(0)
  for (let j = 0; j < d.length; j++) d[j] = (Math.random() * 2 - 1) * (1 - j / d.length) ** 2
  const src = audio.createBufferSource(); src.buffer = buf
  const bp = audio.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1500 + Math.random() * 2600; bp.Q.value = 1.4
  const g = audio.createGain(); g.gain.value = gain
  src.connect(bp); bp.connect(g); g.connect(audio.destination); src.start()
}

// --- the scene ---

type Recording = { frames: Float32Array[]; hits: { frame: number; speed: number }[]; tops: number[]; flat: boolean }

const FPS = 60
const lerp = (a: number, b: number, t: number) => a + (b - a) * t

export class DiceScene {
  renderer: THREE.WebGLRenderer
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100)
  dice: Die[] = []
  bounds = { w: 8, top: -5, bottom: 5 }
  private gold = new THREE.Color("#c9a96e")
  private glow = new THREE.PointLight("#ffffff", 0, 30)
  private raf = 0
  private ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), -3)
  private hold: THREE.Vector3 | null = null
  private playback: { rec: Recording; t0: number; last: number; done: () => void } | null = null
  private clock = new THREE.Clock()

  constructor(private canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.0
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    pmrem.dispose()

    const key = new THREE.DirectionalLight("#fff0d8", 2.6)
    key.position.set(-6, 18, 4)
    key.castShadow = true
    key.shadow.mapSize.set(2048, 2048)
    Object.assign(key.shadow.camera, { left: -22, right: 22, top: 22, bottom: -22, far: 50 })
    key.shadow.radius = 5
    this.scene.add(key, this.glow)
    this.glow.position.set(0, 4, 0)

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.ShadowMaterial({ opacity: 0.55 }))
    floor.rotation.x = -Math.PI / 2
    floor.receiveShadow = true
    this.scene.add(floor)

    this.resize()
    addEventListener("resize", this.resize)
    this.loop()
  }

  resize = () => {
    const w = this.canvas.clientWidth || innerWidth, h = this.canvas.clientHeight || innerHeight
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    this.camera.position.set(0, w < h ? 34 : 24, w < h ? 9 : 6)
    this.camera.lookAt(0, 0, 0.3)
    this.camera.updateProjectionMatrix()
    this.camera.updateMatrixWorld()
    const corner = (x: number, y: number) => this.worldAt(x, y, 0)
    const tl = corner(-1, 1), bl = corner(-1, -1)
    this.bounds = { w: Math.abs(tl.x) - 0.3, top: tl.z + 0.4, bottom: bl.z - 0.4 }
  }

  /** Where a screen point (-1..1) hits a flat level at this height. */
  private worldAt(x: number, y: number, height: number) {
    const ray = new THREE.Raycaster()
    ray.setFromCamera(new THREE.Vector2(x, y), this.camera)
    this.ground.constant = -height
    return ray.ray.intersectPlane(this.ground, new THREE.Vector3()) ?? new THREE.Vector3()
  }

  /** Lay these dice out, ready to be picked up. */
  setDice(specs: DieSpec[]) {
    for (const d of this.dice) this.scene.remove(d.mesh)
    this.dice = specs.map((spec) => buildDie(spec, spec.die === "d100" ? "blood" : "dark", this.gold))
    this.dice.forEach((d, i) => {
      d.mesh.position.set((i - (specs.length - 1) / 2) * 2.3, 1.3, this.bounds.bottom * 0.55)
      d.mesh.quaternion.random()
      this.scene.add(d.mesh)
    })
  }

  grab(x: number, y: number) { this.hold = this.worldAt(x, y, 3.2) }
  release() { this.hold = null }

  /** Throw with a swipe (world units/s), or a random throw from the side when none is given. */
  async throwDice(values: number[], swipe?: { vx: number; vz: number }) {
    this.hold = null
    const { w, top, bottom } = this.bounds
    const side = Math.random() < 0.5 ? -1 : 1
    const starts = this.dice.map((d, i) => (swipe
      ? d.mesh.position.clone().setY(Math.max(d.mesh.position.y, 1.8))
      : new THREE.Vector3(side * (w - 1.6), 3 + i * 0.4, lerp(top, bottom, 0.3 + Math.random() * 0.4) + i * 1.1)))
    starts.forEach((p) => {
      p.x = THREE.MathUtils.clamp(p.x, -w + 1.2, w - 1.2)
      p.z = THREE.MathUtils.clamp(p.z, top + 1.2, bottom - 1.2)
    })
    let vel = swipe ? new THREE.Vector3(swipe.vx, -3, swipe.vz) : new THREE.Vector3(-side * 26, -2, (Math.random() - 0.5) * 8)
    const speed = vel.length()
    if (speed < 18) vel = (speed > 2 ? vel : new THREE.Vector3((Math.random() - 0.5) * 8, -3, -18)).setLength(18)
    if (speed > 44) vel.setLength(44)

    let rec = this.simulate(starts, vel)
    for (let tries = 0; !rec.flat && tries < 6; tries++) rec = this.simulate(starts, vel)   // never accept a cocked die

    this.dice.forEach((d, i) => {
      const v = d.spec.die === "d10" ? values[i] % 10 : values[i]
      reprint(d.shape, rec.tops[i], v)
      printFaces(d)
    })
    if (this.instant) { this.pose(rec.frames[rec.frames.length - 1]); return }
    await new Promise<void>((done) => { this.playback = { rec, t0: performance.now(), last: -1, done } })
  }

  /** What each die actually shows, read from its final pose. The tests compare this with the server. */
  readTops() {
    const up = new THREE.Vector3()
    return this.dice.map((d) => {
      if (d.shape.type === "d4") {
        let best = 0, high = -9
        d.shape.verts.forEach((v, n) => { const y = up.set(...v).applyQuaternion(d.mesh.quaternion).y; if (y > high) { high = y; best = n } })
        return d.shape.values[best]
      }
      let best = 0, high = -2
      d.shape.faces.forEach((f, n) => { const y = up.set(...f.normal).applyQuaternion(d.mesh.quaternion).y; if (y > high) { high = y; best = n } })
      return d.shape.values[best]
    })
  }

  instant = false   // tests: skip the replay

  private simulate(starts: THREE.Vector3[], vel: THREE.Vector3): Recording {
    const { w, top, bottom } = this.bounds
    const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -42, 0) })
    world.allowSleep = true
    world.defaultContactMaterial.friction = 0.28
    world.defaultContactMaterial.restitution = 0.34
    ;(world.solver as CANNON.GSSolver).iterations = 20
    const wall = (x: number, y: number, z: number, rx: number, ry: number) => {
      const b = new CANNON.Body({ mass: 0, shape: new CANNON.Plane() })
      b.position.set(x, y, z)
      b.quaternion.setFromEuler(rx, ry, 0)
      world.addBody(b)
    }
    wall(0, 0, 0, -Math.PI / 2, 0)        // floor
    wall(0, 16, 0, Math.PI / 2, 0)        // ceiling
    wall(-w, 0, 0, 0, Math.PI / 2)
    wall(w, 0, 0, 0, -Math.PI / 2)
    wall(0, 0, top, 0, 0)
    wall(0, 0, bottom, 0, Math.PI)

    const hits: Recording["hits"] = []
    const frames: Float32Array[] = []
    let frame = 0
    const bodies = this.dice.map((d, i) => {
      const shape = new CANNON.ConvexPolyhedron({
        vertices: d.shape.verts.map((v) => new CANNON.Vec3(...v)),
        faces: d.shape.faces.map((f) => f.verts),
      })
      const b = new CANNON.Body({ mass: 1, shape, angularDamping: 0.08, linearDamping: 0.06, allowSleep: true,
        sleepSpeedLimit: 0.18, sleepTimeLimit: 0.2 })
      b.position.set(starts[i].x + i * 0.05, starts[i].y, starts[i].z)
      const q = d.mesh.quaternion
      b.quaternion.set(q.x, q.y, q.z, q.w)
      b.velocity.set(vel.x + (Math.random() - 0.5) * 4, vel.y, vel.z + (Math.random() - 0.5) * 4)
      const spin = () => (Math.random() - 0.5) * 44
      b.angularVelocity.set(spin(), spin(), spin())
      b.addEventListener("collide", (e: { contact: CANNON.ContactEquation }) => {
        hits.push({ frame, speed: Math.abs(e.contact.getImpactVelocityAlongNormal()) })
      })
      world.addBody(b)
      return b
    })

    const MAX = FPS * 7
    for (; frame < MAX; frame++) {
      world.step(1 / FPS)
      const f = new Float32Array(bodies.length * 7)
      bodies.forEach((b, i) => {
        f.set([b.position.x, b.position.y, b.position.z, b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w], i * 7)
      })
      frames.push(f)
      if (bodies.every((b) => b.sleepState === CANNON.Body.SLEEPING)) break
    }

    let flat = frame < MAX
    const up = new THREE.Vector3()
    const tops = this.dice.map((d, i) => {
      const q = new THREE.Quaternion(...bodies[i].quaternion.toArray())
      if (d.shape.type === "d4") {   // read the corner pointing at the sky
        let best = 0, high = -9
        d.shape.verts.forEach((v, n) => { const y = up.set(...v).applyQuaternion(q).y; if (y > high) { high = y; best = n } })
        flat &&= high / Math.hypot(...d.shape.verts[best]) > 0.97
        return best
      }
      let best = 0, high = -2
      d.shape.faces.forEach((f, n) => { const y = up.set(...f.normal).applyQuaternion(q).y; if (y > high) { high = y; best = n } })
      flat &&= high > 0.985
      return best
    })
    return { frames, hits, tops, flat }
  }

  /** After landing: dim dice that didn't count, light the table in the result's colour. */
  celebrate(color: string, keptFlags: boolean[]) {
    this.dice.forEach((d, i) => {
      if (keptFlags[i] === false) d.materials.forEach((m) => { m.color.set("#555555"); m.clearcoat = 0.2 })
    })
    this.glow.color.set(color)
    this.glow.intensity = 90
  }

  private pose(f: Float32Array) {
    this.dice.forEach((d, i) => {
      d.mesh.position.set(f[i * 7], f[i * 7 + 1], f[i * 7 + 2])
      d.mesh.quaternion.set(f[i * 7 + 3], f[i * 7 + 4], f[i * 7 + 5], f[i * 7 + 6])
    })
  }

  private loop = () => {
    this.raf = requestAnimationFrame(this.loop)
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const now = performance.now()
    if (this.playback) {
      const p = this.playback
      const idx = Math.floor(((now - p.t0) / 1000) * FPS)
      const f = p.rec.frames[Math.min(idx, p.rec.frames.length - 1)]
      this.pose(f)
      for (const h of p.rec.hits) if (h.frame > p.last && h.frame <= idx) clack(h.speed)
      p.last = idx
      if (idx >= p.rec.frames.length) { this.playback = null; p.done() }
    } else if (this.hold) {
      const n = this.dice.length
      this.dice.forEach((d, i) => {
        const a = (i / Math.max(n, 1)) * Math.PI * 2 + now / 90
        const tx = this.hold!.x + Math.cos(a) * (n > 1 ? 1.2 : 0.15), tz = this.hold!.z + Math.sin(a) * (n > 1 ? 1.2 : 0.15)
        d.mesh.position.set(lerp(d.mesh.position.x, tx, 0.35), lerp(d.mesh.position.y, this.hold!.y, 0.3), lerp(d.mesh.position.z, tz, 0.35))
        d.mesh.rotation.x += dt * 14; d.mesh.rotation.y += dt * 11
      })
    } else if (!this.settled) {
      this.dice.forEach((d, i) => {   // waiting on the table: a slow, tempting turn
        d.mesh.rotation.y += dt * 0.5
        d.mesh.position.y = 1.3 + Math.sin(now / 700 + i) * 0.12
      })
    }
    this.glow.intensity *= 0.985
    this.renderer.render(this.scene, this.camera)
  }

  settled = false

  dispose() {
    cancelAnimationFrame(this.raf)
    removeEventListener("resize", this.resize)
    for (const d of this.dice) { d.mesh.geometry.dispose(); d.materials.forEach((m) => m.dispose()) }
    this.renderer.dispose()
  }
}
