import os
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagram import PyDatagram

from otp.local import LocalDCUtil
from otp.local.LocalMessageDirector import MDParticipant

try:
    import yaml
except ImportError:
    yaml = None


class DatabaseObject:
    """
    One stored object: its class and its db fields as packed bytes, keyed by
    field name (names survive DC file edits better than field numbers).
    """

    def __init__(self, doId, dclass, fields=None):
        self.doId = doId
        self.dclass = dclass
        self.fields = fields or {}


class YAMLBackend:
    """
    Stores objects one file per object, in the same layout and value format as
    Astron's YAML database backend, so existing saves from
    astron/databases/astrondb load unchanged:

        <directory>/info.yaml       next: <doId>, free: [<doId>, ...]
        <directory>/<doId>.yaml     ID, class, fields: {name: formatted value}

    Objects are cached in memory. Writes are batched and flushed to disk every
    `flushInterval` seconds and on shutdown.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalDatabase')

    def __init__(self, dcFile, directory, minId, maxId, flushInterval=2.0):
        if yaml is None:
            raise RuntimeError('PyYAML is required for the local database.')

        self.dcFile = dcFile
        self.directory = directory
        self.minId = minId
        self.maxId = maxId
        self.flushInterval = flushInterval

        self.cache = {}
        self.missing = set()
        self.dirty = set()
        self.deleted = set()
        self.infoDirty = False
        self.lastFlush = time.time()

        os.makedirs(self.directory, exist_ok=True)
        self.nextId = minId
        self.freeIds = []
        self.loadInfo()

    # Ids:

    def loadInfo(self):
        path = os.path.join(self.directory, 'info.yaml')
        if not os.path.exists(path):
            return
        with open(path, 'r') as f:
            info = yaml.safe_load(f) or {}
        self.nextId = int(info.get('next', self.minId))
        self.freeIds = [int(doId) for doId in (info.get('free') or [])]

    def allocateId(self):
        while self.freeIds:
            doId = self.freeIds.pop(0)
            self.infoDirty = True
            if not self.exists(doId):
                return doId

        while self.nextId <= self.maxId:
            doId = self.nextId
            self.nextId += 1
            self.infoDirty = True
            if not self.exists(doId):
                return doId

        return 0

    # Objects:

    def filename(self, doId):
        return os.path.join(self.directory, '%d.yaml' % doId)

    def exists(self, doId):
        return self.get(doId) is not None

    def get(self, doId):
        if doId in self.cache:
            return self.cache[doId]
        if doId in self.missing or doId in self.deleted:
            return None

        obj = self.loadObject(doId)
        if obj is None:
            self.missing.add(doId)
        else:
            self.cache[doId] = obj
        return obj

    def loadObject(self, doId):
        path = self.filename(doId)
        if not os.path.exists(path):
            return None

        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            self.notify.warning('Could not read object %d: %s' % (doId, e))
            return None

        dclass = self.dcFile.getClassByName(str(data.get('class', '')))
        if dclass is None:
            self.notify.warning('Object %d has unknown class %r.' % (doId, data.get('class')))
            return None

        fields = {}
        for name, text in (data.get('fields') or {}).items():
            field = dclass.getFieldByName(name)
            if field is None:
                self.notify.warning('Dropping unknown field %s.%s on object %d.' % (dclass.getName(), name, doId))
                continue
            try:
                fields[name] = LocalDCUtil.parseValue(field, str(text))
            except ValueError as e:
                self.notify.warning('Dropping unreadable field on object %d: %s' % (doId, e))

        return DatabaseObject(doId, dclass, fields)

    def create(self, dclass, fields):
        doId = self.allocateId()
        if not doId:
            return 0

        self.missing.discard(doId)
        self.deleted.discard(doId)
        self.cache[doId] = DatabaseObject(doId, dclass, dict(fields))
        self.dirty.add(doId)
        return doId

    def setFields(self, doId, fields):
        obj = self.get(doId)
        if obj is None:
            return False
        obj.fields.update(fields)
        self.dirty.add(doId)
        return True

    def deleteFields(self, doId, names):
        obj = self.get(doId)
        if obj is None:
            return False
        for name in names:
            obj.fields.pop(name, None)
        self.dirty.add(doId)
        return True

    def delete(self, doId):
        if self.get(doId) is None:
            return False
        del self.cache[doId]
        self.dirty.discard(doId)
        self.deleted.add(doId)
        self.freeIds.append(doId)
        self.infoDirty = True
        return True

    # Disk:

    def update(self):
        if time.time() - self.lastFlush >= self.flushInterval:
            self.flush()

    def flush(self):
        self.lastFlush = time.time()

        for doId in list(self.dirty):
            obj = self.cache.get(doId)
            if obj is not None:
                self.writeObject(obj)
        self.dirty.clear()

        for doId in list(self.deleted):
            try:
                os.remove(self.filename(doId))
            except FileNotFoundError:
                pass
            self.missing.add(doId)
        self.deleted.clear()

        if self.infoDirty:
            self.writeFile(os.path.join(self.directory, 'info.yaml'),
                           {'next': self.nextId, 'free': list(self.freeIds)})
            self.infoDirty = False

    def writeObject(self, obj):
        fields = {}
        for name, value in obj.fields.items():
            field = obj.dclass.getFieldByName(name)
            if field is None:
                continue
            try:
                fields[name] = LocalDCUtil.formatValue(field, value)
            except ValueError as e:
                self.notify.warning('Not saving field on object %d: %s' % (obj.doId, e))

        self.writeFile(self.filename(obj.doId),
                       {'ID': obj.doId, 'class': obj.dclass.getName(), 'fields': fields})

    def writeFile(self, path, data):
        tmpPath = path + '.tmp'
        with open(tmpPath, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmpPath, path)


class LocalDatabaseServer(MDParticipant):
    """
    Answers Astron DBSERVER_* messages on the database control channel.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalDatabaseServer')

    def __init__(self, md, dcFile, backend, control):
        MDParticipant.__init__(self, md)
        self.dcFile = dcFile
        self.backend = backend
        self.control = control
        self.subscribe(control)

        self.handlers = {
            DBSERVER_CREATE_OBJECT: self.handleCreateObject,
            DBSERVER_OBJECT_GET_ALL: self.handleGetAll,
            DBSERVER_OBJECT_GET_FIELD: self.handleGetField,
            DBSERVER_OBJECT_GET_FIELDS: self.handleGetFields,
            DBSERVER_OBJECT_SET_FIELD: self.handleSetField,
            DBSERVER_OBJECT_SET_FIELDS: self.handleSetFields,
            DBSERVER_OBJECT_SET_FIELD_IF_EQUALS: self.handleSetFieldIfEquals,
            DBSERVER_OBJECT_SET_FIELDS_IF_EQUALS: self.handleSetFieldsIfEquals,
            DBSERVER_OBJECT_SET_FIELD_IF_EMPTY: self.handleSetFieldIfEmpty,
            DBSERVER_OBJECT_DELETE_FIELD: self.handleDeleteField,
            DBSERVER_OBJECT_DELETE_FIELDS: self.handleDeleteFields,
            DBSERVER_OBJECT_DELETE: self.handleDelete,
        }

    def handleDatagram(self, dg, channels, sender, msgType, di):
        handler = self.handlers.get(msgType)
        if handler is None:
            self.notify.warning('Unhandled database message %d from %d.' % (msgType, sender))
            return
        handler(sender, di)

    def reply(self, target, msgType):
        dg = PyDatagram()
        dg.addServerHeader(target, self.control, msgType)
        return dg

    def readFieldIds(self, dclass, di, count):
        fields = []
        for _ in range(count):
            field = dclass.getFieldByIndex(di.getUint16())
            if field is not None:
                fields.append(field)
        return fields

    # Creation:

    def handleCreateObject(self, sender, di):
        ctx = di.getUint32()
        dclassId = di.getUint16()
        dclass = self.dcFile.getClass(dclassId)
        doId = 0

        if dclass is None:
            self.notify.warning('Create request for unknown class %d.' % dclassId)
        else:
            try:
                values = LocalDCUtil.readFieldList(dclass, di)
            except ValueError as e:
                self.notify.warning('Bad create request for %s: %s' % (dclass.getName(), e))
                values = None

            if values is not None:
                fields = {}
                for field, value in values:
                    for atomic, atomicValue in LocalDCUtil.splitMolecular(field, value):
                        if atomic.isDb():
                            fields[atomic.getName()] = atomicValue
                        else:
                            self.notify.warning('Ignoring non-db field %s in create of %s.'
                                                % (atomic.getName(), dclass.getName()))

                # Required db fields that were not given get their defaults:
                for field in LocalDCUtil.requiredFields(dclass):
                    if field.isDb() and field.getName() not in fields:
                        fields[field.getName()] = LocalDCUtil.defaultValue(field)

                doId = self.backend.create(dclass, fields)

        dg = self.reply(sender, DBSERVER_CREATE_OBJECT_RESP)
        dg.addUint32(ctx)
        dg.addUint32(doId)
        self.send(dg)

    # Queries:

    def addFields(self, dg, obj, names):
        for name in names:
            field = obj.dclass.getFieldByName(name)
            dg.addUint16(field.getNumber())
            dg.appendData(obj.fields[name])

    def handleGetAll(self, sender, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        obj = self.backend.get(doId)

        dg = self.reply(sender, DBSERVER_OBJECT_GET_ALL_RESP)
        dg.addUint32(ctx)
        if obj is None:
            dg.addUint8(0)
        else:
            names = [n for n in obj.fields if obj.dclass.getFieldByName(n)]
            dg.addUint8(1)
            dg.addUint16(obj.dclass.getNumber())
            dg.addUint16(len(names))
            self.addFields(dg, obj, names)
        self.send(dg)

    def handleGetField(self, sender, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        fieldId = di.getUint16()
        obj = self.backend.get(doId)

        dg = self.reply(sender, DBSERVER_OBJECT_GET_FIELD_RESP)
        dg.addUint32(ctx)
        field = obj.dclass.getFieldByIndex(fieldId) if obj else None
        if field is None or field.getName() not in obj.fields:
            dg.addUint8(0)
        else:
            dg.addUint8(1)
            self.addFields(dg, obj, [field.getName()])
        self.send(dg)

    def handleGetFields(self, sender, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        count = di.getUint16()
        obj = self.backend.get(doId)

        dg = self.reply(sender, DBSERVER_OBJECT_GET_FIELDS_RESP)
        dg.addUint32(ctx)
        if obj is None:
            dg.addUint8(0)
        else:
            fields = self.readFieldIds(obj.dclass, di, count)
            names = [f.getName() for f in fields if f.getName() in obj.fields]
            dg.addUint8(1)
            dg.addUint16(len(names))
            self.addFields(dg, obj, names)
        self.send(dg)

    # Updates:

    def readUpdates(self, obj, di, count, withOld=False):
        """
        Reads (field, [old,] new) entries for obj. Returns a list of
        (fieldName, oldBytes or None, newBytes) for db fields only.
        """
        updates = []
        for _ in range(count):
            field = obj.dclass.getFieldByIndex(di.getUint16())
            if field is None:
                raise ValueError('Unknown field in update for object %d' % obj.doId)
            old = LocalDCUtil.readFieldValue(field, di) if withOld else None
            new = LocalDCUtil.readFieldValue(field, di)
            if field.isDb():
                updates.append((field.getName(), old, new))
            else:
                self.notify.warning('Ignoring non-db field %s in update of %d.' % (field.getName(), obj.doId))
        return updates

    def doSetFields(self, di, multi):
        doId = di.getUint32()
        obj = self.backend.get(doId)
        if obj is None:
            self.notify.warning('Update for missing object %d.' % doId)
            return
        count = di.getUint16() if multi else 1
        try:
            updates = self.readUpdates(obj, di, count)
        except ValueError as e:
            self.notify.warning(str(e))
            return
        self.backend.setFields(doId, {name: new for name, _, new in updates})

    def handleSetField(self, sender, di):
        self.doSetFields(di, False)

    def handleSetFields(self, sender, di):
        self.doSetFields(di, True)

    def doSetFieldsIfEquals(self, sender, di, multi):
        ctx = di.getUint32()
        doId = di.getUint32()
        respType = DBSERVER_OBJECT_SET_FIELDS_IF_EQUALS_RESP if multi else DBSERVER_OBJECT_SET_FIELD_IF_EQUALS_RESP
        dg = self.reply(sender, respType)
        dg.addUint32(ctx)

        obj = self.backend.get(doId)
        updates = None
        if obj is not None:
            count = di.getUint16() if multi else 1
            try:
                updates = self.readUpdates(obj, di, count, withOld=True)
            except ValueError as e:
                self.notify.warning(str(e))

        if updates is None:
            dg.addUint8(0)
            self.send(dg)
            return

        if all(obj.fields.get(name) == old for name, old, _ in updates):
            self.backend.setFields(doId, {name: new for name, _, new in updates})
            dg.addUint8(1)
        else:
            dg.addUint8(0)
            present = [name for name, _, _ in updates if name in obj.fields]
            if multi:
                dg.addUint16(len(present))
                self.addFields(dg, obj, present)
            elif present:
                self.addFields(dg, obj, present)
        self.send(dg)

    def handleSetFieldIfEquals(self, sender, di):
        self.doSetFieldsIfEquals(sender, di, False)

    def handleSetFieldsIfEquals(self, sender, di):
        self.doSetFieldsIfEquals(sender, di, True)

    def handleSetFieldIfEmpty(self, sender, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        dg = self.reply(sender, DBSERVER_OBJECT_SET_FIELD_IF_EMPTY_RESP)
        dg.addUint32(ctx)

        obj = self.backend.get(doId)
        try:
            updates = self.readUpdates(obj, di, 1) if obj else None
        except ValueError:
            updates = None

        if not updates:
            dg.addUint8(0)
        elif updates[0][0] in obj.fields:
            dg.addUint8(0)
            self.addFields(dg, obj, [updates[0][0]])
        else:
            self.backend.setFields(doId, {updates[0][0]: updates[0][2]})
            dg.addUint8(1)
        self.send(dg)

    # Deletion:

    def handleDeleteField(self, sender, di):
        doId = di.getUint32()
        obj = self.backend.get(doId)
        if obj:
            fields = self.readFieldIds(obj.dclass, di, 1)
            self.backend.deleteFields(doId, [f.getName() for f in fields])

    def handleDeleteFields(self, sender, di):
        doId = di.getUint32()
        obj = self.backend.get(doId)
        if obj:
            fields = self.readFieldIds(obj.dclass, di, di.getUint16())
            self.backend.deleteFields(doId, [f.getName() for f in fields])

    def handleDelete(self, sender, di):
        self.backend.delete(di.getUint32())
