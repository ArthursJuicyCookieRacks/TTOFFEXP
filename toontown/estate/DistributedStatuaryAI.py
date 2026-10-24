from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedStatuaryAI(DistributedPlantBaseAI):
    # Statues need no water and never die, so they share the plant fields
    # without the plant care.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedStatuaryAI")

    def waterPlant(self):
        pass

    def waterPlantDone(self):
        pass

    def runEpoch(self):
        return True
