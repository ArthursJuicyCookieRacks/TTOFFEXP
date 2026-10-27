from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

class DistributedScavengerHuntTargetAI(DistributedObjectAI):
    # One shop of a scavenger hunt; the hunt's manager decides what a toon
    # gets for saying the hunt's phrase here.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedScavengerHuntTargetAI")

    def __init__(self, air, huntMgr=None, goal=0):
        DistributedObjectAI.__init__(self, air)
        self.huntMgr = huntMgr
        self.goal = goal

    def attemptScavengerHunt(self):
        avId = self.air.getAvatarIdFromSender()
        if self.huntMgr is not None:
            self.huntMgr.avatarAttemptingGoal(avId, self.goal)
