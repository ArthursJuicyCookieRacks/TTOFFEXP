from direct.interval.IntervalGlobal import *
from panda3d.core import *
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownBattleGlobals
import random
TTBG = ToontownBattleGlobals
TTL = TTLocalizer
EFFECT_RADIUS = 30
RESISTANCE_TOONUP = 0
RESISTANCE_RESTOCK = 1
RESISTANCE_MONEY = 2
resistanceMenu = [RESISTANCE_TOONUP, RESISTANCE_RESTOCK, RESISTANCE_MONEY]
resistanceDict = {RESISTANCE_TOONUP: {'menuName': TTL.ResistanceToonupMenu,
                     'itemText': TTL.ResistanceToonupItem,
                     'chatText': TTL.ResistanceToonupChat,
                     'values': [20,
                                35,
                                50,
                                65,
                                80],
                     'items': [0,
                               1,
                               2,
                               3,
                               4]},
 RESISTANCE_MONEY: {'menuName': TTL.ResistanceMoneyMenu,
                    'itemText': TTL.ResistanceMoneyItem,
                    'chatText': TTL.ResistanceMoneyChat,
                    'values': [100,
                               200,
                               350,
                               600],
                    'items': [0,
                              1,
                              2,
                              3]},
 RESISTANCE_RESTOCK: {'menuName': TTL.ResistanceRestockMenu,
                      'itemText': TTL.ResistanceRestockItem,
                      'chatText': TTL.ResistanceRestockChat,
                      'values': [TTBG.HEAL_TRACK,
                                 TTBG.TRAP_TRACK,
                                 TTBG.LURE_TRACK,
                                 TTBG.SOUND_TRACK,
                                 TTBG.THROW_TRACK,
                                 TTBG.SQUIRT_TRACK,
                                 TTBG.DROP_TRACK,
                                 -1],
                      'extra': [TTL.MovieNPCSOSHeal,
                                TTL.MovieNPCSOSTrap,
                                TTL.MovieNPCSOSLure,
                                TTL.MovieNPCSOSSound,
                                TTL.MovieNPCSOSThrow,
                                TTL.MovieNPCSOSSquirt,
                                TTL.MovieNPCSOSDrop,
                                TTL.MovieNPCSOSAll],
                      'items': [0,
                                1,
                                2,
                                3,
                                4,
                                5,
                                6,
                                7]}}

# Mini Unites: very small versions of the regular ones, the reward for a
# Cashbot field office. They stay out of resistanceMenu so getRandomId and
# the full restock never hand them out.
RESISTANCE_MINI_TOONUP = 3
RESISTANCE_MINI_RESTOCK = 4
RESISTANCE_MINI_MONEY = 5
miniMenu = [RESISTANCE_MINI_TOONUP, RESISTANCE_MINI_RESTOCK, RESISTANCE_MINI_MONEY]
allMenus = resistanceMenu + miniMenu
# What each mini kind is a small copy of.
MiniOf = {RESISTANCE_MINI_TOONUP: RESISTANCE_TOONUP,
          RESISTANCE_MINI_RESTOCK: RESISTANCE_RESTOCK,
          RESISTANCE_MINI_MONEY: RESISTANCE_MONEY}
# How small a mini Unite's sparkles are.
MiniEffectScale = 0.4
resistanceDict[RESISTANCE_MINI_TOONUP] = {'menuName': getattr(TTL, 'ResistanceMiniToonupMenu', 'Mini Toon-up'),
 'itemText': getattr(TTL, 'ResistanceMiniToonupItem', 'Mini %s Toon-up'),
 'chatText': getattr(TTL, 'ResistanceMiniToonupChat', 'Toons of the World, a little Toon-up!'),
 'values': [5, 10, 15],
 'items': [0, 1, 2]}
resistanceDict[RESISTANCE_MINI_RESTOCK] = {'menuName': getattr(TTL, 'ResistanceMiniRestockMenu', 'Mini Gag-up'),
 'itemText': getattr(TTL, 'ResistanceMiniRestockItem', 'Mini Gag-up %s'),
 'chatText': getattr(TTL, 'ResistanceMiniRestockChat', 'Toons of the World, a little Gag-up!'),
 'values': resistanceDict[RESISTANCE_RESTOCK]['values'],
 'extra': resistanceDict[RESISTANCE_RESTOCK]['extra'],
 'items': resistanceDict[RESISTANCE_RESTOCK]['items']}
resistanceDict[RESISTANCE_MINI_MONEY] = {'menuName': getattr(TTL, 'ResistanceMiniMoneyMenu', 'Mini Jellybeans'),
 'itemText': getattr(TTL, 'ResistanceMiniMoneyItem', 'Mini %s Jellybeans'),
 'chatText': getattr(TTL, 'ResistanceMiniMoneyChat', 'Toons of the World, a little something!'),
 'values': [25, 50, 75],
 'items': [0, 1, 2]}

# Mini Gag-up: this many of each of a track's three smallest gags.
MiniRestockLevels = (0, 1, 2)
MiniRestockAmount = 2


def isMini(textId):
    return decodeId(textId)[0] in miniMenu


