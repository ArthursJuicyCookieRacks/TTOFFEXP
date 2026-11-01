import time
from datetime import datetime, timedelta, tzinfo
from direct.distributed import DistributedObject
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import TTLocalizer

# Toontown time is the device's own local time (Arthur: "if the clock on
# their device is in Eastern then the Toontown time should be Eastern"). It
# used to be US/Pacific, the original servers' time zone, so the clock in
# the Shticker Book, the calendar and the party planner were hours off for
# most players. The offset (and daylight saving) comes from the device for
# each date, so it is right all year.
class ToontownTimeZone(tzinfo):

    @staticmethod
    def _local(dt):
        try:
            stamp = time.mktime((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, -1))
            return time.localtime(stamp)
        except (OverflowError, ValueError):
            return time.localtime()

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(seconds=time.localtime().tm_gmtoff)
        return timedelta(seconds=self._local(dt).tm_gmtoff)

    def dst(self, dt):
        local = self._local(dt) if dt is not None else time.localtime()
        return timedelta(hours=1) if local.tm_isdst > 0 else timedelta(0)

    def tzname(self, dt):
        local = self._local(dt) if dt is not None else time.localtime()
        return local.tm_zone

    def fromutc(self, dt):
        # Straight from the device's clock rules, so the hour that repeats
        # when daylight saving ends comes out right.
        stamp = (dt.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()
        local = time.localtime(stamp)
        return datetime(*local[:6], microsecond=dt.microsecond, tzinfo=self)


# UTC is very simple, though:
class UTC(tzinfo):
    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)

class ToontownTimeManager(DistributedObject.DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownTimeManager')
    ClockFormat = '%I:%M:%S %p'
    formatStr = '%Y-%m-%d %H:%M:%S'

    def __init__(self, serverTimeUponLogin = 0, clientTimeUponLogin = 0, globalClockRealTimeUponLogin = 0):
        self.serverTimeZone = ToontownTimeZone()
        self.updateLoginTimes(serverTimeUponLogin, clientTimeUponLogin, globalClockRealTimeUponLogin)
        self.debugSecondsAdded = 0

    def updateLoginTimes(self, serverTimeUponLogin, clientTimeUponLogin, globalClockRealTimeUponLogin):
        self.serverTimeUponLogin = serverTimeUponLogin
        self.clientTimeUponLogin = clientTimeUponLogin
        self.globalClockRealTimeUponLogin = globalClockRealTimeUponLogin
        naiveTime = datetime.utcfromtimestamp(self.serverTimeUponLogin)
        self.serverDateTime = datetime.fromtimestamp(self.serverTimeUponLogin, self.serverTimeZone)

    def getCurServerDateTime(self):
        secondsPassed = globalClock.getRealTime() - self.globalClockRealTimeUponLogin + self.debugSecondsAdded
        curDateTime = (self.serverDateTime + timedelta(seconds=secondsPassed)).astimezone(self.serverTimeZone)
        return curDateTime

    def getRelativeServerDateTime(self, timeOffset):
        secondsPassed = globalClock.getRealTime() - self.globalClockRealTimeUponLogin + self.debugSecondsAdded
        secondsPassed += timeOffset
        curDateTime = (self.serverDateTime + timedelta(seconds=secondsPassed)).astimezone(self.serverTimeZone)
        return curDateTime

    def getCurServerDateTimeForComparison(self):
        secondsPassed = globalClock.getRealTime() - self.globalClockRealTimeUponLogin + self.debugSecondsAdded
        curDateTime = self.serverDateTime + timedelta(seconds=secondsPassed)
        curDateTime = curDateTime.replace(tzinfo=self.serverTimeZone)
        return curDateTime

    def getCurServerTimeStr(self):
        curDateTime = self.getCurServerDateTime()
        result = curDateTime.strftime(self.ClockFormat)
        if result[0] == '0':
            result = result[1:]
        return result

    def setDebugSecondsAdded(self, moreSeconds):
        self.debugSecondsAdded = moreSeconds

    def debugTest(self):
        startTime = datetime.today()
        serverTzInfo = self.serverTimeZone
        startTime = startTime.replace(tzinfo=serverTzInfo)
        self.notify.info('startTime = %s' % startTime)
        serverTime = self.getCurServerDateTime()
        self.notify.info('serverTime = %s' % serverTime)
        result = startTime <= serverTime
        self.notify.info('start < serverTime %s' % result)
        startTime1MinAgo = startTime + timedelta(minutes=-1)
        self.notify.info('startTime1MinAgo = %s' % startTime1MinAgo)
        result2 = startTime1MinAgo <= serverTime
        self.notify.info('startTime1MinAgo < serverTime %s' % result2)
        serverTimeForComparison = self.getCurServerDateTimeForComparison()
        self.notify.info('serverTimeForComparison = %s' % serverTimeForComparison)
        result3 = startTime1MinAgo <= serverTimeForComparison
        self.notify.info('startTime1MinAgo < serverTimeForComparison %s' % result3)

    def convertStrToToontownTime(self, dateStr):
        curDateTime = self.getCurServerDateTime()
        try:
            curDateTime = datetime.fromtimestamp(time.mktime(time.strptime(dateStr, self.formatStr)), self.serverTimeZone)
        except:
            self.notify.warning('error parsing date string=%s' % dateStr)

        result = curDateTime
        return result

    def convertUtcStrToToontownTime(self, dateStr):
        curDateTime = self.getCurServerDateTime()
        try:
            timeTuple = time.strptime(dateStr, self.formatStr)
            utcDateTime = datetime(timeTuple[0], timeTuple[1], timeTuple[2], timeTuple[3], timeTuple[4], timeTuple[5], timeTuple[6], UTC())
            curDateTime = utcDateTime.astimezone(self.serverTimeZone)
        except:
            self.notify.warning('error parsing date string=%s' % dateStr)

        result = curDateTime
        return result
