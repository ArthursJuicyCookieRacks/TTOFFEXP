"""Finding its own way through a place, for an NPC player.

Inside a factory, a mint, a DA office, a cog building or a golf course the
NPC toons go about on their own, the way players do: each works out its own
route over the floors of the place, around the walls, up and down stairs and
ramps, off ledges and over the gaps a toon can jump, rather than walking in
the player's footsteps or teleporting when it falls behind.

The district knows nothing of the geometry, so the map is made from the
client's scene (the offline game runs both in one process): every floor and
wall a toon collides with, including the rooms a factory has put away out of
the player's sight. The floors are laid on a grid of CELL squares, a few
floors deep where floors overlap; the walls are kept as they are and a step
from one square to the next is allowed when no wall is in the way. The map is
made a little at a time (BUILD_BUDGET) and kept for the place, and each
search does a little work each tick (BUDGET), so the game never stutters.

Moving platforms (paint mixers, lifts) are not on the map: where the only way
on is a moving floor, the toon goes the way the floors carry toons across
(NPCFacilities.trailWalk) instead.
"""

import heapq
import math
import time

from panda3d.core import Point3, Vec3, CollisionNode, CollisionPolygon, CollisionCapsule, CollisionSphere

from otp.local.ExecutionContext import getClientBuiltin
from toontown.toonbase import ToontownGlobals

CELL = 2.5
# Wall pieces are filed in buckets this big for quick lookups.
BUCKET = 8.0
STEP_UP = 2.6
STEP_DOWN = 4.0
# A toon walks off a ledge this high and lands unhurt.
DROP_MAX = 16.0
# A running jump: this many cells (flat) and up to this much higher.
JUMP_CELLS = (1, 2, 3, 4, 5, 6)
# A toon's jump (OTPGlobals.ToonJumpForce 24, gravity 64.3) tops out 4.47;
# with its wall sphere it lands on a ledge up to about 4.6 (GravityWalker run
# headless against boxes of each height)
# up: a box or ledge up to this high is jumped onto.
JUMP_UP = 4.55
# Up onto a box: the jump takes the feet (and the wall sphere's bottom) this
# high, over a side that ends below it; the box top may stand a little
# higher still (the floor ray lifts the toon onto it): up to CLIMB_UP.
CLIMB_WALL = 4.5
CLIMB_UP = 6.0
# A running jump across a gap may land well below: the boiler room's crate
# stack is 8.2 above the catwalk players jump over to.
JUMP_DOWN = 12.0
JUMP_COST = 6.0
DROP_COST = 2.0
# Squares near where the player has walked cost this much less: where the
# way splits (the two sides of the factory) the toons go the player's way.
PLAYER_WAY = 0.35
PLAYER_WAY_REACH = 2
# A floor closer than this over a spot leaves no room to stand.
HEADROOM = 4.5
CHEST = 1.6
TOON_RADIUS = 0.9
# How much work a tick may do (seconds) over all searches, and for making a
# map.
BUDGET = 0.006
BUILD_BUDGET = 0.012
# A search gives up after visiting this many squares.
MAX_VISITS = 40000
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))

WALK = 'walk'
DROP = 'drop'
JUMP = 'jump'
# Getting on a moving platform (or a lift) at one of its stops, and riding
# it to its other stop.
BOARD = 'board'
RIDE = 'ride'
# A platform this close to a stop is there (they wait at each end).
AT_STOP = 0.35
BOARD_REACH = 3
RIDE_COST = 18.0
# The player's own steps joined into links: samples this close together
# (in trail samples, and in distance; further apart the player rode or
# teleported).
TRAIL_LINK_SAMPLES = 12
# How much a toon's own taste in squares changes their cost (0..TASTE).
TASTE = 0.35
TRAIL_LINK_REACH = 14.0

FLOOR = ToontownGlobals.FloorBitmask.getWord()
WALL = ToontownGlobals.WallBitmask.getWord()


def cellOf(x, y):
    return (int(math.floor(x / CELL + 0.5)), int(math.floor(y / CELL + 0.5)))


def isMoving(np):
    node = np
    for i in range(3):
        if node.isEmpty():
            break
        if node.getName().startswith('MovingPlatform'):
            return True
        node = node.getParent()
    return False


def newellNormal(points):
    nx = ny = nz = 0.0
    n = len(points)
    for k in range(n):
        a = points[k]
        b = points[(k + 1) % n]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    normal = Vec3(nx, ny, nz)
    if normal.length() < 1e-6:
        return None
    normal.normalize()
    return normal


DOOR_LEAVES = ('doorLeft', 'doorRight', 'doorTop', 'doorBottom')


def isStomperHead(np):
    while not np.isEmpty():
        # The head and the shaft above it move up and down: where they
        # happen to be when the grid is made is no wall.
        if np.getName() in ('head_collisions', 'shaft_collisions'):
            return True
        np = np.getParent()
    return False


