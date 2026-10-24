import math

from direct.directnotify import DirectNotifyGlobal
from toontown.estate import GardenGlobals
from toontown.estate.DistributedGardenBoxAI import DistributedGardenBoxAI
from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
from toontown.estate.DistributedFlowerAI import DistributedFlowerAI
from toontown.estate.DistributedGagTreeAI import DistributedGagTreeAI
from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI
from toontown.estate.DistributedToonStatuaryAI import DistributedToonStatuaryAI
from toontown.estate.DistributedChangingStatuaryAI import DistributedChangingStatuaryAI
from toontown.estate.DistributedAnimatedStatuaryAI import DistributedAnimatedStatuaryAI
from toontown.toonbase import ToontownBattleGlobals

# How far apart the flowers sit along a planter, by the number of flowers
# it holds (planterD holds one, planterC two and planterA three).
FlowerSpacing = {GardenGlobals.BOX_ONE: 0,
 GardenGlobals.BOX_TWO: 4.5,
 GardenGlobals.BOX_THREE: 3.75}

# The client snaps every garden item down onto the ground.
PLANT_Z = 20


class GardenAI:
    # One toon's garden beside their house: the planters, a plot at every
    # hard point, and whatever grows there. The plants are kept in the
    # estate's lawnItem slot for that house as
    # (typeIndex, hardPoint, waterLevel, growthLevel, optional).
    notify = DirectNotifyGlobal.directNotify.newCategory('GardenAI')

    def __init__(self, air, estate, ownerIndex):
        self.air = air
        self.estate = estate
        self.ownerIndex = ownerIndex
        self.boxes = []
        self.objects = {}

    def getOwnerId(self):
        return self.estate.toons[self.ownerIndex]

    def getOwner(self):
        return self.air.doId2do.get(self.getOwnerId())

    def getPlots(self):
        return GardenGlobals.estatePlots[self.ownerIndex]

    def create(self, items):
        boxes = GardenGlobals.estateBoxes[self.ownerIndex]
        for index, (x, y, h, boxType) in enumerate(boxes):
            box = DistributedGardenBoxAI(self.air, self)
            box.setPlot(index)
            box.setOwnerIndex(self.ownerIndex)
            box.setTypeIndex(boxType)
            box.setPosition(x, y, PLANT_Z)
            box.setHeading(h)
            box.generateWithRequired(self.estate.zoneId)
            self.boxes.append(box)

        plants = {}
        for item in self.validItems(items):
            plants[item[1]] = item
        for hardPoint in range(len(self.getPlots())):
            item = plants.get(hardPoint)
            if item:
                typeIndex, hardPoint, waterLevel, growthLevel, optional = item
                self.objects[hardPoint] = self.makePlant(hardPoint, typeIndex, waterLevel, growthLevel, optional)
            else:
                self.objects[hardPoint] = self.makePlot(hardPoint)

    def validItems(self, items):
        # Keeps the plants that fit their plot. Before plants were saved,
        # the starter garden stored a placeholder at every hard point; those
        # put gag trees in flower plots and are dropped here.
        valid = []
        plots = self.getPlots()
        for item in items:
            typeIndex, hardPoint = item[0], item[1]
            attrib = GardenGlobals.PlantAttributes.get(typeIndex)
            if hardPoint >= len(plots) or not attrib or attrib['plantType'] != plots[hardPoint][3]:
                self.notify.warning('dropping garden item %s of toon %d' % (list(item), self.getOwnerId()))
                continue
            valid.append(list(item))
        return valid

    def destroy(self):
        for obj in self.boxes + list(self.objects.values()):
            obj.requestDelete()
        self.boxes = []
        self.objects = {}
        self.estate = None

    def getPlotPosition(self, hardPoint):
        x, y, h, plotType = self.getPlots()[hardPoint]
        if plotType != GardenGlobals.FLOWER_TYPE:
            return (x, y, h)
        # A flower plot's x and y are its planter and its place in it.
        boxIndex, slot = int(x), int(y)
        boxX, boxY, boxH, boxType = GardenGlobals.estateBoxes[self.ownerIndex][boxIndex]
        offset = (slot - (boxType - 1) / 2.0) * FlowerSpacing[boxType]
        radians = math.radians(boxH)
        return (boxX + offset * math.cos(radians), boxY + offset * math.sin(radians), boxH)

    def place(self, obj, hardPoint):
        x, y, h = self.getPlotPosition(hardPoint)
        obj.setPlot(hardPoint)
        obj.setOwnerIndex(self.ownerIndex)
        obj.setPosition(x, y, PLANT_Z)
        obj.setHeading(h)

    def makePlot(self, hardPoint):
        plot = DistributedGardenPlotAI(self.air, self)
        self.place(plot, hardPoint)
        plot.generateWithRequired(self.estate.zoneId)
        return plot

    def makePlant(self, hardPoint, typeIndex, waterLevel=0, growthLevel=0, optional=0):
        plantType = GardenGlobals.PlantAttributes[typeIndex]['plantType']
        if plantType == GardenGlobals.FLOWER_TYPE:
            plant = DistributedFlowerAI(self.air, self)
            plant.setVariety(optional)
        elif plantType == GardenGlobals.GAG_TREE_TYPE:
            plant = DistributedGagTreeAI(self.air, self)
        elif typeIndex in GardenGlobals.ToonStatuaryTypeIndices:
            plant = DistributedToonStatuaryAI(self.air, self)
            plant.setOptional(optional)
        elif typeIndex in GardenGlobals.ChangingStatuaryTypeIndices:
            plant = DistributedChangingStatuaryAI(self.air, self)
        elif typeIndex in GardenGlobals.AnimatedStatuaryTypeIndices:
            plant = DistributedAnimatedStatuaryAI(self.air, self)
        else:
            plant = DistributedStatuaryAI(self.air, self)
        self.place(plant, hardPoint)
        plant.setTypeIndex(typeIndex)
        plant.setWaterLevel(waterLevel)
        plant.setGrowthLevel(growthLevel)
        plant.generateWithRequired(self.estate.zoneId)
        return plant

    def plant(self, hardPoint, typeIndex, optional, avId):
        # The dig movie is done: the plot turns into the plant.
        old = self.objects.get(hardPoint)
        if old:
            old.requestDelete()
        plant = self.makePlant(hardPoint, typeIndex, optional=optional)
        self.objects[hardPoint] = plant
        plant.startMovie(GardenGlobals.MOVIE_FINISHPLANTING, avId)
        self.save()
        self.air.writeServerEvent('garden_plant', avId=avId, typeIndex=typeIndex, hardPoint=hardPoint)

    def removePlant(self, hardPoint, avId=0):
        old = self.objects.get(hardPoint)
        if old:
            old.requestDelete()
        plot = self.makePlot(hardPoint)
        self.objects[hardPoint] = plot
        if avId:
            plot.startMovie(GardenGlobals.MOVIE_FINISHREMOVING, avId)
        self.save()

    def plantChanged(self, plant):
        self.save()

    def getPlants(self):
        return [obj for obj in self.objects.values() if hasattr(obj, 'getLawnItem')]

    def getGagTree(self, track, level):
        for obj in self.objects.values():
            if isinstance(obj, DistributedGagTreeAI) and obj.getTrackAndLevel() == (track, level):
                return obj
        return None

    def hasGagTree(self, track, level):
        return self.getGagTree(track, level) is not None

    def runEpochs(self, count):
        # Days pass for every plant; the ones that dried out die.
        if count <= 0:
            return
        for plant in self.getPlants():
            alive = True
            for i in range(count):
                alive = plant.runEpoch()
                if not alive:
                    break
            if alive:
                plant.sendState()
            else:
                self.removePlant(plant.plot)
        self.save()

    def save(self):
        items = [plant.getLawnItem() for plant in self.getPlants()]
        items.sort(key=lambda item: item[1])
        self.estate.b_setSlotItems(self.ownerIndex, items)
        self.updateTrackBonus()

    def getTrackBonus(self):
        # Organic gags: a track is boosted up to the highest gag whose tree
        # and every lower tree of the track are full grown and not wilted.
        bonus = []
        for track in range(len(ToontownBattleGlobals.Tracks)):
            level = -1
            for curLevel in range(len(ToontownBattleGlobals.Levels[track])):
                tree = self.getGagTree(track, curLevel)
                if not tree or not tree.isGTEFullGrown() or tree.isWilted():
                    break
                level = curLevel
            bonus.append(level)
        return bonus

    def updateTrackBonus(self):
        av = self.getOwner()
        if av:
            bonus = self.getTrackBonus()
            if bonus != list(av.getTrackBonusLevel()):
                av.b_setTrackBonusLevel(bonus)
