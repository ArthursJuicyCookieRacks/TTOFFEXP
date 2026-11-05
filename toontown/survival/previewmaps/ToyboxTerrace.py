"""Toybox Terrace: a playground put together from giant wooden toys.

A wide round plaza paved like a board game (cream tiles, a ring of
coloured squares round it like a game track, a spinner set in the middle).
A jack-in-the-box clock tower stands at the back, with Jack bobbing on his
spring over the clock. Round the plaza, toy-block buildings with ordinary
Toon-sized doors: Toon HQ (a toy fort), the Gag Shop, the Clothing Shop (a
dollhouse), the Pet Shop (a round toy drum), with the trolley and the
Party Gate. A little pond in the south-west corner has marbles set in its
rim and three docks. Three tunnels lead out: Wind-Up Way (a tin wind-up
box with a turning key), Loose Marble Lane (an arch of marbles) and
Building Block Boulevard (an arch of stacked blocks). A wall of giant ABC
blocks runs all round. Everything is on one level.

Cherry red, sky blue, golden yellow and warm cream, painted on the game's
own wood grain, with quiet cream between the bright bits.
"""

import math
import random

from panda3d.core import (NodePath, PNMImage, Point3, SamplerState, Texture, TextNode, TransparencyAttrib, Vec3, Vec4)

from toontown.survival.previewmaps.MapKit import heading, rng
from toontown.survival.previewmaps.PreviewMap import PreviewMap
from toontown.survival.previewmaps.ToyGeo import Geo, Part, signText

# The game's own hand-painted textures.
# The playground's grey wood grain, lightened (paint) so colours on it stay
# true: on the plain grain cream came out grey.
WOOD_SRC = 'phase_3.5/maps/wood_gray.jpg'
WOOD = 'gen:paint'
SOFT = 'gen:soft'
PLANK = 'phase_5.5/maps/floor_wood_neutral.jpg'
TILE = 'phase_4/maps/brick_floor_Ncont.jpg'
WALK = 'phase_3.5/maps/sidewalk_4cont_brown.jpg'
GRASS = 'phase_3.5/maps/grassTT.jpg'
WATER = 'phase_5.5/maps/terrain_water.jpg'
CONCRETE = 'phase_4/maps/concrete.jpg'
# Painted here (ToyboxTerrace.paint): marbles, the clock face, the dark
# inside of a tunnel.
MARBLES = ('gen:marble_red', 'gen:marble_blue', 'gen:marble_yellow', 'gen:marble_green')
CLOCK = 'gen:clock'
# Arthur's painted models (2026-11-05) for the pond, ducks, tops and key.
ART = 'phase_4/models/props/toybox_'
DARK = 'gen:tunnel_dark'
PLAIN = None

# The palette.
RED = (0.86, 0.22, 0.2, 1)
RED_D = (0.66, 0.14, 0.14, 1)
BLUE = (0.44, 0.7, 0.94, 1)
BLUE_D = (0.26, 0.48, 0.76, 1)
YELLOW = (1.0, 0.8, 0.26, 1)
YELLOW_D = (0.86, 0.6, 0.12, 1)
CREAM = (1.0, 0.94, 0.8, 1)
CREAM_D = (0.9, 0.82, 0.66, 1)
GREEN = (0.46, 0.76, 0.36, 1)
INK = (0.2, 0.16, 0.3, 1)
BRIGHT = (RED, BLUE, YELLOW)

PLAZA_R = 92.0
TRACK = (56.0, 68.0)
HALF = 170.0
CUT = 50.0
# The playground's outline (an octagon), anticlockwise.
OUTLINE = [(-HALF + CUT, -HALF), (HALF - CUT, -HALF), (HALF, -HALF + CUT), (HALF, HALF - CUT),
           (HALF - CUT, HALF), (-HALF + CUT, HALF), (-HALF, HALF - CUT), (-HALF, -HALF + CUT)]

TOWER = Point3(0, 128, 0)
# The tower's body: half-width at the foot and the top, height, how far
# it leans (feet at the top), twists (degrees) and bulges (feet).
TW0, TW1, TZ0, TH = 18.5, 16.0, 1.2, 42.0
TLEAN, TTWIST, TBULGE = 1.8, 3.0, 1.6
HQ = Point3(-118, 62, 0)
GAG = Point3(66, 126, 0)
PARTY = Point3(-66, 128, 0)
# The trolley stands back against the north-east wall, set into a hill as
# in Toontown Central; this is the middle of its platform's front.
TROLLEY = Point3(121, 121, 0)
CLOTHES = Point3(120, -64, 0)
PETS = Point3(-120, -64, 0)
POND = Point3(-104, -122, 0)
POND_R = (30.0, 21.0)
YARD = Point3(104, -118, 0)
# Tunnel mouths: (where, which way the mouth looks, street, theme).
TUNNELS = ((Point3(0, -HALF, 0), 0, 'Wind-Up Way', 'key'),
           (Point3(HALF, 0, 0), 90, 'Loose Marble Lane', 'marble'),
           (Point3(-HALF, 0, 0), -90, 'Building Block Boulevard', 'blocks'))
# Each tunnel sign's lettering (Arthur: pink, red and blue).
SIGN_LIFT = {'marble': 0.14, 'blocks': 0.14}
SIGN_INK = {'key': (0.93, 0.33, 0.62), 'marble': (0.86, 0.1, 0.12), 'blocks': (0.12, 0.36, 0.86)}
TUNNEL_GAP = 23.0


def facing(pos, target):
    """The heading that turns a building's front (its -y side) to target."""
    d = Vec3(pos[0] - target[0], pos[1] - target[1], 0)
    return math.degrees(math.atan2(-d[0], d[1]))


class _AnimProp:
    """An animated playground prop, put away with the map's actors."""

    def __init__(self, prop):
        self.prop = prop

    def cleanup(self):
        prop, self.prop = self.prop, None
        if prop is not None:
            prop.exit()
            prop.delete()

    def removeNode(self):
        pass


