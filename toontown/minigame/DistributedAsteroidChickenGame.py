"""Asteroid Chicken, the space minigame of Disney's Toontown 2.0 prototype,
as a trolley game. The game itself is toontown.asteroidchicken (ACSim plays
it by Disney's own scripts, ACGame draws it); this puts it on the trolley:
the rules page, the start, and the score that goes back for jellybeans."""

from direct.fsm import ClassicFSM, State

from toontown.asteroidchicken import ACGame, ACSim
from toontown.toonbase import TTLocalizer
from .DistributedMinigame import DistributedMinigame


class DistributedAsteroidChickenGame(DistributedMinigame):

    def __init__(self, cr):
        DistributedMinigame.__init__(self, cr)
        self.gameFSM = ClassicFSM.ClassicFSM('DistributedAsteroidChickenGame', [
            State.State('off', self.enterOff, self.exitOff, ['play']),
            State.State('play', self.enterPlay, self.exitPlay, ['cleanup']),
            State.State('cleanup', self.enterCleanup, self.exitCleanup, [])], 'off', 'cleanup')
        self.addChildGameFSM(self.gameFSM)
        self.game = None

    def getTitle(self):
        return TTLocalizer.AsteroidChickenGameTitle

    def getInstructions(self):
        # (How many hits the windshield takes goes by the playground the trolley left from.)
        return TTLocalizer.AsteroidChickenGameInstructions % (ACSim.tuning(self.getDifficulty())['cracks'] + 1)

    def getMaxDuration(self):
        return 0

    def load(self):
        self.notify.debug('load')
        DistributedMinigame.load(self)
        # As in Toontown's own trolley games, the playground the trolley left from sets how hard it is.
        self.game = ACGame.Game(seed=self.randomNumGen.randrange(1 << 30), onFinished=self.__finished, difficulty=self.getDifficulty())
        self.game.load()

    def unload(self):
        self.notify.debug('unload')
        DistributedMinigame.unload(self)
        if self.game is not None:
            self.game.destroy()
            self.game = None
        self.removeChildGameFSM(self.gameFSM)
        del self.gameFSM

    def onstage(self):
        self.notify.debug('onstage')
        DistributedMinigame.onstage(self)
        # The toons ride inside the ship: only the cockpit shows.
        self.game.show()

    def offstage(self):
        self.notify.debug('offstage')
        if self.game is not None:
            self.game.destroy()
            self.game = None
        DistributedMinigame.offstage(self)

    def setGameReady(self):
        if not self.hasLocalToon:
            return
        self.notify.debug('setGameReady')
        if DistributedMinigame.setGameReady(self):
            return

    def setGameStart(self, timestamp):
        if not self.hasLocalToon:
            return
        self.notify.debug('setGameStart')
        DistributedMinigame.setGameStart(self, timestamp)
        self.gameFSM.request('play')

    def __finished(self, won, score):
        self.sendUpdate('setScore', [max(0, min(int(score), 65535)), 1 if won else 0])
        self.gameOver()

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterPlay(self):
        self.game.start()

    def exitPlay(self):
        pass

    def enterCleanup(self):
        pass

    def exitCleanup(self):
        pass
