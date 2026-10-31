from direct.directnotify import DirectNotifyGlobal
from panda3d.core import CollisionNode, CollisionSphere
from toontown.cogdominium.DistCogdoCraneObjectAI import DistCogdoCraneObjectAI
from toontown.cogdominium import CogdoCraneGameConsts as Consts


class DistCogdoCraneMoneyBagAI(DistCogdoCraneObjectAI):
    # A money bag for the cranes to drop on the cogs. One left lying where
    # no crane can reach it goes back to its spot beside its crane.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoCraneMoneyBagAI")
    wantsWatchDrift = 0

    def __init__(self, air, craneGame, index):
        DistCogdoCraneObjectAI.__init__(self, air, craneGame)
        self.index = index
        cn = CollisionNode('sphere')
        cn.addSolid(CollisionSphere(0, 0, 4, 4))
        self.attachNewNode(cn)
        self.resetToInitialPosition()

    def delete(self):
        taskMgr.remove(self.uniqueName('return'))
        DistCogdoCraneObjectAI.delete(self)

    def getIndex(self):
        return self.index

    def resetToInitialPosition(self):
        self.setPosHpr(*Consts.MoneyBagPosHprs[self.index])

    def requestInitial(self):
        sender = self.air.getAvatarIdFromSender()
        if self.state != 'Grabbed' and (not self.avId or self._speaksFor(sender, self.avId)):
            self.demand('Initial')

    def inReach(self):
        x, y = self.getX(), self.getY()
        for i in range(len(Consts.CranePosHprs)):
            if Consts.inCraneReach(i, x, y, slack=1.0):
                return True
        return False

    def enterInitial(self):
        self.avId = 0
        self.craneId = 0
        self.resetToInitialPosition()
        self.d_setObjectState('I', 0, 0)

    def exitInitial(self):
        pass

    def enterFree(self):
        DistCogdoCraneObjectAI.enterFree(self)
        if not self.inReach():
            taskMgr.doMethodLater(Consts.BagReturnDelay, self.__return, self.uniqueName('return'))

    def exitFree(self):
        taskMgr.remove(self.uniqueName('return'))

    def __return(self, task):
        if self.state == 'Free':
            self.demand('Initial')
        return task.done
