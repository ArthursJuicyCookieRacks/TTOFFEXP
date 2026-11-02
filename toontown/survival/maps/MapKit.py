"""Building blocks for the Survival parody maps.

Everything placed here comes from the game's own resources: whole models
by path, DNA storage pieces by code (streets, walls, windows, props) and
DNA snippets generated the way the playgrounds and streets are.
"""

import io
import math

from panda3d.core import (AmbientLight, CardMaker, DirectionalLight, Fog, Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, NodePath, PointLight, SamplerState, TextNode, Texture,
                          TextureStage, Vec3, Vec4)

from toontown.dna import DNAParser
from toontown.dna.DNAStorage import DNAStorage
from toontown.toonbase import ToontownGlobals

BASE_STORAGE = ('phase_4/dna/storage.xml', 'phase_4/dna/storage_TT.xml', 'phase_4/dna/storage_TT_sz.xml',
                'phase_5/dna/storage_town.xml', 'phase_5/dna/storage_TT_town.xml')

_storage = {}


def getStorage(files=BASE_STORAGE):
    key = tuple(files)
    store = _storage.get(key)
    if store is None:
        store = DNAStorage()
        for name in files:
            loader.loadDNA(name).store(store)
        store.storeFont(ToontownGlobals.getInterfaceFont(), 'humanist')
        store.storeFont(ToontownGlobals.getSignFont(), 'mickey')
        store.storeFont(ToontownGlobals.getSuitFont(), 'suit')
        _storage[key] = store
    return store


def place(np, pos=(0, 0, 0), h=0, p=0, r=0, scale=None):
    np.setPosHpr(pos[0], pos[1], pos[2] if len(pos) > 2 else 0, h, p, r)
    if scale is not None:
        if isinstance(scale, (tuple, list)):
            np.setScale(*scale)
        else:
            np.setScale(scale)
    return np


