import time

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject

from toontown.ai import ScavengerHuntGlobals
from toontown.ai.DistributedTrickOrTreatTargetAI import DistributedTrickOrTreatTargetAI
from toontown.ai.DistributedWinterCarolingTargetAI import DistributedWinterCarolingTargetAI
from toontown.toonbase import ToontownGlobals


class ScavengerHuntMgrAI(DirectObject):
    # Runs the Trick-or-Treat and Winter Caroling scavenger hunts: puts a
    # target in each of the hunt's shops while its holiday runs, pays out
    # jellybeans for each shop and the cheesy effect for all of them.
    notify = DirectNotifyGlobal.directNotify.newCategory('ScavengerHuntMgrAI')

    TargetClasses = {
        ToontownGlobals.TRICK_OR_TREAT: DistributedTrickOrTreatTargetAI,
        ToontownGlobals.WINTER_CAROLING: DistributedWinterCarolingTargetAI,
    }

    def __init__(self, air):
        DirectObject.__init__(self)
        self.air = air
        self.targets = {}
        self.accept('holidayStarted', self.__holidayStarted)
        self.accept('holidayEnded', self.__holidayEnded)
        for holidayId in air.holidayManager.currentHolidays:
            self.__holidayStarted(holidayId)

    def __holidayStarted(self, holidayId):
        if holidayId not in ScavengerHuntGlobals.Hunts or holidayId in self.targets:
            return
        goals, _ = ScavengerHuntGlobals.Hunts[holidayId]
        targets = []
        for goal, zoneId in goals.items():
            target = self.TargetClasses[holidayId](self.air, HuntGoals(self, holidayId), goal)
            target.generateWithRequired(zoneId)
            targets.append(target)
        self.targets[holidayId] = targets

    def __holidayEnded(self, holidayId):
        for target in self.targets.pop(holidayId, []):
            target.requestDelete()

    def avatarAttemptingGoal(self, holidayId, avId, goal):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        goals, effect = ScavengerHuntGlobals.Hunts[holidayId]
        year = time.localtime().tm_year
        code = ScavengerHuntGlobals.encodeGoal(holidayId, year, goal)
        found = av.getScavengerHuntGoals()
        if code in found:
            # The client shows "already found" for no jellybeans.
            self.__sendTargetMet(av, holidayId, 0)
            return
        found = found + [code]
        av.b_setScavengerHuntGoals(found)
        av.addMoney(ScavengerHuntGlobals.BeanReward)
        self.__sendTargetMet(av, holidayId, ScavengerHuntGlobals.BeanReward)
        self.notify.info('toon %d found goal %d of holiday %d' % (avId, goal, holidayId))
        foundThisYear = [g for h, y, g in map(ScavengerHuntGlobals.decodeGoal, found) if h == holidayId and y == year]
        if all(g in foundThisYear for g in goals):
            expireTime = self.air.holidayManager.getHolidayEndTime(holidayId) + ToontownGlobals.TOT_REWARD_END_OFFSET_AMOUNT
            av.b_setCheesyEffect(effect, 0, expireTime)
            if holidayId == ToontownGlobals.TRICK_OR_TREAT:
                av.sendUpdate('trickOrTreatMilestoneMet', [])

    def __sendTargetMet(self, av, holidayId, beanAmount):
        if holidayId == ToontownGlobals.WINTER_CAROLING:
            av.sendUpdate('winterCarolingTargetMet', [beanAmount])
        else:
            av.sendUpdate('trickOrTreatTargetMet', [beanAmount])


class HuntGoals:
    # What a target calls back into: the manager, for one hunt.

    def __init__(self, mgr, holidayId):
        self.mgr = mgr
        self.holidayId = holidayId

    def avatarAttemptingGoal(self, avId, goal):
        self.mgr.avatarAttemptingGoal(self.holidayId, avId, goal)
