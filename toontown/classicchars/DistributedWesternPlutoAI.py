"""WesternPluto: the Halloween costume version of Pluto, same brain, own look."""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from .DistributedPlutoAI import DistributedPlutoAI


class DistributedWesternPlutoAI(DistributedPlutoAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedWesternPlutoAI')

    def __init__(self, air):
        DistributedPlutoAI.__init__(self, air, TTLocalizer.WesternPluto)

    def walkSpeed(self):
        return ToontownGlobals.WesternPlutoSpeed
