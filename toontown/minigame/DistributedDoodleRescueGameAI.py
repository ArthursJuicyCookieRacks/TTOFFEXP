from direct.fsm import ClassicFSM, State

from .DistributedMinigameAI import DistributedMinigameAI

# Four jellybeans for every three doodles saved: the 24 that win the game are 32.
BEANS_PER_DOODLE = 4.0 / 3.0
MOST_BEANS = 40
WIN_BONUS = 10
# The game ends itself (a minute, the poster before it and the Cog's picture after); this is only for a client that never answers.
TIMEOUT = 240.0


class DistributedDoodleRescueGameAI(DistributedMinigameAI):
    """Doodle Rescue is one astronaut: every toon aboard gets the same jellybeans."""

    def __init__(self, air, minigameId):
        try:
            self.DistributedDoodleRescueGameAI_initialized
        except AttributeError:
            self.DistributedDoodleRescueGameAI_initialized = 1
            DistributedMinigameAI.__init__(self, air, minigameId)
            self.gameFSM = ClassicFSM.ClassicFSM('DistributedDoodleRescueGameAI', [
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

    def setSaved(self, saved, won):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.avIdList or not self._playing():
            return
        beans = min(MOST_BEANS, max(1, int(saved * BEANS_PER_DOODLE + 0.5)))
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
