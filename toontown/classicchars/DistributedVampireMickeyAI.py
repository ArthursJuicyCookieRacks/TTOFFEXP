"""VampireMickey: the Halloween costume version of Mickey, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedMickeyAI import DistributedMickeyAI


class DistributedVampireMickeyAI(DistributedMickeyAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedVampireMickeyAI')

    def __init__(self, air):
        DistributedMickeyAI.__init__(self, air, TTLocalizer.VampireMickey)

    def walkSpeed(self):
        return ToontownGlobals.VampireMickeySpeed
