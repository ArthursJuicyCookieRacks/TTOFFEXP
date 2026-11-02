from panda3d.core import *
from .DistributedNPCToonBaseAI import *
from toontown.toonbase import TTLocalizer
from direct.task import Task
from toontown.fishing import FishGlobals
from toontown.pets import PetUtil, PetDNA, PetConstants, PetCreator, PetAccessories

class DistributedNPCPetclerkAI(DistributedNPCToonBaseAI):

    def __init__(self, air, npcId):
        DistributedNPCToonBaseAI.__init__(self, air, npcId)
        self.givesQuests = 0
        self.busy = 0

    def delete(self):
        taskMgr.remove(self.uniqueName('clearMovie'))
        self.ignoreAll()
        DistributedNPCToonBaseAI.delete(self)

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.air.doId2do:
            self.notify.warning('Avatar: %s not found' % avId)
            return
        if self.isBusy():
            self.freeAvatar(avId)
            return
        self.petSeeds = simbase.air.petMgr.getAvailablePets(3, 2)
        numGenders = len(PetDNA.PetGenders)
        self.petSeeds *= numGenders
        self.petSeeds.sort()
        self.sendUpdateToAvatarId(avId, 'setPetSeeds', [self.petSeeds])
        self.transactionType = ''
        av = self.air.doId2do[avId]
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleUnexpectedExit, extraArgs=[avId])
        flag = NPCToons.SELL_MOVIE_START
        self.d_setMovie(avId, flag)
        # The shop's clock is the toon's own (PetshopGUI), which stops while
        # a doodle is being built; a toon who leaves the game frees the
        # clerk through the exit event above.
        DistributedNPCToonBaseAI.avatarEnter(self)

    def rejectAvatar(self, avId):
        self.notify.warning('rejectAvatar: should not be called by a fisherman!')

    def d_setMovie(self, avId, flag, extraArgs = []):
        self.sendUpdate('setMovie', [flag,
         self.npcId,
         avId,
         extraArgs,
         ClockDelta.globalClockDelta.getRealNetworkTime()])

    def sendTimeoutMovie(self, task):
        self.d_setMovie(self.busy, NPCToons.SELL_MOVIE_TIMEOUT)
        self.sendClearMovie(None)
        return Task.done

    def sendClearMovie(self, task):
        self.ignore(self.air.getAvatarExitEvent(self.busy))
        taskMgr.remove(self.uniqueName('clearMovie'))
        self.busy = 0
        self.d_setMovie(0, NPCToons.SELL_MOVIE_CLEAR)
        return Task.done

    def fishSold(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetshopAI.fishSold busy with %s' % self.busy)
            self.notify.warning('somebody called fishSold that I was not busy with! avId: %s' % avId)
            return
        av = simbase.air.doId2do.get(avId)
        if av:
            trophyResult = self.air.fishManager.creditFishTank(av)
            if trophyResult:
                movieType = NPCToons.SELL_MOVIE_TROPHY
                extraArgs = [len(av.fishCollection), FishGlobals.getTotalNumFish()]
            else:
                movieType = NPCToons.SELL_MOVIE_COMPLETE
                extraArgs = []
            self.d_setMovie(avId, movieType, extraArgs)
            self.transactionType = 'fish'
        self.sendClearMovie(None)
        return

    def petAdopted(self, petNum, nameIndex):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetshopAI.petAdopted busy with %s' % self.busy)
            self.notify.warning('somebody called petAdopted that I was not busy with! avId: %s' % avId)
            return
        av = simbase.air.doId2do.get(avId)
        if av:
            from toontown.hood import ZoneUtil
            zoneId = ZoneUtil.getCanonicalSafeZoneId(self.zoneId)
            if petNum not in list(range(0, len(self.petSeeds))):
                self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetshopAI.petAdopted and no such pet!')
                self.notify.warning('somebody called petAdopted on a non-existent pet! avId: %s' % avId)
                return
            cost = PetUtil.getPetCostFromSeed(self.petSeeds[petNum], zoneId)
            if cost > av.getTotalMoney():
                self.air.writeServerEvent('suspicious', avId=avId, issue="DistributedNPCPetshopAI.petAdopted and toon doesn't have enough money!")
                self.notify.warning("somebody called petAdopted and didn't have enough money to adopt! avId: %s" % avId)
                return
            if av.petId != 0:
                simbase.air.petMgr.deleteToonsPet(avId)
            gender = petNum % len(PetDNA.PetGenders)
            if nameIndex not in list(range(0, TTLocalizer.PetNameIndexMAX)):
                self.air.writeServerEvent('suspicious', avId=avId, issue="DistributedNPCPetclerkAI.petAdopted and didn't have valid nameIndex!")
                self.notify.warning("somebody called petAdopted and didn't have valid nameIndex to adopt! avId: %s" % avId)
                return
            simbase.air.petMgr.createNewPetFromSeed(avId, self.petSeeds[petNum], nameIndex=nameIndex, gender=gender, safeZoneId=zoneId)
            self.transactionType = 'adopt'
            bankPrice = min(av.getBankMoney(), cost)
            walletPrice = cost - bankPrice
            av.b_setBankMoney(av.getBankMoney() - bankPrice)
            av.b_setMoney(av.getMoney() - walletPrice)

    def __checkSender(self, method):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetclerkAI.%s busy with %s' % (method, self.busy))
            self.notify.warning('somebody called %s that I was not busy with! avId: %s' % (method, avId))
            return None
        return simbase.air.doId2do.get(avId)

    def __reject(self, av, method, issue):
        self.air.writeServerEvent('suspicious', avId=av.doId, issue='DistributedNPCPetclerkAI.%s %s' % (method, issue))
        self.notify.warning('%s: %s, avId: %s' % (method, issue, av.doId))

    def petBuilt(self, dna, traitLevels, name, accessories):
        # The toon built its own doodle in the pet shop (PetCreator); it
        # costs what a daily doodle with that body and those traits costs.
        av = self.__checkSender('petBuilt')
        if not av:
            return
        from toontown.hood import ZoneUtil
        zoneId = ZoneUtil.getCanonicalSafeZoneId(self.zoneId)
        dna = list(dna)
        traitLevels = list(traitLevels)
        accessories = list(accessories)
        name = PetCreator.cleanName(name)
        if not PetCreator.isValidDNA(dna, zoneId):
            self.__reject(av, 'petBuilt', 'doodle look not sold here: %s' % dna)
            return
        if not PetCreator.isValidTraitLevels(traitLevels, zoneId):
            self.__reject(av, 'petBuilt', 'trait levels not sold here: %s' % traitLevels)
            return
        if not PetCreator.isValidName(name):
            self.__reject(av, 'petBuilt', 'bad name: %r' % name)
            return
        if not PetCreator.isValidAccessories(accessories):
            self.__reject(av, 'petBuilt', 'bad accessories: %s' % accessories)
            return
        cost = PetCreator.getCost(dna[PetDNA.Fields['body']], traitLevels, zoneId)
        cost += PetAccessories.getCost(accessories)
        if cost > av.getTotalMoney():
            self.__reject(av, 'petBuilt', "doesn't have enough money")
            return
        if av.petId != 0:
            simbase.air.petMgr.deleteToonsPet(av.doId)
        simbase.air.petMgr.createBuiltPet(av.doId, dna, traitLevels, name, accessories, zoneId)
        self.transactionType = 'adopt'
        self.__charge(av, cost)

    def __charge(self, av, cost):
        bankPrice = min(av.getBankMoney(), cost)
        walletPrice = cost - bankPrice
        av.b_setBankMoney(av.getBankMoney() - bankPrice)
        av.b_setMoney(av.getMoney() - walletPrice)

    def petRestyled(self, name, accessories):
        # A new name and accessories for the toon's doodle. The name is
        # free; each accessory it doesn't already wear costs its price.
        av = self.__checkSender('petRestyled')
        if not av:
            return
        name = PetCreator.cleanName(name)
        accessories = list(accessories)
        if not av.getPetId():
            self.__reject(av, 'petRestyled', 'has no doodle')
            return
        if not PetCreator.isValidName(name):
            self.__reject(av, 'petRestyled', 'bad name: %r' % name)
            return
        if not PetCreator.isValidAccessories(accessories):
            self.__reject(av, 'petRestyled', 'bad accessories: %s' % accessories)
            return
        self.transactionType = 'restyle'
        petId = av.getPetId()
        pet = self.air.doId2do.get(petId)
        if pet is not None and hasattr(pet, 'getAccessories'):
            self.__restyle(av.doId, name, accessories, list(pet.getAccessories()))
            return

        def gotPet(dclass, fields):
            wearing = None
            if fields and fields.get('setAccessories'):
                wearing = list(fields['setAccessories'][0])
            self.__restyle(av.doId, name, accessories, wearing)

        self.air.dbInterface.queryObject(self.air.dbId, petId, gotPet)

    def __restyle(self, avId, name, accessories, wearing):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        if not wearing or not PetCreator.isValidAccessories(wearing):
            wearing = None
        cost = PetAccessories.getCost(accessories, wearing)
        if cost > av.getTotalMoney():
            self.__reject(av, 'petRestyled', "doesn't have enough money")
            return
        simbase.air.petMgr.restylePet(avId, name, accessories)
        self.__charge(av, cost)

    def petReturned(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetshopAI.petReturned busy with %s' % self.busy)
            self.notify.warning('somebody called petReturned that I was not busy with! avId: %s' % avId)
            return
        av = simbase.air.doId2do.get(avId)
        if av:
            simbase.air.petMgr.deleteToonsPet(avId)
            self.transactionType = 'return'

    def transactionDone(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='DistributedNPCPetshopAI.transactionDone busy with %s' % self.busy)
            self.notify.warning('somebody called transactionDone that I was not busy with! avId: %s' % avId)
            return
        av = simbase.air.doId2do.get(avId)
        if av:
            if self.transactionType == 'adopt':
                self.d_setMovie(avId, NPCToons.SELL_MOVIE_PETADOPTED)
            elif self.transactionType == 'return':
                self.d_setMovie(avId, NPCToons.SELL_MOVIE_PETRETURNED)
            elif self.transactionType == 'restyle':
                self.d_setMovie(avId, NPCToons.SELL_MOVIE_PETRESTYLED)
            elif self.transactionType == '':
                self.d_setMovie(avId, NPCToons.SELL_MOVIE_PETCANCELED)
        self.sendClearMovie(None)
        return

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar:' + str(avId) + ' has exited unexpectedly')
        self.notify.warning('not busy with avId: %s, busy: %s ' % (avId, self.busy))
        taskMgr.remove(self.uniqueName('clearMovie'))
        self.sendClearMovie(None)
        return
