from panda3d.core import *
from direct.task.Task import Task
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import StateData
from direct.fsm import ClassicFSM, State
from direct.fsm import State
from direct.showbase.InputStateGlobal import inputState
from otp.otpbase import OTPGlobals

# How much faster a sprint is than walking, and how quickly the second press
# of forward must follow the first.
# Arthur asked for a slightly slower sprint (it was 1.5).
SprintFactor = 1.35
SprintDoubleTap = 0.3
# A double tap is two short taps: a press of forward held longer than this
# was walking, and stopping then going again straight after must not sprint
# (Arthur: "you'll still be running instead of going into walking").
SprintTapHold = 0.25
# How long a sprinting toon can stand still before it goes back to walking.
SprintStopStill = 0.0
SprintStartGrace = 1.5

class Walk(StateData.StateData):
    notify = DirectNotifyGlobal.directNotify.newCategory('Walk')

    def __init__(self, doneEvent):
        StateData.StateData.__init__(self, doneEvent)
        self.fsm = ClassicFSM.ClassicFSM('Walk', [State.State('off', self.enterOff, self.exitOff, ['walking', 'swimming', 'slowWalking', 'sprinting']),
         State.State('walking', self.enterWalking, self.exitWalking, ['sprinting', 'swimming', 'slowWalking']),
         State.State('sprinting', self.enterSprinting, self.exitSprinting, ['walking', 'swimming', 'slowWalking']),
         State.State('swimming', self.enterSwimming, self.exitSwimming, ['walking', 'slowWalking']),
         State.State('slowWalking', self.enterSlowWalking, self.exitSlowWalking, ['walking', 'swimming'])], 'off', 'off')
        self.fsm.enterInitialState()
        self.IsSwimSoundAudible = 0
        self.swimSoundPlaying = 0

    def load(self):
        pass

    def unload(self):
        del self.fsm

    def enter(self, slowWalk = 0):
        base.localAvatar.startPosHprBroadcast()
        base.localAvatar.startBlink()
        base.localAvatar.attachCamera()
        shouldPush = 1
        if len(base.localAvatar.cameraPositions) > 0:
            shouldPush = not base.localAvatar.cameraPositions[base.localAvatar.cameraIndex][4]
        base.localAvatar.startUpdateSmartCamera(shouldPush)
        base.localAvatar.showName()
        base.localAvatar.collisionsOn()
        base.localAvatar.startGlitchKiller()
        base.localAvatar.enableAvatarControls()

    def exit(self):
        self.fsm.request('off')
        self.ignore('control')
        base.localAvatar.disableAvatarControls()
        base.localAvatar.stopUpdateSmartCamera()
        base.localAvatar.stopPosHprBroadcast()
        base.localAvatar.stopBlink()
        base.localAvatar.detachCamera()
        base.localAvatar.stopGlitchKiller()
        base.localAvatar.collisionsOff()
        base.localAvatar.controlManager.placeOnFloor()
        base.localAvatar.setWalkSpeedNormal()
        

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterWalking(self):
        if base.localAvatar.hp > 0:
            from toontown.toonbase import ToontownGlobals
            # The player's field of view (Shticker Book > Settings).
            base.camLens.setMinFov(ToontownGlobals.DefaultCameraFov/(4./3.))
            base.localAvatar.startTrackAnimToSpeed()
            base.localAvatar.setWalkSpeedNormal()
            # Two quick presses of forward, or the left stick pushed in on a
            # controller, sprint.
            self.lastForwardPress = None
            self.lastForwardRelease = None
            self.lastTapShort = False
            for key in self.getForwardKeys():
                self.accept(key, self.__forwardPressed)
                self.accept(key + '-up', self.__forwardReleased)
            self.accept('running-on', self.__startSprint)
        else:
            self.fsm.request('slowWalking')

    def getForwardKeys(self):
        # The arrow (the controller's stick presses it too) and the
        # player's own forward key. The keymap's MOVE_UP was never set, so
        # W (want-WASD's forward) never counted and a double tap of W did
        # not sprint.
        from toontown.toonbase import KeyBindings
        return KeyBindings.forwardKeys()

    def __forwardPressed(self):
        # The touch joystick (and a controller's stick) presses the arrow
        # and W together: one push, one press. Counted as two, every push
        # of the stick was a double tap and started a sprint (Arthur: "you
        # still run forever").
        frame = globalClock.getFrameCount()
        if frame == getattr(self, 'lastForwardFrame', None):
            return
        self.lastForwardFrame = frame
        now = globalClock.getFrameTime()
        # A controller runs with its run button (L3) only: letting go of the
        # stick and pushing it again was taken for a double tap, so the toon
        # sprinted again after every quick stop.
        from toontown.toonbase import Gamepad
        if Gamepad.isActive():
            self.lastForwardPress = None
            return
        # Only a short tap, let go of and pressed again quickly, sprints.
        release = getattr(self, 'lastForwardRelease', None)
        if (getattr(self, 'lastTapShort', False) and release is not None
                and now - release <= SprintDoubleTap):
            self.lastForwardPress = None
            self.lastTapShort = False
            self.__startSprint(byKey=True)
        else:
            self.lastForwardPress = now

    def __forwardReleased(self):
        frame = globalClock.getFrameCount()
        if frame == getattr(self, 'lastReleaseFrame', None):
            return
        self.lastReleaseFrame = frame
        now = globalClock.getFrameTime()
        press = getattr(self, 'lastForwardPress', None)
        self.lastTapShort = press is not None and now - press <= SprintTapHold
        self.lastForwardRelease = now

    def __startSprint(self, byKey=False):
        # A double tap sprints while forward is held; the controller's run
        # button sprints until it is pressed again.
        self.sprintByKey = byKey
        if self.fsm.getCurrentState().getName() == 'walking':
            self.fsm.request('sprinting')

    def enterSprinting(self):
        if base.localAvatar.hp > 0:
            base.localAvatar.startTrackAnimToSpeed()
            base.localAvatar.controlManager.setSpeeds(OTPGlobals.ToonForwardSpeed * SprintFactor, OTPGlobals.ToonJumpForce,
                                                      OTPGlobals.ToonReverseSpeed, OTPGlobals.ToonRotateSpeed)
            self.accept('running-off', self.__stopSprint)
            self.stillSince = None
            self.sprintMoved = False
            # Letting go of forward (or the stick) stops the sprint.
            taskMgr.add(self.__watchSprint, 'walkSprintWatch')
        else:
            self.fsm.request('slowWalking')

    def __watchSprint(self, task):
        # Standing still ends a sprint, however it was started (the double
        # tap or the controller's run button): moving again walks until run
        # is pressed again.
        if self.__moving():
            self.stillSince = None
            self.sprintMoved = True
            return task.cont
        now = globalClock.getFrameTime()
        if getattr(self, 'stillSince', None) is None:
            self.stillSince = now
        # Run pressed while standing gets a moment to start moving.
        wait = SprintStopStill if getattr(self, 'sprintMoved', False) else SprintStartGrace
        if getattr(self, 'sprintByKey', False) or now - self.stillSince >= wait:
            self.__stopSprint()
            return task.done
        return task.cont

    @staticmethod
    def __moving():
        if inputState.isSet('forward'):
            return True
        controls = getattr(base.localAvatar.controlManager, 'currentControls', None)
        # Backing up is not running: pulling the stick back to stop kept
        # the sprint going.
        speed = getattr(controls, 'speed', 0.0) or 0.0
        slide = abs(getattr(controls, 'slideSpeed', 0.0) or 0.0)
        return speed > 0.1 or slide > 0.1

    def __stopSprint(self):
        if self.fsm.getCurrentState().getName() == 'sprinting':
            self.fsm.request('walking')

    def exitSprinting(self):
        taskMgr.remove('walkSprintWatch')
        self.ignore('running-off')
        # The controller's run button goes back to off too.
        messenger.send('sprint-stopped')
        base.localAvatar.startTrackAnimToSpeed()
        base.localAvatar.setWalkSpeedNormal()

    def exitWalking(self):
        for key in self.getForwardKeys():
            self.ignore(key)
            self.ignore(key + '-up')
        self.ignore('running-on')
        base.localAvatar.stopTrackAnimToSpeed()
        base.localAvatar.setWalkSpeedNormal()

    def setSwimSoundAudible(self, IsSwimSoundAudible):
        self.IsSwimSoundAudible = IsSwimSoundAudible
        if IsSwimSoundAudible == 0 and self.swimSoundPlaying:
            self.swimSound.stop()
            self.swimSoundPlaying = 0

    def enterSwimming(self, swimSound):
        base.localAvatar.setWalkSpeedNormal()
        self.swimSound = swimSound
        self.swimSoundPlaying = 0
        base.localAvatar.b_setAnimState('swim', base.localAvatar.animMultiplier)
        base.localAvatar.startSleepSwimTest()
        taskMgr.add(self.__swim, 'localToonSwimming')

    def exitSwimming(self):
        taskMgr.remove('localToonSwimming')
        self.swimSound.stop()
        del self.swimSound
        self.swimSoundPlaying = 0
        base.localAvatar.stopSleepSwimTest()

    def __swim(self, task):
        speed = base.mouseInterfaceNode.getSpeed()
        if speed == 0 and self.swimSoundPlaying:
            self.swimSoundPlaying = 0
            self.swimSound.stop()
        elif speed > 0 and self.swimSoundPlaying == 0 and self.IsSwimSoundAudible:
            self.swimSoundPlaying = 1
            base.playSfx(self.swimSound, looping=1)
        return Task.cont

    def enterSlowWalking(self):
        self.accept(base.localAvatar.uniqueName('positiveHP'), self.__handlePositiveHP)
        base.localAvatar.startTrackAnimToSpeed()
        base.localAvatar.setWalkSpeedSlow()

    def __handlePositiveHP(self):
        self.fsm.request('walking')

    def exitSlowWalking(self):
        base.localAvatar.stopTrackAnimToSpeed()
        self.ignore(base.localAvatar.uniqueName('positiveHP'))
