"""The player in Survival Mode: a first-person toon.

The camera is the toon's eyes. A GravityWalker (the game's own walking
physics) carries an invisible body around the playground against its
walls and floors; the mouse (or a finger on the right half of the screen)
turns the view; the keys are Survival Mode's own and never touch the
game's walking controls.
"""

import math
import random

from direct.controls import GravityWalker
from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from direct.showbase.InputStateGlobal import inputState
from panda3d.core import BitMask32, NodePath, Point3, Vec3, WindowProperties

from toontown.survival import SurvivalGlobals as G
from toontown.toonbase import ToontownGlobals, TouchControls

SOURCE = 'survival'
MOUSE_SENSITIVITY = 0.12
# Camera sensitivity 1 (very slow) to 10 (very fast), from the pause
# menu's Settings; 5 is the turn speed the game always had.
SENSITIVITY_SETTING = ('survival', 'sensitivity')
DEFAULT_SENSITIVITY = 5


def sensitivityFactor(level):
    level = max(1, min(10, int(level)))
    # 1 turns at a quarter of the old speed, 5 at the old speed, 10 three
    # times it; each step multiplies by the same amount on either side.
    if level <= 5:
        return 0.25 * 4.0 ** ((level - 1) / 4.0)
    return 3.0 ** ((level - 5) / 5.0)


def loadSensitivity():
    try:
        return int(base.settings.settings.getOption(SENSITIVITY_SETTING[0], SENSITIVITY_SETTING[1], DEFAULT_SENSITIVITY))
    except Exception:
        return DEFAULT_SENSITIVITY


def saveSensitivity(level):
    try:
        base.settings.settings.updateSetting(SENSITIVITY_SETTING[0], SENSITIVITY_SETTING[1], int(level))
    except Exception:
        pass
