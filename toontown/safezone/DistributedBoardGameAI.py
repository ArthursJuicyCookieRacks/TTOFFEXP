from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedNodeAI import DistributedNodeAI

# Seconds the players get to press Start, and to make each move.
BeginTime = 60
TurnTime = 60
# Seconds a computer player thinks before it moves.
ComputerMoveTime = 2.0
# A game where nobody can win any more ends after this many moves.
MaxQuietMoves = 80


class DistributedBoardGameAI(DistributedNodeAI):
    # A game on a picnic table. The seated toons press Start; seats the
    # game still needs are then taken by computer players, so a toon can
    # always play, also alone.
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBoardGameAI')
    GameName = ''
    MinPlayers = 2
    MaxPlayers = 2
    MaxQuietMoves = MaxQuietMoves

    def __init__(self, air, table):
        DistributedNodeAI.__init__(self, air)
        self.table = table
        self.tableDoId = table.doId
        self.playing = False
        self.ready = set()
        # The player numbers by seat; a seat without a toon may still have
        # a computer player.
        self.seatPlayers = {}
        self.computerSeats = set()
        self.turnOrder = []
        self.turn = 0
        self.quietMoves = 0
        self.timerEnd = self.__networkTime(BeginTime)
        self.turnEnd = 0

    def generate(self):
        DistributedNodeAI.generate(self)
        taskMgr.doMethodLater(BeginTime, self.__beginTimeout, self.uniqueName('begin-timeout'))

    def delete(self):
        taskMgr.remove(self.uniqueName('begin-timeout'))
        taskMgr.remove(self.uniqueName('turn-timeout'))
        taskMgr.remove(self.uniqueName('computer-move'))
        self.table = None
        DistributedNodeAI.delete(self)

    def __networkTime(self, seconds):
        return globalClockDelta.localToNetworkTime(globalClock.getRealTime() + seconds, bits=16)

    def getTableDoId(self):
        return self.tableDoId

    def getTimer(self):
        return self.timerEnd

    def getTurnTimer(self):
        return self.turnEnd

    def requestTimer(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'setTimer', [self.timerEnd])

    def requestExit(self):
        self.table.requestExit()

    def requestBegin(self):
        avId = self.air.getAvatarIdFromSender()
        if self.playing or avId not in self.table.getSeatedToons():
            return
        self.ready.add(avId)
        if self.ready >= set(self.table.getSeatedToons()):
            self.startGame()

    def __beginTimeout(self, task):
        if not self.playing and self.table.getSeatedToons():
            self.startGame()
        return task.done

    def getPlayerCount(self, numToons):
        return min(self.MaxPlayers, max(self.MinPlayers, numToons))

    def getPlayerNums(self, numPlayers):
        return list(range(1, numPlayers + 1))

    def startGame(self):
        taskMgr.remove(self.uniqueName('begin-timeout'))
        self.playing = True
        seats = self.table.getSeatedSeats()[:self.MaxPlayers]
        numPlayers = self.getPlayerCount(len(seats))
        # The computer players sit in the free seats across from the toons.
        free = [seat for seat in self.table.getFreeSeats() if seat not in seats]
        free.sort(key=lambda seat: -min([abs(seat - other) for other in seats] or [0]))
        computerSeats = free[:numPlayers - len(seats)]
        allSeats = sorted(seats + computerSeats)
        playerNums = self.getPlayerNums(numPlayers)
        self.seatPlayers = dict(zip(allSeats, playerNums))
        self.computerSeats = set(computerSeats)
        self.turnOrder = sorted(playerNums)
        self.turn = 0
        self.quietMoves = 0
        self.table.gameStarted()
        for seat, playerNum in self.seatPlayers.items():
            avId = self.table.getSeatAvatar(seat)
            if avId:
                self.sendUpdateToAvatarId(avId, 'gameStart', [playerNum])
        self.setupBoard(playerNums)
        self.d_setGameState([])
        self.startTurn()

    def getCurrentPlayer(self):
        return self.turnOrder[self.turn]

    def getPlayerSeat(self, playerNum):
        for seat, num in self.seatPlayers.items():
            if num == playerNum:
                return seat
        return None

    def getPlayerAvatar(self, playerNum):
        seat = self.getPlayerSeat(playerNum)
        if seat is None or seat in self.computerSeats:
            return 0
        return self.table.getSeatAvatar(seat)

    def getAvatarPlayer(self, avId):
        for seat, num in self.seatPlayers.items():
            if seat not in self.computerSeats and self.table.getSeatAvatar(seat) == avId:
                return num
        return None

    def startTurn(self):
        taskMgr.remove(self.uniqueName('turn-timeout'))
        taskMgr.remove(self.uniqueName('computer-move'))
        player = self.getCurrentPlayer()
        self.turnEnd = self.__networkTime(TurnTime)
        self.sendUpdate('sendTurn', [player])
        self.sendUpdate('setTurnTimer', [self.turnEnd])
        if self.getPlayerAvatar(player):
            taskMgr.doMethodLater(TurnTime, self.__turnTimeout, self.uniqueName('turn-timeout'))
        else:
            taskMgr.doMethodLater(ComputerMoveTime, self.__computerMove, self.uniqueName('computer-move'))

    def __turnTimeout(self, task):
        # The toon took too long; the move is made for them.
        self.__computerMove(task)
        return task.done

    def __computerMove(self, task):
        if self.playing:
            move = self.pickMove(self.getCurrentPlayer())
            if move is None:
                self.endGame(0)
            else:
                self.doMove(move)
        return task.done

    def requestMove(self, move):
        avId = self.air.getAvatarIdFromSender()
        if not self.playing or self.getAvatarPlayer(avId) != self.getCurrentPlayer():
            return
        if not self.doMove(move):
            # The board on the client got out of step; send it again.
            self.sendUpdateToAvatarId(avId, 'setGameState', self.getGameStateArgs([]))
            self.sendUpdateToAvatarId(avId, 'sendTurn', [self.getCurrentPlayer()])

    def doMove(self, move):
        # Plays a move for the current player and returns whether it was
        # allowed.
        player = self.getCurrentPlayer()
        captured = self.applyMove(player, move)
        if captured is None:
            return False
        self.quietMoves = 0 if captured else self.quietMoves + 1
        self.d_setGameState(move)
        winner = self.getWinner(player)
        if winner:
            self.endGame(winner)
        elif winner is None or self.quietMoves >= self.MaxQuietMoves:
            self.endGame(0)
        else:
            self.turn = (self.turn + 1) % len(self.turnOrder)
            self.startTurn()
        return True

    def requestWin(self, *args):
        # The server sees wins on its own.
        pass

    def endGame(self, winner):
        # winner is a player number, or 0 when nobody won.
        self.playing = False
        taskMgr.remove(self.uniqueName('turn-timeout'))
        taskMgr.remove(self.uniqueName('computer-move'))
        avId = self.getPlayerAvatar(winner) if winner else 0
        self.announceWinner(winner, avId)
        self.sendUpdate('announceWin', [avId])
        self.table.gameOver(self.GameName, avId, winner != 0)
        if avId:
            self.air.writeServerEvent('board_game_won', avId=avId, game=self.GameName)

    def announceWinner(self, winner, avId):
        pass

    def playerLeft(self, avId, seat):
        # A toon got up. A computer player takes over their side, unless no
        # toon is left at the table.
        if not self.playing:
            self.ready.discard(avId)
            return
        if not self.table.getSeatedToons():
            self.playing = False
            taskMgr.remove(self.uniqueName('turn-timeout'))
            taskMgr.remove(self.uniqueName('computer-move'))
            return
        if seat in self.seatPlayers:
            self.computerSeats.add(seat)
            if self.seatPlayers[seat] == self.getCurrentPlayer():
                self.startTurn()

    # Each game fills these in:

    def setupBoard(self, playerNums):
        pass

    def getGameStateArgs(self, move):
        return []

    def d_setGameState(self, move):
        self.sendUpdate('setGameState', self.getGameStateArgs(move))

    def getGameState(self):
        return self.getGameStateArgs([])

    def applyMove(self, player, move):
        # Returns None for a move that is not allowed, else whether it
        # took something.
        return None

    def getWinner(self, player):
        # The winning player number, 0 to play on, or None for a draw.
        return 0

    def pickMove(self, player):
        return None
