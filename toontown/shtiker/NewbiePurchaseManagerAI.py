from . import PurchaseManagerAI

class NewbiePurchaseManagerAI(PurchaseManagerAI.PurchaseManagerAI):

    def __init__(self, air, newbieId, playerArray, mpArray, previousMinigameId, trolleyZone):
        self.ownedNewbieId = newbieId
        newbieList = []
        PurchaseManagerAI.PurchaseManagerAI.__init__(self, air, playerArray, mpArray, previousMinigameId, trolleyZone, newbieList)
        # The trolley ToonTask counts as soon as the game is over, before the
        # gag shop: counted only on leaving the shop, the update reached the
        # client after Toontown Central had already loaded, which then said
        # "Remember to ride the trolley" to a toon that just had.
        toon = self.air.doId2do.get(newbieId)
        if toon:
            self.air.questManager.toonRodeTrolleyFirstTime(toon)

    def startCountdown(self):
        pass

    def getOwnedNewbieId(self):
        return self.ownedNewbieId

    def getInvolvedPlayerIds(self):
        return [self.ownedNewbieId]

    def handlePlayerLeaving(self, avId):
        pass
