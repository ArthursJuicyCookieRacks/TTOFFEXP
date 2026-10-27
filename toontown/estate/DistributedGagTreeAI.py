from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI
from toontown.estate import GardenGlobals


class DistributedGagTreeAI(DistributedPlantBaseAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedGagTreeAI")

    def getWilted(self):
        return int(self.isWilted())

    def getTrackAndLevel(self):
        return GardenGlobals.getTreeTrackAndLevel(self.typeIndex)

    def sendState(self):
        DistributedPlantBaseAI.sendState(self)
        self.sendUpdate('setWilted', [self.getWilted()])

    def canBeHarvested(self):
        # A tree bears gags the toon can pick once every lower tree of its
        # track is full grown.
        if not self.isFruiting() or self.isWilted():
            return False
        track, level = self.getTrackAndLevel()
        for lower in range(level):
            tree = self.garden.getGagTree(track, lower)
            if not tree or not tree.isGTEFullGrown():
                return False
        return True

    def requestHarvest(self):
        av = self.getOwnerSender()
        if not av:
            return
        if not self.canBeHarvested():
            self.d_interactionDenied(av.doId)
            return
        track, level = self.getTrackAndLevel()
        picked = 0
        while picked < self.attributes['maxFruit'] and av.inventory.addItem(track, level) > 0:
            picked += 1
        if not picked:
            self.d_interactionDenied(av.doId)
            return
        av.b_setInventory(av.inventory.makeNetString())
        self.startMovie(GardenGlobals.MOVIE_HARVEST, av.doId, self.__doneHarvesting)

    def __doneHarvesting(self):
        # The fruit grows back in a day.
        self.clearMovie()
        self.b_setGrowthLevel(self.growthThresholds[1])
        self.plantChanged()
