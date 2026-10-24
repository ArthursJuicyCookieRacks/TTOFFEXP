from direct.directnotify import DirectNotifyGlobal
from direct.fsm import FSM
from direct.interval.IntervalGlobal import *
from direct.task import Task
from direct.distributed.ClockDelta import globalClockDelta
from direct.showbase.PythonUtil import lerp
from toontown.pets import PetTricks
from toontown.toon import DistributedToonAI

class PetActionFSM(FSM.FSM):
    notify = DirectNotifyGlobal.directNotify.newCategory('PetActionFSM')

    def __init__(self, pet):
        FSM.FSM.__init__(self, PetActionFSM.__name__)
        self.pet = pet
        self.trickSerialNum = 0

    def destroy(self):
        self.cleanup()

    # The pet moves with PetMoverAI, which walks to a point or an avatar;
    # these stand in for the impulses the original mover took.
    def __wander(self):
        if self.pet.mover.state != 'Wander':
            self.pet.mover.request('Wander')

    def __stopMoving(self):
        if self.pet.mover.state not in ('Still', 'Off'):
            self.pet.mover.request('Still')

    def enterNeutral(self):
        PetActionFSM.notify.debug('enterNeutral')

    def exitNeutral(self):
        pass

    def enterChase(self, target):
        PetActionFSM.notify.debug('enterChase: %s' % target)
        self.pet.mover.walkToAvatar(target)
        self.pet.unstickFSM.request('on')

    def exitChase(self):
        self.pet.unstickFSM.request('off')
        self.__stopMoving()

    def enterFlee(self, chaser):
        PetActionFSM.notify.debug('enterFlee: %s' % chaser)
        # PetMoverAI has no fleeing; the pet runs off somewhere else.
        self.__wander()
        self.pet.unstickFSM.request('on')

    def exitFlee(self):
        self.pet.unstickFSM.request('off')
        self.__stopMoving()

    def enterWander(self):
        PetActionFSM.notify.debug('enterWander')
        self.__wander()

    def exitWander(self):
        pass

    def enterUnstick(self):
        PetActionFSM.notify.debug('enterUnstick')
        self.__wander()

    def exitUnstick(self):
        pass

    def enterInspectSpot(self, spot):
        PetActionFSM.notify.debug('enterInspectSpot')
        self.pet.mover.walkToAvatar(spot)
        self.pet.unstickFSM.request('on')

    def exitInspectSpot(self):
        self.pet.unstickFSM.request('off')
        self.__stopMoving()

    def enterStay(self, avatar):
        PetActionFSM.notify.debug('enterStay')

    def exitStay(self):
        pass

    def enterHeal(self, avatar):
        PetActionFSM.notify.debug('enterHeal')
        avatar.toonUp(3)
        self.pet.mover.walkToAvatar(avatar)

    def exitHeal(self):
        self.__stopMoving()

    def enterTrick(self, avatar, trickId):
        PetActionFSM.notify.debug('enterTrick')
        if not self.pet.isLockedDown():
            self.pet.lockPet()
        self.pet.sendUpdate('doTrick', [trickId, globalClockDelta.getRealNetworkTime()])

        def finish(avatar = avatar, trickId = trickId, self = self):
            if hasattr(self.pet, 'brain'):
                healRange = PetTricks.TrickHeals[trickId]
                aptitude = self.pet.getTrickAptitude(trickId)
                healAmt = int(lerp(healRange[0], healRange[1], aptitude))
                if healAmt:
                    for avId in self.pet.brain.getAvIdsLookingAtUs():
                        av = self.pet.air.doId2do.get(avId)
                        if av:
                            if isinstance(av, DistributedToonAI.DistributedToonAI):
                                av.toonUp(healAmt)

                self.pet._handleDidTrick(trickId)
                if not self.pet.isLockedDown():
                    self.pet.unlockPet()
                messenger.send(self.getTrickDoneEvent())

        self.trickDoneEvent = 'trickDone-%s-%s' % (self.pet.doId, self.trickSerialNum)
        self.trickSerialNum += 1
        self.trickFinishIval = Sequence(WaitInterval(PetTricks.TrickLengths[trickId]), Func(finish), name='petTrickFinish-%s' % self.pet.doId)
        self.trickFinishIval.start()

    def getTrickDoLaterName(self):
        return 'petTrickDoLater-%s' % self.pet.doId

    def getTrickDoneEvent(self):
        return self.trickDoneEvent

    def exitTrick(self):
        if self.trickFinishIval.isPlaying():
            self.trickFinishIval.finish()
        del self.trickFinishIval
        if self.pet.isLockedDown():
            self.pet.unlockPet()
        del self.trickDoneEvent

    def enterMovie(self):
        PetActionFSM.notify.debug('enterMovie')

    def exitMovie(self):
        pass