TOUCH_SENSITIVITY = 160.0
PITCH_LIMIT = 80.0
# The toon's own footsteps, the loops the playground uses.
# The toon-hit sound from the Cogdominium games, on every hit a cog lands.
HIT_SOUND = 'phase_5/audio/sfx/tt_s_ara_cfg_toonHit.ogg'
WALK_STEPS = 'phase_3.5/audio/sfx/AV_footstep_walkloop.ogg'
RUN_STEPS = 'phase_3.5/audio/sfx/AV_footstep_runloop.ogg'
STEP_VOLUME = 0.6

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
# RT fires, A jumps, X reloads (tap) or uses (hold), Y swaps gags, RB throws
# TNT (BO1's lethal grenade), LB the Presentation (BO1's special grenade),
# R3 bonks, L3 sprints, the D-pad picks a gag, Start pauses.
GAMEPAD_BUTTONS = {
    'rtrigger': ('action', 'fire'),
    'face_a': ('key', 'jump'),
    'face_x': ('action', 'useOrReload'),
    'face_y': ('action', 'swap'),
    
    'rshoulder': ('action', 'tnt'),
    'lshoulder': ('action', 'grenade'),
    'rstick': ('action', 'bonk'),
    'lstick': ('key', 'sprint'),
    'dpad_left': ('action', 'gag1'),
    'dpad_right': ('action', 'gag2'),
    'dpad_up': ('action', 'swap'),
    'dpad_down': ('action', 'trap'),
    'start': ('action', 'pause'),
    'back': ('action', 'pause'),
}
# The right stick's top turn rate, degrees a second, with a curve that is
# slow near the middle for fine aim.
GAMEPAD_LOOK_SPEED = 150.0
GAMEPAD_LOOK_DEAD_ZONE = 0.15
GAMEPAD_WALK_DEAD_ZONE = 0.3
# X tapped reloads; X held this long uses.
GAMEPAD_HOLD_TIME = 0.35
SLIDE_TOKENS = ('slideLeft', 'slideRight')
# Big maps: a move shorter than this in one frame is checked for having
# gone through a wall.
GUARD_REACH = 10.0
# The toon's wall sphere (GravityWalker's: radius 1.4, resting on the floor).
PUSH_RADIUS = 1.4
ACTIONS = {
    'fire': ('mouse1',),
    'reload': ('r',),
    'use': ('e', 'f'),
    'gag1': ('1',),
    'gag2': ('2',),
    'gag3': ('3',),
    # BO1 on a computer: G throws the lethal grenade (TNT), Q the special
    # one (the Presentation); the wheel or Tab swaps gags.
    'swap': ('tab', 'wheel_up', 'wheel_down'),
    'bonk': ('v', 'mouse3'),
    'tnt': ('g',),
    'grenade': ('q',),
    'trap': ('4',),
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
        # Sprinting now; the meter ran dry (wait for a fresh press); when
        # the last sprint was.
        self.sprintActive = False
        self.sprintSpent = False
        self.lastSprint = -100.0
        self.firing = False
        self.using = False
        self.enabled = False
        self.lookDelta = Vec3(0)
        self.touchLook = None
        self.walker = GravityWalker.GravityWalker(legacyLifter=False)
        self.walker.setWallBitMask(ToontownGlobals.WallBitmask)
        self.walker.setFloorBitMask(ToontownGlobals.FloorBitmask)
        # The fluid pusher: it sweeps the toon's wall sphere along the whole
        # step of a frame, not only where the step ends. With the plain
        # pusher a slow frame (a phone, a busy round) moved the toon most
        # of a foot past the edge of a thin wall or a ring of posts, and
        # it came out on the far side: the toon walked through props and
        # into the tunnels with a jitter (Arthur).
        from panda3d.core import ConfigVariableBool
        fluid = ConfigVariableBool('want-fluid-pusher', False)
        wasFluid = fluid.getValue()
        # Not on the big maps (Toon Theater, Cog Nation): there every wall
        # is a CollisionBox, and the fluid pusher froze a toon that came to
        # rest touching one (Arthur: stuck all over the lobby). They get
        # the plain pusher and the walk-through check in __guard instead.
        self.big = bool(getattr(game.arena, 'big', False))
        fluid.setValue(not self.big)
        try:
            self.walker.initializeCollisions(base.cTrav, self.body, avatarRadius=1.4, floorOffset=0.025, reach=4.0)
        finally:
            fluid.setValue(wasFluid)
        if self.big:
            # The walls push the toon out in __pushOut instead.
            self.walker.cWallSphereNodePath.node().setFromCollideMask(BitMask32.allOff())
        self.respectedPrev = base.cTrav.getRespectPrevTransform()
        # Only the fluid pusher needs where the toon was last frame; with
        # the plain one (big maps) it made a box wall miss a toon walking
        # into it every other frame, so the toon shook against it.
        base.cTrav.setRespectPrevTransform(not self.big)
        self.walker.setWalkSpeed(G.WALK_SPEED, G.JUMP_FORCE, G.WALK_SPEED * G.REVERSE_SCALE, 0)
        self.walker.placeOnFloor()
        self.mouseCentered = False
        self.touchMode = TouchControls.wantTouchControls()
        self.sprintLatched = False
        self.touch = None
        self.xHeldSince = None
        self.slideForcedOff = {}
        self.moveState = 'idle'
        self.setSensitivity(loadSensitivity())
        self.hitSound = None
        self.stepSounds = {}
        self.stepPlaying = None
        for key, path in (('walk', WALK_STEPS), ('run', RUN_STEPS)):
            sound = base.loader.loadSfx(path)
            if sound:
                sound.setLoop(True)
                sound.setVolume(STEP_VOLUME)
                self.stepSounds[key] = sound

    # --- Turning on and off ---

    def enable(self):
        if self.enabled:
            return
        self.enabled = True
        self.acceptKeys()
        self.walker.enableAvatarControls()
        self.__allowSliding(True)
        if self.touchMode:
            from toontown.survival.SurvivalTouch import SurvivalTouch
            self.touch = SurvivalTouch(self, self.game)
        else:
            self.grabMouse(True)
        gamepad = getattr(base, 'gamepad', None)
        if gamepad is not None:
            gamepad.setGame(self)
        taskMgr.add(self.__tick, 'survivalPlayer', priority=24)
        if self.big:
            self.safePos = self.body.getPos()
            # After the walls have pushed (collisionLoop is sort 30).
            taskMgr.add(self.__guard, 'survivalPlayerGuard', sort=35)

    def acceptKeys(self):
        """Listen for the keys, as the player has bound them (Settings >
        Key Bindings); called again after a key is changed."""
        from toontown.survival import SurvivalKeys
        for key in getattr(self, 'keysAccepted', ()):
            self.ignore(key)
            self.ignore(key + '-up')
        self.keysAccepted = []
        SurvivalKeys.load()
        for token in KEYS:
            for key in SurvivalKeys.keysFor(token):
                self.accept(key, self.__set, [token, True])
                self.accept(key + '-up', self.__set, [token, False])
                self.keysAccepted.append(key)
        for action in ACTIONS:
            for key in SurvivalKeys.keysFor(action):
                if self.touchMode and key.startswith(('mouse', 'wheel')):
                    # Touches drive the on-screen buttons instead.
                    continue
                self.accept(key, self.__action, [action, True])
                self.accept(key + '-up', self.__action, [action, False])
                self.keysAccepted.append(key)

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
        self.__allowSliding(False)
        taskMgr.remove('survivalHoldX')
        gamepad = getattr(base, 'gamepad', None)
        if gamepad is not None and gamepad.game is self:
            gamepad.setGame(None)
        if self.touch:
            self.touch.destroy()
            self.touch = None
        self.grabMouse(False)
        self.__footsteps(off=True)
        taskMgr.remove('survivalPlayer')
        taskMgr.remove('survivalPlayerGuard')

    def destroy(self):
        self.disable()
        self.walker.setCollisionsActive(0)
        self.walker.deleteCollisions()
        if hasattr(self, 'guardNode'):
            self.guardNode.removeNode()
        if hasattr(self, 'probeNode'):
            self.probeNode.removeNode()
        if hasattr(self, 'pushNode'):
            self.pushNode.removeNode()
        if base.cTrav:
            base.cTrav.setRespectPrevTransform(self.respectedPrev)
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

    def __allowSliding(self, allow):
        """Every Toon.Toon forces slideLeft/slideRight off for good (the
        playground has no strafing). In here the toon strafes, so the force
        goes away while the game runs and comes back after."""
        forcing = getattr(inputState, '_forcingOff', None)
        if forcing is None:
            return
        if allow:
            self.slideForcedOff = dict((token, forcing.pop(token)) for token in SLIDE_TOKENS if token in forcing)
        else:
            for token, sources in getattr(self, 'slideForcedOff', {}).items():
                forcing.setdefault(token, set()).update(sources)
            self.slideForcedOff = {}

    def __blocked(self):
        # Paused, over, or in Freddy's menu: a press now is dropped, never
        # kept for later (Arthur: buttons pressed on the pause screen went
        # off when it closed). Letting go always counts.
        game = self.game
        return game.paused or game.over or game.inMenu()

    def __set(self, token, down):
        if down and self.__blocked():
            return
        if token == 'sprint':
            self.setSprint(down)
            return
        if token == 'jump' and down and not self.down:
            inputState.set('jump', True, inputSource=SOURCE)
            taskMgr.doMethodLater(0.1, lambda t: inputState.set('jump', False, inputSource=SOURCE), 'survivalJumpUp')
            return
        if token != 'jump':
            # Downed, the toon still crawls (the tick slows it to a crawl).
            inputState.set(token, down, inputSource=SOURCE)

    def setSensitivity(self, level):
        self.sensitivity = max(1, min(10, int(level)))
        self.lookScale = sensitivityFactor(self.sensitivity)

    def setSprint(self, down, held=False):
        """down: the sprint button is pressed. held: the touch stick, which
        says each frame whether it is pushed to the edge."""
        if down and (not self.sprinting or not held):
            # A fresh press: a spent sprint goes again as soon as there is
            # breath for it, without stopping first (Arthur).
            self.sprintSpent = False
        elif down and held and self.sprintSpent and self.stamina >= G.SPRINT_MIN:
            # The stick never lets go to press again: it starts again by
            # itself once there is breath.
            self.sprintSpent = False
        self.sprinting = down

    def __action(self, action, down):
        if down and action != 'pause' and self.__blocked():
            return
        if action == 'fire':
            self.firing = down
            if down:
                self.game.playerFires()
        elif action == 'use':
            self.using = down
            if down:
                self.game.playerUses()
        elif action == 'useOrReload':
            if down:
                self.xHeldSince = globalClock.getFrameTime()
                taskMgr.doMethodLater(GAMEPAD_HOLD_TIME, self.__holdX, 'survivalHoldX')
            else:
                taskMgr.remove('survivalHoldX')
                if self.xHeldSince is not None:
                    # Let go before the hold time: a tap, which reloads.
                    self.xHeldSince = None
                    self.game.playerAction('reload')
                else:
                    # The end of a hold: the use (a revive) stops.
                    self.using = False
        elif action == 'tnt':
            # Held, the TNT cooks; let go, it is thrown.
            self.game.playerAction('tnt' if down else 'tntUp')
        elif down:
            self.game.playerAction(action)

    def __holdX(self, task):
        # X held: use (and keep using, for a revive, until it is let go);
        # the release is not a tap any more.
        self.xHeldSince = None
        self.using = True
        self.game.playerUses()
        return task.done

    def touchMove(self, x, y):
        """The Android stick (or a controller's): x, y in -1..1."""
        dead = GAMEPAD_WALK_DEAD_ZONE
        inputState.set('forward', y > dead, inputSource=SOURCE)
        inputState.set('reverse', y < -dead, inputSource=SOURCE)
        inputState.set('slideLeft', x < -dead, inputSource=SOURCE)
        inputState.set('slideRight', x > dead, inputSource=SOURCE)
        if self.sprintLatched and y <= dead:
            # L3's sprint lasts while the stick is pushed forward (BO1).
            self.sprintLatched = False
            self.setSprint(False)

    def touchLookBy(self, dx, dy):
        self.lookDelta += Vec3(dx * TOUCH_SENSITIVITY, dy * TOUCH_SENSITIVITY, 0) * self.lookScale

    # --- The controller (see toontown.toonbase.Gamepad.setGame) ---

    def wantsPointer(self):
        # A menu or the pause card up: the controller moves the pointer.
        return self.game.paused or self.game.over or self.game.inMenu()

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
        speed = GAMEPAD_LOOK_SPEED * dt * self.lookScale
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
                    self.setSprint(True)
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
        x, y = md.getX(), md.getY()
        cx, cy = win.getXSize() // 2, win.getYSize() // 2
        if not self.mouseCentered:
            # A phone or TV box can't warp its pointer back to the middle
            # (the controller's pointer is only told where it is), so the
            # look is measured from wherever the pointer was last seen.
            # Measured from the middle, a pointer left low on Map Select
            # (the Cog HQ rows) turned the view every frame: the toon spun
            # round and round, looking at the floor (Arthur, on a controller).
            self.mouseLast = (cx, cy) if win.movePointer(0, cx, cy) else (x, y)
            self.mouseCentered = True
            return
        lx, ly = self.mouseLast
        dx, dy = x - lx, y - ly
        if dx or dy:
            self.lookDelta += Vec3(-dx * MOUSE_SENSITIVITY, -dy * MOUSE_SENSITIVITY, 0) * self.lookScale
            self.mouseLast = (cx, cy) if win.movePointer(0, cx, cy) else (x, y)

    # --- Each frame ---

    def __guard(self, task):
        """Big maps: the walls push the toon out here (see __pushOut), and
        a line from last frame's middle of the toon to this frame's that
        crosses a wall means it went through one (a long step on a slow
        frame): put it back."""
        pos = self.body.getPos()
        last = self.safePos
        if any(c != c for c in pos):
            self.body.setPos(last)
            return task.cont
        pos = self.__pushOut(pos)
        self.body.setPos(pos)
        moved = pos - last
        # Not the game's own long moves (a teleporter, a trip back from a
        # room): those go where they like. A wall's push can be a long
        # one (it threw a toon in a corner 3 feet out through the wall),
        # so anything shorter is checked.
        if 0.04 < moved.lengthSquared() < GUARD_REACH * GUARD_REACH:
            if self.__crossesWall(last, pos):
                self.guardReverts = getattr(self, 'guardReverts', 0) + 1
                self.body.setPos(last)
                self.__unwedge(Vec3(0))
                return task.cont
        self.safePos = Point3(pos)
        self.__unwedge(moved)
        return task.cont

    def __pushOut(self, pos):
        """Out of every wall the toon's sphere sinks into, along each
        wall's own level push: Panda's pushers summed the pushes of the
        stacked bars of one wall (the toon shook against it) or let it
        sink into a corner and held it there. A few rounds settle a toon
        in a corner between two or three walls."""
        from panda3d.core import (CollisionHandlerQueue, CollisionNode, CollisionSphere,
                                  CollisionTraverser)
        if not hasattr(self, 'pushTrav'):
            node = CollisionNode('survivalPush')
            node.addSolid(CollisionSphere(0, 0, PUSH_RADIUS, PUSH_RADIUS))
            node.setFromCollideMask(ToontownGlobals.WallBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            self.pushNode = render.attachNewNode(node)
            self.pushQueue = CollisionHandlerQueue()
            self.pushTrav = CollisionTraverser('survivalPush')
            self.pushTrav.addCollider(self.pushNode, self.pushQueue)
        root = self.game.arena.root
        pos = Point3(pos)
        for i in range(4):
            self.pushNode.setPos(pos)
            self.pushQueue.clearEntries()
            self.pushTrav.traverse(root)
            pushes = []
            for k in range(self.pushQueue.getNumEntries()):
                entry = self.pushQueue.getEntry(k)
                n = entry.getSurfaceNormal(render)
                n = Vec3(n[0], n[1], 0)
                if n.length() < 0.3:
                    # On top of (or under) a low bar: a railing, a low wall
                    # with nothing to stand on. Off it to the nearer side.
                    n, depth = self.__offTheTop(entry, pos)
                    if n is None:
                        continue
                else:
                    n.normalize()
                    depth = (entry.getSurfacePoint(render) - entry.getInteriorPoint(render)).dot(n)
                if depth <= 0.002:
                    continue
                for j, (m, d) in enumerate(pushes):
                    if m.dot(n) > 0.94:
                        if depth > d:
                            pushes[j] = (m, depth)
                        break
                else:
                    pushes.append((n, depth))
            if not pushes:
                break
            total = Vec3(0)
            for n, d in pushes:
                total += n * (d + 0.005)
            if total.length() > 2.0:
                total.normalize()
                total *= 2.0
            pos += total
        return pos

    def __offTheTop(self, entry, pos):
        from panda3d.core import CollisionCapsule
        solid = entry.getInto()
        if not isinstance(solid, CollisionCapsule):
            return None, 0
        mat = entry.getIntoNodePath().getMat(render)
        a, b = mat.xformPoint(solid.getPointA()), mat.xformPoint(solid.getPointB())
        r = solid.getRadius() * mat.getRow3(0).length()
        axis = Vec3(b[0] - a[0], b[1] - a[1], 0)
        length = axis.length()
        c = Point3(pos[0], pos[1], 0)
        if length < 1e-3:
            near = Point3(a[0], a[1], 0)
        else:
            axis /= length
            t = max(0.0, min(length, (c - Point3(a[0], a[1], 0)).dot(axis)))
            near = Point3(a[0], a[1], 0) + axis * t
        out = c - near
        if out.length() < 0.05:
            if length < 1e-3:
                return None, 0
            # Right on its line: toward where the toon came from.
            out = Vec3(-axis[1], axis[0], 0)
            back = Vec3(self.safePos[0] - pos[0], self.safePos[1] - pos[1], 0)
            if back.dot(out) < 0:
                out = -out
        depth = r + PUSH_RADIUS - out.length()
        if depth <= 0:
            return None, 0
        out.normalize()
        return out, depth

    def __unwedge(self, moved):
        """Big maps: a toon trying to walk that hasn't moved for a few
        frames and is sunk into something solid (between two posts, on a
        rail's line, in a gap narrower than itself) is wedged: no push gets
        it out, so put it on the nearest spot that's clear."""
        trying = not self.game.inMenu() and any(inputState.isSet(t) for t in ('forward', 'reverse') + SLIDE_TOKENS)
        if not trying or moved[0] * moved[0] + moved[1] * moved[1] > 0.0004:
            self.stillFrames = 0
            return
        self.stillFrames = getattr(self, 'stillFrames', 0) + 1
        if self.stillFrames < 4:
            return
        self.stillFrames = 0
        here = self.body.getPos()
        if not self.__overlaps(here):
            return
        for ring in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
            for k in range(16):
                a = k * math.pi / 8
                spot = Point3(here[0] + math.cos(a) * ring, here[1] + math.sin(a) * ring, here[2])
                # Out of the solid it's sunk in, not through a wall beyond.
                if not self.__overlaps(spot) and not self.__crossesWall(spot, here, near=here, within=1.5):
                    self.body.setPos(spot)
                    self.safePos = Point3(spot)
                    self.notify.info('unwedged the toon from %s to %s' % (here, spot))
                    return

    def __overlaps(self, pos):
        from panda3d.core import (CollisionHandlerQueue, CollisionNode, CollisionSphere,
                                  CollisionTraverser)
        if not hasattr(self, 'probeTrav'):
            node = CollisionNode('survivalProbe')
            # A little smaller than the toon: a toon only touching a wall
            # (walking into it) isn't wedged.
            node.addSolid(CollisionSphere(0, 0, 1.4, 1.25))
            node.setFromCollideMask(ToontownGlobals.WallBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            self.probeNode = render.attachNewNode(node)
            self.probeQueue = CollisionHandlerQueue()
            self.probeTrav = CollisionTraverser('survivalProbe')
            self.probeTrav.addCollider(self.probeNode, self.probeQueue)
        self.probeNode.setPos(pos)
        self.probeQueue.clearEntries()
        self.probeTrav.traverse(self.game.arena.root)
        return self.probeQueue.getNumEntries() > 0

    def __crossesWall(self, a, b, near=None, within=0.0):
        from panda3d.core import (CollisionHandlerQueue, CollisionNode, CollisionSegment,
                                  CollisionTraverser)
        if not hasattr(self, 'guardTrav'):
            self.guardSeg = CollisionSegment()
            node = CollisionNode('survivalGuard')
            node.addSolid(self.guardSeg)
            node.setFromCollideMask(ToontownGlobals.WallBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            self.guardNode = render.attachNewNode(node)
            self.guardQueue = CollisionHandlerQueue()
            self.guardTrav = CollisionTraverser('survivalGuard')
            self.guardTrav.addCollider(self.guardNode, self.guardQueue)
        # At the middle of the wall sphere (radius 1.4, sitting on the floor).
        self.guardSeg.setPointA(a[0], a[1], a[2] + 1.4)
        self.guardSeg.setPointB(b[0], b[1], b[2] + 1.4)
        self.guardQueue.clearEntries()
        self.guardTrav.traverse(self.game.arena.root)
        start = Point3(a[0], a[1], a[2] + 1.4)
        for i in range(self.guardQueue.getNumEntries()):
            entry = self.guardQueue.getEntry(i)
            hit = entry.getSurfacePoint(render)
            # A hit right where the step began is a toon that was already
            # in a solid (a squeeze, a landing): let the walls push it out.
            if (hit - start).length() > 0.1:
                if near is not None and (Vec3(hit[0] - near[0], hit[1] - near[1], 0)).length() <= within:
                    continue
                return True
        return False

    def __tick(self, task):
        dt = globalClock.getDt()
        if self.game.paused:
            self.__footsteps(off=True)
            return task.cont
        inMenu = self.game.inMenu()
        if inMenu:
            self.lookDelta = Vec3(0)
        else:
            self.__readMouse()
        if self.lookDelta.lengthSquared() > 0:
            self.body.setH(self.body.getH() + self.lookDelta[0])
            self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch + self.lookDelta[1]))
            self.lookDelta = Vec3(0)
        self.head.setP(self.pitch)
        camera.reparentTo(self.head)
        camera.setPosHpr(0, 0, 0, 0, 0, 0)
        # BO1's sprint: forward only, burns the meter, and once the meter
        # runs dry the sprint stops until the button is let go and pressed
        # again (with at least SPRINT_MIN back in the meter).
        forward = inputState.isSet('forward')
        moving = forward or any(inputState.isSet(token) for token in ('reverse',) + SLIDE_TOKENS)
        soda = self.game.hasTonic('sprint')
        speedScale = G.SPRINT_SODA_SPEED if soda else 1.0
        sprintTime = G.SPRINT_TIME * (G.SPRINT_SODA_TIME if soda else 1.0)
        now = globalClock.getFrameTime()
        wantSprint = self.sprinting and forward and not self.down and not inMenu and not self.sprintSpent
        if wantSprint and not self.sprintActive and self.stamina < G.SPRINT_MIN:
            wantSprint = False
        if wantSprint and self.stamina > 0:
            self.sprintActive = True
            self.stamina = max(0.0, self.stamina - dt)
            self.lastSprint = now
            speed = G.SPRINT_SPEED * speedScale
            if self.stamina <= 0:
                # Out of breath: no more until the button is pressed again.
                self.sprintSpent = True
                self.sprintActive = False
        else:
            self.sprintActive = False
            if now - self.lastSprint > G.SPRINT_RECOVER_PAUSE:
                self.stamina = min(sprintTime, self.stamina + dt * sprintTime / G.SPRINT_RECOVER)
            speed = G.WALK_SPEED * speedScale
        self.stamina = min(self.stamina, sprintTime)
        reverse = G.WALK_SPEED * speedScale * G.REVERSE_SCALE
        if self.down:
            # Downed: a slow crawl any way, no sprint, no jump (BO1's last
            # stand; before, a downed toon couldn't move at all).
            speed = reverse = G.DOWN_CRAWL_SPEED
        if inMenu:
            speed = 0.0
            reverse = 0.0
        self.walker.setWalkSpeed(speed, 0 if inMenu or self.down else G.JUMP_FORCE, reverse, 0)
        if self.down or not moving or speed <= 0:
            self.moveState = 'idle'
        elif self.sprintActive:
            self.moveState = 'run'
        else:
            self.moveState = 'walk'
        self.__footsteps()
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

    def __footsteps(self, off=False):
        want = None
        if not off and self.moveState in self.stepSounds and not getattr(self.walker, 'isAirborne', False):
            want = self.moveState
        if want == self.stepPlaying:
            return
        if self.stepPlaying is not None:
            self.stepSounds[self.stepPlaying].stop()
        self.stepPlaying = want
        if want is not None:
            self.stepSounds[want].play()

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
        # Laff comes back a fraction at a time, so after the regen a hit
        # could leave 0.4: the meter said 0 and the toon stayed up (Arthur,
        # with Toon-Up and Second Wind). Under one point is down.
        if self.hp < 1:
            self.hp = 0
            self.goDown()
        self.game.hud.setLaff(self.hp, self.maxHp)
        self.game.hud.flashHurt()
        # A thump on every hit, as a toon gets when a cog lands one (Arthur).
        if self.hitSound is None:
            self.hitSound = base.loader.loadSfx(HIT_SOUND) or False
        if self.hitSound:
            self.hitSound.setVolume(1.0)
            self.hitSound.setPlayRate(random.uniform(0.95, 1.05))
            self.hitSound.play()

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
        self.game.hud.setDowned(False)

    def setMaxHp(self, maxHp):
        self.maxHp = maxHp
        self.hp = min(self.hp, maxHp) if self.hp < maxHp else maxHp
        self.game.hud.setLaff(self.hp, self.maxHp)
