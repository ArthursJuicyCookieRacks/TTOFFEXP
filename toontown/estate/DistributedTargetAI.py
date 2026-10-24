from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

# The Toon-up Target: every hit in a row raises the level by one, and the
# toon is healed by the new level. The time to land the next hit shrinks as
# the level goes up; a miss or running out of time starts over.
MaxLevel = 10
StartTime = 30
MinTime = 10
TimeStep = 2


class DistributedTargetAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedTargetAI")

    def __init__(self, air, x=0, y=0, z=0):
        DistributedObjectAI.__init__(self, air)
        self.position = (x, y, z)
        self.enabled = 0
        self.score = 0
        self.time = 0
        self.pinballHiScore = 0
        self.pinballHiScorer = ''

    def delete(self):
        taskMgr.remove(self.uniqueName('target-timeout'))
        DistributedObjectAI.delete(self)

    def setPosition(self, x, y, z):
        self.position = (x, y, z)

    def getPosition(self):
        return self.position

    def d_setState(self):
        self.sendUpdate('setState', [self.enabled, self.score, self.time])

    def setEnabled(self, enabled):
        self.enabled = enabled
        self.score = 0
        self.time = 0
        taskMgr.remove(self.uniqueName('target-timeout'))
        self.d_setState()

    def __getHitTime(self):
        return max(MinTime, StartTime - TimeStep * int(self.score))

    def __restart(self):
        taskMgr.remove(self.uniqueName('target-timeout'))
        self.score = 0
        self.time = 0
        self.d_setState()

    def __timeout(self, task):
        self.__restart()
        return task.done

    def setResult(self, avId):
        if not self.enabled:
            return
        senderId = self.air.getAvatarIdFromSender()
        if not avId:
            self.__restart()
            return
        if avId != senderId:
            return
        av = self.air.doId2do.get(avId)
        if not av:
            return
        self.score = min(int(self.score) + 1, MaxLevel)
        self.time = self.__getHitTime()
        av.toonUp(int(self.score))
        self.sendUpdate('setReward', [int(self.score)])
        self.d_setState()
        taskMgr.remove(self.uniqueName('target-timeout'))
        taskMgr.doMethodLater(self.time, self.__timeout, self.uniqueName('target-timeout'))

    def setBonus(self, bonus):
        # Bouncing off a cloud on the way is worth a little extra.
        if self.enabled and self.score:
            self.score = min(self.score + bonus, MaxLevel)
            self.d_setState()

    def setCurPinballScore(self, avId, score, multiplier):
        if avId != self.air.getAvatarIdFromSender():
            return
        av = self.air.doId2do.get(avId)
        total = score * multiplier
        if av and total > self.pinballHiScore:
            self.pinballHiScore = total
            self.pinballHiScorer = av.getName()
            self.sendUpdate('setPinballHiScorer', [self.pinballHiScorer])
            self.sendUpdate('setPinballHiScore', [self.pinballHiScore])

    def getPinballHiScorer(self):
        return self.pinballHiScorer

    def getPinballHiScore(self):
        return self.pinballHiScore
