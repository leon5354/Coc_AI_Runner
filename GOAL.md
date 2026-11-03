# Goal: a playable product

The bar for "done". Work loops until every box is ticked **and checked for real**, not assumed.
`python test_all.py` covers the mechanics; the rest is checked by playing in a browser.

## 1. Anyone can start it
- [ ] One command / double-click starts it. No API key needed.
- [ ] Brain choice is plain: local GPU model, Claude subscription, or an API key.
- [ ] A title screen shows the campaigns as cards. Pick one, press Continue. No dev words on screen.

## 2. The game works end to end
- [ ] A campaign can be played from the first scene to an ending, and the ending has its own screen.
- [ ] A real AI (not the scripted mock) plays turns with working rolls, clues, damage and scene changes.
- [ ] An AI failure never corrupts the story, and the player can retry.

## 3. Every mechanic is proven
- [ ] All 4 rule systems: odds match the rulebook, checked over thousands of rolls.
- [ ] Bonus/penalty dice, advantage/disadvantage really change the odds.
- [ ] HP, sanity/resolve, status changes, healing, death, inventory, clues, scene exits.
- [ ] Roll gate, negotiate, chain guard, undo, save/resume mid-roll, all 9 minigames.

## 4. Dice feel real
- [ ] 3D dice with physics. You can grab and throw them.
- [ ] The right dice per system (d100 pair, d20, damage dice, and d4/d6/d8/d10/d12 in the tray).
- [ ] The server decides the number. The die always lands on it.
- [ ] AI companion rolls and sanity rolls are shown too.

## 5. Character panel (狀態欄 / 物品欄)
- [ ] Status, skills, inventory, journal in one panel you can click through.
- [ ] Items have icons and can be inspected, used, given, dropped.
- [ ] The Keeper can give and take items. Clues and places fill the journal.

## 6. It looks like a game
- [ ] Every scene has code-made art matching the place and mood, in all supported campaigns.
- [ ] Characters have portraits. Moods have weather and light. Scene changes feel like events.
- [ ] Text stays easy to read. It works on a phone.
