"""NPC toons working the CFO's cranes on the player's screen.

Offline, the player's game is the only client, and a crane is worked from
its controlling toon's client: the arm swings and slides, the cable swings by
physics, the magnet picks things up, and a dropped safe or goon flies off on
its own and hits the CFO (or not). An NPC has no client of its own, so the
player's game works an NPC's crane here, the way a player at the controls
would: NPCBossCrew only says where the arm should go (as a player holds the
arrow keys) and when to grab or let go; where the safe flies and whether it
hits is down to the swing, as for anyone.
"""

import math

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task

notify = DirectNotifyGlobal.directNotify.newCategory('NPCCraneOperator')

# The NPC toons (by doId) whose cranes and objects this game works, and the
# district they belong to (to send their requests as theirs).
npcIds = set()
air = [None]
# The district's execution context (what it hears runs there, with its own
# task manager and builtins, even when the player's game saw it).
aiContext = [None]
# craneDoId -> (crane y, arm h) the NPC is steering for, or None to hold.
targets = {}
# How close the arm counts as there.
H_SLACK = 1.5
Y_SLACK = 0.4

_installed = [False]


def isNPC(avId):
    return avId in npcIds


def asNPC(avId, doId, method, *args):
    """Calls the district's object method as the NPC's client would."""
    a = air[0]
    if a is None:
        return
    obj = a.doId2do.get(doId)
    if obj is None:
        return
    from otp.local import ExecutionContext
    contexts = ExecutionContext.contexts
    if contexts is None or aiContext[0] is None:
        return a.callAsSender(avId, getattr(obj, method), *args)
    with contexts.use(aiContext[0]):
        return a.callAsSender(avId, getattr(obj, method), *args)


def onClient(func, *args):
    """Runs func with the player's game's task manager and builtins."""
    from otp.local import ExecutionContext
    contexts = ExecutionContext.contexts
    if contexts is None:
        return func(*args)
    with contexts.use(contexts.client):
        return func(*args)


def _rememberContext():
    from otp.local import ExecutionContext
    contexts = ExecutionContext.contexts
    if contexts is not None and contexts.current is not contexts.client:
        aiContext[0] = contexts.current


def install(theAir):
    air[0] = theAir
    _rememberContext()
    if _installed[0]:
        return
    _installed[0] = True
    from toontown.coghq.DistributedCashbotBossCrane import DistributedCashbotBossCrane as Crane
    from toontown.coghq.DistributedCashbotBossObject import DistributedCashbotBossObject as Obj

    # --- The crane ---
    origEnter = Crane.enterControlled
    origExit = Crane.exitControlled

    def enterControlled(self, avId):
        _ownBits(self)
        origEnter(self, avId)
        if isNPC(avId) and self.avId == avId:
            # As at its own controls: the arm moves here, the cable swings.
            self.stopSmooth()
            self._DistributedCashbotBossCrane__activatePhysics()
            self.npcWorked = avId
            taskMgr.add(_drive, self.uniqueName('npcCrane'), extraArgs=[self], appendTask=True)

    def exitControlled(self):
        npc = getattr(self, 'npcWorked', None)
        taskMgr.remove(self.uniqueName('npcCrane'))
        origExit(self)
        if npc is not None:
            self.npcWorked = None
            targets.pop(self.doId, None)
            self._DistributedCashbotBossCrane__setMoveSound(None)
            self._DistributedCashbotBossCrane__deactivatePhysics()

    Crane.enterControlled = enterControlled
    origSetup = Crane.setupCable

    def setupCable(self):
        origSetup(self)
        _ownBits(self)

    Crane.setupCable = setupCable
    Crane.exitControlled = exitControlled

    # --- What it drops: flown here, by the swing ---
    origEnterDropped = Obj.enterDropped
    origExitDropped = Obj.exitDropped
    origEnterSliding = Obj.enterSlidingFloor
    origExitSliding = Obj.exitSlidingFloor

    def enterDropped(self, avId, craneId):
        if not isNPC(avId):
            return origEnterDropped(self, avId, craneId)
        self.avId = avId
        self.craneId = craneId
        self.crane = self.cr.doId2do.get(craneId)
        self.npcFlown = avId
        self.activatePhysics()
        self.handler.setStaticFrictionCoef(0)
        self.handler.setDynamicFrictionCoef(0)
        self.hideShadows()

    def exitDropped(self):
        if getattr(self, 'npcFlown', None) is None:
            return origExitDropped(self)
        if self.newState != 'SlidingFloor':
            self.deactivatePhysics()
            self.npcFlown = None
        del self.crane
        self.showShadows()

    def enterSlidingFloor(self, avId):
        if not isNPC(avId):
            return origEnterSliding(self, avId)
        self.avId = avId
        self.npcFlown = avId
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        self.activatePhysics()
        self.handler.setStaticFrictionCoef(0.9)
        self.handler.setDynamicFrictionCoef(0.5)
        if self.wantsWatchDrift:
            taskMgr.add(_watchDrift, self.uniqueName('npcDrift'), extraArgs=[self], appendTask=True)
        self.hitFloorSoundInterval.start()

    def exitSlidingFloor(self):
        if getattr(self, 'npcFlown', None) is None:
            return origExitSliding(self)
        taskMgr.remove(self.uniqueName('npcDrift'))
        self.deactivatePhysics()
        self.npcFlown = None

    Obj.enterDropped = enterDropped
    Obj.exitDropped = exitDropped
    Obj.enterSlidingFloor = enterSlidingFloor
    Obj.exitSlidingFloor = exitSlidingFloor

    # What it hits is told to the district as the NPC's doing.
    origHitBoss = Obj.d_hitBoss
    origHitFloor = Obj.d_hitFloor
    origRequestFree = Obj.d_requestFree

    def d_hitBoss(self, impact):
        npc = getattr(self, 'npcFlown', None)
        if npc is None:
            return origHitBoss(self, impact)
        notify.info('NPC %d: %s hits the CFO, impact %.2f' % (npc, self.doId, impact))
        asNPC(npc, self.doId, 'hitBoss', min(1.0, impact))

    def d_hitFloor(self):
        npc = getattr(self, 'npcFlown', None)
        if npc is None:
            return origHitFloor(self)
        asNPC(npc, self.doId, 'hitFloor')

    def d_requestFree(self):
        npc = getattr(self, 'npcFlown', None)
        if npc is None:
            return origRequestFree(self)
        asNPC(npc, self.doId, 'requestFree', self.getX(), self.getY(), self.getZ(), self.getH())

    Obj.d_hitBoss = d_hitBoss
    Obj.d_hitFloor = d_hitFloor
    Obj.d_requestFree = d_requestFree

    # A floor hit hands the slide to whoever's game saw it: the NPC's here.
    origDemand = Obj.demand

    def demand(self, state, *args):
        npc = getattr(self, 'npcFlown', None)
        if npc is not None and state == 'SlidingFloor' and args and args[0] != npc:
            args = (npc,) + tuple(args[1:])
        return origDemand(self, state, *args)

    Obj.demand = demand