def isDoorLeaf(np):
    if np.getName().endswith('innerCollision'):
        return True
    node = np
    for i in range(6):
        if node.isEmpty():
            return False
        if node.getName() in DOOR_LEAVES:
            return True
        node = node.getParent()
    return False


def under(np, roots):
    node = np
    for i in range(8):
        if node.isEmpty():
            return False
        if node in roots:
            return True
        node = node.getParent()
    return False


class Stop:
    """One end of a moving platform's (or a lift's) run."""

    def __init__(self, mover, index, local):
        self.mover = mover
        self.index = index
        # Where the moving node is (in its parent) when it is at this stop.
        self.local = Point3(local)
        self.cells = set()
        self.z = 0.0
        self.node = None
        self.other = None
        self.exits = None

    def worldOf(self, point):
        """Where a point of the platform (in the moving node's space) is
        when the platform is at this stop."""
        render = getClientBuiltin('base').render
        return self.mover.moving.getParent().getMat(render).xformPoint(self.local + Vec3(point))

    def present(self):
        mover = self.mover
        if isinstance(mover, GhostLift):
            mover.update()
            return not mover.isMovingNow() and mover.lift.state == self.index
        moving = mover.moving
        if moving.isEmpty():
            return False
        return (moving.getPos() - self.local).length() < AT_STOP

    def center(self):
        """Where the middle of the platform's floor is now."""
        render = getClientBuiltin('base').render
        if isinstance(self.mover, GhostLift):
            self.mover.update()
        return self.mover.moving.getMat(render).xformPoint(self.mover.centerLocal)


class Mover:

    def __init__(self, entity, moving, stops, liftDoId=None):
        self.entity = entity
        self.moving = moving
        self.base = moving
        self.liftDoId = liftDoId
        self.centerLocal = Point3(0, 0, 0)
        self.stops = [Stop(self, i, local) for i, local in enumerate(stops)]
        self.stops[0].other = self.stops[1]
        self.stops[1].other = self.stops[0]


def findMovers(levels):
    """The moving platforms and lifts of the levels (factories, mints,
    offices), and the gears (which turn in place: just floor)."""
    movers = []
    gears = []
    for level in levels:
        for ent in list(getattr(level, 'entities', {}).values()):
            name = ent.__class__.__name__
            if name == 'GearEntity':
                gears.append(ent)
                continue
            moving = getattr(ent, 'platform', None)
            if moving is None or not hasattr(moving, 'isEmpty') or moving.isEmpty():
                continue
            if name == 'DistributedLift':
                if hasattr(ent, 'startPos') and hasattr(ent, 'endPos'):
                    movers.append(Mover(ent, moving, (ent.startPos, ent.endPos), ent.doId))
            elif hasattr(ent, 'offset') and hasattr(ent, 'period'):
                if Vec3(ent.offset).length() > 0.5:
                    movers.append(Mover(ent, moving, (Point3(0, 0, 0), Point3(ent.offset))))
    # The lifts are objects of their own (not in the level's entities), and
    # the client only has the ones near the player: they are taken from the
    # district (aiLiftSource), with a copy of each lift's floor (stashed,
    # touched by nothing) kept where the district says the lift is.
    if not levels or aiLiftSource is None:
        return movers, gears
    byId = dict((getattr(level, 'doId', None), level) for level in levels)
    for lift in aiLiftSource():
        level = byId.get(getattr(lift, 'levelDoId', None))
        if level is None:
            continue
        try:
            ghost = GhostLift(level, lift)
        except Exception:
            import traceback
            traceback.print_exc()
            continue
        if ghost.moving is not None:
            movers.append(ghost)
    return movers, gears


# Set by the district: a function giving its lifts (DistributedLiftAI).
aiLiftSource = None


