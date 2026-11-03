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

from panda3d.core import (PNMImage, Point3, SamplerState, Texture, TextNode, TransparencyAttrib, Vec3, Vec4)

from toontown.survival.previewmaps.MapKit import heading, rng
from toontown.survival.previewmaps.PreviewMap import PreviewMap
from toontown.survival.previewmaps.ToyGeo import Geo, Part, signText

# The game's own hand-painted textures.
# The playground's grey wood grain, lightened (paint) so colours on it stay
# true: on the plain grain cream came out grey.
WOOD_SRC = 'phase_3.5/maps/wood_gray.jpg'
WOOD = 'gen:paint'
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
HQ = Point3(-118, 62, 0)
GAG = Point3(66, 126, 0)
PARTY = Point3(-66, 128, 0)
TROLLEY = Point3(122, 66, 0)
CLOTHES = Point3(120, -64, 0)
PETS = Point3(-120, -64, 0)
POND = Point3(-104, -122, 0)
POND_R = (30.0, 21.0)
YARD = Point3(104, -118, 0)
# Tunnel mouths: (where, which way the mouth looks, street, theme).
TUNNELS = ((Point3(0, -HALF, 0), 0, 'Wind-Up Way', 'key'),
           (Point3(HALF, 0, 0), 90, 'Loose Marble Lane', 'marble'),
           (Point3(-HALF, 0, 0), -90, 'Building Block Boulevard', 'blocks'))
TUNNEL_GAP = 23.0


def facing(pos, target):
    """The heading that turns a building's front (its -y side) to target."""
    d = Vec3(pos[0] - target[0], pos[1] - target[1], 0)
    return math.degrees(math.atan2(-d[0], d[1]))


