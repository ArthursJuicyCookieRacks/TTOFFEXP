"""The Survival menu behind the SURVIVAL button on Pick-A-Toon, and the
glue that runs a game from there and brings Pick-A-Toon back after."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenImage, OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode, Vec4

from toontown.toonbase import TTLocalizer, ToontownGlobals

RED = (0.85, 0.1, 0.1, 1)


class SurvivalMenu(DirectObject):
    """A dark card: the Survival Mode button, a description under it, how
    many NPC toons come along, the best round and Back."""

    def __init__(self, doneEvent, bestRound, npcs=0):
        DirectObject.__init__(self)
        self.doneEvent = doneEvent
        self.npcs = npcs
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
        self.__setNpcs(npcs)

    def __setNpcs(self, n):
        self.npcs = n
        for i, b in enumerate(self.npcButtons):
            b.setColorScale(Vec4(1, 1, 1, 1) if i == n else Vec4(0.55, 0.55, 0.55, 1))

    def __play(self):
        messenger.send(self.doneEvent, [{'mode': 'maps', 'npcs': self.npcs}])

    def __back(self):
        messenger.send(self.doneEvent, [{'mode': 'back'}])

    def destroy(self):
        self.ignoreAll()
        self.frame.destroy()


DARK_RED = (0.22, 0.03, 0.03, 0.96)
HEADER = (0.1, 0.01, 0.01, 1)
ROW = (0.1, 0.01, 0.01, 0.85)
ROW_LIT = (1, 1, 1, 1)


class SurvivalMapSelect(DirectObject):
    """Map Select: the maps listed on the left; the one under the pointer
    lights up and shows its name, a picture and a few words on the right.
    Clicking a map plays it. On a touch screen, where nothing hovers, the
    first tap shows a map and a second tap on it plays it."""

    def __init__(self, doneEvent, npcs):
        DirectObject.__init__(self)
        from toontown.survival.SurvivalArena import MAPS, MAP_ORDER
        from toontown.toonbase import TouchControls
        self.doneEvent = doneEvent
        self.npcs = npcs
        self.maps = [(key, MAPS[key]) for key in MAP_ORDER]
        self.touch = TouchControls.wantTouchControls()
        self.lit = None
        self.timePopup = None
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        self.frame = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=DARK_RED,
                                 frameSize=(-1.3, 1.3, -0.8, 0.8), sortOrder=50, state=DGG.NORMAL)
        DirectFrame(parent=self.frame, relief=DGG.FLAT, frameColor=HEADER, frameSize=(-1.3, 1.3, 0.6, 0.8))
        OnscreenText(parent=self.frame, text=TTLocalizer.SurvivalMapSelect, font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                     scale=0.1, pos=(-1.22, 0.665), align=TextNode.ALeft)
        self.rows = []
        # The rows close up (and their text shrinks a little) so a longer
        # list still fits between the header and the Back button.
        step = min(0.14, 0.97 / max(1, len(self.maps) - 1))
        squeeze = step / 0.14
        for i, (key, info) in enumerate(self.maps):
            row = DirectButton(parent=self.frame, relief=DGG.FLAT, frameColor=ROW,
                               frameSize=(-0.05, 1.05, -0.045 * squeeze, 0.075 * squeeze - 0.008 * (squeeze < 1)),
                               text=info['title'].upper(), text_font=face, text_fg=(1, 1, 1, 1), text_scale=0.065 * max(0.85, squeeze),
                               text_align=TextNode.ALeft, pos=(-1.2, 0, 0.42 - step * i),
                               command=self.__click, extraArgs=[i])
            row.bind(DGG.ENTER, self.__hover, [i])
            self.rows.append(row)
        self.title = OnscreenText(parent=self.frame, text='', font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                  scale=0.1, pos=(0.62, 0.43))
        # The picture is 16:9, the screenshots' own shape.
        self.picture = None
        self.description = OnscreenText(parent=self.frame, text='', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                        scale=0.048, pos=(0.62, -0.4), wordwrap=23, align=TextNode.ACenter)
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        self.backButton = DirectButton(parent=self.frame, relief=None, image=(up, down, over), image_scale=(1.1, 1, 1.2),
                                       text=TTLocalizer.SurvivalBack, text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.07,
                                       text_pos=(0, -0.02), pos=(-1.0, 0, -0.68), command=self.__back)
        gui.removeNode()
        self.__light(0)

    def __light(self, i):
        if i == self.lit:
            return
        self.lit = i
        for j, row in enumerate(self.rows):
            on = j == i
            row['frameColor'] = ROW_LIT if on else ROW
            row['text_fg'] = (0, 0, 0, 1) if on else (1, 1, 1, 1)
        key, info = self.maps[i]
        self.title.setText(info['title'].upper())
        self.description.setText(info['description'])
        if self.picture:
            self.picture.destroy()
        # The picture is 16:9, the screenshots' own shape.
        self.picture = OnscreenImage(parent=self.frame, image=info['picture'], pos=(0.62, 0, 0.0), scale=(0.56, 1, 0.315))

    def __hover(self, i, event=None):
        self.__light(i)

    def __click(self, i):
        if self.timePopup:
            return
        if self.touch and self.lit != i:
            self.__light(i)
            return
        self.__light(i)
        key, info = self.maps[i]
        if info.get('dayAndNight'):
            self.__askTime(key)
            return
        self.__play(key, True)

    def __askTime(self, key):
        """A map with a daytime and a night-time version asks which."""
        sign = ToontownGlobals.getSignFont()
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        self.timePopup = DirectFrame(parent=self.frame, relief=DGG.FLAT, frameColor=(0.06, 0.01, 0.01, 0.97),
                                     frameSize=(-0.62, 0.62, -0.36, 0.36), sortOrder=10, state=DGG.NORMAL)
        OnscreenText(parent=self.timePopup, text=self.title.getText(), font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                     scale=0.075, pos=(0, 0.2))
        for label, night, x in ((TTLocalizer.SurvivalDayTime, False, -0.3), (TTLocalizer.SurvivalNightTime, True, 0.3)):
            DirectButton(parent=self.timePopup, relief=None, image=(up, down, over), image_scale=(1.15, 1, 1.4),
                         text=label, text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.065, text_pos=(0, -0.02),
                         pos=(x, 0, 0.0), command=self.__play, extraArgs=[key, night])
        DirectButton(parent=self.timePopup, relief=None, image=(up, down, over), image_scale=(0.9, 1, 1.0),
                     text=TTLocalizer.SurvivalBack, text_font=sign, text_fg=(1, 0.95, 0.4, 1), text_scale=0.055,
                     text_pos=(0, -0.015), pos=(0, 0, -0.24), command=self.__closeTime)
        gui.removeNode()

    def __closeTime(self):
        if self.timePopup:
            self.timePopup.destroy()
            self.timePopup = None

    def __play(self, key, night):
        messenger.send(self.doneEvent, [{'mode': 'play', 'npcs': self.npcs, 'map': key, 'night': night}])

    def __back(self):
        if self.timePopup:
            self.__closeTime()
            return
        messenger.send(self.doneEvent, [{'mode': 'back', 'npcs': self.npcs}])

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
        self.music = []
        self.showMenu()

    def __chooserMusic(self):
        # Pick-A-Toon's music is the loading screen's theme (its second
        # part; the first part plays silently beside it), not only the
        # client's own music, which the menu used to stop on its own.
        screen = getattr(base, 'loadingScreen', None)
        sounds = [getattr(base.cr, 'music', None), getattr(screen, 'musPhase1', None), getattr(screen, 'musPhase2', None)]
        return [sound for sound in sounds if sound is not None]

    def __stopMusic(self):
        # Another game right after one ('again') finds it stopped already
        # and keeps the list from the first.
        for sound in self.__chooserMusic():
            if sound.status() == sound.PLAYING:
                if sound not in self.music:
                    self.music.append(sound)
                sound.stop()

    def __resumeMusic(self):
        for sound in self.music:
            sound.play()
        self.music = []

    def showMenu(self, npcs=0):
        from toontown.survival.SurvivalGame import SurvivalGame
        self.menu = SurvivalMenu('survivalMenuDone', SurvivalGame.loadBest(), npcs)
        self.acceptOnce('survivalMenuDone', self.__menuDone)

    def __menuDone(self, status):
        self.menu.destroy()
        self.menu = None
        if status['mode'] == 'maps':
            self.showMaps(status['npcs'])
        elif status['mode'] == 'play':
            self.startGame(status['npcs'], status.get('map'), status.get('night', True))
        else:
            self.finish()

    def showMaps(self, npcs):
        self.menu = SurvivalMapSelect('survivalMapsDone', npcs)
        self.acceptOnce('survivalMapsDone', self.__mapsDone)

    def __mapsDone(self, status):
        self.menu.destroy()
        self.menu = None
        if status['mode'] == 'play':
            self.startGame(status['npcs'], status['map'], status.get('night', True))
        else:
            self.showMenu(status['npcs'])

    def startGame(self, npcs, mapName=None, night=True):
        from toontown.survival.SurvivalGame import SurvivalGame
        self.__stopMusic()
        self.chooser.exit()
        base.transitions.fadeScreen(1.0)
        # The loading screen, kept drawing while the map is built: on a phone
        # Toybox Terrace took a minute with no frame drawn, and Android kept
        # saying the game wasn't responding (Arthur 2026-11-06).
        from toontown.survival import SurvivalArena, SurvivalLoading
        key = mapName if mapName in SurvivalArena.MAPS else SurvivalArena.mapName()
        SurvivalLoading.begin(SurvivalArena.MAPS[key].get('title', 'Survival'))
        try:
            self.game = SurvivalGame(self.dna, self.name, npcs, 'survivalGameDone', mapName, night)
        finally:
            SurvivalLoading.end()
        base.transitions.fadeIn(0.8)
        self.acceptOnce('survivalGameDone', self.__gameDone)

    def __gameDone(self, status):
        self.game.destroy()
        self.game = None
        if status['mode'] == 'again':
            self.startGame(status['npcs'], status.get('map'), status.get('night', True))
            return
        self.chooser.enter()
        self.__resumeMusic()
        if status['mode'] == 'exit':
            # Escaped on the trolley: straight back to Pick-A-Toon.
            self.finish()
            return
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
