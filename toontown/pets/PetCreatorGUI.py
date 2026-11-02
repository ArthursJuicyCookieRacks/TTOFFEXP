"""
The pet shop's Build a Doodle screen, and its Restyle screen for the doodle
a toon already has.

On the left the doodle stands on the pet shop's adoption board, turning on
the paw buttons, with its name, its price and the toon's jellybean jar. On
the right a board of tabs picks everything about it: its looks, its traits
(only the levels this playground sells, PetCreator), its name, typed in,
and the toon accessories it wears (PetAccessories). Restyling only offers
the name and the accessories.

The screen sends doneEvent with None when cancelled, or with
('build', dna, traitLevels, name, accessories) or
('restyle', name, accessories) once the toon confirms.
"""

import random

from direct.directnotify import DirectNotifyGlobal
from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import LerpHprInterval
from panda3d.core import *

from toontown.hood import ZoneUtil
from toontown.pets import Pet, PetAccessories, PetCreator, PetDNA, PetNameGenerator, PetTraits
from toontown.toonbase import AndroidKeyboard, TTLocalizer, ToontownGlobals
from toontown.toontowngui import TTDialog

PURPLE = Vec4(0.45, 0.0, 0.61, 1)
DARK = Vec4(0.25, 0.1, 0.35, 1)
GOLD = Vec4(1, 1, 0.5, 1)
BOARD_GREEN = Vec4(0.6, 0.95, 0.45, 1)
TEAL = Vec4(0.42, 0.9, 0.9, 1)
PALE_TEAL = Vec4(0.75, 0.97, 0.97, 1)
PICKED = Vec4(1, 0.93, 0.45, 1)
GREY = Vec4(0.6, 0.6, 0.6, 1)
PRICE_GREEN = Vec4(0.1, 0.5, 0.1, 1)

TAB_LOOKS, TAB_TRAITS, TAB_NAME, TAB_WEAR = range(4)
TILE_COLUMNS = 4
TILE_ROWS = 3
TILES_PER_PAGE = TILE_COLUMNS * TILE_ROWS


