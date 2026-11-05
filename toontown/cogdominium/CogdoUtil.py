from panda3d.core import ColorBlendAttrib, Point3, ScissorEffect
ModelPhase = 5
ModelTypes = {'animation': 'a',
 'model': 'm',
 'rig': 'r'}
ModelGroups = {'area': 'ara',
 'gui': 'gui'}
Games = {'flying': 'cfg',
 'maze': 'cmg',
 'shared': 'csa'}

def loadFlyingModel(baseName, type = 'model', group = 'area'):
    return loadModel(baseName, 'flying', type=type, group=group)


def loadMazeModel(baseName, type = 'model', group = 'area'):
    return loadModel(baseName, 'maze', type=type, group=group)


def getModelPath(baseName, game = 'shared', type = 'model', group = 'area'):
    return 'phase_%i/models/cogdominium/tt_%s_%s_%s_%s' % (ModelPhase,
     ModelTypes[type],
     ModelGroups[group],
     Games[game],
     baseName)


def loadModel(baseName, game = 'shared', type = 'model', group = 'area'):
    return loader.loadModel(getModelPath(baseName, game, type, group))


class VariableContainer:
    pass

class DevVariableContainer:

    def __init__(self, name):
        self.__dict__['_enabled'] = config.ConfigVariableBool('%s-dev' % name, False).getValue()

    def __setattr__(self, name, value):
        self.__dict__[name] = self._enabled and value


def loadElevatorModel():
    # The field office elevator's floor is 0.1 above its origin, so toons
    # stepped up onto it. Lower the model so its floor is level with the
    # ground and toons walk in flat.
    model = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_csa_elevatorB')
    grp = model.find('**/Grp_elevatorB')
    if not grp.isEmpty():
        grp.setZ(grp.getZ() - 0.1)
    return model


def addElevatorShell(model):
    # The car is only 6 ft deep, so the ride camera (14 ft back, as in the
    # cog buildings) sits behind its back wall and sees the room past its
    # sides. Stretch a second copy of the car's walls back past the camera,
    # so from inside you only see the elevator and what's out its doors.
    car = model.find('**/elevator')
    if car.isEmpty() or not model.find('**/elevatorShell').isEmpty():
        return None
    shell = car.copyTo(car.getParent())
    shell.setName('elevatorShell')
    for coll in shell.findAllMatches('**/+CollisionNode'):
        coll.removeNode()
    shell.setY(car, 5.9)
    shell.setSy(car, 1.75)
    # The car's own back wall stays where it was, 6 ft in, between the ride
    # camera and the toons: drawn from both sides (addElevatorHousing) it
    # filled the whole view (Arthur). The shell has the back wall now, so
    # take the car's out.
    _dropBackWall(car)
    return shell


def _dropBackWall(car):
    from panda3d import core as PM
    b = car.getTightBounds(car)
    if not b:
        return
    back = b[1][1] - 0.15
    nodes = [car] if car.node().isGeomNode() else list(car.findAllMatches('**/+GeomNode'))
    for gnp in nodes:
        gn = gnp.node()
        for gi in range(gn.getNumGeoms()):
            geom = gn.modifyGeom(gi)
            reader = PM.GeomVertexReader(geom.getVertexData(), 'vertex')
            for pi in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(pi).decompose()
                keep = PM.GeomTriangles(prim.getUsageHint())
                keep.setIndexType(prim.getIndexType())
                dropped = 0
                for t in range(prim.getNumPrimitives()):
                    vs = [prim.getVertex(prim.getPrimitiveStart(t) + j) for j in range(3)]
                    ys = []
                    for v in vs:
                        reader.setRow(v)
                        ys.append(reader.getData3()[1])
                    if min(ys) > back:
                        dropped += 1
                        continue
                    keep.addVertices(*vs)
                if dropped:
                    geom.setPrimitive(pi, keep)


