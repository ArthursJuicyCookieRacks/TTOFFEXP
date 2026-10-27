"""SockHopDaisy: the Halloween costume version of Daisy, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedDaisyAI import DistributedDaisyAI


class DistributedSockHopDaisyAI(DistributedDaisyAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedSockHopDaisyAI')

    def __init__(self, air):
        DistributedDaisyAI.__init__(self, air, TTLocalizer.SockHopDaisy)

    def walkSpeed(self):
        return ToontownGlobals.DaisySpeed
