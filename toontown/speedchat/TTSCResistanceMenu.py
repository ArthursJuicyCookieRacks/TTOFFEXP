from direct.showbase import PythonUtil
from otp.speedchat.SCMenu import SCMenu
from otp.speedchat.SCMenuHolder import SCMenuHolder
from toontown.chat import ResistanceChat
from .TTSCResistanceTerminal import TTSCResistanceTerminal

class TTSCResistanceMenu(SCMenu):

    def __init__(self):
        SCMenu.__init__(self)
        self.accept('resistanceMessagesChanged', self.__resistanceMessagesChanged)
        self.__resistanceMessagesChanged()
        submenus = []

    def destroy(self):
        SCMenu.destroy(self)

    def clearMenu(self):
        SCMenu.clearMenu(self)

    def __resistanceMessagesChanged(self):
        self.clearMenu()
        try:
            lt = base.localAvatar
        except:
            return

        phrases = lt.resistanceMessages
        for menuIndex in ResistanceChat.allMenus:
            menu = SCMenu()
            for itemIndex in ResistanceChat.getItems(menuIndex):
                textId = ResistanceChat.encodeId(menuIndex, itemIndex)
                charges = lt.getResistanceMessageCharges(textId)
                if charges > 0:
                    menu.append(TTSCResistanceTerminal(textId, charges))
            if menuIndex in ResistanceChat.miniMenu and not len(menu):
                # Mini Unites only show once you have some.
                menu.destroy()
                continue

            textId = ResistanceChat.encodeId(menuIndex, 0)
            menuName = ResistanceChat.getMenuName(textId)
            self.append(SCMenuHolder(menuName, menu))
