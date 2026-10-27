"""SuperGoofy: the Halloween costume version of GoofySpeedway, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedGoofySpeedwayAI import DistributedGoofySpeedwayAI


class DistributedSuperGoofyAI(DistributedGoofySpeedwayAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedSuperGoofyAI')

    def __init__(self, air):
        DistributedGoofySpeedwayAI.__init__(self, air, TTLocalizer.SuperGoofy)

    def walkSpeed(self):
        return ToontownGlobals.SuperGoofySpeed
