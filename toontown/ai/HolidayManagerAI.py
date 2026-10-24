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
        self.stoppedHolidays = []
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

    def startHoliday(self, holidayId):
        # Starts a holiday until endHoliday, whatever the calendar says.
        if holidayId in self.stoppedHolidays:
            self.stoppedHolidays.remove(holidayId)
        if holidayId not in self.forcedHolidays:
            self.forcedHolidays.append(holidayId)
        self.updateHolidays()

    def endHoliday(self, holidayId):
        # Ends a holiday until startHoliday, whatever the calendar says.
        if holidayId in self.forcedHolidays:
            self.forcedHolidays.remove(holidayId)
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
