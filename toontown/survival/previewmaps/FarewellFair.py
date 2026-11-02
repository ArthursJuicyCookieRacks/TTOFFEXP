"""Farewell Fair: a Toontown fair, long abandoned, at night.

About 300 feet square inside a leaning wooden fence. The chained-up
entrance arch at the south; a midway of faded ToonFest booths; the old
ToonFest tower rusting in the middle; a stopped Ferris wheel that still
creaks round now and then; a carousel turning by itself; a crashed hot-air
balloon; a dead stage with Mickey still waiting in front of it; and the
old trolley at the west fence. Dead trees, flickering lamps, string
lights with most bulbs out, litter and weeds all over.
"""

import math

from panda3d.core import NodePath, Point3, TextNode, Vec3, Vec4

from toontown.survival.previewmaps.MapKit import MapKit, heading, rng
from toontown.survival.previewmaps.PreviewMap import PreviewMap

DIRT_TEX = 'phase_12/maps/dirt_golf.jpg'
DIRT2_TEX = 'phase_6/maps/CountryDirt.jpg'
GRASS_TEX = 'phase_3.5/maps/grassDG.jpg'
PLAZA_TEX = 'phase_3.5/maps/cobblestone_brown.jpg'
WOOD_TEX = 'phase_3.5/maps/wood_gray.jpg'
BOARD_TEX = 'phase_3.5/maps/boardwalk_floor_dark.jpg'
FENCE_TEX = 'phase_3.5/maps/wall_fence_wood.jpg'
STRIPE_TEX = 'phase_10/maps/CBStationStripes2.jpg'
METAL_TEX = 'phase_9/maps/WallMetalPlateLargeRivets.jpg'
RUST_TEX = 'phase_9/maps/rustyWallStomperRm.jpg'
OIL_TEX = 'phase_9/maps/ttr_t_ara_shq_resistanceHideout_oilDrip.jpg'
BULB_TEX = 'phase_10/maps/CBStationLightTubes.jpg'

HALF = 150.0
FADED = (0.72, 0.66, 0.62, 1)
DEAD = (0.46, 0.42, 0.42, 1)

# The dead trees outside the fence: the tree files and the trees in them
# (the ones without a planter box).
TREES = (('phase_3.5/models/props/tt_m_ara_TT_trees_halloween',
          ('prop_tree_small_no_box_ul', 'prop_tree_small_nobox_ur', 'prop_tree_large_no_box_ul', 'prop_tree_large_no_box_ur',
           'prop_tree_fat_no_box_ul', 'prop_tree_fat_no_box_ur')),
         ('phase_8/models/props/tt_m_ara_BR_pinetrees_halloween',
          ('prop_snow_tree_large_nobox_ul', 'prop_snow_tree_large_nobox_ur', 'prop_snow_tree_small_nobox_ul',
           'prop_snow_tree_small_nobox_ur')))

TOWER = Point3(0, 30, 0)
WHEEL = Point3(-88, 86, 0)
CAROUSEL = Point3(88, 84, 0)
STAGE = Point3(104, -54, 0)
BALLOON = Point3(-96, -66, 0)
TROLLEY = Point3(-138, 10, 0)


