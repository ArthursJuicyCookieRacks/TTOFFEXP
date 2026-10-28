"""Making (or changing) one of the toon's looks, in the Make-A-Toon room.

The Make-A-Toon shops (boy or girl, body, colours, clothes and accessories)
on a stand-in toon, with no name to pick: the look is all that changes. It
plays in the game itself, over the place the toon is in (which is hidden,
along with its buttons, until the editor closes).

`done` is called with the new look (see ToonLooks), or None if cancelled.
"""

from panda3d.core import *
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import ClassicFSM, State
from direct.gui.DirectGui import *
from direct.showbase.DirectObject import DirectObject

from toontown.toon import Toon
from toontown.toon import ToonLooks
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownGlobals
from .MakeAToonGlobals import *
from . import BodyShop
from . import ColorShop
from . import GenderShop
from . import HoldRepeat
from . import MakeClothesGUI

# Far under the world, so the room is the only thing the camera sees.
STAGE_POS = (0, 0, -1000)
CAMERA_POS_HPR = (-5.7, -12.3501, 2.15, -24.8499, 2.73, 0)
SHOPS = ('GenderShop', 'BodyShop', 'ColorShop', 'ClothesShop')


class LookEditor(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('LookEditor')

    def __init__(self, look, done):
        """look: the look to start from, or None to start a new one."""
        DirectObject.__init__(self)
        self.done = done
        self.toonPosition = Point3(-1.62, -3.49, 0)
        self.toonScale = Point3(1, 1, 1)
        self.toonHpr = Point3(180, 0, 0)
        self.hprDelta = -1
        self.toon = None
        self.ownToon = False
        self.shopsVisited = []
        self.fsm = ClassicFSM.ClassicFSM('LookEditor', [
            State.State('Init', lambda: None, lambda: None, ['GenderShop', 'BodyShop']),
            State.State('GenderShop', self.enterGenderShop, self.exitGenderShop, ['BodyShop', 'Done']),
            State.State('BodyShop', self.enterBodyShop, self.exitBodyShop, ['GenderShop', 'ColorShop', 'Done']),
            State.State('ColorShop', self.enterColorShop, self.exitColorShop, ['BodyShop', 'ClothesShop', 'Done']),
            State.State('ClothesShop', self.enterClothesShop, self.exitClothesShop, ['ColorShop', 'Done']),
            State.State('Done', lambda: None, lambda: None, [])], 'Init', 'Done')
        self.fsm.enterInitialState()
        self.hideGame()
        self.load()
        if look is not None:
            self.startFrom(look)
            self.fsm.request('BodyShop')
        else:
            self.fsm.request('GenderShop')

    # --- The game behind it ---

    def hideGame(self):
        self.hiddenGui = [child for child in aspect2d.getChildren() if not child.isHidden()]
        for child in self.hiddenGui:
            child.hide()
        self.oldCameraParent = camera.getParent()
        self.oldCameraTransform = camera.getTransform()
        self.oldFov = base.camLens.getMinFov()
        self.stage = render.attachNewNode('lookEditorStage')
        self.stage.setPos(*STAGE_POS)
        self.stage.setFogOff()
        camera.reparentTo(self.stage)
        camera.setPosHpr(*CAMERA_POS_HPR)
        base.camLens.setFov(ToontownGlobals.MakeAToonCameraFov)

    def showGame(self):
        camera.reparentTo(self.oldCameraParent)
        camera.setTransform(self.oldCameraTransform)
        base.camLens.setMinFov(self.oldFov)
        for child in self.hiddenGui:
            if not child.isEmpty():
                child.show()
        self.hiddenGui = []

    # --- Loading ---

    def load(self):
        self.room = loader.loadModel('phase_3/models/makeatoon/tt_m_ara_mat_room')
        self.room.reparentTo(self.stage)
        self.walls = {}
        for shop, walls, props in (('GenderShop', 'genderWalls', 'genderProps'),
                                   ('BodyShop', 'bodyWalls', 'bodyProps'),
                                   ('ColorShop', 'colorWalls', 'colorProps'),
                                   ('ClothesShop', 'clothWalls', 'clothProps')):
            self.walls[shop] = [self.room.find('**/' + walls), self.room.find('**/' + props)]
        for name in ('nameWalls', 'nameProps', 'spotlight'):
            self.room.find('**/' + name).stash()
        self.showWalls(None)
        gui = loader.loadModel('phase_3/models/gui/tt_m_gui_mat_mainGui')
        acceptUp = gui.find('**/tt_t_gui_mat_okUp')
        acceptDown = gui.find('**/tt_t_gui_mat_okDown')
        cancelUp = gui.find('**/tt_t_gui_mat_closeUp')
        cancelDown = gui.find('**/tt_t_gui_mat_closeDown')
        nextUp = gui.find('**/tt_t_gui_mat_nextUp')
        nextDown = gui.find('**/tt_t_gui_mat_nextDown')
        nextDisabled = gui.find('**/tt_t_gui_mat_nextDisabled')
        rotateUp = gui.find('**/tt_t_gui_mat_arrowRotateUp')
        rotateDown = gui.find('**/tt_t_gui_mat_arrowRotateDown')
        self.topBar = DirectFrame(relief=None, text='', text_font=ToontownGlobals.getSignFont(), text_fg=(1, 0.92, 0.2, 1), text_scale=0.18, text_pos=(0, -0.03), pos=(0, 0, 0.86))
        self.bottomBar = DirectFrame(relief=None, pos=(0.01, 0, -0.86))
        textArgs = dict(text_font=ToontownGlobals.getInterfaceFont(), text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1))
        self.doneButton = DirectButton(parent=self.bottomBar, relief=None, image=(acceptUp, acceptDown, acceptUp, acceptDown), image_scale=halfButtonScale, image1_scale=halfButtonHoverScale, image2_scale=halfButtonHoverScale, pos=(1.165, 0, -0.018), command=self.finish, text=('', TTLocalizer.MakeAToonDone, TTLocalizer.MakeAToonDone), text_scale=0.08, text_align=TextNode.ARight, text_pos=(0.13, 0.13), **textArgs)
        self.cancelButton = DirectButton(parent=self.bottomBar, relief=None, image=(cancelUp, cancelDown, cancelUp, cancelDown), image_scale=halfButtonScale, image1_scale=halfButtonHoverScale, image2_scale=halfButtonHoverScale, pos=(-1.179, 0, -0.011), command=self.cancel, text=('', TTLocalizer.MakeAToonCancel, TTLocalizer.MakeAToonCancel), text_scale=TTLocalizer.MATguiCancelButton, text_pos=(0, 0.115), **textArgs)
        self.nextButton = DirectButton(parent=self.bottomBar, relief=None, image=(nextUp, nextDown, nextUp, nextDisabled), image_scale=(0.3, 0.3, 0.3), image1_scale=(0.35, 0.35, 0.35), image2_scale=(0.35, 0.35, 0.35), pos=(1.165, 0, -0.018), command=messenger.send, extraArgs=['next'], text=('', TTLocalizer.MakeAToonNext, TTLocalizer.MakeAToonNext, ''), text_scale=TTLocalizer.MATguiNextButton, text_pos=(0, 0.115), **textArgs)
        self.lastButton = DirectButton(parent=self.bottomBar, relief=None, image=(nextUp, nextDown, nextUp, nextDown), image3_color=Vec4(0.5, 0.5, 0.5, 0.75), image_scale=(-0.3, 0.3, 0.3), image1_scale=(-0.35, 0.35, 0.35), image2_scale=(-0.35, 0.35, 0.35), pos=(0.825, 0, -0.018), command=messenger.send, extraArgs=['last'], text=('', TTLocalizer.MakeAToonLast, TTLocalizer.MakeAToonLast, ''), text_scale=0.08, text_pos=(0, 0.115), **textArgs)
        self.rotateLeftButton = DirectButton(parent=self.bottomBar, relief=None, image=(rotateUp, rotateDown, rotateUp, rotateDown), image_scale=(-0.4, 0.4, 0.4), image1_scale=(-0.5, 0.5, 0.5), image2_scale=(-0.5, 0.5, 0.5), pos=(-0.329249, 0, 0.262961), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        self.rotateLeftButton.bind(DGG.B1PRESS, self.startRotate, [1])
        self.rotateLeftButton.bind(DGG.B1RELEASE, self.stopRotate)
        self.rotateRightButton = DirectButton(parent=self.bottomBar, relief=None, image=(rotateUp, rotateDown, rotateUp, rotateDown), image_scale=(0.4, 0.4, 0.4), image1_scale=(0.5, 0.5, 0.5), image2_scale=(0.5, 0.5, 0.5), pos=(0.309534, 0, 0.266116), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        self.rotateRightButton.bind(DGG.B1PRESS, self.startRotate, [-1])
        self.rotateRightButton.bind(DGG.B1RELEASE, self.stopRotate)
        gui.removeNode()
        self.gs = GenderShop.GenderShop(self, 'LookGenderShop-done')
        self.bs = BodyShop.BodyShop('LookBodyShop-done')
        self.cos = ColorShop.ColorShop('LookColorShop-done')
        self.cls = MakeClothesGUI.MakeClothesGUI('LookClothesShop-done')
        for shop in (self.gs, self.bs, self.cos, self.cls):
            shop.load()
        for shop in (self.bs, self.cos, self.cls):
            shop.hideButtons()
            HoldRepeat.addToArrows(shop.parentFrame)
        self.gs.hideButtons()
        self.music = base.loader.loadMusic('phase_3/audio/bgm/create_a_toon.ogg')
        base.playMusic(self.music, looping=1, volume=0.8)

    def unload(self):
        self.stopRotate()
        if self.fsm.getCurrentState().getName() != 'Done':
            self.fsm.request('Done')
        self.ignoreAll()
        self.music.stop()
        for shop in (self.bs, self.cos, self.cls):
            shop.unload()
        if self.ownToon and self.toon:
            self.toon.stopBlink()
            self.toon.stopLookAroundNow()
            self.toon.delete()
        else:
            self.toon = None
        # The Boy/Girl shop deletes the toon it made, if that's the one here.
        self.gs.unload()
        self.toon = None
        for widget in (self.topBar, self.bottomBar):
            widget.destroy()
        self.room.removeNode()
        self.stage.removeNode()
        self.showGame()
        if base.cr.playGame.hood is not None and getattr(base.cr.playGame.hood, 'loader', None) is not None:
            music = getattr(base.cr.playGame.hood.loader, 'music', None)
            if music:
                base.playMusic(music, looping=1, volume=0.8)

    # --- The stand-in toon ---

    def startFrom(self, look):
        toon = Toon.Toon()
        toon.setDNA(ToonLooks.dnaOf(look))
        for kind in ToonLooks.ACCESSORIES:
            getattr(toon, 'set' + kind.capitalize())(*look.get(kind, (0, 0, 0)))
            choices = self.cls.accessories[kind][0]
            value = tuple(look.get(kind, (0, 0, 0)))
            self.cls.accessories[kind][1] = choices.index(value) if value in choices else 0
        toon.useLOD(1000)
        toon.setNameVisible(0)
        toon.startBlink()
        toon.startLookAround()
        toon.setPos(self.toonPosition)
        toon.setHpr(self.toonHpr)
        toon.loop('neutral')
        self.setToon(toon)
        self.ownToon = True
        self.shopsVisited = [GENDERSHOP]

    def setToon(self, toon):
        """Also the Boy/Girl shop's call, when it makes a new toon."""
        if self.ownToon and self.toon is not None and self.toon is not toon:
            self.toon.stopBlink()
            self.toon.stopLookAroundNow()
            self.toon.delete()
        self.ownToon = False
        self.toon = toon
        toon.reparentTo(self.stage)

    def setNextButtonState(self, state):
        self.nextButton['state'] = state

    def startRotate(self, direction, event=None):
        self.stopRotate()
        taskMgr.add(self.rotateTask, 'lookEditorRotate', extraArgs=[direction], appendTask=True)

    def stopRotate(self, event=None):
        taskMgr.remove('lookEditorRotate')

    def rotateTask(self, direction, task):
        if not HoldRepeat.mouseHeld() or self.toon is None:
            return task.done
        self.toon.setH(self.toon.getH() + self.hprDelta * direction)
        return task.cont

    # --- The shops ---

    def showWalls(self, shop):
        for name, nodes in self.walls.items():
            for node in nodes:
                if name == shop:
                    node.unstash()
                else:
                    node.stash()

    def showShop(self, shop, title, color):
        self.showWalls(shop)
        self.topBar['text'] = title
        self.topBar['text_fg'] = color
        first = shop == 'GenderShop'
        last = shop == 'ClothesShop'
        self.lastButton.show() if not first else self.lastButton.hide()
        self.nextButton.show() if not last else self.nextButton.hide()
        self.doneButton.show() if last else self.doneButton.hide()
        self.rotateLeftButton.show() if not first else self.rotateLeftButton.hide()
        self.rotateRightButton.show() if not first else self.rotateRightButton.hide()

    def shopDone(self, shop):
        status = getattr(shop, 'doneStatus', 'next')
        index = SHOPS.index(self.fsm.getCurrentState().getName())
        index = index + 1 if status == 'next' else index - 1
        self.fsm.request(SHOPS[max(0, min(len(SHOPS) - 1, index))])

    def enterGenderShop(self):
        self.showShop('GenderShop', TTLocalizer.CreateYourToonTitle, (1, 0.92, 0.2, 1))
        if self.toon is None:
            self.nextButton['state'] = DGG.DISABLED
        self.accept('LookGenderShop-done', self.shopDone, [self.gs])
        self.gs.enter()
        self.gs.showButtons()

    def exitGenderShop(self):
        self.gs.exit()
        self.gs.hideButtons()
        self.ignore('LookGenderShop-done')

    def enterBodyShop(self):
        self.showShop('BodyShop', TTLocalizer.ShapeYourToonTitle, (0.0, 0.98, 0.5, 1))
        self.toon.show()
        self.accept('LookBodyShop-done', self.shopDone, [self.bs])
        self.bs.enter(self.toon, self.shopsVisited)
        if BODYSHOP not in self.shopsVisited:
            self.shopsVisited.append(BODYSHOP)
        self.bs.showButtons()

    def exitBodyShop(self):
        self.bs.exit()
        self.bs.hideButtons()
        self.ignore('LookBodyShop-done')

    def enterColorShop(self):
        self.showShop('ColorShop', TTLocalizer.PaintYourToonTitle, (0, 1, 1, 1))
        self.toon.setPos(self.toonPosition)
        self.accept('LookColorShop-done', self.shopDone, [self.cos])
        self.cos.showButtons()
        self.cos.enter(self.toon, self.shopsVisited)
        if COLORSHOP not in self.shopsVisited:
            self.shopsVisited.append(COLORSHOP)

    def exitColorShop(self):
        self.cos.exit()
        self.cos.hideButtons()
        self.ignore('LookColorShop-done')

    def enterClothesShop(self):
        self.showShop('ClothesShop', TTLocalizer.PickClothesTitle, (1, 0.92, 0.2, 1))
        self.toon.setScale(self.toonScale)
        self.toon.setPos(self.toonPosition)
        self.accept('LookClothesShop-done', self.shopDone, [self.cls])
        self.cls.showButtons()
        self.cls.enter(self.toon)
        if CLOTHESSHOP not in self.shopsVisited:
            self.shopsVisited.append(CLOTHESSHOP)

    def exitClothesShop(self):
        self.cls.exit()
        self.cls.hideButtons()
        self.ignore('LookClothesShop-done')

    # --- Leaving ---

    def finish(self):
        look = {'dna': self.toon.style.makeNetString().hex()}
        for kind, value in zip(ToonLooks.ACCESSORIES, self.cls.getAccessories()):
            look[kind] = list(value)
        self.close(look)

    def cancel(self):
        self.close(None)

    def close(self, look):
        done = self.done
        self.done = None
        self.unload()
        if done:
            done(look)
