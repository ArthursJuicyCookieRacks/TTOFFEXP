from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed.ClockDelta import *
from direct.task import Task

from toontown.toonbase import ToontownGlobals
from toontown.parties import PartyGlobals

from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI
from toontown.effects import FireworkShows

import random
import time

class HolidayManagerAI:
    # Runs Toontown's holiday calendar from the device's clock. The running
    # holidays go to every client through the NewsManager, which starts and
    # ends each holiday's decorations, costumes and chat on its side.
    notify = directNotify.newCategory('HolidayManagerAI')

    # Yearly holidays: (holidayId, (month, day, hour, minute) start,
    # (month, day, hour, minute) end). An end before its start wraps into
    # the next year.
    YearlyHolidays = [
        (ToontownGlobals.WINTER_DECORATIONS, (12, 1, 0, 0), (1, 3, 23, 59)),
        (ToontownGlobals.WINTER_CAROLING, (12, 14, 0, 0), (1, 3, 23, 59)),
        (ToontownGlobals.NEWYEARS_FIREWORKS, (12, 30, 0, 0), (1, 1, 23, 59)),
        (ToontownGlobals.VALENTINES_DAY, (2, 9, 0, 0), (2, 16, 23, 59)),
        (ToontownGlobals.IDES_OF_MARCH, (3, 14, 0, 0), (3, 20, 23, 59)),
        (ToontownGlobals.APRIL_FOOLS_COSTUMES, (3, 29, 0, 0), (4, 11, 23, 59)),
        (ToontownGlobals.SILLYMETER_HOLIDAY, (3, 29, 0, 0), (4, 11, 23, 59)),
        (ToontownGlobals.HYDRANT_ZERO_HOLIDAY, (3, 29, 0, 0), (4, 4, 23, 59)),
        (ToontownGlobals.MAILBOX_ZERO_HOLIDAY, (4, 1, 0, 0), (4, 7, 23, 59)),
        (ToontownGlobals.TRASHCAN_ZERO_HOLIDAY, (4, 5, 0, 0), (4, 11, 23, 59)),
        (ToontownGlobals.JULY4_FIREWORKS, (6, 29, 0, 0), (7, 5, 23, 59)),
        (ToontownGlobals.HALLOWEEN_PROPS, (10, 18, 0, 0), (11, 1, 23, 59)),
        (ToontownGlobals.HALLOWEEN_COSTUMES, (10, 18, 0, 0), (11, 1, 23, 59)),
        (ToontownGlobals.TRICK_OR_TREAT, (10, 18, 0, 0), (11, 1, 23, 59)),
        (ToontownGlobals.BLACK_CAT_DAY, (10, 31, 0, 0), (10, 31, 23, 59)),
    ]

    # Weekly holidays: (holidayId, weekday), Monday being 0.
    WeeklyHolidays = [
        (ToontownGlobals.CIRCUIT_RACING_EVENT, 0),
        (ToontownGlobals.FISH_BINGO_NIGHT, 2),
        (ToontownGlobals.TROLLEY_HOLIDAY, 3),
        (ToontownGlobals.SILLY_SATURDAY_BINGO, 5),
    ]

    # Silly Saturday takes turns, an hour each, between these three.
    SillySaturdayHolidays = [
        ToontownGlobals.SILLY_SATURDAY_BINGO,
        ToontownGlobals.SILLY_SATURDAY_CIRCUIT,
        ToontownGlobals.SILLY_SATURDAY_TROLLEY,
    ]

    # Holidays that move through phases over their run, and how many.
    PhasedHolidays = {
        ToontownGlobals.SILLYMETER_HOLIDAY: 16,
        ToontownGlobals.HYDRANT_ZERO_HOLIDAY: 7,
        ToontownGlobals.MAILBOX_ZERO_HOLIDAY: 7,
        ToontownGlobals.TRASHCAN_ZERO_HOLIDAY: 7,
    }

    # The Silly Meter's SpeedChat phrases, by phase.
    SillyChatterPhases = [ToontownGlobals.SILLY_CHATTER_ONE] * 4 + [ToontownGlobals.SILLY_CHATTER_TWO] * 4 + \
                         [ToontownGlobals.SILLY_CHATTER_THREE] * 4 + [ToontownGlobals.SILLY_CHATTER_FOUR] * 3 + \
                         [ToontownGlobals.SILLY_CHATTER_FIVE]

    FireworksHolidays = {
        ToontownGlobals.JULY4_FIREWORKS: ToontownGlobals.JULY4_FIREWORKS,
        ToontownGlobals.NEWYEARS_FIREWORKS: ToontownGlobals.NEWYEARS_FIREWORKS,
    }

    def __init__(self, air):
        self.air = air
        self.currentHolidays = []

        # want-holidays #f turns the calendar off; force-holidays is a comma
        # separated list of holiday ids that always run.
        self.wantHolidays = config.ConfigVariableBool('want-holidays', True).getValue()
        self.forcedHolidays = []
        self.forcedStartTimes = {}
        self.stoppedHolidays = []
        self.phaseOverrides = {}
        for holidayId in config.ConfigVariableString('force-holidays', '').getValue().split(','):
            if holidayId.strip():
                self.forcedHolidays.append(int(holidayId))

        self.updateHolidays()
        taskMgr.doMethodLater(60, self.__holidayTick, 'holiday-tick')

        if config.ConfigVariableBool('want-hourly-fireworks', False).getValue():
            self.__startFireworksTick()
        else:
            self.__startHolidayFireworksTick()

    def __holidayTick(self, task):
        self.updateHolidays()
        return task.again

    def getHolidaysAt(self, now):
        # The holiday ids running at the given time.struct_time.
        holidays = []
        if self.wantHolidays:
            stamp = (now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min)
            for holidayId, start, end in self.YearlyHolidays:
                if start <= end:
                    running = start <= stamp <= end
                else:
                    running = stamp >= start or stamp <= end
                if running:
                    holidays.append(holidayId)
            for holidayId, weekday in self.WeeklyHolidays:
                if now.tm_wday == weekday:
                    if holidayId == ToontownGlobals.SILLY_SATURDAY_BINGO:
                        holidayId = self.SillySaturdayHolidays[now.tm_hour % len(self.SillySaturdayHolidays)]
                    holidays.append(holidayId)
        for holidayId in self.forcedHolidays:
            if holidayId not in holidays:
                holidays.append(holidayId)
        if ToontownGlobals.SILLYMETER_HOLIDAY in holidays and ToontownGlobals.SILLYMETER_HOLIDAY not in self.stoppedHolidays:
            phase = self.getHolidayPhase(ToontownGlobals.SILLYMETER_HOLIDAY, time.mktime(now))
            holidays.append(self.SillyChatterPhases[phase])
        return [holidayId for holidayId in holidays if holidayId not in self.stoppedHolidays]

    def updateHolidays(self):
        holidays = self.getHolidaysAt(time.localtime())
        if holidays == self.currentHolidays:
            return
        ended = [holidayId for holidayId in self.currentHolidays if holidayId not in holidays]
        started = [holidayId for holidayId in holidays if holidayId not in self.currentHolidays]
        self.currentHolidays = holidays
        for holidayId in ended:
            self.notify.info('holiday %d ended' % holidayId)
            messenger.send('holidayEnded', [holidayId])
        for holidayId in started:
            self.notify.info('holiday %d started' % holidayId)
            messenger.send('holidayStarted', [holidayId])
        newsManager = getattr(self.air, 'newsManager', None)
        if newsManager is not None:
            newsManager.b_setHolidayIdList(self.currentHolidays)

    def getHolidayRun(self, holidayId, now=None):
        # The (start, end) of the current run of a holiday, in seconds since
        # the epoch. A holiday started by hand runs for a day from then.
        if now is None:
            now = time.time()
        if holidayId in self.forcedStartTimes:
            start = self.forcedStartTimes[holidayId]
            return start, start + 86400
        local = time.localtime(now)
        for yearlyId, start, end in self.YearlyHolidays:
            if yearlyId != holidayId:
                continue
            startYear = endYear = local.tm_year
            if end < start:
                # A run over New Year's: which one depends on the side we are on.
                if (local.tm_mon, local.tm_mday, local.tm_hour, local.tm_min) >= start:
                    endYear += 1
                else:
                    startYear -= 1
            startTime = time.mktime((startYear,) + start + (0, 0, 0, -1))
            endTime = time.mktime((endYear,) + end + (59, 0, 0, -1))
            return int(startTime), int(endTime)
        dayStart = time.mktime(local[:3] + (0, 0, 0, 0, 0, -1))
        return int(dayStart), int(dayStart) + 86400

    def getHolidayEndTime(self, holidayId):
        return self.getHolidayRun(holidayId)[1]

    def getHolidayPhase(self, holidayId, now=None):
        # Which phase a phased holiday is in: its run split evenly.
        if now is None:
            now = time.time()
        start, end = self.getHolidayRun(holidayId, now)
        numPhases = self.PhasedHolidays[holidayId]
        phase = int((now - start) * numPhases // max(1, end - start))
        phase = max(0, min(numPhases - 1, phase))
        return self.phaseOverrides.get(holidayId, phase)

    def setHolidayPhase(self, holidayId, phase):
        self.phaseOverrides[holidayId] = phase
        self.updateHolidays()
        messenger.send('holidayPhaseChanged', [holidayId])

    def startHoliday(self, holidayId):
        # Starts a holiday until endHoliday, whatever the calendar says.
        if holidayId in self.stoppedHolidays:
            self.stoppedHolidays.remove(holidayId)
        if holidayId not in self.forcedHolidays:
            self.forcedHolidays.append(holidayId)
            self.forcedStartTimes[holidayId] = int(time.time())
        self.updateHolidays()

    def endHoliday(self, holidayId):
        # Ends a holiday until startHoliday, whatever the calendar says.
        if holidayId in self.forcedHolidays:
            self.forcedHolidays.remove(holidayId)
            self.forcedStartTimes.pop(holidayId, None)
        self.phaseOverrides.pop(holidayId, None)
        if holidayId not in self.stoppedHolidays:
            self.stoppedHolidays.append(holidayId)
        self.updateHolidays()

    """
    Fireworks Stuff
    """
    def __startFireworksTick(self):
        # Check seconds until next hour.
        ts = time.time()
        nextHour = 3600 - (ts % 3600)
        taskMgr.doMethodLater(nextHour, self.__fireworksTick, 'hourly-fireworks')

    def __fireworksTick(self, task):
        # The next tick will occur in exactly an hour.
        task.delayTime = 3600

        showName = config.ConfigVariableString('hourly-fireworks-type', 'july4').getValue()

        if showName == 'july4':
            showType = ToontownGlobals.JULY4_FIREWORKS

        elif showName == 'newyears':
            showType = ToontownGlobals.NEWYEARS_FIREWORKS

        elif showName == 'summer':
            showType = PartyGlobals.FireworkShows.Summer

        elif showName == 'random':
            shows = [ToontownGlobals.JULY4_FIREWORKS, ToontownGlobals.NEWYEARS_FIREWORKS, PartyGlobals.FireworkShows.Summer]
            showType = random.choice(shows)
        else:
            raise AttributeError('%s is an invalid firework type' % showName)
            return

        numShows = len(FireworkShows.shows.get(showType, []))
        showIndex = random.randint(0, numShows - 1)
        for hood in self.air.hoods:
            if hood.HOOD == ToontownGlobals.GolfZone:
                continue
            fireworksShow = DistributedFireworkShowAI(self.air)
            fireworksShow.generateWithRequired(hood.HOOD)
            fireworksShow.b_startShow(showType, showIndex, globalClockDelta.getRealNetworkTime())
        return task.again

    def __startHolidayFireworksTick(self):
        # Fireworks go off every hour, on the hour, during the fireworks
        # holidays.
        ts = time.time()
        nextHour = 3600 - (ts % 3600)
        taskMgr.doMethodLater(nextHour, self.__holidayFireworksTick, 'holiday-fireworks')

    def __holidayFireworksTick(self, task):
        task.delayTime = 3600
        for holidayId in self.currentHolidays:
            showType = self.FireworksHolidays.get(holidayId)
            if showType is not None:
                self.startFireworks(showType)
                break
        return task.again

    def startFireworks(self, showType):
        numShows = len(FireworkShows.shows.get(showType, []))
        if not numShows:
            return
        showIndex = random.randint(0, numShows - 1)
        for hood in self.air.hoods:
            if hood.HOOD == ToontownGlobals.GolfZone:
                continue
            fireworksShow = DistributedFireworkShowAI(self.air)
            fireworksShow.generateWithRequired(hood.HOOD)
            fireworksShow.b_startShow(showType, showIndex, globalClockDelta.getRealNetworkTime())

    def isHolidayRunning(self, *holidayIds):
        for holidayId in holidayIds:
            if holidayId in self.currentHolidays:
                return True
        return False

    def getWeeklyCalendarHolidays(self):
        return [[holidayId, weekday] for holidayId, weekday in self.WeeklyHolidays]

    def getYearlyCalendarHolidays(self):
        return [[holidayId, list(start), list(end)] for holidayId, start, end in self.YearlyHolidays]
