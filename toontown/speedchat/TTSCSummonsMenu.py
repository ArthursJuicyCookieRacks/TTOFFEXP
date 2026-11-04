"""SpeedChat's Summons menu: where a toon uses the mini summons won from the
field offices (Arthur). They are kept apart from the boss battles' summons
in the Shticker Book. One submenu for each department that has any, listing
each cog held and how many; picking one asks first, then calls that cog onto
the street."""

from otp.speedchat.SCMenu import SCMenu
from otp.speedchat.SCMenuHolder import SCMenuHolder
from otp.speedchat.SCTerminal import SCTerminal
from toontown.toonbase import TTLocalizer
from toontown.suit import SuitDNA
from toontown.battle import SuitBattleGlobals


def cogName(suitIndex):
    return SuitBattleGlobals.SuitAttributes[SuitDNA.suitHeadTypes[suitIndex]]['name']


class TTSCSummonsTerminal(SCTerminal):

    def __init__(self, suitIndex, count):
        SCTerminal.__init__(self)
        self.suitIndex = suitIndex
        self.text = cogName(suitIndex) if count == 1 else '%s  x%d' % (cogName(suitIndex), count)

    def isWhisperable(self):
        return False

    def handleSelect(self, event):
        if str(event).startswith('mouse3'):
            return
        SCTerminal.handleSelect(self, event)
        askToSummon(self.suitIndex)


class TTSCNoSummonsTerminal(SCTerminal):

    def __init__(self):
        SCTerminal.__init__(self)
        self.text = TTLocalizer.SCSummonsNone

    def isWhisperable(self):
        return False

    def handleSelect(self, event):
        # Nothing to use yet: just closes SpeedChat.
        SCTerminal.handleSelect(self, event)


_dialog = None


def askToSummon(suitIndex):
    global _dialog
    from toontown.toontowngui import TTDialog
    from direct.gui import DirectGuiGlobals as DGG
    if _dialog:
        _dialog.cleanup()

    def answer(choice):
        global _dialog
        if _dialog:
            _dialog.cleanup()
            _dialog = None
        if choice == DGG.DIALOG_OK and base.localAvatar.getMiniSummons()[suitIndex] > 0:
            base.localAvatar.d_reqMiniSummons(suitIndex)

    _dialog = TTDialog.TTDialog(parent=aspect2dp, style=TTDialog.YesNo, text=TTLocalizer.SCSummonsConfirm % cogName(suitIndex),
                                fadeScreen=0.5, command=answer)
    _dialog.show()


class TTSCSummonsMenu(SCMenu):

    def __init__(self):
        SCMenu.__init__(self)
        self.accept('miniSummonsChanged', self.__summonsChanged)
        self.__summonsChanged()

    def destroy(self):
        self.ignoreAll()
        SCMenu.destroy(self)

    def __summonsChanged(self):
        self.clearMenu()
        try:
            held = base.localAvatar.getMiniSummons()
        except Exception:
            return
        perDept = SuitDNA.suitsPerDept
        anything = False
        for dept in range(len(SuitDNA.suitDepts)):
            cogs = [(i, held[i]) for i in range(dept * perDept, (dept + 1) * perDept) if i < len(held) and held[i] > 0]
            if not cogs:
                continue
            anything = True
            menu = SCMenu()
            for i, count in cogs:
                menu.append(TTSCSummonsTerminal(i, count))
            self.append(SCMenuHolder(TTLocalizer.SCSummonsDepts[dept], menu=menu))
        if not anything:
            self.append(TTSCNoSummonsTerminal())
