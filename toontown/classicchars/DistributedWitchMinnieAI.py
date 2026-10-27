"""WitchMinnie: the Halloween costume version of Minnie, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedMinnieAI import DistributedMinnieAI


class DistributedWitchMinnieAI(DistributedMinnieAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedWitchMinnieAI')

    def __init__(self, air):
        DistributedMinnieAI.__init__(self, air, TTLocalizer.WitchMinnie)

    def walkSpeed(self):
        return ToontownGlobals.WitchMinnieSpeed
