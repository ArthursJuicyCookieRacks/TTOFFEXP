from direct.directnotify import DirectNotifyGlobal
from toontown.safezone.DistributedBoardGameAI import DistributedBoardGameAI
from toontown.safezone.BoardGameRules import CheckersRules


class DistributedCheckersAI(DistributedBoardGameAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedCheckersAI")
    GameName = 'Checkers'
    MinPlayers = 2
    MaxPlayers = 2

    def __init__(self, air, table):
        DistributedBoardGameAI.__init__(self, air, table)
        self.rules = CheckersRules()
        self.states = self.rules.getInitialState()

    def setupBoard(self, playerNums):
        self.states = self.rules.getInitialState()

    def getGameStateArgs(self, move):
        return [self.states, list(move)]

    def applyMove(self, player, move):
        after = self.rules.applyMove(self.states, player, list(move))
        if after is None:
            return None
        captured = after.count(0) > self.states.count(0)
        self.states = after
        return captured

    def d_setGameState(self, move):
        # The client animates the piece from where it stood, so the move
        # goes out with the board as it is after it.
        self.sendUpdate('setGameState', [self.states, list(move)])

    def getWinner(self, player):
        return self.rules.getWinner(self.states, 3 - player)

    def pickMove(self, player):
        return self.rules.pickMove(self.states, player)
