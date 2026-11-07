"""
The rules for a doodle built in the pet shop, shared by the shop screen and
the pet clerk on the AI.

A built doodle's traits are exactly what that playground's daily doodles
could have, as before: each trait only comes in the levels (from "Always
Forgets" to "Rarely Forgets") that its daily doodles could reach there
(PetTraits.Sz2MinMax), at a value they could have. Each playground's traits
are a level of their own, Toontown Central's level 1 up to Donald's
Dreamland's level 6, since the better the playground, the better its
doodles' traits.

A built doodle's body costs what it always did there: the bottom of the
playground's price range (PetConstants.ZoneToCostRange) up to BodyShare of
it, by rarity as in PetUtil.getPetCostFromSeed. Each better choice of a
trait adds jellybeans on top. The shop's daily doodles never came with every
trait at its best, and a built one can, so in every playground the rarest
body with every best trait costs BestPriceRate times the top of the old
range: 6,000 in Donald's Dreamland (whose range topped out at 5,000), 600 in
Toontown Central, and so on.
"""

from toontown.pets import PetConstants, PetDNA, PetTraits
from toontown.pets import PetAccessories

TraitQuality = PetTraits.TraitDistribution.TraitQuality

MaxNameLength = 16
NameCharacters = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '-.&")

Levels = (TraitQuality.VERY_BAD, TraitQuality.BAD, TraitQuality.AVERAGE,
          TraitQuality.GOOD, TraitQuality.VERY_GOOD)
# How much of a playground's price range the rarest body takes; this keeps
# every body at the price it had.
BodyShare = 0.6
# The rarest body with every trait at its best costs this times the top of
# the playground's old price range (Arthur: 6,000 in Donald's Dreamland).
BestPriceRate = 1.2


def getZones():
    # The playgrounds with a pet shop, cheapest first.
    return sorted(PetConstants.ZoneToCostRange.keys(), key=lambda zoneId: PetConstants.ZoneToCostRange[zoneId])


def getBodies(zoneId):
    # The body types sold in this playground, cheapest (most common) first.
    names = list(PetDNA.PetRarities['body'][zoneId].keys())
    bodies = [PetDNA.BodyTypes.index(name) for name in names]
    bodies.sort(key=lambda body: -PetDNA.getBodyRarity(body))
    return bodies


def getColors(body):
    # The colors a daily doodle with this body can have: the pet shop has
    # always picked a doodle's color as a place in its body's color list and
    # shown that place in AllPetColors (Pet.setDNA), so these are the first
    # colors of AllPetColors.
    return list(range(len(PetDNA.getColors(body))))


def getShopLevel(zoneId):
    # This playground's trait level: 1 for Toontown Central up to 6.
    return getZones().index(zoneId) + 1


def _band(distrib, level):
    # The trait values (in the global range) that count as this level.
    gMin, gMax = distrib.getGlobalMinMax()
    cutoffs = distrib.TraitCutoffs[distrib.TraitType]
    if distrib.getHigherIsBetter():
        edges = {TraitQuality.VERY_BAD: (0.0, cutoffs[TraitQuality.VERY_BAD]),
                 TraitQuality.BAD: (cutoffs[TraitQuality.VERY_BAD], cutoffs[TraitQuality.BAD]),
                 TraitQuality.AVERAGE: (cutoffs[TraitQuality.BAD], cutoffs[TraitQuality.GOOD]),
                 TraitQuality.GOOD: (cutoffs[TraitQuality.GOOD], cutoffs[TraitQuality.VERY_GOOD]),
                 TraitQuality.VERY_GOOD: (cutoffs[TraitQuality.VERY_GOOD], 1.0)}
    else:
        edges = {TraitQuality.VERY_GOOD: (0.0, cutoffs[TraitQuality.VERY_GOOD]),
                 TraitQuality.GOOD: (cutoffs[TraitQuality.VERY_GOOD], cutoffs[TraitQuality.GOOD]),
                 TraitQuality.AVERAGE: (cutoffs[TraitQuality.GOOD], cutoffs[TraitQuality.BAD]),
                 TraitQuality.BAD: (cutoffs[TraitQuality.BAD], cutoffs[TraitQuality.VERY_BAD]),
                 TraitQuality.VERY_BAD: (cutoffs[TraitQuality.VERY_BAD], 1.0)}
    lo, hi = edges[level]
    return (gMin + lo * (gMax - gMin), gMin + hi * (gMax - gMin))


_levelValues = {}


