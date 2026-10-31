from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.cogdominium import CogdoCraneGameConsts as Consts


class DistCogdoCraneCogAI(DistributedObjectAI):
    # A cog with a coin for the Stomp-O-Matic. It walks out of its hallway
    # and down the lit lane to the machine, puts the coin in and flies off.
    # A money bag dropped on it on the way knocks the coin away: it sits
    # dazed for a moment and flies off with nothing.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoCraneCogAI")

    def __init__(self, air, craneGame, dna, entranceId, spawnTime):
        DistributedObjectAI.__init__(self, air)
        self.craneGame = craneGame
        self.dna = dna
        self.entranceId = entranceId
        self.spawnTime = spawnTime
        self.state = 'Walk'
        self.stunTime = 0

    def generate(self):
        DistributedObjectAI.generate(self)
        walk = (Consts.HallwayDistance - Consts.MachineDistance) / Consts.CogWalkSpeed
        taskMgr.doMethodLater(walk, self.__atMachine, self.uniqueName('atMachine'))

    def delete(self):
        taskMgr.remove(self.uniqueName('atMachine'))
        taskMgr.remove(self.uniqueName('insert'))
        taskMgr.remove(self.uniqueName('gone'))
        self.craneGame = None
        DistributedObjectAI.delete(self)

    def getGameId(self):
        return self.craneGame.doId

    def getDNAString(self):
        return self.dna.makeNetString()

    def getSpawnInfo(self):
        return [self.entranceId, self.__networkTime(self.spawnTime)]

    def __networkTime(self, realTime):
        from direct.distributed.ClockDelta import globalClockDelta
        return globalClockDelta.localToNetworkTime(realTime, bits=16)

    def isWalking(self):
        return self.state in ('Walk', 'Insert')

    def __atMachine(self, task):
        if self.state == 'Walk':
            self.state = 'Insert'
            self.sendUpdate('insertCoin', [self.__networkTime(globalClock.getRealTime())])
            taskMgr.doMethodLater(Consts.CogInsertDuration, self.__inserted, self.uniqueName('insert'))
        return task.done

    def __inserted(self, task):
        if self.state == 'Insert':
            self.state = 'Fly'
            if self.craneGame:
                self.craneGame.coinInserted(self)
            self.__goAway(Consts.CogFlyAwayDuration)
        return task.done

    def hitByBag(self, avId):
        if self.state not in ('Walk', 'Insert'):
            return
        taskMgr.remove(self.uniqueName('atMachine'))
        taskMgr.remove(self.uniqueName('insert'))
        self.state = 'Stunned'
        self.stunTime = globalClock.getRealTime()
        self.sendUpdate('setStunned', [self.__networkTime(self.stunTime)])
        self.__goAway(Consts.CogStunDuration + Consts.CogFlyAwayDuration)

    def flyAway(self):
        # The game is over: the cogs still walking leave.
        if self.state in ('Walk', 'Insert'):
            taskMgr.remove(self.uniqueName('atMachine'))
            taskMgr.remove(self.uniqueName('insert'))
            self.state = 'Fly'
            self.sendUpdate('setStunned', [self.__networkTime(globalClock.getRealTime() - Consts.CogStunDuration)])
            self.__goAway(Consts.CogFlyAwayDuration)

    def __goAway(self, delay):
        taskMgr.doMethodLater(delay, self.__gone, self.uniqueName('gone'))

    def __gone(self, task):
        if self.craneGame:
            self.craneGame.cogDone(self)
        return task.done

