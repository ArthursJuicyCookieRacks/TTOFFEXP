"""The player in Survival Mode: a first-person toon.

The camera is the toon's eyes. A GravityWalker (the game's own walking
physics) carries an invisible body around the playground against its
walls and floors; the mouse (or a finger on the right half of the screen)
turns the view; the keys are Survival Mode's own and never touch the
game's walking controls.
"""

import math

from direct.controls import GravityWalker
from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from direct.showbase.InputStateGlobal import inputState
from panda3d.core import NodePath, Point3, Vec3, WindowProperties

from toontown.survival import SurvivalGlobals as G
from toontown.toonbase import ToontownGlobals, TouchControls

SOURCE = 'survival'
MOUSE_SENSITIVITY = 0.12
TOUCH_SENSITIVITY = 160.0
PITCH_LIMIT = 80.0

# Survival Mode's own keys (BO1 layout). Android gets buttons for these.
KEYS = {
    'forward': ('w', 'arrow_up'),
    'reverse': ('s', 'arrow_down'),
    'slideLeft': ('a', 'arrow_left'),
    'slideRight': ('d', 'arrow_right'),
    'jump': ('space',),
    'sprint': ('shift', 'lshift', 'rshift'),
}
# The controller (BO1's layout): the left stick walks, the right stick looks,
# RT fires, A jumps, X reloads or uses, Y swaps gags, RB throws the
# Presentation, R3 bonks, L3 sprints, the D-pad picks a gag, Start pauses.
GAMEPAD_BUTTONS = {
    'rtrigger': ('action', 'fire'),
    'face_a': ('key', 'jump'),
    'face_x': ('action', 'use'),
    'face_y': ('action', 'swap'),
    'face_b': ('action', 'reload'),
    'rshoulder': ('action', 'grenade'),
    'lshoulder': ('action', 'reload'),
    'rstick': ('action', 'bonk'),
    'lstick': ('key', 'sprint'),
    'dpad_left': ('action', 'gag1'),
    'dpad_right': ('action', 'gag2'),
    'dpad_up': ('action', 'swap'),
    'start': ('action', 'pause'),
    'back': ('action', 'pause'),
}
# The right stick's top turn rate, degrees a second, with a curve that is
# slow near the middle for fine aim.
GAMEPAD_LOOK_SPEED = 150.0
GAMEPAD_LOOK_DEAD_ZONE = 0.15
GAMEPAD_WALK_DEAD_ZONE = 0.3
ACTIONS = {
    'fire': ('mouse1',),
    'reload': ('r',),
    'use': ('e', 'f'),
    'gag1': ('1',),
    'gag2': ('2',),
    'swap': ('q', 'wheel_up', 'wheel_down'),
    'bonk': ('v', 'mouse3'),
    'grenade': ('g', 'mouse2'),
    'pause': ('escape',),
}


