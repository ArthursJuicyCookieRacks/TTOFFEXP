"""
Plays through the offline game automatically, to check that every part of it
works with the in-process server (otp.local).

Run it from the repository root, with the resources in resources/:

    python tools/offline/autoplay.py [scenario ...]

With no arguments every scenario runs, in order. The game window opens as
usual (use a virtual display such as Xvfb on a headless machine). The run
uses a throwaway database (autoplay-db/ by default, or $AUTOPLAY_DB) and
stops with a non-zero exit code at the first failing step, or when the
client or a server hits an exception.
"""

import builtins
import glob
import math
import os
import re
import sys
import time
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = os.path.abspath(os.environ.get('AUTOPLAY_DB', 'autoplay-db'))

from panda3d.core import loadPrcFileData, Filename, NodePath, Point3, Vec3
loadPrcFileData('autoplay', '''
audio-library-name null
toontown-auto-run 0
auto-start-server 1
local-db-directory %(db)s
account-bridge-filename %(db)s/account-bridge
local-event-log-directory %(db)s/events
local-server-catch-exceptions 1
sync-video 0
want-magic-words 1
''' % {'db': DB})
os.environ.setdefault('TTR_PLAYCOOKIE', 'autoplay')
os.environ.setdefault('TTR_GAMESERVER', '127.0.0.1')

from toontown.toonbase import ToontownStart
# Extra config for a run, such as want-doomsday 1 for the election. It is
# loaded after the game's own config so that it wins.
loadPrcFileData('autoplay-extra', os.environ.get('AUTOPLAY_PRC', '').replace(';', '\n'))
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals
from toontown.hood import ZoneUtil
from toontown.building import DoorTypes
from direct.showbase.DirectObject import DirectObject
from direct.gui import DirectGuiGlobals as DGG
from direct.showbase.InputStateGlobal import inputState
from otp.local import LocalServer


class StepFailed(Exception):
    pass


def log(*args):
    print('AUTOPLAY:', *args, flush=True)


# --- Error collection ---

# Interval callbacks fail far from the code that queued them; name the function.
from direct.interval import FunctionInterval
_privInstant = FunctionInterval.FunctionInterval.privInstant


def privInstant(self):
    try:
        return _privInstant(self)
    except Exception as e:
        e.add_note('in FunctionInterval %s calling %r' % (self.getName(), self.function))
        raise


FunctionInterval.FunctionInterval.privInstant = privInstant

errors = []

server = LocalServer.getInstance()
_report = server.reportException
_handle = server.handleRepositoryException


def reportException(context):
    errors.append('%s: %s' % (context.name, traceback.format_exc()))
    return _report(context)


def handleRepositoryException(repository):
    errors.append('%s: %s' % (server.contexts.current.name, traceback.format_exc()))
    return _handle(repository)


server.reportException = reportException
server.handleRepositoryException = handleRepositoryException


# --- Waiting helpers, used as `yield until(...)` inside scenarios ---

class until:

    def __init__(self, condition, timeout=60, what=None):
        self.condition = condition
        self.deadline = time.time() + timeout
        self.what = what or getattr(condition, '__name__', 'condition')


def sleep(seconds):
    end = time.time() + seconds
    return until(lambda: time.time() >= end, seconds + 5, 'sleep')


def loginState():
    try:
        return base.cr.loginFSM.getCurrentState().getName()
    except AttributeError:
        return None


def place():
    try:
        return base.cr.playGame.getPlace()
    except AttributeError:
        return None


def hoodState():
    try:
        return base.cr.playGame.hood.fsm.getCurrentState().getName()
    except AttributeError:
        return None


def placeState():
    p = place()
    if p is None or getattr(p, 'fsm', None) is None:
        return None
    return p.fsm.getCurrentState().getName()


def magicWord(word):
    log('magic word', word)
    messenger.send('magicWord', [word])


def doLater(delay, func, *args):
    taskMgr.doMethodLater(delay, lambda task: (func(*args), task.done)[1], 'autoplay-later')


def walking():
    return placeState() == 'walk'


def inZone(zoneId):
    # On a street the toon may walk into a neighbouring visgroup as it lands.
    branchId = ZoneUtil.getBranchZone(zoneId)

    def check():
        return walking() and ZoneUtil.getBranchZone(localAvatar.zoneId) == branchId
    check.__name__ = 'walking in zone %d' % zoneId
    return check


def teleport(hoodId, zoneId=None):
    zoneId = zoneId or hoodId
    log('teleporting to', hoodId, zoneId)
    yield until(walking, 60, 'walking before teleport')
    place().requestTeleport(hoodId, zoneId, None, -1)
    yield until(inZone(zoneId), 120)


# --- Scenarios ---

listener = DirectObject()
ready = []
listener.accept('localServerReady', lambda: ready.append(1))


def scenarioLogin():
    yield until(lambda: ready, 300, 'local server ready')
    yield until(lambda: loginState() == 'connect', 60, 'press a key screen')
    yield sleep(1)
    messenger.send('buttonpress', ['space'])
    yield until(lambda: loginState() == 'chooseAvatar', 120, 'avatar chooser')
    chooser = base.cr.avChoice
    if not any(av.position == 0 for av in chooser.avatarList):
        log('creating a toon')
        chooser.choice = 0
        messenger.send(chooser.doneEvent, [{'mode': 'create'}])
        yield until(lambda: loginState() == 'createAvatar', 60, 'Make-A-Toon')
        mat = base.cr.avCreate
        shop = lambda: mat.fsm.getCurrentState().getName()
        yield until(lambda: shop() == 'GenderShop', 60, 'gender shop')
        mat.gs.createRandomBoy()
        for name in ('BodyShop', 'ColorShop', 'ClothesShop', 'NameShop'):
            yield sleep(0.5)
            mat.goToNextShop()
            yield until(lambda: shop() == name, 30, name)
        yield sleep(2)
        mat.ns._NameShop__createAvatar(skipTutorial=not TUTORIAL)
    else:
        log('choosing the toon in slot 0')
        chooser.choice = 0
        messenger.send(chooser.doneEvent, [{'mode': 'chose'}])
    yield until(lambda: loginState() == 'playingGame', 180, 'playing the game')
    if TUTORIAL:
        return
    yield until(walking, 180, 'walking in the playground')
    log('in game as %s (%d) in zone %d' % (localAvatar.getName(), localAvatar.doId, localAvatar.zoneId))


# AUTOPLAY_TUTORIAL=1 makes the new toon go through the Toontorial (the
# tutorial scenario) instead of skipping it.
TUTORIAL = bool(os.environ.get('AUTOPLAY_TUTORIAL'))


def scenarioTutorial():
    # The Toontorial: Tutorial Tom's ToonTask, the Flunky outside, the HQ
    # officer, and out through the tunnel to Toontown Central.
    recordNPCMovies()
    yield until(lambda: place() and place().__class__.__name__ == 'ToonInterior' and walking(), 120, "Tutorial Tom's shop")
    shop = localAvatar.zoneId
    tom = findObject('DistributedNPCToon', lambda do: do.zoneId == shop)
    yield from talkTo(tom)
    yield until(lambda: localAvatar.quests, 30, "Tom's ToonTask")
    log('ToonTask from Tom: %s' % (localAvatar.quests,))

    door = findObject('DistributedDoor', lambda do: do.zoneId == shop)
    messenger.send(door.getEnterTriggerEvent(), [None])
    yield until(lambda: localAvatar.zoneId != shop and walking(), 120, 'the tutorial street')
    street = localAvatar.zoneId
    yield until(lambda: findObject('DistributedTutorialSuit'), 60, 'the Flunky')
    suit = findObject('DistributedTutorialSuit')
    log('fighting the Flunky')
    while placeState() == 'walk' and not suit.isEmpty():
        localAvatar.setPos(render, suit.getPos(render))
        yield sleep(0.1)
    yield from fightBattle()
    yield until(walking, 120, 'walking after the Flunky')

    hqDoor = lambda: findObject('DistributedDoor', lambda do: do.zoneId == street and do.doorType == DoorTypes.EXT_HQ)
    yield until(hqDoor, 60, 'the HQ door')
    yield sleep(2)
    messenger.send(hqDoor().getEnterTriggerEvent(), [None])
    yield until(lambda: localAvatar.zoneId != street and walking(), 120, 'the tutorial HQ')
    hq = localAvatar.zoneId
    harry = findObject('DistributedNPCToon', lambda do: do.zoneId == hq)
    yield from talkTo(harry)
    log('ToonTask from the HQ officer: %s' % (localAvatar.quests,))

    exitDoor = lambda: findObject('DistributedDoor', lambda do: do.zoneId == hq and do.doorIndex == 1)
    yield until(exitDoor, 30, 'the HQ door to the playground')
    yield sleep(2)
    messenger.send(exitDoor().getEnterTriggerEvent(), [None])
    yield until(lambda: localAvatar.zoneId != hq and walking(), 120, 'back on the street')
    tunnel = localAvatar.zoneId
    yield until(lambda: findObject('DistributedNPCBlocker', lambda do: do.zoneId == tunnel), 30, 'Flippy')
    log('Flippy is waiting by the tunnel')
    triggers = render.findAllMatches('**/tunnel_trigger_*')
    log('walking into the tunnel %s' % triggers[0].getName())
    messenger.send('enter' + triggers[0].getName(), [None])
    # Toontown Central greets a new toon with a dialog pointing at their next
    # ToonTask, which they acknowledge before walking.
    yield until(lambda: localAvatar.zoneId == ToontownGlobals.ToontownCentral and placeState() == 'popup'
                and getattr(place(), 'dialog', None), 120, 'the Toontown Central welcome dialog')
    log('Toontown Central says: %s' % place().dialog['text'])
    place().dialog['command'](DGG.DIALOG_OK)
    yield until(inZone(ToontownGlobals.ToontownCentral), 60, 'walking in Toontown Central')
    yield until(lambda: localAvatar.tutorialAck, 30, 'the tutorial to be done')
    log('Toontorial done; ToonTasks %s' % (localAvatar.quests,))


def scenarioTouchControls():
    # The on-screen joystick and jump button of the Android build, pressed
    # with the X pointer (run with AUTOPLAY_PRC="want-touch-controls 1").
    import subprocess
    yield until(walking, 60, 'walking')
    controls = getattr(base, 'touchControls', None)
    if controls is None or controls.joystick.isHidden():
        raise StepFailed('no touch controls while walking')
    window = str(base.win.getWindowHandle().getIntHandle())

    def pixel(node, offset=(0, 0)):
        point = render2d.getRelativePoint(node, Point3(offset[0], 0, offset[1]))
        return (str(int((point[0] + 1) / 2 * base.win.getXSize())), str(int((1 - point[2]) / 2 * base.win.getYSize())))

    def xdotool(*args):
        subprocess.check_call(['xdotool'] + list(args))

    if os.environ.get('AUTOPLAY_SCREENSHOT'):
        base.graphicsEngine.renderFrame()
        base.win.saveScreenshot(Filename.fromOsSpecific(os.environ['AUTOPLAY_SCREENSHOT']))
    start = localAvatar.getPos(render)
    xdotool('mousemove', '--window', window, *pixel(controls.joystick))
    xdotool('mousedown', '1')
    yield sleep(0.3)
    xdotool('mousemove', '--window', window, *pixel(controls.joystick, (0, controls.RADIUS)))
    yield sleep(2)
    pressed = sorted(controls.pressed)
    xdotool('mouseup', '1')
    yield sleep(0.5)
    moved = (localAvatar.getPos(render) - start).length()
    log('the joystick pressed %s and the toon walked %.1f feet' % (pressed, moved))
    if pressed != ['up'] or moved < 5:
        raise StepFailed('the joystick did not walk the toon forward')
    if controls.pressed or inputState.isSet('forward'):
        raise StepFailed('the toon kept walking after the touch ended')

    stopped = localAvatar.getPos(render)
    yield sleep(1)
    if (localAvatar.getPos(render) - stopped).length() > 0.5:
        raise StepFailed('the toon kept moving after the touch ended')

    ground = localAvatar.getZ(render)
    xdotool('mousemove', '--window', window, *pixel(controls.jumpButton))
    xdotool('mousedown', '1')
    highest = ground
    for i in range(10):
        yield sleep(0.05)
        highest = max(highest, localAvatar.getZ(render))
    xdotool('mouseup', '1')
    log('the jump button lifted the toon %.1f feet' % (highest - ground))
    if highest - ground < 1:
        raise StepFailed('the jump button did not jump')
    yield sleep(1)


def scenarioMaxToon():
    magicWord('~maxToon CONFIRM')
    yield until(lambda: localAvatar.getMaxHp() == ToontownGlobals.MaxHpLimit, 30, 'maxed laff')
    yield until(lambda: ToontownGlobals.SellbotHQ in localAvatar.getTeleportAccess(), 30, 'teleport access')
    # A lone toon can go sad in the long facilities; the runs test the game's
    # flow, not its balance.
    magicWord('~immortal')
    magicWord('~unlimitedGags')
    yield sleep(1)


PLAYGROUNDS = [
    ToontownGlobals.ToontownCentral, ToontownGlobals.DonaldsDock, ToontownGlobals.DaisyGardens,
    ToontownGlobals.MinniesMelodyland, ToontownGlobals.TheBrrrgh, ToontownGlobals.DonaldsDreamland,
    ToontownGlobals.GoofySpeedway, ToontownGlobals.OutdoorZone,
    ToontownGlobals.SellbotHQ, ToontownGlobals.CashbotHQ, ToontownGlobals.LawbotHQ, ToontownGlobals.BossbotHQ,
]

STREETS = [
    ToontownGlobals.SillyStreet, ToontownGlobals.LoopyLane, ToontownGlobals.PunchlinePlace,
    ToontownGlobals.BarnacleBoulevard, ToontownGlobals.SeaweedStreet, ToontownGlobals.LighthouseLane,
    ToontownGlobals.ElmStreet, ToontownGlobals.MapleStreet, ToontownGlobals.OakStreet,
    ToontownGlobals.AltoAvenue, ToontownGlobals.BaritoneBoulevard, ToontownGlobals.TenorTerrace,
    ToontownGlobals.WalrusWay, ToontownGlobals.SleetStreet, ToontownGlobals.PolarPlace,
    ToontownGlobals.LullabyLane, ToontownGlobals.PajamaPlace,
]


def scenarioPlaygrounds():
    for hoodId in PLAYGROUNDS:
        yield from teleport(hoodId)
        yield sleep(2)


def firstVisgroup(streetId):
    # A street's own zone has no scenery; toons stand in its visgroups.
    for path in glob.glob(os.path.join('resources', 'phase_*', 'dna', '*_%d.xml' % streetId)):
        match = re.search(r'<visgroup zone="(\d+)"', open(path).read())
        if match:
            return int(match.group(1))
    raise StepFailed('no visgroups found for street %d' % streetId)


def scenarioStreets():
    for zoneId in STREETS:
        hoodId = zoneId - zoneId % 1000
        yield from teleport(hoodId, firstVisgroup(zoneId))
        yield sleep(2)
    yield from teleport(ToontownGlobals.ToontownCentral)


def suitsNearby():
    from toontown.suit.DistributedSuit import DistributedSuit
    return [do for do in base.cr.doId2do.values() if isinstance(do, DistributedSuit) and not do.isEmpty()]


def townBattle():
    p = place()
    if hasattr(p, 'townBattle'):
        return p.townBattle
    return getattr(getattr(p, 'loader', None), 'townBattle', None)


def townBattleState():
    try:
        return townBattle().fsm.getCurrentState().getName()
    except AttributeError:
        return None


def onDistrict(func, *args):
    # Runs func inside the first district's AI, and returns its result.
    context, simbase = server.servers[1]
    with server.contexts.use(context):
        return func(simbase.air, *args)


def pickGag():
    # The strongest gag the toon still carries; sound hits every cog at once.
    inventory = localAvatar.inventory
    for level in range(6, -1, -1):
        for track in (ToontownBattleGlobals.SOUND_TRACK, ToontownBattleGlobals.THROW_TRACK,
                      ToontownBattleGlobals.SQUIRT_TRACK, ToontownBattleGlobals.DROP_TRACK):
            if inventory.numItem(track, level) > 0:
                return track, level
    raise StepFailed('the toon is out of sound, throw, squirt and drop gags')


def fightBattle(timeout=1800, during=None):
    # during, if given, is called between gag choices.
    yield until(lambda: placeState() == 'battle', 60, 'battle to start')
    deadline = time.time() + timeout
    rounds = 0
    nextReport = time.time() + 30
    while placeState() == 'battle':
        if time.time() > deadline:
            raise StepFailed('the battle did not end in %d seconds' % timeout)
        if time.time() > nextReport:
            nextReport = time.time() + 30
            log('still in battle: round %d, gag panel %s' % (rounds, townBattleState()))
        if townBattleState() == 'Attack':
            rounds += 1
            track, level = pickGag()
            messenger.send(townBattle().battleEvent,
                           [{'mode': 'Attack', 'track': track, 'level': level, 'target': 0}])
            yield until(lambda: townBattleState() != 'Attack', 30, 'gag choice to register')
        else:
            if during is not None:
                during()
            yield sleep(0.2)
    log('battle won after %d rounds' % rounds)


