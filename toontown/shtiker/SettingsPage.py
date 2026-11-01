"""The Shticker Book's Settings page (after Events).

General: field of view, music and sound effects volume, and how fast the
controller moves the on-screen pointer (1 slowest .. 10 fastest).
Keyboard: what key does each action (click one, then press the new key).
Controller: what each controller button does.
"""

from panda3d.core import TextNode, Vec4
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectSlider, DGG
from direct.directnotify import DirectNotifyGlobal

from toontown.shtiker import ShtikerPage
from toontown.toonbase import GameSettings, KeyBindings, TTLocalizer, ToontownGlobals

GENERAL, KEYBOARD, CONTROLLER = range(3)
TEXT_COLOR = Vec4(0.2, 0.1, 0, 1)
CAPTURE_PREFIX = 'settings-capture-'
CAPTURE_EVENT = 'settings-capture-key'


class SettingsPage(ShtikerPage.ShtikerPage):
    notify = DirectNotifyGlobal.directNotify.newCategory('SettingsPage')

    def __init__(self):
        ShtikerPage.ShtikerPage.__init__(self)
        self.mode = GENERAL
        self.capturing = None
        self.keyButtons = {}
        self.padButtons = {}
        self.sliders = {}

    def load(self):
        ShtikerPage.ShtikerPage.load(self)
        self.title = DirectLabel(parent=self, relief=None, text=TTLocalizer.SettingsPageTitle, text_scale=0.12,
                                 pos=(0, 0, 0.61))
        self.buttonGui = loader.loadModel('phase_3/models/gui/quit_button')
        self.btnImage = (self.buttonGui.find('**/QuitBtn_UP'), self.buttonGui.find('**/QuitBtn_DN'),
                         self.buttonGui.find('**/QuitBtn_RLVR'))
        gui = loader.loadModel('phase_3.5/models/gui/fishingBook')
        normalColor = (1, 1, 1, 1)
        clickColor = (0.8, 0.8, 0, 1)
        rolloverColor = (0.15, 0.82, 1.0, 1)
        disabledColor = (1.0, 0.98, 0.15, 1)
        self.tabs = []
        for mode, text, surface, imagePos, x in (
                (GENERAL, TTLocalizer.SettingsPageGeneralTab, 'polySurface1', (0.55, 1, -0.91), -0.55),
                (KEYBOARD, TTLocalizer.SettingsPageKeyboardTab, 'polySurface2', (0.12, 1, -0.91), -0.13),
                (CONTROLLER, TTLocalizer.SettingsPageControllerTab, 'polySurface3', (-0.28, 1, -0.91), 0.28)):
            tab = DirectButton(parent=self, relief=None, text=text, text_scale=0.06, text_align=TextNode.ALeft,
                               text_pos=(-0.01, 0.0, 0.0), image=gui.find('**/tabs/' + surface), image_pos=imagePos,
                               image_hpr=(0, 0, -90), image_scale=(0.033, 0.033, 0.035), image_color=normalColor,
                               image1_color=clickColor, image2_color=rolloverColor, image3_color=disabledColor,
                               text_fg=TEXT_COLOR, command=self.setMode, extraArgs=[mode], pos=(x, 0, 0.775))
            self.tabs.append(tab)
        gui.removeNode()
        self.frames = [DirectFrame(parent=self, relief=None) for i in range(3)]
        self.__loadGeneral(self.frames[GENERAL])
        self.__loadKeyboard(self.frames[KEYBOARD])
        self.__loadController(self.frames[CONTROLLER])

    # General

    def __loadGeneral(self, frame):
        rows = (
            ('fov', TTLocalizer.SettingsPageFov, GameSettings.FOV_MIN, GameSettings.FOV_MAX, 1,
             GameSettings.getFov, GameSettings.setFov),
            ('music', TTLocalizer.SettingsPageMusic, 0, 100, 5, GameSettings.getMusicVolume,
             GameSettings.setMusicVolume),
            ('sfx', TTLocalizer.SettingsPageSfx, 0, 100, 5, GameSettings.getSfxVolume, GameSettings.setSfxVolume),
            ('cursor', TTLocalizer.SettingsPageCursor, 1, 10, 1, KeyBindings.getCursorSpeed,
             KeyBindings.setCursorSpeed),
        )
        z = 0.42
        for name, label, low, high, step, getter, setter in rows:
            DirectLabel(parent=frame, relief=None, text=label, text_align=TextNode.ALeft, text_scale=0.055,
                        text_fg=TEXT_COLOR, pos=(-0.72, 0, z))
            value = DirectLabel(parent=frame, relief=None, text='', text_align=TextNode.ACenter, text_scale=0.055,
                                text_fg=TEXT_COLOR, pos=(0.62, 0, z))
            slider = DirectSlider(parent=frame, range=(low, high), value=getter(), pageSize=step, scrollSize=step,
                                  pos=(0.12, 0, z + 0.015), scale=(0.38, 1, 0.4), frameColor=(0.55, 0.45, 0.3, 1),
                                  thumb_relief=DGG.FLAT, thumb_frameColor=(1, 0.85, 0.2, 1),
                                  thumb_frameSize=(-0.05, 0.05, -0.1, 0.1))
            slider['command'] = self.__sliderMoved
            slider['extraArgs'] = [name]
            self.sliders[name] = (slider, value, low, high, step, getter, setter)
            z -= 0.2
        DirectLabel(parent=frame, relief=None, text=TTLocalizer.SettingsPageCursorHelp, text_align=TextNode.ALeft,
                    text_scale=0.04, text_wordwrap=34, text_fg=TEXT_COLOR, pos=(-0.72, 0, z + 0.07))
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1), text=TTLocalizer.SettingsPageReset,
                     text_scale=0.05, text_pos=(0, -0.02), pos=(0, 0, -0.5), command=self.__resetGeneral)

    def __sliderMoved(self, name):
        slider, valueLabel, low, high, step, getter, setter = self.sliders[name]
        value = int(round(slider['value'] / float(step))) * step
        value = max(low, min(high, value))
        valueLabel['text'] = str(value)
        if value != getter():
            setter(value)

    def __refreshGeneral(self):
        for name, (slider, valueLabel, low, high, step, getter, setter) in self.sliders.items():
            slider['value'] = getter()
            valueLabel['text'] = str(getter())

    def __resetGeneral(self):
        GameSettings.setFov(GameSettings.FOV_DEFAULT)
        GameSettings.setMusicVolume(GameSettings.VOLUME_DEFAULT)
        GameSettings.setSfxVolume(GameSettings.VOLUME_DEFAULT)
        KeyBindings.setCursorSpeed(KeyBindings.CURSOR_SPEED_DEFAULT)
        self.__refreshGeneral()

    # Keyboard

    def __loadKeyboard(self, frame):
        self.keyHelp = DirectLabel(parent=frame, relief=None, text=TTLocalizer.SettingsPageKeyHelp, text_scale=0.045,
                                   text_wordwrap=30, text_fg=TEXT_COLOR, pos=(0, 0, 0.47))
        actions = KeyBindings.KEY_ACTIONS
        half = (len(actions) + 1) // 2
        for i, (action, label, default) in enumerate(actions):
            col, row = divmod(i, half)
            x = -0.72 + col * 0.76
            z = 0.36 - row * 0.12
            DirectLabel(parent=frame, relief=None, text=KeyBindings.KEY_LABELS[action], text_align=TextNode.ALeft,
                        text_scale=0.045, text_wordwrap=8, text_fg=TEXT_COLOR, pos=(x, 0, z))
            button = DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.6, 1, 0.9),
                                  text='', text_scale=0.045, text_pos=(0, -0.015), pos=(x + 0.55, 0, z + 0.01),
                                  command=self.__startCapture, extraArgs=[action])
            self.keyButtons[action] = button
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1), text=TTLocalizer.SettingsPageReset,
                     text_scale=0.05, text_pos=(0, -0.02), pos=(0, 0, -0.5), command=self.__resetKeys)

    def __refreshKeys(self):
        for action, button in self.keyButtons.items():
            if action == self.capturing:
                button['text'] = TTLocalizer.SettingsPagePressKey
            else:
                button['text'] = KeyBindings.keyLabel(KeyBindings.getKey(action))

    def __startCapture(self, action):
        self.__stopCapture()
        self.capturing = action
        # Every key press reaches the game under another name while a key
        # is chosen, so pressing F8 or Space only picks it (the book stays
        # open, the toon does not jump).
        self.savedThrowers = []
        for thrower in base.buttonThrowers:
            node = thrower.node()
            self.savedThrowers.append((node, node.getPrefix(), node.getButtonDownEvent()))
            node.setPrefix(CAPTURE_PREFIX)
            node.setButtonDownEvent(CAPTURE_EVENT)
        self.accept(CAPTURE_EVENT, self.__keyCaptured)
        self.keyHelp['text'] = TTLocalizer.SettingsPageKeyWaiting % KeyBindings.KEY_LABELS[action]
        self.__refreshKeys()

    def __stopCapture(self):
        if self.capturing is None:
            return
        self.capturing = None
        self.ignore(CAPTURE_EVENT)
        for node, prefix, downEvent in getattr(self, 'savedThrowers', []):
            node.setPrefix(prefix)
            node.setButtonDownEvent(downEvent)
        self.savedThrowers = []
        self.keyHelp['text'] = TTLocalizer.SettingsPageKeyHelp
        self.__refreshKeys()

    def __keyCaptured(self, key):
        action = self.capturing
        if action is None:
            return
        if key.startswith('mouse') or key.startswith('wheel'):
            # Clicking (on the button again, or elsewhere) keeps waiting.
            return
        if key == 'escape':
            self.__stopCapture()
            return
        if key in KeyBindings.RESERVED:
            self.keyHelp['text'] = TTLocalizer.SettingsPageKeyReserved % KeyBindings.keyLabel(key)
            return
        # Left and right modifier keys are one key to the game.
        key = {'lalt': 'alt', 'ralt': 'alt'}.get(key, key)
        KeyBindings.setKey(action, key)
        self.__stopCapture()

    def __resetKeys(self):
        self.__stopCapture()
        KeyBindings.resetKeys()
        self.__refreshKeys()

    # Controller

    def __loadController(self, frame):
        DirectLabel(parent=frame, relief=None, text=TTLocalizer.SettingsPagePadHelp, text_scale=0.045,
                    text_wordwrap=30, text_fg=TEXT_COLOR, pos=(0, 0, 0.47))
        buttons = KeyBindings.PAD_BUTTONS
        half = (len(buttons) + 1) // 2
        for i, (button, label, default) in enumerate(buttons):
            col, row = divmod(i, half)
            x = -0.72 + col * 0.76
            z = 0.36 - row * 0.105
            DirectLabel(parent=frame, relief=None, text=label, text_align=TextNode.ALeft, text_scale=0.045,
                        text_fg=TEXT_COLOR, pos=(x, 0, z))
            widget = DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.95, 1, 0.85),
                                  text='', text_scale=0.036, text_pos=(0, -0.012), pos=(x + 0.46, 0, z + 0.012),
                                  command=self.__cyclePad, extraArgs=[button, 1])
            widget.bind(DGG.B3PRESS, lambda event, button=button: self.__cyclePad(button, -1))
            self.padButtons[button] = widget
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1), text=TTLocalizer.SettingsPageReset,
                     text_scale=0.05, text_pos=(0, -0.02), pos=(0, 0, -0.5), command=self.__resetPad)

    def __refreshPad(self):
        for button, widget in self.padButtons.items():
            widget['text'] = KeyBindings.PAD_LABELS.get(KeyBindings.getPad(button), '-')

    def __cyclePad(self, button, step):
        order = KeyBindings.PAD_ACTION_ORDER
        current = KeyBindings.getPad(button)
        index = order.index(current) if current in order else 0
        KeyBindings.setPad(button, order[(index + step) % len(order)])
        self.__refreshPad()

    def __resetPad(self):
        KeyBindings.resetPad()
        self.__refreshPad()

    # Page

    def setMode(self, mode):
        messenger.send('wakeup')
        self.__stopCapture()
        self.mode = mode
        for i, frame in enumerate(self.frames):
            if i == mode:
                frame.show()
            else:
                frame.hide()
        for i, tab in enumerate(self.tabs):
            tab['state'] = DGG.DISABLED if i == mode else DGG.NORMAL
        if mode == GENERAL:
            self.__refreshGeneral()
        elif mode == KEYBOARD:
            self.__refreshKeys()
        else:
            self.__refreshPad()

    def enter(self):
        self.setMode(self.mode)
        ShtikerPage.ShtikerPage.enter(self)

    def exit(self):
        self.__stopCapture()
        ShtikerPage.ShtikerPage.exit(self)

    def unload(self):
        self.__stopCapture()
        self.buttonGui.removeNode()
        for frame in self.frames:
            frame.destroy()
        del self.title
        ShtikerPage.ShtikerPage.unload(self)
