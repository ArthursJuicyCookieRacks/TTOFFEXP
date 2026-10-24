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
import os
import re
import sys
import time
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = os.path.abspath(os.environ.get('AUTOPLAY_DB', 'autoplay-db'))

from panda3d.core import loadPrcFileData
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
from direct.showbase.DirectObject import DirectObject
from otp.local import LocalServer


class StepFailed(Exception):
    pass


def log(*args):
    print('AUTOPLAY:', *args, flush=True)


# --- Error collection ---

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


def placeState():
    p = place()
    if p is None or p.fsm is None:
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
    # The strongest single-target gag the toon still carries.
    inventory = localAvatar.inventory
    for level in range(6, -1, -1):
        for track in (ToontownBattleGlobals.THROW_TRACK, ToontownBattleGlobals.SQUIRT_TRACK,
                      ToontownBattleGlobals.DROP_TRACK):
            if inventory.numItem(track, level) > 0:
                return track, level
    raise StepFailed('the toon is out of throw, squirt and drop gags')


def fightBattle(timeout=600):
    yield until(lambda: placeState() == 'battle', 60, 'battle to start')
    deadline = time.time() + timeout
    rounds = 0
    while placeState() == 'battle':
        if time.time() > deadline:
            raise StepFailed('the battle did not end in %d seconds' % timeout)
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


SCENARIOS = [
    ('login', scenarioLogin),
    ('maxtoon', scenarioMaxToon),
    ('playgrounds', scenarioPlaygrounds),
    ('streets', scenarioStreets),
    ('battle', scenarioBattle),
    ('building', scenarioBuilding),
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
                raise StepFailed('%s: timed out waiting for %s (login state %s, place state %s)' % (
                    name, waiting.what, loginState(), placeState()))
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
