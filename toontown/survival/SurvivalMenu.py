"""The Survival menu behind the SURVIVAL button on Pick-A-Toon, and the
glue that runs a game from there and brings Pick-A-Toon back after."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode, Vec4

from toontown.toonbase import TTLocalizer, ToontownGlobals

RED = (0.85, 0.1, 0.1, 1)


class SurvivalMenu(DirectObject):
    """A dark card: the Survival Mode button, a description under it, how
    many NPC toons come along, the best round and Back."""

    def __init__(self, doneEvent, bestRound):
        DirectObject.__init__(self)
        self.doneEvent = doneEvent
        self.npcs = 0
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        self.frame = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.03, 0.03, 0.06, 0.95),
                                 frameSize=(-1.0, 1.0, -0.72, 0.72), pos=(0, 0, 0), sortOrder=50, state=DGG.NORMAL)
        OnscreenText(parent=self.frame, text=TTLocalizer.SurvivalTitle, font=sign, fg=RED, shadow=(0, 0, 0, 1), scale=0.16, pos=(0, 0.5))
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        self.playButton = DirectButton(parent=self.frame, relief=None, image=(up, down, over), image_scale=(1.9, 1, 1.6),
                                       text=TTLocalizer.SurvivalPlay, text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.085,
                                       text_pos=(0, -0.025), pos=(0, 0, 0.27), command=self.__play)
        OnscreenText(parent=self.frame, text=TTLocalizer.SurvivalDescription, font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                     scale=0.05, pos=(0, 0.13), wordwrap=34, align=TextNode.ACenter)
        OnscreenText(parent=self.frame, text=TTLocalizer.SurvivalFriends, font=face, fg=(1, 1, 1, 1), scale=0.055, pos=(-0.5, -0.31))
        self.npcButtons = []
        for i in range(4):
            b = DirectButton(parent=self.frame, relief=None, image=(up, down, over), image_scale=(0.45, 1, 0.9),
                             text=str(i), text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.07, text_pos=(0, -0.02),
                             pos=(0.0 + 0.24 * i, 0, -0.29), command=self.__setNpcs, extraArgs=[i])
            self.npcButtons.append(b)
        self.bestText = OnscreenText(parent=self.frame, text=TTLocalizer.SurvivalBestRound % bestRound if bestRound else '', font=face,
                                     fg=(1, 0.95, 0.4, 1), scale=0.05, pos=(0, -0.45))
        self.backButton = DirectButton(parent=self.frame, relief=None, image=(up, down, over), image_scale=(1.1, 1, 1.2),
                                       text=TTLocalizer.SurvivalBack, text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.07,
                                       text_pos=(0, -0.02), pos=(0, 0, -0.6), command=self.__back)
        gui.removeNode()
        self.__setNpcs(0)

    def __setNpcs(self, n):
        self.npcs = n
        for i, b in enumerate(self.npcButtons):
            b.setColorScale(Vec4(1, 1, 1, 1) if i == n else Vec4(0.55, 0.55, 0.55, 1))

    def __play(self):
        messenger.send(self.doneEvent, [{'mode': 'play', 'npcs': self.npcs}])

    def __back(self):
        messenger.send(self.doneEvent, [{'mode': 'back'}])

    def destroy(self):
        self.ignoreAll()
        self.frame.destroy()


class SurvivalLauncher(DirectObject):
    """Runs Survival Mode from Pick-A-Toon: shows the menu, plays games
    until the player quits, then hands Pick-A-Toon back."""

    def __init__(self, chooser, dna, name):
        DirectObject.__init__(self)
        self.chooser = chooser
        self.dna = dna
        self.name = name
        self.menu = None
        self.game = None
        self.music = getattr(base.cr, 'music', None)
        self.showMenu()

    def showMenu(self):
        from toontown.survival.SurvivalGame import SurvivalGame
        self.menu = SurvivalMenu('survivalMenuDone', SurvivalGame.loadBest())
        self.acceptOnce('survivalMenuDone', self.__menuDone)

    def __menuDone(self, status):
        self.menu.destroy()
        self.menu = None
        if status['mode'] == 'play':
            self.startGame(status['npcs'])
        else:
            self.finish()

    def startGame(self, npcs):
        from toontown.survival.SurvivalGame import SurvivalGame
        if self.music:
            self.music.stop()
        self.chooser.exit()
        base.transitions.fadeScreen(1.0)
        self.game = SurvivalGame(self.dna, self.name, npcs, 'survivalGameDone')
        base.transitions.fadeIn(0.8)
        self.acceptOnce('survivalGameDone', self.__gameDone)

    def __gameDone(self, status):
        self.game.destroy()
        self.game = None
        if status['mode'] == 'again':
            self.startGame(status['npcs'])
            return
        self.chooser.enter()
        if self.music:
            self.music.play()
        self.showMenu()

    def finish(self):
        self.ignoreAll()
        self.chooser.survivalLauncher = None

    def destroy(self):
        self.ignoreAll()
        if self.menu:
            self.menu.destroy()
            self.menu = None
        if self.game:
            self.game.destroy()
            self.game = None
