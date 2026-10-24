from .SZHoodAI import SZHoodAI
from toontown.toonbase import ToontownGlobals
from toontown.distributed.DistributedTimerAI import DistributedTimerAI
from toontown.safezone.DistributedPicnicBasketAI import DistributedPicnicBasketAI
from toontown.safezone.DistributedPicnicTableAI import DistributedPicnicTableAI

# Where the game_table and picnic_table props stand in the Acorn Acres DNA.
GameTables = [(91.7, 5.68547, 1.2, 30, 1.45363, 0),
              (-75.439, 62.507, 0.55, 90, -1.45363, 0),
              (7.156, 116.564, 0.79, 0, -1.45363, 0)]
PicnicTables = [(1, -22.0614, -23.779, 1.45, 0, 0, 0),
                (2, 35.4114, -35.0274, 0.5, 0, 1.10906, 0)]


class OZHoodAI(SZHoodAI):
    HOOD = ToontownGlobals.OutdoorZone

    def createZone(self):
        SZHoodAI.createTreasurePlanner(self)
        self.timer = DistributedTimerAI(self.air)
        self.timer.generateWithRequired(self.HOOD)
        self.gameTables = []
        for x, y, z, h, p, r in GameTables:
            self.gameTables.append(DistributedPicnicTableAI(self.air, self.HOOD, 'gameTable', x, y, z, h, p, r))
        self.picnicBaskets = []
        for tableNumber, x, y, z, h, p, r in PicnicTables:
            basket = DistributedPicnicBasketAI(self.air, tableNumber, x, y, z, h, p, r)
            basket.generateWithRequired(self.HOOD)
            self.picnicBaskets.append(basket)
