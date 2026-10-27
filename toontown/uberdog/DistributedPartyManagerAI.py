import time
from datetime import datetime, timedelta

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from otp.ai.MagicWordGlobal import *
from toontown.parties.DistributedPartyAI import DistributedPartyAI
from toontown.parties.PartyGlobals import *
from toontown.parties.ToontownTimeManager import ToontownTimeZone

PARTY_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# How often hosts who are online are told that their party can start.
CHECK_PERIOD = 60

# Fields of the party struct.
PARTY_ID, HOST_ID = 0, 1
PARTY_PRIVATE, PARTY_THEME, PARTY_ACTIVITIES, PARTY_DECORATIONS, PARTY_STATUS = 12, 13, 14, 15, 16


def now():
    # Party times are Toontown time, the clock in the party planner.
    return datetime.now(ToontownTimeZone()).replace(tzinfo=None)


def getStart(struct):
    return datetime(*struct[2:7])


def getEnd(struct):
    return datetime(*struct[7:12])


def getPartyCost(activities, decorations):
    cost = 0
    for activity in activities:
        cost += ActivityInformationDict.get(activity[0], {}).get('cost', 0)
    for decoration in decorations:
        cost += DecorationInformationDict.get(decoration[0], {}).get('cost', 0)
    return cost


class DistributedPartyManagerAI(DistributedObjectAI):
    # Plans, starts and ends parties. In the offline game this one district
    # is the whole of Toontown, so it keeps the parties itself instead of
    # asking the party UberDOG. The party a toon plans is kept in their
    # setHostedPartyRecord database field, so it waits for them across
    # restarts.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPartyManagerAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.planningZones = {}
        self.parties = {}
        self.hostToParty = {}

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.accept('avatarEntered', self.__avatarEntered)
        taskMgr.doMethodLater(CHECK_PERIOD, self.__checkParties, self.uniqueName('check-parties'))

    def delete(self):
        self.ignoreAll()
        taskMgr.remove(self.uniqueName('check-parties'))
        for partyId in list(self.parties):
            self.__deleteParty(partyId)
        DistributedObjectAI.delete(self)

    # The host's party record.

    def getRecord(self, av):
        record = av.getHostedPartyRecord()
        return record[0] if record else None

    def saveRecord(self, av, struct):
        av.b_setHostedPartyRecord([struct] if struct else [])
        self.sendHostedParties(av)

    def sendHostedParties(self, av):
        record = av.getHostedPartyRecord()
        av.setHostedParties(record)
        av.sendUpdate('setHostedParties', [record])

    def __avatarEntered(self, av):
        self.updateStatus(av)
        self.sendHostedParties(av)
        struct = self.getRecord(av)
        if struct and struct[PARTY_STATUS] == PartyStatus.CanStart:
            av.sendUpdate('setPartyCanStart', [struct[PARTY_ID]])

    def __checkParties(self, task):
        for av in list(self.air.doId2do.values()):
            if hasattr(av, 'getHostedPartyRecord') and av.isPlayerControlled():
                struct = self.getRecord(av)
                if struct and self.updateStatus(av):
                    if struct[PARTY_STATUS] == PartyStatus.CanStart:
                        av.sendUpdate('setPartyCanStart', [struct[PARTY_ID]])
        return task.again

    def updateStatus(self, av):
        # Moves the party along the clock. Returns True when it changed.
        struct = self.getRecord(av)
        if not struct:
            return False
        status = struct[PARTY_STATUS]
        current = now()
        if status == PartyStatus.Pending and getStart(struct) <= current:
            status = PartyStatus.CanStart
        if status in (PartyStatus.Pending, PartyStatus.CanStart) and getEnd(struct) <= current:
            # The party time went by without the host: the beans come back.
            status = PartyStatus.NeverStarted
            refund = getPartyCost(struct[PARTY_ACTIVITIES], struct[PARTY_DECORATIONS])
            av.addMoney(refund)
            struct[PARTY_STATUS] = status
            self.saveRecord(av, struct)
            av.sendUpdate('setNeverStartedPartyRefunded', [struct[PARTY_ID], status, refund])
            return True
        if status != struct[PARTY_STATUS]:
            struct[PARTY_STATUS] = status
            self.saveRecord(av, struct)
            return True
        return False

    # Planning.

    def canBuyParties(self):
        return True

    def getPartyZone(self, hostId, zoneId, isAvAboutToPlanParty):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not av:
            return
        if isAvAboutToPlanParty:
            # The planner opens in an empty party grounds of its own.
            if hostId != avId or not av.canPlanParty():
                self.sendUpdateToAvatarId(avId, 'receivePartyZone', [hostId, 0, 0])
                return
            zoneId = self.air.allocateZone(owner=self)
            self.planningZones[avId] = zoneId
            self.sendUpdateToAvatarId(avId, 'receivePartyZone', [hostId, self.newPartyId(), zoneId])
            return
        partyId = self.hostToParty.get(hostId)
        if partyId is None and hostId == avId:
            partyId = self.startParty(av)
        party = self.parties.get(partyId)
        if not party or (party.isPrivate() and avId != hostId and avId not in party.getInviteeIds()):
            self.sendUpdateToAvatarId(avId, 'receivePartyZone', [hostId, 0, 0])
            return
        self.sendUpdateToAvatarId(avId, 'receivePartyZone', [hostId, partyId, party.zoneId])

    def newPartyId(self):
        return int(time.time() * 1000)

    def freeZoneIdFromPlannedParty(self, hostId, zoneId):
        avId = self.air.getAvatarIdFromSender()
        if avId != hostId or self.planningZones.get(avId) != zoneId:
            return
        del self.planningZones[avId]
        self.air.deallocateZone(zoneId)

    def addPartyRequest(self, hostId, startTime, endTime, isPrivate, inviteTheme, activities, decorations, inviteeIds):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not av or hostId != avId:
            self.air.writeServerEvent('suspicious', avId=avId, issue='Toon tried to create a party as someone else!')
            return
        if not av.canPlanParty():
            self.sendUpdateToAvatarId(avId, 'addPartyResponse', [hostId, AddPartyErrorCode.TooManyHostedParties])
            return
        try:
            start = datetime.strptime(startTime, PARTY_TIME_FORMAT)
            end = datetime.strptime(endTime, PARTY_TIME_FORMAT)
        except ValueError:
            self.sendUpdateToAvatarId(avId, 'addPartyResponse', [hostId, AddPartyErrorCode.ValidationError])
            return
        if end <= start or not any(activity[0] == ActivityIds.PartyClock for activity in activities):
            self.sendUpdateToAvatarId(avId, 'addPartyResponse', [hostId, AddPartyErrorCode.ValidationError])
            return
        if not av.takeMoney(getPartyCost(activities, decorations)):
            self.sendUpdateToAvatarId(avId, 'addPartyResponse', [hostId, AddPartyErrorCode.ValidationError])
            return
        struct = [self.newPartyId(), hostId,
                  start.year, start.month, start.day, start.hour, start.minute,
                  end.year, end.month, end.day, end.hour, end.minute,
                  isPrivate, inviteTheme, activities, decorations, PartyStatus.Pending]
        self.saveRecord(av, struct)
        self.updateStatus(av)
        self.air.writeServerEvent('party-planned', avId=avId, start=startTime, end=endTime)
        self.sendUpdateToAvatarId(avId, 'addPartyResponse', [hostId, AddPartyErrorCode.AllOk])
        if self.getRecord(av)[PARTY_STATUS] == PartyStatus.CanStart:
            av.sendUpdate('setPartyCanStart', [struct[PARTY_ID]])

    def changePrivateRequest(self, partyId, newPrivateStatus):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        struct = av and self.getRecord(av)
        if not struct or struct[PARTY_ID] != partyId:
            self.sendUpdateToAvatarId(avId, 'changePrivateResponse', [partyId, newPrivateStatus, ChangePartyFieldErrorCode.ValidationError])
            return
        if struct[PARTY_STATUS] == PartyStatus.Started:
            self.sendUpdateToAvatarId(avId, 'changePrivateResponse', [partyId, newPrivateStatus, ChangePartyFieldErrorCode.AlreadyStarted])
            return
        struct[PARTY_PRIVATE] = newPrivateStatus
        self.saveRecord(av, struct)
        self.sendUpdateToAvatarId(avId, 'changePrivateResponse', [partyId, newPrivateStatus, ChangePartyFieldErrorCode.AllOk])

    def changePartyStatusRequest(self, partyId, newPartyStatus):
        # The host cancels a party that has not started, for most of the
        # beans back.
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        struct = av and self.getRecord(av)
        if not struct or struct[PARTY_ID] != partyId or newPartyStatus != PartyStatus.Cancelled:
            self.sendUpdateToAvatarId(avId, 'changePartyStatusResponse', [partyId, newPartyStatus, ChangePartyFieldErrorCode.ValidationError, 0])
            return
        status = struct[PARTY_STATUS]
        if status == PartyStatus.NeverStarted:
            self.sendUpdateToAvatarId(avId, 'changePartyStatusResponse', [partyId, status, ChangePartyFieldErrorCode.AlreadyRefunded, 0])
            return
        if status not in (PartyStatus.Pending, PartyStatus.CanStart):
            self.sendUpdateToAvatarId(avId, 'changePartyStatusResponse', [partyId, status, ChangePartyFieldErrorCode.AlreadyStarted, 0])
            return
        refund = int(getPartyCost(struct[PARTY_ACTIVITIES], struct[PARTY_DECORATIONS]) * PartyRefundPercentage)
        av.addMoney(refund)
        struct[PARTY_STATUS] = PartyStatus.Cancelled
        self.saveRecord(av, struct)
        self.sendUpdateToAvatarId(avId, 'changePartyStatusResponse', [partyId, PartyStatus.Cancelled, ChangePartyFieldErrorCode.AllOk, refund])

    # Running parties.

    def startParty(self, av):
        self.updateStatus(av)
        struct = self.getRecord(av)
        if not struct or struct[PARTY_STATUS] != PartyStatus.CanStart:
            return None
        partyId = struct[PARTY_ID]
        info = {'partyId': partyId,
                'hostId': av.doId,
                'start': getStart(struct),
                'end': getEnd(struct),
                'isPrivate': struct[PARTY_PRIVATE],
                'inviteTheme': struct[PARTY_THEME],
                'activities': struct[PARTY_ACTIVITIES],
                'decorations': struct[PARTY_DECORATIONS],
                'inviteeIds': []}
        zoneId = self.air.allocateZone(owner=self)
        party = DistributedPartyAI(self.air, av.doId, zoneId, info)
        party.generateWithRequired(zoneId)
        self.parties[partyId] = party
        self.hostToParty[av.doId] = partyId
        struct[PARTY_STATUS] = PartyStatus.Started
        self.saveRecord(av, struct)
        self.air.writeServerEvent('party-started', avId=av.doId, partyId=partyId)
        taskMgr.doMethodLater(PARTY_DURATION, self.closeParty, self.uniqueName('close-party-%d' % partyId), extraArgs=[partyId])
        return partyId

    def closeParty(self, partyId):
        party = self.parties.get(partyId)
        if not party:
            return
        for avId in party.avIdsAtParty:
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])
        party.b_setPartyState(True)
        host = self.air.doId2do.get(party.hostId)
        if host:
            struct = self.getRecord(host)
            if struct and struct[PARTY_ID] == partyId:
                struct[PARTY_STATUS] = PartyStatus.Finished
                self.saveRecord(host, struct)
        taskMgr.doMethodLater(10, lambda task: self.__deleteParty(partyId), self.uniqueName('delete-party-%d' % partyId))

    def __deleteParty(self, partyId):
        taskMgr.remove(self.uniqueName('close-party-%d' % partyId))
        taskMgr.remove(self.uniqueName('delete-party-%d' % partyId))
        party = self.parties.pop(partyId, None)
        if not party:
            return
        for avId in party.avIdsAtParty:
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 1])
        if self.hostToParty.get(party.hostId) == partyId:
            del self.hostToParty[party.hostId]
        zoneId = party.zoneId
        party.requestDelete()
        self.air.deallocateZone(zoneId)

    def getPartyInZone(self, zoneId):
        for party in self.parties.values():
            if party.zoneId == zoneId:
                return party
        return None

    def exitParty(self, partyZone):
        party = self.getPartyInZone(partyZone)
        if party:
            party._removeAvatar(self.air.getAvatarIdFromSender())

    def removeGuest(self, ownerId, avId):
        # The host sends a guest home.
        if self.air.getAvatarIdFromSender() != ownerId:
            return
        party = self.parties.get(self.hostToParty.get(ownerId))
        if party and avId in party.avIdsAtParty:
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])

    def getPublicPartyInfo(self, party):
        minLeft = max(0, int((PARTY_DURATION - (time.time() - party.startedTimestamp)) / 60))
        activityIds = [activity[0] for activity in party.info['activities']]
        return [self.air.districtId, party.zoneId, min(len(party.avIdsAtParty), 255), party.getHostName(), activityIds, minLeft]

    def getPublicParties(self):
        return [self.getPublicPartyInfo(party) for party in self.parties.values()
                if not party.isPrivate() and not party.partyState]

    def requestShardIdZoneIdForHostId(self, hostId):
        avId = self.air.getAvatarIdFromSender()
        party = self.parties.get(self.hostToParty.get(hostId))
        if not party or party.partyState:
            self.sendUpdateToAvatarId(avId, 'sendShardIdZoneIdToAvatar', [0, 0])
            return
        self.sendUpdateToAvatarId(avId, 'sendShardIdZoneIdToAvatar', [self.air.districtId, party.zoneId])

    # Messages the party UberDOG used to send. Nothing sends them offline.

    def receiveId(self, ids):
        pass

    def partyManagerUdStartingUp(self):
        pass

    def partyManagerUdLost(self):
        pass

    def addPartyResponseUdToAi(self, partyId, errorCode, partyStruct):
        pass

    def respondToInviteResponse(self, *args):
        pass

    def changePrivateResponseUdToAi(self, *args):
        pass

    def changePartyStatusResponseUdToAi(self, *args):
        pass

    def partyInfoOfHostFailedResponseUdToAi(self, *args):
        pass

    def partyInfoOfHostResponseUdToAi(self, *args):
        pass

    def partyHasFinishedUdToAllAi(self, partyId):
        pass

    def updateToPublicPartyInfoUdToAllAi(self, *args):
        pass

    def updateToPublicPartyCountUdToAllAi(self, *args):
        pass

    def mwResponseUdToAllAi(self, *args):
        pass


@magicWord(category=CATEGORY_OVERRIDE)
def endParty():
    """ End the party you are at. """
    manager = simbase.air.partyManager
    party = manager.getPartyInZone(spellbook.getInvoker().zoneId)
    if not party:
        return 'You are not at a party!'
    manager.closeParty(party.info['partyId'])
    return 'The party is over.'
