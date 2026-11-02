"""Where the cogs can walk on a map with floors above floors.

The playground maps keep one floor per spot on the ground (the highest),
which is all an open playground needs. The big maps have balconies over
lobbies, walkways over courtyards and rooms stacked on rooms, so here every
spot on the grid can hold several floors, one cell each, and the cells are
joined where a toon could walk from one to the next.

Some joins can be shut: a door that has not been bought, a curtain or a
shutter that waits for the power, a bridge that is not down yet. Each such
thing is a named blocker; a join (or a cell) that crosses one is tagged
with its name and only used once the blocker is open. Maps can also join
two cells by hand: a drop off a ledge (toons fall down it, cogs fly back
up it with their propellers) or a hop only a cog can make.
"""

import math
import random

from panda3d.core import BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser, Point3

from toontown.toonbase import ToontownGlobals

# Floor this close over another is the underside of stairs or a table, not
# room to stand.
HEADROOM = 5.0
# Two floor hits closer than this are one floor.
SAME_FLOOR = 0.6
# The most a walk can climb or drop from one cell to the next.
RISE = 3.2
EIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
FOUR = ((1, 0), (-1, 0), (0, 1), (0, -1))


def segmentsCross(a, b, c, d):
    """Whether the 2D segments ab and cd cross."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


class Blocker:
    """Something that shuts some joins until it opens: a line across the
    floor (a door), and/or an area whose cells only exist once it opens (a
    bridge), between two heights."""

    def __init__(self, name, line=None, area=None, z=(-100.0, 100.0)):
        self.name = name
        self.line = line
        self.area = area
        self.z = z

    def crosses(self, a, b):
        if self.line is None:
            return False
        lo, hi = self.z
        if not (lo - 1 <= a[2] <= hi + 1 or lo - 1 <= b[2] <= hi + 1):
            return False
        return segmentsCross(a, b, self.line[0], self.line[1])

    def covers(self, p):
        if self.area is None:
            return False
        x0, y0, x1, y1 = self.area
        lo, hi = self.z
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and lo - 1 <= p[2] <= hi + 1


class LayeredNav:

    def __init__(self, arena, step=3.0):
        self.arena = arena
        self.step = step
        self.trav = CollisionTraverser('layeredNav')
        self.queue = CollisionHandlerQueue()
        self.ray = CollisionRay()
        node = CollisionNode('layeredNavRay')
        node.addSolid(self.ray)
        node.setFromCollideMask(ToontownGlobals.FloorBitmask)
        node.setIntoCollideMask(BitMask32.allOff())
        self.rayPath = arena.root.attachNewNode(node)
        self.trav.addCollider(self.rayPath, self.queue)
        self.blockers = {}
        self.open = set()
        self.cells = {}
        self.columns = {}
        self.cellTags = {}
        self.edges = {}
        self.flows = {}
        self.links = []

    # --- Building ---

    def addBlocker(self, blocker):
        self.blockers[blocker.name] = blocker

    def addLink(self, a, b, kind):
        """kind 'drop': a (high) down to b, both ways for cogs, down only
        for toons. 'hop': both ways, cogs only."""
        self.links.append((Point3(a), Point3(b), kind))

    def floorsAt(self, x, y, top):
        self.ray.setOrigin(x, y, top)
        self.ray.setDirection(0, 0, -1)
        self.queue.clearEntries()
        self.trav.traverse(self.arena.root)
        zs = sorted(self.queue.getEntry(i).getSurfacePoint(self.arena.root).getZ() for i in range(self.queue.getNumEntries()))
        floors = []
        for z in zs:
            if floors and z - floors[-1] < SAME_FLOOR:
                floors[-1] = z
                continue
            floors.append(z)
        # Keep only floors with room over them.
        out = []
        for i, z in enumerate(floors):
            if i + 1 < len(floors) and floors[i + 1] - z < HEADROOM:
                continue
            out.append(z)
        return out

    def build(self, start, center, span, top=120.0, lowest=-20.0):
        """Flood out from start over every floor a toon could walk to with
        every blocker open, then tag what each blocker shuts."""
        step = self.step
        lo = (int((center[0] - span) / step), int((center[1] - span) / step))
        hi = (int((center[0] + span) / step), int((center[1] + span) / step))
        clear = self.arena.clearLine
        # Everything that can open is opened while the floors are found
        # (door walls away, the bridge down), and put back after.
        shut, opened = self.arena.openableSolids()
        for np in shut:
            np.stash()
        for np in opened:
            np.unstash()
        try:
            self.columns = {}
            origin = (int(round(start[0] / step)), int(round(start[1] / step)))
            first = self.__column(origin, top, lowest)
            if not first:
                return
            k = min(range(len(first)), key=lambda i: abs(first[i] - start[2]))
            startKey = (origin[0], origin[1], k)
            self.cells = {startKey: Point3(origin[0] * step, origin[1] * step, first[k])}
            self.edges = {startKey: set()}
            frontier = [startKey]
            while frontier:
                key = frontier.pop()
                here = self.cells[key]
                for di, dj in FOUR:
                    ci, cj = key[0] + di, key[1] + dj
                    if not (lo[0] <= ci <= hi[0] and lo[1] <= cj <= hi[1]):
                        continue
                    for kk, z in enumerate(self.__column((ci, cj), top, lowest)):
                        if abs(z - here[2]) > RISE:
                            continue
                        there = Point3(ci * step, cj * step, z)
                        nkey = (ci, cj, kk)
                        if nkey in self.edges.get(key, ()):
                            continue
                        if not clear(here, there):
                            continue
                        self.edges.setdefault(key, set()).add(nkey)
                        self.edges.setdefault(nkey, set()).add(key)
                        if nkey not in self.cells:
                            self.cells[nkey] = there
                            frontier.append(nkey)
            # The hand-made joins: drops and hops.
            self.special = {}
            for a, b, kind in self.links:
                ka, kb = self.nearestCell(a, maxRing=3), self.nearestCell(b, maxRing=3)
                if ka is None or kb is None:
                    continue
                self.special[(ka, kb)] = kind if kind == 'hop' else 'drop'
                self.special[(kb, ka)] = 'hop'
        finally:
            for np in shut:
                np.unstash()
            for np in opened:
                np.stash()
        self.__tag()
        self.__diagonals()
        self.flows = {}

    def __column(self, cell, top, lowest):
        col = self.columns.get(cell)
        if col is None:
            col = [z for z in self.floorsAt(cell[0] * self.step, cell[1] * self.step, top) if z >= lowest]
            self.columns[cell] = col
        return col

    def __tag(self):
        self.cellTags = {}
        self.edgeTags = {}
        for key, p in self.cells.items():
            tags = frozenset(b.name for b in self.blockers.values() if b.covers(p))
            if tags:
                self.cellTags[key] = tags
        for key, others in self.edges.items():
            a = self.cells[key]
            for other in others:
                if (other, key) in self.edgeTags or other < key:
                    continue
                b = self.cells[other]
                tags = frozenset(bl.name for bl in self.blockers.values() if bl.crosses(a, b))
                if tags:
                    self.edgeTags[(key, other)] = tags
                    self.edgeTags[(other, key)] = tags

    def __diagonals(self):
        """Eight ways: a diagonal joins two cells when both corners round it
        are open walks."""
        self.diag = {}
        for key, others in self.edges.items():
            for o1 in others:
                for o2 in others:
                    if o1 >= o2 or o1[0] == o2[0] or o1[1] == o2[1]:
                        continue
                    # The far corner reached through both.
                    shared = self.edges.get(o1, set()) & self.edges.get(o2, set())
                    for far in shared:
                        if far != key and far[0] != key[0] and far[1] != key[1]:
                            self.diag.setdefault(key, set()).add((far, o1, o2))

    # --- Open and shut ---

    def setOpen(self, name, isOpen=True):
        if isOpen:
            self.open.add(name)
        else:
            self.open.discard(name)
        self.flows = {}

    def usableCell(self, key):
        tags = self.cellTags.get(key)
        return not tags or tags <= self.open

    def usableEdge(self, a, b):
        tags = self.edgeTags.get((a, b))
        return (not tags or tags <= self.open) and self.usableCell(b)

    def neighbours(self, key, cog=True, reverse=False):
        """Where a walker can go from key (or, reverse, come to key from)."""
        out = []
        for other in self.edges.get(key, ()):
            if self.usableEdge(key, other):
                out.append(other)
        for far, o1, o2 in self.diag.get(key, ()):
            if self.usableEdge(key, o1) and self.usableEdge(key, o2) and self.usableEdge(o1, far) and self.usableEdge(o2, far):
                out.append(far)
        for (a, b), kind in self.special.items():
            src, dst = (b, a) if reverse else (a, b)
            if src != key or not self.usableCell(dst):
                continue
            if kind == 'hop' and not cog:
                continue
            out.append(dst)
        return out

    # --- Asking ---

    def nearestCell(self, p, maxRing=3, usable=True):
        step = self.step
        ci, cj = int(round(p[0] / step)), int(round(p[1] / step))
        best, bestScore = None, None
        for r in range(0, maxRing + 1):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if max(abs(di), abs(dj)) != r:
                        continue
                    col = self.columns.get((ci + di, cj + dj)) or ()
                    for k, z in enumerate(col):
                        key = (ci + di, cj + dj, k)
                        if key not in self.cells or (usable and not self.usableCell(key)):
                            continue
                        dz = z - p[2]
                        # A floor a little below the feet is likeliest.
                        if dz > 2.5 or dz < -6.0:
                            continue
                        score = di * di + dj * dj + abs(dz) * 0.5
                        if bestScore is None or score < bestScore:
                            best, bestScore = key, score
            if best is not None:
                return best
        return None

    def cellPoint(self, key):
        return self.cells.get(key)

    def flowTo(self, goal):
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
                # Who can come to here: walk the joins backwards.
                for c in self.neighbours(here, cog=True, reverse=True):
                    if c in came:
                        continue
                    came[c] = here
                    nxt.append(c)
            frontier = nxt
        if len(self.flows) >= 40:
            del self.flows[next(iter(self.flows))]
        self.flows[cell] = came
        return came, cell

    def reachable(self, a, b):
        flow, cell = self.flowTo(b)
        start = self.nearestCell(a)
        return bool(flow) and start is not None and start in flow

    def path(self, a, b, cog=False):
        start, goal = self.nearestCell(a), self.nearestCell(b)
        if start is None or goal is None or start == goal:
            return [Point3(b)]
        came = {start: None}
        frontier = [start]
        while frontier and goal not in came:
            nxt = []
            for here in frontier:
                for c in self.neighbours(here, cog=cog):
                    if c not in came:
                        came[c] = here
                        nxt.append(c)
            frontier = nxt
        if goal not in came:
            return []
        keys = []
        c = goal
        while c is not None:
            keys.append(c)
            c = came[c]
        keys.reverse()
        return [Point3(self.cells[k]) for k in keys[1:-1]] + [Point3(b)]

    def isSpecial(self, a, b):
        return self.special.get((a, b))

    def randomSpot(self):
        keys = [k for k in self.cells if self.usableCell(k)]
        return Point3(self.cells[random.choice(keys)]) if keys else None

    def destroy(self):
        self.rayPath.removeNode()
