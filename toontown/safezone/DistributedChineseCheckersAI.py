from direct.directnotify import DirectNotifyGlobal
from toontown.safezone.DistributedBoardGameAI import DistributedBoardGameAI
from toontown.safezone.BoardGameRules import ChineseCheckersRules


class DistributedChineseCheckersAI(DistributedBoardGameAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedChineseCheckersAI")
    GameName = 'Chinese Checkers'
    MinPlayers = 2
    MaxPlayers = 6
    MaxQuietMoves = 200

    def __init__(self, air, table):
        DistributedBoardGameAI.__init__(self, air, table)
        self.rules = ChineseCheckersRules()
        self.states = [0] * self.rules.NumSquares

    def getPlayerNums(self, numPlayers):
        return self.rules.PlayerNums[numPlayers]

    def setupBoard(self, playerNums):
        self.states = self.rules.getInitialState(playerNums)
        self.sendUpdate('announceSeatPositions', [self.getSeatPositions()])

    def getSeatPositions(self):
        return [self.seatPlayers.get(seat, 0) for seat in range(6)]

    def requestSeatPositions(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'announceSeatPositions', [self.getSeatPositions()])
        if self.playing:
            self.sendUpdateToAvatarId(avId, 'sendTurn', [self.getCurrentPlayer()])

    def getGameStateArgs(self, move):
        return [self.states, list(move)]

    def applyMove(self, player, move):
        after = self.rules.applyMove(self.states, player, list(move))
        if after is None:
            return None
        self.states = after
        # Marbles are never taken; a move into the target counts as
        # progress for the draw rule.
        return move[-1] in self.rules.getTarget(player)

    def getWinner(self, player):
        return player if self.rules.hasWon(self.states, player) else 0

    def pickMove(self, player):
        return self.rules.pickMove(self.states, player)
