"""Draws the 3D world at a share of the screen's resolution (MOBILE settings).

Phones have screens of 2400x1080 pixels or more, and filling every one of
them each frame is much of what keeps the frame rate down. At 75% the world
is drawn into a smaller picture, which is then stretched over the screen; the
menus, chat and nametags on top are still drawn at full resolution.
"""

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import (CardMaker, FrameBufferProperties, GraphicsOutput, GraphicsPipe, SamplerState, Texture,
                          TextureStage, WindowProperties)

notify = DirectNotifyGlobal.directNotify.newCategory('RenderScale')

SCALES = (100, 75, 50)

_current = None


class RenderScale:

    def __init__(self, percent):
        self.share = percent / 100.0
        win = base.win
        self.tex = Texture('renderScale')
        self.tex.setMinfilter(SamplerState.FTLinear)
        self.tex.setMagfilter(SamplerState.FTLinear)
        self.tex.setWrapU(SamplerState.WMClamp)
        self.tex.setWrapV(SamplerState.WMClamp)
        fbp = FrameBufferProperties()
        fbp.setRgbColor(True)
        fbp.setRgbaBits(8, 8, 8, 0)
        fbp.setDepthBits(24)
        self.size = self.wantedSize()
        flags = GraphicsPipe.BFRefuseWindow | GraphicsPipe.BFResizeable
        self.buffer = base.graphicsEngine.makeOutput(win.getPipe(), 'renderScale', -2, fbp,
                                                     WindowProperties.size(*self.size), flags, win.getGsg(), win)
        if self.buffer is None:
            notify.warning('no offscreen buffer; drawing at full resolution')
            return
        self.buffer.addRenderTexture(self.tex, GraphicsOutput.RTMBindOrCopy, GraphicsOutput.RTPColor)
        self.buffer.setClearColorActive(True)
        self.buffer.setClearDepthActive(True)
        # The 3D camera draws into the picture instead of onto the screen.
        self.windowRegion = base.camNode.getDisplayRegion(0)
        self.windowRegion.setActive(False)
        self.region = self.buffer.makeDisplayRegion()
        self.region.setCamera(base.cam)
        # The picture, stretched over the screen behind everything 2D.
        cm = CardMaker('renderScale')
        cm.setFrameFullscreenQuad()
        self.card = render2d.attachNewNode(cm.generate())
        self.card.setTexture(self.tex)
        self.card.setBin('background', -100)
        self.card.setDepthTest(False)
        self.card.setDepthWrite(False)
        taskMgr.add(self.update, 'renderScale', sort=48)

    def wantedSize(self):
        return max(1, int(base.win.getXSize() * self.share)), max(1, int(base.win.getYSize() * self.share))

    def update(self, task):
        # The sky colour each place sets on the window.
        self.buffer.setClearColor(base.win.getClearColor())
        size = self.wantedSize()
        if size != self.size:
            self.size = size
            self.buffer.setSize(*size)
        # A picture padded up to a power of two only fills part of itself.
        x, y = self.tex.getXSize(), self.tex.getYSize()
        if x and y:
            self.card.setTexScale(TextureStage.getDefault(), (x - self.tex.getPadXSize()) / float(x),
                                  (y - self.tex.getPadYSize()) / float(y))
        return task.cont


def apply(percent):
    global _current
    if percent >= 100 or _current is not None:
        return
    _current = RenderScale(percent)
