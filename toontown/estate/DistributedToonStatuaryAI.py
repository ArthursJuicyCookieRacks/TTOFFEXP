from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI


class DistributedToonStatuaryAI(DistributedStatuaryAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedToonStatuaryAI")

    def setOptional(self, optional):
        # The toon the statue shows, as ToonStatueSelectionGUI encodes it.
        self.optional = optional

    def getOptional(self):
        return self.optional
