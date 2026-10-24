from direct.directnotify import DirectNotifyGlobal
from toontown.safezone.DistributedBoardGameAI import DistributedBoardGameAI
from toontown.safezone.BoardGameRules import FindFourRules


class DistributedFindFourAI(DistributedBoardGameAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedFindFourAI")
    GameName = 'Find Four'
    MinPlayers = 2
    MaxPlayers = 2

    def __init__(self, air, table):
        DistributedBoardGameAI.__init__(self, air, table)
        self.rules = FindFourRules()
        self.board = self.rules.getInitialState()
        self.lastMove = (0, 0, 0)

    def setupBoard(self, playerNums):
        self.board = self.rules.getInitialState()
        self.lastMove = (0, 0, 0)

    def getGameStateArgs(self, move):
        # The client drops the piece in column moveCol down to row movePos;
        # turn is 0 for player 1 and 1 for player 2. All zero just shows the
        # board.
        moveCol, movePos, turn = self.lastMove if move else (0, 0, 0)
        return [self.board, moveCol, movePos, turn]

    def applyMove(self, player, move):
        if isinstance(move, (list, tuple)):
            move = move[0] if move else -1
        after, row = self.rules.applyMove(self.board, player, move)
        if after is None:
            return None
        self.board = after
        self.lastMove = (move, row, player - 1)
        return False

    def doMove(self, move):
        return DistributedBoardGameAI.doMove(self, [move] if not isinstance(move, (list, tuple)) else move)

    def getWinner(self, player):
        if self.rules.findWin(self.board, player):
            return player
        if self.rules.isFull(self.board):
            return None
        return 0

    def announceWinner(self, winner, avId):
        if winner:
            cells, direction = self.rules.findWin(self.board, winner)
            row, col = self.__getBlinkCell(cells, direction, winner)
            self.sendUpdate('announceWinnerPosition', [row, col, direction, winner])
        else:
            self.sendUpdate('tie', [])

    def __getBlinkCell(self, cells, direction, player):
        # The client blinks the line found from one of its cells; pick the
        # cell its search starts from.
        from toontown.safezone.DistributedFindFour import DistributedFindFour
        finder = {0: DistributedFindFour.findHorizontal,
                  1: DistributedFindFour.findVertical,
                  2: DistributedFindFour.findDiagonal}[direction]

        class Board:
            pass
        holder = Board()
        holder.board = self.board
        for row, col in cells:
            found = finder(holder, row, col, player)
            if found and all(tuple(cell) in cells for cell in found):
                return row, col
        return cells[0]

    def pickMove(self, player):
        col = self.rules.pickMove(self.board, player)
        return None if col is None else [col]