def addElevatorHousing(model, color=(0.16, 0.16, 0.17, 1)):
    # An elevator standing free in a room (not set in a wall as in the cog
    # buildings) showed its inside through its sides and back: the car's
    # walls face in only. Box it in from outside, sides, back and roof the
    # dark grey of its frame, open only at the doors (Arthur).
    from panda3d import core as PM
    if not model.find('**/elevatorHousing').isEmpty():
        return None
    b = model.getTightBounds(model)
    if not b:
        return None
    (x0, y0, z0), (x1, y1, z1) = b
    frame = model.find('**/frame')
    fy = frame.getTightBounds(model)[1][1] if not frame.isEmpty() else y0 + 0.3
    x0, x1, y0, y1, z0, z1 = x0 + 0.02, x1 - 0.02, fy, y1 + 0.3, 0.0, z1 - 0.02
    # The doorway: the car's floor is as wide as it, its lintel as high.
    floor = [c for c in model.findAllMatches('**/+GeomNode') if c.getTightBounds(model)
             and abs(c.getTightBounds(model)[1][2] - c.getTightBounds(model)[0][2]) < 0.05]
    dw = 4.2
    dh = 9.9
    if floor:
        fb = floor[0].getTightBounds(model)
        dw = max(abs(fb[0][0]), abs(fb[1][0])) + 0.15
    fmt = PM.GeomVertexFormat.getV3n3()
    vdata = PM.GeomVertexData('housing', fmt, PM.Geom.UHStatic)
    vw = PM.GeomVertexWriter(vdata, 'vertex')
    nw = PM.GeomVertexWriter(vdata, 'normal')
    tris = PM.GeomTriangles(PM.Geom.UHStatic)
    faces = (((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (0, 1, 0)),
             ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (-1, 0, 0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
             # And a front just behind the door frame round the doorway:
             # the frame leans in towards its top, so beside it there was a
             # gap to see in through (Arthur).
             ((x0, y0, z0), (-dw, y0, z0), (-dw, y0, z1), (x0, y0, z1), (0, -1, 0)),
             ((dw, y0, z0), (x1, y0, z0), (x1, y0, z1), (dw, y0, z1), (0, -1, 0)),
             ((-dw, y0, dh), (dw, y0, dh), (dw, y0, z1), (-dw, y0, z1), (0, -1, 0)))
    for i, face in enumerate(faces):
        for v in face[:4]:
            vw.addData3(*v)
            nw.addData3(*face[4])
        k = i * 4
        # Outward faces only: from inside the car you still see its walls.
        tris.addVertices(k, k + 1, k + 2)
        tris.addVertices(k, k + 2, k + 3)
    geom = PM.Geom(vdata)
    geom.addPrimitive(tris)
    gn = PM.GeomNode('elevatorHousing')
    gn.addGeom(geom)
    node = model.attachNewNode(gn)
    node.setColor(*color)
    # The car's front wall, either side of the doors, faces in only too:
    # from outside, beside the frame, you looked through it into the car.
    # Drawn from both sides it closes that gap.
    car = model.find('**/elevator')
    if not car.isEmpty():
        car.setTwoSided(True)
    return node


def getRandomDialogueLine(lineList, rng):
    return lineList[rng.randint(0, len(lineList) - 1)]


class CogdoGameMovie:

    def __init__(self):
        self._ival = None
        self._task = None
        return

    def load(self):
        from toontown.toonbase import ToontownGlobals
        from panda3d.core import TextNode
        textNode = TextNode('moviedialogue')
        textNode.setTextColor(0, 0, 0, 1)
        textNode.setCardColor(1, 1, 1, 1)
        textNode.setCardAsMargin(0, 0, 0, 0)
        textNode.setCardDecal(True)
        textNode.setWordwrap(27.0)
        textNode.setAlign(TextNode.ACenter)
        textNode.setFont(ToontownGlobals.getToonFont())
        self._dialogueLabel = aspect2d.attachNewNode(textNode)
        self._dialogueLabel.setScale(0.06, 0.06, 0.06)
        self._dialogueLabel.setPos(0.32, 0, -0.75)
        self._dialogueLabel.reparentTo(hidden)

    def unload(self):
        if self._ival != None and self._ival.isPlaying():
            # Stopped where it is: there is no self.finish (that raised), and
            # finishing the ival would run its last steps, such as the
            # flying game's iris out, after the next floor has started.
            self._ival.pause()
        self._ival = None
        self._dialogueLabel.removeNode()
        del self._dialogueLabel
        return

    def getIval(self):
        return self._ival

    def play(self, elapsedTime = 0.0):
        self._dialogueLabel.reparentTo(aspect2d)
        self._ival.start(elapsedTime)

    def _startUpdateTask(self):
        self._task = taskMgr.add(self._updateTask, 'CogdoGameMovie_updateTask', 45)

    def _stopUpdateTask(self):
        if self._task != None:
            taskMgr.remove(self._task)
            self._task = None
        return

    def _updateTask(self, task):
        return task.cont

    def end(self):
        self._ival.finish()


def initializeLightCone(np, bin = 'fixed', sorting = 3):
    np.node().setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    if bin:
        np.setBin(bin, sorting)
    np.setDepthWrite(False)
    np.setTwoSided(True, 10000)


ROTATE_TABLE_ALLOWED_ANGLES = (0, 90, 180, 270)

def rotateTable(table, angle):
    if angle == 0:
        t = table[:]
    elif angle == 90:
        t = []
        width = len(table[0])
        height = len(table)
        for j in range(width):
            row = []
            for i in range(height):
                row.append(table[height - 1 - i][j])

            t.append(row)

    elif angle == 180:
        t = table[:]
        for row in t:
            row.reverse()

        t.reverse()
    elif angle == 270:
        t = []
        width = len(table[0])
        height = len(table)
        for j in range(width):
            row = []
            for i in range(height):
                row.append(table[i][width - 1 - j])

            t.append(row)

    return t


# The tag on the entrance elevator while the toons ride up in it.
RIDING_TAG = 'cogdoRidingElevator'


def isRidingElevator(toon):
    np = toon.getParent()
    while not np.isEmpty():
        if np.hasPythonTag(RIDING_TAG):
            return True
        np = np.getParent()
    return False


def takeToon(toon):
    """Puts a toon in the game's world. The game can load while the toons
    still ride up in the elevator (so its room is there when the doors
    open); a riding toon stays in the elevator, which lets it out."""
    if not isRidingElevator(toon):
        toon.reparentTo(render)


# The intro and dialogue movies cut the speaker's head off at the bottom
# edge of the talk box with a clip plane. Phones (OpenGL ES 2) have no clip
# planes, so the whole toon or cog showed outside the box. A scissor cut, in
# screen space, does the same job everywhere.
BOX_CLIP_Z = -1.27 + 2.45 * 0.18


def clipToBox(node, z = BOX_CLIP_Z):
    node.setEffect(ScissorEffect.makeNode(Point3(-10, 0, z), Point3(10, 0, 10), aspect2d))


def makeOilSlick(parent, radius, pick=0, h=0.0):
    """A pool of spilled oil lying flat on a table or floor, `radius` ft
    across at scale 1: one of the game's own ground-oil decals, picked by
    `pick` and turned `h` degrees (so no two slicks look alike)."""
    from panda3d.core import CardMaker, TransparencyAttrib, SamplerState
    from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
    names = Consts.OilTextures
    name = names[pick % len(names)]
    tex = loader.loadTexture(name, name.replace('.jpg', '_a.rgb'))
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    cm = CardMaker('oilSlick')
    # The decals' oil fills most of the square, not all of it.
    cm.setFrame(-radius * 1.15, radius * 1.15, -radius * 1.15, radius * 1.15)
    slick = parent.attachNewNode(cm.generate())
    slick.setP(-90)
    slick.setH(h)
    slick.setTexture(tex)
    slick.setTransparency(TransparencyAttrib.MAlpha)
    slick.setDepthOffset(2)
    slick.setDepthWrite(False)
    slick.setLightOff()
    slick.setBin('fixed', 0)
    return slick
