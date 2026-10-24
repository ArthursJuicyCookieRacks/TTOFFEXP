"""Controller support.

A game controller plays the game through the keys and the mouse, the way the
game is played on a computer: each button presses a key, the left stick
walks, and the right stick moves the pointer, which the triggers click.

    A        Control             Start    Escape
    B        Delete              Select   Shift + Escape
    X        Alt                 LB       Shift
    Y        End                 RB       Tab
    D-pad    Page Up (up), End (right), Home (left), Page Down (down)
    LT, RT   Left click          Left stick   Walk (the arrow keys)
    L3       Run (press once)    Right stick  The pointer
    R3       F2

The controller takes over as soon as it is used, and on a touch screen the
on-screen controls go away while it is; touching the screen brings them back.
"""

import sys

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from panda3d.core import ButtonRegistry, Camera, InputDevice, MouseButton, NodePath, OrthographicLens, TransparencyAttrib

# What each controller button presses.
BUTTON_KEYS = {
    'face_a': ('control',),
    'face_b': ('delete',),
    'face_x': ('alt',),
    'face_y': ('end',),
    'start': ('escape',),
    'back': ('shift', 'escape'),
    'lshoulder': ('shift',),
    'rshoulder': ('tab',),
    'rstick': ('f2',),
    'dpad_up': ('page_up',),
    'dpad_right': ('end',),
    'dpad_left': ('home',),
    'dpad_down': ('page_down',),
}
CLICK_BUTTONS = ('ltrigger', 'rtrigger')
RUN_BUTTON = 'lstick'

# The left stick: how far it must go before it walks, and how wide each of
# the four directions is (so the diagonals press two arrows).
STICK_DEAD_ZONE = 0.35
DIRECTION_KEYS = {'up': 'arrow_up', 'down': 'arrow_down', 'left': 'arrow_left', 'right': 'arrow_right'}
# The right stick: the pointer's top speed, in window heights a second.
POINTER_SPEED = 1.3
POINTER_DEAD_ZONE = 0.15
# How far an analog trigger must go to click.
TRIGGER_PRESS = 0.5
# How long after the controller was last used a touch on the screen counts
# as going back to touch.
TOUCH_AFTER = 2.0


def isActive():
    gamepad = getattr(base, 'gamepad', None)
    return gamepad is not None and gamepad.active


