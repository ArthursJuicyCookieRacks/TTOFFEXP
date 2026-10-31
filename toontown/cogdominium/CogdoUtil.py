from panda3d.core import ColorBlendAttrib
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
