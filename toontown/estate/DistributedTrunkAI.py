from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.estate.DistributedClosetAI import DistributedClosetAI
from toontown.toon import ToonDNA
from . import ClosetGlobals

# The accessory kinds, with the toon's getters and setters for what it wears
# and what its trunk holds.
ACCESSORIES = (
    (ToonDNA.HAT, 'Hat', 'HatList'),
    (ToonDNA.GLASSES, 'Glasses', 'GlassesList'),
    (ToonDNA.BACKPACK, 'Backpack', 'BackpackList'),
    (ToonDNA.SHOES, 'Shoes', 'ShoesList'),
)


class DistributedTrunkAI(DistributedClosetAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedTrunkAI")

    def __init__(self, air, furnitureMgr, itemType):
        DistributedClosetAI.__init__(self, air, furnitureMgr, itemType)
        self.lists = {kind: [] for kind, _, _ in ACCESSORIES}
        self.customerAccessories = None
        self.removedItems = []

    def generate(self):
        owner = self.air.doId2do.get(self.furnitureMgr.ownerId)
        if owner:
            self.__readOwner(owner)
        elif self.furnitureMgr.ownerId:
            self.air.dbInterface.queryObject(self.air.dbId, self.furnitureMgr.ownerId, self.__gotOwner)

    def __readOwner(self, owner):
        for kind, _, listName in ACCESSORIES:
            self.lists[kind] = list(getattr(owner, 'get' + listName)())
        self.gender = owner.dna.gender

    def __gotOwner(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedToonAI']:
            self.notify.warning('Got object of wrong type!')
            return
        for kind, _, listName in ACCESSORIES:
            self.lists[kind] = list(fields.get('set' + listName, [[]])[0])
        self.gender = ToonDNA.ToonDNA(fields['setDNAString'][0]).gender

    def d_setState(self, mode, avId, ownerId, gender, *lists):
        self.sendUpdate('setState', [mode, avId, ownerId, gender] + [self.lists[kind] for kind, _, _ in ACCESSORIES])

    def __sendState(self, mode, avId):
        self.d_setState(mode, avId, self.furnitureMgr.ownerId, self.gender)

    def __getAvatar(self, issue):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='%s while not using the trunk!' % issue)
            return None
        av = self.air.doId2do.get(avId)
        if not av or av.getLocation() != self.getLocation():
            self.air.writeServerEvent('suspicious', avId=avId, issue='%s from another zone!' % issue)
            return None
        return av

    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId:
            if self.avId == avId:
                self.air.writeServerEvent('suspicious', avId=avId, issue='Tried to use trunk twice!')
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        av = self.air.doId2do.get(avId)
        if not av or av.getLocation() != self.getLocation():
            self.air.writeServerEvent('suspicious', avId=avId, issue='Not in the same zone as the trunk!')
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        if avId == self.furnitureMgr.ownerId:
            self.__readOwner(av)
        self.avId = avId
        self.customerAccessories = {kind: tuple(getattr(av, 'get' + name)()) for kind, name, _ in ACCESSORIES}
        self.removedItems = []
        self.__sendState(ClosetGlobals.OPEN, avId)

    def removeItem(self, geomIdx, texIdx, colorIdx, which):
        av = self.__getAvatar('Tried to remove an accessory')
        if not av:
            return
        if av.doId != self.furnitureMgr.ownerId:
            self.air.writeServerEvent('suspicious', avId=av.doId, issue="Tried to remove an accessory from someone else's trunk!")
            return
        if which not in self.lists:
            self.air.writeServerEvent('suspicious', avId=av.doId, issue='Sent an invalid accessory type!')
            return
        self.removedItems.append((which, geomIdx, texIdx, colorIdx))

    def setDNA(self, hatIdx, hatTexture, hatColor, glassesIdx, glassesTexture, glassesColor,
               backpackIdx, backpackTexture, backpackColor, shoesIdx, shoesTexture, shoesColor, finished, which):
        av = self.__getAvatar('Tried to change accessories')
        if not av:
            return
        chosen = {
            ToonDNA.HAT: (hatIdx, hatTexture, hatColor),
            ToonDNA.GLASSES: (glassesIdx, glassesTexture, glassesColor),
            ToonDNA.BACKPACK: (backpackIdx, backpackTexture, backpackColor),
            ToonDNA.SHOES: (shoesIdx, shoesTexture, shoesColor),
        }
        if finished == 0:
            # A preview while the toon flips through the trunk.
            self.sendUpdate('setCustomerDNA', [av.doId, hatIdx, hatTexture, hatColor, glassesIdx, glassesTexture, glassesColor,
                                               backpackIdx, backpackTexture, backpackColor, shoesIdx, shoesTexture, shoesColor, which])
            return
        if finished == 2:
            if av.doId != self.furnitureMgr.ownerId:
                self.air.writeServerEvent('suspicious', avId=av.doId, issue="Tried to wear accessories from someone else's trunk!")
            else:
                self.__wear(av, chosen, which)
        # Done (finished 2) or cancelled (finished 1); a cancel puts back what
        # the toon wore, which the client sends.
        for kind, name, _ in ACCESSORIES:
            current = tuple(getattr(av, 'get' + name)())
            getattr(av, 'b_set' + name)(*current)
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_COMPLETE, av.doId, globalClockDelta.getRealNetworkTime())
        taskMgr.doMethodLater(1, self._DistributedClosetAI__resetMovie, 'resetMovie-%d' % self.getDoId(), extraArgs=[])
        self.avId = None
        self.customerAccessories = None
        self.removedItems = []
        self.__sendState(ClosetGlobals.CLOSED, 0)

    def __wear(self, av, chosen, which):
        # The trunk holds what the toon is not wearing (an empty slot, 0 0 0,
        # once it has worn something over nothing). Putting one on swaps it
        # with the one worn before; then the thrown-away ones go.
        for kind, name, listName in ACCESSORIES:
            if not which & kind:
                continue
            new = chosen[kind]
            old = self.customerAccessories[kind]
            if new == old:
                continue
            if not av.replaceItemInAccessoriesList(kind, new[0], new[1], new[2], old[0], old[1], old[2]):
                self.air.writeServerEvent('suspicious', avId=av.doId, issue="Tried to wear an accessory they don't own!")
                continue
            getattr(av, 'set' + name)(*new)
        for kind, geomIdx, texIdx, colorIdx in self.removedItems:
            if not av.removeItemInAccessoriesList(kind, geomIdx, texIdx, colorIdx):
                self.air.writeServerEvent('suspicious', avId=av.doId, issue="Tried to remove an accessory they don't have!")
        for kind, _, listName in ACCESSORIES:
            getattr(av, 'b_set' + listName)(getattr(av, 'get' + listName)())
        self.__readOwner(av)
