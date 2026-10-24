from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI
from toontown.estate import GardenGlobals


class DistributedFlowerAI(DistributedPlantBaseAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedFlowerAI")

    def setVariety(self, variety):
        self.optional = variety

    def getVariety(self):
        return self.optional

    def harvest(self, av):
        # Picking a bloom puts it in the basket. Picking one that took every
        # bean the shovel can plant trains the shovel.
        if not self.isFruiting() or self.isWilted():
            return
        if not av.addFlowerToBasket(self.typeIndex, self.optional):
            return
        beans = GardenGlobals.getNumBeansRequired(self.typeIndex, self.optional)
        if beans == GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill()):
            if av.getShovelSkill() < GardenGlobals.getMaxShovelSkill():
                av.b_setShovelSkill(av.getShovelSkill() + 1)
