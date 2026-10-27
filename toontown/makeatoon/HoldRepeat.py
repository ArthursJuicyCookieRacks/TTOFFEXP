"""Holding a Make-A-Toon arrow keeps stepping through the choices.

A press steps once, straight away. Held past HOLD_DELAY the arrow steps again
every REPEAT_TIME (the first, quicker pace: Arthur found the slower one too slow), until
it is let go or reaches the end of the list (where the arrow is disabled).
"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectButton import DirectButton
from direct.gui.DirectGuiBase import DirectGuiWidget
from direct.task import Task
from panda3d.core import MouseButton

HOLD_DELAY = 0.5
REPEAT_TIME = 0.35


def mouseHeld():
    return base.mouseWatcherNode.isButtonDown(MouseButton.one())


def isArrow(widget):
    if not isinstance(widget, DirectButton) or not widget['command']:
        return False
    extraArgs = widget['extraArgs']
    return bool(extraArgs) and extraArgs[-1] in (-1, 1)


def addToArrows(root):
    """Gives every left/right arrow under root the hold-to-repeat."""
    for nodePath in root.findAllMatches('**;+s'):
        # A widget's node is named after its class and guiId: DirectButton-pg12.
        widget = DirectGuiWidget.guiDict.get(nodePath.getName().split('-')[-1])
        if widget is not None and isArrow(widget) and not getattr(widget, 'holdRepeat', False):
            HoldRepeater(widget)


class HoldRepeater:

    def __init__(self, button):
        self.button = button
        self.pressed = False
        self.taskName = 'makeAToonHold-%s' % button.guiId
        button.holdRepeat = True
        self.command = button['command']
        button['command'] = self.click
        button.bind(DGG.B1PRESS, self.press)
        button.bind(DGG.B1RELEASE, self.release)
        button.bind(DGG.EXIT, self.release)

    def step(self):
        self.command(*self.button['extraArgs'])

    def click(self, *args):
        # The press stepped already; a click with no press (from code) steps.
        if self.pressed:
            self.pressed = False
            return
        self.step()

    def press(self, event=None):
        self.pressed = True
        self.step()
        taskMgr.remove(self.taskName)
        taskMgr.doMethodLater(HOLD_DELAY, self.repeat, self.taskName)

    def release(self, event=None):
        taskMgr.remove(self.taskName)

    def repeat(self, task):
        button = self.button
        if button.isEmpty() or button['state'] == DGG.DISABLED or button.isHidden():
            return Task.done
        if not mouseHeld():
            return Task.done
        self.step()
        task.delayTime = REPEAT_TIME
        return Task.again
