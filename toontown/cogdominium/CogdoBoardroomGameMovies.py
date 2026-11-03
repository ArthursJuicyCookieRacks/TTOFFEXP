from panda3d.core import NodePath, PlaneNode, Plane, Point3, VBase3
from direct.showbase.RandomNumGen import RandomNumGen
from direct.interval.IntervalGlobal import Func, LerpPosHprInterval, Parallel, Sequence, Wait
from toontown.toonbase import TTLocalizer
from toontown.suit import Suit, SuitDNA
from toontown.toon import Toon, ToonDNA
from .CogdoUtil import CogdoGameMovie
from . import CogdoBoardroomGameConsts as Consts
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


class CogdoBoardroomGameIntro(CogdoGameMovie):
    """Boardroom Hijinks' intro: The Big Cheese calls the meeting to order
    from the head of the table, then the Toon Resistance explains the
    slide, a page at a time, while the camera looks down the table."""

    def __init__(self, rng, game=None):
        CogdoGameMovie.__init__(self)
        self._rng = RandomNumGen(rng)
        self._suits = []
        self._game = game

    def _getRandomLine(self, lineList):
        return CogdoUtil.getRandomDialogueLine(lineList, self._rng)

    def displayLine(self, who, text):
        self._dialogueLabel.node().setText(text)
        if who == 'toon':
            self.toonHead.reparentTo(aspect2d)
            self.cogHead.reparentTo(hidden)
            self._toonDialogueSfx.play()
            self.toonHead.setClipPlane(self.clipPlane)
            CogdoUtil.clipToBox(self.toonHead)
        else:
            self.toonHead.reparentTo(hidden)
            self.cogHead.reparentTo(aspect2d)
            self._cogDialogueSfx.play()
            self.cogHead.setClipPlane(self.cogClipPlane, 100)
            CogdoUtil.clipToBox(self.cogHead, -0.8)

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
        self._loadHeads()
        self._makeIval()

    def _loadHeads(self):
        self.toonDNA = ToonDNA.ToonDNA()
        self.toonDNA.newToonFromProperties('dss', 'ss', 'm', 'm', 2, 0, 2, 2, 1, 8, 1, 8, 1, 14)
        self.toonHead = Toon.Toon()
        self.toonHead.setDNA(self.toonDNA)
        self.makeSuit('f')
        self.toonHead.getGeomNode().setDepthWrite(1)
        self.toonHead.getGeomNode().setDepthTest(1)
        self.toonHead.loop('neutral')
        self.toonHead.setPosHprScale(-0.73, 0, -1.27, 180, 0, 0, 0.18, 0.18, 0.18)
        self.toonHead.reparentTo(hidden)
        self.toonHead.startBlink()
        self.cogHead = Suit.Suit()
        self.cogDNA = SuitDNA.SuitDNA()
        self.cogDNA.newSuit('tbc')
        self.cogHead.setDNA(self.cogDNA)
        self.cogHead.getGeomNode().setDepthWrite(1)
        self.cogHead.getGeomNode().setDepthTest(1)
        self.cogHead.loop('neutral')
        # The Big Cheese is a big cog: small in the box, so his head and
        # shoulders fill it, cut off at its bottom edge.
        self.cogHead.setPosHprScale(-0.73, 0, -1.52, 180, 0, 0, 0.115, 0.115, 0.115)
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

    def _shot(self, duration, pos, target, startPos=None, startTarget=None):
        pos = Point3(*pos)
        target = Point3(*target)
        ival = LerpPosHprInterval(camera, duration, pos, _lookHpr(pos, target), blendType='easeInOut')
        if startPos is None:
            return ival
        startPos = Point3(*startPos)
        startHpr = _lookHpr(startPos, Point3(*startTarget))
        return Sequence(Func(camera.setPosHpr, startPos, startHpr), ival)

    def _makeIval(self):
        dialogue = TTLocalizer.BoardroomIntroMovieDialogue
        page = IntroDurationSeconds / len(dialogue)
        chairman = self._game.chairman if self._game else None

        def shot(duration, pos, target, startPos=None, startTarget=None):
            pos = Point3(*pos)
            target = Point3(*target)
            ival = LerpPosHprInterval(camera, duration, pos, _lookHpr(pos, target), blendType='easeInOut')
            if startPos is None:
                return ival
            startPos = Point3(*startPos)
            startHpr = _lookHpr(startPos, Point3(*startTarget))
            return Sequence(Func(camera.setPosHpr, startPos, startHpr), ival)

        top = Consts.TableTop
        start = Consts.TableStart
        end = Consts.TableEnd
        cx, cy, cz = Consts.ChairmanPos
        mid = (start + end) / 2.0
        anger = (lambda: chairman.loop('sit-angry')) if chairman and chairman.getAnimControl('sit-angry') else (lambda: None)
        sit = (lambda: chairman.loop('sit')) if chairman else (lambda: None)
        self._ival = Sequence(
            Func(camera.wrtReparentTo, render),
            # The Big Cheese at the head of the table.
            Func(anger),
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[0])),
            shot(page, (6, cy - 16, top + 8), (cx, cy, top + 3), (-8, cy - 26, top + 12), (cx, cy, top + 3)),
            # Down the table from the near end.
            Func(sit),
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[1])),
            shot(page, (0, start + 40, top + 6), (0, start + 90, top), (0, start - 8, top + 10), (0, start + 40, top)),
            # Along the Boss Cogs' chairs.
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[2])),
            shot(page, (Consts.TableHalfWidth + 14, mid + 40, top + 10), (0, mid + 70, top),
                 (Consts.TableHalfWidth + 14, mid - 40, top + 10), (0, mid - 10, top)),
            # The whole meeting.
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[3])),
            shot(page, (36, start - 20, 48), (0, mid + 30, top), (-36, start - 20, 48), (0, mid + 30, top)))

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