# Online each client swings only its own crane's cable, so every crane's
# cable links use the same collision bits (21-23). Here several swing at
# once, and one crane's links would catch in another's shells (the cable
# flying off hundreds of feet): each crane gets bits of its own.
CRANE_BITS = (21, 12, 15, 18)


def _ownBits(crane):
    from panda3d.core import BitMask32
    first = CRANE_BITS[crane.index % len(CRANE_BITS)] if crane.index is not None else 21
    shells = {}
    for np in crane.collisions:
        name = np.getName()
        if name.startswith('shell'):
            shells[int(name[5:])] = np
    for linkNum, (an, anp, cnp) in enumerate(crane.activeLinks):
        mask = BitMask32.bit(first + linkNum)
        cnp.node().setFromCollideMask(mask)
        shell = shells.get(linkNum)
        if shell is not None:
            shell.node().setIntoCollideMask(mask)


def _watchDrift(obj, task):
    v = obj.physicsObject.getVelocity()
    if abs(v[0]) < 0.0001 and abs(v[1]) < 0.0001:
        obj.d_requestFree()
        obj.demand('Free')
        return Task.done
    return Task.cont


def _drive(crane, task):
    """The NPC at the controls: holds the arrows towards its target."""
    if crane.isDisabled() if hasattr(crane, 'isDisabled') else False:
        return Task.done
    target = targets.get(crane.doId)
    xd = yd = 0
    if target is not None:
        y, h = target
        dh = h - crane.arm.getH()
        if abs(dh) > H_SLACK:
            # (A positive xd turns the arm's heading down.)
            xd = -1 if dh > 0 else 1
        dy = y - crane.crane.getY()
        if abs(dy) > Y_SLACK:
            yd = 1 if dy > 0 else -1
    if xd or yd:
        crane._DistributedCashbotBossCrane__moveCraneArcHinge(xd, yd)
    else:
        crane._DistributedCashbotBossCrane__setMoveSound(None)
    return Task.cont


def reachFor(crane, worldPoint):
    """The (crane y, arm h) that puts the magnet over worldPoint, within the
    crane's reach, or None."""
    p = crane.arm.getParent().getRelativePoint(_render(), worldPoint)
    dist = math.hypot(p[0], p[1])
    h = math.degrees(math.atan2(-p[0], p[1]))
    if not (crane.armMinH - 0.5 <= h <= crane.armMaxH + 0.5):
        return None
    if not (crane.craneMinY - 1.0 <= dist <= crane.craneMaxY + 1.0):
        return None
    return (max(min(dist, crane.craneMaxY), crane.craneMinY), max(min(h, crane.armMaxH), crane.armMinH))


def _render():
    from otp.local.ExecutionContext import getClientBuiltin
    return getClientBuiltin('base').render


def magnetPos(crane):
    """Where the magnet hangs, on the player's screen."""
    for name in ('gripper', 'bottomLink'):
        np = getattr(crane, name, None)
        if np is not None and not np.isEmpty():
            return np.getPos(_render())
    return crane.crane.getPos(_render())
