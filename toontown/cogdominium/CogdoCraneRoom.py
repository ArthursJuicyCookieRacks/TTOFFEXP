import math
import random

from panda3d.core import (BitMask32, CardMaker, LineSegs, TextureStage, CollisionBox, CollisionNode, CollisionPlane, ColorBlendAttrib,
                          Mat4, NodePath, Plane, PNMImage, Point3, SamplerState, TexGenAttrib, Texture, TransformState,
                          TransparencyAttrib, Vec3, Vec4)

from otp.otpbase import OTPGlobals
from toontown.cogdominium import CogdoCraneGameConsts as Consts
from toontown.toonbase import ToontownGlobals

# The props the junk piles are made of: model, scale range, how tall one is
# at scale 1, and how often it comes up. Safes are most of it, as in the
# concept art; the money is scattered through.
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


_wallTex = None


def _wallTexture():
    """The walls over the piles: big grimy stone blocks from the mint,
    stained a dark Cashbot red that glows a little low down (behind the
    piles, as in the concept art) and goes nearly black up by the ceiling,
    with rust streaks running down."""
    blocks = PNMImage()
    source = loader.loadTexture('phase_10/maps/CBMintBigBlocks.jpg')
    if not (source and source.store(blocks)):
        blocks = PNMImage()
    global _wallTex
    if _wallTex:
        return _wallTex
    w, h = 256, 512
    image = PNMImage(w, h, 3)
    rng = random.Random(51)
    streaks = [0.0] * w
    for i in range(14):
        x0 = rng.randrange(w)
        width = rng.randrange(2, 9)
        dark = rng.uniform(0.15, 0.4)
        for x in range(x0, x0 + width):
            streaks[x % w] = max(streaks[x % w], dark)
    low = Consts.WallGlow
    high = Consts.WallTop
    bw, bh = (blocks.getXSize(), blocks.getYSize()) if blocks.isValid() and blocks.getXSize() else (0, 0)
    for y in range(h):
        # PNMImage rows run top down; v 0 is the floor.
        t = 1.0 - y / float(h - 1)
        k = t ** 0.8
        base = [low[c] + (high[c] - low[c]) * k for c in range(3)]
        for x in range(w):
            g = blocks.getGray((x * 2) % bw, (y * 2) % bh) * 1.6 if bw else 1.0
            # The streaks fade out towards the floor.
            g *= 1.0 - streaks[x] * min(1.0, t * 1.4)
            image.setXel(x, y, base[0] * g, base[1] * g, base[2] * g)
    tex = Texture('craneWallGrime')
    tex.load(image)
    tex.setWrapU(SamplerState.WMRepeat)
    tex.setWrapV(SamplerState.WMClamp)
    tex.setMinfilter(SamplerState.FTLinearMipmapLinear)
    _wallTex = tex
    return tex


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


class _BoxMaker:
    # Five faces of a box (no floor), as one GeomNode.

    def __init__(self, x0, x1, y0, y1, z0, z1):
        self.bounds = (x0, x1, y0, y1, z0, z1)

    def generate(self):
        x0, x1, y0, y1, z0, z1 = self.bounds
        node = NodePath('box')
        cm = CardMaker('side')
        for frame, pos, hpr in (((x0, x1, z0, z1), (0, y1, 0), (0, 0, 0)),
                                ((y0, y1, z0, z1), (x0, 0, 0), (90, 0, 0)),
                                ((y0, y1, z0, z1), (x1, 0, 0), (90, 0, 0)),
                                ((x0, x1, y0, y1), (0, 0, z1), (0, -90, 0))):
            cm.setFrame(*frame)
            face = node.attachNewNode(cm.generate())
            face.setPos(*pos)
            face.setHpr(*hpr)
        node.flattenStrong()
        return node.node()


