"""NPC players who race karts at Goofy Speedway.

A race pad that isn't for practice needs two racers or more, so when the
player sits in a starting block, NPCs from the Speedway pull up in the other
blocks. In the race they answer what each racer's client sends: they ask for
their kart, drive it round the track at a pace a decent racer would keep,
say how far round they are, pick up and throw race gags, and are slowed by
anvils, pies and banana peels like anyone else.

The track's shape comes from the player's client, which offline runs in the
same process and has loaded the same track.
"""

import bisect
import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from panda3d.core import Point3, Vec3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.hood import ZoneUtil
from toontown.npcplayers.NPCMinigames import clientSend, isNPC
from toontown.racing import RaceGlobals
from toontown.racing.DistributedRaceAI import DistributedRaceAI
from toontown.racing.DistributedRacePadAI import DistributedRacePadAI
from toontown.racing.KartShopGlobals import KartGlobals
from toontown.toonbase import ToontownGlobals

TICK = 0.1
TELEPORT_TIME = 2.6
# How long a starting block's enter and exit movies take on a client.
MOVIE_TIME = 3.0
# How often a racer tells the race how far round it is, as clients do.
REPORT_TIME = 0.5
# How near a racer has to pass a gag to pick it up, or a banana peel to hit it.
PICKUP_RADIUS = 6.0
BANANA_RADIUS = 2.5
# How long a racer is slowed, and to what share of its speed.
SPIN_TIME, SPIN_SPEED = 1.5, 0.3
PIE_TIME, PIE_SPEED = 2.0, 0.4
ANVIL_SPEED = 0.25
TURBO_TIME, TURBO_SPEED = 3.0, 1.5


def clientRace(race):
    base = getClientBuiltin('base')
    return base.cr.doId2do.get(race.doId) if base else None


class Track:
    """A race's track as distances along its curve, from the start line."""

    def __init__(self, client):
        self.points = [Point3(p) for p in client.curvePoints]
        self.ts = list(client.curveTs)
        self.maxT = client.curve.getMaxT()
        self.startT = client.startT
        count = len(self.points)
        self.startIndex = int(round(self.startT / self.maxT * count)) % count
        # The points in the order a racer passes them, and how far along
        # each is.
        self.order = [(self.startIndex + i) % count for i in range(count)]
        self.along = [0.0]
        for i in range(1, count + 1):
            a = self.points[self.order[i - 1]]
            b = self.points[self.order[i % count]]
            self.along.append(self.along[-1] + (b - a).length())
        self.length = self.along[-1]

    def at(self, distance):
        """Where a racer this far round is: its point, heading, and the
        curve's t there."""
        d = distance % self.length
        i = max(bisect.bisect_right(self.along, d) - 1, 0)
        i = min(i, len(self.order) - 1)
        a = self.points[self.order[i]]
        b = self.points[self.order[(i + 1) % len(self.order)]]
        span = self.along[i + 1] - self.along[i]
        f = (d - self.along[i]) / span if span > 0 else 0.0
        point = a + (b - a) * f
        heading = math.degrees(math.atan2(-(b - a)[0], (b - a)[1]))
        t0 = self.ts[self.order[i]]
        t1 = self.ts[self.order[(i + 1) % len(self.order)]]
        if t1 < t0:
            t1 += self.maxT
        t = (t0 + (t1 - t0) * f) % self.maxT
        return point, heading, t

    def lapT(self, t):
        return ((t - self.startT) / self.maxT) % 1.0

    def nearest(self, pos):
        """How far round the track is the point nearest pos, and how far
        to the right of the curve pos is."""
        best = None
        for i, index in enumerate(self.order):
            offset = self.points[index] - pos
            offset.setZ(0)
            d2 = offset.lengthSquared()
            if best is None or d2 < best[0]:
                best = (d2, i)
        i = best[1]
        distance = self.along[i]
        if distance > self.length / 2:
            distance -= self.length
        point, heading, t = self.at(distance)
        right = Vec3(math.cos(math.radians(heading)), math.sin(math.radians(heading)), 0)
        side = Vec3(pos - point)
        side.setZ(0)
        return distance, side.dot(right)


