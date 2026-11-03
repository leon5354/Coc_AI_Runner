// Thin client for server/app.py. Types mirror core/game_state.py (GameState/CharacterState).

export type Character = {
  id: string; name: string; controller: "human" | "ai"; player_label: string
  hp: number; max_hp: number; stress: number; max_stress: number
  skills: Record<string, number>; inventory: string[]
  personality: string; backstory: string; status: string
  private_thoughts: string[]; memory_summary: string; relationships: Record<string, string>
}
export type Message = { role: string; name?: string | null; content: string }
export type PendingRoll = {
  character_id: string; skill: string; target: number; difficulty: string; reason?: string
}
export type Payload = Record<string, any> & { type: string }
export type State = {
  scene_id: string; characters: Character[]; active_character_id: string
  party_mode: string; language: string; god_mode: boolean; companion_style: string
  turn_count: number; summary: string
  messages: Message[]; messages_archive: Message[]
  pending_roll: PendingRoll | null; pending_minigame: Payload | null
  minigame_count: number; dice_log: string[]
}
export type DiceSpec = { kind: string; sides?: number }
export type Game = {
  state: State; title: string; campaign: string; scene_name: string; mood: string
  dice_spec: DiceSpec; has_stress: boolean; can_undo: boolean
}
export type LLMConfig = { provider: string; model: string; util_provider: string; util_model: string }
export type Meta = {
  mock: boolean; llm: LLMConfig
  providers: string[]; main_models: string[]; util_models: string[]
  languages: Record<string, string>
  campaigns: { file: string; name: string; has_save: boolean }[]
  rule_systems: string[]; settings: Record<string, string>; default_setting: Record<string, string>
  minigames: Record<string, string>; coverage: string[][]; audio: string[]
}
export type DiceResult = { roll: number; tier: string; detail: string; spec: DiceSpec }
export type TurnLine = { label?: string; done?: boolean; error?: string; game: Game | null; dice?: DiceResult }

async function check(r: Response) {
  if (r.ok) return r
  let msg = `${r.status} ${r.statusText}`
  try { msg = (await r.json()).detail ?? msg } catch { /* not json */ }
  throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg))
}

export async function get<T>(path: string): Promise<T> {
  return (await check(await fetch(path))).json()
}

export async function send<T>(path: string, body: unknown = {}, method = "POST"): Promise<T> {
  const r = await fetch(path, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  })
  return (await check(r)).json()
}

/** POST a turn and call onLine for every NDJSON beat the server streams back. */
export async function stream(path: string, body: unknown, onLine: (l: TurnLine) => void) {
  const r = await check(await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }))
  const reader = r.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value
    let i
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i)
      buf = buf.slice(i + 1)
      if (line.trim()) onLine(JSON.parse(line))
    }
  }
}
