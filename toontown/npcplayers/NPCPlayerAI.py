"""A toon that the district plays itself, standing in for another player.

To everyone else it is an ordinary DistributedToon: it has a name, a look,
laff and gags, walks around, and joins battles and boss fights. Nothing of it
is saved; the NPCPlayerManagerAI makes these toons where the real player is
and throws them away when the player leaves.

The toon's actions reach the district's objects the way a client's messages
do (see asSender), so the battle, elevator and boss code treat it like any
other toon.
"""

import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from panda3d.core import Datagram, DatagramIterator

from otp.otpbase import OTPGlobals
from toontown.toon import Experience
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import ToontownGlobals


class NPCPlayerAI(DistributedToonAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCPlayerAI')

    def __init__(self, air, manager):
        # The objects of this class are DistributedToons on the wire.
        air.dclassesByName.setdefault('NPCPlayerAI', air.dclassesByName['DistributedToonAI'])
        DistributedToonAI.__init__(self, air)
        self.manager = manager
        self.brain = None
        # Some setters log the doId, so the toon has it before the defaults.
        self.doId = air.allocateChannel()
        self.applyFieldDefaults()
        self.gameAccess = OTPGlobals.AccessFull

    def applyProfile(self, profile):
        # Before generate, so the toon arrives on the clients as it is.
        self.setName(profile['name'])
        self.setDNAString(profile['dna'].makeNetString())
        self.setMaxHp(profile['maxHp'])
        self.setHp(profile['maxHp'])
        self.setTrackAccess(profile['trackAccess'])
        experience = Experience.Experience(owner=self)
        experience.experience = list(profile['experience'])
        self.setExperience(experience.makeNetString())
        self.setMaxCarry(profile['maxCarry'])
        self.inventory.zeroInv()
        self.inventory.maxOutInv()

    def restock(self):
        # NPC players never run out of gags.
        self.inventory.zeroInv()
        self.inventory.maxOutInv()
        self.d_setInventory(self.inventory.makeNetString())

    def generateInZone(self, zoneId, x=0, y=0, z=0, h=0):
        self.setPosHpr(x, y, z, h, 0, 0)
        self.generateWithRequiredAndId(self.doId, self.air.districtId, zoneId)
        # What a player's own client would send once it is in the zone; these
        # are kept for toons who arrive later.
        self.sendUpdate('setParent', [ToontownGlobals.SPRender])
        self.placeAt(x, y, z, h)
        self.b_setAnimState('neutral', 1.0)

    def isPlayerControlled(self):
        return False

    def isNPCPlayer(self):
        return True

    def applyFieldDefaults(self):
        # Every required field starts at its default from the dc file, the
        # way a new toon in the database would.
        for i in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(i)
            if not field.isRequired() or field.asMolecularField():
                continue
            if field.getName() == 'setDNAString':
                # Has no usable default; applyProfile sets it.
                continue
            default = field.getDefaultValue()
            dg = Datagram()
            dg.addUint16(field.getNumber())
            dg.appendData(default)
            try:
                self.dclass.receiveUpdate(self, DatagramIterator(dg))
            except Exception as e:
                self.notify.warning('default for %s: %s' % (field.getName(), e))

    # Getters the district never needed, since only the database used to
    # send a toon's required fields; they return what the field holds.

    def getKartAccessoriesOwned(self):
        return list(self.accessories)

    # --- Acting like a client ---

    def asSender(self, func, *args):
        """Calls func as though this toon's client had sent it."""
        return self.air.callAsSender(self.doId, func, *args)

    # --- Moving ---

    def placeAt(self, x, y, z, h):
        # A jump to a spot, remembered for toons who arrive later.
        self.setPosHpr(x, y, z, h, 0, 0)
        self.sendUpdate('setPosHpr', [x, y, z, h, 0, 0])

    def moveTo(self, x, y, z, h):
        self.setPosHpr(x, y, z, h, 0, 0)
        self.sendUpdate('setSmPosHpr', [x, y, z, h, 0, 0, globalClockDelta.getRealNetworkTime(bits=16)])

    def stopMoving(self):
        self.sendUpdate('setSmStop', [globalClockDelta.getRealNetworkTime(bits=16)])

    def delete(self):
        if self.brain is not None:
            self.brain.destroy()
            self.brain = None
        DistributedToonAI.delete(self)
