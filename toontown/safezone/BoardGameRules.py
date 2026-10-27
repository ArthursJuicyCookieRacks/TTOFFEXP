import random

from toontown.safezone.CheckersBoard import CheckersBoard
from toontown.safezone.ChineseCheckersBoard import ChineseCheckersBoard

# The rules of the three picnic table games, as the server checks them, and
# the moves a computer player picks when no other toon is there to play.


class CheckersRules:
    # 32 dark squares. A state is 0 for empty, 1 or 2 for a player's man and
    # 3 or 4 for that player's king. Player 1 starts on 0-11 and moves up
    # the board (adjacent directions 1 and 2); player 2 starts on 20-31.
    NumSquares = 32
    StartingPositions = [list(range(0, 12)), list(range(20, 32))]
    Forward = {1: (1, 2), 2: (0, 3)}
    KingRow = {1: list(range(28, 32)), 2: list(range(0, 4))}

    def __init__(self):
        self.board = CheckersBoard()

    def getInitialState(self):
        states = [0] * self.NumSquares
        for player in (1, 2):
            for square in self.StartingPositions[player - 1]:
                states[square] = player
        return states

    def owner(self, state):
        if state in (1, 3):
            return 1
        if state in (2, 4):
            return 2
        return 0

    def directions(self, state):
        if state in (3, 4):
            return range(4)
        return self.Forward[self.owner(state)]

    def jumpsFrom(self, states, square, state, visited=()):
        # Every jump the piece on square can make next: (landing, captured).
        jumps = []
        player = self.owner(state)
        for d in self.directions(state):
            over = self.board.getAdjacent(square)[d]
            land = self.board.getJumps(square)[d]
            if over is None or land is None:
                continue
            if self.owner(states[over]) not in (0, player) and states[land] == 0 and over not in visited:
                jumps.append((land, over))
        return jumps

    def stepsFrom(self, states, square, state):
        steps = []
        for d in self.directions(state):
            dest = self.board.getAdjacent(square)[d]
            if dest is not None and states[dest] == 0:
                steps.append(dest)
        return steps

    def jumpChains(self, states, square, state, visited=()):
        # Every way to keep jumping from square, as lists of landings.
        chains = []
        for land, over in self.jumpsFrom(states, square, state, visited):
            after = list(states)
            after[square] = 0
            after[over] = 0
            after[land] = state
            rest = self.jumpChains(after, land, state, visited + (over,))
            if rest:
                chains.extend([[land] + chain for chain in rest])
            else:
                chains.append([land])
        return chains

    def mustJump(self, states, player):
        for square, state in enumerate(states):
            if self.owner(state) == player and self.jumpsFrom(states, square, state):
                return True
        return False

    def getMoves(self, states, player):
        jumps = []
        steps = []
        for square, state in enumerate(states):
            if self.owner(state) != player:
                continue
            for chain in self.jumpChains(states, square, state):
                jumps.append([square] + chain)
            for dest in self.stepsFrom(states, square, state):
                steps.append([square, dest])
        return jumps or steps

    def applyMove(self, states, player, moveList):
        # Returns the new states, or None when the move is not allowed.
        if len(moveList) < 2 or any(not 0 <= square < self.NumSquares for square in moveList):
            return None
        start = moveList[0]
        state = states[start]
        if self.owner(state) != player:
            return None
        after = list(states)
        if len(moveList) == 2 and moveList[1] in self.stepsFrom(states, start, state):
            if self.mustJump(states, player):
                return None
            after[start] = 0
            after[moveList[1]] = state
        else:
            square = start
            captured = ()
            for land in moveList[1:]:
                jumps = dict(self.jumpsFrom(after, square, state, captured))
                if land not in jumps:
                    return None
                after[square] = 0
                after[jumps[land]] = 0
                after[land] = state
                captured += (jumps[land],)
                square = land
        end = moveList[-1]
        if state in (1, 2) and end in self.KingRow[player]:
            after[end] = state + 2
        return after

    def getWinner(self, states, playerToMove):
        # The player who has to move and cannot has lost.
        if not self.getMoves(states, playerToMove):
            return 3 - playerToMove
        return 0

    def pickMove(self, states, player):
        moves = self.getMoves(states, player)
        if not moves:
            return None

        def score(move):
            after = self.applyMove(states, player, move)
            value = 0
            # Take as many pieces as possible, crown kings and keep out of
            # reach of the other player's next jump.
            value += 10 * (len(move) - 2 if self.board.getAdjacent(move[0]).count(move[1]) == 0 else 0)
            if after[move[-1]] in (3, 4) and states[move[0]] in (1, 2):
                value += 8
            opponent = 3 - player
            for square, state in enumerate(after):
                if self.owner(state) == opponent:
                    for land, over in self.jumpsFrom(after, square, state):
                        value -= 6 if after[over] in (1, 2) else 9
            return value + random.random()

        return max(moves, key=score)