def scenarioBattle():
    street = ToontownGlobals.SillyStreet
    yield from teleport(street - street % 1000, firstVisgroup(street))
    magicWord('~spawn f 1')
    yield until(suitsNearby, 120, 'a cog on the street')
    suit = min(suitsNearby(), key=lambda s: (s.getPos(render) - localAvatar.getPos(render)).length())
    log('walking into', suit.getName(), suit.doId)
    while placeState() == 'walk':
        if suit.isEmpty():
            raise StepFailed('the cog left before the battle started')
        localAvatar.setPos(render, suit.getPos(render))
        yield sleep(0.1)
    yield from fightBattle()
    yield until(walking, 120, 'walking after the battle')


def scenarioBuilding():
    street = ToontownGlobals.SillyStreet

    def takeOver(air):
        manager = air.buildingManagers[street]
        block = manager.getToonBlocks()[0]
        building = manager.getBuilding(block)
        building.suitTakeOver('s', 0, 0)
        return block, building.getExteriorAndInteriorZoneId()[0]

    block, zoneId = onDistrict(takeOver)
    log('cogs took over block %d in zone %d' % (block, zoneId))
    yield from teleport(street - street % 1000, zoneId)

    def elevator():
        from toontown.building.DistributedElevatorExt import DistributedElevatorExt
        for do in base.cr.doId2do.values():
            if isinstance(do, DistributedElevatorExt) and getattr(do, 'bldg', None) and do.bldg.block == block:
                return do

    yield until(elevator, 120, 'the cog building elevator')
    yield sleep(2)
    log('boarding the elevator')
    messenger.send(elevator().uniqueName('enterelevatorSphere'), [None])
    yield until(lambda: place().__class__.__name__ == 'SuitInterior', 120, 'inside the cog building')
    deadline = time.time() + 1200
    while place().__class__.__name__ == 'SuitInterior':
        if time.time() > deadline:
            raise StepFailed('still inside the cog building after 20 minutes (place state %s)' % placeState())
        if placeState() == 'battle':
            yield from fightBattle()
        else:
            yield sleep(0.5)
    yield until(walking, 180, 'walking after the cog building')
    log('back outside in zone %d' % localAvatar.zoneId)

    def isToonBlock(air):
        return air.buildingManagers[street].getBuilding(block).isToonBlock()

    yield until(lambda: onDistrict(isToonBlock), 120, 'the building to turn back into a toon building')


def cogdoGameState(game):
    return game.fsm.getCurrentState().getName() if game.fsm else None


def playCogdoMaze(dist):
    # Splashes each big cog twice, as the water coolers' gags would, and
    # walks out the exit once it opens.
    from toontown.cogdominium import CogdoMazeGameGlobals as Globals
    game = dist.game
    for bossNum in range(dist._numSuits[0]):
        for hit in range(Globals.SuitData[Globals.SuitTypes.Boss]['hp']):
            dist.b_suitHitByGag(Globals.SuitTypes.Boss, bossNum)
            yield sleep(0.5)
    yield until(lambda: game._exit.isOpen(), 30, 'the maze exit to open')
    log('the maze exit is open')
    game.handleLocalToonEntersDoor(game._exit)


def playCogdoFlying(dist):
    # Flies straight to the far platform, as landing on it would.
    player = dist.game.localPlayer
    yield sleep(3)
    player.setCheckpointPlatform(player._level.endPlatform)
    player.request('WaitingForWin')


def scenarioCogdo(track='s'):
    # A field office: a Sellbot one is a maze, a Lawbot one a flying game,
    # then the executive suite battle that frees the shopkeeper.
    street = ToontownGlobals.SillyStreet

    def takeOver(air):
        manager = air.buildingManagers[street]
        block = manager.getToonBlocks()[0]
        building = manager.getBuilding(block)
        building.cogdoTakeOver(track, 0, 0)
        return block, building.getExteriorAndInteriorZoneId()[0]

    block, zoneId = onDistrict(takeOver)
    log('the %s cogs made block %d in zone %d a field office' % (track, block, zoneId))
    yield from teleport(street - street % 1000, zoneId)
    def ours(do):
        return getattr(do, 'bldg', None) and do.bldg.block == block

    yield until(lambda: findObject('DistributedCogdoElevatorExt', ours), 120, 'the field office elevator')
    elevator = findObject('DistributedCogdoElevatorExt', ours)
    yield until(lambda: elevator.fsm.getCurrentState().getName() == 'waitEmpty', 60,
                'the field office elevator to open (it is %s)' % elevator.fsm.getCurrentState().getName())
    yield from boardElevator('DistributedCogdoElevatorExt', ours)
    yield until(lambda: placeName() == 'CogdoInterior', 120, 'inside the field office')
    interior = findObject('DistributedCogdoInterior')
    played = set()
    deadline = time.time() + 1500
    nextReport = 0
    while placeName() == 'CogdoInterior':
        if time.time() > deadline:
            raise StepFailed('still inside the field office after 25 minutes (place state %s)' % placeState())
        state = interior.fsm.getCurrentState().getName() if interior.fsm else None
        game = findObject('DistCogdoMazeGame') or findObject('DistCogdoFlyingGame')
        if time.time() > nextReport:
            nextReport = time.time() + 15
            log('field office state %s, floor %d, place %s, game %s' % (
                state, interior.currentFloor, placeState(), game and cogdoGameState(game)))
        if game and game.doId not in played and cogdoGameState(game) == 'Game':
            played.add(game.doId)
            log('playing', game.__class__.__name__)
            if game.__class__.__name__ == 'DistCogdoMazeGame':
                yield from playCogdoMaze(game)
            else:
                yield from playCogdoFlying(game)
        elif state == 'Resting' and walking():
            yield from boardElevator('DistributedCogdoElevatorInt')
            yield until(lambda: interior.fsm.getCurrentState().getName() != 'Resting', 120, 'the elevator up')
        elif placeState() == 'battle':
            yield from fightBattle()
        elif state == 'Reward':
            # Reading the shopkeeper's thank-you.
            messenger.send('doneChatPage', [0])
            yield sleep(1)
        else:
            yield sleep(0.5)
    yield until(walking, 180, 'walking after the field office')
    log('back outside in zone %d with %d SOS cards' % (localAvatar.zoneId, len(localAvatar.NPCFriendsDict)))

    def isToonBlock(air):
        return air.buildingManagers[street].getBuilding(block).isToonBlock()

    yield until(lambda: onDistrict(isToonBlock), 120, 'the field office to turn back into a toon building')


def placeName():
    return place().__class__.__name__ if place() else None


def findObject(className, test=lambda do: True):
    for do in list(base.cr.doId2do.values()):
        if do.__class__.__name__ == className and test(do):
            return do


def boardElevator(className, test=lambda do: True):
    yield until(lambda: findObject(className, test), 120, 'a %s' % className)
    yield until(walking, 60, 'walking by the elevator')
    yield sleep(2)
    log('boarding', className)
    messenger.send(findObject(className, test).uniqueName('enterelevatorSphere'), [None])


def clearFacility(interior, suitClass, levelClass=None, timeout=1800):
    # Walks into the boss cog until it is beaten, fighting whatever joins.
    yield until(lambda: placeName() == interior, 180, 'inside the %s' % interior)
    deadline = time.time() + timeout
    nextReport = 0
    while placeName() == interior:
        if time.time() > deadline:
            raise StepFailed('still inside the %s after %d seconds' % (interior, timeout))
        if placeState() == 'battle':
            yield from fightBattle()
            continue
        boss = findObject(suitClass, lambda do: getattr(do, 'boss', 0) and not do.isEmpty())
        if boss is None and walking() and levelClass:
            # Cogs only exist for the zones the toon can see, so look through
            # the zones one at a time until the boss shows up.
            level = findObject(levelClass)
            for zoneNum in [z for z in level.zoneNums if z != 0]:
                level.lockVisibility(zoneNum=zoneNum)
                yield sleep(0.5)
                boss = findObject(suitClass, lambda do: getattr(do, 'boss', 0) and not do.isEmpty())
                if boss is not None:
                    log('found the boss cog in zone %d' % zoneNum)
                    break
            level.unlockVisibility()
        if boss is not None and walking():
            localAvatar.setPos(render, boss.getPos(render))
        if time.time() > nextReport:
            nextReport = time.time() + 15
            suits = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == suitClass]
            level = findObject(levelClass) if levelClass else None
            log('%d cogs here, boss %s, toon at %s in zone %d, state %s, level zone %s, visible %s' % (
                len(suits), boss and (boss.doId, boss.getPos(render)), localAvatar.getPos(render),
                localAvatar.zoneId, placeState(), getattr(level, 'curZoneNum', None),
                sorted(getattr(level, 'curVisibleZoneNums', {}))))
        yield sleep(0.2)
    yield until(walking, 180, 'walking after the %s' % interior)
    log('out of the %s, in zone %d' % (interior, localAvatar.zoneId))


def playMoleField(field, beaten, timeout=900):
    # Stands in the mole field and hits every cog that pops up (the hills
    # with HILL_BOMB are the cogs to whack; HILL_MOLE is the bomb).
    from toontown.coghq import MoleFieldBase
    log('whacking moles')
    localAvatar.setPos(render, field.centerNode.getPos(render))
    deadline = time.time() + timeout

    class Hit:
        def __init__(self, index):
            self.index = index

        def getSurfaceNormal(self, other):
            return Vec3(0, 0, 1)

        def getIntoNodePath(self):
            return NodePath('moleCol-%d' % self.index)

    while not beaten():
        if time.time() > deadline:
            raise StepFailed('the mole field was not beaten in %d seconds' % timeout)
        for index, hill in enumerate(field.moleHills):
            if hill.isUp and hill.hillType == MoleFieldBase.HILL_BOMB:
                field.handleEnterMole(Hit(index))
        yield sleep(0.1)
    log('mole field beaten')


def playGolfGreen(game, timeout=1300):
    # Bust-A-Cog: shoots each ball at the lowest ball of its own colour,
    # which is where a player would usually aim.
    log('playing the golf green puzzle')
    game._DistributedGolfGreenGame__handleToonEnter(None)
    yield until(lambda: localAvatar.doId in game.joinedToons, 30, 'joining the golf green')
    deadline = time.time() + timeout
    boards = 0
    while not game.finished:
        if time.time() > deadline:
            raise StepFailed('the golf green puzzle did not finish in %d seconds' % timeout)
        sprite = game.controlSprite
        if game.ballLoaded and sprite and not sprite.nodeObj.isEmpty():
            targets = [(cell[0], cell[1], cell[2]) for row in game.grid for cell in row
                       if cell[0] is not None and cell[0].colorType == sprite.colorType]
            if not targets:
                targets = [(cell[0], cell[1], cell[2]) for row in game.grid for cell in row if cell[0] is not None]
            if targets:
                target = min(targets, key=lambda target: target[0].getZ())[0]
                dx = target.getX() - sprite.getX()
                dz = target.getZ() - sprite.getZ()
                game.aimRadian = max(0.2 - math.pi, min(-0.2, -math.atan2(dz, dx)))
                game._DistributedGolfGreenGame__handleMouseClick()
        yield sleep(0.5)
    log('golf green puzzle over')


def clearRooms(interior, facilityClass, timeout=3600):
    # Mints, DA offices and country clubs are strings of rooms: go to each
    # room in turn and beat every cog in it. DA offices and country clubs
    # have more than one floor, joined by an elevator.
    yield until(lambda: placeName() == interior, 180, 'inside the %s' % interior)
    deadline = time.time() + timeout
    floorsDone = set()
    while placeName() == interior:
        newFloor = lambda do: do.rooms and do.doId not in floorsDone
        yield until(lambda: findObject(facilityClass, newFloor) or placeName() != interior, 180,
                    'the %s rooms' % facilityClass)
        facility = findObject(facilityClass, newFloor)
        if facility is None:
            break
        floorsDone.add(facility.doId)
        log('floor %d' % len(floorsDone))
        for index, room in enumerate(list(facility.rooms)):
            if placeName() != interior:
                break
            yield until(walking, 120, 'walking before room %d' % index)
            log('room %d of %d: %s' % (index + 1, len(facility.rooms), room.__class__.__name__))
            facility.warpToRoom(room.roomId)
            # Give the room's cogs time to arrive once the room is visible.
            yield sleep(3)
            # Country club rooms can hold a puzzle that unblocks the way on.
            inRoom = lambda do: getattr(do, 'levelDoId', None) == room.doId
            moles = findObject('DistributedMoleField', inRoom)
            if moles:
                yield from playMoleField(moles, lambda: index not in facility.blockedRooms)
            golf = findObject('DistributedGolfGreenGame', inRoom)
            if golf:
                yield from playGolfGreen(golf)
                yield until(walking, 60, 'walking after the golf green')
            nextReport = time.time() + 30
            target = targetSince = None
            while placeName() == interior:
                if time.time() > deadline:
                    raise StepFailed('still inside the %s after %d seconds' % (interior, timeout))
                if placeState() == 'battle':
                    yield from fightBattle()
                    continue
                suits = [do for do in list(base.cr.doId2do.values())
                         if getattr(do, 'levelDoId', None) == room.doId and hasattr(do, 'boss') and not do.isEmpty()]
                if not suits:
                    break
                if walking():
                    localAvatar.setPos(render, suits[0].getPos(render))
                    if suits[0].doId != target:
                        target, targetSince = suits[0].doId, time.time()
                    elif time.time() - targetSince > 5:
                        # Some cogs stand where the toon's collisions can't
                        # reach them (a part of the room that isn't shown);
                        # start the battle the way a battle blocker does.
                        log('walking into %d did not start a battle; using its battle blocker' % target)
                        suits[0].handleBattleBlockerCollision()
                        targetSince = time.time()
                if time.time() > nextReport:
                    nextReport = time.time() + 30
                    log('%d cogs left in the room: %s; toon at %s, state %s' % (
                        len(suits), ', '.join('%s %s in %s' % (suit.doId, suit.getPos(render), suit.fsm.getCurrentState().getName())
                                              for suit in suits), localAvatar.getPos(render), placeState()))
                yield sleep(0.2)
        yield sleep(3)
        # DA offices join floors with DistributedElevatorFloor, country clubs
        # with DistributedClubElevator.
        elevatorClass = next((name for name in ('DistributedElevatorFloor', 'DistributedClubElevator')
                              if findObject(name)), None)
        if placeName() == interior and elevatorClass:
            yield from boardElevator(elevatorClass)
            yield until(lambda: findObject(facilityClass, newFloor) or placeName() != interior, 300,
                        'the next floor')
        else:
            break
    yield until(lambda: placeName() != interior, 300, 'leaving the %s' % interior)
    yield until(walking, 180, 'walking after the %s' % interior)
    log('out of the %s, in zone %d' % (interior, localAvatar.zoneId))


def scenarioMint():
    yield from teleport(ToontownGlobals.CashbotHQ)
    yield from boardElevator('DistributedMintElevatorExt',
                             lambda do: getattr(do, 'mintId', None) == ToontownGlobals.CashbotMintIntA)
    yield from clearRooms('MintInterior', 'DistributedMint')


def scenarioOffice():
    yield from teleport(ToontownGlobals.LawbotHQ, ToontownGlobals.LawbotOfficeExt)
    yield from boardElevator('DistributedLawOfficeElevatorExt',
                             lambda do: getattr(do, 'intZoneId', None) == ToontownGlobals.LawbotStageIntA)
    yield from clearRooms('StageInterior', 'DistributedStage')


def scenarioCountryClub():
    yield from teleport(ToontownGlobals.BossbotHQ)
    yield from boardElevator('DistributedCogKart',
                             lambda do: getattr(do, 'countryClubId', None) == ToontownGlobals.BossbotCountryClubIntA)
    yield from clearRooms('CountryClubInterior', 'DistributedCountryClub')


def bossStatus(air, bossId):
    boss = air.doId2do.get(bossId)
    if boss is None:
        return 'no boss on the AI'
    status = 'damage %s of %s' % (getattr(boss, 'bossDamage', '?'), getattr(boss, 'bossMaxDamage', '?'))
    if hasattr(boss, 'heldObject'):
        status += ', helmet %s, attack code %s' % (boss.heldObject and boss.heldObject.doId, boss.attackCode)
    for crane in getattr(boss, 'cranes', None) or []:
        if crane.avId:
            status += ', crane %d holds %s' % (crane.doId, crane.objectId)
    objects = [do for do in air.doId2do.values() if do.__class__.__name__ in ('DistributedCashbotBossSafeAI', 'DistributedCashbotBossGoonAI')]
    if objects:
        states = {}
        for do in objects:
            key = '%s %s' % (do.__class__.__name__[20:-2], do.state)
            states[key] = states.get(key, 0) + 1
        status += ', objects %s' % sorted(states.items())
    return status


