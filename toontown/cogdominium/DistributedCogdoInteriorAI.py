import copy
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.fsm import ClassicFSM, State
from direct.task import Timer

from toontown.battle import BattleBase
from toontown.building.ElevatorConstants import ELEVATOR_NORMAL, ElevatorData, SUIT_HOLD_ELEVATOR_TIME
from toontown.cogdominium.DistCogdoFlyingGameAI import DistCogdoFlyingGameAI
from toontown.cogdominium.DistCogdoMazeGameAI import DistCogdoMazeGameAI
from toontown.cogdominium.DistributedCogdoBattleBldgAI import DistributedCogdoBattleBldgAI
from toontown.cogdominium.DistributedCogdoElevatorIntAI import DistributedCogdoElevatorIntAI
from toontown.hood import ZoneUtil
from toontown.toon import NPCToons
from toontown.toonbase.ToontownBattleGlobals import getCreditMultiplier, getInvasionMultiplier

# The game on each floor of a field office, by the department that owns it.
FloorGames = {'s': DistCogdoMazeGameAI,
              'l': DistCogdoFlyingGameAI}
# Seconds the executive suite intro movie plays before the battle starts.
BattleIntroTime = 10.5
# The SOS card the rescued shopkeeper hands out, by how hard the building
# was: the third number in FOnpcFriends.
SOSTiers = ((3, 0), (7, 1), (99, 2))


