"""Draws a Survival map's still scenery in as few pieces as it can.

A parody map is put together from dozens of whole models (houses, karts,
picnic tables, fences, lamp posts, trees) and posed cogs standing about as
statues. Each model brings its own handful of pieces, and every piece is a
separate draw for the graphics card, with its own trip through the culling
each frame: Downsizer Drive had about 2,100 of them, more than a whole
playground, which is what made it lag (phones the most).

Nothing here changes what the map looks like or how it plays:
- The models' collisions stay exactly where they are (the walking map and
  its saved copy keep matching); only the pictures move, into one node
  under the map's root, and that is flattened into one piece per texture
  and look.
- A posed cog statue is an animated character holding one pose for ever.
  Its posed shape is written out as plain geometry, the same pose and
  colours, and the character goes.
- Anything that moves, animates, is looked up by name later or draws in its
  own order (the sky, the trolley, the animated props, the stations) is
  left as it was.
"""

from panda3d.core import CollisionNode, GeomNode, LODNode, Thread

from toontown.toonbase import ToontownGlobals

# A model whose own picture is also something to walk on or into keeps that
# picture where it is (the walking map is made from those).
SOLID_MASK = ToontownGlobals.WallBitmask | ToontownGlobals.FloorBitmask


def _solidGeom(np):
    return not (np.node().getIntoCollideMask() & SOLID_MASK).isZero()


def bakeStatue(actor, parent):
    """Write a posed character's shape into plain geometry under parent,
    where it stands now. Returns the new node (or None if it drew nothing)."""
    if hasattr(actor, 'update'):
        actor.update(force=True)
    out = parent.attachNewNode('statue')
    thread = Thread.getCurrentThread()
    count = 0
    # Only what is drawn now: the character's other levels of detail (if
    # any) and hidden parts stay out.
    for gnp in actor.findAllMatches('**/+GeomNode'):
        if gnp.isHidden() or gnp.isStashed():
            continue
        if _underOtherLOD(gnp, actor):
            continue
        node = gnp.node()
        baked = GeomNode(node.getName())
        for i in range(node.getNumGeoms()):
            geom = node.getGeom(i)
            posed = geom.makeCopy()
            posed.setVertexData(geom.getAnimatedVertexData(True, thread))
            baked.addGeom(posed, node.getGeomState(i))
        if not baked.getNumGeoms():
            continue
        np = out.attachNewNode(baked)
        np.setMat(gnp.getMat(parent))
        np.setState(gnp.getState(parent))
        count += 1
    if not count:
        out.removeNode()
        return None
    return out


def _underOtherLOD(np, top):
    """True if np hangs under a level of detail that isn't the one shown."""
    child = np
    node = np.getParent()
    while not node.isEmpty() and node != top:
        if isinstance(node.node(), LODNode):
            lod = node.node()
            shown = lod.getForceSwitch() if lod.getForceSwitch() >= 0 else 0
            if node.node().findChild(child.node()) != shown:
                return True
        child = node
        node = node.getParent()
    return False


def _collapseLODs(np):
    """A level-of-detail switch held on one level (forceSwitch) is that level."""
    for lodNp in np.findAllMatches('**/+LODNode'):
        lod = lodNp.node()
        if lod.getForceSwitch() < 0:
            continue
        keep = lod.getForceSwitch()
        children = lodNp.getChildren()
        holder = lodNp.getParent().attachNewNode(lodNp.getName())
        holder.setTransform(lodNp.getTransform())
        holder.setState(lodNp.getState())
        for i in range(children.getNumPaths()):
            if i == keep:
                children[i].reparentTo(holder)
        lodNp.removeNode()


def flattenStatic(root, skip=(), statues=()):
    """Merge the still pictures under root into one flattened node,
    except what hangs under a node in skip, an animated character, or
    anything hidden. statues (posed characters under root) are baked into it
    and deleted. Returns (pieces before, pieces after)."""
    skip = [np for np in skip if np is not None and not np.isEmpty()]
    stage = root.attachNewNode('mapStill')
    before = _countGeoms(root)
    for actor in statues:
        if actor is None or actor.isEmpty():
            continue
        if bakeStatue(actor, stage) is not None:
            actor.delete()
            actor.removeNode()

    def kept(np):
        if _solidGeom(np) or np.isHidden() or np.isStashed():
            # Something walks on it, or it is hidden on purpose (a door's
            # hole) and may be shown later.
            return True
        for s in skip:
            if s == np or s.isAncestorOf(np):
                return True
        node = np.getParent()
        while not node.isEmpty() and node != root:
            if type(node.node()).__name__ == 'Character':
                return True
            node = node.getParent()
        return False

    for child in root.getChildren():
        if child == stage or isinstance(child.node(), CollisionNode):
            continue
        if any(child == s for s in skip) or child.isHidden() or child.isStashed():
            continue
        originals = _geomNodes(child)
        if not originals:
            continue
        keep = [kept(np) for np in originals]
        if all(keep):
            continue
        copy = child.copyTo(stage)
        copies = _geomNodes(copy)
        if len(copies) != len(originals):
            # Shouldn't happen; leave this one alone.
            copy.removeNode()
            continue
        # Only the pictures move: a piece's node stays (with anything
        # hanging under it, such as a wall's collisions), empty.
        for i in range(len(originals)):
            if keep[i]:
                copies[i].node().removeAllGeoms()
            else:
                originals[i].node().removeAllGeoms()
        for col in copy.findAllMatches('**/+CollisionNode'):
            col.removeNode()
        for character in copy.findAllMatches('**/+Character'):
            character.removeNode()
        _collapseLODs(copy)
        # Pictures don't need to be found by name once merged.
        for np in copy.findAllMatches('**/*'):
            np.clearTag('DNARoot')
            np.clearTag('DNACode')
    stage.clearModelNodes()
    stage.flattenStrong()
    return before, _countGeoms(root)


def _geomNodes(np):
    """np itself (if it is one) and every GeomNode under it, in order."""
    found = [np] if np.node().isGeomNode() else []
    found += list(np.findAllMatches('**/+GeomNode'))
    return found


def _countGeoms(np):
    total = 0
    for gn in np.findAllMatches('**/+GeomNode'):
        total += gn.node().getNumGeoms()
    return total
