from direct.directnotify import DirectNotifyGlobal
from toontown.building.SuitPlannerInteriorAI import SuitPlannerInteriorAI


class SuitPlannerCogdoInteriorAI(SuitPlannerInteriorAI):
    # The cogs of a field office. Only the top floor, the executive suite,
    # has a battle; it is planned like the top floor of a cog building of
    # the same height, boss included.
    notify = DirectNotifyGlobal.directNotify.newCategory('SuitPlannerCogdoInteriorAI')

    def __init__(self, layout, bldgLevel, bldgTrack, zone):
        self.layout = layout
        SuitPlannerInteriorAI.__init__(self, layout.getNumFloors(), bldgLevel, bldgTrack, zone)
        self.numFloors = layout.getNumGameFloors()

    def genBossFloorSuits(self):
        return self.genFloorSuits(len(self.suitInfos) - 1)
