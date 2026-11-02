"""The Shticker Book's Settings page (after Events).

General: field of view, music and sound effects volume, and a Double XP button whose menu turns double experience on or off for gags,
gardening and doodle training, each on its own.
Keyboard: what key does each action (click one, then press the new key).
Controller: what each controller button does, and how fast the controller
moves the on-screen pointer (1 slowest .. 10 fastest).
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


def fitText(widget, scale, maxWidth):
    # Shrinks a button's words to fit inside it ("Camera Down (Page Down)"
    # ran over the edges).
    widget['text_scale'] = scale
    width = widget.component('text0').textNode.getWidth() * scale
    if width > maxWidth:
        widget['text_scale'] = (scale * maxWidth / width, scale)


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
        # (mode, word, tab picture, picture offset, x, middle of the picture)
        for mode, text, surface, imagePos, x, center in (
                (GENERAL, TTLocalizer.SettingsPageGeneralTab, 'polySurface1', (0.55, 1, -0.91), -0.55, 0.131),
                (KEYBOARD, TTLocalizer.SettingsPageKeyboardTab, 'polySurface2', (0.12, 1, -0.91), -0.13, 0.13),
                (CONTROLLER, TTLocalizer.SettingsPageControllerTab, 'polySurface3', (-0.28, 1, -0.91), 0.28, 0.148)):
            tab = DirectButton(parent=self, relief=None, text=text, text_scale=0.06, text_align=TextNode.ALeft,
                               text_pos=(-0.01, 0.0, 0.0), image=gui.find('**/tabs/' + surface), image_pos=imagePos,
                               image_hpr=(0, 0, -90), image_scale=(0.033, 0.033, 0.035), image_color=normalColor,
                               image1_color=clickColor, image2_color=rolloverColor, image3_color=disabledColor,
                               text_fg=TEXT_COLOR, command=self.setMode, extraArgs=[mode], pos=(x, 0, 0.775))
            # The word in the middle of its tab (the tab pictures sit at
            # different offsets from their buttons).
            tab['text_align'] = TextNode.ACenter
            tab['text_pos'] = (center, 0.0)
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
        )
        z = 0.45
        for row in rows:
            self.__addSlider(frame, z, *row)
            z -= 0.22
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1), text=TTLocalizer.SettingsPageReset,
                     text_scale=0.05, text_pos=(0, -0.02), pos=(-0.3, 0, -0.5), command=self.__resetGeneral)
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1),
                     image_color=(1, 0.85, 0.3, 1), text=TTLocalizer.SettingsPageDoubleXp, text_scale=0.05,
                     text_pos=(0, -0.02), pos=(0.3, 0, -0.5), command=self.__openDoubleXp)

    def __addSlider(self, frame, z, name, label, low, high, step, getter, setter):
        # The name on its own line, the slider and its value under it.
        DirectLabel(parent=frame, relief=None, text=label, text_align=TextNode.ACenter, text_scale=0.055,
                    text_fg=TEXT_COLOR, pos=(-0.06, 0, z))
        value = DirectLabel(parent=frame, relief=None, text='', text_align=TextNode.ACenter, text_scale=0.055,
                            text_fg=TEXT_COLOR, pos=(0.62, 0, z - 0.085))
        slider = DirectSlider(parent=frame, range=(low, high), value=getter(), pageSize=step, scrollSize=step,
                              pos=(-0.06, 0, z - 0.07), scale=(0.6, 1, 0.4), frameColor=(0.55, 0.45, 0.3, 1),
                              thumb_relief=DGG.FLAT, thumb_frameColor=(1, 0.85, 0.2, 1),
                              thumb_frameSize=(-0.05, 0.05, -0.1, 0.1))
        slider['command'] = self.__sliderMoved
        slider['extraArgs'] = [name]
        self.sliders[name] = (slider, value, low, high, step, getter, setter)

    def __sliderMoved(self, name):
        slider, valueLabel, low, high, step, getter, setter = self.sliders[name]
        value = int(round(slider['value'] / float(step))) * step
        value = max(low, min(high, value))
        valueLabel['text'] = str(value)
        if value != getter():
            setter(value)

    def __refreshGeneral(self):
        for name, (slider, valueLabel, low, high, step, getter, setter) in self.sliders.items():
            if name == 'cursor':
                continue
            slider['value'] = getter()
            valueLabel['text'] = str(getter())

    def __resetGeneral(self):
        GameSettings.setFov(GameSettings.FOV_DEFAULT)
        GameSettings.setMusicVolume(GameSettings.VOLUME_DEFAULT)
        GameSettings.setSfxVolume(GameSettings.VOLUME_DEFAULT)
        self.__refreshGeneral()

    # Double XP

    def __openDoubleXp(self):
        # A menu with an on/off switch for each kind of experience.
        messenger.send('wakeup')
        self.__closeDoubleXp()
        rows = ((GameSettings.DOUBLE_XP_GAGS, TTLocalizer.SettingsPageDoubleXpGags),
                (GameSettings.DOUBLE_XP_GARDENING, TTLocalizer.SettingsPageDoubleXpGardening),
                (GameSettings.DOUBLE_XP_DOODLES, TTLocalizer.SettingsPageDoubleXpDoodles))
        top = 0.42
        popup = DirectFrame(parent=self, relief=DGG.RIDGE, borderWidth=(0.015, 0.015),
                            frameColor=(1, 0.97, 0.85, 1), frameSize=(-0.66, 0.66, -top, top),
                            pos=(0, 0, 0.02), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        popup.setBin('gui-popup', 0)
        DirectLabel(parent=popup, relief=None, text=TTLocalizer.SettingsPageDoubleXp, text_scale=0.075,
                    text_fg=TEXT_COLOR, pos=(0, 0, top - 0.1))
        DirectLabel(parent=popup, relief=None, text=TTLocalizer.SettingsPageDoubleXpHelp, text_scale=0.04,
                    text_wordwrap=28, text_fg=TEXT_COLOR, pos=(0, 0, top - 0.17))
        self.doubleXpButtons = {}
        z = top - 0.33
        for kind, label in rows:
            DirectLabel(parent=popup, relief=None, text=label, text_align=TextNode.ALeft, text_scale=0.055,
                        text_fg=TEXT_COLOR, pos=(-0.56, 0, z - 0.015))
            toggle = DirectButton(parent=popup, relief=None, image=self.btnImage, image_scale=(0.6, 1, 0.9),
                                  text='', text_scale=0.05, text_pos=(0, -0.017), pos=(0.38, 0, z),
                                  command=self.__toggleDoubleXp, extraArgs=[kind])
            self.doubleXpButtons[kind] = toggle
            z -= 0.14
        DirectButton(parent=popup, relief=None, image=self.btnImage, image_scale=(0.7, 1, 0.9),
                     text=TTLocalizer.SettingsPageClose, text_scale=0.045, text_pos=(0, -0.015),
                     pos=(0, 0, -top + 0.08), command=self.__closeDoubleXp)
        self.doubleXpMenu = popup
        self.frames[GENERAL].hide()
        self.__refreshDoubleXp()

    def __refreshDoubleXp(self):
        for kind, toggle in self.doubleXpButtons.items():
            on = GameSettings.getDoubleXp(kind)
            toggle['text'] = TTLocalizer.SettingsPageOn if on else TTLocalizer.SettingsPageOff
            toggle['image_color'] = (0.55, 1, 0.55, 1) if on else (1, 0.6, 0.6, 1)

    def __toggleDoubleXp(self, kind):
        GameSettings.setDoubleXp(kind, not GameSettings.getDoubleXp(kind))
        self.__refreshDoubleXp()

    def __closeDoubleXp(self):
        popup = getattr(self, 'doubleXpMenu', None)
        if popup is not None:
            popup.destroy()
            if self.mode == GENERAL:
                self.frames[GENERAL].show()
        self.doubleXpMenu = None
        self.doubleXpButtons = {}

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
            z = 0.35 - row * 0.085
            DirectLabel(parent=frame, relief=None, text=label, text_align=TextNode.ALeft, text_scale=0.045,
                        text_fg=TEXT_COLOR, pos=(x, 0, z))
            widget = DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.95, 1, 0.85),
                                  text='', text_scale=0.036, text_pos=(0, -0.012), pos=(x + 0.46, 0, z + 0.012),
                                  command=self.__openPadList, extraArgs=[button])
            self.padButtons[button] = widget
        # How fast the right stick moves the on-screen pointer.
        self.__addSlider(frame, -0.33, 'cursor', TTLocalizer.SettingsPageCursor, 1, 10, 1,
                         KeyBindings.getCursorSpeed, KeyBindings.setCursorSpeed)
        DirectButton(parent=frame, relief=None, image=self.btnImage, image_scale=(0.9, 1, 1), text=TTLocalizer.SettingsPageReset,
                     text_scale=0.05, text_pos=(0, -0.02), pos=(0, 0, -0.54), command=self.__resetPad)

    def __refreshPad(self):
        slider, valueLabel = self.sliders['cursor'][:2]
        slider['value'] = KeyBindings.getCursorSpeed()
        valueLabel['text'] = str(KeyBindings.getCursorSpeed())
        for button, widget in self.padButtons.items():
            widget['text'] = KeyBindings.PAD_LABELS.get(KeyBindings.getPad(button), '-')
            fitText(widget, 0.036, 0.36)

    def __openPadList(self, button):
        # A popup listing every action; picking one gives it to the button.
        self.__closePadList()
        order = KeyBindings.PAD_ACTION_ORDER
        current = KeyBindings.getPad(button)
        columns = 3
        rows = (len(order) + columns - 1) // columns
        height = 0.32 + rows * 0.1
        top = height / 2.0
        popup = DirectFrame(parent=self, relief=DGG.RIDGE, borderWidth=(0.015, 0.015),
                            frameColor=(1, 0.97, 0.85, 1), frameSize=(-0.78, 0.78, -top, top),
                            pos=(0, 0, 0.02), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        popup.setBin('gui-popup', 0)
        DirectLabel(parent=popup, relief=None, text=TTLocalizer.SettingsPagePadChoose % KeyBindings.PAD_BUTTON_LABELS[button],
                    text_scale=0.055, text_fg=TEXT_COLOR, pos=(0, 0, top - 0.09))
        for i, action in enumerate(order):
            row, col = divmod(i, columns)
            chosen = action == current
            choice = DirectButton(parent=popup, relief=None, image=self.btnImage, image_scale=(0.82, 1, 0.85),
                         image_color=(0.55, 1, 0.55, 1) if chosen else (1, 1, 1, 1),
                         text=KeyBindings.PAD_LABELS[action], text_scale=0.034, text_pos=(0, -0.012),
                         pos=(-0.5 + col * 0.5, 0, top - 0.2 - row * 0.1),
                         command=self.__pickPad, extraArgs=[button, action])
            fitText(choice, 0.034, 0.32)
        DirectButton(parent=popup, relief=None, image=self.btnImage, image_scale=(0.7, 1, 0.9),
                     text=TTLocalizer.SettingsPageCancel, text_scale=0.045, text_pos=(0, -0.015),
                     pos=(0, 0, -top + 0.08), command=self.__closePadList)
        self.padList = popup
        # The list covers the buttons, so they can't be clicked through it.
        self.frames[CONTROLLER].hide()

    def __pickPad(self, button, action):
        KeyBindings.setPad(button, action)
        self.__closePadList()
        self.__refreshPad()

    def __closePadList(self):
        popup = getattr(self, 'padList', None)
        if popup is not None:
            popup.destroy()
            if self.mode == CONTROLLER:
                self.frames[CONTROLLER].show()
        self.padList = None

    def __resetPad(self):
        self.__closePadList()
        KeyBindings.resetPad()
        KeyBindings.setCursorSpeed(KeyBindings.CURSOR_SPEED_DEFAULT)
        self.__refreshPad()

    # Page

    def setMode(self, mode):
        messenger.send('wakeup')
        self.__stopCapture()
        self.__closePadList()
        self.__closeDoubleXp()
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
        self.__closePadList()
        self.__closeDoubleXp()
        ShtikerPage.ShtikerPage.exit(self)

    def unload(self):
        self.__stopCapture()
        self.buttonGui.removeNode()
        for frame in self.frames:
            frame.destroy()
        del self.title
        ShtikerPage.ShtikerPage.unload(self)
