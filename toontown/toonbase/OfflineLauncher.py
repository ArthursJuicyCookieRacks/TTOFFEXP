"""The launcher screen the packaged game opens on.

Before anything of the game loads, the player sees the old Toontown Online
launcher: PLAY! starts the game (the bar under it fills as it loads),
DRIVERS picks a graphics driver on Android, and SETTINGS holds the game's
own options, such as the touch screen controls. It is part of the game, not
a program of its own.

The launcher draws in a display region of its own, above the game's, so it
covers the loading screens until the game is ready.
"""

import sys

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectWaitBar
from direct.showbase.DirectObject import DirectObject
from panda3d.core import Camera, CardMaker, ClockObject, ConfigVariableBool, ConfigVariableString, Filename, NodePath
from panda3d.core import ATSNone, OrthographicLens, PGTop, PNMImage, SamplerState, Texture, TextNode, loadPrcFileData
from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, TransparencyAttrib

from otp.local.ExecutionContext import getClientBuiltin
from otp.otpbase.Settings import Settings
from toontown.toonbase import ToontownGlobals

# The background picture is 750 by 500; everything is laid out on it.
IMAGE_WIDTH, IMAGE_HEIGHT = 750.0, 500.0
# How much the background picture goes on at each side of the launcher art,
# as a share of the art's width.
EXTRA_WIDTH = 500 / 2250.0
# The sky at the picture's edges, for the sides of a still wider screen.
SIDE_COLOR = (0.43, 0.67, 0.86, 1)
# The navy border around the art, and its shadow.
NAVY = (0.13, 0.2, 0.5, 1)
BORDER_WIDTH = 0.022
SHADOW_WIDTH = 0.09
SHADOW_ALPHA = 0.35

RED = (1, 0.18, 0.15, 1)
RED_ROLLOVER = (1, 0.38, 0.32, 1)
# Held down, a red button swaps its colors: yellow, with red writing.
PRESSED = (1, 1, 0.75, 1)
PRESSED_TEXT = (0.9, 0.1, 0.08, 1)
YELLOW = (1, 0.9, 0.1, 1)
TEXT_DARK = (0.16, 0.16, 0.32, 1)

BLURB = ('Toontown - The Offline Experience is a Fan Made project and not affiliated with any of the '
         'original creators of Toontown Online. This is a fully playable from start to finish offline '
         'version of Toontown with NPC toons to help you along the way, to ensure you can do EVERY '
         'activity in Toontown!')
CREDITS = ('Credits to RegDogg, DarthMDev & DankMickey of the TTR-Offline GitHub for providing the '
           'original base source code.')

_launcher = None


def place(px, py):
    """Where a point of the background picture is, in the launcher's units."""
    width = IMAGE_WIDTH / IMAGE_HEIGHT
    return (px / IMAGE_WIDTH - 0.5) * 2 * width, 0, 1 - py / IMAGE_HEIGHT * 2


def isAndroid():
    return sys.platform == 'android'


def touchControlsWanted(settings=None):
    settings = settings or Settings()
    return settings.getBool('controls', 'touch-controls', True)


def applyTouchSetting(settings=None):
    # The touch controls are for touch screens (the Android build turns them
    # on); the player can turn them off.
    on = isAndroid() and touchControlsWanted(settings)
    loadPrcFileData('OfflineLauncher touch controls', 'want-touch-controls %d' % on)


