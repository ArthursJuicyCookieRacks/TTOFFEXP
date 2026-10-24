"""On-screen controls for touch screens (the Android build).

A joystick in the bottom left corner and a jump button in the bottom right
stand in for the keyboard. They send the same events the keys do, so
everything that listens for the keys works with them: walking (the arrow
keys and Control) and the minigames (W, A, S, D and Space).

The controls show while something asks for them: the toon's walking controls
or a minigame's keys. Each asks under its own name, and the controls hide
when no one wants them any more.
"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from direct.showbase.DirectObject import DirectObject
from panda3d.core import ConfigVariableBool, GeomNode, NodePath, Point3
from panda3d.core import Geom, GeomTrifans, GeomVertexData, GeomVertexFormat, GeomVertexWriter

from toontown.toonbase import TTLocalizer, ToontownGlobals

# The keys each direction of the joystick presses.
DIRECTION_KEYS = {
    'up': ('arrow_up', 'w'),
    'down': ('arrow_down', 's'),
    'left': ('arrow_left', 'a'),
    'right': ('arrow_right', 'd'),
}
JUMP_KEYS = ('control', 'space')

# How far from the centre, as a fraction of the joystick's radius, the thumb
# must go before a direction counts, and the angle either side of a straight
# direction that still presses it (so the diagonals press two).
DEAD_ZONE = 0.25
DIRECTION_SPREAD = math.radians(67.5)


def wantTouchControls():
    return ConfigVariableBool('want-touch-controls', False).getValue()


def makeDisc(radius, color, segments=32):
    data = GeomVertexData('disc', GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vertices = GeomVertexWriter(data, 'vertex')
    colors = GeomVertexWriter(data, 'color')
    vertices.addData3(0, 0, 0)
    colors.addData4(*color)
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        vertices.addData3(radius * math.cos(angle), 0, radius * math.sin(angle))
        colors.addData4(*color)
    fan = GeomTrifans(Geom.UHStatic)
    fan.addConsecutiveVertices(0, segments + 2)
    fan.closePrimitive()
    geom = Geom(data)
    geom.addPrimitive(fan)
    node = GeomNode('disc')
    node.addGeom(geom)
    disc = NodePath(node)
    disc.setTransparency(1)
    return disc


class TouchControls(DirectObject):
    RADIUS = 0.22
    THUMB_RADIUS = 0.09
    JUMP_RADIUS = 0.13

    def __init__(self):
        self.requesters = set()
        self.pressed = set()
        self.jumping = False
        self.dragging = False

        # Behind the rest of the interface, so a dialog over it wins a touch.
        self.joystick = DirectFrame(parent=base.a2dBottomLeft, relief=None, state=DGG.NORMAL, sortOrder=-10,
                                    pos=(0.58, 0, 0.32),
                                    frameSize=(-self.RADIUS, self.RADIUS, -self.RADIUS, self.RADIUS))
        makeDisc(self.RADIUS, (1, 1, 1, 0.25)).reparentTo(self.joystick)
        self.thumb = makeDisc(self.THUMB_RADIUS, (1, 1, 1, 0.6))
        self.thumb.reparentTo(self.joystick)
        self.joystick.bind(DGG.B1PRESS, self.__startDrag)
        self.joystick.bind(DGG.B1RELEASE, self.__endDrag)

        self.jumpButton = DirectFrame(parent=base.a2dBottomRight, relief=None, state=DGG.NORMAL, sortOrder=-10,
                                      pos=(-0.48, 0, 0.3),
                                      frameSize=(-self.JUMP_RADIUS, self.JUMP_RADIUS, -self.JUMP_RADIUS, self.JUMP_RADIUS))
        makeDisc(self.JUMP_RADIUS, (1, 1, 1, 0.3)).reparentTo(self.jumpButton)
        self.jumpButton['text'] = TTLocalizer.TouchControlsJump
        self.jumpButton['text_font'] = ToontownGlobals.getInterfaceFont()
        self.jumpButton['text_scale'] = 0.06
        self.jumpButton['text_pos'] = (0, -0.02)
        self.jumpButton['text_fg'] = (1, 1, 1, 0.9)
        self.jumpButton.bind(DGG.B1PRESS, self.__jump, [True])
        self.jumpButton.bind(DGG.B1RELEASE, self.__jump, [False])

        self.joystick.hide()
        self.jumpButton.hide()

    def destroy(self):
        self.__release()
        self.ignoreAll()
        self.joystick.destroy()
        self.jumpButton.destroy()

    def request(self, name):
        self.requesters.add(name)
        self.joystick.show()
        self.jumpButton.show()

    def release(self, name):
        self.requesters.discard(name)
        if not self.requesters:
            self.__release()
            self.joystick.hide()
            self.jumpButton.hide()

    def __startDrag(self, event):
        self.dragging = True
        # The touch may end anywhere on the screen, off the joystick.
        self.accept('mouse1-up', self.__endDrag)
        taskMgr.add(self.__drag, 'touchControlsDrag')

    def __endDrag(self, event=None):
        self.ignore('mouse1-up')
        self.__release()

    def __drag(self, task):
        if not self.dragging:
            return task.done
        if not base.mouseWatcherNode.hasMouse():
            return task.cont
        mouse = base.mouseWatcherNode.getMouse()
        point = self.joystick.getRelativePoint(render2d, Point3(mouse[0], 0, mouse[1]))
        x, z = point[0] / self.RADIUS, point[2] / self.RADIUS
        distance = math.hypot(x, z)
        if distance > 1:
            x, z = x / distance, z / distance
        self.thumb.setPos(x * self.RADIUS, 0, z * self.RADIUS)

        wanted = set()
        if distance > DEAD_ZONE:
            angle = math.atan2(z, x)
            for direction, centre in (('right', 0), ('up', math.pi / 2), ('left', math.pi), ('down', -math.pi / 2)):
                difference = abs((angle - centre + math.pi) % (2 * math.pi) - math.pi)
                if difference < DIRECTION_SPREAD:
                    wanted.add(direction)
        for direction in self.pressed - wanted:
            self.__send(DIRECTION_KEYS[direction], up=True)
        for direction in wanted - self.pressed:
            self.__send(DIRECTION_KEYS[direction], up=False)
        self.pressed = wanted
        return task.cont

    def __jump(self, down, event=None):
        if down == self.jumping:
            return
        self.jumping = down
        self.__send(JUMP_KEYS, up=not down)

    def __release(self):
        self.dragging = False
        taskMgr.remove('touchControlsDrag')
        for direction in self.pressed:
            self.__send(DIRECTION_KEYS[direction], up=True)
        self.pressed = set()
        self.thumb.setPos(0, 0, 0)
        self.__jump(False)

    @staticmethod
    def __send(keys, up):
        for key in keys:
            messenger.send(key + '-up' if up else key)


def request(name):
    if wantTouchControls():
        if not hasattr(base, 'touchControls'):
            base.touchControls = TouchControls()
        base.touchControls.request(name)


def release(name):
    if hasattr(base, 'touchControls'):
        base.touchControls.release(name)
