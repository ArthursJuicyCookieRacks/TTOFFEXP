"""Where an NPC player can stand and walk.

The district has no idea of the ground or the walls; only the client loads the
geometry. The offline game runs both in one process, so this asks the
client's scene graph: a ray down finds the ground under a spot, and a segment
at chest height tells whether a wall is in the way. Without a loaded scene
(the player is elsewhere) nothing can be checked, so the NPCs stand still.
"""

from panda3d.core import (BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay,
                          CollisionSegment, CollisionTraverser, NodePath, Point3)

from otp.local.ExecutionContext import getClientBuiltin
from toontown.toonbase import ToontownGlobals

STEP_UP = 3.0
# A walk may not drop the toon further than this in one step.
MAX_DROP = 4.0
CHEST = 2.0
# Floor this close over a spot means it is under stairs or a ramp.
HEADROOM = 12.0


# A staircase changes height within a stride; a level floor with 'stair' in
# its name (Bossbot HQ's courtyard) does not.
STAIR_STEP = 2.0
STAIR_RISE = 0.12


class NPCNav:

    def __init__(self):
        # A place the client has loaded but not shown yet (see NPCPreload).
        self.sceneOverride = None
        self.levelRoots = {}
        self.traverser = CollisionTraverser('npcNav')
        self.queue = CollisionHandlerQueue()
        self.root = NodePath('npcNavRays')
        self.ray = CollisionRay()
        rayNode = CollisionNode('npcNavRay')
        rayNode.addSolid(self.ray)
        rayNode.setFromCollideMask(ToontownGlobals.FloorBitmask)
        rayNode.setIntoCollideMask(BitMask32.allOff())
        self.rayPath = self.root.attachNewNode(rayNode)
        self.segment = CollisionSegment()
        segmentNode = CollisionNode('npcNavSegment')
        segmentNode.addSolid(self.segment)
        segmentNode.setFromCollideMask(ToontownGlobals.WallBitmask)
        segmentNode.setIntoCollideMask(BitMask32.allOff())
        self.segmentPath = self.root.attachNewNode(segmentNode)

    def getScene(self):
        if self.sceneOverride is not None:
            return self.sceneOverride
        base = getClientBuiltin('base')
        if base is None or not hasattr(base, 'render'):
            return None
        return base.render

    def traverse(self, scene):
        # The rays have to be in the scene they test.
        self.queue.clearEntries()
        self.root.reparentTo(scene)
        try:
            self.traverser.traverse(scene)
        finally:
            self.root.detachNode()
        self.queue.sortEntries()

    def hits(self, scene):
        """Every hit of the ray or segment set up now, as (point, into
        NodePath, tangible), in the scene's coordinates: the scene itself,
        and the parts of a factory, mint or office its client has put away
        for now (the rooms the player can't see; see hiddenRooms)."""
        out = []
        roots = [scene]
        if scene is not self.sceneOverride:
            roots += self.hiddenRooms()
        for root in roots:
            self.traverse(root)
            for i in range(self.queue.getNumEntries()):
                entry = self.queue.getEntry(i)
                out.append((entry.getSurfacePoint(root), entry.getIntoNodePath(), entry.getInto().isTangible()))
        return out

    def hiddenRooms(self):
        """A factory or mint hides (stashes) the rooms out of the player's
        sight, and a stashed node can't be hit; the NPCs elsewhere in the
        place still need its floors and walls. Each such level gets a copy
        of its rooms (instances, never drawn) at their place in the world."""
        base = getClientBuiltin('base')
        if base is None or not hasattr(base, 'cr'):
            return []
        roots = []
        live = set()
        for obj in list(base.cr.doId2do.values()):
            zones = getattr(obj, 'zoneNum2node', None)
            geom = getattr(obj, 'geom', None)
            if not zones or geom is None or geom.isEmpty():
                continue
            live.add(obj.doId)
            root = self.levelRoots.get(obj.doId)
            if root is None or root[1] is not geom:
                if root is not None:
                    root[0].removeNode()
                holder = NodePath('npcNavRooms-%d' % obj.doId)
                for zoneNum, zone in zones.items():
                    if zone is geom or zone.isEmpty() or zone == geom:
                        continue
                    parent = holder.attachNewNode('room-%s' % zoneNum)
                    parent.setMat(zone.getParent().getMat(base.render))
                    zone.instanceTo(parent)
                root = self.levelRoots[obj.doId] = (holder, geom)
            roots.append(root[0])
        for doId in list(self.levelRoots):
            if doId not in live:
                self.levelRoots.pop(doId)[0].removeNode()
        return roots

    def available(self):
        return self.getScene() is not None

    def groundZ(self, x, y, z):
        """The ground under (x, y) near height z, or None if there is none."""
        scene = self.getScene()
        if scene is None:
            return z
        self.ray.setOrigin(x, y, z + STEP_UP)
        self.ray.setDirection(0, 0, -1)
        self.traverser.clearColliders()
        self.traverser.addCollider(self.rayPath, self.queue)
        best = None
        for point, into, tangible in self.hits(scene):
            hitZ = point.getZ()
            if hitZ <= z + STEP_UP and (best is None or hitZ > best):
                best = hitZ
        if best is None or best < z - MAX_DROP:
            return None
        return best

    def groundHit(self, x, y, z):
        """Like groundZ, but also the node the ground belongs to (a moving
        platform carries whoever stands on it), or (None, None)."""
        scene = self.getScene()
        if scene is None:
            return z, None
        self.ray.setOrigin(x, y, z + STEP_UP)
        self.ray.setDirection(0, 0, -1)
        self.traverser.clearColliders()
        self.traverser.addCollider(self.rayPath, self.queue)
        best = None
        into = None
        for point, hitInto, tangible in self.hits(scene):
            hitZ = point.getZ()
            if hitZ <= z + STEP_UP and (best is None or hitZ > best):
                best = hitZ
                into = hitInto
        if best is None or best < z - MAX_DROP:
            return None, None
        return best, into

    def covered(self, x, y, z):
        """Whether there is floor overhead at (x, y), as under a staircase."""
        scene = self.getScene()
        if scene is None:
            return False
        self.ray.setOrigin(x, y, z + HEADROOM)
        self.ray.setDirection(0, 0, -1)
        self.traverser.clearColliders()
        self.traverser.addCollider(self.rayPath, self.queue)
        for point, into, tangible in self.hits(scene):
            hitZ = point.getZ()
            if z + STEP_UP < hitZ <= z + HEADROOM:
                return True
        return False

    def standZ(self, x, y, z):
        """The ground a toon can stand on at (x, y) near height z: groundZ,
        but None under stairs, where the toon would be stuck."""
        ground = self.groundZ(x, y, z)
        if ground is None or self.covered(x, y, ground):
            return None
        return ground

    def onStairs(self, x, y, z):
        """Whether the ground at (x, y) is a staircase (or a step), by the
        name of the floor it belongs to. Stairs are built as ramps to walk
        on, so a toon put on one stands inside the steps."""
        ground, into = self.groundHit(x, y, z)
        if into is None:
            return False
        node = into
        named = False
        while not node.isEmpty():
            name = node.getName().lower()
            if 'stair' in name or 'satir' in name or 'step' in name:
                named = True
                break
            node = node.getParent()
        if not named:
            return False
        # Bossbot HQ's whole courtyard floor is one collision named
        # G_Stair_coll, so the name alone is not enough: a staircase is
        # where the ground a step away is higher or lower.
        for dx, dy in ((STAIR_STEP, 0), (-STAIR_STEP, 0), (0, STAIR_STEP), (0, -STAIR_STEP)):
            near = self.groundZ(x + dx, y + dy, ground)
            if near is None or abs(near - ground) > STAIR_RISE:
                return True
        return False

    def spawnZ(self, x, y, z):
        """The ground to put a new toon on at (x, y): standZ, but None on a
        staircase."""
        ground = self.standZ(x, y, z)
        if ground is None or self.onStairs(x, y, ground):
            return None
        return ground

    def clearLine(self, a, b):
        """Whether a toon can walk straight from a to b without hitting a wall."""
        scene = self.getScene()
        if scene is None:
            return False
        if (Point3(*a) - Point3(*b)).lengthSquared() < 1e-6:
            # A segment from a point to itself fails an assertion in Panda.
            return True
        self.segment.setPointA(a[0], a[1], a[2] + CHEST)
        self.segment.setPointB(b[0], b[1], b[2] + CHEST)
        self.traverser.clearColliders()
        self.traverser.addCollider(self.segmentPath, self.queue)
        for point, into, tangible in self.hits(scene):
            # Other toons and the cogs walk about, and trigger spheres stop
            # nobody; only the scenery counts.
            if not tangible:
                continue
            if into.findNetTag('avatarDoId').isEmpty() and into.findNetPythonTag('avatar').isEmpty():
                return False
        return True

    def walkable(self, a, b, step=3.0):
        """Whether the ground holds all the way from a to b; returns the path
        snapped to the ground, or None."""
        if not self.clearLine(a, b):
            return None
        a = Point3(a)
        b = Point3(b)
        length = (b - a).length()
        steps = max(1, int(length / step))
        points = []
        z = a[2]
        for i in range(1, steps + 1):
            p = a + (b - a) * (float(i) / steps)
            ground = self.groundZ(p[0], p[1], z)
            if ground is None:
                return None
            z = ground
            points.append(Point3(p[0], p[1], z))
        # Never stop under stairs; a toon there can't find its way out.
        if self.covered(points[-1][0], points[-1][1], points[-1][2]):
            return None
        return points


_nav = None


def getNav():
    global _nav
    if _nav is None:
        _nav = NPCNav()
    return _nav
