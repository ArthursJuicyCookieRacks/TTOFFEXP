"""Asks, before the player boards the trolley, whether to ride solo or with
other players (the NPC players). Solo, no NPC players get on with them."""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import ConfigVariableBool

from otp.otpbase import OTPGlobals
from toontown.npcplayers import NPCSettings
from toontown.toonbase import ToontownGlobals

TITLE = 'Ride the trolley'
QUESTION = 'Ride solo, or with other players?'
CHOICES = (('Solo', False), ('With Others', True))


def wantAsk():
    # The game's own tests board the trolley without anyone to answer.
    return ConfigVariableBool('trolley-ask-company', True).getValue()


class TrolleyCompanyDialog(DirectFrame):

    def __init__(self, avId, done):
        """done(boarding) is called with False when the player backs off."""
        box = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        DirectFrame.__init__(self, parent=aspect2d, relief=None, image=box,
                             image_color=OTPGlobals.GlobalDialogColor, image_scale=(1.1, 1, 0.78),
                             pos=(0, 0, 0.1), state=DGG.NORMAL, sortOrder=DGG.NO_FADE_SORT_INDEX)
        self.initialiseoptions(TrolleyCompanyDialog)
        box.removeNode()
        self.avId = avId
        self.done = done
        font = ToontownGlobals.getInterfaceFont()
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.22), text=TITLE, text_scale=0.08,
                    text_font=ToontownGlobals.getSignFont(), text_fg=(0.1, 0.3, 0.7, 1))
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.1), text=QUESTION, text_scale=0.055, text_font=font)
        buttons = loader.loadModel('phase_3/models/gui/quit_button')
        images = (buttons.find('**/QuitBtn_UP'), buttons.find('**/QuitBtn_DN'), buttons.find('**/QuitBtn_RLVR'))
        for i, (text, company) in enumerate(CHOICES):
            DirectButton(parent=self, relief=None, image=images, image_scale=(1.0, 1, 1.4), pos=(-0.25 + i * 0.5, 0, -0.04),
                         text=text, text_scale=0.055, text_pos=(0, -0.018), text_font=font,
                         command=self.choose, extraArgs=[company])
        DirectButton(parent=self, relief=None, image=images, image_scale=(0.7, 1, 1.1), pos=(0, 0, -0.24),
                     text='Cancel', text_scale=0.045, text_pos=(0, -0.014), text_font=font,
                     command=self.cancel)
        buttons.removeNode()

    def choose(self, company):
        NPCSettings.setTrolleyCompany(self.avId, company)
        self.finish(True)

    def cancel(self):
        self.finish(False)

    def finish(self, boarding):
        done = self.done
        self.done = None
        self.destroy()
        if done is not None:
            done(boarding)
