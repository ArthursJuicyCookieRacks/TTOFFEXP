"""The Setup screen: how the NPC toons play along with the player.

Opened from the Setup button in Make-A-Toon and on the Shticker Book's
Options page. Three choices, kept in the settings file:

  Normal      NPC toons join the player's battles and elevators as they do.
  Turn based  Each time, the player is asked: Solo or Need Help!
  Solo        No NPC toon ever helps.
"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel

from otp.otpbase import OTPGlobals
from toontown.npcplayers import NPCSettings
from toontown.toonbase import ToontownGlobals

TITLE = 'Setup'
HEADING = 'How should the other toons play with you?'
CHOICES = (
    (NPCSettings.HELP_NORMAL, 'Normal', 'Other toons join your battles and elevators as they like.'),
    (NPCSettings.HELP_TURN_BASED, 'Turn based', 'Each time, you are asked: Solo or Need Help!'),
    (NPCSettings.HELP_SOLO, 'Solo', 'No other toon ever helps you.'),
)
CLOSE = 'Close'
PICKED = (0.6, 1.0, 0.6, 1)
UNPICKED = (1, 1, 1, 1)


class NPCSetupPanel(DirectFrame):

    def __init__(self, doneEvent=None):
        self.box = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        DirectFrame.__init__(self, parent=aspect2d, relief=None, image=self.box,
                             image_color=OTPGlobals.GlobalDialogColor, image_scale=(1.5, 1, 1.25),
                             pos=(0, 0, 0.05), state=DGG.NORMAL, sortOrder=DGG.NO_FADE_SORT_INDEX)
        self.initialiseoptions(NPCSetupPanel)
        self.doneEvent = doneEvent
        font = ToontownGlobals.getInterfaceFont()
        buttons = loader.loadModel('phase_3/models/gui/quit_button')
        images = (buttons.find('**/QuitBtn_UP'), buttons.find('**/QuitBtn_DN'), buttons.find('**/QuitBtn_RLVR'))
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.5), text=TITLE, text_scale=0.1,
                    text_font=ToontownGlobals.getSignFont(), text_fg=(0.0, 0.65, 0.35, 1))
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.37), text=HEADING, text_scale=0.055, text_font=font,
                    text_wordwrap=24)
        self.buttons = {}
        for i, (mode, label, blurb) in enumerate(CHOICES):
            z = 0.2 - i * 0.2
            self.buttons[mode] = DirectButton(parent=self, relief=None, image=images, image_scale=(1.0, 1, 1.4),
                                              pos=(-0.42, 0, z), text=label, text_scale=0.055, text_pos=(0, -0.018),
                                              text_font=font, command=self.pick, extraArgs=[mode])
            DirectLabel(parent=self, relief=None, pos=(-0.17, 0, z + 0.03), text=blurb, text_scale=0.045,
                        text_font=font, text_align=0, text_wordwrap=18)
        DirectButton(parent=self, relief=None, image=images, image_scale=(0.8, 1, 1.2), pos=(0, 0, -0.48),
                     text=CLOSE, text_scale=0.05, text_pos=(0, -0.016), text_font=font, command=self.close)
        buttons.removeNode()
        self.showPicked()

    def showPicked(self):
        mode = NPCSettings.helpMode()
        for name, button in self.buttons.items():
            button['image_color'] = PICKED if name == mode else UNPICKED

    def pick(self, mode):
        settings = getattr(getattr(base, 'display', None), 'settings', None)
        NPCSettings.setHelpMode(mode, settings)
        self.showPicked()

    def close(self):
        doneEvent = self.doneEvent
        self.destroy()
        if doneEvent:
            messenger.send(doneEvent)

    def destroy(self):
        if self.box is not None:
            self.box.removeNode()
            self.box = None
        DirectFrame.destroy(self)