def fightBoss(interior, bossClass, actions, timeout=2400, prelude={}):
    # Plays a boss battle: cog rounds are fought as usual, and actions maps
    # the boss's other states to what a toon does in them (called every
    # half second with the boss). prelude actions also run while that
    # state's cog round is being fought.
    yield until(lambda: placeName() == interior, 180, 'inside the %s' % interior)
    yield until(lambda: findObject(bossClass), 120, 'the %s' % bossClass)
    boss = findObject(bossClass)
    deadline = time.time() + timeout
    lastState = None

    def finishEpilogue(boss):
        # One click through the speech, as a player would; every click
        # restarts the walk out of the boss room.
        if time.time() - stateStart > 3 and time.time() > getattr(boss, 'autoplayNextClick', 0):
            boss.autoplayNextClick = time.time() + 20
            messenger.send('doneChatPage', [0])

    while placeName() == interior:
        if time.time() > deadline:
            raise StepFailed('the %s did not end in %d seconds (boss state %s)' % (bossClass, timeout, boss.state))
        if boss.state != lastState:
            lastState = boss.state
            stateStart = time.time()
            log('boss state', lastState)
        elif time.time() - stateStart > 60:
            stateStart = time.time()
            log('boss still in %s; place state %s, gag panel %s; %s' % (
                boss.state, placeState(), townBattleState(), onDistrict(bossStatus, boss.doId)))
        during = lambda: prelude[boss.state](boss) if boss.state in prelude else None
        during()
        if placeState() == 'battle':
            yield from fightBattle(during=during)
            continue
        # In the epilogue a rescued toon talks; clicking through the speech
        # balloon's pages ends it.
        action = actions.get(boss.state) or {'Epilogue': finishEpilogue}.get(boss.state)
        if action is not None:
            action(boss)
        yield sleep(0.5)
    yield until(walking, 180, 'walking after the %s' % bossClass)
    log('out of the %s, in zone %d' % (interior, localAvatar.zoneId))


def vpBattleThree(boss):
    # What hitting the VP with pies sends: take pies from the cage, open
    # the VP up with a pie inside, then hit him while he is dizzy.
    if localAvatar.numPies == 0:
        boss.sendUpdate('touchCage', [])
    elif boss.attackCode != ToontownGlobals.BossCogDizzyNow:
        boss.d_hitBossInsides()
    else:
        boss.d_hitBoss(1)


def scenarioVP():
    yield from teleport(ToontownGlobals.SellbotHQ, ToontownGlobals.SellbotLobby)
    yield from boardElevator('DistributedVPElevator')
    yield from fightBoss('SellbotHQBossBattle', 'DistributedSellbotBoss', {
        'BattleThree': vpBattleThree,
        'NearVictory': lambda boss: boss.sendUpdate('finalPieSplat', []),
    })


def cfoBattleThree(boss):
    # What the cranes do: take a crane, pick up a goon or a safe, and swing
    # it into the CFO. A safe knocks his helmet off, and hurts him while he
    # is dizzy; a goon hurts him whenever he has no helmet on.
    me = localAvatar.doId
    crane = findObject('DistributedCashbotBossCrane', lambda do: do.avId == me)
    if crane is None:
        free = findObject('DistributedCashbotBossCrane', lambda do: do.avId == 0)
        if free is not None:
            free.sendUpdate('requestControl', [])
        return
    if not crane.magnetOn:
        # Holding the control key keeps the magnet on; without it the crane
        # lets go of whatever it picks up.
        crane._DistributedCashbotBossCrane__controlPressed()
    if time.time() > getattr(boss, 'autoplayNextNote', 0):
        boss.autoplayNextNote = time.time() + 15
        log('cfo: crane %s; my objects %s' % (crane.doId, [(do.__class__.__name__[20:], do.state) for do in base.cr.doId2do.values()
                                                            if 'CashbotBoss' in do.__class__.__name__ and getattr(do, 'avId', None) == me]))
    held = findObject('DistributedCashbotBossSafe', lambda do: do.avId == me and do.state in ('Grabbed', 'LocalGrabbed')) or \
        findObject('DistributedCashbotBossGoon', lambda do: do.avId == me and do.state in ('Grabbed', 'LocalGrabbed'))
    if held is not None:
        held.sendUpdate('hitBoss', [1.0])
        return
    wantSafe = boss.heldObject is not None or getattr(boss, 'attackCode', None) == ToontownGlobals.BossCogDizzy
    kinds = ['DistributedCashbotBossSafe', 'DistributedCashbotBossGoon']
    if not wantSafe:
        kinds.reverse()
    for kind in kinds:
        thing = findObject(kind, lambda do: do.state not in ('Grabbed', 'LocalGrabbed', 'Off') and do is not boss.heldObject)
        if thing is not None:
            thing.sendUpdate('requestGrab', [])
            return


def scenarioCFO():
    yield from teleport(ToontownGlobals.CashbotHQ, ToontownGlobals.CashbotLobby)
    yield from boardElevator('DistributedCFOElevator')
    yield from fightBoss('CashbotHQBossBattle', 'DistributedCashbotBoss', {
        'BattleThree': cfoBattleThree,
    })


def cjBattleThree(boss):
    # What throwing evidence does: take evidence at the witness stand, then
    # land it on the scale's pan.
    if localAvatar.numPies == 0:
        boss.sendUpdate('touchWitnessStand', [])
    else:
        boss.d_hitBoss(1)


def cjBattleTwo(boss):
    # What the cannons do: take a cannon, and fire a toon into every chair
    # of the jury box. Jurors put more weight on the toons' side of the
    # scale when the third round starts.
    # Cogs fly back into the chairs, so empty ones keep getting refilled.
    cannon = findObject('DistributedLawbotCannon')
    if cannon is None:
        return
    if not getattr(boss, 'autoplayCannon', False):
        cannon.sendUpdate('requestEnter', [])
        boss.autoplayCannon = True
    chairs = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedLawbotChair'
              and do.state != 'ToonJuror']
    for chair in chairs:
        boss.sendUpdate('hitChair', [chair.index, cannon.index])


def scenarioCJ():
    yield from teleport(ToontownGlobals.LawbotHQ, ToontownGlobals.LawbotLobby)
    yield from boardElevator('DistributedCJElevator')
    yield from fightBoss('LawbotHQBossBattle', 'DistributedLawbotBoss', {
        'BattleThree': cjBattleThree,
        'NearVictory': lambda boss: boss.sendUpdate('finalPieSplat', []),
    }, prelude={'BattleTwo': cjBattleTwo})


def ceoBattleTwo(boss):
    # Waits on the banquet: takes food off a belt and serves it to a hungry
    # diner, the way a toon runs between the belts and the tables. Diners
    # who eat enough leave and stay out of the next cog round.
    if time.time() < getattr(boss, 'autoplayNextServe', 0):
        return
    boss.autoplayNextServe = time.time() + 1
    avId = localAvatar.doId
    if not boss.toonFoodStatus.get(avId):
        boss.autoplayFoodNum = getattr(boss, 'autoplayFoodNum', 0) + 1
        boss.localToonTouchedBeltFood(0, 0, boss.autoplayFoodNum)
        return
    for table in list(boss.tables.values()):
        for chairIndex, status in table.dinerStatus.items():
            if status in (table.HUNGRY, table.ANGRY):
                boss.localToonTouchedChair(table.index, chairIndex)
                boss.autoplayServed = getattr(boss, 'autoplayServed', 0) + 1
                return


def scenarioCEO():
    # Serves the banquet, fights the diners who are left, and in the last
    # round seltzer hits the CEO.
    yield from teleport(ToontownGlobals.BossbotHQ, ToontownGlobals.BossbotLobby)
    yield from boardElevator('DistributedBBElevator')
    yield from fightBoss('BossbotHQBossBattle', 'DistributedBossbotBoss', {
        'BattleTwo': ceoBattleTwo,
        'BattleFour': lambda boss: boss.d_hitBoss(1),
    }, timeout=5400)


def fishingState(spot):
    return spot.fsm.getCurrentState().getName()


def watchFishingTargets():
    from toontown.fishing.DistributedFishingTarget import DistributedFishingTarget
    setState = DistributedFishingTarget.setState

    def recordingSetState(self, stateIndex, angle, radius, time, timeStamp):
        self.autoplayDest = self.getDestPos(angle, radius)
        setState(self, stateIndex, angle, radius, time, timeStamp)

    DistributedFishingTarget.setState = recordingSetState


def aimCast(spot):
    targets = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedFishingTarget'
               and do.pondDoId == spot.pondDoId]
    if not targets:
        spot.power = 0.6
        return
    parent = spot.angleNP.getParent()

    def resting(target):
        # Where the fish is swimming to; it waits there a few seconds.
        return getattr(target, 'autoplayDest', None) or target.getPos(render)

    center = min((parent.getRelativePoint(render, Point3(resting(target))) for target in targets),
                 key=lambda point: point.length())
    spot.angleNP.setH(math.degrees(math.atan2(-center[0], center[1])))
    distance = Vec3(center[0], center[1], 0).length()

    def landing(power):
        # The bob's flight in DistributedFishingSpot.moveBobTask.
        speed = power * spot.vZeroMax
        angle = math.radians(power * spot.angleMax)
        a, b, c = -16.1, speed * math.sin(angle), 8.5 - spot.waterLevel
        t = (-b - math.sqrt(b * b - 4 * a * c)) / (2 * a)
        return 3.0 + speed * math.cos(angle) * t

    spot.power = min((p / 100.0 for p in range(5, 101)), key=lambda power: abs(landing(power) - distance))


def scenarioFishing(casts=5):
    watchFishingTargets()
    yield from teleport(ToontownGlobals.ToontownCentral)
    yield until(lambda: findObject('DistributedFishingSpot', lambda do: do.avId == 0), 60, 'a free fishing spot')
    spot = findObject('DistributedFishingSpot', lambda do: do.avId == 0)
    log('walking onto fishing spot', spot.doId)
    messenger.send(spot.uniqueName('enterFishingSpotSphere'), [None])
    yield until(lambda: fishingState(spot) == 'waiting', 60, 'holding the fishing pole')
    caught = 0
    for cast in range(casts):
        yield sleep(2)
        # What dragging the cast button and letting go does, aimed at the
        # middle of where a fish swims.
        spot.fsm.request('localAdjusting')
        aimCast(spot)
        spot.fsm.request('localCasting')
        yield until(lambda: fishingState(spot) == 'fishing' or spot.avId != localAvatar.doId, 20, 'the bob landing')
        if fishingState(spot) == 'fishing':
            targets = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedFishingTarget'
                       and do.pondDoId == spot.pondDoId]
            bob = spot.bob.getPos(render)
            log('bob landed at %s, nearest fish %.1f away' % (
                bob, min([(target.getPos(render) - bob).length() for target in targets] or [-1])))
        yield until(lambda: fishingState(spot) in ('reward', 'waiting', 'localAdjusting') or
                    spot.avId != localAvatar.doId, 60, 'a bite')
        if spot.avId != localAvatar.doId:
            raise AssertionError('the fishing spot sent the toon away after %d casts' % cast)
        if fishingState(spot) == 'reward':
            caught += 1
        yield until(lambda: spot.track is None or not spot.track.isPlaying(), 30, 'reeling in')
    log('caught %d things in %d casts' % (caught, casts))
    spot._DistributedFishingSpot__userExit()
    yield until(walking, 60, 'walking after fishing')


def castOnce(spot):
    # One cast at the nearest fish; True if something was caught.
    spot.fsm.request('localAdjusting')
    aimCast(spot)
    spot.fsm.request('localCasting')
    yield until(lambda: fishingState(spot) == 'fishing' or spot.avId != localAvatar.doId, 20, 'the bob landing')
    # No bite in 20 seconds: reel in and cast again, as a player would, before
    # the spot's idle timer sends the toon away.
    end = time.time() + 20
    yield until(lambda: fishingState(spot) in ('reward', 'waiting', 'localAdjusting') or
                spot.avId != localAvatar.doId or time.time() > end, 30, 'a bite')
    if spot.avId != localAvatar.doId:
        raise StepFailed('the fishing spot sent the toon away')
    caught = fishingState(spot) == 'reward'
    yield until(lambda: spot.track is None or not spot.track.isPlaying(), 30, 'reeling in')
    return caught


def scenarioBingo(timeout=2400):
    # Plays Fish Bingo at the Toontown Central pond until the toon wins a
    # game, marking each catch on the card like a player clicking it.
    watchFishingTargets()
    onDistrict(lambda air: air.holidayManager.startHoliday(ToontownGlobals.FISH_BINGO_NIGHT))
    # Each cast costs a jellybean; the jackpot goes to the bank.
    onDistrict(lambda air, avId: (air.doId2do[avId].b_setMoney(air.doId2do[avId].getMaxMoney()),
                                  air.doId2do[avId].b_setBankMoney(0)), localAvatar.doId)
    yield from teleport(ToontownGlobals.ToontownCentral)
    yield until(lambda: findObject('DistributedFishingSpot', lambda do: do.avId == 0), 60, 'a free fishing spot')
    spot = findObject('DistributedFishingSpot', lambda do: do.avId == 0)
    messenger.send(spot.uniqueName('enterFishingSpotSphere'), [None])
    yield until(lambda: fishingState(spot) == 'waiting', 60, 'holding the fishing pole')
    pond = base.cr.doId2do[spot.pondDoId]
    yield until(lambda: getattr(pond, 'pondBingoMgr', None) is not None, 60, 'the pond bingo manager')
    mgr = pond.pondBingoMgr
    yield until(lambda: mgr.state == 'Playing', 120, 'a bingo game')
    log('bingo game %d started, card type %d, jackpot %d' % (mgr.cardId, mgr.typeId, mgr.jackpot))
    games = set([mgr.cardId])
    end = time.time() + timeout
    while mgr.state != 'Reward':
        if time.time() > end:
            raise StepFailed('no bingo in %d games' % len(games))
        # Keeps fishing between games too; an idle spot sends the toon away.
        yield sleep(1)
        if mgr.state == 'Playing' and mgr.cardId not in games:
            games.add(mgr.cardId)
            log('bingo game %d started, card type %d' % (mgr.cardId, mgr.typeId))
        # A trip to the Fisherman between casts: sell the bucket, and keep
        # jellybeans for casting.
        onDistrict(lambda air, avId: (air.doId2do[avId].b_setFishTank([], [], []),
                                      air.doId2do[avId].b_setMoney(air.doId2do[avId].getMaxMoney())), localAvatar.doId)
        caught = yield from castOnce(spot)
        if caught and mgr.lastCatch is not None and mgr.state == 'Playing':
            matches = mgr.card.getUnmarkedMatches(mgr.lastCatch)
            if matches:
                mgr.checkForUpdate(matches[0].cellId)
                log('marked cell %d for %s' % (matches[0].cellId, mgr.lastCatch if mgr.lastCatch else 'the catch'))
            if mgr.card.checkForBingo():
                log('Bingo!')
                mgr.checkForBingo()
    yield until(lambda: localAvatar.getBankMoney() > 0, 30, 'the jackpot')
    log('won the bingo jackpot after %d games' % len(games))
    onDistrict(lambda air: air.holidayManager.endHoliday(ToontownGlobals.FISH_BINGO_NIGHT))
    spot._DistributedFishingSpot__userExit()
    yield until(walking, 60, 'walking after fishing')


def scenarioEstate():
    yield until(walking, 60, 'walking before going home')
    log('going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')
    me = localAvatar.doId
    yield until(lambda: findObject('DistributedHouse', lambda do: do.ownerId == me), 60, 'the toon\'s own house')
    house = findObject('DistributedHouse', lambda do: do.ownerId == me)
    houses = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedHouse']
    log('%d houses on the estate; ours is %d' % (len(houses), house.doId))
    yield until(lambda: findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD),
                60, 'the front door')
    door = findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD)
    yield sleep(2)
    log('going inside')
    messenger.send(door.getEnterTriggerEvent(), [None])
    yield until(lambda: placeName() == 'House' and walking(), 120, 'walking inside the house')
    furniture = [do for do in base.cr.doId2do.values() if 'Furniture' in do.__class__.__name__]
    log('inside, with %d pieces of furniture' % len(furniture))
    yield sleep(3)
    yield from teleport(ToontownGlobals.ToontownCentral)


def restock(air, avId):
    # Stands in for a trip to the Gag Shop and the playground between
    # fights, so a new 15-laff toon does not go sad.
    av = air.doId2do[avId]
    av.b_setHp(av.getMaxHp())
    av.inventory.maxOutInv()
    av.b_setInventory(av.inventory.makeNetString())


