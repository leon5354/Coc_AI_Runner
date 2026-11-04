// The living backdrop: GPU-drawn sky and fog behind code-drawn silhouettes, with weather on top
// and a little parallax as the mouse moves. Nothing here is an image file.
import { useEffect, useMemo, useRef } from "react"
import { paintScene, readSky, type Art } from "./kits"

export const PALETTE: Record<string, { top: string; bottom: string; fog: string; far: string; near: string; light: string }> = {
  daylight: { top: "#39414f", bottom: "#8d8672", fog: "#c9bda2", far: "#5a5a5e", near: "#121318", light: "#ffe3a8" },
  dusk: { top: "#1d1533", bottom: "#a34b3c", fog: "#e08a55", far: "#4a2c48", near: "#0c0911", light: "#ffb36e" },
  night: { top: "#04060e", bottom: "#132242", fog: "#33507c", far: "#1b2a46", near: "#04050a", light: "#a9c8ff" },
  unearthly: { top: "#040c09", bottom: "#123a30", fog: "#4f9a72", far: "#123a30", near: "#030706", light: "#8dffc4" },
}

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
function mix(a: string, b: string, t: number) {
  const A = hex(a), B = hex(b)
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(",")})`
}

const FRAG = `precision mediump float;
uniform vec2 res; uniform float time; uniform vec3 top, bottom, fog; uniform vec2 moon; uniform float hasMoon;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
void main(){
  vec2 uv=gl_FragCoord.xy/res; float ar=res.x/res.y; vec2 p=vec2(uv.x*ar,uv.y);
  vec3 c=mix(bottom,top,smoothstep(0.,.95,uv.y));
  float t=time*.018;
  float stars=step(.9975,hash(floor(p*340.)))*smoothstep(.25,.9,uv.y)*(.5+.5*sin(time+hash(floor(p*340.))*40.));
  c+=stars*.75*hasMoon;
  vec2 m=vec2(moon.x*ar,moon.y); float d=distance(p,m);
  c+=hasMoon*(smoothstep(.092,.086,d)*vec3(.95,.93,.82)*(.82+.18*fbm(p*16.))+exp(-d*5.)*fog*.62);
  float q=fbm(p*1.6+vec2(t,t*.4));
  float cloud=fbm(p*2.1+vec2(q*1.5+t*1.6,q-t*.5));
  c=mix(c,fog*.72,smoothstep(.42,.95,cloud)*.68*smoothstep(0.,.5,uv.y+.1));
  float mist=fbm(vec2(p.x*1.4-t*2.4,p.y*3.4+t));
  c=mix(c,fog,smoothstep(.34,.86,mist)*(1.-smoothstep(.05,.62,uv.y))*.72);
  gl_FragColor=vec4(c,1.);
}`

function Sky({ mood, art }: { mood: string; art: Art }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = ref.current!
    const gl = canvas.getContext("webgl", { antialias: false })
    if (!gl) return
    const shader = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s }
    const prog = gl.createProgram()!
    gl.attachShader(prog, shader(gl.VERTEX_SHADER, "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}"))
    gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FRAG))
    gl.linkProgram(prog)
    gl.useProgram(prog)
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer())
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const a = gl.getAttribLocation(prog, "a")
    gl.enableVertexAttribArray(a)
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0)
    const u = (n: string) => gl.getUniformLocation(prog, n)
    const pal = PALETTE[mood] ?? PALETTE.night
    const col = (n: string, h: string) => gl.uniform3fv(u(n), hex(h).map((v) => v / 255))
    col("top", pal.top); col("bottom", pal.bottom); col("fog", pal.fog)
    gl.uniform1f(u("hasMoon"), art.moon && art.outdoors && mood !== "daylight" ? 1 : 0)
    if (art.moon) gl.uniform2f(u("moon"), art.moon[0] / 1600, 1 - art.moon[1] / 900)
    const resize = () => {
      // ponytail: half resolution at 30fps. Fog is soft, nobody can tell, and it stays cool on laptops.
      canvas.width = Math.max(320, innerWidth >> 1); canvas.height = Math.max(180, innerHeight >> 1)
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(u("res"), canvas.width, canvas.height)
    }
    resize()
    addEventListener("resize", resize)
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches
    let raf = 0, last = 0
    const draw = (t: number) => {
      raf = requestAnimationFrame(draw)
      if (t - last < 33) return
      last = t
      gl.uniform1f(u("time"), t / 1000)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
      if (still) cancelAnimationFrame(raf)
    }
    gl.uniform1f(u("time"), 40)
    gl.drawArrays(gl.TRIANGLES, 0, 3)       // first frame right away, even in a background tab
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize) }
  }, [mood, art])
  return <canvas ref={ref} className="art-sky" />
}

type P = { x: number; y: number; v: number; s: number; o: number }

/** Weather: rain, snow, dust, embers, spores, sparks, fog. */
function Weather({ fx, light }: { fx: string; light: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const canvas = ref.current!
    const g = canvas.getContext("2d")!
    const count = { rain: 240, snow: 170, dust: 70, embers: 60, spores: 90, sparks: 26, fog: 26 }[fx] ?? 40
    const resize = () => { canvas.width = innerWidth; canvas.height = innerHeight }
    resize()
    addEventListener("resize", resize)
    const spawn = (y = Math.random() * canvas.height): P => ({
      x: Math.random() * canvas.width, y, v: 0.4 + Math.random(), s: 0.5 + Math.random() * 2, o: Math.random(),
    })
    const ps = Array.from({ length: count }, () => spawn())
    let raf = 0
    const draw = (t: number) => {
      raf = requestAnimationFrame(draw)
      g.clearRect(0, 0, canvas.width, canvas.height)
      for (const p of ps) {
        if (fx === "rain") {
          p.y += 19 * p.v; p.x -= 4 * p.v
          g.strokeStyle = `rgba(190,210,235,${0.1 + p.o * 0.2})`; g.lineWidth = 1
          g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(p.x + 3 * p.v, p.y - 14 * p.v); g.stroke()
        } else if (fx === "snow") {
          p.y += p.v * 1.3; p.x += Math.sin(t / 900 + p.o * 9) * 0.9 - 0.5
          g.fillStyle = `rgba(235,242,255,${0.35 + p.o * 0.5})`
          g.beginPath(); g.arc(p.x, p.y, p.s, 0, 7); g.fill()
        } else if (fx === "embers" || fx === "sparks") {
          p.y -= p.v * (fx === "sparks" ? 2.4 : 1.1); p.x += Math.sin(t / 500 + p.o * 9) * 0.8
          const a = (0.4 + 0.6 * Math.sin(t / 240 + p.o * 20)) * Math.min(1, p.y / 300)
          g.fillStyle = fx === "sparks" ? `rgba(170,225,255,${a})` : `rgba(255,${130 + p.o * 80},60,${a})`
          g.beginPath(); g.arc(p.x, p.y, p.s * 0.9, 0, 7); g.fill()
        } else if (fx === "fog") {
          p.x += p.v * 0.3
          const r = 170 + p.s * 90
          const grad = g.createRadialGradient(p.x, p.y, 0, p.x, p.y, r)
          grad.addColorStop(0, `rgba(190,205,215,${0.035 + p.o * 0.03})`); grad.addColorStop(1, "rgba(190,205,215,0)")
          g.fillStyle = grad; g.fillRect(p.x - r, p.y - r, r * 2, r * 2)
        } else {
          p.y -= fx === "spores" ? p.v * 0.4 : 0.05; p.x += Math.sin(t / 1500 + p.o * 12) * 0.35 + 0.05
          g.fillStyle = light
          g.globalAlpha = (0.12 + p.o * 0.3) * (0.6 + 0.4 * Math.sin(t / 900 + p.o * 30))
          g.beginPath(); g.arc(p.x, p.y, p.s * 0.75, 0, 7); g.fill()
          g.globalAlpha = 1
        }
        if (p.y > canvas.height + 20) Object.assign(p, spawn(-20))
        if (p.y < -20) Object.assign(p, spawn(canvas.height + 10))
        if (p.x < -200) p.x = canvas.width + 100
        if (p.x > canvas.width + 200) p.x = -100
      }
    }
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize) }
  }, [fx, light])
  return <canvas ref={ref} className="art-weather" />
}

export function SceneArt({ name, text, art: forced, mood, weather = true, story = "" }: {
  name: string; text: string; art?: string; mood: string; weather?: boolean
  story?: string     // the Keeper's latest words: storms and blackouts follow the story live
}) {
  const art = useMemo(() => paintScene(name, text, forced), [name, text, forced])
  const live = useMemo(() => readSky(story), [story])
  const pal = PALETTE[mood] ?? PALETTE.night
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const move = (e: PointerEvent) => {
      root.current?.style.setProperty("--px", String(e.clientX / innerWidth - 0.5))
      root.current?.style.setProperty("--py", String(e.clientY / innerHeight - 0.5))
    }
    addEventListener("pointermove", move)
    return () => removeEventListener("pointermove", move)
  }, [])

  return (
    <div className="scene-art" ref={root}>
      <Sky mood={mood} art={art} />
      <svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice" className="art-svg">
        <defs>
          <filter id="b1"><feGaussianBlur stdDeviation="1" /></filter>
          <filter id="b2"><feGaussianBlur stdDeviation="2.4" /></filter>
          <filter id="b3"><feGaussianBlur stdDeviation="5" /></filter>
          <linearGradient id="floorfade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0.55" stopColor={pal.near} stopOpacity="0" /><stop offset="1" stopColor={pal.near} stopOpacity="0.85" />
          </linearGradient>
          {art.glows.map((g, i) => (
            <radialGradient key={i} id={`glow${i}`}>
              <stop offset="0" stopColor={g.color ?? pal.light} stopOpacity={g.o ?? 0.6} />
              <stop offset="0.35" stopColor={g.color ?? pal.light} stopOpacity={(g.o ?? 0.6) * 0.34} />
              <stop offset="1" stopColor={g.color ?? pal.light} stopOpacity="0" />
            </radialGradient>
          ))}
        </defs>
        {art.layers.filter((l) => l.d).map((l, i) => (
          <g key={i} className="art-layer" style={{ "--d": l.depth } as React.CSSProperties}>
            <path d={l.d} fill={l.light !== undefined && l.light > 0 ? pal.light : mix(pal.far, pal.near, l.tone)}
              fillOpacity={l.light !== undefined ? l.light : 1}
              fillRule={l.hole ? "evenodd" : "nonzero"} filter={l.blur ? `url(#b${l.blur})` : undefined} />
          </g>
        ))}
        {art.glows.map((g, i) => (
          <circle key={i} cx={g.x} cy={g.y} r={g.r} fill={`url(#glow${i})`} className={g.flicker ? "art-flicker" : ""}
            style={{ mixBlendMode: "screen", animationDelay: `${i * -0.7}s` }} />
        ))}
        <rect width="1600" height="900" fill="url(#floorfade)" />
      </svg>
      {weather && <Weather fx={live.weather || art.fx} light={pal.light} />}
      {live.lightning && <div className="art-lightning" />}
      {live.dark && <div className="art-dark" />}
    </div>
  )
}
