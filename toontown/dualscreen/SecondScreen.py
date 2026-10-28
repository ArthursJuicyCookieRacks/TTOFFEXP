"""The second screen of a dual-screen handheld (such as the AYN Thor).

On Android the game asks for a second display (a Presentation, see the
second-screen Panda patch). When there is one, the bottom screen's picture
is drawn by Panda in an offscreen buffer with the game's own art, a few
times a second, and handed to Android to show there; the touches on it come
back here and press the bottom screen's buttons (BottomScreenPages).

Off Android, `second-screen-size W H` in the config draws it the same way
without showing it anywhere, for testing (see saveFrame and touch).
"""

import sys

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from panda3d.core import (Camera, ConfigVariableString, NodePath, OrthographicLens, PGTop, Point3,
                          Texture)

notify = DirectNotifyGlobal.directNotify.newCategory('SecondScreen')

# How often the bottom screen is drawn and handed over, and how often a
# missing second display is looked for again.
FRAME_TIME = 1.0 / 12
LOOK_TIME = 2.0
# Drawn at no more than this many pixels across (and stretched to fit):
# reading the picture back is the costly part.
MAX_WIDTH = 720
# The launcher's blue.
BLUE = (0.43, 0.67, 0.86, 1)

_instance = None


def start():
    global _instance
    if _instance is None:
        _instance = SecondScreen()
    return _instance


def get():
    return _instance


def isAndroid():
    return sys.platform == 'android'


class SecondScreen(DirectObject):

    def __init__(self):
        DirectObject.__init__(self)
        self.size = None
        self.buffer = None
        self.pages = None
        self.touches = []
        self.pressed = None
        self.armed = False
        self.lastFrame = 0
        self.lastPicture = None
        self.nextLook = 0
        taskMgr.add(self.tick, 'secondScreen', sort=48)

    # --- Finding the second display ---

    def detect(self):
        simulated = ConfigVariableString('second-screen-size', '').getValue().split()
        if len(simulated) == 2:
            return int(simulated[0]), int(simulated[1])
        if isAndroid():
            try:
                import android_support
                return android_support.second_screen()
            except (ImportError, AttributeError):
                return None
        return None

    def open(self, size):
        width, height = size
        renderWidth = min(width, MAX_WIDTH)
        renderHeight = max(1, int(round(height * renderWidth / float(width))))
        self.size = (renderWidth, renderHeight)
        self.texture = Texture('secondScreen')
        self.buffer = base.win.makeTextureBuffer('secondScreen', renderWidth, renderHeight, self.texture, True)
        if self.buffer is None:
            notify.warning('no offscreen buffer for the second screen')
            self.size = None
            return
        self.buffer.setClearColor(BLUE)
        self.buffer.setSort(-50)
        self.buffer.setOneShot(True)
        self.root = NodePath(PGTop('secondScreenTop'))
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.setMaterialOff(1)
        self.root.setTwoSided(1)
        lens = OrthographicLens()
        lens.setFilmSize(2, 2)
        lens.setNearFar(-1000, 1000)
        camera = self.root.attachNewNode(Camera('secondScreenCam', lens))
        region = self.buffer.makeDisplayRegion()
        region.setCamera(camera)
        self.aspectRatio = renderWidth / float(renderHeight)
        self.aspect = self.root.attachNewNode('secondScreenAspect')
        self.aspect.setScale(1.0 / self.aspectRatio, 1, 1)
        notify.info('second screen %dx%d, drawn at %dx%d' % (width, height, renderWidth, renderHeight))
        from toontown.dualscreen import BottomScreenPages
        self.pages = BottomScreenPages.BottomScreen(self, self.aspect, self.aspectRatio)

    def close(self):
        if self.pages is not None:
            self.pages.destroy()
            self.pages = None
        if self.buffer is not None:
            base.graphicsEngine.removeWindow(self.buffer)
            self.buffer = None
            self.root.removeNode()
        self.size = None
        self.lastPicture = None

    # --- Every frame ---

    def tick(self, task):
        now = globalClock.getRealTime()
        if now >= self.nextLook:
            self.nextLook = now + LOOK_TIME
            size = self.detect()
            if self.buffer is None and size:
                self.open(size)
            elif self.buffer is not None and not size:
                self.close()
        if self.buffer is None:
            return task.cont
        self.readTouches()
        try:
            self.pages.update()
        except Exception:
            notify.warning('bottom screen update failed')
            import traceback
            traceback.print_exc()
        if self.armed:
            self.armed = False
            self.handOver()
        if now - self.lastFrame >= FRAME_TIME:
            self.lastFrame = now
            self.buffer.setOneShot(True)
            self.armed = True
        return task.cont

    def handOver(self):
        if not isAndroid() or not self.texture.hasRamImage():
            return
        picture = self.texture.getRamImageAs('RGBA').getData()
        key = hash(picture)
        if key == self.lastPicture:
            return
        self.lastPicture = key
        try:
            import android_support
            android_support.second_screen_frame(picture, self.size[0], self.size[1])
        except (ImportError, AttributeError):
            pass

    # --- Touches ---

    def readTouches(self):
        if isAndroid():
            try:
                import android_support
                while True:
                    touch = android_support.second_screen_touch()
                    if touch is None:
                        break
                    self.touches.append(touch)
            except (ImportError, AttributeError):
                pass
        touches, self.touches = self.touches, []
        for kind, x, y in touches:
            self.handleTouch(kind, x, y)

    def touch(self, kind, x, y):
        """A touch, x and y from 0 to 1 from the top left (for tests too)."""
        self.touches.append((kind, x, y))

    def toAspect(self, x, y):
        return Point3((x * 2 - 1) * self.aspectRatio, 0, 1 - y * 2)

    def handleTouch(self, kind, x, y):
        point = self.toAspect(x, y)
        if kind == 'down':
            self.press(self.pages.tapAt(point))
        elif kind == 'move':
            if self.pressed is not None and self.pages.tapAt(point) is not self.pressed:
                self.press(None)
        elif kind == 'up':
            tap = self.pressed
            self.press(None)
            if tap is not None and self.pages.tapAt(point) is tap:
                self.pages.fire(tap)
        else:
            self.press(None)

    def press(self, tap):
        if self.pressed is not None and not self.pressed.node.isEmpty():
            self.pressed.node.clearColorScale()
            self.pressed.node.setScale(self.pressed.scale)
        self.pressed = tap
        if tap is not None:
            tap.node.setColorScale(0.85, 0.85, 0.85, 1)
            tap.node.setScale(tap.scale * 0.94)

    def saveFrame(self, path):
        """The bottom screen's last picture, as an image file (for tests)."""
        from panda3d.core import Filename
        if self.buffer is not None and self.texture.hasRamImage():
            self.texture.write(Filename.fromOsSpecific(path))
            return True
        return False