class GhostLift(Mover):
    """A lift, as the district runs it. Its floor is a stashed copy of the
    lift's model, moved to where the lift is now each time it is asked."""

    def __init__(self, level, lift):
        self.lift = lift
        self.moving = None
        zoneNode = level.getZoneNode(lift.parentEntId) if hasattr(level, 'getZoneNode') else None
        if zoneNode is None or zoneNode.isEmpty():
            return
        model = getClientBuiltin('base').loader.loadModel(lift.modelPath)
        if model is None or model.isEmpty():
            return
        self.holder = zoneNode.attachNewNode('npcGhostLift-%s' % lift.entId)
        self.holder.setPos(lift.pos)
        self.holder.setHpr(lift.hpr)
        self.holder.setScale(getattr(lift, 'scale', 1) or 1)
        moving = self.holder.attachNewNode('platParent')
        copy = model.copyTo(moving)
        copy.setScale(lift.modelScale)
        # Only its floor counts; nothing collides with the copy.
        keep = set()
        for floor in copy.findAllMatches('**/%s' % lift.floorName):
            for np in floor.findAllMatches('**/+CollisionNode;+s'):
                keep.add(np.node())
            if isinstance(floor.node(), CollisionNode):
                keep.add(floor.node())
        for np in copy.findAllMatches('**/+CollisionNode;+s'):
            if np.node() not in keep:
                np.removeNode()
        copy.findAllMatches('**/+GeomNode').detach()
        self.holder.stash()
        Mover.__init__(self, lift, moving, (Point3(lift.startPos), Point3(lift.endPos)), lift.doId)
        self.update()

    def update(self):
        """Puts the copy where the lift is now."""
        lift = self.lift
        if self.moving is None or self.moving.isEmpty():
            return
        try:
            from direct.distributed.ClockDelta import globalClockDelta
            now = globalClock.getFrameTime()
            arrive = globalClockDelta.networkToLocalTime(lift.stateTimestamp, now, bits=32)
        except Exception:
            arrive = 0
            now = 1
        to = self.stops[lift.state].local
        frm = self.stops[lift.fromState].local
        duration = max(0.1, float(getattr(lift, 'duration', 7.0)))
        if now >= arrive:
            self.moving.setPos(to)
            return
        t = 1.0 - (arrive - now) / duration
        t = max(0.0, min(1.0, t))
        # (easeInOut, as the client lerps it)
        t = t * t * (3 - 2 * t)
        self.moving.setPos(frm + (to - frm) * t)

    def isMovingNow(self):
        state = self.lift.fsm.getCurrentState() if hasattr(self.lift, 'fsm') else None
        return state is not None and state.getName() == 'moving'


class Wall:
    __slots__ = ('kind', 'points', 'normal', 'd', 'lo', 'hi', 'a', 'b', 'radius', 'name')

    def __init__(self, kind):
        self.kind = kind