def scenarioPets():
    # Adopts a doodle at the Toontown Central pet shop, then meets it on the
    # estate and plays with it.
    from toontown.building.PetshopBuildingAI import PetshopBuildingAI
    from toontown.pets import PetConstants

    def petshopBlock(air):
        buildings = air.buildingManagers[ToontownGlobals.ToontownCentral]._DistributedBuildingMgrAI__buildings
        return next(block for block, building in buildings.items() if isinstance(building, PetshopBuildingAI))

    def giveBeans(air, avId):
        av = air.doId2do[avId]
        av.b_setMoney(av.getMaxMoney())
        av.b_setBankMoney(av.getMaxBankMoney())

    yield from teleport(ToontownGlobals.ToontownCentral)
    onDistrict(giveBeans, localAvatar.doId)
    block = onDistrict(petshopBlock)
    door = lambda doorType: findObject('DistributedDoor', lambda do: do.block == block and do.doorType == doorType)
    yield until(lambda: door(DoorTypes.EXT_STANDARD), 60, 'the pet shop door')
    yield sleep(2)
    log('going into the pet shop (block %d)' % block)
    messenger.send(door(DoorTypes.EXT_STANDARD).getEnterTriggerEvent(), [None])
    yield until(lambda: findObject('DistributedNPCPetclerk') and walking(), 120, 'walking in the pet shop')
    clerk = findObject('DistributedNPCPetclerk')
    log('talking to', clerk.getName())
    clerk.handleCollisionSphereEnter(None)
    yield until(lambda: getattr(clerk, 'petshopGui', None) is not None, 30, 'the pet shop')
    log('pets for adoption today: %s' % (clerk.petSeeds,))
    messenger.send(clerk.eventDict['petAdopted'], [0, 1])
    yield until(localAvatar.hasPet, 30, 'owning a doodle')
    log('adopted doodle', localAvatar.getPetId())
    messenger.send(clerk.eventDict['guiDone'])
    yield until(walking, 60, 'walking after adopting')
    yield sleep(2)
    messenger.send(door(DoorTypes.INT_STANDARD).getEnterTriggerEvent(), [None])
    yield until(lambda: placeName() == 'TTPlayground' and walking(), 120, 'walking out of the pet shop')

    log('going home to meet the doodle')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and placeState() in ('walk', 'petTutorial'), 180, 'arriving at the estate')
    if placeState() == 'petTutorial':
        log('reading the doodle tutorial')
        yield sleep(2)
        place().petTutorial._PetTutorial__handleQuit()
    yield until(walking, 60, 'walking around the estate')
    petId = localAvatar.getPetId()
    yield until(lambda: petId in base.cr.doId2do, 60, 'the doodle on the estate')
    pet = base.cr.doId2do[petId]
    petName = pet.getName()
    log('the doodle %s is here, feeling %s' % (pet.getName(), pet.mood.getDominantMood() if hasattr(pet, 'mood') else '?'))
    for flag, name in ((PetConstants.PET_MOVIE_CALL, 'calling'), (PetConstants.PET_MOVIE_SCRATCH, 'scratching'),
                       (PetConstants.PET_MOVIE_FEED, 'feeding')):
        pet.autoplayMovies = []
        setMovie = pet.setMovie

        def recordMovie(mode, avId, timestamp, setMovie=setMovie, pet=pet):
            pet.autoplayMovies.append(mode)
            setMovie(mode, avId, timestamp)

        pet.setMovie = recordMovie
        log(name, 'the doodle')
        localAvatar.sendUpdate('setPetMovie', [petId, flag])
        yield until(lambda: PetConstants.PET_MOVIE_CLEAR in pet.autoplayMovies or flag in pet.autoplayMovies,
                    60, 'the doodle to answer %s' % name)
        yield until(lambda: PetConstants.PET_MOVIE_CLEAR in pet.autoplayMovies, 60, 'the doodle to finish')
        log('doodle movies:', pet.autoplayMovies)
        pet.setMovie = setMovie
        yield sleep(1)
    # Asking for a trick with SpeedChat: an untrained doodle balks, which is
    # a trick movie too.
    from toontown.pets import PetTricks
    tricks = []
    doTrick = pet.doTrick
    pet.doTrick = lambda trickId, timestamp: (tricks.append(trickId), doTrick(trickId, timestamp))
    jump = PetTricks.TrickId2scIds[PetTricks.Tricks.JUMP][0]
    log('asking the doodle to jump')
    localAvatar.b_setSC(jump)
    yield until(lambda: tricks, 60, 'the doodle to try a trick')
    log('the doodle did trick %d (%s)' % (tricks[0], 'balked' if tricks[0] == PetTricks.Tricks.BALK else 'jumped'))
    pet.doTrick = doTrick
    if not localAvatar.bPetTutorialDone:
        raise StepFailed('the doodle tutorial was never shown')

    # Calling the doodle for help in a cog battle, through the SOS panel.
    street = ToontownGlobals.SillyStreet
    yield from teleport(street - street % 1000, firstVisgroup(street))
    onDistrict(restock, localAvatar.doId)
    for attempt in range(5):
        magicWord('~spawn f 1')
        yield until(suitsNearby, 120, 'a cog on the street')
        suit = min(suitsNearby(), key=lambda s: (s.getPos(render) - localAvatar.getPos(render)).length())
        while placeState() == 'walk' and not suit.isEmpty():
            localAvatar.setPos(render, suit.getPos(render))
            yield sleep(0.1)
        if placeState() != 'walk':
            break
    yield until(lambda: townBattleState() == 'Attack', 120, 'the first gag choice')
    log('calling the doodle for help')
    townBattle().fsm.request('SOS')
    townBattle()._TownBattle__handleSOSPanelDone({'mode': 'Pet', 'petId': petId, 'petName': petName})
    yield until(lambda: townBattleState() == 'SOSPetInfo', 60, 'the doodle to come to the battle')
    townBattle()._TownBattle__handleSOSPetInfoPanelDone({'mode': 'OK', 'trickId': PetTricks.Tricks.JUMP})
    yield until(lambda: townBattleState() != 'AttackWait', 120, 'the doodle\'s turn')
    log('the doodle helped; gag panel now', townBattleState())
    yield from fightBattle()
    yield until(walking, 120, 'walking after the battle')
    yield from teleport(ToontownGlobals.ToontownCentral)


def raceState(race):
    return race.fsm.getCurrentState().getName()


def driveKart(race):
    # Drives the local kart the way a player holding the arrow keys would:
    # full throttle, steering toward a pole a little way down the track.
    def drive(task):
        if race.isDisabled() or raceState(race) != 'racing':
            return task.done
        kart = race.localKart
        pos = kart.getPos(render)
        goal = race.curvePoints[(race.currentPole + 3) % len(race.curvePoints)]
        offset = Vec3(goal - pos)
        wanted = math.degrees(math.atan2(-offset[0], offset[1]))
        error = (wanted - kart.getH(render) + 180) % 360 - 180
        kart.arrowVert = 1
        # A positive arrowHorz turns the kart clockwise (its heading drops).
        kart.arrowHorz = max(-1.0, min(1.0, -error / 20.0))
        return task.cont

    taskMgr.add(drive, 'autoplay-drive-kart')


def scenarioRacing():
    from toontown.racing import KartDNA, RaceGlobals
    yield from teleport(ToontownGlobals.GoofySpeedway)
    if not localAvatar.hasKart():
        magicWord('~setTickets %d' % RaceGlobals.MaxTickets)
        yield until(lambda: localAvatar.getTickets() == RaceGlobals.MaxTickets, 30, 'race tickets')
        # The kart clerks work inside the kart shop.
        door = lambda doorType: findObject('DistributedDoor', lambda do: do.doorType == doorType)
        yield until(lambda: door(DoorTypes.EXT_KS), 60, 'the kart shop door')
        yield sleep(2)
        log('going into the kart shop')
        messenger.send(door(DoorTypes.EXT_KS).getEnterTriggerEvent(), [None])
        yield until(lambda: findObject('DistributedNPCKartClerk') and walking(), 120, 'walking in the kart shop')
        clerk = findObject('DistributedNPCKartClerk')
        log('buying a kart from', clerk.getName())
        clerk.handleCollisionSphereEnter(None)
        yield until(lambda: clerk.kartShopGui is not None, 30, 'the kart shop')
        kartId = min(KartDNA.KartDict, key=KartDNA.getKartCost)
        clerk._DistributedNPCKartClerk__handleBuyKart(kartId)
        yield until(localAvatar.hasKart, 30, 'owning a kart')
        clerk._DistributedNPCKartClerk__handleGuiDone()
        yield until(walking, 60, 'walking after buying the kart')
        yield sleep(2)
        messenger.send(door(DoorTypes.INT_KS).getEnterTriggerEvent(), [None])
        yield until(lambda: placeName() == 'GSPlayground' and walking(), 120, 'walking out of the kart shop')
    yield until(lambda: findObject('DistributedStartingBlock',
                                   lambda do: do.kartPad and getattr(do.kartPad, 'isPractice', lambda: False)() and do.avId == 0),
                60, 'a practice starting block')
    block = findObject('DistributedStartingBlock',
                       lambda do: do.kartPad and getattr(do.kartPad, 'isPractice', lambda: False)() and do.avId == 0)
    yield sleep(2)
    log('getting on a practice starting block for track', block.kartPad.trackId)
    localAvatar.setPos(render, block.nodePath.getPos(render))
    messenger.send(block.uniqueName('enterStartingBlockSphere'), [None])
    yield until(lambda: getattr(block, 'dialog', None) is not None, 10, 'the practice dialog')
    block.dialog.doneStatus = 'ok'
    messenger.send('enterRequest|dialog')
    yield until(lambda: findObject('DistributedRace'), 180, 'the race')
    race = findObject('DistributedRace')
    yield until(lambda: raceState(race) in ('tutorial', 'waiting', 'start', 'racing'), 120, 'the race rules')
    if raceState(race) == 'tutorial':
        messenger.send(race.rulesDoneEvent)
    yield until(lambda: raceState(race) == 'racing', 120, 'the starting light')
    log('racing %d laps on track %d' % (race.lapCount, race.trackId))
    driveKart(race)
    deadline = time.time() + 1200
    nextReport = time.time() + 30
    while raceState(race) == 'racing':
        if time.time() > deadline:
            raise StepFailed('still racing after 1200 seconds, lap %d' % race.laps)
        if time.time() > nextReport:
            nextReport = time.time() + 30
            log('lap %d, %.2f of the way round' % (race.laps, race.currLapT))
        yield sleep(0.5)
    log('race over in state', raceState(race))
    yield sleep(5)
    messenger.send('leaveRace')
    yield until(lambda: placeName() == 'GSPlayground' and walking(), 120, 'walking at the speedway again')


def golfState(do):
    return do.state if do is not None else None


def swingGolf(hole, power):
    # Holds the swing button and lets go when the power bar reads power,
    # as a player watching the bar would.
    elapsed = math.pow(power / 100.0, 1.0 / hole.golfPowerExponent) * hole.golfPowerSpeed
    hole._DistributedGolfHole__beginTossGolf()
    hole.aimStart = globalClock.getFrameTime() - elapsed
    hole.power = power
    taskMgr.remove(hole.golfPowerTaskName)
    hole._DistributedGolfHole__endTossGolf()


def scenarioGolf():
    yield from teleport(ToontownGlobals.GolfZone)
    yield until(lambda: findObject('DistributedGolfKart', lambda do: do.golfCourse == 0), 60, 'the golf kart')
    kart = findObject('DistributedGolfKart', lambda do: do.golfCourse == 0)
    yield sleep(2)
    log('getting in the golf kart for course', kart.golfCourse)
    messenger.send('entergolfkart_sphere_%d' % kart.doId, [None])
    yield until(lambda: findObject('DistributedGolfCourse'), 180, 'the golf course')
    course = findObject('DistributedGolfCourse')
    distancePerPower = 0.5
    deadline = time.time() + 1800
    nextReport = time.time() + 30
    holesSeen = set()
    while not course.isDisabled() and golfState(course) not in ('WaitReward', 'Cleanup'):
        if time.time() > deadline:
            raise StepFailed('the golf course did not finish in 1800 seconds')
        hole = base.cr.doId2do.get(course.curHoleDoId)
        if time.time() > nextReport:
            nextReport = time.time() + 30
            log('golf course %s, hole %s' % (golfState(course), golfState(hole)))
        if hole is None or hole.currentGolfer != localAvatar.doId:
            yield sleep(0.5)
            continue
        if hole.doId not in holesSeen:
            holesSeen.add(hole.doId)
            log('playing hole %d of %d (par %d)' % (len(holesSeen), course.numHoles, hole.holeInfo['par']))
        if golfState(hole) == 'ChooseTee' and not hole.localAvatarChosenTee:
            yield sleep(1)
            hole.sendTeeInfo()
        elif golfState(hole) == 'Aim' and not hole.swingInfoSent:
            yield sleep(1)
            hole.ballFollow.headsUp(hole.holeBottomNodePath)
            start = hole.ballFollow.getPos(render)
            distance = (hole.holeBottomNodePath.getPos(render) - start).length()
            power = int(max(5, min(100, distance / distancePerPower)))
            swingGolf(hole, power)
            yield until(lambda: golfState(hole) != 'Aim', 30, 'the swing')
            yield until(lambda: hole.isDisabled() or golfState(hole) not in ('Playback',), 120, 'the ball stopping')
            if not hole.isDisabled():
                moved = (hole.ballFollow.getPos(render) - start).length()
                if moved > 1:
                    # Learn how far a point of power sends the ball.
                    distancePerPower = max(0.2, min(1.5, moved / power))
                log('swung at %d power from %.0f away; the ball went %.0f' % (power, distance, moved))
        else:
            yield sleep(0.2)
    log('golf course over; scores', course.scores.get(localAvatar.doId))
    yield until(lambda: placeName() == 'GZPlayground' and walking(), 180, 'walking at the golf zone again')


QUEST_COGS = {'c': 'f', 'l': 'bf', 'm': 'sc', 's': 'cc'}


def recordNPCMovies():
    from toontown.toon.DistributedNPCToon import DistributedNPCToon
    if getattr(DistributedNPCToon, 'autoplayRecording', False):
        return
    setMovie = DistributedNPCToon.setMovie

    def recordingSetMovie(self, mode, npcId, avId, quests, timestamp):
        if avId == localAvatar.doId:
            self.autoplayMovie = (mode, quests)
        setMovie(self, mode, npcId, avId, quests, timestamp)

    DistributedNPCToon.setMovie = recordingSetMovie
    DistributedNPCToon.autoplayRecording = True


def goToNPC(npcId):
    # Walks in through the front door of the building the NPC works in.
    from toontown.quest import Quests
    from toontown.toon import NPCToons
    if npcId == Quests.ToonHQ:
        zoneId, name = ToontownGlobals.ToontownCentral + 520, None
    else:
        zoneId, name = NPCToons.NPCToonDict[npcId][0], NPCToons.NPCToonDict[npcId][1]
    hoodId = ZoneUtil.getCanonicalHoodId(zoneId)
    branchId = ZoneUtil.getCanonicalBranchZone(zoneId)
    block = zoneId % 100
    if branchId == hoodId:
        yield from teleport(hoodId)
    else:
        yield from teleport(hoodId, firstVisgroup(branchId))
        outside = base.cr.playGame.dnaData.getBlock(block).zone
        if outside != localAvatar.zoneId:
            yield from teleport(hoodId, outside)
    isNPC = lambda do: (hasattr(do, 'questChoiceGui') and do.zoneId % 1000 >= 500
                        and (name is None or do.getName() == name))
    # Quest NPCs are DistributedNPCToons or subclasses of it (Flippy in
    # Toon Hall, for one).
    findNPC = lambda: next((do for do in list(base.cr.doId2do.values()) if isNPC(do)), None)
    def reclaim(air, branchId, block):
        # A cog building in the way stands in for one the toon has already
        # beaten (the building scenario tests that part).
        building = air.buildingManagers[branchId].getBuilding(block)
        if building.isSuitBlock():
            building.toonTakeOver()
            return True
        return False

    if not findNPC() and branchId != hoodId and onDistrict(reclaim, branchId, block):
        log('building %d of zone %d was a cog building; taking it back' % (block, branchId))
        yield sleep(15)
    if not findNPC():
        door = lambda: findObject('DistributedDoor', lambda do: do.block == block and do.doorType in (
            DoorTypes.EXT_STANDARD, DoorTypes.EXT_HQ))
        yield until(door, 60, 'the door of building %d' % block)
        yield sleep(2)
        log('going into building %d of zone %d for %s' % (block, branchId, name or 'an HQ officer'))
        messenger.send(door().getEnterTriggerEvent(), [None])
    yield until(lambda: findNPC() and walking(), 120, 'walking up to %s' % (name or 'an HQ officer'))
    return findNPC()


