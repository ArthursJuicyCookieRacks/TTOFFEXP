"""NPC toons at the CEO's water pitchers and golf spots, on the player's
screen.

As with the cranes (NPCCraneOperator), an NPC has no client of its own, so
the player's game works an NPC's pitcher or golf spot the way a player at
it would: it turns towards the CEO at the station's own speed, holds the
button for a power, and fires. The water's line and the ball's flight are
the game's own, and only what really reaches the CEO on the player's screen
counts, told to the district as the NPC's hit. NPCBossCrew says when to take
a shot and whether to aim it well (the NPCs' share).
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from panda3d.core import (BitMask32, CollisionHandlerQueue, CollisionNode, CollisionSegment, Point3)

from toontown.npcplayers import NPCCraneOperator
from toontown.toonbase import ToontownGlobals

notify = DirectNotifyGlobal.directNotify.newCategory('NPCBanquetOperator')

# station doId -> the shot being lined up: {'npc', 'h', 'hold', 'wide',
# 'phase', 'until'}
shots = {}
# How close a turn counts as aimed.
H_SLACK = 1.5
_installed = [False]


def isNPC(avId):
    return NPCCraneOperator.isNPC(avId)


def _render():
    return NPCCraneOperator._render()


def install(theAir):
    NPCCraneOperator.air[0] = theAir
    if _installed[0]:
        return
    _installed[0] = True
    from toontown.coghq.DistributedBanquetTable import DistributedBanquetTable as Table
    from toontown.coghq.DistributedGolfSpot import DistributedGolfSpot as Spot

    for cls in (Table, Spot):
        _patchControlled(cls)

    # A golf ball that really reaches the CEO on the player's screen counts
    # for the NPC that hit it.
    origHit = Spot._DistributedGolfSpot__flyBallHit

    def flyBallHit(self, entry):
        result = origHit(self, entry)
        npc = getattr(self, 'npcWorked', None)
        if npc is None or not entry.hasInto() or not entry.getInto().isTangible():
            return result
        code = entry.getIntoNodePath().getNetTag('pieCode')
        if code and int(code) == ToontownGlobals.PieCodeBossCog:
            seq = entry.getFromNodePath().getNetTag('pieSequence')
            if seq and getattr(self, 'npcLastHit', None) != seq:
                self.npcLastHit = seq
                notify.info('NPC %d: golf ball hits the CEO' % npc)
                NPCCraneOperator.asNPC(npc, self.boss.doId, 'ballHitBoss', 1)
        return result

    Spot._DistributedGolfSpot__flyBallHit = flyBallHit
    taskMgr.add(_tick, 'npcBanquetOperator')


def _patchControlled(cls):
    origEnter = cls.enterControlled
    origExit = cls.exitControlled

    def enterControlled(self, avId):
        origEnter(self, avId)
        if isNPC(avId):
            # Turned here, not smoothed from someone's broadcasts.
            self.stopSmooth()
            self.npcWorked = avId

    def exitControlled(self):
        shots.pop(self.doId, None)
        self.npcWorked = None
        origExit(self)

    cls.enterControlled = enterControlled
    cls.exitControlled = exitControlled


def busy(station):
    return station.doId in shots


def wantShot(station, npcId, wide=False):
    """An NPC at this (client) station lines up a shot at the CEO."""
    if station.doId in shots or getattr(station, 'npcWorked', None) != npcId:
        return False
    boss = station.boss
    if boss is None or boss.isEmpty():
        return False
    render = _render()
    bossPos = boss.getPos(render)
    error = random.gauss(0, 3.0) + (random.choice((-1, 1)) * random.uniform(14, 25) if wide else 0)
    if hasattr(station, 'waterPitcherNode'):
        origin = station.nozzle.getPos(render)
        deg = math.degrees(math.atan2(bossPos[1] - origin[1], bossPos[0] - origin[0]))
        # (The water goes out at the pitcher's heading + 90.)
        h = (deg - 90 + error) % 360
        power = random.uniform(0.35, 0.99)
        t = 1 - math.pow(1 - power, 1.0 / station.waterPowerExponent)
        hold = t * station.waterPowerSpeed
        hold = max(0.3, hold + random.uniform(-0.15, 0.15))
        kind = 'water'
    else:
        root = station.root
        here = root.getPos(render)
        heading = math.degrees(math.atan2(-(bossPos[0] - here[0]), bossPos[1] - here[1]))
        parentH = root.getParent().getH(render)
        h = (heading - parentH + error) % 360
        dist = math.hypot(bossPos[0] - here[0], bossPos[1] - here[1]) + random.uniform(5, 30)
        power = max(5, min(100, 100 * (1 - (300 - dist) / 200.0)))
        hold = station.golfPowerSpeed * math.pow(power / 100.0, 1.0 / station.golfPowerExponent)
        kind = 'golf'
    shots[station.doId] = {'npc': npcId, 'h': h, 'hold': hold, 'power': power, 'phase': 'turn',
                           'until': 0, 'kind': kind, 'station': station}
    return True


def _angleTo(cur, want):
    return (want - cur + 180) % 360 - 180


def _tick(task):
    now = globalClock.getFrameTime()
    for doId, shot in list(shots.items()):
        station = shot['station']
        if station.isDisabled() or getattr(station, 'npcWorked', None) != shot['npc'] or station.state != 'Controlled':
            shots.pop(doId, None)
            continue
        node = station.waterPitcherNode if shot['kind'] == 'water' else station.root
        if shot['phase'] == 'turn':
            d = _angleTo(node.getH(), shot['h'])
            if abs(d) > H_SLACK:
                xd = -1 if d > 0 else 1
                step = station.rotateSpeed * globalClock.getDt()
                if step >= abs(d):
                    node.setH(shot['h'])
                elif shot['kind'] == 'water':
                    station._DistributedBanquetTable__movePitcher(xd)
                else:
                    station._DistributedGolfSpot__moveGolfSpot(xd)
                continue
            if shot['kind'] == 'water':
                station._DistributedBanquetTable__setMoveSound(None)
            shot['phase'] = 'hold'
            shot['until'] = now + shot['hold']
        elif shot['phase'] == 'hold' and now >= shot['until']:
            shots.pop(doId, None)
            if shot['kind'] == 'water':
                _fireWater(station, shot)
            else:
                _swing(station, shot)
    return Task.cont


def _fireWater(station, shot):
    """As the pitcher's own release (__endFireWater), for the NPC."""
    render = _render()
    origin = station.nozzle.getPos(render)
    angle = math.radians(station.waterPitcherNode.getH() + 90)
    power = max(0.001, shot['power'])
    target = origin + Point3(math.cos(angle), math.sin(angle), 0) * (station.fireLength * power)
    segment = CollisionSegment(origin[0], origin[1], origin[2], target[0], target[1], target[2])
    fromObject = render.attachNewNode(CollisionNode('npcPitcherColNode'))
    fromObject.node().addSolid(segment)
    fromObject.node().setFromCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask | ToontownGlobals.FloorBitmask)
    fromObject.node().setIntoCollideMask(BitMask32.allOff())
    queue = CollisionHandlerQueue()
    trav = base.cTrav
    trav.addCollider(fromObject, queue)
    trav.traverse(render)
    queue.sortEntries()
    hit = None
    if queue.getNumEntries():
        entry = queue.getEntry(0)
        target = entry.getSurfacePoint(render)
        hit = entry.getIntoNodePath()
    trav.removeCollider(fromObject)
    fromObject.removeNode()
    station.fireWater(origin, target)
    if hit is not None and hit.getNetTag('pieCode') and int(hit.getNetTag('pieCode')) == ToontownGlobals.PieCodeBossCog:
        station.hitBossSoundInterval.start()
        damage = 1 if power < station.YELLOW_POWER_THRESHOLD else (2 if power < station.RED_POWER_THRESHOLD else 3)
        notify.info('NPC %d: water hits the CEO for %d' % (shot['npc'], damage))
        NPCCraneOperator.asNPC(shot['npc'], station.boss.doId, 'hitBoss', damage)


def _swing(station, shot):
    """As the golf spot's own release (__endFireBall), for the NPC."""
    seq = (getattr(station, 'npcSwingSeq', 100) + 1) % 255
    station.npcSwingSeq = seq
    station.setSwingInfo(int(shot['power']), station.root.getH(), seq)
