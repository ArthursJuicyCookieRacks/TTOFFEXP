"""Building blocks for the Survival preview maps.

Every map here is put together in code from the game's own models and
textures: boxes, ramps, stairs, cylinders and cards textured with the
game's maps, and the game's props placed on top. Each piece can carry its
own collisions, made the way the game's levels make them: floors on the
floor bit (what the toons and cogs stand on and the ground rays find),
walls on the wall bit (what they bump into and the way-finding sees).

Stairs are a ramp to walk on under steps to look at, in a node whose name
says "stairs", so the cogs' landing code and NPCNav.onStairs know them.
"""

import math
import random

from panda3d.core import (BitMask32, CollisionBox, CollisionNode, CollisionPolygon, CollisionTube, Geom, GeomNode,
                          GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath, Point3,
                          SamplerState, Texture, TransparencyAttrib, Vec3, Vec4)

from toontown.toonbase import ToontownGlobals

WALL = ToontownGlobals.WallBitmask
FLOOR = ToontownGlobals.FloorBitmask
CAMERA = ToontownGlobals.CameraBitmask


def heading(h):
    """The unit vector a node with heading h faces (+y at 0)."""
    r = math.radians(h)
    return Vec3(-math.sin(r), math.cos(r), 0)


class Mesh:
    """Triangles collected for one texture and written out as one Geom."""

    def __init__(self):
        self.vdata = GeomVertexData('kit', GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
        self.vw = GeomVertexWriter(self.vdata, 'vertex')
        self.nw = GeomVertexWriter(self.vdata, 'normal')
        self.cw = GeomVertexWriter(self.vdata, 'color')
        self.tw = GeomVertexWriter(self.vdata, 'texcoord')
        self.tris = GeomTriangles(Geom.UHStatic)
        self.count = 0

    def quad(self, pts, uvs, color):
        a, b, c = Vec3(pts[0]), Vec3(pts[1]), Vec3(pts[2])
        n = (b - a).cross(c - a)
        if n.length() > 0:
            n.normalize()
        for p, uv in zip(pts, uvs):
            self.vw.addData3(p[0], p[1], p[2])
            self.nw.addData3(n)
            self.cw.addData4(color)
            self.tw.addData2(uv[0], uv[1])
        i = self.count
        self.tris.addVertices(i, i + 1, i + 2)
        if len(pts) == 4:
            self.tris.addVertices(i, i + 2, i + 3)
        self.count += len(pts)

    def node(self, name):
        geom = Geom(self.vdata)
        geom.addPrimitive(self.tris)
        node = GeomNode(name)
        node.addGeom(geom)
        return node


# How high the posts round any solid reach, at the least (MapKit.__posts).
POST_MIN_TOP = 2.6


class MapKit:

    def __init__(self, root):
        self.root = root
        self.visual = root.attachNewNode('visual')
        self.solid = root.attachNewNode('collisions')
        self.textures = {}
        self.models = {}
        self.meshes = {}
        self.extra = []
        # The outlines footprint() made solid (for tests).
        self.hulls = []

    # --- Textures and models ---

    def tex(self, path):
        if path is None:
            return None
        tex = self.textures.get(path)
        if tex is None:
            alpha = path.rsplit('.', 1)[0] + '_a.rgb'
            from panda3d.core import VirtualFileSystem, Filename
            vfs = VirtualFileSystem.getGlobalPtr()
            if path.endswith('.jpg') and vfs.exists(Filename('/' + alpha)) or vfs.exists(Filename(alpha)):
                tex = loader.loadTexture(path, alpha)
            else:
                tex = loader.loadTexture(path)
            tex.setWrapU(SamplerState.WM_repeat)
            tex.setWrapV(SamplerState.WM_repeat)
            tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
            tex.setMagfilter(SamplerState.FT_linear)
            self.textures[path] = tex
        return tex

    def mesh(self, texPath, group='static'):
        key = (texPath, group)
        m = self.meshes.get(key)
        if m is None:
            m = self.meshes[key] = Mesh()
        return m

    def model(self, path, pos=(0, 0, 0), h=0, p=0, r=0, scale=1.0, color=None, parent=None, keepCollisions=False, name=None):
        """One of the game's models, placed. Its own collisions go unless
        asked for: the map adds the solids it wants itself."""
        proto = self.models.get(path)
        if proto is None:
            proto = self.models[path] = loader.loadModel(path)
        np = proto.copyTo(parent or self.visual)
        if name:
            np.setName(name)
        np.setPos(Point3(*pos))
        np.setHpr(h, p, r)
        if isinstance(scale, (tuple, list)):
            np.setScale(*scale)
        else:
            np.setScale(scale)
        if color is not None:
            np.setColorScale(*color)
        if not keepCollisions:
            for c in np.findAllMatches('**/+CollisionNode'):
                c.removeNode()
        self.liftShadows(np)
        return np

    def liftShadows(self, np):
        """A model's drop shadow card lying at exactly its feet fights the
        ground it stands on (the ToonFest booths' square shadows flickered
        black): lift each a little and draw it over the ground."""
        for shadow in np.findAllMatches('**/*shadow*'):
            if not shadow.node().isGeomNode():
                continue
            shadow.setZ(render, shadow.getZ(render) + 0.06)
            shadow.setDepthOffset(2)

    def part(self, path, nodeName, pos=(0, 0, 0), h=0, scale=1.0, color=None, parent=None):
        """One named piece of a model (one tree out of trees.bam), placed."""
        proto = self.models.get(path)
        if proto is None:
            proto = self.models[path] = loader.loadModel(path)
        piece = proto.find('**/' + nodeName)
        if piece.isEmpty():
            return None
        np = (parent or self.visual).attachNewNode(nodeName)
        piece.copyTo(np).setPos(0, 0, 0)
        np.setPos(Point3(*pos))
        np.setH(h)
        np.setScale(scale)
        if color is not None:
            np.setColorScale(*color)
        for c in np.findAllMatches('**/+CollisionNode'):
            c.removeNode()
        self.liftShadows(np)
        return np

    def fit(self, np, size, axis=None, ground=True):
        """Scale a placed model so its biggest side (or the given axis 0/1/2)
        is `size` feet, and stand it on its base."""
        targetZ = np.getZ()
        np.setScale(1)
        bounds = np.getTightBounds(np.getParent())
        if not bounds:
            return np
        lo, hi = bounds
        dims = hi - lo
        cur = dims[axis] if axis is not None else max(dims[0], dims[1], dims[2])
        if cur <= 0:
            return np
        s = size / cur
        np.setScale(s)
        if ground:
            lo, hi = np.getTightBounds(np.getParent())
            np.setZ(np.getZ() + targetZ - lo[2])
        return np

    def actor(self, model, anims, pos=(0, 0, 0), h=0, scale=1.0, loop=None, rate=1.0, parent=None):
        from direct.actor.Actor import Actor
        a = Actor(model, anims)
        a.reparentTo(parent or self.root)
        a.setPos(Point3(*pos))
        a.setH(h)
        a.setScale(scale)
        if loop:
            a.loop(loop)
            a.setPlayRate(rate, loop)
        self.extra.append(a)
        return a

    # --- Collisions ---

    def __colNode(self, name, mask):
        node = CollisionNode(name)
        node.setIntoCollideMask(mask)
        node.setFromCollideMask(BitMask32.allOff())
        return node

    def floorPoly(self, pts, name='floor'):
        """A floor through the points (anticlockwise seen from above)."""
        node = self.__colNode(name, FLOOR)
        node.addSolid(CollisionPolygon(*[Point3(*p) for p in pts]))
        return self.solid.attachNewNode(node)

    def wallPoly(self, pts, name='wall'):
        node = self.__colNode(name, WALL | CAMERA)
        node.addSolid(CollisionPolygon(*[Point3(*p) for p in pts]))
        return self.solid.attachNewNode(node)

    # Upright posts make every solid here: a post always pushes a toon
    # (or a cog's body check) straight out sideways. A CollisionBox pushed
    # toons up, down or the wrong way, so they walked through crates and
    # booths from some sides, and two walls back to back cancel each
    # other out (Arthur, Farewell Fair).
    POST_RADIUS = 0.45
    POST_STEP = 0.8

    def __posts(self, node, pts, z0, z1, closed=True):
        r = self.POST_RADIUS
        # At least up past the middle of a toon's wall ball (1.4 feet up):
        # posts round a low box (a lamp post's foot) only reached its
        # bottom, pushed it up more than out, and a toon slid over them
        # into the ring and couldn't get out (Farewell Fair).
        top = max(z0 + POST_MIN_TOP, z1 - r)
        pairs = list(zip(pts, pts[1:] + pts[:1])) if closed else list(zip(pts[:-1], pts[1:]))
        for (ax, ay), (bx, by) in pairs:
            length = math.hypot(bx - ax, by - ay)
            count = max(1, int(length / self.POST_STEP + 0.999))
            for j in range(count + (0 if closed else 1)):
                t = float(j) / count
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                node.addSolid(CollisionTube(x, y, z0 + r, x, y, top, r))

    def wallBox(self, lo, hi, name='wallBox'):
        """Solid all round the box lo..hi (seen from above)."""
        node = self.__colNode(name, WALL | CAMERA)
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        self.__posts(node, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)
        return self.solid.attachNewNode(node)

    def wallTube(self, pos, radius, height=8.0, name='wallTube'):
        node = self.__colNode(name, WALL | CAMERA)
        x, y, z = pos
        node.addSolid(CollisionTube(x, y, z + 0.2, x, y, z + height, radius))
        return self.solid.attachNewNode(node)

    def wallSegment(self, a, b, z0, z1, name='wall', thick=0.6):
        """A thin solid wall from a to b (seen from above), z0 to z1, solid
        from both sides: capsules lying along it, stacked a foot or so
        apart."""
        a, b = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        if (b - a).length() < 0.01:
            return None
        node = self.__colNode(name, WALL | CAMERA)
        radius = max(0.3, thick * 0.5)
        z = max(z0, 0) + 0.6
        while True:
            node.addSolid(CollisionTube(Point3(a[0], a[1], z), Point3(b[0], b[1], z), radius))
            if z >= z1 - 0.3:
                break
            z = min(z1 - 0.3, z + 1.1)
        return self.solid.attachNewNode(node)

    def footprint(self, np, below=6.0, grow=0.0, height=None, skip=('shadow',), name='solid'):
        """Make a placed model solid where it really is: posts round the
        outline (seen from above) of its own geometry up to `below` feet
        over its base, so no invisible wall stands where the model
        doesn't, and nothing is left to walk through. Overhangs (canopies,
        roofs) above `below` don't count. Returns the outline's points."""
        from panda3d.core import GeomVertexReader
        pts = []
        base = None
        top = None
        for gnp in np.findAllMatches('**/+GeomNode'):
            if any(word in gnp.getName().lower() for word in skip) or gnp.isStashed():
                continue
            mat = gnp.getMat(self.root)
            node = gnp.node()
            for i in range(node.getNumGeoms()):
                vdata = node.getGeom(i).getVertexData()
                reader = GeomVertexReader(vdata, 'vertex')
                while not reader.isAtEnd():
                    p = mat.xformPoint(reader.getData3())
                    pts.append(p)
        if not pts:
            return None
        base = min(p[2] for p in pts)
        top = max(p[2] for p in pts)
        flat = [(p[0], p[1]) for p in pts if p[2] <= base + below]
        hull = convexHull(flat)
        if len(hull) < 3:
            return None
        if grow:
            cx = sum(p[0] for p in hull) / len(hull)
            cy = sum(p[1] for p in hull) / len(hull)
            out = []
            for x, y in hull:
                d = math.hypot(x - cx, y - cy) or 1.0
                out.append((x + (x - cx) / d * grow, y + (y - cy) / d * grow))
            hull = out
        node = self.__colNode(name, WALL | CAMERA)
        self.__posts(node, hull, base, base + (height or max(4.0, min(top - base, 14.0))))
        self.solid.attachNewNode(node)
        self.hulls.append(hull)
        return hull

    # --- Visual pieces ---

    def quad(self, pts, texPath, uvs, color=(1, 1, 1, 1), group='static'):
        self.mesh(texPath, group).quad([Point3(*p) for p in pts], uvs, Vec4(*color))

    def box(self, lo, hi, side=None, top=None, bottom=None, tile=10.0, color=(1, 1, 1, 1), topColor=None,
            collide=True, floorName='floor', faces='nsewt', group='static', sideTile=None):
        """A box from lo to hi, textured in world units (one copy of the
        texture every `tile` feet). collide: True gives a wall box and a
        floor on top; 'wall' only the walls; False nothing."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        st = sideTile or tile
        c = color
        tc = topColor or color
        if side:
            if 's' in faces:
                self.quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], side,
                          [(x0 / st, z0 / st), (x1 / st, z0 / st), (x1 / st, z1 / st), (x0 / st, z1 / st)], c, group)
            if 'n' in faces:
                self.quad([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], side,
                          [(-x1 / st, z0 / st), (-x0 / st, z0 / st), (-x0 / st, z1 / st), (-x1 / st, z1 / st)], c, group)
            if 'e' in faces:
                self.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], side,
                          [(y0 / st, z0 / st), (y1 / st, z0 / st), (y1 / st, z1 / st), (y0 / st, z1 / st)], c, group)
            if 'w' in faces:
                self.quad([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], side,
                          [(-y1 / st, z0 / st), (-y0 / st, z0 / st), (-y0 / st, z1 / st), (-y1 / st, z1 / st)], c, group)
        if top and 't' in faces:
            self.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], top,
                      [(x0 / tile, y0 / tile), (x1 / tile, y0 / tile), (x1 / tile, y1 / tile), (x0 / tile, y1 / tile)], tc, group)
        if bottom:
            self.quad([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], bottom,
                      [(x0 / tile, y1 / tile), (x1 / tile, y1 / tile), (x1 / tile, y0 / tile), (x0 / tile, y0 / tile)], c, group)
        if collide:
            # The wall box stops a little under the top, so a toon standing
            # on top touches only the floor.
            self.wallBox((x0, y0, z0), (x1, y1, max(z0 + 0.1, z1 - 0.6)))
            if collide is True:
                self.floorPoly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], floorName)

    def beam(self, a, b, thick, texPath, color=(1, 1, 1, 1), tile=4.0, group='static', depth=None):
        """A square beam from point a to point b (any direction), thick
        across, depth deep (defaults to thick). No collisions."""
        a, b = Vec3(*a), Vec3(*b)
        d = b - a
        length = d.length()
        if length < 0.01:
            return
        axis = d / length
        up = Vec3(0, 0, 1) if abs(axis[2]) < 0.95 else Vec3(1, 0, 0)
        s1 = axis.cross(up)
        s1.normalize()
        s2 = s1.cross(axis)
        s2.normalize()
        h1 = s1 * (thick / 2.0)
        h2 = s2 * ((depth or thick) / 2.0)
        corners = [h1 + h2, -h1 + h2, -h1 - h2, h1 - h2]
        for i in range(4):
            c0, c1 = corners[i], corners[(i + 1) % 4]
            self.quad([a + c0, a + c1, b + c1, b + c0], texPath,
                      [(0, 0), (thick / tile, 0), (thick / tile, length / tile), (0, length / tile)], color, group)
            self.quad([a + c1, a + c0, b + c0, b + c1], texPath,
                      [(0, 0), (thick / tile, 0), (thick / tile, length / tile), (0, length / tile)], color, group)

    def ground(self, x0, y0, x1, y1, texPath, tile=20.0, z=0.0, color=(1, 1, 1, 1), name='ground', collide=True):
        self.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], texPath,
                  [(x0 / tile, y0 / tile), (x1 / tile, y0 / tile), (x1 / tile, y1 / tile), (x0 / tile, y1 / tile)], color)
        if collide:
            self.floorPoly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], name)

    def card(self, center, w, hgt, h, texPath, color=(1, 1, 1, 1), z=0.0, twoSided=True, uv=((0, 0), (1, 0), (1, 1), (0, 1)), group='decal'):
        """An upright picture w wide and hgt high, facing heading h."""
        f = heading(h)
        right = Vec3(f[1], -f[0], 0)
        c = Point3(center[0], center[1], center[2] if len(center) > 2 else z)
        a = c - right * (w / 2.0)
        b = c + right * (w / 2.0)
        up = Vec3(0, 0, hgt)
        # The front faces back along f (the way the viewer looks from).
        self.quad([b, a, a + up, b + up], texPath, uv, color, group)
        if twoSided:
            self.quad([a, b, b + up, a + up], texPath, [uv[1], uv[0], uv[3], uv[2]], color, group)

    def decal(self, center, w, d, texPath, color=(1, 1, 1, 1), z=0.03, rot=0.0):
        """A picture lying on the ground (oil stains, puddles)."""
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = []
        for dx, dy in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            pts.append((center[0] + dx * cr - dy * sr, center[1] + dx * sr + dy * cr, z))
        self.quad(pts, texPath, [(0, 0), (1, 0), (1, 1), (0, 1)], color, 'decal')

    def cylinder(self, pos, radius, height, texPath, sides=16, color=(1, 1, 1, 1), tile=10.0, cap=None, collide=True,
                 group='static', radiusTop=None):
        x, y, z = pos
        rt = radius if radiusTop is None else radiusTop
        circ = 2 * math.pi * radius
        for i in range(sides):
            a0 = 2 * math.pi * i / sides
            a1 = 2 * math.pi * (i + 1) / sides
            p0 = (x + radius * math.cos(a0), y + radius * math.sin(a0), z)
            p1 = (x + radius * math.cos(a1), y + radius * math.sin(a1), z)
            p2 = (x + rt * math.cos(a1), y + rt * math.sin(a1), z + height)
            p3 = (x + rt * math.cos(a0), y + rt * math.sin(a0), z + height)
            u0 = circ * i / sides / tile
            u1 = circ * (i + 1) / sides / tile
            self.quad([p0, p1, p2, p3], texPath, [(u0, z / tile), (u1, z / tile), (u1, (z + height) / tile), (u0, (z + height) / tile)], color, group)
        if cap:
            for i in range(sides):
                a0 = 2 * math.pi * i / sides
                a1 = 2 * math.pi * (i + 1) / sides
                self.quad([(x, y, z + height), (x + rt * math.cos(a0), y + rt * math.sin(a0), z + height),
                           (x + rt * math.cos(a1), y + rt * math.sin(a1), z + height)], cap,
                          [(0.5, 0.5), (0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0)), (0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1))],
                          color, group)
        if collide:
            self.wallTube((x, y, z), max(radius, rt), height)

    def dome(self, pos, radius, texPath, rings=6, sides=16, color=(1, 1, 1, 1), group='static'):
        x, y, z = pos
        for j in range(rings):
            t0 = math.pi / 2 * j / rings
            t1 = math.pi / 2 * (j + 1) / rings
            for i in range(sides):
                a0 = 2 * math.pi * i / sides
                a1 = 2 * math.pi * (i + 1) / sides
                pts = []
                for t, a in ((t0, a0), (t0, a1), (t1, a1), (t1, a0)):
                    pts.append((x + radius * math.cos(t) * math.cos(a), y + radius * math.cos(t) * math.sin(a), z + radius * math.sin(t)))
                self.quad(pts, texPath, [(i / sides * 4, j / rings), ((i + 1) / sides * 4, j / rings),
                                         ((i + 1) / sides * 4, (j + 1) / rings), (i / sides * 4, (j + 1) / rings)], color, group)

    def stairs(self, start, h, width, rise, run=None, steps=None, side=None, tread=None, color=(1, 1, 1, 1),
               rails=True, railHeight=3.0, railTex=None, solidUnder=True, name='stairs'):
        """Stairs from start (the bottom step's front middle) going up
        toward heading h: `rise` feet up over `run` feet along. A ramp to
        walk on, steps to look at, a solid block under them and walls each
        side so nobody steps off."""
        run = run or rise * 1.6
        steps = steps or max(2, int(round(rise / 1.0)))
        f = heading(h)
        right = Vec3(f[1], -f[0], 0)
        s = Point3(*start)
        hw = width / 2.0
        stepRun = run / steps
        stepRise = rise / float(steps)
        tread = tread or side
        for i in range(steps):
            z0 = s[2] + stepRise * i
            z1 = s[2] + stepRise * (i + 1)
            front = s + f * (stepRun * i)
            back = s + f * (stepRun * (i + 1))
            fl, fr = front - right * hw, front + right * hw
            bl, br = back - right * hw, back + right * hw
            zt = z1
            # Riser.
            self.quad([Point3(fl[0], fl[1], z0), Point3(fr[0], fr[1], z0), Point3(fr[0], fr[1], zt), Point3(fl[0], fl[1], zt)], side,
                      [(0, 0), (width / 10.0, 0), (width / 10.0, stepRise / 10.0), (0, stepRise / 10.0)], color)
            # Tread.
            self.quad([Point3(fl[0], fl[1], zt), Point3(fr[0], fr[1], zt), Point3(br[0], br[1], zt), Point3(bl[0], bl[1], zt)], tread,
                      [(0, 0), (width / 10.0, 0), (width / 10.0, stepRun / 10.0), (0, stepRun / 10.0)], color)
        top = s + f * run
        bl, br = s - right * hw, s + right * hw
        tl, tr = top - right * hw, top + right * hw
        zb, zt = s[2], s[2] + rise
        if solidUnder:
            # Each side: a sloped panel down to the ground.
            for a, b in ((tl, bl), (br, tr)):
                za = zt if a is tl or a is tr else zb
                zb2 = zb if b is bl or b is br else zt
                self.quad([Point3(a[0], a[1], zb), Point3(b[0], b[1], zb), Point3(b[0], b[1], zb2), Point3(a[0], a[1], za)], side,
                          [(0, 0), (run / 10.0, 0), (run / 10.0, rise / 10.0), (0, rise / 10.0)], color)
            self.quad([Point3(tr[0], tr[1], zb), Point3(tl[0], tl[1], zb), Point3(tl[0], tl[1], zt), Point3(tr[0], tr[1], zt)], side,
                      [(0, 0), (width / 10.0, 0), (width / 10.0, rise / 10.0), (0, rise / 10.0)], color)
        # The ramp, in a node called stairs.
        node = CollisionNode(name)
        node.setIntoCollideMask(FLOOR)
        node.setFromCollideMask(BitMask32.allOff())
        node.addSolid(CollisionPolygon(Point3(bl[0], bl[1], zb + 0.05), Point3(br[0], br[1], zb + 0.05),
                                       Point3(tr[0], tr[1], zt), Point3(tl[0], tl[1], zt)))
        holder = self.solid.attachNewNode(name)
        holder.attachNewNode(node)
        # Walls along both sides (a rail to look at too).
        if rails:
            for a, b in ((bl, tl), (br, tr)):
                self.wallSegment(a, b, zb - 1, zt + railHeight, name='stairRail')
                if railTex:
                    self.quad([Point3(a[0], a[1], zb + railHeight), Point3(b[0], b[1], zt + railHeight),
                               Point3(b[0], b[1], zt + railHeight + 0.4), Point3(a[0], a[1], zb + railHeight + 0.4)], railTex,
                              [(0, 0), (run / 4.0, 0), (run / 4.0, 1), (0, 1)], color, 'decal')
                    self.quad([Point3(b[0], b[1], zt + railHeight), Point3(a[0], a[1], zb + railHeight),
                               Point3(a[0], a[1], zb + railHeight + 0.4), Point3(b[0], b[1], zt + railHeight + 0.4)], railTex,
                              [(0, 0), (run / 4.0, 0), (run / 4.0, 1), (0, 1)], color, 'decal')
                    for t in (0.0, 0.33, 0.66, 1.0):
                        p = a + (b - a) * t
                        zz = zb + (zt - zb) * t
                        self.box((p[0] - 0.2, p[1] - 0.2, zz), (p[0] + 0.2, p[1] + 0.2, zz + railHeight + 0.4), side=railTex,
                                 top=railTex, tile=2, color=color, collide=False)
        return top, zt

    def railing(self, pts, z, height=3.2, texPath=None, color=(1, 1, 1, 1), posts=6.0, solid=True, postTex=None):
        """A railing along the points at height z: a solid wall nobody walks
        through, a top bar and a mid bar between posts to look at."""
        for a, b in zip(pts[:-1], pts[1:]):
            if solid:
                self.wallSegment(a, b, z - 0.5, z + height + 1.5, name='railing')
            if texPath:
                a3, b3 = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
                d = b3 - a3
                length = d.length()
                n = max(1, int(length / posts))
                for bar in (height, height * 0.5):
                    for (p, q) in ((a3, b3), (b3, a3)):
                        self.quad([Point3(p[0], p[1], z + bar - 0.18), Point3(q[0], q[1], z + bar - 0.18),
                                   Point3(q[0], q[1], z + bar + 0.18), Point3(p[0], p[1], z + bar + 0.18)], texPath,
                                  [(0, 0), (length / 4.0, 0), (length / 4.0, 1), (0, 1)], color, 'decal')
                for i in range(n + 1):
                    p = a3 + d * (float(i) / n)
                    self.box((p[0] - 0.22, p[1] - 0.22, z), (p[0] + 0.22, p[1] + 0.22, z + height + 0.2), side=postTex or texPath,
                             top=postTex or texPath, tile=2, color=color, collide=False)

    # --- Finishing ---

    def finish(self):
        """Write every collected mesh into the scene, one node per texture,
        and flatten the static parts."""
        static = self.visual.attachNewNode('kitStatic')
        decals = self.visual.attachNewNode('kitDecals')
        # Other groups stay their own nodes: 'glow' (lamps, lit windows: not
        # dimmed by the night), 'belt' (conveyor treads that scroll), and so on.
        self.groups = {'static': static, 'decal': decals}
        for (texPath, group), mesh in self.meshes.items():
            parent = self.groups.get(group)
            if parent is None:
                parent = self.groups[group] = self.root.attachNewNode('kit-' + group)
                if group == 'glow':
                    parent.setColorScaleOff(10)
                    parent.setLightOff(10)
            np = parent.attachNewNode(mesh.node('kit-%s' % (texPath or 'plain')))
            tex = self.tex(texPath)
            if tex is not None:
                np.setTexture(tex, 1)
                if tex.getFormat() in (Texture.F_rgba, Texture.F_rgbm, Texture.F_rgba8, Texture.F_luminance_alpha):
                    np.setTransparency(TransparencyAttrib.MDual)
            else:
                np.setTextureOff(1)
            if group == 'decal':
                np.setTwoSided(False)
                np.setDepthOffset(1)
        self.meshes = {}
        decals.setTransparency(TransparencyAttrib.MDual)
        self.visual.flattenMedium()

    def destroy(self):
        for a in self.extra:
            try:
                a.cleanup()
                a.removeNode()
            except Exception:
                pass
        self.extra = []
        for m in self.models.values():
            m.removeNode()
        self.models = {}


def convexHull(points):
    """The convex outline round 2D points, anticlockwise."""
    pts = sorted(set((round(x, 2), round(y, 2)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def rng(seed):
    return random.Random(seed)
