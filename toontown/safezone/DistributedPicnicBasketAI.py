from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI

NumSeats = 4


class DistributedPicnicBasketAI(DistributedObjectAI):
    # A picnic table in Acorn Acres. Toons sit down and share a snack; the
    # client gets them up again when its countdown runs out.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPicnicBasketAI")

    def __init__(self, air, tableNumber=0, x=0, y=0, z=0, h=0, p=0, r=0):
        DistributedObjectAI.__init__(self, air)
        self.tableNumber = tableNumber
        self.posHpr = (x, y, z, h, p, r)
        self.seats = [0] * NumSeats
        self.state = 'waitEmpty'
        self.stateTime = globalClockDelta.getRealNetworkTime(bits=16)

    def delete(self):
        for avId in self.seats:
            if avId:
                self.ignore(self.air.getAvatarExitEvent(avId))
        DistributedObjectAI.delete(self)

    def getPosHpr(self):
        return self.posHpr

    def getTableNumber(self):
        return self.tableNumber

    def getState(self):
        return [self.state, 0, self.stateTime]

    def b_setState(self, state):
        self.state = state
        self.stateTime = globalClockDelta.getRealNetworkTime(bits=16)
        self.sendUpdate('setState', [state, 0, self.stateTime])

    def generate(self):
        DistributedObjectAI.generate(self)
        self.b_setState('waitEmpty')

    def requestBoard(self, seat):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.seats or not 0 <= seat < NumSeats or self.seats[seat]:
            self.sendUpdateToAvatarId(avId, 'rejectBoard', [avId])
            return
        self.seats[seat] = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleAvatarExit, [avId])
        self.sendUpdate('fillSlot%d' % seat, [avId])
        if self.state != 'waitCountdown':
            self.b_setState('waitCountdown')

    def requestExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.seats:
            self.__emptySeat(self.seats.index(avId), avId)

    def __handleAvatarExit(self, avId):
        if avId in self.seats:
            # avId 1 tells the clients the toon is gone without a jump.
            self.__emptySeat(self.seats.index(avId), 1)

    def __emptySeat(self, seat, avId):
        self.ignore(self.air.getAvatarExitEvent(self.seats[seat]))
        self.seats[seat] = 0
        self.sendUpdate('emptySlot%d' % seat, [avId, globalClockDelta.getRealNetworkTime(bits=16)])
        self.sendUpdate('fillSlot%d' % seat, [0])
        if not any(self.seats):
            self.b_setState('waitEmpty')

    def doneExit(self):
        pass
