from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.toon.ToonDNA import ToonDNA

# The colour list here is in Toontown Rewritten's order, where black is 38
# (0x1a, Disney's black, is a light blue now).
BLACK = 38

class DistributedBlackCatMgrAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedBlackCatMgrAI")

    def requestBlackCatTransformation(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not av: return

        if av.dna.getAnimal() == 'cat' and av.dna.headColor != BLACK:
            newDNA = ToonDNA()
            newDNA.makeFromNetString(av.getDNAString())
            newDNA.headColor = BLACK
            newDNA.armColor = BLACK
            newDNA.legColor = BLACK
            taskMgr.doMethodLater(1.0, lambda task: av.b_setDNAString(newDNA.makeNetString()), 'transform-%d' % avId)

            self.sendUpdate('doBlackCatTransformation', [avId])
