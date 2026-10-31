from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.fsm import FSM


class DistCogdoCraneAI(DistributedObjectAI, FSM.FSM):
    # One of the four cranes of the Vend-A-Stomper. A toon steps up to its
    # controls to take it; it is theirs until they step off.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoCraneAI")

    def __init__(self, air, craneGame, index):
        DistributedObjectAI.__init__(self, air)
        FSM.FSM.__init__(self, 'DistCogdoCraneAI')
        self.craneGame = craneGame
        self.index = index
        self.avId = 0
        self.objectId = 0

    def delete(self):
        self.demand('Off')
        self.craneGame = None
        DistributedObjectAI.delete(self)

    def getCraneGameId(self):
        return self.craneGame.doId

    def getIndex(self):
        return self.index

    def getState(self):
        if self.state == 'Controlled':
            return ['C', self.avId]
        return ['F', 0]

    def d_setState(self, state, avId):
        self.sendUpdate('setState', [state, avId])

    def requestControl(self):
        avId = self.air.getAvatarIdFromSender()
        game = self.craneGame
        self.notify.info('crane %s requestControl from %s: state %s avId %s playing %s' % (self.index, avId, self.state, self.avId, game and game.isPlaying(avId)))
        if game is None or not game.isPlaying(avId) or game.finished:
            return
        if self.state == 'Free' and self.avId == 0 and not self.__craneOf(avId):
            self.request('Controlled', avId)

    def requestFree(self):
        avId = self.air.getAvatarIdFromSender()
        if avId == self.avId and self.state == 'Controlled':
            self.request('Free')

    def removeToon(self, avId):
        if avId == self.avId and self.state == 'Controlled':
            self.request('Free')

    def __craneOf(self, avId):
        for crane in self.craneGame.cranes:
            if crane.avId == avId:
                return crane
        return None

    def enterOff(self):
        self.__dropHeld()
        self.avId = 0

    def exitOff(self):
        pass

    def enterControlled(self, avId):
        self.avId = avId
        self.d_setState('C', avId)

    def exitControlled(self):
        self.__dropHeld()

    def __dropHeld(self):
        if self.objectId:
            obj = self.air.doId2do.get(self.objectId)
            if obj is not None and obj.state == 'Grabbed':
                obj.request('Dropped', self.avId, self.doId)
            self.objectId = 0

    def enterFree(self):
        self.avId = 0
        self.d_setState('F', 0)

    def exitFree(self):
        pass
