import random
import time

from direct.directnotify import DirectNotifyGlobal
from toontown.pets import PetCreator, PetDNA, PetMood, PetNameGenerator, PetTraits, PetTricks, PetUtil
from toontown.toonbase import ToontownGlobals


class PetManagerAI:
    # Keeps the pet shop's daily pets and creates and deletes the pets that
    # toons adopt. A pet lives in the database; it is spawned in its owner's
    # estate while the estate is loaded (see EstateManagerAI).
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    def __init__(self, air):
        self.air = air

    def getAvailablePets(self, numDaysPetAvailable, numPetsPerDay):
        # Each pet stays in the shop for numDaysPetAvailable days, and
        # numPetsPerDay new ones arrive each day; every pet shop offers the
        # same seeds on the same day.
        today = int(time.time() // 86400)
        seeds = []
        state = random.getstate()
        for day in range(today - numDaysPetAvailable + 1, today + 1):
            random.seed(day)
            for i in range(numPetsPerDay):
                seeds.append(random.randrange(0xFFFF))
        random.setstate(state)
        return seeds

    def createNewPetFromSeed(self, avId, seed, nameIndex, gender, safeZoneId):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        name = PetNameGenerator.PetNameGenerator().getName(nameIndex)
        _, dna, traitSeed = PetUtil.getPetInfoFromSeed(seed, safeZoneId)
        dna = list(dna)
        PetDNA.setGender(dna, gender)
        head, ears, nose, tail, body, color, colorScale, eyes, gender = dna
        traits = PetTraits.PetTraits(traitSeed, safeZoneId)
        fields = {
            'setOwnerId': [avId],
            'setPetName': [name],
            'setTraitSeed': [traitSeed],
            'setSafeZone': [safeZoneId],
            'setHead': [head],
            'setEars': [ears],
            'setNose': [nose],
            'setTail': [tail],
            'setBodyTexture': [body],
            'setColor': [color],
            'setColorScale': [colorScale],
            'setEyeColor': [eyes],
            'setGender': [gender],
            'setLastSeenTimestamp': [int(time.time())],
            'setTrickAptitudes': [[]],
            'setAccessories': [[0, 0, 0, 0, 0, 0]],
        }
        for traitName in PetTraits.getTraitNames():
            setter = 'set' + traitName[0].upper() + traitName[1:]
            fields[setter] = [traits.getTraitValue(traitName)]
        self._createPet(avId, name, fields)

    def createBuiltPet(self, avId, dna, traitLevels, name, accessories, safeZoneId):
        # A doodle the toon built in the pet shop (PetCreator): its own look,
        # trait levels, name and accessories.
        head, ears, nose, tail, body, color, colorScale, eyes, gender = dna
        traitValues = PetCreator.getTraitValues(traitLevels, safeZoneId)
        fields = {
            'setOwnerId': [avId],
            'setPetName': [name],
            'setTraitSeed': [random.randrange(1, 0x7FFFFFFF)],
            'setSafeZone': [safeZoneId],
            'setHead': [head],
            'setEars': [ears],
            'setNose': [nose],
            'setTail': [tail],
            'setBodyTexture': [body],
            'setColor': [color],
            'setColorScale': [colorScale],
            'setEyeColor': [eyes],
            'setGender': [gender],
            'setLastSeenTimestamp': [int(time.time())],
            'setTrickAptitudes': [[]],
            'setAccessories': [list(accessories)],
        }
        for traitName, value in zip(PetTraits.getTraitNames(), traitValues):
            setter = 'set' + traitName[0].upper() + traitName[1:]
            fields[setter] = [value]
        self._createPet(avId, name, fields)

    def restylePet(self, avId, name, accessories):
        # Renames a toon's doodle and changes what it wears, whether it is
        # out in the estate right now or only in the database.
        av = self.air.doId2do.get(avId)
        if av is None or not av.getPetId():
            return
        petId = av.getPetId()
        pet = self.air.doId2do.get(petId)
        if pet is not None and hasattr(pet, 'b_setAccessories'):
            pet.b_setPetName(name)
            pet.b_setAccessories(list(accessories))
        else:
            self.air.dbInterface.updateObject(self.air.dbId, petId, self.air.dclassesByName['DistributedPetAI'],
                                              {'setPetName': [name], 'setAccessories': [list(accessories)]})

    def maxPet(self, avId):
        # ~maxDoodle: the toon learns every trick phrase, and its doodle
        # knows every trick perfectly, has the best trait a doodle can have
        # in every trait, and is in a calm, contented mood. Works whether
        # the doodle is out on the estate or only in the database.
        av = self.air.doId2do.get(avId)
        if av is None or not av.getPetId():
            return False
        tricks = [trickId for trickId in PetTricks.Tricks if trickId != PetTricks.Tricks.BALK]
        av.b_setPetTrickPhrases(sorted(set(list(av.getPetTrickPhrases()) + tricks)))
        aptitudes = [1.0] * len(tricks)
        traits = getBestTraitValues()
        petId = av.getPetId()
        pet = self.air.doId2do.get(petId)
        if pet is not None and hasattr(pet, 'b_setTrickAptitudes'):
            pet.b_setTrickAptitudes(aptitudes)
            for traitName, value in zip(PetTraits.getTraitNames(), traits):
                getattr(pet, pet.getSetterName(traitName, 'b_set'))(value)
            pet.traits = PetTraits.PetTraits(pet.traitSeed, pet.safeZone, traitValueList=pet.traitList)
            if getattr(pet, 'mood', None) is not None:
                for component in PetMood.PetMood.Components:
                    pet.mood.setComponent(component, 0.0)
        else:
            fields = {'setTrickAptitudes': [aptitudes]}
            for traitName, value in zip(PetTraits.getTraitNames(), traits):
                fields['set' + traitName[0].upper() + traitName[1:]] = [value]
            for component in PetMood.PetMood.Components:
                fields['set' + component[0].upper() + component[1:]] = [0.0]
            # Its calm mood is as of now, not of when it was last out (a
            # doodle's mood drifts by the time it has been away).
            fields['setLastSeenTimestamp'] = [int(time.time())]
            self.air.dbInterface.updateObject(self.air.dbId, petId, self.air.dclassesByName['DistributedPetAI'], fields)
        return True

    def _createPet(self, avId, name, fields):
        def created(doId):
            if not doId:
                self.notify.warning('could not create a pet for %d' % avId)
                return
            self.notify.info('toon %d adopted pet %d (%s)' % (avId, doId, name))
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                toon.b_setPetId(doId)
            else:
                self.air.dbInterface.updateObject(self.air.dbId, avId, self.air.dclassesByName['DistributedToonAI'],
                                                  {'setPetId': [doId]})

        self.air.dbInterface.createObject(self.air.dbId, self.air.dclassesByName['DistributedPetAI'], fields, created)

    def deleteToonsPet(self, avId):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        petId = av.getPetId()
        pet = self.air.doId2do.get(petId)
        if pet is not None:
            pet.requestDelete()
        # The pet's database record is left behind, as Astron's database
        # has no delete; nothing refers to it once the toon forgets it.
        av.b_setPetId(0)


def getBestTraitValues():
    # The best value a doodle can have in each trait: the best end of
    # Donald's Dreamland's range (highest for a trait that is better high,
    # lowest for one better low), as one of its doodles could have.
    values = []
    for traitName, distrib, hasWorth in PetTraits.PetTraits.TraitDescs:
        lo, hi = distrib.getMinMax(ToontownGlobals.DonaldsDreamland)
        if distrib.TraitType == PetTraits.TraitDistribution.TraitTypes.INCREASING:
            value = hi
        else:
            value = lo
        # Never 0: a doodle with a 0 trait gets it rolled again.
        values.append(max(int(round(value * PetTraits.TraitDivisor)), 1) / float(PetTraits.TraitDivisor))
    return values
