from panda3d.core import *
from panda3d.direct import DCPacker
from direct.directnotify.DirectNotifyGlobal import *
from toontown.toon import DistributedToonAI


class DatabaseObject:
    """
    Reads and writes stored objects that are not generated on this AI.

    This used to speak the old OTP database server protocol
    (DBSERVER_GET_STORED_VALUES and friends), which Astron never understood.
    It now goes through the repository's Astron database interface, keeping
    the same interface for its callers.
    """
    notify = directNotify.newCategory('DatabaseObject')
    notify.setInfo(0)

    def __init__(self, air, doId = None, doneEvent = 'DatabaseObject'):
        self.air = air
        self.doId = doId
        self.values = {}
        self.gotDataHandler = None
        self.doneEvent = doneEvent

    def readToon(self, fields = None):
        toon = DistributedToonAI.DistributedToonAI(self.air)
        self.readObject(toon, fields)
        return toon

    if simbase.wantPets:

        def readPet(self):
            from toontown.pets import DistributedPetAI
            pet = DistributedPetAI.DistributedPetAI(self.air)
            self.readObject(pet, None)
            return pet

        def readPetProxy(self):
            from toontown.pets import DistributedPetProxyAI
            petProxy = DistributedPetProxyAI.DistributedPetProxyAI(self.air)
            self.readObject(petProxy, None)
            return petProxy

    def readObject(self, do, fields = None):
        self.do = do
        self.dclass = self.getStoredClass(do)
        self.gotDataHandler = self.fillin
        if fields != None:
            self.getFields(fields)
        else:
            self.getFields(self.getDatabaseFields(self.dclass))

    def storeObject(self, do, fields = None):
        self.do = do
        self.dclass = self.getStoredClass(do)
        if fields != None:
            self.reload(self.do, self.dclass, fields)
        else:
            self.reload(self.do, self.dclass, self.getDatabaseFields(self.dclass))
        values = self.values
        if fields != None:
            values = {}
            for field in fields:
                if field in self.values:
                    values[field] = self.values[field]
                else:
                    self.notify.warning('Field %s not defined.' % field)

        self.setFields(values)

    def getStoredClass(self, do):
        className = do.__class__.__name__
        if className.endswith('AI'):
            className = className[:-2]
        # A pet proxy is read from and stored into its pet's record.
        if className == 'DistributedPetProxy':
            className = 'DistributedPet'
        return self.air.dclassesByName.get(className) or self.air.dclassesByName[className + 'AI']

    def getFields(self, fields):
        if not fields:
            self.__handleQuery(self.dclass, {})
            return
        self.air.dbInterface.queryObject(self.air.dbId, self.doId, self.__handleQuery,
                                         self.dclass, fieldNames=fields)

    def __handleQuery(self, dclass, fields):
        if dclass is None:
            self.notify.warning('Failed to retrieve data for object %d' % self.doId)
            retCode = 1
        else:
            retCode = 0
            self.values = dict(fields)
            self.notify.info('got data for %d' % self.doId)
            if self.gotDataHandler != None:
                self.gotDataHandler(self.do, self.dclass)
                self.gotDataHandler = None
        if self.doneEvent != None:
            messenger.send(self.doneEvent, [self, retCode])

    def setFields(self, values):
        if not values:
            return
        self.air.dbInterface.updateObject(self.air.dbId, self.doId, self.dclass, values)

    def getDatabaseFields(self, dclass):
        fields = []
        for i in range(dclass.getNumInheritedFields()):
            dcf = dclass.getInheritedField(i)
            af = dcf.asAtomicField()
            if af:
                if af.isDb():
                    fields.append(af.getName())

        return fields

    def fillin(self, do, dclass):
        do.doId = self.doId
        for field, value in list(self.values.items()):
            if field == 'setZonesVisited' and len(value) == 1 and not value[0]:
                self.notify.warning('Ignoring broken setZonesVisited')
                continue
            setter = getattr(do, field, None)
            if setter is None:
                continue
            setter(*value)

    def reload(self, do, dclass, fields):
        self.doId = do.doId
        self.values = {}
        for fieldName in fields:
            field = dclass.getFieldByName(fieldName)
            if field == None:
                self.notify.warning('No definition for %s' % fieldName)
                continue
            # Ask the object for the value the same way a generate would, then
            # turn the packed value back into arguments for updateObject.
            dg = Datagram()
            if not dclass.packRequiredField(dg, do, field):
                self.notify.warning('Could not pack %s' % fieldName)
                continue
            unpacker = DCPacker()
            unpacker.setUnpackData(dg.getMessage())
            unpacker.beginUnpack(field)
            self.values[fieldName] = field.unpackArgs(unpacker)
            unpacker.endUnpack()

    def createObject(self, objectType):
        def handleCreate(doId):
            retCode = 0 if doId else 1
            if retCode:
                self.notify.warning('Database object %s create failed' % objectType)
            else:
                self.doId = doId
            if self.doneEvent != None:
                messenger.send(self.doneEvent, [self, retCode])

        self.air.dbInterface.createObject(self.air.dbId, self.air.dclassesByNumber[objectType],
                                          {}, callback=handleCreate)

    def deleteObject(self):
        # Astron's database has no delete message for game servers; objects
        # are dropped by unlinking them from their owner instead.
        self.notify.warning('not deleting object %s (unsupported)' % self.doId)