class Grid:
    """The map of one place: the floors in each square and the walls."""

    def __init__(self, nodePaths, levels=()):
        # (ix, iy) -> sorted list of floor heights.
        self.floors = {}
        # (bx, by) -> walls whose footprint reaches that bucket.
        self.walls = {}
        self.ready = False
        self.links = {}
        self.movers, gears = findMovers(levels)
        self.moverRoots = [m.moving for m in self.movers]
        self.gearRoots = [g for g in gears if hasattr(g, 'isEmpty') and not g.isEmpty()]
        self.stops = {}
        self.stopAdj = {}
        self.work = self.build(nodePaths)

    def step(self, deadline):
        if self.ready:
            return True
        try:
            while time.perf_counter() < deadline:
                next(self.work)
        except StopIteration:
            self.ready = True
            self.finishFloors()
        return self.ready

    def build(self, nodePaths):
        base = getClientBuiltin('base')
        render = base.render
        count = 0
        for root in nodePaths:
            if root.isEmpty():
                continue
            for np in root.findAllMatches('**/+CollisionNode;+s'):
                node = np.node()
                mask = node.getIntoCollideMask().getWord()
                if not mask & (FLOOR | WALL):
                    continue
                if not np.findNetTag('avatarDoId').isEmpty() or not np.findNetPythonTag('avatar').isEmpty():
                    continue
                if self.moverRoots and under(np, self.moverRoots):
                    continue
                if np.getName().startswith('goonColl'):
                    # A goon walks its beat: no wall on the map.
                    continue
                if isStomperHead(np):
                    # A stomper's head goes up and down: the way under it
                    # is walked while it is up (NPCParty.nextLeg waits).
                    continue
                if isDoorLeaf(np):
                    # A facility door slides open as toons come up to it:
                    # its leaves are no wall on the map.
                    continue
                # (Other moving floors - gears turning in place, conveyor
                # treads, a room's own turning floor - stay where they are
                # and carry a toon standing on them: floor like any other.)
                mat = np.getMat(render)
                self.curName = '/'.join(str(np).split('/')[-4:])
                # A mirrored node turns its polygons' winding around.
                flipped = mat.getUpper3().determinant() < 0
                for i in range(node.getNumSolids()):
                    solid = node.getSolid(i)
                    if not solid.isTangible():
                        continue
                    if isinstance(solid, CollisionPolygon):
                        points = [mat.xformPoint(solid.getPoint(j)) for j in range(solid.getNumPoints())]
                        if len(points) < 3:
                            continue
                        # Newell's normal: polygons with three points in a
                        # row (doorway floors) have no normal from their
                        # first three points.
                        normal = newellNormal(points)
                        if normal is None:
                            continue
                        facing = -normal if flipped else normal
                        # (A floor faces up: one facing down is the
                        # underside of something, stood on by nobody.)
                        if mask & FLOOR and facing[2] > 0.35:
                            self.addFloor(points, normal)
                        elif mask & WALL:
                            self.addWallPolygon(points, normal)
                    elif mask & WALL and isinstance(solid, CollisionCapsule):
                        self.addCapsule(mat.xformPoint(solid.getPointA()), mat.xformPoint(solid.getPointB()),
                                        solid.getRadius() * mat.getRow3(0).length())
                    elif mask & WALL and isinstance(solid, CollisionSphere):
                        c = mat.xformPoint(solid.getCenter())
                        r = solid.getRadius() * mat.getRow3(0).length()
                        self.addCapsule(c - Vec3(0, 0, r * 0.5), c + Vec3(0, 0, r * 0.5), r)
                    count += 1
                    if count % 25 == 0:
                        yield

    # --- Floors ---

    def addFloor(self, points, normal):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x0, y0 = cellOf(min(xs), min(ys))
        x1, y1 = cellOf(max(xs), max(ys))
        d = normal.dot(Vec3(points[0]))
        n = len(points)
        sign = 1 if normal[2] > 0 else -1
        for ix in range(x0, x1 + 1):
            x = ix * CELL
            for iy in range(y0, y1 + 1):
                y = iy * CELL
                inside = True
                for k in range(n):
                    a = points[k]
                    b = points[(k + 1) % n]
                    if ((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) * sign < -1e-6:
                        inside = False
                        break
                if not inside:
                    continue
                z = (d - normal[0] * x - normal[1] * y) / normal[2]
                self.floors.setdefault((ix, iy), []).append(z)

    def addStops(self):
        """The floors of each moving platform at its two stops."""
        render = getClientBuiltin('base').render
        for mover in self.movers:
            pts = []
            for np in mover.moving.findAllMatches('**/+CollisionNode;+s'):
                node = np.node()
                if not node.getIntoCollideMask().getWord() & FLOOR:
                    continue
                mat = np.getMat(mover.moving)
                for i in range(node.getNumSolids()):
                    solid = node.getSolid(i)
                    if isinstance(solid, CollisionPolygon):
                        pts.append([mat.xformPoint(solid.getPoint(j)) for j in range(solid.getNumPoints())])
            if not pts:
                continue
            allPts = [p for poly in pts for p in poly]
            mover.centerLocal = Point3(sum(p[0] for p in allPts) / len(allPts), sum(p[1] for p in allPts) / len(allPts),
                                       max(p[2] for p in allPts))
            parentMat = mover.moving.getParent().getMat(render)
            for stop in mover.stops:
                world = parentMat.xformPoint(stop.local + Vec3(mover.centerLocal))
                stop.z = world[2]
                for poly in pts:
                    wpoly = [parentMat.xformPoint(stop.local + Vec3(p)) for p in poly]
                    xs = [p[0] for p in wpoly]
                    ys = [p[1] for p in wpoly]
                    x0, y0 = cellOf(min(xs), min(ys))
                    x1, y1 = cellOf(max(xs), max(ys))
                    for ix in range(x0, x1 + 1):
                        for iy in range(y0, y1 + 1):
                            stop.cells.add((ix, iy))
                cx, cy = cellOf(world[0], world[1])
                stop.node = (cx, cy, stop.z, 'stop%d-%d' % (id(mover), stop.index))
                self.stops[stop.node] = stop
                for (ix, iy) in stop.cells:
                    for dx in range(-BOARD_REACH, BOARD_REACH + 1):
                        for dy in range(-BOARD_REACH, BOARD_REACH + 1):
                            c = (ix + dx, iy + dy)
                            if c not in stop.cells:
                                lst = self.stopAdj.setdefault(c, [])
                                if stop not in lst:
                                    lst.append(stop)

    def finishFloors(self):
        try:
            self.addStops()
        except Exception:
            import traceback
            traceback.print_exc()
        for key, heights in self.floors.items():
            heights.sort()
            merged = []
            for z in heights:
                if merged and z - merged[-1] < 0.6:
                    merged[-1] = z
                else:
                    merged.append(z)
            # No room to stand under a floor just overhead (under stairs).
            self.floors[key] = [z for i, z in enumerate(merged)
                                if i + 1 >= len(merged) or merged[i + 1] - z > HEADROOM]

    def heightNear(self, ix, iy, z, up=STEP_UP, down=STEP_DOWN):
        best = None
        for h in self.floors.get((ix, iy), ()):
            if z - down <= h <= z + up and (best is None or abs(h - z) < abs(best - z)):
                best = h
        return best

    # --- Walls ---

    def file(self, wall, xs, ys):
        bx0 = int(math.floor((min(xs) - TOON_RADIUS) / BUCKET))
        bx1 = int(math.floor((max(xs) + TOON_RADIUS) / BUCKET))
        by0 = int(math.floor((min(ys) - TOON_RADIUS) / BUCKET))
        by1 = int(math.floor((max(ys) + TOON_RADIUS) / BUCKET))
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                self.walls.setdefault((bx, by), []).append(wall)

    def addWallPolygon(self, points, normal):
        wall = Wall('poly')
        wall.name = getattr(self, 'curName', '')
        wall.points = points
        wall.normal = normal
        wall.d = normal.dot(Vec3(points[0]))
        wall.lo = min(p[2] for p in points)
        wall.hi = max(p[2] for p in points)
        self.file(wall, [p[0] for p in points], [p[1] for p in points])

    def addCapsule(self, a, b, radius):
        wall = Wall('capsule')
        wall.name = getattr(self, 'curName', '')
        wall.a = Point3(a)
        wall.b = Point3(b)
        wall.radius = radius
        wall.lo = min(a[2], b[2]) - radius
        wall.hi = max(a[2], b[2]) + radius
        self.file(wall, [a[0], b[0]], [a[1], b[1]])

    def blocked(self, p, q):
        """Whether a wall stands between p and q (points at chest height)."""
        lo = min(p[2], q[2]) - 0.5
        hi = max(p[2], q[2]) + 0.5
        seen = set()
        bx0 = int(math.floor(min(p[0], q[0]) / BUCKET))
        bx1 = int(math.floor(max(p[0], q[0]) / BUCKET))
        by0 = int(math.floor(min(p[1], q[1]) / BUCKET))
        by1 = int(math.floor(max(p[1], q[1]) / BUCKET))
        for bx in range(bx0, bx1 + 1):
            for by in range(by0, by1 + 1):
                for wall in self.walls.get((bx, by), ()):
                    if id(wall) in seen or wall.hi < lo or wall.lo > hi:
                        continue
                    seen.add(id(wall))
                    if wall.kind == 'poly':
                        if self.crossesPolygon(wall, p, q):
                            return True
                    elif self.nearCapsule(wall, p, q):
                        return True
        return False

    def blockers(self, p, q):
        """The walls between p and q (for finding why there is no way)."""
        out = []
        for wall in set(w for ws in self.walls.values() for w in ws):
            if wall.hi < min(p[2], q[2]) - 0.5 or wall.lo > max(p[2], q[2]) + 0.5:
                continue
            if (wall.kind == 'poly' and self.crossesPolygon(wall, p, q)) or \
                    (wall.kind != 'poly' and self.nearCapsule(wall, p, q)):
                out.append(wall.name)
        return out

    def crossesPolygon(self, wall, p, q):
        n = wall.normal
        dp = n[0] * p[0] + n[1] * p[1] + n[2] * p[2] - wall.d
        dq = n[0] * q[0] + n[1] * q[1] + n[2] * q[2] - wall.d
        if dp * dq > 0:
            return False
        if dp == dq:
            return False
        t = dp / (dp - dq)
        x = Point3(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, p[2] + (q[2] - p[2]) * t)
        pts = wall.points
        m = len(pts)
        sign = 0
        for k in range(m):
            a = pts[k]
            b = pts[(k + 1) % m]
            c = (b - a).cross(x - a).dot(n)
            if abs(c) < 1e-6:
                continue
            s = 1 if c > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
        return True

    def nearCapsule(self, wall, p, q):
        # Flat distance from the step to the capsule's axis.
        a, b = wall.a, wall.b
        mid = (a + b) * 0.5
        d = segmentPointDistance2D(p, q, mid)
        return d < wall.radius + TOON_RADIUS * 0.5

    # --- Moves ---

    def linksFrom(self, node):
        known = self.links.get(node)
        if known is not None:
            return known
        if len(node) == 4:
            return self.stopLinks(node)
        ix, iy, z = node
        out = []
        for stop in self.stopAdj.get((ix, iy), ()):
            # (Down onto it, or a jump up onto it.)
            if -(STEP_DOWN + 2.0) <= stop.z - z <= JUMP_UP:
                out.append((stop.node, BOARD, CELL * 2 + 2.0))
        here = Point3(ix * CELL, iy * CELL, z + CHEST)
        gaps = []
        climbs = []
        for dx, dy in DIRS:
            nx, ny = ix + dx, iy + dy
            h = self.heightNear(nx, ny, z)
            length = CELL * math.hypot(dx, dy)
            if h is not None:
                if not self.blocked(here, Point3(nx * CELL, ny * CELL, h + CHEST)):
                    out.append(((nx, ny, h), WALK, length))
                else:
                    # Something stands on the floor there (a crate, a
                    # gear): a toon jumps up onto it.
                    climbs.append((dx, dy))
                continue
            low = self.heightNear(nx, ny, z, up=0, down=DROP_MAX)
            if low is not None and not self.blocked(here, Point3(nx * CELL, ny * CELL, z + CHEST)):
                out.append(((nx, ny, low), DROP, length + DROP_COST))
            gaps.append((dx, dy))
        for dx, dy in gaps:
            for k in JUMP_CELLS:
                lx, ly = ix + dx * k, iy + dy * k
                h = self.heightNear(lx, ly, z, up=JUMP_UP, down=JUMP_DOWN)
                if h is None:
                    continue
                top = max(z, h) + CHEST + 1.0
                if self.blocked(Point3(here[0], here[1], top), Point3(lx * CELL, ly * CELL, top)):
                    break
                out.append(((lx, ly, h), JUMP, CELL * k * math.hypot(dx, dy) + JUMP_COST))
                if h >= z - STEP_DOWN:
                    break
                # Landing well below: a farther ledge nearer this height
                # may be the one to make for.
        for dx, dy in climbs + gaps:
            # (Up to three squares off: a running jump's top comes about
            # seven along, as off a pushed crate to the crate wall.)
            for k in (1, 2, 3):
                lx, ly = ix + dx * k, iy + dy * k
                ups = [f for f in self.floors.get((lx, ly), ()) if STEP_UP < f - z <= CLIMB_UP]
                if not ups:
                    continue
                h = max(ups)
                # The toon's feet clear the side at the top of the jump,
                # and it lands on the top above it.
                clear = z + CLIMB_WALL
                top = h + CHEST + 1.0
                there = Point3(lx * CELL, ly * CELL, clear)
                if not self.blocked(Point3(here[0], here[1], clear), there) and \
                        not self.blocked(Point3(here[0], here[1], top), Point3(there[0], there[1], top)):
                    out.append(((lx, ly, h), JUMP, CELL * k * math.hypot(dx, dy) + JUMP_COST))
                break
        self.links[node] = out
        return out

    def stopLinks(self, node):
        stop = self.stops[node]
        out = [(stop.other.node, RIDE, RIDE_COST + (stop.other.z - stop.z) * 0.1)]
        seen = set()
        hops = set()
        for (ix, iy) in stop.cells:
            for dx in range(-BOARD_REACH, BOARD_REACH + 1):
                for dy in range(-BOARD_REACH, BOARD_REACH + 1):
                    c = (ix + dx, iy + dy)
                    if c in stop.cells or c in seen:
                        continue
                    seen.add(c)
                    h = self.heightNear(c[0], c[1], stop.z, up=JUMP_UP, down=STEP_DOWN + 2.0)
                    if h is not None:
                        # Off the edge: a step, or a running jump over the gap.
                        far = min(max(abs(c[0] - x), abs(c[1] - y)) for (x, y) in stop.cells) > 1
                        out.append(((c[0], c[1], h), JUMP if far else WALK, CELL * 2 + 2.0))
                    # Over to the next platform when it waits beside this
                    # one (the paint mixers take toons across in turn).
                    for other in self.stopAdj.get(c, ()):
                        if other.mover is not stop.mover and other.node not in hops and \
                                -(STEP_DOWN + 2.0) <= other.z - stop.z <= JUMP_UP:
                            hops.add(other.node)
                            out.append((other.node, BOARD, CELL * 2 + 2.0))
        self.links[node] = out
        return out

    def stopAt(self, point):
        cell = cellOf(point[0], point[1])
        for stop in self.stops.values():
            if cell in stop.cells and abs(point[2] - stop.z) < 1.5 and stop.present():
                return stop.node
        return None

    def nodeAt(self, point, up=STEP_UP, down=6.0):
        ix, iy = cellOf(point[0], point[1])
        h = self.heightNear(ix, iy, point[2], up, down)
        if h is not None:
            return (ix, iy, h)
        # The nearest square with floor around it.
        for r in (1, 2):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    h = self.heightNear(ix + dx, iy + dy, point[2], up, down)
                    if h is not None:
                        return (ix + dx, iy + dy, h)
        return None


def segmentPointDistance2D(p, q, c):
    vx, vy = q[0] - p[0], q[1] - p[1]
    wx, wy = c[0] - p[0], c[1] - p[1]
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / l2))
    dx, dy = p[0] + vx * t - c[0], p[1] + vy * t - c[1]
    return math.hypot(dx, dy)