class CogdoBoardroomGolfIntro(CogdoBoardroomGameIntro):
    """The golf office's intro, after the ride over: the Big Cheese on the
    intercom, then the Toon Resistance shows the barrels, the cogs'
    elevators and the tee, a page at a time, with the game's panel up as in
    the other field offices' intros."""

    def load(self, root):
        CogdoGameMovie.load(self)
        self._loadHeads()
        from .CogdoGameRulesPanel import CogdoGameRulesPanel
        self._panel = CogdoGameRulesPanel('BoardroomGolfPanel', TTLocalizer.BoardroomGolfTitle, '',
                                          'boardroomGolfPanelDone', timeout=Consts.GolfIntroDuration + 2)
        self._panel.load()
        self._panel.playButton.hide()
        self._root = root
        self._makeIval()

    def play(self, elapsedTime=0.0):
        self._panel.enter()
        CogdoGameMovie.play(self, elapsedTime)

    def _makeIval(self):
        dialogue = TTLocalizer.BoardroomGolfIntroDialogue
        page = Consts.GolfIntroDuration / len(dialogue)
        ox, oy, oz = Consts.GolfOrigin
        game = self._game
        index = game.startIndex(base.localAvatar.doId) if game else 0
        tx, ty = Consts.GolfTees[index % len(Consts.GolfTees)]

        def at(x, y, z):
            return (ox + x, oy + y, oz + z)

        px, py = Consts.BarrelPile
        fx, fy, fh = Consts.GolfElevators[0]
        lx, ly, lh = Consts.GolfElevators[1]
        rx, ry, rh = Consts.GolfElevators[2]
        self._ival = Sequence(
            Func(camera.wrtReparentTo, render),
            # The laff barrels, piled where the aisles cross.
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[0])),
            self._shot(page, at(px + 9, py - 14, 9), at(px, py, 2), at(px - 12, py - 22, 14), at(px, py, 2)),
            # The cogs' three elevators: in front, left and right.
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[1])),
            Sequence(self._shot(page / 3.0, at(fx, py, 9), at(fx, fy, 5), at(px + 8, py - 6, 9), at(fx, fy, 5)),
                     self._shot(page / 3.0, at(lx + 22, ly - 4, 9), at(lx, ly, 5)),
                     self._shot(page / 3.0, at(rx - 22, ry - 4, 9), at(rx, ry, 5))),
            # Back to the tee.
            Func(self.displayLine, 'toon', self._getRandomLine(dialogue[2])),
            self._shot(page, at(tx + 5, ty + 6, 5), at(tx, ty, 2), at(rx - 30, ry - 18, 14), at(tx, ty, 2)),
            # And off it goes: the golf camera's view from behind the tee.
            Func(self.displayLine, 'cog', self._getRandomLine(dialogue[3])),
            self._shot(page, at(tx, ty - Consts.GolfCamBack, Consts.GolfCamUp), at(tx, ty + Consts.GolfCamLook, 1)))

    def unload(self):
        self._panel.exit()
        self._panel.unload()
        self._panel = None
        CogdoBoardroomGameIntro.unload(self)