class ToyboxTerrace(PreviewMap):
    KEY = 'toybox_terrace'
    TITLE = 'Toybox Terrace'
    DESCRIPTION = 'A playground built from giant wooden toys. Even the clock tower pops out of a box.'
    PLAYER_START = (Point3(0, -118, 0), 0)
    MICKEY_SPOT = (Point3(0, 96, 0), 180)
    FISHERMAN_SPOT = (Point3(-76, -112, 0), 70)
    TRUNK_SPOT = (Point3(96, -104, 0), 135)
    REACH_SPAN = 175.0
    SPAWN_RING = (35.0, 240.0)
    NO_LANDING = ((TOWER, 30.0), (Point3(0, 96, 0), 12.0), (Point3(-76, -112, 0), 12.0), (Point3(96, -104, 0), 10.0),
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
        for pos, h, street, theme in TUNNELS:
            self.__tunnel(pos, h, street, theme)
        self.__hq()
        self.__gagShop()
        self.__clothes()
        self.__pets()
        self.__party()
        self.__trolley()
        self.__pond()
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
            # The solid line, broken where a tunnel goes through.
            cuts = [0.0]
            for g, half in gaps:
                t = (g - a).dot(along)
                if -1 < t < length + 1 and abs((g - a).dot(inward)) < 2:
                    cuts += [t - half, t + half]
            cuts.append(length)
            for s0, s1 in zip(cuts[::2], cuts[1::2]):
                if s1 - s0 > 0.5:
                    k.wallSegment(a + along * s0 - inward * 1.0, a + along * s1 - inward * 1.0, -1, 30, name='toyWall', thick=2.4)
            size = 12.0
            n = int(length / size)
            step = length / n
            for i in range(n):
                t = (i + 0.5) * step
                c = a + along * t - inward * 6.0
                if any((c - g).length() < half + 4 for g, half in gaps):
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

    def __tower(self):
        k = self.kit
        x, y = TOWER[0], TOWER[1]
        W = 38.0
        H = 42.0
        g = self.place(TOWER)
        hw = W / 2
        # A plinth to stand on, one step up, and the box on it.
        g.trimBox((-hw - 4, -hw - 4, 0), (hw + 4, hw + 4, 1.2), WOOD, CREAM, CREAM_D, t=0.8, tile=8)
        g.trimBox((-hw, -hw, 1.2), (hw, hw, H), WOOD, RED, BLUE, t=2.0, tile=10)
        # Each side a cream panel with a coloured inset, like a toy box's.
        b = 4.0
        e = 0.06
        for face, col in (('s', CREAM), ('e', CREAM), ('w', CREAM), ('n', CREAM)):
            fg = {'s': g, 'n': g.at((0, 0, 0), (180, 0, 0)), 'e': g.at((0, 0, 0), (90, 0, 0)), 'w': g.at((0, 0, 0), (-90, 0, 0))}[face]
            fg.quad(WOOD, [(-hw + b, -hw - e, 1.2 + b), (hw - b, -hw - e, 1.2 + b), (hw - b, -hw - e, H - b), (-hw + b, -hw - e, H - b)],
                    [(0, 0), (2, 0), (2, 2), (0, 2)], col)
            fg.quad(WOOD, [(-hw + b + 1.2, -hw - 2 * e, 1.2 + b + 1.2), (hw - b - 1.2, -hw - 2 * e, 1.2 + b + 1.2),
                           (hw - b - 1.2, -hw - 2 * e, 1.2 + b + 2.0), (-hw + b - -1.2, -hw - 2 * e, 1.2 + b + 2.0)],
                    [(0, 0), (2, 0), (2, 0.2), (0, 0.2)], YELLOW)
        # The clock on the front panel.
        cz = 23.5
        cr = 12.5
        cg = g.at((0, -hw - 0.16, cz), (0, 0, 0))
        cg.quad(CLOCK, [(-cr, 0, -cr), (cr, 0, -cr), (cr, 0, cr), (-cr, 0, cr)], [(0, 0), (1, 0), (1, 1), (0, 1)], (1, 1, 1, 1))
        # A thick yellow bezel round it.
        ring = g.at((0, -hw - 0.2, cz), (0, 90, 0))
        ring.torus(cr + 0.4, 0.75, WOOD, YELLOW, seg=40, sides=8)
        for i in range(12):
            a = math.radians(90 - i * 30)
            num = 12 if i == 0 else i
            self.text(str(num), (x + 8.4 * math.cos(a), y - hw - 0.3, cz + 8.4 * math.sin(a) - 1.15), 0, 3.1, INK)
        # The hands turn with the real time (see __animate).
        hands = self.part('clockHands')
        hg = hands.geo
        hg.box((-0.45, -0.15, -0.6), (0.45, 0.15, 4.6), WOOD, INK, tile=2)
        hg.box((-0.6, -0.12, -0.8), (0.6, 0.12, 3.4), WOOD, RED_D, tile=2)
        hg.sphere((0, -0.2, 0), 0.9, WOOD, YELLOW, rings=6, sides=10)
        # Two hands in one part would turn together: make each its own.
        minute = self.part('minuteHand')
        minute.geo.box((-0.5, -0.25, -1.0), (0.5, 0.0, 9.6), WOOD, INK, tile=2)
        minute.geo.sphere((0, -0.25, 0), 0.9, WOOD, YELLOW, rings=6, sides=10)
        hour = self.part('hourHand')
        hour.geo.box((-0.75, -0.12, -0.9), (0.75, 0.12, 6.2), WOOD, RED_D, tile=2)
        self.hourHand = self.keep(hour, (x, y - hw - 0.5, cz))
        self.minuteHand = self.keep(minute, (x, y - hw - 0.7, cz))
        # The crank on the east side, turning slowly.
        crank = self.part('crank')
        cgeo = crank.geo
        cgeo.at((0, 0, 0), (0, 0, 90)).cyl(0.9, 5.0, WOOD, YELLOW_D, sides=12)
        cgeo.box((4.4, -0.7, -0.7), (5.6, 0.7, 8.0), WOOD, YELLOW, tile=2)
        cgeo.at((5.0, 0, 8.0), (0, 0, 90)).cyl(0.75, 4.0, WOOD, YELLOW_D, sides=10)
        cgeo.sphere((9.4, 0, 8.0), (1.6, 1.6, 1.6), WOOD, RED, rings=8, sides=12)
        self.crank = self.keep(crank, (x + hw, y, 24))
        # The lid, flung open backwards on its hinge.
        lid = g.at((0, hw, H), (0, -118, 0))
        lid.trimBox((-hw - 1, -W - 1, 0), (hw + 1, 1, 2.2), WOOD, CREAM, RED, t=1.2, tile=10, faces='nsewtb')
        # The lid's painted inside, the side the plaza sees: a blue panel
        # with a yellow border and stars.
        inner = lid.at((0, -W / 2, -0.06), (0, 180, 0))
        e = 3.0
        inner.quad(WOOD, [(-hw + e, -W / 2 + e, 0), (hw - e, -W / 2 + e, 0), (hw - e, W / 2 - e, 0), (-hw + e, W / 2 - e, 0)],
                   [(0, 0), (3, 0), (3, 3), (0, 3)], BLUE)
        inner2 = lid.at((0, -W / 2, -0.03), (0, 180, 0))
        inner2.quad(WOOD, [(-hw + e - 1.2, -W / 2 + e - 1.2, 0), (hw - e + 1.2, -W / 2 + e - 1.2, 0), (hw - e + 1.2, W / 2 - e + 1.2, 0),
                           (-hw + e - 1.2, W / 2 - e + 1.2, 0)], [(0, 0), (3, 0), (3, 3), (0, 3)], YELLOW)
        star = [(math.cos(math.radians(90 + 36 * i)) * (1.0 if i % 2 == 0 else 0.42),
                 math.sin(math.radians(90 + 36 * i)) * (1.0 if i % 2 == 0 else 0.42)) for i in range(10)]
        for sx, sy, ss in ((-7, -7, 4.2), (7, 6, 5.0), (-6, 8, 3.0), (8, -8, 2.6), (0, 0, 2.2)):
            pts = [(sx + px * ss, sy + py * ss) for px, py in star]
            lid.at((0, -W / 2, -0.09), (0, 180, 0)).extrude(pts, 0, 0.02, WOOD, YELLOW, bottom=False)
        # Jack: a coiled spring, his ruff, his head and jester's hat. He
        # bobs on the spring (__animate).
        jack = self.part('jack')
        j = jack.geo
        coil = []
        turns = 5
        steps = turns * 20
        for i in range(steps + 1):
            t = i / float(steps)
            a = 2 * math.pi * turns * t
            coil.append((6.0 * math.cos(a), 6.0 * math.sin(a), t * 16.0))
        j.tube(coil, 0.85, WOOD, (0.86, 0.88, 0.94, 1), sides=8)
        j.cyl(6.6, 1.2, WOOD, BLUE, z0=-0.6, sides=24, caps='tb')
        # Ruff: soft points in alternating colours.
        for i in range(12):
            a = 360.0 * i / 12
            col = RED if i % 2 else YELLOW
            j.at((0, 0, 16.6), (a, 0, 0)).at((0, 4.5, 0), (0, -70, 0)).cyl(2.2, 4.0, WOOD, col, sides=10, rTop=0.3, caps='b')
        j.cyl(3.0, 2.2, WOOD, BLUE, z0=15.8, sides=16, caps='')
        # Head.
        hz = 23.5
        j.sphere((0, 0, hz), (6.4, 6.0, 6.6), PLAIN, (1.0, 0.9, 0.8, 1), rings=14, sides=24)
        # Rosy cheeks, a big red nose, eyes and a smile on the south side.
        j.sphere((0, -6.3, hz - 0.6), 1.5, PLAIN, (0.92, 0.18, 0.18, 1), rings=8, sides=12)
        for sx in (-1, 1):
            j.sphere((2.3 * sx, -5.4, hz + 1.8), (0.85, 0.5, 1.2), PLAIN, (0.12, 0.1, 0.18, 1), rings=6, sides=10)
            j.sphere((2.0 * sx, -5.75, hz + 2.3), (0.25, 0.15, 0.3), PLAIN, (1, 1, 1, 1), rings=4, sides=6)
            j.sphere((3.9 * sx, -4.6, hz - 1.0), (1.2, 0.5, 0.8), PLAIN, (1.0, 0.62, 0.6, 1), rings=6, sides=10)
            # Eyebrows.
            j.at((2.3 * sx, -5.6, hz + 3.8), (0, 90, -12 * sx)).torus(1.0, 0.22, PLAIN, (0.25, 0.15, 0.2, 1), seg=8, sides=5,
                                                                         arc=(20, 160))
        j.at((0, -4.9, hz - 2.6), (0, 90, 0)).torus(2.6, 0.38, PLAIN, (0.7, 0.12, 0.14, 1), seg=14, sides=6, arc=(200, 340))
        # Jester's hat: two floppy horns, red and blue, bells on the tips.
        j.cyl(6.0, 2.0, WOOD, YELLOW, z0=hz + 3.6, sides=24, rTop=5.6, caps='')
        for sx, col in ((-1, RED), (1, BLUE)):
            horn = []
            for i in range(13):
                t = i / 12.0
                horn.append((sx * (2.0 + 7.5 * math.sin(t * 1.6)), 0, hz + 5.0 + 7.0 * math.sin(t * 2.4) - t * t * 2.0))
            for i in range(12):
                rad = 3.4 * (1 - i / 12.0) + 0.5
                j.tube(horn[i:i + 2], rad, WOOD, col, sides=12)
            tip = horn[-1]
            j.sphere(tip, 1.5, WOOD, YELLOW, rings=8, sides=12)
        self.jack = self.keep(jack, (x, y, H - 0.4))
        self.jack.setScale(1.3)
        self.jackScale = 1.3
        # The box is solid; the plinth is a step up all round.
        k.wallBox((x - hw, y - hw, 1.2), (x + hw, y + hw, H))
        k.floorPoly([(x - hw - 4, y - hw - 4, 1.2), (x + hw + 4, y - hw - 4, 1.2), (x + hw + 4, y + hw + 4, 1.2),
                     (x - hw - 4, y + hw + 4, 1.2)], 'towerPlinth')

    # --- Tunnels ---

    def __portal(self, g, W, D, H, archW, spring, tex, color, trim, depth=26.0):
        """A tunnel portal: a block W wide, D deep and H high, its front at
        y = 0 looking -y, with an arched opening and a tunnel going in."""
        hw = W / 2.0
        ar = archW / 2.0
        steps = 16
        arch = []
        for i in range(steps + 1):
            a = math.pi * i / steps
            arch.append((-ar * math.cos(a), spring + ar * math.sin(a)))
        # The front face round the opening, in strips up to the top.
        for (x0, z0), (x1, z1) in zip(arch[:-1], arch[1:]):
            g.quad(tex, [(x0, 0, z0), (x1, 0, z1), (x1, 0, H), (x0, 0, H)],
                   [(x0 / 8, z0 / 8), (x1 / 8, z1 / 8), (x1 / 8, H / 8), (x0 / 8, H / 8)], color)
        g.quad(tex, [(-hw, 0, 0), (-ar, 0, 0), (-ar, 0, H), (-hw, 0, H)], [(-hw / 8, 0), (-ar / 8, 0), (-ar / 8, H / 8), (-hw / 8, H / 8)], color)
        g.quad(tex, [(ar, 0, 0), (hw, 0, 0), (hw, 0, H), (ar, 0, H)], [(ar / 8, 0), (hw / 8, 0), (hw / 8, H / 8), (ar / 8, H / 8)], color)
        # Sides, top and back.
        g.box((-hw, 0, 0), (hw, D, H), tex, color, tile=8, faces='ewnt')
        # Inside: the walls and the vault, getting darker inward.
        prof = [(-ar, 0)] + arch + [(ar, 0)]
        for (x0, z0), (x1, z1) in zip(prof[:-1], prof[1:]):
            n0 = Vec3(-x0, 0, -(z0 - spring) if z0 > spring else 0)
            g.quad(DARK, [(x0, 0.02, z0), (x0, depth, z0), (x1, depth, z1), (x1, 0.02, z1)],
                   [(0, 0.5), (1, 0.5), (1, 0.5), (0, 0.5)], (1, 1, 1, 1))
        g.quad(DARK, [(-ar, depth, 0), (ar, depth, 0), (ar, depth, spring + ar), (-ar, depth, spring + ar)],
               [(1, 0.5), (1, 0.5), (1, 0.5), (1, 0.5)], (1, 1, 1, 1))
        g.quad(DARK, [(-ar, 0.02, 0.03), (-ar, depth, 0.03), (ar, depth, 0.03), (ar, 0.02, 0.03)][::-1],
               [(0, 0.5), (1, 0.5), (1, 0.5), (0, 0.5)][::-1], (0.9, 0.85, 0.8, 1))
        return arch

    def __tunnel(self, pos, h, street, theme):
        k = self.kit
        r = self.r
        # pos is on the outline; the portal's front sits a little inside it.
        out = Vec3(pos[0], pos[1], 0)
        out.normalize()
        front = Vec3(pos[0], pos[1], 0) - out * 10.0
        # The mouth looks back into the plaza: heading such that -y faces in.
        bh = facing(front, (0, 0))
        g = self.place((front[0], front[1], 0), bh)
        W, D, H = 54.0, 30.0, 30.0
        archW, spring = 22.0, 9.0
        if theme == 'key':
            arch = self.__portal(g, W, D, H, archW, spring, WOOD, YELLOW, RED)
            # Tin-toy trim: a red band at the foot and the top, blue edges.
            g.trimBox((-W / 2, 0, 0), (W / 2, D, 3.0), WOOD, RED, RED_D, t=1.0, faces='sew')
            g.trimBox((-W / 2, 0, H - 3.0), (W / 2, D, H), WOOD, RED, RED_D, t=1.0, faces='sewt')
            for sx in (-1, 1):
                g.box((sx * W / 2 - 1.0, -0.6, 0), (sx * W / 2 + 1.0, 0.6, H + 0.3), WOOD, BLUE, tile=4)
            # Rivets along the bands.
            for i in range(13):
                xx = -W / 2 + 2 + i * (W - 4) / 12.0
                for zz in (1.5, H - 1.5):
                    g.sphere((xx, -0.1, zz), 0.45, WOOD, YELLOW_D, rings=4, sides=8)
            self.__archTrim(g, arch, RED, 1.6)
            # The giant winding key on top, turning (see __animate).
            key = self.part('windKey')
            kg = key.geo
            kg.cyl(1.4, 8.0, WOOD, YELLOW_D, sides=14, caps='t')
            kg.cyl(2.4, 1.4, WOOD, YELLOW, z0=0, sides=16, caps='t')
            bow = kg.at((0, 0, 13.0), (0, 0, 90))
            for sx in (-1, 1):
                bow.at((0, sx * 5.2, 0), (0, 0, 0)).torus(4.0, 1.25, WOOD, YELLOW, seg=28, sides=10)
            bow.at((0, 0, 0), (0, 0, 0)).cyl(2.4, 2.4, WOOD, YELLOW_D, z0=-1.2, sides=16, caps='tb')
            kg.at((0, 0, 7.6), (0, 0, 0)).cyl(1.6, 2.6, WOOD, YELLOW, sides=12, caps='t')
            top = self.world(front, bh, (0, D * 0.55, H))
            self.windKey = self.keep(key, top)
            self.windKey.setScale(1.7)
        elif theme == 'marble':
            arch = self.__portal(g, W, D, H, archW, spring, WOOD, BLUE, CREAM)
            g.trimBox((-W / 2, 0, H - 2.4), (W / 2, D, H), WOOD, CREAM, CREAM_D, t=1.0, faces='sewt')
            for sx in (-1, 1):
                g.box((sx * W / 2 - 1.2, -0.6, 0), (sx * W / 2 + 1.2, 0.6, H + 0.3), WOOD, CREAM, tile=4)
            # Marbles all round the opening, and up its sides to the ground.
            mr = 2.3
            ar = archW / 2.0
            ring = [(-ar - mr, z) for z in (mr, mr * 3, mr * 5 - 0.6)]
            for i in range(11):
                a = math.pi * i / 10
                ring.append((-(ar + mr) * math.cos(a), spring + (ar + mr) * math.sin(a)))
            ring += [(ar + mr, z) for z in (mr * 5 - 0.6, mr * 3, mr)]
            for i, (xx, zz) in enumerate(ring):
                g.sphere((xx, -mr * 0.6, zz), mr, MARBLES[i % 4], (1, 1, 1, 1), rings=10, sides=16)
            # A big one crowning the arch, and a few rolled loose.
            g.sphere((0, -1.4, H + 2.6), 4.0, MARBLES[0], (1, 1, 1, 1), rings=12, sides=18)
            for i, (lx, ly) in enumerate(((-ar - 7, -6), (ar + 9, -9), (ar + 4, -15))):
                wp = self.world(front, bh, (lx, ly, 0))
                self.g.sphere((wp[0], wp[1], 1.6), 1.6, MARBLES[(i + 1) % 4], (1, 1, 1, 1), rings=8, sides=14)
                k.wallTube((wp[0], wp[1], 0), 1.7, 3.2)
        else:
            # Building Block Boulevard: a toy block set built up into an arch.
            arch = self.__portal(g, W, D, H, archW, spring, WOOD, CREAM, CREAM_D)
            g.trimBox((-W / 2, 0, H - 2.0), (W / 2, D, H), WOOD, CREAM, CREAM_D, t=0.8, faces='t')
            ar = archW / 2.0
            # The portal's front built up from ABC blocks, row on row,
            # round the arch.
            bs = 6.0
            abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            n = 0
            for row in range(5):
                z = row * bs
                off = (bs / 2.0) if row % 2 else 0.0
                x = -W / 2 + bs / 2 - off
                while x < W / 2 + 0.1:
                    inner = abs(x) - bs / 2 < ar + 6.6
                    low = z + bs <= 23.0
                    if not (inner and low) and abs(x) + bs / 2 <= W / 2 + 2.6:
                        col = (RED, BLUE, YELLOW, CREAM, GREEN)[(row * 3 + n) % 5] if r.random() < 0.85 else CREAM
                        bh2 = bh + r.uniform(-2.5, 2.5)
                        wp = self.world(front, bh, (x, -2.6))
                        self.letterBlock(self.place((wp[0], wp[1], z), bh2), bs * r.uniform(0.97, 1.0), col, abc[n % 26],
                                         letterFaces='s', worldFrame=((wp[0], wp[1]), bh2))
                        n += 1
                    x += bs
            # Round column blocks each side of the opening, the arch block
            # across them, a triangle block and two cubes on top.
            colZ = spring + 0.4
            for sx, col in ((-1, RED), (1, BLUE)):
                cg = g.at((sx * (ar + 3.2), -3.6, 0), (0, 0, 0))
                cg.cyl(3.0, colZ, WOOD, col, sides=20, caps='t', tile=6)
                cg.at((0, 0, colZ * 0.5), (0, 0, 0)).torus(3.0, 0.35, WOOD, CREAM, seg=20, sides=6)
            ag = g.at((0, -3.6, colZ), (0, 0, 0))
            self.__archBlock(ag, ar + 6.4, ar, 7.0, 7.0, YELLOW, YELLOW_D)
            archTop = colZ + ar * 0.9 + 7.0 * 0.55
            tg = g.at((0, -3.6, archTop), (0, 0, 0))
            tg.prism((-7, -3.5, 0), (7, 3.5, 7.5), WOOD, RED, gable=RED_D, tile=6)
            for sx, col, s in ((-1, BLUE, 5.6), (1, GREEN, 5.0)):
                cg = g.at((sx * 12.0, -3.6, archTop), (r.uniform(-12, 12), 0, 0))
                self.letterBlock(cg, s, col, 'B' if sx < 0 else 'K', letterFaces='s', worldFrame=(front, bh))
            # A few loose blocks at the foot of the columns.
            for lx, ly, s, col, letter in ((-ar - 9.5, -7.0, 4.4, YELLOW, 'A'), (ar + 9.0, -6.0, 3.8, RED, 'C')):
                hh = bh + r.uniform(-25, 25)
                wp = self.world(front, bh, (lx, ly))
                self.letterBlock(self.place((wp[0], wp[1], 0), hh), s, col, letter, letterFaces='sn', worldFrame=((wp[0], wp[1]), hh))
                k.wallTube((wp[0], wp[1], 0), s * 0.62, 5)
        # The sign over the mouth, in the playground tunnels' style.
        signZ = H - 6.0 if theme != 'blocks' else spring + archW / 2 + 0.5
        if theme == 'blocks':
            signZ = H - 3.2
        sg = g.at((0, -0.5 if theme != 'marble' else -3.2, signZ), (0, 0, 0))
        sg.box((-12.5, -0.5, -3.4), (12.5, 0.0, 3.4), WOOD, CREAM, tile=4)
        sg.trimBox((-12.5, -0.5, -3.4), (12.5, 0.0, 3.4), WOOD, CREAM, {'key': RED, 'marble': BLUE_D, 'blocks': RED}[theme], t=0.9,
                   faces='s')
        sp = self.world(front, bh, (0, -1.1 if theme != 'marble' else -3.8, signZ - 1.1))
        self.text(street, sp, bh, 3.6, {'key': RED_D, 'marble': BLUE_D, 'blocks': RED_D}[theme], maxWidth=22.0)
        # Solid: the portal's front either side of the opening, its sides,
        # and a wall a little way in (the streets are closed tonight).
        ar = archW / 2.0
        self.solidRect(front, bh, -W / 2, 0, -ar, D, height=H)
        self.solidRect(front, bh, ar, 0, W / 2, D, height=H)
        a = self.world(front, bh, (-ar, 8.0))
        b = self.world(front, bh, (ar, 8.0))
        k.wallSegment(a, b, -1, 16, name='tunnelClosed', thick=2.0)
        for sx in (-1, 1):
            k.wallSegment(self.world(front, bh, (sx * ar, 0)), self.world(front, bh, (sx * ar, 9)), -1, 16, name='tunnelSide', thick=1.2)

    def __archTrim(self, g, arch, color, t):
        prof = [(arch[0][0], 0)] + arch + [(arch[-1][0], 0)]
        path = [(x, -0.3, z) for x, z in prof]
        g.tube(path, t * 0.5, WOOD, color, sides=8, plane=(0, 1, 0))

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

    # --- Buildings ---

    def __door(self, pos, h, local, color=CREAM, kind='door_double_round', scale=1.0):
        """One of the playground buildings' own doors, set in a front."""
        wp = self.world(pos, h, local)
        door = self.kit.model('phase_3.5/models/modules/doors_practical', pos=wp, h=h, scale=scale)
        node = door.find('**/' + kind)
        for child in door.find('**/newdoors').getChildren():
            if child.getName() != kind:
                child.removeNode()
        door.setColorScale(*color)
        # The door leaves stay shut and the black hole behind them hidden,
        # as on the playgrounds.
        for hole in door.findAllMatches('**/*hole*'):
            hole.hide()
        return door

    def __sign(self, pos, h, local, words, w, hgt, board=CREAM, trim=RED, ink=RED_D, scale=3.0):
        """A wooden shop sign board with the shop's name, on a front."""
        g = self.place(self.world(pos, h, local), h)
        g.box((-w / 2, -0.7, -hgt / 2), (w / 2, 0, hgt / 2), WOOD, board, tile=6)
        g.trimBox((-w / 2, -0.7, -hgt / 2), (w / 2, 0, hgt / 2), WOOD, board, trim, t=0.9, faces='s')
        tp = self.world(pos, h, (local[0], local[1] - 1.3, local[2] - scale * 0.3))
        self.text(words, tp, h, scale, ink, maxWidth=w - 2.5)

    def __hq(self):
        """Toon HQ: a toy fort of painted blocks with two round towers."""
        pos = HQ
        h = facing(pos, (0, 0))
        g = self.place(pos, h)
        W, D, H = 34.0, 26.0, 18.0
        g.trimBox((-W / 2, 0, 0), (W / 2, D, H), WOOD, CREAM, BLUE, t=1.4, tile=10)
        # Battlements along the top.
        for i in range(7):
            x = -W / 2 + 2.4 + i * (W - 4.8) / 6
            g.trimBox((x - 1.8, -0.2, H), (x + 1.8, 3.2, H + 3.6), WOOD, BLUE, BLUE_D, t=0.5, tile=4)
        # The middle: a taller red keep with the HQ star.
        g.trimBox((-8, 4, H), (8, D - 4, H + 10), WOOD, RED, YELLOW, t=1.2, tile=8)
        for i in range(4):
            x = -6.5 + i * 13 / 3.0
            g.trimBox((x - 1.5, 3.8, H + 10), (x + 1.5, 7, H + 12.6), WOOD, YELLOW, YELLOW_D, t=0.4, tile=4)
        star = [(math.cos(math.radians(90 + 36 * i)) * (5.0 if i % 2 == 0 else 2.2),
                 math.sin(math.radians(90 + 36 * i)) * (5.0 if i % 2 == 0 else 2.2)) for i in range(10)]
        g.at((0, 3.6, H + 5.0), (0, 90, 0)).extrude(star, 0, 0.8, WOOD, YELLOW, sideColor=YELLOW_D)
        # Two round towers at the front corners, pointed roofs.
        for sx in (-1, 1):
            tg = g.at((sx * (W / 2 + 1), 1.0, 0), (0, 0, 0))
            tg.cyl(6.5, 26, WOOD, RED, sides=20, caps='', tile=8)
            tg.at((0, 0, 9), (0, 0, 0)).torus(6.5, 0.6, WOOD, YELLOW, seg=24, sides=6)
            tg.at((0, 0, 18), (0, 0, 0)).torus(6.5, 0.6, WOOD, YELLOW, seg=24, sides=6)
            tg.cyl(7.8, 1.2, WOOD, YELLOW, z0=26, sides=20, caps='tb')
            tg.cyl(7.4, 11, WOOD, BLUE, z0=27.2, sides=20, rTop=0.4, caps='', tile=8)
            tg.sphere((0, 0, 38.6), 1.1, WOOD, YELLOW, rings=6, sides=10)
            # A little flag.
            tg.box((-0.15, -0.15, 38.6), (0.15, 0.15, 43), WOOD, CREAM_D, tile=2)
            tg.at((0, 0, 41.4), (0, 0, 0)).quad(WOOD, [(0, 0, 0), (3.4, 0, 0.8), (0, 0, 1.6), (0, 0, 1.6)],
                                                [(0, 0), (1, 0), (1, 1), (0, 1)], YELLOW, nrms=[(0, -1, 0)] * 4)
            # Arrow-slit windows.
            for z in (12, 21):
                tg.box((-0.8, -6.7, z), (0.8, -6.2, z + 3.4), WOOD, INK, tile=2)
        # The door in the middle, a sign over it.
        self.__door(pos, h, (0, -0.25, 0), color=(0.8, 0.86, 1.0, 1))
        self.__sign(pos, h, (0, -0.3, 12.3), 'TOON HQ', 18, 4.6, board=YELLOW, trim=BLUE_D, ink=BLUE_D, scale=3.4)
        # The periscope and telescope look about, as on every Toon HQ.
        from direct.actor.Actor import Actor
        self.hqToys = []
        for model, anim, local, s in (('phase_3.5/models/props/HQ_periscope-mod', 'phase_3.5/models/props/HQ_periscope-chan', (-4, D - 8, H + 10), 2.2),
                                      ('phase_3.5/models/props/HQ_telescope-mod', 'phase_3.5/models/props/HQ_telescope-chan', (12, D - 4, H), 2.0)):
            a = Actor(model, {'anim': anim})
            a.reparentTo(self.root)
            a.setPos(self.world(pos, h, local))
            a.setH(h + 180)
            a.setScale(s)
            a.loop('anim')
            self.kit.extra.append(a)
        self.solidRect(pos, h, -W / 2 - 7.5, 0.0, W / 2 + 7.5, D, height=18)
        # Windows each side of the door.
        for sx in (-1, 1):
            wg = g.at((sx * 11, -0.05, 6), (0, 0, 0))
            self.__window(wg, 5.0, 6.0, BLUE)

    def __window(self, g, w, hgt, frame):
        """A painted toy window: a frame, four panes and a sill."""
        g.box((-w / 2, -0.3, 0), (w / 2, 0.02, hgt), WOOD, frame, tile=2)
        e = 0.7
        g.quad(WOOD, [(-w / 2 + e, -0.33, e), (w / 2 - e, -0.33, e), (w / 2 - e, -0.33, hgt - e), (-w / 2 + e, -0.33, hgt - e)],
               [(0, 0), (1, 0), (1, 1), (0, 1)], (0.55, 0.74, 0.9, 1))
        g.box((-0.18, -0.42, e), (0.18, -0.3, hgt - e), WOOD, frame, tile=2)
        g.box((-w / 2 + e, -0.42, hgt / 2 - 0.18), (w / 2 - e, -0.3, hgt / 2 + 0.18), WOOD, frame, tile=2)
        g.box((-w / 2 - 0.5, -1.0, -0.5), (w / 2 + 0.5, 0.02, 0.05), WOOD, CREAM, tile=2)

    def __gagShop(self):
        """The Gag Shop: red and yellow blocks piled up, a pie on top."""
        pos = GAG
        h = facing(pos, (0, 0))
        g = self.place(pos, h)
        W, D = 30.0, 24.0
        g.trimBox((-W / 2, 0, 0), (W / 2, D, 16), WOOD, RED, YELLOW, t=1.4, tile=10)
        g2 = g.at((1.0, D / 2, 16), (4, 0, 0))
        g2.trimBox((-11, -10, 0), (11, 10, 12), WOOD, YELLOW, RED, t=1.2, tile=10)
        # Gable roof, blue.
        g3 = g2.at((0, 0, 12), (0, 0, 0))
        g3.prism((-12, -11, 0), (12, 11, 8), WOOD, BLUE, gable=CREAM, overhang=1.0, tile=8)
        # A striped awning over the door.
        for i in range(8):
            x0 = -9 + i * 18 / 8.0
            col = RED if i % 2 == 0 else CREAM
            g.quad(WOOD, [(x0, -5, 10.2), (x0 + 18 / 8.0, -5, 10.2), (x0 + 18 / 8.0, 0, 12.2), (x0, 0, 12.2)],
                   [(0, 0), (1, 0), (1, 1), (0, 1)], col)
            g.quad(WOOD, [(x0, 0, 12.2), (x0 + 18 / 8.0, 0, 12.2), (x0 + 18 / 8.0, -5, 10.2), (x0, -5, 10.2)],
                   [(0, 0), (1, 0), (1, 1), (0, 1)], col)
            g.sphere((x0 + 18 / 16.0, -5, 10.0), (18 / 16.0, 0.3, 0.7), WOOD, col, rings=4, sides=8, lat=(-90, 0))
        self.__door(pos, h, (0, -0.25, 0), color=(1, 1, 1, 1), kind='door_double_square')
        self.__sign(pos, h, (0, -0.3, 14.2), 'GAG SHOP', 22, 3.8, board=CREAM, trim=RED, ink=RED_D, scale=3.2)
        for sx in (-1, 1):
            self.__window(g.at((sx * 11.0, -0.05, 4.0), (0, 0, 0)), 4.5, 5.0, YELLOW_D)
        # The shop's sign of signs: a giant cream pie on a plate, hung on the
        # upper block's front.
        g2.at((0, -10.1, 6.2), (0, 90, 0)).cyl(6.4, 0.5, WOOD, CREAM, sides=28, caps='tb')
        g2.at((0, -10.4, 6.2), (0, 90, 0)).torus(6.4, 0.5, WOOD, BLUE, seg=32, sides=6)
        # The pie itself, painted wood: a fluted golden crust, a heap of
        # cream and a cherry.
        pg = g2.at((0, -10.6, 6.2), (0, 90, 0))
        crust = (0.9, 0.62, 0.32, 1)
        pg.cyl(5.0, 1.0, WOOD, crust, sides=24, rTop=5.4, caps='')
        for i in range(16):
            a = 2 * math.pi * i / 16
            pg.sphere((5.2 * math.cos(a), 5.2 * math.sin(a), 1.0), 0.75, WOOD, crust, rings=5, sides=8)
        pg.sphere((0, 0, 1.0), (4.8, 4.8, 2.0), WOOD, CREAM, rings=6, sides=20, lat=(0, 90))
        for i in range(6):
            a = 2 * math.pi * i / 6 + 0.3
            pg.sphere((2.9 * math.cos(a), 2.9 * math.sin(a), 2.0), (1.1, 1.1, 0.9), WOOD, CREAM, rings=5, sides=10, lat=(0, 90))
        pg.sphere((0, 0, 3.4), 0.9, WOOD, RED, rings=6, sides=10)
        for sx in (-1, 1):
            g2.at((sx * 8.2, -10.05, 2.0), (0, 0, 0)).box((-1.6, -0.3, 0), (1.6, 0, 8.6), WOOD, RED, tile=3)
        self.solidRect(pos, h, -W / 2, 0, W / 2, D, height=16)

    def __clothes(self):
        """The Clothing Shop: a dollhouse with a red roof and big buttons."""
        pos = CLOTHES
        h = facing(pos, (0, 0))
        g = self.place(pos, h)
        W, D = 32.0, 24.0
        g.trimBox((-W / 2, 0, 0), (W / 2, D, 22), WOOD, BLUE, CREAM, t=1.4, tile=10)
        g.at((0, D / 2, 22), (0, 0, 0)).prism((-W / 2, -D / 2, 0), (W / 2, D / 2, 12), WOOD, RED, gable=CREAM, overhang=1.4, tile=8)
        # A chimney like a thread spool.
        cg = g.at((9, D * 0.65, 22), (0, 0, 0))
        cg.cyl(2.4, 12, WOOD, CREAM, sides=14, caps='', tile=4)
        cg.cyl(3.4, 1.0, WOOD, YELLOW, z0=0, sides=14, caps='t')
        cg.cyl(3.4, 1.0, WOOD, YELLOW, z0=11.5, sides=14, caps='tb')
        cg.cyl(2.5, 9.6, WOOD, RED, z0=1.6, sides=14, caps='', tile=2)
        # Upstairs windows and a round attic window.
        for sx in (-1, 1):
            self.__window(g.at((sx * 9.0, -0.05, 15.2), (0, 0, 0)), 5.0, 5.5, CREAM)
            self.__window(g.at((sx * 11.0, -0.05, 3.5), (0, 0, 0)), 4.5, 5.0, CREAM)
        # Giant buttons on the gable.
        bg = g.at((0, -0.1, 27.5), (0, 90, 0))
        bg.cyl(3.2, 0.7, WOOD, YELLOW, sides=20, caps='tb', z0=0)
        for dx, dz in ((-0.9, -0.9), (0.9, -0.9), (0.9, 0.9), (-0.9, 0.9)):
            bg.at((dx, dz, 0.75), (0, 0, 0)).cyl(0.42, 0.05, PLAIN, YELLOW_D, sides=8, caps='t')
        self.__door(pos, h, (0, -0.25, 0), color=(1, 1, 1, 1), kind='door_double_clothshop', scale=1.1)
        self.__sign(pos, h, (0, -0.3, 12.4), 'CLOTHING SHOP', 24, 3.8, board=CREAM, trim=RED, ink=BLUE_D, scale=3.0)
        # A dressmaker's dummy and a spool by the door.
        sp = self.place(self.world(pos, h, (-12.5, -5, 0)), h)
        sp.cyl(2.0, 0.8, WOOD, CREAM, sides=14, caps='t')
        sp.cyl(1.4, 3.2, WOOD, RED, z0=0.8, sides=14, caps='', tile=2)
        sp.cyl(2.0, 0.8, WOOD, CREAM, z0=4.0, sides=14, caps='t')
        self.kit.wallTube(tuple(self.world(pos, h, (-12.5, -5, 0))), 2.1, 5)
        self.solidRect(pos, h, -W / 2, 0, W / 2, D, height=22)

    def __pets(self):
        """The Pet Shop: a round toy drum with a cone roof, fish swimming
        over the sign."""
        pos = PETS
        h = facing(pos, (0, 0))
        g = self.place(pos, h)
        R = 15.0
        c = g.at((0, R + 2, 0), (0, 0, 0))
        c.cyl(R, 22, WOOD, YELLOW, sides=28, caps='', tile=10)
        # Drum cords zig-zagging between red rims.
        for z in (0.0, 20.6):
            c.at((0, 0, z + 0.7), (0, 0, 0)).torus(R + 0.4, 0.9, WOOD, RED, seg=32, sides=8)
        for i in range(14):
            a0 = math.radians(360.0 * i / 14)
            a1 = math.radians(360.0 * (i + 0.5) / 14)
            p0 = ((R + 0.25) * math.cos(a0), (R + 0.25) * math.sin(a0), 1.6)
            p1 = ((R + 0.25) * math.cos(a1), (R + 0.25) * math.sin(a1), 19.8)
            p2 = ((R + 0.25) * math.cos(math.radians(360.0 * (i + 1) / 14)), (R + 0.25) * math.sin(math.radians(360.0 * (i + 1) / 14)), 1.6)
            c.tube([p0, p1, p2], 0.28, WOOD, CREAM, sides=6)
        c.cyl(R + 1.5, 1.2, WOOD, BLUE, z0=22, sides=28, caps='b')
        c.cyl(R + 1.5, 13, WOOD, BLUE, z0=23.2, sides=28, rTop=1.0, caps='', tile=8)
        c.sphere((0, 0, 36.6), 1.8, WOOD, RED, rings=6, sides=12)
        # A flat front porch block to hang the door and sign on.
        g.trimBox((-9, -1.0, 0), (9, 4, 11.5), WOOD, CREAM, BLUE, t=1.0, tile=8)
        g.at((0, 1.5, 11.5), (0, 0, 0)).prism((-10, -3.2, 0), (10, 3.2, 3.4), WOOD, RED, gable=RED_D, tile=6)
        self.__door(pos, h, (0, -1.25, 0), color=(0.86, 1.0, 0.86, 1), kind='door_double_round')
        self.__sign(pos, h, (0, 1.6, 17.4), 'PET SHOP', 18, 4.2, board=CREAM, trim=GREEN, ink=(0.26, 0.5, 0.22, 1), scale=3.2)
        from direct.actor.Actor import Actor
        fish = Actor('phase_4/models/props/exteriorfish-zero', {'swim': 'phase_4/models/props/exteriorfish-swim'})
        fish.reparentTo(self.root)
        fish.setPos(self.world(pos, h, (0, 7.0, -10.0)))
        fish.setH(h)
        fish.loop('swim')
        self.kit.extra.append(fish)
        # Paw prints walking up to the door.
        for i in range(5):
            wp = self.world(pos, h, ((-1.6 if i % 2 else 1.6), -5 - i * 3.6, 0.07))
            self.d.at(wp, (h, 0, 0)).sphere((0, 0, 0), (0.9, 1.1, 0.01), PLAIN, (0.62, 0.48, 0.38, 1), rings=2, sides=10, lat=(0, 90))
        cw = self.world(pos, h, (0, R + 2))
        self.kit.wallTube((cw[0], cw[1], 0), R + 0.6, 22)
        self.solidRect(pos, h, -9, -1.0, 9, 4, height=11.5)

    def __party(self):
        pos = PARTY
        h = facing(pos, (0, 0))
        gate = self.kit.model('phase_4/models/modules/partyGate_TT', pos=pos, h=h)
        self.kit.footprint(gate, below=8.0)

    def __trolley(self):
        pos = TROLLEY
        h = facing(pos, (0, 0))
        # The station model's platform runs from its origin 30 feet along
        # x; its middle goes on the spot. Its tunnels and hill are for a
        # playground's hillside (stashed, as on the Cog HQ maps): toy block
        # piles stand at each end instead.
        m = self.kit.model('phase_4/models/modules/trolley_station_TT', pos=self.world(pos, h, (-15, -4)), h=h, keepCollisions=True)
        m.setName('toy_trolley_station')
        for name in ('hill_1', 'tunnelL', 'tunnelR'):
            for n in m.findAllMatches('**/' + name):
                n.stash()
        # The plaque on the awning, lettered as on the playgrounds.
        self.text('TROLLEY', self.world(pos, h, (-0.4, -9.2, 16.6)), h, 2.6, RED_D, maxWidth=11.0)
        r = self.r
        for sx in (-1, 1):
            z = 0.0
            for i, (s, col) in enumerate(((7.5, BLUE if sx < 0 else RED), (6.0, YELLOW), (4.6, CREAM))):
                lx = sx * (19.0 + (i % 2) * 0.8)
                bh = h + r.uniform(-10, 10)
                wp = self.world(pos, h, (lx, 6.0))
                self.letterBlock(self.place((wp[0], wp[1], z), bh), s, col, 'TRO'[i] if sx < 0 else 'LEY'[i], letterFaces='sn',
                                 worldFrame=((wp[0], wp[1]), bh))
                z += s
            self.solidRect(pos, h, sx * 19.0 - 4.0, 2.0, sx * 19.0 + 4.0, 10.0, height=16)

    # --- The pond ---

    def __pond(self):
        k = self.kit
        cx, cy = POND[0], POND[1]
        rx, ry = POND_R
        n = 72
        # The three docks' angles round the rim (degrees, 0 = east).
        docks = (20.0, 75.0, 140.0)
        dockW = 3.6
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
            w = 3.6
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
            body, key = self.__duck('duck%d' % i)
            np = self.keep(body, (x, y, 0), (h, 0, 0))
            knp = self.keep(key, (0, 0, 0), parent=np)
            knp.setPos(0, -3.6, 4.0)
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
            top = self.__top('top%d' % i, cols)
            holder = self.root.attachNewNode('topHolder%d' % i)
            holder.setPos(x, y, 0)
            np = self.keep(top, parent=holder)
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
