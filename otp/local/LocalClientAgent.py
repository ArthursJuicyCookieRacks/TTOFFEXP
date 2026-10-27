from direct.directnotify import DirectNotifyGlobal
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagram import PyDatagram
from panda3d.core import Datagram, DatagramIterator, UniqueIdAllocator

from otp.local import LocalDCUtil
from otp.local.LocalMessageDirector import MDParticipant
from otp.local.LocalStateServer import locationChannel

CLIENT_STATE_NEW = 0
CLIENT_STATE_ANONYMOUS = 1
CLIENT_STATE_ESTABLISHED = 2

# Astron's disconnect reasons:
CLIENT_DISCONNECT_OVERSIZED_DATAGRAM = 106
CLIENT_DISCONNECT_NO_HELLO = 107
CLIENT_DISCONNECT_INVALID_MSGTYPE = 108
CLIENT_DISCONNECT_TRUNCATED_DATAGRAM = 109
CLIENT_DISCONNECT_ANONYMOUS_VIOLATION = 113
CLIENT_DISCONNECT_FORBIDDEN_INTEREST = 115
CLIENT_DISCONNECT_MISSING_OBJECT = 117
CLIENT_DISCONNECT_FORBIDDEN_FIELD = 118
CLIENT_DISCONNECT_FORBIDDEN_RELOCATE = 119
CLIENT_DISCONNECT_BAD_VERSION = 124
CLIENT_DISCONNECT_SESSION_OBJECT_DELETED = 153
CLIENT_DISCONNECT_GENERIC = 1


class Interest:

    def __init__(self, interestId, parentId, zoneIds):
        self.interestId = interestId
        self.parentId = parentId
        self.zoneIds = set(zoneIds)


