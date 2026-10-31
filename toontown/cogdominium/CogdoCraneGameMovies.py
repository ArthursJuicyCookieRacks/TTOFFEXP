from panda3d.core import NodePath, PlaneNode, Plane, Point3, VBase3
from direct.showbase.RandomNumGen import RandomNumGen
from direct.interval.IntervalGlobal import Func, LerpPosHprInterval, Parallel, Sequence, Wait
from toontown.toonbase import TTLocalizer
from toontown.suit import Suit, SuitDNA
from toontown.toon import Toon, ToonDNA
from .CogdoUtil import CogdoGameMovie
from . import CogdoCraneGameConsts as Consts
from . import CogdoUtil

# Seconds the intro runs: four pages of talk, as long as the other field
# offices' intros.
IntroDurationSeconds = 24.0


def _lookHpr(pos, target):
    np = NodePath('look')
    np.setPos(pos)
    np.lookAt(target)
    hpr = np.getHpr()
    np.removeNode()
    return hpr


class CogdoCraneGameIntro(CogdoGameMovie):
    """The Vend-A-Stomper's intro: the Loan Shark talks in the box on the
    left, then the Toon Resistance explains the cranes, a page at a time,
    while the camera looks round the room."""

    def __init__(self, rng):
        CogdoGameMovie.__init__(self)
        self._rng = RandomNumGen(rng)
        self._suits = []

    def _getRandomLine(self, lineList):
        return CogdoUtil.getRandomDialogueLine(lineList, self._rng)

    def displayLine(self, who, text):
        self._dialogueLabel.node().setText(text)
        if who == 'toon':
            self.toonHead.reparentTo(aspect2d)
            self.cogHead.reparentTo(hidden)
            self._toonDialogueSfx.play()
            self.toonHead.setClipPlane(self.clipPlane)
        else:
            self.toonHead.reparentTo(hidden)
            self.cogHead.reparentTo(aspect2d)
            self._cogDialogueSfx.play()
            self.cogHead.setClipPlane(self.cogClipPlane, 100)

    def makeSuit(self, suitType):
        # The Toon Resistance's toon, in a cog suit.
        suit = Suit.Suit()
        dna = SuitDNA.SuitDNA()
        dna.newSuit(suitType)
        suit.setStyle(dna)
        suit.isDisguised = 1
        suit.generateSuit()
        suit.setScale(1, 1, 2)
        suit.setPos(0, 0, -4.4)
        suit.reparentTo(self.toonHead)
        for part in suit.getHeadParts():
            part.hide()
        suit.loop('neutral')

    def load(self, root):
        CogdoGameMovie.load(self)
        self.toonDNA = ToonDNA.ToonDNA()
        self.toonDNA.newToonFromProperties('dss', 'ss', 'm', 'm', 2, 0, 2, 2, 1, 8, 1, 8, 1, 14)
        self.toonHead = Toon.Toon()
        self.toonHead.setDNA(self.toonDNA)
        self.makeSuit('sc')
        self.toonHead.getGeomNode().setDepthWrite(1)
        self.toonHead.getGeomNode().setDepthTest(1)
        self.toonHead.loop('neutral')
        self.toonHead.setPosHprScale(-0.73, 0, -1.27, 180, 0, 0, 0.18, 0.18, 0.18)
        self.toonHead.reparentTo(hidden)
        self.toonHead.startBlink()
        self.cogHead = Suit.Suit()
        self.cogDNA = SuitDNA.SuitDNA()
        self.cogDNA.newSuit('ls')
        self.cogHead.setDNA(self.cogDNA)
        self.cogHead.getGeomNode().setDepthWrite(1)
        self.cogHead.getGeomNode().setDepthTest(1)
        self.cogHead.loop('neutral')
        # The Loan Shark is a tall cog: smaller than the other offices'
        # cogs, so his head and shoulders fill the box, and cut off at its
        # bottom edge.
        self.cogHead.setPosHprScale(-0.73, 0, -1.49, 180, 0, 0, 0.12, 0.12, 0.12)
        self.cogHead.reparentTo(hidden)
        self.cogClipPlane = NodePath(PlaneNode('cogClip', Plane(0, 0, 1, 0)))
        self.cogClipPlane.reparentTo(aspect2d)
        self.cogClipPlane.setZ(-0.8)
        self.clipPlane = self.toonHead.attachNewNode(PlaneNode('clip'))
        self.clipPlane.node().setPlane(Plane(0, 0, 1, 0))
        self.clipPlane.setPos(0, 0, 2.45)
        # The same voices as the other field offices' intros (this game has
        # no cogdo audio manager of its own).
        self._cogDialogueSfx = loader.loadSfx('phase_3.5/audio/dial/COG_VO_statement.ogg')
        self._toonDialogueSfx = loader.loadSfx('phase_3.5/audio/dial/AV_dog_long.ogg')
        # The Loan Shark himself, by the machine, for the first page.
        boss = Suit.Suit()
        d = SuitDNA.SuitDNA()
        d.newSuit('ls')
        boss.setDNA(d)
        boss.reparentTo(root)
        boss.setPos(0, -9, 0)
        boss.setH(180)
        boss.loop('neutral')
        self._suits.append(boss)
        dialogue = TTLocalizer.CogdoCraneIntroMovieDialogue
        page = IntroDurationSeconds / len(dialogue)

        def shot(duration, pos, target, startPos=None, startTarget=None):
            pos = Point3(*pos)
            target = Point3(*target)
            ival = LerpPosHprInterval(camera, duration, pos, _lookHpr(pos, target), blendType='easeInOut')
            if startPos is None:
                return ival
            startPos = Point3(*startPos)
            startHpr = _lookHpr(startPos, Point3(*startTarget))
            return Sequence(Func(camera.setPosHpr, startPos, startHpr), ival)

        # The first crane, the one in front of the elevator.
        cx, cy = Consts.craneWorld(0, 0, 0)
        # The lane on the left as the toons come in.
        lane = Consts.LaneAngles[0]
        l1, l2, l3, l4 = (Consts.lanePoint(lane, d) for d in (6, 18, 70, 84))
        self._ival = Sequence(
            Func(camera.wrtReparentTo, render),
            # The Loan Shark at his Stomp-O-Matic.
            Func(boss.loop, 'victory'),
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[0])),
            shot(page, (8, -36, 12), (0, 0, 7), (0, -60, 24), (0, 0, 6)),
            # The cranes and their money bags.
            Func(boss.loop, 'neutral'),
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[1])),
            shot(page, (cx + 16, cy - 22, 22), (cx, cy + 6, 4), (cx - 18, cy - 26, 26), (cx, cy + 6, 4)),
            # Down the lanes to the hallways the cogs come out of.
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[2])),
            shot(page, (l2[0], l2[1], 16), (l4[0], l4[1], 4), (l1[0], l1[1], 24), (l3[0], l3[1], 2)),
            # The whole room.
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[3])),
            shot(page, (36, -50, 40), (0, 0, 4), (-36, -50, 40), (0, 0, 4)))

    def unload(self):
        for suit in self._suits:
            suit.cleanup()
            suit.removeNode()
            suit.delete()
        self._suits = []
        CogdoGameMovie.unload(self)
        del self._cogDialogueSfx
        del self._toonDialogueSfx
        self.toonHead.stopBlink()
        self.toonHead.stop()
        self.toonHead.removeNode()
        self.toonHead.delete()
        del self.toonHead
        self.cogHead.stop()
        self.cogHead.removeNode()
        self.cogHead.delete()
        del self.cogHead
        self.cogClipPlane.removeNode()
