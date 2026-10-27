from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.toonbase import ToontownGlobals
from otp.ai.MagicWordGlobal import *

class NewsManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("NewsManagerAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.holidayIdList = list(air.holidayManager.currentHolidays)
        self.accept('avatarEntered', self.__avatarEntered)

    def __avatarEntered(self, avatar):
        self.sendUpdateToAvatarId(avatar.getDoId(), 'setHolidayIdList', [self.holidayIdList])
        if self.air.suitInvasionManager.getInvading():
            self.sendUpdateToAvatarId(avatar.getDoId(), 'setInvasionStatus', [
                ToontownGlobals.SuitInvasionBulletin, self.air.suitInvasionManager.suitName,
                self.air.suitInvasionManager.numSuits, self.air.suitInvasionManager.specialSuit
            ])

    def setPopulation(self, todo0):
        pass

    def setBingoWin(self, todo0):
        pass

    def setBingoStart(self):
        pass

    def setBingoEnd(self):
        pass

    def setCircuitRaceStart(self):
        pass

    def setCircuitRaceEnd(self):
        pass

    def setTrolleyHolidayStart(self):
        pass

    def setTrolleyHolidayEnd(self):
        pass

    def setTrolleyWeekendStart(self):
        pass

    def setTrolleyWeekendEnd(self):
        pass

    def setRoamingTrialerWeekendStart(self):
        pass

    def setRoamingTrialerWeekendEnd(self):
        pass

    def setInvasionStatus(self, todo0, todo1, todo2, todo3):
        pass

    def setHolidayIdList(self, holidayIdList):
        self.holidayIdList = holidayIdList

    def d_setHolidayIdList(self, holidayIdList):
        self.sendUpdate('setHolidayIdList', [holidayIdList])

    def b_setHolidayIdList(self, holidayIdList):
        self.setHolidayIdList(holidayIdList)
        self.d_setHolidayIdList(holidayIdList)

    def getHolidayIdList(self):
        return self.holidayIdList

    def holidayNotify(self):
        pass

    def setWeeklyCalendarHolidays(self, todo0):
        pass

    def getWeeklyCalendarHolidays(self):
        return self.air.holidayManager.getWeeklyCalendarHolidays()

    def setYearlyCalendarHolidays(self, todo0):
        pass

    def getYearlyCalendarHolidays(self):
        return self.air.holidayManager.getYearlyCalendarHolidays()

    def setOncelyCalendarHolidays(self, todo0):
        pass

    def getOncelyCalendarHolidays(self):
        return []

    def setRelativelyCalendarHolidays(self, todo0):
        pass

    def getRelativelyCalendarHolidays(self):
        return []

    def setMultipleStartHolidays(self, todo0):
        pass

    def getMultipleStartHolidays(self):
        return []

    def sendSystemMessage(self, todo0, todo1):
        pass

@magicWord(category=CATEGORY_DEBUG)
def invasionstatus():
    """ Returns the number of cogs available in an invasion in a pretty way. """
    simbase.air.newsManager.sendUpdateToAvatarId(spellbook.getInvoker().getDoId(), 'setInvasionStatus', [
        ToontownGlobals.SuitInvasionUpdate, simbase.air.suitInvasionManager.suitName,
        simbase.air.suitInvasionManager.numSuits, simbase.air.suitInvasionManager.specialSuit
    ])

@magicWord(category=CATEGORY_OVERRIDE, types=[int])
def startHoliday(holidayId):
    """ Starts a holiday, whatever the calendar says. """
    simbase.air.holidayManager.startHoliday(holidayId)
    return 'Holiday %d started.' % holidayId

@magicWord(category=CATEGORY_OVERRIDE, types=[int])
def endHoliday(holidayId):
    """ Ends a holiday, whatever the calendar says. """
    simbase.air.holidayManager.endHoliday(holidayId)
    return 'Holiday %d ended.' % holidayId

@magicWord(category=CATEGORY_DEBUG)
def holidays():
    """ Lists the holidays that are running. """
    return 'Holidays: %s' % (simbase.air.holidayManager.currentHolidays or 'none')
