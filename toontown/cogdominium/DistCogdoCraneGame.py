import math

from panda3d import core as PM
from panda3d.physics import LinearEulerIntegrator, LinearVectorForce, ForceNode, PhysicsManager
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed.ClockDelta import globalClockDelta
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.interval.IntervalGlobal import (Func, LerpHprInterval, LerpPosInterval, LerpScaleInterval, Parallel,
                                            Sequence, SoundInterval, Wait)
from direct.task.Task import Task
from otp.otpbase import OTPGlobals
from toontown.cogdominium.DistCogdoGame import DistCogdoGame
from toontown.cogdominium import CogdoCraneGameMovies
from toontown.cogdominium.CogdoCraneRoom import CogdoCraneRoom
from toontown.cogdominium import CogdoCraneGameConsts as GameConsts
from toontown.cogdominium.CogdoCraneGameBase import CogdoCraneGameBase
from toontown.toonbase import ToontownTimer
from toontown.toonbase import TTLocalizer as TTL
from toontown.toonbase import ToontownGlobals

# The cables' and bags' physics step at most this long, up to this many
# steps a frame.
PhysicsStep = 1.0 / 60
PhysicsMaxSteps = 6


class DistCogdoCraneGame(CogdoCraneGameBase, DistCogdoGame):
    """The Vend-A-Stomper (the Cashbot field office): the cranes, money
    bags and cogs are their own distributed objects; this keeps the room,
    the physics they share, the barrel count and the Stomp-O-Matic."""
    notify = directNotify.newCategory('DistCogdoCraneGame')

    def __init__(self, cr):
        DistCogdoGame.__init__(self, cr)
        self.cranes = {}
        self.moneyBags = {}
        self.cogs = {}
        self.barrelsLeft = GameConsts.NumBarrels
        self.coins = 0
        self.heldObject = None
        self.stunCount = 0
        self.room = None
        self.gui = None
        self._stompIval = None
        self._introMovie = None

    def getTitle(self):
        return TTL.CogdoCraneGameTitle

    def getInstructions(self):
        return TTL.CogdoCraneGameInstructions

    def announceGenerate(self):
        DistCogdoGame.announceGenerate(self)
        self.timer = ToontownTimer.ToontownTimer()
        self.timer.stash()

    def disable(self):
        self.timer.destroy()
        self.timer = None
        DistCogdoGame.disable(self)

    # --- Loading ---

    def enterLoaded(self):
        DistCogdoGame.enterLoaded(self)
        self.lightning = loader.loadModel('phase_10/models/cogHQ/CBLightning')
        self.magnet = loader.loadModel('phase_10/models/cogHQ/CBMagnet')
        self.craneArm = loader.loadModel('phase_10/models/cogHQ/CBCraneArm')
        self.controls = loader.loadModel('phase_10/models/cogHQ/CBCraneControls')
        self.stick = loader.loadModel('phase_10/models/cogHQ/CBCraneStick')
        self.cableTex = self.craneArm.findTexture('MagnetControl')
        self.moneyBag = loader.loadModel('phase_10/models/cashbotHQ/MoneyBag')
        self.coinModel = loader.loadModel('phase_10/models/cashbotHQ/CBCoin1')
        self.geomRoot = PM.NodePath('geom')
        self.room = CogdoCraneRoom()
        self.room.load().reparentTo(self.geomRoot)
        self.sceneRoot = self.geomRoot.attachNewNode('sceneRoot')
        # The cranes' objects fall out of the world here and go back.
        plane = PM.CollisionPlane(PM.Plane(PM.Vec3(0, 0, 1), PM.Point3(0, 0, -50)))
        planeNode = PM.CollisionNode('dropPlane')
        planeNode.addSolid(plane)
        planeNode.setCollideMask(ToontownGlobals.PieBitmask)
        self.geomRoot.attachNewNode(planeNode)
        self.physicsMgr = PhysicsManager()
        self.physicsMgr.attachLinearIntegrator(LinearEulerIntegrator())
        fn = ForceNode('gravity')
        self.fnp = self.geomRoot.attachNewNode(fn)
        gravity = LinearVectorForce(0, 0, GameConsts.Gravity)
        fn.addForce(gravity)
        self.physicsMgr.addLinearForce(gravity)
        # The cables and money bags collide in their own traversal, run
        # with every physics step (see _doPhysics).
        self.physicsTrav = PM.CollisionTraverser('cranePhysics')
        self.stompSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_FACT_stomper_large.ogg')
        self.raiseSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_FACT_stomper_raise.ogg')
        self.coinSfx = loader.loadSfx('phase_4/audio/sfx/MG_maze_pickup.ogg')
        self.crushSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_safe.ogg')
        self.hitSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.music = loader.loadMusic('phase_9/audio/bgm/encntr_suit_CBHQ_nbrhood.ogg')
        self._loadGui()

    def exitLoaded(self):
        self._finishStomp()
        if self._introMovie:
            self._introMovie.end()
            self._introMovie.unload()
            self._introMovie = None
        self.music.stop()
        self._unloadGui()
        self.fnp.removeNode()
        self.physicsMgr.clearLinearForces()
        self.room.destroy()
        self.room = None
        self.geomRoot.removeNode()
        for model in (self.lightning, self.magnet, self.craneArm, self.controls, self.stick, self.moneyBag, self.coinModel):
            model.removeNode()
        DistCogdoGame.exitLoaded(self)

    def _loadGui(self):
        # The barrels left and how full the machine is, top left; the clock
        # is top right.
        self.gui = DirectFrame(parent=base.a2dTopLeft, relief=None, pos=(0.32, 0, -0.2))
        barrel = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_cbr_laughBarrel')
        barrel.setScale(0.045)
        barrel.setHpr(30, 10, 0)
        barrel.reparentTo(self.gui)
        barrel.setPos(-0.17, 0, -0.07)
        barrel.setDepthTest(1)
        barrel.setDepthWrite(1)
        self.barrelLabel = DirectLabel(parent=self.gui, relief=None, text='', text_scale=0.08, text_fg=(1, 1, 1, 1),
                                       text_shadow=(0, 0, 0, 1), text_align=PM.TextNode.ALeft, text_font=ToontownGlobals.getSignFont(),
                                       pos=(-0.08, 0, -0.04))
        self.coinLabel = DirectLabel(parent=self.gui, relief=None, text='', text_scale=0.055, text_fg=(1, 0.9, 0.4, 1),
                                     text_shadow=(0, 0, 0, 1), text_align=PM.TextNode.ALeft, pos=(-0.2, 0, -0.16))
        self.gui.hide()
        self._updateGui()

    def _unloadGui(self):
        if self.gui:
            self.gui.destroy()
        self.gui = None

    def _updateGui(self):
        if not self.gui:
            return
        self.barrelLabel['text'] = TTL.CogdoCraneBarrelsLeft % self.barrelsLeft
        self.coinLabel['text'] = TTL.CogdoCraneCoins % (self.coins, GameConsts.CoinsPerStomp)

    def getSceneRoot(self):
        return self.sceneRoot

    def placeEntranceElev(self, elev):
        elev.setPosHpr(*GameConsts.ElevatorPosHpr)

    # --- States ---

    def enterVisible(self):
        DistCogdoGame.enterVisible(self)
        self.geomRoot.reparentTo(render)

    def enterIntro(self):
        # The title and clock in the panel, and the Loan Shark and the Toon
        # Resistance talking in its bubble a page at a time, as the other
        # field offices do it.
        DistCogdoGame.enterIntro(self, CogdoCraneGameMovies.IntroDurationSeconds)
        self._introMovie = CogdoCraneGameMovies.CogdoCraneGameIntro(self.doId)
        self._introMovie.load(self.sceneRoot)
        self._introMovie.play()
        base.playMusic(self.music, looping=1, volume=0.8)

    def exitIntro(self):
        if self._introMovie:
            self._introMovie.end()
            self._introMovie.unload()
            self._introMovie = None
        DistCogdoGame.exitIntro(self)
        self.stashEntranceElevator()

    def enterGame(self):
        DistCogdoGame.enterGame(self)
        self._physicsTask = taskMgr.add(self._doPhysics, self.uniqueName('physics'), priority=25)
        self._hitTask = taskMgr.add(self._checkHits, self.uniqueName('hits'), priority=26)
        self._lastGoodPos = None
        self._roomTask = taskMgr.add(self._keepInRoom, self.uniqueName('keepInRoom'), priority=40)
        self._startTimer()
        self.gui.show()
        self._placeToons()
        camera.reparentTo(base.localAvatar)
        camera.setPosHpr(base.localAvatar.cameraPositions[0][0], PM.VBase3(0, 0, 0))
        place = base.cr.playGame.getPlace()
        if place and place.fsm.getCurrentState().getName() != 'walk':
            place.fsm.request('walk')

    def _placeToons(self):
        # Out of the elevator, side by side, facing the machine.
        toonIds = self.getToonIds()
        for i, toonId in enumerate(toonIds):
            toon = self.getToon(toonId)
            if toon is None or toon.isEmpty():
                continue
            x = (i - (len(toonIds) - 1) / 2.0) * 4.0
            if toon.isLocal():
                toon.setPosHpr(render, x, GameConsts.ElevatorPosHpr[1] + 10, 0, 0, 0, 0)
                toon.sendCurrentPosition()

    def _keepInRoom(self, task):
        # The walls round the piles are only boxes, and a toon running fast
        # at a low frame rate, or squeezed into a corner, can come out the
        # far side of one. Anywhere off the floor, the hallways and the
        # pockets, it goes back to where it last stood on them.
        toon = base.localAvatar
        if toon.isEmpty() or self.room is None:
            return Task.cont
        pos = toon.getPos(render)
        if self.room._inPlayArea(pos[0], pos[1], margin=-1.5) and pos[2] < 6:
            self._lastGoodPos = pos
        elif self._lastGoodPos is not None:
            toon.setPos(render, self._lastGoodPos)
        else:
            toon.setPos(render, 0, GameConsts.ElevatorPosHpr[1] + 10, 0)
        return Task.cont

    def _startTimer(self):
        timeLeft = GameConsts.GameDuration - (globalClock.getFrameTime() - self.getStartTime())
        self.timer.posInTopRightCorner()
        self.timer.setTime(timeLeft)
        self.timer.countdown(timeLeft, self.timerExpired)
        self.timer.unstash()

    def _doPhysics(self, task):
        # In small steps: at a low frame rate one big step lets the cables
        # whip about and the bags on them swing wildly.
        dt = min(globalClock.getDt(), 0.25)
        steps = max(1, min(PhysicsMaxSteps, int(math.ceil(dt / PhysicsStep))))
        cranes = [crane for crane in self.cranes.values() if crane.physicsActivated]
        for i in range(steps):
            self.physicsMgr.doPhysics(dt / steps)
            for crane in cranes:
                crane.linkTrav.traverse(crane.hinge)
            self.physicsTrav.traverse(render)
        return Task.cont

    def _checkHits(self, task):
        # A money bag dropped by a crane the local client runs (the
        # player's, or an NPC toon's) knocks over a cog it lands on. One
        # still on the magnet, or lying on the floor, does nothing.
        for bag in list(self.moneyBags.values()):
            if not bag.isRunHere() or bag.state not in ('LocalDropped', 'Dropped'):
                continue
            pos = bag.getPos(render)
            for cog in list(self.cogs.values()):
                if cog.canBeHit() and cog.isHitBy(pos):
                    cog.markHit()
                    bag.d_hitCog(cog.doId)
        return Task.cont

    def exitGame(self):
        taskMgr.remove(self._physicsTask)
        taskMgr.remove(self._hitTask)
        taskMgr.remove(self._roomTask)
        self.timer.stop()
        self.timer.stash()
        DistCogdoGame.exitGame(self)

    def enterFinish(self):
        DistCogdoGame.enterFinish(self)
        self.music.stop()
        place = base.cr.playGame.getPlace()
        if place:
            state = place.fsm.getCurrentState().getName()
            if state == 'crane':
                place.fsm.request('walk')
                state = 'walk'
            if state == 'walk':
                place.fsm.request('stopped')
        self.gui.hide()
        self.finishLabel = DirectLabel(relief=None, text=TTL.CogdoCraneGameFinish % self.barrelsLeft if self.barrelsLeft
                                       else TTL.CogdoCraneGameAllSmashed, text_scale=0.09, text_fg=(1, 1, 0.6, 1),
                                       text_shadow=(0, 0, 0, 1), text_font=ToontownGlobals.getSignFont(),
                                       text_wordwrap=18, pos=(0, 0, 0.45))

    def exitFinish(self):
        if getattr(self, 'finishLabel', None):
            self.finishLabel.destroy()
            self.finishLabel = None
        DistCogdoGame.exitFinish(self)

    def timerExpired(self):
        pass

    def isPlaying(self):
        return self.fsm is not None and self.fsm.getCurrentState().getName() == 'Game'

    def runsHere(self, avId):
        # Whose cranes and money bags this client runs: its own toon's, and
        # offline every other toon at a crane is an NPC with no client of
        # its own, so theirs too. (Only toons in the game can take one.)
        return bool(avId)

    def cogStunned(self, cog):
        self.stunCount += 1
        base.playSfx(self.hitSfx, node=cog)

    # --- Crane modes, for the cranes ---

    def toCraneMode(self):
        place = self.cr.playGame.getPlace() if self.cr else None
        if place and hasattr(place, 'fsm'):
            place.setState('crane')

    def toWalkMode(self):
        place = self.cr.playGame.getPlace() if self.cr else None
        if place and hasattr(place, 'fsm') and place.fsm.getCurrentState().getName() == 'crane':
            place.setState('walk')

    # --- The Stomp-O-Matic ---

    def setBarrels(self, barrelsLeft, coins):
        self.barrelsLeft = barrelsLeft
        self.coins = coins
        self._updateGui()

    def coinIn(self, cog):
        # A cog put a coin in: the machine's drum lights up for it.
        if self.room and self.room.stomper:
            drum = self.room.stomperDrum
            Sequence(Func(drum.setColorScale, 1.6, 1.5, 0.6, 1), Wait(0.4), Func(drum.clearColorScale)).start()
            base.playSfx(self.coinSfx, node=self.room.stomper)

    def stomp(self, barrelsLeft, timestamp):
        # The machine is full: its spikes pound down and the next laff
        # barrel on the belt is crushed.
        self.barrelsLeft = barrelsLeft
        self.coins = 0
        self._updateGui()
        if not self.room:
            return
        self._finishStomp()
        index = GameConsts.NumBarrels - barrelsLeft - 1
        barrels = self.room.barrels
        barrel = barrels[index] if 0 <= index < len(barrels) else None
        spikes = self.room.stomperSpikes
        stomper = self.room.stomper
        track = Sequence(
            Parallel(SoundInterval(self.raiseSfx, node=stomper),
                     LerpPosInterval(spikes, 0.5, PM.Point3(0, 0, 2.5), blendType='easeOut')),
            Parallel(SoundInterval(self.stompSfx, node=stomper),
                     LerpPosInterval(spikes, 0.12, PM.Point3(0, 0, -1.2), blendType='easeIn'),
                     Sequence(LerpScaleInterval(stomper, 0.12, PM.Vec3(1.08, 1.08, 0.92)),
                              LerpScaleInterval(stomper, 0.3, PM.Vec3(1, 1, 1)))),
            LerpPosInterval(spikes, 0.3, PM.Point3(0, 0, 0)))
        if barrel is not None and not barrel.isEmpty():
            # The barrel the machine is wired to: squashed flat, then gone.
            scale = barrel.getScale()
            track = Parallel(track, Sequence(
                Wait(0.55),
                Func(base.playSfx, self.crushSfx, node=barrel),
                LerpScaleInterval(barrel, 0.15, PM.Vec3(scale[0] * 1.4, scale[1] * 1.4, scale[2] * 0.1)),
                Wait(0.6),
                Func(barrel.hide)))
        self._stompIval = track
        track.start(globalClockDelta.localElapsedTime(timestamp, bits=16))
        if base.localAvatar:
            base.localAvatar.setSystemMessage(0, TTL.CogdoCraneBarrelSmashed % barrelsLeft)

    def _finishStomp(self):
        if self._stompIval:
            self._stompIval.finish()
            self._stompIval = None
