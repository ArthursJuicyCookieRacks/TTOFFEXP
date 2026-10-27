from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI
from toontown.estate import GardenGlobals

# A movie whose movieDone never comes back (the toon left) ends on its own
# after this many seconds.
MOVIE_TIMEOUT = 20


class DistributedLawnDecorAI(DistributedNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedLawnDecorAI")

    def __init__(self, air, garden=None):
        DistributedNodeAI.__init__(self, air)
        self.garden = garden
        self.plot = 0
        self.h = 0
        self.pos = (0, 0, 0)
        self.ownerIndex = 0
        self.movieAvId = 0
        self.movieCallback = None

    def delete(self):
        taskMgr.remove(self.uniqueName('movie-timeout'))
        self.movieCallback = None
        self.garden = None
        DistributedNodeAI.delete(self)

    def setPlot(self, plot):
        self.plot = plot

    def getPlot(self):
        return self.plot

    def setHeading(self, h):
        self.setH(h)
        self.h = h

    def getHeading(self):
        return self.h

    def setPosition(self, x, y, z):
        self.setPos(x, y, z)
        self.pos = (x, y, z)

    def d_setPosition(self, x, y, z):
        self.sendUpdate('setPos', [x, y, z])
        self.sendUpdate('setPosition', [x, y, z])

    def b_setPosition(self, x, y, z):
        self.setPosition(x, y, z)
        self.d_setPosition(x, y, z)

    def getPosition(self):
        return self.pos

    def getOwnerIndex(self):
        return self.ownerIndex

    def setOwnerIndex(self, index):
        self.ownerIndex = index

    def getOwnerId(self):
        if self.garden:
            return self.garden.getOwnerId()
        return 0

    def getOwner(self):
        return self.air.doId2do.get(self.getOwnerId())

    def getOwnerSender(self):
        # The owner's toon when the owner sent this message, otherwise None.
        avId = self.air.getAvatarIdFromSender()
        if not avId or avId != self.getOwnerId():
            self.air.writeServerEvent('suspicious', avId=avId, issue='%s used a garden item it does not own' % self.__class__.__name__)
            return None
        if self.movieCallback:
            self.d_interactionDenied(avId)
            return None
        return self.air.doId2do.get(avId)

    def plotEntered(self):
        pass

    def removeItem(self):
        pass

    def setMovie(self, mode, avId):
        pass

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def startMovie(self, mode, avId, callback=None):
        # Plays a movie on the toon's client; callback runs once the client
        # says the movie is done.
        self.movieAvId = avId
        self.movieCallback = callback or self.clearMovie
        self.d_setMovie(mode, avId)
        taskMgr.doMethodLater(MOVIE_TIMEOUT, self.__movieTimeout, self.uniqueName('movie-timeout'))

    def __movieTimeout(self, task):
        self.__finishMovie()
        return task.done

    def __finishMovie(self):
        taskMgr.remove(self.uniqueName('movie-timeout'))
        callback = self.movieCallback
        self.movieCallback = None
        if callback:
            callback()

    def clearMovie(self):
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, self.movieAvId)
        self.movieAvId = 0

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.movieAvId or not self.movieCallback:
            return
        self.__finishMovie()

    def interactionDenied(self, avId):
        pass

    def d_interactionDenied(self, avId):
        self.sendUpdate('interactionDenied', [avId])
