"""Pause menu > Settings > Key Bindings: Survival's keys on a keyboard and
mouse. Click an action, then press the key (or mouse button) for it; Esc
stops waiting. Reset puts every key back."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode

from toontown.survival import SurvivalKeys
from toontown.toonbase import ToontownGlobals

RED = (0.85, 0.08, 0.08, 1)
YELLOW = (1, 0.95, 0.4, 1)
CAPTURE_PREFIX = 'survivalKeyCapture-'
CAPTURE_EVENT = 'survivalKeyCaptured'
# The click that picked a row is not the new key.
CLICK_GRACE = 0.3


class SurvivalKeyCard(DirectObject):

    def __init__(self, game, onBack):
        DirectObject.__init__(self)
        self.game = game
        self.onBack = onBack
        self.capturing = None
        self.captureStart = 0.0
        self.savedThrowers = []
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        self.frame = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.05, 0.05, 0.08, 0.92),
                                 frameSize=(-1.05, 1.05, -0.85, 0.85), sortOrder=100, state=DGG.NORMAL)
        OnscreenText(parent=self.frame, text='Key Bindings', font=sign, fg=RED, shadow=(0, 0, 0, 1), scale=0.12, pos=(0, 0.68))
        self.help = OnscreenText(parent=self.frame, text='', font=face, fg=(0.85, 0.85, 0.85, 1), scale=0.045,
                                 pos=(0, 0.58), mayChange=True)
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        self.image = (gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR'))
        self.buttons = {}
        rows = SurvivalKeys.BINDABLE
        half = (len(rows) + 1) // 2
        for i, (name, label, default) in enumerate(rows):
            col, row = divmod(i, half)
            x = -0.98 + col * 1.02
            z = 0.45 - row * 0.115
            OnscreenText(parent=self.frame, text=label, font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), scale=0.05,
                         pos=(x, z - 0.015), align=TextNode.ALeft)
            self.buttons[name] = DirectButton(parent=self.frame, relief=None, image=self.image, image_scale=(0.75, 1, 0.9),
                                              text='', text_font=face, text_fg=(0.2, 0.1, 0.02, 1), text_scale=0.045,
                                              text_pos=(0, -0.015), pos=(x + 0.72, 0, z), command=self.__start,
                                              extraArgs=[name])
        DirectButton(parent=self.frame, relief=None, image=self.image, image_scale=(1.1, 1, 1.15), text='Reset', text_font=sign,
                     text_fg=YELLOW, text_scale=0.065, text_pos=(0, -0.02), pos=(-0.3, 0, -0.72), command=self.__reset)
        DirectButton(parent=self.frame, relief=None, image=self.image, image_scale=(1.1, 1, 1.15), text='Back', text_font=sign,
                     text_fg=YELLOW, text_scale=0.065, text_pos=(0, -0.02), pos=(0.3, 0, -0.72), command=self.__back)
        self.__refresh()

    def __refresh(self, message=None):
        for name, button in self.buttons.items():
            if name == self.capturing:
                button['text'] = 'Press a key'
            else:
                button['text'] = SurvivalKeys.label(SurvivalKeys.getKey(name))
        if message is not None:
            self.help.setText(message)
        elif self.capturing:
            self.help.setText('Press the key for %s (Esc to cancel)' % SurvivalKeys.LABELS[self.capturing])
        else:
            self.help.setText('Click an action, then press its new key or mouse button.')

    def __start(self, name):
        self.__stop()
        self.capturing = name
        self.captureStart = globalClock.getRealTime()
        # Every press comes in under another name while a key is picked, so
        # Esc or a gag key only picks it.
        for thrower in base.buttonThrowers:
            node = thrower.node()
            self.savedThrowers.append((node, node.getPrefix(), node.getButtonDownEvent()))
            node.setPrefix(CAPTURE_PREFIX)
            node.setButtonDownEvent(CAPTURE_EVENT)
        self.accept(CAPTURE_EVENT, self.__captured)
        self.__refresh()

    def __stop(self):
        if self.capturing is None:
            return
        self.capturing = None
        self.ignore(CAPTURE_EVENT)
        for node, prefix, downEvent in self.savedThrowers:
            node.setPrefix(prefix)
            node.setButtonDownEvent(downEvent)
        self.savedThrowers = []

    def __captured(self, key):
        name = self.capturing
        if name is None:
            return
        if key.startswith('mouse') and globalClock.getRealTime() - self.captureStart < CLICK_GRACE:
            return
        if key == 'escape':
            self.__stop()
            self.__refresh()
            return
        key = SurvivalKeys.NORMALIZE.get(key, key)
        if key in SurvivalKeys.RESERVED or key.startswith('wheel'):
            self.__refresh('%s always does its own job. Pick another key.' % SurvivalKeys.label(key))
            return
        SurvivalKeys.setKey(name, key)
        self.__stop()
        self.game.player.acceptKeys()
        self.__refresh('%s: %s' % (SurvivalKeys.LABELS[name], SurvivalKeys.label(key)))

    def __reset(self):
        self.__stop()
        SurvivalKeys.resetKeys()
        self.game.player.acceptKeys()
        self.__refresh('Every key is back to the start.')

    def __back(self):
        self.destroy()
        self.game.hud.card = None
        self.onBack()

    def destroy(self):
        self.__stop()
        self.ignoreAll()
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None
