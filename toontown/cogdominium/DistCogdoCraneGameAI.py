import random

from direct.directnotify import DirectNotifyGlobal
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium.DistCogdoCraneAI import DistCogdoCraneAI
from toontown.cogdominium.DistCogdoCraneCogAI import DistCogdoCraneCogAI
from toontown.cogdominium.DistCogdoCraneMoneyBagAI import DistCogdoCraneMoneyBagAI
from toontown.cogdominium import CogdoCraneGameConsts as Consts
from toontown.suit import SuitDNA


class DistCogdoCraneGameAI(DistCogdoGameAI):
    # The Vend-A-Stomper, the Cashbot field office. Cogs walk out of four
    # hallways, each with a coin for the Stomp-O-Matic in the middle of the
    # room; every few coins it stomps one of the toons' laff barrels. The
    # toons work four cranes and drop money bags on the cogs, which knocks
    # the coin out of their hands. The barrels left when the clock runs out
    # are laff for the toons.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoCraneGameAI")

    def __init__(self, air, interior):
        DistCogdoGameAI.__init__(self, air, interior)
        self.cranes = []
        self.moneyBags = []
        self.cogs = {}
        self.barrelsLeft = Consts.NumBarrels
        self.coins = 0
        self.nextLane = 0

    def generate(self):
        DistCogdoGameAI.generate(self)
        for i in range(len(Consts.CranePosHprs)):
            crane = DistCogdoCraneAI(self.air, self, i)
            crane.generateWithRequired(self.zoneId)
            self.cranes.append(crane)
        for i in range(len(Consts.MoneyBagPosHprs)):
            bag = DistCogdoCraneMoneyBagAI(self.air, self, i)
            bag.generateWithRequired(self.zoneId)
            self.moneyBags.append(bag)

    def delete(self):
        taskMgr.remove(self.uniqueName('game-over'))
        taskMgr.remove(self.uniqueName('spawn'))
        for obj in self.cranes + self.moneyBags + list(self.cogs.values()):
            if not obj.isDeleted():
                obj.requestDelete()
        self.cranes = []
        self.moneyBags = []
        self.cogs = {}
        DistCogdoGameAI.delete(self)

    def getBarrels(self):
        return [self.barrelsLeft, self.coins]

    def d_setBarrels(self):
        self.sendUpdate('setBarrels', self.getBarrels())

    def getDifficulty(self):
        return DistCogdoGameAI.getDifficulty(self)

    # --- The game ---

    def start(self):
        for crane in self.cranes:
            crane.request('Free')
        for bag in self.moneyBags:
            bag.request('Initial')
        DistCogdoGameAI.start(self)

    def startGame(self):
        taskMgr.doMethodLater(Consts.GameDuration, self.__gameOver, self.uniqueName('game-over'))
        # The first cog comes out soon, so the toons see what they are up
        # against while they get to the cranes.
        taskMgr.doMethodLater(3.0, self.__spawnCog, self.uniqueName('spawn'))

    def __gameOver(self, task):
        self.finishGame()
        return task.done

    def endGame(self):
        taskMgr.remove(self.uniqueName('game-over'))
        taskMgr.remove(self.uniqueName('spawn'))
        for crane in self.cranes:
            if crane.state != 'Off':
                crane.request('Off')
        for cog in list(self.cogs.values()):
            cog.flyAway()
        self.interior.setGameMemos(self.barrelsLeft * Consts.LaffPerBarrel)

    def __spawnCog(self, task):
        if self.finished:
            return task.done
        difficulty = self.getDifficulty()
        maxCogs = int(round(Consts.lerpDifficulty(Consts.MaxCogsRange, difficulty)))
        walking = [cog for cog in self.cogs.values() if cog.isWalking()]
        if len(walking) < maxCogs:
            self.__makeCog(difficulty)
        period = Consts.lerpDifficulty(Consts.SpawnPeriodRange, difficulty)
        task.delayTime = period * random.uniform(0.8, 1.2)
        return task.again

    def __makeCog(self, difficulty):
        # A cashbot fitting the field office's playground: the cogs on the
        # streets there are the ones that bring the coins.
        lane = self.nextLane
        self.nextLane = (self.nextLane + random.choice((1, 2, 3))) % len(Consts.LaneAngles)
        level = 1 + int(difficulty * 4) + random.randint(0, 2)
        dna = SuitDNA.SuitDNA()
        dna.newSuitRandom(level=min(level, 7), dept='m')
        cog = DistCogdoCraneCogAI(self.air, self, dna, lane, globalClock.getRealTime())
        cog.generateWithRequired(self.zoneId)
        self.cogs[cog.doId] = cog

    def cogDone(self, cog):
        self.cogs.pop(cog.doId, None)
        if not cog.isDeleted():
            cog.requestDelete()

    def coinInserted(self, cog):
        if self.finished or self.barrelsLeft <= 0:
            return
        self.coins += 1
        if self.coins >= Consts.CoinsPerStomp:
            self.coins = 0
            self.barrelsLeft -= 1
            self.sendUpdate('stomp', [self.barrelsLeft, self.getNetworkTime()])
        self.d_setBarrels()
        if self.barrelsLeft <= 0:
            # Every barrel is smashed: nothing left to save up here.
            self.finishGame()

    # --- What the toons do ---

    def hitCog(self, avId, bag, cogId):
        cog = self.cogs.get(cogId)
        if cog is None or not self.started or self.finished:
            return
        cog.hitByBag(avId)

    def isPlaying(self, avId):
        return avId in self.toons and avId not in self.sadToons

    def toonLeft(self, avId):
        for crane in self.cranes:
            crane.removeToon(avId)
        for bag in self.moneyBags:
            bag.removeToon(avId)
