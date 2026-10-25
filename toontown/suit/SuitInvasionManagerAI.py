from . import SuitDNA
from otp.ai.MagicWordGlobal import *
from direct.task import Task
from toontown.toonbase import ToontownGlobals
from random import random, randint, choice
import datetime
from direct.directnotify import DirectNotifyGlobal

# TODO: NewsManagerAI to properly announce invasions starting, invasions
# ending, and invasions currently in progress.
# All numbers/values in here are hard-coded. Maybe we should move them to
# ToontownGlobals or something?

# The holidays that are an invasion, and their cogs: (cog, special suit),
# special suit being 1 for skelecogs. A None cog is a random one.
G = ToontownGlobals
HolidayInvasions = {
    G.SKELECOG_INVASION: (None, 1),
    G.MR_HOLLYWOOD_INVASION: ('mh', 0),
    G.BOSSCOG_INVASION: ('tbc', 0),
    G.YES_MAN_INVASION: ('ym', 0),
    G.TIGHTWAD_INVASION: ('tw', 0),
    G.TELEMARKETER_INVASION: ('tm', 0),
    G.HEADHUNTER_INVASION: ('hh', 0),
    G.SPINDOCTOR_INVASION: ('sd', 0),
    G.MONEYBAGS_INVASION: ('mb', 0),
    G.TWOFACES_INVASION: ('tf', 0),
    G.MINGLER_INVASION: ('m', 0),
    G.LOANSHARK_INVASION: ('ls', 0),
    G.CORPORATE_RAIDER_INVASION: ('cr', 0),
    G.ROBBER_BARON_INVASION: ('rb', 0),
    G.LEGAL_EAGLE_INVASION: ('le', 0),
    G.BIG_WIG_INVASION: ('bw', 0),
    G.BIG_CHEESE_INVASION: ('tbc', 0),
    G.DOWN_SIZER_INVASION: ('ds', 0),
    G.MOVER_AND_SHAKER_INVASION: ('ms', 0),
    G.DOUBLETALKER_INVASION: ('dt', 0),
    G.PENNY_PINCHER_INVASION: ('pp', 0),
    G.NAME_DROPPER_INVASION: ('nd', 0),
    G.AMBULANCE_CHASER_INVASION: ('ac', 0),
    G.MICROMANAGER_INVASION: ('mm', 0),
    G.NUMBER_CRUNCHER_INVASION: ('nc', 0),
    G.COLD_CALLER_INVASION: ('cc', 0),
    G.BEAN_COUNTER_INVASION: ('bc', 0),
    G.DOUBLE_TALKER_INVASION: ('dt', 0),
    G.DOWNSIZER_INVASION: ('ds', 0),
    G.SELLBOT_INVASION_MOVER_AND_SHAKER: ('ms', 0),
    G.PRE_JULY_4_DOWNSIZER_INVASION: ('ds', 0),
    G.PRE_JULY_4_BIGWIG_INVASION: ('bw', 0),
}
del G
# Enough cogs to last until the holiday is over.
HolidayInvasionSuits = 100000

# The offline game's districts with their own rules. The developers'
# district only gets an invasion someone summons. Each training district
# always has an invasion of one cog track, going from one cog of it to
# another, chosen at random, every TrainingInvasionSuits cogs.
DEVELOPER_DISTRICTS = ('Developers Dreams', 'Developer Dreamland')
TRAINING_DISTRICTS = {
    'Training Tycoon': 's',
    'Training Tundra': 'm',
    'Training Township': 'l',
    'Training Turf': 'c',
}
TrainingInvasionSuits = 250
# The pause between one training invasion and the next.
TrainingInvasionGap = 5


def trainingCogs(dept):
    start = SuitDNA.suitDepts.index(dept) * SuitDNA.suitsPerDept
    return SuitDNA.suitHeadTypes[start:start + SuitDNA.suitsPerDept]


