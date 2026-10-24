from direct.directnotify import DirectNotifyGlobal
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium import CogdoMazeGameGlobals as Globals


class DistCogdoMazeGameAI(DistCogdoGameAI):
    # The Mover & Shaker field office: find water coolers, splash the cogs,
    # and pop the four big cogs to open the exit. The jokes the small cogs
    # drop become the toon-up at the end.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoMazeGameAI")

    def __init__(self, air, interior):
        DistCogdoGameAI.__init__(self, air, interior)
        difficulty = self.getDifficulty()
        self.numSuits = [int(Globals.NumSuits[i] + Globals.SuitsModifier[i] * difficulty) for i in range(3)]
        self.bossHits = {}
        self.bossesDefeated = set()
        self.pickups = set()
        self.memos = {}
        self.doorOpen = False
        self.toonsOut = set()

    def delete(self):
        taskMgr.remove(self.uniqueName('time-alert'))
        taskMgr.remove(self.uniqueName('timeout'))
        taskMgr.remove(self.uniqueName('door-closes'))
        DistCogdoGameAI.delete(self)

    def getNumSuits(self):
        return self.numSuits

    def d_doAction(self, action, data=0):
        self.sendUpdate('doAction', [action, data, self.getNetworkTime()])

    def startGame(self):
        self.d_doAction(Globals.GameActions.Countdown)
        taskMgr.doMethodLater(Globals.SecondsUntilTimeout - Globals.SecondsForTimeAlert, self.__timeAlert, self.uniqueName('time-alert'))
        taskMgr.doMethodLater(Globals.SecondsUntilTimeout, self.__timeout, self.uniqueName('timeout'))

    def __timeAlert(self, task):
        if not self.doorOpen:
            self.d_doAction(Globals.GameActions.TimeAlert)
        return task.done

    def __timeout(self, task):
        # Time ran out before the exit opened: the jokes are lost.
        self.memos = {}
        self.finishGame()
        return task.done

    def __doorCloses(self, task):
        # The toons still inside lose their jokes.
        for avId in list(self.memos):
            if avId not in self.toonsOut:
                del self.memos[avId]
        self.finishGame()
        return task.done

    def endGame(self):
        taskMgr.remove(self.uniqueName('time-alert'))
        taskMgr.remove(self.uniqueName('timeout'))
        taskMgr.remove(self.uniqueName('door-closes'))
        self.interior.setGameMemos(sum(self.memos.values()))

    def requestAction(self, action, data):
        avId = self.getSenderToon()
        if not avId:
            return
        if action == Globals.GameActions.RevealDoor:
            self.d_doAction(Globals.GameActions.RevealDoor, avId)
        elif action == Globals.GameActions.EnterDoor and self.doorOpen and avId not in self.toonsOut:
            self.toonsOut.add(avId)
            self.d_doAction(Globals.GameActions.EnterDoor, avId)
            if set(self.getActiveToons()) <= self.toonsOut:
                self.finishGame()

    def requestUseGag(self, x, y, h, networkTime):
        avId = self.getSenderToon()
        if avId:
            self.sendUpdate('toonUsedGag', [avId, x, y, h, networkTime])

    def requestSuitHitByGag(self, suitType, suitNum):
        avId = self.getSenderToon()
        if not avId:
            return
        self.sendUpdate('suitHitByGag', [avId, suitType, suitNum])
        if suitType == Globals.SuitTypes.Boss and suitNum not in self.bossesDefeated:
            self.bossHits[suitNum] = self.bossHits.get(suitNum, 0) + 1
            if self.bossHits[suitNum] >= Globals.SuitData[Globals.SuitTypes.Boss]['hp']:
                self.bossesDefeated.add(suitNum)
                if len(self.bossesDefeated) >= self.numSuits[0] and not self.doorOpen:
                    self.__openDoor()

    def __openDoor(self):
        self.doorOpen = True
        taskMgr.remove(self.uniqueName('time-alert'))
        taskMgr.remove(self.uniqueName('timeout'))
        self.d_doAction(Globals.GameActions.OpenDoor)
        taskMgr.doMethodLater(Globals.SecondsUntilGameEnds, self.__doorCloses, self.uniqueName('door-closes'))

    def requestHitBySuit(self, suitType, suitNum, networkTime):
        avId = self.getSenderToon()
        if not avId or suitType not in Globals.SuitData:
            return
        self.sendUpdate('toonHitBySuit', [avId, suitType, suitNum, networkTime])
        damage = Globals.SuitData[suitType]['toonDamage'] * (1.0 + self.getDifficulty() * Globals.DamageModifier / 3.0)
        self.damageToon(avId, round(damage))

    def requestHitByDrop(self):
        avId = self.getSenderToon()
        if avId:
            self.sendUpdate('toonHitByDrop', [avId])
            self.damageToon(avId, Globals.DropDamage)

    def requestPickUp(self, pickupNum):
        avId = self.getSenderToon()
        if not avId or pickupNum in self.pickups or avId in self.toonsOut:
            return
        self.pickups.add(pickupNum)
        self.memos[avId] = self.memos.get(avId, 0) + 1
        self.sendUpdate('pickUp', [avId, pickupNum, self.getNetworkTime()])

    def requestGag(self, waterCoolerIndex):
        avId = self.getSenderToon()
        if avId:
            self.sendUpdate('hasGag', [avId, self.getNetworkTime()])

    def toonWentSad(self, avId):
        self.memos.pop(avId, None)
        DistCogdoGameAI.toonWentSad(self, avId)
        if self.doorOpen and set(self.getActiveToons()) <= self.toonsOut:
            self.finishGame()

    def toonLeft(self, avId):
        self.memos.pop(avId, None)
        if self.doorOpen and set(self.getActiveToons()) <= self.toonsOut:
            self.finishGame()
