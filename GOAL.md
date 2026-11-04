# Goal: a playable product

The bar for "done". Work loops until every box is ticked **and checked for real**, not assumed.
`python test_all.py` covers the mechanics, `python checklist.py` proves in minutes that a model can
run the game, `python playtest.py` plays a longer game with a real AI, and the rest is checked by
playing in a browser.

## 1. Anyone can start it
- [x] One command / double-click starts it. No API key needed.
- [x] Brain choice is plain: local GPU model, Claude subscription, or an API key.
- [x] A title screen shows the campaigns as cards. Pick one, press Continue. No dev words on screen.

## 2. The game works end to end
- [x] A campaign can be played from the first scene to an ending, and the ending has its own screen. (A real AI finishes the 3-scene test story. The ending screen itself was checked on the demo. Long campaigns: see below.)
- [x] A real AI (not the scripted mock) plays turns with working rolls, clues, damage and scene changes.
- [x] An AI failure never corrupts the story, and the player can retry.

## 3. Every mechanic is proven
- [x] All 4 rule systems: odds match the rulebook, checked over thousands of rolls.
- [x] Bonus/penalty dice, advantage/disadvantage really change the odds.
- [x] HP, sanity/resolve, status changes, healing, death, inventory, clues, scene exits.
- [x] Roll gate, negotiate, chain guard, undo, save/resume mid-roll, all 9 minigames.

## 4. Dice feel real
- [x] 3D dice with physics. You can grab and throw them.
- [x] The right dice per system (d100 pair, d20, damage dice, and d4/d6/d8/d10/d12 in the tray).
- [x] The server decides the number. The die always lands on it.
- [x] AI companion rolls and sanity rolls are shown too.

## 5. Character panel (狀態欄 / 物品欄)
- [x] Status, skills, inventory, journal in one panel you can click through.
- [x] Items have icons and can be inspected, used, given, dropped.
- [x] The Keeper can give and take items. Clues and places fill the journal.

## 6. It looks like a game
- [x] Every scene has code-made art matching the place and mood, in all supported campaigns.
- [x] Characters have portraits. Moods have weather and light. Scene changes feel like events.
- [x] Text stays easy to read. It works on a phone.

## Checklist runs (`checklist.py`, 3-scene test story, 2026-11-04)

20 checks: rolls, clues, push, negotiate, damage, Sanity, items, moving, puzzles, companions, Talk,
Ask the Keeper, Archives, Inspect, memory, ending, and the whole story played to its ending.

| Brain | Result | Bad text on screen | Whole story ended |
|---|---|---|---|
| Dolphin 12B, local | 38/40 over two rounds. After the last fixes, the 5 weakest checks: 14/15 | 15/15 clean after the fixes | 5 of 5, in 3-6 turns |
| Claude Haiku, through a helper | 18/20. After the fixes, the 2 misses (puzzle, whole story) passed | 20/20 clean | Yes, 6 turns |

The one weak spot on 12B: a horror sometimes doesn't cost Sanity (3 of 5 tries worked). 12B's writing
is also clearly weaker than Haiku's: it can ignore the action or make up details.
The Haiku run went through a helper, not the `claude -p` path. It proves the prompts, not the login.

## Real-AI playtest results (Dolphin 24B, 2026-11-04)

| Campaign | System | Turns | Rolls | Sanity | Clues | Moves | Items |
|---|---|---|---|---|---|---|---|
| The House on Marsh Lane | CoC 7e | 6 | 7 | 4 | 3 | 2 | 1 |
| 孤獨對抗霜寒 | CoC 7e | 4 | 4 | 3 | 2 | 0 | 0 |
| The Drowned Bell | D&D 5e | 6 | 7 | n/a | 1 | 1 | 1 |
| 深淵的蜜語 | WFRP | 3 | 3 | 1 | 1 | 1 | 0 |
| 機械測試：幽冥實驗室 | Basic d100 | 5 | 4 | n/a | 1 | 0 | 0 |

No fake dice, no leaked ids, no AI errors in any of them. The last run also started a minigame on
its own. Direct checks on the same model: a described wound became -1d6, a near miss changed
nothing, an item found and an item lost both reached the sheet, and a finished story was recognised
as its ending while an unfinished one was not.

## Long runs with a real AI (The Drowned Bell, stand-in player given the aim)

| Run | Turns | Rolls | HP changes | Clues | Moves | Items | Ended? |
|---|---|---|---|---|---|---|---|
| Whole campaign | 16 | 17 | 5 | 5 | 2 | 3 | No, reached scene 3 of 4 |
| Whole campaign, with pacing | 16 | 16 | 1 | 3 | 4 | 2 | No, wandered between places |
| Last scene only | 5 | 5 | 2 | 0 | 0 | 2 | No, the hero lost the clapper |

## Not checked yet
- A real AI playing a long campaign to its ending. The short story ends every time, but 16 turns
  wasn't enough on The Drowned Bell before the pacing fixes.
- Claude plan brain with a real login (needs `claude auth login` once).
- Scenario Architect in the web app with a real AI.
- `run_web.bat` from start to finish, adding a model from a Hugging Face link, and OpenRouter sign-in.
- How the sound and the dice flick feel to a person, and a real phone.
