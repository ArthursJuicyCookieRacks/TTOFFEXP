"""Der Toonen Riese: a cog gag factory the cogs run day and night.

Black Ops 1's Der Riese, laid out the way Arthur described it, built from
Toontown's own factory walls, floors and props (Sellbot's factory, the
Cashbot mint). Feet; +y runs from the forecourt to the rear factory.

- The forecourt (start): the mainframe in the middle with its pad, the gag
  upgrade behind a shutter in the north wall, the Fruit Pie Slice and the
  Cream Pie Slice on the walls, four boarded windows.
- Animal-testing wing (west door): a hall (Whistle), the lab with the toon
  cages (Aoogah), teleporter A's room (Whole Fruit Pie), then the walkway
  up high (Marbles, Toon-Up Tonic) down into the power courtyard.
- Garage wing (east door): the garage (Speedy Seltzer, Bugle), the furnace
  hall (Squirt Gun, Training Tracks, the furnaces, Organic Gags), then
  teleporter B's lab (Glass of Water) with its vats and balcony.
- The power courtyard: the generator, the power switch, the box's first
  spot, the Seltzer Bottle. The power opens the shutter back to the
  forecourt and lowers the bridge from the walkway to the rear factory.
- The rear factory: teleporter C, the catwalk (Sandbag) and the office
  (Second Wind, the Bamboo Cane).
- Link all three teleporters at the mainframe and the upgrade opens.
"""

import math
import random

from direct.interval.IntervalGlobal import Func, LerpHprInterval, LerpPosInterval, Sequence
from panda3d.core import Point3, Vec3, Vec4

from toontown.survival import SurvivalGlobals as G
from toontown.survival.bigmaps.Building import *  # noqa: F401,F403 (the shared textures and colours)
from toontown.survival.bigmaps.Building import Building
from toontown.survival.previewmaps.MapKit import rng

# The factory's own materials (all the game's).
BLOCKS = 'phase_9/maps/FootFactory_Wall1.jpg'
STONE = 'phase_9/maps/WallStone.jpg'
CORRUGATED = 'phase_9/maps/FlatWall1.jpg'
CONCRETE = 'phase_9/maps/CementFloorx4Warm.jpg'
FAC_FLOOR = 'phase_9/maps/FootFactoryFloor.jpg'
GRAVEL = 'phase_9/maps/ground7.jpg'
PLATE = 'phase_9/maps/FootFactoryMetalPlate.jpg'
PANELS = 'phase_9/maps/metalPannel.jpg'
CEIL_PLATE = 'phase_9/maps/CeilingMetalPlate2.jpg'
CEIL_SQ = 'phase_9/maps/CeilingSquares.jpg'
HIGH_WINDOWS = 'phase_9/maps/FootFactorySingleSqWndw.jpg'
ROLLUP = 'phase_10/maps/RollUpDoors.jpg'
DUCT = 'phase_9/maps/Duct3.jpg'
STONE_FLOOR = 'phase_10/maps/LargeStoneBlocksLtEdge.jpg'

STEEL = (0.62, 0.62, 0.64, 1)
DARK_STEEL = (0.38, 0.38, 0.4, 1)
GRIME = (0.82, 0.78, 0.74, 1)
LAB_TILE = (0.72, 0.8, 0.76, 1)
FAC_C = (0.86, 0.82, 0.78, 1)
YARD_C = (0.78, 0.76, 0.74, 1)
WARN = (1.0, 0.45, 0.2)
SICK_GREEN = (0.55, 1.0, 0.45)

MAINFRAME_PAD = Point3(0, -2, 0)
PADS = {'A': Point3(-96, 28, 0), 'B': Point3(72, 64, 0), 'C': Point3(10, 112, 0)}
LINK_TIME = 30.0
TELEPORT_COOL = 60.0