class FarewellFair(PreviewMap):
    KEY = 'farewell_fair'
    TITLE = 'Farewell Fair'
    DESCRIPTION = 'The fun left town years ago. The cogs moved in.'
    PLAYER_START = (Point3(0, -122, 0), 0)
    MICKEY_SPOT = (Point3(88, -54, 0), 90)
    FISHERMAN_SPOT = (Point3(-22, -88, 0), -90)
    TRUNK_SPOT = (Point3(24, 2, 0), 90)
    REACH_SPAN = 155.0
    SPAWN_RING = (35.0, 220.0)
    NO_LANDING = ((TOWER, 36.0), (Point3(88, -54, 0), 12.0), (Point3(-22, -88, 0), 12.0), (Point3(24, 2, 0), 10.0))
    NIGHT_SCALE = Vec4(0.86, 0.82, 0.96, 1)
    SKY_FILE = 'phase_3.5/models/props/BR_sky'
    SKY_COLOR = Vec4(0.2, 0.18, 0.3, 1)
    BACKGROUND = Vec4(0.06, 0.05, 0.1, 1)
    FOG = ((0.14, 0.12, 0.2), 0.0035)
    LIGHT = ((0.5, 0.48, 0.6), (0.7, 0.72, 0.95), (-30, -55, 0))
    WALK_TESTS = [('midway', (0, -120, 0), 0, 4.0)]
    PLAYER_VIEWS = {
        'start': ((0, -126, 0), 0, 6),
        'midway': ((0, -95, 0), 0, 8),
        'wheel': ((-50, 40, 0), 40, 22),
        'carousel': ((60, 40, 0), -30, 10),
        'mickey': ((70, -54, 0), -90, -2),
        'freddy': ((-4, -88, 0), 90, -4),
        'trunk': ((8, -6, 0), -70, -10),
        'balloon': ((-60, -40, 0), 125, 4),
        'stage': ((50, -54, 0), -90, 12),
    }
    SHOTS = {
        'menu': ((70, -175, 34), (0, 10, 22)),
        'overview': ((150, -240, 150), (0, 10, 0)),
        'high': ((0, -260, 210), (0, 10, 0)),
        'entrance': ((0, -175, 14), (0, -120, 6)),
        'wheel': ((-30, 20, 12), (-88, 86, 34)),
        'tower': ((40, -40, 8), (0, 30, 40)),
    }

    def build(self):
        self.r = rng(1313)
        self.spinners = []
        self.flicker = []
        k = self.kit
        # Dirt everywhere, dead grass in patches, a cobbled plaza round the tower.
        k.ground(-HALF, -HALF, HALF, HALF, DIRT_TEX, tile=22, color=(0.8, 0.74, 0.66, 1), name='fairGround')
        for i in range(60):
            x, y = self.r.uniform(-HALF + 10, HALF - 10), self.r.uniform(-HALF + 10, HALF - 10)
            s = self.r.uniform(8, 20)
            k.decal((x, y), s, s * self.r.uniform(0.6, 1.2), 'phase_3/maps/drop-shadow.jpg', color=(0.18, 0.2, 0.1, 0.55), rot=self.r.uniform(0, 90))
        for i in range(30):
            x, y = self.r.uniform(-HALF + 10, HALF - 10), self.r.uniform(-HALF + 10, HALF - 10)
            s = self.r.uniform(6, 14)
            k.decal((x, y), s, s, OIL_TEX, color=(0.3, 0.26, 0.24, 1), rot=self.r.uniform(0, 360))
        self.__disc(TOWER, 46, PLAZA_TEX, (0.7, 0.66, 0.62, 1), 0.04)
        # The midway's boardwalk.
        k.quad([(-14, -140, 0.05), (14, -140, 0.05), (14, -10, 0.05), (-14, -10, 0.05)], BOARD_TEX,
               [(0, 0), (28 / 10.0, 0), (28 / 10.0, 13), (0, 13)], (0.72, 0.66, 0.6, 1), 'decal')
        self.__fence()
        self.__entrance()
        self.__midway()
        self.__tower()
        self.__wheel()
        self.__carousel()
        self.__stage()
        self.__balloon()
        self.__trolley()
        self.__tents()
        self.__litter()
        self.__lamps()
        # Outside: dead grass to the horizon and dead trees.
        k.ground(-900, -900, 900, 900, GRASS_TEX, tile=30, z=-0.06, color=(0.35, 0.36, 0.3, 1), collide=False)
        for i in range(46):
            a = 2 * math.pi * i / 46 + self.r.uniform(-0.05, 0.05)
            d = self.r.uniform(HALF + 18, HALF + 70)
            # One tree from the tree file. Each file holds every kind of
            # tree (small, large, fat, with and without a planter), all at
            # the file's origin: the whole file put down at one spot was
            # twenty trees in one place, their flat leaf cards fighting each
            # other, so the trees flickered as you walked and blinked out
            # (Arthur).
            path, parts = self.r.choice(TREES)
            k.part(path, self.r.choice(parts), pos=(d * math.cos(a), d * math.sin(a), 0), h=self.r.uniform(0, 360),
                   scale=self.r.uniform(1.0, 1.6), color=(0.42, 0.4, 0.38, 1))

    # --- Helpers ---

    def __disc(self, c, radius, tex, color, z, sides=32):
        for i in range(sides):
            a0 = 2 * math.pi * i / sides
            a1 = 2 * math.pi * (i + 1) / sides
            p0 = (c[0], c[1], z)
            p1 = (c[0] + radius * math.cos(a0), c[1] + radius * math.sin(a0), z)
            p2 = (c[0] + radius * math.cos(a1), c[1] + radius * math.sin(a1), z)
            self.kit.quad([p0, p1, p2], tex, [(c[0] / 10, c[1] / 10), (p1[0] / 10, p1[1] / 10), (p2[0] / 10, p2[1] / 10)], color, 'decal')

    def __text(self, text, pos, h, scale, color, parent=None, font='sign', roll=0, maxWidth=None):
        from toontown.toonbase import ToontownGlobals
        tn = TextNode('fairSign')
        tn.setFont(ToontownGlobals.getSignFont() if font == 'sign' else ToontownGlobals.getInterfaceFont())
        tn.setAlign(TextNode.ACenter)
        tn.setText(text)
        tn.setTextColor(*color)
        np = (parent or self.root).attachNewNode(tn)
        np.setPos(pos)
        np.setHpr(h, 0, roll)
        if maxWidth and tn.getWidth() * scale > maxWidth:
            # Shrunk to fit its board (the entrance arch's name ran into
            # the posts and lost its first and last letters: Arthur).
            scale = maxWidth / tn.getWidth()
        np.setScale(scale)
        np.setTwoSided(True)
        return np

    # --- Pieces ---

    def __fence(self):
        k = self.kit
        r = self.r
        # An old wooden fence all round, solid. The panels used to be put
        # down leaning sideways (rolled) at different heights, with one in
        # twelve knocked flat: gaps and holes all along it (Arthur). Now
        # every panel stands at one height, a little wider than the gap it
        # fills so the neighbours overlap, and leans only in or out (so
        # its sides stay against its neighbours'). The fallen panels lie
        # in the weeds inside, in front of a whole fence.
        corners = [(-HALF, -HALF), (HALF, -HALF), (HALF, HALF), (-HALF, HALF), (-HALF, -HALF)]
        for (ax, ay), (bx, by) in zip(corners[:-1], corners[1:]):
            k.wallSegment((ax, ay), (bx, by), -1, 14, name='fairFence', thick=2.0)
            length = math.hypot(bx - ax, by - ay)
            h = math.degrees(math.atan2(by - ay, bx - ax))
            along = Vec3(bx - ax, by - ay, 0) / length
            inward = Vec3(-along[1], along[0], 0)
            n = int(length / 10)
            step = length / n
            for i in range(n):
                t = (i + 0.5) / n
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                # Leave the entrance arch's gap in the south fence.
                if ay == -HALF and by == -HALF and abs(x) < 12:
                    continue
                start = Vec3(x, y, 0) - along * (step * 0.5 + 0.3)
                # Alternate panels sit a hair in and out, so the overlaps
                # never draw on top of each other.
                start += inward * (0.06 if i % 2 else -0.06)
                k.model('phase_3.5/models/modules/wood_fence', pos=start, h=h, p=r.uniform(-3, 3), color=DEAD,
                        scale=((step + 0.6) / 10.0, 1, 1.8))
                if r.random() < 0.08:
                    # A fallen panel, lying in the weeds inside.
                    spot = Vec3(x, y, 0) + inward * r.uniform(5, 8) - along * 5
                    k.model('phase_3.5/models/modules/wood_fence', pos=(spot[0], spot[1], 0.15), h=h + r.uniform(-20, 20), p=-90,
                            color=DEAD)

    def __entrance(self):
        k = self.kit
        y = -HALF
        for sx in (-1, 1):
            x = sx * 13
            k.box((x - 1.5, y - 1.5, 0), (x + 1.5, y + 1.5, 26), side=WOOD_TEX, top=WOOD_TEX, tile=6, color=(0.7, 0.35, 0.32, 1), collide='wall')
            k.cylinder((x, y, 26), 2.2, 2.5, WOOD_TEX, sides=10, color=FADED, cap=WOOD_TEX, tile=4, collide=False)
        # The arch board, sagging to one side.
        k.beam((-15, y, 24.5), (15, y, 22.0), 1.6, BOARD_TEX, color=FADED, depth=7.0)
        for side, hh, rl in ((-1.3, 0, 4.5), (1.3, 180, -4.5)):
            self.__text('FAREWELL FAIR', Point3(0, y + side, 22.2), hh, 3.4, (0.85, 0.3, 0.3, 1), roll=rl, maxWidth=20.5)
        self.__text('CLOSED', Point3(0, y + 1.2, 9), 180, 2.2, (0.9, 0.85, 0.75, 1), font='int')
        # The gates, chained shut.
        for sx in (-1, 1):
            k.model('phase_3.5/models/modules/wood_fence', pos=(sx * 11.5, y, 0), h=0 if sx < 0 else 180, color=DEAD, scale=(1.15, 1, 2.2))
        k.wallSegment((-13, y), (13, y), -1, 14, name='fairGate', thick=2.0)
        k.beam((-11, y + 0.6, 6), (11, y + 0.6, 8.5), 0.4, 'phase_9/maps/hq_chain.jpg', color=FADED, tile=2)
        k.beam((-11, y + 0.6, 8.5), (11, y + 0.6, 6), 0.4, 'phase_9/maps/hq_chain.jpg', color=FADED, tile=2)
        # Ticket booth just inside.
        b = k.model('phase_6/models/events/ttr_m_tf_booth', pos=(26, -132, 0), h=-90, color=FADED, scale=0.6)
        k.footprint(b, below=4.0)

    def __midway(self):
        k = self.kit
        r = self.r
        booths = ['phase_6/models/events/ttr_m_tf_booth', 'phase_6/models/events/ttr_m_tf_piebooth', 'phase_6/models/events/ttr_m_tf_xpbooth']
        rows = (-100, -62, -24)
        for side in (-1, 1):
            for i, y in enumerate(rows):
                x = side * 34
                # The booths' signs face the model's -y: turn them to face the boardwalk.
                h = 90 if side < 0 else -90
                if side < 0 and i == 0:
                    # The duck tank (the fisherman fishes for ducks here).
                    m = k.model('phase_6/models/events/ttr_m_tf_ducktank', pos=(x - 6, y + 14, 0), h=h, color=FADED, scale=0.85)
                    # Its square drop shadow lies at exactly the ground's
                    # height, so the two fought: a flickering black box
                    # under the tank (Arthur).
                    m.find('**/square_drop_shadow').removeNode()
                    k.footprint(m, below=4.0)
                    continue
                m = k.model(booths[(i + (side > 0)) % 3], pos=(x, y, 0), h=h + r.uniform(-6, 6), r=r.uniform(-3, 3), color=FADED, scale=0.85)
                k.footprint(m, below=4.0)
        # String lights over the midway, most bulbs dead.
        for y in (-118, -82, -44, -8):
            self.__stringLights((-26, y, 16), (26, y + 6, 15), 14)
            # A leaning wooden pole at each end of the string, in the gaps between booths.
            for x, py, top in ((-26, y, 16), (26, y + 6, 15)):
                k.cylinder((x, py, 0), 0.45, top + 1.5, WOOD_TEX, sides=8, color=DEAD, tile=3, cap=WOOD_TEX, collide=False)
                k.beam((x - 1.2, py, top + 0.4), (x + 1.2, py, top + 0.4), 0.3, WOOD_TEX, color=DEAD, tile=1)
                k.wallTube((x, py, 0), 0.8, 10)

    def __stringLights(self, a, b, count):
        k = self.kit
        r = self.r
        a, b = Vec3(*a), Vec3(*b)
        prev = a
        for i in range(1, count + 1):
            t = i / float(count)
            p = a + (b - a) * t
            p[2] -= math.sin(t * math.pi) * 3.0
            k.beam(prev, p, 0.12, WOOD_TEX, color=(0.2, 0.2, 0.2, 1), tile=1, group='decal')
            prev = p
            if i < count:
                lit = r.random() < 0.25
                color = r.choice(((1, 0.3, 0.3, 1), (1, 0.85, 0.3, 1), (0.4, 0.8, 1, 1), (0.6, 1, 0.5, 1))) if lit else (0.25, 0.25, 0.25, 1)
                k.box((p[0] - 0.35, p[1] - 0.35, p[2] - 0.9), (p[0] + 0.35, p[1] + 0.35, p[2] - 0.2), side=BULB_TEX, top=BULB_TEX,
                      bottom=BULB_TEX, tile=1, color=color, collide=False, group='glow' if lit else 'static')

    def __tower(self):
        k = self.kit
        t = k.model('phase_6/models/events/ttr_m_tf_tower', pos=TOWER, h=20, color=(0.62, 0.56, 0.55, 1), scale=0.32)
        # Rust streaks and a lean.
        t.setR(2.5)
        k.wallTube(TOWER, 26, 30)
        self.towerTop = t.find('**/tf_tower_hat_out')

    def __wheel(self):
        k = self.kit
        r = self.r
        c = WHEEL
        hubZ = 44.0
        R = 36.0
        # The base platform and the A-frame legs, on both sides of the wheel.
        k.box((c[0] - 22, c[1] - 12, 0), (c[0] + 22, c[1] + 12, 2.5), side=BOARD_TEX, top=BOARD_TEX, tile=6, color=FADED, collide='wall')
        for sy in (-1, 1):
            y = c[1] + sy * 6
            for sx in (-1, 1):
                k.beam((c[0] + sx * 18, y, 2.5), (c[0], y, hubZ), 1.8, METAL_TEX, color=FADED, tile=6)
            k.wallTube((c[0] - 16, y, 0), 2.2, 10)
            k.wallTube((c[0] + 16, y, 0), 2.2, 10)
        k.beam((c[0], c[1] - 7, hubZ), (c[0], c[1] + 7, hubZ), 1.6, METAL_TEX, color=FADED, tile=4)
        # The wheel itself turns (very slowly), so it is its own kit.
        holder = self.root.attachNewNode('ferrisWheel')
        holder.setPos(c[0], c[1], hubZ)
        wk = MapKit(holder)
        self.wheelKit = wk
        spokes = 16
        for ring in (-4.0, 4.0):
            pts = []
            for i in range(spokes):
                a = 2 * math.pi * i / spokes
                pts.append(Vec3(R * math.cos(a), ring, R * math.sin(a)))
            for i in range(spokes):
                wk.beam(pts[i], pts[(i + 1) % spokes], 1.2, RUST_TEX, color=FADED, tile=6)
                wk.beam(Vec3(0, ring, 0), pts[i], 0.6, METAL_TEX, color=FADED, tile=6)
        for i in range(spokes):
            a = 2 * math.pi * i / spokes
            wk.beam(Vec3(R * math.cos(a), -4, R * math.sin(a)), Vec3(R * math.cos(a), 4, R * math.sin(a)), 0.5, METAL_TEX, color=FADED)
        wk.finish()
        self.litNodes = [holder]
        self.spinners.append((holder, -1.2, 'r'))
        # The cars hang from the rim and stay upright (one hangs by one side).
        self.cars = []
        colors = [(0.75, 0.3, 0.3, 1), (0.3, 0.45, 0.75, 1), (0.8, 0.7, 0.3, 1), (0.35, 0.65, 0.4, 1)]
        for i in range(0, spokes, 2):
            a = 2 * math.pi * i / spokes
            car = holder.attachNewNode('car%d' % i)
            car.setPos(R * math.cos(a), 0, R * math.sin(a))
            ck = MapKit(car)
            col = colors[(i // 2) % 4]
            ck.box((-3, -2.6, -6.5), (3, 2.6, -3.5), side=STRIPE_TEX if i % 4 else BOARD_TEX, top=BOARD_TEX, bottom=BOARD_TEX, tile=4,
                   color=col, collide=False)
            ck.beam((0, 0, 0), (0, 0, -3.5), 0.3, METAL_TEX, color=FADED, tile=2)
            ck.box((-3.2, -2.8, -1.2), (3.2, 2.8, -0.8), side=WOOD_TEX, top=WOOD_TEX, bottom=WOOD_TEX, tile=4, color=col, collide=False)
            ck.finish()
            self.litNodes.append(car)
            self.cars.append((car, r.choice((0, 0, 0, 25, -18))))

    def __carousel(self):
        k = self.kit
        c = CAROUSEL
        holder = self.root.attachNewNode('carousel')
        holder.setPos(c)
        m = k.model('phase_13/models/parties/partyMerryGoRound', parent=holder, scale=2.6, color=(0.7, 0.62, 0.66, 1))
        self.spinners.append((holder, 6.0, 'h'))
        k.wallTube(c, 20, 14)
        # The canopy pole in the middle and a torn tent roof.
        k.cylinder((c[0], c[1], 0), 1.2, 30, STRIPE_TEX, sides=10, color=FADED, tile=6, collide=False)
        k.cylinder((c[0], c[1], 22), 23, 8, STRIPE_TEX, sides=20, color=(0.7, 0.4, 0.4, 1), tile=8, collide=False, radiusTop=2)
        cake = k.model('phase_13/models/parties/tt_m_ara_pty_cakeTower', pos=(c[0] - 32, c[1] - 26, 0), r=8, scale=2.0, color=(0.6, 0.55, 0.58, 1))
        k.wallTube((c[0] - 32, c[1] - 26, 0), 6.5, 18)

    def __stage(self):
        k = self.kit
        c = STAGE
        # The quiz stage, facing west over the midway (Mickey stands in
        # front). Stage, sign and poles all share one centre line, y = c.
        m = k.model('phase_6/models/events/ttr_m_tf_quizStage', pos=(c[0] + 6, c[1], 0), h=90, color=FADED, scale=1.3)
        k.footprint(m, below=4.5)
        # The sign hangs between two poles, the same distance either side,
        # on ropes from each pole's top (the string lights' wire) to its
        # top corners (it floated in the air before: Arthur).
        half, poleY, poleTop = 11.0, 17.0, 21.0
        x = c[0] + 2.8
        k.box((x - 0.4, c[1] - half, 10.2), (x + 0.4, c[1] + half, 17.6), side=BOARD_TEX, top=WOOD_TEX, tile=4, color=(0.45, 0.3, 0.45, 1),
              collide=False)
        self.__text('TONIGHT ONLY!', Point3(x - 0.5, c[1], 14.6), -90, 2.6, (0.95, 0.85, 0.5, 1), maxWidth=2 * half - 2)
        self.__text('THE GRAND FINALE', Point3(x - 0.5, c[1], 11.6), -90, 1.8, (0.9, 0.6, 0.5, 1), roll=-3, maxWidth=2 * half - 2)
        for sy in (-1, 1):
            y = c[1] + sy * poleY
            k.box((x - 0.6, y - 0.6, 0), (x + 0.6, y + 0.6, poleTop), side=WOOD_TEX, top=WOOD_TEX, tile=4, color=FADED, collide='wall')
            # A crossbar at the top, the rope tied round it.
            k.beam((x - 1.0, y, poleTop - 0.5), (x + 1.0, y, poleTop - 0.5), 0.35, WOOD_TEX, color=DEAD, tile=1)
            corner = Vec3(x, c[1] + sy * (half - 0.4), 17.6)
            top = Vec3(x, y - sy * 0.6, poleTop - 0.5)
            self.__rope(top, corner, sag=0.5)
            # And a second rope from lower down the pole to the sign's
            # bottom corner, so it hangs steady.
            self.__rope(Vec3(x, y - sy * 0.6, 12.0), Vec3(x, c[1] + sy * (half - 0.4), 10.4), sag=0.35)
        # A couple of dead bulbs on the top ropes, like the midway's.
        self.__stringLights((x, c[1] - poleY + 0.6, poleTop - 0.5), (x, c[1] - half + 0.4, 17.6), 4)
        self.__stringLights((x, c[1] + half - 0.4, 17.6), (x, c[1] + poleY - 0.6, poleTop - 0.5), 4)

    def __rope(self, a, b, sag=0.5, pieces=6):
        a, b = Vec3(*a), Vec3(*b)
        prev = a
        for i in range(1, pieces + 1):
            t = i / float(pieces)
            p = a + (b - a) * t
            p[2] -= math.sin(t * math.pi) * sag
            self.kit.beam(prev, p, 0.12, WOOD_TEX, color=(0.2, 0.2, 0.2, 1), tile=1, group='decal')
            prev = p

    def __balloon(self):
        k = self.kit
        c = BALLOON
        # The ToonFest balloon, come down hard and tipped over in the dirt.
        m = k.model('phase_6/models/events/tf_balloon', pos=(c[0], c[1], -2), h=60, p=0, r=-62, color=(0.62, 0.56, 0.58, 1))
        # Solid where it lies (two guessed tubes stood off to one side of
        # it: an invisible wall by the popcorn cart, Arthur's video).
        k.footprint(m, below=60.0, height=12.0)
        # Its ropes, trailing.
        for dx, dy in ((10, -8), (14, 4), (-6, 12)):
            k.beam((c[0], c[1], 1), (c[0] + dx, c[1] + dy, 0.2), 0.25, WOOD_TEX, color=DEAD, tile=1)
        cart = k.model('phase_5.5/models/estate/popcornCart', pos=(c[0] + 26, c[1] - 14, 0), h=40, r=7, color=FADED, scale=1.4)
        k.footprint(cart)

    def __trolley(self):
        k = self.kit
        # The old trolley at the west fence: the way out if the cogs win.
        m = k.model('phase_4/models/modules/trolley_station_TT', pos=TROLLEY, h=-90, color=(0.6, 0.56, 0.56, 1), keepCollisions=True)
        m.setName('fair_trolley_station')

    def __tents(self):
        k = self.kit
        r = self.r
        # Striped game tents, sagging, and a couple of strength testers.
        for (x, y), col in (((60, -112), (0.7, 0.35, 0.35, 1)), ((-70, 110), (0.35, 0.45, 0.7, 1)), ((118, 30), (0.7, 0.6, 0.3, 1)),
                            ((-122, 64), (0.4, 0.6, 0.4, 1)), ((70, 124), (0.65, 0.4, 0.6, 1))):
            rad = r.uniform(9, 12)
            k.cylinder((x, y, 0), rad, 8, STRIPE_TEX, sides=12, color=col, tile=6, collide=True)
            k.cylinder((x, y, 8), rad + 1.5, 7, STRIPE_TEX, sides=12, color=col, tile=6, collide=False, radiusTop=0.8)
            k.cylinder((x, y, 14.5), 0.3, 4, WOOD_TEX, sides=6, color=DEAD, collide=False)
        for x, y in ((-60, -118), (52, 96)):
            k.box((x - 2.5, y - 2.5, 0), (x + 2.5, y + 2.5, 2), side=WOOD_TEX, top=METAL_TEX, tile=4, color=FADED, collide='wall')
            k.box((x - 0.6, y - 0.6, 2), (x + 0.6, y + 0.6, 24), side=STRIPE_TEX, top=WOOD_TEX, tile=4, color=FADED, collide='wall')
            k.cylinder((x, y, 24), 1.4, 1.0, METAL_TEX, sides=10, color=(0.85, 0.75, 0.4, 1), cap=METAL_TEX, collide=False)
            k.box((x - 4.5, y - 0.9, 25.6), (x + 4.5, y - 0.5, 29.6), side=BOARD_TEX, top=WOOD_TEX, tile=4, color=(0.75, 0.35, 0.3, 1), collide=False)
            self.__text('TEST YOUR', Point3(x, y - 1.0, 28.0), 0, 1.3, (0.95, 0.88, 0.6, 1))
            self.__text('STRENGTH!', Point3(x, y - 1.0, 26.2), 0, 1.3, (0.95, 0.88, 0.6, 1))

    def __litter(self):
        k = self.kit
        r = self.r
        self.trashSpots = []
        self.tippedCans = []
        for i in range(36):
            x, y = r.uniform(-HALF + 15, HALF - 15), r.uniform(-HALF + 15, HALF - 15)
            if (Point3(x, y, 0) - TOWER).length() < 40 or abs(x) < 16 and y < -10:
                continue
            kind = r.random()
            if kind < 0.35:
                tipped = r.random() < 0.33
                # A knocked-over can lies on its side, on the ground (not
                # half sunk into it).
                m = k.model('phase_5/models/props/trashcan_TT', pos=(x, y, 1.35 if tipped else 0), h=r.uniform(0, 360), r=90 if tipped else 0,
                            color=DEAD)
                self.trashSpots.append((x, y, tipped))
                self.__trash(m, x, y, tipped)
                k.footprint(m)
            elif kind < 0.65:
                m = k.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, 0), h=r.uniform(0, 360), color=DEAD, scale=r.uniform(0.9, 1.3))
                k.footprint(m)
            elif kind < 0.8:
                # Sacks and pumpkins are solid too: nobody walks through
                # them (Arthur).
                m = k.model('phase_5.5/models/estate/sack', pos=(x, y, 0), h=r.uniform(0, 360), color=DEAD, scale=1.5)
                k.footprint(m)
            else:
                m = k.model('phase_4/models/estate/pumpkin_short', pos=(x, y, 0), h=r.uniform(0, 360), color=(0.6, 0.5, 0.45, 1), scale=1.4)
                k.footprint(m)
            if r.random() < 0.4:
                k.decal((x + 3, y + 2), 6, 6, OIL_TEX, color=(0.4, 0.38, 0.36, 1), rot=r.uniform(0, 360))

    def __trash(self, can, x, y, tipped):
        """Litter round a trash can. The can's model has no bottom, so a
        can knocked over showed an empty, see-through ring (Arthur): its
        open end gets a dark inside, and the trash spills out of it, tilted
        every which way, the way a real spill lies."""
        k = self.kit
        r = self.r
        if not tipped:
            for i in range(r.randint(3, 5)):
                a = r.uniform(0, 2 * math.pi)
                d = r.uniform(2.2, 4.0)
                self.__junk(x + d * math.cos(a), y + d * math.sin(a), r.choice(('paper', 'paper', 'peel', 'can', 'bottle')))
            return
        # Its shadow card stands on edge once the can lies down.
        for shadow in can.findAllMatches('**/o11'):
            shadow.removeNode()
        self.__canInside(can)
        up = render.getRelativeVector(can, Vec3(0, 0, 1))
        up[2] = 0
        up.normalize()
        side = Vec3(-up[1], up[0], 0)
        mouth = Vec3(x, y, 0)
        self.tippedCans.append((mouth, up))
        # A wooden crate stands right against the open bottom and covers
        # it (Arthur), the can's base resting on it.
        # Small crates stacked against the open bottom cover it (Arthur):
        # two side by side on the ground, one on top, nudged about the way
        # junk gets piled.
        h = math.degrees(math.atan2(-up[0], up[1]))
        for across, height, scale in ((-0.75, 0.0, 0.25), (0.78, 0.0, 0.24), (r.uniform(-0.25, 0.25), 1.36, 0.22)):
            spot = mouth - up * (0.78 + r.uniform(-0.05, 0.12)) + side * across
            box = k.model('phase_9/models/cogHQ/woodCrateB', pos=(spot[0], spot[1], height), h=h + r.uniform(-14, 14),
                          r=r.uniform(-3, 3) if height else 0, color=DEAD, scale=scale)
            if not height:
                k.footprint(box)
        # Trash spilled round the boxes and on past them.
        for i in range(10):
            t = r.uniform(0.0, 1.0) ** 1.3
            d = 1.0 + t * 4.0
            w = r.choice((-1, 1)) * (1.8 + t * 1.6) + r.uniform(-0.5, 0.5)
            p = mouth - up * d + side * w
            kind = r.choice(('paper', 'paper', 'paper', 'shred', 'peel', 'can', 'can', 'bottle'))
            self.__junk(p[0], p[1], kind, pile=max(0.0, 0.9 - t * 1.5))
        k.decal((mouth[0] - up[0] * 3, mouth[1] - up[1] * 3), 7, 5, OIL_TEX, color=(0.32, 0.3, 0.28, 1),
                rot=math.degrees(math.atan2(up[1], up[0])))

    def __canInside(self, can):
        """A dark disc just inside the can's open bottom: the inside of the
        can, not a hole you see the ground through."""
        from panda3d.core import GeomVertexReader
        from toontown.survival.previewmaps.MapKit import Mesh, convexHull
        ring = []
        for gnp in can.findAllMatches('**/metal_3d'):
            mat = gnp.getMat(can)
            for i in range(gnp.node().getNumGeoms()):
                reader = GeomVertexReader(gnp.node().getGeom(i).getVertexData(), 'vertex')
                while not reader.isAtEnd():
                    v = mat.xformPoint(reader.getData3())
                    if v[2] < 0.3:
                        ring.append((v[0], v[1]))
        hull = convexHull(ring)
        if len(hull) < 3:
            return
        cx = sum(p[0] for p in hull) / len(hull)
        cy = sum(p[1] for p in hull) / len(hull)
        mesh = Mesh()
        for (ax, ay), (bx, by) in zip(hull, hull[1:] + hull[:1]):
            mesh.quad([Point3(cx, cy, 0.25), Point3(bx * 0.97, by * 0.97, 0.25), Point3(ax * 0.97, ay * 0.97, 0.25)],
                      [(0.5, 0.5), (0, 0), (1, 0)], Vec4(0.08, 0.07, 0.08, 1))
        disc = can.attachNewNode(mesh.node('canInside'))
        disc.setTwoSided(True)
        disc.setTextureOff(1)

    def __junk(self, x, y, kind, pile=0.0):
        """One piece of litter at (x, y), tilted as it fell; pile lifts it
        onto the heap at a can's mouth."""
        k = self.kit
        r = self.r
        tint = r.choice(((0.7, 0.68, 0.62, 1), (0.6, 0.58, 0.55, 1), (0.66, 0.6, 0.5, 1)))
        h = r.uniform(0, 360)
        if kind == 'paper':
            k.model('phase_5/models/props/newspaper', pos=(x, y, 0.04 + pile * r.uniform(0.15, 0.5)), h=h, p=r.uniform(-14, 14) if pile else 0,
                    r=r.uniform(-14, 14) if pile else r.uniform(-3, 3), color=(tint[0] * 0.8, tint[1] * 0.8, tint[2] * 0.75, 1),
                    scale=r.uniform(1.6, 2.4))
        elif kind == 'shred':
            k.model('phase_3.5/models/props/shredder-paper-mod', pos=(x, y, -0.85 + pile * 0.5), h=h, p=r.uniform(-15, 15), color=tint,
                    scale=r.uniform(0.6, 0.9))
        elif kind == 'peel':
            k.model('phase_5/models/props/banana-peel-mod', pos=(x, y, 0), h=h, r=r.uniform(-10, 10), color=(0.7, 0.62, 0.45, 1),
                    scale=r.uniform(0.35, 0.5))
        elif kind == 'can':
            # A soda can on its side.
            k.model('phase_5/models/props/can', pos=(x, y, 0.3 + pile * 0.4), h=h, p=r.choice((90, -90, 80)), color=tint, scale=r.uniform(3.5, 4.5))
        else:
            k.model('phase_3.5/models/props/bottle', pos=(x, y, 0.05), h=h, r=r.choice((88, -88)), color=(0.5, 0.6, 0.5, 1), scale=r.uniform(0.35, 0.5))

    def __lamps(self):
        k = self.kit
        r = self.r
        spots = [(-20, -120), (20, -120), (-20, -80), (20, -80), (-20, -40), (20, -40), (-40, 10), (40, 10), (-40, 60), (40, 60),
                 (-120, -120), (120, -120), (-120, 120), (120, 120), (60, -100), (-70, 20), (70, 20), (130, 0), (-60, 120), (60, 120)]
        for x, y in spots:
            m = k.model('phase_3.5/models/props/streetlight_TT', pos=(x, y, 0), h=r.uniform(0, 360), color=DEAD,
                        r=r.choice((0, 0, 0, 6, -8)))
            for name in ('**/prop_post_sign', '**/prop_post_three_light'):
                m.find(name).removeNode()
            k.wallTube((x, y, 0), 0.8, 10)
            if r.random() < 0.55:
                # A glow round the bulb, some flickering.
                glow = self.__glowCard(Point3(x, y, 10.6), 3.5)
                if r.random() < 0.5:
                    self.flicker.append((glow, r.uniform(0, 10)))

    def __glowCard(self, pos, size):
        from panda3d.core import CardMaker, TransparencyAttrib
        cm = CardMaker('glow')
        cm.setFrame(-size, size, -size, size)
        np = self.root.attachNewNode(cm.generate())
        np.setPos(pos)
        np.setBillboardPointEye()
        np.setTexture(self.kit.tex('phase_4/maps/particleGlow.jpg'), 1)
        np.setColor(1, 0.85, 0.5, 0.55)
        np.setColorScaleOff(10)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthWrite(False)
        np.setBin('fixed', 5)
        from panda3d.core import ColorBlendAttrib
        np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        return np

    # --- Moving parts ---

    def afterFinish(self):
        self.addTask(self.__animate, 'animate')

    def __animate(self, task):
        t = task.time
        for np, speed, axis in self.spinners:
            if axis == 'h':
                np.setH(t * speed)
            else:
                # The wheel creaks: a little, a stop, a little more.
                step = t * speed
                np.setR(step + 2.0 * math.sin(t * 0.7))
        for car, tilt in getattr(self, 'cars', ()):
            # Keep the cars hanging straight down, swinging a little.
            wheelR = car.getParent().getR()
            car.setR(-wheelR + tilt + 3.0 * math.sin(t * 1.3 + tilt))
        for glow, phase in self.flicker:
            v = math.sin(t * 9 + phase) + math.sin(t * 23 + phase * 2)
            glow.setAlphaScale(1.0 if v > -0.6 else 0.1)
        return task.cont

    def destroy(self):
        PreviewMap.destroy(self)
        for kit in [getattr(self, 'wheelKit', None)]:
            if kit:
                kit.destroy()