class CogdoCraneRoom:
    """The Vend-A-Stomper room: the crane room model from the original game
    (tt_m_ara_ccg_level), dressed as the Cashbot field office concept art
    shows it. Piles of safes and money fill the room up to a
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
        self._loadElevators()
        self._loadDressing(rng)
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
        # The walls run along x or y, so world x + y across and height up
        # map the grime texture round the room without the model's UVs.
        across = 1.0 / Consts.WallTileWidth
        wallTex = _wallTexture()
        for wall in level.findAllMatches('**/wallBarrier*'):
            wall.setTexture(wallTex, 1)
            wall.setTexGen(TextureStage.getDefault(), TexGenAttrib.MWorldPosition)
            wall.setTexTransform(TextureStage.getDefault(), TransformState.makeMat(Mat4(
                across, 0, 0, 0,
                across, 0, 0, 0,
                0, 1.0 / Consts.CeilingHeight, 0, 0,
                0, 0, 0, 1)))
            wall.setColor(1, 1, 1, 1, 1)
        floorTex = loader.loadTexture('phase_10/maps/StoneSquares.jpg')
        flooring = level.find('**/flooring')
        flooring.setTexture(floorTex, 1)
        flooring.setTexScale(TextureStage.getDefault(), 18, 18)
        # Its vertex colours are baked shading in blotches; light it evenly.
        flooring.setColor(1, 1, 1, 1, 1)
        flooring.setColorScale(*Consts.FloorColorScale)
        self.ceiling = level.find('**/ceiling')
        # A dark riveted steel ceiling instead of the flat magenta one.
        steel = loader.loadTexture('phase_5/maps/tt_t_ara_cbr_steelWalls.jpg')
        self.ceiling.setTexture(steel, 1)
        self.ceiling.setTexGen(TextureStage.getDefault(), TexGenAttrib.MWorldPosition)
        self.ceiling.setTexScale(TextureStage.getDefault(), 1 / 24.0, 1 / 24.0)
        self.ceiling.setColor(1, 1, 1, 1, 1)
        self.ceiling.setColorScale(*Consts.CeilingColorScale)

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
        box = _BoxMaker(-4.7, 4.7, 0.6, 17.5, 0, 10)
        for angle in Consts.LaneAngles:
            d = door.copyTo(self.root)
            pos = Consts.lanePoint(angle, Consts.HallwayDistance + 2)
            d.setPos(pos)
            # Facing into the room; the little room behind it goes back into
            # the junk.
            d.setH(angle)
            d.setScale(0.7)
            self.hallwayDoors.append(d)
            # The room behind the door is drawn from outside only: a dark
            # box inside it, so the door opens onto the dark, not the junk.
            inside = d.attachNewNode(box.generate())
            inside.setColor(0.08, 0.07, 0.07, 1)
            inside.setTwoSided(True)
            inside.setLightOff()
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

    def _inDoorway(self, x, y):
        # Inside the little room behind a hallway's door (the door model
        # has one, about 12 deep): kept clear of junk.
        for angle in Consts.LaneAngles:
            rad = math.radians(angle)
            along = -x * math.sin(rad) + y * math.cos(rad)
            across = x * math.cos(rad) + y * math.sin(rad)
            if Consts.HallwayDistance - 1 < along < Consts.HallwayDistance + 18 and abs(across) < 7.5:
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
        if depth >= 3 and rng.random() < 0.22 and not self._inDoorway(x, y):
            name, scales, height, weight = pick(BackProps)
            prop = model(name).copyTo(parent)
            prop.setPos(x + rng.uniform(-half, half) * 0.5, y + rng.uniform(-half, half) * 0.5, 0)
            prop.setH(rng.uniform(0, 360))
            prop.setScale(rng.uniform(*scales))
            return
        # A few stacks in every cell, taller away from the floor, like a
        # skyline.
        # The cells at the edge of the floor have the walls toons bump
        # into, so they are filled up to the edge, with no floor showing
        # between an invisible wall and the junk.
        for stack in range(3 if depth else 5):
            for attempt in range(8):
                sx = x + rng.uniform(-half, half) * 0.9
                sy = y + rng.uniform(-half, half) * 0.9
                if self._inDoorway(sx, sy):
                    continue
                if depth or not self._inPlayArea(sx, sy, margin=-1.0):
                    break
            else:
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

    def _loadElevators(self):
        # The room's walls have doorways for the elevators. The exit's
        # stands closed at the far end, as in the other field offices; the
        # entrance's own stands in once the ride up is over and the
        # elevator the toons came in is put away.
        from toontown.cogdominium import CogdoUtil
        self.exitElevator = CogdoUtil.loadElevatorModel()
        self.exitElevator.reparentTo(self.root)
        self.exitElevator.setPosHpr(*Consts.ExitPosHpr)
        self.entranceElevator = CogdoUtil.loadElevatorModel()
        self.entranceElevator.reparentTo(self.root)
        self.entranceElevator.setPosHpr(*Consts.ElevatorPosHpr)
        self.entranceElevator.stash()

    # --- Dressing: the walls, the ceiling and round the elevators ---

    def _loadDressing(self, rng):
        """Fills the room out like the concept art: steel girders up the
        walls with pipes running between them and Loan Shark posters over
        the piles, ducts and more girders across the ceiling with lamps
        hanging in the gloom, and boilers, crates and girders round the
        elevators. All Cashbot HQ and field office models."""
        dressing = self.root.attachNewNode('dressing')
        self.dressingWalls = []
        cache = {}

        def place(name, pos, h=0, scale=1.0, p=0, r=0, parent=dressing):
            if name not in cache:
                cache[name] = loader.loadModel(name)
            prop = cache[name].copyTo(parent)
            prop.setPos(pos)
            prop.setHpr(h, p, r)
            if isinstance(scale, tuple):
                prop.setScale(*scale)
            else:
                prop.setScale(scale)
            return prop

        hx, hy = Consts.RoomHalfSize
        top = Consts.CeilingHeight
        girder = 'phase_10/models/cashbotHQ/pipes_A1'
        # The four walls: (heading into the room, a point on the wall for
        # 'along' u, and the wall's direction).
        walls = (
            (0, lambda u, d=0: Point3(u, hy - d, 0)),      # far (exit) wall
            (180, lambda u, d=0: Point3(u, -hy + d, 0)),   # entrance wall
            (90, lambda u, d=0: Point3(-hx + d, u, 0)),    # belt wall
            (-90, lambda u, d=0: Point3(hx - d, u, 0)),    # right wall
        )
        for h, at in walls:
            belt = h == 90
            elevatorWall = h in (0, 180)
            # Girders up the wall to the ceiling beams.
            for u in Consts.WallGirders:
                if elevatorWall and abs(u) < 16:
                    continue
                place(girder, at(u, 4), h, (0.6, 0.6, top / 30.1))
            # A pipe run along the top of the wall, over the girders.
            for u in (-46, 0, 46):
                if elevatorWall and u == 0:
                    continue
                pipe = place('phase_10/models/cashbotHQ/pipes_C', at(u, 8), h + 180, (0.85, 0.7, 0.7))
                pipe.setZ(top - 15)
            if belt:
                # The laff barrel belt runs along this wall: posters over it.
                posterSpots = (-40, 40)
            elif elevatorWall:
                posterSpots = (-34, 34, -58, 58)
            else:
                posterSpots = (-50, 0, 50)
            for u in posterSpots:
                self._addPoster(place, at(u, 0.6), h, Consts.PosterHeight + rng.uniform(-2, 2))
            # Zigzag pipes and boilers on top of the piles, against the wall.
            if not belt:
                for u in Consts.WallPipes:
                    if elevatorWall and abs(u) < 22:
                        continue
                    pipe = place('phase_10/models/cashbotHQ/pipes_B', at(u, 5), h + rng.choice((0, 180)), 0.9)
                    pipe.setZ(rng.uniform(18, 24))
        # Round the elevators: a girder each side of the doorway, a big
        # Cashbot sign over it, and boilers and crates in the corners of
        # the space in front.
        logo = loader.loadTexture('phase_5/maps/ttoff_t_ara_ccg_stomp_cashbot_logo.png')
        for h, at in walls[:2]:
            for side in (-1, 1):
                place(girder, at(side * 11.5, 2.5), h, (0.45, 0.45, top / 30.1))
                place('phase_10/models/cashbotHQ/boiler_B1', at(side * 19, 4), h + (90 if side > 0 else -90), 0.9)
                place('phase_10/models/cashbotHQ/crates_C1', at(side * 25, 3.5), h + rng.uniform(-20, 20), 0.85)
                place('phase_10/models/cashbotHQ/boiler_A1', at(side * 26, 11), h + rng.uniform(0, 360), 0.75)
                # Tall pipes up the wall behind them, and more crates on top.
                place('phase_10/models/cashbotHQ/pipes_D4', at(side * 15.5, 4), h, (0.4, 0.4, 1.25))
                place('phase_10/models/cashbotHQ/pipes_E', at(side * 22, 2), h + (90 if side > 0 else -90), (1.0, 1.0, 1.2))
                crate = place('phase_10/models/cashbotHQ/crates_C1', at(side * 25, 3.5), h + rng.uniform(-30, 30), 0.75)
                crate.setZ(14.3 * 0.85)
                place('phase_10/models/cashbotHQ/MoneyBag', at(side * 27.5, 12), h + rng.uniform(0, 360), 0.9)
                self.dressingWalls.append((at(side * 19, 4), 7))
                self.dressingWalls.append((at(side * 25, 3.5), 4.5))
                self.dressingWalls.append((at(side * 26, 11), 4.5))
            if logo:
                cm = CardMaker('cashbotSign')
                cm.setFrame(-6, 6, -6, 6)
                sign = dressing.attachNewNode(cm.generate())
                sign.setPos(at(0, 0.8) + Vec3(0, 0, 27))
                sign.setH(h)
                sign.setTexture(logo)
                sign.setTransparency(TransparencyAttrib.MAlpha)
                sign.setColorScale(0.75, 0.75, 0.72, 1)
        # The ceiling: girders the other way too, ducts between them and
        # lamps hanging in the dark.
        arm = 'phase_10/models/cogHQ/CBCraneArm'
        for x in range(-int(hx) + 18, int(hx), 30):
            place(arm, Point3(x, -hy, top - 3), 0, (0.7, hy * 2 / 44.3, 0.7))
        for x, y, h in Consts.CeilingDucts:
            duct = place('phase_10/models/cashbotHQ/pipes_A4', Point3(x, y, top + 15.5 * 0.9), h, 0.9, p=180)
        lamp = loader.loadModel('phase_10/models/cashbotHQ/boiler_A1')
        glow = _gradientTexture('lampGlow', True)
        cable = LineSegs('lampCables')
        cable.setThickness(2)
        cable.setColor(0.06, 0.06, 0.06, 1)
        glows = dressing.attachNewNode('lampGlows')
        for x, y, z in Consts.CeilingLamps:
            shade = lamp.copyTo(dressing)
            shade.setPos(x, y, z)
            shade.setScale(0.45, 0.45, 0.25)
            shade.setP(180)
            cable.moveTo(x, y, z)
            cable.drawTo(x, y, top)
            if glow:
                cm = CardMaker('glow')
                cm.setFrame(-6, 6, -6, 6)
                card = glows.attachNewNode(cm.generate())
                card.setPos(x, y, z - 1.5)
                card.setBillboardPointEye()
                card.setTexture(glow)
                card.setColor(1, 0.8, 0.6, 0.5)
        lamp.removeNode()
        dressing.attachNewNode(cable.create())
        glows.setTransparency(TransparencyAttrib.MAlpha)
        glows.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        glows.setDepthWrite(0)
        glows.setBin('fixed', 5)
        glows.setLightOff()
        glows.wrtReparentTo(self.root)
        for m in cache.values():
            m.removeNode()
        dressing.setColorScale(*Consts.DressingShade)
        dressing.clearModelNodes()
        dressing.flattenStrong()

    def _addPoster(self, place, pos, h, z):
        # The Loan Shark poster from the building and the executive suite.
        poster = place('phase_5/models/cogdominium/tt_m_ara_crg_paintingMoverShaker', pos, h, Consts.PosterScale)
        poster.setZ(z)
        for name, path in Consts.CashbotPosterTextures.items():
            old = poster.findTexture(name)
            if old:
                poster.replaceTexture(old, loader.loadTexture(path))

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
        # The boilers and crates by the elevators.
        for pos, r in getattr(self, 'dressingWalls', []):
            walls.addSolid(CollisionBox(Point3(pos[0] - r, pos[1] - r, 0), Point3(pos[0] + r, pos[1] + r, 15)))
        walls.setIntoCollideMask(OTPGlobals.WallBitmask | ToontownGlobals.PieBitmask)
        self.walls = self.root.attachNewNode(walls)
