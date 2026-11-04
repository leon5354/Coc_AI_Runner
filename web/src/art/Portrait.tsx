// Character portraits drawn in code: a rim-lit silhouette built from what the sheet says.
// Same character, same face, on every screen.
import { hash } from "./kits"

const HUES = ["#8f3b3b", "#3b6a8f", "#6a4b8f", "#3b8f73", "#8f6a3b", "#4b5a8f", "#8f3b6e"]

/** How steady a mind looks on a portrait. Systems without sanity are always 1. */
export const mindOf = (c: { stress: number; max_stress: number }) => (c.max_stress > 1 ? c.stress / c.max_stress : 1)

export function Portrait({ name, about = "", size = 64, ratio = 1, down = false }: {
  name: string; about?: string; size?: number; ratio?: number; down?: boolean
}) {
  const h = hash(name)
  const accent = HUES[h % HUES.length]
  const id = `p${h}`
  const text = `${name} ${about}`
  const hat = /detective|investigator|inquiry|agent|gumshoe|偵探|探員|警探|警察/i.test(text)
  const glasses = /professor|scholar|doctor|librarian|dr\.|教授|博士|學者|研究/i.test(text)
  const armor = /inquisitor|soldier|knight|guard|sergeant|審判|騎士|士兵|衛|軍/i.test(text)
  const hood = /cult|priest|nun|witch|mystic|修女|祭司|巫|僧/i.test(text)
  const long = !hat && !armor && !hood && h % 3 === 0
  const skew = (h % 7) - 3
  const mind = Math.max(0, Math.min(1, ratio))

  const body = `M8 100 C10 ${armor ? 70 : 76} 28 ${armor ? 66 : 72} 40 68 L60 68 C72 ${armor ? 66 : 72} 90 ${armor ? 70 : 76} 92 100 Z`
  const head = <ellipse cx="50" cy="44" rx={15 + (h % 3)} ry="19" />
  return (
    <svg className={down ? "portrait down" : "portrait"} width={size} height={size} viewBox="0 0 100 100" role="img" aria-label={name}>
      <defs>
        <radialGradient id={id} cx={`${35 + skew * 3}%`} cy="30%" r="90%">
          <stop offset="0" stopColor={accent} /><stop offset="1" stopColor="#0b0c12" />
        </radialGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#${id})`} />
      {/* rim light: the same figure, a touch larger, behind the dark one */}
      <g fill={accent} opacity="0.9" transform={`translate(${-1.6 + skew * 0.2} -1.2) scale(1.02)`}>
        <path d={body} />{head}
      </g>
      <g fill="#0b0c11">
        <path d={body} />
        <rect x="43" y="56" width="14" height="16" />
        {head}
        {long && <path d="M33 40 C30 22 70 22 67 40 C72 62 70 76 62 80 L60 50 L40 50 L38 80 C30 76 28 62 33 40 Z" />}
        {!long && !hat && !hood && <path d="M34 42 C30 20 70 20 66 42 C62 32 56 30 50 31 C44 30 38 32 34 42 Z" />}
        {hat && <path d="M20 33 C30 30 34 29 36 27 L39 12 C46 9 54 9 61 12 L64 27 C66 29 72 30 80 33 C66 37 34 37 20 33 Z" />}
        {hood && <path d="M50 10 C26 10 26 50 28 76 L38 70 C34 50 36 30 50 28 C64 30 66 50 62 70 L72 76 C74 50 74 10 50 10 Z" />}
        {armor && <path d="M14 76 L30 62 L42 60 L40 74 Z M86 76 L70 62 L58 60 L60 74 Z M38 62 L50 54 L62 62 L58 72 L42 72 Z" />}
      </g>
      {armor && <path d="M46 84 h8 v-6 h-8z M50 74 v16" stroke={accent} strokeWidth="2" fill="none" />}
      {glasses && <g fill="none" stroke={accent} strokeWidth="1.6"><circle cx="43" cy="43" r="4.5" /><circle cx="57" cy="43" r="4.5" /><path d="M47.5 43h5" /></g>}
      <g fill="#f4efe0" opacity={0.35 + mind * 0.6}>
        <circle cx="43" cy="43" r="1.3" /><circle cx="57" cy="43" r="1.3" />
      </g>
      {mind < 0.45 && <path d="M100 0 L74 22 L82 30 L58 56 M0 100 L24 70 L18 62 L38 46" stroke="#c23" strokeWidth="1.2" fill="none" opacity={(0.45 - mind) * 2} />}
    </svg>
  )
}