class Factory(Building):
    KEY = 'factory'
    TITLE = 'Der Toonen Riese'
    DESCRIPTION = 'A cog gag factory with three teleporters and a mainframe.'
    PLAYER_START = (Point3(0, -28, 0), 0)
    MICKEY_SPOT = (Point3(0, 33, 0), 180)
    TRUNK_SPOT = (Point3(-6, 93.5, 0), 0)
    FISHERMAN_SPOT = (Point3(0, -28, 0), 0)
    REACH_CENTER = Point3(0, 50, 0)
    REACH_SPAN = 140.0
    NAV_TOP = 50.0
    NAV_LOWEST = -5.0
    SPAWN_RING = (0.0, 300.0)
    NO_LANDING = ()
    NIGHT_SCALE = Vec4(0.92, 0.92, 0.95, 1)
    SKY_FILE = 'phase_3.5/models/props/BR_sky'
    SKY_COLOR = Vec4(0.14, 0.15, 0.22, 1)
    BACKGROUND = Vec4(0.03, 0.03, 0.05, 1)
    FOG = ((0.06, 0.06, 0.07), 0.004)
    LIGHT = ((0.36, 0.36, 0.38), (0.36, 0.38, 0.48), (-30, -55, 0))
    CAMERA_FAR = 900.0

    # --- Building ---

    def build(self):
        self.rand = rng(1945)
        self.powerBulbs = []
        self.powerLamps = []
        self.forecourt()
        self.upgradeRoom()
        self.hallA()
        self.lab()
        self.teleA()
        self.walkway()
        self.garage()
        self.furnace()
        self.teleB()
        self.court()
        self.rear()
        self.office()
        self.yards()
        self.dressForecourt()
        self.dressTestingWing()
        self.dressGarageWing()
        self.dressCourtAndRear()

    def lamp(self, pos, color=(1.0, 0.78, 0.45), reach=40.0, groups=(), flicker=False):
        # The factory's lamps throw a little further than the theater's.
        return Building.lamp(self, pos, color, reach * 1.35, groups=groups, flicker=flicker)

    def powerLamp(self, pos, color, reach, groups):
        """A lamp that stays dark until the power comes on."""
        np = self.lamp(pos, (0, 0, 0), reach, groups=groups)
        self.powerLamps.append((np, Vec4(color[0], color[1], color[2], 1)))
        return np

    def cageLight(self, pos, group, color=WARN):
        """A caged factory light on the wall: dead until the power."""
        node = self.kit.visual.attachNewNode('cageLight')
        node.setPos(Point3(*pos))
        self.boxNode(node, (-0.5, -0.5, -0.3), (0.5, 0.5, 0.3), METAL, color=DARK_STEEL, tile=1)
        bulb = self.boxNode(node, (-0.35, -0.35, -0.75), (0.35, 0.35, -0.3), CEMENT, color=(0.3, 0.22, 0.18, 1), tile=1)
        self.powerBulbs.append((bulb, color))
        return node

    def crate(self, pos, h=0, scale=0.5, metal=False):
        x, y, z = pos
        if metal:
            self.kit.model('phase_9/models/cogHQ/metal_crateB', pos=(x, y, z), h=h, scale=scale, color=GRIME)
            half = 2.95 * scale
            self.kit.wallBox((x - half, y - half, z), (x + half, y + half, z + 5.5 * scale))
        else:
            self.kit.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, z), h=h, scale=scale, color=(0.7, 0.64, 0.56, 1))
            self.kit.wallTube((x, y, z), 4.2 * scale, 5.5 * scale)

    def pipesAlong(self, a, b, z, group, radius=0.35, count=2, gap=0.9):
        """Pipes run along a wall from a to b at height z."""
        a, b = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        u = b - a
        u.normalize()
        n = Vec3(-u[1], u[0], 0)
        for i in range(count):
            off = n * (i * gap)
            self.kit.beam(a + off + Vec3(0, 0, z - i * 0.2), b + off + Vec3(0, 0, z - i * 0.2), radius * 2, RUST,
                          color=(0.55, 0.47, 0.42, 1), tile=3, group=group)

    def highWindows(self, a, b, z, group, color=(0.55, 0.58, 0.62, 1)):
        """A band of factory windows high on a wall (the room's side of the
        wall from a to b): a picture on the wall, nobody climbs that far."""
        a, b = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        u = b - a
        length = u.length()
        u.normalize()
        n = Vec3(-u[1], u[0], 0) * 0.08
        p0, p1 = a + n, b + n
        self.kit.quad([p0 + Vec3(0, 0, z), p1 + Vec3(0, 0, z), p1 + Vec3(0, 0, z + 5), p0 + Vec3(0, 0, z + 5)], HIGH_WINDOWS,
                      [(0, 0), (length / 6.0, 0), (length / 6.0, 1), (0, 1)], color, 'glow')

    # --- The forecourt (the start) ---

    def forecourt(self):
        g = 'forecourt'
        self.zone('forecourt', 'the forecourt', (-36, -36, -1, 36, 24, 30), startOpen=True)
        self.floor(-36, -36, 36, 24, 0, GRAVEL, tile=10, color=YARD_C, group=g)
        # A concrete apron round the mainframe.
        self.kit.quad([(-14, -10, 0.03), (14, -10, 0.03), (14, 16, 0.03), (-14, 16, 0.03)], CONCRETE,
                      [(0, 0), (3, 0), (3, 2.6), (0, 2.6)], (0.62, 0.6, 0.58, 1), g)
        # The factory's walls all round, the doors east and west, the
        # upgrade's shutter and the passage north.
        self.shell(-36, -36, 36, 24, 0, 24, BLOCKS, color=FAC_C, ops={
            's': [(-22, 6, 2, 8), (22, 6, 2, 8)],
            'w': [(-6, 8, 0, 9), (14, 6, 2, 8)],
            'e': [(-6, 8, 0, 9), (14, 6, 2, 8)],
            'n': [(0, 12, 0, 10), (26, 8, 0, 10)],
        }, group=g, lower=(PANELS, 4.0, GRIME), outside={'w': (CEMENT, GRIME), 'e': (CORRUGATED, GRIME), 'n': (BLOCKS, FAC_C)},
            tile=10)
        for x in (-22, 22):
            self.window('forecourt', (x, -36, 0), 0)
        self.window('forecourt', (-36, 14, 0), -90)
        self.window('forecourt', (36, 14, 0), 90)
        self.highWindows((-34, 23.4), (-8, 23.4), 13, g)
        self.highWindows((8, 23.4), (21, 23.4), 13, g)
        self.highWindows((-35.4, -34), (-35.4, -12), 13, g)
        self.highWindows((35.4, -12), (35.4, -34), 13, g)
        # The big gate out, rolled down for good, sandbagged.
        self.kit.quad([(-10, -35.4, 0), (10, -35.4, 0), (10, -35.4, 14), (-10, -35.4, 14)], ROLLUP,
                      [(0, 0), (3, 0), (3, 3), (0, 3)], (0.6, 0.58, 0.55, 1), g)
        self.kit.beam((-10.6, -35.2, 14.3), (10.6, -35.2, 14.3), 0.8, METAL, color=DARK_STEEL, tile=3)
        for x in (-10.6, 10.6):
            self.kit.beam((x, -35.2, 0), (x, -35.2, 14.3), 0.8, METAL, color=DARK_STEEL, tile=3)
        r = rng(3)
        for i in range(9):
            x = -9 + i * 2.2
            self.kit.model('phase_5/models/props/sandbag-mod', pos=(x, -34.2, 0), h=r.uniform(-20, 20), scale=1.3,
                           color=(0.72, 0.66, 0.55, 1))
        self.kit.wallBox((-10, -35.5, 0), (10, -33.2, 2.2))
        # The wall gags on the front wall.
        self.wallGag((G.THROW, 1), (-6, -36, 0), 0, 200, 'forecourt')     # Kar98k: Fruit Pie Slice
        self.wallGag((G.THROW, 2), (6, -36, 0), 0, 600, 'forecourt')      # Gewehr 43: Cream Pie Slice
        # The mainframe: a riveted cabinet between two lattice towers, a
        # gear on top, the link pad in front.
        self.mainframe((0, 8, 0))
        self.pad(MAINFRAME_PAD, g, glow=(0.6, 0.9, 1.0))
        self.teleporter('mainframe', MAINFRAME_PAD, 0, role='mainframe')
        # Crates and junk round the walls.
        for x, y, hh, m in ((-31, -31, 10, False), (-27.5, -31.5, 40, True), (31, 18, -15, False), (30, -30, 5, True),
                            (-31, 0, 0, True), (31, 6, 30, False)):
            self.crate((x, y, 0), hh, 0.5, metal=m)
        self.kit.model('phase_10/models/cashbotHQ/gears_A1', pos=(-28, 12, 0), h=90, scale=0.45, color=GRIME)
        self.kit.wallBox((-31, 6.5, 0), (-25, 17.5, 2.8))
        # Lamp posts and cold light.
        for x, y in ((-30, -20), (30, -20)):
            self.kit.model('phase_6/models/karting/GoofyStadium_Lamppost_Base1', pos=(x, y, 0), scale=0.6, color=(0.5, 0.5, 0.55, 1))
            self.kit.wallTube((x, y, 0), 1.0, 10)
            self.lamp((x, y + 2, 13), COLD, 40.0, groups=(g, 'static'))
        self.lamp((0, -6, 18), (0.5, 0.55, 0.7), 50.0, groups=(g,))
        for x in (-20, 20):
            self.cageLight((x, -35.2, 16), g)
            self.cageLight((x, 23.2, 16), g)
        self.powerLamp((0, -10, 16), (1.0, 0.75, 0.5), 50.0, (g,))
        # Cogs come over the walls too.
        self.roofEdge('forecourt', Point3(-20, 24.5, 24.5), Point3(-20, 19, 0), 180)
        self.roofEdge('forecourt', Point3(20, -36.5, 24.5), Point3(16, -31, 0), 0)

    def mainframe(self, pos):
        x, y, z = pos
        self.kit.box((x - 5, y - 2.5, z), (x + 5, y + 3, z + 9), side=PLATE, top=METAL, tile=4, color=STEEL, collide='wall')
        self.kit.box((x - 4, y - 2.7, z + 2), (x + 4, y - 2.5, z + 7), side=PANELS, top=PANELS, tile=4, color=(0.5, 0.52, 0.5, 1),
                     collide=False)
        for dx in (-7.5, 7.5):
            self.kit.model('phase_10/models/cashbotHQ/pipes_A1', pos=(x + dx, y + 0.3, z), scale=(0.32, 0.32, 0.5), color=GRIME)
            self.kit.wallTube((x + dx, y + 0.3, z), 2.2, 15)
            self.kit.beam((x + dx, y + 0.3, z + 14.5), (x, y + 0.3, z + 9.5), 0.5, RUST, color=(0.55, 0.47, 0.42, 1), tile=2)
        self.kit.model('phase_9/models/cogHQ/FactoryGearB', pos=(x, y + 0.3, z + 9.3), scale=(3.0, 3.0, 4.0), color=STEEL)
        # Dials and lamps on the front.
        node = self.kit.visual.attachNewNode('mainframeLamps')
        for i in range(5):
            bulb = self.boxNode(node, (x - 3.4 + i * 1.7 - 0.35, y - 2.9, z + 7.4), (x - 3.4 + i * 1.7 + 0.35, y - 2.6, z + 8.1),
                                CEMENT, color=(0.25, 0.25, 0.25, 1), tile=1)
            self.powerBulbs.append((bulb, (0.4, 1.0, 0.5) if i % 2 else (1.0, 0.35, 0.25)))
        self.text('MAINFRAME', (x, y - 2.95, z + 0.9), 0, 0.9, (0.95, 0.85, 0.5, 1))

    def upgradeRoom(self):
        """Behind the shutter in the forecourt's north wall: Mickey and his
        gag upgrade, shut until all three teleporters are linked."""
        g = 'upgrade'
        self.zone('upgrade', 'the upgrade room', (-8, 24, -1, 8, 38, 12))
        self.floor(-8, 24, 8, 38, 0, PLATE, tile=6, color=STEEL, group=g)
        self.ceiling(-8, 24, 8, 38, 11, CEIL_PLATE, color=(0.5, 0.5, 0.52, 1), group=g)
        self.shell(-8, 24, 8, 38, 0, 11, PANELS, color=GRIME, sides='ewn', group=g, outside={'e': (BLOCKS, FAC_C),
                                                                                             'w': (BLOCKS, FAC_C),
                                                                                             'n': (BLOCKS, FAC_C)})
        self.lamp((0, 32, 9), (0.9, 0.8, 1.0), 20.0, groups=(g,))
        # The shutter, rolled down until the teleporters are linked.
        node = self.root.attachNewNode('upgradeShutter')
        node.setPos(0, 24, 0)
        self.boxNode(node, (-6, -0.25, 0), (6, 0.25, 10), ROLLUP, color=(0.62, 0.6, 0.58, 1), tile=3)
        self.upgradeShutter = node
        solid = self.kit.wallBox((-6, 23.4, 0), (6, 24.6, 10))
        self.shutSolids.append(solid)
        self.upgradeSolid = solid
        self.navAreas.append(('upgrade', (-8, 24.2, 8, 38), (-1, 4)))
        self.text('GAG UPGRADE', (0, 23.3, 11.2), 0, 0.8, (0.95, 0.85, 0.5, 1))

    # --- Animal-testing wing ---

    def hallA(self):
        g = 'hallA'
        self.zone('hallA', 'the testing hall', (-72, -16, -1, -36, 4, 14))
        self.floor(-72, -16, -36, 4, 0, CONCRETE, tile=8, color=GRIME, group=g)
        self.ceiling(-72, -16, -36, 4, 12, CEIL_PLATE, color=(0.48, 0.48, 0.5, 1), group=g, holes=[(-64, -9, -58, -3)])
        self.ceilingHole('hallA', Point3(-61, -6, 0), 12)
        self.shell(-72, -16, -36, 4, 0, 12, CEMENT, color=GRIME, ops={
            'w': [(-6, 8, 0, 9)],
            's': [(-50, 6, 2, 8)],
        }, sides='wsn', group=g, lower=(PANELS, 4.0, GRIME), outside={'s': (BLOCKS, FAC_C), 'n': (BLOCKS, FAC_C)})
        self.threshold(-38, -10, -34, -2, 0, CONCRETE, GRIME, g)
        d = self.door('westdoor', 750, (-36, -10), (-36, -2), 0, 9, ['hallA'], title='the testing wing door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('hallA', (-50, -16, 0), 0)
        self.wallGag((G.SOUND, 1), (-56, 4, 0), 180, 600, 'hallA')      # M1A1: Whistle
        self.pipesAlong((-72, 3.2), (-36, 3.2), 10.8, g)
        for x, hh, m in ((-68, 8, True), (-64.5, -12, False), (-42, 20, False)):
            self.crate((x, -13, 0), hh, 0.5, metal=m)
        self.crate((-68, -13, 2.74), 30, 0.4)
        self.lamp((-54, -6, 10), DIM_AMBER, 24.0, groups=(g,), flicker=True)
        self.cageLight((-54, 3.3, 9), g)
        self.powerLamp((-54, -6, 9), (1.0, 0.8, 0.6), 24.0, (g,))

    def lab(self):
        g = 'lab'
        self.zone('lab', 'the lab', (-112, -28, -1, -72, 8, 16))
        self.floor(-112, -28, -72, 8, 0, FAC_FLOOR, tile=8, color=(0.7, 0.72, 0.7, 1), group=g)
        self.ceiling(-112, -28, -72, 8, 14, CEIL_SQ, tile=8, color=(0.55, 0.57, 0.58, 1), group=g, holes=[(-94, -14, -88, -8)])
        self.ceilingHole('lab', Point3(-91, -11, 0), 14)
        self.shell(-112, -28, -72, 8, 0, 14, TILE, color=LAB_TILE, ops={
            'e': [(-6, 8, 0, 9)],
            'n': [(-96, 8, 0, 9)],
            's': [(-92, 6, 2, 8)],
        }, group=g, lower=(PANELS, 3.5, GRIME), outside={'e': (CEMENT, GRIME), 'w': (BLOCKS, FAC_C), 's': (BLOCKS, FAC_C)},
            tile=4)
        self.threshold(-74, -10, -70, -2, 0, CONCRETE, GRIME, g)
        d = self.door('labdoor', 1000, (-72, -10), (-72, -2), 0, 9, ['lab'], title='the lab door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('lab', (-92, -28, 0), 0)
        self.wallGag((G.SOUND, 3), (-112, -12, 0), -90, 1500, 'lab')    # Trench Gun: Aoogah
        self.boxSpot('lab', (-110.5, 0, 0), 90)
        # The toon cages down the south side, a few smashed open.
        # The cages hang on their chains from the ceiling.
        for i, x in enumerate((-108, -100, -84, -76)):
            self.kit.model('phase_5/models/cogdominium/tt_m_ara_crg_toonCage', pos=(x, -23.5, 0.1), h=self.rand.uniform(-8, 8),
                           scale=0.3, color=(0.95, 0.92, 0.9, 1))
            self.kit.wallTube((x, -23.5, 0), 2.0, 4)
        # Lab benches with their tanks, a chalkboard of cog sums.
        for x, y in ((-100, -8), (-84, -8)):
            self.kit.box((x - 5, y - 1.6, 0), (x + 5, y + 1.6, 3.2), side=PLATE, top=METAL, tile=3, color=STEEL, collide='wall')
            self.kit.model('phase_9/models/cogHQ/ttr_m_prp_gen_gagTank', pos=(x - 2.5, y, 3.2), scale=0.18, color=(0.8, 0.9, 0.7, 1))
            self.kit.model('phase_9/models/cogHQ/ttr_m_prp_gen_gagTank', pos=(x + 2.8, y + 0.3, 3.2), scale=0.14,
                           color=(0.7, 0.85, 0.95, 1))
        self.kit.quad([(-111.9, -24, 5), (-111.9, -18, 5), (-111.9, -18, 9), (-111.9, -24, 9)], CEMENT,
                      [(0, 0), (1, 0), (1, 1), (0, 1)], (0.16, 0.24, 0.18, 1), g)
        self.text('2 + 2 = 5', (-111.6, -21, 7.4), -90, 0.6, (0.85, 0.85, 0.8, 1))
        # The electric trap in the doorway to teleporter A.
        self.trap('labtrap', 'electric', (-100, 4, -92, 12), (-104, 7.2, 0), 180, z=(0, 12),
                  line=(Point3(-100, 8, 0), Point3(-92, 8, 0)))
        self.lamp((-92, -10, 12), (0.75, 0.95, 0.85), 30.0, groups=(g,), flicker=True)
        self.powerLamp((-92, -14, 12), (0.8, 1.0, 0.9), 34.0, (g,))

    def teleA(self):
        g = 'teleA'
        self.zone('teleA', "teleporter A's room", (-112, 8, -1, -72, 56, 26))
        self.floor(-112, 8, -72, 56, 0, PLATE, tile=8, color=STEEL, group=g)
        self.ceiling(-112, 8, -72, 56, 24, CEIL_PLATE, color=(0.45, 0.45, 0.48, 1), group=g, holes=[(-106, 14, -100, 20)])
        self.ceilingHole('teleA', Point3(-103, 17, 0), 24)
        self.shell(-112, 8, -72, 56, 0, 24, CEMENT, color=GRIME, ops={
            'e': [(50, 8, 14, 23)],
            'w': [(40, 6, 2, 8)],
        }, sides='wen', group=g, lower=(PANELS, 4.0, GRIME), outside={'w': (BLOCKS, FAC_C), 'n': (BLOCKS, FAC_C),
                                                                     'e': (BLOCKS, FAC_C)})
        self.threshold(-100, 6, -92, 10, 0, CONCRETE, GRIME, g)
        d = self.door('teleAdoor', 1000, (-100, 8), (-92, 8), 0, 9, ['teleA', 'walkway', 'court'], title="teleporter A's door")
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('teleA', (-112, 40, 0), -90)
        self.wallGag((G.THROW, 3), (-112, 22, 0), -90, 1000, 'teleA')   # MP40: Whole Fruit Pie
        self.pad(PADS['A'], g, glow=(0.6, 0.9, 1.0))
        self.teleporter('A', PADS['A'], 0, role='pad')
        self.text('TELEPORTER A', (-96, 21.5, 9), 180, 1.0, (0.95, 0.85, 0.5, 1))
        self.kit.beam((-100, 21.6, 8.6), (-92, 21.6, 8.6), 0.3, METAL, color=DARK_STEEL, tile=2)
        # Up to the balcony and out onto the walkway.
        self.floor(-92, 44, -72, 56, 14, PLATE, tile=6, color=STEEL, group=g, thick=1.0, under=PLATE)
        self.kit.stairs((-108, 50, 0), -90, 8, 14, run=16, steps=14, side=PLATE, tread=GRATE, color=STEEL, railTex=METAL)
        self.kit.railing([(-92, 46), (-92, 44), (-72, 44)], 14, texPath=METAL, color=DARK_STEEL)
        self.kit.railing([(-92, 56), (-92, 54)], 14, texPath=METAL, color=DARK_STEEL)
        self.kit.model('phase_10/models/cashbotHQ/pipes_E', pos=(-111, 30, 0), h=0, scale=0.6, color=GRIME)
        self.kit.model('phase_10/models/cashbotHQ/boiler_A1', pos=(-80, 16, 0), h=-90, scale=0.6, color=GRIME)
        self.kit.wallTube((-80, 16, 0), 3.4, 9)
        self.lamp((-96, 28, 20), (0.6, 0.75, 0.9), 40.0, groups=(g,))
        self.lamp((-82, 50, 20), DIM_AMBER, 20.0, groups=(g,), flicker=True)
        self.cageLight((-96, 55.2, 12), g)
        self.powerLamp((-96, 30, 18), (0.8, 0.95, 1.0), 40.0, (g,))

    def walkway(self):
        g = 'walkway'
        z = 14
        self.zone('walkway', 'the walkway', (-72, 44, 13, -36, 58, 36), (-36, 44, 13, -12, 58, 30))
        self.floor(-72, 46, -28, 56, z, PLATE, tile=6, color=STEEL, group=g, thick=1.2, under=PLATE)
        # The factory's wall along the north side; railings on the south.
        self.wall((-36, 56.5), (-72, 56.5), 0, 34, BLOCKS, faces='left', tile=10, color=FAC_C, group=g)
        self.kit.railing([(-72, 46), (-28, 46), (-28, 47)], z, texPath=METAL, color=DARK_STEEL)
        self.highWindows((-70, 56.4), (-38, 56.4), 24, g)
        # Bouncing Betties: Marbles, and the Toon-Up Tonic.
        self.wallGag('marbles', (-62, 56.5, z), 180, 1000, 'walkway')   # Bouncing Betties: Marbles
        self.tonic('toonup', (-46, 54.4, z), 180)                       # Juggernog: Toon-Up Tonic
        self.roofEdge('walkway', Point3(-54, 57, 34.5), Point3(-54, 50, z), 180)
        self.roofEdge('walkway', Point3(-68, 57, 34.5), Point3(-68, 50, z), 180)
        # The landing over the courtyard and the stairs down into it.
        self.kit.stairs((-12, 51, 0), 90, 8, 14, run=16, steps=14, side=PLATE, tread=GRATE, color=STEEL, railTex=METAL)
        self.kit.railing([(-36, 56), (-35, 56)], z, texPath=METAL, color=DARK_STEEL)
        self.kit.railing([(-29, 56), (-28, 56), (-28, 55)], z, texPath=METAL, color=DARK_STEEL)
        for x in (-66, -54, -42, -30):
            self.kit.beam((x, 46.2, 0), (x, 46.2, z), 0.6, METAL, color=DARK_STEEL, tile=3)
        self.lamp((-54, 51, z + 8), COLD, 30.0, groups=(g, 'static'))
        self.cageLight((-40, 56, z + 8), g)
        self.powerLamp((-50, 51, z + 7), (1.0, 0.8, 0.6), 26.0, (g,))
        self.bridge()

    def bridge(self):
        """From the landing across the courtyard to the rear factory's
        catwalk: pulled up against the rear wall until the power comes on."""
        z = 14
        d = self.door('bridge', 0, (-35, 56), (-29, 56), z, z + 9, ['rear'], kind='bridge', title='the bridge', power=True)
        node = d['visual']
        node.setPos(-32, 96, z)
        deck = node.attachNewNode('deck')
        self.boxNode(deck, (-3, -40, -0.8), (3, 0, 0), GRATE, color=STEEL, tile=3)
        for x in (-3.1, 2.9):
            self.boxNode(deck, (x, -40, 0), (x + 0.2, 0, 3.4), METAL, color=DARK_STEEL, tile=2)
        for y in range(-38, 0, 6):
            for x in (-3.1, 2.9):
                self.boxNode(deck, (x - 0.1, y - 0.2, 0), (x + 0.3, y + 0.2, 3.4), METAL, color=DARK_STEEL, tile=1)
        node.setP(-88)
        # The deck's floor only exists once it is down.
        floor = self.kit.floorPoly([(-35, 56, z), (-29, 56, z), (-29, 96, z), (-35, 96, z)], 'bridgeFloor')
        self.laterSolids.append(floor)
        d['later'] = [floor]
        self.navAreas.append(('bridge', (-35, 56.5, -29, 95.5), (z - 1, z + 1)))
        # The far end is shut too until it is down.
        stop = self.kit.wallBox((-35, 95.4, z), (-29, 96.6, z + 9))
        self.shutSolids.append(stop)
        d['stops'] = [stop]
        # Its rails stop a toon stepping off (above the courtyard's heads).
        for x in (-35.2, -28.8):
            self.kit.wallSegment((x, 56), (x, 96), z - 0.5, z + 4.5, name='bridgeRail')

    # --- Garage wing ---

    def garage(self):
        g = 'garage'
        self.zone('garage', 'the garage', (36, -30, -1, 80, 10, 20))
        self.floor(36, -30, 80, 10, 0, CONCRETE, tile=8, color=(0.55, 0.53, 0.5, 1), group=g)
        self.ceiling(36, -30, 80, 10, 18, CEIL_PLATE, color=(0.45, 0.45, 0.47, 1), group=g, holes=[(54, -16, 60, -10)])
        self.ceilingHole('garage', Point3(57, -13, 0), 18)
        self.shell(36, -30, 80, 10, 0, 18, CORRUGATED, color=(0.62, 0.6, 0.58, 1), ops={
            'n': [(66, 8, 0, 9)],
            's': [(48, 6, 2, 8)],
        }, sides='nse', group=g, lower=(PANELS, 4.0, GRIME), outside={'s': (BLOCKS, FAC_C),
                                                                     'e': (BLOCKS, FAC_C)}, tile=8)
        self.threshold(34, -10, 38, -2, 0, CONCRETE, GRIME, g)
        d = self.door('eastdoor', 750, (36, -10), (36, -2), 0, 9, ['garage'], title='the garage door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('garage', (48, -30, 0), 0)
        # The big roller door on the east wall, the truck in front of it.
        self.kit.quad([(79.4, -22, 0), (79.4, -6, 0), (79.4, -6, 13), (79.4, -22, 13)], ROLLUP, [(0, 0), (3, 0), (3, 3), (0, 3)],
                      (0.6, 0.58, 0.55, 1), g)
        self.kit.model('phase_12/models/bossbotHQ/Coggolf_cart3', pos=(66, -14, 0), h=90, scale=1.1, color=(0.8, 0.78, 0.75, 1))
        self.kit.wallBox((60, -20.5, 0), (72.5, -7.5, 6))
        self.tonic('seltzer', (40, 8.4, 0), 180)                        # Speed Cola: Speedy Seltzer
        self.wallGag((G.SOUND, 2), (56, 10, 0), 180, 1200, 'garage')    # Double-Barreled: Bugle
        self.boxSpot('garage', (78.5, 2, 0), -90)
        # Oil drums and a tool rack.
        for x, y in ((40, -27), (42.5, -27.5), (40.8, -24.6)):
            self.kit.model('phase_6/models/props/small_round_barrel', pos=(x, y, 0), scale=1.0, color=(0.45, 0.5, 0.42, 1))
            self.kit.wallTube((x, y, 0), 1.3, 3)
        for x, hh, m in ((72, 5, True), (75.2, -10, True), (77, -22, False)):
            self.crate((x, -27, 0), hh, 0.5, metal=m)
        self.pipesAlong((36.8, 9.2), (79, 9.2), 16.2, g)
        self.lamp((58, -10, 16), (0.85, 0.8, 0.7), 34.0, groups=(g,), flicker=True)
        self.cageLight((58, -29.2, 12), g)
        self.powerLamp((58, -12, 15), (1.0, 0.85, 0.65), 34.0, (g,))

    def furnace(self):
        g = 'furnace'
        self.zone('furnace', 'the furnace hall', (56, 10, -1, 96, 44, 18))
        self.floor(56, 10, 96, 44, 0, STONE_FLOOR, tile=8, color=(0.52, 0.48, 0.45, 1), group=g)
        self.ceiling(56, 10, 96, 44, 16, CEIL_PLATE, color=(0.4, 0.38, 0.38, 1), group=g, holes=[(66, 30, 72, 36)])
        self.ceilingHole('furnace', Point3(69, 33, 0), 16)
        self.shell(56, 10, 96, 44, 0, 16, BLOCKS, color=(0.6, 0.52, 0.48, 1), ops={
            'e': [(28, 6, 2, 8)],
            'n': [(80, 8, 0, 9)],
        }, sides='wen', group=g, lower=(PANELS, 4.0, (0.5, 0.42, 0.38, 1)), outside={'w': (BLOCKS, FAC_C), 'e': (BLOCKS, FAC_C)})
        # The garage's north wall is this hall's south wall (x 56..80);
        # the rest of the south side.
        self.wall((56, 10), (96, 10), 0, 16, BLOCKS, openings=[(10, 8, 0, 9)], faces='left', tile=10, color=(0.6, 0.52, 0.48, 1), group=g,
                  lower=(PANELS, 4.0, (0.5, 0.42, 0.38, 1)))
        self.threshold(62, 8, 70, 12, 0, CONCRETE, GRIME, g)
        d = self.door('furnacedoor', 1000, (62, 10), (70, 10), 0, 9, ['furnace'], title='the furnace hall door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('furnace', (96, 28, 0), 90)
        # The two furnaces, burning.
        self.fires = []
        for x in (62, 72):
            self.kit.model('phase_10/models/cashbotHQ/boiler_A1', pos=(x, 39, 0), h=180, scale=0.7, color=(0.7, 0.55, 0.5, 1))
            self.kit.wallTube((x, 39, 0), 4.0, 10)
            mouth = self.kit.visual.attachNewNode('furnaceMouth')
            self.boxNode(mouth, (x - 1.4, 34.9, 1.4), (x + 1.4, 35.2, 3.6), CEMENT, color=(1.0, 0.5, 0.15, 1), tile=1)
            mouth.setLightOff(1)
            self.lamp((x, 33, 3), (1.0, 0.5, 0.2), 18.0, groups=(g,), flicker=True)
        # Coal heaped by them.
        for x, y, w in ((66.5, 31.5, 3.2), (77, 33, 2.4)):
            self.kit.cylinder((x, y, 0), w, 1.1, GRAVEL, sides=10, color=(0.2, 0.19, 0.18, 1), tile=3, cap=GRAVEL, collide=False,
                              group=g, radiusTop=w * 0.35)
        self.kit.model('phase_6/models/props/small_round_barrel', pos=(58.6, 41.5, 0), scale=1.0, color=(0.45, 0.4, 0.36, 1))
        self.wallGag((G.SQUIRT, 2), (96, 18, 0), 90, 1200, 'furnace')    # Thompson: Squirt Gun
        self.tonic('tracks', (58.4, 22, 0), -90)                         # Mule Kick: Training Tracks
        self.tonic('organic', (93.6, 38, 0), 90)                         # Double Tap: Organic Gags
        self.pipesAlong((95.2, 11), (95.2, 43), 14.0, g)
        # The electric trap at the door to teleporter B.
        self.trap('furnacetrap', 'electric', (76, 40, 84, 48), (87, 43.2, 0), 180, z=(0, 12),
                  line=(Point3(76, 44, 0), Point3(84, 44, 0)))
        self.cageLight((86, 43.2, 11), g)
        self.powerLamp((80, 24, 14), (1.0, 0.75, 0.5), 30.0, (g,))

    def teleB(self):
        g = 'teleB'
        self.zone('teleB', "teleporter B's lab", (56, 44, -1, 100, 84, 28))
        self.floor(56, 44, 100, 84, 0, FAC_FLOOR, tile=8, color=(0.62, 0.66, 0.62, 1), group=g)
        self.ceiling(56, 44, 100, 84, 26, CEIL_SQ, tile=8, color=(0.48, 0.5, 0.5, 1), group=g, holes=[(64, 74, 70, 80)])
        self.ceilingHole('teleB', Point3(67, 77, 0), 26)
        self.shell(56, 44, 100, 84, 0, 26, TILE, color=LAB_TILE, ops={
            's': [(80, 8, 0, 9)],
            'w': [(64, 8, 0, 9)],
            'n': [(80, 6, 2, 8)],
        }, group=g, lower=(PANELS, 4.0, GRIME), outside={'w': (STONE, FAC_C), 'e': (BLOCKS, FAC_C),
                                                         'n': (BLOCKS, FAC_C)}, tile=4)
        self.threshold(76, 42, 84, 46, 0, CONCRETE, GRIME, g)
        d = self.door('teleBdoor', 1000, (76, 44), (84, 44), 0, 9, ['teleB'], title="teleporter B's door")
        self.leaves(d, tex=PLATE, color=STEEL)
        self.threshold(54, 60, 58, 68, 0, CONCRETE, GRIME, g)
        d = self.door('teleBcourt', 750, (56, 60), (56, 68), 0, 9, ['court', 'walkway'], title='the courtyard door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('teleB', (80, 84, 0), 180)
        self.pad(PADS['B'], g, glow=(0.6, 0.9, 1.0))
        self.teleporter('B', PADS['B'], 0, role='pad')
        self.text('TELEPORTER B', (72, 83.3, 10), 180, 1.0, (0.95, 0.85, 0.5, 1))
        # The vats of glowing gunk, piped together.
        for x, y in ((62, 50), (70, 50), (62, 78)):
            self.kit.cylinder((x, y, 0), 3.0, 6.0, PLATE, sides=18, color=STEEL, tile=4, cap=None, collide=True, group=g)
            self.kit.cylinder((x, y, 5.6), 2.7, 0.5, CEMENT, sides=18, color=(0.5, 1.0, 0.4, 1), tile=2, collide=False, group='glow')
            self.kit.beam((x, y, 6), (x, y, 26), 0.4, RUST, color=(0.55, 0.47, 0.42, 1), tile=3)
        self.lamp((66, 54, 8), SICK_GREEN, 22.0, groups=(g,), flicker=True)
        # The balcony down the east side, the Glass of Water up there.
        self.floor(88, 48, 100, 80, 14, PLATE, tile=6, color=STEEL, group=g, thick=1.0, under=PLATE)
        self.kit.railing([(88, 80), (88, 64)], 14, texPath=METAL, color=DARK_STEEL)
        self.kit.railing([(88, 56), (88, 48)], 14, texPath=METAL, color=DARK_STEEL)
        # Stairs up along the balcony's front, rising north onto it.
        self.kit.stairs((84, 48, 0), 0, 6, 14, run=16, steps=14, side=PLATE, tread=GRATE, color=STEEL, railTex=METAL)
        self.floor(81, 64, 88, 66, 14, PLATE, tile=6, color=STEEL, group=g, thick=1.0, under=PLATE)
        self.kit.railing([(81, 66), (88, 66)], 14, texPath=METAL, color=DARK_STEEL)
        self.kit.railing([(81, 64), (81, 66)], 14, texPath=METAL, color=DARK_STEEL)
        self.wallGag((G.SQUIRT, 1), (100, 70, 14), 90, 1000, 'teleB')   # Type 100: Glass of Water
        self.boxSpot('teleB', (98.5, 56, 14), -90)
        self.lamp((78, 64, 22), (0.65, 0.85, 0.8), 44.0, groups=(g,))
        self.cageLight((94, 83.2, 22), g)
        self.powerLamp((76, 66, 20), (0.85, 1.0, 0.95), 44.0, (g,))

    # --- The power courtyard ---

    def court(self):
        g = 'court'
        self.zone('court', 'the power courtyard', (-36, 44, -1, 56, 96, 36))
        self.floor(-36, 44, 56, 96, 0, GRAVEL, tile=10, color=YARD_C, group=g)
        self.kit.quad([(-6, 70, 0.03), (40, 70, 0.03), (40, 94, 0.03), (-6, 94, 0.03)], CONCRETE, [(0, 0), (5, 0), (5, 2.6), (0, 2.6)],
                      (0.6, 0.58, 0.56, 1), g)
        # West wall (the walkway comes through it up high); the south wall
        # with the passage from the forecourt; the rear factory's wall north.
        self.wall((-36, 96), (-36, 44), 0, 24, STONE, openings=[(45, 10, 14, 24)], faces='left', tile=10, color=FAC_C, group=g)
        self.wall((-36, 44), (56, 44), 0, 24, STONE, openings=[(62, 8, 0, 10)], faces='left', tile=10, color=FAC_C, group=g)
        # The passage from the forecourt, under the power's shutter.
        self.floor(22, 24, 30, 44, 0, CONCRETE, tile=8, color=GRIME, group=g)
        self.ceiling(22, 24, 30, 44, 10, CEIL_PLATE, color=(0.45, 0.45, 0.47, 1), group=g)
        for x, f in ((21.5, 'right'), (30.5, 'left')):
            self.wall((x, 24), (x, 44), 0, 10, CEMENT, faces='both', tile=8, color=GRIME, group=g)
        d = self.door('passage', 0, (22, 24), (30, 24), 0, 10, ['court', 'walkway'], kind='shutter', title='the shutter', power=True)
        self.shutter(d)
        self.trap('courttrap', 'electric', (22, 30, 30, 38), (32.6, 22.5, 0), 180, z=(0, 10),
                  line=(Point3(22, 34, 0), Point3(30, 34, 0)))
        # The generator and its switch.
        self.generator((40, 86, 0))
        self.switch((30, 95.4, 0), 180)
        self.text('POWER', (30, 95.3, 9), 180, 1.1, (1.0, 0.85, 0.3, 1))
        self.wallGag((G.SQUIRT, 3), (56, 80, 0), 90, 1500, 'court')       # FG42: Seltzer Bottle
        self.boxSpot('courtyard', (-6, 93.5, 0), 0, start=True)
        # Junk: crates, pipes, a toppled gear.
        for x, y, hh, m in ((-30, 62, 0, True), (-27, 59, 30, False), (50, 50, 10, True), (-14, 88, 45, False)):
            self.crate((x, y, 0), hh, 0.5, metal=m)
        self.kit.model('phase_10/models/cashbotHQ/pipes_C', pos=(10, 47, 0), h=0, scale=0.4, color=GRIME)
        # A parked cart, oil drums, sandbags round the generator, lamp
        # posts, pipes along the walls: a yard the cogs work in.
        self.kit.model('phase_12/models/bossbotHQ/Coggolf_cart3', pos=(-22, 76, 0), h=-30, scale=1.1, color=(0.75, 0.72, 0.7, 1))
        self.kit.wallTube((-22, 76, 0), 5.5, 6)
        for x, y in ((52, 58), (54.6, 58.4), (53, 60.8), (-32, 92), (-29.4, 92.6)):
            self.kit.model('phase_6/models/props/small_round_barrel', pos=(x, y, 0), scale=1.0, color=(0.45, 0.5, 0.42, 1))
            self.kit.wallTube((x, y, 0), 1.3, 3)
        r = rng(8)
        for i in range(7):
            a = math.pi * (0.15 + 0.7 * i / 6.0)
            x, y = 40 - math.cos(a) * 11, 86 - math.sin(a) * 9.5
            self.kit.model('phase_5/models/props/sandbag-mod', pos=(x, y, 0), h=math.degrees(-a) + 90 + r.uniform(-10, 10), scale=1.3,
                           color=(0.72, 0.66, 0.55, 1))
        for x, y in ((-32, 70), (50, 70), (0, 92)):
            self.kit.model('phase_6/models/karting/GoofyStadium_Lamppost_Base1', pos=(x, y, 0), scale=0.6, color=(0.5, 0.5, 0.55, 1))
            self.kit.wallTube((x, y, 0), 1.0, 10)
            self.lamp((x, y, 13), COLD, 34.0, groups=(g, 'static'))
        self.pipesAlong((55.2, 45), (55.2, 95), 18.0, g)
        self.highWindows((-24, 95.4), (54, 95.4), 20, g)
        self.kit.wallBox((-1, 44, 0), (22, 51, 7.5))
        # Cogs come over the walls.
        self.roofEdge('court', Point3(-36.5, 80, 24.5), Point3(-30, 80, 0), -90)
        self.roofEdge('court', Point3(10, 43.5, 24.5), Point3(10, 56, 0), 0)
        self.roofEdge('court', Point3(56.5, 90, 26.5), Point3(50, 90, 0), 90)
        self.roofEdge('court', Point3(40, 96.5, 30.5), Point3(20, 90, 0), 180)
        self.lamp((10, 70, 20), COLD, 60.0, groups=(g, 'static'))
        for x, y in ((-34, 70), (54, 60)):
            self.cageLight((x + (0.8 if x < 0 else -0.8), y, 14), g)
        self.powerLamp((36, 78, 12), (1.0, 0.7, 0.4), 40.0, (g,))

    def generator(self, pos):
        x, y, z = pos
        self.kit.model('phase_10/models/cashbotHQ/boiler_B1', pos=(x, y, z), h=180, scale=0.75, color=(0.75, 0.68, 0.62, 1))
        self.kit.wallBox((x - 7, y - 4.5, z), (x + 7, y + 5, z + 12))
        self.kit.model('phase_10/models/cashbotHQ/gears_A1', pos=(x - 12, y, z), h=0, scale=0.5, color=GRIME)
        self.kit.wallBox((x - 15.5, y - 6, z), (x - 9.5, y + 6, z + 3))
        node = self.kit.visual.attachNewNode('generatorLamps')
        for i in range(3):
            bulb = self.boxNode(node, (x - 2 + i * 2 - 0.4, y - 4.9, z + 10), (x - 2 + i * 2 + 0.4, y - 4.6, z + 10.8), CEMENT,
                                color=(0.25, 0.25, 0.25, 1), tile=1)
            self.powerBulbs.append((bulb, (0.4, 1.0, 0.5)))

    # --- The rear factory and the office ---

    def rear(self):
        g = 'rear'
        z = 14
        self.zone('rear', 'the rear factory', (-36, 96, -1, 56, 136, 32))
        self.floor(-36, 96, 56, 136, 0, CONCRETE, tile=10, color=(0.55, 0.53, 0.5, 1), group=g)
        self.ceiling(-36, 96, 56, 136, 30, CEIL_PLATE, tile=12, color=(0.4, 0.4, 0.42, 1), group=g,
                     holes=[(16, 104, 22, 110), (-20, 112, -14, 118)])
        self.ceilingHole('rear', Point3(19, 107, 0), 30)
        self.ceilingHole('rear', Point3(-17, 115, 0), 30)
        self.shell(-36, 96, 56, 136, 0, 30, BLOCKS, color=FAC_C, ops={
            's': [(-32, 6, 14, 23), (10, 8, 0, 9)],
            'e': [(108, 8, 0, 9)],
            'w': [(116, 6, 2, 8)],
        }, group=g, lower=(PANELS, 4.0, GRIME), outside={'s': (STONE, FAC_C), 'w': (BLOCKS, FAC_C), 'n': (BLOCKS, FAC_C),
                                                         'e': (BLOCKS, FAC_C)})
        self.threshold(6, 94, 14, 98, 0, CONCRETE, GRIME, g)
        d = self.door('reardoor', 1250, (6, 96), (14, 96), 0, 9, ['rear'], title='the factory door')
        self.leaves(d, tex=PLATE, color=STEEL)
        self.window('rear', (-36, 116, 0), -90)
        # The catwalk: down the west wall from the bridge, along the north
        # wall, and stairs down at the east end.
        self.floor(-36, 96, -28, 128, z, GRATE, tile=4, color=STEEL, group=g, thick=1.0, under=PLATE)
        self.floor(-36, 128, 56, 136, z, GRATE, tile=4, color=STEEL, group=g, thick=1.0, under=PLATE)
        self.kit.railing([(-28, 96), (-28, 128), (48, 128)], z, texPath=METAL, color=DARK_STEEL)
        self.kit.stairs((52, 112, 0), 0, 8, 14, run=16, steps=14, side=PLATE, tread=GRATE, color=STEEL, railTex=METAL)
        for x, y in ((-28.4, 104), (-28.4, 120), (0, 128.4), (24, 128.4)):
            self.kit.beam((x, y, 0), (x, y, z), 0.6, METAL, color=DARK_STEEL, tile=3)
        self.wallGag((G.DROP, 1), (6, 136, z), 180, 1200, 'rear')         # STG-44: Sandbag
        self.boxSpot('rear factory', (-20, 98.5, 0), 180)
        # Teleporter C on the floor.
        self.pad(PADS['C'], g, glow=(0.6, 0.9, 1.0))
        self.teleporter('C', PADS['C'], 0, role='pad')
        self.text('TELEPORTER C', (10, 121, 9), 180, 1.0, (0.95, 0.85, 0.5, 1))
        self.kit.beam((6, 121.2, 8.6), (14, 121.2, 8.6), 0.3, METAL, color=DARK_STEEL, tile=2)
        self.kit.beam((10, 121.2, 0), (10, 121.2, 8.6), 0.3, METAL, color=DARK_STEEL, tile=2)
        # The machines: the stamping press and the mixer over it, the
        # lattice towers.
        # The press: it stamps down on its bed and back up, all game.
        press = self.root.attachNewNode('press')
        press.setPos(30, 112, 26)
        self.kit.model('phase_9/models/cogHQ/PaintMixer', parent=press, scale=0.6, color=GRIME)
        self.boxNode(press, (-0.6, -0.6, 0), (0.6, 0.6, 6), METAL, color=DARK_STEEL, tile=2)
        self.keepLooping(Sequence(Wait(1.2), LerpPosInterval(press, 0.35, Point3(30, 112, 19.2), blendType='easeIn'),
                                  Func(self.pressThump), Wait(0.5),
                                  LerpPosInterval(press, 2.2, Point3(30, 112, 26), blendType='easeInOut')))
        self.kit.box((25, 107, 0), (35, 117, 3), side=PLATE, top=METAL, tile=4, color=STEEL, collide='wall')
        for x, y in ((-12, 104), (-12, 124), (40, 102)):
            self.kit.model('phase_10/models/cashbotHQ/pipes_A1', pos=(x, y, 0), scale=(0.3, 0.3, 0.99), color=GRIME)
            self.kit.wallTube((x, y, 0), 2.0, 30)
        self.kit.model('phase_10/models/cashbotHQ/crates_A', pos=(-24, 132, 0), scale=0.4, color=GRIME)
        self.highWindows((-34, 135.4), (54, 135.4), 22, g)
        self.lamp((10, 112, 24), (0.6, 0.65, 0.8), 55.0, groups=(g,))
        self.lamp((-32, 112, 20), DIM_AMBER, 22.0, groups=(g,), flicker=True)
        self.cageLight((-35.2, 104, 22), g)
        self.cageLight((55.2, 120, 22), g)
        self.powerLamp((20, 120, 26), (1.0, 0.85, 0.6), 55.0, (g,))

    def office(self):
        g = 'office'
        self.zone('office', 'the office', (56, 100, -1, 84, 132, 14))
        self.floor(56, 100, 84, 132, 0, PLANKS, tile=6, color=(0.62, 0.55, 0.48, 1), group=g)
        self.ceiling(56, 100, 84, 132, 12, CEILING, color=(0.5, 0.48, 0.45, 1), group=g, holes=[(70, 120, 76, 126)])
        self.ceilingHole('office', Point3(73, 123, 0), 12)
        self.shell(56, 100, 84, 132, 0, 12, WALLPAPER, color=(0.62, 0.6, 0.55, 1), ops={
            'e': [(116, 6, 2, 8)],
        }, sides='nse', group=g, lower=(WAINSCOT, 4.0, PANEL), outside={'n': (BLOCKS, FAC_C), 's': (BLOCKS, FAC_C),
                                                                        'e': (BLOCKS, FAC_C)})
        self.threshold(54, 104, 58, 112, 0, CONCRETE, GRIME, g)
        d = self.door('officedoor', 750, (56, 104), (56, 112), 0, 9, ['office'], title='the office door')
        self.leaves(d)
        self.window('office', (84, 116, 0), 90)
        self.tonic('wind', (60, 130.4, 0), 180, needsPower=False)          # Quick Revive: Second Wind
        self.wallGag('cane', (70, 132, 0), 180, 3000, 'office')           # Bowie Knife: Bamboo Cane
        self.boxSpot('office', (82.5, 106, 0), -90)
        # The foreman's desk, chair, cabinets.
        self.kit.model('phase_11/models/lawbotHQ/LB_deskA', pos=(70, 110, 0), h=180, scale=0.8, color=(0.75, 0.65, 0.55, 1))
        self.kit.wallBox((65, 107, 0), (75, 113, 3.5))
        self.kit.model('phase_11/models/lawbotHQ/LB_chairA', pos=(70, 114, 0), h=180, scale=0.6)
        self.kit.model('phase_11/models/lawbotHQ/LB_bookshelfA', pos=(83.4, 126, 0), h=90, scale=0.6, color=(0.7, 0.62, 0.55, 1))
        self.kit.wallBox((82, 122, 0), (84, 130, 4.5))
        self.poster((56.6, 124, 4.5), -90)
        self.lamp((70, 116, 10), AMBER, 26.0, groups=(g,), flicker=True)
        self.powerLamp((70, 116, 10), (1.0, 0.85, 0.6), 26.0, (g,))

    # --- Detail: flat on floors and walls, or overhead ---

    def dressForecourt(self):
        g = 'forecourt'
        self.scatterGrime(-34, -34, 34, 22, 0, g, 22, 41)
        # Oil under the mainframe, puddles in the gravel.
        for c, sz in (((0, 3), 9.0), ((-4, 12), 5.0), ((6, 13), 4.0)):
            self.grime(c, sz, g, color=(0.05, 0.05, 0.05, 0.6))
        for c, sz in (((-20, -18), 6.0), ((18, 2), 5.0), ((-8, -30), 4.5)):
            self.grime(c, sz, g, color=(0.18, 0.22, 0.3, 0.55), lift=0.05)
        # Warning paint round the mainframe's apron and the pad.
        for a, b in (((-14, -10), (14, -10)), ((-14, 16), (14, 16)), ((-14, -10), (-14, 16)), ((14, -10), (14, 16))):
            self.hazard(a, b, 1.0, g)
        # Cables from the mainframe to the walls (flat on the ground).
        self.floorCable([(5, 6), (12, 9), (22, 12), (35.4, 12)], 0, g)
        self.floorCable([(-5, 7), (-15, 2), (-26, -4), (-35.4, -5)], 0, g)
        self.floorCable([(0, 5.4), (0, 3.2)], 0, g, thick=0.2)
        self.drain((-18, 6), 2.5, g)
        self.drain((20, -24), 2.5, g)
        self.papers(-30, -30, 30, 18, 0, g, 10, 5, color=(0.7, 0.68, 0.62, 1))
        # Signs, plates, vents and conduits on the walls.
        self.sign((0, 23.5, 13.5), 180, 'NO TOONS\nPAST THIS POINT', g, plate=(0.8, 0.14, 0.1, 1), ink=(1, 0.95, 0.85, 1))
        self.sign((-22, -35.5, 10.5), 0, 'LOADING\nGATE', g)
        self.sign((22, -35.5, 10.5), 0, 'LOADING\nGATE', g)
        self.sign((-35.5, -21, 8), -90, 'TESTING WING', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        self.sign((35.5, 4, 8), 90, 'GARAGE', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        self.sign((5.6, 8, 11.6), -90, 'DANGER\nHIGH VOLTAGE', g, scale=0.42)
        for x in (-30, -16, 30):
            self.panel((x, 23.5, 3.5), 180, 4.5, 3.6, RIVET_PLATE, g, color=(0.8, 0.78, 0.75, 1))
        self.vent((-35.5, 4, 17), -90, 4, 3, g)
        self.vent((35.5, -24, 17), 90, 4, 3, g)
        self.vent((28, -35.5, 18), 0, 4, 3, g)
        self.conduit((-35.5, -28), -90, 0, 24, g)
        self.conduit((35.5, 20), 90, 0, 24, g)
        self.conduit((-12, -35.5), 0, 0, 24, g)
        # Alive: the big gears on the wall turn, the mainframe blinks and
        # its stacks puff steam.
        self.spinningGear((-21, 23.5, 20.5), 180, 6.0, 14.0)
        self.spinningGear((-15.6, 23.5, 21.6), 180, 3.6, 8.4, backwards=True)
        self.spinningGear((31, -35.5, 21), 0, 4.0, 10.0)
        for i, c in enumerate(((1, 0.3, 0.2), (0.4, 1, 0.4), (1, 0.8, 0.2), (0.4, 0.7, 1))):
            self.blinker((-3.6 + i * 2.4, 5.4, 1.9), 180, c, on=0.4 + 0.15 * i, off=0.5 + 0.1 * i, phase=0.2 * i)
        for x in (-7.5, 7.5):
            self.steam((x, 8.3, 15.3), every=1.8 + abs(x) * 0.02, size=2.6, rise=7.0, color=(0.8, 0.8, 0.82, 0.45))

    def dressTestingWing(self):
        # The testing hall.
        g = 'hallA'
        self.scatterGrime(-71, -15, -37, 3, 0, g, 10, 51)
        self.papers(-70, -14, -38, 2, 0, g, 6, 52)
        self.drain((-60, -10), 2.2, g)
        self.hazard((-38, -10), (-38, -2), 0.9, g)
        self.sign((-50, -15.5, 9.4), 0, 'ANIMAL\nTESTING', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        self.sign((-71.5, -12, 6.5), -90, 'LAB  -->', g, scale=0.6, plate=(0.85, 0.82, 0.75, 1))
        self.panel((-43, 3.5, 3.0), 180, 5.0, 4.0, RIVET_PLATE, g, color=(0.8, 0.78, 0.75, 1))
        self.vent((-64, 3.5, 7.4), 180, 3.2, 2.2, g)
        self.conduit((-71.5, 0), -90, 0, 12, g)
        self.swingingLamp((-46, -6, 12), 2.4, g, color=(1.0, 0.82, 0.55), angle=3.0, seconds=3.4, reach=18.0)
        # The lab.
        g = 'lab'
        self.scatterGrime(-111, -27, -73, 7, 0, g, 12, 61, color=(0.16, 0.2, 0.12, 0.4))
        self.papers(-110, -20, -76, 6, 0, g, 12, 62)
        self.drain((-92, -16), 2.4, g)
        self.drain((-80, 2), 2.0, g)
        self.hazard((-100, 4), (-92, 4), 0.9, g)
        for x in (-108, -100, -84, -76):
            self.grime((x, -23.5), 3.4, g, color=(0.05, 0.05, 0.04, 0.55))
        self.sign((-92, -27.5, 10.4), 0, 'SPECIMENS - DO NOT FEED', g, plate=(0.85, 0.82, 0.75, 1))
        self.sign((-72.5, -20, 10.4), 90, 'BIOHAZARD', g, plate=(0.85, 0.7, 0.18, 1))
        # A machine on the east wall, its lights blinking.
        self.panel((-72, -22, 3.2), 90, 6.0, 6.0, MACHINE_PANEL, g, frame=(0.45, 0.45, 0.47, 1))
        for i, c in enumerate(((1, 0.3, 0.2), (0.4, 1, 0.4), (1, 0.8, 0.2))):
            self.blinker((-72, -24.2 + i * 1.6, 10.0), 90, c, on=0.35 + 0.2 * i, off=0.6, phase=0.3 * i)
        self.vent((-111.9, 2, 9.2), -90, 3.2, 2.2, g)
        self.conduit((-111.9, -27), -90, 0, 14, g)
        self.conduit((-72.5, 6), 90, 0, 14, g, box=False)
        for x, y in ((-100, -8), (-84, -8)):
            self.steam((x - 2.5, y, 4.9), every=2.6, size=1.4, rise=3.5, color=(0.6, 1.0, 0.5, 0.35))
        # Teleporter A's room.
        g = 'teleA'
        self.scatterGrime(-111, 9, -73, 55, 0, g, 14, 71)
        self.papers(-110, 10, -74, 42, 0, g, 6, 72)
        p = PADS['A']
        for a, b in (((-6.5, -6.5), (6.5, -6.5)), ((-6.5, 6.5), (6.5, 6.5)), ((-6.5, -6.5), (-6.5, 6.5)), ((6.5, -6.5), (6.5, 6.5))):
            self.hazard((p[0] + a[0], p[1] + a[1]), (p[0] + b[0], p[1] + b[1]), 0.9, g)
        self.floorCable([(p[0] + 4.5, p[1] + 1), (-84, 31), (-72.4, 33)], 0, g)
        self.floorCable([(p[0] - 4.5, p[1] - 1), (-106, 26), (-111.6, 26)], 0, g)
        self.panel((-72, 33, 3.2), 90, 6.0, 6.0, MACHINE_PANEL, g, frame=(0.45, 0.45, 0.47, 1))
        for i, c in enumerate(((0.4, 0.8, 1.0), (1, 0.8, 0.2), (0.4, 1, 0.4), (1, 0.3, 0.2))):
            self.blinker((-72, 30.6 + i * 1.6, 10.0), 90, c, on=0.3 + 0.1 * i, off=0.5 + 0.15 * i, phase=0.25 * i)
        self.sign((-72.5, 22, 12.5), 90, 'KEEP CLEAR OF PAD', g, scale=0.6)
        self.chainHang((-84, 36, 24), 9, g)
        self.chainHang((-104, 40, 24), 6, g)
        self.chainHang((-88, 14, 24), 7, g)
        self.spinningGear((-100, 55.5, 19), 180, 6.0, 15.0)
        self.spinningGear((-94.6, 55.5, 20.6), 180, 3.4, 8.5, backwards=True)
        self.vent((-111.9, 48, 18), -90, 4, 3, g)
        self.steam((-80, 16, 10.2), every=2.0, size=2.4, rise=8.0)
        # The walkway.
        g = 'walkway'
        self.scatterGrime(-71, 47, -29, 55, 14, g, 8, 81)
        for a, b in (((-72, 46.6), (-28, 46.6)),):
            self.hazard(a, b, 0.7, g, z=14)
        self.sign((-54, 56, 20.5), 180, 'CAUTION\nWATCH YOUR STEP', g)
        self.conduit((-70, 56), 180, 14, 34, g)
        self.conduit((-38, 56), 180, 14, 34, g)
        self.vent((-62, 56, 24), 180, 4, 3, g)
        self.spinningGear((-46, 56, 28), 180, 7.0, 16.0)
        self.spinningGear((-39.8, 56, 30.2), 180, 4.0, 9.0, backwards=True)

    def dressGarageWing(self):
        # The garage: oil under the cart, tyre tracks, the bay painted out.
        g = 'garage'
        self.scatterGrime(37, -29, 79, 9, 0, g, 12, 91)
        for c, sz in (((66, -14), 10.0), ((70, -11), 4.0), ((42, -25), 5.0)):
            self.grime(c, sz, g, color=(0.04, 0.04, 0.04, 0.6))
        for y in (-17.5, -10.5):
            self.floorPic((60, y), 36, 1.6, SOFT_SPOT, g, color=(0.05, 0.05, 0.05, 0.35), lift=0.042)
        self.hazard((78.6, -22), (78.6, -6), 1.4, g)
        for a, b in (((48, -22), (48, -6)), ((76, -24), (52, -24)), ((76, -4), (52, -4))):
            self.floorPic(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), abs(b[0] - a[0]) + 0.4, abs(b[1] - a[1]) + 0.4, CEMENT, g,
                          color=(0.85, 0.75, 0.25, 1), lift=0.045)
        self.drain((50, -14), 2.4, g)
        self.papers(38, -28, 78, 8, 0, g, 6, 92)
        self.sign((58, -29.5, 10.5), 0, 'LOADING BAY', g)
        self.sign((79.5, -14, 15), 90, 'NO PARKING', g, plate=(0.8, 0.14, 0.1, 1), ink=(1, 0.95, 0.85, 1), scale=0.7)
        self.panel((48, 9.5, 3.0), 180, 4.4, 4.0, RIVET_PLATE, g, color=(0.8, 0.78, 0.75, 1))
        self.vent((44, -29.5, 12), 0, 4, 3, g)
        self.vent((79.5, 4, 12), 90, 3.2, 2.2, g)
        self.conduit((79.5, -28), 90, 0, 18, g)
        self.conduit((36.5, 4), -90, 0, 18, g, box=False)
        self.chainHang((58, -20, 18), 6, g)
        self.chainHang((62, -20, 18), 6, g)
        self.swingingLamp((50, 0, 18), 3.0, g, color=(1.0, 0.85, 0.6), angle=3.5, seconds=3.8, reach=20.0)
        # The furnace hall: soot, the furnaces smoking, the walls scorched.
        g = 'furnace'
        self.scatterGrime(57, 11, 95, 43, 0, g, 14, 101, color=(0.08, 0.07, 0.06, 0.5))
        for x in (62, 72):
            self.grime((x, 33.4), 6.0, g, color=(0.03, 0.03, 0.03, 0.6))
            self.wallPic((x, 44, 7.5), 180, 8.0, 8.5, SOFT_SPOT, g, color=(0.02, 0.02, 0.02, 0.45), off=0.05)
            self.steam((x, 39, 10.6), every=1.6, size=3.2, rise=6.0, color=(0.22, 0.2, 0.19, 0.6))
        self.hazard((57, 34.4), (78, 34.4), 1.0, g)
        self.drain((86, 20), 2.4, g)
        self.papers(78, 12, 94, 30, 0, g, 3, 102, color=(0.7, 0.66, 0.6, 1))
        self.sign((56.5, 34, 10), -90, 'FURNACE ROOM', g)
        self.sign((88, 43.5, 10.8), 180, 'HOT!  KEEP BACK', g, plate=(0.8, 0.14, 0.1, 1), ink=(1, 0.95, 0.85, 1), scale=0.65)
        self.panel((95.5, 30, 10.5), 90, 5.0, 3.6, RIVET_PLATE, g, color=(0.7, 0.62, 0.58, 1))
        self.spinningGear((95.5, 22.5, 12.6), 90, 4.0, 10.0)
        self.vent((56.5, 14, 10), -90, 3.2, 2.2, g)
        self.conduit((56.5, 42), -90, 0, 16, g)
        self.swingingLamp((84, 28, 16), 2.6, g, color=(1.0, 0.7, 0.45), angle=3.0, seconds=4.0, reach=18.0)
        # Teleporter B's lab: green gunk, the pad, the machines.
        g = 'teleB'
        self.scatterGrime(57, 45, 87, 83, 0, g, 12, 111, color=(0.14, 0.2, 0.1, 0.45))
        for x, y in ((62, 50), (70, 50), (62, 78)):
            self.grime((x, y), 9.0, g, color=(0.25, 0.55, 0.15, 0.4))
            self.steam((x, y, 6.4), every=2.4, size=2.0, rise=5.0, color=(0.55, 1.0, 0.45, 0.35))
        self.grime((66, 56), 4.0, g, color=(0.3, 0.65, 0.18, 0.45))
        p = PADS['B']
        for a, b in (((-6.5, -6.5), (6.5, -6.5)), ((-6.5, 6.5), (6.5, 6.5)), ((-6.5, -6.5), (-6.5, 6.5)), ((6.5, -6.5), (6.5, 6.5))):
            self.hazard((p[0] + a[0], p[1] + a[1]), (p[0] + b[0], p[1] + b[1]), 0.9, g)
        self.floorCable([(p[0] - 4.4, p[1] - 1), (66, 58), (64, 52.8)], 0, g)
        self.floorCable([(p[0] - 4.4, p[1] + 1), (64, 72), (62, 75.2)], 0, g)
        self.floorCable([(p[0] + 4.4, p[1]), (80, 66), (80.8, 66)], 0, g)
        self.drain((76, 54), 2.4, g)
        self.papers(58, 56, 80, 82, 0, g, 6, 112)
        self.panel((56.5, 74, 3.2), -90, 6.0, 6.0, MACHINE_PANEL, g, frame=(0.45, 0.45, 0.47, 1))
        for i, c in enumerate(((0.4, 1, 0.4), (1, 0.3, 0.2), (0.4, 0.8, 1.0), (1, 0.8, 0.2))):
            self.blinker((56.5, 71.6 + i * 1.6, 10.0), -90, c, on=0.3 + 0.12 * i, off=0.55, phase=0.2 * i)
        self.sign((56.5, 52, 11), -90, 'BIOHAZARD', g)
        self.sign((99.5, 64, 21.5), 90, 'OBSERVATION', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        self.hazard((88.6, 48), (88.6, 64), 0.7, g, z=14)
        self.hazard((88.6, 66), (88.6, 80), 0.7, g, z=14)
        self.spinningGear((64, 83.5, 18), 180, 6.0, 14.0)
        self.spinningGear((69.4, 83.5, 19.8), 180, 3.6, 8.0, backwards=True)
        self.chainHang((76, 74, 26), 8, g)
        self.vent((99.5, 76, 20), 90, 3.2, 2.2, g)
        self.conduit((99.5, 46), 90, 0, 26, g)

    def pressThump(self):
        game = getattr(self, 'game', None)
        if game is None or not hasattr(self, 'pressSfx'):
            return
        player = getattr(game, 'player', None)
        if player is None:
            return
        far = (player.getPos() - Point3(30, 112, 0)).length()
        if far < 70:
            base.playSfx(self.pressSfx, volume=max(0.0, 0.5 - far / 140.0))

    def dressCourtAndRear(self):
        # The courtyard: puddles, oil, the generator's cables, signs.
        g = 'court'
        self.scatterGrime(-35, 45, 55, 95, 0, g, 24, 121)
        for c, sz in (((0, 64), 7.0), ((26, 80), 6.0), ((-24, 88), 5.0), ((44, 56), 6.0)):
            self.grime(c, sz, g, color=(0.18, 0.22, 0.3, 0.55), lift=0.05)
        self.grime((40, 84), 12.0, g, color=(0.04, 0.04, 0.04, 0.6))
        self.grime((-22, 76), 8.0, g, color=(0.04, 0.04, 0.04, 0.55))
        self.floorCable([(33, 86), (31, 90), (30, 94.6)], 0, g)
        self.floorCable([(40, 80.6), (34, 72), (26, 52), (26, 44.8)], 0, g)
        self.floorCable([(47, 86), (55.4, 86)], 0, g)
        for a, b in (((22, 44.6), (30, 44.6)), ((6, 95.2), (14, 95.2))):
            self.hazard(a, b, 0.9, g)
        self.drain((10, 70), 2.6, g)
        self.drain((-14, 52), 2.4, g)
        self.papers(-30, 50, 50, 92, 0, g, 12, 122, color=(0.7, 0.68, 0.62, 1))
        self.sign((48, 95.2, 9), 180, 'DANGER\nHIGH VOLTAGE', g)
        self.sign((10, 95.2, 11.5), 180, 'ASSEMBLY HALL', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        self.sign((26, 44.6, 11.5), 0, 'TO FORECOURT', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1), scale=0.6)
        self.sign((55.5, 64, 10.5), 90, 'LAB', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1))
        for x in (-20, 0, 40):
            self.panel((x, 44.6, 3.0), 0, 4.6, 4.0, RIVET_PLATE, g, color=(0.8, 0.78, 0.75, 1))
        self.vent((-35.5, 66, 16), -90, 4, 3, g)
        self.vent((55.5, 50, 16), 90, 4, 3, g)
        self.conduit((-35.5, 90), -90, 0, 24, g)
        self.conduit((55.5, 92), 90, 0, 26, g)
        self.spinningGear((-35.5, 60, 19), -90, 6.0, 13.0)
        self.spinningGear((-35.5, 54.6, 20.8), -90, 3.6, 7.8, backwards=True)
        self.steam((36.4, 86, 13.4), every=1.5, size=3.0, rise=8.0, color=(0.75, 0.75, 0.78, 0.5))
        self.steam((44, 86.6, 16.8), every=2.0, size=2.4, rise=8.0, color=(0.75, 0.75, 0.78, 0.45))
        for i, c in enumerate(((1, 0.3, 0.2), (1, 0.8, 0.2))):
            self.blinker((28.6 + i * 2.8, 95.2, 6.8), 180, c, on=0.5, off=0.5, phase=0.5 * i)
        # The rear factory: the press bed painted, oil, the pad.
        g = 'rear'
        self.pressSfx = base.loader.loadSfx('phase_9/audio/sfx/CHQ_FACT_stomper_med.ogg')
        self.scatterGrime(-35, 97, 55, 127, 0, g, 22, 131)
        for a, b in (((23.5, 105.5), (36.5, 105.5)), ((23.5, 118.5), (36.5, 118.5)), ((23.5, 105.5), (23.5, 118.5)),
                     ((36.5, 105.5), (36.5, 118.5))):
            self.hazard(a, b, 1.0, g)
        p = PADS['C']
        for a, b in (((-6.5, -6.5), (6.5, -6.5)), ((-6.5, 6.5), (6.5, 6.5)), ((-6.5, -6.5), (-6.5, 6.5)), ((6.5, -6.5), (6.5, 6.5))):
            self.hazard((p[0] + a[0], p[1] + a[1]), (p[0] + b[0], p[1] + b[1]), 0.9, g)
        self.floorCable([(p[0] + 4.4, p[1]), (20, 110), (24.4, 110)], 0, g)
        self.floorCable([(p[0] - 4.4, p[1]), (-4, 116), (-27.6, 120)], 0, g)
        self.grime((30, 112), 10.0, g, color=(0.04, 0.04, 0.04, 0.55))
        for c in ((40, 124), (-6, 102), (46, 100)):
            self.grime(c, 6.0, g, color=(0.04, 0.04, 0.04, 0.5))
        self.drain((-2, 124), 2.6, g)
        self.drain((44, 118), 2.4, g)
        self.papers(-26, 98, 46, 126, 0, g, 10, 132)
        self.hazard((-28.6, 96), (-28.6, 128), 0.7, g, z=14)
        self.hazard((-28, 128.6), (48, 128.6), 0.7, g, z=14)
        self.sign((30, 135.4, 21), 180, 'PRODUCTION LINE', g)
        self.sign((55.5, 108, 11), 90, 'FOREMAN', g, plate=(0.25, 0.3, 0.35, 1), ink=(0.95, 0.95, 0.9, 1), scale=0.7)
        self.sign((30, 96.6, 9.5), 0, 'KEEP CLEAR OF PRESS', g, plate=(0.8, 0.14, 0.1, 1), ink=(1, 0.95, 0.85, 1), scale=0.65)
        for x in (-12, 20, 44):
            self.panel((x, 135.4, 3.2), 180, 5.0, 4.4, RIVET_PLATE, g, color=(0.8, 0.78, 0.75, 1))
        self.panel((-35.5, 104, 3.2), -90, 6.0, 6.0, MACHINE_PANEL, g, frame=(0.45, 0.45, 0.47, 1))
        for i, c in enumerate(((0.4, 1, 0.4), (1, 0.3, 0.2), (1, 0.8, 0.2))):
            self.blinker((-35.5, 101.6 + i * 2.4, 10.0), -90, c, on=0.4, off=0.45 + 0.1 * i, phase=0.3 * i)
        self.spinningGear((4, 135.4, 23.5), 180, 7.0, 16.0)
        self.spinningGear((10.2, 135.4, 25.8), 180, 4.2, 9.6, backwards=True)
        self.spinningGear((55.5, 100.6, 22), 90, 5.0, 12.0)
        self.chainHang((0, 104, 30), 10, g)
        self.chainHang((22, 124, 30), 8, g)
        self.chainHang((-18, 122, 30), 12, g)
        self.vent((-35.5, 124, 20), -90, 4, 3, g)
        self.conduit((-35.5, 132), -90, 0, 30, g)
        self.conduit((55.5, 132), 90, 0, 30, g)
        for x, y in ((-12, 104), (-12, 124), (40, 102)):
            self.steam((x, y, 30.3), every=2.4, size=2.6, rise=4.0, color=(0.7, 0.7, 0.72, 0.4))
        self.swingingLamp((10, 104, 30), 6.0, g, color=(1.0, 0.85, 0.6), angle=2.5, seconds=4.6, reach=24.0)
        # The office: papers everywhere, filing cabinets, a rug.
        g = 'office'
        self.floorPic((70, 112), 14, 10, CARPET, g, color=(0.42, 0.2, 0.18, 1), lift=0.03, uv=[(0, 0), (2, 0), (2, 1.4), (0, 1.4)])
        self.scatterGrime(57, 101, 83, 131, 0, g, 8, 141, color=(0.1, 0.08, 0.06, 0.35))
        self.papers(57, 101, 83, 131, 0, g, 26, 142)
        for x in (63.4, 66.4):
            self.kit.model('phase_11/models/lawbotHQ/LB_filing_cabA', pos=(x, 101.4, 0), h=180, scale=1.1, color=(0.85, 0.82, 0.78, 1))
        self.kit.wallBox((62, 100, 0), (67.8, 102.9, 4.6))
        self.kit.model('phase_11/models/lawbotHQ/LB_CardBoardBox', pos=(58.4, 101.8, 0), h=12, scale=0.3, color=(0.85, 0.82, 0.78, 1))
        self.kit.wallBox((57, 100.4, 0), (59.8, 103.2, 2.8))
        self.sign((70, 100.6, 9), 0, 'QUOTA:  MORE GAGS', g, plate=(0.85, 0.82, 0.75, 1), scale=0.6)
        self.panel((83.5, 110, 4.5), 90, 4.0, 3.0, 'phase_9/maps/mickeyposter.jpg', g, color=(0.8, 0.75, 0.7, 1), frame=(0.35, 0.25, 0.2, 1))
        self.wallPic((76, 131.5, 3.2), 180, 4.0, 5.0, SOFT_SPOT, g, color=(0.1, 0.08, 0.06, 0.35), off=0.04)
        self.vent((64, 131.5, 9), 180, 2.6, 1.8, g)
        self.swingingLamp((70, 120, 12), 2.2, g, color=(1.0, 0.85, 0.6), angle=2.0, seconds=4.0, reach=16.0)

    def yards(self):
        """The ground between the buildings nobody can reach, seen from the
        walkway: gravel, junk."""
        g = 'yard'
        self.floor(-72, 4, -36, 58, 0, GRAVEL, tile=10, color=(0.45, 0.44, 0.43, 1), group=g, name='yard')
        self.floor(-36, 24, 22, 44, 0, GRAVEL, tile=10, color=(0.45, 0.44, 0.43, 1), group=g, name='yard')
        # The walls round them that the rooms don't already give.
        self.wall((-72, 4), (-72, 8), 0, 24, BLOCKS, faces='both', tile=10, color=FAC_C, group=g)
        self.wall((-36, 24), (-36, 44), 0, 24, BLOCKS, faces='both', tile=10, color=FAC_C, group=g)
        self.wall((-8, 38), (8, 38), 0, 11, BLOCKS, faces='both', tile=10, color=FAC_C, group=g)
        for x, y in ((-60, 14), (-50, 30), (-20, 34)):
            self.kit.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, 0), h=self.rand.uniform(0, 90), scale=0.5,
                           color=(0.6, 0.55, 0.5, 1))
        self.kit.model('phase_10/models/cashbotHQ/pipes_D1', pos=(-56, 22, 0), h=90, scale=0.4, color=GRIME)

    # --- In the game: the power, the teleporters, the upgrade ---

    def startGame(self, game):
        Building.startGame(self, game)
        self.linked = {'A': False, 'B': False, 'C': False}
        self.charging = None
        self.chargeUntil = 0.0
        self.coolUntil = {'A': 0.0, 'B': 0.0, 'C': 0.0}
        self.upgradeIsOpen = False

    def setPower(self, on):
        self.lampBoost = 1.1
        own = dict((id(np), color) for np, color in self.powerLamps)
        for np, names, color in self.lamps:
            np.node().setColor(own.get(id(np), color * self.lampBoost))
        for bulb, color in self.powerBulbs:
            bulb.setColorScale(color[0] * 4.0, color[1] * 4.0, color[2] * 4.0, 1)
            bulb.setLightOff(1)
        base.playSfx(base.loader.loadSfx('phase_11/audio/sfx/LB_sparks_1.ogg'), volume=0.8)

    def upgradeOpen(self, game):
        return self.upgradeIsOpen

    def teleporterPrompt(self, game, pad):
        role = pad.entry.get('role')
        now = globalClock.getFrameTime()
        name = pad.entry.get('name')
        if role == 'pad':
            if not game.powerOn:
                return 'The teleporter needs the power on'
            if not self.linked[name]:
                if self.charging == name and now < self.chargeUntil:
                    return 'Run to the mainframe and link it! %d' % int(self.chargeUntil - now + 0.99)
                return 'Use: start teleporter %s' % name
            if now < self.coolUntil[name]:
                return 'The teleporter is cooling down'
            return 'Use: teleport to the mainframe'
        if role == 'mainframe':
            if self.charging and now < self.chargeUntil:
                return 'Use: link teleporter %s' % self.charging
            if game.powerOn and not all(self.linked.values()):
                return 'Start a teleporter, then link it here'
        return ''

    def useTeleporter(self, game, pad):
        role = pad.entry.get('role')
        now = globalClock.getFrameTime()
        name = pad.entry.get('name')
        if role == 'mainframe':
            if self.charging and now < self.chargeUntil:
                self.linked[self.charging] = True
                game.hud.say('Teleporter %s is linked!' % self.charging, 3.0)
                base.playSfx(base.loader.loadSfx('phase_11/audio/sfx/LB_sparks_1.ogg'), volume=0.7)
                self.charging = None
                game.count('teleporters linked')
                if all(self.linked.values()):
                    self.openUpgrade(game)
                return True
            return False
        if role != 'pad' or not game.powerOn:
            return False
        if not self.linked[name]:
            self.charging = name
            self.chargeUntil = now + LINK_TIME
            game.hud.say('Teleporter %s is on! Link it at the mainframe.' % name, 3.0)
            base.playSfx(base.loader.loadSfx('phase_5/audio/sfx/teleport_reappear.ogg'), volume=0.6)
            return True
        if now < self.coolUntil[name]:
            return False
        self.coolUntil[name] = now + TELEPORT_COOL
        game.count('teleports')
        self.warp(game, MAINFRAME_PAD + Vec3(0, 0, 0.8), 180)
        return True

    def openUpgrade(self, game):
        if self.upgradeIsOpen:
            return
        self.upgradeIsOpen = True
        self.upgradeSolid.stash()
        game.arena.openBlocker('upgrade')
        game.hud.say('All three linked: the gag upgrade is open!', 4.0)
        Sequence(LerpPosInterval(self.upgradeShutter, 3.0, self.upgradeShutter.getPos() + Vec3(0, 0, 9.6), blendType='easeInOut'),
                 Func(self.upgradeShutter.stash)).start()