class ChineseCheckersRules:
    # 121 holes, a state is 0 or the player number 1-6. Player n starts in
    # triangle n-1 and has to fill the opposite triangle, n+2 (mod 6).
    NumSquares = 121
    StartingPositions = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [10, 11, 12, 13, 23, 24, 25, 35, 36, 46],
        [65, 75, 76, 86, 87, 88, 98, 99, 100, 101],
        [111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
        [74, 84, 85, 95, 96, 97, 107, 108, 109, 110],
        [19, 20, 21, 22, 32, 33, 34, 44, 45, 55]]
    # Which player numbers take part, by the number of players, so that
    # two players face each other.
    PlayerNums = {2: [1, 4],
                  3: [1, 3, 5],
                  4: [1, 2, 4, 5],
                  5: [1, 2, 3, 4, 5],
                  6: [1, 2, 3, 4, 5, 6]}

    def __init__(self):
        self.board = ChineseCheckersBoard()
        self.distances = {}

    def getInitialState(self, playerNums):
        states = [0] * self.NumSquares
        for player in playerNums:
            for square in self.StartingPositions[player - 1]:
                states[square] = player
        return states

    def getTarget(self, player):
        return self.StartingPositions[(player + 2) % 6]

    def getForbidden(self, player):
        # A move may not end in the side triangles, which belong to the
        # players that are neither this one nor its opposite.
        forbidden = set()
        for index, triangle in enumerate(self.StartingPositions):
            if index != player - 1 and index != (player + 2) % 6:
                forbidden.update(triangle)
        return forbidden

    def adjacent(self, square):
        return self.board.getAdjacent(square)

    def jumpsFrom(self, states, square):
        jumps = []
        for d, over in enumerate(self.adjacent(square)):
            if over is None or states[over] == 0:
                continue
            land = self.adjacent(over)[d]
            if land is not None and states[land] == 0:
                jumps.append(land)
        return jumps

    def applyMove(self, states, player, moveList):
        if len(moveList) < 2 or any(not 0 <= square < self.NumSquares for square in moveList):
            return None
        start = moveList[0]
        if states[start] != player or moveList[-1] in self.getForbidden(player):
            return None
        after = list(states)
        after[start] = 0
        if len(moveList) == 2 and moveList[1] in self.adjacent(start):
            if states[moveList[1]] != 0:
                return None
        else:
            square = start
            seen = {start}
            for land in moveList[1:]:
                if land in seen or land not in self.jumpsFrom(after, square):
                    return None
                seen.add(land)
                square = land
        after[moveList[-1]] = player
        return after

    def hasWon(self, states, player):
        return all(states[square] == player for square in self.getTarget(player))

    def getDistances(self, player):
        # Steps from every hole to the far corner of the player's target.
        if player not in self.distances:
            target = self.getTarget(player)
            # The corner is the target hole with the fewest neighbours.
            tip = min(target, key=lambda square: sum(1 for adj in self.adjacent(square) if adj is not None))
            distances = {tip: 0}
            queue = [tip]
            while queue:
                square = queue.pop(0)
                for adj in self.adjacent(square):
                    if adj is not None and adj not in distances:
                        distances[adj] = distances[square] + 1
                        queue.append(adj)
            self.distances[player] = distances
        return self.distances[player]

    def getMoves(self, states, player):
        forbidden = self.getForbidden(player)
        moves = []
        for start, state in enumerate(states):
            if state != player:
                continue
            for adj in self.adjacent(start):
                if adj is not None and states[adj] == 0 and adj not in forbidden:
                    moves.append([start, adj])
            # Every hole reachable by a chain of jumps.
            after = list(states)
            after[start] = 0
            paths = {start: [start]}
            queue = [start]
            while queue:
                square = queue.pop(0)
                for land in self.jumpsFrom(after, square):
                    if land not in paths:
                        paths[land] = paths[square] + [land]
                        queue.append(land)
            for land, path in paths.items():
                if land != start and land not in forbidden:
                    moves.append(path)
        return moves

    def pickMove(self, states, player):
        moves = self.getMoves(states, player)
        if not moves:
            return None
        distances = self.getDistances(player)
        target = set(self.getTarget(player))

        def score(move):
            gain = distances[move[0]] - distances[move[-1]]
            # Bring the stragglers along rather than racing one marble.
            value = gain * 10 + distances[move[0]]
            if move[-1] in target and move[0] not in target:
                value += 5
            if move[0] in target and move[-1] not in target:
                value -= 50
            return value + random.random()

        return max(moves, key=score)


class FindFourRules:
    # Six rows of seven; row 0 is the top. A state is 0 or the player 1-2.
    Rows = 6
    Cols = 7

    def getInitialState(self):
        return [[0] * self.Cols for i in range(self.Rows)]

    def dropRow(self, board, col):
        if not 0 <= col < self.Cols:
            return None
        for row in range(self.Rows - 1, -1, -1):
            if board[row][col] == 0:
                return row
        return None

    def applyMove(self, board, player, col):
        row = self.dropRow(board, col)
        if row is None:
            return None, None
        after = [list(line) for line in board]
        after[row][col] = player
        return after, row

    def findWin(self, board, player):
        # The four in a row as (row, col, direction) for every line through
        # four of the player's pieces: 0 across, 1 down, 2 diagonal.
        for row in range(self.Rows):
            for col in range(self.Cols):
                for direction, (dr, dc) in ((0, (0, 1)), (1, (1, 0)), (2, (1, 1)), (2, (1, -1))):
                    cells = [(row + dr * i, col + dc * i) for i in range(4)]
                    if all(0 <= r < self.Rows and 0 <= c < self.Cols and board[r][c] == player for r, c in cells):
                        return cells, direction
        return None

    def isFull(self, board):
        return all(board[0][col] != 0 for col in range(self.Cols))

    def pickMove(self, board, player):
        cols = [col for col in range(self.Cols) if self.dropRow(board, col) is not None]
        if not cols:
            return None
        opponent = 3 - player
        for who in (player, opponent):
            # Win now, or stop the other player from winning next turn.
            for col in cols:
                after, row = self.applyMove(board, who, col)
                if self.findWin(after, who):
                    return col

        def score(col):
            after, row = self.applyMove(board, player, col)
            value = 3 - abs(3 - col)
            # Do not set up a win for the other player right above.
            above, aboveRow = self.applyMove(after, opponent, col)
            if above and self.findWin(above, opponent):
                value -= 20
            return value + random.random()

        return max(cols, key=score)
