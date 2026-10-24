"""Who an NPC player is: a name, a look, laff and gags that fit the place.

A toon met on the Toontown Central streets is new to the game, and one in a
boss lobby has maxed gags and laff, the way the players met there online were.
"""

import random

from toontown.hood import ZoneUtil
from toontown.makeatoon.NameGenerator import NameGenerator
from toontown.toon import ToonDNA
from toontown.toonbase import ToontownGlobals
from toontown.toonbase.ToontownBattleGlobals import (
    Levels, HEAL_TRACK, TRAP_TRACK, LURE_TRACK, SOUND_TRACK, THROW_TRACK, SQUIRT_TRACK, DROP_TRACK)

# For each place: the laff range, and the highest gag level (0 to 6) the
# toons there have.
TIERS = {
    ToontownGlobals.ToontownCentral: ((20, 35), 2),
    ToontownGlobals.DonaldsDock: ((35, 50), 3),
    ToontownGlobals.DaisyGardens: ((45, 60), 4),
    ToontownGlobals.MinniesMelodyland: ((55, 75), 4),
    ToontownGlobals.TheBrrrgh: ((70, 90), 5),
    ToontownGlobals.DonaldsDreamland: ((85, 105), 5),
    ToontownGlobals.SellbotHQ: ((90, 115), 5),
    ToontownGlobals.CashbotHQ: ((105, 125), 6),
    ToontownGlobals.LawbotHQ: ((115, 135), 6),
    ToontownGlobals.BossbotHQ: ((125, 137), 6),
}
# The boss lobbies and the facilities are where the maxed toons are.
LOBBY_TIERS = {
    ToontownGlobals.SellbotHQ: ((105, 137), 6),
    ToontownGlobals.CashbotHQ: ((115, 137), 6),
    ToontownGlobals.LawbotHQ: ((125, 137), 6),
    ToontownGlobals.BossbotHQ: ((130, 137), 6),
}
LOBBIES = (ToontownGlobals.SellbotLobby, ToontownGlobals.CashbotLobby,
           ToontownGlobals.LawbotLobby, ToontownGlobals.BossbotLobby)
COG_HQS = (ToontownGlobals.SellbotHQ, ToontownGlobals.CashbotHQ, ToontownGlobals.LawbotHQ, ToontownGlobals.BossbotHQ)
# Places every kind of toon visits.
MIXED_TIER = ((25, 137), 6)

# Online, nearly everyone with a choice took these.
CORE_TRACKS = (HEAL_TRACK, LURE_TRACK, THROW_TRACK, SQUIRT_TRACK)
EXTRA_TRACKS = (TRAP_TRACK, SOUND_TRACK, DROP_TRACK)

_nameGenerator = None


def getTier(zoneId, player=None):
    hoodId = ZoneUtil.getHoodId(zoneId)
    canonical = ZoneUtil.getCanonicalZoneId(zoneId)
    if canonical in LOBBIES or zoneId >= ToontownGlobals.DynamicZonesBegin and hoodId in LOBBY_TIERS:
        tier = LOBBY_TIERS[hoodId]
    elif hoodId in TIERS:
        tier = TIERS[hoodId]
    else:
        tier = MIXED_TIER
    if player is not None:
        # Nobody tags along with a toon much stronger than themselves.
        (low, high), level = tier
        low = max(low, min(player.getMaxHp() - 10, 137))
        high = max(high, low)
        tier = ((low, high), max(level, highestGagLevel(player)))
    return tier


def highestGagLevel(toon):
    best = 0
    for track in range(len(Levels)):
        if toon.hasTrackAccess(track):
            exp = toon.experience.getExp(track)
            for level in range(len(Levels[track])):
                if exp >= Levels[track][level]:
                    best = max(best, level)
    return best


def randomName(gender):
    global _nameGenerator
    if _nameGenerator is None:
        _nameGenerator = NameGenerator()
    if gender == 'm':
        return _nameGenerator.randomName(boy=1)
    return _nameGenerator.randomName(girl=1)


def makeProfile(zoneId, player=None):
    (laffLow, laffHigh), gagLevel = getTier(zoneId, player)
    gender = random.choice(('m', 'f'))
    dna = ToonDNA.ToonDNA()
    dna.newToonRandom(gender=gender)
    maxHp = random.randint(laffLow, laffHigh)

    tracks = list(CORE_TRACKS)
    numExtra = 2 if gagLevel >= 3 else 1
    tracks += random.sample(EXTRA_TRACKS, numExtra)

    trackAccess = [0] * len(Levels)
    experience = [0] * len(Levels)
    for track in tracks:
        trackAccess[track] = 1
        # Most toons are part way into their top level.
        level = gagLevel if random.random() < 0.7 else max(gagLevel - 1, 0)
        top = Levels[track][level]
        nextLevel = Levels[track][level + 1] if level + 1 < len(Levels[track]) else top + 1
        experience[track] = random.randint(top, max(top, nextLevel - 1))

    profile = {'name': randomName(gender),
            'dna': dna,
            'maxHp': maxHp,
            'trackAccess': trackAccess,
            'experience': experience,
            'maxCarry': 20 + 10 * (gagLevel + 1) if gagLevel < 6 else 80}
    if ZoneUtil.getHoodId(zoneId) in COG_HQS:
        # Toons at Cog HQ have their cog suits, and those in the lobbies are
        # ready to see the boss.
        profile['cogSuits'] = True
    return profile
