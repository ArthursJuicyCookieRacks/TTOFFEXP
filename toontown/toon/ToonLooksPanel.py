"""The looks window: the yellow + button by the laff meter, and what it opens.

The button shows while the toon is free to walk around. It opens a small
Shticker Book-like window with the toon's six looks (see ToonLooks) as
Pick-A-Toon squares: tap one to wear it, Edit to change it, the trash can to
delete it, or an empty square to make a new look in the Make-A-Toon room.
"""

from panda3d.core import *
from direct.directnotify import DirectNotifyGlobal
from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import *
from direct.showbase.DirectObject import DirectObject

from toontown.toon import ToonHead
from toontown.toon import ToonLooks
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownGlobals
from toontown.toontowngui import TTDialog

BUTTON_POS = (0.275, 0, 0.22)
YELLOW = (1.0, 0.86, 0.12, 1)
OUTLINE = (0.6, 0.38, 0.0, 1)
# The window sits a little above the middle of the screen.
WINDOW_Z = 0.1
SQUARES = ('Red', 'Green', 'Purple', 'Blue', 'Pink', 'Yellow')
SLOT_POS = ((-0.5, 0.22), (0, 0.22), (0.5, 0.22),
            (-0.5, -0.24), (0, -0.24), (0.5, -0.24))
_circle = []


def circleTexture():
    """A yellow circle with a darker rim and a white plus, made once."""
    if _circle:
        return _circle[0]
    size = 128
    # Half the plus's length and half its thickness, in pixels.
    ARM, THICK = 36, 10
    image = PNMImage(size, size, 4)
    middle = (size - 1) / 2.0
    outer = size / 2.0 - 1
    rim = outer - 9
    for x in range(size):
        for y in range(size):
            distance = ((x - middle) ** 2 + (y - middle) ** 2) ** 0.5
            alpha = max(0.0, min(1.0, outer - distance))
            if distance > rim:
                blend = max(0.0, min(1.0, distance - rim))
                color = [YELLOW[i] * (1 - blend) + OUTLINE[i] * blend for i in range(3)]
            else:
                # A little lighter at the top, like the game's round buttons.
                light = 0.18 * max(0.0, (middle - y) / middle)
                color = [min(1.0, YELLOW[i] + light) for i in range(3)]
            # The plus, drawn in so it sits exactly in the middle: white,
            # with a thin darker edge like the game's button text.
            dx, dy = abs(x - middle), abs(y - middle)
            inside = max(min(ARM - dx, THICK - dy), min(THICK - dx, ARM - dy))
            if inside > -2.5:
                edge = max(0.0, min(1.0, inside + 2.5))
                fill = max(0.0, min(1.0, inside + 0.5))
                color = [color[i] * (1 - edge) + OUTLINE[i] * edge for i in range(3)]
                color = [color[i] * (1 - fill) + fill for i in range(3)]
            image.setXelA(x, y, color[0], color[1], color[2], alpha)
    texture = Texture('looksButtonCircle')
    texture.load(image)
    texture.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    texture.setMagfilter(SamplerState.FT_linear)
    card = CardMaker('looksButton')
    card.setFrame(-1, 1, -1, 1)
    node = NodePath(card.generate())
    node.setTexture(texture)
    node.setTransparency(TransparencyAttrib.MAlpha)
    _circle.append(node)
    return node


def currentPlace():
    playGame = getattr(base.cr, 'playGame', None)
    return playGame.getPlace() if playGame else None


def canOpen():
    place = currentPlace()
    if place is None or not hasattr(place, 'fsm') or getattr(localAvatar, 'isDisguised', 0):
        return False
    state = place.fsm.getCurrentState()
    return state is not None and state.getName() == 'walk' and state.isTransitionDefined('stopped')


class LooksButton(DirectObject):
    """The yellow + by the laff meter."""

    def __init__(self):
        DirectObject.__init__(self)
        circle = circleTexture()
        self.button = DirectButton(parent=base.a2dBottomLeft, relief=None, image=circle, image_scale=0.048, image1_scale=0.053, image2_scale=0.053, pos=BUTTON_POS, command=self.open, sortOrder=DGG.FOREGROUND_SORT_INDEX)
        self.button.hide()
        self.window = None
        taskMgr.add(self.watch, 'looksButtonWatch')

    def watch(self, task):
        laffShown = not localAvatar.laffMeter.isHidden()
        show = laffShown and self.window is None and canOpen()
        if show and self.button.isHidden():
            self.button.show()
        elif not show and not self.button.isHidden():
            self.button.hide()
        return task.cont

    def open(self):
        if self.window is None and canOpen():
            self.window = LooksWindow(self.closed)

    def closed(self):
        self.window = None

    def destroy(self):
        taskMgr.remove('looksButtonWatch')
        if self.window is not None:
            self.window.close(walk=False)
        self.button.destroy()


