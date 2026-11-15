"""Doodle Rescue, the doodle minigame of Disney's Toontown 2.0 prototype,
as a trolley game. The game itself is toontown.doodlerescue (DRSim plays
it by Disney's own scripts, DRGame draws it); this puts it on the trolley:
the rules page, the start, the controls, and the count of doodles saved
that goes back for jellybeans."""

from direct.fsm import ClassicFSM, State

from toontown.doodlerescue import DRGame, DRSim
from toontown.toonbase import TTLocalizer
from . import ArrowKeys
from .DistributedMinigame import DistributedMinigame


class DistributedDoodleRescueGame(DistributedMinigame):

    def __init__(self, cr):
        DistributedMinigame.__init__(self, cr)
        self.gameFSM = ClassicFSM.ClassicFSM('DistributedDoodleRescueGame', [
            State.State('off', self.enterOff, self.exitOff, ['play']),
            State.State('play', self.enterPlay, self.exitPlay, ['cleanup']),
            State.State('cleanup', self.enterCleanup, self.exitCleanup, [])], 'off', 'cleanup')
        self.addChildGameFSM(self.gameFSM)
        self.game = None
        self.arrowKeys = None

    def getTitle(self):
        return TTLocalizer.DoodleRescueGameTitle

    def getInstructions(self):
        # (How many the pen asks for goes by the playground the trolley left from.)
        return TTLocalizer.DoodleRescueGameInstructions % DRSim.need(self.getDifficulty())

    def getMaxDuration(self):
        return 0

    def load(self):
        self.notify.debug('load')
        DistributedMinigame.load(self)
        # The arrow keys (and, on a touch screen, the arrow pad and the jump button) every walking trolley game uses.
        self.arrowKeys = ArrowKeys.ArrowKeys()
        self.arrowKeys.disable()
        # As in Toontown's own trolley games, the playground the trolley left from sets how hard it is.
        self.game = DRGame.Game(seed=self.randomNumGen.randrange(1 << 30), onFinished=self.__finished, controls=self.arrowKeys,
                                difficulty=self.getDifficulty())
        self.game.load()

    def unload(self):
        self.notify.debug('unload')
        DistributedMinigame.unload(self)
        self.__cleanup()
        self.removeChildGameFSM(self.gameFSM)
        del self.gameFSM

    def __cleanup(self):
        if self.game is not None:
            self.game.destroy()
            self.game = None
        if self.arrowKeys is not None:
            self.arrowKeys.destroy()
            self.arrowKeys = None

    def onstage(self):
        self.notify.debug('onstage')
        DistributedMinigame.onstage(self)
        # The toons play the astronaut: only the pen and its doodles show.
        self.game.show()

    def offstage(self):
        self.notify.debug('offstage')
        self.__cleanup()
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

    def __finished(self, won, saved):
        self.sendUpdate('setSaved', [max(0, min(int(saved), 255)), 1 if won else 0])
        self.gameOver()

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterPlay(self):
        self.arrowKeys.enable()
        self.game.start()

    def exitPlay(self):
        if self.arrowKeys is not None:
            self.arrowKeys.disable()

    def enterCleanup(self):
        pass

    def exitCleanup(self):
        pass