class Search:
    """One A* search, done a little at a time."""

    def __init__(self, grid, start, goal, playerWay=None):
        self.grid = grid
        # The squares the player went over (see NPCFacilities trails).
        self.playerWay = set()
        # The player's steps, as links of their own (playerWay is the
        # player's trail: (point, inTheAir) pairs, oldest first): where the
        # floors alone show no way on (a gear to hop across, a crate pushed
        # up to a ledge, a door the map has shut) the toon does what the
        # player did there.
        self.trailWay = playerWay or ()
        self.trailLinks = None
        for item in playerWay or ():
            point = item[0] if isinstance(item, tuple) else item
            ix, iy = cellOf(point[0], point[1])
            for dx in range(-PLAYER_WAY_REACH, PLAYER_WAY_REACH + 1):
                for dy in range(-PLAYER_WAY_REACH, PLAYER_WAY_REACH + 1):
                    self.playerWay.add((ix + dx, iy + dy))
        self.start = Point3(start)
        self.goalPoint = Point3(goal)
        self.done = False
        self.path = None
        self.visits = 0
        self.began = False
        self.open = []
        self.why = ''
        self.taste = 0

    def begin(self):
        self.began = True
        grid = self.grid
        sNode = grid.nodeAt(self.start)
        if sNode is None:
            # Standing on a moving platform that waits at a stop.
            sNode = grid.stopAt(self.start)
        gNode = grid.nodeAt(self.goalPoint, up=4.0, down=8.0)
        if sNode is None or gNode is None:
            self.done = True
            self.why = 'no floor at the %s' % ('start' if sNode is None else 'goal')
            return
        self.goal = gNode
        self.trailLinks = self.makeTrailLinks()
        self.came = {sNode: None}
        self.cost = {sNode: 0.0}
        self.open = [(self.h(sNode), 0, sNode)]
        self.counter = 1

    def makeTrailLinks(self):
        grid = self.grid
        links = {}
        prev = None
        airborne = False
        for i, item in enumerate(self.trailWay):
            point, air = item if isinstance(item, tuple) else (item, False)
            if air:
                airborne = True
                continue
            node = grid.nodeAt(point, up=1.0, down=1.5)
            if node is None:
                prev = None
                airborne = False
                continue
            if prev is not None and node != prev[0] and i - prev[1] <= TRAIL_LINK_SAMPLES and \
                    (Point3(point) - prev[2]).length() <= TRAIL_LINK_REACH:
                a, b = prev[0], node
                known = [n for n, k, c in grid.linksFrom(a)]
                if b not in known:
                    length = (Point3(point) - prev[2]).length()
                    kind = JUMP if airborne or b[2] - a[2] > STEP_UP else WALK
                    links.setdefault(a, []).append((b, kind, length))
                    if kind == WALK and abs(b[2] - a[2]) <= STEP_UP:
                        links.setdefault(b, []).append((a, WALK, length))
            prev = (node, i, Point3(point))
            airborne = False
        return links

    def h(self, node):
        g = self.goal
        d = math.hypot((node[0] - g[0]) * CELL, (node[1] - g[1]) * CELL) + abs(node[2] - g[2]) * 0.5
        # (Still a lower bound when the cheap squares lead there.)
        return d * PLAYER_WAY if self.playerWay else d

    def work(self, deadline):
        if not self.grid.step(deadline):
            return
        if not self.began:
            self.begin()
        g = self.goal if not self.done else None
        while self.open and not self.done:
            if time.perf_counter() > deadline:
                return
            f, n, node = heapq.heappop(self.open)
            if node[0] == g[0] and node[1] == g[1] and abs(node[2] - g[2]) < 1.0:
                self.finish(node)
                return
            self.visits += 1
            if self.visits > MAX_VISITS:
                break
            base = self.cost[node]
            way = self.playerWay
            extra = self.trailLinks.get(node, ()) if self.trailLinks else ()
            for nNode, kind, step in list(self.grid.linksFrom(node)) + list(extra):
                if way and (nNode[0], nNode[1]) in way:
                    step *= PLAYER_WAY
                if self.taste:
                    # A toon's own liking for some squares over others, so
                    # toons going the same way take different lines.
                    step *= 1.0 + TASTE * ((((nNode[0] // 4) * 73856093) ^ ((nNode[1] // 4) * 19349663) ^ self.taste) % 1000) / 1000.0
                c = base + step
                if c < self.cost.get(nNode, 1e18):
                    self.cost[nNode] = c
                    self.came[nNode] = (node, kind)
                    self.counter += 1
                    heapq.heappush(self.open, (c + self.h(nNode), self.counter, nNode))
        if not self.done:
            self.done = True
            self.path = None
            self.why = 'no way (%d squares tried)' % self.visits

    def finish(self, node):
        steps = []
        while self.came.get(node) is not None:
            prev, kind = self.came[node]
            if len(node) == 4:
                steps.append((kind, self.grid.stops[node]))
            else:
                steps.append((kind, Point3(node[0] * CELL, node[1] * CELL, node[2])))
            node = prev
        steps.reverse()
        self.path = steps
        self.done = True


class NPCPathfinder:
    """The searches of every NPC, and the map of each place."""

    def __init__(self):
        self.grids = {}
        self.searches = {}
        self.stats = {}

    def sceneRoots(self):
        """What the map is made of: the client's scene, and the rooms a
        factory or mint has put away for now."""
        base = getClientBuiltin('base')
        if base is None or not hasattr(base, 'render'):
            return None, None
        roots = [base.render]
        levels = []
        for obj in list(base.cr.doId2do.values()):
            geom = getattr(obj, 'geom', None)
            if getattr(obj, 'zoneNum2node', None) and geom is not None and not geom.isEmpty():
                # (Its put-away rooms are in the scene, stashed: the map
                # takes stashed nodes too.)
                levels.append(obj.doId)
        place = None
        try:
            place = base.cr.playGame.getPlace()
        except Exception:
            pass
        self.levels = [base.cr.doId2do[doId] for doId in levels]
        return roots, (id(place), tuple(sorted(levels)), self.movedCrates(base))

    def movedCrates(self, base):
        """The crates players have pushed off their first places (a crate
        pushed against the crate wall is the step up over it): the map is
        drawn again with them where they are now."""
        firsts = self.__dict__.setdefault('crateFirsts', {})
        moved = []
        for obj in list(base.cr.doId2do.values()):
            if obj.__class__.__name__ != 'DistributedCrate' or obj.isEmpty():
                continue
            pos = obj.getPos(base.render)
            spot = (int(round(pos[0] / 2.0)), int(round(pos[1] / 2.0)))
            first = firsts.setdefault(obj.doId, spot)
            if spot != first:
                moved.append((obj.doId,) + spot)
        return tuple(sorted(moved))

    def gridFor(self):
        roots, key = self.sceneRoots()
        if roots is None:
            return None
        grid = self.grids.get(key)
        if grid is None:
            for old in self.grids.values():
                for mover in old.movers:
                    holder = getattr(mover, 'holder', None)
                    if holder is not None and not holder.isEmpty():
                        holder.removeNode()
            self.grids.clear()
            grid = self.grids[key] = Grid(roots, self.levels)
        return grid

    def request(self, npc, goal, playerWay=None):
        """Starts (or restarts) a search for npc's way to goal, keeping to
        the player's way (points) where it can."""
        grid = self.gridFor()
        if grid is None:
            return None
        search = Search(grid, npc.getPos(), goal, playerWay)
        self.searches[npc.doId] = search
        return search

    def result(self, npc):
        search = self.searches.get(npc.doId)
        if search is None or not search.done:
            return None
        del self.searches[npc.doId]
        return search

    def pending(self, npc):
        search = self.searches.get(npc.doId)
        return search is not None and not search.done

    def cancel(self, npc):
        self.searches.pop(npc.doId, None)

    def tick(self):
        start = time.perf_counter()
        deadline = start + BUDGET
        for search in list(self.searches.values()):
            if time.perf_counter() > deadline:
                break
            if not search.done:
                search.work(start + (BUILD_BUDGET if not search.grid.ready else BUDGET))

    # --- Making a route the toon can follow ---

    def legs(self, start, steps, grid=None):
        """The path as legs: ('walk', [points]) runs, ('jump', landing) and
        ('drop', [points]). Straight stretches are joined into one run."""
        legs = []
        run = []
        pos = Point3(start)
        for kind, point in steps:
            if kind == WALK:
                run.append(point)
                continue
            if run:
                legs.append((WALK, self.smooth(pos, run, grid)))
                pos = run[-1]
                run = []
            if kind in (BOARD, RIDE):
                # point is the Stop to get on at, or to ride to.
                legs.append((kind, point))
                pos = point.worldOf(point.mover.centerLocal)
                continue
            if kind == JUMP:
                legs.append((JUMP, point))
            else:
                legs.append((DROP, [Point3(point[0], point[1], pos[2]), point]))
            pos = point
        if run:
            legs.append((WALK, self.smooth(pos, run, grid)))
        return legs

    def smooth(self, start, points, grid, lookahead=12):
        """Cuts corners where the way is clear and the floor level, so the
        toon runs straight lines instead of grid steps."""
        if grid is None:
            return list(points)
        out = []
        here = Point3(start)
        i = 0
        while i < len(points):
            best = i
            for j in range(min(len(points) - 1, i + lookahead), i, -1):
                if self.straight(grid, here, points[i:j + 1]):
                    best = j
                    break
            out.append(points[best])
            here = points[best]
            i = best + 1
        return out

    def straight(self, grid, here, points):
        end = points[-1]
        # Stairs and ramps keep their steps (the heights along the way).
        if any(abs(p[2] - here[2]) > 0.4 for p in points):
            return False
        a = Point3(here[0], here[1], here[2] + CHEST)
        b = Point3(end[0], end[1], end[2] + CHEST)
        if grid.blocked(a, b):
            return False
        # Floor all along the way.
        length = (end - here).length()
        steps = max(1, int(length / CELL))
        for k in range(1, steps):
            p = here + (end - here) * (k / float(steps))
            ix, iy = cellOf(p[0], p[1])
            if grid.heightNear(ix, iy, here[2], 0.6, 0.6) is None:
                return False
        return True


_finder = None


def getPathfinder():
    global _finder
    if _finder is None:
        _finder = NPCPathfinder()
    return _finder