class OfflineLauncher(DirectObject):

    def __init__(self):
        self.settings = Settings()
        self.started = False
        self.closed = False
        self.panel = None
        applyTouchSetting(self.settings)

        # A layer of its own, drawn over everything else in the window.
        self.top = NodePath(PGTop('offlineLauncher'))
        self.top.node().setMouseWatcher(base.mouseWatcherNode)
        self.top.setDepthTest(False)
        self.top.setDepthWrite(False)
        lens = OrthographicLens()
        lens.setFilmSize(2, 2)
        lens.setNearFar(-1000, 1000)
        camera = Camera('offlineLauncherCamera', lens)
        self.camera = self.top.attachNewNode(camera)
        self.region = base.win.makeDisplayRegion()
        self.region.setSort(100)
        self.region.setClearColorActive(True)
        self.region.setClearColor(SIDE_COLOR)
        self.region.setClearDepthActive(True)
        self.region.setCamera(self.camera)

        self.canvas = self.top.attachNewNode('canvas')
        self.fit()
        self.accept('window-event', self.fit)

        self.loadArt()
        self.makeBackground()
        self.makePlay()
        self.makeLeftPanel()

    def loadArt(self):
        self.buttonModel = loader.loadModel('phase_3/models/gui/quit_button')
        self.dialogBox = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        self.minnieFont = ToontownGlobals.getMinnieFont()
        self.interfaceFont = ToontownGlobals.getInterfaceFont()

    def fit(self, window=None):
        # The picture fills the window's height, and is narrowed to fit a
        # window less wide than it.
        aspect = base.getAspectRatio()
        width = IMAGE_WIDTH / IMAGE_HEIGHT
        scale = min(1.0, aspect / width)
        self.canvas.setScale(scale / aspect, 1, scale)

    # --- Making the screen ---

    def makeBackground(self):
        card = CardMaker('offlineLauncherBackground')
        # The picture runs on past the art at the sides (EXTRA_WIDTH of the
        # art's own width at each), so a wide screen has no bars.
        width = IMAGE_WIDTH / IMAGE_HEIGHT * (1 + 2 * EXTRA_WIDTH)
        card.setFrame(-width, width, -1, 1)
        self.background = self.canvas.attachNewNode(card.generate())
        gameDir = ConfigVariableString('offline-game-dir', '').getValue()
        # Kept at its own size rather than squeezed to a power of two.
        texture = Texture('offlineLauncherBackground')
        texture.setAutoTextureScale(ATSNone)
        texture.read(Filename(Filename(gameDir), 'assets/launcher-background.jpg'))
        texture.setMinfilter(SamplerState.FTLinear)
        texture.setMagfilter(SamplerState.FTLinear)
        self.background.setTexture(texture)
        self.makeBorder()

    def makeBorder(self):
        # A navy border around the art, with a soft shadow falling outward
        # onto the picture's extended sides.
        width = IMAGE_WIDTH / IMAGE_HEIGHT
        border = self.canvas.attachNewNode('offlineLauncherBorder')
        border.setTransparency(TransparencyAttrib.MAlpha)
        shadow = (0, 0, 0.08, SHADOW_ALPHA)
        clear = (0, 0, 0.08, 0)
        for side in (-1, 1):
            edge = side * width
            # The shadow, fading out from the border.
            self.gradientCard(border, edge, edge + side * SHADOW_WIDTH, -1, 1, shadow, clear)
            # The border's sides.
            self.gradientCard(border, edge - side * BORDER_WIDTH / 2, edge + side * BORDER_WIDTH / 2, -1, 1,
                              NAVY, NAVY)
            # The top and bottom, kept on the screen.
            z = side * (1 - BORDER_WIDTH / 2)
            self.gradientCard(border, -width - BORDER_WIDTH / 2, width + BORDER_WIDTH / 2,
                              z - BORDER_WIDTH / 2, z + BORDER_WIDTH / 2, NAVY, NAVY)
            # A faint shadow just inside the top and bottom.
            inner = side * (1 - BORDER_WIDTH)
            self.gradientCard(border, -width, width, inner, inner - side * SHADOW_WIDTH / 2, shadow, clear,
                              vertical=True)

    def gradientCard(self, parent, x0, x1, z0, z1, color0, color1, vertical=False):
        # A rectangle shaded from color0 (at x0, or z0 if vertical) to color1.
        data = GeomVertexData('launcherCard', GeomVertexFormat.getV3c4(), Geom.UHStatic)
        vertices = GeomVertexWriter(data, 'vertex')
        colors = GeomVertexWriter(data, 'color')
        for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
            vertices.addData3(x, 0, z)
            near = (z == z0) if vertical else (x == x0)
            colors.addData4(*(color0 if near else color1))
        triangles = GeomTriangles(Geom.UHStatic)
        triangles.addVertices(0, 1, 2)
        triangles.addVertices(0, 2, 3)
        geom = Geom(data)
        geom.addPrimitive(triangles)
        node = GeomNode('launcherCard')
        node.addGeom(geom)
        card = parent.attachNewNode(node)
        card.setTwoSided(True)
        return card

    def buttonImages(self, colors=None):
        # The rounded button of the original game; tinted, for the red ones.
        up = self.buttonModel.find('**/QuitBtn_UP')
        if colors is None:
            images = [up, self.buttonModel.find('**/QuitBtn_DN'), self.buttonModel.find('**/QuitBtn_RLVR'), up.copyTo(NodePath())]
            images[3].setTexture(self.greyTexture(up), 1)
            return images
        images = []
        for color in colors:
            image = up.copyTo(NodePath())
            image.setColorScale(*color)
            images.append(image)
        return images

    def greyTexture(self, image):
        # The button greyed out, for when it can't be pressed.
        texture = image.findTexture('*')
        picture = PNMImage()
        texture.store(picture)
        picture.makeGrayscale()
        grey = Texture('greyButton')
        grey.load(picture)
        return grey

    def redButton(self, text, pos, command, scale=1.0, textScale=0.085, imageScale=(1.45, 1, 2.1)):
        return DirectButton(parent=self.canvas, relief=None, pos=pos, scale=scale,
                            image=self.buttonImages((RED, PRESSED, RED_ROLLOVER, (0.82, 0.22, 0.2, 1))),
                            image_scale=imageScale, text=text, text_font=self.minnieFont, text_scale=textScale,
                            text_fg=YELLOW, text_shadow=(0.3, 0.05, 0, 1), text_pos=(0, -0.028),
                            text1_fg=PRESSED_TEXT, text1_shadow=(0.45, 0.3, 0, 1),
                            pressEffect=0, command=command)

    def makePlay(self):
        # All inside the white box on the right.
        self.playButton = self.redButton('PLAY!', place(569, 176), self.play, textScale=0.075,
                                         imageScale=(1.4, 1, 1.75))
        x, y, z = place(569, 216)
        self.loadingBar = DirectWaitBar(parent=self.canvas, pos=(x, 0, z), relief=DGG.SUNKEN,
                                        frameSize=(-0.55, 0.55, -0.022, 0.022), borderWidth=(0.008, 0.008),
                                        frameColor=(0.96, 0.92, 0.9, 1), barColor=RED, range=100, value=0)
        self.loadingLabel = DirectLabel(parent=self.canvas, relief=None, pos=place(569, 231), text='',
                                        text_font=self.interfaceFont, text_scale=0.032, text_fg=TEXT_DARK)

    def makeLeftPanel(self):
        self.driversButton = self.redButton('DRIVERS', place(192, 100), self.showDrivers)
        # Greyed out, rather than a darker red, when it can't be pressed.
        images = self.buttonImages((RED, PRESSED, RED_ROLLOVER)) + [self.buttonImages()[3]]
        self.driversButton['image'] = images
        self.driversButton['text3_fg'] = (0.85, 0.85, 0.85, 1)
        self.driversButton['text3_shadow'] = (0.3, 0.3, 0.3, 1)
        if not isAndroid():
            # Custom graphics drivers are a thing of Android phones.
            self.driversButton['state'] = DGG.DISABLED
        # The text fills the panel between the two buttons.
        self.blurb = DirectLabel(parent=self.canvas, relief=None, pos=place(192, 150), text=BLURB,
                                 text_font=self.interfaceFont, text_scale=0.08, text_wordwrap=16.3,
                                 text_fg=TEXT_DARK, text_align=TextNode.ACenter)
        self.credits = DirectLabel(parent=self.canvas, relief=None, pos=place(192, 338), text=CREDITS,
                                   text_font=self.interfaceFont, text_scale=0.056, text_wordwrap=23,
                                   text_fg=TEXT_DARK, text_align=TextNode.ACenter)
        self.settingsButton = self.redButton('SETTINGS', place(192, 405), self.showSettings)

    # --- Panels ---

    def closePanel(self):
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None

    def openPanel(self, title, titleZ=0.38):
        self.closePanel()
        # A shade over the launcher, which also keeps its buttons from being
        # pressed while the panel is up.
        width = IMAGE_WIDTH / IMAGE_HEIGHT
        self.panel = DirectFrame(parent=self.canvas, relief=DGG.FLAT, frameColor=(0, 0, 0, 0.4),
                                 frameSize=(-width, width, -1, 1), state=DGG.NORMAL)
        self.panel.setBin('gui-popup', 50)
        DirectFrame(parent=self.panel, relief=None, image=self.dialogBox, image_scale=(1.6, 1, 1.2),
                    image_color=(1, 1, 0.92, 1), pos=(0, 0, 0.02))
        DirectLabel(parent=self.panel, relief=None, pos=(0, 0, titleZ), text=title, text_font=self.minnieFont,
                    text_scale=0.1, text_fg=RED, text_shadow=(0.3, 0.05, 0, 1))
        close = self.redButton('CLOSE', (0, 0, -0.4), self.closePanel, textScale=0.075)
        close.reparentTo(self.panel)
        return self.panel

    def showSettings(self):
        panel = self.openPanel('SETTINGS')
        self.touchButton = self.redButton(self.touchText(), (0, 0, 0.14), self.toggleTouch, textScale=0.055,
                                          imageScale=(2.9, 1, 2.1))
        self.touchButton.reparentTo(panel)
        DirectLabel(parent=panel, relief=None, pos=(0, 0, -0.04), text_font=self.interfaceFont,
                    text_scale=0.045, text_fg=TEXT_DARK, text_wordwrap=26,
                    text='The joystick and jump button on the screen. They go away by themselves while '
                         'a controller is in use.')

    def touchText(self):
        return 'TOUCH CONTROLS: %s' % ('ON' if touchControlsWanted(self.settings) else 'OFF')

    def toggleTouch(self):
        self.settings.updateSetting('controls', 'touch-controls', not touchControlsWanted(self.settings))
        applyTouchSetting(self.settings)
        self.touchButton['text'] = self.touchText()

    def showDrivers(self):
        from toontown.toonbase import TurnipDrivers
        TurnipDrivers.DriversPanel(self, self.openPanel('DRIVERS', titleZ=0.45))

    # --- Starting the game ---

    def play(self):
        if self.started:
            return
        self.started = True
        for button in (self.playButton, self.settingsButton, self.driversButton):
            button['state'] = DGG.DISABLED
        self.setProgress(2, 'Starting Toontown...')

    def setProgress(self, value, label=None):
        value = max(self.loadingBar['value'], min(value, 100))
        self.loadingBar['value'] = value
        if label is not None:
            self.loadingLabel['text'] = label
        # Loading holds up the game's own frames; draw the bar now and then.
        # (The AI reports from inside its own context, without the game's
        # builtins.)
        now = ClockObject.getGlobalClock().getRealTime()
        if now - getattr(self, 'lastFrame', 0) > 0.1:
            self.lastFrame = now
            getClientBuiltin('base').graphicsEngine.renderFrame()

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        self.ignoreAll()
        self.closePanel()
        for item in (self.playButton, self.loadingBar, self.loadingLabel, self.driversButton, self.blurb,
                     self.credits, self.settingsButton):
            item.destroy()
        base.win.removeDisplayRegion(self.region)
        self.top.removeNode()


# --- What ToontownStart calls ---

def wanted():
    return ConfigVariableBool('want-offline-launcher', False).getValue()


def run():
    """Shows the launcher and waits until the player presses PLAY!."""
    global _launcher
    _launcher = OfflineLauncher()
    while not _launcher.started:
        taskMgr.step()


def progress(value, label=None):
    if _launcher is not None and not _launcher.closed:
        _launcher.setProgress(value, label)


# The AI building the town reports each zone it builds; the bar goes from
# START to END over about this many.
TOWN_STEPS = 87
TOWN_START, TOWN_END = 30, 95
_townSteps = 0


def townStep():
    global _townSteps
    _townSteps += 1
    progress(TOWN_START + (TOWN_END - TOWN_START) * min(_townSteps / float(TOWN_STEPS), 1.0), 'Building Toontown...')


def finish():
    """The game is ready: the bar fills and the launcher goes."""
    global _launcher
    if _launcher is None:
        return
    progress(100, 'Ready!')
    launcher, _launcher = _launcher, None
    getClientBuiltin('taskMgr').doMethodLater(0.4, lambda task: launcher.destroy(), 'offlineLauncherFinish')