class NPCDriver:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCDriver')

    def __init__(self, racing, npc, race):
        self.racing = racing
        self.npc = npc
        self.race = race
        self.air = race.air
        self.track = None
        self.askedForKart = False
        self.distance = None
        self.side = 0.0
        self.lane = random.uniform(-3, 3)
        self.lastTime = None
        self.lastReport = 0
        self.finished = False
        self.left = False
        # A racer's pace: its whole race takes between a little over the
        # track record and well inside the time to qualify.
        record, qualify = RaceGlobals.TrackDict[race.trackId][2], RaceGlobals.TrackDict[race.trackId][1]
        skill = random.random()
        self.raceTime = record * 1.1 + skill * (qualify * 0.8 - record * 1.1)
        self.wobble = random.uniform(0, 2 * math.pi)
        self.gag = 0
        self.useGagAt = 0
        self.turboUntil = 0
        self.slowUntil = 0
        self.slowSpeed = 1.0
        self.seenPies = 0
        self.seenGags = {}

    def kart(self):
        for avId, kartId in self.race.avatarKarts:
            if avId == self.npc.doId:
                return self.air.doId2do.get(kartId)
        return None

    def update(self, now):
        race = self.race
        if self.left or self.npc.doId not in race.avatars:
            return
        if race.state in ('Prep', 'Tutorial', 'Start') and not self.askedForKart and self.kart() is not None:
            self.askedForKart = True
            self.npc.asSender(race.requestKart)
        if self.track is None:
            client = clientRace(race)
            if client is None or len(getattr(client, 'curvePoints', ())) < 2 or client.curve is None \
                    or not getattr(client, 'startingPos', None) or self.npc.doId not in client.avIds:
                return
            self.track = Track(client)
            self.startPos, self.startH = self.startingSpot(client)
            self.distance, self.side = self.track.nearest(self.startPos)
            self.startSide = self.side
            self.startDistance = self.distance
        kart = self.kart()
        if kart is None or kart.isDeleted() or not self.askedForKart:
            return
        startTime = getattr(race, 'startTime', None)
        if self.finished:
            self.leaveWhenDone()
            return
        if race.state != 'Start' or startTime is None or now < startTime:
            # On the grid, waiting for the lights.
            if now - self.lastReport > REPORT_TIME:
                self.lastReport = now
                self.place(kart, self.startPos, self.startH)
            return
        dt = 0.0 if self.lastTime is None else now - self.lastTime
        self.lastTime = now
        self.distance += self.speed(now) * dt
        lapCount = race.lapCount
        if self.distance >= lapCount * self.track.length:
            self.finish(now)
            return
        point, heading, t = self.track.at(self.distance)
        # From its place on the grid into its own lane.
        blend = min(max((self.distance - self.startDistance) / 120.0, 0.0), 1.0)
        side = self.startSide * (1 - blend) + self.lane * blend
        right = Vec3(math.cos(math.radians(heading)), math.sin(math.radians(heading)), 0)
        pos = point + right * side
        self.place(kart, pos, heading)
        self.pos = pos
        self.heading = heading
        if now - self.lastReport > REPORT_TIME:
            self.lastReport = now
            self.report(t)
        if race.raceType != RaceGlobals.Practice:
            self.gags(now, pos, heading)

    def startingSpot(self, client):
        spin = 180 if client.reversed else 0
        pos, hpr = client.startingPos[client.startingPlaces[client.avIds.index(self.npc.doId)]]
        return Point3(pos), hpr[0] + spin

    def place(self, kart, pos, heading):
        kart.sendUpdate('setSmPosHpr', [pos[0], pos[1], pos[2], heading, 0, 0,
                                        globalClockDelta.getRealNetworkTime(bits=16)])

    def speed(self, now):
        race = self.race
        speed = race.lapCount * self.track.length / self.raceTime
        # Up to speed over the first few seconds off the grid.
        speed *= min(max((now - race.startTime) / 3.0, 0.1), 1.0)
        # Nobody drives at one speed the whole way.
        speed *= 1 + 0.08 * math.sin(now * 0.4 + self.wobble)
        if now < self.turboUntil:
            speed *= TURBO_SPEED
        if race.currentlyAffectedByAnvil.get(self.npc.doId):
            speed *= ANVIL_SPEED
        pie = race.pieTargets.get(self.npc.doId, 0)
        if pie > self.seenPies:
            self.seenPies = pie
            self.slow(now + PIE_TIME, PIE_SPEED)
        if now < self.slowUntil:
            speed *= self.slowSpeed
        return speed

    def slow(self, until, speed):
        self.slowUntil = until
        self.slowSpeed = speed

    def laps(self):
        return int(math.floor(self.distance / self.track.length))

    def report(self, t):
        if self.distance < 0:
            laps, lapT = 0, 0.0
        else:
            laps, lapT = self.laps(), self.track.lapT(t)
        lapT = min(max(lapT, 0.0), 0.9999)
        clientSend(self.npc, self.race, 'heresMyT', self.npc.doId, laps, lapT,
                   globalClockDelta.getRealNetworkTime(bits=16))

    def finish(self, now):
        self.finished = True
        self.finishedAt = now
        clientSend(self.npc, self.race, 'heresMyT', self.npc.doId, self.race.lapCount, 0.0,
                   globalClockDelta.getRealNetworkTime(bits=16))
        stats = self.racing.manager.stats
        stats['race finishes'] = stats.get('race finishes', 0) + 1
        self.notify.info('NPC %d finished race %d' % (self.npc.doId, self.race.doId))

    def leaveWhenDone(self):
        # A racer leaves once the players have, so the race can end.
        race = self.race
        players = [avId for avId in race.avatars if not isNPC(self.air.doId2do.get(avId))]
        if not players or all(avId in race.finishedAvatars for avId in players) and \
                globalClock.getFrameTime() - self.finishedAt > 30:
            self.leave()

    def leave(self):
        if self.left:
            return
        self.left = True
        if self.npc.doId in self.race.avatars and not self.race.isDeleted():
            clientSend(self.npc, self.race, 'racerLeft', self.npc.doId)

    def gags(self, now, pos, heading):
        race = self.race
        npcId = self.npc.doId
        if self.gag and now >= self.useGagAt:
            self.useGag(now, pos, heading)
        if not self.gag:
            for slot, point in enumerate(getattr(race, 'gagPoints', ())):
                gag = race.gags.get(slot)
                if not gag or not gag[0]:
                    continue
                if (Vec3(point[0] - pos[0], point[1] - pos[1], 0)).length() > PICKUP_RADIUS:
                    continue
                places = sorted(race.avatarProgress, key=race.avatarProgress.get, reverse=True)
                if npcId not in places:
                    break
                gagType = RaceGlobals.GagFreq[places.index(npcId)][gag[1]]
                clientSend(self.npc, race, 'hasGag', slot, gagType, gag[1])
                if race.avatarGags.get(npcId) == gagType:
                    self.gag = gagType
                    self.useGagAt = now + random.uniform(2.0, 6.0)
                break
        for gag in race.livingGags:
            if gag.isDeleted() or gag.getType() != 0:
                continue
            seen = self.seenGags.setdefault(gag.doId, now)
            if now - seen < 1.0:
                continue
            gx, gy, gz = gag.getPos()
            if (Vec3(gx - pos[0], gy - pos[1], 0)).length() < BANANA_RADIUS:
                clientSend(self.npc, gag, 'hitSomebody', npcId, globalClockDelta.getFrameNetworkTime(16, 100))
                self.slow(now + SPIN_TIME, SPIN_SPEED)
                break

    def useGag(self, now, pos, heading):
        gag, self.gag = self.gag, 0
        stats = self.racing.manager.stats
        stats['race gags'] = stats.get('race gags', 0) + 1
        if gag == RaceGlobals.BANANA:
            # Dropped just behind the kart.
            back = Vec3(math.sin(math.radians(heading)), -math.cos(math.radians(heading)), 0) * 6
            self.npc.asSender(self.race.requestThrow, pos[0] + back[0], pos[1] + back[1], pos[2])
            return
        if gag == RaceGlobals.TURBO:
            self.turboUntil = now + TURBO_TIME
        self.npc.asSender(self.race.requestThrow, 0, 0, 0)


