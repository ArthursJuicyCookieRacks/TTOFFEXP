from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedSmoothNodeAI import DistributedSmoothNodeAI
from direct.fsm import FSM
from direct.task import Task


class DistCogdoCraneObjectAI(DistributedSmoothNodeAI, FSM.FSM):
    # Something the Vend-A-Stomper's cranes can pick up. The toon whose
    # crane holds or dropped it runs its physics and says where it is;
    # offline the player's client also runs the NPC toons' cranes, so it
    # may speak for an NPC's object too.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoCraneObjectAI")
    wantsWatchDrift = 1

    def __init__(self, air, craneGame):
        DistributedSmoothNodeAI.__init__(self, air)
        FSM.FSM.__init__(self, 'DistCogdoCraneObjectAI')
        self.craneGame = craneGame
        self.avId = 0
        self.craneId = 0

    def delete(self):
        self.stopWaitFree()
        self.demand('Off')
        self.craneGame = None
        DistributedSmoothNodeAI.delete(self)

    def getCraneGameId(self):
        return self.craneGame.doId

    def d_setObjectState(self, state, avId, craneId):
        self.sendUpdate('setObjectState', [state, avId, craneId])

    def _speaksFor(self, sender, avId):
        # The sender, or the client running an NPC toon's crane.
        if sender == avId:
            return True
        av = self.air.doId2do.get(avId)
        return av is not None and getattr(av, 'isNPCPlayer', lambda: False)()

    def _craneOf(self, avId):
        if self.craneGame:
            for crane in self.craneGame.cranes:
                if crane.avId == avId and crane.state == 'Controlled':
                    return crane
        return None

    def startWaitFree(self, delayTime):
        name = self.uniqueName('waitFree')
        taskMgr.remove(name)
        taskMgr.doMethodLater(delayTime, self.doFree, name)

    def stopWaitFree(self):
        taskMgr.remove(self.uniqueName('waitFree'))

    def doFree(self, task=None):
        if not self.isDeleted() and self.state not in ('Off', 'Initial'):
            self.demand('Free')
        return Task.done

    def requestGrab(self, avId=None):
        # A crane's magnet touched this. avId: the NPC whose crane it is.
        sender = self.air.getAvatarIdFromSender()
        avId = avId or sender
        crane = self._craneOf(avId)
        if self.state not in ('Grabbed', 'Off') and crane and not crane.objectId and self._speaksFor(sender, avId):
            self.demand('Grabbed', avId, crane.doId)
            return
        self.sendUpdateToAvatarId(sender, 'rejectGrab', [])

    def requestDrop(self):
        sender = self.air.getAvatarIdFromSender()
        if self.state == 'Grabbed' and self._speaksFor(sender, self.avId):
            self.demand('Dropped', self.avId, self.craneId)

    def hitFloor(self):
        sender = self.air.getAvatarIdFromSender()
        if self.state == 'Dropped' and self._speaksFor(sender, self.avId):
            self.demand('SlidingFloor', self.avId)

    def requestFree(self, x, y, z, h):
        sender = self.air.getAvatarIdFromSender()
        if self.state in ('Dropped', 'SlidingFloor') and self._speaksFor(sender, self.avId):
            self.setPosHpr(x, y, 0, h, 0, 0)
            self.demand('WaitFree')

    def hitBoss(self, impact):
        pass

    def hitCog(self, cogId):
        sender = self.air.getAvatarIdFromSender()
        if self.state in ('Grabbed', 'Dropped', 'SlidingFloor') and self._speaksFor(sender, self.avId):
            self.craneGame.hitCog(self.avId, self, cogId)

    def removeToon(self, avId):
        if avId == self.avId and self.state not in ('Off', 'Free', 'Initial'):
            self.doFree()

    def __setCraneObject(self, craneId, objectId):
        crane = self.air.doId2do.get(craneId)
        if crane is not None:
            crane.objectId = objectId

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterGrabbed(self, avId, craneId):
        self.avId = avId
        self.craneId = craneId
        self.__setCraneObject(craneId, self.doId)
        self.d_setObjectState('G', avId, craneId)

    def exitGrabbed(self):
        self.__setCraneObject(self.craneId, 0)

    def enterDropped(self, avId, craneId):
        self.avId = avId
        self.craneId = craneId
        self.d_setObjectState('D', avId, craneId)
        self.startWaitFree(10)

    def exitDropped(self):
        self.stopWaitFree()

    def enterSlidingFloor(self, avId):
        self.avId = avId
        self.d_setObjectState('s', avId, 0)
        if self.wantsWatchDrift:
            self.startWaitFree(5)

    def exitSlidingFloor(self):
        self.stopWaitFree()

    def enterWaitFree(self):
        self.avId = 0
        self.craneId = 0
        self.startWaitFree(1)

    def exitWaitFree(self):
        self.stopWaitFree()

    def enterFree(self):
        self.avId = 0
        self.craneId = 0
        self.d_setObjectState('F', 0, 0)

    def exitFree(self):
        pass
