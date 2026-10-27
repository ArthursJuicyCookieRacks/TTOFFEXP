"""PoliceChip: the Halloween costume version of Chip, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedChipAI import DistributedChipAI


class DistributedPoliceChipAI(DistributedChipAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPoliceChipAI')

    def __init__(self, air):
        DistributedChipAI.__init__(self, air, TTLocalizer.PoliceChip)

    def walkSpeed(self):
        return ToontownGlobals.ChipSpeed
