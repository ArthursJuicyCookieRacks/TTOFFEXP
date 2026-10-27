from toontown.toonbase import ToontownGlobals
from toontown.hood import HoodAI
from toontown.building.DistributedBuildingMgrAI import DistributedBuildingMgrAI

from toontown.classicchars import ClassicCharsAI

class GSHoodAI(HoodAI.HoodAI):
    HOOD = ToontownGlobals.GoofySpeedway

    def __init__(self, air):
        HoodAI.HoodAI.__init__(self, air)
        self.createZone()
        self.spawnObjects()
        
    def createZone(self):
        HoodAI.HoodAI.createZone(self)
        self.air.dnaStoreMap[self.HOOD] = self.air.loadDNA(self.air.genDNAFileName(self.HOOD)).generateData()
        self.buildingMgr = DistributedBuildingMgrAI(self.air, self.HOOD, self.air.dnaStoreMap[self.HOOD], self.air.trophyMgr)
        
        self.classicChars = ClassicCharsAI.spawn(self.air, self.HOOD)

    def spawnObjects(self):
        HoodAI.HoodAI.spawnObjects(self)
        filename = self.air.genDNAFileName(self.HOOD)
        self.air.dnaSpawner.spawnObjects(filename, self.HOOD)
