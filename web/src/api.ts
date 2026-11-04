// Thin client for server/app.py. Types mirror core/game_state.py (GameState/CharacterState).

export type Character = {
  id: string; name: string; controller: "human" | "ai"; player_label: string
  hp: number; max_hp: number; stress: number; max_stress: number
  skills: Record<string, number>; inventory: string[]
  personality: string; backstory: string; status: string
  private_thoughts: string[]; memory_summary: string; relationships: Record<string, string>
  item_notes: Record<string, string>; luck: number
}
export type Message = { role: string; name?: string | null; content: string }
export type PendingRoll = {
  character_id: string; skill: string; target: number; difficulty: string; reason?: string
  bonus?: number; penalty?: number
}
export type PendingPush = PendingRoll & { roll: number; need: number; luck_cost: number }
export type Payload = Record<string, any> & { type: string }
export type State = {
  scene_id: string; characters: Character[]; active_character_id: string
  party_mode: string; language: string; god_mode: boolean; companion_style: string
  turn_count: number; summary: string
  messages: Message[]; messages_archive: Message[]
  pending_roll: PendingRoll | null; pending_minigame: Payload | null; pending_push: PendingPush | null
  minigame_count: number; dice_log: string[]; rule_system: string
  visited_scenes: string[]; ending: { outcome: string; description: string } | null
  stats: { rolls?: number; crits?: number; fumbles?: number }
}
export type DiceSpec = { kind: string; sides?: number }
export type Game = {
  state: State; title: string; campaign: string; scene_name: string; scene_text: string; scene_art: string
  scene_index: number; mood: string; dice_spec: DiceSpec; has_stress: boolean; stress_name: string
  rule_label: string; can_undo: boolean; roll_preview: { need: string; chance: number } | null
  clues: { id: string; name: string; text: string }[]; clues_total: number
  npcs: { name: string; role: string }[]
  map: { id: string; name: string; visited: boolean; exits: string[] }[]
}
export type LLMConfig = { provider: string; model: string; util_provider: string; util_model: string }
export type Campaign = {
  file: string; name: string; title: string; has_save: boolean; system: string; intro: string
  mood: string; scene_name: string; scene_text: string; scene_art: string
}
export type Meta = {
  mock: boolean; llm: LLMConfig
  providers: string[]; main_models: string[]; util_models: string[]; claude_models: string[]
  languages: Record<string, string>
  campaigns: Campaign[]
  rule_systems: string[]; settings: Record<string, string>; default_setting: Record<string, string>
  minigames: Record<string, string>; coverage: string[][]; audio: string[]
}
export type RollEvent = {
  kind: "skill" | "stress" | "free"; who: string; label: string; roll: number; tier: string
  success: boolean; detail: string; dice: { die: string; value: number; kept: boolean }[]
}
export type TurnLine = { label?: string; done?: boolean; error?: string; game?: Game | null; dice?: RollEvent[]; partial?: string }
export type Brains = {
  ollama: { installed: boolean; running: boolean; models: { name: string; gb: number }[] }
  gpu: { name: string; gb: number } | null
  claude: { installed: boolean; logged_in: boolean }
  keys: { openrouter: boolean; google: boolean }
}

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
export async function stream<T = TurnLine>(path: string, body: unknown, onLine: (l: T) => void) {
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
