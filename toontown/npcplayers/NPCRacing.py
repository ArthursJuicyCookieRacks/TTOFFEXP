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
# Surfaces a kart wheel should not be on, and how the NPCs keep off them.
OFF_ROAD = ('grass', 'sand')
# Floors with no surface named that are the ground beside the road.
OFF_ROAD_FLOORS = ('inner_ground', 'outter_ground', 'ground1')
# The road's edges are measured every ROAD_BIN feet round, ROAD_WIDTH
# either side of the curve; a kart keeps ROAD_MARGIN inside them (half a
# kart and a little), looking ROAD_AHEAD feet ahead.
ROAD_BIN = 8.0
ROAD_STEP = 1.0
ROAD_WIDTH = 40.0
ROAD_AHEAD = 40.0
ROAD_MARGIN = 2.6
ROAD_REACH = 40.0
ROAD_STEER_SPEED = 25.0
import os as _os
ROAD_DEBUG = bool(_os.environ.get('NPC_ROAD_DEBUG'))
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
        # Steering in from the edge where the curve runs off the road (it
        # hugs the inside of some turns): how far, and toward where.
        self.shift = 0.0
        self.shiftTarget = 0.0
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
        # Its lane is about the road's middle, which isn't always the curve.
        road = self.roadPoint(self.distance)
        middle = road[1] if road is not None else 0.0
        side = self.startSide * (1 - blend) + (middle + self.lane) * blend
        right = Vec3(math.cos(math.radians(heading)), math.sin(math.radians(heading)), 0)
        # Kept between the road's edges a little way ahead (the curve
        # hugs the inside of some turns, past the edge of the asphalt).
        want = side
        bounds = self.roadBounds(self.distance, side)
        if bounds is not None:
            lo, hi = bounds
            if hi - lo >= 2 * ROAD_MARGIN:
                want = min(max(side, lo + ROAD_MARGIN), hi - ROAD_MARGIN)
            else:
                want = (lo + hi) / 2.0
        self.shiftTarget = want - side
        step = ROAD_STEER_SPEED * dt
        self.shift += max(-step, min(step, self.shiftTarget - self.shift))
        pos = point + right * (side + self.shift)
        pos, pitch, roll = self.ground(pos, heading)
        if ROAD_DEBUG and now > getattr(self, 'posDebugAt', 0):
            self.posDebugAt = now + 2.0
            self.notify.info('NPC kart %s at %d ft round: placed %s hpr %.0f %.0f %.0f, road height %s, curve %s, lift %s' % (
                self.npc.doId, self.distance, tuple(round(v, 1) for v in pos), heading, pitch, roll,
                self.roadZ(self.distance), tuple(round(v) for v in point), getattr(self, 'lift', None)))
        self.place(kart, pos, heading, pitch, roll)
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

    def place(self, kart, pos, heading, pitch=0.0, roll=0.0):
        kart.sendUpdate('setSmPosHpr', [pos[0], pos[1], pos[2], heading, pitch, roll,
                                        globalClockDelta.getRealNetworkTime(bits=16)])

    def ground(self, pos, heading):
        """On the road itself, tilted with it (the banked turns, the hills),
        as a player's kart sits: the road under each corner of the kart,
        from the floor collisions a kart's wheels use. The curve alone can
        be a few feet off the road."""
        base = getClientBuiltin('base')
        if base is None or getattr(self, 'rayNP', None) is None:
            if base is None:
                return pos, 0.0, 0.0
            from panda3d.core import CollisionTraverser, CollisionHandlerQueue, CollisionNode, CollisionRay
            from otp.otpbase import OTPGlobals
            self.trav = CollisionTraverser('npcKartGround')
            self.queue = CollisionHandlerQueue()
            node = CollisionNode('npcKartGround')
            node.addSolid(CollisionRay(0, 0, 0, 0, 0, -1))
            node.setFromCollideMask(OTPGlobals.FloorBitmask)
            node.setIntoCollideMask(0)
            self.rayNP = base.render.attachNewNode(node)
            self.trav.addCollider(self.rayNP, self.queue)
        h = math.radians(heading)
        fwd = Vec3(-math.sin(h), math.cos(h), 0)
        right = Vec3(math.cos(h), math.sin(h), 0)
        # Where the road was last found against the curve: on some tracks
        # the curve runs several feet above or below the road, and a kart
        # sank into the ground when a wheel's ray missed the road there.
        expect = self.roadZ(self.distance) if self.distance is not None and self.track is not None else None
        if expect is None:
            expect = pos[2] + getattr(self, 'lift', 0.0)
        heights = []
        for dx, dy in ((1.5, 2.0), (-1.5, 2.0), (1.5, -2.0), (-1.5, -2.0)):
            at = pos + right * dx + fwd * dy
            heights.append(self.floorZ(base, Point3(at[0], at[1], expect)))
        found = [z for z in heights if z is not None]
        if not found:
            return Point3(pos[0], pos[1], expect), 0.0, 0.0
        z = sum(found) / len(found)
        if abs(z - expect) > 12.0:
            # Something else under it (a bridge over the road): keep on.
            return Point3(pos[0], pos[1], expect), 0.0, 0.0
        rf, lf, rr, lr = [h if h is not None else z for h in heights]
        z = (rf + lf + rr + lr) / 4.0
        self.lift = z - pos[2]
        pitch = math.degrees(math.atan2((rf + lf) / 2 - (rr + lr) / 2, 4.0))
        roll = math.degrees(math.atan2((lf + lr) / 2 - (rf + rr) / 2, 3.0))
        return Point3(pos[0], pos[1], z), pitch, roll

    def roadZ(self, distance):
        point = self.roadPoint(distance)
        return None if point is None else point[0]

    def roadPoint(self, distance):
        """Where the road is this far round: its height, and how far right
        of the curve its middle runs. The curve is only a guide (on the
        rural tracks it is flat, 150 ft under the road, and strays 50 ft
        off it), so the road is followed from the starting grid on, bit by
        bit, each piece near the last one's height and place across: never
        a hillside, the ground under a jump, or another stretch of the
        track passing over or under. Kept for every racer on the track."""
        track = self.track
        if distance < 0:
            return self.startPos[2], self.startSide
        profile = track.__dict__.setdefault('roadPoints', [])
        key = int((distance % track.length) // ROAD_BIN)
        if key < len(profile):
            return profile[key]
        base = getClientBuiltin('base')
        if base is None:
            return None
        if getattr(self, 'rayNP', None) is None:
            self.ground(Point3(0, 0, 0), 0)
            if getattr(self, 'rayNP', None) is None:
                return None
        z, o = profile[-1] if profile else (self.startPos[2], self.startSide)
        slope = track.__dict__.get('roadSlope', 0.0)
        airborne = track.__dict__.get('roadAirborne', 0)

        def isRoad(hit):
            return hit is not None and hit[1] not in OFF_ROAD and hit[2] not in OFF_ROAD_FLOORS

        while len(profile) <= key:
            point, heading, t = track.at(len(profile) * ROAD_BIN + ROAD_BIN / 2.0)
            right = Vec3(math.cos(math.radians(heading)), math.sin(math.radians(heading)), 0)
            expect = z + max(-12.0, min(4.0, slope))
            reach = 40.0 if airborne else 8.0
            found = None
            # Across from where the road was, nearest first: the road's
            # surface at about its height.
            for width in (8, 24):
                best = None
                for x in range(-width, width + 1, 2):
                    at = point + right * (o + x)
                    hit = self.floorHit(base, Point3(at[0], at[1], expect), reach, top=not airborne)
                    if isRoad(hit) and (not airborne or hit[0] >= expect - 40.0):
                        score = abs(x) + abs(hit[0] - expect) * 2
                        if best is None or score < best[0]:
                            best = (score, hit[0], o + x)
                if best is not None:
                    found = best
                    break
            if found is not None:
                # The middle of the road there, so a kart's lane is about it.
                lo = hi = found[2]
                at0 = point + right * found[2]
                while hi - found[2] < ROAD_WIDTH and isRoad(self.floorHit(base, Point3(
                        (at0 + right * (hi + 2 - found[2]))[0], (at0 + right * (hi + 2 - found[2]))[1], found[1]), 6.0)):
                    hi += 2
                while found[2] - lo < ROAD_WIDTH and isRoad(self.floorHit(base, Point3(
                        (at0 + right * (lo - 2 - found[2]))[0], (at0 + right * (lo - 2 - found[2]))[1], found[1]), 6.0)):
                    lo -= 2
                newO = (lo + hi) / 2.0
                # The middle moves smoothly (a fork or a widening doesn't
                # jerk the karts across).
                newO = o + max(-3.0, min(3.0, newO - o))
                slope = 0.0 if airborne else found[1] - z
                z, o = found[1], newO
                airborne = 0
            else:
                # Off a ramp or a cliff: through the air, falling.
                airborne += 1
                slope -= 0.6
                z += max(-12.0, min(4.0, slope))
            if ROAD_DEBUG:
                self.notify.info('road point %d ft round: curve %s, road %s, now z %.1f across %.1f%s' % (
                    len(profile) * ROAD_BIN, tuple(round(v) for v in point), found and round(found[1], 1), z, o,
                    ' (in the air)' if airborne else ''))
            profile.append((z, o))
        track.roadSlope = slope
        track.roadAirborne = airborne
        return profile[key]

    def roadBounds(self, distance, side):
        """The road's edges (as offsets right of the curve) where this
        kart is and a short way ahead of it: the narrowest of them, or
        None where no road is loaded to tell."""
        lo, hi = None, None
        # (Not behind the start line on the first lap: the road there is
        # only traced once the karts get round to it.)
        d = max(distance - ROAD_BIN, 0.0)
        while d <= distance + ROAD_AHEAD:
            edges = self.roadEdges(d, side + self.shift)
            if edges is not None:
                lo = edges[0] if lo is None else max(lo, edges[0])
                hi = edges[1] if hi is None else min(hi, edges[1])
            d += ROAD_BIN
        if lo is None:
            return None
        if lo > hi:
            mid = (lo + hi) / 2.0
            lo = hi = mid
        return lo, hi

    def roadEdges(self, distance, near):
        """Where the road's edges are across the track this far round:
        the stretch of road under the curve's crosswise line that holds
        (or is nearest) the offset near. Worked out once a track piece is
        loaded, and kept for every racer on the track."""
        cache = self.track.__dict__.setdefault('roadEdges', {})
        key = int((distance % self.track.length) // ROAD_BIN)
        if key in cache:
            return cache[key]
        base = getClientBuiltin('base')
        if base is None:
            return None
        if getattr(self, 'rayNP', None) is None:
            self.ground(Point3(0, 0, 0), 0)
            if getattr(self, 'rayNP', None) is None:
                return None
        point, heading, t = self.track.at(key * ROAD_BIN + ROAD_BIN / 2.0)
        roadPoint = self.roadPoint(key * ROAD_BIN + ROAD_BIN / 2.0)
        if roadPoint is None:
            return None
        roadZ, middle = roadPoint
        right = Vec3(math.cos(math.radians(heading)), math.sin(math.radians(heading)), 0)
        point = Point3(point[0], point[1], roadZ) + right * middle
        steps = int(ROAD_WIDTH / ROAD_STEP)
        offsets = [middle + x * ROAD_STEP for x in range(-steps, steps + 1)]
        road, anyHit = [False] * len(offsets), False
        # Out from the middle each way, following the road's height across
        # (the banked turns), so the ground far under a jump or a bridge
        # above isn't taken for it.
        for sign in (1, -1):
            ref = roadZ
            for x in range(0 if sign == 1 else 1, steps + 1):
                at = point + right * (x * ROAD_STEP * sign)
                hit = self.floorHit(base, Point3(at[0], at[1], ref), 6.0)
                if hit is not None:
                    anyHit = True
                    ref = hit[0]
                road[steps + x * sign] = hit is not None and hit[1] not in OFF_ROAD and hit[2] not in OFF_ROAD_FLOORS
        if not anyHit:
            # This stretch isn't loaded (far from the player): ask again later.
            return None
        runs, start = [], None
        for i, ok in enumerate(road + [False]):
            if ok and start is None:
                start = i
            elif not ok and start is not None:
                runs.append((offsets[start] - ROAD_STEP / 2.0, offsets[i - 1] + ROAD_STEP / 2.0))
                start = None
        if not runs:
            edges = None
        else:
            edges = min(runs, key=lambda r: 0 if r[0] <= middle <= r[1] else min(abs(r[0] - middle), abs(r[1] - middle)))
        if ROAD_DEBUG:
            self.notify.info('road edges %d ft round: %s (runs %s; road middle %.1f)' % (
                key * ROAD_BIN, edges, runs, middle))
        cache[key] = edges
        return edges

    def floorHit(self, base, at, reach=12.0, top=False):
        """The road surface under a point: (height, surface kind, floor), the one
        nearest the point's height (or the highest, with top), within reach
        of it. The ground goes on under a ramp, so going up one the ramp is
        the highest."""
        self.rayNP.setPos(base.render, at[0], at[1], at[2] + reach - 2.0)
        self.queue.clearEntries()
        self.trav.traverse(base.render)
        best = None
        for i in range(self.queue.getNumEntries()):
            entry = self.queue.getEntry(i)
            if not entry.hasSurfacePoint():
                continue
            z = entry.getSurfacePoint(base.render)[2]
            if abs(z - at[2]) > reach:
                continue
            if best is None or (z > best[0] if top else abs(z - at[2]) < abs(best[0] - at[2])):
                into = entry.getIntoNodePath()
                best = (z, into.getNetTag('surface'), into.getName())
        return best

    def floorZ(self, base, at):
        # The road nearest the curve's height there (not a bridge above).
        self.rayNP.setPos(base.render, at[0], at[1], at[2] + 12.0)
        self.queue.clearEntries()
        self.trav.traverse(base.render)
        best = None
        for i in range(self.queue.getNumEntries()):
            entry = self.queue.getEntry(i)
            if not entry.hasSurfacePoint():
                continue
            z = entry.getSurfacePoint(base.render)[2]
            if abs(z - at[2]) <= 12.0 and (best is None or z > best):
                best = z
        return best

    def speed(self, now):
        race = self.race
        speed = race.lapCount * self.track.length / self.raceTime
        # Up to speed over the first few seconds off the grid.
        speed *= min(max((now - race.startTime) / 3.0, 0.1), 1.0)
        # Nobody drives at one speed the whole way.
        speed *= 1 + 0.08 * math.sin(now * 0.4 + self.wobble)
        speed *= self.pack(speed)
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

    def pack(self, speed):
        # Racers react to the players around them, a little: one far ahead
        # of every player eases off, one far behind pushes harder. It stays
        # a race (a slow driver still loses, a fast one can still win):
        # never quicker than the track record's pace, never slower than the
        # pace to qualify, and no more than 12% either way.
        race = self.race
        players = [p for a, p in race.avatarProgress.items() if a != self.npc.doId and not isNPC(self.air.doId2do.get(a))]
        if not players or self.distance is None or self.distance <= 0:
            return 1.0
        lead = self.distance / self.track.length - max(players)
        factor = 1.0
        if lead > 0.15:
            factor = 1.0 - min(0.12, (lead - 0.15) * 0.25)
        elif lead < -0.15:
            factor = 1.0 + min(0.12, (-lead - 0.15) * 0.25)
        record, qualify = RaceGlobals.TrackDict[race.trackId][2], RaceGlobals.TrackDict[race.trackId][1]
        fastest = race.lapCount * self.track.length / record
        slowest = race.lapCount * self.track.length / qualify
        return min(max(speed * factor, slowest), max(speed, fastest)) / speed if speed > 0 else 1.0

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
        if getattr(self, 'rayNP', None) is not None:
            self.rayNP.removeNode()
            self.rayNP = None
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
