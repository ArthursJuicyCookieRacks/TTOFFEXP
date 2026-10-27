"""Turn based help: Solo or Need Help!

With Setup on Turn based, whenever the player starts something other toons
could join (a street battle, or an elevator into a building, field office,
factory, mint, office, golf course or boss fight) the district leaves a
question (NPCSettings.wantsHelp) and the player's game shows this: Solo keeps
the NPC toons out of it, Need Help! lets them join as they normally would.

Client side; it answers the district directly (see NPCFriends).
"""

import builtins

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.task import Task

from otp.otpbase import OTPGlobals
from toontown.npcplayers import NPCSettings
from toontown.npcplayers.NPCFriends import _call
from toontown.toonbase import ToontownGlobals

QUESTION = 'Other toons want to join you.'
SOLO = 'Solo'
NEED_HELP = 'Need Help!'
TASK_NAME = 'npcHelpPrompt'
POLL = 0.25

_prompt = [None]


def start():
    """Starts watching for the district's questions (once in the game)."""
    taskMgr.remove(TASK_NAME)
    taskMgr.doMethodLater(POLL, _poll, TASK_NAME)


def stop():
    taskMgr.remove(TASK_NAME)
    if _prompt[0] is not None:
        _prompt[0].destroy()
        _prompt[0] = None


def _poll(task):
    avatar = getattr(builtins, 'localAvatar', None)
    if avatar is None or avatar.isEmpty():
        return Task.again
    if _prompt[0] is not None:
        if _prompt[0].key != NPCSettings.takeHelpQuestion(avatar.doId):
            # Over before it was answered (the battle ended, the player
            # got off).
            _prompt[0].destroy()
            _prompt[0] = None
        return Task.again
    key = NPCSettings.takeHelpQuestion(avatar.doId)
    if key is not None:
        _prompt[0] = NPCHelpPrompt(key)
    return Task.again


class NPCHelpPrompt(DirectFrame):

    def __init__(self, key):
        self.box = loader.loadModel('phase_3/models/gui/dialog_box_gui')
        DirectFrame.__init__(self, parent=aspect2d, relief=None, image=self.box,
                             image_color=OTPGlobals.GlobalDialogColor, image_scale=(1.0, 1, 0.6),
                             pos=(0, 0, 0.55), scale=0.85, state=DGG.NORMAL, sortOrder=DGG.NO_FADE_SORT_INDEX)
        self.initialiseoptions(NPCHelpPrompt)
        self.key = key
        font = ToontownGlobals.getInterfaceFont()
        buttons = loader.loadModel('phase_3/models/gui/quit_button')
        images = (buttons.find('**/QuitBtn_UP'), buttons.find('**/QuitBtn_DN'), buttons.find('**/QuitBtn_RLVR'))
        DirectLabel(parent=self, relief=None, pos=(0, 0, 0.1), text=QUESTION, text_scale=0.065, text_font=font)
        for i, (text, wantHelp) in enumerate(((SOLO, False), (NEED_HELP, True))):
            DirectButton(parent=self, relief=None, image=images, image_scale=(1.1, 1, 1.4),
                         pos=(-0.24 + i * 0.48, 0, -0.1), text=text, text_scale=0.055, text_pos=(0, -0.018),
                         text_font=font, command=self.answer, extraArgs=[wantHelp])
        buttons.removeNode()

    def destroy(self):
        if self.box is not None:
            self.box.removeNode()
            self.box = None
        DirectFrame.destroy(self)

    def answer(self, wantHelp):
        key = self.key
        if _prompt[0] is self:
            _prompt[0] = None
        self.destroy()
        _call('helpAnswer', key, wantHelp)