class LooksWindow(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('LooksWindow')

    def __init__(self, onClosed):
        DirectObject.__init__(self)
        self.onClosed = onClosed
        self.looks = ToonLooks.Looks.load(localAvatar)
        self.frame = None
        self.editor = None
        self.dialog = None
        self.slots = []
        self.place = currentPlace()
        self.place.fsm.request('stopped')
        localAvatar.stopSleepWatch()
        bookModel = loader.loadModel('phase_3.5/models/gui/stickerbook_gui')
        self.bookImage = bookModel.find('**/big_book')
        self.openSound = base.loader.loadSfx('phase_3.5/audio/sfx/GUI_stickerbook_open.ogg')
        self.closeSound = base.loader.loadSfx('phase_3.5/audio/sfx/GUI_stickerbook_delete.ogg')
        self.wearSound = base.loader.loadSfx('phase_3/audio/sfx/GUI_create_toon_fwd.ogg')
        bookModel.removeNode()
        taskMgr.add(self.guard, 'looksWindowGuard')
        localAvatar.b_setAnimState('OpenBook', 1, self.show)

    # --- The window ---

    def show(self):
        if self.onClosed is None:
            return
        localAvatar.b_setAnimState('ReadBook', 1)
        base.playSfx(self.openSound)
        self.build()
        self.frame.setScale(0.2)
        self.popIval = self.frame.scaleInterval(0.18, 1.0, startScale=0.2, blendType='easeOut')
        self.popIval.start()

    def build(self):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = DirectFrame(parent=aspect2d, relief=None, image=self.bookImage, image_scale=(1.75, 1, 1.32), pos=(0, 0, WINDOW_Z), sortOrder=DGG.BACKGROUND_SORT_INDEX + 5, state=DGG.NORMAL)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.55), text=TTLocalizer.LooksTitle, text_font=ToontownGlobals.getSignFont(), text_scale=0.1, text_fg=(0.16, 0.32, 0.72, 1))
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.48), text=TTLocalizer.LooksHelp, text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.042, text_fg=(0.3, 0.3, 0.3, 1))
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        DirectButton(parent=self.frame, relief=None, image=(buttons.find('**/CloseBtn_UP'), buttons.find('**/CloseBtn_DN'), buttons.find('**/CloseBtn_Rllvr')), pos=(0.72, 0, -0.5), scale=0.8, text=TTLocalizer.LooksClose, text_scale=0.05, text_pos=(0, -0.1), text_fg=(0.3, 0.3, 0.3, 1), command=self.close)
        buttons.removeNode()
        patGui = loader.loadModel('phase_3/models/gui/tt_m_gui_pat_mainGui')
        trashGui = loader.loadModel('phase_3/models/gui/trashcan_gui')
        quitGui = loader.loadModel('phase_3/models/gui/quit_button')
        self.slots = []
        for slot in range(ToonLooks.SLOTS):
            self.slots.append(self.makeSlot(slot, patGui, trashGui, quitGui))
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, -0.53), text=TTLocalizer.LooksKeep, text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.038, text_fg=(0.35, 0.35, 0.35, 1))
        for model in (patGui, trashGui, quitGui):
            model.removeNode()

    def makeSlot(self, slot, patGui, trashGui, quitGui):
        x, z = SLOT_POS[slot]
        look = self.looks.looks[slot]
        square = patGui.find('**/tt_t_gui_pat_square' + SQUARES[slot])
        wearing = slot == self.looks.wearing
        button = DirectButton(parent=self.frame, relief=None, image=square, image_scale=0.62, image1_scale=0.66, image2_scale=0.66, image3_color=(1, 1, 1, 1), pos=(x, 0, z), text_font=ToontownGlobals.getSignFont(), text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), command=self.pick, extraArgs=[slot])
        if look is None:
            button['text'] = ('+', '+', '+', '+')
            button['text_scale'] = 0.16
            button['text_pos'] = (0, -0.03)
            button['image_color'] = (1, 1, 1, 0.55)
            DirectLabel(parent=button, relief=None, pos=(0, 0, -0.12), text=TTLocalizer.LooksNew, text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.045, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1))
            return button
        if wearing:
            button['state'] = DGG.DISABLED
        head = hidden.attachNewNode('lookHead')
        head.setPosHprScale(0, 5, -0.05, 180, 0, 0, 0.15, 0.15, 0.15)
        head.reparentTo(button.stateNodePath[0], 20)
        for state in (1, 2, 3):
            head.instanceTo(button.stateNodePath[state], 20)
        dna = ToonLooks.dnaOf(look)
        model = ToonHead.ToonHead()
        model.setupHead(dna, forGui=1)
        model.reparentTo(head)
        model.setScale(ToontownGlobals.toonBodyScales[dna.getAnimal()] / 0.75)
        model.startBlink()
        model.startLookAround()
        button.headModel = model
        DirectLabel(parent=button, relief=None, pos=(0, 0, 0.115), text=TTLocalizer.LooksNumber % (slot + 1), text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.04, text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1))
        if wearing:
            DirectLabel(parent=button, relief=None, pos=(0, 0, -0.178), text=TTLocalizer.LooksWearing, text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.045, text_fg=(1, 0.95, 0.3, 1), text_shadow=(0, 0, 0, 1))
        else:
            DirectButton(parent=button, relief=None, image=(trashGui.find('**/TrashCan_CLSD'), trashGui.find('**/TrashCan_OPEN'), trashGui.find('**/TrashCan_RLVR')), pos=(0.14, 0, -0.16), scale=0.27, command=self.askRemove, extraArgs=[slot])
        DirectButton(parent=button, relief=None, image=(quitGui.find('**/QuitBtn_UP'), quitGui.find('**/QuitBtn_DN'), quitGui.find('**/QuitBtn_RLVR')), image_scale=(0.75, 1, 1.1), pos=(-0.06 if not wearing else 0, 0, -0.235), scale=0.5, text=TTLocalizer.LooksEdit, text_font=ToontownGlobals.getInterfaceFont(), text_scale=0.1, text_pos=(0, -0.03), text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), command=self.edit, extraArgs=[slot])
        return button

    def destroyFrame(self):
        if getattr(self, 'popIval', None):
            self.popIval.finish()
            self.popIval = None
        for button in self.slots:
            if hasattr(button, 'headModel'):
                button.headModel.stopBlink()
                button.headModel.stopLookAroundNow()
                button.headModel.delete()
        self.slots = []
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None

    # --- Choices ---

    def pick(self, slot):
        if self.looks.looks[slot] is None:
            self.edit(slot)
        elif slot != self.looks.wearing:
            self.wearSlot(slot)
            self.build()

    def wearSlot(self, slot):
        # The worn look as it is now (a closet may have changed it), then the new one.
        self.looks.looks[self.looks.wearing] = ToonLooks.lookOf(localAvatar)
        if ToonLooks.wear(self.looks.looks[slot]):
            self.looks.wearing = slot
            base.playSfx(self.wearSound)
        self.looks.save()

    def askRemove(self, slot):
        self.closeDialog()
        self.dialog = TTDialog.TTDialog(parent=aspect2dp, style=TTDialog.YesNo, text=TTLocalizer.LooksDeleteAsk % (slot + 1), text_wordwrap=14, command=self.remove, extraArgs=[slot])
        self.dialog.show()

    def remove(self, answer, slot):
        self.closeDialog()
        if answer == DGG.DIALOG_OK and self.looks.remove(slot):
            self.build()

    def closeDialog(self):
        if self.dialog is not None:
            self.dialog.cleanup()
            self.dialog = None

    def edit(self, slot):
        from toontown.makeatoon import LookEditor
        self.closeDialog()
        self.destroyFrame()
        look = self.looks.looks[slot]
        if slot == self.looks.wearing:
            look = ToonLooks.lookOf(localAvatar)
        self.editing = slot
        self.editor = LookEditor.LookEditor(look, self.edited)

    def edited(self, look):
        self.editor = None
        slot = self.editing
        if look is not None:
            self.looks.looks[self.looks.wearing] = ToonLooks.lookOf(localAvatar)
            self.looks.looks[slot] = look
            # A new or changed look goes straight on.
            if ToonLooks.wear(look):
                self.looks.wearing = slot
            self.looks.save()
        if self.onClosed is not None:
            self.build()

    # --- Closing ---

    def guard(self, task):
        # Anything that takes the toon out of its stopped place (a teleport,
        # the server) closes the window without walking.
        place = currentPlace()
        state = place.fsm.getCurrentState() if place is not None and hasattr(place, 'fsm') else None
        if place is not self.place or state is None or state.getName() != 'stopped':
            self.close(walk=False)
            return task.done
        return task.cont

    def close(self, walk=True):
        if self.onClosed is None:
            return
        onClosed = self.onClosed
        self.onClosed = None
        taskMgr.remove('looksWindowGuard')
        self.closeDialog()
        if self.editor is not None:
            editor = self.editor
            self.editor = None
            editor.close(None)
        self.destroyFrame()
        if walk:
            base.playSfx(self.closeSound)
            localAvatar.b_setAnimState('CloseBook', 1, callback=self.walk)
        onClosed()

    def walk(self):
        place = currentPlace()
        if place is self.place and place.fsm.getCurrentState().getName() == 'stopped':
            place.fsm.request('walk')
