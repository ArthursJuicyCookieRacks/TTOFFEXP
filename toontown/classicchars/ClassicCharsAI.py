"""Spawns the playground's classic character (Mickey, Minnie, Pluto...).

The AI brains in this package come from open-toontown. Each playground has
one character, except Acorn Acres, which has Chip with Dale orbiting him.
The Cog HQs have none. Hoods call spawn() from their createZone().

Over Halloween the costume versions come out instead (Vampire Mickey, Witch
Minnie, Franken Donald, Western Pluto, Super Goofy, Police Chip, Jailbird
Dale and Sock Hop Daisy), and over April Fools the characters swap
playgrounds and walk each other's paths, as they did in the real game. When
one of those holidays starts or ends the current character fades away and
the right one takes over.
"""

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from toontown.toonbase import ToontownGlobals

notify = DirectNotifyGlobal.directNotify.newCategory('ClassicCharsAI')

COSTUME_HOLIDAYS = (ToontownGlobals.HALLOWEEN_COSTUMES, ToontownGlobals.SPOOKY_COSTUMES)
SWAP_HOLIDAYS = (ToontownGlobals.APRIL_FOOLS_COSTUMES,)
# How long the old character takes to fade before it is removed.
FADE_TIME = 1.0


def spawn(air, hoodId):
    """Starts looking after the hood's character(s); returns the keeper."""
    if not air.config.ConfigVariableBool('want-classic-chars', True).getValue():
        return None
    return HoodChars(air, hoodId)


class HoodChars(DirectObject):

    def __init__(self, air, hoodId):
        self.air = air
        self.hoodId = hoodId
        self.chars = []
        self.look = None
        self.create()
        self.accept('holidayStarted', self.holidayChanged)
        self.accept('holidayEnded', self.holidayChanged)

    def currentLook(self):
        holidays = getattr(getattr(self.air, 'holidayManager', None), 'currentHolidays', ())
        if any(h in holidays for h in COSTUME_HOLIDAYS):
            return 'costume'
        if any(h in holidays for h in SWAP_HOLIDAYS):
            return 'swap'
        return 'normal'

    def holidayChanged(self, holidayId):
        if holidayId in COSTUME_HOLIDAYS or holidayId in SWAP_HOLIDAYS:
            if self.currentLook() != self.look:
                self.fadeOut()
                self.create()

    def fadeOut(self):
        old = self.chars
        self.chars = []
        for char in old:
            char.fadeAway()
        taskMgr.doMethodLater(FADE_TIME, self.remove, 'classicCharsFade-%d' % self.hoodId, extraArgs=[old])

    def remove(self, chars):
        for char in chars:
            if not char.isDeleted():
                char.requestDelete()

    def create(self):
        self.look = self.currentLook()
        hoodId = self.hoodId
        makers = LOOKS[self.look].get(hoodId)
        if makers is None:
            return
        if hoodId == ToontownGlobals.OutdoorZone:
            chipClass, daleClass = makers
            chip = chipClass(self.air)
            chip.generateWithRequired(hoodId)
            dale = daleClass(self.air, chip.doId)
            dale.generateWithRequired(hoodId)
            chip.setDaleId(dale.doId)
            chip.start()
            dale.start()
            self.chars = [chip, dale]
        else:
            char = makers(self.air)
            char.generateWithRequired(hoodId)
            char.start()
            self.chars = [char]
        notify.info('%s out in %s (%s)' % (', '.join(c.getName() for c in self.chars), hoodId, self.look))


from .DistributedMickeyAI import DistributedMickeyAI
from .DistributedMinnieAI import DistributedMinnieAI
from .DistributedPlutoAI import DistributedPlutoAI
from .DistributedDonaldAI import DistributedDonaldAI
from .DistributedDonaldDockAI import DistributedDonaldDockAI
from .DistributedDaisyAI import DistributedDaisyAI
from .DistributedGoofyAI import DistributedGoofyAI
from .DistributedGoofySpeedwayAI import DistributedGoofySpeedwayAI
from .DistributedChipAI import DistributedChipAI
from .DistributedDaleAI import DistributedDaleAI
from .DistributedVampireMickeyAI import DistributedVampireMickeyAI
from .DistributedWitchMinnieAI import DistributedWitchMinnieAI
from .DistributedWesternPlutoAI import DistributedWesternPlutoAI
from .DistributedFrankenDonaldAI import DistributedFrankenDonaldAI
from .DistributedSockHopDaisyAI import DistributedSockHopDaisyAI
from .DistributedSuperGoofyAI import DistributedSuperGoofyAI
from .DistributedPoliceChipAI import DistributedPoliceChipAI
from .DistributedJailbirdDaleAI import DistributedJailbirdDaleAI

TG = ToontownGlobals
LOOKS = {
    'normal': {
        TG.ToontownCentral: DistributedMickeyAI,
        TG.DonaldsDock: DistributedDonaldDockAI,
        TG.DaisyGardens: DistributedDaisyAI,
        TG.MinniesMelodyland: DistributedMinnieAI,
        TG.TheBrrrgh: DistributedPlutoAI,
        TG.DonaldsDreamland: DistributedDonaldAI,
        TG.GoofySpeedway: DistributedGoofySpeedwayAI,
        TG.OutdoorZone: (DistributedChipAI, DistributedDaleAI),
    },
    'costume': {
        TG.ToontownCentral: DistributedVampireMickeyAI,
        TG.DonaldsDock: DistributedDonaldDockAI,
        TG.DaisyGardens: DistributedSockHopDaisyAI,
        TG.MinniesMelodyland: DistributedWitchMinnieAI,
        TG.TheBrrrgh: DistributedWesternPlutoAI,
        TG.DonaldsDreamland: DistributedFrankenDonaldAI,
        TG.GoofySpeedway: DistributedSuperGoofyAI,
        TG.OutdoorZone: (DistributedPoliceChipAI, DistributedJailbirdDaleAI),
    },
    # April Fools: everyone turns up in a friend's playground and walks
    # the friend's path (the characters' handleHolidays set the path).
    'swap': {
        TG.ToontownCentral: DistributedDaisyAI,
        TG.DonaldsDock: DistributedDonaldDockAI,
        TG.DaisyGardens: DistributedMickeyAI,
        TG.MinniesMelodyland: DistributedPlutoAI,
        TG.TheBrrrgh: DistributedMinnieAI,
        TG.DonaldsDreamland: DistributedGoofySpeedwayAI,
        TG.GoofySpeedway: DistributedDonaldAI,
        TG.OutdoorZone: (DistributedChipAI, DistributedDaleAI),
    },
}