def talkTo(npc, pickQuest=None):
    # Talks to an NPC and answers whatever it asks.
    log('talking to', npc.getName())
    npc.autoplayMovie = None
    npc.handleCollisionSphereEnter(None)
    yield until(lambda: npc.autoplayMovie is not None, 30, '%s to answer' % npc.getName())
    yield sleep(1)
    mode, quests = npc.autoplayMovie
    if npc.questChoiceGui is not None:
        choices = [quests[i:i + 3] for i in range(0, len(quests), 3)]
        questId = pickQuest(choices)
        log('offered ToonTasks %s; choosing %d' % ([c[0] for c in choices], questId))
        messenger.send('chooseQuest', [questId])
        yield until(lambda: npc.autoplayMovie[1] is not quests, 30, 'the ToonTask to be given')
        yield sleep(1)
    elif npc.trackChoiceGui is not None:
        log('choosing gag track', quests[0])
        messenger.send('chooseTrack', [quests[0]])
        yield until(lambda: npc.autoplayMovie[1] is not quests, 30, 'the track to be given')
        yield sleep(1)
    # Click through the speech pages; a scripted movie such as Tutorial
    # Tom's has a dozen of them.
    deadline = time.time() + 300
    while not walking():
        if time.time() > deadline:
            raise StepFailed('still talking to %s' % npc.getName())
        messenger.send(npc.uniqueName('doneChatPage'), [0])
        if TUTORIAL:
            pressShownBookButton()
        yield sleep(1.5)


def pressShownBookButton():
    # The HQ officer's Toontorial movie waits for the player to open the
    # Shticker Book, turn its pages and close it, showing each button in turn.
    book = localAvatar.book
    for button in (book.bookOpenButton, book.nextArrow, book.bookCloseButton):
        if not button.isEmpty() and not button.isHidden() and button['command']:
            log('pressing the Shticker Book button', button.getName())
            button['command'](*button['extraArgs'])
            return


def defeatCogsFor(questId, quest):
    from toontown.quest import Quests
    if isinstance(quest, Quests.CogTrackQuest):
        cog, level = QUEST_COGS[quest.getCogTrack()], 1
    elif isinstance(quest, Quests.CogLevelQuest):
        cog, level = 'f', quest.getCogLevel()
    elif isinstance(quest, Quests.CogQuest) and quest.getCogType() != Quests.Any:
        cog, level = quest.getCogType(), 1
    else:
        cog, level = 'f', 1
    done = lambda: quest.getCompletionStatus(localAvatar, next(q for q in localAvatar.quests if q[0] == questId)) == Quests.COMPLETE
    street = ToontownGlobals.SillyStreet
    yield from teleport(street - street % 1000, firstVisgroup(street))
    while not done():
        onDistrict(restock, localAvatar.doId)
        magicWord('~spawn %s %d' % (cog, level))
        yield until(suitsNearby, 120, 'a cog on the street')
        suit = min(suitsNearby(), key=lambda s: (s.getPos(render) - localAvatar.getPos(render)).length())
        while placeState() == 'walk' and not suit.isEmpty():
            localAvatar.setPos(render, suit.getPos(render))
            yield sleep(0.1)
        if placeState() != 'walk':
            yield from fightBattle()
            yield until(walking, 120, 'walking after the battle')
        log('ToonTask progress:', quest.getProgressString(localAvatar, next(q for q in localAvatar.quests if q[0] == questId)))


def scenarioToonHall():
    # Walks into Toon Hall, where Flippy and the Loony Labs scientists work.
    # The scientists stay hidden unless the Silly Meter holiday is on.
    from toontown.toon import NPCToons
    npc = yield from goToNPC(2001)
    log('in Toon Hall with', npc.getName())
    aiObjects = lambda air, zoneId: sorted(do.__class__.__name__ for do in list(air.doId2do.values())
                                          if getattr(do, 'zoneId', None) == zoneId)
    expected = onDistrict(aiObjects, localAvatar.zoneId).count('DistributedNPCScientistAI')
    scientists = lambda: [do for do in list(base.cr.doId2do.values())
                          if do.__class__.__name__ == 'DistributedNPCScientist']
    yield until(lambda: expected and len(scientists()) == expected, 60, 'the %d scientists' % expected)
    for scientist in scientists():
        log('scientist %s, %s' % (scientist.getName(), 'shown' if not scientist.isHidden() else 'hidden until the Silly Meter'))
        scientist.handleCollisionSphereEnter(None)
    yield sleep(5)
    door = lambda: findObject('DistributedDoor', lambda do: do.doorType == DoorTypes.INT_STANDARD)
    yield until(door, 30, 'the Toon Hall door')
    messenger.send(door().getEnterTriggerEvent(), [None])
    yield until(lambda: walking() and localAvatar.zoneId == ToontownGlobals.ToontownCentral, 120, 'back outside')


def scenarioElection():
    # The Toon Council election and the cog invasion of Toontown Central
    # that follows it. Needs want-doomsday 1 (AUTOPLAY_PRC).
    yield from teleport(ToontownGlobals.ToontownCentral)
    yield until(lambda: findObject('DistributedElectionEvent'), 60, 'the election')
    election = findObject('DistributedElectionEvent')
    onDistrict(lambda air: air.doFind('ElectionEvent').b_setState('Event'))
    states = []

    def stateIs(name):
        if election.state not in states:
            states.append(election.state)
            log('election: %s' % election.state)
        return election.state == name

    yield until(lambda: stateIs('Invasion'), 420, 'the cogs to invade')
    yield until(lambda: findObject('DistributedSafezoneInvasion'), 60, 'the invasion')
    invasion = findObject('DistributedSafezoneInvasion')
    election.sendUpdate('wheelbarrowAvatarEnter', [])
    yield until(lambda: localAvatar.numPies > 0, 30, 'pies from Flippy')

    def invasionState(air):
        return air.doFind('SafezoneInvasion').state, air.doFind('SafezoneInvasion').waveNumber

    def splatSuits():
        for suit in list(base.cr.doId2do.values()):
            if suit.__class__.__name__ == 'DistributedInvasionSuit' and suit.zoneId == ToontownGlobals.ToontownCentral:
                invasion.d_pieHitSuit(suit.doId)

    def fightWave(wave):
        while onDistrict(invasionState) in (('BeginWave', wave), ('Wave', wave)):
            splatSuits()
            yield sleep(0.5)
        log('wave %d won: invasion now %s' % (wave, onDistrict(invasionState)))

    yield from fightWave(0)

    def lastWave(air):
        from toontown.election import SafezoneInvasionGlobals
        invasion = air.doFind('SafezoneInvasion')
        invasion.lastWave = True
        invasion.demand('BeginWave', len(SafezoneInvasionGlobals.SuitWaves) - 1)
        return invasion.waveNumber

    yield until(lambda: onDistrict(invasionState)[0] in ('Intermission', 'BeginWave', 'Wave'), 60, 'the next wave')
    wave = onDistrict(lastWave)
    yield from fightWave(wave)
    yield until(lambda: onDistrict(invasionState)[0] == 'Finale', 60, 'the boss')
    log('the boss is coming')
    yield until(lambda: stateIs('InvasionEnd'), 400, 'Flippy to face the boss')
    yield until(lambda: onDistrict(invasionState)[0] == 'Victory', 200, 'the boss to explode')
    log('Toontown Central is saved')
    yield until(lambda: stateIs('WrapUp'), 200, 'the wrap-up')
    log('election states seen: %s' % states)


def scenarioToonfest():
    # ToonFest: whack the cog pinata to spin the tower, and bounce on the
    # victory trampoline for ToonFest tokens.
    yield from teleport(ToontownGlobals.ToonFest)
    yield until(lambda: findObject('DistributedToonfestCog') and findObject('DistributedToonfestVictoryTrampolineActivity'), 60, 'the ToonFest activities')

    def countTowerHits(air):
        cog = air.doFind('ToonfestCog')
        cog.hits = 0
        updateTower = cog.updateTower

        def counted(avName):
            cog.hits += 1
            updateTower(avName)
        cog.updateTower = counted

    onDistrict(countTowerHits)
    cog = findObject('DistributedToonfestCog')
    yield until(lambda: cog.state == 'Up', 30, 'the cog to pop up')
    cog.respondToPieHit(cog.timestamp, cog.position)
    yield until(lambda: onDistrict(lambda air: air.doFind('ToonfestCog').hits), 30, 'the tower to hear of the hit')
    log('hit the ToonFest cog')

    tramp = findObject('DistributedToonfestVictoryTrampolineActivity')
    tokens = localAvatar.getTokens()
    tramp.onTrampolineTrigger(None)
    yield until(lambda: tramp.activityFSM.state == 'Rules', 30, 'the trampoline rules')
    tramp.handleRulesDone()
    yield until(lambda: tramp.activityFSM.state == 'Active', 30, 'the trampoline to start')
    yield sleep(3)
    tramp.collectJellyBeans(10000)
    log('collected %d trampoline jellybeans' % tramp.numBeansCollected)
    yield until(lambda: localAvatar.getTokens() > tokens, 120, 'ToonFest tokens from the trampoline')
    # Click OK on the reward panel.
    yield sleep(2)
    messenger.send(tramp.showRewardDoneEvent)
    yield until(walking, 60, 'walking off the trampoline')
    log('the trampoline gave %d tokens' % (localAvatar.getTokens() - tokens))

    balloon = findObject('DistributedToonfestBalloon')
    balloon.sendUpdate('requestEnter', [])
    yield until(lambda: balloon.state == 'StartRide', 30, 'the balloon to take off')
    log('riding the balloon with Alec')
    yield until(lambda: balloon.state == 'RideOver', 120, 'the balloon ride to end')
    yield until(walking, 60, 'walking after the balloon ride')
    log('balloon ride over at %s' % localAvatar.getPos(render))


def scenarioHolidays():
    # Checks that the holidays the calendar runs today reach the client, then
    # starts and ends a holiday the way the calendar would.
    import time
    expected = onDistrict(lambda air: air.holidayManager.getHolidaysAt(time.localtime()))
    yield until(lambda: sorted(base.cr.newsManager.getHolidayIdList()) == sorted(expected), 60, 'the holidays %s' % expected)
    log('holidays running today:', expected)
    yield from teleport(ToontownGlobals.ToontownCentral)
    yield sleep(5)
    for holidayId in (ToontownGlobals.WINTER_DECORATIONS, ToontownGlobals.HALLOWEEN_PROPS, ToontownGlobals.VALENTINES_DAY):
        running = holidayId in expected
        action = 'endHoliday' if running else 'startHoliday'
        onDistrict(lambda air: getattr(air.holidayManager, action)(holidayId))
        yield until(lambda: (holidayId in base.cr.newsManager.getHolidayIdList()) != running, 30, 'holiday %d to change' % holidayId)
        log('holiday %d %s' % (holidayId, 'ended' if running else 'started'))
        yield sleep(5)
    yield from teleport(ToontownGlobals.DonaldsDock)
    yield sleep(5)


def scenarioHolidayEffects():
    # The holidays that change the game rather than its looks: a cog
    # invasion, double experience, jellybean day and extra fireworks.
    G = ToontownGlobals

    def invasion(air):
        mgr = air.suitInvasionManager
        return mgr.getInvading(), mgr.suitName

    onDistrict(lambda air: air.holidayManager.startHoliday(G.YES_MAN_INVASION))
    yield until(lambda: onDistrict(invasion) == (True, 'ym'), 30, 'the Yes Man invasion')
    yield until(lambda: base.cr.newsManager.isHolidayRunning(G.YES_MAN_INVASION), 30, 'the client to hear of the invasion')
    log('Yes Men are invading')
    onDistrict(lambda air: air.holidayManager.endHoliday(G.YES_MAN_INVASION))
    yield until(lambda: not onDistrict(invasion)[0], 30, 'the invasion to end')

    def jellybeans(air):
        from toontown.fishing import FishGlobals
        return air.holidayManager.getPartyJellybeanMultiplier(), FishGlobals.getValue(0, 0, 1.0)

    before = onDistrict(jellybeans)
    onDistrict(lambda air: air.holidayManager.startHoliday(G.JELLYBEAN_DAY))
    yield until(lambda: base.cr.newsManager.isHolidayRunning(G.JELLYBEAN_DAY), 30, 'jellybean day')
    after = onDistrict(jellybeans)
    if after[0] != 2 * before[0] or after[1] != 2 * before[1]:
        raise StepFailed('jellybean day gave %s, before %s' % (after, before))
    log('jellybean day doubles party (%s -> %s) and fish (%s -> %s) jellybeans' % (before[0], after[0], before[1], after[1]))
    onDistrict(lambda air: air.holidayManager.endHoliday(G.JELLYBEAN_DAY))

    onDistrict(lambda air: air.holidayManager.startHoliday(G.MORE_XP_HOLIDAY))
    yield until(lambda: base.cr.newsManager.isHolidayRunning(G.MORE_XP_HOLIDAY), 30, 'double experience')
    # A sturdier toon, so the fight is won rather than lost.
    onDistrict(lambda air, avId: air.doId2do[avId].b_setMaxHp(100), localAvatar.doId)
    onDistrict(restock, localAvatar.doId)
    yield sleep(1)
    exp = list(localAvatar.experience.experience)
    yield from scenarioBattle()
    gained = [new - old for new, old in zip(localAvatar.experience.experience, exp)]
    log('experience gained in a double experience battle: %s' % gained)
    maxed = all(e >= ToontownBattleGlobals.regMaxSkill for e in exp)
    if not any(gained) and not maxed:
        raise StepFailed('no experience from the battle')
    onDistrict(lambda air: air.holidayManager.endHoliday(G.MORE_XP_HOLIDAY))

    yield from teleport(ToontownGlobals.ToontownCentral)
    onDistrict(lambda air: air.holidayManager.startFireworks(air.holidayManager.FireworksHolidays[G.OCTOBER31_FIREWORKS]))
    yield until(lambda: findObject('DistributedFireworkShow'), 30, 'the fireworks show')
    log('fireworks are going off')


def scenarioScavengerHunts():
    # Trick-or-treats and carols through every shop of both scavenger hunts,
    # checking the jellybeans for each shop and the head for finishing.
    from toontown.ai import ScavengerHuntGlobals
    from toontown.toon import NPCToons
    from otp.speedchat.SpeedChatGlobals import SCCustomMsgEvent
    from toontown.speedchat.TTSCIndexedTerminal import TTSCIndexedMsgEvent

    def prepare(air, avId):
        av = air.doId2do[avId]
        if 10003 not in av.getCustomMessages():
            av.b_setCustomMessages(av.getCustomMessages() + [10003])
        av.b_setScavengerHuntGoals([])
        av.b_setCheesyEffect(ToontownGlobals.CENormal, 0, 0)
        for holidayId in ScavengerHuntGlobals.Hunts:
            air.holidayManager.startHoliday(holidayId)

    onDistrict(prepare, localAvatar.doId)
    hunts = [(ToontownGlobals.TRICK_OR_TREAT, 'trickOrTreatTargetMet', lambda: messenger.send(SCCustomMsgEvent, [10003])),
             (ToontownGlobals.WINTER_CAROLING, 'winterCarolingTargetMet', lambda: messenger.send(TTSCIndexedMsgEvent, [30220]))]
    for holidayId, rewardField, sayPhrase in hunts:
        goals, effect = ScavengerHuntGlobals.Hunts[holidayId]
        rewards = []
        original = getattr(localAvatar, rewardField)
        setattr(localAvatar, rewardField, lambda beans, original=original: (rewards.append(beans), original(beans)))
        for goal, zoneId in sorted(goals.items()):
            npc = yield from goToNPC(NPCToons.zone2NpcDict[zoneId][0])
            yield until(lambda: findObject('DistributedScavengerHuntTarget') or findObject('DistributedTrickOrTreatTarget')
                        or findObject('DistributedWinterCarolingTarget'), 30, 'the hunt target in %s' % npc.getName())
            count = len(rewards)
            sayPhrase()
            yield until(lambda: len(rewards) > count, 30, 'the reward in zone %d' % zoneId)
            log('holiday %d goal %d in zone %d: %d jellybeans' % (holidayId, goal, zoneId, rewards[-1]))
            if rewards[-1] != ScavengerHuntGlobals.BeanReward:
                raise StepFailed('expected %d jellybeans' % ScavengerHuntGlobals.BeanReward)
        yield until(lambda: localAvatar.savedCheesyEffect == effect, 30, 'the cheesy effect %d' % effect)
        log('got cheesy effect', effect)
        # Coming back to a shop already visited gives nothing.
        yield sleep(16)
        count = len(rewards)
        sayPhrase()
        yield until(lambda: len(rewards) > count, 30, 'the repeat answer')
        if rewards[-1] != 0:
            raise StepFailed('a repeat visit paid %d jellybeans' % rewards[-1])
        log('a repeat visit pays nothing')
        setattr(localAvatar, rewardField, original)
    # The Snowman Head goes once caroling is over.
    onDistrict(lambda air: air.holidayManager.endHoliday(ToontownGlobals.WINTER_CAROLING))
    onDistrict(lambda air, avId: air.doId2do[avId].b_setCheesyEffect(*air.doId2do[avId].getCheesyEffect()), localAvatar.doId)
    yield until(lambda: localAvatar.savedCheesyEffect == ToontownGlobals.CENormal, 30, 'the Snowman Head to go')
    log('the Snowman Head went with the holiday')