class Gamepad(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('Gamepad')

    def __init__(self):
        self.devices = []
        self.active = False
        self.lastUsed = 0
        self.pressed = set()
        self.directions = set()
        self.clicking = False
        self.running = False
        self.pointer = None
        self.cursor = None
        manager = base.devices
        for device in manager.getDevices(InputDevice.DeviceClass.gamepad):
            self.connect(device)
        self.accept('connect-device', self.connect)
        self.accept('disconnect-device', self.disconnect)
        # A touch (or a click) after the controller has gone quiet hands the
        # game back to the screen.
        self.accept('mouse1', self.__touched)
        taskMgr.add(self.__poll, 'gamepadPoll', sort=-45)

    def destroy(self):
        self.ignoreAll()
        taskMgr.remove('gamepadPoll')
        self.__releaseAll()
        if self.cursor is not None:
            base.win.removeDisplayRegion(self.cursorRegion)
            self.cursor.getParent().removeNode()

    def connect(self, device):
        if device.getDeviceClass() != InputDevice.DeviceClass.gamepad or device in self.devices:
            return
        self.notify.info('controller connected: %s' % device.getName())
        self.devices.append(device)

    def disconnect(self, device):
        if device in self.devices:
            self.notify.info('controller disconnected: %s' % device.getName())
            self.devices.remove(device)
            if not self.devices:
                self.__releaseAll()

    # --- Reading the controller ---

    def __poll(self, task):
        if not self.devices or base.win is None:
            return task.cont
        buttons = set()
        axes = {}
        for device in self.devices:
            device.poll()
            for i in range(device.getNumButtons()):
                if device.isButtonPressed(i):
                    buttons.add(device.getButtonMap(i).getName())
            for axis in ('left_x', 'left_y', 'right_x', 'right_y', 'left_trigger', 'right_trigger'):
                state = device.findAxis(getattr(InputDevice.Axis, axis))
                if state is not None and abs(state.value) > abs(axes.get(axis, 0)):
                    axes[axis] = state.value
        if axes.get('left_trigger', 0) > TRIGGER_PRESS:
            buttons.add('ltrigger')
        if axes.get('right_trigger', 0) > TRIGGER_PRESS:
            buttons.add('rtrigger')

        used = buttons or any(abs(axes.get(a, 0)) > STICK_DEAD_ZONE for a in ('left_x', 'left_y', 'right_x', 'right_y'))
        if used:
            self.lastUsed = globalClock.getFrameTime()
            if not self.active:
                self.__takeOver()

        self.__buttons(buttons)
        self.__walk(axes.get('left_x', 0), axes.get('left_y', 0))
        self.__point(axes.get('right_x', 0), axes.get('right_y', 0), globalClock.getDt())
        return task.cont

    def __buttons(self, buttons):
        for name in buttons - self.pressed:
            if name in BUTTON_KEYS:
                for key in BUTTON_KEYS[name]:
                    self.__key(key, True)
            elif name in CLICK_BUTTONS:
                self.__click(True)
            elif name == RUN_BUTTON:
                self.running = not self.running
                messenger.send('running-on' if self.running else 'running-off')
        for name in self.pressed - buttons:
            if name in BUTTON_KEYS:
                for key in reversed(BUTTON_KEYS[name]):
                    self.__key(key, False)
            elif name in CLICK_BUTTONS:
                self.__click(bool((buttons & set(CLICK_BUTTONS))))
        self.pressed = buttons

    def __walk(self, x, y):
        wanted = set()
        if max(abs(x), abs(y)) > STICK_DEAD_ZONE:
            # Diagonals press two arrows; a nearly straight push presses one.
            if y > STICK_DEAD_ZONE and y > abs(x) * 0.4:
                wanted.add('up')
            if y < -STICK_DEAD_ZONE and -y > abs(x) * 0.4:
                wanted.add('down')
            if x < -STICK_DEAD_ZONE and -x > abs(y) * 0.4:
                wanted.add('left')
            if x > STICK_DEAD_ZONE and x > abs(y) * 0.4:
                wanted.add('right')
        for direction in self.directions - wanted:
            self.__key(DIRECTION_KEYS[direction], False)
        for direction in wanted - self.directions:
            self.__key(DIRECTION_KEYS[direction], True)
        self.directions = wanted

    def __point(self, x, y, dt):
        if max(abs(x), abs(y)) < POINTER_DEAD_ZONE:
            return
        width, height = base.win.getXSize(), base.win.getYSize()
        if self.pointer is None:
            mouse = base.win.getPointer(0)
            self.pointer = [mouse.getX(), mouse.getY()] if mouse.getInWindow() else [width / 2.0, height / 2.0]
        # Slow near the middle of the stick, for aiming at small buttons.
        speed = POINTER_SPEED * height * dt
        self.pointer[0] = min(max(self.pointer[0] + x * abs(x) * speed, 0), width - 1)
        self.pointer[1] = min(max(self.pointer[1] - y * abs(y) * speed, 0), height - 1)
        px, py = int(self.pointer[0]), int(self.pointer[1])
        if not base.win.movePointer(0, px, py):
            # A window that can't warp a real pointer (a phone's) is told
            # where the pointer is.
            base.win.getInputDevice(0).setPointerInWindow(px, py)
        self.__showCursor(px, py)

    # --- Pressing keys ---

    def __key(self, name, down):
        button = ButtonRegistry.ptr().findButton(name)
        device = base.win.getInputDevice(0)
        if down:
            device.buttonDown(button)
        else:
            device.buttonUp(button)

    def __click(self, down):
        if down == self.clicking:
            return
        self.clicking = down
        device = base.win.getInputDevice(0)
        if down:
            device.buttonDown(MouseButton.one())
        else:
            device.buttonUp(MouseButton.one())

    def __releaseAll(self):
        self.__buttons(set())
        self.__walk(0, 0)

    # --- Touch controls and the pointer ---

    def __takeOver(self):
        self.active = True
        self.notify.info('playing with the controller')
        touch = getattr(base, 'touchControls', None)
        if touch is not None:
            touch.hideForGamepad()

    def __touched(self):
        if not self.active or self.clicking:
            return
        if globalClock.getFrameTime() - self.lastUsed < TOUCH_AFTER:
            return
        self.active = False
        self.notify.info('back to the touch screen')
        if self.cursor is not None:
            self.cursor.hide()
        touch = getattr(base, 'touchControls', None)
        if touch is not None:
            touch.showAfterGamepad()

    def __showCursor(self, px, py):
        if sys.platform != 'android':
            # A computer shows its own pointer.
            return
        if self.cursor is None:
            self.cursor = self.__makeCursor()
        self.cursor.show()
        width, height = base.win.getXSize(), base.win.getYSize()
        self.cursor.setPos(px / float(width) * 2 - 1, 0, 1 - py / float(height) * 2)

    def __makeCursor(self):
        # A white arrow with a dark edge, in a layer over everything (the
        # launcher's too).
        root = NodePath('gamepadCursor')
        lens = OrthographicLens()
        lens.setFilmSize(2, 2)
        lens.setNearFar(-1000, 1000)
        camera = root.attachNewNode(Camera('gamepadCursorCamera', lens))
        self.cursorRegion = base.win.makeDisplayRegion()
        self.cursorRegion.setSort(1000)
        self.cursorRegion.setCamera(camera)
        root.setDepthTest(False)
        root.setDepthWrite(False)
        root.setTransparency(TransparencyAttrib.MAlpha)
        from panda3d.core import GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Geom, GeomNode
        aspect = base.getAspectRatio()
        for scale, color in ((1.25, (0.1, 0.1, 0.2, 1)), (1.0, (1, 1, 1, 1))):
            data = GeomVertexData('cursor', GeomVertexFormat.getV3(), Geom.UHStatic)
            writer = GeomVertexWriter(data, 'vertex')
            size = 0.06 * scale
            for x, z in ((0, 0), (0.0, -size), (size * 0.72, -size * 0.72)):
                writer.addData3(x / aspect - (scale - 1) * 0.01, 0, z + (scale - 1) * 0.012)
            tris = GeomTriangles(Geom.UHStatic)
            tris.addVertices(0, 1, 2)
            geom = Geom(data)
            geom.addPrimitive(tris)
            node = GeomNode('cursorPart')
            node.addGeom(geom)
            part = root.attachNewNode(node)
            part.setColor(*color)
            part.setTwoSided(True)
        self.cursorArrow = root.attachNewNode('arrow')
        for part in root.findAllMatches('cursorPart'):
            part.reparentTo(self.cursorArrow)
        self.cursorArrow.hide()
        return self.cursorArrow
