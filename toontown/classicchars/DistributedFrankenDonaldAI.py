"""FrankenDonald: the Halloween costume version of Donald, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedDonaldAI import DistributedDonaldAI


class DistributedFrankenDonaldAI(DistributedDonaldAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFrankenDonaldAI')

    def __init__(self, air):
        DistributedDonaldAI.__init__(self, air, TTLocalizer.FrankenDonald)

    def walkSpeed(self):
        return ToontownGlobals.FrankenDonaldSpeed