def scenarioSillyMeter():
    # Runs the Silly Meter through all its phases in Toon Hall, with the
    # scientists, and checks the Zero props' managers come and go.
    meter = ToontownGlobals.SILLYMETER_HOLIDAY
    onDistrict(lambda air: air.holidayManager.startHoliday(meter))
    yield until(lambda: hasattr(base.cr, 'SillyMeterMgr') and meter in base.cr.newsManager.getHolidayIdList(), 60, 'the Silly Meter manager')
    npc = yield from goToNPC(2001)
    interior = findObject('DistributedToonHallInterior')
    yield until(lambda: interior.sillyFSM.getCurrentState().getName() == 'Phase0', 30, 'the Silly Meter at phase 0')
    scientists = [do for do in list(base.cr.doId2do.values()) if do.__class__.__name__ == 'DistributedNPCScientist']
    if not scientists or any(scientist.isHidden() for scientist in scientists):
        raise StepFailed('the scientists are not out for the Silly Meter')
    for phase in range(1, 16):
        onDistrict(lambda air: air.holidayManager.setHolidayPhase(meter, phase))
        yield until(lambda: interior.sillyFSM.getCurrentState().getName() == 'Phase%d' % phase, 30, 'Silly Meter phase %d' % phase)
        chatter = onDistrict(lambda air: air.holidayManager.SillyChatterPhases[phase])
        yield until(lambda: chatter in base.cr.newsManager.getHolidayIdList(), 30, 'the phase %d SpeedChat' % phase)
        yield sleep(2)
    log('the Silly Meter went through all 16 phases')
    from toontown.toon import NPCToons
    emcee = [scientist for scientist in scientists if scientist.getName() == NPCToons.getNPCName(2020)]
    yield until(lambda: any(scientist.nametag.getChat() for scientist in emcee), 60, 'the emcee scientist to talk')
    log('the emcee says:', emcee[0].nametag.getChat())
    onDistrict(lambda air: air.holidayManager.endHoliday(meter))
    yield until(lambda: not hasattr(base.cr, 'SillyMeterMgr'), 30, 'the Silly Meter to go')
    for holidayId, attr in ((ToontownGlobals.HYDRANT_ZERO_HOLIDAY, 'hydrantZeroMgr'),
                            (ToontownGlobals.MAILBOX_ZERO_HOLIDAY, 'mailboxZeroMgr'),
                            (ToontownGlobals.TRASHCAN_ZERO_HOLIDAY, 'trashcanZeroMgr')):
        onDistrict(lambda air: air.holidayManager.startHoliday(holidayId))
        yield until(lambda: hasattr(base.cr, attr), 30, attr)
        onDistrict(lambda air: air.holidayManager.setHolidayPhase(holidayId, 6))
        yield until(lambda: getattr(base.cr, attr).getCurPhase() == 6, 30, '%s phase 6' % attr)
        onDistrict(lambda air: air.holidayManager.endHoliday(holidayId))
        yield until(lambda: not hasattr(base.cr, attr), 30, '%s to go' % attr)
        log(attr, 'came and went')


def scenarioBlackCat():
    # On Black Cat Day a cat who says "Toontastic!" in Toon Hall turns black.
    from toontown.toon.ToonDNA import ToonDNA
    from otp.speedchat.SpeedChatGlobals import SCStaticTextMsgEvent

    def makeCat(air, avId):
        av = air.doId2do[avId]
        dna = ToonDNA()
        dna.makeFromNetString(av.getDNAString())
        dna.head = 'c' + dna.head[1:]
        av.b_setDNAString(dna.makeNetString())
        air.holidayManager.startHoliday(ToontownGlobals.BLACK_CAT_DAY)

    onDistrict(makeCat, localAvatar.doId)
    yield until(lambda: localAvatar.style.getAnimal() == 'cat', 30, 'the toon to be a cat')
    npc = yield from goToNPC(2001)
    yield until(lambda: findObject('DistributedBlackCatMgr'), 30, 'the black cat manager')
    yield sleep(1)
    messenger.send(SCStaticTextMsgEvent, [5700])
    black = localAvatar.style.getBlackColor()
    yield until(lambda: localAvatar.style.headColor == localAvatar.style.armColor == localAvatar.style.legColor == 0x1a,
                30, 'the toon to turn black')
    log('the cat turned black')
    onDistrict(lambda air: air.holidayManager.endHoliday(ToontownGlobals.BLACK_CAT_DAY))
    yield until(lambda: not findObject('DistributedBlackCatMgr'), 30, 'the black cat manager to go')


def scenarioTrolleyTracks():
    # During Trolley Tracks the trolley plays the board game between
    # minigames: the board game, a minigame, Play Again, the next one.
    onDistrict(lambda air: air.holidayManager.startHoliday(ToontownGlobals.TROLLEY_HOLIDAY))
    yield from teleport(ToontownGlobals.ToontownCentral)
    for attempt in range(10):
        if placeState() == 'walk':
            trolley = findObject('DistributedTrolley')
            if trolley is not None:
                localAvatar.setPos(render, trolley.trolleyCar.getPos(render))
            messenger.send('entertrolley_sphere', [None])
        yield sleep(5)
        if placeState() != 'walk':
            break
    seen = []
    while len(seen) < 3:
        yield until(lambda: minigameState() == 'frameworkRules' or hoodState() == 'purchase', 180, 'the next game')
        if hoodState() == 'purchase':
            yield until(lambda: base.cr.playGame.hood.purchase.fsm.getCurrentState().getName() == 'purchase', 60, 'the gag shop buttons')
            yield sleep(1)
            log('playing again')
            messenger.send('purchasePlayAgain')
            continue
        name = base.curMinigame.__class__.__name__
        seen.append(name)
        log('trolley tracks game %d: %s, metagame round %d' % (len(seen), name, base.curMinigame.metagameRound))
        if base.curMinigame.metagameRound < 0:
            raise StepFailed('the trolley did not start Trolley Tracks')
        yield sleep(1)
        messenger.send(base.curMinigame.rulesDoneEvent)
        yield until(lambda: minigameState() not in ('frameworkRules', 'frameworkWaitServerStart', 'frameworkGame', 'frameworkWaitServerFinish'),
                    480, 'the %s game to end' % name)
    if seen[0] != 'DistributedTravelGame' or seen[2] != 'DistributedTravelGame':
        raise StepFailed('the board game did not come every other game: %s' % seen)
    log('the board game comes every other game')
    yield until(lambda: hoodState() == 'purchase' or minigameState() == 'frameworkRules', 180, 'what comes after the board game')
    onDistrict(lambda air: air.holidayManager.endHoliday(ToontownGlobals.TROLLEY_HOLIDAY))


def scenarioInvasion(battles=2):
    # A Flunky invasion on Silly Street: the cogs on the street fly away and
    # every new one is a Flunky. Invasion cogs come to every street, so the
    # toon fights a few on this one and then calls the invasion off.
    street = ToontownGlobals.SillyStreet
    yield from teleport(street - street % 1000, firstVisgroup(street))
    magicWord('~invasion start f 1000')
    yield until(lambda: base.cr.newsManager.getInvading(), 60, 'the invasion to start')
    multiplier = localAvatar.inventory.getInvasionCreditMultiplier()
    log('invasion started; gag experience multiplier %s' % multiplier)
    if multiplier != 2.0:
        raise StepFailed('gag experience is not doubled during the invasion')
    flunkies = lambda: [suit for suit in suitsNearby() if suit.dna.name == 'f']
    others = lambda: [suit for suit in suitsNearby() if suit.dna.name != 'f']
    yield until(lambda: not others(), 300, 'the cogs that were on the street to fly away')
    for fought in range(battles):
        onDistrict(restock, localAvatar.doId)
        yield until(flunkies, 300, 'an invading Flunky')
        suit = min(flunkies(), key=lambda s: (s.getPos(render) - localAvatar.getPos(render)).length())
        while placeState() == 'walk' and not suit.isEmpty():
            localAvatar.setPos(render, suit.getPos(render))
            yield sleep(0.1)
        if placeState() != 'walk':
            yield from fightBattle()
            yield until(walking, 120, 'walking after the battle')
        log('fought invading Flunky %d' % (fought + 1))
    magicWord('~invasion stop')
    yield until(lambda: not base.cr.newsManager.getInvading(), 60, 'the invasion to end')
    log('the invasion ended')


def scenarioGarden():
    # Starts a garden the way the Gardening Kit from the catalog does, then
    # grows, picks and sells a flower, grows a gag tree to organic gags and
    # picks its gags, and plants a statue, a day at a time.
    from toontown.estate import GardenGlobals
    me = localAvatar.doId
    yield until(walking, 60, 'walking before going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')

    def startGarden(air, avId):
        av = air.doId2do[avId]
        av.b_setMoney(av.getMaxMoney())
        av.estate.placeStarterGarden(av)
        return av.estate.toons.index(avId)

    def nextDay(air, avId):
        air.doId2do[avId].estate.doEpochNow()

    ownerIndex = onDistrict(startGarden, me)
    numPlots = len(GardenGlobals.estatePlots[ownerIndex])
    myPlots = lambda: [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedGardenPlot' and do.getOwnerId() == me]
    yield until(lambda: len(myPlots()) == numPlots, 60, 'the garden plots')
    boxes = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedGardenBox']
    log('garden started: %d plots and %d planters' % (numPlots, len(boxes)))

    def plotFor(plantType):
        return next(plot for plot in myPlots() if GardenGlobals.whatCanBePlanted(plot.ownerIndex, plot.plot) == plantType)

    def plantAt(hardPoint, className):
        return findObject(className, lambda do: do.plot == hardPoint and do.getOwnerId() == me)

    def dismissDialogs():
        # Clicks OK on the "you planted..." dialogs, which hold the toon
        # still until they are closed.
        from toontown.estate.DistributedLawnDecor import DistributedLawnDecor
        for do in list(base.cr.doId2do.values()):
            if isinstance(do, DistributedLawnDecor) and getattr(do, 'resultDialog', None):
                do.resultsCallback(1)

    def water(plant):
        level = plant.waterLevel
        plant.sendUpdate('waterPlant', [])
        yield until(lambda: plant.waterLevel > level, 30, 'the water to soak in')

    # A flower: one bean is all a new toon's shovel can plant.
    species, variety = next((s, v) for s in GardenGlobals.getFlowerSpecies()
                            for v in range(len(GardenGlobals.getFlowerVarieties(s)))
                            if GardenGlobals.getNumBeansRequired(s, v) == 1)
    plot = plotFor(GardenGlobals.FLOWER_TYPE)
    hardPoint = plot.plot
    money = localAvatar.getMoney()
    plot.sendUpdate('plantFlower', [species, variety])
    yield until(lambda: plantAt(hardPoint, 'DistributedFlower'), 60, 'the flower to be planted')
    flower = plantAt(hardPoint, 'DistributedFlower')
    log('planted %s for %d bean' % (GardenGlobals.getFlowerVarietyName(species, variety), money - localAvatar.getMoney()))
    yield until(lambda: not flower.movie or flower.movie.isStopped(), 30, 'the planting movie')
    yield from water(flower)
    onDistrict(nextDay, me)
    yield until(lambda: flower.growthLevel >= 1, 30, 'the flower to bloom')
    log('a day later the flower bloomed (water %d)' % flower.waterLevel)
    flower.sendUpdate('removeItem', [])
    yield until(lambda: len(localAvatar.flowerBasket) == 1, 60, 'the flower in the basket')
    yield until(lambda: plantAt(hardPoint, 'DistributedGardenPlot'), 60, 'the empty plot')
    estate = findObject('DistributedEstate')
    money = localAvatar.getMoney()
    estate.sendUpdate('completeFlowerSale', [1])
    yield until(lambda: len(localAvatar.flowerCollection) == 1, 30, 'the flower in the collection')
    log('sold the flower for %d beans; it is in the flower collection' % (localAvatar.getMoney() - money))

    # A gag tree, planted from a gag. It bears gags once full grown, and a
    # full grown tree makes its track organic.
    track, level = ToontownBattleGlobals.THROW_TRACK, 0
    plot = plotFor(GardenGlobals.GAG_TREE_TYPE)
    hardPoint = plot.plot
    plot.sendUpdate('plantGagTree', [track, level])
    yield until(lambda: plantAt(hardPoint, 'DistributedGagTree'), 60, 'the gag tree to be planted')
    tree = plantAt(hardPoint, 'DistributedGagTree')
    thresholds = GardenGlobals.PlantAttributes[tree.typeIndex]['growthThresholds']
    while tree.growthLevel < thresholds[2]:
        yield until(lambda: not tree.movie or tree.movie.isStopped(), 30, 'the tree movie')
        yield from water(tree)
        growth = tree.growthLevel
        onDistrict(nextDay, me)
        yield until(lambda: tree.growthLevel > growth, 30, 'the tree to grow')
    yield until(lambda: localAvatar.getTrackBonusLevel(track) >= level, 30, 'organic throw gags')
    log('the tree grew in %d days; throw gags are organic up to level %d' % (tree.growthLevel, localAvatar.getTrackBonusLevel(track)))

    def emptyPies(air, avId):
        av = air.doId2do[avId]
        av.inventory.inventory[track][level] = 0
        av.inventory.calcTotalProps()
        av.b_setInventory(av.inventory.makeNetString())

    onDistrict(emptyPies, me)
    yield until(lambda: localAvatar.inventory.numItem(track, level) == 0, 30, 'room for the gags')
    tree.sendUpdate('requestHarvest', [])
    yield until(lambda: localAvatar.inventory.numItem(track, level) > 0, 60, 'the picked gags')
    log('picked %d gags off the tree' % localAvatar.inventory.numItem(track, level))

    # A statue, from a catalog garden item.
    def giveStatue(air, avId):
        av = air.doId2do[avId]
        av.addGardenItem(100, 1)
        av.addGardenItem(GardenGlobals.GardenAcceleratorSpecial, 1)
        av.b_setShovelSkill(GardenGlobals.ShovelAttributes[0]['skillPts'] // 2)

    onDistrict(giveStatue, me)
    yield until(lambda: len(localAvatar.getGardenSpecials()) == 2, 30, 'the garden items')
    plot = plotFor(GardenGlobals.STATUARY_TYPE)
    hardPoint = plot.plot
    plot.sendUpdate('plantStatuary', [200])
    yield until(lambda: plantAt(hardPoint, 'DistributedStatuary'), 60, 'the statue')
    yield until(lambda: getattr(plantAt(hardPoint, 'DistributedStatuary'), 'resultDialog', None), 30, 'the statue planting dialog')
    dismissDialogs()
    log('planted a %s' % GardenGlobals.PlantAttributes[200]['name'])

    # The garden accelerator from the Shtiker Book makes a day pass.
    growth = tree.growthLevel
    responses = []
    localAvatar.accept('use-special-response', responses.append)
    localAvatar.sendUpdate('reqUseSpecial', [GardenGlobals.GardenAcceleratorSpecial])
    yield until(lambda: responses, 30, 'the garden accelerator')
    localAvatar.ignore('use-special-response')
    if responses[0] != 'success':
        raise StepFailed('the garden accelerator answered %s' % responses[0])
    yield until(lambda: tree.growthLevel > growth or tree.waterLevel < 0, 30, 'the accelerated day')
    saved = onDistrict(lambda air, avId: air.doId2do[avId].estate.items[ownerIndex], me)
    log('accelerator used; the estate keeps %d plants: %s' % (len(saved), saved))
    dismissDialogs()
    yield until(walking, 30, 'walking after gardening')
    yield from teleport(ToontownGlobals.ToontownCentral)


def scenarioParty():
    # Plans a party that starts now, goes to it, and has it end; then plans
    # one more and cancels it for a refund.
    from toontown.parties import PartyGlobals
    from toontown.parties.PartyGlobals import ActivityIds, DecorationIds, PartyStatus
    from datetime import timedelta
    yield until(walking, 60, 'walking before planning')
    onDistrict(lambda air, avId: air.doId2do[avId].b_setMoney(air.doId2do[avId].getMaxMoney()), localAvatar.doId)
    yield until(lambda: localAvatar.getMoney() == localAvatar.getMaxMoney(), 30, 'beans for the party')
    activities = [[ActivityIds.PartyClock, 9, 13, 0], [ActivityIds.PartyJukebox, 3, 3, 0],
                  [ActivityIds.PartyTrampoline, 14, 3, 0], [ActivityIds.PartyCatch, 4, 10, 0],
                  [ActivityIds.PartyCannon, 14, 10, 0], [ActivityIds.PartyDance, 9, 7, 0]]
    decorations = [[DecorationIds.Cake, 1, 1, 0], [DecorationIds.Bow, 16, 13, 0]]
    cost = sum(PartyGlobals.ActivityInformationDict[a[0]]['cost'] for a in activities) + \
           sum(PartyGlobals.DecorationInformationDict[d[0]]['cost'] for d in decorations)

    def plan(start):
        responses = []
        base.cr.partyManager.accept('addPartyResponseReceived', lambda hostId, code: responses.append(code))
        end = start + timedelta(hours=1)
        fmt = '%Y-%m-%d %H:%M:%S'
        base.cr.partyManager.sendAddParty(localAvatar.doId, start.strftime(fmt), end.strftime(fmt), 0, 0,
                                          activities, decorations, [])
        yield until(lambda: responses, 30, 'the party planner to answer')
        base.cr.partyManager.ignore('addPartyResponseReceived')
        if responses[0] != PartyGlobals.AddPartyErrorCode.AllOk:
            raise StepFailed('planning the party failed with %s' % responses[0])

    def hosted():
        return localAvatar.hostedParties[0] if localAvatar.hostedParties else None

    # The planner opens in party grounds of its own.
    zones = []
    localAvatar.aboutToPlanParty = True
    base.cr.partyManager.requestPartyZone(localAvatar.doId, 0, lambda hostId, partyId, zoneId: zones.append(zoneId))
    yield until(lambda: zones, 30, 'a party grounds to plan in')
    localAvatar.aboutToPlanParty = False
    if not zones[0]:
        raise StepFailed('no party grounds to plan in')
    messenger.send('deallocateZoneIdFromPlannedParty', [zones[0]])

    money = localAvatar.getMoney()
    now = base.cr.toontownTimeManager.getCurServerDateTime().replace(tzinfo=None, second=0, microsecond=0)
    yield from plan(now)
    yield until(lambda: hosted() and hosted().status == PartyStatus.CanStart, 90, 'the party to be able to start')
    log('planned a party for %d beans (it costs %d); it can start' % (money - localAvatar.getMoney(), cost))

    place().startPartyNow(True, localAvatar.doId)
    yield until(lambda: placeName() == 'Party' and walking() and hasattr(base, 'distributedParty'), 180, 'walking around the party')
    party = base.distributedParty
    acts = [do.__class__.__name__ for do in base.cr.doId2do.values() if do.__class__.__name__.startswith('DistributedParty') and do.__class__.__name__ != 'DistributedPartyManager']
    log('at the party in zone %d with %s' % (localAvatar.zoneId, sorted(acts)))
    if len(acts) < len(activities) - 1:
        raise StepFailed('the party is missing activities')
    yield sleep(5)
    magicWord('~endParty')
    yield until(lambda: placeName() != 'Party' and walking(), 120, 'being sent home when the party ends')
    yield until(lambda: hosted() and hosted().status == PartyStatus.Finished, 30, 'the party to be over')
    log('the party ended and the toon went back to %s' % placeName())

    # A party for tomorrow, cancelled.
    money = localAvatar.getMoney()
    yield from plan(now + timedelta(days=1))
    yield until(lambda: hosted() and hosted().status == PartyStatus.Pending, 30, 'the planned party')
    refunds = []
    base.cr.partyManager.accept(base.cr.partyManager.PartyStatusChangedEvent, lambda *args: refunds.append(args))
    base.cr.partyManager.sendChangePartyStatusRequest(hosted().partyId, PartyStatus.Cancelled)
    yield until(lambda: refunds, 30, 'the cancellation')
    base.cr.partyManager.ignore(base.cr.partyManager.PartyStatusChangedEvent)
    partyId, status, errorCode, refund = refunds[0]
    if status != PartyStatus.Cancelled or errorCode != PartyGlobals.ChangePartyFieldErrorCode.AllOk:
        raise StepFailed('cancelling answered status %s error %s' % (status, errorCode))
    yield sleep(1)
    log('cancelled tomorrow\'s party: %d beans back, %d lost' % (refund, money - localAvatar.getMoney()))


def scenarioCatalog():
    # Calls Clarabelle on the house phone, buys from the catalog, and takes
    # the delivery out of the mailbox.
    from toontown.catalog import CatalogItem
    me = localAvatar.doId
    yield until(lambda: len(localAvatar.weeklyCatalog) or len(localAvatar.monthlyCatalog), 60, 'the first catalog')
    onDistrict(lambda air, avId: air.doId2do[avId].b_setMoney(air.doId2do[avId].getMaxMoney()), me)
    yield until(walking, 60, 'walking before going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')
    yield until(lambda: findObject('DistributedHouse', lambda do: do.ownerId == me), 60, 'the toon\'s own house')
    house = findObject('DistributedHouse', lambda do: do.ownerId == me)
    yield until(lambda: findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD), 60, 'the front door')
    door = findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD)
    yield sleep(2)
    messenger.send(door.getEnterTriggerEvent(), [None])
    yield until(lambda: placeName() == 'House' and walking(), 120, 'walking inside the house')
    yield until(lambda: findObject('DistributedPhone'), 60, 'the phone')
    phone = findObject('DistributedPhone')
    phone.sendUpdate('avatarEnter', [])
    yield sleep(2)

    # One item of each kind the catalog has this week that the toon can buy.
    kinds = {}
    money = localAvatar.getMoney() + localAvatar.getBankMoney()
    for item in list(localAvatar.monthlyCatalog) + list(localAvatar.weeklyCatalog):
        kind = item.__class__.__name__
        if kind in kinds or item.loyaltyRequirement() or item.reachedPurchaseLimit(localAvatar):
            continue
        if kind == 'CatalogAccessoryItem' and not localAvatar.getMaxAccessories():
            # Accessories need a trunk first (the accessories scenario).
            continue
        if item.getPrice(0) <= money:
            kinds[kind] = item
            money -= item.getPrice(0)
    log('buying %s' % sorted(kinds))
    results = {}
    for kind, item in sorted(kinds.items()):
        phone.requestPurchase(item, lambda retcode, item, kind=kind: results.__setitem__(kind, retcode))
        yield until(lambda: kind in results, 30, 'Clarabelle to take the order for a %s' % kind)
    phone.sendUpdate('avatarExit', [])
    failed = {kind: code for kind, code in results.items() if code < 0}
    if failed:
        raise StepFailed('purchases failed: %s' % failed)
    log('bought %d items; %d on order' % (len(results), len(localAvatar.onOrder)))

    if len(localAvatar.onOrder):
        # Skip the delivery wait.
        def deliverNow(air, avId):
            av = air.doId2do[avId]
            for item in av.onOrder:
                item.deliveryDate = int(time.time() / 60)
            # A plain list: the item list would re-read its cached blob.
            from toontown.catalog.CatalogItemList import CatalogItemList
            av.b_setDeliverySchedule(CatalogItemList(list(av.onOrder), store=av.onOrder.store))

        onDistrict(deliverNow, me)

        yield until(lambda: len(localAvatar.mailboxContents) and not len(localAvatar.onOrder), 120, 'the delivery')
    log('%d items in the mailbox' % len(localAvatar.mailboxContents))
    if len(localAvatar.mailboxContents):
        # Out the front door to the mailbox.
        yield until(lambda: findObject('DistributedHouseDoor', lambda do: do.doorType == DoorTypes.INT_STANDARD), 60, 'the inside of the front door')
        door = findObject('DistributedHouseDoor', lambda do: do.doorType == DoorTypes.INT_STANDARD)
        messenger.send(door.getEnterTriggerEvent(), [None])
        yield until(lambda: placeName() == 'Estate' and walking(), 120, 'walking out of the house')
        yield until(lambda: findObject('DistributedMailbox', lambda do: do.houseId == house.doId), 60, 'the mailbox')
        mailbox = findObject('DistributedMailbox', lambda do: do.houseId == house.doId)
        mailbox.sendUpdate('avatarEnter', [])
        yield sleep(2)
        accepted = []
        while len(localAvatar.mailboxContents):
            count = len(localAvatar.mailboxContents)
            item = localAvatar.mailboxContents[0]
            mailbox.acceptItem(item, 0, lambda retcode, item, index: accepted.append((item.__class__.__name__, retcode)))
            yield until(lambda: len(accepted) and len(localAvatar.mailboxContents) < count, 30, 'taking an item from the mailbox')
        mailbox.sendUpdate('avatarExit', [])
        failed = [entry for entry in accepted if entry[1] < 0]
        if failed:
            raise StepFailed('mailbox items failed: %s' % failed)
        log('took %s out of the mailbox' % accepted)
    yield sleep(3)
    yield from teleport(ToontownGlobals.ToontownCentral)