class LocalClient(MDParticipant):
    """
    One client connection on the Client Agent. Translates between the Astron
    client protocol (spoken by the game client) and server messages, enforcing
    the same rules Astron does: interests decide what the client sees, and the
    client can only send clsend/ownsend fields to objects it knows about.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalClient')

    def __init__(self, agent, connection, channel):
        MDParticipant.__init__(self, agent.md)
        self.agent = agent
        self.connection = connection
        self.channel = channel
        self.allocatedChannel = channel
        self.state = CLIENT_STATE_NEW
        self.alive = True

        self.interests = {}
        self.visible = {}
        self.owned = {}
        self.declared = {}
        self.sessionObjects = set()
        self.sendableFields = {}
        self.openChannels = set()
        self.clientPostRemoves = []

        self.subscribe(channel)

    # Helpers:

    def sendToClient(self, dg):
        if self.alive:
            self.connection.deliver(bytes(dg.getMessage()))

    def newClientDatagram(self, msgType):
        dg = PyDatagram()
        dg.addUint16(msgType)
        return dg

    def sendServer(self, target, msgType):
        dg = PyDatagram()
        dg.addServerHeader(target, self.channel, msgType)
        return dg

    def lookupClass(self, doId):
        """
        Returns the dclass of an object this client may talk to, or None.
        """
        if doId in self.owned:
            return self.owned[doId]
        if doId in self.visible:
            return self.visible[doId][0]
        if doId in self.declared:
            return self.declared[doId]
        uberdog = self.agent.uberdogs.get(doId)
        if uberdog is not None:
            return uberdog[0]
        return None

    def violation(self, code, reason):
        """
        Astron disconnects clients that break the protocol rules. Offline we
        log the problem and drop the message, unless local-ca-strict is set.
        """
        if self.agent.strict:
            self.eject(code, reason)
        else:
            self.notify.warning('Client %d: %s (message dropped)' % (self.channel, reason))

    # Messages from the game client:

    def handleClientDatagram(self, data):
        if not self.alive:
            return
        dg = Datagram(data)
        di = DatagramIterator(dg)
        try:
            msgType = di.getUint16()
            self.handleClientMessage(msgType, di)
        except (AssertionError, ValueError, IndexError) as e:
            self.violation(CLIENT_DISCONNECT_TRUNCATED_DATAGRAM, 'Malformed datagram: %s' % e)

    def handleClientMessage(self, msgType, di):
        if self.state == CLIENT_STATE_NEW:
            if msgType != CLIENT_HELLO:
                self.eject(CLIENT_DISCONNECT_NO_HELLO, 'First packet is not CLIENT_HELLO')
                return
            di.getUint32()  # DC hash
            version = di.getString()
            expected = self.agent.version
            if expected and version != expected:
                self.eject(CLIENT_DISCONNECT_BAD_VERSION,
                           'Client version mismatch: server=%s, client=%s' % (expected, version))
                return
            self.state = CLIENT_STATE_ANONYMOUS
            self.sendToClient(self.newClientDatagram(CLIENT_HELLO_RESP))
            return

        if msgType == CLIENT_DISCONNECT:
            self.disconnect()
        elif msgType == CLIENT_HEARTBEAT:
            pass
        elif msgType == CLIENT_OBJECT_SET_FIELD:
            self.handleClientSetField(di.getUint32(), di)
        elif msgType == CLIENT_OBJECT_SET_FIELDS:
            doId = di.getUint32()
            count = di.getUint16()
            for _ in range(count):
                self.handleClientSetField(doId, di)
        elif msgType == CLIENT_OBJECT_LOCATION:
            self.handleClientLocation(di.getUint32(), di.getUint32(), di.getUint32())
        elif msgType == CLIENT_ADD_INTEREST:
            ctx = di.getUint32()
            interestId = di.getUint16()
            parentId = di.getUint32()
            zoneId = di.getUint32()
            self.handleClientAddInterest(ctx, interestId, parentId, [zoneId])
        elif msgType == CLIENT_ADD_INTEREST_MULTIPLE:
            ctx = di.getUint32()
            interestId = di.getUint16()
            parentId = di.getUint32()
            count = di.getUint16()
            zoneIds = [di.getUint32() for _ in range(count)]
            self.handleClientAddInterest(ctx, interestId, parentId, zoneIds)
        elif msgType == CLIENT_REMOVE_INTEREST:
            ctx = di.getUint32()
            interestId = di.getUint16()
            if self.state != CLIENT_STATE_ESTABLISHED:
                self.violation(CLIENT_DISCONNECT_ANONYMOUS_VIOLATION, 'Anonymous client removed an interest')
                return
            self.removeInterest(interestId, ctx, notify=True)
        else:
            self.violation(CLIENT_DISCONNECT_INVALID_MSGTYPE, 'Unknown message type %d' % msgType)

    def handleClientSetField(self, doId, di):
        dclass = self.lookupClass(doId)
        if dclass is None:
            self.violation(CLIENT_DISCONNECT_MISSING_OBJECT,
                           'Field update for unknown object %d' % doId)
            di.skipBytes(di.getRemainingSize())
            return

        if self.state != CLIENT_STATE_ESTABLISHED:
            uberdog = self.agent.uberdogs.get(doId)
            if uberdog is None or not uberdog[1]:
                self.violation(CLIENT_DISCONNECT_ANONYMOUS_VIOLATION,
                               'Anonymous client sent to non-anonymous object %d' % doId)
                di.skipBytes(di.getRemainingSize())
                return

        fieldId = di.getUint16()
        field = dclass.getFieldByIndex(fieldId)
        if field is None:
            self.violation(CLIENT_DISCONNECT_FORBIDDEN_FIELD,
                           'Unknown field %d on %s(%d)' % (fieldId, dclass.getName(), doId))
            di.skipBytes(di.getRemainingSize())
            return

        value = LocalDCUtil.readFieldValue(field, di)

        allowed = field.isClsend() or (doId in self.owned and field.isOwnsend()) or \
                  fieldId in self.sendableFields.get(doId, ())
        if not allowed:
            self.violation(CLIENT_DISCONNECT_FORBIDDEN_FIELD,
                           'Field %s on %s(%d) is not sendable' % (field.getName(), dclass.getName(), doId))
            return

        dg = self.sendServer(doId, STATESERVER_OBJECT_SET_FIELD)
        dg.addUint32(doId)
        dg.addUint16(fieldId)
        dg.appendData(value)
        self.send(dg)

    def handleClientLocation(self, doId, parentId, zoneId):
        if doId not in self.owned:
            if self.lookupClass(doId) is None:
                self.violation(CLIENT_DISCONNECT_MISSING_OBJECT, 'Relocate of unknown object %d' % doId)
            else:
                self.violation(CLIENT_DISCONNECT_FORBIDDEN_RELOCATE, 'Relocate of object %d it does not own' % doId)
            return
        if not self.agent.relocate:
            self.violation(CLIENT_DISCONNECT_FORBIDDEN_RELOCATE, 'Relocation is disabled')
            return

        dg = self.sendServer(doId, STATESERVER_OBJECT_SET_LOCATION)
        dg.addUint32(parentId)
        dg.addUint32(zoneId)
        self.send(dg)

    def handleClientAddInterest(self, ctx, interestId, parentId, zoneIds):
        if self.state != CLIENT_STATE_ESTABLISHED:
            self.violation(CLIENT_DISCONNECT_ANONYMOUS_VIOLATION, 'Anonymous client added an interest')
            return
        if not self.agent.clientInterests:
            self.violation(CLIENT_DISCONNECT_FORBIDDEN_INTEREST, 'Client interests are disabled')
            return
        self.addInterest(interestId, parentId, zoneIds, ctx, notify=True)

    # Interests:

    def coveredLocations(self, exclude=None):
        locations = set()
        for interest in self.interests.values():
            if interest is exclude:
                continue
            for zoneId in interest.zoneIds:
                locations.add((interest.parentId, zoneId))
        return locations

    def isInInterest(self, parentId, zoneId):
        return (parentId, zoneId) in self.coveredLocations()

    def addInterest(self, interestId, parentId, zoneIds, ctx, notify):
        old = self.interests.get(interestId)
        oldLocations = set()
        if old is not None:
            oldLocations = {(old.parentId, z) for z in old.zoneIds}

        interest = Interest(interestId, parentId, zoneIds)
        others = self.coveredLocations(exclude=old)
        self.interests[interestId] = interest
        newLocations = {(parentId, z) for z in interest.zoneIds}

        # Zones this interest no longer covers, and no other interest does:
        killed = oldLocations - newLocations - others
        if killed:
            self.closeLocations(killed)

        # Zones that just became visible:
        opened = newLocations - oldLocations - others
        for location in sorted(opened):
            self.subscribe(locationChannel(*location))

        for location in sorted(newLocations - oldLocations):
            for obj in self.agent.stateServer.getObjectsInZones(location[0], [location[1]]):
                self.enterObject(obj.doId, obj.parentId, obj.zoneId, obj.dclass,
                                 obj.required, obj.ram)

        if notify:
            dg = self.newClientDatagram(CLIENT_DONE_INTEREST_RESP)
            dg.addUint32(ctx)
            dg.addUint16(interestId)
            self.sendToClient(dg)

    def removeInterest(self, interestId, ctx, notify):
        interest = self.interests.pop(interestId, None)
        if interest is None:
            self.notify.warning('Client %d removed unknown interest %d.' % (self.channel, interestId))
        else:
            others = self.coveredLocations()
            killed = {(interest.parentId, z) for z in interest.zoneIds} - others
            self.closeLocations(killed)

        if notify:
            dg = self.newClientDatagram(CLIENT_DONE_INTEREST_RESP)
            dg.addUint32(ctx)
            dg.addUint16(interestId)
            self.sendToClient(dg)

    def closeLocations(self, locations):
        for location in locations:
            self.unsubscribe(locationChannel(*location))

        for doId, (dclass, parentId, zoneId) in list(self.visible.items()):
            if (parentId, zoneId) not in locations:
                continue
            if doId in self.owned:
                continue
            if doId in self.sessionObjects:
                self.notify.warning('Interest closed on session object %d.' % doId)
            self.leaveObject(doId)

    # Objects entering and leaving:

    def unpackEntry(self, di):
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        dclass = self.agent.dcFile.getClass(di.getUint16())
        required = LocalDCUtil.readRequired(dclass, di)
        ram = {}
        if di.getRemainingSize():
            for field, value in LocalDCUtil.readFieldList(dclass, di):
                ram[field.getNumber()] = value
        return doId, parentId, zoneId, dclass, required, ram

    def addClientEntry(self, dg, doId, parentId, zoneId, dclass, required, ram, owner):
        dg.addUint32(doId)
        dg.addUint32(parentId)
        dg.addUint32(zoneId)
        dg.addUint16(dclass.getNumber())
        # The client's parser (DCClass.receiveUpdateBroadcastRequired[Owner])
        # decides which required fields are present; mirror it exactly.
        for field in LocalDCUtil.requiredFields(dclass):
            if field.isBroadcast() or (owner and field.isOwnrecv()):
                value = required.get(field.getNumber())
                if value is None:
                    value = LocalDCUtil.defaultValue(field)
                dg.appendData(value)

        other = []
        for number in sorted(ram):
            field = dclass.getFieldByIndex(number)
            if field is not None and LocalDCUtil.isVisibleToClient(field, owner):
                other.append((number, ram[number]))
        return other

    def enterObject(self, doId, parentId, zoneId, dclass, required, ram):
        if doId in self.visible:
            return
        if not self.isInInterest(parentId, zoneId):
            return

        self.visible[doId] = (dclass, parentId, zoneId)
        body = PyDatagram()
        other = self.addClientEntry(body, doId, parentId, zoneId, dclass, required, ram, False)
        dg = self.newClientDatagram(CLIENT_ENTER_OBJECT_REQUIRED_OTHER if other
                                    else CLIENT_ENTER_OBJECT_REQUIRED)
        dg.appendData(body.getMessage())
        if other:
            dg.addUint16(len(other))
            for number, value in other:
                dg.addUint16(number)
                dg.appendData(value)
        self.sendToClient(dg)

    def enterOwner(self, doId, parentId, zoneId, dclass, required, ram):
        if doId in self.owned:
            return
        self.owned[doId] = dclass
        self.visible[doId] = (dclass, parentId, zoneId)

        dg = self.newClientDatagram(CLIENT_ENTER_OBJECT_REQUIRED_OTHER_OWNER)
        other = self.addClientEntry(dg, doId, parentId, zoneId, dclass, required, ram, True)
        dg.addUint16(len(other))
        for number, value in other:
            dg.addUint16(number)
            dg.appendData(value)
        self.sendToClient(dg)

    def leaveObject(self, doId):
        if self.visible.pop(doId, None) is None:
            return
        dg = self.newClientDatagram(CLIENT_OBJECT_LEAVING)
        dg.addUint32(doId)
        self.sendToClient(dg)

    def leaveOwner(self, doId):
        if self.owned.pop(doId, None) is None:
            return
        dg = self.newClientDatagram(CLIENT_OBJECT_LEAVING_OWNER)
        dg.addUint32(doId)
        self.sendToClient(dg)

    # Messages from the server:

    def handleDatagram(self, dg, channels, sender, msgType, di):
        if not self.alive:
            return
        handler = self.agent.serverHandlers.get(msgType)
        if handler is None:
            self.notify.warning('Client %d got unhandled server message %d.' % (self.channel, msgType))
            return
        try:
            handler(self, sender, di)
        except AssertionError:
            # A truncated message; Astron logs these and carries on.
            self.notify.warning('Client %d got a malformed server message %d from %d.' % (
                self.channel, msgType, sender))

    def handleEnterLocation(self, sender, di):
        doId, parentId, zoneId, dclass, required, ram = self.unpackEntry(di)
        self.enterObject(doId, parentId, zoneId, dclass, required, ram)

    def handleEnterOwner(self, sender, di):
        doId, parentId, zoneId, dclass, required, ram = self.unpackEntry(di)
        self.enterOwner(doId, parentId, zoneId, dclass, required, ram)

    def handleChangingLocation(self, sender, di):
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        entry = self.visible.get(doId)
        if entry is None:
            return

        if doId in self.owned or self.isInInterest(parentId, zoneId):
            self.visible[doId] = (entry[0], parentId, zoneId)
            dg = self.newClientDatagram(CLIENT_OBJECT_LOCATION)
            dg.addUint32(doId)
            dg.addUint32(parentId)
            dg.addUint32(zoneId)
            self.sendToClient(dg)
        else:
            self.leaveObject(doId)

    def handleChangingOwner(self, sender, di):
        doId = di.getUint32()
        newOwner = di.getUint64()
        if newOwner == self.channel:
            return
        self.leaveOwner(doId)
        entry = self.visible.get(doId)
        if entry is not None and not self.isInInterest(entry[1], entry[2]):
            self.leaveObject(doId)

    def handleDeleteRam(self, sender, di):
        doId = di.getUint32()
        if doId in self.sessionObjects:
            self.eject(CLIENT_DISCONNECT_SESSION_OBJECT_DELETED,
                       'The session object with id %d has been unexpectedly deleted.' % doId)
            return
        self.leaveOwner(doId)
        self.leaveObject(doId)

    def handleSetField(self, sender, di):
        if sender == self.channel:
            # Astron never echoes a client's own updates back to it.
            return
        doId = di.getUint32()
        if self.lookupClass(doId) is None:
            return
        dg = self.newClientDatagram(CLIENT_OBJECT_SET_FIELD)
        dg.addUint32(doId)
        dg.appendData(di.getRemainingBytes())
        self.sendToClient(dg)

    def handleSetFields(self, sender, di):
        if sender == self.channel:
            return
        doId = di.getUint32()
        dclass = self.lookupClass(doId)
        if dclass is None:
            return
        for field, value in LocalDCUtil.readFieldList(dclass, di):
            dg = self.newClientDatagram(CLIENT_OBJECT_SET_FIELD)
            dg.addUint32(doId)
            dg.addUint16(field.getNumber())
            dg.appendData(value)
            self.sendToClient(dg)

    # CLIENTAGENT_* messages:

    def handleSetState(self, sender, di):
        self.state = di.getUint16()

    def handleSetClientId(self, sender, di):
        newChannel = di.getUint64()
        if newChannel == self.channel:
            return
        # Like Astron, the channel the client was allocated stays subscribed.
        if self.channel != self.allocatedChannel and self.channel not in self.openChannels:
            self.unsubscribe(self.channel)
        self.channel = newChannel
        self.subscribe(newChannel)

    def handleSendDatagram(self, sender, di):
        self.connection.deliver(bytes(di.getBlob()))

    def handleEject(self, sender, di):
        code = di.getUint16()
        reason = di.getString()
        self.eject(code, reason)

    def handleDrop(self, sender, di):
        self.disconnect(dropped=True)

    def handleGetNetworkAddress(self, sender, di):
        ctx = di.getUint32()
        dg = self.sendServer(sender, CLIENTAGENT_GET_NETWORK_ADDRESS_RESP)
        dg.addUint32(ctx)
        dg.addString('127.0.0.1')
        dg.addUint16(0)
        dg.addString('127.0.0.1')
        dg.addUint16(0)
        self.send(dg)

    def handleDeclareObject(self, sender, di):
        doId = di.getUint32()
        dclass = self.agent.dcFile.getClass(di.getUint16())
        if dclass is not None:
            self.declared[doId] = dclass

    def handleUndeclareObject(self, sender, di):
        self.declared.pop(di.getUint32(), None)

    def handleAddSessionObject(self, sender, di):
        self.sessionObjects.add(di.getUint32())

    def handleRemoveSessionObject(self, sender, di):
        self.sessionObjects.discard(di.getUint32())

    def handleSetFieldsSendable(self, sender, di):
        doId = di.getUint32()
        count = di.getUint16()
        self.sendableFields[doId] = set(di.getUint16() for _ in range(count))

    def handleOpenChannel(self, sender, di):
        channel = di.getUint64()
        self.openChannels.add(channel)
        self.subscribe(channel)

    def handleCloseChannel(self, sender, di):
        channel = di.getUint64()
        self.openChannels.discard(channel)
        if channel not in (self.channel, self.allocatedChannel):
            self.unsubscribe(channel)

    def handleAddPostRemove(self, sender, di):
        self.clientPostRemoves.append(bytes(di.getBlob()))

    def handleClearPostRemoves(self, sender, di):
        self.clientPostRemoves = []

    def handleServerAddInterest(self, sender, di):
        interestId = di.getUint16()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        self.addInterest(interestId, parentId, [zoneId], 0, notify=False)

    def handleServerAddInterestMultiple(self, sender, di):
        interestId = di.getUint16()
        parentId = di.getUint32()
        count = di.getUint16()
        self.addInterest(interestId, parentId, [di.getUint32() for _ in range(count)], 0, notify=False)

    def handleServerRemoveInterest(self, sender, di):
        self.removeInterest(di.getUint16(), 0, notify=False)

    # Disconnection:

    def eject(self, code, reason):
        if not self.alive:
            return
        self.notify.info('Ejecting client %d: %d %s' % (self.channel, code, reason))
        dg = self.newClientDatagram(CLIENT_EJECT)
        dg.addUint16(code)
        dg.addString(reason)
        self.sendToClient(dg)
        self.disconnect(dropped=True)

    def disconnect(self, dropped=False):
        if not self.alive:
            return
        self.alive = False

        for data in self.clientPostRemoves:
            self.md.route(Datagram(data), None)
        self.clientPostRemoves = []

        for doId in list(self.sessionObjects):
            dg = self.sendServer(doId, STATESERVER_OBJECT_DELETE_RAM)
            dg.addUint32(doId)
            self.send(dg)
        self.sessionObjects.clear()

        self.md.removeParticipant(self)
        self.agent.clientDisconnected(self)
        # Where the drop came from, for the "connection broken" box: offline
        # there is no network, so a drop is always the game's own doing.
        import traceback
        frames = traceback.extract_stack()[-6:-1]
        self.connection.closeReason = ' < '.join('%s:%d' % (frame.name, frame.lineno) for frame in reversed(frames))
        self.notify.warning('Client %d dropped: %s' % (self.channel, self.connection.closeReason))
        self.connection.closed(dropped)


class LocalClientAgent:
    """
    The Client Agent role. Accepts LocalClientConnection objects instead of
    TCP sockets.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalClientAgent')

    def __init__(self, md, dcFile, stateServer, uberdogs, channelMin, channelMax,
                 version='', relocate=True, clientInterests=True, strict=False):
        self.md = md
        self.dcFile = dcFile
        self.stateServer = stateServer
        self.version = version
        self.relocate = relocate
        self.clientInterests = clientInterests
        self.strict = strict
        self.channelAllocator = UniqueIdAllocator(channelMin, channelMax)
        self.clients = set()

        # doId -> (dclass, anonymous)
        self.uberdogs = {}
        for doId, className, anonymous in uberdogs:
            dclass = dcFile.getClassByName(className)
            if dclass is None:
                self.notify.warning('Unknown UberDOG class %s.' % className)
                continue
            self.uberdogs[doId] = (dclass, anonymous)

        self.serverHandlers = {
            STATESERVER_OBJECT_ENTER_LOCATION_WITH_REQUIRED: LocalClient.handleEnterLocation,
            STATESERVER_OBJECT_ENTER_LOCATION_WITH_REQUIRED_OTHER: LocalClient.handleEnterLocation,
            STATESERVER_OBJECT_ENTER_OWNER_WITH_REQUIRED: LocalClient.handleEnterOwner,
            STATESERVER_OBJECT_ENTER_OWNER_WITH_REQUIRED_OTHER: LocalClient.handleEnterOwner,
            STATESERVER_OBJECT_CHANGING_LOCATION: LocalClient.handleChangingLocation,
            STATESERVER_OBJECT_CHANGING_OWNER: LocalClient.handleChangingOwner,
            STATESERVER_OBJECT_DELETE_RAM: LocalClient.handleDeleteRam,
            STATESERVER_OBJECT_SET_FIELD: LocalClient.handleSetField,
            STATESERVER_OBJECT_SET_FIELDS: LocalClient.handleSetFields,
            CLIENTAGENT_SET_STATE: LocalClient.handleSetState,
            CLIENTAGENT_SET_CLIENT_ID: LocalClient.handleSetClientId,
            CLIENTAGENT_SEND_DATAGRAM: LocalClient.handleSendDatagram,
            CLIENTAGENT_EJECT: LocalClient.handleEject,
            CLIENTAGENT_DROP: LocalClient.handleDrop,
            CLIENTAGENT_GET_NETWORK_ADDRESS: LocalClient.handleGetNetworkAddress,
            CLIENTAGENT_DECLARE_OBJECT: LocalClient.handleDeclareObject,
            CLIENTAGENT_UNDECLARE_OBJECT: LocalClient.handleUndeclareObject,
            CLIENTAGENT_ADD_SESSION_OBJECT: LocalClient.handleAddSessionObject,
            CLIENTAGENT_REMOVE_SESSION_OBJECT: LocalClient.handleRemoveSessionObject,
            CLIENTAGENT_SET_FIELDS_SENDABLE: LocalClient.handleSetFieldsSendable,
            CLIENTAGENT_OPEN_CHANNEL: LocalClient.handleOpenChannel,
            CLIENTAGENT_CLOSE_CHANNEL: LocalClient.handleCloseChannel,
            CLIENTAGENT_ADD_POST_REMOVE: LocalClient.handleAddPostRemove,
            CLIENTAGENT_CLEAR_POST_REMOVES: LocalClient.handleClearPostRemoves,
            CLIENTAGENT_ADD_INTEREST: LocalClient.handleServerAddInterest,
            CLIENTAGENT_ADD_INTEREST_MULTIPLE: LocalClient.handleServerAddInterestMultiple,
            CLIENTAGENT_REMOVE_INTEREST: LocalClient.handleServerRemoveInterest,
        }

    def connect(self, connection):
        channel = self.channelAllocator.allocate()
        client = LocalClient(self, connection, channel)
        self.clients.add(client)
        return client

    def clientDisconnected(self, client):
        self.clients.discard(client)
        self.channelAllocator.free(client.allocatedChannel)
