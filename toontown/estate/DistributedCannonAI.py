from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.estate import CannonGlobals


class DistributedCannonAI(DistributedObjectAI):
    # One of the rental cannons beside the houses. A toon climbs in, aims
    # and lights the fuse; the flight itself is played by every client.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedCannonAI")

    def __init__(self, air, estateId=0, targetId=0, x=0, y=0, z=0, h=0, p=0, r=0):
        DistributedObjectAI.__init__(self, air)
        self.estateId = estateId
        self.targetId = targetId
        self.posHpr = (x, y, z, h, p, r)
        self.bumperPos = (0, 0, 0)
        self.active = 1
        self.avId = 0

    def delete(self):
        self.__stopTimeout()
        if self.avId:
            self.ignore(self.air.getAvatarExitEvent(self.avId))
        DistributedObjectAI.delete(self)

    def setEstateId(self, estateId):
        self.estateId = estateId

    def getEstateId(self):
        return self.estateId

    def setTargetId(self, targetId):
        self.targetId = targetId

    def getTargetId(self):
        return self.targetId

    def setPosHpr(self, x, y, z, h, p, r):
        self.posHpr = (x, y, z, h, p, r)

    def getPosHpr(self):
        return self.posHpr

    def setCannonBumperPos(self, x, y, z):
        self.bumperPos = (x, y, z)

    def getCannonBumperPos(self):
        return self.bumperPos

    def setActive(self, active):
        # The secret arrow code shows or hides the cannons for everyone.
        self.active = active
        self.sendUpdate('setActiveState', [active])

    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId:
            self.sendUpdateToAvatarId(avId, 'requestExit', [])
            return
        self.avId = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleAvatarExit)
        self.d_setMovie(CannonGlobals.CANNON_MOVIE_LOAD, avId)
        self.__startTimeout()

    def __startTimeout(self):
        self.__stopTimeout()
        taskMgr.doMethodLater(CannonGlobals.CANNON_TIMEOUT, self.__timeout, self.uniqueName('cannon-timeout'))

    def __stopTimeout(self):
        taskMgr.remove(self.uniqueName('cannon-timeout'))

    def __timeout(self, task):
        # The toon sat in the cannon too long without firing.
        avId = self.avId
        self.__clearAvatar()
        self.d_setMovie(CannonGlobals.CANNON_MOVIE_FORCE_EXIT, avId)
        self.d_setMovie(CannonGlobals.CANNON_MOVIE_CLEAR, 0)
        return task.done

    def __handleAvatarExit(self):
        self.__clearAvatar()
        self.d_setMovie(CannonGlobals.CANNON_MOVIE_CLEAR, 0)

    def __clearAvatar(self):
        self.__stopTimeout()
        if self.avId:
            self.ignore(self.air.getAvatarExitEvent(self.avId))
        self.avId = 0

    def __isShooter(self):
        return self.avId and self.air.getAvatarIdFromSender() == self.avId

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def setCannonPosition(self, zRot, angle):
        if self.__isShooter():
            self.sendUpdate('updateCannonPosition', [self.avId, zRot, angle])

    def setCannonLit(self, zRot, angle):
        if not self.__isShooter():
            return
        self.__stopTimeout()
        self.sendUpdate('setCannonWillFire', [self.avId, 0.0, zRot, angle,
                                              globalClockDelta.getRealNetworkTime(bits=16)])

    def setFired(self):
        pass

    def setLanded(self):
        if not self.__isShooter():
            return
        self.__clearAvatar()
        self.d_setMovie(CannonGlobals.CANNON_MOVIE_CLEAR, 0)

    def requestBumperMove(self, x, y, z):
        if self.__isShooter():
            self.bumperPos = (x, y, z)
            self.sendUpdate('setCannonBumperPos', [x, y, z])
