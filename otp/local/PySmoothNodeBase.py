"""
A Python version of Panda3D's CDistributedSmoothNodeBase.

The C++ class sends its position updates straight through the C++ side of the
repository, which bypasses the in-process connection otp.local uses. This
version sends the same messages, chosen the same way, through the
repository's Python send().
"""

import math

from panda3d.core import ClockObject, ConfigVariableDouble, Point3, VBase3

F_NEW_X = 0x01
F_NEW_Y = 0x02
F_NEW_Z = 0x04
F_NEW_H = 0x08
F_NEW_P = 0x10
F_NEW_R = 0x20


smoothNodeEpsilon = ConfigVariableDouble('smooth-node-epsilon', 0.01)
networkTimePrecision = 100.0


def nearlyZero(value):
    return abs(value) <= smoothNodeEpsilon.getValue()


def onlyChanged(flags, compare):
    return (flags & compare) != 0 and (flags & ~compare) == 0


class PyDistributedSmoothNodeBase:

    def __init__(self):
        self.repository = None
        self.isAI = False
        self.aiId = 0
        self.clockDelta = None
        self.nodePath = None
        self.dclass = None
        self.doId = 0
        self.storeXyz = Point3(0, 0, 0)
        self.storeHpr = VBase3(0, 0, 0)
        self.storeStop = False
        self.currL = [0, 0]

    def setRepository(self, repository, isAI, aiId):
        self.repository = repository
        self.isAI = bool(isAI)
        self.aiId = aiId

    def setClockDelta(self, clockDelta):
        self.clockDelta = clockDelta

    def initialize(self, nodePath, dclass, doId):
        self.nodePath = nodePath
        self.dclass = dclass
        self.doId = doId
        self.storeXyz = Point3(nodePath.getPos())
        self.storeHpr = VBase3(nodePath.getHpr())
        self.storeStop = False

    def setCurrL(self, l):
        self.currL[1] = l

    setEmbeddedVal = setCurrL

    def printCurrL(self):
        print('printCurrL: sent l: %s last set l: %s' % (self.currL[1], self.currL[0]))

    def sendEverything(self):
        self.currL[0] = self.currL[1]
        self.sendPosHprL()

    def broadcastPosHprFull(self):
        xyz = self.nodePath.getPos()
        hpr = self.nodePath.getHpr()
        flags = 0
        for i, flag in enumerate((F_NEW_X, F_NEW_Y, F_NEW_Z)):
            if not nearlyZero(self.storeXyz[i] - xyz[i]):
                self.storeXyz[i] = xyz[i]
                flags |= flag
        for i, flag in enumerate((F_NEW_H, F_NEW_P, F_NEW_R)):
            if not nearlyZero(self.storeHpr[i] - hpr[i]):
                self.storeHpr[i] = hpr[i]
                flags |= flag

        x, y, z = self.storeXyz
        h, p, r = self.storeHpr
        if self.currL[0] != self.currL[1]:
            # The location (zoneId) changed: send everything.
            self.currL[0] = self.currL[1]
            self.storeStop = False
            self.sendPosHprL()
        elif flags == 0:
            # No change: send one, and only one, stop message.
            if not self.storeStop:
                self.storeStop = True
                self.sendUpdate('setSmStop', [])
        else:
            self.storeStop = False
            if onlyChanged(flags, F_NEW_H):
                self.sendUpdate('setSmH', [h])
            elif onlyChanged(flags, F_NEW_Z):
                self.sendUpdate('setSmZ', [z])
            elif onlyChanged(flags, F_NEW_X | F_NEW_Y):
                self.sendUpdate('setSmXY', [x, y])
            elif onlyChanged(flags, F_NEW_X | F_NEW_Z):
                self.sendUpdate('setSmXZ', [x, z])
            elif onlyChanged(flags, F_NEW_X | F_NEW_Y | F_NEW_Z):
                self.sendUpdate('setSmPos', [x, y, z])
            elif onlyChanged(flags, F_NEW_H | F_NEW_P | F_NEW_R):
                self.sendUpdate('setSmHpr', [h, p, r])
            elif onlyChanged(flags, F_NEW_X | F_NEW_Y | F_NEW_H):
                self.sendUpdate('setSmXYH', [x, y, h])
            elif onlyChanged(flags, F_NEW_X | F_NEW_Y | F_NEW_Z | F_NEW_H):
                self.sendUpdate('setSmXYZH', [x, y, z, h])
            else:
                self.sendUpdate('setSmPosHpr', [x, y, z, h, p, r])

    def broadcastPosHprXyh(self):
        xyz = self.nodePath.getPos()
        hpr = self.nodePath.getHpr()
        flags = 0
        for i, flag in ((0, F_NEW_X), (1, F_NEW_Y)):
            if not nearlyZero(self.storeXyz[i] - xyz[i]):
                self.storeXyz[i] = xyz[i]
                flags |= flag
        if not nearlyZero(self.storeHpr[0] - hpr[0]):
            self.storeHpr[0] = hpr[0]
            flags |= F_NEW_H

        if flags == 0:
            if not self.storeStop:
                self.storeStop = True
                self.sendUpdate('setSmStop', [])
            return
        self.storeStop = False
        x, y = self.storeXyz[0], self.storeXyz[1]
        h = self.storeHpr[0]
        if onlyChanged(flags, F_NEW_H):
            self.sendUpdate('setSmH', [h])
        elif onlyChanged(flags, F_NEW_X | F_NEW_Y):
            self.sendUpdate('setSmXY', [x, y])
        else:
            self.sendUpdate('setSmXYH', [x, y, h])

    def broadcastPosHprXy(self):
        xyz = self.nodePath.getPos()
        flags = 0
        for i, flag in ((0, F_NEW_X), (1, F_NEW_Y)):
            if not nearlyZero(self.storeXyz[i] - xyz[i]):
                self.storeXyz[i] = xyz[i]
                flags |= flag

        if flags == 0:
            if not self.storeStop:
                self.storeStop = True
                self.sendUpdate('setSmStop', [])
            return
        self.storeStop = False
        self.sendUpdate('setSmXY', [self.storeXyz[0], self.storeXyz[1]])

    def sendPosHprL(self):
        x, y, z = self.storeXyz
        h, p, r = self.storeHpr
        self.sendUpdate('setSmPosHprL', [self.currL[0], x, y, z, h, p, r])

    def sendUpdate(self, fieldName, args):
        if self.repository is None or self.dclass is None:
            return
        # The timestamp, as the C++ class computes it (from the real time).
        localTime = ClockObject.getGlobalClock().getRealTime()
        networkTime = int(math.floor((localTime - self.clockDelta.delta) * networkTimePrecision + 0.5))
        networkTime = ((networkTime + 0x8000) & 0xFFFF) - 0x8000
        args = list(args) + [networkTime]
        if self.isAI:
            dg = self.dclass.aiFormatUpdate(fieldName, self.doId, self.doId, self.aiId, args)
        else:
            dg = self.dclass.clientFormatUpdate(fieldName, self.doId, args)
        self.repository.send(dg)


def install():
    """
    Makes direct's smooth nodes use PyDistributedSmoothNodeBase.
    """
    from direct.distributed import DistributedSmoothNodeBase
    DistributedSmoothNodeBase.CDistributedSmoothNodeBase = PyDistributedSmoothNodeBase
