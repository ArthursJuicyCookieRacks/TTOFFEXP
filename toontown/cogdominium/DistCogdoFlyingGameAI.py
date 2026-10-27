from direct.directnotify import DirectNotifyGlobal
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium import CogdoFlyingGameGlobals as Globals

Actions = Globals.AI.GameActions
Gatherables = Globals.Level.GatherableTypes
# Seconds past the game clock before the server ends the game itself.
GameOverGrace = 60


class DistCogdoFlyingGameAI(DistCogdoGameAI):
    # The Legal Eagle field office: fly with propellers to the far
    # platform, picking up memos on the way while the eagles swoop.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoFlyingGameAI")

    def __init__(self, air, interior):
        DistCogdoGameAI.__init__(self, air, interior)
        self.memoPickups = set()
        self.powerupPickups = set()
        self.memos = {}
        self.landed = set()
        self.winDone = set()
        self.eagleTargets = {}
        self.wentToWin = False

    def delete(self):
        taskMgr.remove(self.uniqueName('game-over'))
        for avId in self.toons:
            taskMgr.remove(self.uniqueName('invul-%d' % avId))
        DistCogdoGameAI.delete(self)

    def startGame(self):
        taskMgr.doMethodLater(Globals.Gameplay.SecondsUntilGameOver + GameOverGrace, self.__gameOver, self.uniqueName('game-over'))

    def __gameOver(self, task):
        self.finishGame()
        return task.done

    def endGame(self):
        taskMgr.remove(self.uniqueName('game-over'))
        self.interior.setGameMemos(sum(self.memos.values()))

    def __getDamage(self, table):
        return table.get(self.getSafezoneId(), 1)

    def requestAction(self, action, data):
        avId = self.getSenderToon()
        if not avId:
            return
        if action == Actions.LandOnWinPlatform:
            self.landed.add(avId)
            self.__checkAllLanded()
        elif action == Actions.WinStateFinished:
            self.winDone.add(avId)
            if set(self.getActiveToons()) <= self.winDone:
                self.finishGame()
        elif action == Actions.HitWhirlwind:
            self.damageToon(avId, self.__getDamage(Globals.AI.SafezoneId2WhirlwindDamage))
        elif action == Actions.HitLegalEagle:
            self.damageToon(avId, self.__getDamage(Globals.AI.SafezoneId2LegalEagleDamage))
        elif action == Actions.HitMinion:
            self.damageToon(avId, self.__getDamage(Globals.AI.SafezoneId2MinionDamage))
        elif action == Actions.RanOutOfTimePenalty:
            self.memos.pop(avId, None)
        elif action == Actions.Died:
            self.sendUpdate('toonDied', [avId, self.getNetworkTime()])
            self.damageToon(avId, self.__getDamage(Globals.AI.SafezoneId2DeathDamage))
        elif action == Actions.Spawn:
            self.sendUpdate('toonSpawn', [avId, self.getNetworkTime()])
        elif action == Actions.SetBlades:
            self.sendUpdate('toonSetBlades', [avId, data])
        elif action == Actions.BladeLost:
            self.sendUpdate('toonBladeLost', [avId])
        elif action == Actions.RequestEnterEagleInterest:
            if not self.eagleTargets.get(data) and avId not in self.eagleTargets.values():
                self.eagleTargets[data] = avId
                self.sendUpdate('toonSetAsEagleTarget', [avId, data, self.getNetworkTime()])
        elif action == Actions.RequestExitEagleInterest:
            if self.eagleTargets.get(data) == avId:
                self.__clearEagle(data)

    def __clearEagle(self, eagleId):
        avId = self.eagleTargets.pop(eagleId, 0)
        if avId:
            self.sendUpdate('toonClearAsEagleTarget', [avId, eagleId, self.getNetworkTime()])

    def __checkAllLanded(self):
        if not self.wentToWin and self.getActiveToons() and set(self.getActiveToons()) <= self.landed:
            self.wentToWin = True
            self.sendUpdate('doAction', [Actions.GotoWinState, 0])

    def requestPickUp(self, pickupNum, pickupType):
        avId = self.getSenderToon()
        if not avId:
            return
        if pickupType == Gatherables.Memo:
            if pickupNum in self.memoPickups:
                return
            self.memoPickups.add(pickupNum)
            self.memos[avId] = self.memos.get(avId, 0) + 1
        elif pickupType in (Gatherables.LaffPowerup, Gatherables.InvulPowerup):
            # Every toon can take each power-up once.
            if (avId, pickupNum) in self.powerupPickups:
                return
            self.powerupPickups.add((avId, pickupNum))
            if pickupType == Gatherables.LaffPowerup:
                av = self.air.doId2do.get(avId)
                if av:
                    av.toonUp(Globals.Gameplay.SafezoneId2LaffPickupHealAmount.get(self.getSafezoneId(), 1))
            else:
                taskMgr.remove(self.uniqueName('invul-%d' % avId))
                taskMgr.doMethodLater(Globals.Gameplay.InvulBuffTime, self.__debuff, self.uniqueName('invul-%d' % avId),
                                      extraArgs=[avId, pickupType])
        self.sendUpdate('pickUp', [avId, pickupNum, self.getNetworkTime()])

    def __debuff(self, avId, pickupType):
        self.sendUpdate('debuffPowerup', [avId, pickupType, self.getNetworkTime()])

    def toonWentSad(self, avId):
        self.memos.pop(avId, None)
        for eagleId, target in list(self.eagleTargets.items()):
            if target == avId:
                self.__clearEagle(eagleId)
        DistCogdoGameAI.toonWentSad(self, avId)
        self.__checkAllLanded()

    def toonLeft(self, avId):
        self.memos.pop(avId, None)
        for eagleId, target in list(self.eagleTargets.items()):
            if target == avId:
                self.eagleTargets.pop(eagleId)
        self.__checkAllLanded()
        if self.wentToWin and set(self.getActiveToons()) <= self.winDone:
            self.finishGame()
