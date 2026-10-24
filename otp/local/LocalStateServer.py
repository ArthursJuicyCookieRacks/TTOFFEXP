from direct.directnotify import DirectNotifyGlobal
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagram import PyDatagram
from panda3d.core import DatagramIterator

from otp.local import LocalDCUtil
from otp.local.LocalMessageDirector import MDParticipant


def locationChannel(parentId, zoneId):
    return (parentId << 32) | zoneId


class StateObject:
    """
    One distributed object living on the State Server. Field values are kept
    as packed bytes keyed by field number.
    """

    def __init__(self, doId, dclass, required, ram=None, dbObject=False):
        self.doId = doId
        self.dclass = dclass
        self.parentId = 0
        self.zoneId = 0
        self.aiChannel = 0
        self.explicitAi = False
        self.ownerChannel = 0
        self.required = required
        self.ram = dict(ram or {})
        self.dbObject = dbObject
        self.children = {}

    def getLocationChannel(self):
        if not self.parentId:
            return None
        return locationChannel(self.parentId, self.zoneId)

    def getValue(self, field):
        number = field.getNumber()
        if number in self.required:
            return self.required[number]
        return self.ram.get(number)

    def addChild(self, zoneId, doId):
        self.children.setdefault(zoneId, set()).add(doId)

    def removeChild(self, zoneId, doId):
        zone = self.children.get(zoneId)
        if zone is None:
            return
        zone.discard(doId)
        if not zone:
            del self.children[zoneId]

    def allChildren(self):
        doIds = []
        for zone in self.children.values():
            doIds.extend(zone)
        return doIds