def scenarioAccessories():
    # The accessory trunk (run with AUTOPLAY_PRC="want-accessories 1"): the
    # trunk and one hat, pair of glasses, backpack and pair of shoes arrive,
    # the toon moves the trunk out of the attic with the furniture arranger
    # and puts on each accessory from it.
    me = localAvatar.doId

    def deliver(air, avId):
        from toontown.catalog import CatalogFurnitureItem
        from toontown.catalog.CatalogAccessoryItem import CatalogAccessoryItem
        from toontown.catalog.CatalogAccessoryItemGlobals import AccessoryTypes, ATArticle
        av = air.doId2do[avId]
        trunk = CatalogFurnitureItem.CatalogFurnitureItem(CatalogFurnitureItem.MaxTrunkIds[av.dna.gender == 'f'])
        results = [('trunk', trunk.recordPurchase(av, None))]
        kinds = {}
        for accessoryType in sorted(AccessoryTypes):
            item = CatalogAccessoryItem(accessoryType)
            kind = AccessoryTypes[accessoryType][ATArticle] % 4
            if kind not in kinds and not item.notOfferedTo(av):
                kinds[kind] = item
                results.append((accessoryType, item.recordPurchase(av, None)))
        return results

    yield from goInsideHouse()
    results = onDistrict(deliver, me)
    log('delivered: %s' % (results,))
    if any(code < 0 for name, code in results) or len(results) != 5:
        raise StepFailed('the trunk and accessories were not delivered: %s' % (results,))
    yield until(lambda: localAvatar.getMaxAccessories() > 0 and all(
        len(getattr(localAvatar, 'get%sList' % kind)()) == 3 for kind in ('Hat', 'Glasses', 'Backpack', 'Shoes')), 30, 'the accessories in the trunk')

    # Arrange the furniture: the trunk comes out of the attic.
    manager = base.cr.furnitureManager
    manager.d_suggestDirector(me)
    yield until(lambda: manager.director == me, 30, 'furniture arranging')
    from toontown.catalog.CatalogFurnitureItem import FLTrunk
    yield until(lambda: [item for item in manager.atticItems if item.getFlags() & FLTrunk], 30, 'the trunk in the attic')
    index = [i for i, item in enumerate(manager.atticItems) if item.getFlags() & FLTrunk][0]
    placed = []
    pos = localAvatar.getPos(render) + Vec3(0, 6, 0)
    manager.moveItemFromAttic(index, (pos[0], pos[1], pos[2], 180, 0, 0), lambda retcode, dfitem, index: placed.append((retcode, dfitem)))
    yield until(lambda: placed, 30, 'the trunk to come out of the attic')
    if placed[0][0] < 0:
        raise StepFailed('could not move the trunk out of the attic: %s' % placed[0][0])
    # And another piece of furniture goes up to the attic and back down.
    other = [do for do in manager.dfitems if do.__class__.__name__ == 'DistributedFurnitureItem']
    if other:
        name = other[0].item.getName()
        pos = other[0].getPos(render)
        posHpr = (pos[0], pos[1], pos[2], other[0].getH(render), 0, 0)
        moved = []
        manager.moveItemToAttic(other[0], lambda retcode, item: moved.append(retcode))
        yield until(lambda: moved, 30, 'the %s to go up to the attic' % name)
        if moved[0] < 0:
            raise StepFailed('could not move the %s to the attic: %s' % (name, moved[0]))
        yield until(lambda: [i for i, item in enumerate(manager.atticItems) if item.getName() == name], 30, 'the %s in the attic' % name)
        index = [i for i, item in enumerate(manager.atticItems) if item.getName() == name][-1]
        back = []
        manager.moveItemFromAttic(index, posHpr, lambda retcode, dfitem, index: back.append(retcode))
        yield until(lambda: back, 30, 'the %s to come back down' % name)
        if back[0] < 0:
            raise StepFailed('could not bring the %s back down: %s' % (name, back[0]))
        log('moved the %s up to the attic and back down' % name)
    manager.releaseDirector()
    yield until(lambda: findObject('DistributedTrunk'), 30, 'the trunk in the room')
    trunk = findObject('DistributedTrunk')

    # A bought accessory goes straight on, and what was worn (nothing, for a
    # new toon) goes in the trunk.
    kinds = ('Hat', 'Glasses', 'Backpack', 'Shoes')
    bought = {kind: tuple(getattr(localAvatar, 'get' + kind)()) for kind in kinds}
    log('wearing %s' % bought)
    if (0, 0, 0) in bought.values():
        raise StepFailed('a bought accessory was not put on: %s' % bought)
    if not localAvatar.hatNodes or not localAvatar.glassesNodes or not localAvatar.backpackNodes or not localAvatar.shoes:
        raise StepFailed('an accessory is not drawn')

    def useTrunk(kind):
        trunk.sendUpdate('enterAvatar', [])
        yield until(lambda: trunk.closetGUI, 30, 'the trunk to open')
        yield sleep(0.5)
        getattr(trunk.closetGUI, 'swap' + kind)(1)
        trunk.closetGUI.button['command']()
        yield until(lambda: not trunk.closetGUI and walking(), 30, 'the trunk to close')
        yield sleep(1)

    # Each one comes off into the trunk...
    for kind in kinds:
        yield from useTrunk(kind)
        if tuple(getattr(localAvatar, 'get' + kind)()) != (0, 0, 0) or getattr(localAvatar, 'get%sList' % kind)() != list(bought[kind]):
            raise StepFailed('the %s did not come off: %s, trunk %s' % (
                kind, getattr(localAvatar, 'get' + kind)(), getattr(localAvatar, 'get%sList' % kind)()))
    if localAvatar.hatNodes or localAvatar.backpackNodes:
        raise StepFailed('a removed accessory is still drawn')
    log('took everything off')
    # ...and the hat goes back on.
    yield from useTrunk('Hat')
    if tuple(localAvatar.getHat()) != bought['Hat'] or localAvatar.getHatList() != [0, 0, 0] or not localAvatar.hatNodes:
        raise StepFailed('the hat did not go back on: %s, trunk %s' % (localAvatar.getHat(), localAvatar.getHatList()))
    stored = onDistrict(lambda air, avId: (air.doId2do[avId].getHat(), air.doId2do[avId].getHatList()), me)
    log('put the hat back on; the server has hat %s with %s in the trunk' % stored)
    yield from teleport(ToontownGlobals.ToontownCentral)


def goInsideHouse():
    me = localAvatar.doId
    yield until(walking, 60, 'walking before going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')
    yield until(lambda: findObject('DistributedHouse', lambda do: do.ownerId == me), 60, 'the toon\'s own house')
    house = findObject('DistributedHouse', lambda do: do.ownerId == me)
    yield until(lambda: findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD), 60, 'the front door')
    door = findObject('DistributedHouseDoor', lambda do: do.houseId == house.doId and do.doorType == DoorTypes.EXT_STANDARD)
    yield sleep(2)
    messenger.send(door.getEnterTriggerEvent(), [None])
    yield until(lambda: placeName() == 'House' and walking(), 120, 'walking inside the house')


def scenarioGifts():
    # Buys a catalog gift for a friend. The toon is its own friend here, so
    # the gift comes back to its own mailbox.
    me = localAvatar.doId
    yield until(lambda: len(localAvatar.weeklyCatalog), 60, 'the first catalog')

    def setUp(air, avId):
        av = air.doId2do[avId]
        # Enough jellybeans for any gift in the catalog.
        av.b_setMaxMoney(250)
        av.b_setMoney(250)
        av.b_setMaxBankMoney(12000)
        av.b_setBankMoney(12000)
        av.friendsList = [(avId, 0)]

    onDistrict(setUp, me)
    acked = []
    base.acceptOnce('DeliveryManagerAck', lambda: acked.append(1))
    base.cr.deliveryManager.sendAck()
    yield until(lambda: acked, 30, 'the delivery manager to answer')
    yield from goInsideHouse()
    yield until(lambda: findObject('DistributedPhone'), 60, 'the phone')
    phone = findObject('DistributedPhone')
    phone.sendUpdate('avatarEnter', [])
    yield sleep(2)
    gifts = [item for item in list(localAvatar.weeklyCatalog) + list(localAvatar.monthlyCatalog)
             if item.isGift() and not item.loyaltyRequirement() and not item.reachedPurchaseLimit(localAvatar)
             and not item.notOfferedTo(localAvatar) and item.getPrice(0) <= localAvatar.getMoney() + localAvatar.getBankMoney()]
    if not gifts:
        raise StepFailed('nothing in the catalog can be a gift')
    item = gifts[0]
    results = []
    phone.requestGiftPurchase(item, me, lambda retcode, item: results.append(retcode))
    yield until(lambda: results, 30, 'Clarabelle to take the gift order')
    phone.sendUpdate('avatarExit', [])
    if results[0] != ToontownGlobals.P_ItemOnOrder:
        raise StepFailed('the gift order for %s gave %s' % (item.getName(), results[0]))
    log('ordered a %s as a gift' % item.getName())

    def deliverNow(air, avId):
        av = air.doId2do[avId]
        for gift in av.onGiftOrder:
            gift.deliveryDate = int(time.time() / 60)
        from toontown.catalog.CatalogItemList import CatalogItemList
        av.b_setGiftSchedule(CatalogItemList(list(av.onGiftOrder), store=av.onGiftOrder.store))

    count = len(localAvatar.mailboxContents)
    onDistrict(deliverNow, me)
    yield until(lambda: len(localAvatar.mailboxContents) > count, 120, 'the gift delivery')
    gift = localAvatar.mailboxContents[-1]
    log('the gift arrived: %s from %s' % (gift.getName(), gift.giftTag))
    onDistrict(lambda air, avId: setattr(air.doId2do[avId], 'friendsList', []), me)


