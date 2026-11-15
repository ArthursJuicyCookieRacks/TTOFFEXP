from direct.fsm import ClassicFSM, State

from .DistributedMinigameAI import DistributedMinigameAI

# Ten points a pinata or candy popped; a good two minutes is 800 to 2,000.
POINTS_PER_BEAN = 40.0
MOST_BEANS = 40
WIN_BONUS = 10          # lasting the whole two minutes
# The game ends itself (two minutes and the ending); this is only for a client that never answers.
TIMEOUT = 300.0


class DistributedAsteroidChickenGameAI(DistributedMinigameAI):
    """Asteroid Chicken is one ship: every toon aboard gets the ship's score."""

    def __init__(self, air, minigameId):
        try:
            self.DistributedAsteroidChickenGameAI_initialized
        except AttributeError:
            self.DistributedAsteroidChickenGameAI_initialized = 1
            DistributedMinigameAI.__init__(self, air, minigameId)
            self.gameFSM = ClassicFSM.ClassicFSM('DistributedAsteroidChickenGameAI', [
                State.State('inactive', self.enterInactive, self.exitInactive, ['play']),
                State.State('play', self.enterPlay, self.exitPlay, ['cleanup']),
                State.State('cleanup', self.enterCleanup, self.exitCleanup, ['inactive'])], 'inactive', 'inactive')
            self.addChildGameFSM(self.gameFSM)

    def delete(self):
        taskMgr.remove(self.taskName('timeout'))
        del self.gameFSM
        DistributedMinigameAI.delete(self)

    def setGameReady(self):
        DistributedMinigameAI.setGameReady(self)

    def setGameStart(self, timestamp):
        DistributedMinigameAI.setGameStart(self, timestamp)
        self.gameFSM.request('play')

    def setGameAbort(self):
        if self.gameFSM.getCurrentState():
            self.gameFSM.request('cleanup')
        DistributedMinigameAI.setGameAbort(self)

    def gameOver(self):
        self.gameFSM.request('cleanup')
        DistributedMinigameAI.gameOver(self)

    def setScore(self, score, won):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.avIdList or not self._playing():
            return
        beans = min(MOST_BEANS, max(1, int(score / POINTS_PER_BEAN + 0.5)))
        if won:
            beans += WIN_BONUS
        for toonId in self.avIdList:
            self.scoreDict[toonId] = beans
        self.gameOver()

    def enterInactive(self):
        pass

    def exitInactive(self):
        pass

    def enterPlay(self):
        taskMgr.doMethodLater(TIMEOUT, self.__timeout, self.taskName('timeout'))

    def __timeout(self, task):
        self.gameOver()
        return task.done

    def exitPlay(self):
        taskMgr.remove(self.taskName('timeout'))

    def enterCleanup(self):
        self.gameFSM.request('inactive')

    def exitCleanup(self):
        pass
