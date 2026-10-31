"""On-screen controls for Survival Mode on a touch screen (Android).

A stick in the bottom left moves; dragging anywhere on the right half
looks around; buttons on the right fire, jump, use, reload, swap gags,
bonk and throw the Presentation. They talk to the player directly, so
they are separate from the regular game's touch controls and keys.
"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from direct.showbase.DirectObject import DirectObject
from panda3d.core import Point3

from toontown.toonbase import ToontownGlobals
from toontown.toonbase.TouchControls import makeDisc

STICK_RADIUS = 0.22
THUMB_RADIUS = 0.09
BUTTON_RADIUS = 0.1
LOOK_SPEED = 1.0


class SurvivalTouch(DirectObject):

    def __init__(self, player, game):
        DirectObject.__init__(self)
        self.player = player
        self.game = game
        self.dragging = False
        self.looking = False
        self.lastLook = None
        font = ToontownGlobals.getInterfaceFont()
        self.stick = DirectFrame(parent=base.a2dBottomLeft, relief=None, state=DGG.NORMAL, sortOrder=-10, pos=(0.5, 0, 0.42),
                                 frameSize=(-STICK_RADIUS, STICK_RADIUS, -STICK_RADIUS, STICK_RADIUS))
        makeDisc(STICK_RADIUS, (1, 1, 1, 0.22)).reparentTo(self.stick)
        self.thumb = makeDisc(THUMB_RADIUS, (1, 1, 1, 0.55))
        self.thumb.reparentTo(self.stick)
        self.stick.bind(DGG.B1PRESS, self.__startDrag)
        self.stick.bind(DGG.B1RELEASE, self.__endDrag)
        # The right half of the screen turns the view.
        self.lookPad = DirectFrame(parent=base.a2dBottomRight, relief=None, state=DGG.NORMAL, sortOrder=-20, pos=(0, 0, 0),
                                   frameSize=(-1.4, -0.3, 0.0, 1.9))
        self.lookPad.bind(DGG.B1PRESS, self.__startLook)
        self.lookPad.bind(DGG.B1RELEASE, self.__endLook)
        self.buttons = []
        layout = (('FIRE', (-0.32, 0.55), 0.14, 'fire'), ('JUMP', (-0.62, 0.3), 0.1, 'jump'), ('USE', (-0.32, 0.95), 0.09, 'use'),
                  ('RELOAD', (-0.62, 0.7), 0.09, 'reload'), ('SWAP', (-0.92, 0.5), 0.085, 'swap'), ('MELEE', (-0.62, 1.0), 0.085, 'bonk'),
                  ('GIFT', (-0.92, 0.8), 0.085, 'grenade'), ('TNT', (-0.92, 1.1), 0.085, 'tnt'),
                  ('II', (-0.12, 1.85), 0.06, 'pause'))
        for label, (x, z), radius, action in layout:
            b = DirectFrame(parent=base.a2dBottomRight, relief=None, state=DGG.NORMAL, sortOrder=-5, pos=(x, 0, z),
                            frameSize=(-radius, radius, -radius, radius), text=label, text_font=font, text_scale=radius * 0.45,
                            text_pos=(0, -radius * 0.15), text_fg=(1, 1, 1, 0.9))
            makeDisc(radius, (1, 0.2, 0.2, 0.35) if action == 'fire' else (1, 1, 1, 0.28)).reparentTo(b)
            b.bind(DGG.B1PRESS, self.__press, [action, True])
            b.bind(DGG.B1RELEASE, self.__press, [action, False])
            self.buttons.append(b)
        taskMgr.add(self.__tick, 'survivalTouch')

    def hideForGamepad(self):
        self.stick.hide()
        self.lookPad.hide()
        for b in self.buttons:
            b.hide()

    def showAfterGamepad(self):
        self.stick.show()
        self.lookPad.show()
        for b in self.buttons:
            b.show()

    def destroy(self):
        taskMgr.remove('survivalTouch')
        self.ignoreAll()
        self.stick.destroy()
        self.lookPad.destroy()
        for b in self.buttons:
            b.destroy()

    # --- Buttons ---

    def __press(self, action, down, event=None):
        if action == 'jump':
            self.player.press('jump', down)
        elif action == 'fire':
            self.player.pressAction('fire', down)
        elif down:
            self.player.pressAction(action, True)

    # --- The stick ---

    def __startDrag(self, event):
        self.dragging = True

    def __endDrag(self, event=None):
        self.dragging = False
        self.thumb.setPos(0, 0, 0)
        self.player.touchMove(0, 0)

    def __startLook(self, event):
        self.looking = True
        self.lastLook = None

    def __endLook(self, event=None):
        self.looking = False
        self.lastLook = None

    def __tick(self, task):
        if not base.mouseWatcherNode.hasMouse():
            return task.cont
        mouse = base.mouseWatcherNode.getMouse()
        if self.dragging:
            point = self.stick.getRelativePoint(render2d, Point3(mouse[0], 0, mouse[1]))
            x, z = point[0] / STICK_RADIUS, point[2] / STICK_RADIUS
            d = math.hypot(x, z)
            if d > 1:
                x, z = x / d, z / d
            self.thumb.setPos(x * STICK_RADIUS, 0, z * STICK_RADIUS)
            self.player.touchMove(x, z)
            self.player.setSprint(d > 0.95)
        if self.looking:
            cur = (mouse[0], mouse[1])
            if self.lastLook is not None:
                dx, dy = cur[0] - self.lastLook[0], cur[1] - self.lastLook[1]
                self.player.touchLookBy(-dx * LOOK_SPEED, dy * LOOK_SPEED)
            self.lastLook = cur
        return task.cont
