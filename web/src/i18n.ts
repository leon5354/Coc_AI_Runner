// Interface text in English and Traditional Chinese. The English sentence is the key, so any
// string without a translation simply shows in English.
const ZH: Record<string, string> = {
  // title
  "New game": "新遊戲", "Your character": "你的角色", "{n} points left": "尚餘 {n} 點", "Skills": "技能", "You carry": "隨身物品",
  "Delete this save": "刪除存檔", "Delete this save? It can't be brought back.": "刪除這個存檔？刪除後無法復原。", "finished": "已完結",
  "New scenario": "新劇本", "⚙ Settings": "⚙ 設定", "Continue": "繼續", "Resume": "繼續遊戲", "Begin": "開始",
  "Start over": "重新開始", "saved game": "有存檔", "Pick a campaign": "選擇劇本",
  // story
  "must roll": "需要擲骰：", "failed": "失敗：", "🎲 Pick up the dice": "🎲 拿起骰子", "Negotiate": "交涉",
  "…or argue for a different approach": "……或者提出另一種做法", "Accept it": "接受結果",
  "Spend {n} Luck": "花費 {n} 點幸運", "Push the roll": "孤注一擲",
  "Or push it: how do you try harder? Failing again will cost you.": "或者孤注一擲：你會如何更進一步？再失敗要付出代價。",
  "Rolled {roll}, needed {need} or less. You have {luck} Luck.": "擲出 {roll}，需要 {need} 或以下。你有 {luck} 點幸運。",
  "Spend Luck to turn this into a bare success": "花費幸運，將結果變成勉強成功",
  "Act": "行動", "Talk": "對話", "Ask the Keeper": "問守秘人", "📚 Archives": "📚 查資料", "Send": "送出", "Search": "搜尋",
  "web": "網上", "Look something up in the archives…": "在檔案中查找……", "Acting as": "扮演角色",
  "What does {name} do?": "{name} 會做什麼？", "What does {name} say? No turn spent.": "{name} 會說什麼？（不花費回合）",
  "Ask anything: rules, a recap, your options…": "問什麼都可以：規則、前情、你的選擇……",
  "Nobody at the table can act. Undo the last turn, or switch a companion to a human player in their panel.": "沒有人可以行動。請復原上一回合，或在同伴的面板把他轉為玩家控制。",
  "How many": "數量", "Modifier": "加值", "Roll {expr}": "擲 {expr}",
  "turns": "回合", "rolls": "擲骰", "criticals": "大成功", "fumbles": "大失敗", "clues": "線索", "places": "地點",
  "📜 Keep the story": "📜 保存故事", "↩ Undo the ending": "↩ 復原結局", "Back to the title": "返回標題",
  "turn {n}": "第 {n} 回合", "🧩 Last minigame": "🧩 上一個小遊戲", "Rewind the last turn": "復原上一回合",
  "Roll any dice": "自由擲骰", "狀態欄 / 物品欄 — status and items": "狀態欄 / 物品欄", "Clues and places": "線索與地點",
  // panel
  "Player": "玩家", "AI companion": "AI 同伴", "Played by AI": "由 AI 控制", "Personality": "性格", "Background": "背景",
  "Edit": "編輯", "Save": "儲存", "Cancel": "取消", "Name": "名字", "Player label": "玩家名稱",
  "🧠 What they privately think": "🧠 內心想法", "Their memory forms as they live through more.": "經歷越多，記憶越深。",
  "Find a skill…": "搜尋技能……", "Click a skill to try it. The Keeper decides if it needs a roll.": "點擊技能嘗試運用。由守秘人決定是否需要擲骰。",
  "Use": "使用", "Inspect": "查看", "Drop": "丟棄", "Give to": "交給", "Click an item to look at it.": "點擊物品查看。",
  "Nothing carried.": "身上沒有物品。", "You haven't looked at it closely.": "你還未仔細查看。", "Turning it over in your hands…": "你把它拿在手中細看……",
  "Clues": "線索", "Places": "地點", "People": "人物", "Nothing found yet.": "暫時未有發現。", "The story so far": "前情提要",
  // dice
  "Press and hold to grab the dice, then flick and let go": "按住骰子，甩動後放手", "Just throw": "直接擲骰", "Back": "返回",
  "Let go to throw!": "放手擲骰！", "Click to continue": "點擊繼續", "Held firm": "穩住了", "Shaken": "動搖了",
  "Fail this and something terrible happens": "再失敗，將有可怕的事發生", "chance": "機會", "about": "約",
  "Critical Success": "大成功", "Extreme Success": "極難成功", "Hard Success": "困難成功", "Regular Success": "成功",
  "Success": "成功", "Failure": "失敗", "Fumble": "大失敗",
  "regular": "普通", "hard": "困難", "extreme": "極難", "easy": "容易", "medium": "中等", "very_hard": "極難",
  "average": "普通", "challenging": "挑戰", "bonus": "獎勵骰", "penalty": "懲罰骰",
  // settings
  "Settings": "設定", "Who is the Keeper?": "誰來當守秘人？", "Sound and dice": "聲音與骰子", "This game": "本局設定",
  "Skip the 3D dice": "略過 3D 骰子", "Language": "敘事語言", "Interface": "介面語言", "AI companions": "AI 同伴",
  "Companion voice": "同伴語氣", "Narrated by Keeper": "由守秘人敘述", "Act when called": "被點名才行動", "Act every turn": "每回合行動",
  "Like a player": "像玩家", "Like a novel": "像小說", "😇 God mode": "😇 上帝模式", "➕ Add a character": "➕ 新增角色",
  "Played by": "控制者", "Add": "新增", "🧪 Try a minigame": "🧪 試玩小遊戲", "🎲 Dice log": "🎲 擲骰紀錄", "📜 Export story": "📜 匯出故事",
  "Background music": "背景音樂", "Off": "關閉", "🔇 Turn on sound": "🔇 開啟聲音", "🔊 Sound on": "🔊 聲音已開啟",
  "In use": "使用中", "Remove": "移除", "Add model": "新增模型", "Looking at what this PC can run…": "正在檢查這部電腦……",
  "Free, private, no key.": "免費、私密、不用金鑰。", "Starting Ollama… reopen Settings in a moment.": "正在啟動 Ollama……請稍後重新打開設定。",
  "Pick a file up to {n} GB. A bigger one won't fit on the GPU and runs much slower.": "請選 {n} GB 或以下的檔案。太大的模型放不進顯示卡，會慢很多。",
  "Too big, will be slow": "太大，會很慢",
  "Small model for summaries (optional)": "用於摘要的小型模型（可選）", "Same as the Keeper": "與守秘人相同",
  // minigames
  "Move the candle across the surface…": "把蠟燭在表面上移動……", "Expose the whole surface to the heat": "把整個表面放近熱源",
  "The planchette begins to move...": "占卜板開始移動……", "It stops.": "它停下來了。", "A cipher blocks the way": "密碼擋住了去路",
  "Your answer": "你的答案", "Try it": "嘗試", "Give up": "放棄", "A combination lock": "密碼鎖", "Turn the dial": "轉動轉盤",
  "Step away": "走開", "Draw three cards": "抽三張牌", "Accept the omen": "接受預兆", "Arcane glyphs await the correct order": "神秘符文等待正確次序",
  "Activated:": "已啟動：", "Step back from the glyphs": "從符文前退開", "Choose your play:": "選擇你的打法：",
  "🔥 Bold (d10 — swing big)": "🔥 大膽（d10，放手一搏）", "🛡️ Steady (d6+2 — play safe)": "🛡️ 穩陣（d6+2，保守）",
  "One cut. Choose.": "只能剪一刀。選吧。", "Back away without cutting": "不剪，退開", "Step away from the pattern": "離開圖案",
  "Watch…": "看清楚……", "Repeat the sequence.": "重複這個次序。", "The pattern answers.": "圖案回應了。",
  "The pattern fades, unanswered.": "圖案消失，沒有回應。", "Wrong — it begins again…": "錯了，重新開始……",
}

let lang: "en" | "zh" = "en"

export const uiPref = (): string => { try { return localStorage.getItem("ui.lang") ?? "auto" } catch { return "auto" } }
export const setUiPref = (v: string) => { try { localStorage.setItem("ui.lang", v) } catch { /* private window */ } }

/** Follow the choice in Settings; on auto, follow the game's language, then the browser's. */
export function pickLang(gameLanguage?: string, title?: string) {
  const pref = uiPref()
  if (pref === "en" || pref === "zh") lang = pref
  else if (gameLanguage === "zh" || gameLanguage === "yue") lang = "zh"
  else if (gameLanguage === "en") lang = "en"
  else if (title) lang = /[㐀-鿿]/.test(title) ? "zh" : "en"
  else lang = navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en"
}

export function t(text: string, vars?: Record<string, string | number>) {
  let out = (lang === "zh" && ZH[text]) || text
  for (const [k, v] of Object.entries(vars ?? {})) out = out.replace(`{${k}}`, String(v))
  return out
}
