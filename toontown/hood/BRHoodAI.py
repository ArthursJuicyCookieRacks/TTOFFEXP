from toontown.toonbase import ToontownGlobals
from .SZHoodAI import SZHoodAI
from toontown.toon import NPCToons

from toontown.classicchars import ClassicCharsAI

class BRHoodAI(SZHoodAI):
    HOOD = ToontownGlobals.TheBrrrgh

    def createZone(self):
        SZHoodAI.createZone(self)

        self.spawnObjects()
        self.classicChars = ClassicCharsAI.spawn(self.air, self.HOOD)

