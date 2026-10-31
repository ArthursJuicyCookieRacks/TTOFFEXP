import math
import random

from panda3d.core import (BitMask32, CardMaker, LineSegs, TextureStage, CollisionBox, CollisionNode, CollisionPlane, ColorBlendAttrib,
                          NodePath, Plane, PNMImage, Point3, Texture, TransparencyAttrib, Vec3, Vec4)

from otp.otpbase import OTPGlobals
from toontown.cogdominium import CogdoCraneGameConsts as Consts
from toontown.toonbase import ToontownGlobals

# The props the junk piles are made of: model, scale range, how tall one is
# at scale 1, and how often it comes up. Safes are most of it, as in the
# concept art; the money and piggy banks are scattered through.
PileProps = (
    ('phase_10/models/cogHQ/CBSafe', (0.45, 0.75), 8.1, 10),
    ('phase_5/models/cogdominium/tt_m_ara_ccg_safesA', (0.55, 0.8), 24.8, 6),
    ('phase_5/models/cogdominium/tt_m_ara_ccg_safesB', (0.55, 0.8), 24.8, 6),
    ('phase_10/models/cashbotHQ/CashBotSafe', (0.2, 0.32), 20.5, 4),
    ('phase_10/models/cashbotHQ/CBMetalCrate', (0.55, 0.8), 5.5, 3),
    ('phase_10/models/cashbotHQ/MoneyBag', (0.55, 0.85), 5.3, 3),
    ('phase_10/models/cashbotHQ/DoubleCoinStack', (0.28, 0.4), 15.9, 1),
    ('phase_10/models/cashbotHQ/GoldBarStack', (0.3, 0.45), 6.8, 1),
    ('phase_5/models/cogdominium/tt_m_ara_cmg_cabinetSmFalling', (0.9, 1.2), 5.1, 2),
    ('phase_5/models/cogdominium/ttr_r_ara_cig_fileCabinet', (0.6, 0.8), 8.0, 2),
    ('phase_3/models/char/pig-heads-1000', (2.0, 2.8), 1.6, 2),
)
# Props for the back of the piles, far from the floor: big and few.
BackProps = (
    ('phase_10/models/cogHQ/CashBotBoxCar', (0.14, 0.17), 55.4, 2),
    ('phase_10/models/cogHQ/CashBotTankCar', (0.12, 0.15), 56.6, 1),
    ('phase_10/models/cashbotHQ/shelf_A1MoneyBags', (0.55, 0.7), 14.1, 2),
    ('phase_10/models/cashbotHQ/VaultDoorCover', (0.45, 0.6), 15.2, 1),
    ('phase_10/models/cashbotHQ/crates_A', (0.5, 0.7), 14.1, 2),
)
# How dark the piles are, away from the lit floor (the concept art is lit
# from the middle of the room).
PileShade = 0.74
CellSize = 7.5


def _gradientTexture(name, radial):
    # A soft white pool of light: brightest in the middle (radial) or along
    # the middle line (a lane), fading to nothing at the edges.
    size = 64
    image = PNMImage(size, size, 4)
    for x in range(size):
        for y in range(size):
            u = (x + 0.5) / size * 2 - 1
            v = (y + 0.5) / size * 2 - 1
            d = math.sqrt(u * u + v * v) if radial else abs(u)
            a = max(0.0, 1.0 - d)
            image.setXelA(x, y, 1, 1, 1, a * a * (3 - 2 * a))
    tex = Texture(name)
    tex.load(image)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    return tex