class PetCreatorGUI(DirectFrame):
    notify = DirectNotifyGlobal.directNotify.newCategory('PetCreatorGUI')

    def __init__(self, doneEvent, restyleAvatar=None):
        DirectFrame.__init__(self, relief=None, state='normal')
        self.initialiseoptions(PetCreatorGUI)
        self.doneEvent = doneEvent
        self.restyle = restyleAvatar is not None
        self.zoneId = ZoneUtil.getCanonicalSafeZoneId(base.localAvatar.getZoneId())
        if self.zoneId not in PetCreator.getZones():
            self.zoneId = ToontownGlobals.ToontownCentral
        self.confirmDialog = None
        self.petModel = None
        self.turnIval = None
        self.tabPages = []
        self.tabButtons = []
        self.rows = {}
        self.tiles = []
        self.thumbCache = {}
        if self.restyle:
            self.dna = list(restyleAvatar.getDNA())
            self.name = restyleAvatar.getName()
            self.accessories = list(getattr(restyleAvatar, 'accessories', [])) or list(PetAccessories.NoAccessories)
            if not PetAccessories.isValid(self.accessories):
                self.accessories = list(PetAccessories.NoAccessories)
            self.traitLevels = None
        else:
            self.dna = self.__startingDNA()
            self.traitLevels = PetCreator.getDefaultLevels(self.zoneId)
            self.name = ''
            self.accessories = list(PetAccessories.NoAccessories)
        self.nameGenerator = PetNameGenerator.PetNameGenerator()
        self.wearKind = PetAccessories.HAT
        self.wearPage = {kind: 0 for kind in PetAccessories.KINDS}
        self.__loadArt()
        self.__makeStage()
        self.__makeBoard()
        if self.restyle:
            self.nameEntry.enterText(self.name)
        else:
            self.__randomName()
        self.__showPet()
        self.__refresh()
        self.__showTab(TAB_NAME if self.restyle else TAB_LOOKS)
        self.accept(localAvatar.uniqueName('moneyChange'), self.__moneyChange)
        self.accept(localAvatar.uniqueName('bankMoneyChange'), self.__moneyChange)

    # Setting up.

    def __startingDNA(self):
        bodies = PetCreator.getBodies(self.zoneId)
        dna = PetDNA.getRandomPetDNA(self.zoneId)
        dna[PetDNA.Fields['body']] = bodies[0]
        dna[PetDNA.Fields['color']] = random.choice(PetCreator.getColors(bodies[0]))
        dna[PetDNA.Fields['colorScale']] = PetDNA.ColorScales.index(1.0)
        return dna

    def __centered(self, art, name, size=None):
        # A piece of a GUI model, moved to its own middle (the pet shop's
        # pieces sit where they were drawn on their own boards), and scaled
        # so its width is size.
        wrapper = NodePath(name)
        inner = wrapper.attachNewNode('inner')
        art.find('**/' + name).copyTo(inner)
        bounds = inner.getTightBounds()
        if bounds:
            lo, hi = bounds
            inner.setPos(-(lo[0] + hi[0]) / 2.0, 0, -(lo[2] + hi[2]) / 2.0)
            if size:
                wrapper.setScale(size / max(hi[0] - lo[0], 0.001))
        wrapper.flattenStrong()
        return wrapper

    def __loadArt(self):
        self.adoptArt = loader.loadModel('phase_4/models/gui/AdoptPet')
        self.shopArt = loader.loadModel('phase_4/models/gui/PetShopInterface')
        self.nameArt = loader.loadModel('phase_4/models/gui/PetNamePanel')
        self.matArt = loader.loadModel('phase_3/models/gui/tt_m_gui_mat_mainGui')
        self.dialogGeom = DGG.getDefaultDialogGeom()

    def __makeStage(self):
        # The doodle on the adoption board.
        scale = 0.06
        self.stage = DirectFrame(parent=self, relief=None, geom=self.adoptArt.find('**/PannelUP'),
                                 geom_scale=scale, pos=(-0.73, 0, -0.8))
        self.jar = DirectFrame(parent=self.stage, relief=None, geom=self.adoptArt.find('**/Jar'), geom_scale=scale)
        self.moneyLabel = DirectLabel(parent=self.stage, relief=None, text='', text_scale=0.07,
                                      text_fg=(0.95, 0.95, 0, 1), text_shadow=(0, 0, 0, 1),
                                      text_font=ToontownGlobals.getSignFont(), pos=(0.24, 0, 0.36))
        self.titleLabel = DirectLabel(parent=self.stage, relief=None,
                                      text=TTLocalizer.PetRestyleTitle if self.restyle else TTLocalizer.PetCreatorTitle,
                                      text_scale=0.075, text_fg=Vec4(0.36, 0.94, 0.93, 1), text_shadow=(0, 0, 0, 1),
                                      text_font=ToontownGlobals.getSignFont(), pos=(-0.04, 0, 1.2))
        self.nameLabel = DirectLabel(parent=self.stage, relief=None, text='', text_scale=0.065,
                                     text_fg=PURPLE, text_shadow=(1, 1, 1, 1), pos=(-0.07, 0, 1.06))
        self.costLabel = DirectLabel(parent=self.stage, relief=None, text='', text_scale=0.045,
                                     text_fg=PURPLE, text_shadow=(1, 1, 1, 1), text_wordwrap=14,
                                     pos=(-0.04, 0, 0.12))
        self.petView = self.stage.attachNewNode('petView')
        self.petView.setPos(-0.12, 0, 0.22)
        self.petTurn = self.petView.attachNewNode('petTurn')
        self.petTurn.setH(200)
        okArt = (self.adoptArt.find('**/CheckButtonUp'), self.adoptArt.find('**/CheckButtonDown'),
                 self.adoptArt.find('**/CheckButtonRollover'), self.adoptArt.find('**/CheckButtonUp'))
        cancelArt = (self.adoptArt.find('**/CancelButtonUp'), self.adoptArt.find('**/CancelButtonDown'),
                     self.adoptArt.find('**/CancelRollover'))
        self.cancelButton = DirectButton(parent=self.stage, relief=None, image=cancelArt,
                                         geom=self.adoptArt.find('**/CancelIcon'), scale=scale,
                                         text=('', TTLocalizer.PetshopGoBack), text_pos=(-5.8, 4.4), text_scale=0.7,
                                         pressEffect=False, command=self.__cancel)
        self.okButton = DirectButton(parent=self.stage, relief=None, image=okArt, image3_color=GREY,
                                     geom=self.adoptArt.find('**/CheckIcon'), geom3_color=GREY, scale=scale,
                                     text=('', TTLocalizer.PetCreatorSave if self.restyle else TTLocalizer.PetshopAdopt),
                                     text_pos=(5.8, 4.4), text_scale=0.7, pressEffect=False, command=self.__confirm)
        pawL = (self.shopArt.find('**/Paw1Up'), self.shopArt.find('**/Paw1Down'), self.shopArt.find('**/Paw1Rollover'))
        pawR = (self.shopArt.find('**/Paw2Up'), self.shopArt.find('**/Paw2Down'), self.shopArt.find('**/Paw2Rollover'))
        for art, arrow, x, turn in ((pawL, 'Arrow1', -0.47, -45), (pawR, 'Arrow2', 0.33, 45)):
            paw = DirectButton(parent=self.stage, relief=None, image=art, geom=self.shopArt.find('**/' + arrow),
                               scale=0.085, pos=(x, 0, 0.55), pressEffect=False, command=self.__turnPet,
                               extraArgs=[turn])
            # The shop's paws were placed for its own board; this puts the
            # paw (and its arrow) where we want it.
            bounds = paw.getBounds()
            paw.setPos(paw, -(bounds[0] + bounds[1]) / 2.0, 0, -(bounds[2] + bounds[3]) / 2.0)

    def __makeBoard(self):
        # The board of choices on the right.
        self.board = DirectFrame(parent=self, relief=None, image=self.dialogGeom, image_color=BOARD_GREEN,
                                 image_scale=(1.27, 1, 1.6), pos=(0.68, 0, -0.03))
        inner = DirectFrame(parent=self.board, relief=None, image=self.dialogGeom, image_color=PALE_TEAL,
                            image_scale=(1.17, 1, 1.32), pos=(0, 0, -0.1))
        tabs = (TAB_NAME, TAB_WEAR) if self.restyle else (TAB_LOOKS, TAB_TRAITS, TAB_NAME, TAB_WEAR)
        tabArt = tuple(self.__centered(self.nameArt, name, 0.27) for name in
                       ('SubmitUpButton', 'SubmitDownButton', 'SubmitRolloverButton', 'SubmitUpButton'))
        width = 0.29
        left = -width * (len(tabs) - 1) / 2.0
        for i in range(4):
            self.tabPages.append(None)
            self.tabButtons.append(None)
        for n, tab in enumerate(tabs):
            button = DirectButton(parent=self.board, relief=None, image=tabArt,
                                  text=TTLocalizer.PetCreatorTabs[tab], text_scale=0.05, text_pos=(0, -0.015),
                                  text_fg=PURPLE, pos=(left + n * width, 0, 0.67), pressEffect=False,
                                  command=self.__showTab, extraArgs=[tab])
            self.tabButtons[tab] = button
            page = DirectFrame(parent=self.board, relief=None)
            page.hide()
            self.tabPages[tab] = page
        if not self.restyle:
            self.__makeLooksPage(self.tabPages[TAB_LOOKS])
            self.__makeTraitsPage(self.tabPages[TAB_TRAITS])
        self.__makeNamePage(self.tabPages[TAB_NAME])
        self.__makeWearPage(self.tabPages[TAB_WEAR])

    def __makeRow(self, page, key, label, z, scale, changer, spread=0.215):
        arrowArt = (self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDown'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDisabled'))
        row = DirectFrame(parent=page, relief=None, pos=(0, 0, z))
        DirectLabel(parent=row, relief=None, text=label, text_scale=scale, text_align=TextNode.ALeft,
                    text_fg=DARK, pos=(-0.56, 0, -scale * 0.35))
        left = DirectButton(parent=row, relief=None, image=arrowArt, image_scale=(0.55, 1, 0.55),
                            pos=(0.115 - spread, 0, 0), pressEffect=False, command=changer, extraArgs=[-1])
        right = DirectButton(parent=row, relief=None, image=arrowArt, image_scale=(-0.55, 1, 0.55),
                             pos=(0.115 + spread, 0, 0), pressEffect=False, command=changer, extraArgs=[1])
        value = DirectLabel(parent=row, relief=None, text='', text_scale=scale, text_fg=PURPLE,
                            pos=(0.115, 0, -scale * 0.35))
        price = DirectLabel(parent=row, relief=None, text='', text_scale=scale * 0.9, text_align=TextNode.ARight,
                            text_fg=PRICE_GREEN, pos=(0.57, 0, -scale * 0.35))
        self.rows[key] = (row, value, price, left, right)
        return row

    def __makeLooksPage(self, page):
        rows = (('body', TTLocalizer.PetCreatorBody), ('color', TTLocalizer.PetCreatorColor),
                ('colorScale', TTLocalizer.PetCreatorShade), ('eyes', TTLocalizer.PetCreatorEyes),
                ('gender', TTLocalizer.PetCreatorGender), ('head', TTLocalizer.PetCreatorHead),
                ('ears', TTLocalizer.PetCreatorEars), ('nose', TTLocalizer.PetCreatorNose),
                ('tail', TTLocalizer.PetCreatorTail))
        z = 0.5
        for field, label in rows:
            self.__makeRow(page, field, label, z, 0.055, lambda step, field=field: self.__changeLook(field, step))
            z -= 0.135
        swatchRow = self.rows['color'][0]
        self.swatch = DirectFrame(parent=swatchRow, relief=DGG.SUNKEN, borderWidth=(0.01, 0.01),
                                  frameSize=(-0.035, 0.035, -0.035, 0.035), pos=(-0.2, 0, 0))

    def __makeTraitsPage(self, page):
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorTraitsHelp, text_scale=0.04,
                    text_fg=DARK, text_wordwrap=27, pos=(0, 0, 0.53))
        z = 0.42
        for i, name in enumerate(PetTraits.getTraitNames()):
            self.__makeRow(page, ('trait', i), TTLocalizer.PetCreatorTraitNames[name], z, 0.04,
                           lambda step, i=i: self.__changeTrait(i, step), spread=0.27)
            z -= 0.087

    def __makeNamePage(self, page):
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorNameHelp, text_scale=0.055,
                    text_fg=DARK, pos=(0, 0, 0.35))
        # The entry's own units are its text's: 12 letters wide.
        self.nameEntry = DirectEntry(parent=page, relief=None, image=self.dialogGeom, image_color=Vec4(1, 1, 1, 1),
                                     image_scale=(12.6, 1, 2.0), image_pos=(6.0, 0, 0.3), scale=0.07,
                                     pos=(-0.42, 0, 0.13), width=12, numLines=1, text_fg=PURPLE, focus=0,
                                     cursorKeys=1, initialText='', command=self.__nameEntered,
                                     focusOutCommand=self.__nameTyped)
        self.nameEntry.bind(DGG.TYPE, self.__nameTyped)
        self.nameEntry.bind(DGG.ERASE, self.__nameTyped)
        if AndroidKeyboard.available():
            self.nameEntry.bind(DGG.B1PRESS, self.__askAndroidName)
        randomArt = tuple(self.__centered(self.nameArt, name, 0.3) for name in
                          ('RandomUpButton', 'RandomDownButton', 'RandomRolloverButton'))
        DirectButton(parent=page, relief=None, image=randomArt,
                     text=TTLocalizer.PetCreatorRandomName, text_scale=0.05, text_pos=(0, -0.015),
                     text_fg=GOLD, pos=(0, 0, -0.1), pressEffect=False, command=self.__randomName)
        self.nameWarning = DirectLabel(parent=page, relief=None, text='', text_scale=0.045, text_fg=Vec4(0.8, 0, 0, 1),
                                       text_wordwrap=24, pos=(0, 0, -0.3))

    def __makeWearPage(self, page):
        kindArt = tuple(self.__centered(self.nameArt, name, 0.24) for name in
                        ('SubmitUpButton', 'SubmitDownButton', 'SubmitRolloverButton'))
        self.kindButtons = {}
        for n, (kind, label) in enumerate(((PetAccessories.HAT, TTLocalizer.PetCreatorHat),
                                           (PetAccessories.GLASSES, TTLocalizer.PetCreatorGlasses),
                                           (PetAccessories.BACKPACK, TTLocalizer.PetCreatorBackpack))):
            self.kindButtons[kind] = DirectButton(parent=page, relief=None, image=kindArt,
                                                  text=label, text_scale=0.045,
                                                  text_pos=(0, -0.013), text_fg=PURPLE,
                                                  pos=(-0.33 + n * 0.33, 0, 0.53), pressEffect=False,
                                                  command=self.__showWearKind, extraArgs=[kind])
        for i in range(TILES_PER_PAGE):
            row, column = divmod(i, TILE_COLUMNS)
            tile = DirectButton(parent=page, relief=None, image=self.dialogGeom, image_scale=(0.24, 1, 0.24),
                                image_color=TEAL, text='', text_scale=0.04, text_fg=PURPLE,
                                pos=(-0.405 + column * 0.27, 0, 0.3 - row * 0.27), pressEffect=False,
                                command=self.__pickTile, extraArgs=[i])
            tile.thumb = tile.attachNewNode('thumb')
            self.tiles.append(tile)
        arrowArt = (self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDown'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDisabled'))
        self.pageLeft = DirectButton(parent=page, relief=None, image=arrowArt, image_scale=(0.6, 1, 0.6),
                                     pos=(-0.25, 0, -0.52), pressEffect=False, command=self.__turnWearPage,
                                     extraArgs=[-1])
        self.pageRight = DirectButton(parent=page, relief=None, image=arrowArt, image_scale=(-0.6, 1, 0.6),
                                      pos=(0.25, 0, -0.52), pressEffect=False, command=self.__turnWearPage,
                                      extraArgs=[1])
        self.pageLabel = DirectLabel(parent=page, relief=None, text='', text_scale=0.05, text_fg=PURPLE,
                                     pos=(0, 0, -0.535))
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorWearHelp, text_scale=0.04,
                    text_fg=DARK, pos=(0, 0, -0.66))

    # The doodle.

    def __showPet(self):
        if self.petModel:
            self.petModel.delete()
        self.petModel = Pet.Pet(forGui=1)
        self.petModel.setDNA(list(self.dna))
        self.petModel.getGeomNode().setDepthWrite(1)
        self.petModel.getGeomNode().setDepthTest(1)
        self.petModel.pose('neutral', 0)
        # Fitted by its body alone, so the doodle stays the same size
        # whatever it wears; it stands on the board's floor.
        lo, hi = self.petModel.getGeomNode().getTightBounds()
        scale = 0.6 / max(hi[2] - lo[2], 0.001)
        self.petModel.setScale(scale)
        self.petModel.setPos(-(lo[0] + hi[0]) / 2.0 * scale, -(lo[1] + hi[1]) / 2.0 * scale, -lo[2] * scale)
        self.petModel.reparentTo(self.petTurn)
        self.petModel.enterNeutralHappy()
        self.petModel.startBlink()
        self.petModel.setAccessoriesLook(self.accessories)

    def __turnPet(self, turn):
        if self.turnIval:
            self.turnIval.finish()
        self.turnIval = LerpHprInterval(self.petTurn, 0.35, (self.petTurn.getH() + turn, 0, 0),
                                        blendType='easeInOut')
        self.turnIval.start()

    # Looks.

    def __lookChoices(self, field):
        body = self.dna[PetDNA.Fields['body']]
        if field == 'body':
            return PetCreator.getBodies(self.zoneId)
        if field == 'color':
            return PetCreator.getColors(body)
        if field == 'colorScale':
            return list(range(len(PetDNA.ColorScales)))
        if field == 'eyes':
            return list(range(len(PetDNA.PetEyeColors)))
        if field == 'gender':
            return list(PetDNA.PetGenders)
        parts = {'head': PetDNA.HeadParts, 'ears': PetDNA.EarParts, 'nose': PetDNA.NoseParts,
                 'tail': PetDNA.TailParts}[field]
        return list(range(-1, len(parts)))

    def __lookName(self, field, value):
        if field == 'body':
            return TTLocalizer.PetCreatorBodyNames[PetDNA.BodyTypes[value]]
        if field == 'color':
            return '%d' % (PetCreator.getColors(self.dna[PetDNA.Fields['body']]).index(value) + 1)
        if field == 'colorScale':
            return '%d' % (value + 1)
        if field == 'eyes':
            return TTLocalizer.PetCreatorEyeNames[value]
        if field == 'gender':
            return TTLocalizer.PetCreatorGenders[value]
        if value == -1:
            return TTLocalizer.PetCreatorNone
        names = {'head': TTLocalizer.PetCreatorHeadNames, 'ears': TTLocalizer.PetCreatorEarNames,
                 'nose': TTLocalizer.PetCreatorNoseNames, 'tail': TTLocalizer.PetCreatorTailNames}[field]
        return names[value]

    def __changeLook(self, field, step):
        choices = self.__lookChoices(field)
        index = PetDNA.Fields[field]
        current = self.dna[index]
        i = choices.index(current) if current in choices else 0
        self.dna[index] = choices[(i + step) % len(choices)]
        if field == 'body':
            colors = PetCreator.getColors(self.dna[index])
            if self.dna[PetDNA.Fields['color']] not in colors:
                self.dna[PetDNA.Fields['color']] = colors[0]
        self.__showPet()
        self.__refresh()

    # Traits.

    def __changeTrait(self, traitIndex, step):
        levels = sorted(PetCreator.getTraitLevels(traitIndex, self.zoneId).keys())
        i = levels.index(self.traitLevels[traitIndex])
        i = max(0, min(len(levels) - 1, i + step))
        self.traitLevels[traitIndex] = levels[i]
        self.__refresh()

    # The name.

    def __randomName(self):
        gender = self.dna[PetDNA.Fields['gender']]
        names = self.nameGenerator.boyFirsts if gender == 1 else self.nameGenerator.girlFirsts
        names = names + self.nameGenerator.neutralFirsts
        names = [name for name in names if PetCreator.isValidName(name)]
        self.name = random.choice(names)
        self.nameEntry.enterText(self.name)
        self.__refresh()

    def __nameTyped(self, *args):
        self.name = self.nameEntry.get(plain=True)
        self.__refresh()

    def __nameEntered(self, text):
        self.nameEntry['focus'] = 0
        self.__nameTyped()

    def __askAndroidName(self, *args):
        AndroidKeyboard.start(self.nameEntry, PetCreator.MaxNameLength, onSend=self.__nameEntered,
                              onClose=lambda text: self.__nameTyped(), onChange=lambda text: self.__nameTyped())

    # Accessories.

    def __showWearKind(self, kind):
        self.wearKind = kind
        self.__refreshWear()

    def __turnWearPage(self, step):
        pages = self.__numWearPages()
        self.wearPage[self.wearKind] = (self.wearPage[self.wearKind] + step) % pages
        self.__refreshWear()

    def __numWearPages(self):
        return (len(PetAccessories.getChoices(self.wearKind)) + TILES_PER_PAGE - 1) // TILES_PER_PAGE

    def __pickTile(self, i):
        choices = PetAccessories.getChoices(self.wearKind)
        n = self.wearPage[self.wearKind] * TILES_PER_PAGE + i
        if n >= len(choices):
            return
        self.accessories = PetAccessories.setPair(self.accessories, self.wearKind, choices[n])
        if self.petModel:
            self.petModel.setAccessoriesLook(self.accessories)
        self.__refreshWear()

    def __makeThumb(self, kind, model, texture):
        geom = loader.loadModel(PetAccessories.modelList(kind)[model], okMissing=True)
        if not geom:
            return None
        if texture:
            tex = loader.loadTexture(PetAccessories.textureList(kind)[texture], okMissing=True)
            if tex:
                geom.setTexture(tex, 1)
        pos, hpr, scale = PetAccessories.getPlacement(kind, model)
        # Shown from its front, as the doodle wears it, a little from above.
        holder = NodePath('thumb')
        geom.reparentTo(holder)
        geom.setHpr(hpr[0] + 180 + (200 if kind == PetAccessories.BACKPACK else 25), 0, 0)
        holder.setP(-20 if kind == PetAccessories.HAT else -8)
        bounds = holder.getTightBounds()
        if not bounds:
            return None
        lo, hi = bounds
        size = max(hi[0] - lo[0], hi[2] - lo[2], 0.001)
        top = NodePath('thumbTop')
        holder.reparentTo(top)
        holder.setScale(0.165 / size)
        center = (lo + hi) / 2.0
        holder.setPos(-center[0] * 0.165 / size, 0, -center[2] * 0.165 / size)
        top.setDepthWrite(1)
        top.setDepthTest(1)
        return top

    def __refreshWear(self):
        choices = PetAccessories.getChoices(self.wearKind)
        page = self.wearPage[self.wearKind]
        picked = PetAccessories.getPair(self.accessories, self.wearKind)
        for kind, button in self.kindButtons.items():
            button['image_color'] = Vec4(1, 1, 1, 1) if kind == self.wearKind else GREY
        for i, tile in enumerate(self.tiles):
            tile.thumb.getChildren().detach()
            n = page * TILES_PER_PAGE + i
            if n >= len(choices):
                tile.hide()
                continue
            tile.show()
            pair = choices[n]
            tile['image_color'] = PICKED if pair == picked else TEAL
            if pair == (0, 0):
                tile['text'] = TTLocalizer.PetCreatorNone
                continue
            tile['text'] = ''
            key = (self.wearKind,) + pair
            if key not in self.thumbCache:
                self.thumbCache[key] = self.__makeThumb(self.wearKind, *pair)
            thumb = self.thumbCache[key]
            if thumb:
                thumb.reparentTo(tile.thumb)
        self.pageLabel['text'] = TTLocalizer.PetCreatorPage % (page + 1, self.__numWearPages())

    # Showing it all.

    def __showTab(self, tab):
        for i, page in enumerate(self.tabPages):
            if page is None:
                continue
            if i == tab:
                page.show()
                self.tabButtons[i]['image_color'] = Vec4(1, 1, 1, 1)
                self.tabButtons[i].setScale(1.08)
            else:
                page.hide()
                self.tabButtons[i]['image_color'] = GREY
                self.tabButtons[i].setScale(1.0)
        self.curTab = tab
        if tab == TAB_WEAR:
            self.__refreshWear()

    def getCost(self):
        if self.restyle:
            return 0
        return PetCreator.getCost(self.dna[PetDNA.Fields['body']], self.traitLevels, self.zoneId)

    def __costWith(self, body=None, traitIndex=None, level=None):
        levels = list(self.traitLevels)
        if traitIndex is not None:
            levels[traitIndex] = level
        if body is None:
            body = self.dna[PetDNA.Fields['body']]
        return PetCreator.getCost(body, levels, self.zoneId)

    def __setPrice(self, label, extra):
        if extra is None:
            label['text'] = TTLocalizer.PetCreatorFree
        elif extra > 0:
            label['text'] = TTLocalizer.PetCreatorPlus % extra
        else:
            label['text'] = ''

    def __refresh(self):
        name = PetCreator.cleanName(self.name)
        self.nameLabel['text'] = name
        cost = self.getCost()
        money = base.localAvatar.getTotalMoney()
        self.moneyLabel['text'] = str(money)
        if self.restyle:
            self.costLabel['text'] = TTLocalizer.PetCreatorRestyleCost
        else:
            self.costLabel['text'] = TTLocalizer.PetCreatorCost % cost
            body = self.dna[PetDNA.Fields['body']]
            for field in ('body', 'color', 'colorScale', 'eyes', 'gender', 'head', 'ears', 'nose', 'tail'):
                row, value, price, left, right = self.rows[field]
                value['text'] = self.__lookName(field, self.dna[PetDNA.Fields[field]])
                if field == 'body':
                    cheapest = min(self.__costWith(body=b) for b in PetCreator.getBodies(self.zoneId))
                    self.__setPrice(price, cost - cheapest)
                else:
                    self.__setPrice(price, None)
            color = PetDNA.AllPetColors[self.dna[PetDNA.Fields['color']]]
            self.swatch['frameColor'] = color
            for i in range(PetTraits.PetTraits.NumTraits):
                row, value, price, left, right = self.rows[('trait', i)]
                levels = sorted(PetCreator.getTraitLevels(i, self.zoneId).keys())
                level = self.traitLevels[i]
                value['text'] = PetCreator.getTraitDescription(i, level)
                if PetTraits.PetTraits.TraitDescs[i][2]:
                    cheapest = min(self.__costWith(traitIndex=i, level=l) for l in levels)
                    self.__setPrice(price, cost - cheapest)
                else:
                    # This trait isn't counted in a doodle's worth.
                    self.__setPrice(price, None)
                left['state'] = DGG.NORMAL if level != levels[0] else DGG.DISABLED
                right['state'] = DGG.NORMAL if level != levels[-1] else DGG.DISABLED
        nameOk = PetCreator.isValidName(name)
        self.nameWarning['text'] = '' if nameOk else TTLocalizer.PetCreatorNameBad % PetCreator.MaxNameLength
        if nameOk and cost <= money:
            self.okButton['state'] = DGG.NORMAL
        else:
            self.okButton['state'] = DGG.DISABLED

    def __moneyChange(self, money):
        self.__refresh()

    # Finishing.

    def __confirm(self):
        name = PetCreator.cleanName(self.name)
        if self.restyle:
            text = TTLocalizer.PetCreatorRestyleConfirm % name
        else:
            text = TTLocalizer.PetCreatorAdoptConfirm % (name, self.getCost())
            if base.localAvatar.hasPet():
                text += '\n\n' + TTLocalizer.PetCreatorReplaceWarning
        self.__closeConfirm()
        self.confirmDialog = TTDialog.TTDialog(parent=aspect2dp, text=text, style=TTDialog.YesNo,
                                               text_wordwrap=15, command=self.__confirmed)
        self.confirmDialog.show()

    def __closeConfirm(self):
        if self.confirmDialog:
            self.confirmDialog.cleanup()
            self.confirmDialog = None

    def __confirmed(self, value):
        self.__closeConfirm()
        if value <= 0:
            return
        name = PetCreator.cleanName(self.name)
        if self.restyle:
            messenger.send(self.doneEvent, [('restyle', name, list(self.accessories))])
        else:
            messenger.send(self.doneEvent, [('build', list(self.dna), [int(level) for level in self.traitLevels],
                                             name, list(self.accessories))])

    def __cancel(self):
        messenger.send(self.doneEvent, [None])

    def destroy(self):
        self.ignoreAll()
        AndroidKeyboard.stop(quiet=True)
        self.__closeConfirm()
        if self.turnIval:
            self.turnIval.finish()
            self.turnIval = None
        if self.petModel:
            self.petModel.delete()
            self.petModel = None
        for thumb in self.thumbCache.values():
            if thumb:
                thumb.removeNode()
        self.thumbCache = {}
        for art in (self.adoptArt, self.shopArt, self.nameArt, self.matArt):
            art.removeNode()
        DirectFrame.destroy(self)
