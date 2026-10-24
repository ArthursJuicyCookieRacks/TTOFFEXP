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

from panda3d.core import loadPrcFileData, Point3, Vec3
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
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals
from toontown.hood import ZoneUtil
from toontown.building import DoorTypes
from direct.showbase.DirectObject import DirectObject
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
        mat.ns._NameShop__createAvatar(skipTutorial=True)
    else:
        log('choosing the toon in slot 0')
        chooser.choice = 0
        messenger.send(chooser.doneEvent, [{'mode': 'chose'}])
    yield until(lambda: loginState() == 'playingGame', 180, 'playing the game')
    yield until(walking, 180, 'walking in the playground')
    log('in game as %s (%d) in zone %d' % (localAvatar.getName(), localAvatar.doId, localAvatar.zoneId))


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


def fightBattle(timeout=1800):
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


def fightBoss(interior, bossClass, actions, timeout=2400):
    # Plays a boss battle: cog rounds are fought as usual, and actions maps
    # the boss's other states to what a toon does in them (called every
    # half second with the boss).
    yield until(lambda: placeName() == interior, 180, 'inside the %s' % interior)
    yield until(lambda: findObject(bossClass), 120, 'the %s' % bossClass)
    boss = findObject(bossClass)
    deadline = time.time() + timeout
    lastState = None
    while placeName() == interior:
        if time.time() > deadline:
            raise StepFailed('the %s did not end in %d seconds (boss state %s)' % (bossClass, timeout, boss.state))
        if boss.state != lastState:
            lastState = boss.state
            stateStart = time.time()
            log('boss state', lastState)
        elif time.time() - stateStart > 60:
            stateStart = time.time()
            log('boss still in %s; place state %s, gag panel %s' % (boss.state, placeState(), townBattleState()))
        if placeState() == 'battle':
            yield from fightBattle()
            continue
        # In the epilogue a rescued toon talks; clicking through the speech
        # balloon's pages ends it.
        action = actions.get(boss.state) or {'Epilogue': lambda boss: messenger.send('doneChatPage', [0])}.get(boss.state)
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


def scenarioCJ():
    yield from teleport(ToontownGlobals.LawbotHQ, ToontownGlobals.LawbotLobby)
    yield from boardElevator('DistributedCJElevator')
    yield from fightBoss('LawbotHQBossBattle', 'DistributedLawbotBoss', {
        'BattleThree': cjBattleThree,
        'NearVictory': lambda boss: boss.sendUpdate('finalPieSplat', []),
    })


def scenarioCEO():
    # The banquet runs out its clock unserved, so every diner joins the
    # third round. In the last round, seltzer hits the CEO.
    yield from teleport(ToontownGlobals.BossbotHQ, ToontownGlobals.BossbotLobby)
    yield from boardElevator('DistributedBBElevator')
    yield from fightBoss('BossbotHQBossBattle', 'DistributedBossbotBoss', {
        'BattleFour': lambda boss: boss.d_hitBoss(1),
    })


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
    ('maxtoon', scenarioMaxToon),
    ('playgrounds', scenarioPlaygrounds),
    ('streets', scenarioStreets),
    ('battle', scenarioBattle),
    ('building', scenarioBuilding),
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