def scenarioCodes():
    # Types codes on the Options page, then takes the presents out of the
    # award mailbox.
    from toontown.coderedemption.TTCodeRedemptionConsts import RedeemErrors
    me = localAvatar.doId
    yield until(lambda: hasattr(base, 'codeRedemptionMgr'), 60, 'the code redemption manager')
    results = []

    def redeem(code):
        base.codeRedemptionMgr.redeemCode(code, lambda result, awardResult: results.append((code, result, awardResult)))

    expected = [('toontown', RedeemErrors.Success), ('TOONTOWN', RedeemErrors.CodeAlreadyRedeemed),
                ('notacode', RedeemErrors.CodeDoesntExist), ('toon council', RedeemErrors.CodeDoesntExist),
                ('ToonCouncil', RedeemErrors.Success)]
    for code, result in expected:
        redeem(code)
        yield until(lambda: len(results) and results[-1][0] == code, 30, 'the answer for code %s' % code)
        if results[-1][1] != result:
            raise StepFailed('code %s gave %s, expected %s' % (code, results[-1][1:], result))
    log('codes: %s' % results)
    yield until(lambda: len(localAvatar.awardMailboxContents) == 2, 30, 'the awards in the mailbox')
    yield until(walking, 60, 'walking before going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')
    house = None
    yield until(lambda: findObject('DistributedHouse', lambda do: do.ownerId == me), 60, 'the toon\'s own house')
    house = findObject('DistributedHouse', lambda do: do.ownerId == me)
    yield until(lambda: findObject('DistributedMailbox', lambda do: do.houseId == house.doId), 60, 'the mailbox')
    mailbox = findObject('DistributedMailbox', lambda do: do.houseId == house.doId)
    mailbox.sendUpdate('avatarEnter', [])
    yield sleep(2)
    money = localAvatar.getMoney() + localAvatar.getBankMoney()
    accepted = []
    while len(localAvatar.awardMailboxContents):
        count = len(localAvatar.awardMailboxContents)
        item = localAvatar.awardMailboxContents[0]
        mailbox.acceptItem(item, 0, lambda retcode, item, index: accepted.append((item.__class__.__name__, retcode)))
        yield until(lambda: len(accepted) and len(localAvatar.awardMailboxContents) < count, 30, 'taking an award from the mailbox')
    mailbox.sendUpdate('avatarExit', [])
    failed = [entry for entry in accepted if entry[1] < 0]
    if failed:
        raise StepFailed('awards failed: %s' % failed)
    log('took %s out of the mailbox; jellybeans %d -> %d' % (
        accepted, money, localAvatar.getMoney() + localAvatar.getBankMoney()))
    yield sleep(2)
    yield from teleport(ToontownGlobals.ToontownCentral)


def playBoardGames(table, games=(1, 2, 3), seat=1):
    # Sits at a game table and plays each game through against the
    # computer, moving with the same rules the computer players use.
    from toontown.safezone import BoardGameRules
    rules = {1: BoardGameRules.ChineseCheckersRules(),
             2: BoardGameRules.CheckersRules(),
             3: BoardGameRules.FindFourRules()}
    names = {1: 'Chinese Checkers', 2: 'Checkers', 3: 'Find Four'}
    winners = []
    original = table.announceWinner

    def recordingAnnounceWinner(winString, avId):
        winners.append((winString, avId))
        original(winString, avId)
    table.announceWinner = recordingAnnounceWinner
    for gameNum in games:
        yield until(walking, 60, 'walking by the table')
        yield until(lambda: not table.isPlaying, 60, 'a free table')
        log('sitting down for', names[gameNum])
        table.handleEnterPicnicTableSphere(seat, None)
        table.joinButtonPushed()
        yield until(lambda: table.gameMenu, 30, 'the game menu')
        table.pickFunction(gameNum)
        yield until(lambda: table.game and table.game.fsm.getCurrentState().getName() == 'waitingToBegin', 60, 'the %s board' % names[gameNum])
        game = table.game
        game.startButtonPushed()
        yield until(lambda: game.fsm.getCurrentState().getName() == 'playing' and game.playerNum, 60, 'the game to start')
        count = len(winners)
        moves = 0
        rule = rules[gameNum]
        while len(winners) == count:
            if game.isMyTurn and game.fsm and game.fsm.getCurrentState().getName() == 'playing':
                yield sleep(0.5)
                if gameNum == 3:
                    if game.moveSequence.isPlaying():
                        continue
                    col = rule.pickMove(game.board, game.playerNum)
                    game.isMyTurn = False
                    taskMgr.remove('playerTurnTask')
                    game.d_requestMove(col)
                else:
                    move = rule.pickMove(game.board.getStates(), game.playerNum)
                    game.isMyTurn = False
                    game.d_requestMove(move)
                moves += 1
            yield until(lambda: game.isMyTurn or len(winners) > count, 120, 'our turn in %s' % names[gameNum])
        log('%s over after %d of our moves: %s' % (names[gameNum], moves, winners[-1]))
        yield until(lambda: walking() and not table.inGame, 60, 'getting up from the table')
        yield sleep(3)
    table.announceWinner = original
    return winners


def scenarioBoardGames():
    # The game tables in Acorn Acres, and the picnic tables beside them.
    yield from teleport(ToontownGlobals.OutdoorZone)
    yield until(lambda: findObject('DistributedPicnicTable'), 60, 'a game table')
    tables = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedPicnicTable']
    baskets = [do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedPicnicBasket']
    log('%d game tables and %d picnic tables' % (len(tables), len(baskets)))
    if len(tables) != 3 or len(baskets) != 2:
        raise StepFailed('expected 3 game tables and 2 picnic tables')
    winners = yield from playBoardGames(tables[0])
    log('results: %s' % winners)

    basket = baskets[0]
    yield until(walking, 60, 'walking by the picnic table')
    log('sitting at a picnic table')
    basket.seatNumber = 2
    place().detectedPicnicTableSphereCollision(basket)
    yield until(lambda: basket.localToonOnBoard and basket.fullSeat[2], 30, 'a seat at the picnic table')
    yield sleep(4)
    basket.handleExitButton()
    yield until(lambda: walking() and not basket.localToonOnBoard, 60, 'getting up from the picnic table')


def scenarioRentals():
    # Rents the estate cannons and the game table from the catalog.
    from toontown.catalog.CatalogRentalItem import CatalogRentalItem
    me = localAvatar.doId
    yield until(walking, 60, 'walking before going home')
    place().goHomeNow(localAvatar.zoneId)
    yield until(lambda: placeName() == 'Estate' and walking(), 180, 'walking around the estate')

    def rent(air, avId, typeIndex):
        av = air.doId2do[avId]
        return CatalogRentalItem(typeIndex, 60, 1000).recordPurchase(av, 0)

    log('renting the cannons')
    onDistrict(rent, me, ToontownGlobals.RentalCannon)
    yield until(lambda: len([do for do in base.cr.doId2do.values() if do.__class__.__name__ == 'DistributedCannon']) == 6
                and findObject('DistributedTarget'), 60, 'the cannons and the target')
    target = findObject('DistributedTarget')
    yield until(lambda: target.enabled, 30, 'the target game to start')
    cannon = findObject('DistributedCannon')
    log('climbing into cannon', cannon.doId)
    messenger.send(cannon.uniqueName('enterCannonSphere'), [None])
    yield until(lambda: cannon.localToonShooting and cannon.madeGui, 30, 'sitting in the cannon')
    yield sleep(1)
    cannon._DistributedCannon__firePressed()
    yield until(lambda: not cannon.localToonShooting, 120, 'flying and landing')
    yield until(walking, 60, 'walking after landing')
    log('landed at %s' % localAvatar.getPos())

    onDistrict(lambda air, avId: air.doId2do[avId].b_setHp(1), me)
    yield until(lambda: localAvatar.hp == 1, 30, 'a hurt toon')
    for hit in range(3):
        target.handleHitTarget(me)
        yield until(lambda: target.score == hit + 1, 30, 'target level %d' % (hit + 1))
    yield until(lambda: localAvatar.hp == 7, 30, 'the target to toon us up')
    log('three target hits healed the toon to %d' % localAvatar.hp)

    overs = []
    estate = findObject('DistributedEstate')
    original = estate.cannonsOver
    estate.cannonsOver = lambda *args: (overs.append(1), original(*args))
    onDistrict(lambda air, avId: air.estateManager.toon2estate[air.doId2do[avId]].endRental(), me)
    yield until(lambda: overs and not findObject('DistributedCannon') and not findObject('DistributedTarget'), 30, 'the cannon rental to end')
    estate.cannonsOver = original

    log('renting the game table')
    onDistrict(rent, me, ToontownGlobals.RentalGameTable)
    yield until(lambda: findObject('DistributedPicnicTable'), 60, 'the game table')
    table = findObject('DistributedPicnicTable')
    winners = yield from playBoardGames(table, games=(3,))
    log('results: %s' % winners)
    onDistrict(lambda air, avId: air.estateManager.toon2estate[air.doId2do[avId]].endRental(), me)
    yield until(lambda: not findObject('DistributedPicnicTable'), 30, 'the game table rental to end')
    yield sleep(2)
    yield from teleport(ToontownGlobals.ToontownCentral)


def scenarioQuest(steps=12):
    # Takes a ToonTask from Toon HQ and plays it through every step to the
    # reward, the way a new toon would.
    from toontown.quest import Quests
    recordNPCMovies()
    fightable = (Quests.CogQuest, Quests.RecoverItemQuest)

    def pickQuest(choices):
        preferred = [c for c in choices if isinstance(Quests.getQuest(c[0]), fightable + (Quests.VisitQuest,))
                     and not isinstance(Quests.getQuest(c[0]), (Quests.BuildingQuest, Quests.SkelecogQBase))]
        return (preferred or choices)[0][0]

    tier = localAvatar.getRewardHistory()
    npc = yield from goToNPC(Quests.ToonHQ)
    yield from talkTo(npc, pickQuest)
    if not localAvatar.quests:
        raise StepFailed('Toon HQ gave no ToonTask')
    for step in range(steps):
        if not localAvatar.quests:
            break
        questId, fromNpcId, toNpcId, rewardId, progress = localAvatar.quests[0]
        quest = Quests.getQuest(questId)
        log('ToonTask %d (%s), hand in to %s' % (questId, quest.__class__.__name__, toNpcId))
        status = quest.getCompletionStatus(localAvatar, localAvatar.quests[0])
        if status != Quests.COMPLETE and isinstance(quest, fightable):
            yield from defeatCogsFor(questId, quest)
        elif status != Quests.COMPLETE and not isinstance(quest, (Quests.VisitQuest, Quests.TrackChoiceQuest)):
            raise StepFailed('the autoplay test cannot do %s yet' % quest.__class__.__name__)
        npc = yield from goToNPC(toNpcId)
        yield from talkTo(npc, pickQuest)
    if localAvatar.quests:
        raise StepFailed('ToonTask still not done after %d steps: %s' % (steps, localAvatar.quests))
    log('ToonTask finished; reward history went from %s to %s' % (tier, localAvatar.getRewardHistory()))


def scenarioFactory():
    yield from teleport(ToontownGlobals.SellbotHQ, ToontownGlobals.SellbotFactoryExt)
    yield from boardElevator('DistributedFactoryElevatorExt')
    yield from clearFacility('FactoryInterior', 'DistributedFactorySuit', 'DistributedFactory')


SOLO_MINIGAMES = ['cannon', 'maze', 'tug', 'ring', 'vine', 'thief', '2d', 'diving', 'pairing', 'catch',
                  'target', 'photo']


def minigameState():
    game = getattr(base, 'curMinigame', None)
    if game is None or game.frameworkFSM is None:
        return None
    return game.frameworkFSM.getCurrentState().getName()


def scenarioMinigames():
    for name in SOLO_MINIGAMES:
        yield from teleport(ToontownGlobals.ToontownCentral)
        magicWord('~requestMinigame %s' % name)
        yield sleep(1)
        log('boarding the trolley for', name)
        for attempt in range(10):
            if placeState() == 'walk':
                # The trolley only takes toons standing level with it.
                trolley = findObject('DistributedTrolley')
                if trolley is not None:
                    localAvatar.setPos(render, trolley.trolleyCar.getPos(render))
                messenger.send('entertrolley_sphere', [None])
            yield sleep(5)
            if placeState() != 'walk':
                break
        yield until(lambda: minigameState() == 'frameworkRules', 120, 'the %s rules' % name)
        yield sleep(1)
        messenger.send(base.curMinigame.rulesDoneEvent)
        yield until(lambda: minigameState() == 'frameworkGame', 60, 'the %s game to start' % name)
        log('playing', name)
        # Nobody plays: the game has to end on its own, through its timer.
        yield until(lambda: minigameState() not in ('frameworkGame', 'frameworkWaitServerFinish'), 420,
                    'the %s game to end' % name)
        yield until(lambda: hoodState() == 'purchase', 120, 'the gag shop after %s' % name)
        yield until(lambda: base.cr.playGame.hood.purchase.fsm.getCurrentState().getName() == 'purchase', 60,
                    'the gag shop buttons')
        yield sleep(1)
        messenger.send('purchaseBackToToontown')
        yield until(walking, 120, 'walking after %s' % name)


SCENARIOS = [
    ('login', scenarioLogin),
    ('tutorial', scenarioTutorial),
    ('touch', scenarioTouchControls),
    ('maxtoon', scenarioMaxToon),
    ('playgrounds', scenarioPlaygrounds),
    ('streets', scenarioStreets),
    ('battle', scenarioBattle),
    ('building', scenarioBuilding),
    ('cogdo', scenarioCogdo),
    ('cogdolaw', lambda: scenarioCogdo('l')),
    ('minigames', scenarioMinigames),
    ('factory', scenarioFactory),
    ('mint', scenarioMint),
    ('office', scenarioOffice),
    ('countryclub', scenarioCountryClub),
    ('vp', scenarioVP),
    ('cfo', scenarioCFO),
    ('cj', scenarioCJ),
    ('ceo', scenarioCEO),
    ('fishing', scenarioFishing),
    ('estate', scenarioEstate),
    ('racing', scenarioRacing),
    ('golf', scenarioGolf),
    ('pets', scenarioPets),
    ('toonhall', scenarioToonHall),
    ('holidays', scenarioHolidays),
    ('toonfest', scenarioToonfest),
    ('election', scenarioElection),
    ('holidayeffects', scenarioHolidayEffects),
    ('hunts', scenarioScavengerHunts),
    ('bingo', scenarioBingo),
    ('sillymeter', scenarioSillyMeter),
    ('blackcat', scenarioBlackCat),
    ('trolleytracks', scenarioTrolleyTracks),
    ('invasion', scenarioInvasion),
    ('garden', scenarioGarden),
    ('party', scenarioParty),
    ('catalog', scenarioCatalog),
    ('codes', scenarioCodes),
    ('gifts', scenarioGifts),
    ('accessories', scenarioAccessories),
    ('boardgames', scenarioBoardGames),
    ('rentals', scenarioRentals),
    ('quest', scenarioQuest),
]


# --- Runner ---

def run(names):
    selected = [s for s in SCENARIOS if not names or s[0] in names or s[0] == 'login']
    for name, scenario in selected:
        log('=== %s ===' % name)
        start = time.time()
        steps = scenario()
        waiting = None
        while True:
            if waiting is None or waiting.condition():
                try:
                    waiting = next(steps)
                except StopIteration:
                    break
                continue
            if time.time() > waiting.deadline:
                raise StepFailed('%s: timed out waiting for %s (login state %s, hood state %s, place %s in state %s)' % (
                    name, waiting.what, loginState(), hoodState(), place().__class__.__name__, placeState()))
            taskMgr.step()
            if errors:
                raise StepFailed('%s: server exception:\n%s' % (name, errors[0]))
        log('=== %s passed in %.1fs ===' % (name, time.time() - start))


def main():
    try:
        run(sys.argv[1:])
    except StepFailed as e:
        log('FAILED', e)
        return 1
    except Exception:
        log('FAILED with a client exception:\n' + traceback.format_exc())
        return 1
    log('all scenarios passed')
    return 0


if __name__ == '__main__':
    code = main()
    try:
        server.shutdown()
    finally:
        os._exit(code)
