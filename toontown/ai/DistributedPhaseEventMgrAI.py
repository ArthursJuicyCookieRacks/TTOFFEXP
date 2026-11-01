import datetime
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

class DistributedPhaseEventMgrAI(DistributedObjectAI):
    # Tells clients where a phased holiday (the Silly Meter, the animated
    # Zero props) is: its phase dates and the phase it is in now.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPhaseEventMgrAI")
    PhaseEvent = None

    def __init__(self, air, holidayId):
        DistributedObjectAI.__init__(self, air)
        self.holidayId = holidayId
        holidayManager = air.holidayManager
        self.numPhases = holidayManager.PhasedHolidays[holidayId]
        self.holidayDates = self.__runDates()
        self.curPhase = holidayManager.getHolidayPhase(holidayId)
        self.isRunning = True

    def __runDates(self):
        start, end = self.air.holidayManager.getHolidayRun(self.holidayId)
        dates = []
        for phase in range(self.numPhases + 1):
            stamp = time.localtime(start + (end - start) * phase // self.numPhases)
            dates.append(list(stamp[:6]))
        return dates

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.accept('holidayPhaseChanged', self.__updatePhase)
        taskMgr.doMethodLater(60, self.__phaseTick, self.uniqueName('phase-tick'))
        if self.PhaseEvent:
            messenger.send(self.PhaseEvent, [self.curPhase])

    def delete(self):
        self.ignoreAll()
        taskMgr.remove(self.uniqueName('phase-tick'))
        DistributedObjectAI.delete(self)

    def __phaseTick(self, task):
        self.__updatePhase(self.holidayId)
        return task.again

    def __updatePhase(self, holidayId):
        if holidayId != self.holidayId:
            return
        # A holiday that runs again (the Silly Meter's new month) has new
        # phase dates.
        dates = self.__runDates()
        if dates != self.holidayDates:
            self.holidayDates = dates
            self.sendUpdate('setDates', [dates])
        phase = self.air.holidayManager.getHolidayPhase(self.holidayId)
        if phase != self.curPhase:
            self.b_setCurPhase(phase)

    def setNumPhases(self, numPhases):
        self.numPhases = numPhases

    def getNumPhases(self):
        return self.numPhases

    def setDates(self, holidayDates):
        self.holidayDates = holidayDates

    def getDates(self):
        return self.holidayDates

    def setCurPhase(self, curPhase):
        self.curPhase = curPhase
        if self.PhaseEvent:
            messenger.send(self.PhaseEvent, [curPhase])

    def d_setCurPhase(self, curPhase):
        self.sendUpdate('setCurPhase', [curPhase])

    def b_setCurPhase(self, curPhase):
        self.setCurPhase(curPhase)
        self.d_setCurPhase(curPhase)

    def getCurPhase(self):
        return self.curPhase

    def setIsRunning(self, isRunning):
        self.isRunning = isRunning

    def getIsRunning(self):
        return self.isRunning