class LocalStateServer(MDParticipant):
    """
    An in-process Astron State Server and Database State Server.

    Objects created with STATESERVER_CREATE_OBJECT_WITH_REQUIRED(_OTHER) live
    here, and so do database objects activated with
    DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS(_OTHER). Messages for database objects
    that are not active are answered from the database, like the DBSS does.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalStateServer')

    def __init__(self, md, dcFile, control, database, dbMin, dbMax):
        MDParticipant.__init__(self, md)
        self.dcFile = dcFile
        self.control = control
        self.database = database
        self.dbMin = dbMin
        self.dbMax = dbMax
        self.objects = {}

        self.subscribe(control)
        self.subscribeRange(dbMin, dbMax)

        self.objectHandlers = {
            STATESERVER_CREATE_OBJECT_WITH_REQUIRED: self.handleCreateOnChannel,
            STATESERVER_CREATE_OBJECT_WITH_REQUIRED_OTHER: self.handleCreateOnChannel,
            STATESERVER_OBJECT_SET_FIELD: self.handleSetField,
            STATESERVER_OBJECT_SET_FIELDS: self.handleSetFields,
            STATESERVER_OBJECT_DELETE_FIELD_RAM: self.handleDeleteFieldRam,
            STATESERVER_OBJECT_DELETE_FIELDS_RAM: self.handleDeleteFieldsRam,
            STATESERVER_OBJECT_DELETE_RAM: self.handleDeleteRam,
            STATESERVER_OBJECT_SET_LOCATION: self.handleSetLocation,
            STATESERVER_OBJECT_GET_LOCATION: self.handleGetLocation,
            STATESERVER_OBJECT_SET_AI: self.handleSetAI,
            STATESERVER_OBJECT_GET_AI: self.handleGetAI,
            STATESERVER_OBJECT_SET_OWNER: self.handleSetOwner,
            STATESERVER_OBJECT_GET_OWNER: self.handleGetOwner,
            STATESERVER_OBJECT_GET_FIELD: self.handleGetField,
            STATESERVER_OBJECT_GET_FIELDS: self.handleGetFields,
            STATESERVER_OBJECT_GET_ALL: self.handleGetAll,
            STATESERVER_OBJECT_GET_ZONE_COUNT: self.handleGetZoneCount,
            STATESERVER_OBJECT_GET_ZONES_COUNT: self.handleGetZonesCount,
            STATESERVER_OBJECT_GET_CHILD_COUNT: self.handleGetChildCount,
            STATESERVER_OBJECT_DELETE_ZONE: self.handleDeleteZone,
            STATESERVER_OBJECT_DELETE_ZONES: self.handleDeleteZones,
            STATESERVER_OBJECT_DELETE_CHILDREN: self.handleDeleteChildren,
            DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS: self.handleActivate,
            DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS_OTHER: self.handleActivate,
            DBSS_OBJECT_GET_ACTIVATED: self.handleGetActivated,
            DBSS_OBJECT_DELETE_FIELD_DISK: self.handleDeleteFieldDisk,
            DBSS_OBJECT_DELETE_FIELDS_DISK: self.handleDeleteFieldsDisk,
            DBSS_OBJECT_DELETE_DISK: self.handleDeleteDisk,
        }

    def isDatabaseId(self, doId):
        return self.dbMin <= doId <= self.dbMax

    # Routing:

    def handleDatagram(self, dg, channels, sender, msgType, di):
        start = di.getCurrentIndex()
        for channel in channels:
            channelDi = DatagramIterator(dg, start)
            if channel == self.control:
                self.handleControlMessage(sender, msgType, channelDi)
            elif channel in self.objects or (self.isDatabaseId(channel) and channel < (1 << 32)):
                handler = self.objectHandlers.get(msgType)
                if handler is None:
                    self.notify.warning('Unhandled message %d for object %d.' % (msgType, channel))
                    continue
                handler(channel, sender, msgType, channelDi)

    def handleControlMessage(self, sender, msgType, di):
        if msgType in (STATESERVER_CREATE_OBJECT_WITH_REQUIRED,
                       STATESERVER_CREATE_OBJECT_WITH_REQUIRED_OTHER):
            self.handleCreate(sender, di, msgType == STATESERVER_CREATE_OBJECT_WITH_REQUIRED_OTHER)
        elif msgType == STATESERVER_DELETE_AI_OBJECTS:
            aiChannel = di.getUint64()
            for obj in list(self.objects.values()):
                if obj.doId in self.objects and obj.aiChannel == aiChannel:
                    self.annihilate(obj, sender)
        else:
            self.notify.warning('Unhandled control message %d from %d.' % (msgType, sender))

    def reply(self, target, doId, msgType):
        dg = PyDatagram()
        dg.addServerHeader(target, doId, msgType)
        return dg

    def sendTo(self, targets, sender, msgType):
        """
        Starts a datagram to several channels at once (deduplicated, like
        Astron's target sets). Returns None when there are no targets.
        """
        channels = []
        for target in targets:
            if target and target not in channels:
                channels.append(target)
        if not channels:
            return None
        dg = PyDatagram()
        dg.addUint8(len(channels))
        for channel in channels:
            dg.addUint64(channel)
        dg.addUint64(sender)
        dg.addUint16(msgType)
        return dg

    # Packing:

    def addRequired(self, dg, obj):
        for field in LocalDCUtil.requiredFields(obj.dclass):
            value = obj.required.get(field.getNumber())
            if value is None:
                value = LocalDCUtil.defaultValue(field)
            dg.appendData(value)

    def addRam(self, dg, obj):
        dg.addUint16(len(obj.ram))
        for number in sorted(obj.ram):
            dg.addUint16(number)
            dg.appendData(obj.ram[number])

    def addEntry(self, dg, obj):
        dg.addUint32(obj.doId)
        dg.addUint32(obj.parentId)
        dg.addUint32(obj.zoneId)
        dg.addUint16(obj.dclass.getNumber())
        self.addRequired(dg, obj)
        if obj.ram:
            self.addRam(dg, obj)

    # Creation:

    def handleCreateOnChannel(self, doId, sender, msgType, di):
        self.handleCreate(sender, di, msgType == STATESERVER_CREATE_OBJECT_WITH_REQUIRED_OTHER)

    def handleCreate(self, sender, di, other):
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        dclassId = di.getUint16()

        dclass = self.dcFile.getClass(dclassId)
        if dclass is None:
            self.notify.warning('Create of %d with unknown class %d.' % (doId, dclassId))
            return
        if doId in self.objects:
            self.notify.warning('Create of %d (%s), which already exists.' % (doId, dclass.getName()))
            return

        try:
            required = LocalDCUtil.readRequired(dclass, di)
            ram = {}
            if other:
                for field, value in LocalDCUtil.readFieldList(dclass, di):
                    for atomic, atomicValue in LocalDCUtil.splitMolecular(field, value):
                        if atomic.isRam() or atomic.isRequired():
                            ram[atomic.getNumber()] = atomicValue
                        else:
                            self.notify.warning('Non-ram field %s in create of %d.' % (atomic.getName(), doId))
        except ValueError as e:
            self.notify.warning('Bad create of %d (%s): %s' % (doId, dclass.getName(), e))
            return

        for number in list(ram):
            if number in required:
                required[number] = ram.pop(number)

        obj = StateObject(doId, dclass, required, ram)
        self.addObject(obj)
        self.setLocation(obj, parentId, zoneId, sender)

    def addObject(self, obj):
        self.objects[obj.doId] = obj
        if not self.isDatabaseId(obj.doId):
            self.subscribe(obj.doId)

    # Database activation:

    def handleActivate(self, doId, sender, msgType, di):
        di.getUint32()  # doId again
        parentId = di.getUint32()
        zoneId = di.getUint32()

        if doId in self.objects:
            self.notify.warning('Activate of %d, which is already active.' % doId)
            return

        stored = self.database.get(doId)
        if stored is None:
            self.notify.warning('Activate of %d, which is not in the database.' % doId)
            return

        dclass = stored.dclass
        defaults = {}
        if msgType == DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS_OTHER:
            try:
                for field, value in LocalDCUtil.readFieldList(dclass, di):
                    for atomic, atomicValue in LocalDCUtil.splitMolecular(field, value):
                        defaults[atomic.getNumber()] = atomicValue
            except ValueError as e:
                self.notify.warning('Bad activate of %d: %s' % (doId, e))

        required = {}
        ram = {}
        for field in LocalDCUtil.requiredFields(dclass):
            value = stored.fields.get(field.getName())
            if value is None:
                value = LocalDCUtil.defaultValue(field)
            required[field.getNumber()] = value
        for name, value in stored.fields.items():
            field = dclass.getFieldByName(name)
            if field is not None and field.isRam() and not field.isRequired():
                ram[field.getNumber()] = value
        for number, value in defaults.items():
            if number in required:
                required[number] = value
            else:
                ram[number] = value

        obj = StateObject(doId, dclass, required, ram, dbObject=True)
        self.addObject(obj)
        self.setLocation(obj, parentId, zoneId, sender)

    def handleGetActivated(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        di.getUint32()
        dg = self.reply(sender, doId, DBSS_OBJECT_GET_ACTIVATED_RESP)
        dg.addUint32(ctx)
        dg.addUint32(doId)
        dg.addUint8(1 if doId in self.objects else 0)
        self.send(dg)

    def handleDeleteFieldDisk(self, doId, sender, msgType, di):
        self.deleteDiskFields(doId, [di.getUint16()])

    def handleDeleteFieldsDisk(self, doId, sender, msgType, di):
        count = di.getUint16()
        self.deleteDiskFields(doId, [di.getUint16() for _ in range(count)])

    def deleteDiskFields(self, doId, fieldIds):
        stored = self.database.get(doId)
        if stored is None:
            return
        names = []
        for fieldId in fieldIds:
            field = stored.dclass.getFieldByIndex(fieldId)
            if field is None:
                continue
            names.append(field.getName())
            obj = self.objects.get(doId)
            if obj is not None:
                if field.isRequired():
                    obj.required[fieldId] = LocalDCUtil.defaultValue(field)
                else:
                    obj.ram.pop(fieldId, None)
        self.database.deleteFields(doId, names)

    def handleDeleteDisk(self, doId, sender, msgType, di):
        self.database.delete(doId)
        obj = self.objects.get(doId)
        if obj is not None:
            obj.dbObject = False

    # Field updates:

    def handleSetField(self, doId, sender, msgType, di):
        di.getUint32()
        self.applyUpdates(doId, sender, di, 1)

    def handleSetFields(self, doId, sender, msgType, di):
        di.getUint32()
        self.applyUpdates(doId, sender, di, di.getUint16())

    def applyUpdates(self, doId, sender, di, count):
        obj = self.objects.get(doId)
        dclass = obj.dclass if obj else None
        if dclass is None:
            stored = self.database.get(doId)
            if stored is None:
                return
            dclass = stored.dclass

        try:
            updates = LocalDCUtil.readFieldList(dclass, di, count)
        except ValueError as e:
            self.notify.warning('Bad field update for %d: %s' % (doId, e))
            return

        if obj is None:
            # Inactive database object: the DBSS writes db fields straight
            # to the database.
            fields = {}
            for field, value in updates:
                for atomic, atomicValue in LocalDCUtil.splitMolecular(field, value):
                    if atomic.isDb():
                        fields[atomic.getName()] = atomicValue
            if fields:
                self.database.setFields(doId, fields)
            return

        for field, value in updates:
            self.applyUpdate(obj, field, value, sender)

    def applyUpdate(self, obj, field, value, sender):
        dbFields = {}
        for atomic, atomicValue in LocalDCUtil.splitMolecular(field, value):
            number = atomic.getNumber()
            if atomic.isRequired():
                obj.required[number] = atomicValue
            elif atomic.isRam():
                obj.ram[number] = atomicValue
            if obj.dbObject and atomic.isDb():
                dbFields[atomic.getName()] = atomicValue
        if dbFields:
            self.database.setFields(obj.doId, dbFields)

        targets = []
        if field.isBroadcast():
            targets.append(obj.getLocationChannel())
        if field.isAirecv():
            targets.append(obj.aiChannel)
        if field.isOwnrecv():
            targets.append(obj.ownerChannel)

        dg = self.sendTo(targets, sender, STATESERVER_OBJECT_SET_FIELD)
        if dg is not None:
            dg.addUint32(obj.doId)
            dg.addUint16(field.getNumber())
            dg.appendData(value)
            self.send(dg)

    def handleDeleteFieldRam(self, doId, sender, msgType, di):
        di.getUint32()
        self.deleteRamFields(doId, [di.getUint16()])

    def handleDeleteFieldsRam(self, doId, sender, msgType, di):
        di.getUint32()
        count = di.getUint16()
        self.deleteRamFields(doId, [di.getUint16() for _ in range(count)])

    def deleteRamFields(self, doId, fieldIds):
        obj = self.objects.get(doId)
        if obj is None:
            return
        for fieldId in fieldIds:
            field = obj.dclass.getFieldByIndex(fieldId)
            if field is None:
                continue
            if field.isRequired():
                obj.required[fieldId] = LocalDCUtil.defaultValue(field)
            else:
                obj.ram.pop(fieldId, None)

    # Queries:

    def handleGetField(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        di.getUint32()
        fieldId = di.getUint16()
        values = self.lookupFields(doId, [fieldId])
        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_FIELD_RESP)
        dg.addUint32(ctx)
        if values is None or not values:
            dg.addUint8(0)
        else:
            dg.addUint8(1)
            number, value = values[0]
            dg.addUint16(number)
            dg.appendData(value)
        self.send(dg)

    def handleGetFields(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        di.getUint32()
        count = di.getUint16()
        values = self.lookupFields(doId, [di.getUint16() for _ in range(count)])
        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_FIELDS_RESP)
        dg.addUint32(ctx)
        if values is None:
            dg.addUint8(0)
        else:
            dg.addUint8(1)
            dg.addUint16(len(values))
            for number, value in values:
                dg.addUint16(number)
                dg.appendData(value)
        self.send(dg)

    def lookupFields(self, doId, fieldIds):
        """
        Returns [(fieldNumber, bytes)] for the requested fields that have a
        value, looking in RAM first and in the database for db fields.
        Returns None if the object does not exist at all.
        """
        obj = self.objects.get(doId)
        stored = self.database.get(doId) if (obj is None or obj.dbObject) else None
        if obj is None and stored is None:
            return None

        dclass = obj.dclass if obj else stored.dclass
        values = []
        for fieldId in fieldIds:
            field = dclass.getFieldByIndex(fieldId)
            if field is None:
                continue
            value = obj.getValue(field) if obj else None
            if value is None and stored is not None and field.isDb():
                value = stored.fields.get(field.getName())
            if value is None and obj is None and field.isRequired():
                value = LocalDCUtil.defaultValue(field)
            if value is not None:
                values.append((fieldId, value))
        return values

    def handleGetAll(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        di.getUint32()

        obj = self.objects.get(doId)
        if obj is None:
            # The DBSS answers for inactive database objects.
            stored = self.database.get(doId)
            if stored is None:
                return
            required = {}
            ram = {}
            for name, value in stored.fields.items():
                field = stored.dclass.getFieldByName(name)
                if field is None:
                    continue
                if field.isRequired():
                    required[field.getNumber()] = value
                elif field.isRam():
                    ram[field.getNumber()] = value
            obj = StateObject(doId, stored.dclass, required, ram)

        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_ALL_RESP)
        dg.addUint32(ctx)
        dg.addUint32(obj.doId)
        dg.addUint32(obj.parentId)
        dg.addUint32(obj.zoneId)
        dg.addUint16(obj.dclass.getNumber())
        self.addRequired(dg, obj)
        self.addRam(dg, obj)
        self.send(dg)

    def handleGetLocation(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_LOCATION_RESP)
        dg.addUint32(di.getUint32())
        dg.addUint32(doId)
        dg.addUint32(obj.parentId)
        dg.addUint32(obj.zoneId)
        self.send(dg)

    def handleGetAI(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_AI_RESP)
        dg.addUint32(di.getUint32())
        dg.addUint32(doId)
        dg.addUint64(obj.aiChannel)
        self.send(dg)

    def handleGetOwner(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        dg = self.reply(sender, doId, STATESERVER_OBJECT_GET_OWNER_RESP)
        dg.addUint32(di.getUint32())
        dg.addUint32(doId)
        dg.addUint64(obj.ownerChannel)
        self.send(dg)

    def handleGetZoneCount(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        self.sendCount(sender, doId, STATESERVER_OBJECT_GET_ZONE_COUNT_RESP, ctx,
                       len(self.getObjectsInZones(parentId, [zoneId])))

    def handleGetZonesCount(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        parentId = di.getUint32()
        count = di.getUint16()
        zones = [di.getUint32() for _ in range(count)]
        self.sendCount(sender, doId, STATESERVER_OBJECT_GET_ZONES_COUNT_RESP, ctx,
                       len(self.getObjectsInZones(parentId, zones)))

    def handleGetChildCount(self, doId, sender, msgType, di):
        ctx = di.getUint32()
        obj = self.objects.get(doId)
        count = len(obj.allChildren()) if obj else 0
        self.sendCount(sender, doId, STATESERVER_OBJECT_GET_CHILD_COUNT_RESP, ctx, count)

    def sendCount(self, target, doId, msgType, ctx, count):
        dg = self.reply(target, doId, msgType)
        dg.addUint32(ctx)
        dg.addUint32(count)
        self.send(dg)

    def getObjectsInZones(self, parentId, zoneIds):
        """
        Used by the Client Agent to resolve interests.
        """
        parent = self.objects.get(parentId)
        result = []
        for zoneId in zoneIds:
            if parent is not None:
                doIds = parent.children.get(zoneId, ())
            else:
                doIds = [o.doId for o in self.objects.values()
                         if o.parentId == parentId and o.zoneId == zoneId]
            for doId in sorted(doIds):
                obj = self.objects.get(doId)
                if obj is not None:
                    result.append(obj)
        return result

    # Location, AI and owner:

    def handleSetLocation(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            self.notify.warning('Set location of %d, which is not active.' % doId)
            return
        self.setLocation(obj, di.getUint32(), di.getUint32(), sender)

    def setLocation(self, obj, parentId, zoneId, sender):
        if parentId == obj.doId:
            self.notify.warning('Object %d tried to parent itself.' % obj.doId)
            return

        oldParentId, oldZoneId = obj.parentId, obj.zoneId
        if (parentId, zoneId) == (oldParentId, oldZoneId) and obj.parentId:
            return

        oldParent = self.objects.get(oldParentId)
        if oldParent is not None:
            oldParent.removeChild(oldZoneId, obj.doId)

        obj.parentId = parentId
        obj.zoneId = zoneId
        newParent = self.objects.get(parentId)
        if newParent is not None:
            newParent.addChild(zoneId, obj.doId)

        if oldParentId or oldZoneId:
            targets = [locationChannel(oldParentId, oldZoneId) if oldParentId else None,
                       obj.aiChannel, obj.ownerChannel]
            dg = self.sendTo(targets, sender, STATESERVER_OBJECT_CHANGING_LOCATION)
            if dg is not None:
                dg.addUint32(obj.doId)
                dg.addUint32(parentId)
                dg.addUint32(zoneId)
                dg.addUint32(oldParentId)
                dg.addUint32(oldZoneId)
                self.send(dg)

        if parentId:
            msgType = (STATESERVER_OBJECT_ENTER_LOCATION_WITH_REQUIRED_OTHER if obj.ram
                       else STATESERVER_OBJECT_ENTER_LOCATION_WITH_REQUIRED)
            dg = self.sendTo([locationChannel(parentId, zoneId)], sender, msgType)
            self.addEntry(dg, obj)
            self.send(dg)

        if not obj.explicitAi and newParent is not None and newParent.aiChannel:
            self.changeAI(obj, newParent.aiChannel, sender)

    def handleSetAI(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        obj.explicitAi = True
        self.changeAI(obj, di.getUint64(), sender)

    def changeAI(self, obj, aiChannel, sender):
        if aiChannel == obj.aiChannel:
            return

        oldAi = obj.aiChannel
        if oldAi:
            dg = self.sendTo([oldAi], sender, STATESERVER_OBJECT_CHANGING_AI)
            dg.addUint32(obj.doId)
            dg.addUint64(aiChannel)
            dg.addUint64(oldAi)
            self.send(dg)

        obj.aiChannel = aiChannel
        if aiChannel:
            msgType = (STATESERVER_OBJECT_ENTER_AI_WITH_REQUIRED_OTHER if obj.ram
                       else STATESERVER_OBJECT_ENTER_AI_WITH_REQUIRED)
            dg = self.sendTo([aiChannel], sender, msgType)
            self.addEntry(dg, obj)
            self.send(dg)

        for childId in obj.allChildren():
            child = self.objects.get(childId)
            if child is not None and not child.explicitAi:
                self.changeAI(child, aiChannel, sender)

    def handleSetOwner(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        ownerChannel = di.getUint64()
        if ownerChannel == obj.ownerChannel:
            return

        oldOwner = obj.ownerChannel
        if oldOwner:
            dg = self.sendTo([oldOwner], sender, STATESERVER_OBJECT_CHANGING_OWNER)
            dg.addUint32(doId)
            dg.addUint64(ownerChannel)
            dg.addUint64(oldOwner)
            self.send(dg)

        obj.ownerChannel = ownerChannel
        if ownerChannel:
            msgType = (STATESERVER_OBJECT_ENTER_OWNER_WITH_REQUIRED_OTHER if obj.ram
                       else STATESERVER_OBJECT_ENTER_OWNER_WITH_REQUIRED)
            dg = self.sendTo([ownerChannel], sender, msgType)
            self.addEntry(dg, obj)
            self.send(dg)

    # Deletion:

    def handleDeleteRam(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        self.annihilate(obj, sender)

    def handleDeleteZone(self, doId, sender, msgType, di):
        self.deleteZones(doId, [di.getUint32()], sender)

    def handleDeleteZones(self, doId, sender, msgType, di):
        count = di.getUint16()
        self.deleteZones(doId, [di.getUint32() for _ in range(count)], sender)

    def deleteZones(self, doId, zoneIds, sender):
        obj = self.objects.get(doId)
        if obj is None:
            return
        for zoneId in zoneIds:
            for childId in list(obj.children.get(zoneId, ())):
                child = self.objects.get(childId)
                if child is not None:
                    self.annihilate(child, sender)

    def handleDeleteChildren(self, doId, sender, msgType, di):
        obj = self.objects.get(doId)
        if obj is None:
            return
        for childId in obj.allChildren():
            child = self.objects.get(childId)
            if child is not None:
                self.annihilate(child, sender)

    def annihilate(self, obj, sender):
        if self.objects.get(obj.doId) is not obj:
            return

        parent = self.objects.get(obj.parentId)
        if parent is not None:
            parent.removeChild(obj.zoneId, obj.doId)

        dg = self.sendTo([obj.getLocationChannel(), obj.ownerChannel, obj.aiChannel],
                         sender, STATESERVER_OBJECT_DELETE_RAM)
        if dg is not None:
            dg.addUint32(obj.doId)
            self.send(dg)

        del self.objects[obj.doId]
        if not self.isDatabaseId(obj.doId):
            self.unsubscribe(obj.doId)

        for childId in obj.allChildren():
            child = self.objects.get(childId)
            if child is not None:
                self.annihilate(child, sender)
