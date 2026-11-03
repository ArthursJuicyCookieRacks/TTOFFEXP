import math

from panda3d.core import (CardMaker, CollisionBox, CollisionCapsule, CollisionNode, CollisionPlane, CollisionPolygon,
                          NodePath, Plane, Point3, TextureStage, TransparencyAttrib, Vec3, Vec4)

from otp.otpbase import OTPGlobals
from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
from toontown.cogdominium import CogdoBoardroomLayout as Layout
from toontown.cogdominium import CogdoUtil
from toontown.toonbase import ToontownGlobals

# The banquet table model's chairs face its middle: the one on its left
# side (-x) faces +x, the right one -x, the far one -y. Each with the
# heading its sitting cog needs (as the CEO battle seats them).
ChairLeft = ('chair_5', -90)
ChairRight = ('chair_1', 90)
ChairFar = ('chair_7', 180)
PileModels = ('phase_11/models/lawbotHQ/LB_paper_stacks', 'phase_11/models/lawbotHQ/LB_paper_big_stacks3')


class CogdoBoardroomRoom:
    """Boardroom Hijinks' room: the Bossbot banquet hall with one long
    meeting table down its middle, built from the banquet table's cloth,
    legs and chairs. The toons come in at the floor, run up a ramp onto the
    table and along it, past paperwork piles, pencils and ramps, and jump
    off the far end by the chairman's chair to the exit."""

    def __init__(self, layout):
        self.layout = layout
        self.root = None
        self.memoModels = []
        self.powerUpModels = []
        self.oilCanModels = []
        self.slickModels = []
        self.chairNodes = []
        self.seatLocators = []
        self.chairmanLocator = None

    def load(self):
        self.root = NodePath('boardroom')
        self._loadHall()
        self._loadTable()
        self._loadChairs()
        self._loadObstacles()
        self._loadPickups()
        self._loadOilCans()
        self._loadElevators()
        self._loadCollisions()
        return self.root

    def destroy(self):
        if self.root:
            self.root.removeNode()
        self.root = None
        self.memoModels = []
        self.powerUpModels = []
        self.oilCanModels = []
        self.slickModels = []
        self.seatLocators = []

    # --- The hall ---

    def _loadHall(self):
        # The CEO's banquet hall, NumHalls of them end to end: the first
        # keeps its entry corridor, the last its fireplace, and the walls in
        # between are taken out so the table runs straight through. The
        # kitchen behind the far wall and the banquet's own table spots are
        # no use to the meeting. The halls' collision walls go too (they
        # cross the table where the halls join); the table has its own.
        self.halls = []
        for i in range(Consts.NumHalls):
            hall = loader.loadModel(Consts.RoomModel)
            hall.reparentTo(self.root)
            hall.setY(i * Consts.HallLength)
            for name in ('**/Kitchen', '**/TableLocators', '**/collision_walls1', '**/collision_wall',
                         '**/collision_props', '**/collison_door'):
                hall.findAllMatches(name).detach()
            if i > 0:
                for name in ('**/wallA', '**/entry1', '**/door3', '**/elevator_origin'):
                    hall.findAllMatches(name).detach()
            if i < Consts.NumHalls - 1:
                hall.findAllMatches('**/wallC').detach()
                hall.findAllMatches('**/lights').detach()
            self.halls.append(hall)
        self.hall = self.halls[-1]

    # --- The table ---

    def _loadTable(self):
        model = loader.loadModel(Consts.TableModel)
        self.tableModel = model
        table = self.root.attachNewNode('table')
        cloth = model.find('**/table/cloth')
        mn, mx = cloth.getTightBounds()
        clothW = mx[0] - mn[0]
        clothL = mx[1] - mn[1]
        clothTop = mx[2]
        sx = Consts.TableHalfWidth * 2.0 / clothW
        length = Consts.TableEnd - Consts.TableStart
        count = max(1, int(round(length / clothL)))
        sy = length / (count * clothL)
        # Cloth after cloth, end to end: one long table cloth with the
        # banquet table's drape down the sides.
        cx = (mn[0] + mx[0]) / 2.0
        cy = (mn[1] + mx[1]) / 2.0
        for i in range(count):
            piece = cloth.copyTo(table)
            y = Consts.TableStart + (i + 0.5) * clothL * sy
            piece.setPos(-cx * sx, y - cy * sy, Consts.TableTop - clothTop)
            piece.setScale(sx, sy, 1.0)
        # The legs, in pairs down the table.
        leg = model.find('**/table/leg1')
        lmn, lmx = leg.getTightBounds()
        lcx = (lmn[0] + lmx[0]) / 2.0
        lcy = (lmn[1] + lmx[1]) / 2.0
        y = Consts.TableStart + 3.0
        while y < Consts.TableEnd - 1.0:
            for side in (-1, 1):
                piece = leg.copyTo(table)
                piece.setPos(side * (Consts.TableHalfWidth - 1.5) - lcx, y - lcy, 0)
            y += Consts.TableLegSpacing
        # A desk lamp now and then, at the table's edges, as at the banquet.
        lamp = model.find('**/lamp_med_5')
        if not lamp.isEmpty():
            lamp.clearTransform()
            y = Consts.TableStart + Consts.SeatSpacing
            side = 1
            while y < Consts.TableEnd - 10:
                piece = lamp.copyTo(table)
                piece.setPos(side * (Consts.TableHalfWidth - 0.9), y, Consts.TableTop - 3.62 + 0.02)
                side = -side
                y += Consts.SeatSpacing * 1.5
        table.flattenStrong()
        # The ramp up from the floor at the near end, wood like the table's
        # legs.
        self.ramp = self._makeRamp(self.root, 0, Consts.TableStart - Consts.RampLength / 2.0, Consts.TableHalfWidth * 0.5,
                                   Consts.RampLength / 2.0, 0, Consts.TableTop, 'phase_12/maps/BQ_WoodPanel.jpg', 0.55)

    def _makeRamp(self, parent, x, y, w, l, z0, z1, texture, shade):
        # A slab from (y - l, z0) up to (y + l, z1), w either side of x.
        ramp = parent.attachNewNode('ramp')
        cm = CardMaker('rampTop')
        rise = z1 - z0
        run = 2.0 * l
        slope = math.hypot(run, rise)
        cm.setFrame(-w, w, 0, slope)
        cm.setUvRange((0, 0), (w / 4.0, slope / 4.0))
        top = ramp.attachNewNode(cm.generate())
        top.setPos(x, y - l, z0)
        top.setP(-90 + math.degrees(math.atan2(rise, run)))
        tex = loader.loadTexture(texture)
        if tex:
            ramp.setTexture(tex, 1)
        ramp.setColorScale(shade, shade * 0.92, shade * 0.85, 1)
        ramp.setTwoSided(True)
        return ramp

    # --- The meeting: chairs down both sides, the chairman at the head ---

    def _loadChairs(self):
        chairs = self.root.attachNewNode('chairs')
        for index, (side, y, taken) in enumerate(self.layout.seats):
            name, heading = ChairLeft if side < 0 else ChairRight
            locator = self._placeChair(chairs, name, Point3(side * Consts.SeatSideX, y, 0), heading)
            self.seatLocators.append(locator)
        name, heading = ChairFar
        self.chairmanLocator = self._placeChair(chairs, name, Point3(*Consts.ChairmanPos), heading)

    def _placeChair(self, parent, name, pos, heading):
        source = self.tableModel.find('**/chairs/' + name)
        chair = parent.attachNewNode(name)
        geom = source.copyTo(chair)
        # The chair's geometry sits round its own node, at its seat height.
        geom.setPos(0, 0, source.getZ())
        chair.setPos(pos)
        locator = chair.attachNewNode('correctHeading')
        locator.setZ(source.getZ())
        locator.setH(heading)
        self.chairNodes.append(chair)
        return locator

    @staticmethod
    def sitCog(suit, locator, bodyType):
        # As the CEO battle seats its diners.
        sit = locator.attachNewNode('sitLocator')
        if bodyType == 'c':
            sit.setPos(0.5, 3.65, -3.75)
        else:
            sit.setPos(0.5, 2.5, -2.4)
        suit.reparentTo(sit)
        return sit

    # --- On the table ---

    def _loadObstacles(self):
        obstacles = self.root.attachNewNode('obstacles')
        pileModels = [loader.loadModel(name) for name in PileModels]
        pencil = NodePath('unused')
        paperTex = loader.loadTexture('phase_11/maps/LB_WoodPanel.jpg')
        for i, ob in enumerate(self.layout.obstacles):
            if ob.kind == Layout.PILE:
                model = pileModels[i % len(pileModels)]
                mn, mx = model.getTightBounds()
                pile = model.copyTo(obstacles)
                pile.setPos(ob.x - (mn[0] + mx[0]) / 2.0 * ob.w * 2.0 / (mx[0] - mn[0]),
                            ob.y - (mn[1] + mx[1]) / 2.0 * ob.l * 2.0 / (mx[1] - mn[1]), Consts.TableTop)
                pile.setScale(ob.w * 2.0 / (mx[0] - mn[0]), ob.l * 2.0 / (mx[1] - mn[1]), ob.h / (mx[2] - mn[2]))
            elif ob.kind == Layout.PENCIL:
                # A giant pencil lying across the table, as thick as a
                # toon's knees are high.
                holder = obstacles.attachNewNode('pencil')
                p = makePencil(2.0 * ob.w + 1.0, Consts.PencilHeight / 2.0)
                p.reparentTo(holder)
                p.setZ(Consts.PencilHeight / 2.0)
                holder.setPos(ob.x, ob.y, Consts.TableTop)
                holder.setH(90 + ob.angle)
            elif ob.kind == Layout.RAMP:
                self._makeRamp(obstacles, ob.x, ob.y, ob.w, ob.l, Consts.TableTop, Consts.TableTop + ob.h,
                               'phase_11/maps/LB_WoodPanel.jpg', 0.85)
        for model in pileModels:
            model.removeNode()
        pencil.removeNode()

    def _loadPickups(self):
        pickups = self.root.attachNewNode('pickups')
        memo = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_csa_memo')
        for i, (x, y, z) in enumerate(self.layout.memos):
            m = memo.copyTo(pickups)
            m.setPos(x, y, z + 1.6)
            m.setScale(1.1)
            m.setH(i * 37)
            # They turn round where they lie, as in the Sellbot maze.
            m.hprInterval(3.0, Vec3(m.getH() + 360, 0, 0)).loop()
            self.memoModels.append(m)
        memo.removeNode()
        for kind, x, y in self.layout.powerUps:
            holder = pickups.attachNewNode('powerUp')
            holder.setPos(x, y, Consts.TableTop + 1.4)
            if kind == Layout.INVULNERABLE:
                # A gold Cog Award: nothing can touch the toon who holds it.
                model = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_crg_goldTrophy')
                model.setScale(4.0)
                model.setZ(-1.0)
            else:
                # A spring-loaded propeller: hop higher for a while.
                model = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_cfg_propellerPack')
                model.setScale(1.6)
                model.setZ(-0.4)
            model.reparentTo(holder)
            glow = loader.loadModel('phase_3/models/props/drop_shadow')
            glow.reparentTo(holder)
            glow.setPos(0, 0, -1.35)
            glow.setScale(1.8)
            glow.setColor(1, 0.9, 0.3, 0.6) if kind == Layout.INVULNERABLE else glow.setColor(0.4, 0.8, 1, 0.6)
            glow.setTransparency(TransparencyAttrib.MAlpha)
            holder.hprInterval(2.0, Vec3(360, 0, 0)).loop()
            self.powerUpModels.append(holder)

    def _loadOilCans(self):
        cans = self.root.attachNewNode('oilCans')
        for i, (x, y) in enumerate(self.layout.oilCans):
            can = loader.loadModel('phase_6/models/props/small_round_barrel')
            can.reparentTo(cans)
            can.setPos(x, y, Consts.TableTop)
            can.setScale(0.75, 0.75, 1.0)
            # An oil drum: dark, with an oily sheen.
            can.setColorScale(0.32, 0.3, 0.26, 1)
            self.oilCanModels.append(can)
            # Its spill, ready to spread when it is knocked over.
            sx, sy, r = self.layout.slickAt(i)
            slick = loader.loadModel('phase_3/models/props/drop_shadow')
            slick.reparentTo(cans)
            slick.setPos(sx, sy, Consts.TableTop + 0.03)
            slick.setScale(r * 2.0 / 2.2)
            slick.setColor(0.08, 0.07, 0.05, 0.85)
            slick.setTransparency(TransparencyAttrib.MAlpha)
            slick.setDepthOffset(2)
            slick.hide()
            self.slickModels.append(slick)

    # --- The way in and out ---

    def _loadElevators(self):
        self.exitElevator = CogdoUtil.loadElevatorModel()
        self.exitElevator.reparentTo(self.root)
        self.exitElevator.setPosHpr(*Consts.ExitPosHpr)
        CogdoUtil.addElevatorShell(self.exitElevator)
        self.entranceElevator = CogdoUtil.loadElevatorModel()
        self.entranceElevator.reparentTo(self.root)
        self.entranceElevator.setPosHpr(*Consts.ElevatorPosHpr)
        self.entranceElevator.stash()
        # The exit's doors stand open (the way out is past the chairman) and
        # close on the toons when they all are in, for the ride to the golf
        # office.
        self.exitLeftDoor = self.exitElevator.find('**/left_door')
        self.exitRightDoor = self.exitElevator.find('**/right_door')
        for door in (self.exitLeftDoor, self.exitRightDoor):
            if not door.isEmpty():
                door.setPos(0, 0, 0)

    def _loadCollisions(self):
        walls = CollisionNode('tableWalls')
        mask = OTPGlobals.WallBitmask | OTPGlobals.FloorBitmask | ToontownGlobals.PieBitmask
        hw = Consts.TableHalfWidth
        # The table itself: walk on its top, not through its sides.
        walls.addSolid(CollisionBox(Point3(-hw, Consts.TableStart, 0), Point3(hw, Consts.TableEnd, Consts.TableTop)))
        for ob in self.layout.obstacles:
            if ob.kind == Layout.PILE:
                walls.addSolid(CollisionBox(Point3(ob.x - ob.w, ob.y - ob.l, Consts.TableTop),
                                            Point3(ob.x + ob.w, ob.y + ob.l, Consts.TableTop + ob.h)))
            elif ob.kind == Layout.PENCIL:
                a = math.radians(ob.angle)
                dx, dy = math.cos(a) * ob.w, math.sin(a) * ob.w
                r = Consts.PencilHeight / 2.0
                z = Consts.TableTop + r
                walls.addSolid(CollisionCapsule(Point3(ob.x - dx, ob.y - dy, z), Point3(ob.x + dx, ob.y + dy, z), r))
        self.walls = self.root.attachNewNode(walls)
        self.walls.node().setIntoCollideMask(mask)
        # Ramps are walked up: floor only.
        ramps = CollisionNode('ramps')
        rampList = [(0, Consts.TableStart - Consts.RampLength / 2.0, hw * 0.5, Consts.RampLength / 2.0, 0.0, Consts.TableTop)]
        for ob in self.layout.obstacles:
            if ob.kind == Layout.RAMP:
                rampList.append((ob.x, ob.y, ob.w, ob.l, Consts.TableTop, Consts.TableTop + ob.h))
        for x, y, w, l, z0, z1 in rampList:
            ramps.addSolid(CollisionPolygon(Point3(x - w, y - l, z0), Point3(x + w, y - l, z0),
                                            Point3(x + w, y + l, z1), Point3(x - w, y + l, z1)))
        self.ramps = self.root.attachNewNode(ramps)
        self.ramps.node().setIntoCollideMask(OTPGlobals.FloorBitmask)
        # Invisible rails along the table's edges: the toons keep to the
        # table, and the only way down is off its far end.
        rails = CollisionNode('rails')
        top = Consts.TableTop + 14
        for side in (-1, 1):
            x = side * (hw + 0.4)
            rails.addSolid(CollisionBox(Point3(x - 0.4, Consts.TableStart - Consts.RampLength, 0), Point3(x + 0.4, Consts.TableEnd, top)))
        for side in (-1, 1):
            # And along the near ramp's sides.
            x = side * (hw * 0.5 + 0.3)
            rails.addSolid(CollisionBox(Point3(x - 0.3, Consts.TableStart - Consts.RampLength, 0), Point3(x + 0.3, Consts.TableStart, top)))
        self.rails = self.root.attachNewNode(rails)
        self.rails.node().setIntoCollideMask(OTPGlobals.WallBitmask)


