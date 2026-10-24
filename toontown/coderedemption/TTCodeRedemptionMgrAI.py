import json
import os

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogBeanItem, CatalogClothingItem, CatalogEmoteItem, CatalogFurnitureItem
from toontown.coderedemption.TTCodeRedemptionConsts import RedeemErrors
from toontown.rpc.AwardManagerConsts import GiveAwardErrors
from toontown.toonbase import ToontownGlobals

# The codes every game knows, by code: a list of awards, each one of
# ('beans', amount), ('clothing', clothingType, color), ('emote', emoteIndex)
# or ('furniture', furnitureType). More codes can be added in the file named
# by code-redemption-file, as JSON in the same shape.
DefaultCodes = {
    'TOONTOWN': [('beans', 1000)],
    'TOONCOUNCIL': [('clothing', 1700, 0)],
    'DOODLE': [('clothing', 1710, 0)],
    'SILLYMETER': [('clothing', 1723, 0)],
}
# The mailbox message for the awards: "A special item from the Toon
# Council just for you!"
ToonCouncilEvent = 1


class TTCodeRedemptionMgrAI(DistributedObjectAI):
    # Turns the codes toons type on the Options page into presents in their
    # award mailbox. Each toon can redeem each code once.
    notify = DirectNotifyGlobal.directNotify.newCategory("TTCodeRedemptionMgrAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.codes = dict(DefaultCodes)
        path = config.ConfigVariableString('code-redemption-file', '').getValue()
        if path and os.path.isfile(path):
            try:
                with open(path) as f:
                    for code, awards in json.load(f).items():
                        self.codes[code.upper()] = [tuple(award) for award in awards]
            except (OSError, ValueError, TypeError) as e:
                self.notify.warning('could not read the codes in %s: %s' % (path, e))

    def makeAward(self, award):
        kind = award[0]
        if kind == 'beans':
            item = CatalogBeanItem.CatalogBeanItem(award[1])
        elif kind == 'clothing':
            item = CatalogClothingItem.CatalogClothingItem(award[1], award[2] if len(award) > 2 else 0)
        elif kind == 'emote':
            item = CatalogEmoteItem.CatalogEmoteItem(award[1])
        elif kind == 'furniture':
            item = CatalogFurnitureItem.CatalogFurnitureItem(award[1])
        else:
            raise ValueError('unknown award %r' % (award,))
        item.specialEventId = ToonCouncilEvent
        return item

    def redeemCode(self, context, code):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not av:
            return
        result, awardResult = self.__redeem(av, code.strip().upper())
        self.sendUpdateToAvatarId(avId, 'redeemCodeResult', [context, result, awardResult])

    def __redeem(self, av, code):
        if code not in self.codes:
            return RedeemErrors.CodeDoesntExist, 0
        key = ('code-redemption', (av.doId,))
        redeemed = simbase.backups.load(*key, default={'codes': []})
        if code in redeemed['codes']:
            return RedeemErrors.CodeAlreadyRedeemed, 0
        try:
            items = [self.makeAward(award) for award in self.codes[code]]
        except (ValueError, IndexError, KeyError) as e:
            self.notify.warning('bad awards for code %s: %s' % (code, e))
            return RedeemErrors.AwardCouldntBeGiven, GiveAwardErrors.UnknownError
        for item in items:
            error = self.__checkAward(av, item)
            if error != GiveAwardErrors.Success:
                return RedeemErrors.AwardCouldntBeGiven, error
        for item in items:
            av.awardMailboxContents.append(item)
        av.b_setAwardMailboxContents(av.awardMailboxContents)
        av.b_setAwardNotify(ToontownGlobals.NewItems)
        redeemed['codes'].append(code)
        simbase.backups.save(*key, redeemed)
        self.air.writeServerEvent('code-redeemed', avId=av.doId, code=code)
        return RedeemErrors.Success, GiveAwardErrors.Success

    def __checkAward(self, av, item):
        if item.notOfferedTo(av):
            return GiveAwardErrors.WrongGender
        if len(av.awardMailboxContents) + len(av.onAwardOrder) >= ToontownGlobals.MaxMailboxContents:
            return GiveAwardErrors.FullAwardMailbox
        if item in av.awardMailboxContents:
            return GiveAwardErrors.AlreadyInAwardMailbox
        if item.reachedPurchaseLimit(av):
            return GiveAwardErrors.GenericAlreadyHaveError
        return GiveAwardErrors.Success