class SuitInvasionManagerAI:
    """
    This is a very basic AI class to handle Suit Invasions in Toontown.
    This class doesn't need to do much, besides telling the suit planners
    when an invasion starts and stops.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('SuitInvasionManagerAI')

    def __init__(self, air):
        self.air = air
        self.invading = 0
        self.specialSuit = 0
        self.suitName = None
        self.numSuits = 0
        self.spawnedSuits = 0
        self.holidayInvasion = None
        districtName = getattr(air, 'districtName', '')
        self.trainingDept = TRAINING_DISTRICTS.get(districtName)
        # Only invasions someone asks for (a summons, a magic word): no
        # random ones and none for a holiday.
        self.summonsOnly = districtName in DEVELOPER_DISTRICTS or self.trainingDept is not None
        if self.trainingDept is not None:
            taskMgr.doMethodLater(1, self.__nextTrainingInvasion, 'training-invasion')
        if self.summonsOnly:
            return
        messenger.accept('holidayStarted', self, self.__holidayStarted)
        messenger.accept('holidayEnded', self, self.__holidayEnded)
        # Holidays already running when the district started.
        taskMgr.doMethodLater(1, self.__startRunningHolidays, 'holiday-invasions')

        if config.ConfigVariableBool('want-mega-invasions', False).getValue(): # TODO - config for this
            # Mega invasion configuration.
            self.randomInvasionProbability = config.GetFloat('mega-invasion-probability', 0.4)
            self.megaInvasionCog = config.ConfigVariableString('mega-invasion-cog-type', '').getValue()
            if not self.megaInvasionCog:
                raise AttributeError("No mega invasion cog specified, but mega invasions are on!")
            if self.megaInvasionCog not in SuitDNA.suitHeadTypes:
                raise AttributeError("Invalid cog type specified for mega invasion!")
            # Start ticking.
            taskMgr.doMethodLater(randint(1800, 5400), self.__randomInvasionTick, 'random-invasion-tick')

        elif config.ConfigVariableBool('want-random-invasions', True).getValue():
            # Random invasion configuration.
            self.randomInvasionProbability = config.GetFloat('random-invasion-probability', 0.3)
            # Start ticking.
            taskMgr.doMethodLater(randint(1800, 5400), self.__randomInvasionTick, 'random-invasion-tick')

    def __randomInvasionTick(self, task=None):
        """
        Each hour, have a tick to check if we want to start an invasion in
        the current district. This works by having a random invasion
        probability, and each tick it will generate a random float between
        0 and 1, and then if it's less than or equal to the probablity, it
        will spawn the invasion.

        An invasion will not be started if there is an invasion already
        on-going.
        """
        # Generate a new tick delay.
        task.delayTime = randint(1800, 5400)
        if self.getInvading():
            # We're already running an invasion. Don't start a new one.
            self.notify.debug('Invasion tested but already running invasion!')
            return task.again
        if random() <= self.randomInvasionProbability:
            # We want an invasion!
            self.notify.debug('Invasion probability hit! Starting invasion.')
            # We want to test if we get a mega invasion or a normal invasion.
            # Take the mega invasion probability and test it. If we get lucky
            # a second time, spawn a mega invasion, otherwise spawn a normal
            # invasion.
            if config.ConfigVariableBool('want-mega-invasions', False).getValue() and random() <= self.randomInvasionProbability:
                # N.B.: randomInvasionProbability = mega invasion probability.
                suitName = self.megaInvasionCog
                numSuits = randint(2000, 15000)
                specialSuit = choice([0, 0, 0, 1, 2])
            else:
                suitName = choice(SuitDNA.suitHeadTypes)
                numSuits = randint(1500, 5000)
                specialSuit = False
            self.startInvasion(suitName, numSuits, specialSuit)
        return task.again

    def __nextTrainingInvasion(self, task=None):
        if not self.getInvading():
            cogs = [cog for cog in trainingCogs(self.trainingDept) if cog != self.lastTrainingCog] or \
                trainingCogs(self.trainingDept)
            cog = choice(cogs)
            self.lastTrainingCog = cog
            self.startInvasion(cog, TrainingInvasionSuits, 0)
        return Task.done

    lastTrainingCog = None

    def __startRunningHolidays(self, task):
        for holidayId in self.air.holidayManager.currentHolidays:
            self.__holidayStarted(holidayId)
        return task.done

    def __holidayStarted(self, holidayId):
        if holidayId not in HolidayInvasions:
            return
        suitName, specialSuit = HolidayInvasions[holidayId]
        if self.getInvading():
            # The holiday's cogs take over from the invasion going on.
            self.stopInvasion()
        if self.startInvasion(suitName or choice(SuitDNA.suitHeadTypes), HolidayInvasionSuits, specialSuit):
            self.holidayInvasion = holidayId

    def __holidayEnded(self, holidayId):
        if holidayId == self.holidayInvasion:
            self.stopInvasion()

    def getInvading(self):
        """ Tell the caller if an invasion is currently running. """
        return self.invading

    def stopInvasion(self, task=None):
        """
        Stop an invasion on the current AI. This is called either by
        self.__checkInvasionOver or by magic word.
        """
        if not self.getInvading():
            # We're not currently invading, go away!
            return False
        # TODO: Fix once we have NewsManagerAI working.
        self.air.newsManager.sendUpdate('setInvasionStatus', [
            ToontownGlobals.SuitInvasionEnd, self.suitName,
            self.numSuits, self.specialSuit
        ])
        # Remove the invasion timeout.
        if task != None:
            task.remove()
        else:
            taskMgr.remove('invasion-timeout')
        self.specialSuit = 0
        self.numSuits = 0
        self.spawnedSuits = 0
        self.invading = 0
        self.suitName = None
        self.holidayInvasion = None
        self.__spAllCogsSupaFly()
        if self.trainingDept is not None:
            # On to the next cog of the track.
            taskMgr.remove('training-invasion')
            taskMgr.doMethodLater(TrainingInvasionGap, self.__nextTrainingInvasion, 'training-invasion')

    def __checkInvasionOver(self):
        """ Test if the current invasion has created all the suits. """
        if self.spawnedSuits >= self.numSuits:
            self.stopInvasion()

    def getInvadingCog(self):
        """ Tell the caller the current cog type invading and if they are a skelecog or v2.0 """
        self.spawnedSuits += 1
        self.__checkInvasionOver()
        return (self.suitName, self.specialSuit)

    def __spAllCogsSupaFly(self):
        """ Tell all SuitPlanners to get rid of the current cogs. """
        for sp in list(self.air.suitPlanners.values()):
            sp.flySuits()

    def startInvasion(self, suitName='f', numSuits=1000, specialSuit=0):
        """
        Start an invasion on the current AI. This can be invoked by anything, such
        as a toon summoning an invasion, or an admin manually starting an
        invasion via a magic word.
        """
        if self.getInvading():
            # We're already invading Toontown, go away!
            return False
        self.invading = True
        self.spawnedSuits = 0
        self.suitName = suitName
        self.numSuits = numSuits
        self.specialSuit = specialSuit
        # Tell all the client's that an invasion has started via the NewsManager.
        self.air.newsManager.sendUpdate('setInvasionStatus', [
            ToontownGlobals.SuitInvasionBegin, self.suitName,
            self.numSuits, self.specialSuit
        ])
        # If the cogs aren't defeated in a set amount of time, the invasion will
        # simply timeout. This was calculated by judging that 1000 cogs should
        # take around 20 minutes, becoming 1.2 seconds per cog.
        # We added in a bit of a grace period, making it 1.5 seconds per cog, or 25 minutes.
        timePerCog = config.GetFloat('invasion-time-per-cog', 1.5)
        taskMgr.doMethodLater(timePerCog * numSuits, self.stopInvasion, 'invasion-timeout')
        self.__spAllCogsSupaFly()
        return True

@magicWord(types=[str, str, int, int], category=CATEGORY_OVERRIDE)
def invasion(cmd, name='f', num=1000, specialSuit = 0):
    """ Spawn an invasion on the current AI if one doesn't exist. """
    invMgr = simbase.air.suitInvasionManager
    if cmd == 'start':
        if invMgr.getInvading():
            return "There is already an invasion on the current AI!"
        if not name in SuitDNA.suitHeadTypes:
            return "This cog does not exist!"
        invMgr.startInvasion(name, num, specialSuit)
    elif cmd == 'stop':
        if not invMgr.getInvading():
            return "There is no invasion on the current AI!"
        invMgr.stopInvasion()
    else:
        return "You didn't enter a valid command! Commands are ~invasion start or stop."
