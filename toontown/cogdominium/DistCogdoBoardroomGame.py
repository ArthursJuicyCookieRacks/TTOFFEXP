import math
import random

from panda3d import core as PM
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed.ClockDelta import globalClockDelta
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpFunctionInterval, LerpColorScaleInterval, LerpHprInterval, LerpPosInterval,
                                            LerpScaleInterval, Parallel, ProjectileInterval, Sequence, SoundInterval, Wait)
from direct.task.Task import Task
from otp.otpbase import OTPGlobals
from toontown.battle import BattleProps
from toontown.cogdominium.DistCogdoGame import DistCogdoGame
from toontown.cogdominium.CogdoBoardroomGameBase import CogdoBoardroomGameBase
from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
from toontown.cogdominium import CogdoBoardroomLayout as Layout
from toontown.cogdominium.CogdoBoardroomRoom import CogdoBoardroomRoom
from toontown.cogdominium.CogdoBoardroomGolf import CogdoBoardroomGolf
from toontown.cogdominium.CogdoBoardroomDecor import CogdoBoardroomDecor
from otp.nametag.NametagConstants import CFSpeech, CFTimeout
from toontown.cogdominium import CogdoUtil
from toontown.building.ElevatorConstants import ElevatorPoints, ELEVATOR_NORMAL
from toontown.building import ElevatorUtils
from toontown.suit import Suit, SuitDNA
from toontown.toonbase import ToontownTimer
from toontown.toonbase import TTLocalizer as TTL
from toontown.toonbase import ToontownGlobals