class ToyboxTerrace(PreviewMap):
    KEY = 'toybox_terrace'
    TITLE = 'Toybox Terrace'
    DESCRIPTION = 'A playground built from giant wooden toys. Even the clock tower pops out of a box.'
    PLAYER_START = (Point3(0, -118, 0), 0)
    MICKEY_SPOT = (Point3(0, 96, 0), 180)
    FISHERMAN_SPOT = (Point3(-76, -112, 0), 70)
    TRUNK_SPOT = (Point3(0, 0, 0), 0)
    REACH_SPAN = 175.0
    SPAWN_RING = (35.0, 240.0)
    NO_LANDING = ((TOWER, 30.0), (TROLLEY, 16.0), (Point3(0, 96, 0), 12.0), (Point3(-76, -112, 0), 12.0), (Point3(0, 0, 0), 10.0),
                  (POND, 34.0))
    # A soft summer dusk, not a dark night: the toys keep their colours.
    NIGHT_SCALE = Vec4(0.95, 0.93, 1.0, 1)
    SKY_FILE = 'phase_3.5/models/props/BR_sky'
    SKY_COLOR = Vec4(0.36, 0.34, 0.56, 1)
    BACKGROUND = Vec4(0.12, 0.1, 0.2, 1)
    FOG = ((0.34, 0.3, 0.46), 0.0012)
    # Soft and even: a lot of ambient, a gentle moon.
    LIGHT = ((0.88, 0.86, 0.9), (0.26, 0.26, 0.3), (-35, -55, 0))
    WALK_TESTS = [('plaza', (0, -110, 0), 0, 4.0)]
    PLAYER_VIEWS = {
        'start': ((0, -122, 0), 0, 6),
        'tower': ((0, 60, 0), 0, 20),
        'hq': ((-70, 38, 0), 115, 6),
        'gag': ((40, 80, 0), 20, 6),
        'pond': ((-70, -95, 0), 135, 2),
    }
    SHOTS = {
        'overview': ((0, -300, 190), (0, 0, 0)),
        'high': ((240, -240, 230), (0, 0, 0)),
        'tower': ((0, 30, 12), (0, 128, 36)),
        'plaza': ((0, -100, 10), (0, 40, 8)),
        'west': ((60, 10, 14), (-120, 20, 14)),
        'east': ((-60, -10, 14), (120, 10, 14)),
        'south': ((0, 60, 14), (0, -160, 10)),
        'pond': ((-60, -80, 16), (-104, -122, 0)),
    }

    def build(self):
        self.r = rng(2468)
        self.litNodes = []
        self.movers = []
        self.paint()
        k = self.kit
        self.g = Geo(lambda tex: k.mesh(tex))
        self.d = Geo(lambda tex: k.mesh(tex, 'decal'))
        self.letters = self.root.attachNewNode('toyLetters')
        self.signs = self.root.attachNewNode('toySigns')
        self.__ground()
        self.__plaza()
        self.__paths()
        self.__boundary()
        self.__tower()
        self.__dna()
        self.__hills()
        # Arthur's painted pond: the built one only for its collisions.
        self.collisionsOnly(self.__pond)
        self.artModel('marble_pond_with_docks', (POND[0], POND[1], 0))
        self.__ducks()
        self.__tops()
        self.__puzzles()
        self.__yard()
        self.__lamps()
        self.__trees()
        self.letters.flattenStrong()
        self.signs.flattenStrong()
        self.addTask(self.__animate, 'toys')

    # --- Painted textures ---

    def paint(self):
        """A few textures painted here, soft-edged like the game's own."""
        k = self.kit
        swirls = {'gen:marble_red': (0.9, 0.22, 0.2), 'gen:marble_blue': (0.25, 0.5, 0.95),
                  'gen:marble_yellow': (1.0, 0.75, 0.15), 'gen:marble_green': (0.3, 0.75, 0.35)}
        for key, col in swirls.items():
            k.textures[key] = self.__marbleTex(col)
        k.textures[CLOCK] = self.__clockTex()
        k.textures[DARK] = self.__darkTex()
        k.textures[WOOD] = self.__paintTex()
        k.textures[SOFT] = self.__softTex()

    def __tex(self, img, name):
        tex = Texture(name)
        tex.load(img)
        tex.setWrapU(SamplerState.WM_repeat)
        tex.setWrapV(SamplerState.WM_clamp)
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        tex.setMagfilter(SamplerState.FT_linear)
        return tex

    def __marbleTex(self, col):
        # Wrapped round a ball: u goes round, v from the south pole up.
        w, h = 128, 64
        img = PNMImage(w, h)
        base = (0.86, 0.92, 0.98)
        for y in range(h):
            v = y / float(h - 1)
            for x in range(w):
                u = x / float(w)
                # Two ribbons twisting round the glass.
                a = (u * 2.0 + v * 1.3) % 1.0
                ribbon = math.exp(-((min(a, 1 - a) - 0.0) ** 2) / 0.012) + 0.85 * math.exp(-((abs(a - 0.5)) ** 2) / 0.006)
                ribbon = min(1.0, ribbon)
                shade = 0.85 + 0.15 * math.sin(v * math.pi)
                r = (base[0] * (1 - ribbon) + col[0] * ribbon) * shade
                g = (base[1] * (1 - ribbon) + col[1] * ribbon) * shade
                b = (base[2] * (1 - ribbon) + col[2] * ribbon) * shade
                img.setXel(x, y, r, g, b)
        return self.__tex(img, 'marble')

    def __clockTex(self):
        n = 256
        img = PNMImage(n, n, 4)
        c = (n - 1) / 2.0
        for y in range(n):
            for x in range(n):
                dx, dy = (x - c) / c, (y - c) / c
                d = math.hypot(dx, dy)
                if d > 1.0:
                    img.setXelA(x, y, 0, 0, 0, 0)
                    continue
                if d > 0.88:
                    col = (0.26, 0.48, 0.78)
                elif d > 0.84:
                    col = (0.95, 0.75, 0.22)
                else:
                    col = (1.0, 0.95, 0.84)
                    # Hour marks: soft painted dots.
                    ang = math.atan2(dy, dx)
                    for i in range(12):
                        a = i * math.pi / 6
                        mx, my = 0.72 * math.cos(a), 0.72 * math.sin(a)
                        md = math.hypot(dx - mx, dy - my)
                        rad = 0.07 if i % 3 == 0 else 0.045
                        if md < rad:
                            col = (0.86, 0.22, 0.2) if i % 3 == 0 else (0.26, 0.48, 0.78)
                    # A faint painted shadow round the inside of the rim.
                    k = max(0.0, (d - 0.7) / 0.14) * 0.08
                    col = (col[0] - k, col[1] - k, col[2] - k)
                a = 1.0 if d < 0.985 else (1.0 - d) / 0.015
                img.setXelA(x, y, col[0], col[1], col[2], a)
        tex = self.__tex(img, 'clock')
        tex.setWrapU(SamplerState.WM_clamp)
        return tex

    def __paintTex(self):
        from panda3d.core import Filename
        img = PNMImage()
        src = loader.loadTexture(WOOD_SRC)
        if not src or not src.store(img):
            img = PNMImage(64, 64)
            img.fill(1, 1, 1)
        lo, hi = 1.0, 0.0
        for y in range(img.getYSize()):
            for x in range(img.getXSize()):
                v = img.getBright(x, y)
                lo, hi = min(lo, v), max(hi, v)
        span = max(0.01, hi - lo)
        for y in range(img.getYSize()):
            for x in range(img.getXSize()):
                v = (img.getBright(x, y) - lo) / span
                # Keep the painted strokes, but light: 0.8 .. 1.0.
                v = 0.8 + 0.2 * v
                img.setXel(x, y, v, v, v * 0.985)
        tex = self.__tex(img, 'paint')
        tex.setWrapV(SamplerState.WM_repeat)
        return tex

    def __darkTex(self):
        # Dark at the far end of a tunnel, lighter at the mouth (u 0..1).
        img = PNMImage(64, 4)
        for x in range(64):
            v = 0.42 * (1.0 - x / 63.0) ** 1.6 + 0.02
            for y in range(4):
                img.setXel(x, y, v * 0.95, v * 0.9, v * 1.05)
        tex = self.__tex(img, 'dark')
        tex.setWrapU(SamplerState.WM_clamp)
        return tex

    # --- Helpers ---

    def place(self, pos, h=0.0, p=0.0, r=0.0, scale=1.0, geo=None):
        return (geo or self.g).at(pos, (h, p, r), scale)

    def part(self, name):
        return Part(self.kit, name)

    def keep(self, part, pos=(0, 0, 0), hpr=(0, 0, 0), parent=None):
        np = part.make(parent or self.root)
        np.setPos(*pos)
        np.setHpr(*hpr)
        self.litNodes.append(np)
        return np

    def artModel(self, name, pos=(0, 0, 0), h=0.0, parent=None):
        """One of Arthur's painted Toybox Terrace models (resources-overlay
        phase_4/models/props/toybox_<name>.bam), lit like the built pieces."""
        np = loader.loadModel('%s%s.bam' % (ART, name))
        np.reparentTo(parent or self.root)
        np.setPos(*pos)
        np.setH(h)
        self.litNodes.append(np)
        return np

    def collisionsOnly(self, build):
        """Run a builder for its collisions only: what it draws is thrown
        away (a painted model stands in its place)."""
        k = self.kit
        meshes, signs, letters = k.meshes, self.signs, self.letters
        k.meshes = {}
        self.signs = self.letters = NodePath('discarded')
        try:
            build()
        finally:
            k.meshes = meshes
            self.signs, self.letters = signs, letters

    def solidOutline(self, pts, z0, z1, name='toySolid'):
        """Posts round a footprint (world x, y), like MapKit's wallBox."""
        from panda3d.core import CollisionNode, CollisionTube, BitMask32
        from toontown.survival.previewmaps.MapKit import WALL, CAMERA, POST_MIN_TOP
        node = CollisionNode(name)
        node.setIntoCollideMask(WALL | CAMERA)
        node.setFromCollideMask(BitMask32.allOff())
        r = self.kit.POST_RADIUS
        top = max(z0 + POST_MIN_TOP, z1 - r)
        for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
            length = math.hypot(bx - ax, by - ay)
            count = max(1, int(length / self.kit.POST_STEP + 0.999))
            for j in range(count):
                t = float(j) / count
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                node.addSolid(CollisionTube(x, y, z0 + r, x, y, top, r))
        return self.kit.solid.attachNewNode(node)

    def solidRect(self, pos, h, x0, y0, x1, y1, height=10.0, z=0.0):
        """Solid round a rectangle given in a building's own frame."""
        f = heading(h)
        right = Vec3(f[1], -f[0], 0)
        pts = []
        for lx, ly in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            p = Vec3(pos[0], pos[1], 0) + right * lx + f * ly
            pts.append((p[0], p[1]))
        return self.solidOutline(pts, z, z + height)

    def text(self, words, pos, h, scale, color, maxWidth=None, parent=None, p=0):
        return signText(parent or self.signs, words, pos, h, scale, color, maxWidth=maxWidth, p=p)

    def world(self, pos, h, local):
        """A point given in a building's frame, in the world."""
        f = heading(h)
        right = Vec3(f[1], -f[0], 0)
        return Point3(pos[0], pos[1], 0) + right * local[0] + f * local[1] + Vec3(0, 0, local[2] if len(local) > 2 else 0)

    def letterBlock(self, geo, size, color, letter=None, faces='nsewt', letterFaces='s', worldFrame=None, inset=None):
        """A painted ABC block, `size` feet on a side, standing at the
        origin of geo: a coloured block with a cream panel on each side and
        a big letter in the middle."""
        s = size
        h = s * 0.5
        trim = {RED: RED_D, BLUE: BLUE_D, YELLOW: YELLOW_D, CREAM: CREAM_D, GREEN: (0.3, 0.56, 0.24, 1)}.get(color, color)
        geo.trimBox((-h, -h, 0), (h, h, s), WOOD, color, trim, t=s * 0.08, tile=s, faces=faces)
        b = s * 0.17
        panel = CREAM if color != CREAM else (0.98, 0.86, 0.62, 1)
        e = 0.04
        for face in letterFaces:
            if face == 's':
                geo.quad(WOOD, [(-h + b, -h - e, b), (h - b, -h - e, b), (h - b, -h - e, s - b), (-h + b, -h - e, s - b)],
                         [(0, 0), (1, 0), (1, 1), (0, 1)], panel)
            elif face == 'n':
                geo.quad(WOOD, [(h - b, h + e, b), (-h + b, h + e, b), (-h + b, h + e, s - b), (h - b, h + e, s - b)],
                         [(0, 0), (1, 0), (1, 1), (0, 1)], panel)
            elif face == 'e':
                geo.quad(WOOD, [(h + e, -h + b, b), (h + e, h - b, b), (h + e, h - b, s - b), (h + e, -h + b, s - b)],
                         [(0, 0), (1, 0), (1, 1), (0, 1)], panel)
            elif face == 'w':
                geo.quad(WOOD, [(-h - e, h - b, b), (-h - e, -h + b, b), (-h - e, -h + b, s - b), (-h - e, h - b, s - b)],
                         [(0, 0), (1, 0), (1, 1), (0, 1)], panel)
            if letter and worldFrame is not None:
                pos, hh = worldFrame
                local = {'s': ((0, -h - 0.12, s * 0.27), 0), 'n': ((0, h + 0.12, s * 0.27), 180),
                         'e': ((h + 0.12, 0, s * 0.27), 90), 'w': ((-h - 0.12, 0, s * 0.27), -90)}[face]
                lp = geo.mat.xformPoint(Point3(*local[0]))
                # The block's own turn, read from its matrix.
                fwd = geo.mat.xformVec(Vec3(0, 1, 0))
                bh = math.degrees(math.atan2(-fwd[0], fwd[1]))
                self.text(letter, lp, bh + local[1], s * 0.62, trim, parent=self.letters)

    # --- Ground and plaza ---

    def __ground(self):
        k = self.kit
        k.ground(-HALF - 10, -HALF - 10, HALF + 10, HALF + 10, GRASS, tile=24, color=(0.78, 0.92, 0.56, 1), name='toyGround')
        # Grass to the horizon outside, a little lower.
        k.ground(-700, -700, 700, 700, GRASS, tile=30, z=-0.08, color=(0.62, 0.78, 0.46, 1), collide=False)

    def __disc(self, geo, r0, r1, tex, color, z, sides=72, a0=0.0, a1=360.0, tile=10.0):
        for i in range(sides):
            t0 = math.radians(a0 + (a1 - a0) * i / sides)
            t1 = math.radians(a0 + (a1 - a0) * (i + 1) / sides)
            pts = [(r0 * math.cos(t0), r0 * math.sin(t0), z), (r1 * math.cos(t0), r1 * math.sin(t0), z),
                   (r1 * math.cos(t1), r1 * math.sin(t1), z), (r0 * math.cos(t1), r0 * math.sin(t1), z)]
            geo.quad(tex, pts, [(p[0] / tile, p[1] / tile) for p in pts], color, [(0, 0, 1)] * 4)

    def __plaza(self):
        d = self.d
        # Cream tiles, a wooden curb round the edge.
        self.__disc(d, 0, PLAZA_R, TILE, (1.0, 0.95, 0.84, 1), 0.06, tile=9.0)
        self.__disc(d, PLAZA_R, PLAZA_R + 2.2, WOOD, RED, 0.08, tile=4.0)
        self.__disc(d, PLAZA_R - 0.6, PLAZA_R, WOOD, RED_D, 0.09, tile=4.0)
        # The game track: a ring of squares in soft colours, cream between
        # every few, with a little gap of grout round each.
        n = 40
        r0, r1 = TRACK
        soft = [(0.96, 0.66, 0.6, 1), (1.0, 0.95, 0.84, 1), (0.7, 0.84, 0.98, 1), (1.0, 0.95, 0.84, 1),
                (1.0, 0.86, 0.52, 1), (1.0, 0.95, 0.84, 1)]
        self.__disc(d, r0 - 0.5, r1 + 0.5, CONCRETE, (0.82, 0.74, 0.62, 1), 0.08, sides=80, tile=6.0)
        for i in range(n):
            a0 = 360.0 * i / n + 0.6
            a1 = 360.0 * (i + 1) / n - 0.6
            col = soft[i % len(soft)]
            self.__disc(d, r0, r1, CONCRETE, col, 0.1, sides=3, a0=a0, a1=a1, tile=6.0)
        # START, on the south side where the toons come in.
        self.text('START', (0, -(r0 + r1) / 2.0 - 2.4, 0.14), 0, 3.4, RED_D, p=-90)
        # The spinner set in the middle: four soft quarters and an arrow.
        quarters = [(0.96, 0.66, 0.6, 1), (0.7, 0.84, 0.98, 1), (1.0, 0.86, 0.52, 1), (0.74, 0.9, 0.66, 1)]
        for i, col in enumerate(quarters):
            self.__disc(d, 1.2, 15, CONCRETE, col, 0.1, sides=8, a0=90 * i + 45, a1=90 * (i + 1) + 45, tile=6.0)
        self.__disc(d, 15, 16.4, WOOD, CREAM_D, 0.11, sides=48)
        self.__disc(d, 0, 1.6, WOOD, RED_D, 0.13, sides=16)
        arrow = [(-0.9, -9), (0.9, -9), (0.9, 6), (2.6, 6), (0, 11.5), (-2.6, 6), (-0.9, 6)]
        a = self.d.at((0, 0, 0.12), (35, 0, 0))
        a.extrude(arrow, 0, 0.02, WOOD, RED_D, bottom=False)

    def __paths(self):
        d = self.d
        # Broad walks from the plaza to each tunnel and to the pond and yard
        # corners, all level.
        for pos, h, street, theme in TUNNELS:
            out = Vec3(pos[0], pos[1], 0)
            out.normalize()
            side = Vec3(-out[1], out[0], 0)
            a = out * (PLAZA_R - 2)
            b = Vec3(pos[0], pos[1], 0) + out * 6
            w = 13.0
            pts = [a - side * w, b - side * w, b + side * w, a + side * w]
            d.quad(WALK, [(p[0], p[1], 0.04) for p in pts], [(p[0] / 12.0, p[1] / 12.0) for p in pts], (1.0, 0.96, 0.86, 1),
                   [(0, 0, 1)] * 4)
        for corner in (POND, YARD):
            out = Vec3(corner[0], corner[1], 0)
            out.normalize()
            side = Vec3(-out[1], out[0], 0)
            a = out * (PLAZA_R - 2)
            b = Vec3(corner[0], corner[1], 0) - out * 18
            w = 10.0
            pts = [a - side * w, b - side * w, b + side * w, a + side * w]
            d.quad(WALK, [(p[0], p[1], 0.035) for p in pts], [(p[0] / 12.0, p[1] / 12.0) for p in pts], (1.0, 0.96, 0.86, 1),
                   [(0, 0, 1)] * 4)

    # --- The wall of blocks round the edge ---

    def __boundary(self):
        k = self.kit
        r = self.r
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        li = 0
        gaps = [(Vec3(p[0], p[1], 0), TUNNEL_GAP) for p, h, s, t in TUNNELS]
        pts = OUTLINE + OUTLINE[:1]
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            a, b = Vec3(ax, ay, 0), Vec3(bx, by, 0)
            length = (b - a).length()
            along = (b - a) / length
            inward = Vec3(-along[1], along[0], 0)
            h = math.degrees(math.atan2(-inward[0], inward[1])) + 180
            # The solid line, unbroken: the tunnels are walled off too, and a
            # gap left for each let a toon slip in beside the tunnel's face
            # and round behind the boundary.
            # Run on past each corner, and a post at the corner: at a bare
            # corner a sprinting toon (Sprint Soda, a slow frame) got out
            # between the two walls' ends.
            k.wallSegment(a - along * 4.0 - inward * 1.0, b + along * 4.0 - inward * 1.0, -1, 30, name='toyWall', thick=2.4)
            k.wallTube((a[0] - inward[0] * 1.0, a[1] - inward[1] * 1.0, -1), 2.5, 31, name='toyWallCorner')
            size = 12.0
            n = int(length / size)
            step = length / n
            for i in range(n):
                t = (i + 0.5) * step
                c = a + along * t - inward * 6.0
                if any((c - g).length() < half + 12 for g, half in gaps):
                    continue
                col = BRIGHT[(i + li) % 3] if r.random() < 0.8 else CREAM
                s = size * r.uniform(0.94, 1.02)
                geo = self.place((c[0], c[1], 0), h + r.uniform(-4, 4))
                self.letterBlock(geo, s, col, letters[li % 26], letterFaces='sn', worldFrame=((c[0], c[1]), h))
                li += 1
                # A second block on many, a third on a few, never quite square.
                if r.random() < 0.55:
                    s2 = size * r.uniform(0.7, 0.9)
                    col2 = BRIGHT[(i + li + 1) % 3]
                    g2 = self.place((c[0] + r.uniform(-1, 1), c[1] + r.uniform(-1, 1), s), h + r.uniform(-14, 14))
                    self.letterBlock(g2, s2, col2, letters[li % 26], letterFaces='sn', worldFrame=((c[0], c[1]), h))
                    li += 1
                    if r.random() < 0.25:
                        s3 = size * 0.55
                        g3 = self.place((c[0], c[1], s + s2), h + r.uniform(-25, 25))
                        self.letterBlock(g3, s3, CREAM, letters[li % 26], letterFaces='sn', worldFrame=((c[0], c[1]), h))
                        li += 1

    # --- The jack-in-the-box clock tower ---

    def __softTex(self):
        """Flat paint with soft, uneven brushing, like the game's painted
        buildings: no wood grain."""
        n = 128
        img = PNMImage(n, n)
        r = random.Random(7)
        blobs = [(r.uniform(0, n), r.uniform(0, n), r.uniform(10, 30), r.uniform(-1, 1)) for _ in range(26)]
        for y in range(n):
            for x in range(n):
                v = 0.0
                for bx, by, br, bs in blobs:
                    for ox in (-n, 0, n):
                        for oy in (-n, 0, n):
                            d2 = ((x - bx - ox) ** 2 + (y - by - oy) ** 2) / (br * br)
                            if d2 < 1:
                                v += bs * (1 - d2) ** 2
                # Faint upright brush strokes.
                v += 0.25 * math.sin(x * 0.9 + math.sin(y * 0.11) * 2.0)
                v = 0.95 + 0.035 * max(-1.0, min(1.0, v))
                img.setXel(x, y, v, v, v * 0.99)
        tex = self.__tex(img, 'soft')
        tex.setWrapV(SamplerState.WM_repeat)
        return tex

    def __towerPoint(self, side, u, v):
        """A point on the tower's body: side 0..3 (south, east, north,
        west), u -1..1 across it, v 0..1 up it. The body tapers, leans a
        little and bulges, like the playground's crooked buildings."""
        hw = TW0 + (TW1 - TW0) * v
        bulge = TBULGE * (1 - u * u) * max(0.0, math.sin(math.pi * v)) ** 0.8
        a = math.radians(-90 + 90 * side + TTWIST * v)
        out = Vec3(math.cos(a), math.sin(a), 0)
        along = Vec3(-out[1], out[0], 0)
        centre = Vec3(TLEAN * v, 0, TZ0 + (TH - TZ0) * v)
        return centre + out * (hw + bulge) + along * (u * hw)

    def __towerSurface(self, g, side, u0, u1, v0, v1, color, lift=0.0, nu=8, nv=10, shade=True, tex=None):
        """A patch of the body's skin, moved out by `lift` (a panel)."""
        tex = tex or SOFT
        P = self.__towerPoint

        def pt(u, v):
            p = P(side, u, v)
            if lift:
                du = P(side, u + 0.01, v) - P(side, u - 0.01, v)
                dv = P(side, u, v + 0.01) - P(side, u, v - 0.01)
                n = du.cross(dv)
                n.normalize()
                p = p + n * lift
            return p

        def nrm(u, v):
            du = P(side, u + 0.01, v) - P(side, u - 0.01, v)
            dv = P(side, u, v + 0.01) - P(side, u, v - 0.01)
            n = du.cross(dv)
            n.normalize()
            return n

        for i in range(nu):
            for j in range(nv):
                ua, ub = u0 + (u1 - u0) * i / nu, u0 + (u1 - u0) * (i + 1) / nu
                va, vb = v0 + (v1 - v0) * j / nv, v0 + (v1 - v0) * (j + 1) / nv
                k = 0.86 + 0.14 * (va + vb) * 0.5 if shade else 1.0
                col = (color[0] * k, color[1] * k, color[2] * k, 1)
                pts = [pt(ua, va), pt(ub, va), pt(ub, vb), pt(ua, vb)]
                uvs = [(ua * 1.5, va * 3), (ub * 1.5, va * 3), (ub * 1.5, vb * 3), (ua * 1.5, vb * 3)]
                g.quad(tex, pts, uvs, col, [nrm(ua, va), nrm(ub, va), nrm(ub, vb), nrm(ua, vb)])

    def __tower(self):
        k = self.kit
        x, y = TOWER[0], TOWER[1]
        g = self.place(TOWER)
        P = self.__towerPoint
        # A round, slightly lumpy plinth one step up.
        g.cyl(TW0 + 6.0, 1.2, SOFT, CREAM, sides=40, caps='t', tile=12)
        g.at((0, 0, 1.2), (0, 90, 0)).torus(TW0 + 6.0, 0.6, SOFT, CREAM_D, seg=40, sides=6)
        # The body: red sides with a cream panel on each, set in a little.
        for side in range(4):
            self.__towerSurface(g, side, -1, 1, 0, 1, RED)
            self.__towerSurface(g, side, -0.74, 0.74, 0.1, 0.9, CREAM, lift=0.12, nu=6, nv=8)
            # The panel's thick yellow rim, following the bulge.
            edge = ([(-0.74 + 1.48 * t / 8.0, 0.1) for t in range(9)] + [(0.74, 0.1 + 0.8 * t / 8.0) for t in range(1, 9)] +
                    [(0.74 - 1.48 * t / 8.0, 0.9) for t in range(1, 9)] + [(-0.74, 0.9 - 0.8 * t / 8.0) for t in range(1, 9)])
            rim = []
            for u, v in edge:
                p = P(side, u, v)
                du = P(side, u + 0.01, v) - P(side, u - 0.01, v)
                dv = P(side, u, v + 0.01) - P(side, u, v - 0.01)
                n = du.cross(dv)
                n.normalize()
                rim.append(p + n * 0.2)
            g.tube(rim, 0.75, SOFT, YELLOW, sides=8)
        # Fat blue corner posts and rims, following the lean and the twist.
        for side in range(4):
            post = [P(side, 1, v / 10.0) for v in range(11)]
            g.tube(post, 1.6, SOFT, BLUE, sides=10)
            g.sphere(post[0] + Vec3(0, 0, 0.4), 1.9, SOFT, BLUE_D, rings=6, sides=10)
            g.sphere(post[-1], 2.0, SOFT, YELLOW, rings=8, sides=12)
            for v in (0.0, 1.0):
                edge = [P(side, -1 + 2 * t / 12.0, v) for t in range(13)]
                g.tube(edge, 1.25 if v else 1.5, SOFT, BLUE if v else BLUE_D, sides=8)
        # The top, under the lid.
        top = [P(s, u, 1.0) for s in range(4) for u in (-1,)]
        g.quad(SOFT, [top[0], top[1], top[2], top[3]], [(0, 0), (1, 0), (1, 1), (0, 1)], RED_D)
        # The clock on the front, an alarm clock's: fat orange-gold bezel
        # and two bells on top.
        cv = 0.52
        cr = 10.5
        front = P(0, 0, cv)
        cy = front[1] - 0.6
        cz = front[2]
        cx = front[0]
        cg = g.at((cx, cy, cz), (0, 0, 0))
        cg.quad(CLOCK, [(-cr, 0, -cr), (cr, 0, -cr), (cr, 0, cr), (-cr, 0, cr)], [(0, 0), (1, 0), (1, 1), (0, 1)], (1, 1, 1, 1))
        g.at((cx, cy - 0.2, cz), (0, 90, 0)).torus(cr + 0.6, 1.5, SOFT, (0.98, 0.62, 0.16, 1), seg=40, sides=10)
        for sx in (-1, 1):
            a = math.radians(90 - 42 * sx)
            bx, bz = cx + (cr + 2.6) * math.cos(a), cz + (cr + 2.6) * math.sin(a)
            bell = g.at((bx, cy + 1.0, bz), (0, 0, -40 * sx))
            bell.sphere((0, 0, 0), (4.0, 3.2, 4.0), SOFT, YELLOW, rings=8, sides=16, lat=(0, 90))
            bell.cyl(4.0, 0.5, SOFT, YELLOW_D, z0=-0.25, sides=16, caps='b')
            bell.sphere((0, 0, 4.2), 0.9, SOFT, (0.98, 0.62, 0.16, 1), rings=6, sides=8)
        for i in range(12):
            a = math.radians(90 - i * 30)
            num = 12 if i == 0 else i
            self.text(str(num), (x + cx + 7.2 * math.cos(a), y + cy - 0.15, cz + 7.2 * math.sin(a) - 0.95), 0, 2.6, INK)
        # The hands turn with the real time (see __animate): fat and round-ended.
        minute = self.part('minuteHand')
        minute.geo.box((-0.45, -0.25, -0.8), (0.45, 0.0, 7.6), SOFT, INK, tile=2)
        minute.geo.sphere((0, -0.12, 7.6), 0.75, SOFT, INK, rings=5, sides=8)
        minute.geo.sphere((0, -0.3, 0), 1.0, SOFT, (0.98, 0.62, 0.16, 1), rings=6, sides=10)
        hour = self.part('hourHand')
        hour.geo.box((-0.7, -0.12, -0.8), (0.7, 0.12, 4.8), SOFT, RED_D, tile=2)
        hour.geo.sphere((0, 0, 4.8), 1.0, SOFT, RED_D, rings=5, sides=8)
        self.hourHand = self.keep(hour, (x + cx, y + cy - 0.3, cz))
        self.minuteHand = self.keep(minute, (x + cx, y + cy - 0.5, cz))
        # The crank on the east side, turning slowly.
        east = P(1, 0, 0.5)
        crank = self.part('crank')
        cgeo = crank.geo
        cgeo.at((0, 0, 0), (0, 0, 90)).cyl(1.1, 4.0, SOFT, YELLOW_D, sides=12)
        cgeo.at((0, 0, 0), (0, 0, 90)).cyl(2.2, 0.9, SOFT, YELLOW, sides=16, caps='tb')
        cgeo.box((3.4, -0.9, -0.9), (4.8, 0.9, 7.0), SOFT, YELLOW, tile=2)
        cgeo.at((4.1, 0, 7.0), (0, 0, 90)).cyl(0.8, 3.6, SOFT, YELLOW_D, sides=10)
        cgeo.sphere((8.0, 0, 7.0), (1.9, 1.9, 1.9), SOFT, RED, rings=8, sides=12)
        self.crank = self.keep(crank, (x + east[0] - 0.5, y + east[1], east[2]))
        # The lid, flung open backwards on its hinge, a little warped.
        hw1 = TW1
        hinge = P(2, 0, 1.0)
        lid = g.at((hinge[0], hinge[1], TH), (TTWIST, -118, 0))
        W = 2 * hw1
        lid.trimBox((-hw1 - 1.2, -W - 1.2, 0), (hw1 + 1.2, 1.2, 2.4), SOFT, CREAM, RED, t=1.4, tile=4, faces='nsewtb')
        for ex, ey0, ey1 in ((-hw1 - 1.2, -W - 1.2, 1.2), (hw1 + 1.2, -W - 1.2, 1.2)):
            lid.tube([(ex, ey0, 1.2), (ex, ey1, 1.2)], 1.3, SOFT, BLUE, sides=8)
        for ey in (-W - 1.2, 1.2):
            lid.tube([(-hw1 - 1.2, ey, 1.2), (hw1 + 1.2, ey, 1.2)], 1.3, SOFT, BLUE, sides=8)
        inner = lid.at((0, -W / 2, -0.06), (0, 180, 0))
        e = 3.0
        inner.quad(SOFT, [(-hw1 + e, -W / 2 + e, 0), (hw1 - e, -W / 2 + e, 0), (hw1 - e, W / 2 - e, 0), (-hw1 + e, W / 2 - e, 0)],
                   [(0, 0), (3, 0), (3, 3), (0, 3)], BLUE)
        star = [(math.cos(math.radians(90 + 36 * i)) * (1.0 if i % 2 == 0 else 0.45),
                 math.sin(math.radians(90 + 36 * i)) * (1.0 if i % 2 == 0 else 0.45)) for i in range(10)]
        for sx, sy, ss, rot in ((-6, -6, 4.0, 8), (6, 5, 4.6, -12), (-5, 7, 2.8, 20), (7, -7, 2.4, -6), (0, 0, 2.0, 30)):
            c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            pts = [(sx + (px * c - py * s_) * ss, sy + (px * s_ + py * c) * ss) for px, py in star]
            lid.at((0, -W / 2, -0.09), (0, 180, 0)).extrude(pts, 0, 0.02, SOFT, YELLOW, bottom=False)
        # Jack: a fat golden spring, a frilly collar, a toon-like head and
        # a floppy jester's hat. He bobs on the spring (__animate).
        jack = self.part('jack')
        j = jack.geo
        coil = []
        turns = 3.5
        steps = int(turns * 18)
        for i in range(steps + 1):
            t = i / float(steps)
            a = 2 * math.pi * turns * t
            rr = 5.4 - 0.8 * t
            coil.append((rr * math.cos(a), rr * math.sin(a), 0.8 + t * 13.0))
        j.tube(coil, 1.35, SOFT, (0.98, 0.78, 0.25, 1), sides=10)
        j.cyl(6.4, 1.4, SOFT, BLUE, z0=-0.6, sides=24, caps='tb')
        j.cyl(2.6, 3.0, SOFT, BLUE, z0=12.0, sides=16, caps='')
        # Collar: a ring of fat round frills, red and yellow by turns.
        for i in range(10):
            a = math.radians(36.0 * i)
            col = RED if i % 2 else YELLOW
            j.sphere((4.2 * math.cos(a), 4.2 * math.sin(a), 15.0), (2.6, 2.6, 1.5), SOFT, col, rings=6, sides=12)
        hz = 21.0
        # The head: a big egg, a toon's big eyes, a round red nose, a wide smile.
        j.sphere((0, 0, hz), (6.2, 5.8, 6.9), PLAIN, (1.0, 0.92, 0.84, 1), rings=14, sides=24)
        for sx in (-1, 1):
            # Eyes: tall white ovals with big black pupils looking at the plaza.
            j.sphere((2.0 * sx, -4.75, hz + 1.6), (1.55, 1.1, 2.2), PLAIN, (1, 1, 1, 1), rings=8, sides=12)
            j.sphere((1.75 * sx, -5.6, hz + 1.2), (0.85, 0.5, 1.15), PLAIN, (0.05, 0.05, 0.08, 1), rings=6, sides=10)
            j.sphere((1.5 * sx, -5.95, hz + 1.7), (0.25, 0.12, 0.3), PLAIN, (1, 1, 1, 1), rings=4, sides=6)
            # Rosy cheeks.
            j.sphere((4.1 * sx, -3.9, hz - 1.6), (1.4, 0.7, 1.0), PLAIN, (1.0, 0.6, 0.6, 1), rings=6, sides=10)
            # A diamond under each eye, like a jester's face paint.
            j.at((2.3 * sx, -5.35, hz - 1.5), (0, 0, 45)).box((-0.45, -0.1, -0.45), (0.45, 0.1, 0.45), PLAIN,
                                                            BLUE if sx < 0 else RED, faces='s')
        j.sphere((0, -6.3, hz - 0.6), 1.55, PLAIN, (0.92, 0.16, 0.16, 1), rings=8, sides=12)
        # Smile: a wide dark crescent with a pink tongue.
        smile = []
        for i in range(13):
            a = math.radians(200 + 140 * i / 12.0)
            smile.append((3.2 * math.cos(a), -5.0 - 0.6 * math.sin(math.radians(180 * i / 12.0)), hz - 2.2 + 2.2 * math.sin(a)))
        j.tube(smile, 0.55, PLAIN, (0.42, 0.06, 0.1, 1), sides=6)
        j.sphere((0, -5.0, hz - 4.15), (1.3, 0.5, 0.6), PLAIN, (0.95, 0.45, 0.5, 1), rings=6, sides=10)
        # Jester's hat: a band and three floppy points, bells on the tips.
        j.cyl(6.1, 2.0, SOFT, YELLOW, z0=hz + 3.4, sides=24, rTop=5.7, caps='')
        for ang, col, lift in ((-70, RED, 0.0), (70, BLUE, 0.0), (0, RED, 1.6)):
            horn = []
            for i in range(11):
                t = i / 10.0
                rx = 1.5 + 7.0 * math.sin(t * 1.5)
                rz = hz + 5.0 + lift + 6.5 * math.sin(t * 2.6) - t * t * 3.0
                a = math.radians(ang)
                horn.append((math.sin(a) * rx, math.cos(a) * rx * (1.0 if ang else 0.9) if ang == 0 else 0.0, rz))
                if ang:
                    horn[-1] = (math.copysign(rx, ang), 0.6, rz)
                else:
                    horn[-1] = (0.0, rx * 0.95, rz)
            for i in range(10):
                rad = 3.3 * (1 - i / 10.0) + 0.6
                j.tube(horn[i:i + 2], rad, SOFT, col, sides=12)
            j.sphere(horn[-1], 1.4, SOFT, YELLOW, rings=8, sides=12)
        self.jack = self.keep(jack, (x + TLEAN, y, TH + 0.6))
        self.jack.setScale(1.3)
        self.jackScale = 1.3
        # The box is solid; the plinth is a step up all round.
        hw = TW0 + TBULGE
        k.wallBox((x - hw, y - hw, 1.2), (x + hw, y + hw, TH))
        rr = TW0 + 6.0
        ring = [(x + rr * math.cos(math.radians(a)), y + rr * math.sin(math.radians(a)), 1.2) for a in range(0, 360, 30)]
        for i in range(len(ring)):
            k.floorPoly([(x, y, 1.2), ring[i], ring[(i + 1) % len(ring)]], 'towerPlinth')

    # --- Tunnels ---

    def __archBlock(self, g, hw, ar, height, depth, color, trim):
        """A wooden arch block: hw half-wide, with a half-round ar cut out of
        its underside, standing on its lower edge at z 0, front at y -d/2."""
        hd = depth / 2.0
        steps = 16
        arch = []
        for i in range(steps + 1):
            a = math.pi * i / steps
            arch.append((-ar * math.cos(a), ar * math.sin(a) * 0.9))
        for yy, sign in ((-hd, 1), (hd, -1)):
            for (x0, z0), (x1, z1) in zip(arch[:-1], arch[1:]):
                pts = [(x0, yy, z0), (x1, yy, z1), (x1, yy, ar * 0.9 + height * 0.55), (x0, yy, ar * 0.9 + height * 0.55)]
                if sign < 0:
                    pts = pts[::-1]
                g.quad(WOOD, pts, [(p[0] / 6, p[2] / 6) for p in pts], color)
            top = ar * 0.9 + height * 0.55
            for xa, xb in ((-hw, -ar), (ar, hw)):
                pts = [(xa, yy, 0), (xb, yy, 0), (xb, yy, top), (xa, yy, top)]
                if sign < 0:
                    pts = pts[::-1]
                g.quad(WOOD, pts, [(p[0] / 6, p[2] / 6) for p in pts], color)
        top = ar * 0.9 + height * 0.55
        g.box((-hw, -hd, 0), (hw, hd, top), WOOD, color, tile=6, faces='ewt')
        # The underside of the cut.
        for (x0, z0), (x1, z1) in zip(arch[:-1], arch[1:]):
            g.quad(WOOD, [(x0, hd, z0), (x1, hd, z1), (x1, -hd, z1), (x0, -hd, z0)], [(0, 0), (1, 0), (1, 1), (0, 1)], trim)
        g.quad(WOOD, [(-hw, -hd, 0), (-ar, -hd, 0), (-ar, hd, 0), (-hw, hd, 0)][::-1], [(0, 0), (1, 0), (1, 1), (0, 1)], trim)
        g.quad(WOOD, [(ar, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (ar, hd, 0)][::-1], [(0, 0), (1, 0), (1, 1), (0, 1)], trim)

    # --- The playground's own buildings, tunnels and trolley ---

    def __dnaXml(self):
        """The Toontown Central pieces, written as playground DNA so the
        game builds them exactly as in Toontown Central: the shops with
        their doors and signs, the trolley, the Party Gate and the three
        tunnels with their street signs."""
        out = []

        def place(pos, h):
            return '<pos x="%.3f" y="%.3f" z="%.3f" /><nhpr h="%.3f" p="0" r="0" />' % (pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, h)

        def front(pos):
            # A landmark building's front is its +y side.
            return facing(pos, (0, 0)) + 180

        def sign(words, color, scale=1.7, z=-0.5):
            return ('<sign><baseline code="mickey"><color r="%.3f" g="%.3f" b="%.3f" a="1" /><pos x="0" y="0" z="%.2f" />'
                    '<scale x="%.2f" y="1" z="%.2f" /><text>%s</text></baseline></sign>' % (color[0], color[1], color[2], z, scale, scale, words))

        # Its periscope and telescope as Toontown Central has them, in the
        # building's own frame.
        out.append('<landmark_building id="tb20:toon_landmark_hqTT_DNARoot" code="toon_landmark_hqTT" type="hq"><title>Toon HQ</title>%s'
                   '<prop name="animated_prop_HQPeriscopeAnimatedProp_DNARoot" code="animated_prop_HQPeriscopeAnimatedProp">'
                   '<pos x="7.17" y="-7.67" z="19.07" /><nhpr h="110" p="0" r="0" /><scale x="4" y="4" z="4" /></prop>'
                   '<prop name="animated_prop_HQTelescopeAnimatedProp_DNARoot" code="animated_prop_HQTelescopeAnimatedProp">'
                   '<pos x="7.003" y="0" z="13.191" /><nhpr h="168" p="81" r="0" /><scale x="4" y="4" z="4" /></prop>'
                   '</landmark_building>' % place(HQ, front(HQ)))
        out.append('<landmark_building id="sz19:toon_landmark_TT_gag_shop_DNARoot" code="toon_landmark_TT_gag_shop" type="gagshop">'
                   '<title>Gag Shop</title>%s<door code="door_double_square_ur"><color r="1" g="0.63" b="0.38" a="1" /></door>'
                   '</landmark_building>' % place(GAG, front(GAG)))
        out.append('<landmark_building id="sz21:toon_landmark_TT_clothes_shop_DNARoot" code="toon_landmark_TT_clothes_shop" type="clotheshop">'
                   '<title>Clothing Shop</title>%s<door code="door_double_clothesshop_ur"><color r="0.88" g="0.45" b="0.38" a="1" /></door>%s'
                   '</landmark_building>' % (place(CLOTHES, front(CLOTHES)), sign('Clothing Shop', (1, 0.611765, 0.423529))))
        out.append('<landmark_building id="sz22:toon_landmark_TT_pet_shop_DNARoot" code="toon_landmark_TT_pet_shop" type="petshop">'
                   '<title>Pet Shop</title>%s<door code="door_double_round_ur"><color r="1" g="0.87" b="0.38" a="1" /></door>'
                   '<sign><baseline code="mickey" width="14.2363" height="14.2363" flags="d"><color r="1" g="1" b="0" a="1" />'
                   '<pos x="-0.0715486" y="0" z="0.575594" /><scale x="1.58014" y="1" z="2.42354" /><text>PET SHOP</text></baseline></sign>'
                   '</landmark_building>' % place(PETS, front(PETS)))
        out.append('<prop name="prop_party_gate_DNARoot" code="prop_party_gate">%s</prop>' % place(PARTY, facing(PARTY, (0, 0))))
        # Tunnels: the model's mouth (tunnel_origin) is at (60, 95, 6.67)
        # in its own frame, looking +y.
        from panda3d.core import TextNode
        from toontown.toonbase import ToontownGlobals
        tn = TextNode('measure')
        tn.setFont(ToontownGlobals.getSignFont())
        # Toontown Central's widest street name that sits well on this plaque.
        maxW = tn.calcWidth('SILLY STREET') * 1.5 * 1.08
        for mouth, h, street, theme in TUNNELS:
            th = facing(mouth, (0, 0)) + 180
            f = heading(th)
            right = Vec3(f[1], -f[0], 0)
            origin = Vec3(mouth[0], mouth[1], 0) - right * 60.0 - f * 95.0
            # Curved round the plaque like the other playgrounds' signs
            # (Arthur), sized to stay inside its border: a long name is
            # squeezed across, as the Punchline Place sign is.
            sx = min(1.5, maxW / max(tn.calcWidth(street.upper()), 0.01))
            sz = min(1.5, max(sx, 1.15))
            # A long name sits a touch higher (Arthur).
            up = SIGN_LIFT.get(theme, 0.0)
            ink = '<color r="%.3f" g="%.3f" b="%.3f" a="1" />' % SIGN_INK[theme]
            out.append('<prop name="linktunnel_toy_%s_DNARoot" code="prop_safe_zone_tunnel">%s'
                       '<sign code="tunnel_sign_orange"><scale x="1.5" y="1" z="1.5" />'
                       '<baseline code="mickey" width="33.3333" height="33.3333">%s<pos x="0" y="0" z="%.3f" />'
                       '<scale x="%.3f" y="1" z="%.3f" /><text>%s</text></baseline>'
                       '<baseline code="mickey" width="44.0567" height="44.0567">%s<pos x="-0.08" y="0" z="%.3f" />'
                       '<scale x="0.8" y="1" z="0.8" /><text>TOYBOX TERRACE</text></baseline>'
                       '<baseline><pos x="0" y="0" z="1.75" /><scale x="2.5" y="1" z="2.5" /><graphic code="mickeySZ" /></baseline>'
                       '</sign></prop>'
                       % (theme, place((origin[0], origin[1], -6.6666), th), ink, -0.76 + up, sx, sz, street.upper(), ink, -1.98 + up))
        return ('<?xml version="1.0" encoding="utf-8"?><scene zone="2000"><group name="toyboxTerrace">'
                '<visgroup zone="2000:safe_zone" vis="2000:safe_zone">%s</visgroup></group></scene>' % ''.join(out))

    def __dna(self):
        import io
        from panda3d.core import Filename, NodePath, VirtualFileSystem
        from toontown.dna import DNAParser
        from toontown.dna.DNAStorage import DNAStorage
        from toontown.toonbase import ToontownGlobals
        vfs = VirtualFileSystem.getGlobalPtr()
        store = DNAStorage()
        for name in ('phase_4/dna/storage.xml', 'phase_4/dna/storage_TT.xml', 'phase_4/dna/storage_TT_sz.xml'):
            text = vfs.readFile(Filename('/' + name), True).decode('utf-8')
            DNAParser.parse(io.StringIO(text)).store(store)
        store.storeFont(ToontownGlobals.getInterfaceFont(), 'humanist')
        store.storeFont(ToontownGlobals.getSignFont(), 'mickey')
        store.storeFont(ToontownGlobals.getSuitFont(), 'suit')
        node = DNAParser.parse(io.StringIO(self.__dnaXml())).generate(store)
        geom = NodePath(node)
        geom.reparentTo(self.root)
        self.dnaGeom = geom
        self.dnaStore = store
        # As in a Survival playground: nothing leads anywhere, the doors'
        # black holes stay hidden, no cog buildings.
        for trigger in geom.findAllMatches('**/tunnel_trigger*') + geom.findAllMatches('**/door_trigger*'):
            trigger.stash()
        for hole in geom.findAllMatches('**/doorFrameHole*'):
            hole.hide()
        for flat in geom.findAllMatches('**/door_flat*'):
            suffix = flat.getName()[len('door_flat'):]
            building = flat.getParent()
            for leaf in ('leftDoor', 'rightDoor'):
                for door in building.findAllMatches('**/%s%s' % (leaf, suffix)):
                    door.hide()
        for origin in geom.findAllMatches('**/suit_building_origin'):
            origin.removeNode()
        # The moving bits Toontown Central has: Toon HQ's periscope and
        # telescope, the Pet Shop's fish.
        from direct.actor.Actor import Actor

        def building(pattern):
            # The DNA can make an empty node of the same name as well (Toon
            # HQ does): the building is the one with something in it.
            for np in geom.findAllMatches(pattern):
                if np.getTightBounds() is not None:
                    return np
            return geom.find(pattern)

        # Toon HQ's periscope and telescope look about, as SafeZoneLoader
        # runs them.
        from toontown.hood.HQPeriscopeAnimatedProp import HQPeriscopeAnimatedProp
        from toontown.hood.HQTelescopeAnimatedProp import HQTelescopeAnimatedProp
        for name, cls in (('**/animated_prop_HQPeriscopeAnimatedProp*', HQPeriscopeAnimatedProp),
                          ('**/animated_prop_HQTelescopeAnimatedProp*', HQTelescopeAnimatedProp)):
            node = geom.find(name)
            if node.isEmpty():
                continue
            prop = cls(node)
            prop.enter()
            self.kit.extra.append(_AnimProp(prop))
        pet = building('**/sz22:toon_landmark_TT_pet_shop_DNARoot')
        fish = Actor('phase_4/models/props/exteriorfish-zero', {'swim': 'phase_4/models/props/exteriorfish-swim'})
        fish.reparentTo(pet)
        fish.loop('swim')
        self.kit.extra.append(fish)
        # Each shop turned so its own door looks at the plaza's middle and
        # stands on its spot (the models' fronts face different ways).
        for root, spot in (('**/tb20:toon_landmark_hqTT_DNARoot', HQ), ('**/sz19:toon_landmark_TT_gag_shop_DNARoot', GAG),
                           ('**/sz21:toon_landmark_TT_clothes_shop_DNARoot', CLOTHES), ('**/sz22:toon_landmark_TT_pet_shop_DNARoot', PETS)):
            bldg = building(root)
            door = bldg.find('**/door_origin_0')
            if door.isEmpty():
                door = bldg.find('**/door_origin')
            bldg.setPosHpr(0, 0, 0, 0, 0, 0)
            dp = door.getPos(bldg)
            dh = door.getH(bldg)
            hb = facing(spot, (0, 0)) - dh
            bldg.setH(hb)
            off = bldg.getRelativeVector(geom, Vec3(1, 0, 0))
            w = geom.getRelativePoint(bldg, dp)
            bldg.setPos(spot[0] - w[0], spot[1] - w[1], 0)
        # The trolley: just the car, parked by the plaza like the one on
        # Downsizer Drive (Arthur), under a node named like a station so
        # Survival finds it for the way out.
        station = geom.attachNewNode('toy_trolley_station')
        proto = loader.loadModel('phase_4/models/modules/trolley_station_TT')
        car = proto.find('**/trolley_car').copyTo(station)
        proto.removeNode()
        for c in car.findAllMatches('**/+CollisionNode'):
            c.removeNode()
        th = facing(TROLLEY, (0, 0))
        car.setPosHpr(TROLLEY[0], TROLLEY[1], 0.05, th + 90, 0, 0)
        # Far away it switched to low-detail models missing pieces.
        for lod in car.findAllMatches('**/+LODNode'):
            lod.node().forceSwitch(0)
        low, high = car.getTightBounds(car)
        self.solidRect(TROLLEY, th + 90, low[0] * 0.9, low[1] * 0.9, high[0] * 0.9, high[1] * 0.9, height=high[2] * 0.8)
        # Marks the car as solid, so the way-out prompt shows all along its sides.
        car.attachNewNode('mapSolid')

    def __hill(self, center, h, radii, trees=0):
        """A grassy Toontown hill, like the ones the playgrounds' tunnels
        and trolley are set into."""
        g = self.place(center, h)
        g.sphere((0, 0, -2.0), radii, GRASS, (0.74, 0.9, 0.52, 1), rings=10, sides=28, uvScale=(10, 3), lat=(0, 90))
        r = self.r
        for i in range(trees):
            a = math.radians(r.uniform(20, 160))
            d = r.uniform(0.35, 0.7)
            lx, ly = math.cos(a) * radii[0] * d, math.sin(a) * radii[1] * d
            z = radii[2] * math.sqrt(max(0.0, 1 - (lx / radii[0]) ** 2 - (ly / radii[1]) ** 2)) - 2.5
            wp = self.world(center, h, (lx, ly))
            self.kit.part('phase_3.5/models/props/trees', r.choice(('prop_tree_small', 'prop_tree_large', 'prop_tree_fat')),
                          pos=(wp[0], wp[1], z), h=r.uniform(0, 360), scale=r.uniform(1.0, 1.4))

    def __hills(self):
        for mouth, h, street, theme in TUNNELS:
            out = Vec3(mouth[0], mouth[1], 0)
            out.normalize()
            th = facing(mouth, (0, 0))
            self.__hill(Vec3(mouth[0], mouth[1], 0) + out * 60.0, th, (60.0, 32.0, 32.0), trees=3)
            {'key': self.__keyGate, 'marble': self.__marbleGate, 'blocks': self.__blockGate}[theme](mouth, th)
            # Nobody goes into a tunnel: they lead nowhere here (Arthur).
            # A thick wall across the mouth, a little out in front of it.
            a = self.world(mouth, th, (-17.0, -1.5))
            b = self.world(mouth, th, (17.0, -1.5))
            self.kit.wallSegment(a, b, -1, 26, name='toyTunnelBlock', thick=2.4)

    def __keyGate(self, mouth, th):
        """Wind-Up Way: a giant winding key turning in the hill over the
        tunnel, as if the hill were a wind-up toy (Arthur's painted key and
        its brass plate)."""
        top = self.world(mouth, th, (0, 52, 0))
        key = self.artModel('wind_up_key', (top[0], top[1], 28.0), th)
        self.windKey = key.find('**/windKey')

    def __marbleGate(self, mouth, th):
        """Loose Marble Lane: an arch of big marbles over the path just
        in front of the tunnel, and a few rolled loose."""
        g = self.place(mouth, th)
        mr = 2.4
        ar = 14.0
        spring = 9.0
        y = -10.0
        ring = [(-ar - mr, z) for z in (mr, mr * 3 - 0.2)]
        for i in range(13):
            a = math.pi * i / 12
            ring.append((-(ar + mr) * math.cos(a), spring + (ar + mr) * math.sin(a)))
        ring += [(ar + mr, z) for z in (mr * 3 - 0.2, mr)]
        for i, (xx, zz) in enumerate(ring):
            g.sphere((xx, y, zz), mr, MARBLES[i % 4], (1, 1, 1, 1), rings=10, sides=16)
        g.sphere((0, y, spring + ar + mr * 3 + 1.0), 3.6, MARBLES[0], (1, 1, 1, 1), rings=12, sides=18)
        for sx in (-1, 1):
            wp = self.world(mouth, th, (sx * (ar + mr), y))
            self.kit.wallTube((wp[0], wp[1], 0), mr + 0.3, spring)
        for i, (lx, ly) in enumerate(((-ar - 9, -16), (ar + 8, -19), (ar + 4, -25))):
            wp = self.world(mouth, th, (lx, ly))
            self.g.sphere((wp[0], wp[1], 1.6), 1.6, MARBLES[(i + 1) % 4], (1, 1, 1, 1), rings=8, sides=14)
            self.kit.wallTube((wp[0], wp[1], 0), 1.7, 3.2)

    def __blockGate(self, mouth, th):
        """Building Block Boulevard: a toy block-set gateway over the path
        (round columns, an arch block, a triangle and cubes on top) and
        blocks stacked up each side of the tunnel."""
        r = self.r
        g = self.place(mouth, th)
        y = -10.0
        ar = 17.0
        colZ = 11.0
        for sx, col in ((-1, RED), (1, BLUE)):
            cg = g.at((sx * (ar + 3.2), y, 0), (0, 0, 0))
            cg.cyl(3.0, colZ, WOOD, col, sides=20, caps='t', tile=6)
            cg.at((0, 0, colZ * 0.5), (0, 0, 0)).torus(3.0, 0.35, WOOD, CREAM, seg=20, sides=6)
            wp = self.world(mouth, th, (sx * (ar + 3.2), y))
            self.kit.wallTube((wp[0], wp[1], 0), 3.2, colZ)
        self.__archBlock(g.at((0, y, colZ), (0, 0, 0)), ar + 5.0, ar, 4.0, 4.5, YELLOW, YELLOW_D)
        archTop = colZ + ar * 0.9 + 4.0 * 0.55
        tg = g.at((0, y, archTop), (0, 0, 0))
        tg.prism((-6, -2.25, 0), (6, 2.25, 6.0), WOOD, RED, gable=RED_D, tile=6)
        tg.at((0, 0, 0), (90, 0, 0)).prism((-2.25, -6, 0), (2.25, 6, 6.0), WOOD, RED, gable=RED, tile=6)
        for sx, col, s, letter in ((-1, BLUE, 4.6, 'B'), (1, GREEN, 4.2, 'K')):
            bh = th + r.uniform(-12, 12)
            wp = self.world(mouth, th, (sx * 16.5, y))
            self.letterBlock(self.place((wp[0], wp[1], archTop), bh), s, col, letter, letterFaces='sn', worldFrame=((wp[0], wp[1]), bh))
        # Stacks of blocks against the hill each side of the tunnel.
        abc = 'TOYBLOCKS'
        n = 0
        for sx in (-1, 1):
            z = 0.0
            for i, (sz, col) in enumerate(((8.0, RED if sx < 0 else YELLOW), (6.6, BLUE), (5.2, CREAM if sx < 0 else RED))):
                bh = th + r.uniform(-14, 14)
                wp = self.world(mouth, th, (sx * (31.0 + i * 0.6), -2.0))
                self.letterBlock(self.place((wp[0], wp[1], z), bh), sz, col, abc[n % len(abc)], letterFaces='sn',
                                 worldFrame=((wp[0], wp[1]), bh))
                n += 1
                z += sz
            wp = self.world(mouth, th, (sx * 31.0, -2.0))
            self.kit.wallTube((wp[0], wp[1], 0), 5.4, 12)

    # --- The pond ---

    def __pond(self):
        k = self.kit
        cx, cy = POND[0], POND[1]
        rx, ry = POND_R
        n = 72
        # The three docks' angles round the rim (degrees, 0 = east).
        docks = (20.0, 75.0, 140.0)
        # Wide enough for the biggest cogs to walk out after a toon (at 3.6
        # they crowded at the foot of a dock and never got onto it).
        dockW = 5.4
        # Each dock's line in from the rim: the rim opens only where a dock
        # crosses it (wider, and toons slipped past a dock into the water).
        dockLines = []
        for d in docks:
            a = math.radians(d)
            edge = Vec3(cx + rx * math.cos(a), cy + ry * math.sin(a), 0)
            inward = Vec3(cx, cy, 0) - edge
            inward.normalize()
            dockLines.append((edge, inward))
        rim = []
        for i in range(n):
            a = 2 * math.pi * i / n
            rim.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        # Water and a darker bed showing through at the edge.
        for i in range(n):
            a0 = 2 * math.pi * i / n
            a1 = 2 * math.pi * (i + 1) / n
            p0 = (cx + (rx - 0.6) * math.cos(a0), cy + (ry - 0.6) * math.sin(a0), 0.2)
            p1 = (cx + (rx - 0.6) * math.cos(a1), cy + (ry - 0.6) * math.sin(a1), 0.2)
            self.d.tri(WATER, [(cx, cy, 0.2), p0, p1], [(0, 0, 1)] * 3, [(cx / 20, cy / 20), (p0[0] / 20, p0[1] / 20), (p1[0] / 20, p1[1] / 20)],
                       (0.62, 0.92, 0.96, 1))
        # The rim: a thick cream curb, marbles set in it.
        g = self.g
        for i in range(n):
            a0 = 2 * math.pi * i / n
            a1 = 2 * math.pi * (i + 1) / n
            am = (a0 + a1) / 2
            mp = Vec3(cx + (rx + 1.5) * math.cos(am), cy + (ry + 1.5) * math.sin(am), 0)
            if any(abs((mp - e).cross(f)[2]) < dockW - 0.4 and (mp - e).dot(f) < 6 for e, f in dockLines):
                continue
            pts = []
            for a, rr in ((a0, 0), (a1, 0), (a1, 3), (a0, 3)):
                pts.append((cx + (rx + rr) * math.cos(a), cy + (ry + rr * ry / rx) * math.sin(a)))
            z = 1.6
            # Top.
            g.quad(WOOD, [(p[0], p[1], z) for p in pts], [(p[0] / 6, p[1] / 6) for p in pts], CREAM)
            # Inner and outer faces.
            g.quad(WOOD, [(pts[1][0], pts[1][1], 0), (pts[0][0], pts[0][1], 0), (pts[0][0], pts[0][1], z), (pts[1][0], pts[1][1], z)],
                   [(0, 0), (1, 0), (1, 0.3), (0, 0.3)], CREAM_D)
            g.quad(WOOD, [(pts[3][0], pts[3][1], 0), (pts[2][0], pts[2][1], 0), (pts[2][0], pts[2][1], z), (pts[3][0], pts[3][1], z)],
                   [(0, 0), (1, 0), (1, 0.3), (0, 0.3)], CREAM)
            if i % 3 == 0:
                mx = (pts[0][0] + pts[1][0] + pts[2][0] + pts[3][0]) / 4
                my = (pts[0][1] + pts[1][1] + pts[2][1] + pts[3][1]) / 4
                g.sphere((mx, my, 1.5), 1.25, MARBLES[(i // 3) % 4], (1, 1, 1, 1), rings=8, sides=12)
            k.wallSegment(((pts[0][0] + pts[3][0]) / 2, (pts[0][1] + pts[3][1]) / 2), ((pts[1][0] + pts[2][0]) / 2, (pts[1][1] + pts[2][1]) / 2),
                          -1, 3.5, name='pondRim', thick=2.6)
        # Docks: plank decks out over the water, posts down into it, low rails.
        self.dockEnds = []
        for d in docks:
            a = math.radians(d)
            edge = Vec3(cx + (rx + 1.5) * math.cos(a), cy + (ry + 1.5) * math.sin(a), 0)
            inward = Vec3(cx, cy, 0) - edge
            inward.normalize()
            h = math.degrees(math.atan2(-inward[0], inward[1]))
            dg = self.place((edge[0], edge[1], 0), h)
            L = 14.0
            w = dockW
            dg.box((-w, -4.0, 0.0), (w, L, 0.5), PLANK, (0.98, 0.86, 0.66, 1), tile=6)
            for yy in (2.5, L - 1.0):
                for sx in (-1, 1):
                    dg.at((sx * (w - 0.5), yy, -1.0), (0, 0, 0)).cyl(0.5, 3.4, WOOD, CREAM_D, sides=8, caps='t')
            # Low rails: red posts, a cream top rail.
            for sx in (-1, 1):
                for yy in (1.6, 1.6 + (L - 2.0) / 3, 1.6 + 2 * (L - 2.0) / 3, L - 0.4):
                    dg.box((sx * (w - 0.2) - 0.22, yy - 0.22, 0.5), (sx * (w - 0.2) + 0.22, yy + 0.22, 2.6), WOOD, RED, tile=2)
                dg.box((sx * (w - 0.2) - 0.3, 1.3, 2.5), (sx * (w - 0.2) + 0.3, L - 0.1, 2.9), WOOD, CREAM, tile=3)
            dg.box((-0.22, L - 0.62, 0.5), (0.22, L - 0.18, 2.6), WOOD, RED, tile=2)
            dg.box((-w + 0.2, L - 0.7, 2.5), (w - 0.2, L - 0.1, 2.9), WOOD, CREAM, tile=3)
            end = self.world((edge[0], edge[1]), h, (0, L - 2))
            self.dockEnds.append((end, h))
            corners = [self.world((edge[0], edge[1]), h, p) for p in ((-w, -4.0), (w, -4.0), (w, L), (-w, L))]
            k.floorPoly([(p[0], p[1], 0.5) for p in corners], 'pondDock')
            for sx in (-1, 1):
                k.wallSegment(self.world((edge[0], edge[1]), h, (sx * w, -1.0)), self.world((edge[0], edge[1]), h, (sx * w, L)), -1, 3.4,
                              name='dockRail', thick=1.2)
            k.wallSegment(self.world((edge[0], edge[1]), h, (-w, L)), self.world((edge[0], edge[1]), h, (w, L)), -1, 3.4, name='dockRail', thick=1.2)
        # A little sign.
        sp = self.world(POND, 0, (rx + 10, 10))
        sg = self.place(sp, -60)
        sg.box((-0.3, -0.3, 0), (0.3, 0.3, 5.5), WOOD, CREAM_D, tile=2)
        sg.trimBox((-5, -0.4, 5.0), (5, 0.2, 8.6), WOOD, CREAM, BLUE, t=0.6, faces='s')
        self.text('FISHING', self.world(sp, -60, (0, -0.8, 6.1)), -60, 1.9, BLUE_D)
        k.wallTube((sp[0], sp[1], 0), 0.6, 6)

    # --- Props ---

    def __duck(self, name):
        """A wind-up duck: yellow body, orange beak, a key in its back."""
        part = self.part(name)
        g = part.geo
        g.sphere((0, 0, 3.2), (2.6, 3.6, 2.4), WOOD, YELLOW, rings=10, sides=18)
        g.sphere((0, -3.6, 3.6), (1.0, 1.0, 1.2), WOOD, YELLOW, rings=6, sides=10)
        g.sphere((0, 3.0, 4.6), (1.3, 1.4, 0.8), WOOD, YELLOW_D, rings=6, sides=10)
        g.sphere((0, 2.2, 6.9), 2.3, WOOD, YELLOW, rings=10, sides=16)
        g.sphere((0, 4.5, 6.5), (1.2, 1.7, 0.42), WOOD, (1.0, 0.55, 0.15, 1), rings=6, sides=10)
        g.sphere((0, 4.4, 6.0), (1.0, 1.4, 0.3), WOOD, (0.95, 0.48, 0.12, 1), rings=6, sides=10)
        # A tail flicked up, and orange feet on the base.
        g.at((0, -3.4, 4.2), (0, 35, 0)).cyl(1.4, 2.6, WOOD, YELLOW, sides=12, rTop=0.2, caps='')
        for sx in (-1, 1):
            g.sphere((sx * 1.0, 2.6, 1.35), (0.9, 1.3, 0.2), WOOD, (1.0, 0.55, 0.15, 1), rings=4, sides=10)
        for sx in (-1, 1):
            g.sphere((sx * 1.3, 3.6, 7.7), (0.36, 0.36, 0.5), PLAIN, INK, rings=4, sides=8)
            g.sphere((sx * 2.4, -0.2, 3.6), (0.5, 2.2, 1.2), WOOD, YELLOW_D, rings=6, sides=10)
        # Wheels and a base, like a pull toy.
        g.box((-1.8, -2.4, 0.9), (1.8, 2.4, 1.3), WOOD, RED, tile=3)
        for yy in (-1.6, 1.6):
            for sx in (-1, 1):
                g.at((sx * 1.9, yy, 0.9), (0, 0, 90)).cyl(0.9, 0.5, WOOD, BLUE, z0=-0.25, sides=12, caps='tb')
        key = self.part(name + 'Key')
        kg = key.geo
        kg.at((0, 0, 0), (0, 90, 0)).cyl(0.25, 1.4, WOOD, YELLOW_D, sides=8, caps='')
        for sx in (-1, 1):
            kg.at((sx * 0.9, -1.6, 0), (0, 90, 0)).torus(0.7, 0.22, WOOD, YELLOW_D, seg=12, sides=5)
        return part, key

    def __ducks(self):
        self.ducks = []
        for i, (x, y, h) in enumerate(((-42, -40, 110), (36, 70, -150), (-70, -96, 160))):
            np = self.artModel('wind_up_duck', (x, y, 0), h)
            knp = np.find('**/duck_key')
            self.ducks.append((np, knp, Point3(x, y, 0), h, i * 1.7))
            self.kit.wallTube((x, y, 0), 3.0, 5)

    def __top(self, name, colors):
        part = self.part(name)
        g = part.geo
        g.cyl(0.25, 1.2, WOOD, CREAM_D, sides=8, rTop=0.9, caps='')
        g.cyl(0.9, 2.8, WOOD, colors[0], z0=1.2, sides=20, rTop=4.0, caps='')
        g.cyl(4.0, 1.0, WOOD, colors[1], z0=4.0, sides=20, caps='')
        g.at((0, 0, 4.5), (0, 0, 0)).torus(4.0, 0.5, WOOD, colors[1], seg=24, sides=6)
        g.cyl(4.0, 2.4, WOOD, colors[2], z0=5.0, sides=20, rTop=1.0, caps='t')
        g.cyl(0.55, 2.6, WOOD, colors[0], z0=7.4, sides=10, caps='t')
        g.sphere((0, 0, 10.0), 0.75, WOOD, colors[1], rings=6, sides=10)
        # Painted stripes so the spin shows.
        for i in range(6):
            a = 60.0 * i
            g.at((0, 0, 5.02), (a, 0, 0)).quad(WOOD, [(0.6, -0.4, 2.0), (3.9, -0.7, 0.04), (3.9, 0.7, 0.04), (0.6, 0.4, 2.0)],
                                               [(0, 0), (1, 0), (1, 1), (0, 1)], CREAM)
        return part

    def __tops(self):
        self.tops = []
        spots = ((86, -96, (RED, YELLOW, BLUE)), (118, -128, (BLUE, CREAM, RED)), (-30, 52, (YELLOW, RED, BLUE)),
                 (52, -48, (BLUE, YELLOW, RED)))
        for i, (x, y, cols) in enumerate(spots):
            holder = self.root.attachNewNode('topHolder%d' % i)
            holder.setPos(x, y, 0)
            # Arthur's painted tops, in the same colours as these spots'.
            tops = self.artModel('spinning_tops', parent=holder)
            np = tops.find('**/spinning_top_%d' % (i + 1))
            np.wrtReparentTo(holder)
            np.setPos(0, 0, 0)
            tops.removeNode()
            self.litNodes.remove(tops)
            self.litNodes.append(np)
            self.tops.append((holder, np, i * 2.1, 1.0 + 0.25 * i))
            self.kit.wallTube((x, y, 0), 3.6, 9)

    def __puzzle(self, size, knobs):
        """A jigsaw piece outline: a square with knobs out (+1), sockets in
        (-1) or flat (0) on each side (south, east, north, west)."""
        s = size / 2.0
        pts = []
        corners = [(-s, -s), (s, -s), (s, s), (-s, s)]
        for side in range(4):
            a = corners[side]
            b = corners[(side + 1) % 4]
            ax, ay = a
            bx, by = b
            dx, dy = (bx - ax) / size, (by - ay) / size
            nx, ny = dy, -dx
            kind = knobs[side]
            pts.append(a)
            if kind == 0:
                continue
            kr = size * 0.17
            neck = size * 0.1
            mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
            out = kind * 1.0
            pts.append((mx - dx * neck, my - dy * neck))
            # The knob: most of a circle beyond the neck.
            cxk = mx + nx * out * kr * 1.1
            cyk = my + ny * out * kr * 1.1
            base = math.atan2(-ny * out, -nx * out)
            for j in range(1, 16):
                ang = base + (math.radians(40) + math.radians(280) * j / 16.0) * (1 if out > 0 else -1)
                pts.append((cxk + kr * math.cos(ang), cyk + kr * math.sin(ang)))
            pts.append((mx + dx * neck, my + dy * neck))
        return pts

    def __puzzles(self):
        r = self.r
        # A few lying flat in the grass like stepping stones, two standing
        # fitted together by the Pet Shop path.
        flat = ((-74, -30, 20, RED, (1, -1, 0, 1)), (78, 22, -35, BLUE, (0, 1, -1, 1)), (-20, -104, 10, YELLOW, (-1, 1, 1, 0)),
                (60, 96, 70, GREEN, (1, 0, -1, -1)))
        for x, y, h, col, knobs in flat:
            poly = self.__puzzle(10.0, knobs)
            self.place((x, y, 0.03), h).extrude(poly, 0, 0.35, WOOD, col, tile=10)
        for (x, y, h, col, knobs, dx) in ((-82, -96, 30, BLUE, (0, 1, 0, 0), -4.5), (-82, -96, 30, RED, (0, 0, 0, -1), 4.5)):
            poly = self.__puzzle(9.0, knobs)
            wp = self.world((x, y), h, (dx, 0))
            self.place((wp[0], wp[1], 0), h, 90, 0).at((0, 4.6, 0), (0, 0, 0)).extrude(poly, -0.6, 0.6, WOOD, col, tile=10)
        self.kit.wallSegment(self.world((-82, -96), 30, (-9, 0)), self.world((-82, -96), 30, (9, 0)), -1, 9, name='puzzle', thick=1.4)

    def __yard(self):
        """The south-east corner: a toy yard with a few big blocks to sit on."""
        r = self.r
        blocks = ((132, -92, 6.5, RED, 'T', 0), (138, -100, 6.0, BLUE, 'O', 0), (134, -96, 5.0, YELLOW, 'Y', 6.5))
        for x, y, s, col, letter, z in blocks:
            hh = facing((x, y), (0, 0)) + r.uniform(-15, 15)
            g = self.place((x, y, z), hh)
            self.letterBlock(g, s, col, letter, letterFaces='sn', worldFrame=((x, y), hh))
        self.kit.wallTube((135, -96, 0), 8.0, 12)

    def __lamps(self):
        # The playground's own lamp posts round the plaza.
        # Between the walks, never on one.
        for deg in (14, 45, 103, 135, 166, 194, 250, 290, 321, 346):
            a = math.radians(deg)
            x, y = (PLAZA_R + 5) * math.cos(a), (PLAZA_R + 5) * math.sin(a)
            if any((Vec3(x, y, 0) - Vec3(p[0], p[1], 0)).length() < 30 for p in (TROLLEY, HQ, PETS, CLOTHES)):
                continue
            lamp = self.kit.part('phase_3.5/models/props/streetlight_TT', 'prop_post_one_light', pos=(x, y, 0), h=math.degrees(a) + 90)
            self.kit.wallTube((x, y, 0), 0.8, 10)

    def __trees(self):
        r = self.r
        spots = ((-150, 100), (-148, 30), (-150, -38), (150, 30), (148, -32), (-30, -150), (34, -152), (-96, 150),
                 (98, 150), (150, 102), (-128, -146), (60, -140), (-52, 76), (40, 156))
        for x, y in spots:
            self.kit.part('phase_3.5/models/props/trees', r.choice(('prop_tree_small', 'prop_tree_large', 'prop_tree_fat')),
                          pos=(x, y, 0), h=r.uniform(0, 360), scale=r.uniform(1.0, 1.3))
            self.kit.wallTube((x, y, 0), 2.0, 10)
        # Trees outside the wall, so the blocks stand against green.
        for i in range(40):
            a = 2 * math.pi * i / 40 + r.uniform(-0.04, 0.04)
            d = r.uniform(HALF + 30, HALF + 70)
            self.kit.part('phase_3.5/models/props/trees', r.choice(('prop_tree_small', 'prop_tree_large', 'prop_tree_fat')),
                          pos=(d * math.cos(a), d * math.sin(a), 0), h=r.uniform(0, 360), scale=r.uniform(1.4, 2.0))

    # --- Moving toys ---

    def __animate(self, task):
        import time
        t = task.time
        now = time.localtime()
        minutes = now.tm_min + now.tm_sec / 60.0
        hours = (now.tm_hour % 12) + minutes / 60.0
        self.minuteHand.setR(minutes * 6.0)
        self.hourHand.setR(hours * 30.0)
        self.crank.setP(-t * 25.0)
        # Jack bobs on his spring and nods.
        bob = math.sin(t * 1.7)
        self.jack.setSz(self.jackScale * (1.0 + 0.05 * bob))
        self.jack.setR(2.5 * math.sin(t * 0.9))
        if getattr(self, "windKey", None) is not None:
            self.windKey.setH(t * 30.0)
        for np, key, home, h, phase in self.ducks:
            s = math.sin(t * 1.4 + phase)
            np.setR(5.0 * math.sin(t * 6.0 + phase))
            f = heading(h)
            np.setPos(home + f * (s * 1.8))
            key.setR(t * 160.0)
        for holder, np, phase, rate in self.tops:
            np.setH(t * 540.0 * rate)
            holder.setP(5.0 * math.sin(t * 1.3 + phase))
            holder.setR(5.0 * math.cos(t * 1.3 + phase))
        return task.cont
