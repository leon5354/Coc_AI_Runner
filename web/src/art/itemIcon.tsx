// Picks an icon from the item's own name, in English or Chinese. Icons: game-icons.net (CC BY 3.0).
import { GiAmmoBox, GiBackpack, GiBookCover, GiBread, GiBreastplate, GiBroadsword, GiCandles, GiChemicalDrop, GiCigarette, GiCloak, GiCoins, GiCompass, GiCrossbow, GiCrowbar, GiCrucifix, GiCrystalBall, GiEnergySword, GiFirstAidKit, GiFlashlight, GiGems, GiHammerNails, GiHolySymbol, GiKey, GiKeyCard, GiLantern, GiLeatherBoot, GiLighter, GiMagnifyingGlass, GiMatchHead, GiMedal, GiMedicines, GiMicrophone, GiMirrorMirror, GiNotebook, GiPadlock, GiPaper, GiPhotoCamera, GiPistolGun, GiPlainDagger, GiPocketWatch, GiQuillInk, GiRadarSweep, GiRadioTower, GiRevolver, GiRing, GiRopeCoil, GiRose, GiScrollUnfurled, GiShield, GiSmartphone, GiSpectacles, GiSpellBook, GiStandingPotion, GiSwapBag, GiSyringe, GiToolbox, GiWaterFlask, GiWallet, GiWineBottle, GiWinterGloves } from "react-icons/gi"
import type { IconType } from "react-icons"

const RULES: [RegExp, IconType][] = [
  [/revolver|左輪/i, GiRevolver], [/pistol|gun|rifle|shotgun|手槍|步槍|槍/i, GiPistolGun],
  [/power sword|chainsword|動力劍|鏈鋸/i, GiEnergySword], [/sword|blade|saber|劍|刀刃/i, GiBroadsword],
  [/knife|dagger|shiv|匕首|刀/i, GiPlainDagger], [/crossbow|bow\b|弩|弓/i, GiCrossbow],
  [/ammo|bullets?|shells?|彈/i, GiAmmoBox], [/shield|盾/i, GiShield],
  [/armou?r|carapace|vest|plate|裝甲|盔甲|護甲/i, GiBreastplate],
  [/key ?card|room card|access card|門卡|房卡/i, GiKeyCard], [/key|鑰匙/i, GiKey], [/lock|鎖/i, GiPadlock],
  [/torch|flashlight|電筒|手電/i, GiFlashlight], [/lantern|lamp|提燈|油燈|燈/i, GiLantern],
  [/lighter|打火機/i, GiLighter], [/match|火柴/i, GiMatchHead], [/candle|蠟燭/i, GiCandles],
  [/notebook|pad|journal|diary|筆記|日記|清單/i, GiNotebook], [/pen\b|pencil|quill|筆/i, GiQuillInk],
  [/grimoire|tome|spell|魔法書|經文/i, GiSpellBook], [/book|書/i, GiBookCover],
  [/scroll|map|卷軸|地圖/i, GiScrollUnfurled], [/letter|paper|document|note|clipping|信|紙|文件/i, GiPaper],
  [/first aid|bandage|medkit|急救|繃帶/i, GiFirstAidKit], [/syringe|needle|注射/i, GiSyringe],
  [/pill|medicine|medic|藥/i, GiMedicines], [/potion|elixir|tonic|藥水/i, GiStandingPotion],
  [/flask|canteen|water|水壺|水/i, GiWaterFlask], [/wine|whisk|bottle|酒|瓶/i, GiWineBottle],
  [/chemical|acid|試劑|化學/i, GiChemicalDrop], [/food|ration|bread|乾糧|食/i, GiBread],
  [/phone|手機|電話/i, GiSmartphone], [/recorder|microphone|錄音/i, GiMicrophone], [/radio|對講/i, GiRadioTower],
  [/auspex|scanner|detector|探測|掃描/i, GiRadarSweep], [/camera|相機/i, GiPhotoCamera],
  [/magnif|放大鏡/i, GiMagnifyingGlass], [/glasses|spectacles|眼鏡/i, GiSpectacles], [/mirror|鏡/i, GiMirrorMirror],
  [/compass|指南針/i, GiCompass], [/watch|clock|懷錶|手錶/i, GiPocketWatch],
  [/rope|cord|繩/i, GiRopeCoil], [/crowbar|撬棍/i, GiCrowbar], [/hammer|nail|錘/i, GiHammerNails], [/tool|工具/i, GiToolbox],
  [/rosette|medal|badge|insignia|紋章|徽章|勳章/i, GiMedal], [/seal|sigil|talisman|聖印|符/i, GiHolySymbol],
  [/cross|crucifix|十字/i, GiCrucifix], [/ring|戒指/i, GiRing], [/crystal|orb|水晶/i, GiCrystalBall], [/gem|jewel|寶石/i, GiGems],
  [/coin|money|gold|cash|錢|金幣/i, GiCoins], [/wallet|purse|皮夾|錢包/i, GiWallet],
  [/coat|cloak|robe|jacket|大衣|外套|斗篷/i, GiCloak], [/glove|手套/i, GiWinterGloves], [/boots?|shoes?|靴|鞋/i, GiLeatherBoot],
  [/flower|rose|daisy|bouquet|花/i, GiRose], [/cigar|煙/i, GiCigarette], [/bag|sack|pack|背包|袋/i, GiBackpack],
]

export function itemIcon(name: string): IconType {
  return RULES.find(([re]) => re.test(name))?.[1] ?? GiSwapBag
}
