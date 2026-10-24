from toontown.toonbase import ToontownGlobals
from toontown.toonbase.ToontownGlobals import *
from otp.ai.AIBaseGlobal import *
from direct.distributed.ClockDelta import *
import pickle
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import ClassicFSM, State
from direct.distributed import DistributedObjectAI
from direct.fsm import State
from toontown.toon import NPCToons

class DistributedToonInteriorAI(DistributedObjectAI.DistributedObjectAI):

    def __init__(self, block, air, zoneId, building):
        DistributedObjectAI.DistributedObjectAI.__init__(self, air)
        self.block = block
        self.zoneId = zoneId
        self.building = building
        self.npcs = NPCToons.createNpcsInZone(air, zoneId)
        self.fsm = ClassicFSM.ClassicFSM('DistributedToonInteriorAI', [State.State('toon', self.enterToon, self.exitToon, ['beingTakenOver']), State.State('beingTakenOver', self.enterBeingTakenOver, self.exitBeingTakenOver, []), State.State('off', self.enterOff, self.exitOff, [])], 'toon', 'off')
        self.fsm.enterInitialState()

        # On Black Cat Day, cats who say "Toontastic!" in Toon Hall turn black.
        self.blackCatMgr = None
        if self.zoneId == 2513:
            self.accept('holidayStarted', self.__updateBlackCatMgr)
            self.accept('holidayEnded', self.__updateBlackCatMgr)
            self.__updateBlackCatMgr()

    def __updateBlackCatMgr(self, holidayId=None):
        wanted = config.ConfigVariableBool('want-toonhall-cats', False).getValue() or \
                 self.air.holidayManager.isHolidayRunning(ToontownGlobals.BLACK_CAT_DAY, ToontownGlobals.SPOOKY_BLACK_CAT)
        if wanted and not self.blackCatMgr:
            from toontown.ai.DistributedBlackCatMgrAI import DistributedBlackCatMgrAI
            self.blackCatMgr = DistributedBlackCatMgrAI(self.air)
            self.blackCatMgr.generateWithRequired(self.zoneId)
        elif not wanted and self.blackCatMgr:
            self.blackCatMgr.requestDelete()
            self.blackCatMgr = None

    def delete(self):
        self.ignoreAll()
        if self.blackCatMgr:
            self.blackCatMgr.requestDelete()
            self.blackCatMgr = None
        for npc in self.npcs:
            if npc:
                npc.requestDelete()

        del self.npcs
        del self.fsm
        del self.building
        del self.block
        DistributedObjectAI.DistributedObjectAI.delete(self)

    def getZoneIdAndBlock(self):
        r = [self.zoneId, self.block]
        return r

    def getToonData(self):
        return pickle.dumps(self.building.savedBy, 1)

    def getState(self):
        r = [self.fsm.getCurrentState().getName(), globalClockDelta.getRealNetworkTime()]
        return r

    def setState(self, state):
        self.sendUpdate('setState', [state, globalClockDelta.getRealNetworkTime()])
        self.fsm.request(state)

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterToon(self):
        pass

    def exitToon(self):
        pass

    def enterBeingTakenOver(self):
        pass

    def exitBeingTakenOver(self):
        pass
