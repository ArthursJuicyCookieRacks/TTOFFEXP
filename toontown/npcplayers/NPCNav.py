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


class NPCNav:

    def __init__(self):
        # A place the client has loaded but not shown yet (see NPCPreload).
        self.sceneOverride = None
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
        self.traverse(scene)
        best = None
        for i in range(self.queue.getNumEntries()):
            hitZ = self.queue.getEntry(i).getSurfacePoint(scene).getZ()
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
        self.traverse(scene)
        best = None
        into = None
        for i in range(self.queue.getNumEntries()):
            entry = self.queue.getEntry(i)
            hitZ = entry.getSurfacePoint(scene).getZ()
            if hitZ <= z + STEP_UP and (best is None or hitZ > best):
                best = hitZ
                into = entry.getIntoNodePath()
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
        self.traverse(scene)
        for i in range(self.queue.getNumEntries()):
            hitZ = self.queue.getEntry(i).getSurfacePoint(scene).getZ()
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

    def clearLine(self, a, b):
        """Whether a toon can walk straight from a to b without hitting a wall."""
        scene = self.getScene()
        if scene is None:
            return False
        self.segment.setPointA(a[0], a[1], a[2] + CHEST)
        self.segment.setPointB(b[0], b[1], b[2] + CHEST)
        self.traverser.clearColliders()
        self.traverser.addCollider(self.segmentPath, self.queue)
        self.traverse(scene)
        for i in range(self.queue.getNumEntries()):
            entry = self.queue.getEntry(i)
            into = entry.getIntoNodePath()
            # Other toons and the cogs walk about, and trigger spheres stop
            # nobody; only the scenery counts.
            if not entry.getInto().isTangible():
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
