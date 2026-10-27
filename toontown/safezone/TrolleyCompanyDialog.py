"""Asks, before the player boards the trolley, whether to ride solo or with
other players (the NPC players), and then whether to pick the trolley game
or have a random one. Solo, no NPC players get on with them."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import ConfigVariableBool

from otp.otpbase import OTPGlobals
from toontown.npcplayers import NPCSettings
from toontown.toonbase import TTLocalizer, ToontownGlobals

TITLE = 'Ride the trolley'
QUESTION = 'Ride solo, or with other players?'
CHOICES = (('Solo', False), ('With Others', True))
GAME_QUESTION = 'Choose the game, or play a random one?'
GAME_CHOICES = (('Choose Game', True), ('Random Game', False))
PICK_TITLE = 'Pick a trolley game'
# Every trolley game, in the order the list shows them.
GAMES = ((ToontownGlobals.CannonGameId, 'CannonGameTitle'),
         (ToontownGlobals.CatchGameId, 'CatchGameTitle'),
         (ToontownGlobals.CogThiefGameId, 'CogThiefGameTitle'),
         (ToontownGlobals.IceGameId, 'IceGameTitle'),
         (ToontownGlobals.VineGameId, 'VineGameTitle'),
         (ToontownGlobals.PatternGameId, 'PatternGameTitle'),
         (ToontownGlobals.MazeGameId, 'MazeGameTitle'),
         (ToontownGlobals.PhotoGameId, 'PhotoGameTitle'),
         (ToontownGlobals.RaceGameId, 'RaceGameTitle'),
         (ToontownGlobals.RingGameId, 'RingGameTitle'),
         (ToontownGlobals.TagGameId, 'TagGameTitle'),
         (ToontownGlobals.TwoDGameId, 'TwoDGameTitle'),
         (ToontownGlobals.PairingGameId, 'PairingGameTitle'),
         (ToontownGlobals.DivingGameId, 'DivingGameTitle'),
         (ToontownGlobals.TargetGameId, 'TargetGameTitle'),
         (ToontownGlobals.TugOfWarGameId, 'TugOfWarGameTitle'))


def wantAsk():
    # The game's own tests board the trolley without anyone to answer.
    return ConfigVariableBool('trolley-ask-company', True).getValue()


class TrolleyCompanyDialog(DirectFrame):

    def __init__(self, avId, done):
        """done(boarding) is called with False when the player backs off."""
        self.box = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        DirectFrame.__init__(self, parent=aspect2d, relief=None, image=self.box,
                             image_color=OTPGlobals.GlobalDialogColor, image_scale=(1.1, 1, 0.78),
                             pos=(0, 0, 0.1), state=DGG.NORMAL, sortOrder=DGG.NO_FADE_SORT_INDEX)
        self.initialiseoptions(TrolleyCompanyDialog)
        self.avId = avId
        self.done = done
        self.company = True
        self.font = ToontownGlobals.getInterfaceFont()
        buttons = loader.loadModel('phase_3/models/gui/quit_button')
        self.images = (buttons.find('**/QuitBtn_UP'), buttons.find('**/QuitBtn_DN'), buttons.find('**/QuitBtn_RLVR'))
        for image in self.images:
            image.detachNode()
        buttons.removeNode()
        self.page = []
        NPCSettings.setTrolleyGame(avId, None)
        self.showQuestion(QUESTION, CHOICES, self.choose)

    def destroy(self):
        self.clearPage()
        if self.box is not None:
            self.box.removeNode()
            self.box = None
        DirectFrame.destroy(self)

    def clearPage(self):
        for widget in self.page:
            widget.destroy()
        self.page = []

    def button(self, text, pos, command, extraArgs=[], scale=(1.0, 1, 1.4), textScale=0.055):
        widget = DirectButton(parent=self, relief=None, image=self.images, image_scale=scale, pos=pos,
                              text=text, text_scale=textScale, text_pos=(0, -0.018), text_font=self.font,
                              command=command, extraArgs=extraArgs)
        self.page.append(widget)
        return widget

    def label(self, text, pos, scale, font=None, fg=(0, 0, 0, 1)):
        widget = DirectLabel(parent=self, relief=None, pos=pos, text=text, text_scale=scale,
                             text_font=font or self.font, text_fg=fg)
        self.page.append(widget)
        return widget

    def showQuestion(self, question, choices, command):
        self.clearPage()
        self['image_scale'] = (1.1, 1, 0.78)
        self.label(TITLE, (0, 0, 0.22), 0.08, ToontownGlobals.getSignFont(), (0.1, 0.3, 0.7, 1))
        self.label(question, (0, 0, 0.1), 0.055)
        for i, (text, value) in enumerate(choices):
            self.button(text, (-0.25 + i * 0.5, 0, -0.04), command, [value])
        self.button('Cancel', (0, 0, -0.25), self.cancel)

    def choose(self, company):
        self.company = company
        self.showQuestion(GAME_QUESTION, GAME_CHOICES, self.chooseGameOrRandom)

    def chooseGameOrRandom(self, choose):
        if choose:
            self.showGames()
        else:
            self.board(None)

    def showGames(self):
        # A button for each trolley game, four to a row.
        self.clearPage()
        self['image_scale'] = (1.75, 1, 1.25)
        self.label(PICK_TITLE, (0, 0, 0.43), 0.08, ToontownGlobals.getSignFont(), (0.1, 0.3, 0.7, 1))
        for i, (gameId, title) in enumerate(GAMES):
            row, column = divmod(i, 4)
            text = getattr(TTLocalizer, title)
            # Long names (Toon Memory Game) shrink to stay on their button.
            self.button(text, (-0.6 + column * 0.4, 0, 0.27 - row * 0.15), self.board, [gameId],
                        scale=(0.82, 1, 1.25), textScale=min(0.042, 0.042 * 14.0 / max(len(text), 1)))
        self.button(TTLocalizer.lCancel, (0, 0, -0.4), self.cancel)

    def board(self, gameId):
        company = self.company
        if gameId is not None and gameId not in ToontownGlobals.MinigamePlayerMatrix[1]:
            # This game needs more than one toon, so NPC players come along
            # even on a solo ride.
            company = True
        NPCSettings.setTrolleyCompany(self.avId, company)
        NPCSettings.setTrolleyGame(self.avId, gameId)
        self.finish(True)

    def cancel(self):
        NPCSettings.setTrolleyGame(self.avId, None)
        self.finish(False)

    def finish(self, boarding):
        done = self.done
        self.done = None
        self.destroy()
        if done is not None:
            done(boarding)
