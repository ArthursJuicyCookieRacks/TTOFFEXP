"""Asks the player in a full elevator whether to start.

When the player and NPC toons fill every seat, the district stops the
elevator's countdown (NPCParty.askReady) and the player's elevator shows
this: Start goes at once, Cancel sends the NPC toons back out and the
countdown carries on.

Client side; it answers the district directly (see NPCFriends).
"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import ConfigVariableBool

from otp.otpbase import OTPGlobals
from toontown.npcplayers.NPCFriends import _call
from toontown.toonbase import ToontownGlobals

QUESTION = 'Are you ready to start?'
START = 'Start'
CANCEL = 'Cancel'


def wantAsk():
    # The game's own tests board without anyone to answer: they go at once.
    return ConfigVariableBool('npc-elevator-ask', True).getValue()


class NPCReadyPrompt(DirectFrame):

    def __init__(self, elevatorId, done):
        """done(started) is called once the player has answered."""
        self.box = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        DirectFrame.__init__(self, parent=aspect2d, relief=None, image=self.box,
                             image_color=OTPGlobals.GlobalDialogColor, image_scale=(1.0, 1, 0.6),
                             pos=(0, 0, 0.1), state=DGG.NORMAL, sortOrder=DGG.NO_FADE_SORT_INDEX)
        self.initialiseoptions(NPCReadyPrompt)
        self.elevatorId = elevatorId
        self.done = done
        font = ToontownGlobals.getInterfaceFont()
        buttons = loader.loadModel('phase_3/models/gui/quit_button')
        images = (buttons.find('**/QuitBtn_UP'), buttons.find('**/QuitBtn_DN'), buttons.find('**/QuitBtn_RLVR'))
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.1), text=QUESTION, text_scale=0.065, text_font=font)
        for i, (text, start) in enumerate(((START, True), (CANCEL, False))):
            DirectButton(parent=self, relief=None, image=images, image_scale=(1.0, 1, 1.4),
                         pos=(-0.22 + i * 0.44, 0, -0.1), text=text, text_scale=0.055, text_pos=(0, -0.018),
                         text_font=font, command=self.answer, extraArgs=[start])
        buttons.removeNode()

    def destroy(self):
        if self.box is not None:
            self.box.removeNode()
            self.box = None
        DirectFrame.destroy(self)

    def answer(self, start):
        done = self.done
        self.done = None
        self.destroy()
        _call('readyAnswer', self.elevatorId, start)
        if done is not None:
            done(start)
