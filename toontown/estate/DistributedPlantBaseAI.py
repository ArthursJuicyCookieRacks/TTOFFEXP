from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI
from toontown.estate import GardenGlobals

# Growth stops here so that it fits the int8 field.
MAX_GROWTH = 100


class DistributedPlantBaseAI(DistributedLawnDecorAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPlantBaseAI")

    def __init__(self, air, garden=None):
        DistributedLawnDecorAI.__init__(self, air, garden)
        self.typeIndex = 0
        self.waterLevel = 0
        self.growthLevel = 0
        self.optional = 0

    def setTypeIndex(self, typeIndex):
        self.typeIndex = typeIndex
        self.attributes = GardenGlobals.PlantAttributes[typeIndex]
        self.growthThresholds = self.attributes.get('growthThresholds', (1, 1, 1))
        self.maxWaterLevel = self.attributes.get('maxWaterLevel', 0)
        self.minWaterLevel = self.attributes.get('minWaterLevel', 0)

    def getTypeIndex(self):
        return self.typeIndex

    def setWaterLevel(self, waterLevel):
        self.waterLevel = waterLevel

    def d_setWaterLevel(self, waterLevel):
        self.sendUpdate('setWaterLevel', [waterLevel])

    def b_setWaterLevel(self, waterLevel):
        self.setWaterLevel(waterLevel)
        self.d_setWaterLevel(waterLevel)

    def getWaterLevel(self):
        return self.waterLevel

    def setGrowthLevel(self, growthLevel):
        self.growthLevel = growthLevel

    def d_setGrowthLevel(self, growthLevel):
        self.sendUpdate('setGrowthLevel', [growthLevel])

    def b_setGrowthLevel(self, growthLevel):
        self.setGrowthLevel(growthLevel)
        self.d_setGrowthLevel(growthLevel)

    def getGrowthLevel(self):
        return self.growthLevel

    def isWilted(self):
        return self.waterLevel < 0

    def isFruiting(self):
        return self.growthLevel >= self.growthThresholds[2]

    def isGTEFullGrown(self):
        return self.growthLevel >= self.growthThresholds[1]

    def getLawnItem(self):
        return [self.typeIndex, self.plot, self.waterLevel, self.growthLevel, self.optional]

    def waterPlant(self):
        av = self.getOwnerSender()
        if not av:
            return
        # The bigger the can and the more skilled the toon, the more water
        # the plant can store.
        power = GardenGlobals.getWateringCanPower(av.getWateringCan(), av.getWateringCanSkill())
        watered = self.waterLevel < min(power, self.maxWaterLevel)
        if watered:
            self.waterLevel += 1
            if self.waterLevel < 0:
                # Water revives a wilted plant.
                self.waterLevel = 0
            av.b_setWateringCanSkill(av.getWateringCanSkill() + 1)
        self.startMovie(GardenGlobals.MOVIE_WATER, av.doId, self.__doneWatering)

    def waterPlantDone(self):
        # The movie sends both this and finishInteraction; the movie's end is
        # handled through movieDone below.
        if self.air.getAvatarIdFromSender() == self.movieAvId and self.movieCallback:
            self.movieDone()

    def __doneWatering(self):
        self.clearMovie()
        self.d_setWaterLevel(self.waterLevel)
        self.plantChanged()

    def plantChanged(self):
        if self.garden:
            self.garden.plantChanged(self)

    def runEpoch(self):
        # A day passes: a watered plant grows and drinks some of its water.
        # It returns False once the plant has died of thirst.
        if self.waterLevel > 0:
            self.growthLevel = min(self.growthLevel + 1, MAX_GROWTH)
        self.waterLevel -= 1
        return self.waterLevel >= self.minWaterLevel

    def sendState(self):
        self.d_setWaterLevel(self.waterLevel)
        self.d_setGrowthLevel(self.growthLevel)

    def removeItem(self):
        av = self.getOwnerSender()
        if not av:
            return
        self.harvest(av)
        self.dig(av)

    def harvest(self, av):
        pass

    def dig(self, av):
        avId = av.doId
        self.startMovie(GardenGlobals.MOVIE_REMOVE, avId, lambda: self.garden.removePlant(self.plot, avId))
