from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.cogdominium import CogdoGameConsts

# Seconds the toons get to read the rules before the game starts anyway.
IntroTimeout = 40
# Seconds the clients play their finish movie before the floor is done.
FinishDuration = 5


class DistCogdoGameAI(DistributedObjectAI):
    # The game on a field office floor. The interior makes it once all the
    # toons have ridden the elevator up, and hears back through gameDone
    # when it is over.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoGameAI")

    def __init__(self, air, interior):
        DistributedObjectAI.__init__(self, air)
        self.interior = interior
        self.interiorId = interior.doId
        self.exteriorZone = interior.extZoneId
        self.toons = list(interior.toons)
        self.readyToons = set()
        self.sadToons = set()
        self.started = False
        self.finished = False
        self.startTime = 0

    def generate(self):
        DistributedObjectAI.generate(self)
        for avId in self.toons:
            self.accept(self.air.getAvatarExitEvent(avId), self.__handleAvatarExit, [avId])

    def delete(self):
        taskMgr.remove(self.uniqueName('intro-timeout'))
        taskMgr.remove(self.uniqueName('finish'))
        self.ignoreAll()
        self.interior = None
        DistributedObjectAI.delete(self)

    def getInteriorId(self):
        return self.interiorId

    def getExteriorZone(self):
        return self.exteriorZone

    def getDifficultyOverrides(self):
        return [CogdoGameConsts.NoDifficultyOverride, CogdoGameConsts.NoExteriorZoneOverride]

    def getSafezoneId(self):
        return CogdoGameConsts.getSafezoneId(self.exteriorZone)

    def getDifficulty(self):
        return CogdoGameConsts.getDifficulty(self.getSafezoneId())

    def getNetworkTime(self):
        return globalClockDelta.getRealNetworkTime(bits=16)

    def getActiveToons(self):
        return [avId for avId in self.toons if avId not in self.sadToons]

    def start(self):
        # The toons are out of the elevator: show the game and its rules.
        self.sendUpdate('setVisible', [])
        self.sendUpdate('setIntroStart', [])
        taskMgr.doMethodLater(IntroTimeout, self.__introTimeout, self.uniqueName('intro-timeout'))

    def setAvatarReady(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toons:
            self.readyToons.add(avId)
            if self.readyToons >= set(self.toons):
                self.__startGame()

    def __introTimeout(self, task):
        self.__startGame()
        return task.done

    def __startGame(self):
        if self.started:
            return
        taskMgr.remove(self.uniqueName('intro-timeout'))
        self.started = True
        self.startTime = globalClock.getRealTime()
        self.sendUpdate('setGameStart', [self.getNetworkTime()])
        self.startGame()

    def startGame(self):
        pass

    def finishGame(self, failed=False):
        if self.finished:
            return
        self.finished = True
        self.sendUpdate('setGameFinish', [self.getNetworkTime()])
        self.endGame()
        taskMgr.doMethodLater(FinishDuration, self.__finished, self.uniqueName('finish'), extraArgs=[failed])

    def endGame(self):
        pass

    def __finished(self, failed):
        self.interior.gameDone(failed)

    def damageToon(self, avId, damage):
        av = self.air.doId2do.get(avId)
        if not av or damage <= 0 or avId in self.sadToons:
            return
        av.takeDamage(int(damage))
        if av.getHp() <= 0:
            self.sadToons.add(avId)
            self.sendUpdate('setToonSad', [avId])
            self.toonWentSad(avId)

    def toonWentSad(self, avId):
        if not self.getActiveToons():
            self.finishGame(failed=True)

    def __handleAvatarExit(self, avId):
        if avId in self.toons:
            self.toons.remove(avId)
            self.sendUpdate('setToonDisconnect', [avId])
            self.toonLeft(avId)
            if not self.toons:
                self.finishGame(failed=True)
            elif not self.started and self.readyToons >= set(self.toons):
                self.__startGame()

    def toonLeft(self, avId):
        pass

    def getSenderToon(self):
        # The sender, when it is one of the toons still playing.
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toons and self.started and not self.finished:
            return avId
        return 0
