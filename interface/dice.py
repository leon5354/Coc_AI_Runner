"""Animated 3D dice component (CCv2). Cosmetic only — the result is always rolled server-side.
Each die is a CSS 3D bipyramid (two fans of 5 triangular faces, evoking a d10) that tumbles
in real 3D, with the value on a screen-facing badge."""
import streamlit as st

TIER_COLORS = {
    "Critical Success": "#ffd700",
    "Extreme Success": "#2ecc71",
    "Hard Success": "#1abc9c",
    "Regular Success": "#aaaaaa",
    "Success": "#2ecc71",
    "Failure": "#e74c3c",
    "Fumble": "#8b0000",
}

_HTML = """
<div class="stage">
  <div class="dice" id="dice"></div>
  <div class="banner" id="banner"></div>
</div>
"""

_CSS = """
.stage { display: flex; flex-direction: column; align-items: center; gap: 16px;
         font-family: Georgia, serif; padding: 12px 0; }
.dice { display: flex; gap: 42px; }
.die-scene { width: 90px; height: 100px; perspective: 420px; position: relative; }
.solid { position: absolute; inset: 0; transform-style: preserve-3d;
         animation: tumble 1.6s cubic-bezier(.25,1.2,.5,1) forwards; }
.face { position: absolute; left: 50%; top: 50%; width: 56px; height: 56px;
        margin: -28px 0 0 -28px; transform-style: preserve-3d;
        clip-path: polygon(50% 0%, 100% 100%, 0% 100%); }
.face.up   { background: linear-gradient(170deg, #f2ead6, #c9bb9a); }
.face.down { background: linear-gradient(10deg, #ded1ac, #a89975); }
.badge { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
         font-size: 1.75em; font-weight: bold; color: #2b2118;
         background: radial-gradient(circle, #f4ecd8 58%, rgba(244,236,216,0) 72%);
         width: 62px; height: 62px; display: flex; align-items: center; justify-content: center;
         border-radius: 50%; z-index: 2; }
@keyframes tumble {
  0%   { transform: rotateX(0)      rotateY(0)      rotateZ(0)      translateY(-70px) scale(.7); }
  35%  { transform: rotateX(430deg) rotateY(260deg) rotateZ(120deg) translateY(10px)  scale(1.05); }
  65%  { transform: rotateX(660deg) rotateY(320deg) rotateZ(310deg) translateY(-12px) scale(1); }
  100% { transform: rotateX(720deg) rotateY(360deg) rotateZ(360deg) translateY(0)     scale(1); }
}
.settling { animation: wobble .5s ease-out forwards !important; }
@keyframes wobble {
  0%   { transform: rotateX(720deg) rotateY(360deg) scale(1.06); }
  100% { transform: rotateX(705deg) rotateY(348deg) scale(1); }
}
.banner { opacity: 0; transition: opacity .5s; font-size: 1.05em; text-align: center; }
"""

_JS = """
export default function (component) {
  const { data, parentElement } = component
  const dice = parentElement.querySelector("#dice")
  const banner = parentElement.querySelector("#banner")
  if (!dice || dice.dataset.rolled) return
  dice.dataset.rolled = "1"

  const faces = (data && data.faces) || []
  const color = (data && data.color) || "#aaaaaa"
  banner.textContent = (data && data.detail) || ""
  banner.style.color = color
  banner.style.textShadow = `0 0 8px ${color}`

  const badges = []
  for (const f of faces) {
    const scene = document.createElement("div")
    scene.className = "die-scene"
    const solid = document.createElement("div")
    solid.className = "solid"
    // two fans of 5 triangular faces around the Y axis = stylized d10 bipyramid
    for (let i = 0; i < 5; i++) {
      const up = document.createElement("div")
      up.className = "face up"
      up.style.transform = `rotateY(${i * 72}deg) translateZ(16px) rotateX(28deg)`
      solid.appendChild(up)
      const dn = document.createElement("div")
      dn.className = "face down"
      dn.style.transform = `rotateY(${i * 72 + 36}deg) translateZ(16px) rotateX(152deg) `
      solid.appendChild(dn)
    }
    const badge = document.createElement("div")
    badge.className = "badge"
    scene.appendChild(solid)
    scene.appendChild(badge)
    dice.appendChild(scene)
    badges.push({ badge, solid, final: f.final, pad: f.pad })
  }

  const spin = setInterval(() => {
    for (const b of badges) {
      const v = Math.floor(Math.random() * 10) * (b.pad > 1 ? 10 : 1)
      b.badge.textContent = String(v).padStart(b.pad, "0")
    }
  }, 80)

  const settle = setTimeout(() => {
    clearInterval(spin)
    for (const b of badges) {
      b.badge.textContent = b.final
      b.solid.classList.add("settling")
      b.badge.style.textShadow = `0 0 14px ${color}`
      b.badge.style.boxShadow = `0 0 22px ${color}55`
    }
    banner.style.opacity = 1
  }, 1600)
  return () => { clearInterval(spin); clearTimeout(settle) }
}
"""

_dice_component = st.components.v2.component("dice_roll_3d", html=_HTML, css=_CSS, js=_JS)


def render_dice_roll(roll: int, tier: str, detail: str, spec: dict = None, key: str = None):
    """Show an animated 3D roll settling on `roll`, with a tier-colored result banner."""
    spec = spec or {"kind": "single", "sides": 100}
    color = TIER_COLORS.get(tier, "#aaaaaa")

    if spec.get("kind") == "d100_two_d10":
        tens, units = (roll % 100) // 10, roll % 10
        if roll == 100:
            tens, units = 0, 0
        faces = [{"final": f"{tens}0", "pad": 2}, {"final": str(units), "pad": 1}]
    else:
        faces = [{"final": str(roll), "pad": 1}]

    try:
        _dice_component(data={"faces": faces, "color": color, "detail": detail}, key=key)
    except Exception:
        st.markdown(f"🎲 **{roll}** — {detail}")
