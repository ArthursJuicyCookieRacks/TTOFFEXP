"""The Tools menu of SpeedChat: a few magic words a player of the offline
game may want without typing them."""

from otp.speedchat.SCMenu import SCMenu
from otp.speedchat.SCTerminal import SCTerminal

# How long the second press of Max Toon may wait to confirm the first.
CONFIRM_TIME = 60.0


class TTSCToolsTerminal(SCTerminal):

    def __init__(self, text, word):
        SCTerminal.__init__(self)
        self.text = text
        self.word = word

    def isWhisperable(self):
        return False

    def handleSelect(self, event):
        event = str(event)
        if event.startswith('mouse3'):
            return
        SCTerminal.handleSelect(self, event)
        messenger.send('magicWord', [self.getMagicWord()])

    def getMagicWord(self):
        return self.word


class TTSCMaxToonTerminal(TTSCToolsTerminal):
    # Maxing a toon can't be undone, so the first press asks (the magic word
    # answers with its warning) and a second press within a minute does it.
    pressedAt = None

    def __init__(self):
        TTSCToolsTerminal.__init__(self, 'MaxToon', '~maxToon')

    def getMagicWord(self):
        now = globalClock.getRealTime()
        if TTSCMaxToonTerminal.pressedAt is not None and now - TTSCMaxToonTerminal.pressedAt <= CONFIRM_TIME:
            TTSCMaxToonTerminal.pressedAt = None
            return '~maxToon CONFIRM'
        TTSCMaxToonTerminal.pressedAt = now
        return '~maxToon'


class TTSCToolsMenu(SCMenu):

    def __init__(self):
        SCMenu.__init__(self)
        self.append(TTSCMaxToonTerminal())
        self.append(TTSCToolsTerminal('sostoons', '~sostoons'))
        self.append(TTSCToolsTerminal('unites', '~unites'))