def makePencil(length, radius):
    """A six-sided yellow pencil down the y axis, centred on the origin:
    pink eraser and its metal band at -y, the sharpened wood and lead at +y."""
    from panda3d.core import GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Geom, GeomNode
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('pencil', fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, 'vertex')
    nw = GeomVertexWriter(vdata, 'normal')
    cw = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)
    count = [0]
    ring = [(math.cos(math.radians(30 + 60 * k)), math.sin(math.radians(30 + 60 * k))) for k in range(6)]

    def quad(a, b, c, d, n, col):
        for v in (a, b, c, d):
            vw.addData3(*v)
            nw.addData3(*n)
            cw.addData4(*col)
        i = count[0]
        tris.addVertices(i, i + 1, i + 2)
        tris.addVertices(i, i + 2, i + 3)
        count[0] += 4

    def tube(y0, y1, r0, r1, col):
        for k in range(6):
            (x0, z0), (x1, z1) = ring[k], ring[(k + 1) % 6]
            n = ((x0 + x1) / 2.0, 0, (z0 + z1) / 2.0)
            quad((x0 * r0, y0, z0 * r0), (x1 * r0, y0, z1 * r0), (x1 * r1, y1, z1 * r1), (x0 * r1, y1, z0 * r1), n, col)

    half = length / 2.0
    tip = min(length * 0.16, radius * 4.0)
    eraser = radius * 1.4
    band = radius * 0.9
    tube(-half, -half, 0.0, radius, (0.95, 0.55, 0.62, 1))
    tube(-half, -half + eraser, radius, radius, (0.95, 0.55, 0.62, 1))
    tube(-half + eraser, -half + eraser + band, radius * 1.04, radius * 1.04, (0.7, 0.72, 0.68, 1))
    tube(-half + eraser + band, half - tip, radius, radius, (1.0, 0.8, 0.12, 1))
    tube(half - tip, half - tip * 0.25, radius, radius * 0.25, (0.93, 0.78, 0.55, 1))
    tube(half - tip * 0.25, half, radius * 0.25, 0.0, (0.2, 0.2, 0.22, 1))
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode('pencil')
    node.addGeom(geom)
    np = NodePath(node)
    np.setTwoSided(True)
    return np