class SurvivalPlayer(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalPlayer')

    def __init__(self, game, start, h):
        DirectObject.__init__(self)
        self.game = game
        self.body = render.attachNewNode('survivalPlayer')
        self.body.setPos(start)
        self.body.setH(h)
        self.head = self.body.attachNewNode('head')
        self.head.setZ(G.EYE_HEIGHT)
        self.pitch = 0.0
        self.hp = G.PLAYER_HP
        self.maxHp = G.PLAYER_HP
        self.lastHurt = -100.0
        self.down = False
        self.downSince = 0.0
        self.reviveProgress = 0.0
        self.stamina = G.SPRINT_TIME
        self.sprinting = False
        self.firing = False
        self.using = False
        self.enabled = False
        self.lookDelta = Vec3(0)
        self.touchLook = None
        self.walker = GravityWalker.GravityWalker(legacyLifter=False)
        self.walker.setWallBitMask(ToontownGlobals.WallBitmask)
        self.walker.setFloorBitMask(ToontownGlobals.FloorBitmask)
        self.walker.initializeCollisions(base.cTrav, self.body, avatarRadius=1.4, floorOffset=0.025, reach=4.0)
        self.walker.setWalkSpeed(G.WALK_SPEED, G.JUMP_FORCE, G.WALK_SPEED * 0.6, 0)
        self.walker.placeOnFloor()
        self.mouseCentered = False
        self.touchMode = TouchControls.wantTouchControls()
        self.sprintLatched = False
        self.touch = None

    # --- Turning on and off ---

    def enable(self):
        if self.enabled:
            return
        self.enabled = True
        for token, keys in KEYS.items():
            for key in keys:
                self.accept(key, self.__set, [token, True])
                self.accept(key + '-up', self.__set, [token, False])
        for action, keys in ACTIONS.items():
            for key in keys:
                if self.touchMode and key.startswith(('mouse', 'wheel')):
                    # Touches drive the on-screen buttons instead.
                    continue
                self.accept(key, self.__action, [action, True])
                self.accept(key + '-up', self.__action, [action, False])
        self.walker.enableAvatarControls()
        if self.touchMode:
            from toontown.survival.SurvivalTouch import SurvivalTouch
            self.touch = SurvivalTouch(self, self.game)
        else:
            self.grabMouse(True)
        gamepad = getattr(base, 'gamepad', None)
        if gamepad is not None:
            gamepad.setGame(self)
        taskMgr.add(self.__tick, 'survivalPlayer', priority=24)

    def disable(self):
        if not self.enabled:
            return
        self.enabled = False
        self.ignoreAll()
        for token in KEYS:
            inputState.set(token, False, inputSource=SOURCE)
        self.sprinting = False
        self.firing = False
        self.walker.disableAvatarControls()
        gamepad = getattr(base, 'gamepad', None)
        if gamepad is not None and gamepad.game is self:
            gamepad.setGame(None)
        if self.touch:
            self.touch.destroy()
            self.touch = None
        self.grabMouse(False)
        taskMgr.remove('survivalPlayer')

    def destroy(self):
        self.disable()
        self.walker.setCollisionsActive(0)
        self.walker.deleteCollisions()
        self.body.removeNode()

    def grabMouse(self, grab):
        if base.win is None or self.touchMode:
            return
        props = WindowProperties()
        props.setCursorHidden(grab)
        if grab:
            props.setMouseMode(WindowProperties.M_relative)
        else:
            props.setMouseMode(WindowProperties.M_absolute)
        base.win.requestProperties(props)
        self.mouseCentered = False

    # --- Input ---

    def __set(self, token, down):
        if token == 'sprint':
            self.sprinting = down
            return
        if token == 'jump' and down and not self.down:
            inputState.set('jump', True, inputSource=SOURCE)
            taskMgr.doMethodLater(0.1, lambda t: inputState.set('jump', False, inputSource=SOURCE), 'survivalJumpUp')
            return
        if token != 'jump':
            inputState.set(token, down and not self.down, inputSource=SOURCE)

    def __action(self, action, down):
        if action == 'fire':
            self.firing = down
            if down:
                self.game.playerFires()
        elif action == 'use':
            self.using = down
            if down:
                self.game.playerUses()
        elif down:
            self.game.playerAction(action)

    def touchMove(self, x, y):
        """The Android stick (or a controller's): x, y in -1..1."""
        dead = GAMEPAD_WALK_DEAD_ZONE
        inputState.set('forward', y > dead and not self.down, inputSource=SOURCE)
        inputState.set('reverse', y < -dead and not self.down, inputSource=SOURCE)
        inputState.set('slideLeft', x < -dead and not self.down, inputSource=SOURCE)
        inputState.set('slideRight', x > dead and not self.down, inputSource=SOURCE)
        if self.sprintLatched and y <= dead:
            # L3's sprint lasts while the stick is pushed forward (BO1).
            self.sprintLatched = False
            self.sprinting = False

    def touchLookBy(self, dx, dy):
        self.lookDelta += Vec3(dx * TOUCH_SENSITIVITY, dy * TOUCH_SENSITIVITY, 0)

    # --- The controller (see toontown.toonbase.Gamepad.setGame) ---

    def wantsPointer(self):
        # A menu or the pause card up: the controller moves the pointer.
        return self.game.paused or self.game.over

    def gamepadActive(self, on):
        if self.touch is not None:
            if on:
                self.touch.hideForGamepad()
            else:
                self.touch.showAfterGamepad()

    def gamepadMove(self, x, y):
        self.touchMove(x, y)

    def gamepadLook(self, x, y, dt):
        if max(abs(x), abs(y)) < GAMEPAD_LOOK_DEAD_ZONE:
            return
        speed = GAMEPAD_LOOK_SPEED * dt
        self.lookDelta += Vec3(-x * abs(x) * speed, y * abs(y) * speed, 0)

    def gamepadButton(self, name, down):
        what = GAMEPAD_BUTTONS.get(name)
        if what is None:
            return
        kind, token = what
        if kind == 'key':
            if token == 'sprint':
                if down:
                    self.sprintLatched = True
                    self.sprinting = True
                return
            self.__set(token, down)
        else:
            self.__action(token, down)

    def press(self, token, down):
        """For the touch buttons and tests: a movement key."""
        self.__set(token, down)

    def pressAction(self, action, down):
        """For the touch buttons and tests: an action key."""
        self.__action(action, down)

    def __readMouse(self):
        if self.touchMode or not base.mouseWatcherNode.hasMouse():
            return
        win = base.win
        md = win.getPointer(0)
        cx, cy = win.getXSize() // 2, win.getYSize() // 2
        if not self.mouseCentered:
            win.movePointer(0, cx, cy)
            self.mouseCentered = True
            return
        dx, dy = md.getX() - cx, md.getY() - cy
        if dx or dy:
            self.lookDelta += Vec3(-dx * MOUSE_SENSITIVITY, -dy * MOUSE_SENSITIVITY, 0)
            win.movePointer(0, cx, cy)

    # --- Each frame ---

    def __tick(self, task):
        dt = globalClock.getDt()
        if self.game.paused:
            return task.cont
        self.__readMouse()
        if self.lookDelta.lengthSquared() > 0:
            self.body.setH(self.body.getH() + self.lookDelta[0])
            self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch + self.lookDelta[1]))
            self.lookDelta = Vec3(0)
        self.head.setP(self.pitch)
        camera.reparentTo(self.head)
        camera.setPosHpr(0, 0, 0, 0, 0, 0)
        # Sprinting burns stamina; the stamina comes back when walking.
        moving = inputState.isSet('forward')
        boost = self.game.hasTonic('sprint')
        if self.sprinting and moving and self.stamina > 0 and not self.down:
            self.stamina -= dt / (2.0 if boost else 1.0)
            speed = G.SPRINT_SPEED * (1.2 if boost else 1.0)
        else:
            self.stamina = min(G.SPRINT_TIME, self.stamina + dt * G.SPRINT_TIME / G.SPRINT_RECOVER)
            speed = G.WALK_SPEED
        if self.down:
            speed = 0.0
        self.walker.setWalkSpeed(speed, G.JUMP_FORCE, speed * 0.6, 0)
        # Laff comes back out of the cogs' reach.
        now = globalClock.getFrameTime()
        if not self.down and self.hp < self.maxHp:
            delay = G.REGEN_DELAY_LOW if self.hp < G.LOW_HP else G.REGEN_DELAY
            if now - self.lastHurt > delay:
                self.hp = min(self.maxHp, self.hp + G.REGEN_RATE * dt)
                self.game.hud.setLaff(self.hp, self.maxHp)
        if self.firing:
            self.game.playerFires(held=True)
        if self.down:
            self.game.playerDownTick(dt)
        return task.cont

    # --- Where it is ---

    def alive(self):
        return not self.down

    def getPos(self):
        return self.body.getPos(render)

    def getEye(self):
        return self.head.getPos(render)

    def getForward(self):
        return render.getRelativeVector(self.head, Vec3(0, 1, 0))

    def getFlatForward(self):
        return render.getRelativeVector(self.body, Vec3(0, 1, 0))

    def getH(self):
        return self.body.getH(render)

    def setLook(self, h, p):
        """For tests and the start of a game: face this way."""
        self.body.setH(h)
        self.pitch = p
        self.head.setP(p)

    # --- Getting hit ---

    def hurt(self, damage, cog=None):
        if self.down or self.game.over:
            return
        self.hp -= damage
        self.lastHurt = globalClock.getFrameTime()
        if self.hp <= 0:
            self.hp = 0
            self.goDown()
        self.game.hud.setLaff(self.hp, self.maxHp)
        self.game.hud.flashHurt()

    def goDown(self):
        self.down = True
        self.downSince = globalClock.getFrameTime()
        self.reviveProgress = 0.0
        for token in ('forward', 'reverse', 'slideLeft', 'slideRight'):
            inputState.set(token, False, inputSource=SOURCE)
        self.head.setZ(1.2)
        self.game.playerWentDown()

    def getUp(self, hp):
        self.down = False
        self.hp = min(hp, self.maxHp)
        self.lastHurt = globalClock.getFrameTime()
        self.head.setZ(G.EYE_HEIGHT)
        self.game.hud.setLaff(self.hp, self.maxHp)

    def setMaxHp(self, maxHp):
        self.maxHp = maxHp
        self.hp = min(self.hp, maxHp) if self.hp < maxHp else maxHp
        self.game.hud.setLaff(self.hp, self.maxHp)
