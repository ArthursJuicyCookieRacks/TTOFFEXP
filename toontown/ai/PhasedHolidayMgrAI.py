from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject

from toontown.ai.DistributedHydrantZeroMgrAI import DistributedHydrantZeroMgrAI
from toontown.ai.DistributedMailboxZeroMgrAI import DistributedMailboxZeroMgrAI
from toontown.ai.DistributedSillyMeterMgrAI import DistributedSillyMeterMgrAI
from toontown.ai.DistributedTrashcanZeroMgrAI import DistributedTrashcanZeroMgrAI
from toontown.toonbase import ToontownGlobals


class PhasedHolidayMgrAI(DirectObject):
    # Puts up each phased holiday's event manager while the holiday runs.
    notify = DirectNotifyGlobal.directNotify.newCategory('PhasedHolidayMgrAI')

    # holidayId: (manager class, where the AI keeps it)
    Managers = {
        ToontownGlobals.SILLYMETER_HOLIDAY: (DistributedSillyMeterMgrAI, 'SillyMeterMgr'),
        ToontownGlobals.HYDRANT_ZERO_HOLIDAY: (DistributedHydrantZeroMgrAI, 'hydrantZeroMgr'),
        ToontownGlobals.MAILBOX_ZERO_HOLIDAY: (DistributedMailboxZeroMgrAI, 'mailboxZeroMgr'),
        ToontownGlobals.TRASHCAN_ZERO_HOLIDAY: (DistributedTrashcanZeroMgrAI, 'trashcanZeroMgr'),
    }

    def __init__(self, air):
        DirectObject.__init__(self)
        self.air = air
        self.accept('holidayStarted', self.__holidayStarted)
        self.accept('holidayEnded', self.__holidayEnded)
        for holidayId in air.holidayManager.currentHolidays:
            self.__holidayStarted(holidayId)

    def __holidayStarted(self, holidayId):
        if holidayId not in self.Managers:
            return
        mgrClass, attr = self.Managers[holidayId]
        if hasattr(self.air, attr):
            return
        mgr = mgrClass(self.air, holidayId)
        mgr.generateWithRequired(2)
        setattr(self.air, attr, mgr)

    def __holidayEnded(self, holidayId):
        if holidayId not in self.Managers:
            return
        mgrClass, attr = self.Managers[holidayId]
        mgr = getattr(self.air, attr, None)
        if mgr is not None:
            delattr(self.air, attr)
            mgr.requestDelete()
