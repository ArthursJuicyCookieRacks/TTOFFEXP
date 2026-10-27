"""JailbirdDale: the Halloween costume version of Dale, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedDaleAI import DistributedDaleAI


class DistributedJailbirdDaleAI(DistributedDaleAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedJailbirdDaleAI')

    def __init__(self, air, chipId):
        DistributedDaleAI.__init__(self, air, chipId, TTLocalizer.JailbirdDale)

    def walkSpeed(self):
        return ToontownGlobals.DaleSpeed