class CogdoCraneRoom:
    """The Vend-A-Stomper room: the crane room model from the original game
    (tt_m_ara_ccg_level), dressed as the Cashbot field office concept art
    shows it. Piles of safes, money and piggy banks fill the room up to a
    lit floor in the middle, where the Stomp-O-Matic stands; four hallways
    cut through the piles corner to corner, and the cogs come out of their
    doors along lit lanes to the machine."""

    def __init__(self):
        self.root = None
        self.stomper = None
        self.barrels = []

    def load(self):
        self.root = NodePath('craneRoom')
        rng = random.Random(Consts.RoomSeed)
        self._loadLevel()
        self._loadFloorLights()
        self._loadHallways()
        self._loadPiles(rng)
        self._loadCeiling(rng)
        self._loadStomper()
        self._loadCollisions()
        return self.root

    def destroy(self):
        if self.root:
            self.root.removeNode()
        self.root = None
        self.stomper = None
        self.barrels = []

    # --- The room ---

    def _loadLevel(self):
        level = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_ccg_level')
        level.reparentTo(self.root)
        # The model's own floor plane is a 1-unit card scaled up; ours is a
        # real collision plane below.
        level.findAllMatches('**/+CollisionNode').detach()
        self.level = level
        self.conveyor = level.find('**/conveyor_belt')
        self.barrels = [level.find('**/laffBarrel_%d' % i) for i in range(1, 8)]
        self.barrels = [b for b in self.barrels if not b.isEmpty()]
        # Left to right along the belt, so they go in order.
        self.barrels.sort(key=lambda b: b.getY())
        # The prototype's textures are placeholders (a flat magenta wall, a
        # beige floor). The concept art has a pinkish red glow on the walls
        # over the piles, and a grey stone floor.
        wallTex = Texture('craneWall')
        image = PNMImage(4, 4)
        image.fill(*Consts.WallColor)
        wallTex.load(image)
        level.findAllMatches('**/wallBarrier*').setTexture(wallTex, 1)
        floorTex = loader.loadTexture('phase_10/maps/StoneSquares.jpg')
        flooring = level.find('**/flooring')
        flooring.setTexture(floorTex, 1)
        flooring.setTexScale(TextureStage.getDefault(), 18, 18)
        # Its vertex colours are baked shading in blotches; light it evenly.
        flooring.setColor(1, 1, 1, 1, 1)
        flooring.setColorScale(*Consts.FloorColorScale)
        self.ceiling = level.find('**/ceiling')
        self.ceiling.setColorScale(0.35, 0.33, 0.34, 1)

    def _loadFloorLights(self):
        lights = self.root.attachNewNode('floorLights')
        laneTex = _gradientTexture('craneLane', False)
        poolTex = _gradientTexture('cranePool', True)
        cm = CardMaker('lane')
        cm.setFrame(-Consts.LaneWidth / 2.0, Consts.LaneWidth / 2.0, Consts.MachineDistance, Consts.HallwayDistance)
        for angle in Consts.LaneAngles:
            lane = lights.attachNewNode(cm.generate())
            lane.setP(-90)
            lane.setH(angle)
            lane.setTexture(laneTex)
            lane.setColor(0.85, 0.82, 0.8, 0.32)
        cm = CardMaker('pool')
        cm.setFrame(-1, 1, -1, 1)
        pool = lights.attachNewNode(cm.generate())
        pool.setP(-90)
        pool.setScale(Consts.PoolRadius)
        pool.setTexture(poolTex)
        pool.setColor(1, 0.95, 0.9, 0.45)
        # Little pools under each crane's controls.
        for x, y, z, h, p, r in Consts.CranePosHprs:
            spot = lights.attachNewNode(cm.generate())
            spot.setP(-90)
            spot.setPos(x, y, 0)
            spot.setScale(7)
            spot.setTexture(poolTex)
            spot.setColor(1, 0.9, 0.85, 0.3)
        lights.setZ(0.06)
        lights.setTransparency(TransparencyAttrib.MAlpha)
        lights.setDepthWrite(0)
        lights.setBin('ground', 2)
        lights.setLightOff()
        lights.flattenStrong()
        self.floorLights = lights

    def _loadHallways(self):
        # A door at the far end of each hallway: the cogs walk out of it.
        self.hallwayDoors = []
        door = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_csa_exitDoor')
        for angle in Consts.LaneAngles:
            d = door.copyTo(self.root)
            pos = Consts.lanePoint(angle, Consts.HallwayDistance + 2)
            d.setPos(pos)
            d.setH(angle + 180)
            d.setScale(0.7)
            self.hallwayDoors.append(d)
        door.removeNode()

    def _inPlayArea(self, x, y, margin=0.0):
        hx, hy = Consts.PlayHalfSize
        if abs(x) < hx - margin and abs(y) < hy - margin:
            return True
        # The pockets in front of the elevators.
        for px, py, sx, sy in Consts.Pockets:
            if abs(x - px) < sx - margin and abs(y - py) < sy - margin:
                return True
        # The hallways, corner to corner.
        for angle in Consts.LaneAngles:
            rad = math.radians(angle)
            # Distance along the lane (heading 0 is +y, 90 is -x).
            along = -x * math.sin(rad) + y * math.cos(rad)
            across = x * math.cos(rad) + y * math.sin(rad)
            if 0 < along < Consts.HallwayDistance + 4 and abs(across) < Consts.HallwayHalfWidth - margin:
                return True
        return False

    def _depth(self, x, y):
        # How far into the piles a spot is: 0 at the edge of the floor.
        depth = 0
        while depth < 8 and not self._inPlayArea(x, y, margin=-(depth + 1) * CellSize):
            depth += 1
        return depth

    def _loadPiles(self, rng):
        models = {}

        def model(name):
            if name not in models:
                models[name] = loader.loadModel(name)
            return models[name]

        def pick(table):
            total = sum(t[3] for t in table)
            r = rng.uniform(0, total)
            for t in table:
                r -= t[3]
                if r <= 0:
                    return t
            return table[-1]

        # One node per corner of the room, so each flattens to a few
        # geoms and the camera only draws the ones it sees.
        sectors = {}
        hx, hy = Consts.RoomHalfSize
        self.edgeCells = []
        nx = int(hx * 2 / CellSize)
        ny = int(hy * 2 / CellSize)
        for i in range(nx):
            for j in range(ny):
                x = -hx + (i + 0.5) * CellSize
                y = -hy + (j + 0.5) * CellSize
                if self._inPlayArea(x, y, margin=-CellSize * 0.35):
                    continue
                depth = self._depth(x, y)
                if depth <= 1:
                    self.edgeCells.append((x, y))
                key = (x > 0, y > 0, abs(y) > hy * 0.55)
                sector = sectors.get(key)
                if sector is None:
                    sector = sectors[key] = self.root.attachNewNode('pile-%d%d%d' % key)
                self._fillCell(sector, model, pick, rng, x, y, depth)
        for sector in sectors.values():
            sector.setColorScale(PileShade, PileShade, PileShade, 1)
            sector.clearModelNodes()
            sector.flattenStrong()
        for m in models.values():
            m.removeNode()

    def _fillCell(self, parent, model, pick, rng, x, y, depth):
        half = CellSize / 2.0
        if depth >= 3 and rng.random() < 0.22:
            name, scales, height, weight = pick(BackProps)
            prop = model(name).copyTo(parent)
            prop.setPos(x + rng.uniform(-half, half) * 0.5, y + rng.uniform(-half, half) * 0.5, 0)
            prop.setH(rng.uniform(0, 360))
            prop.setScale(rng.uniform(*scales))
            return
        # A few stacks in every cell, taller away from the floor, like a
        # skyline.
        for stack in range(3 if depth else 2):
            sx = x + rng.uniform(-half, half) * 0.8
            sy = y + rng.uniform(-half, half) * 0.8
            if not depth and self._inPlayArea(sx, sy, margin=-1.5):
                continue
            top = Consts.PileHeights[min(depth, len(Consts.PileHeights) - 1)] * rng.uniform(0.6, 1.25)
            if sx < Consts.BeltSideX:
                top = min(top, Consts.BeltSideMaxHeight)
            z = 0.0
            layer = 0
            while z < top:
                name, scales, height, weight = pick(PileProps)
                scale = rng.uniform(*scales)
                prop = model(name).copyTo(parent)
                prop.setH(rng.uniform(0, 360))
                if layer:
                    prop.setP(rng.uniform(-14, 14))
                    prop.setR(rng.uniform(-14, 14))
                if 'safesA' in name or 'safesB' in name:
                    # A cluster of safes on a post: sink the post in.
                    prop.setPos(sx, sy, z - 11.5 * scale)
                    prop.setScale(scale)
                    z += 12.5 * scale
                elif 'pig-heads' in name:
                    # A piggy bank: a big pink pig's head.
                    prop.setColor(0.98, 0.62, 0.72, 1)
                    prop.setPos(sx, sy, z + 0.9 * scale)
                    prop.setScale(scale)
                    z += height * scale
                else:
                    prop.setPos(sx, sy, z)
                    prop.setScale(scale)
                    z += height * scale * 0.85
                layer += 1

    def _loadCeiling(self, rng):
        # Steel beams across the ceiling, like the crane rails in the
        # concept video, with magnets hanging from a few on cables and
        # strip lights between them.
        ceiling = self.root.attachNewNode('ceilingBeams')
        arm = loader.loadModel('phase_10/models/cogHQ/CBCraneArm')
        magnet = loader.loadModel('phase_10/models/cogHQ/CBMagnet')
        hx, hy = Consts.RoomHalfSize
        for y in range(-int(hy) + 18, int(hy), 30):
            beam = arm.copyTo(ceiling)
            beam.setPos(hx, y, Consts.CeilingHeight - 2)
            beam.setH(-90)
            beam.setScale(0.9, hx * 2 / 44.3, 0.9)
        for x in (-38, 38):
            beam = arm.copyTo(ceiling)
            beam.setPos(x, hy, Consts.CeilingHeight - 4)
            beam.setScale(0.8, hy * 2 / 44.3, 0.8)
        cable = LineSegs('cables')
        cable.setThickness(2)
        cable.setColor(0.08, 0.08, 0.08, 1)
        for pos in Consts.HangingMagnets:
            m = magnet.copyTo(ceiling)
            m.setPos(pos)
            m.setScale(2.2)
            m.setH(rng.uniform(-30, 30))
            cable.moveTo(pos)
            cable.drawTo(pos[0], pos[1], Consts.CeilingHeight)
        ceiling.attachNewNode(cable.create())
        tubes = loader.loadTexture('phase_10/maps/CBStationLightTubes.jpg')
        cm = CardMaker('lights')
        cm.setFrame(-5, 5, -2.2, 2.2)
        for x in (-52, -18, 18, 52):
            for y in (-52, -18, 18, 52):
                light = ceiling.attachNewNode(cm.generate())
                light.setPos(x, y, Consts.CeilingHeight - 0.5)
                light.setP(90)
                light.setTexture(tubes)
                light.setLightOff()
        ceiling.setColorScale(0.7, 0.7, 0.72, 1)
        ceiling.flattenStrong()
        arm.removeNode()
        magnet.removeNode()

    def _loadStomper(self):
        self.stomper = loader.loadModel(Consts.StomperModel)
        self.stomper.reparentTo(self.root)
        self.stomper.setPos(0, 0, 0)
        self.stomper.setH(45)
        self.stomperSpikes = self.stomper.find('**/spikes')
        self.stomperDrum = self.stomper.find('**/drum')

    def _loadCollisions(self):
        # The floor, and walls around the piles where the toons walk
        # along them.
        floor = CollisionNode('floor')
        floor.addSolid(CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, 0))))
        floor.setIntoCollideMask(OTPGlobals.FloorBitmask | ToontownGlobals.PieBitmask)
        self.root.attachNewNode(floor)
        walls = CollisionNode('walls')
        half = CellSize / 2.0
        for x, y in self.edgeCells:
            walls.addSolid(CollisionBox(Point3(x - half, y - half, 0), Point3(x + half, y + half, 20)))
        walls.addSolid(CollisionBox(Point3(-3.2, -3.2, 0), Point3(3.2, 3.2, 12)))
        walls.setIntoCollideMask(OTPGlobals.WallBitmask | ToontownGlobals.PieBitmask)
        self.walls = self.root.attachNewNode(walls)