class MapKit:

    def __init__(self, root, storageFiles=BASE_STORAGE):
        self.root = root
        self.store = getStorage(storageFiles)
        self._models = {}
        self.statues = []

    def destroy(self):
        for suit in self.statues:
            suit.delete()
        self.statues = []
        self.root.removeNode()

    # Models -------------------------------------------------------------
    def load(self, path):
        model = self._models.get(path)
        if model is None:
            model = loader.loadModel(path)
            self._models[path] = model
        return model

    def model(self, path, pos=(0, 0, 0), h=0, p=0, r=0, scale=None, parent=None, find=None, color=None):
        source = self.load(path)
        if find:
            source = source.find('**/' + find)
        np = source.copyTo(parent or self.root)
        place(np, pos, h, p, r, scale)
        if color is not None:
            np.setColorScale(*color)
        return np

    def prop(self, code, pos=(0, 0, 0), h=0, p=0, r=0, scale=None, parent=None, color=None):
        node = self.store.findNode(code)
        if not node:
            raise KeyError(code)
        np = node.copyTo(parent or self.root)
        place(np, pos, h, p, r, scale)
        if color is not None:
            np.setColorScale(*color)
        return np

    def dna(self, xml, parent=None):
        """Generate a snippet of DNA (the inside of a <group>)."""
        text = '<?xml version="1.0" encoding="utf-8"?>\n<scene zone="0"><group name="mapGroup">%s</group></scene>' % xml
        tree = DNAParser.parse(io.StringIO(text))
        node = tree.generate(self.store)
        np = NodePath(node)
        np.reparentTo(parent or self.root)
        return np

    def flat(self, x, y, h, width, walls, parent=None):
        """One street-style flat wall (DNA flat_building), facing -y before h.

        walls: list of dicts with code, height, color, and optional door,
        windows (code, count, color) and cornice (code, color).
        """
        def color(c):
            return '<color r="%s" g="%s" b="%s" a="1" />' % tuple(c[:3])
        parts = []
        for wall in walls:
            inner = color(wall.get('color', (1, 1, 1)))
            if wall.get('door'):
                inner += '<flat_door code="%s">%s</flat_door>' % (wall['door'], color(wall.get('doorColor', (1, 1, 1))))
            if wall.get('windows'):
                code, count, wc = wall['windows']
                inner += '<windows code="%s" count="%d">%s</windows>' % (code, count, color(wc))
            if wall.get('cornice'):
                code, cc = wall['cornice']
                inner += '<cornice code="%s">%s</cornice>' % (code, color(cc))
            parts.append('<wall height="%s" code="%s">%s</wall>' % (wall['height'], wall['code'], inner))
        xml = '<flat_building id="flat" width="%s"><pos x="%s" y="%s" z="0" /><nhpr h="%s" p="0" r="0" />%s</flat_building>' % (
            width, x, y, h, ''.join(parts))
        return self.dna(xml, parent)

    def estateHouse(self, path, pos, h, scale=1.0, color=None):
        """An estate house with its front door, set up the way DistributedHouse does."""
        from toontown.dna import DNADoor
        from toontown.estate import HouseGlobals
        house = self.model(path, pos=pos, h=h, scale=scale)
        door = self.store.findNode('door_double_round_ur')
        origin = house.find('**/door_origin')
        if door and not origin.isEmpty():
            origin.setHpr(90, 0, 0)
            origin.setScale(0.6, 0.6, 0.8)
            origin.setPos(origin, 0.5, 0, 0.0)
            doorNP = door.copyTo(origin)
            wood = HouseGlobals.stairWood
            DNADoor.DNADoor.setupDoor(doorNP, origin, origin, self.store, 'map', Vec4(wood[0], wood[1], wood[2], 1))
            for trigger in house.findAllMatches('**/door_trigger_*'):
                trigger.stash()
        if color is not None:
            for name in ('right', 'left', 'front', 'back'):
                for wall in house.findAllMatches('**/' + name):
                    wall.setColor(color[0], color[1], color[2], 1)
        return house

    def boxBuilding(self, pos, h, width, depth, front, side, back=None, roofTex=None, roofColor=None, parent=None):
        """A closed building of four flats, its front along local x facing -y."""
        group = (parent or self.root).attachNewNode('boxBuilding')
        place(group, pos, h)
        self.flat(0, 0, 0, width, front, group)
        self.flat(width, 0, 90, depth, side, group)
        self.flat(width, depth, 180, width, back or side, group)
        self.flat(0, depth, 270, depth, side, group)
        height = sum(float(w['height']) for w in front)
        if roofTex or roofColor:
            self.rect(0, 0, width, depth, z=height + 0.05, tex=roofTex, tile=10, color=roofColor, parent=group, name='roof')
        return group

    def texture(self, code_or_path, alpha=None):
        tex = self.store.findTexture(code_or_path)
        if not tex:
            tex = loader.loadTexture(code_or_path, alpha) if alpha else loader.loadTexture(code_or_path)
        tex.setWrapU(SamplerState.WM_repeat)
        tex.setWrapV(SamplerState.WM_repeat)
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        return tex

    def tinted(self, path, color, gray=True, crop=None):
        """A copy of a game texture turned grey and tinted (velvet from a judge's robe...)."""
        from panda3d.core import Filename, PNMImage
        key = (path, tuple(color), crop)
        cache = self.__dict__.setdefault('_tinted', {})
        if key in cache:
            return cache[key]
        src = loader.loadTexture(path)
        img = PNMImage()
        src.store(img)
        if crop:
            w, h = img.getXSize(), img.getYSize()
            x0, y0 = int(crop[0] * w), int(crop[1] * h)
            part = PNMImage(int(crop[2] * w) - x0, int(crop[3] * h) - y0)
            part.copySubImage(img, 0, 0, x0, y0, part.getXSize(), part.getYSize())
            img = part
        if gray:
            img.makeGrayscale()
            img.makeRgb()
        from panda3d.core import LColorf
        img *= LColorf(color[0], color[1], color[2], 1)
        tex = Texture(path + '-tinted')
        tex.load(img)
        tex.setWrapU(SamplerState.WM_repeat)
        tex.setWrapV(SamplerState.WM_repeat)
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        cache[key] = tex
        return tex

    # Simple geometry --------------------------------------------------------
    def rect(self, x0, y0, x1, y1, z=0.0, tex=None, tile=10.0, color=None, parent=None, name='rect'):
        cm = CardMaker(name)
        cm.setFrame(x0, x1, y0, y1)
        if tex is not None:
            cm.setUvRange((x0 / tile, y0 / tile), (x1 / tile, y1 / tile))
        np = (parent or self.root).attachNewNode(cm.generate())
        np.setP(-90)
        # setFrame works in the card's x/z plane; pitched flat, z becomes -y.
        np.setY(0)
        np.setZ(z)
        # After setP(-90) card z maps to +y: frame (x0..x1, y0..y1) lands right.
        if tex is not None:
            np.setTexture(self.texture(tex) if isinstance(tex, str) else tex, 1)
        if color is not None:
            np.setColor(*color)
        return np

    def wallQuad(self, a, b, z0, z1, tex=None, tile=10.0, color=None, parent=None, twoSided=True, name='wall', alpha=None, tileZ=None):
        """A vertical wall from point a to point b (x, y), seen from both sides."""
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        cm = CardMaker(name)
        cm.setFrame(0, length, z0, z1)
        if tex is not None:
            if tileZ:
                cm.setUvRange((0, 0), (length / tile, (z1 - z0) / tileZ))
            else:
                cm.setUvRange((0, z0 / tile), (length / tile, z1 / tile))
        np = (parent or self.root).attachNewNode(cm.generate())
        np.setPos(a[0], a[1], 0)
        np.setH(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
        if tex is not None:
            np.setTexture(self.texture(tex, alpha) if isinstance(tex, str) else tex, 1)
            if alpha:
                from panda3d.core import TransparencyAttrib
                np.setTransparency(TransparencyAttrib.MBinary)
        if color is not None:
            np.setColor(*color)
        if twoSided:
            np.setTwoSided(True)
        return np

    def wall(self, a, b, layers, gaps=(), parent=None, name='wall'):
        """A wall from a to b in layers [(z0, z1, tex, tile, color)], with
        doorways cut out: gaps [(from, to, top)] measured along the wall."""
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        group = (parent or self.root).attachNewNode(name)
        cuts = sorted(gaps)
        for z0, z1, tex, tile, color in layers:
            spans = []
            start = 0.0
            for g0, g1, top in cuts:
                spans.append((start, g0, z0, z1))
                if top < z1:
                    spans.append((g0, g1, max(z0, top), z1))
                start = g1
            spans.append((start, length, z0, z1))
            for s0, s1, lo, hi in spans:
                if s1 - s0 < 0.01 or hi - lo < 0.01:
                    continue
                pa = (a[0] + dx * s0, a[1] + dy * s0)
                pb = (a[0] + dx * s1, a[1] + dy * s1)
                q = self.wallQuad(pa, pb, lo, hi, tex=tex, tile=tile, color=color, parent=group, name=name)
                if tex is not None:
                    # Keep the pattern continuous along the wall.
                    from panda3d.core import TexMatrixAttrib, TextureStage
                    q.setTexOffset(TextureStage.getDefault(), s0 / tile, 0)
        return group

    def disc(self, cx, cy, radius, z=0.0, tex=None, tile=10.0, segments=48, color=None, parent=None, name='disc'):
        vdata = GeomVertexData(name, GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vw = GeomVertexWriter(vdata, 'vertex')
        nw = GeomVertexWriter(vdata, 'normal')
        tw = GeomVertexWriter(vdata, 'texcoord')
        vw.addData3(cx, cy, z)
        nw.addData3(0, 0, 1)
        tw.addData2(cx / tile, cy / tile)
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
            vw.addData3(x, y, z)
            nw.addData3(0, 0, 1)
            tw.addData2(x / tile, y / tile)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segments):
            tris.addVertices(0, i + 1, i + 2)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        np = (parent or self.root).attachNewNode(node)
        if tex is not None:
            np.setTexture(self.texture(tex) if isinstance(tex, str) else tex, 1)
        if color is not None:
            np.setColor(*color)
        return np

    def ring(self, cx, cy, r0, r1, z=0.0, tex=None, tile=10.0, segments=48, a0=0.0, a1=360.0, color=None, parent=None, name='ring'):
        vdata = GeomVertexData(name, GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vw = GeomVertexWriter(vdata, 'vertex')
        nw = GeomVertexWriter(vdata, 'normal')
        tw = GeomVertexWriter(vdata, 'texcoord')
        for i in range(segments + 1):
            a = math.radians(a0 + (a1 - a0) * i / segments)
            for r in (r0, r1):
                x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                vw.addData3(x, y, z)
                nw.addData3(0, 0, 1)
                tw.addData2(x / tile, y / tile)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segments):
            k = i * 2
            tris.addVertices(k, k + 1, k + 3)
            tris.addVertices(k, k + 3, k + 2)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        np = (parent or self.root).attachNewNode(node)
        np.setTwoSided(True)
        if tex is not None:
            np.setTexture(self.texture(tex) if isinstance(tex, str) else tex, 1)
        if color is not None:
            np.setColor(*color)
        return np

    # Collisions (for playing the map in Survival) ------------------------------
    def collideFloor(self, x0, y0, x1, y1, z=0.0, name='mapFloor'):
        """A flat floor toons and cogs stand on."""
        from panda3d.core import BitMask32, CollisionNode, CollisionPolygon, Point3
        node = CollisionNode(name)
        node.addSolid(CollisionPolygon(Point3(x0, y0, z), Point3(x1, y0, z), Point3(x1, y1, z), Point3(x0, y1, z)))
        node.setIntoCollideMask(ToontownGlobals.FloorBitmask)
        node.setFromCollideMask(BitMask32.allOff())
        return self.root.attachNewNode(node)

    # Where a toon's wall sphere sits when it stands on the ground: a ball
    # 1.4 feet round, its middle 1.4 feet up.
    TOON_SPHERE_Z = 1.4
    # The rail at that height is this thick round, so a cog's knee and waist
    # checks (0.9 and 1.9 feet up) meet it too.
    TOON_RAIL_RADIUS = 0.55
    # The next rail up starts here: out of reach of a toon's sphere on the
    # ground while it leans on the low rail, in reach of a cog's chest check.
    UPPER_RAIL_Z = 3.2

    def railHeights(self, height):
        """The heights of a wall's rails: one at the middle of a toon's
        sphere, the rest from the cogs' chest up to the top, a foot or so
        apart. Never two in reach of a toon's sphere at once: stacked rails
        a foot apart (0.6, 1.8, 3.0) made notches the sphere sank into, and
        the fluid pusher then held the toon there until it jumped (Arthur,
        Downsizer Drive's fences)."""
        heights = [min(self.TOON_SPHERE_Z, max(0.3, height - 0.3))]
        z = self.UPPER_RAIL_Z
        while z <= height - 0.3 + 1e-6:
            heights.append(z)
            z += 1.2
        if height - 0.3 > heights[-1] + 0.3:
            heights.append(height - 0.3)
        return heights

    def collideWall(self, a, b, height, parent=None, name='mapWall', thick=0.3, z0=0.0):
        """A wall from a to b that stops toons and cogs from both sides:
        capsules lying along it (railHeights). (Two polygons back to back
        don't work: a toon touching both is pushed both ways at once and
        walks through; a CollisionBox pushes toons the wrong way from one
        side.)"""
        from panda3d.core import BitMask32, CollisionCapsule, CollisionNode, Point3
        node = CollisionNode(name)
        thin = max(0.15, thick * 0.5)
        for i, z in enumerate(self.railHeights(height)):
            radius = max(thin, self.TOON_RAIL_RADIUS) if i == 0 else thin
            node.addSolid(CollisionCapsule(Point3(a[0], a[1], z0 + z), Point3(b[0], b[1], z0 + z), radius))
        node.setIntoCollideMask(ToontownGlobals.WallBitmask)
        node.setFromCollideMask(BitMask32.allOff())
        return (parent or self.root).attachNewNode(node)

    def solid(self, np, shrink=0.9, name='mapSolid', minSize=None):
        """Make a model without collisions of its own solid: a wall
        (collideWall) round the box it fills, turned with it. It used to
        be a ring of upright posts, but a toon could sink into the notch
        between two posts and stick there until it jumped (Arthur, the
        target on Downsizer Drive). minSize (feet) widens a flat model,
        such as the flower basket card."""
        from panda3d.core import Point3
        low, high = np.getTightBounds(np)
        if low is None:
            return None
        scale = max(abs(np.getScale()[0]), 0.001)
        mid = (low + high) * 0.5
        half = [(high[i] - low[i]) * 0.5 * shrink for i in range(2)]
        if minSize:
            half = [max(h, minSize * 0.5 / scale) for h in half]
        x0, x1 = mid[0] - half[0], mid[0] + half[0]
        y0, y1 = mid[1] - half[1], mid[1] + half[1]
        # The walls' rails are thick: pull the outline in by their radius,
        # so the model is as solid as before and no wider.
        inset = min(self.TOON_RAIL_RADIUS * 0.6 / scale, half[0] * 0.5, half[1] * 0.5)
        x0, x1, y0, y1 = x0 + inset, x1 - inset, y0 + inset, y1 - inset
        parent = self.root
        corners = [parent.getRelativePoint(np, Point3(x, y, low[2])) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        # From the ground the model stands on (its origin), not from the
        # bottom of its geometry: the watering cans reach ten feet under
        # the lawn, and their walls' toon-height rail went with them.
        base = max(min(c[2] for c in corners), parent.getRelativePoint(np, Point3(0, 0, 0))[2])
        top = max(parent.getRelativePoint(np, Point3(mid[0], mid[1], high[2]))[2] - base, 4.0)
        group = parent.attachNewNode(name)
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            self.collideWall((a[0], a[1]), (b[0], b[1]), top, parent=group, name=name, z0=base)
        return group

    def collideTube(self, pos, radius, height=4.0, name='mapTube'):
        from panda3d.core import BitMask32, CollisionNode, CollisionTube
        node = CollisionNode(name)
        node.addSolid(CollisionTube(0, 0, 0.2, 0, 0, height, radius))
        node.setIntoCollideMask(ToontownGlobals.WallBitmask)
        node.setFromCollideMask(BitMask32.allOff())
        path = self.root.attachNewNode(node)
        path.setPos(pos[0], pos[1], pos[2] if len(pos) > 2 else 0)
        return path

    # Text ----------------------------------------------------------------
    def text(self, text, pos=(0, 0, 0), h=0, scale=1.0, color=(1, 1, 1, 1), font='sign', parent=None,
             align=TextNode.ACenter, shadow=None, wordwrap=None):
        tn = TextNode('mapText')
        if font == 'sign':
            tn.setFont(ToontownGlobals.getSignFont())
        elif font == 'suit':
            tn.setFont(ToontownGlobals.getSuitFont())
        elif font == 'toon':
            tn.setFont(ToontownGlobals.getToonFont())
        else:
            tn.setFont(ToontownGlobals.getInterfaceFont())
        tn.setText(text)
        tn.setAlign(align)
        tn.setTextColor(*color)
        if shadow:
            tn.setShadow(0.05, 0.05)
            tn.setShadowColor(*shadow)
        if wordwrap:
            tn.setWordwrap(wordwrap)
        np = (parent or self.root).attachNewNode(tn.generate())
        place(np, pos, h, 0, 0, scale)
        np.setTwoSided(False)
        np.setDepthOffset(1)
        return np

    # Lighting ------------------------------------------------------------
    def lights(self, ambient=(0.5, 0.5, 0.5, 1), sun=(0.6, 0.6, 0.6, 1), sunHpr=(30, -50, 0)):
        al = AmbientLight('mapAmbient')
        al.setColor(Vec4(*ambient))
        aNp = self.root.attachNewNode(al)
        self.root.setLight(aNp)
        dl = DirectionalLight('mapSun')
        dl.setColor(Vec4(*sun))
        dNp = self.root.attachNewNode(dl)
        dNp.setHpr(*sunHpr)
        self.root.setLight(dNp)
        return aNp, dNp

    def pointLight(self, pos, color=(1, 0.8, 0.5, 1), atten=(1, 0, 0.002)):
        pl = PointLight('mapLamp')
        pl.setColor(Vec4(*color))
        pl.setAttenuation(Vec3(*atten))
        np = self.root.attachNewNode(pl)
        np.setPos(*pos)
        self.root.setLight(np)
        return np

    def stone(self, np):
        """Turn something to stone the way the estate's toon statues are made."""
        from panda3d.core import ConfigVariableBool, VBase4
        pipe = getattr(base, 'pipe', None)
        es = pipe is not None and 'ES' in pipe.getInterfaceName()
        if ConfigVariableBool('statue-single-texture', es).getValue():
            # OpenGL ES only draws the first texture stage: grey shading instead.
            np.setColor(VBase4(0.82, 0.78, 0.74, 1), 10)
            return
        np.setTexture(loader.loadTexture('phase_5.5/maps/smoothwall_1.jpg'), 100)
        np.setColor(VBase4(0.85, 0.83, 0.8, 1), 100)

    # Cogs used as set dressing -------------------------------------------------
    def cogStatue(self, name, pos, h=0, anim='neutral', frame=0, color=None, skeleton=False):
        """A cog that doesn't move: a test dummy, a statue, a prop."""
        from toontown.suit import Suit, SuitDNA
        suit = Suit.Suit()
        dna = SuitDNA.SuitDNA()
        dna.newSuit(name)
        suit.setDNA(dna)
        if skeleton:
            # makeSkeleton names the cog through SuitBase, which a bare Suit lacks.
            suit.getStyleDept = lambda: ''
            suit.getActualLevel = lambda: 1
            suit.makeSkeleton()
        try:
            suit.nametag3d.stash()
            suit.nametag.getNametag2d().setContents(0)
        except Exception:
            pass
        self.statues.append(suit)
        suit.reparentTo(self.root)
        suit.setPosHpr(pos[0], pos[1], pos[2] if len(pos) > 2 else 0, h, 0, 0)
        try:
            suit.pose(anim, frame)
        except Exception:
            pass
        if color is not None:
            suit.setColorScale(*color)
        return suit
