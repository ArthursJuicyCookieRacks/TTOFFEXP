from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedNodeAI import DistributedNodeAI
from toontown.safezone.DistributedChineseCheckersAI import DistributedChineseCheckersAI
from toontown.safezone.DistributedCheckersAI import DistributedCheckersAI
from toontown.safezone.DistributedFindFourAI import DistributedFindFourAI

NumSeats = 6
# The games on the game menu, by the number the client picks them with.
Games = {1: DistributedChineseCheckersAI,
         2: DistributedCheckersAI,
         3: DistributedFindFourAI}
# Seconds the winner gets to dance before everyone gets up.
GameOverDelay = 4
PosFields = ['setX', 'setY', 'setZ', 'setH', 'setP', 'setR']


class DistributedPicnicTableAI(DistributedNodeAI):
    # A game table: toons sit down, the first one picks a game, and the game
    # is played in a zone of its own that the seated toons and the
    # onlookers listen to.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPicnicTableAI")

    def __init__(self, air, zoneId=None, name='', x=0, y=0, z=0, h=0, p=0, r=0):
        DistributedNodeAI.__init__(self, air)
        self.name = name
        self.seats = [0] * NumSeats
        self.observers = []
        self.picker = 0
        self.game = None
        self.gameZone = 0
        self.isPlaying = 0
        self.setPosHpr(x, y, z, h, p, r)
        if zoneId is not None:
            self.generateWithRequired(zoneId, optionalFields=PosFields)

    def delete(self):
        taskMgr.remove(self.uniqueName('game-over'))
        for avId in self.seats + self.observers:
            if avId:
                self.ignore(self.air.getAvatarExitEvent(avId))
        self.__deleteGame()
        DistributedNodeAI.delete(self)

    def getSeatedToons(self):
        return [avId for avId in self.seats if avId]

    def getSeatedSeats(self):
        return [seat for seat, avId in enumerate(self.seats) if avId]

    def getFreeSeats(self):
        return [seat for seat, avId in enumerate(self.seats) if not avId]

    def getSeatAvatar(self, seat):
        return self.seats[seat]

    def __timestamp(self):
        return globalClockDelta.getRealNetworkTime(bits=16)

    def d_setTableState(self):
        self.sendUpdate('setTableState', [self.seats, self.isPlaying])

    def getTableState(self):
        return [self.seats, self.isPlaying]

    def getIsPlaying(self):
        return self.isPlaying

    def requestTableState(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'setTableState', [self.seats, self.isPlaying])

    def requestJoin(self, seat, x, y, z, h, p, r):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.seats:
            return
        maxPlayers = self.game.MaxPlayers if self.game else NumSeats
        if not 0 <= seat < NumSeats or self.seats[seat] or self.isPlaying or len(self.getSeatedToons()) >= maxPlayers:
            self.sendUpdateToAvatarId(avId, 'rejectJoin', [])
            return
        self.seats[seat] = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleAvatarExit, [avId])
        self.sendUpdate('fillSlot', [avId, seat, x, y, z, h, p, r, self.__timestamp(), self.doId])
        self.d_setTableState()
        if self.game:
            # The game is picked and waiting for its players.
            self.sendUpdateToAvatarId(avId, 'setZone', [self.gameZone])
        elif not self.picker:
            self.picker = avId
            self.sendUpdateToAvatarId(avId, 'allowPick', [])

    def requestPickedGame(self, gameNum):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.picker or self.game or gameNum not in Games:
            return
        gameClass = Games[gameNum]
        if len(self.getSeatedToons()) > gameClass.MaxPlayers:
            # Too many toons for this game; let them pick again.
            self.sendUpdateToAvatarId(avId, 'allowPick', [])
            return
        self.gameZone = self.air.allocateZone()
        self.game = gameClass(self.air, self)
        self.game.setPosHpr(self.getX(), self.getY(), self.getZ(), self.getH(), self.getP(), self.getR())
        self.game.generateWithRequired(self.gameZone, optionalFields=PosFields)
        for seated in self.getSeatedToons():
            self.sendUpdateToAvatarId(seated, 'setZone', [self.gameZone])

    def gameStarted(self):
        self.isPlaying = 1
        self.sendUpdate('setIsPlaying', [1])
        self.d_setTableState()

    def gameOver(self, gameName, avId, hasWinner):
        # The winner is named by avId, or 0 for a computer player; without
        # hasWinner the game was a draw.
        if not hasWinner:
            gameName += ' Tie'
        self.sendUpdate('announceWinner', [gameName, avId])
        taskMgr.doMethodLater(GameOverDelay, self.__clearTable, self.uniqueName('game-over'))

    def __clearTable(self, task=None):
        for seat, avId in enumerate(self.seats):
            if avId:
                self.__emptySeat(seat)
        for avId in self.observers:
            self.ignore(self.air.getAvatarExitEvent(avId))
            self.sendUpdateToAvatarId(avId, 'emptySlot', [avId, 255, self.__timestamp()])
        self.observers = []
        self.__reset()
        if task:
            return task.done

    def __reset(self):
        self.__deleteGame()
        self.picker = 0
        self.isPlaying = 0
        self.sendUpdate('setIsPlaying', [0])
        self.d_setTableState()

    def __deleteGame(self):
        if self.game:
            self.game.requestDelete()
            self.game = None
        if self.gameZone:
            self.air.deallocateZone(self.gameZone)
            self.gameZone = 0

    def __emptySeat(self, seat):
        avId = self.seats[seat]
        self.seats[seat] = 0
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.sendUpdate('emptySlot', [avId, seat, self.__timestamp()])
        return avId

    def requestExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.seats:
            self.__leave(avId)

    def __handleAvatarExit(self, avId):
        if avId in self.seats:
            self.__leave(avId)
        elif avId in self.observers:
            self.observers.remove(avId)

    def __leave(self, avId):
        seat = self.seats.index(avId)
        self.__emptySeat(seat)
        self.d_setTableState()
        if self.game:
            self.game.playerLeft(avId, seat)
        if not self.getSeatedToons():
            taskMgr.remove(self.uniqueName('game-over'))
            self.__clearTable()
        elif avId == self.picker and not self.game:
            # The next toon at the table picks the game instead.
            self.picker = self.getSeatedToons()[0]
            self.sendUpdateToAvatarId(self.picker, 'allowPick', [])

    def requestObserve(self):
        self.requestGameZone()

    def requestGameZone(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.game or avId in self.seats:
            return
        if avId not in self.observers:
            self.observers.append(avId)
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleAvatarExit, [avId])
        self.sendUpdateToAvatarId(avId, 'setGameZone', [self.gameZone, self.isPlaying])

    def leaveObserve(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.observers:
            self.observers.remove(avId)
            self.ignore(self.air.getAvatarExitEvent(avId))

    def requestZone(self):
        avId = self.air.getAvatarIdFromSender()
        if self.game and (avId in self.seats or avId in self.observers):
            self.sendUpdateToAvatarId(avId, 'setZone', [self.gameZone])