def getMiniRewardIds(tier):
    """The Cashbot field office reward: one of each mini kind, a bit
    bigger for a harder building (tier 0, 1 or 2)."""
    tier = max(0, min(2, tier))
    restock = random.choice(resistanceDict[RESISTANCE_MINI_RESTOCK]['items'][:-1])
    return [encodeId(RESISTANCE_MINI_TOONUP, tier),
            encodeId(RESISTANCE_MINI_RESTOCK, restock),
            encodeId(RESISTANCE_MINI_MONEY, tier)]


def encodeId(menuIndex, itemIndex):
    textId = menuIndex * 100
    textId += resistanceDict[menuIndex]['items'][itemIndex]
    return textId


def decodeId(textId):
    menuIndex = int(textId / 100)
    itemIndex = textId % 100
    return (menuIndex, itemIndex)


def validateId(textId):
    if textId < 0:
        return 0
    menuIndex, itemIndex = decodeId(textId)
    if menuIndex not in resistanceDict:
        return 0
    if itemIndex >= len(resistanceDict[menuIndex]['values']):
        return 0
    return 1


def getItems(menuIndex):
    return resistanceDict[menuIndex]['items']


def getMenuName(textId):
    menuIndex, itemIndex = decodeId(textId)
    return resistanceDict[menuIndex]['menuName']


def getItemText(textId):
    menuIndex, itemIndex = decodeId(textId)
    value = resistanceDict[menuIndex]['values'][itemIndex]
    text = resistanceDict[menuIndex]['itemText']
    kind = MiniOf.get(menuIndex, menuIndex)
    if kind == RESISTANCE_TOONUP:
        if value == -1:
            value = TTL.ResistanceToonupItemMax
    elif kind == RESISTANCE_RESTOCK:
        value = resistanceDict[menuIndex]['extra'][itemIndex]
    return text % str(value)


def getChatText(textId):
    menuIndex, itemIndex = decodeId(textId)
    return resistanceDict[menuIndex]['chatText']


def getItemValue(textId):
    menuIndex, itemIndex = decodeId(textId)
    return resistanceDict[menuIndex]['values'][itemIndex]


def getRandomId():
    menuIndex = random.choice(resistanceMenu)
    itemIndex = random.choice(getItems(menuIndex))
    return encodeId(menuIndex, itemIndex)


def doEffect(textId, speakingToon, nearbyToons):
    from toontown.battle import BattleParticles
    from direct.particles import Particles
    menuIndex, itemIndex = decodeId(textId)
    itemValue = getItemValue(textId)
    mini = menuIndex in miniMenu
    menuIndex = MiniOf.get(menuIndex, menuIndex)
    if menuIndex == RESISTANCE_TOONUP:
        effect = BattleParticles.loadParticleFile('resistanceEffectSparkle.ptf')
        fadeColor = VBase4(1, 0.5, 1, 1)
    elif menuIndex == RESISTANCE_MONEY:
        effect = BattleParticles.loadParticleFile('resistanceEffectBean.ptf')
        bean = loader.loadModel('phase_4/models/props/jellybean4')
        bean = bean.find('**/jellybean')
        colors = {'particles-1': (1, 1, 0, 1),
         'particles-2': (1, 0, 0, 1),
         'particles-3': (0, 1, 0, 1),
         'particles-4': (0, 0, 1, 1),
         'particles-5': (1, 0, 1, 1)}
        for name, color in list(colors.items()):
            node = bean.copyTo(NodePath())
            node.setColorScale(*color)
            p = effect.getParticlesNamed(name)
            p.renderer.setGeomNode(node.node())

        fadeColor = VBase4(0, 1, 0, 1)
    elif menuIndex == RESISTANCE_RESTOCK:
        effect = BattleParticles.loadParticleFile('resistanceEffectSprite.ptf')
        invModel = loader.loadModel('phase_3.5/models/gui/inventory_icons')
        invModel.setScale(4)
        invModel.flattenLight()
        icons = []
        if itemValue != -1:
            for item in range(6):
                iconName = ToontownBattleGlobals.AvPropsNew[itemValue][item]
                icons.append(invModel.find('**/%s' % iconName))

        else:
            tracks = list(range(7))
            random.shuffle(tracks)
            for i in range(6):
                track = tracks[i]
                item = random.randint(0, 5)
                iconName = ToontownBattleGlobals.AvPropsNew[track][item]
                icons.append(invModel.find('**/%s' % iconName))

        iconDict = {'particles-1': icons[0],
         'particles-2': icons[1],
         'particles-3': icons[2],
         'particles-4': icons[3],
         'particles-5': icons[4],
         'particles-6': icons[5]}
        for name, icon in list(iconDict.items()):
            p = effect.getParticlesNamed(name)
            p.renderer.setFromNode(icon)

        fadeColor = VBase4(0, 0, 1, 1)
    else:
        return
    if mini:
        effect.setScale(MiniEffectScale)
    recolorToons = Parallel()
    for toonId in nearbyToons:
        toon = base.cr.doId2do.get(toonId)
        if toon and not toon.ghostMode:
            i = Sequence(toon.doToonColorScale(fadeColor, 0.3), toon.doToonColorScale(toon.defaultColorScale, 0.3), Func(toon.restoreDefaultColorScale))
            recolorToons.append(i)

    i = Parallel(ParticleInterval(effect, speakingToon, worldRelative=0, duration=3, cleanup=True), Sequence(Wait(0.2), recolorToons), autoFinish=1)
    i.start()