class DistCogdoBoardroomGame(CogdoBoardroomGameBase, DistCogdoGame):
    """Boardroom Hijinks, the Bossbot field office (see
    CogdoBoardroomGameConsts). The AI picks what is thrown where and when;
    this client shows it, and tells the AI when its own toon is hit, picks
    up a memo or a power-up, or reaches the exit."""
    notify = directNotify.newCategory('DistCogdoBoardroomGame')

    def __init__(self, cr):
        DistCogdoGame.__init__(self, cr)
        self.layout = None
        self.room = None
        self.bosses = {}
        self.minions = []
        self.chairman = None
        self.memosGone = set()
        self.powerUpsGone = set()
        self.carried = 0
        self.banked = 0
        self.exited = set()
        self.landings = []
        self.thrownSlicks = []
        self.slicks = {}
        self.thrownSlicks = []
        self.ivals = []
        self.invulnerableUntil = 0
        self.hopUntil = 0
        self.lastHitTime = -99
        self.slideVel = PM.Vec3(0, 0, 0)
        self.lastPos = None
        self.lastProgress = 0
        self.gui = None
        self.timer = None
        self._introMovie = None
        self.golf = None
        self.phase = 'slide'
        self.golfStartTime = None
        self.barrelsHome = Consts.NumBarrels
        # Barrels the cogs got all the way into an elevator with: only those
        # are lost (the count shows the rest as the toons').
        self.barrelsLost = 0
        self.clubs = {}
        self._elevatorTracks = {}
        self._golfArrival = None
        self._golfIntro = None
        self._camInElevator = False
        self.golfLeaving = False
        self.leftGolf = set()
        self.leftOrder = []
        self._leaveLabel = None

    def getTitle(self):
        return TTL.BoardroomGameTitle

    def getInstructions(self):
        return TTL.BoardroomGameInstructions

    def setLayout(self, seed, difficulty):
        self.layout = Layout.BoardroomLayout(seed, difficulty / 100.0)

    def announceGenerate(self):
        self.timer = ToontownTimer.ToontownTimer()
        self.timer.stash()
        DistCogdoGame.announceGenerate(self)

    def disable(self):
        DistCogdoGame.disable(self)
        if self.timer is not None:
            self.timer.destroy()
            self.timer = None

    def gameTime(self):
        try:
            return globalClock.getFrameTime() - self.getStartTime()
        except AttributeError:
            return 0.0

    # --- Loading ---

    def enterLoaded(self):
        DistCogdoGame.enterLoaded(self)
        self.geomRoot = PM.NodePath('boardroomGeom')
        self.room = CogdoBoardroomRoom(self.layout)
        self.room.load().reparentTo(self.geomRoot)
        self.sceneRoot = self.geomRoot.attachNewNode('sceneRoot')
        self._loadMeeting()
        self.decor = CogdoBoardroomDecor(self.layout, self._makeSuit)
        self.decor.load(self.room.root)
        self._loadProps()
        self.golf = CogdoBoardroomGolf(self)
        self.golf.load(self.geomRoot)
        self._loadGui()
        self.music = loader.loadMusic('phase_12/audio/bgm/Bossbot_CEO_v1.ogg')
        self.hitSfx = loader.loadSfx('phase_5/audio/sfx/tt_s_ara_cmg_toonHit.ogg')
        self.memoSfx = loader.loadSfx('phase_4/audio/sfx/MG_maze_pickup.ogg')
        self.powerSfx = loader.loadSfx('phase_4/audio/sfx/MG_pairing_match_bonus_both.ogg')
        self.swingSfx = loader.loadSfx('phase_5/audio/sfx/SA_tee_off.ogg')
        self.throwSfx = loader.loadSfx('phase_5/audio/sfx/SA_paper_throw.ogg') if hasattr(loader, 'loadSfx') else None
        self.dropSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_anvil.ogg')
        self.landSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.oilSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_FACT_stomper_small.ogg')
        self.exitSfx = loader.loadSfx('phase_5/audio/sfx/elevator_door_open.ogg')
        # The ride to the golf office, as between the other field offices'
        # floors.
        self.openSfx = loader.loadSfx('phase_5/audio/sfx/elevator_door_open.ogg')
        self.closeSfx = loader.loadSfx('phase_5/audio/sfx/elevator_door_close.ogg')
        self.elevatorMusic = loader.loadMusic('phase_7/audio/bgm/tt_elevator.ogg')

    def exitLoaded(self):
        for ival in self.ivals:
            ival.pause()
        self.ivals = []
        self._stopGolfArrival()
        self.elevatorMusic.stop()
        if getattr(self, '_defaultFar', None):
            base.camLens.setFar(self._defaultFar)
            self._defaultFar = None
        if self._introMovie:
            self._introMovie.end()
            self._introMovie.unload()
            self._introMovie = None
        self.music.stop()
        self._unloadGui()
        for suit in list(self.bosses.values()) + [m for m in self.minions] + ([self.chairman] if self.chairman else []):
            suit.cleanup()
            suit.removeNode()
            suit.delete()
        self.bosses = {}
        self.minions = []
        self.chairman = None
        for prop in self.props.values():
            prop.removeNode()
        self.props = {}
        taskMgr.removeTasksMatching(self.uniqueName('hush') + '*')
        self.decor.destroy()
        self.decor = None
        for club in self.clubs.values():
            club.removeNode()
        self.clubs = {}
        self._stopExitClock()
        self.golf.destroy()
        self.golf = None
        self.room.destroy()
        self.room = None
        self.geomRoot.removeNode()
        DistCogdoGame.exitLoaded(self)

    def _makeSuit(self, name, level=None):
        suit = Suit.Suit()
        dna = SuitDNA.SuitDNA()
        dna.newSuit(name)
        suit.setDNA(dna)
        suit.nametag3d.stash()
        suit.nametag.destroy() if False else None
        return suit

    def _loadMeeting(self):
        # The Boss Cogs in their chairs: the hardest offices have the
        # biggest cheeses at the table.
        rng = random.Random(self.layout.seed)
        d = self.layout.difficulty
        names = Consts.BossCogNames
        top = max(1, int(round(2 + d * (len(names) - 2))))
        for index in self.layout.bossSeats():
            suit = self._makeSuit(rng.choice(names[:top]))
            CogdoBoardroomRoom.sitCog(suit, self.room.seatLocators[index], suit.style.body)
            CogdoBoardroomRoom.liftOverTable(suit)
            suit.loop('sit', fromFrame=rng.randrange(20))
            self.bosses[index] = suit
        # The chairman at the head of the table.
        self.chairman = self._makeSuit('tbc')
        sit = CogdoBoardroomRoom.sitCog(self.chairman, self.room.chairmanLocator, self.chairman.style.body)
        # The Big Cheese is the biggest cog of all: the shared seat place
        # put his legs through the seat with him sat behind it (Arthur).
        # Forward and up a touch, onto the seat, his legs over its edge.
        sit.setPos(sit.getX(), sit.getY() + Consts.ChairmanSitForward, sit.getZ() + Consts.ChairmanSitUp)
        self.chairman.loop('sit')
        # The minions overhead, each on its propeller.
        for i, minion in enumerate(self.layout.minions):
            suit = self._makeSuit(minion['name'])
            suit.reparentTo(self.sceneRoot)
            suit.pose('landing', 0)
            prop = BattleProps.globalPropPool.getProp('propeller')
            head = suit.find('**/joint_head')
            prop.reparentTo(head if not head.isEmpty() else suit)
            prop.loop('propeller')
            suit.prop = prop
            suit.setPos(*self.layout.minionPos(i, 0))
            self.minions.append(suit)

    def _loadProps(self):
        self.props = {
            Consts.GolfBall: loader.loadModel('phase_6/models/golf/golf_ball'),
            Consts.Paper: loader.loadModel('phase_5/models/props/newspaper'),
            Consts.Pencil: loader.loadModel('phase_5/models/props/pencil'),
            Consts.Anvil: BattleProps.globalPropPool.getProp('anvil'),
            Consts.Paperwork: loader.loadModel('phase_11/models/lawbotHQ/LB_paper_big_stacks3'),
            Consts.Oil: loader.loadModel('phase_6/models/props/small_round_barrel'),
        }
        self.props[Consts.Oil].setColorScale(0.32, 0.3, 0.26, 1)
        self.propScales = {Consts.GolfBall: 1.4, Consts.Paper: 2.2, Consts.Pencil: 2.6, Consts.Anvil: 1.0, Consts.Paperwork: 0.16,
                           Consts.Oil: 0.35}
        self.marker = loader.loadModel('phase_3/models/props/drop_shadow')

    def _loadGui(self):
        # The memos carried, and those brought out, top left; the clock is
        # top right.
        self.gui = DirectFrame(parent=base.a2dTopLeft, relief=None, pos=(0.3, 0, -0.22))
        icon = self.memoIcon = CogdoUtil.loadModel('memo_card', game='shared', group='gui')
        icon.reparentTo(self.gui)
        icon.setScale(0.18)
        icon.setPos(-0.12, 0, 0)
        self.memoLabel = DirectLabel(parent=self.gui, relief=None, text='', text_scale=0.07, text_fg=(1, 1, 1, 1),
                                     text_shadow=(0, 0, 0, 1), text_align=PM.TextNode.ALeft,
                                     text_font=ToontownGlobals.getSignFont(), pos=(-0.02, 0, -0.025))
        self.barrelLabel = DirectLabel(parent=self.gui, relief=None, text='', text_scale=0.07, text_fg=(1, 1, 1, 1),
                                       text_shadow=(0, 0, 0, 1), text_align=PM.TextNode.ALeft,
                                       text_font=ToontownGlobals.getSignFont(), pos=(-0.02, 0, -0.025))
        self.barrelIcon = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_cbr_laughBarrel')
        self.barrelIcon.reparentTo(self.gui)
        self.barrelIcon.setScale(0.032)
        self.barrelIcon.setPos(-0.12, 0, -0.04)
        self.barrelIcon.setHpr(0, 10, 0)
        self.barrelIcon.hide()
        self.barrelLabel.hide()
        self.statusLabel = DirectLabel(parent=self.gui, relief=None, text='', text_scale=0.05, text_fg=(1, 0.95, 0.5, 1),
                                       text_shadow=(0, 0, 0, 1), text_align=PM.TextNode.ALeft, pos=(-0.2, 0, -0.13))
        self.gui.hide()
        self._updateGui()

    def _unloadGui(self):
        if self.gui:
            self.gui.destroy()
        self.gui = None

    def _updateGui(self):
        if not self.gui:
            return
        self.memoLabel['text'] = TTL.BoardroomMemoCount % (self.carried, self.banked)
        if self.phase == 'golf':
            self.barrelLabel['text'] = TTL.BoardroomBarrelCount % (Consts.NumBarrels - self.barrelsLost, Consts.NumBarrels)
            return
        now = self.gameTime()
        status = []
        if self.invulnerableUntil > now:
            status.append(TTL.BoardroomInvulnerable % int(math.ceil(self.invulnerableUntil - now)))
        if self.hopUntil > now:
            status.append(TTL.BoardroomHop % int(math.ceil(self.hopUntil - now)))
        self.statusLabel['text'] = '\n'.join(status)

    def getSceneRoot(self):
        return self.sceneRoot

    def placeEntranceElev(self, elev):
        elev.setPosHpr(*Consts.ElevatorPosHpr)
        CogdoUtil.addElevatorShell(elev)

    # --- States ---

    def enterVisible(self):
        DistCogdoGame.enterVisible(self)
        self.geomRoot.reparentTo(render)
        # Far enough to see the whole hall from the first frame: with the
        # stock 400 ft the far end was the grey background on arrival.
        self._farView()

    def enterIntro(self):
        from toontown.cogdominium import CogdoBoardroomGameMovies
        DistCogdoGame.enterIntro(self, CogdoBoardroomGameMovies.IntroDurationSeconds)
        CogdoBoardroomGameMovies.centerTitle(self._rulesPanel)
        self._introMovie = CogdoBoardroomGameMovies.CogdoBoardroomGameIntro(self.doId, self)
        self._introMovie.load(self.sceneRoot)
        self._farView()
        self._introMovie.play()
        base.playMusic(self.music, looping=1, volume=0.7)

    def _farView(self):
        # The table is longer than the usual 400 feet the camera sees: the
        # far end showed as a grey wall (in the intro's long shots too).
        if not getattr(self, '_defaultFar', None):
            self._defaultFar = base.camLens.getFar()
        base.camLens.setFar(Consts.TableEnd + 150)

    def exitIntro(self):
        if self._introMovie:
            self._introMovie.end()
            self._introMovie.unload()
            self._introMovie = None
        DistCogdoGame.exitIntro(self)
        self.stashEntranceElevator()
        if self.room:
            self.room.entranceElevator.unstash()

    def enterGame(self):
        DistCogdoGame.enterGame(self)
        self._placeToons()
        self.gui.show()
        self._startTimer()
        self.slideState = 'wait'
        self.slideSpeed = 0.0
        self.steerVel = 0.0
        self.crashUntil = -1
        # The obstacle that last knocked the toon down: it slides on through
        # that one (Arthur), till it is past it.
        self.passOb = None
        self.spinUntil = -1
        self.stuckTime = 0.0
        self.launched = set()
        self._task = taskMgr.add(self._update, self.uniqueName('update'), priority=35)
        place = base.cr.playGame.getPlace()
        self._toWalk(place)
        # The walk controls stay on for the jump, the floors and the walls;
        # the slide below does the moving.
        base.localAvatar.stopTrackAnimToSpeed()
        self._holdControls()
        # The camera follows the slide (see _followCamera), after the smart
        # camera has had its go each frame.
        taskMgr.add(self._cameraTask, self.uniqueName('camera'), sort=40)
        # The table is longer than the usual 400 feet the camera sees: the
        # far end showed as a grey wall.
        self._farView()
        base.localAvatar.setSystemMessage(0, TTL.BoardroomSlideHint)

    def startIndex(self, avId):
        toonIds = list(self.getToonIds())
        return toonIds.index(avId) if avId in toonIds else 0

    def startPos(self, avId):
        toonIds = list(self.getToonIds())
        i = self.startIndex(avId)
        x = (i - (len(toonIds) - 1) / 2.0) * 3.2
        return PM.Point3(x, Consts.TableStart + 2.5, Consts.TableTop)

    def _placeToons(self):
        # Onto the near end of the table, side by side, facing up it.
        toon = base.localAvatar
        toon.setPosHpr(render, self.startPos(toon.doId), PM.VBase3(0, 0, 0))
        toon.sendCurrentPosition()

    def _lockUi(self):
        # No Shticker Book, map, gags, friends, My Looks or off-screen
        # nametags while on the slide or in the golf office, as in the
        # other field offices' games. The walk state (which the slide needs
        # for its jump and collisions) turns them all back on whenever it
        # is entered, so this runs after each time it is.
        toon = base.localAvatar
        if not getattr(self, '_uiLocked', False):
            self._uiLocked = True
            toon.book.obscureButton(1)
            toon.obscureFriendsListButton(1)
            base.setCellsAvailable(base.bottomCells + base.leftCells + base.rightCells, 0)
        toon.gameUiLocked = True
        toon.book.hideButton()
        for page in (toon.questPage, toon.invPage):
            page.ignoreOnscreenHooks()
        toon.questPage.hideQuestsOnscreen()
        toon.invPage.hideInventoryOnscreen()
        # (Hiding the map shows its button again: hide it, then the button.)
        toon.questMap.hide()
        toon.questMap.ignoreOnscreenHooks()
        toon.endAllowPies()

    def _unlockUi(self):
        if not getattr(self, '_uiLocked', False):
            return
        self._uiLocked = False
        toon = base.localAvatar
        toon.gameUiLocked = False
        toon.book.obscureButton(0)
        toon.obscureFriendsListButton(-1)
        base.setCellsAvailable(base.bottomCells + base.leftCells + base.rightCells, 1)

    def _toWalk(self, place):
        if place and place.fsm.getCurrentState().getName() != 'walk':
            place.fsm.request('walk')
        self._lockUi()

    def _holdControls(self, jump=None):
        # No walking or turning: only the jump.
        toon = base.localAvatar
        if jump is None:
            jump = Consts.HopJumpForce if self.hopUntil > self.gameTime() else OTPGlobals.ToonJumpForce
        toon.controlManager.setSpeeds(0, jump, 0, 0)

    def _startTimer(self):
        if self.phase == 'golf':
            timeLeft = Consts.GolfDuration - self.golfTime()
        else:
            timeLeft = Consts.SlideDuration - (globalClock.getFrameTime() - self.getStartTime())
        timeLeft = max(0, timeLeft)
        self.timer.posInTopRightCorner()
        self.timer.setTime(timeLeft)
        self.timer.countdown(timeLeft, self.timerExpired)
        self.timer.unstash()

    def _stopGolfArrival(self):
        if getattr(self, '_leaveLabel', None):
            self._leaveLabel.destroy()
            self._leaveLabel = None
        if self._golfArrival is not None:
            self._golfArrival.pause()
            self._golfArrival = None
        self._endGolfIntro()
        for track in self._elevatorTracks.values():
            track.pause()
        self._elevatorTracks = {}
        if self._camInElevator:
            self._camInElevator = False
            camera.wrtReparentTo(render)
            self._fixFov()

    def exitGame(self):
        self._stopGolfArrival()
        self.elevatorMusic.stop()
        taskMgr.remove(self.uniqueName('update'))
        taskMgr.remove(self.uniqueName('golf'))
        if self.golf is not None:
            self.golf.hideAim()
        if self.timer is not None:
            self.timer.stop()
            self.timer.stash()
        self._endPowerUps()
        toon = base.localAvatar
        toon.controlManager.setSpeeds(OTPGlobals.ToonForwardSpeed, OTPGlobals.ToonJumpForce,
                                      OTPGlobals.ToonReverseSpeed, OTPGlobals.ToonRotateSpeed)
        toon.startTrackAnimToSpeed()
        taskMgr.remove(self.uniqueName('camera'))
        if getattr(self, '_fovNow', None) is not None:
            self._fovNow = None
            base.camLens.setMinFov(getattr(toon, 'fov', ToontownGlobals.DefaultCameraFov) / (4.0 / 3.0))
        self._standUp(toon)
        if getattr(self, '_stoppedSmartCam', False):
            self._stoppedSmartCam = False
            camera.reparentTo(base.localAvatar)
            base.localAvatar.startUpdateSmartCamera()
        if getattr(self, '_defaultFar', None):
            base.camLens.setFar(self._defaultFar)
            self._defaultFar = None
        self._holdStill(base.localAvatar, False)
        self._unlockUi()
        DistCogdoGame.exitGame(self)

    def enterFinish(self):
        DistCogdoGame.enterFinish(self)
        place = base.cr.playGame.getPlace()
        if place and place.fsm.getCurrentState().getName() == 'walk':
            place.fsm.request('stopped')
        self.gui.hide()
        text = TTL.BoardroomGameFinish % self.banked if self.banked else TTL.BoardroomGameNoMemos
        if self.phase == 'golf':
            text += '\n' + TTL.BoardroomGolfFinish % (Consts.NumBarrels - self.barrelsLost, Consts.NumBarrels)
        self.finishLabel = DirectLabel(relief=None, text=text, text_scale=0.09, text_fg=(1, 1, 0.6, 1),
                                       text_shadow=(0, 0, 0, 1), text_font=ToontownGlobals.getSignFont(),
                                       text_wordwrap=18, pos=(0, 0, 0.45))

    def exitFinish(self):
        if getattr(self, 'finishLabel', None):
            self.finishLabel.destroy()
            self.finishLabel = None
        self.music.stop()
        DistCogdoGame.exitFinish(self)

    def timerExpired(self):
        pass

    # --- Every frame ---

    def _update(self, task):
        toon = base.localAvatar
        if toon.isEmpty() or self.room is None or self.phase == 'golf':
            return Task.cont
        now = self.gameTime()
        self._animateOthers()
        dt = min(globalClock.getDt(), 0.1)
        for i, suit in enumerate(self.minions):
            x, y, z = self.layout.minionPos(i, now)
            old = suit.getPos()
            suit.setPos(x, y, z + 0.6 * math.sin(now * 2.0 + i))
            if (PM.Vec3(x, y, 0) - PM.Vec3(old[0], old[1], 0)).length() > 0.01:
                suit.headsUp(PM.Point3(x + (x - old[0]) * 10, y + (y - old[1]) * 10, suit.getZ()))
        pos = toon.getPos(render)
        self._cullCogs(pos, now)
        if self.decor:
            self.decor.update(now)
        self._chatter(now)
        if toon.doId not in self.exited:
            if self.slideState in ('wait', 'slide'):
                self._checkPickups(pos)
                self._checkLandings(pos, now)
                self._powerUps(toon, now)
                # In steps of at most 0.1 s, but for all the time that really
                # passed: with dt capped at 0.1, below 10 FPS the player slid
                # slower than the NPCs (at 6 FPS only 60% of the speed).
                left = min(globalClock.getDt(), 0.4)
                while left > 1e-4 and self.slideState in ('wait', 'slide'):
                    step = min(left, 0.1)
                    left -= step
                    self._slide(toon, toon.getPos(render), step, now)
            elif self.slideState == 'off':
                self._walkToExit(toon, pos, dt)
            if pos[2] < -4:
                toon.setPos(render, self.startPos(toon.doId))
            if now - self.lastProgress > 0.25:
                self.lastProgress = now
                self.sendUpdate('requestProgress', [pos[0], pos[1], pos[2]])
        self._updateGui()
        return Task.cont

    def _cullCogs(self, pos, now):
        # The table is long: only the cogs near the toon are shown and
        # animated, for the frame rate on phones.
        if now < getattr(self, '_nextCull', 0):
            return
        self._nextCull = now + 0.4
        y = camera.getY(render) if self.slideState != 'wait' else pos[1]
        decor = self.decor.allSuits() if self.decor else []
        for suit in list(self.bosses.values()) + self.minions + decor:
            near = -40 < suit.getY(render) - y < Consts.ShowCogsWithin
            if near and suit.isStashed():
                suit.unstash()
                if suit in self.minions:
                    suit.pose('landing', 0)
                    suit.prop.loop('propeller')
                elif suit in decor:
                    self.decor.startSuit(suit)
                else:
                    suit.loop('sit', fromFrame=random.randrange(20))
            elif not near and not suit.isStashed():
                suit.stash()
                suit.stop()
                if suit in self.minions:
                    suit.prop.stop()

    def _cameraTask(self, task):
        toon = base.localAvatar
        if getattr(self, '_camInElevator', False):
            # The elevator ride and the golf intro move the camera.
            return Task.cont
        if self.phase == 'golf':
            if not toon.isEmpty():
                self._golfCamera(toon, min(globalClock.getDt(), 0.1))
        elif not toon.isEmpty() and toon.doId not in self.exited:
            self._followCamera(toon, min(globalClock.getDt(), 0.1))
        return Task.cont

    def _followCamera(self, toon, dt):
        pos = toon.getPos(render)
        if self.slideState in ('off', 'jumpoff') and globalClock.getFrameTime() < getattr(self, '_jumpCamUntil', 0):
            # Off the end of the table: watched from out to the side, so the
            # leap down past the chairman's chair shows.
            side = getattr(self, '_jumpSide', 1)
            want = PM.Point3(side * Consts.JumpCamSide, Consts.TableEnd - Consts.JumpCamBack, Consts.TableTop + Consts.JumpCamUp)
            look = PM.Point3((pos[0] + side * Consts.JumpOffX) / 2.0, (pos[1] + Consts.JumpLandY) / 2.0, 2.0 + Consts.JumpLandZ)
            cur = getattr(self, '_camPos', None) or want
            cur = cur + (want - cur) * min(1.0, dt * 3.5)
            self._camPos = PM.Point3(cur)
            camera.setPos(render, cur)
            camera.lookAt(look)
            return
        if self.slideState in ('off', 'jumpoff'):
            want = PM.Point3(pos[0] * 0.5, pos[1] - Consts.CameraBack * 1.2, Consts.TableTop + Consts.CameraUp * 1.3)
            look = PM.Point3(pos[0], pos[1] + 6, pos[2] + 2)
        else:
            want = PM.Point3(pos[0] * 0.6, pos[1] - Consts.CameraBack, max(pos[2], Consts.TableTop) + Consts.CameraUp)
            look = PM.Point3(pos[0] * 0.85, pos[1] + 16, max(pos[2], Consts.TableTop) + 1.0)
        cur = getattr(self, '_camPos', None) or want
        k = min(1.0, dt * 6.0)
        cur = cur + (want - cur) * k if (want - cur).length() < 40 else want
        self._camPos = PM.Point3(cur)
        camera.setPos(render, cur)
        camera.lookAt(look)

    def _steer(self):
        from direct.showbase.InputStateGlobal import inputState
        steer = 0.0
        if inputState.isSet('turnLeft') or inputState.isSet('slideLeft'):
            steer -= 1.0
        if inputState.isSet('turnRight') or inputState.isSet('slideRight'):
            steer += 1.0
        speed = Consts.SlideSpeed
        if inputState.isSet('forward'):
            speed = Consts.SlideFastSpeed
        elif inputState.isSet('reverse'):
            speed = Consts.SlideSlowSpeed
        return steer, speed

    def _slide(self, toon, pos, dt, now):
        """The belly-slide down the table. The walk controls still lift the
        toon for a jump and keep it on floors and out of walls; this moves
        it: always up the table, steered left and right (in the air too),
        faster or slower with forward and back. On an oil slick the steering
        barely grips and the toon drifts."""
        self._holdControls()
        start = Consts.StartDelay + Consts.StartStagger * self.startIndex(toon.doId)
        if self.slideState == 'wait':
            toon.setH(render, 0)
            toon.loop('neutral') if toon.getCurrentAnim() != 'neutral' else None
            if now >= start:
                self.slideState = 'slide'
                self.slideSpeed = Consts.SlideSpeed * 0.5
                self._diveIn(toon)
            self.lastPos = PM.Point3(pos)
            return
        if now >= self.crashUntil and getattr(toon, '_slideMode', None) != 'dive' and not self._isSliding(toon):
            # Something set it playing again (a landing from a hop plays
            # the walk's animations): back down on its belly.
            self._slidePose(toon)
        steer, wanted = self._steer()
        slick = self._onSlick(pos, now)
        if now < self.crashUntil:
            # Knocked flat by an obstacle: stopped dead till it is up again.
            wanted = 0.0
            steer = 0.0
            self.slideSpeed = 0.0
            self.steerVel = 0.0
        self.slideSpeed += max(-Consts.SlideAccel * 2 * dt, min(Consts.SlideAccel * dt, wanted - self.slideSpeed))
        grip = Consts.SlickGrip if slick else 1.0
        self.steerVel += (steer * Consts.SteerSpeed - self.steerVel) * min(1.0, grip * dt * 10.0)
        # Ran into something since last frame? A pile or a pencil stops the
        # toon dead: it spins round and sets off again.
        if self.lastPos is not None and now >= self.crashUntil and self.slideSpeed > 3.0:
            moved = pos[1] - self.lastPos[1]
            if moved < self.slideSpeed * dt * 0.25:
                self.stuckTime += dt
            else:
                self.stuckTime = 0.0
            if self.stuckTime > 0.12:
                hit = self._realObstacleAhead(pos)
                if hit is not None:
                    self._crash(toon, now)
                    self._letThrough(hit)
                else:
                    # Held up by nothing the toon should crash into (the
                    # ramps' slope, after a knock-back took it off its
                    # launch): lifted onto what is under it and on it goes.
                    # (Crashing here again and again kept a toon stuck and
                    # hit at the foot of a ramp: Arthur.)
                    self.stuckTime = 0.0
                    lift = self.layout.heightAt(pos[0], pos[1] + 1.0)
                    toon.setZ(render, max(pos[2], lift + 0.2))
        new = PM.Point3(pos[0] + self.steerVel * dt, pos[1] + self.slideSpeed * dt, pos[2])
        hw = Consts.TableHalfWidth - 1.0
        new.setX(max(-hw, min(hw, new[0])))
        if new[2] < Consts.TableTop - 0.5:
            # Never off the table: whatever pushed it over the edge, it is
            # back on top.
            new.setZ(Consts.TableTop)
        if now >= self.crashUntil:
            hit = self._pencilInWay(new, which=True)
            if hit is not None:
                back, k = hit
                # Into a pencil without hopping it: as good as a pile. Stopped
                # dead short of it, hurt, and it still has to be hopped.
                new.setY(back)
                toon.setFluidPos(render, new)
                self._crash(toon, now)
                self._letThrough(k)
        self._checkPass(new)
        toon.setFluidPos(render, new)
        self._launchRamps(toon, new)
        lean = -self.steerVel / Consts.SteerSpeed * 18.0
        spin = 0.0
        if now < self.spinUntil:
            spin = 720.0 * (1.0 - (self.spinUntil - now) / Consts.SpinTime)
        toon.setH(render, lean + spin)
        self.lastPos = PM.Point3(pos)
        self._slideFx(toon, new, dt, now)
        if new[1] > Consts.TableEnd - Consts.JumpOffAt:
            self._jumpOff(toon, new)

    def _jumpGravity(self, drop):
        # How strong a pull the arc takes so the toon rises JumpOffHeight
        # above the table before dropping to the floor in JumpOffTime.
        # (A ProjectileInterval with an end point can't take a waypoint.)
        T, H = Consts.JumpOffTime, Consts.JumpOffHeight
        # vz0 = (0.5*g*T^2 - drop)/T and vz0^2 = 2*g*H; solve for g.
        best = 1.0
        for k in range(1, 400):
            g = k * 0.5
            vz = (0.5 * g * T * T - drop) / T
            if vz > 0 and vz * vz >= 2 * g * H:
                best = g
                break
        return best / 32.174

    def _jumpOff(self, toon, pos):
        # Near the far end the toon springs up off its belly and jumps down
        # to the floor beside the chairman's chair (not into the chairman),
        # lands, and runs on out.
        self.slideState = 'jumpoff'
        place = base.cr.playGame.getPlace()
        if place and place.fsm.getCurrentState().getName() == 'walk':
            place.fsm.request('stopped')
        side = 1 if pos[0] >= 0 else -1
        land = PM.Point3(side * Consts.JumpOffX, Consts.JumpLandY, Consts.JumpLandZ)
        start = PM.Point3(pos)
        self._standUp(toon)
        toon.setH(render, -side * 35)
        # The camera swings out to the side to watch the jump.
        self._jumpSide = side
        self._jumpCamUntil = globalClock.getFrameTime() + Consts.JumpOffTime + Consts.JumpCamHold

        def landed():
            self.slideState = 'off'
            self._toWalk(place)
            toon.stopTrackAnimToSpeed()
            toon.controlManager.setSpeeds(OTPGlobals.ToonForwardSpeed, OTPGlobals.ToonJumpForce,
                                          OTPGlobals.ToonReverseSpeed, OTPGlobals.ToonRotateSpeed)
            toon.loop('run')
            toon.sendCurrentPosition()

        track = Sequence(
            Parallel(ProjectileInterval(toon, startPos=start, endPos=land, duration=Consts.JumpOffTime,
                                        gravityMult=self._jumpGravity(start[2] - land[2])),
                     Sequence(Func(toon.pose, 'jump-squat', 0), Wait(0.1), Func(toon.loop, 'jump-idle'),
                              Wait(Consts.JumpOffTime - 0.35), ActorInterval(toon, 'jump-land', duration=0.4))),
            Func(landed))
        track.start()
        self.ivals.append(track)
        self._jumpTrack = track

    def _slideFx(self, toon, pos, dt, now):
        # A sense of speed: the view widens as the toon speeds up, it sways
        # into the turns, and the tablecloth squeaks out a trail of dust.
        speed = max(0.0, self.slideSpeed)
        boost = max(0.0, min(1.0, (speed - Consts.SlideSpeed) / (Consts.SlideFastSpeed - Consts.SlideSpeed)))
        self._setFov(Consts.SlideFov + Consts.SlideFovBoost * boost)
        geom = toon.getGeomNode()
        if getattr(toon, '_slideMode', None) == 'slide':
            geom.setR(-self.steerVel / Consts.SteerSpeed * 14.0)
            geom.setZ(Consts.SlideLift + 0.05 * math.sin(now * 9.0))
            try:
                toon.setPlayRate(Consts.PaddleRate[0] + (Consts.PaddleRate[1] - Consts.PaddleRate[0]) * boost, 'swim', partName='torso')
                if 'head' in toon.getPartNames():
                    toon.setPlayRate(Consts.PaddleRate[0] + (Consts.PaddleRate[1] - Consts.PaddleRate[0]) * boost, 'swim', partName='head')
            except Exception:
                pass
        if speed > 4.0 and now - getattr(self, '_lastPuff', 0) > 0.07 and abs(pos[2] - Consts.TableTop) < 0.6:
            self._lastPuff = now
            puff = self.marker.copyTo(self.sceneRoot)
            puff.setPos(pos[0] + random.uniform(-0.6, 0.6), pos[1] - 0.8, pos[2] + 0.06)
            puff.setScale(0.35)
            puff.setColor(1, 1, 0.95, 0.55)
            puff.setTransparency(PM.TransparencyAttrib.MAlpha)
            puff.setDepthOffset(2)
            fx = Sequence(Parallel(LerpScaleInterval(puff, 0.6, 1.2, startScale=0.35),
                                   LerpColorScaleInterval(puff, 0.6, PM.VBase4(1, 1, 1, 0), startColorScale=PM.VBase4(1, 1, 1, 1))),
                          Func(puff.removeNode))
            fx.start()

    def _setFov(self, fov):
        cur = getattr(self, '_fovNow', None)
        if cur is None or abs(cur - fov) > 0.2:
            cur = fov if cur is None else cur + (fov - cur) * 0.15
            self._fovNow = cur
            base.camLens.setMinFov(cur / (4.0 / 3.0))

    # --- The belly slide ---
    # The toon dives forward onto its belly (blended from standing into the
    # slip-and-fall's flat-on-the-table frame) and slides along it: its legs
    # held out behind as in that frame, and its arms paddling at the
    # tablecloth with the diving game's swim strokes, faster as it speeds up.

    def _diveIn(self, toon):
        self._standUp(toon)
        toon._slideMode = 'dive'
        toon.stop()
        toon.enableBlend()
        toon.pose('neutral', 0)
        toon.pose('slip-forward', Consts.SlideLieFrame)
        geom = toon.getGeomNode()

        def mix(w):
            toon.setControlEffect('neutral', 1.0 - w)
            toon.setControlEffect('slip-forward', w)
            geom.setZ(Consts.DiveHop * math.sin(math.pi * w))

        def done():
            toon.disableBlend()
            geom.setZ(0)
            if getattr(toon, '_slideMode', None) == 'dive':
                self._slidePose(toon)

        mix(0.0)
        ival = Sequence(LerpFunctionInterval(mix, duration=Consts.DiveTime, fromData=0.0, toData=1.0), Func(done))
        toon._diveIval = ival
        ival.start()
        self.ivals.append(ival)

    def _slidePose(self, toon):
        # On its belly: the legs lie out behind (slip-forward), the arms
        # paddle (swim). In the water the stroke goes down below the body,
        # into the table: the chest is lifted (as a belly slider holds its
        # head up), the stroke is mixed a little with the lying arms to keep
        # it shallow, and the toon rides a touch above the cloth, so the
        # hands brush the table and never go into it.
        toon._slideMode = 'slide'
        toon.stop()
        toon.pose('slip-forward', Consts.SlideLieFrame, partName='legs')
        for torso in toon.findAllMatches('**/__Actor_torso'):
            torso.setP(Consts.SlideChestUp)
        if 'torso' in toon.getPartNames() and toon.getAnimControl('swim', 'torso') is not None:
            toon.enableBlend(partName='torso')
            toon.setControlEffect('swim', Consts.SlideStroke, partName='torso')
            toon.setControlEffect('slip-forward', 1.0 - Consts.SlideStroke, partName='torso')
            toon.pose('slip-forward', Consts.SlideLieFrame, partName='torso')
            toon.loop('swim', partName='torso')
        if 'head' in toon.getPartNames() and toon.getAnimControl('swim', 'head') is not None:
            toon.loop('swim', partName='head')
        toon.getGeomNode().setZ(Consts.SlideLift)

    def _isSliding(self, toon):
        return (getattr(toon, '_slideMode', None) == 'slide' and toon.getCurrentAnim(partName='legs') is None
                and toon.getCurrentAnim(partName='torso') == 'swim')

    def _bellyFlop(self, toon):
        # A remote toon starting its slide: in with the same dive.
        self._diveIn(toon)

    def _standUp(self, toon):
        ival = getattr(toon, '_diveIval', None)
        if ival is not None:
            toon._diveIval = None
            ival.finish()
        toon._slideMode = None
        try:
            toon.disableBlend()
        except Exception:
            pass
        geom = toon.getGeomNode()
        geom.setHpr(0, 0, 0)
        geom.setZ(0)
        for torso in toon.findAllMatches('**/__Actor_torso'):
            torso.setP(0)

    def _pencilInWay(self, pos, which=False):
        # Where to put a toon that has run into a pencil lying across the
        # table (low enough to touch it: not hopping over), or None. Not the
        # one it was just knocked down by: it goes on through that.
        r = Consts.PencilHeight / 2.0
        if pos[2] > Consts.TableTop + Consts.PencilHeight * 0.8:
            return None
        for k, ob in self._pencils():
            if k == self.passOb:
                continue
            line = ob.y + (pos[0] - ob.x) * math.tan(math.radians(ob.angle))
            if line - r - 0.9 <= pos[1] <= line + r * 0.5:
                return (line - r - 1.0, k) if which else line - r - 1.0
        return None

    def _pencils(self):
        if getattr(self, '_pencilList', None) is None:
            self._pencilList = [(k, ob) for k, ob in enumerate(self.layout.obstacles) if ob.kind == Layout.PENCIL]
        return self._pencilList

    def _crash(self, toon, now):
        # Ran into a pile (or a pencil it didn't hop): stopped dead, hurt,
        # up on its feet seeing stars, then back down and off again.
        self.stuckTime = 0.0
        self.crashUntil = now + Consts.CrashTime
        self.slideSpeed = 0.0
        self.steerVel = 0.0
        base.playSfx(self.hitSfx, node=toon)
        self.sendUpdate('requestHit', [Consts.Obstacle])
        self._standUp(toon)
        toon._slideMode = 'crash'
        back = toon.getPos(render) - PM.Vec3(0, Consts.CrashBounce, 0)
        back.setZ(max(back[2], Consts.TableTop))
        track = Sequence(Parallel(LerpPosInterval(toon, 0.18, back, other=render, blendType='easeOut'),
                                  ActorInterval(toon, 'slip-backward', startFrame=0, endFrame=10, duration=0.18)),
                         ActorInterval(toon, 'conked', duration=Consts.CrashTime - 0.18 - 0.05),
                         Func(self._diveIn, toon))
        track.start()
        self.ivals.append(track)

    def _realObstacleAhead(self, pos):
        # The pile's side or pencil just ahead, low enough to run into (its
        # index in the layout), or None. Not the one being passed through.
        for k, ob in enumerate(self.layout.obstacles):
            if k != self.passOb and ob.kind == Layout.PILE and ob.contains(pos[0], pos[1] + 1.2, 0.6) \
                    and pos[2] < Consts.TableTop + ob.h - 0.5 and not self._onRamp(pos):
                return k
        hit = self._pencilInWay(PM.Point3(pos[0], pos[1] + 0.8, pos[2]), which=True)
        return hit[1] if hit else None

    def _letThrough(self, k):
        # After a hit the toon can go through that obstacle (only that one):
        # it was hitting the same pencil again and again (Arthur).
        self._closePass()
        self.passOb = k
        coll = getattr(self.room, 'obstacleColl', {}).get(k)
        if coll is not None:
            coll.stash()

    def _closePass(self):
        if self.passOb is None:
            return
        coll = getattr(self.room, 'obstacleColl', {}).get(self.passOb)
        if coll is not None:
            coll.unstash()
        self.passOb = None

    def _checkPass(self, pos):
        # Solid again once the toon is clear past it.
        if self.passOb is None:
            return
        ob = self.layout.obstacles[self.passOb]
        far = ob.y + ob.l
        if ob.kind == Layout.PENCIL:
            far = ob.y + abs(ob.w * math.sin(math.radians(ob.angle))) + Consts.PencilHeight
        if pos[1] > far + 1.5:
            self._closePass()

    def _onRamp(self, pos):
        return any(ob.kind == Layout.RAMP and ob.contains(pos[0], pos[1], 0.3) for ob in self.layout.obstacles)

    def _launchRamps(self, toon, pos):
        # Up a ramp and off its top: into the air.
        for i, ob in enumerate(self.layout.obstacles):
            if ob.kind != Layout.RAMP:
                continue
            if i in self.launched:
                # Knocked back down it (or off it): it launches again next
                # time up (once only, a toon knocked back down a ramp could
                # never get up onto its pile).
                if pos[1] < ob.y - ob.l + 0.5 or abs(pos[0] - ob.x) > ob.w + 1.0:
                    self.launched.discard(i)
                continue
            if abs(pos[0] - ob.x) < ob.w and ob.y + ob.l - 1.2 < pos[1] < ob.y + ob.l + 0.8:
                self.launched.add(i)
                controls = toon.controlManager.currentControls
                if controls is not None and hasattr(controls, 'lifter'):
                    controls.lifter.addVelocity(Consts.LaunchForce)
                    controls.isAirborne = 1

    def _walkToExit(self, toon, pos, dt):
        # Off the table: the toon gets up and runs into the exit.
        x, y, z = Consts.ExitPosHpr[:3]
        target = PM.Point3(x, y - 1.0, 0)
        delta = target - PM.Point3(pos[0], pos[1], 0)
        if delta.length() < 1.5 or pos[1] > y - 2.0:
            self.slideState = 'done'
            self.exited.add(toon.doId)
            self.sendUpdate('requestExit', [])
            self._localExited()
            return
        delta.normalize()
        step = delta * OTPGlobals.ToonForwardSpeed * dt
        toon.setFluidPos(render, pos + step)
        toon.headsUp(target)
        toon.setSpeed(OTPGlobals.ToonForwardSpeed, 0)

    def _checkPickups(self, pos):
        for i, (x, y, z) in enumerate(self.layout.memos):
            if i in self.memosGone:
                continue
            if abs(pos[0] - x) < Consts.PickupRadius and abs(pos[1] - y) < Consts.PickupRadius and -1.5 < pos[2] - z < 3.5:
                self.memosGone.add(i)
                self.room.memoModels[i].hide()
                self.sendUpdate('requestMemo', [i])
        for i, (kind, x, y) in enumerate(self.layout.powerUps):
            if i in self.powerUpsGone:
                continue
            if math.hypot(pos[0] - x, pos[1] - y) < Consts.PowerUpRadius and abs(pos[2] - Consts.TableTop) < 3.0:
                self.powerUpsGone.add(i)
                self.room.powerUpModels[i].hide()
                self.sendUpdate('requestPowerUp', [i])

    def _checkLandings(self, pos, now):
        keep = []
        for landing in self.landings:
            when, kind, x, y, z = landing
            if now < when:
                keep.append(landing)
                continue
            if Consts.hazardHits(kind, x, y, z, pos[0], pos[1], pos[2]):
                self.notify.info('landed on us: kind %d at (%.1f, %.1f)' % (kind, x, y))
                if self.invulnerableUntil <= now and now - self.lastHitTime > Consts.HitCooldown:
                    self.lastHitTime = now
                    self.sendUpdate('requestHit', [kind])
        self.landings = keep

    def _spreadThrownSlick(self, x, y, z):
        if self.room is None:
            return
        base.playSfx(self.oilSfx, volume=0.8)
        slick = loader.loadModel('phase_3/models/props/drop_shadow')
        slick.reparentTo(self.sceneRoot)
        slick.setPos(x, y, z + 0.03)
        slick.setColor(0.08, 0.07, 0.05, 0.85)
        slick.setTransparency(PM.TransparencyAttrib.MAlpha)
        slick.setDepthOffset(2)
        scale = Consts.ThrownSlickRadius * 2.0 / 2.2
        track = Sequence(LerpScaleInterval(slick, 0.6, scale, startScale=0.3),
                         Wait(Consts.ThrownSlickDuration - 0.6 - 1.5),
                         LerpColorScaleInterval(slick, 1.5, PM.VBase4(1, 1, 1, 0)), Func(slick.removeNode))
        track.start()
        self.ivals.append(track)

    def _onSlick(self, pos, now):
        for start, end, sx, sy, r in self.thrownSlicks:
            if start <= now < end and math.hypot(pos[0] - sx, pos[1] - sy) < r \
                    and abs(pos[2] - Consts.TableTop) < 0.8:
                return True
        for can, (start, end) in self.slicks.items():
            if start <= now < end:
                sx, sy, r = self.layout.slickAt(can)
                if math.hypot(pos[0] - sx, pos[1] - sy) < r and abs(pos[2] - Consts.TableTop) < 0.8:
                    return True
        return False

    def _powerUps(self, toon, now):
        if self.invulnerableUntil > now:
            pulse = 0.5 + 0.5 * math.sin(now * 10)
            toon.setColorScale(1, 1, 0.6 + 0.4 * pulse, 1)
            self._glowing = True
        elif getattr(self, '_glowing', False):
            self._glowing = False
            toon.clearColorScale()

    def _endPowerUps(self):
        toon = base.localAvatar
        if getattr(self, '_glowing', False):
            toon.clearColorScale()
            self._glowing = False
        controls = getattr(toon.controlManager, 'currentControls', None)
        if controls is not None:
            controls.avatarControlJumpForce = OTPGlobals.ToonJumpForce
        self.hopUntil = 0
        self.invulnerableUntil = 0

    def _localExited(self):
        # Into the exit elevator, to wait there for the others, seen from
        # inside it as in the other field offices' elevators.
        toon = base.localAvatar
        self._endPowerUps()
        base.playSfx(self.exitSfx)
        place = base.cr.playGame.getPlace()
        if place and place.fsm.getCurrentState().getName() == 'walk':
            place.fsm.request('stopped')
        self._toElevator(toon)
        self._cameraInElevator(self.room.exitElevator)

    def _elevatorSpot(self, toon):
        # A toon's spot in the exit elevator: in the order they got there.
        # By its place in the party, as the NPCs take theirs (by arrival
        # order the player and an NPC could be given the same spot).
        order = list(self.getToonIds())
        i = order.index(toon.doId) if toon.doId in order else len(order)
        p = ElevatorPoints[i % len(ElevatorPoints)]
        return render.getRelativePoint(self.room.exitElevator, PM.Point3(p[0], p[1], 0))

    def _toElevator(self, toon, run=True):
        # The toon runs in through the doors to its spot, and turns round
        # to face out.
        spot = self._elevatorSpot(toon)
        old = self._elevatorTracks.pop(toon.doId, None)
        if old is not None:
            old.finish()
        if not run or toon.isEmpty():
            toon.setPos(render, spot)
            toon.setH(render, 180)
            toon.loop('neutral')
            if toon.isLocal():
                toon.sendCurrentPosition()
            return
        here = toon.getPos(render)
        d = (spot - here).length()
        toon.headsUp(render, spot)
        # Walked in to its spot, not run (Arthur).
        track = Sequence(Func(toon.loop, 'walk'),
                         LerpPosInterval(toon, max(0.4, min(2.0, d / 7.0)), spot, other=render),
                         LerpHprInterval(toon, 0.35, PM.VBase3(180, 0, 0), other=render),
                         Func(toon.loop, 'neutral'))
        if toon.isLocal():
            track.append(Func(toon.sendCurrentPosition))
        self._elevatorTracks[toon.doId] = track
        track.start()

    def _cameraInElevator(self, elevator):
        # Inside the elevator behind the toons, looking out of its doors,
        # where the cog building elevators put it for the ride.
        self._camInElevator = True
        camera.reparentTo(elevator)
        camera.setPosHpr(0, 14, 4, 180, 0, 0)

    # --- From the AI ---

    def attack(self, kind, source, x, y, timestamp):
        if self.room is None or self.fsm.getCurrentState().getName() != 'Game':
            return
        elapsed = globalClockDelta.localElapsedTime(timestamp, bits=16)
        if kind == Consts.Swipe:
            self._swipe(source, x, y, elapsed)
            return
        z = self.layout.heightAt(x, y)
        target = PM.Point3(x, y, z)
        if source >= 100:
            flight = Consts.DropFallTime
            index = source - 100
            if 0 <= index < len(self.minions):
                start = self.minions[index].getPos(render) + PM.Vec3(0, 0, -1.0)
            else:
                start = PM.Point3(x, y, z + 18)
            sfx = self.dropSfx if kind == Consts.Anvil else self.landSfx
            if 0 <= index < len(self.minions) and random.random() < 0.3:
                self._say(self.minions[index], ('Downsize', 'Demotion', 'Shred', 'Sacked'))
        else:
            flight = Consts.ThrowFlightTime
            suit = self.bosses.get(source)
            if suit is None:
                return
            start = suit.getPos(render) + PM.Vec3(0, 0, 5.0)
            sfx = self.landSfx
            # The Boss Cog half stands to swing or throw, then sits again.
            anim = self._throwAnim(suit, kind)
            if anim:
                swing = Sequence(Func(suit.headsUp, target), Func(self._standUpFromSeat, suit),
                                 ActorInterval(suit, anim, duration=1.2), Func(suit.setH, 0),
                                 Func(self._sitBackDown, suit), Func(suit.loop, 'sit'))
                swing.start()
                self.ivals.append(swing)
            if kind == Consts.GolfBall:
                base.playSfx(self.swingSfx, node=suit)
            if random.random() < 0.45:
                self._say(suit, ('TeeOff', 'PlayHardball') if kind == Consts.GolfBall else ('Synergy', 'PinkSlip', 'RedTape', 'WriteOff'))
        if kind == Consts.Oil:
            # A jug of oil: no hit where it lands, but a slick spreads there.
            lands = self.gameTime() - elapsed + flight
            self.thrownSlicks.append((lands, lands + Consts.ThrownSlickDuration, x, y, Consts.ThrownSlickRadius))
        else:
            self.landings.append((self.gameTime() - elapsed + flight, kind, x, y, z))
        prop = self.props[kind].copyTo(self.sceneRoot)
        prop.setScale(self.propScales[kind])
        marker = self.marker.copyTo(self.sceneRoot)
        marker.setPos(x, y, z + 0.05)
        marker.setColor(1, 0.1, 0.05, 0.7)
        marker.setTransparency(PM.TransparencyAttrib.MAlpha)
        marker.setDepthOffset(3)
        radius = Consts.ThrownSlickRadius if kind == Consts.Oil else Consts.Hazards[kind][3]
        markerIval = LerpScaleInterval(marker, flight, radius / 1.1, startScale=0.2)
        if source >= 100:
            fly = LerpPosInterval(prop, flight, target, startPos=start, blendType='easeIn')
            spin = LerpHprInterval(prop, flight, PM.Vec3(random.uniform(-90, 90), 360, 0)) if kind != Consts.Anvil else Wait(flight)
        else:
            fly = ProjectileInterval(prop, startPos=start, endPos=target, duration=flight, gravityMult=1.2)
            spin = LerpHprInterval(prop, flight, PM.Vec3(720, 360, 0))
        impact = Sequence(Func(base.playSfx, sfx, volume=0.8, node=prop),
                          LerpScaleInterval(prop, 0.15, prop.getScale() * 1.3), Wait(0.5),
                          LerpColorScaleInterval(prop, 0.4, PM.VBase4(1, 1, 1, 0)), Func(prop.removeNode))
        prop.setTransparency(PM.TransparencyAttrib.MAlpha)
        track = Sequence(Parallel(fly, spin, markerIval), Func(marker.removeNode), impact)
        if kind == Consts.Oil:
            track = Parallel(track, Sequence(Wait(flight), Func(self._spreadThrownSlick, x, y, z)))
        track.start(elapsed)
        self.ivals.append(track)
        self.ivals = [ival for ival in self.ivals if ival.isPlaying()]

    # Which of its own attack animations each Boss Cog throws or swings
    # with (not every cog has every one).
    ThrowAnims = {'ym': ('golf-club-swing', 'throw-paper'), 'mm': ('magic1', 'magic1'), 'hh': ('throw-paper', 'throw-paper'),
                  'cr': ('throw-paper', 'throw-paper'), 'tbc': ('golf-club-swing', 'golf-club-swing')}

    def _throwAnim(self, suit, kind):
        anims = self.ThrowAnims.get(suit.style.name)
        if not anims:
            return None
        return anims[0] if kind in (Consts.GolfBall, Consts.Swipe) else anims[1]

    def _swipe(self, seat, x, y, elapsed):
        # The Boss Cog by the toon swings its golf club in over the table's
        # edge: a red strip there warns where.
        suit = self.bosses.get(seat)
        if suit is None:
            return
        z = Consts.TableTop
        self.landings.append((self.gameTime() - elapsed + Consts.SwipeTime, Consts.Swipe, x, y, z))
        side = 1 if x > 0 else -1
        cm = PM.CardMaker('swipeWarn')
        reach = Consts.SwipeReach
        cm.setFrame(-reach / 2.0, reach / 2.0, -Consts.Hazards[Consts.Swipe][3], Consts.Hazards[Consts.Swipe][3])
        strip = self.sceneRoot.attachNewNode(cm.generate())
        strip.setP(-90)
        strip.setPos(x - side * reach / 2.0, y, z + 0.06)
        strip.setColor(1, 0.15, 0.05, 0.55)
        strip.setTransparency(PM.TransparencyAttrib.MAlpha)
        strip.setDepthOffset(3)
        strip.setTwoSided(True)
        if random.random() < 0.6:
            self._say(suit, ('TeeOff', 'PlayHardball', 'Canned'))
        club = BattleProps.globalPropPool.getProp('golf-club')
        hand = suit.getRightHand() if hasattr(suit, 'getRightHand') else suit
        club.reparentTo(hand)
        anim = self._throwAnim(suit, Consts.GolfBall) or 'sit'
        track = Sequence(
            Func(suit.headsUp, PM.Point3(x - side * 4, y, z)),
            Func(self._standUpFromSeat, suit),
            Parallel(ActorInterval(suit, anim, duration=Consts.SwipeTime + 0.6),
                     Sequence(Wait(Consts.SwipeTime * 0.7), Func(base.playSfx, self.swingSfx, volume=1.0, node=suit)),
                     Sequence(LerpColorScaleInterval(strip, Consts.SwipeTime, PM.VBase4(1, 1, 1, 1), startColorScale=PM.VBase4(1, 1, 1, 0.3)),
                              Func(strip.removeNode))),
            Func(club.removeNode), Func(suit.setH, 0), Func(self._sitBackDown, suit), Func(suit.loop, 'sit'))
        track.start(elapsed)
        self.ivals.append(track)

    def oilSpill(self, can, timestamp):
        if self.room is None:
            return
        elapsed = globalClockDelta.localElapsedTime(timestamp, bits=16)
        start = self.gameTime() - elapsed + 0.6
        self.slicks[can] = (start, start + Consts.SlickDuration)
        drum = self.room.oilCanModels[can]
        slick = self.room.slickModels[can]
        x, y = self.layout.oilCans[can]
        side = 1 if x > 0 else -1
        sx, sy, r = self.layout.slickAt(can)
        scale = r * 2.0 / 2.2
        track = Sequence(
            Func(base.playSfx, self.oilSfx, volume=1.0, node=drum),
            LerpHprInterval(drum, 0.6, PM.Vec3(0, 0, -side * 90), blendType='easeIn'),
            Func(slick.show), LerpScaleInterval(slick, 0.8, scale, startScale=0.3),
            Wait(Consts.SlickDuration - 1.4 - 1.5),
            LerpColorScaleInterval(slick, 1.5, PM.VBase4(1, 1, 1, 0)), Func(slick.hide), Func(slick.clearColorScale),
            LerpHprInterval(drum, 0.5, PM.Vec3(0, 0, 0)))
        track.start(elapsed)
        self.ivals.append(track)
        # Warn only of a slick just ahead, and not more than one at a time.
        now = globalClock.getFrameTime()
        if base.localAvatar and self.fsm.getCurrentState().getName() == 'Game' \
                and 0 < sy - base.localAvatar.getY(render) < 150 and now - getattr(self, '_lastOilMsg', -99) > 6.0:
            self._lastOilMsg = now
            base.localAvatar.setSystemMessage(0, TTL.BoardroomOilSpill)

    def toonHit(self, avId, kind, memosLost):
        toon = self.getToon(avId)
        if toon is None:
            return
        base.playSfx(self.hitSfx, node=toon)
        flash = Sequence(LerpColorScaleInterval(toon, 0.1, PM.VBase4(1, 0.4, 0.4, 1)), LerpColorScaleInterval(toon, 0.3, PM.VBase4(1, 1, 1, 1)),
                         Func(toon.clearColorScale))
        flash.start()
        self.ivals.append(flash)
        if toon.isLocal():
            # Spun round, but still sliding (an obstacle stops it dead
            # instead: see _crash).
            if kind != Consts.Obstacle:
                self.spinUntil = self.gameTime() + Consts.SpinTime
            self.carried = max(0, self.carried - memosLost)
            if memosLost:
                base.localAvatar.setSystemMessage(0, TTL.BoardroomLostMemos % memosLost)

    def memoTaken(self, avId, memo, carried):
        if 0 <= memo < len(self.room.memoModels if self.room else []):
            self.memosGone.add(memo)
            self.room.memoModels[memo].hide()
        toon = self.getToon(avId)
        if toon is not None:
            base.playSfx(self.memoSfx, node=toon)
        if toon is not None and toon.isLocal():
            self.carried = carried

    def powerUpTaken(self, avId, index):
        if self.room is None or not 0 <= index < len(self.layout.powerUps):
            return
        self.powerUpsGone.add(index)
        self.room.powerUpModels[index].hide()
        toon = self.getToon(avId)
        if toon is None:
            return
        base.playSfx(self.powerSfx, node=toon)
        if toon.isLocal():
            kind = self.layout.powerUps[index][0]
            now = self.gameTime()
            if kind == Layout.INVULNERABLE:
                self.invulnerableUntil = now + Consts.InvulnerableTime
                base.localAvatar.setSystemMessage(0, TTL.BoardroomGotInvulnerable)
            else:
                self.hopUntil = now + Consts.HopTime
                self._hopping = True
                base.localAvatar.setSystemMessage(0, TTL.BoardroomGotHop)

    def setBanked(self, banked):
        self.banked = banked
        self._updateGui()

    def toonExited(self, avId):
        self.exited.add(avId)
        toon = self.getToon(avId)
        if toon is not None and not toon.isLocal():
            base.playSfx(self.exitSfx, node=toon)
        if toon is not None and toon.isLocal():
            self.carried = 0

    # --- The others on the table ---

    def _animateOthers(self):
        # The other toons (the NPCs' moves come from the AI) lie on their
        # bellies on the table, and run once off it.
        for avId in self.getToonIds():
            toon = self.getToon(avId)
            if toon is None or toon.isLocal() or toon.isEmpty():
                continue
            pos = toon.getPos(render)
            last = getattr(toon, '_boardroomLast', None)
            toon._boardroomLast = PM.Point3(pos)
            if avId in self.exited:
                # Walking on in to its spot, then stood there.
                moving = last is not None and (pos - last).length() > 0.02
                want = 'walk' if moving else 'neutral'
            elif Consts.TableStart - 2 < pos[1] < Consts.TableEnd - Consts.JumpOffAt and pos[2] > Consts.TableTop - 0.6:
                want = 'slide'
            elif pos[1] >= Consts.TableEnd - Consts.JumpOffAt - 1 and pos[2] > self._floorAt(pos[1]) + 0.4:
                # In the air off the end of the table. (Not just higher than
                # the floor: up on the exit's 2 ft step the NPCs went on in
                # the jump pose, floating into the elevator: Arthur.)
                want = 'jump-idle'
            elif last is not None and (pos - last).length() > 0.02:
                # Walking the last stretch in, running before.
                dt = max(1e-3, globalClock.getDt())
                want = 'walk' if (pos - last).length() / dt < 9.0 else 'run'
            else:
                want = 'neutral'
            if getattr(toon, '_boardroomAnim', None) == want:
                continue
            toon._boardroomAnim = want
            if want == 'slide':
                self._bellyFlop(toon)
            else:
                self._standUp(toon)
                toon.loop(want)

    def _floorAt(self, y):
        # The floor past the end of the table: the exit stands on a step.
        return Consts.ExitFloor if y > Consts.ExitPosHpr[1] - Consts.ExitStepDepth else 0.0

    # --- The golf office ---

    def golfTime(self):
        if self.golfStartTime is None:
            return 0.0
        return globalClock.getFrameTime() - self.golfStartTime

    def startGolf(self, timestamp):
        if self.golf is None or self.phase == 'golf':
            return
        self.phase = 'golf'
        elapsed = globalClockDelta.localElapsedTime(timestamp, bits=16)
        # The golf's clock starts after the ride over and the intro.
        self.golfStartTime = globalClock.getFrameTime() - elapsed + Consts.GolfLeadIn
        for ival in self.ivals:
            ival.finish()
        self.ivals = []
        self.landings = []
        self.thrownSlicks = []
        self._endPowerUps()
        # Anyone still on the table when time was up drops the memos they
        # carried, and is in the elevator with the others for the ride.
        self.carried = 0
        self.memoLabel.hide()
        self.statusLabel['text'] = ''
        if self.timer is not None:
            self.timer.stop()
            self.timer.stash()
        toon = base.localAvatar
        place = base.cr.playGame.getPlace()
        if place and place.fsm.getCurrentState().getName() == 'walk':
            place.fsm.request('stopped')
        if getattr(toon, '_smartCamEnabled', False):
            toon.stopUpdateSmartCamera()
            self._stoppedSmartCam = True
        # (This cleared the margin whisper with an empty one, which can
        # build a NaN-sized balloon and threw from startGolf: removed.)
        self._golfArrival = self._makeGolfArrival()
        self._golfArrival.start(min(elapsed, Consts.GolfLeadIn - 0.1))

    def requestGolfSkip(self):
        # The golf intro's green button.
        if self.phase == 'golf' and not getattr(self, '_golfSkipAsked', False):
            self._golfSkipAsked = True
            self.sendUpdate('requestGolfSkip', [])
            intro = getattr(self, '_golfIntro', None)
            if intro is not None:
                intro.waiting()

    def golfSkip(self, timestamp):
        # Every player pressed it: the golf starts now (after a moment's
        # beat), as the slide does when everyone has pressed play.
        if self.golf is None or self.golfStartTime is None:
            return
        elapsed = globalClockDelta.localElapsedTime(timestamp, bits=16)
        self.golfStartTime = globalClock.getFrameTime() - elapsed + 1.0
        if self._golfArrival is not None:
            self._golfArrival.pause()
            self._golfArrival = None
        if getattr(self, 'elevatorMusic', None):
            self.elevatorMusic.stop()
        self._beginGolf()

    def _makeGolfArrival(self):
        from toontown.building import ElevatorUtils
        from toontown.building.ElevatorConstants import ELEVATOR_NORMAL
        from toontown.cogdominium import CogdoBoardroomGameMovies
        room = self.room

        def intoElevator():
            # Everyone into the exit elevator (those still on the table too).
            for avId in self.getToonIds():
                toon = self.getToon(avId)
                if toon is None or toon.isEmpty():
                    continue
                self.exited.add(avId)
                self._standUp(toon)
                if not toon.isLocal():
                    toon.stopSmooth()
                self._toElevator(toon, run=False)
            self._cameraInElevator(room.exitElevator)
            base.playMusic(self.elevatorMusic, looping=1, volume=0.8)

        def arrive():
            # The elevator is the golf office's now: the boardroom goes, the
            # golf office comes, the toons stand in its elevator.
            room.root.stash()
            for suit in self.minions:
                suit.stash()
            self.golf.show()
            self.golf.setBarrelsHome(Consts.NumBarrels)
            self.golf.closeToonDoors()
            base.camLens.setFar(600)
            for k, avId in enumerate(self.getToonIds()):
                toon = self.getToon(avId)
                if toon is None or toon.isEmpty():
                    continue
                toon._boardroomAnim = None
                track = self._elevatorTracks.pop(avId, None)
                if track is not None:
                    track.finish()
                toon.setPos(render, self.golf.toonElevatorSpot(k))
                toon.setH(render, self.golf.toonElevator.getH(render) + 180)
                toon.loop('neutral')
            self._cameraInElevator(self.golf.toonElevator)

        def walkOut():
            # Out of the doors and over to the tees.
            for avId in self.getToonIds():
                toon = self.getToon(avId)
                if toon is None or toon.isEmpty():
                    continue
                tee = self.golf.teePos(self.startIndex(avId))
                spot = tee + PM.Vec3(-1.6, -0.4, 0)
                toon.headsUp(render, spot)
                track = Sequence(Func(toon.loop, 'run'),
                                 LerpPosInterval(toon, Consts.GolfWalkOutTime * 0.8, spot, other=render),
                                 LerpHprInterval(toon, Consts.GolfWalkOutTime * 0.2, PM.VBase3(-90, 0, 0), other=render),
                                 Func(toon.loop, 'neutral'))
                self._elevatorTracks[avId] = track
                track.start()

        def intro():
            self.elevatorMusic.stop()
            base.playMusic(self.music, looping=1, volume=0.7)
            self._camInElevator = True
            camera.wrtReparentTo(render)
            self._fixFov()
            self._golfIntro = CogdoBoardroomGameMovies.CogdoBoardroomGolfIntro(self.doId + 1, self)
            self._golfIntro.load(self.golf.root)
            self._golfIntro.play()

        doors = Consts.GolfDoorTime
        return Sequence(
            Func(intoElevator),
            ElevatorUtils.getCloseInterval(self, room.exitLeftDoor, room.exitRightDoor, self.closeSfx, None,
                                           type=ELEVATOR_NORMAL),
            ElevatorUtils.getRideElevatorInterval(ELEVATOR_NORMAL),
            Func(arrive),
            ElevatorUtils.getOpenInterval(self, self.golf.toonLeftDoor, self.golf.toonRightDoor, self.openSfx, None,
                                          type=ELEVATOR_NORMAL),
            Func(walkOut),
            Wait(Consts.GolfWalkOutTime),
            Func(intro),
            Wait(Consts.GolfIntroDuration),
            Func(self._beginGolf),
            name=self.uniqueName('golfArrival'))

    def _fixFov(self):
        # The elevator ride sets its own field of view; back to the game's.
        toon = base.localAvatar
        base.camLens.setMinFov(getattr(toon, 'fov', ToontownGlobals.DefaultCameraFov) / (4.0 / 3.0))

    def _endGolfIntro(self):
        intro = getattr(self, '_golfIntro', None)
        if intro is not None:
            intro.end()
            intro.unload()
            self._golfIntro = None

    def _beginGolf(self):
        if getattr(self, '_golfBegun', False):
            return
        self._golfBegun = True
        self._endGolfIntro()
        self._camInElevator = False
        self._fixFov()
        for track in self._elevatorTracks.values():
            track.finish()
        self._elevatorTracks = {}
        self.golf.closeToonDoors()
        self.barrelLabel.show()
        self.barrelIcon.show()
        self.memoIcon.hide()
        for avId in self.getToonIds():
            toon = self.getToon(avId)
            if toon is None or toon.isEmpty():
                continue
            self._placeAtTee(toon, avId)
            if not toon.isLocal():
                toon.startSmooth()
            if avId not in self.clubs:
                club = self.golf.attachPutter(toon)
                if club is not None:
                    self.clubs[avId] = club
            toon.loop('loop-putt' if toon.getAnimControls('loop-putt') else 'neutral')
        toon = base.localAvatar
        self.aimH = 0.0
        self.power = 0.0
        self.charging = False
        self.lastSwing = -99
        self._golfCamPos = None
        place = base.cr.playGame.getPlace()
        self._toWalk(place)
        toon.stopTrackAnimToSpeed()
        toon.controlManager.setSpeeds(0, 0, 0, 0)
        self._holdStill(toon, True)
        if toon.getAnimControls('loop-putt'):
            toon.loop('loop-putt')
        # The golf camera is ours alone: the walk's smart camera would put
        # it back behind the toon's head every frame.
        if getattr(toon, '_smartCamEnabled', False):
            toon.stopUpdateSmartCamera()
            self._stoppedSmartCam = True
        camera.wrtReparentTo(render)
        if self.timer is not None:
            self.timer.stop()
            self._startTimer()
        self._updateGui()
        taskMgr.add(self._golfUpdate, self.uniqueName('golf'), priority=36)
        toon.setSystemMessage(0, TTL.BoardroomGolfHint)

    def _holdStill(self, toon, still):
        # Stood at the tee, the toon is in the walk state only for its keys.
        # Holding Control to wind up a swing is also the walk's jump key: the
        # walker kept hopping the toon (with no force) and flipping it into
        # its jump and land animations, fighting the putting stance every
        # frame (the twitching), and its gravity tugged at the toon we place
        # by hand. No jumps, and no walker physics, while it putts.
        if toon is None or toon.isEmpty() or getattr(self, '_heldStill', False) == still:
            return
        self._heldStill = still
        controls = getattr(toon.controlManager, 'currentControls', None)
        if still:
            toon.ignoreAnimationEvents()
            if controls is not None and hasattr(controls, 'setCollisionsActive'):
                controls.setCollisionsActive(0)
        else:
            toon.setupAnimationEvents()
            if controls is not None and hasattr(controls, 'setCollisionsActive'):
                controls.setCollisionsActive(1)

    def _placeAtTee(self, toon, avId):
        # Beside the tee, side on to the shot, as on the golf course.
        tee = self.golf.teePos(self.startIndex(avId))
        toon.setPos(render, tee + PM.Vec3(-1.6, -0.4, 0))
        toon.setH(render, -90)
        if toon.isLocal():
            toon.sendCurrentPosition()

    def _golfUpdate(self, task):
        if self.golf is None:
            return Task.cont
        dt = min(globalClock.getDt(), 0.1)
        now = self.golfTime()
        for cog in list(self.golf.cogs.values()):
            self.golf.updateCog(cog, now)
        self.golf.updateElevators(dt)
        for cogId in self.golf.updateBalls(dt):
            self.sendUpdate('requestGolfHit', [cogId])
        toon = base.localAvatar
        if toon.isEmpty() or toon.doId not in self.getToonIds():
            return Task.cont
        if self.golfLeaving:
            self._checkGolfLeave(toon)
            return Task.cont
        from direct.showbase.InputStateGlobal import inputState
        turn = 0
        if inputState.isSet('turnLeft') or inputState.isSet('slideLeft'):
            turn += 1
        if inputState.isSet('turnRight') or inputState.isSet('slideRight'):
            turn -= 1
        self.aimH = max(-80.0, min(80.0, self.aimH + turn * Consts.AimSpeed * dt))
        tee = self.golf.teePos(self.startIndex(toon.doId))
        toon.setPos(render, tee + self._teeOffset(self.aimH))
        toon.setH(render, self.aimH - 90)
        held = inputState.isSet('jump')
        if held and not self.charging and now - self.lastSwing > Consts.SwingCooldown:
            self.charging = True
            self.chargeStart = now
        if self.charging:
            # The power goes up and back down while held, as on the course.
            t = ((now - self.chargeStart) / Consts.ChargeTime) % 2.0
            self.power = t if t <= 1.0 else 2.0 - t
            if not held:
                self.charging = False
                self.lastSwing = now
                self.sendUpdate('requestGolfSwing', [self.aimH, self.power])
        else:
            self.power = 0.0
        self.golf.showAim(tee, self.aimH, self.power)
        return Task.cont

    def _teeOffset(self, h):
        # Where a toon stands beside its tee for a shot at heading h.
        a = math.radians(h)
        side = PM.Vec3(-math.cos(a), -math.sin(a), 0) * 1.6
        back = PM.Vec3(math.sin(a), -math.cos(a), 0) * 0.4
        return side + back

    def _golfCamera(self, toon, dt):
        tee = self.golf.teePos(self.startIndex(toon.doId))
        h = getattr(self, 'aimH', 0.0)
        a = math.radians(h)
        fwd = PM.Vec3(-math.sin(a), math.cos(a), 0)
        # Behind the ball down the line of the shot, as at the CEO battle's
        # golf spots; kept inside the walls.
        want = tee - fwd * Consts.GolfCamBack + PM.Vec3(0, 0, Consts.GolfCamUp)
        local = self.golf.toLocal(want)
        local.setX(max(-Consts.GolfHalfX + 1.5, min(Consts.GolfHalfX - 1.5, local[0])))
        local.setY(max(-Consts.GolfHalfY + 0.6, local[1]))
        want = local + self.golf.root.getPos(render)
        look = tee + fwd * Consts.GolfCamLook + PM.Vec3(0, 0, Consts.GolfCamLookUp)
        cur = self._golfCamPos or want
        # Turning with the aim, as the CEO battle's camera does, with just a
        # little easing.
        cur = cur + (want - cur) * min(1.0, dt * 12.0)
        self._golfCamPos = PM.Point3(cur)
        camera.setPos(render, cur)
        camera.lookAt(look)

    def golfCog(self, cogId, name, px, side, exitY, speed, timestamp, toDrop=False, tx=0.0, ty=0.0):
        if self.golf is None:
            return
        elapsed = globalClockDelta.localElapsedTime(timestamp, bits=16)
        self.golf.addCog(cogId, name, px, side, exitY, speed, self.golfTime() - elapsed, (tx, ty) if toDrop else None)

    def golfDrops(self, dropIds, xs, ys):
        if self.golf is None:
            return
        self.golf.setDrops(dict(zip(dropIds, zip(xs, ys))))
        self.dropCount = len(dropIds)
        self._updateGui()

    def golfBarrelsHome(self, barrelsHome):
        if self.golf is None:
            return
        self.barrelsHome = barrelsHome
        self.golf.setBarrelsHome(barrelsHome)
        self._updateGui()

    def golfCogPickup(self, cogId, carrying, barrelsHome):
        if self.golf is None:
            return
        cog = self.golf.cogs.get(cogId)
        self.golf.cogPickup(cogId, carrying)
        if carrying and cog and random.random() < 0.5:
            self._say(cog['suit'], ('Liquidate', 'PickPocket', 'Downsize'), TTL.BoardroomGolfGrabLines)
        self.barrelsHome = barrelsHome
        self.golf.setBarrelsHome(barrelsHome)
        self._updateGui()

    def golfCogEscaped(self, cogId, carrying, barrelsHome):
        if self.golf is None:
            return
        self.golf.cogEscaped(cogId, carrying)
        if carrying:
            self.barrelsLost += 1
        self.barrelsHome = barrelsHome
        self.golf.setBarrelsHome(barrelsHome)
        self._updateGui()
        if carrying:
            base.localAvatar.setSystemMessage(0, TTL.BoardroomBarrelStolen)

    def golfOver(self, timestamp):
        # Time is up in the golf office: the toons' elevator opens and the
        # toons walk into it themselves, to ride up to the executive suite.
        if self.golf is None or self.golfLeaving:
            return
        self.golfLeaving = True
        self.charging = False
        self.golf.hideAim()
        # Every cog left in the office blows up: no more barrels taken.
        for cogId in list(self.golf.cogs):
            self.golf.cogExplode(cogId)
        if self.timer is not None:
            self.timer.stop()
            self.timer.stash()
        for club in self.clubs.values():
            club.stash()
        self.golf.holdExit()
        self._startExitClock(globalClockDelta.localElapsedTime(timestamp, bits=16))
        doors = ElevatorUtils.getOpenInterval(self, self.golf.exitLeftDoor, self.golf.exitRightDoor, self.openSfx, None,
                                              type=ELEVATOR_NORMAL)
        doors.start()
        self.ivals.append(doors)
        toon = base.localAvatar
        if toon.isEmpty() or toon.doId in self.leftGolf:
            return
        for avId in self.getToonIds():
            other = self.getToon(avId)
            if other is not None and not other.isEmpty() and not other.isLocal():
                other.loop('neutral')
        # Free to walk, with the usual camera, for the walk to the doors.
        self._holdStill(toon, False)
        place = base.cr.playGame.getPlace()
        self._toWalk(place)
        toon.controlManager.setSpeeds(OTPGlobals.ToonForwardSpeed, OTPGlobals.ToonJumpForce,
                                      OTPGlobals.ToonReverseSpeed, OTPGlobals.ToonRotateSpeed)
        toon.startTrackAnimToSpeed()
        if getattr(self, '_stoppedSmartCam', False):
            self._stoppedSmartCam = False
            camera.reparentTo(toon)
            toon.startUpdateSmartCamera()
        self._camInElevator = True
        toon.setSystemMessage(0, TTL.BoardroomGolfLeave)
        self._leaveLabel = DirectLabel(relief=None, text=TTL.BoardroomGolfLeave, text_scale=0.07,
                                       text_fg=(1, 1, 0.6, 1), text_shadow=(0, 0, 0, 1),
                                       text_font=ToontownGlobals.getSignFont(), text_wordwrap=24, pos=(0, 0, 0.72))

    def _startExitClock(self, elapsed):
        # The countdown over the elevator's doors, as over the other
        # buildings' and field offices' elevators: the ride goes on without
        # anyone not in when it runs out.
        self._stopExitClock()
        node = PM.TextNode('golfExitClock')
        node.setFont(ToontownGlobals.getSignFont())
        node.setAlign(PM.TextNode.ACenter)
        node.setTextColor(0.5, 0.5, 0.5, 1)
        self._exitClockNode = node
        self._exitClock = self.golf.exitElevator.attachNewNode(node)
        self._exitClock.setPosHprScale(*Consts.GolfExitClock)
        self._exitClock.setLightOff()
        end = globalClock.getFrameTime() - elapsed + Consts.GolfLeaveTime

        def tick(task):
            left = max(0, int(math.ceil(end - globalClock.getFrameTime())))
            text = str(left)
            if node.getText() != text:
                node.setText(text)
            return Task.cont if left > 0 else Task.done

        taskMgr.add(tick, self.uniqueName('golfExitClock'))

    def _stopExitClock(self):
        taskMgr.remove(self.uniqueName('golfExitClock'))
        clock = getattr(self, '_exitClock', None)
        if clock is not None:
            clock.removeNode()
        self._exitClock = None

    def _checkGolfLeave(self, toon):
        # Walked in through the doors?
        local = self.golf.exitElevator.getRelativePoint(render, toon.getPos(render))
        if abs(local[0]) < 3.6 and local[1] > -1.5 and toon.doId not in self.leftGolf:
            self.leftGolf.add(toon.doId)
            self.leftOrder.append(toon.doId)
            self.sendUpdate('requestGolfLeave', [])
            place = base.cr.playGame.getPlace()
            if place and place.fsm.getCurrentState().getName() == 'walk':
                place.fsm.request('stopped')
            if getattr(self, '_leaveLabel', None):
                self._leaveLabel.destroy()
                self._leaveLabel = None
            toon.setSystemMessage(0, TTL.CogdoMazeGameWaitingForToons if self._golfWaiting() else '')
            self._intoGolfElevator(toon)
            self._cameraInElevator(self.golf.exitElevator)

    def _golfWaiting(self):
        return [avId for avId in self.getToonIds() if avId not in self.leftGolf]

    def _intoGolfElevator(self, toon):
        k = self.leftOrder.index(toon.doId) if toon.doId in self.leftOrder else len(self.leftOrder)
        spot = self.golf.exitElevatorSpot(k)
        old = self._elevatorTracks.pop(toon.doId, None)
        if old is not None:
            old.finish()
        here = toon.getPos(render)
        toon.headsUp(render, spot)
        heading = self.golf.exitElevator.getH(render) + 180
        track = Sequence(Func(toon.loop, 'run'),
                         LerpPosInterval(toon, max(0.3, min(1.2, (spot - here).length() / 14.0)), spot, other=render),
                         LerpHprInterval(toon, 0.35, PM.VBase3(heading, 0, 0), other=render),
                         Func(toon.loop, 'neutral'))
        if toon.isLocal():
            track.append(Func(toon.sendCurrentPosition))
        self._elevatorTracks[toon.doId] = track
        track.start()

    def toonLeftGolf(self, avId):
        self.leftGolf.add(avId)
        if avId not in self.leftOrder:
            self.leftOrder.append(avId)
        if not self._golfWaiting() and self.golf is not None:
            # All in: the doors close for the ride up.
            self._stopExitClock()
            pass  # (no empty whisper: it can build a NaN-sized balloon)
            doors = ElevatorUtils.getCloseInterval(self, self.golf.exitLeftDoor, self.golf.exitRightDoor,
                                                   self.closeSfx, None, type=ELEVATOR_NORMAL)
            doors.start()
            self.ivals.append(doors)

    def golfCogHit(self, cogId, avId, barrelsHome):
        if self.golf is None:
            return
        cog = self.golf.cogs.get(cogId)
        if cog and random.random() < 0.6:
            cog['suit']._lastSaid = -99
            self._say(cog['suit'], (), TTL.BoardroomGolfHitLines)
        self.golf.cogHit(cogId)
        self.barrelsHome = barrelsHome
        self.golf.setBarrelsHome(barrelsHome)
        self._updateGui()

    def golfSwing(self, avId, h, power, timestamp):
        if self.golf is None:
            return
        toon = self.getToon(avId)
        index = self.startIndex(avId)
        tee = self.golf.toLocal(self.golf.teePos(index))
        self.golf.addBall(avId, tee, h, power, toon is not None and toon.isLocal())
        if toon is not None and not toon.isEmpty():
            if not toon.isLocal():
                toon.setH(render, h - 90)
            if toon.getAnimControls('swing-putt'):
                Sequence(ActorInterval(toon, 'swing-putt', startFrame=0, endFrame=23),
                         Func(toon.loop, 'loop-putt')).start()

    # --- What the cogs say ---

    ChatterKeys = ('Synergy', 'BuzzWord', 'Jargon', 'ParadigmShift', 'ReOrg', 'Rolodex', 'Watercooler', 'RedTape',
                   'Schmooze', 'Filibuster', 'MumboJumbo', 'PowerTie', 'Tabulate', 'GuiltTrip')

    def _standUpFromSeat(self, suit):
        # A seated cog gets up onto its chair's seat to swing or throw, up
        # over the table where it can see the toons (its sit place puts the
        # big bodies under the floor if it just stood where it sat).
        if suit.isEmpty() or getattr(suit, '_seatPos', None) is not None:
            return
        suit._seatPos = suit.getPos()
        parent = suit.getParent()
        chair = parent.getParent() if parent.getName() == 'sitLocator' else None
        if chair is not None and chair.getName() == 'correctHeading':
            # The chair's locator sits at its seat's height, in its middle.
            suit.setPos(chair, 0, 0, Consts.ChairSeatLift)
        else:
            suit.setZ(render, suit.getZ(render))

    def _sitBackDown(self, suit):
        if suit.isEmpty() or getattr(suit, '_seatPos', None) is None:
            return
        suit.setPos(suit._seatPos)
        suit._seatPos = None

    def _placeChat(self, suit):
        # The speech bubble just over the cog's head, as it sits or stands
        # (from the cog's place, a seated cog's bubble came up through the
        # table, or the floor).
        head = getattr(suit, '_chatHead', None)
        if head is None:
            try:
                head = suit.exposeJoint(None, 'modelRoot', 'joint_head')
            except Exception:
                head = None
            suit._chatHead = head or False
        if head:
            z = suit.getRelativePoint(head, PM.Point3(0, 0, 0))[2]
            suit.nametag3d.setZ(z + 2.2)

    def _say(self, suit, keys, extra=(), answering=False):
        # A line from what the cog would say in battle, in a speech bubble
        # (the name shows while it talks, as on the streets).
        if suit is None or suit.isEmpty() or suit.isStashed():
            return
        now = globalClock.getFrameTime()
        if (now - getattr(suit, '_lastSaid', -99) < (2.0 if answering else 6.0)) or now - getattr(self, '_lastSaid', -99) < 0.3:
            return False
        lines = []
        for key in keys:
            lines.extend(TTL.SuitAttackTaunts.get(key, ()))
        lines.extend(extra)
        if not lines:
            return
        suit._lastSaid = now
        self._lastSaid = now
        suit.nametag3d.unstash()
        self._placeChat(suit)
        suit.setChatAbsolute(random.choice(lines), CFSpeech | CFTimeout)
        name = self.uniqueName('hush-%d' % id(suit))
        taskMgr.remove(name)
        taskMgr.doMethodLater(5.0, self._hush, name, extraArgs=[suit])

    def _hush(self, suit):
        if suit is not None and not suit.isEmpty():
            suit.clearChat()
            suit.nametag3d.stash()

    def _chatter(self, now):
        # The cogs in view talk, every one of them in turn (Arthur: all the
        # cogs talking): the one quiet longest speaks next, about twice a
        # second, the diners and the cogs talking shop among themselves,
        # the Boss Cogs at the table and the flyers overhead too.
        if now < getattr(self, '_nextChatter', 3.0):
            return
        self._nextChatter = now + random.uniform(0.35, 0.7)
        y = base.localAvatar.getY(render)
        pool = (self.decor.allSuits() if self.decor else []) + list(self.bosses.values()) + list(self.minions)
        if self.chairman is not None:
            pool.append(self.chairman)
        near = [s for s in pool if not s.isStashed() and -10 < s.getY(render) - y < 110]
        if not near:
            return
        # A cog talking shop with another answers it, back and forth, as
        # in a real conversation.
        reply = [s for s in near if 0 < getattr(s, '_replyAt', 0) <= now]
        quiet = [s for s in near if now - getattr(s, '_lastSaid', -99) > 6.0]
        if reply:
            suit = reply[0]
        elif quiet:
            suit = min(quiet, key=lambda s: getattr(s, '_lastSaid', -99) + random.uniform(0, 2))
        else:
            return
        answering = bool(getattr(suit, '_replyAt', 0))
        suit._replyAt = 0
        self._say(suit, self.ChatterKeys, answering=answering)
        partner = getattr(suit, 'talkPartner', None)
        if partner is not None and not partner.isEmpty() and random.random() < 0.8:
            partner._replyAt = now + random.uniform(2.2, 3.2)