def getTraitLevels(traitIndex, zoneId):
    # {level: value} for the levels of this trait sold in this playground.
    # A level's value is the middle of the part of that level the
    # playground's doodles can have, so it is a value a daily doodle there
    # could have too.
    key = (traitIndex, zoneId)
    if key not in _levelValues:
        name, distrib, hasWorth = PetTraits.PetTraits.TraitDescs[traitIndex]
        zMin, zMax = distrib.getMinMax(zoneId)
        levels = {}
        for level in Levels:
            lo, hi = _band(distrib, level)
            lo = max(lo, zMin)
            hi = min(hi, zMax)
            if hi - lo < 0.001:
                continue
            value = (lo + hi) / 2.0
            value = max(int(value * PetTraits.TraitDivisor), 1) / float(PetTraits.TraitDivisor)
            if distrib.getQuality(value) != level:
                continue
            levels[level] = value
        _levelValues[key] = levels
    return _levelValues[key]


def getDefaultLevel(traitIndex, zoneId):
    # The level of a typical doodle from this playground: the one at the
    # middle of its range.
    name, distrib, hasWorth = PetTraits.PetTraits.TraitDescs[traitIndex]
    zMin, zMax = distrib.getMinMax(zoneId)
    level = distrib.getQuality((zMin + zMax) / 2.0)
    levels = getTraitLevels(traitIndex, zoneId)
    if level not in levels:
        level = sorted(levels.keys())[len(levels) // 2]
    return level


def getDefaultLevels(zoneId):
    return [getDefaultLevel(i, zoneId) for i in range(PetTraits.PetTraits.NumTraits)]


def getTraitValues(traitLevels, zoneId):
    values = []
    for i, level in enumerate(traitLevels):
        values.append(getTraitLevels(i, zoneId)[level])
    return values


def getTraitDescription(traitIndex, level):
    from toontown.toonbase import TTLocalizer
    name = PetTraits.PetTraits.TraitDescs[traitIndex][0]
    if level == TraitQuality.AVERAGE:
        return TTLocalizer.PetCreatorTraitAverage[name]
    index = {TraitQuality.VERY_BAD: 0, TraitQuality.BAD: 1,
             TraitQuality.GOOD: 2, TraitQuality.VERY_GOOD: 3}[level]
    return TTLocalizer.PetTrait2descriptions[name][index]


def getBodyCost(body, zoneId):
    # The body on its own, with the lowest trait levels the playground
    # sells: the rarer the body, the dearer, as PetUtil.getPetCostFromSeed.
    rarity = pow(0.001, PetDNA.getBodyRarity(body)) - 0.001
    minCost, maxCost = PetConstants.ZoneToCostRange[zoneId]
    return int(minCost + rarity * BodyShare * (maxCost - minCost))


def getTraitsCost(zoneId):
    # What every trait at its best adds: enough to bring the rarest body up
    # to BestPriceRate times the top of the playground's old price range.
    minCost, maxCost = PetConstants.ZoneToCostRange[zoneId]
    rarest = max(getBodyCost(body, zoneId) for body in getBodies(zoneId))
    return int(round(BestPriceRate * maxCost)) - rarest


def getTraitCost(traitIndex, level, zoneId):
    # What this trait's level adds to the body's cost: nothing for the worst
    # one sold here, its share of getTraitsCost for the best (the shares add
    # up to it exactly), and evenly between.
    levels = sorted(getTraitLevels(traitIndex, zoneId).keys())
    if len(levels) < 2:
        return 0
    total = getTraitsCost(zoneId)
    numTraits = PetTraits.PetTraits.NumTraits
    best = total * (traitIndex + 1) // numTraits - total * traitIndex // numTraits
    return int(best * levels.index(level) // (len(levels) - 1))


def getCost(body, traitLevels, zoneId):
    cost = getBodyCost(body, zoneId)
    for i, level in enumerate(traitLevels):
        cost += getTraitCost(i, level, zoneId)
    return cost


def cleanName(name):
    name = ' '.join(name.split())
    return name


def isValidName(name):
    name = cleanName(name)
    if not name or len(name) > MaxNameLength:
        return False
    if not any(c.isalpha() for c in name):
        return False
    return all(c in NameCharacters for c in name)


def isValidDNA(dna, zoneId):
    if len(dna) != PetDNA.NumFields:
        return False
    head, ears, nose, tail, body, color, colorScale, eyes, gender = dna
    if body not in getBodies(zoneId):
        return False
    if color not in getColors(body):
        return False
    return (-1 <= head < len(PetDNA.HeadParts) and -1 <= ears < len(PetDNA.EarParts) and
            -1 <= nose < len(PetDNA.NoseParts) and -1 <= tail < len(PetDNA.TailParts) and
            0 <= colorScale < len(PetDNA.ColorScales) and 0 <= eyes < len(PetDNA.PetEyeColors) and
            gender in PetDNA.PetGenders)


def isValidTraitLevels(traitLevels, zoneId):
    if len(traitLevels) != PetTraits.PetTraits.NumTraits:
        return False
    for i, level in enumerate(traitLevels):
        if level not in getTraitLevels(i, zoneId):
            return False
    return True


def isValidAccessories(accessories):
    return PetAccessories.isValid(list(accessories))
