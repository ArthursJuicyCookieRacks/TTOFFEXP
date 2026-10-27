from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals
from toontown.dna.DNASpawnerAI import *
from toontown.dna.DNAProp import DNAProp

class DistributedPartyGateAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPartyGateAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.area = None

    def setArea(self, area):
        self.area = area

    def getArea(self):
        return self.area

    def getPartyList(self, avId):
        partyManager = simbase.air.partyManager
        self.sendUpdateToAvatarId(avId, 'listAllPublicParties', [partyManager.getPublicParties()])

    def partyChoiceRequest(self, avId, shardId, zoneId):
        # A toon picked a public party from the gate's list.
        avId = self.air.getAvatarIdFromSender()
        partyManager = self.air.partyManager
        party = partyManager.getPartyInZone(zoneId)
        if not party or party.isPrivate() or party.partyState or shardId != self.air.districtId:
            self.sendUpdateToAvatarId(avId, 'partyRequestDenied', [PartyGlobals.PartyGateDenialReasons.Unavailable])
            return
        if len(party.avIdsAtParty) >= PartyGlobals.MaxToonsAtAParty:
            self.sendUpdateToAvatarId(avId, 'partyRequestDenied', [PartyGlobals.PartyGateDenialReasons.Full])
            return
        self.sendUpdateToAvatarId(avId, 'setParty', [partyManager.getPublicPartyInfo(party), party.hostId])

@dnaSpawn(DNAProp, 'prop_party_gate')
def spawn(air, zone, element, match):
    if not config.ConfigVariableBool('want-parties', True).getValue():
        # Parties are disabled, don't spawn the gate!
        return
    gate = DistributedPartyGateAI(air)
    gate.setArea(zone)
    gate.generateWithRequired(zone)