class NPCRacing:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCRacing')

    def __init__(self, manager):
        self.manager = manager
        self.air = manager.air
        self.drivers = {}
        self.taskName = 'npcRacing'
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    def destroy(self):
        taskMgr.remove(self.taskName)
        self.drivers = {}

    def __tick(self, task):
        try:
            self.update()
        except Exception:
            self.notify.warning('racing tick failed')
            import traceback
            traceback.print_exc()
        return Task.again

    def anyoneRacing(self):
        """Whether a player is at Goofy Speedway or in a race (its own zone)."""
        if self.drivers:
            return True
        for player in getattr(self.manager, 'lastPlayers', None) or self.manager.getPlayers():
            zoneId = player.zoneId or 0
            if zoneId >= ToontownGlobals.DynamicZonesBegin or ZoneUtil.getHoodId(zoneId) == ToontownGlobals.GoofySpeedway:
                return True
        return False

    def update(self):
        # Looking through every object in the game ten times a second is
        # only worth it where there is racing to do.
        if not self.anyoneRacing():
            return
        now = globalClock.getFrameTime()
        pads, races = [], []
        for obj in list(self.air.doId2do.values()):
            if isinstance(obj, DistributedRacePadAI):
                pads.append(obj)
            elif isinstance(obj, DistributedRaceAI):
                races.append(obj)
        for pad in pads:
            self.fillPad(pad, now)
        for race in races:
            self.drive(race, now)
        for npcId, driver in list(self.drivers.items()):
            if driver.race.isDeleted() or driver.npc.isDeleted():
                del self.drivers[npcId]

    # --- On the pads ---

    def fillPad(self, pad, now):
        blocks = pad.startingBlocks
        for block in blocks:
            self.finishMovie(block, now)
        if pad.trackType == RaceGlobals.Practice:
            return
        players = [self.air.doId2do.get(block.avId) for block in blocks
                   if block.avId and not isNPC(self.air.doId2do.get(block.avId))]
        npcs = [block for block in blocks if block.avId and isNPC(self.air.doId2do.get(block.avId))]
        if pad.state != 'WaitCountdown':
            return
        if not players:
            # The player got out; so do they.
            for block in npcs:
                if block.currentMovie == 0:
                    self.air.doId2do[block.avId].asSender(block.requestExit)
            return
        player = players[0]
        if player is None or getattr(pad, 'npcBoarding', 0) > now:
            return
        free = [block for block in blocks if not block.avId and not getattr(block, 'npcComing', False)]
        if not free:
            return
        npc = self.pickRacer(pad, player)
        if npc is None:
            return
        pad.npcBoarding = now + 1.5
        self.board(npc, random.choice(free), player)

    def pickRacer(self, pad, player):
        from toontown.npcplayers.NPCPlayerManagerAI import getAreaId
        areaId = getAreaId(pad.zoneId)
        area = self.manager.areas.get(areaId)
        if area is None:
            return None
        fee = RaceGlobals.getEntryFee(pad.trackId, pad.trackType)
        free = [npc for npc in area.npcs if npc.crew is None and not npc.busy and not npc.isDeleted()
                and npc.hasKart() and npc.getTickets() >= fee]
        return random.choice(free) if free else None

    def board(self, npc, block, player):
        self.notify.info('NPC %d drives up to starting block %d with %d' % (npc.doId, block.doId, player.doId))
        party = self.manager.party
        party.take(npc, player)
        npc.walk = None
        npc.busy = True
        block.npcComing = True
        x, y, z = block.posHpr[:3]
        h = math.radians(block.posHpr[3])
        # Beside the block, where a toon walks up to it.
        npc.placeAt(x + 6 * math.cos(h), y + 6 * math.sin(h), z, block.posHpr[3])
        npc.b_setAnimState('TeleportIn', 1.0)

        def getIn(task):
            block.npcComing = False
            if npc.isDeleted() or block.isDeleted():
                return Task.done
            npc.b_setAnimState('Happy', 1.0)
            if not block.avId and block.pad.state == 'WaitCountdown':
                npc.asSender(block.requestEnter, 1)
            if block.avId != npc.doId:
                party.disband(npc)
            return Task.done

        taskMgr.doMethodLater(TELEPORT_TIME, getIn, 'npcRaceBoard-%d' % npc.doId)

    def finishMovie(self, block, now):
        npc = self.air.doId2do.get(block.avId)
        if not isNPC(npc):
            block.npcMovie = None
            return
        if not block.currentMovie:
            block.npcMovie = None
            return
        movie = getattr(block, 'npcMovie', None)
        if movie is None or movie[0] != block.currentMovie:
            block.npcMovie = (block.currentMovie, now)
            return
        if now - movie[1] < MOVIE_TIME:
            return
        block.npcMovie = None
        leaving = block.currentMovie == KartGlobals.EXIT_MOVIE
        npc.asSender(block.movieFinished)
        if leaving and block.avId == 0:
            self.manager.party.disband(npc)

    # --- In the race ---

    def drive(self, race, now):
        for avId in list(race.avatars):
            npc = self.air.doId2do.get(avId)
            if not isNPC(npc):
                continue
            if npc.zoneId != race.zoneId:
                # Out of the starting block; off to the race with the
                # player (see NPCParty.follow).
                npc.busy = False
                continue
            driver = self.drivers.get(avId)
            if driver is None or driver.race is not race:
                driver = self.drivers[avId] = NPCDriver(self, npc, race)
            driver.update(now)
