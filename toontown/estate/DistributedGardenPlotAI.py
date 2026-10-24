from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI
from toontown.estate import GardenGlobals
from toontown.toonbase import ToontownBattleGlobals


class DistributedGardenPlotAI(DistributedLawnDecorAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedGardenPlotAI")

    def getPlotType(self):
        return GardenGlobals.whatCanBePlanted(self.ownerIndex, self.plot)

    def __plant(self, av, typeIndex, optional=0):
        # Digs, then the garden puts the new plant here once the dig movie
        # is done.
        avId = av.doId
        self.startMovie(GardenGlobals.MOVIE_PLANT, avId,
                        lambda: self.garden.plant(self.plot, typeIndex, optional, avId))

    def __payBeans(self, av, beans):
        if beans > GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill()):
            return False
        return av.takeMoney(beans)

    def plantFlower(self, species, variety):
        av = self.getOwnerSender()
        if not av:
            return
        if self.getPlotType() != GardenGlobals.FLOWER_TYPE or variety >= len(GardenGlobals.getFlowerVarieties(species)):
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        if not self.__payBeans(av, GardenGlobals.getNumBeansRequired(species, variety)):
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        self.__plant(av, species, variety)

    def plantGagTree(self, track, level):
        av = self.getOwnerSender()
        if not av:
            return
        if self.getPlotType() != GardenGlobals.GAG_TREE_TYPE or track >= len(ToontownBattleGlobals.Tracks) or level >= len(ToontownBattleGlobals.Levels[track]):
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        # The gag itself is the seed, and a tree needs the trees of every
        # lower gag of its track.
        lowerTrees = all(self.garden.hasGagTree(track, lower) for lower in range(level))
        if av.inventory.numItem(track, level) <= 0 or self.garden.hasGagTree(track, level) or not lowerTrees:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        av.inventory.useItem(track, level)
        av.b_setInventory(av.inventory.makeNetString())
        self.__plant(av, GardenGlobals.getTreeTypeIndex(track, level))

    def __plantStatuary(self, species, optional):
        av = self.getOwnerSender()
        if not av:
            return
        attrib = GardenGlobals.PlantAttributes.get(species)
        if self.getPlotType() != GardenGlobals.STATUARY_TYPE or not attrib or attrib['plantType'] != GardenGlobals.STATUARY_TYPE:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        recipe = GardenGlobals.Recipes.get(attrib['varieties'][0][0], {})
        special = recipe.get('special', -1)
        if not any(index == special and count > 0 for index, count in av.getGardenSpecials()):
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        if not self.__payBeans(av, len(recipe.get('beans', ''))):
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
            return
        av.removeGardenItem(special, 1)
        self.__plant(av, species, optional)

    def plantStatuary(self, species):
        if species in GardenGlobals.ToonStatuaryTypeIndices:
            # A toon statue needs the toon it shows.
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
            return
        self.__plantStatuary(species, 0)

    def plantToonStatuary(self, species, dnaCode):
        if species not in GardenGlobals.ToonStatuaryTypeIndices:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
            return
        self.__plantStatuary(species, dnaCode)

    def plantNothing(self, burntBeans):
        # Beans that make no recipe are lost in the dirt.
        av = self.getOwnerSender()
        if not av:
            return
        av.takeMoney(min(burntBeans, av.getTotalMoney()))