class DistributedCogdoInteriorAI(DistributedObjectAI):
    # A field office. Each game floor is a game for the department, and the
    # top floor is the executive suite: a battle against the boss and its
    # cogs, with the shopkeeper in a cage. Winning frees the building.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedCogdoInteriorAI")

    def __init__(self, air, elevator):
        DistributedObjectAI.__init__(self, air)
        self.bldg = elevator.bldg
        self.elevator = elevator
        self.extZoneId, self.zoneId = self.bldg.getExteriorAndInteriorZoneId()
        self.layout = self.bldg._cogdoLayout
        self.numFloors = self.layout.getNumGameFloors()
        self.bossFloor = self.layout.getBossBattleFloor()
        self.FOType = self.bldg.track
        npcIds = NPCToons.zone2NpcDict.get(ZoneUtil.getCanonicalZoneId(self.zoneId), [])
        self.shopOwnerNpcId = npcIds[0] if npcIds else 0
        self.sosNpcId = self.__pickSOS(self.bldg.difficulty)
        self.currentFloor = 0
        self.toons = []
        self.toonIds = copy.copy(elevator.seats)
        self.responses = {}
        self.ignoreResponses = 0
        self.savedByMap = {}
        self.avatarExitEvents = []
        for toonId in self.toonIds:
            if toonId is not None:
                self.__addToon(toonId)

        self.game = None
        self.gameMemos = 0
        self.battle = None
        self.suits = []
        self.activeSuits = []
        self.reserveSuits = []
        self.joinedReserves = []
        self.suitsKilled = []
        self.suitsKilledPerFloor = []
        self.toonSkillPtsGained = {}
        self.toonExp = {}
        self.toonOrigQuests = {}
        self.toonItems = {}
        self.toonOrigMerits = {}
        self.toonMerits = {}
        self.toonParts = {}
        self.helpfulToons = []
        self.intElevator = None
        self.timer = Timer.Timer()
        self.fsm = ClassicFSM.ClassicFSM('DistributedCogdoInteriorAI', [
            State.State('WaitForAllToonsInside', self.enterWaitForAllToonsInside, self.exitWaitForAllToonsInside, ['Elevator']),
            State.State('Elevator', self.enterElevator, self.exitElevator, ['Game']),
            State.State('Game', self.enterGame, self.exitGame, ['Resting', 'Failed', 'BattleIntro']),
            State.State('BattleIntro', self.enterBattleIntro, self.exitBattleIntro, ['Battle']),
            State.State('Battle', self.enterBattle, self.exitBattle, ['ReservesJoining', 'BattleDone']),
            State.State('ReservesJoining', self.enterReservesJoining, self.exitReservesJoining, ['Battle']),
            State.State('BattleDone', self.enterBattleDone, self.exitBattleDone, ['Reward']),
            State.State('Resting', self.enterResting, self.exitResting, ['Elevator']),
            State.State('Reward', self.enterReward, self.exitReward, ['Off']),
            State.State('Failed', self.enterFailed, self.exitFailed, ['Off']),
            State.State('Off', self.enterOff, self.exitOff, ['WaitForAllToonsInside'])],
            'Off', 'Off', onUndefTransition=ClassicFSM.ClassicFSM.ALLOW)
        self.fsm.enterInitialState()

    def generate(self):
        DistributedObjectAI.generate(self)
        # Not required fields, but the clients need them; the state server
        # keeps them for toons who arrive later.
        self.sendUpdate('setFOType', [self.getFOType()])
        self.sendUpdate('setSOSNpcId', [self.sosNpcId])

    def delete(self):
        self.ignoreAll()
        self.toons = []
        self.toonIds = []
        self.fsm.requestFinalState()
        del self.fsm
        self.timer.stop()
        taskMgr.remove(self.taskName('battle-intro'))
        taskMgr.remove(self.taskName('deleteInterior'))
        self.__cleanupGame()
        self.__cleanupFloorBattle()
        if self.intElevator:
            self.intElevator.requestDelete()
            self.intElevator = None
        del self.bldg
        del self.elevator
        DistributedObjectAI.delete(self)

    def __pickSOS(self, difficulty):
        tier = next(tier for most, tier in SOSTiers if difficulty <= most)
        choices = [npcId for npcId, info in NPCToons.FOnpcFriends.items() if info[3] == tier]
        return random.choice(sorted(choices))

    # The toons

    def __addToon(self, toonId):
        if toonId not in self.air.doId2do:
            self.notify.warning('addToon() - no toon for doId: %d' % toonId)
            return
        event = self.air.getAvatarExitEvent(toonId)
        self.avatarExitEvents.append(event)
        self.accept(event, self.__handleUnexpectedExit, extraArgs=[toonId])
        self.toons.append(toonId)
        self.responses[toonId] = 0

    def __removeToon(self, toonId):
        if toonId in self.toons:
            self.toons.remove(toonId)
        if toonId in self.toonIds:
            self.toonIds[self.toonIds.index(toonId)] = None
        self.responses.pop(toonId, None)
        event = self.air.getAvatarExitEvent(toonId)
        if event in self.avatarExitEvents:
            self.avatarExitEvents.remove(event)
        self.ignore(event)

    def __handleUnexpectedExit(self, toonId):
        self.notify.warning('toon: %d exited unexpectedly' % toonId)
        self.__removeToon(toonId)
        if not self.toons:
            self.timer.stop()
            if self.battle is None and self.fsm.getCurrentState().getName() != 'Resting':
                self.bldg.deleteCogdoInterior()
        elif self.__allToonsResponded():
            # The toon who left was the last one everybody waited for.
            state = self.fsm.getCurrentState().getName()
            if state == 'WaitForAllToonsInside':
                self.fsm.request('Elevator')
            elif state == 'Elevator':
                self.__elevatorDone()
            elif state == 'ReservesJoining':
                self.b_setState('Battle')

    def __resetResponses(self):
        self.responses = {}
        for toon in self.toons:
            self.responses[toon] = 0
        self.ignoreResponses = 0

    def __allToonsResponded(self):
        for toon in self.toons:
            if self.responses.get(toon, 0) == 0:
                return 0
        self.ignoreResponses = 1
        return 1

    def __recordResponse(self, state):
        # Counts a toon's "done" for the state, and returns whether they
        # are all in.
        toonId = self.air.getAvatarIdFromSender()
        if self.ignoreResponses or self.fsm.getCurrentState().getName() != state or toonId not in self.toons:
            return False
        self.responses[toonId] += 1
        return self.__allToonsResponded()

    # The required fields

    def getZoneId(self):
        return self.zoneId

    def getExtZoneId(self):
        return self.extZoneId

    def getDistBldgDoId(self):
        return self.bldg.getDoId()

    def getNumFloors(self):
        return self.numFloors

    def getShopOwnerNpcId(self):
        return self.shopOwnerNpcId

    def getSOSNpcId(self):
        return self.sosNpcId

    def getFOType(self):
        return ord(self.FOType)

    def getToons(self):
        return [[toonId or 0 for toonId in self.toonIds], 0]

    def d_setToons(self):
        self.sendUpdate('setToons', self.getToons())

    def getSuits(self):
        return [[suit.doId for suit in self.activeSuits],
                [info[0].doId for info in self.reserveSuits],
                [info[1] for info in self.reserveSuits]]

    def d_setSuits(self):
        self.sendUpdate('setSuits', self.getSuits())

    def b_setState(self, state):
        self.d_setState(state)
        self.setState(state)

    def d_setState(self, state):
        stime = globalClock.getRealTime() + BattleBase.SERVER_BUFFER_TIME
        self.sendUpdate('setState', [state, globalClockDelta.localToNetworkTime(stime)])

    def setState(self, state):
        self.fsm.request(state)

    def getState(self):
        return [self.fsm.getCurrentState().getName(), globalClockDelta.getRealNetworkTime()]

    # What the clients say

    def setAvatarJoined(self):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toons:
            self.notify.warning('setAvatarJoined() - av: %d not in list' % avId)
            return
        avatar = self.air.doId2do.get(avId)
        if avatar is not None:
            self.savedByMap[avId] = (avatar.getName(), avatar.dna.asTuple())
        if self.__recordResponse('WaitForAllToonsInside'):
            self.fsm.request('Elevator')

    def elevatorDone(self):
        if self.__recordResponse('Elevator'):
            self.__elevatorDone()

    def reserveJoinDone(self):
        if self.__recordResponse('ReservesJoining'):
            self.b_setState('Battle')

    # Barrel rooms are off in this game (cogdo-want-barrel-room), so the
    # clients never send these.

    def toonLeftBarrelRoom(self):
        pass

    def toonBarrelRoomIntroDone(self):
        pass

    def toonBarrelRoomRewardDone(self):
        pass

    # The states

    def enterOff(self):
        pass

    def exitOff(self):
        pass

    def enterWaitForAllToonsInside(self):
        self.__resetResponses()

    def exitWaitForAllToonsInside(self):
        self.__resetResponses()

    def enterElevator(self):
        if self.currentFloor == self.bossFloor:
            suitHandles = self.bldg.planner.genBossFloorSuits()
            self.suits = suitHandles['activeSuits']
            self.activeSuits = list(self.suits)
            self.reserveSuits = suitHandles['reserveSuits']
            self.d_setSuits()
        self.d_setToons()
        self.__resetResponses()
        self.d_setState('Elevator')
        self.timer.startCallback(BattleBase.ELEVATOR_T + ElevatorData[ELEVATOR_NORMAL]['openTime'] + BattleBase.SERVER_BUFFER_TIME,
                                 self.__serverElevatorDone)

    def __serverElevatorDone(self):
        self.ignoreResponses = 1
        self.__elevatorDone()

    def __elevatorDone(self):
        if self.fsm.getCurrentState().getName() == 'Elevator':
            self.b_setState('Game')

    def exitElevator(self):
        self.timer.stop()
        self.__resetResponses()

    def enterGame(self):
        self.elevator.d_setFloor(self.currentFloor)
        if self.currentFloor == self.bossFloor:
            # The executive suite has no game: the boss greets the toons.
            taskMgr.doMethodLater(BattleBase.SERVER_BUFFER_TIME, self.__startBattleIntro, self.taskName('battle-intro'))
            return
        gameClass = FloorGames.get(self.FOType, DistCogdoMazeGameAI)
        self.gameMemos = 0
        self.game = gameClass(self.air, self)
        self.game.generateWithRequired(self.zoneId)
        self.game.start()

    def __startBattleIntro(self, task):
        self.b_setState('BattleIntro')
        return task.done

    def setGameMemos(self, memos):
        self.gameMemos = memos

    def gameDone(self, failed):
        # The floor's game is over; the toons still standing get a toon-up
        # for every memo the team brought out.
        if self.fsm.getCurrentState().getName() != 'Game':
            return
        for toonId in list(self.toons):
            toon = self.air.doId2do.get(toonId)
            if toon is None or toon.getHp() <= 0:
                self.__removeToon(toonId)
            elif self.gameMemos and not failed:
                toon.toonUp(self.gameMemos)
        if failed or not self.toons:
            self.b_setState('Failed')
        else:
            self.d_setToons()
            self.b_setState('Resting')

    def __cleanupGame(self):
        if self.game:
            self.game.requestDelete()
            self.game = None

    def exitGame(self):
        taskMgr.remove(self.taskName('battle-intro'))
        self.__cleanupGame()

    def enterBattleIntro(self):
        self.timer.startCallback(BattleIntroTime, self.__battleIntroDone)

    def __battleIntroDone(self):
        self.b_setState('Battle')

    def exitBattleIntro(self):
        self.timer.stop()

    def __createFloorBattle(self):
        self.battle = DistributedCogdoBattleBldgAI(self.air, self.zoneId, self.__handleRoundDone, self.__handleBattleDone, bossBattle=1)
        self.battle.suitsKilled = self.suitsKilled
        self.battle.suitsKilledPerFloor = self.suitsKilledPerFloor
        self.battle.battleCalc.toonSkillPtsGained = self.toonSkillPtsGained
        self.battle.toonExp = self.toonExp
        self.battle.toonOrigQuests = self.toonOrigQuests
        self.battle.toonItems = self.toonItems
        self.battle.toonOrigMerits = self.toonOrigMerits
        self.battle.toonMerits = self.toonMerits
        self.battle.toonParts = self.toonParts
        self.battle.helpfulToons = self.helpfulToons
        self.battle.setInitialMembers(self.toons, self.suits)
        self.battle.generateWithRequired(self.zoneId)
        mult = getCreditMultiplier(self.currentFloor)
        if self.air.suitInvasionManager.getInvading():
            mult *= getInvasionMultiplier()
        self.battle.battleCalc.setSkillCreditMultiplier(mult)

    def __cleanupFloorBattle(self):
        for suit in self.suits:
            if not suit.isDeleted():
                suit.requestDelete()
        self.suits = []
        self.reserveSuits = []
        self.activeSuits = []
        if self.battle is not None:
            self.battle.requestDelete()
        self.battle = None

    def __handleRoundDone(self, toonIds, totalHp, deadSuits):
        totalMaxHp = 0
        for suit in self.suits:
            totalMaxHp += suit.maxHP
        for suit in deadSuits:
            self.activeSuits.remove(suit)
        if self.reserveSuits and len(self.activeSuits) < 4:
            self.joinedReserves = []
            hpPercent = 100 - totalHp / totalMaxHp * 100.0
            for info in self.reserveSuits:
                if info[1] <= hpPercent and len(self.activeSuits) < 4:
                    self.suits.append(info[0])
                    self.activeSuits.append(info[0])
                    self.joinedReserves.append(info)
            for info in self.joinedReserves:
                self.reserveSuits.remove(info)
            if self.joinedReserves:
                self.fsm.request('ReservesJoining')
                self.d_setSuits()
                return
        if not self.activeSuits:
            self.fsm.request('BattleDone', [toonIds])
        else:
            self.battle.resume()

    def __handleBattleDone(self, zoneId, toonIds):
        if not toonIds:
            taskMgr.doMethodLater(10, self.__doDeleteInterior, self.taskName('deleteInterior'))
        else:
            self.b_setState('Reward')

    def __doDeleteInterior(self, task):
        self.bldg.deleteCogdoInterior()
        return task.done

    def enterBattle(self):
        if self.battle is None:
            self.__createFloorBattle()

    def exitBattle(self):
        pass

    def enterReservesJoining(self):
        self.__resetResponses()
        self.timer.startCallback(ElevatorData[ELEVATOR_NORMAL]['openTime'] + SUIT_HOLD_ELEVATOR_TIME + BattleBase.SERVER_BUFFER_TIME,
                                 self.__serverReserveJoinDone)

    def __serverReserveJoinDone(self):
        self.ignoreResponses = 1
        self.b_setState('Battle')

    def exitReservesJoining(self):
        self.timer.stop()
        self.__resetResponses()
        for info in self.joinedReserves:
            self.battle.suitRequestJoin(info[0])
        self.battle.resume()
        self.joinedReserves = []

    def enterBattleDone(self, toonIds):
        for toon in [toon for toon in self.toons if toon not in toonIds]:
            self.__removeToon(toon)
        self.d_setToons()
        if not self.toons:
            self.bldg.deleteCogdoInterior()
        else:
            self.battle.resume(self.currentFloor, topFloor=1)

    def exitBattleDone(self):
        self.__cleanupFloorBattle()

    def enterResting(self):
        self.intElevator = DistributedCogdoElevatorIntAI(self.air, self, self.toons)
        self.intElevator.generateWithRequired(self.zoneId)

    def handleAllAboard(self, seats):
        if not hasattr(self, 'fsm'):
            return
        if seats.count(None) == 4:
            self.bldg.deleteCogdoInterior()
            return
        for toon in list(self.toons):
            if toon not in seats:
                self.__removeToon(toon)
        self.toonIds = copy.copy(seats)
        self.toons = [toonId for toonId in self.toonIds if toonId is not None]
        self.d_setToons()
        self.currentFloor += 1
        self.fsm.request('Elevator')

    def exitResting(self):
        if self.intElevator:
            self.intElevator.requestDelete()
            self.intElevator = None

    def enterReward(self):
        victors = self.toonIds[:]
        savedBy = []
        for v in victors:
            info = self.savedByMap.get(v)
            if info:
                savedBy.append([v, info[0], info[1]])
            toon = self.air.doId2do.get(v)
            if toon:
                # The shopkeeper's thank-you: their friend's SOS card.
                toon.attemptAddNPCFriend(self.sosNpcId)
        self.bldg.fsm.request('waitForVictorsFromCogdo', [victors, savedBy])
        self.d_setState('Reward')

    def exitReward(self):
        pass

    def enterFailed(self):
        # Everyone is out; the field office stays.
        taskMgr.doMethodLater(10, self.__doDeleteInterior, self.taskName('deleteInterior'))

    def exitFailed(self):
        pass
