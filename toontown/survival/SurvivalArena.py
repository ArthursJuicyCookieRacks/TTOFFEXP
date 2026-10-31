"""Toontown Central after dark: the playground of Survival Mode.

Only the playground is loaded, straight from its DNA, with no district,
no Place and no doors or tunnels that do anything. The sky is the dark
one and the whole scene is dimmed to moonlight. The stations (Mickey by
the Loopy Lane tunnel, the trunk and the fisherman at the gazebo) stand
where the real playground has those landmarks.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import (Fog, BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionSegment, CollisionTraverser,
                          CompassEffect, ModelPool, NodePath, Point3, TexturePool, Vec3, Vec4)

from toontown.dna.DNAStorage import DNAStorage
from toontown.hood import SkyUtil
from toontown.npcplayers.NPCNav import getNav
from toontown.toonbase import ToontownGlobals

STORAGE_FILES = ('phase_4/dna/storage.xml', 'phase_4/dna/storage_TT.xml', 'phase_4/dna/storage_TT_sz.xml')
DNA_FILE = 'phase_4/dna/toontown_central_sz.xml'
SKY_FILE = 'phase_3.5/models/props/BR_sky'
# Moonlight over the playground.
NIGHT_SCALE = Vec4(0.42, 0.46, 0.62, 1)
SKY_COLOR = Vec4(0.22, 0.24, 0.36, 1)

# Where things are in the playground (from its DNA).
LOOPY_LANE_TUNNEL = (Point3(-239.67, 64.08, -6.18), -90)
FISHERMAN = (Point3(-68, -2, -1.975), 27)
GAZEBO = (Point3(-60.94, -8.8, -2), -178)
# Where the accessory trunk stands: beside the fisherman (on his right,
# the player's left facing him) and a step ahead, clear of the gazebo's
# railing behind him so the open lid never reaches it.
TRUNK_BESIDE = 6.0
TRUNK_AHEAD = 3.0
# The player starts on the grass in front of Toon Hall.
PLAYER_START = (Point3(0, -20, 0), 0)
# Cogs land out of sight, this far out from the middle and this far from
# every toon.
SPAWN_RING = (45.0, 130.0)
SPAWN_CLEAR = 30.0
VIEW_HALF_ANGLE = 60.0
# Cogs never land in or around these: the gazebo (railings and steps all
# round, Arthur saw cogs stuck in it) and the stations' corners.
NO_LANDING = ((GAZEBO[0], 22.0), (FISHERMAN[0], 12.0), (LOOPY_LANE_TUNNEL[0], 16.0))
# A landing cell needs this many rings of open cells round it, so a cog
# (a big one is 3 feet across) never lands against a wall, fence or tree.
LANDING_CLEARANCE = 1


class SurvivalArena:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalArena')

    def __init__(self):
        self.root = render.attachNewNode('survivalArena')
        self.dnaStore = DNAStorage()
        for name in STORAGE_FILES:
            loader.loadDNA(name).store(self.dnaStore)
        self.dnaStore.storeFont(ToontownGlobals.getInterfaceFont(), 'humanist')
        self.dnaStore.storeFont(ToontownGlobals.getSignFont(), 'mickey')
        self.dnaStore.storeFont(ToontownGlobals.getSuitFont(), 'suit')
        tree = loader.loadDNA(DNA_FILE)
        node = tree.generate(self.dnaStore)
        if node.getNumParents() == 1:
            self.geom = NodePath(node.getParent(0))
        else:
            self.geom = NodePath(node)
        self.geom.reparentTo(self.root)
        # Nothing leads anywhere: the tunnels' triggers go, the doors are
        # plain geometry without a DistributedDoor behind them.
        for trigger in self.geom.findAllMatches('**/tunnel_trigger*'):
            trigger.stash()
        for trigger in self.geom.findAllMatches('**/door_trigger*'):
            trigger.stash()
        # What a DistributedDoor does to a door's parts when it generates
        # (hideDoorParts): the black "hole" behind each leaf shows only
        # while the door swings, and a door drawn on a flat keeps its leaves
        # hidden. Without doors here nothing did this, so Toon HQ's doorway
        # was a black hole.
        for hole in self.geom.findAllMatches('**/doorFrameHole*'):
            hole.hide()
        for flat in self.geom.findAllMatches('**/door_flat*'):
            suffix = flat.getName()[len('door_flat'):]
            building = flat.getParent()
            for leaf in ('leftDoor', 'rightDoor'):
                for door in building.findAllMatches('**/%s%s' % (leaf, suffix)):
                    door.hide()
        for origin in self.geom.findAllMatches('**/suit_building_origin'):
            origin.removeNode()
        self.geom.flattenMedium()
        gsg = base.win.getGsg()
        if gsg:
            self.geom.prepareScene(gsg)
        self.root.setColorScale(NIGHT_SCALE)
        self.sky = None
        self.skyTask = None
        self.startSky()
        self.nav = getNav()
        self.nav.sceneOverride = None
        # A ray from high up, for the ground anywhere in the playground.
        self.groundTrav = CollisionTraverser('survivalGround')
        self.groundQueue = CollisionHandlerQueue()
        self.groundRay = CollisionRay()
        rayNode = CollisionNode('survivalGroundRay')
        rayNode.addSolid(self.groundRay)
        rayNode.setFromCollideMask(ToontownGlobals.FloorBitmask)
        rayNode.setIntoCollideMask(BitMask32.allOff())
        self.groundRayPath = self.root.attachNewNode(rayNode)
        self.groundTrav.addCollider(self.groundRayPath, self.groundQueue)
        # A segment along the aim line, for the wall or floor a gag lands on.
        self.aimTrav = CollisionTraverser('survivalAim')
        self.aimQueue = CollisionHandlerQueue()
        self.aimSegment = CollisionSegment()
        segNode = CollisionNode('survivalAimSegment')
        segNode.addSolid(self.aimSegment)
        segNode.setFromCollideMask(ToontownGlobals.WallBitmask | ToontownGlobals.FloorBitmask | ToontownGlobals.CameraBitmask)
        segNode.setIntoCollideMask(BitMask32.allOff())
        self.aimSegmentPath = self.root.attachNewNode(segNode)
        self.aimTrav.addCollider(self.aimSegmentPath, self.aimQueue)

    def startSky(self):
        self.sky = loader.loadModel(SKY_FILE)
        self.sky.setTag('sky', 'Survival')
        self.sky.setScale(1.0)
        self.sky.setDepthTest(0)
        self.sky.setDepthWrite(0)
        self.sky.setBin('background', 100)
        self.sky.setColor(SKY_COLOR)
        self.sky.reparentTo(camera)
        self.sky.setZ(0.0)
        self.sky.setHpr(0.0, 0.0, 0.0)
        self.sky.node().setEffect(CompassEffect.make(NodePath(), CompassEffect.PRot | CompassEffect.PZ))
        self.skyTask = taskMgr.add(self.__spinSky, 'survivalSky')
        self.skyTask.h = 0
        self.skyTask.cloud1 = self.sky.find('**/cloud1')
        self.skyTask.cloud2 = self.sky.find('**/cloud2')

    def __spinSky(self, task):
        task.h += globalClock.getDt() * 0.25
        if not task.cloud1.isEmpty():
            task.cloud1.setH(task.h)
        if not task.cloud2.isEmpty():
            task.cloud2.setH(-task.h * 0.8)
        return task.cont

    def setFog(self, on):
        """The Gag-Snatcher rounds come in a fog (BO1's hound rounds)."""
        if on:
            fog = Fog('snatcherFog')
            fog.setColor(0.18, 0.16, 0.22)
            fog.setExpDensity(0.012)
            self.root.setFog(fog)
            if self.sky:
                self.sky.setColorScale(0.6, 0.55, 0.7, 1)
        else:
            self.root.clearFog()
            if self.sky:
                self.sky.clearColorScale()

    def destroy(self):
        if self.skyTask:
            taskMgr.remove(self.skyTask)
            self.skyTask = None
        if self.sky:
            self.sky.removeNode()
            self.sky = None
        self.root.removeNode()
        try:
            self.dnaStore.reset()
        except Exception:
            # The repo's DNAStorage.reset trips over itself; the store goes
            # away with us either way.
            pass
        self.dnaStore = None
        ModelPool.garbageCollect()
        TexturePool.garbageCollect()

    # --- Ground ---

    def groundZ(self, x, y):
        """The highest floor under (x, y), or None off the playground."""
        self.groundRay.setOrigin(x, y, 80.0)
        self.groundRay.setDirection(0, 0, -1)
        self.groundQueue.clearEntries()
        self.groundTrav.traverse(self.root)
        best = None
        for i in range(self.groundQueue.getNumEntries()):
            hitZ = self.groundQueue.getEntry(i).getSurfacePoint(render).getZ()
            if best is None or hitZ > best:
                best = hitZ
        return best

    def rayHit(self, origin, direction, maxDist):
        """The first wall or floor along the line: (distance, point) or None."""
        end = origin + direction * maxDist
        self.aimSegment.setPointA(origin)
        self.aimSegment.setPointB(end)
        self.aimQueue.clearEntries()
        self.aimTrav.traverse(self.root)
        best = None
        for i in range(self.aimQueue.getNumEntries()):
            point = self.aimQueue.getEntry(i).getSurfacePoint(render)
            dist = (point - origin).length()
            if best is None or dist < best[0]:
                best = (dist, point)
        return best

    def spawnZ(self, x, y):
        z = self.groundZ(x, y)
        if z is None or z < -8 or self.nav.onStairs(x, y, z):
            return None
        return z

    def clearLine(self, a, b):
        return self.nav.clearLine(a, b)

    def walkable(self, a, b):
        return self.nav.walkable(a, b)

    # --- Where the stations stand ---

    def mickeySpot(self):
        # Just inside the playground from the Loopy Lane tunnel mouth,
        # facing the toons who walk up.
        # The tunnel prop's own origin is far back inside the hill; the
        # playground end is its tunnel_origin node, the one facing east.
        best = None
        for node in self.geom.findAllMatches('**/tunnel_origin'):
            h = node.getH(render)
            off = abs((h + 90 + 180) % 360 - 180)
            if best is None or off < best[0]:
                best = (off, node.getPos(render), h)
        if best is not None and best[0] < 30:
            pos, h = best[1], best[2]
            forward = Vec3(-math.sin(math.radians(h)), math.cos(math.radians(h)), 0)
            spot = pos + forward * 9.0
            return self.placeOnGround(spot[0], spot[1], h)
        origin, h = LOOPY_LANE_TUNNEL
        pos, h = self.placeOnGround(origin[0] + 14.0, origin[1], -90)
        if self.groundZ(pos[0], pos[1]) is None:
            pos = Point3(pos[0], pos[1], origin[2])
        return pos, h

    def fishermanSpot(self):
        origin, h = FISHERMAN
        return self.placeOnGround(origin[0], origin[1], h)

    def trunkSpot(self):
        # Directly left of the fisherman as the player faces him (his own
        # right), level with him and facing the same way, so the lid opens
        # toward the gazebo behind without reaching it.
        origin, h = FISHERMAN
        right = Vec3(math.cos(math.radians(h)), math.sin(math.radians(h)), 0)
        forward = Vec3(-math.sin(math.radians(h)), math.cos(math.radians(h)), 0)
        spot = origin + right * TRUNK_BESIDE + forward * TRUNK_AHEAD
        # The trunk model's open side is its -y, so it turns about to face
        # the playground the way the fisherman does.
        return self.placeOnGround(spot[0], spot[1], h + 180)

    def placeOnGround(self, x, y, h=0.0):
        z = self.groundZ(x, y)
        if z is None:
            z = 0.0
        return Point3(x, y, z), h

    # --- Where cogs land ---

    def inView(self, spot, eye, forward):
        d = Vec3(spot - eye)
        flat = math.hypot(d[0], d[1])
        if flat < 1:
            return True
        angle = math.degrees(math.atan2(d[0], d[1]))
        facing = math.degrees(math.atan2(forward[0], forward[1]))
        if abs((angle - facing + 180) % 360 - 180) > VIEW_HALF_ANGLE:
            return False
        return self.clearLine(eye, Point3(spot[0], spot[1], spot[2] + 3))

    REACH_STEP = 5.0
    REACH_SPAN = 150.0

    def buildReach(self, start):
        """Flood the playground from where the player starts, one cell at
        a time, over ground a toon can walk: the open playground. Cells
        inside buildings, behind fences, on the hill or off the edge never
        join, so cogs only ever land where the player could stand."""
        step = self.REACH_STEP
        half = int(self.REACH_SPAN / step)
        z0 = self.spawnZ(start[0], start[1])
        if z0 is None:
            z0 = start[2]
        origin = (int(round(start[0] / step)), int(round(start[1] / step)))
        self.reach = {origin: Point3(origin[0] * step, origin[1] * step, z0)}
        self.reachZ = {}
        self.stairs = set()
        frontier = [origin]
        while frontier:
            cell = frontier.pop()
            here = self.reach[cell]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + di, cell[1] + dj)
                if nxt in self.reach or nxt in self.reachZ or abs(nxt[0]) > half or abs(nxt[1]) > half:
                    continue
                x, y = nxt[0] * step, nxt[1] * step
                # Steps and stairs join the walk (a cog follows the player
                # up into the gazebo) but are never landed on.
                z = self.groundZ(x, y)
                if z is not None and z < -8:
                    z = None
                if z is not None and self.nav.onStairs(x, y, z):
                    self.stairs.add(nxt)
                self.reachZ[nxt] = z
                # A step up onto the gazebo is a bit more than three feet
                # from cell to cell; anywhere else three is the most.
                rise = 3.6 if (nxt in self.stairs or cell in self.stairs) else 3.0
                if z is None or abs(z - here[2]) > rise:
                    continue
                there = Point3(x, y, z)
                if not self.clearLine(here, there):
                    continue
                self.reach[nxt] = there
                frontier.append(nxt)
        self.reachList = [p for c, p in self.reach.items() if c not in self.stairs]
        self.landingList = []
        ring = LANDING_CLEARANCE
        for cell, point in self.reach.items():
            if cell in self.stairs:
                continue
            if any((cell[0] + di, cell[1] + dj) not in self.reach
                   for di in range(-ring, ring + 1) for dj in range(-ring, ring + 1)):
                continue
            if any((Point3(point[0], point[1], 0) - Point3(spot[0], spot[1], 0)).length() < radius for spot, radius in NO_LANDING):
                continue
            self.landingList.append(point)
        self.flows = {}
        self.notify.info('reach: %d cells, %d open for landing' % (len(self.reachList), len(self.landingList)))

    def nearestCell(self, p):
        step = self.REACH_STEP
        cell = (int(round(p[0] / step)), int(round(p[1] / step)))
        reach = getattr(self, 'reach', None) or {}
        if cell in reach:
            return cell
        best, bestDist = None, None
        for r in range(1, 4):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    c = (cell[0] + di, cell[1] + dj)
                    if c in reach:
                        d = di * di + dj * dj
                        if bestDist is None or d < bestDist:
                            best, bestDist = c, d
            if best is not None:
                return best
        return None

    def path(self, a, b):
        """Points to walk from a to b over the open playground's cells
        (breadth first, eight ways), ending at b itself; [b] when the way
        is clear or the grid doesn't know either end."""
        if self.walkable(a, b):
            return [Point3(b)]
        reach = getattr(self, 'reach', None) or {}
        start, goal = self.nearestCell(a), self.nearestCell(b)
        if start is None or goal is None or start == goal:
            return [Point3(b)]
        came = {start: None}
        frontier = [start]
        while frontier and goal not in came:
            nxt = []
            for cell in frontier:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    c = (cell[0] + di, cell[1] + dj)
                    if c in came or c not in reach:
                        continue
                    if di and dj and ((cell[0] + di, cell[1]) not in reach or (cell[0], cell[1] + dj) not in reach):
                        continue
                    came[c] = cell
                    nxt.append(c)
            frontier = nxt
        if goal not in came:
            return [Point3(b)]
        cells = []
        c = goal
        while c is not None:
            cells.append(c)
            c = came[c]
        cells.reverse()
        points = [reach[c] for c in cells[1:-1]]
        # Skip the corners a straight walk can cut.
        out = []
        here = Point3(a)
        i = 0
        while i < len(points):
            j = len(points) - 1
            while j > i and not self.walkable(here, points[j]):
                j -= 1
            out.append(points[j])
            here = points[j]
            i = j + 1
        out.append(Point3(b))
        return out

    def randomSpot(self):
        spots = getattr(self, 'reachList', None) or []
        return Point3(random.choice(spots)) if spots else None

    def landingSpots(self):
        # Only open cells: never against a wall or in the gazebo.
        return getattr(self, 'landingList', None) or getattr(self, 'reachList', None) or []

    # --- Finding the way (for the cogs) ---

    def flowTo(self, goal):
        """A map from every open cell to the next cell on the shortest way
        to goal (breadth first over the playground's cells, eight ways, no
        cutting corners), refreshed at most every `every` seconds per goal
        cell. One map serves every cog chasing the same toon, so the cogs
        walk round the gazebo, fences and trees instead of into them."""
        reach = getattr(self, 'reach', None)
        if not reach:
            return None, None
        cell = self.nearestCell(goal)
        if cell is None:
            return None, None
        cached = self.flows.get(cell)
        if cached is not None:
            return cached, cell
        came = {cell: None}
        frontier = [cell]
        while frontier:
            nxt = []
            for here in frontier:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    c = (here[0] + di, here[1] + dj)
                    if c in came or c not in reach:
                        continue
                    if di and dj and ((here[0] + di, here[1]) not in reach or (here[0], here[1] + dj) not in reach):
                        continue
                    came[c] = here
                    nxt.append(c)
            frontier = nxt
        if len(self.flows) >= 40:
            del self.flows[next(iter(self.flows))]
        self.flows[cell] = came
        return came, cell

    def cellPoint(self, cell):
        return self.reach.get(cell)

    def pickLanding(self, toons, eye, forward, tries=20):
        """A spot on the open playground the player cannot see, away from
        every toon; None when none turns up this time."""
        spots = self.landingSpots()
        for i in range(tries):
            if spots:
                cell = random.choice(spots)
                x = cell[0] + random.uniform(-1.5, 1.5)
                y = cell[1] + random.uniform(-1.5, 1.5)
                dist = math.hypot(x, y)
                if not SPAWN_RING[0] <= dist <= SPAWN_RING[1]:
                    continue
            else:
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(*SPAWN_RING)
                x, y = dist * math.cos(angle), dist * math.sin(angle)
            z = self.spawnZ(x, y)
            if z is None:
                continue
            spot = Point3(x, y, z)
            if any((Point3(t[0], t[1], 0) - Point3(x, y, 0)).length() < SPAWN_CLEAR for t in toons):
                continue
            if self.inView(spot, eye, forward):
                continue
            return spot
        return None

    def landingNear(self, goal, eye, forward, near=14.0, far=30.0, tries=12):
        """An open spot near a goal, out of the player's view, with a clear
        walk to the goal; None if there is none this time."""
        spots = self.landingSpots()
        for i in range(tries):
            if spots:
                cell = random.choice(spots)
                x, y = cell[0], cell[1]
                if not near <= math.hypot(x - goal[0], y - goal[1]) <= far:
                    continue
            else:
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(near, far)
                x, y = goal[0] + dist * math.cos(angle), goal[1] + dist * math.sin(angle)
            z = self.spawnZ(x, y)
            if z is None:
                continue
            spot = Point3(x, y, z)
            if self.inView(spot, eye, forward):
                continue
            if self.clearLine(Point3(x, y, z + 2), Point3(goal[0], goal[1], z + 2)):
                return spot
        return None
