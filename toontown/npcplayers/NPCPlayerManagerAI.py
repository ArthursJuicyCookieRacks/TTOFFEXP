"""Keeps the places the player goes full of other toons.

Every playground, street, Cog HQ area and boss lobby the player is in gets at
least NPCS_PER_AREA NPC players walking around, made for the place by
NPCProfiles. They stay while the player is near and are taken away a while
after the player leaves. When the player is in a battle, the nearest NPCs
come and join it.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from panda3d.core import Point3, Vec3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.battle.DistributedBattleBaseAI import DistributedBattleBaseAI
from toontown.classicchars import CCharPaths
from toontown.dna import DNAStoreSuitPoint
from toontown.hood import ZoneUtil
from toontown.npcplayers import NPCProfiles
from toontown.npcplayers.NPCBattleCrew import NPCBattleCrew, isNPC
from toontown.npcplayers.NPCNav import getNav
from toontown.npcplayers.NPCPlayerAI import NPCPlayerAI
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import TTLocalizer, ToontownGlobals

NPCS_PER_AREA = 12
SPAWNS_PER_TICK = 3
MANAGER_TICK = 1.0
WALK_TICK = 0.2
# How long an area keeps its NPCs once the player has left it.
LINGER = 60.0
RUN_SPEED = ToontownGlobals.ToonForwardSpeed
WALK_SPEED = ToontownGlobals.ToonForwardSpeed / 2.0
WANDER_RANGE = (12.0, 90.0)
# NPCs further than this teleport to a battle rather than run to it.
RUN_TO_BATTLE = 40.0
TELEPORT_TIME = 2.6
MAX_TRAIL = 200
TRAIL_SPACING = 8.0

COG_HQ_AREAS = (
    ToontownGlobals.BossbotHQ, ToontownGlobals.BossbotLobby,
    ToontownGlobals.SellbotHQ, ToontownGlobals.SellbotLobby, ToontownGlobals.SellbotFactoryExt,
    ToontownGlobals.CashbotHQ, ToontownGlobals.CashbotLobby,
    ToontownGlobals.LawbotHQ, ToontownGlobals.LawbotLobby, ToontownGlobals.LawbotOfficeExt,
)
# The classic characters' walks are known to be clear ground.
PLAYGROUND_CHARS = {
    ToontownGlobals.ToontownCentral: (TTLocalizer.Mickey, 0),
    ToontownGlobals.MinniesMelodyland: (TTLocalizer.Minnie, 0),
    ToontownGlobals.DaisyGardens: (TTLocalizer.Daisy, 0),
    ToontownGlobals.TheBrrrgh: (TTLocalizer.Pluto, 0),
    ToontownGlobals.DonaldsDreamland: (TTLocalizer.Donald, 0),
    ToontownGlobals.GoofySpeedway: (TTLocalizer.Goofy, 1),
    ToontownGlobals.OutdoorZone: (TTLocalizer.Chip, 0),
}
STREET_BATTLES = ('DistributedBattleAI',)


def getAreaId(zoneId):
    """The area a zone belongs to, or None where no NPCs go."""
    if zoneId is None or zoneId >= ToontownGlobals.DynamicZonesBegin:
        return None
    if zoneId in COG_HQ_AREAS:
        return zoneId
    hoodId = ZoneUtil.getHoodId(zoneId)
    if hoodId in (ToontownGlobals.Tutorial, ToontownGlobals.MyEstate):
        return None
    if zoneId == hoodId:
        return zoneId
    if ZoneUtil.isInterior(zoneId):
        return None
    branchId = ZoneUtil.getBranchZone(zoneId)
    if branchId != hoodId and branchId % 100 == 0 and hoodId not in (ToontownGlobals.BossbotHQ, ToontownGlobals.SellbotHQ,
                                                                    ToontownGlobals.CashbotHQ, ToontownGlobals.LawbotHQ):
        return branchId
    return None


class NPCArea:

    def __init__(self, manager, areaId):
        self.manager = manager
        self.areaId = areaId
        self.npcs = []
        self.lastSeen = globalClock.getFrameTime()
        self.anchors = []
        self.trail = []
        self.loadAnchors()

    def loadAnchors(self):
        from toontown.distributed.HoodMgr import HoodMgr
        air = self.manager.air
        areaId = self.areaId
        if areaId == ZoneUtil.getHoodId(areaId):
            for point in HoodMgr.dropPoints.get(areaId, ()):
                self.anchors.append((Point3(*point[:3]), areaId))
        if areaId in PLAYGROUND_CHARS:
            name, location = PLAYGROUND_CHARS[areaId]
            paths = CCharPaths.getPaths(name, location)
            for node in paths:
                self.anchors.append((Point3(CCharPaths.getNodePos(node, paths)), areaId))
        planner = air.suitPlanners.get(areaId)
        if planner is not None and hasattr(planner, 'dnaData'):
            graph = planner.dnaData.suitGraph
            for point in graph.points:
                if point.getPointType() != DNAStoreSuitPoint.STREETPOINT:
                    continue
                try:
                    zoneId = graph.getPointZone(point)
                except IndexError:
                    continue
                zoneId = ZoneUtil.getTrueZoneId(int(zoneId), areaId)
                self.anchors.append((Point3(point.getPos()), zoneId))

    def addTrail(self, pos, zoneId):
        for point, z in self.trail[-10:]:
            if (point - pos).length() < TRAIL_SPACING:
                return
        self.trail.append((Point3(pos), zoneId))
        if len(self.trail) > MAX_TRAIL:
            del self.trail[0]

    def points(self):
        return self.anchors + self.trail

    def seen(self):
        self.lastSeen = globalClock.getFrameTime()

    def isActive(self):
        return globalClock.getFrameTime() - self.lastSeen < 2 * MANAGER_TICK + 0.5


class NPCPlayerManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCPlayerManagerAI')

    def __init__(self, air):
        self.air = air
        self.areas = {}
        self.crews = {}
        self.taskName = 'npcPlayerManager-%d' % id(self)
        taskMgr.doMethodLater(MANAGER_TICK, self.__tick, self.taskName)
        taskMgr.doMethodLater(WALK_TICK, self.__walkTick, self.taskName + '-walk')

    def delete(self):
        taskMgr.remove(self.taskName)
        taskMgr.remove(self.taskName + '-walk')
        for crew in list(self.crews.values()):
            crew.destroy()
        for area in self.areas.values():
            for npc in area.npcs[:]:
                self.despawn(npc, quietly=True)

    # --- Who and where the players are ---

    def getPlayers(self):
        players = []
        for obj in list(self.air.doId2do.values()):
            if isinstance(obj, DistributedToonAI) and not isNPC(obj) and obj.isPlayerControlled():
                players.append(obj)
        return players

    def getPlayerPos(self, player):
        base = getClientBuiltin('base')
        localAvatar = getClientBuiltin('localAvatar')
        if localAvatar is not None and localAvatar.doId == player.doId and not localAvatar.isEmpty():
            return localAvatar.getPos(base.render)
        return player.getPos()

    # --- Populating ---

    def __tick(self, task):
        try:
            self.__update()
        except Exception:
            self.notify.warning('update failed')
            import traceback
            traceback.print_exc()
        return Task.again

    def __update(self):
        now = globalClock.getFrameTime()
        for player in self.getPlayers():
            areaId = getAreaId(player.zoneId)
            if areaId is None:
                continue
            area = self.areas.get(areaId)
            if area is None:
                area = self.areas[areaId] = NPCArea(self, areaId)
            area.seen()
            pos = self.getPlayerPos(player)
            area.addTrail(pos, player.zoneId)
            self.populate(area, player, pos)
        for areaId, area in list(self.areas.items()):
            if now - area.lastSeen > LINGER:
                for npc in area.npcs[:]:
                    if getattr(npc, 'crew', None) is None:
                        self.despawn(npc, quietly=True)
                if not area.npcs:
                    del self.areas[areaId]
        self.joinBattles()

    def populate(self, area, player, playerPos):
        for i in range(SPAWNS_PER_TICK):
            if len(area.npcs) >= NPCS_PER_AREA:
                return
            spot = self.pickSpawnSpot(area, playerPos, player.zoneId)
            if spot is None:
                return
            self.spawn(area, spot[0], spot[1], player)

    def pickSpawnSpot(self, area, playerPos, playerZone):
        nav = getNav()
        points = area.points()
        random.shuffle(points)
        for point, zoneId in points[:6]:
            ground = nav.groundZ(point[0], point[1], point[2])
            if ground is not None:
                return Point3(point[0], point[1], ground), zoneId
        # Somewhere near the player, in sight of them.
        for i in range(6):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(8, 30)
            target = Point3(playerPos[0] + dist * math.cos(angle), playerPos[1] + dist * math.sin(angle), playerPos[2])
            path = nav.walkable(playerPos, target)
            if path:
                return path[-1], playerZone
        return None

    def spawn(self, area, pos, zoneId, player=None):
        npc = NPCPlayerAI(self.air, self)
        npc.applyProfile(NPCProfiles.makeProfile(zoneId, player))
        npc.unlimitedGags = 1
        npc.area = area
        npc.crew = None
        npc.walk = None
        npc.idleUntil = globalClock.getFrameTime() + random.uniform(0, 6)
        npc.busy = False
        npc.generateInZone(zoneId, pos[0], pos[1], pos[2], random.uniform(-180, 180))
        npc.b_setAnimState('Happy', 1.0)
        area.npcs.append(npc)
        return npc

    def despawn(self, npc, quietly=False):
        area = getattr(npc, 'area', None)
        if area is not None and npc in area.npcs:
            area.npcs.remove(npc)
        npc.walk = None
        npc.busy = True
        if npc.isDeleted():
            return
        if quietly:
            npc.requestDelete()
            return
        npc.b_setAnimState('TeleportOut', 1.0)
        taskMgr.doMethodLater(4.0, lambda task: npc.isDeleted() or npc.requestDelete(),
                              'npcDespawn-%d' % npc.doId)

    # --- Walking around ---

    def __walkTick(self, task):
        dt = task.time - getattr(task, 'lastTime', task.time - WALK_TICK)
        task.lastTime = task.time
        try:
            for area in list(self.areas.values()):
                if not area.isActive():
                    continue
                for npc in area.npcs[:]:
                    if npc.crew is None and not npc.busy:
                        self.walkNPC(area, npc, dt)
        except Exception:
            self.notify.warning('walking failed')
            import traceback
            traceback.print_exc()
        return Task.again

    def walkNPC(self, area, npc, dt):
        now = globalClock.getFrameTime()
        if npc.walk is None:
            if now < npc.idleUntil:
                return
            if not self.startWalk(area, npc):
                npc.idleUntil = now + random.uniform(2, 6)
            return
        points, speed, zoneId, done = npc.walk
        pos = npc.getPos()
        remaining = speed * dt
        while points and remaining > 0:
            target = points[0]
            step = target - pos
            length = step.length()
            if length <= remaining:
                pos = target
                remaining -= length
                points.pop(0)
            else:
                pos = pos + step * (remaining / length)
                remaining = 0
        direction = (points[0] if points else pos) - npc.getPos()
        h = npc.getH()
        if direction.lengthSquared() > 0.01:
            h = -math.degrees(math.atan2(direction[0], direction[1]))
        npc.moveTo(pos[0], pos[1], pos[2], h)
        if not points:
            npc.walk = None
            npc.stopMoving()
            if zoneId is not None and zoneId != npc.zoneId:
                npc.b_setLocation(self.air.districtId, zoneId)
            npc.idleUntil = now + random.uniform(3, 14)
            if done:
                done()

    def startWalk(self, area, npc):
        nav = getNav()
        if not nav.available():
            return False
        pos = npc.getPos()
        candidates = [p for p in area.points() if WANDER_RANGE[0] <= (p[0] - pos).length() <= WANDER_RANGE[1]]
        random.shuffle(candidates)
        candidates = candidates[:3]
        # And a look around close by.
        for i in range(2):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(*WANDER_RANGE) / 3.0
            candidates.append((Point3(pos[0] + dist * math.cos(angle), pos[1] + dist * math.sin(angle), pos[2]), None))
        for target, zoneId in candidates:
            path = nav.walkable(pos, target)
            if path:
                speed = RUN_SPEED if random.random() < 0.75 else WALK_SPEED
                npc.walk = [path, speed, zoneId, None]
                return True
        return False

    # --- Battles ---

    def getBattles(self):
        return [obj for obj in list(self.air.doId2do.values())
                if isinstance(obj, DistributedBattleBaseAI) and obj.__class__.__name__ in STREET_BATTLES]

    def joinBattles(self):
        for battle in self.getBattles():
            if battle.fsm is None or battle.fsm.getCurrentState().getName() in ('Off', 'FaceOff', 'Resume'):
                continue
            players = [t for t in battle.toons if not isNPC(self.air.doId2do.get(t))]
            if not players:
                continue
            crew = self.crews.get(battle.doId)
            if crew is None:
                crew = self.crews[battle.doId] = NPCBattleCrew(self, battle)
            coming = len([npc for area in self.areas.values() for npc in area.npcs
                          if getattr(npc, 'headingTo', None) is battle])
            if coming or len(battle.toons) >= 4 or not battle.toonCanJoin():
                continue
            npc = self.pickHelper(battle)
            if npc is not None:
                self.sendToBattle(npc, battle, crew)

    def pickHelper(self, battle):
        area = self.areas.get(getAreaId(battle.zoneId))
        if area is None:
            return None
        free = [npc for npc in area.npcs if npc.crew is None and not npc.busy and not npc.isDeleted()]
        if not free:
            return None
        battlePos = Point3(battle.pos)
        free.sort(key=lambda npc: (npc.getPos() - battlePos).length())
        return free[0]

    def battleSpot(self, battle):
        nav = getNav()
        center = Point3(battle.pos)
        angles = [random.uniform(0, 2 * math.pi) for i in range(8)]
        for angle in angles:
            spot = Point3(center[0] + 12 * math.cos(angle), center[1] + 12 * math.sin(angle), center[2])
            ground = nav.groundZ(spot[0], spot[1], spot[2])
            if ground is not None and nav.clearLine(Point3(spot[0], spot[1], ground), center):
                return Point3(spot[0], spot[1], ground)
        return Point3(center[0], center[1] - 12, center[2])

    def sendToBattle(self, npc, battle, crew):
        spot = self.battleSpot(battle)
        npc.headingTo = battle
        npc.busy = True

        def arrive():
            npc.headingTo = None
            npc.busy = False
            if npc.isDeleted() or battle.isDeleted():
                return
            if not crew.join(npc, spot[0], spot[1], spot[2]):
                npc.idleUntil = globalClock.getFrameTime() + 3

        path = None
        if (npc.getPos() - spot).length() <= RUN_TO_BATTLE and npc.zoneId == battle.zoneId:
            path = getNav().walkable(npc.getPos(), spot)
        if path:
            npc.busy = False
            npc.walk = [path, RUN_SPEED, battle.zoneId, arrive]
            npc.idleUntil = 0
            return
        # Too far to run: teleport over, the way friends did online.
        if npc.zoneId != battle.zoneId:
            npc.b_setLocation(self.air.districtId, battle.zoneId)
        npc.walk = None
        h = -math.degrees(math.atan2(battle.pos[0] - spot[0], battle.pos[1] - spot[1]))
        npc.placeAt(spot[0], spot[1], spot[2], h)
        npc.b_setAnimState('TeleportIn', 1.0)

        def landed(task):
            if not npc.isDeleted():
                npc.b_setAnimState('Happy', 1.0)
                arrive()
            return Task.done

        taskMgr.doMethodLater(TELEPORT_TIME, landed, 'npcTeleportIn-%d' % npc.doId)

    def npcLeftBattle(self, npc, battle):
        if npc.isDeleted():
            return
        npc.idleUntil = globalClock.getFrameTime() + random.uniform(2, 5)
        if npc.hp <= 0 or npc.hp < npc.maxHp * 0.3:
            # Off to the playground, as a toon would; a fresh one comes later.
            self.despawn(npc)
            return
        npc.b_setAnimState('Happy', 1.0)

    def crewDone(self, crew):
        for doId, other in list(self.crews.items()):
            if other is crew:
                del self.crews[doId]
        crew.destroy()
