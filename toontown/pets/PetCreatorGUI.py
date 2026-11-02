"""
The pet shop's Build a Doodle screen, and its Restyle screen for the doodle
a toon already has.

On the left the doodle stands on the pet shop's adoption board, turning on
the paw buttons, with its name, its price and the toon's jellybean jar. On
the right a board of tabs picks everything about it: its looks, its traits
(only the levels this playground sells, PetCreator), its name, typed in or
picked from the shop's own lists of names, and the toon accessories it wears
(PetAccessories), each at the catalog's price. Restyling only offers the
name, which is free, and the accessories, where only new ones cost
jellybeans.

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

# The two boards sit side by side, the same height, centred on the screen.
BOARD_Z = -0.03
BOARD_HEIGHT = 1.6
STAGE_WIDTH = 0.95
BOARD_WIDTH = 1.3
BOARD_GAP = 0.08
STAGE_X = -(STAGE_WIDTH + BOARD_GAP + BOARD_WIDTH) / 2.0 + STAGE_WIDTH / 2.0
BOARD_X = STAGE_X + STAGE_WIDTH / 2.0 + BOARD_GAP + BOARD_WIDTH / 2.0
PANEL_WIDTH = 0.82
SUM_X = 0.35
# The pages: their middle, help line and the middle of their rows.
PAGE_Z = -0.08
HELP_Z = 0.58
ROWS_MID = -0.06
# The columns of every row.
COL_LABEL = -0.55
COL_LEFT = -0.17
COL_RIGHT = 0.3
COL_PRICE = 0.55
TILE_COLUMNS = 4
TILE_ROWS = 3
TILES_PER_PAGE = TILE_COLUMNS * TILE_ROWS
THUMB_SIZE = 0.15
# The lists of names: letters on the left, the names that start with the
# picked letter on the right.
LIST_Z = -0.1
LIST_HEIGHT = 0.68
LIST_ROWS = 6
LIST_ROW_HEIGHT = 0.068
LETTERS_X = -0.42
LETTERS_WIDTH = 0.22
NAMES_X = 0.13
NAMES_WIDTH = 0.66


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
            # What it wears now is the doodle's already; only new ones cost.
            self.wearing = list(self.accessories)
            self.traitLevels = None
        else:
            self.dna = self.__startingDNA()
            self.traitLevels = PetCreator.getDefaultLevels(self.zoneId)
            self.name = ''
            self.accessories = list(PetAccessories.NoAccessories)
            self.wearing = list(PetAccessories.NoAccessories)
        self.letterList = None
        self.nameList = None
        self.listGender = None
        self.listLetter = None
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
        # The left board: the doodle, turning on the paw buttons, and what it
        # costs, with the toon's jellybeans.
        self.stage = DirectFrame(parent=self, relief=None, image=self.dialogGeom, image_color=BOARD_GREEN,
                                 image_scale=(STAGE_WIDTH, 1, BOARD_HEIGHT), pos=(STAGE_X, 0, BOARD_Z))
        title = TTLocalizer.PetRestyleTitle if self.restyle else TTLocalizer.PetCreatorTitle
        self.titleLabel = DirectLabel(parent=self.stage, relief=None, text=title,
                                      text_scale=0.058 if self.restyle else 0.07,
                                      text_fg=Vec4(0.36, 0.94, 0.93, 1), text_shadow=(0, 0, 0, 1),
                                      text_font=ToontownGlobals.getSignFont(), pos=(0, 0, 0.69))
        self.nameLabel = DirectLabel(parent=self.stage, relief=None, text='', text_scale=0.065,
                                     text_fg=PURPLE, text_shadow=(1, 1, 1, 1), pos=(0, 0, 0.585))
        # The doodle's window.
        DirectFrame(parent=self.stage, relief=None, image=self.dialogGeom, image_color=PALE_TEAL,
                    image_scale=(PANEL_WIDTH, 1, 0.64), pos=(0, 0, 0.215))
        self.petView = self.stage.attachNewNode('petView')
        self.petView.setPos(0, 0, -0.035)
        self.petTurn = self.petView.attachNewNode('petTurn')
        self.petTurn.setH(200)
        pawL = (self.shopArt.find('**/Paw1Up'), self.shopArt.find('**/Paw1Down'), self.shopArt.find('**/Paw1Rollover'))
        pawR = (self.shopArt.find('**/Paw2Up'), self.shopArt.find('**/Paw2Down'), self.shopArt.find('**/Paw2Rollover'))
        for art, arrow, x, turn in ((pawL, 'Arrow1', -0.31, -45), (pawR, 'Arrow2', 0.31, 45)):
            paw = DirectButton(parent=self.stage, relief=None, image=art, geom=self.shopArt.find('**/' + arrow),
                               scale=0.075, pos=(x, 0, 0.215), pressEffect=False, command=self.__turnPet,
                               extraArgs=[turn])
            # The shop's paws were placed for its own board; this puts the
            # paw (and its arrow) where we want it.
            bounds = paw.getBounds()
            paw.setPos(paw, -(bounds[0] + bounds[1]) / 2.0, 0, -(bounds[2] + bounds[3]) / 2.0)
        # The price, adding up as the doodle changes.
        DirectFrame(parent=self.stage, relief=None, image=self.dialogGeom, image_color=PALE_TEAL,
                    image_scale=(PANEL_WIDTH, 1, 0.42), pos=(0, 0, -0.355))
        self.sumLines = []
        for z, size in ((-0.19, 0.044), (-0.248, 0.044), (-0.306, 0.044), (-0.405, 0.06), (-0.495, 0.045)):
            left = DirectLabel(parent=self.stage, relief=None, text='', text_scale=size, text_fg=DARK,
                               text_align=TextNode.ALeft, pos=(-SUM_X, 0, z))
            right = DirectLabel(parent=self.stage, relief=None, text='', text_scale=size, text_fg=DARK,
                                text_align=TextNode.ARight, pos=(SUM_X, 0, z))
            self.sumLines.append((left, right))
        self.sumRule = DirectFrame(parent=self.stage, relief=DGG.FLAT, frameColor=DARK,
                                   frameSize=(-SUM_X, SUM_X, -0.003, 0.003), pos=(0, 0, -0.345))
        self.sumNote = DirectLabel(parent=self.stage, relief=None, text='', text_scale=0.06, text_fg=PURPLE,
                                   text_wordwrap=12, pos=(0, 0, -0.34))
        # Going back, and adopting (or saving).
        scale = 0.06
        okArt = (self.adoptArt.find('**/CheckButtonUp'), self.adoptArt.find('**/CheckButtonDown'),
                 self.adoptArt.find('**/CheckButtonRollover'), self.adoptArt.find('**/CheckButtonUp'))
        cancelArt = (self.adoptArt.find('**/CancelButtonUp'), self.adoptArt.find('**/CancelButtonDown'),
                     self.adoptArt.find('**/CancelRollover'))
        self.cancelButton = self.__placed(DirectButton(parent=self.stage, relief=None, image=cancelArt,
                                                       geom=self.adoptArt.find('**/CancelIcon'), scale=scale,
                                                       pressEffect=False, command=self.__cancel), -0.2, -0.655)
        self.okButton = self.__placed(DirectButton(parent=self.stage, relief=None, image=okArt, image3_color=GREY,
                                                   geom=self.adoptArt.find('**/CheckIcon'), geom3_color=GREY,
                                                   scale=scale, pressEffect=False, command=self.__confirm),
                                      0.2, -0.655)
        for x, text in ((-0.2, TTLocalizer.PetshopGoBack),
                        (0.2, TTLocalizer.PetCreatorSave if self.restyle else TTLocalizer.PetshopAdopt)):
            DirectLabel(parent=self.stage, relief=None, text=text, text_scale=0.045, text_fg=DARK,
                        pos=(x, 0, -0.77))

    def __placed(self, button, x, z):
        # The adoption board's buttons were drawn in place on that board;
        # this moves one so its middle is at (x, z).
        bounds = button.getBounds()
        button.setPos(button, -(bounds[0] + bounds[1]) / 2.0, 0, -(bounds[2] + bounds[3]) / 2.0)
        button.setPos(button.getPos() + Point3(x, 0, z))
        return button

    def __makeBoard(self):
        # The board of choices on the right.
        self.board = DirectFrame(parent=self, relief=None, image=self.dialogGeom, image_color=BOARD_GREEN,
                                 image_scale=(BOARD_WIDTH, 1, BOARD_HEIGHT), pos=(BOARD_X, 0, BOARD_Z))
        DirectFrame(parent=self.board, relief=None, image=self.dialogGeom, image_color=PALE_TEAL,
                    image_scale=(BOARD_WIDTH - 0.1, 1, 1.36), pos=(0, 0, PAGE_Z))
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
                                  text_fg=PURPLE, pos=(left + n * width, 0, 0.7), pressEffect=False,
                                  command=self.__showTab, extraArgs=[tab])
            self.tabButtons[tab] = button
            page = DirectFrame(parent=self.board, relief=None, pos=(0, 0, PAGE_Z))
            page.hide()
            self.tabPages[tab] = page
        if not self.restyle:
            self.__makeLooksPage(self.tabPages[TAB_LOOKS])
            self.__makeTraitsPage(self.tabPages[TAB_TRAITS])
        self.__makeNamePage(self.tabPages[TAB_NAME])
        self.__makeWearPage(self.tabPages[TAB_WEAR])

    def __makeRow(self, page, key, label, z, scale, changer):
        # One choice: its name, the arrows round what it is now, and what it
        # adds to the price. Every row lines up on the same columns.
        arrowArt = (self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDown'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDisabled'))
        row = DirectFrame(parent=page, relief=None, pos=(0, 0, z))
        textZ = -scale * 0.35
        DirectLabel(parent=row, relief=None, text=label, text_scale=scale, text_align=TextNode.ALeft,
                    text_fg=DARK, pos=(COL_LABEL, 0, textZ))
        left = DirectButton(parent=row, relief=None, image=arrowArt, image_scale=(0.5, 1, 0.5),
                            pos=(COL_LEFT, 0, 0), pressEffect=False, command=changer, extraArgs=[-1])
        right = DirectButton(parent=row, relief=None, image=arrowArt, image_scale=(-0.5, 1, 0.5),
                             pos=(COL_RIGHT, 0, 0), pressEffect=False, command=changer, extraArgs=[1])
        value = DirectLabel(parent=row, relief=None, text='', text_scale=scale, text_fg=PURPLE,
                            pos=((COL_LEFT + COL_RIGHT) / 2.0, 0, textZ))
        price = DirectLabel(parent=row, relief=None, text='', text_scale=scale, text_align=TextNode.ARight,
                            text_fg=PRICE_GREEN, pos=(COL_PRICE, 0, textZ))
        self.rows[key] = (row, value, price, left, right)
        return row

    def __makeLooksPage(self, page):
        rows = (('body', TTLocalizer.PetCreatorBody), ('color', TTLocalizer.PetCreatorColor),
                ('colorScale', TTLocalizer.PetCreatorShade), ('eyes', TTLocalizer.PetCreatorEyes),
                ('gender', TTLocalizer.PetCreatorGender), ('head', TTLocalizer.PetCreatorHead),
                ('ears', TTLocalizer.PetCreatorEars), ('nose', TTLocalizer.PetCreatorNose),
                ('tail', TTLocalizer.PetCreatorTail))
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorLooksHelp, text_scale=0.042,
                    text_fg=DARK, pos=(0, 0, HELP_Z))
        step = 0.13
        z = ROWS_MID + step * (len(rows) - 1) / 2.0
        for field, label in rows:
            self.__makeRow(page, field, label, z, 0.052, lambda step, field=field: self.__changeLook(field, step))
            z -= step
        swatchRow = self.rows['color'][0]
        self.swatch = DirectFrame(parent=swatchRow, relief=DGG.SUNKEN, borderWidth=(0.008, 0.008),
                                  frameSize=(-0.03, 0.03, -0.03, 0.03), pos=(COL_LEFT - 0.1, 0, 0))

    def __makeTraitsPage(self, page):
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorTraitsHelp, text_scale=0.042,
                    text_fg=DARK, pos=(0, 0, HELP_Z))
        names = PetTraits.getTraitNames()
        step = 0.09
        z = ROWS_MID + step * (len(names) - 1) / 2.0
        for i, name in enumerate(names):
            self.__makeRow(page, ('trait', i), TTLocalizer.PetCreatorTraitNames[name], z, 0.042,
                           lambda step, i=i: self.__changeTrait(i, step))
            z -= step

    def __makeNamePage(self, page):
        DirectLabel(parent=page, relief=None, text=TTLocalizer.PetCreatorNameHelp, text_scale=0.05,
                    text_fg=DARK, pos=(0, 0, 0.565))
        # The entry's own units are its text's: 12 letters wide.
        self.nameEntry = DirectEntry(parent=page, relief=None, image=self.dialogGeom, image_color=Vec4(1, 1, 1, 1),
                                     image_scale=(12.6, 1, 2.0), image_pos=(6.0, 0, 0.3), scale=0.07,
                                     pos=(-0.42, 0, 0.405), width=12, numLines=1, text_fg=PURPLE, focus=0,
                                     cursorKeys=1, initialText='', command=self.__nameEntered,
                                     focusOutCommand=self.__nameTyped)
        self.nameEntry.bind(DGG.TYPE, self.__nameTyped)
        self.nameEntry.bind(DGG.ERASE, self.__nameTyped)
        if AndroidKeyboard.available():
            self.nameEntry.bind(DGG.B1PRESS, self.__askAndroidName)
        # The shop's own names, as its old name picker had them.
        self.namePage = page
        for x, width in ((LETTERS_X, LETTERS_WIDTH), (NAMES_X, NAMES_WIDTH)):
            DirectFrame(parent=page, relief=None, image=self.dialogGeom, image_color=Vec4(1, 1, 1, 1),
                        image_scale=(width, 1, LIST_HEIGHT), pos=(x, 0, LIST_Z))
        randomArt = tuple(self.__centered(self.nameArt, name, 0.3) for name in
                          ('RandomUpButton', 'RandomDownButton', 'RandomRolloverButton'))
        DirectButton(parent=page, relief=None, image=randomArt,
                     text=TTLocalizer.PetCreatorRandomName, text_scale=0.05, text_pos=(0, -0.015),
                     text_fg=GOLD, pos=(0, 0, -0.55), pressEffect=False, command=self.__randomName)
        self.nameWarning = DirectLabel(parent=page, relief=None, text='', text_scale=0.04, text_fg=Vec4(0.8, 0, 0, 1),
                                       text_wordwrap=28, pos=(0, 0, 0.283))

    def __makeList(self, x, width, arrow, arrowSize, labels, command):
        # One of the name lists: its words, the picked one lit up, with the
        # shop's arrows above and below to scroll it.
        items = []
        for n, label in enumerate(labels):
            items.append(DirectButton(relief=DGG.FLAT, frameColor=Vec4(1, 1, 1, 0),
                                      frameSize=(-width / 2.0 + 0.02, width / 2.0 - 0.02, -0.02, 0.048),
                                      text=label, text_scale=0.05, text_fg=PURPLE, pressEffect=False,
                                      command=command, extraArgs=[label]))
        up = self.__centered(self.nameArt, arrow + 'Button', arrowSize)
        over = self.__centered(self.nameArt, arrow + 'Rollover', arrowSize)
        arrowArt = (up, over, over, up)
        top = LIST_Z + LIST_HEIGHT / 2.0
        bottom = LIST_Z - LIST_HEIGHT / 2.0
        middle = (LIST_ROWS - 1) * LIST_ROW_HEIGHT / 2.0
        return DirectScrolledList(parent=self.namePage, relief=None, items=items, pos=(x, 0, 0),
                                  numItemsVisible=LIST_ROWS, forceHeight=LIST_ROW_HEIGHT,
                                  itemFrame_pos=(0, 0, LIST_Z + middle - 0.016),
                                  decButton_image=arrowArt, decButton_relief=None,
                                  decButton_pos=(0, 0, top - 0.06), decButton_image3_color=GREY,
                                  incButton_image=arrowArt, incButton_relief=None,
                                  incButton_image_scale=(1, 1, -1),
                                  incButton_pos=(0, 0, bottom + 0.06), incButton_image3_color=GREY)

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
                                                  pos=((n - 1) * 0.3, 0, 0.55), pressEffect=False,
                                                  command=self.__showWearKind, extraArgs=[kind])
        gap = 0.265
        for i in range(TILES_PER_PAGE):
            row, column = divmod(i, TILE_COLUMNS)
            tile = DirectButton(parent=page, relief=None, image=self.dialogGeom, image_scale=(0.235, 1, 0.235),
                                image_color=TEAL, text='', text_scale=0.04, text_fg=PURPLE,
                                pos=((column - (TILE_COLUMNS - 1) / 2.0) * gap, 0, 0.3 - row * gap),
                                pressEffect=False, command=self.__pickTile, extraArgs=[i])
            tile.thumb = tile.attachNewNode('thumb')
            tile.thumb.setZ(0.016)
            tile.price = DirectLabel(parent=tile, relief=None, text='', text_scale=0.034, text_fg=PRICE_GREEN,
                                     pos=(0, 0, -0.098))
            self.tiles.append(tile)
        arrowArt = (self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDown'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowUp'),
                    self.matArt.find('**/tt_t_gui_mat_shuffleArrowDisabled'))
        self.pageLeft = DirectButton(parent=page, relief=None, image=arrowArt, image_scale=(0.55, 1, 0.55),
                                     pos=(-0.2, 0, -0.48), pressEffect=False, command=self.__turnWearPage,
                                     extraArgs=[-1])
        self.pageRight = DirectButton(parent=page, relief=None, image=arrowArt, image_scale=(-0.55, 1, 0.55),
                                      pos=(0.2, 0, -0.48), pressEffect=False, command=self.__turnWearPage,
                                      extraArgs=[1])
        self.pageLabel = DirectLabel(parent=page, relief=None, text='', text_scale=0.05, text_fg=PURPLE,
                                     pos=(0, 0, -0.495))
        help = TTLocalizer.PetCreatorWearHelpRestyle if self.restyle else TTLocalizer.PetCreatorWearHelp
        DirectLabel(parent=page, relief=None, text=help, text_scale=0.042,
                    text_fg=DARK, pos=(0, 0, -0.6))

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
        scale = 0.46 / max(hi[2] - lo[2], 0.001)
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

    def __allNames(self):
        gender = self.dna[PetDNA.Fields['gender']]
        names = self.nameGenerator.boyFirsts if gender == 1 else self.nameGenerator.girlFirsts
        names = names + self.nameGenerator.neutralFirsts
        return sorted(set(name for name in names if PetCreator.isValidName(name)))

    def __firstLetters(self, name):
        return name[0:TTLocalizer.PGUIcharLength]

    def __fillNameLists(self, letter=None):
        # The letters for this doodle's gender, and the names under one of
        # them. A boy and a girl have their own names (and share some).
        gender = self.dna[PetDNA.Fields['gender']]
        names = self.__allNames()
        if gender != self.listGender:
            self.listGender = gender
            if self.letterList:
                self.letterList.destroy()
            self.letters = []
            for name in names:
                if self.__firstLetters(name) not in self.letters:
                    self.letters.append(self.__firstLetters(name))
            self.letterList = self.__makeList(LETTERS_X, LETTERS_WIDTH, 'ArrowSmUp', 0.1, self.letters,
                                              self.__pickLetter)
            self.listLetter = None
        if letter is None:
            letter = self.listLetter
        if letter not in self.letters:
            letter = self.__firstLetters(PetCreator.cleanName(self.name)).upper()
            if letter not in self.letters:
                letter = self.letters[0]
        if letter != self.listLetter or not self.nameList:
            self.listLetter = letter
            if self.nameList:
                self.nameList.destroy()
            self.listNames = [name for name in names if self.__firstLetters(name) == letter]
            self.nameList = self.__makeList(NAMES_X, NAMES_WIDTH, 'ArrowUpBig', 0.15, self.listNames,
                                            self.__pickName)
            self.letterList.scrollTo(self.letters.index(letter))
        self.__lightNameLists()

    def __lightNameLists(self):
        if not self.nameList:
            return
        name = PetCreator.cleanName(self.name)
        for item in self.letterList['items']:
            item['frameColor'] = PICKED if item['text'] == self.listLetter else Vec4(1, 1, 1, 0)
        for item in self.nameList['items']:
            item['frameColor'] = PICKED if item['text'] == name else Vec4(1, 1, 1, 0)

    def __pickLetter(self, letter):
        self.__fillNameLists(letter)

    def __pickName(self, name):
        self.name = name
        self.nameEntry.enterText(name)
        self.__refresh()

    def __randomName(self):
        self.name = random.choice(self.__allNames())
        self.nameEntry.enterText(self.name)
        self.__fillNameLists(self.__firstLetters(self.name))
        self.nameList.scrollTo(self.listNames.index(self.name))
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
        self.__refresh()

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
        holder.setScale(THUMB_SIZE / size)
        center = (lo + hi) / 2.0
        holder.setPos(-center[0] * THUMB_SIZE / size, 0, -center[2] * THUMB_SIZE / size)
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
                tile.price['text'] = ''
                continue
            tile['text'] = ''
            if pair == PetAccessories.getPair(self.wearing, self.wearKind):
                tile.price['text'] = TTLocalizer.PetCreatorOwned
            else:
                tile.price['text'] = self.__beans(PetAccessories.getPrice(self.wearKind, pair))
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
        if tab == TAB_NAME:
            # The doodle may have turned from a boy to a girl since.
            self.__fillNameLists()

    def getWearCost(self):
        # The accessories: all of them when building, only the new ones
        # when restyling.
        return PetAccessories.getCost(self.accessories, self.wearing)

    def getPetCost(self):
        if self.restyle:
            return 0
        return PetCreator.getCost(self.dna[PetDNA.Fields['body']], self.traitLevels, self.zoneId)

    def getCost(self):
        return self.getPetCost() + self.getWearCost()

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
        else:
            label['text'] = TTLocalizer.PetCreatorPlus % max(0, extra)

    def __refresh(self):
        name = PetCreator.cleanName(self.name)
        self.nameLabel['text'] = name
        cost = self.getCost()
        petCost = self.getPetCost()
        wearCost = self.getWearCost()
        money = base.localAvatar.getTotalMoney()
        if self.restyle:
            lines = (('', ''),
                     (TTLocalizer.PetCreatorSumName, TTLocalizer.PetCreatorFree),
                     (TTLocalizer.PetCreatorSumNewWear, '+' + self.__beans(wearCost)))
        else:
            body = self.dna[PetDNA.Fields['body']]
            # The body on its own is what it costs with the plainest traits
            # this playground sells; the traits add the rest.
            plainest = [min(PetCreator.getTraitLevels(i, self.zoneId).keys())
                        for i in range(PetTraits.PetTraits.NumTraits)]
            bodyCost = PetCreator.getCost(body, plainest, self.zoneId)
            lines = ((TTLocalizer.PetCreatorSumBody % TTLocalizer.PetCreatorBodyNames[PetDNA.BodyTypes[body]],
                      self.__beans(bodyCost)),
                     (TTLocalizer.PetCreatorSumTraits, '+' + self.__beans(max(0, petCost - bodyCost))),
                     (TTLocalizer.PetCreatorSumWear, '+' + self.__beans(wearCost)))
        lines += ((TTLocalizer.PetCreatorSumTotal, self.__beans(cost)),
                  (TTLocalizer.PetCreatorSumBeans, self.__beans(money)))
        for (left, right), (label, value) in zip(self.sumLines, lines):
            left['text'] = label
            right['text'] = value
        # Short of jellybeans, the last line says so, in red.
        poor = cost > money
        if poor:
            self.sumLines[-1][0]['text'] = TTLocalizer.PetCreatorTooPoor
        for label in self.sumLines[-1]:
            label['text_fg'] = Vec4(0.8, 0, 0, 1) if poor else PRICE_GREEN
        self.sumRule.show()
        self.sumNote['text'] = ''
        if not self.restyle:
            for field in ('body', 'color', 'colorScale', 'eyes', 'gender', 'head', 'ears', 'nose', 'tail'):
                row, value, price, left, right = self.rows[field]
                value['text'] = self.__lookName(field, self.dna[PetDNA.Fields[field]])
                if field == 'body':
                    cheapest = min(self.__costWith(body=b) for b in PetCreator.getBodies(self.zoneId))
                    self.__setPrice(price, petCost - cheapest)
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
                    self.__setPrice(price, petCost - cheapest)
                else:
                    # This trait isn't counted in a doodle's worth.
                    self.__setPrice(price, None)
                left['state'] = DGG.NORMAL if level != levels[0] else DGG.DISABLED
                right['state'] = DGG.NORMAL if level != levels[-1] else DGG.DISABLED
        self.__lightNameLists()
        nameOk = PetCreator.isValidName(name)
        self.nameWarning['text'] = '' if nameOk else TTLocalizer.PetCreatorNameBad % PetCreator.MaxNameLength
        if nameOk and cost <= money:
            self.okButton['state'] = DGG.NORMAL
        else:
            self.okButton['state'] = DGG.DISABLED

    def __beans(self, amount):
        return '{:,}'.format(int(amount))

    def __moneyChange(self, money):
        self.__refresh()

    # Finishing.

    def __confirm(self):
        name = PetCreator.cleanName(self.name)
        if self.restyle:
            cost = self.getCost()
            if cost:
                text = TTLocalizer.PetCreatorRestyleConfirmCost % (name, cost)
            else:
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
