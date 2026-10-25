"""Keeps the places the player goes full of other toons.

Every playground, street, Cog HQ area and boss lobby the player is in gets
NPC players walking around (NPCS_PER_AREA, or as many as the launcher's
settings say), made for the place by
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
from toontown.npcplayers.NPCSettings import npcsPerArea
from toontown.npcplayers.NPCBattleCrew import NPCBattleCrew, isNPC
from toontown.npcplayers.NPCNav import getNav
from toontown.npcplayers.NPCGolf import NPCGolf
from toontown.npcplayers.NPCMinigames import NPCMinigames
from toontown.npcplayers.NPCRacing import NPCRacing
from toontown.npcplayers.NPCParty import NPCParty
from toontown.npcplayers.NPCBossCrew import NPCBossCrew
from toontown.suit.DistributedBossCogAI import DistributedBossCogAI
from toontown.npcplayers.NPCPlayerAI import NPCPlayerAI
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import TTLocalizer, ToontownGlobals

SPAWNS_PER_TICK = 3
# Building a toon's model takes the player's game a moment, so the toons of
# one tick come in one at a time, this far apart, rather than in one frame.
SPAWN_GAP = 0.3
# How long the player's game must have been in a place before NPCs come.
PLACE_SETTLE = 1.0
# A toon that finds nowhere to walk this many times in a row is stuck (in a
# corner, say) and goes off by teleport; another comes in its place.
STUCK_TRIES = 6
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
# How fast a toon turns, in degrees a second; sharper turns slow it down, so
# it curves round corners the way a player steers.
TURN_RATE = 400.0
# How likely a toon that has stood a while is to walk off (rather than do
# something where it stands), and how long it stops after a walk.
WALK_CHANCE = 0.65
PAUSE_AFTER_WALK = (0.5, 4.0)
# How likely a wander is to go and stand by someone, and how close.
SOCIAL_WALK = 0.12
# Toons pick places to go and appear where few others are, so they spread
# out over the place: how near counts as crowding.
CROWD_RADIUS = 12.0
SOCIAL_RANGE = (3.5, 6.0)
# What a toon may do while it stands about, with how likely each is.
IDLE_ACTIONS = (('face', 30), ('look', 20), ('emote', 25), ('chat', 10), ('nothing', 15))
# Emotes (indices into OTPLocalizer.EmoteFuncDict) for standing about, and
# for greeting someone.
IDLE_EMOTES = (1, 5, 6, 7, 9, 11, 13, 16, 22)
GREET_EMOTES = (0, 0, 13, 22)
# SpeedChat phrases (OTPLocalizer.SpeedChatStaticText): hellos and cheers.
GREET_PHRASES = (101, 102, 103, 104, 105)
CHEER_PHRASES = (300, 302, 303, 304, 306, 307, 308, 309, 311)
# How near the player must be to be greeted, and how often a toon may.
GREET_RANGE = 18.0
GREET_EVERY = 90.0

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


def getOutsideAreaId(zoneId):
    """For a building's inside, the area its front door is in."""
    if zoneId is None or zoneId >= ToontownGlobals.DynamicZonesBegin or not ZoneUtil.isInterior(zoneId):
        return None
    if ZoneUtil.getHoodId(zoneId) in (ToontownGlobals.Tutorial, ToontownGlobals.MyEstate):
        return None
    return getAreaId(ZoneUtil.getBranchZone(zoneId))


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
        self.npcsPerArea = npcsPerArea()
        self.crews = {}
        self.party = NPCParty(self)
        self.golf = NPCGolf(self)
        self.minigames = NPCMinigames(self)
        self.racing = NPCRacing(self)
        self.stats = {}
        self.bossCrews = {}
        self.taskName = 'npcPlayerManager-%d' % id(self)
        taskMgr.doMethodLater(MANAGER_TICK, self.__tick, self.taskName)
        taskMgr.doMethodLater(WALK_TICK, self.__walkTick, self.taskName + '-walk')

    def delete(self):
        taskMgr.remove(self.taskName)
        taskMgr.remove(self.taskName + '-walk')
        taskMgr.removeTasksMatching(self.taskName + '-spawn-*')
        for crew in list(self.crews.values()) + list(self.bossCrews.values()):
            crew.destroy()
        for area in self.areas.values():
            for npc in area.npcs[:]:
                self.despawn(npc, quietly=True)
        self.party.destroy()
        self.minigames.destroy()
        self.racing.destroy()

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
                # Inside a shop or other building: the toons outside stay
                # (standing where they are) for when the player comes out.
                outside = self.areas.get(getOutsideAreaId(player.zoneId))
                if outside is not None:
                    outside.lastKept = now
                continue
            area = self.areas.get(areaId)
            if area is None:
                area = self.areas[areaId] = NPCArea(self, areaId)
            area.seen()
            pos = self.getPlayerPos(player)
            area.addTrail(pos, player.zoneId)
            self.populate(area, player, pos)
        for areaId, area in list(self.areas.items()):
            if now - max(area.lastSeen, getattr(area, 'lastKept', 0)) > LINGER:
                for npc in area.npcs[:]:
                    if getattr(npc, 'crew', None) is None:
                        self.despawn(npc, quietly=True)
                if not area.npcs:
                    del self.areas[areaId]
        zoneIndex = {}
        for obj in list(self.air.doId2do.values()):
            zoneIndex.setdefault(getattr(obj, 'zoneId', None), []).append(obj)
        self.party.fillSeats()
        self.party.answerHandshakes(zoneIndex)
        self.joinBattles()
        self.joinBosses()

    def placeReady(self, area, player):
        """Whether the player's own game has the place loaded and is in it.

        The ground and walls the NPCs go by are the client's; while the
        place is still loading, a spot could be found under the steps or
        inside a wall that isn't there yet, and a toon put there is stuck.
        """
        localAvatar = getClientBuiltin('localAvatar')
        if localAvatar is None or localAvatar.doId != player.doId:
            return True
        base = getClientBuiltin('base')
        place = base.cr.playGame.getPlace() if getattr(base, 'cr', None) and base.cr.playGame else None
        zoneId = getattr(place, 'zoneId', None)
        now = globalClock.getFrameTime()
        if zoneId is None or getAreaId(zoneId) != area.areaId:
            area.readySince = None
            return False
        if getattr(area, 'readySince', None) is None:
            area.readySince = now
        return now - area.readySince >= PLACE_SETTLE

    def populate(self, area, player, playerPos):
        if not self.placeReady(area, player):
            return
        if getattr(area, 'spawning', 0) > 0:
            return
        for i in range(SPAWNS_PER_TICK):
            area.spawning = getattr(area, 'spawning', 0) + 1
            taskMgr.doMethodLater(i * SPAWN_GAP, self.__spawnOne, '%s-spawn-%d-%d' % (self.taskName, area.areaId, i),
                                  extraArgs=[area, player, Point3(playerPos)])

    def __spawnOne(self, area, player, playerPos):
        area.spawning -= 1
        if self.areas.get(area.areaId) is not area or player.isDeleted() or len(area.npcs) >= self.npcsPerArea:
            return
        if not self.placeReady(area, player):
            return
        spot = self.pickSpawnSpot(area, playerPos, player.zoneId)
        if spot is not None:
            self.spawn(area, spot[0], spot[1], player)

    def pickSpawnSpot(self, area, playerPos, playerZone):
        nav = getNav()
        points = area.points()
        random.shuffle(points)
        for point, zoneId in sorted(points[:12], key=lambda p: self.crowding(area, p[0])):
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
        npc.party = None
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
        # The time since the last tick. (task.time starts again from nothing
        # each time a delayed task comes round, so it can't be used.)
        now = globalClock.getFrameTime()
        dt = max(0.0, min(1.0, now - getattr(self, 'lastWalkTick', now - WALK_TICK)))
        self.lastWalkTick = now
        try:
            for area in list(self.areas.values()):
                if not area.isActive():
                    continue
                for npc in area.npcs[:]:
                    if npc.crew is None and not npc.busy:
                        self.walkNPC(area, npc, dt)
            self.party.follow()
            for npc in self.party.members[:]:
                if npc.crew is None and not npc.busy and not npc.isDeleted():
                    self.walkNPC(None, npc, dt)
        except Exception:
            self.notify.warning('walking failed')
            import traceback
            traceback.print_exc()
        return Task.again

    def walkNPC(self, area, npc, dt):
        now = globalClock.getFrameTime()
        if npc.walk is None:
            if getattr(npc, 'faceH', None) is not None:
                self.turnNPC(npc, dt)
                return
            if area is None or now < npc.idleUntil:
                return
            # Mostly on the move, the way players run about; now and then
            # they stop for something.
            if random.random() < WALK_CHANCE or not self.idleAction(area, npc):
                if self.startWalk(area, npc):
                    npc.stuckTries = 0
                else:
                    npc.idleUntil = now + random.uniform(0.5, 2)
                    npc.stuckTries = getattr(npc, 'stuckTries', 0) + 1
                    if npc.stuckTries >= STUCK_TRIES and getNav().available():
                        self.despawn(npc)
            return
        points, speed, zoneId, done = npc.walk
        pos = npc.getPos()
        h = npc.getH()
        # Turn toward the next point no faster than a toon can, going slower
        # while the turn is sharp.
        if points:
            ahead = points[0] - pos
            if ahead.lengthSquared() > 0.01:
                wanted = -math.degrees(math.atan2(ahead[0], ahead[1]))
                turn = (wanted - h + 180) % 360 - 180
                if done is None:
                    maxTurn = TURN_RATE * dt
                    speed *= max(0.25, math.cos(math.radians(min(abs(turn), 90))))
                else:
                    # Going somewhere that matters (a battle): no dawdling.
                    maxTurn = TURN_RATE * 3 * dt
                h += max(-maxTurn, min(maxTurn, turn))
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
        npc.moveTo(pos[0], pos[1], pos[2], h)
        if not points:
            npc.walk = None
            npc.stopMoving()
            if zoneId is not None and zoneId != npc.zoneId:
                npc.b_setLocation(self.air.districtId, zoneId)
            npc.idleUntil = now + random.uniform(*PAUSE_AFTER_WALK)
            friend = getattr(npc, 'walkingTo', None)
            npc.walkingTo = None
            if friend is not None and not friend.isDeleted() and done is None:
                # Stopped by someone: turn to them, and sometimes say hello.
                self.faceToward(npc, friend.getPos())
                if random.random() < 0.5:
                    npc.afterTurn = lambda: self.greet(npc, friend)
            if done:
                done()

    def turnNPC(self, npc, dt):
        h = npc.getH()
        turn = (npc.faceH - h + 180) % 360 - 180
        maxTurn = TURN_RATE * 0.6 * dt
        if abs(turn) <= maxTurn:
            h = npc.faceH
            npc.faceH = None
        else:
            h += maxTurn if turn > 0 else -maxTurn
        pos = npc.getPos()
        npc.moveTo(pos[0], pos[1], pos[2], h)
        if npc.faceH is None:
            npc.stopMoving()
            then = getattr(npc, 'afterTurn', None)
            npc.afterTurn = None
            if then is not None:
                then()

    def faceToward(self, npc, pos):
        offset = pos - npc.getPos()
        if offset.lengthSquared() > 0.01:
            npc.faceH = -math.degrees(math.atan2(offset[0], offset[1]))

    def neighbours(self, area, npc, distance):
        """The toons near this one: the area's NPCs and the players."""
        pos = npc.getPos()
        near = []
        for other in area.npcs + self.getPlayers():
            if other is npc or other.isDeleted() or other.zoneId != npc.zoneId:
                continue
            otherPos = self.getPlayerPos(other) if not isNPC(other) else other.getPos()
            if (otherPos - pos).length() < distance:
                near.append(other)
        return near

    def idleAction(self, area, npc):
        """Something to do while standing about; False to walk instead."""
        now = globalClock.getFrameTime()
        roll = random.uniform(0, sum(weight for action, weight in IDLE_ACTIONS))
        for action, weight in IDLE_ACTIONS:
            roll -= weight
            if roll <= 0:
                break
        npc.idleUntil = now + random.uniform(1.5, 4)
        if action == 'face':
            near = self.neighbours(area, npc, 25.0)
            if not near:
                return False
            other = random.choice(near)
            self.faceToward(npc, self.getPlayerPos(other) if not isNPC(other) else other.getPos())
            if not isNPC(other) and now - getattr(npc, 'lastGreet', -GREET_EVERY) > GREET_EVERY and \
                    (self.getPlayerPos(other) - npc.getPos()).length() < GREET_RANGE:
                npc.afterTurn = lambda: self.greet(npc, other)
        elif action == 'look':
            npc.faceH = npc.getH() + random.choice((-1, 1)) * random.uniform(30, 120)
        elif action == 'emote':
            npc.b_setEmoteState(random.choice(IDLE_EMOTES), 1.0)
            npc.idleUntil = now + random.uniform(4, 8)
        elif action == 'chat':
            npc.d_setSC(random.choice(CHEER_PHRASES))
        return True

    def greet(self, npc, other):
        if npc.isDeleted() or npc.walk is not None:
            return
        npc.lastGreet = globalClock.getFrameTime()
        npc.b_setEmoteState(random.choice(GREET_EMOTES), 1.0)
        if random.random() < 0.6:
            npc.d_setSC(random.choice(GREET_PHRASES))
        npc.idleUntil = globalClock.getFrameTime() + random.uniform(3, 6)

    def startWalk(self, area, npc):
        nav = getNav()
        if not nav.available():
            return False
        pos = npc.getPos()
        candidates = []
        if random.random() < SOCIAL_WALK:
            # Go and stand by someone.
            near = self.neighbours(area, npc, WANDER_RANGE[1])
            if near:
                other = random.choice(near)
                otherPos = self.getPlayerPos(other) if not isNPC(other) else other.getPos()
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(*SOCIAL_RANGE)
                spot = Point3(otherPos[0] + dist * math.cos(angle), otherPos[1] + dist * math.sin(angle), otherPos[2])
                candidates.append((spot, other.zoneId, other))
        far = [p for p in area.points() if WANDER_RANGE[0] <= (p[0] - pos).length() <= WANDER_RANGE[1]]
        random.shuffle(far)
        wander = [(p, zoneId, None) for p, zoneId in far[:6]]
        # And a look around close by, which is mostly clear where the far
        # spots are behind something.
        for i in range(6):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(8.0, 35.0)
            wander.append((Point3(pos[0] + dist * math.cos(angle), pos[1] + dist * math.sin(angle), pos[2]), None, None))
        # The emptier places first.
        wander.sort(key=lambda c: self.crowding(area, c[0], npc))
        candidates += wander
        for target, zoneId, friend in candidates:
            path = nav.walkable(pos, target)
            if path:
                # Players mostly run, and walk now and then.
                speed = RUN_SPEED if random.random() < 0.65 else WALK_SPEED
                npc.walk = [path, speed, zoneId, None]
                npc.walkingTo = friend
                npc.faceH = None
                return True
        return False

    def crowding(self, area, point, exclude=None):
        """How many of the area's toons are at or on their way to near point."""
        count = 0
        for other in area.npcs:
            if other is exclude or other.isDeleted():
                continue
            spots = [other.getPos()]
            if other.walk:
                spots.append(other.walk[0][-1])
            for spot in spots:
                if (Point3(spot[0], spot[1], 0) - Point3(point[0], point[1], 0)).length() < CROWD_RADIUS:
                    count += 1
                    break
        return count

    # --- Battles ---

    def getBattles(self, streetOnly=False):
        return [obj for obj in list(self.air.doId2do.values())
                if isinstance(obj, DistributedBattleBaseAI)
                and (not streetOnly or obj.__class__.__name__ in STREET_BATTLES)]

    def crewFor(self, battle):
        crew = self.crews.get(battle.doId)
        if crew is None:
            crew = self.crews[battle.doId] = NPCBattleCrew(self, battle)
        return crew

    def joinBattles(self):
        for battle in self.getBattles():
            if battle.fsm is None or battle.isDeleted():
                continue
            members = [self.air.doId2do.get(t) for t in battle.toons]
            # NPCs a battle started with (inside buildings, they all do).
            for npc in members:
                if isNPC(npc) and npc.crew is None:
                    self.crewFor(battle).add(npc)
            if battle.fsm.getCurrentState().getName() in ('Off', 'FaceOff', 'Resume'):
                continue
            players = [t for t in members if t is not None and not isNPC(t)]
            if not players or len(battle.toons) >= 4 or not battle.toonCanJoin():
                continue
            crew = self.crewFor(battle)
            # The player's party comes along wherever the battle is.
            party = [npc for p in players for npc in self.party.partyOf(p)
                     if npc.crew is None and not npc.busy and npc.zoneId == p.zoneId]
            if party:
                npc = party[0]
                pos = npc.getPos()
                crew.join(npc, pos[0], pos[1], pos[2])
                continue
            if battle.__class__.__name__ not in STREET_BATTLES:
                continue
            coming = len([npc for area in self.areas.values() for npc in area.npcs
                          if getattr(npc, 'headingTo', None) is battle])
            if coming:
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
        if npc.party is not None:
            # Gone sad; off to the playground, out of the player's party.
            if npc.hp <= 0:
                self.party.disband(npc)
            return
        if npc.hp <= 0 or npc.hp < npc.maxHp * 0.3:
            # Off to the playground, as a toon would; a fresh one comes later.
            self.despawn(npc)
            return
        npc.b_setAnimState('Happy', 1.0)

    def joinBosses(self):
        for obj in list(self.air.doId2do.values()):
            if isinstance(obj, DistributedBossCogAI) and obj.doId not in self.bossCrews and \
                    [npc for npc in self.party.members if npc.doId in obj.involvedToons + obj.looseToons]:
                self.bossCrews[obj.doId] = NPCBossCrew(self, obj)

    def bossCrewDone(self, crew):
        for doId, other in list(self.bossCrews.items()):
            if other is crew:
                del self.bossCrews[doId]
        crew.destroy()

    def crewDone(self, crew):
        for doId, other in list(self.crews.items()):
            if other is crew:
                del self.crews[doId]
        crew.destroy()
