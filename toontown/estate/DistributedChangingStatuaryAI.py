from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI
from toontown.estate.DistributedPlantBaseAI import MAX_GROWTH


class DistributedChangingStatuaryAI(DistributedStatuaryAI):
    # The melting snow statues melt a little more every day.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedChangingStatuaryAI")

    def runEpoch(self):
        self.growthLevel = min(self.growthLevel + 1, MAX_GROWTH)
        return True
