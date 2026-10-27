from direct.gui.DirectGui import *
import random
from . import ClothesGUI
from . import ShuffleButton
from toontown.makeatoon.MakeAToonGlobals import *
from toontown.toon import ToonDNA
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownGlobals

# Every accessory the game has, one list per kind, with nothing first.
def accessoryChoices(styles):
    choices = sorted(set(tuple(style) for style in styles.values()))
    choices.remove((0, 0, 0))
    return [(0, 0, 0)] + choices

ACCESSORY_KINDS = (('hat', TTLocalizer.TrunkHatGUI, ToonDNA.HatStyles),
 ('glasses', TTLocalizer.TrunkGlassesGUI, ToonDNA.GlassesStyles),
 ('backpack', TTLocalizer.TrunkBackpackGUI, ToonDNA.BackpackStyles),
 ('shoes', TTLocalizer.TrunkShoesGUI, ToonDNA.ShoesStyles))

class MakeClothesGUI(ClothesGUI.ClothesGUI):
    notify = directNotify.newCategory('MakeClothesGUI')

    def __init__(self, doneEvent):
        ClothesGUI.ClothesGUI.__init__(self, ClothesGUI.CLOTHES_MAKETOON, doneEvent)
        self.accessories = {}
        for kind, label, styles in ACCESSORY_KINDS:
            self.accessories[kind] = [accessoryChoices(styles), 0]
        self.showingAccessories = 0

    def load(self):
        ClothesGUI.ClothesGUI.load(self)
        shuffleFrame = self.gui.find('**/tt_t_gui_mat_shuffleFrame')
        shuffleUp = self.gui.find('**/tt_t_gui_mat_shuffleUp')
        shuffleDown = self.gui.find('**/tt_t_gui_mat_shuffleDown')
        shuffleArrowUp = self.gui.find('**/tt_t_gui_mat_shuffleArrowUp')
        shuffleArrowDown = self.gui.find('**/tt_t_gui_mat_shuffleArrowDown')
        shuffleArrowDisabled = self.gui.find('**/tt_t_gui_mat_shuffleArrowDisabled')
        # Laid out like the clothes frames it takes the place of.
        self.clothesFrames = [self.shirtStyleFrame, self.shirtFrame, self.bottomStyleFrame, self.bottomFrame]
        self.accessoryFrame = DirectFrame(parent=self.parentFrame, relief=None)
        self.accessoryButtons = {}
        for i, (kind, label, styles) in enumerate(ACCESSORY_KINDS):
            frame = DirectFrame(parent=self.accessoryFrame, image=shuffleFrame, image_scale=halfButtonInvertScale, relief=None, pos=(0, 0, -0.073 - 0.227 * i), hpr=(0, 0, (3, -2, 3, -2)[i]), scale=1.0, frameColor=(1, 1, 1, 1), text=label, text_scale=0.0575, text_pos=(-0.001, -0.015), text_fg=(1, 1, 1, 1))
            lButton = DirectButton(parent=frame, relief=None, image=(shuffleArrowUp,
             shuffleArrowDown,
             shuffleArrowUp,
             shuffleArrowDisabled), image_scale=halfButtonScale, image1_scale=halfButtonHoverScale, image2_scale=halfButtonHoverScale, pos=(-0.2, 0, 0), command=self.swapAccessory, extraArgs=[kind, -1])
            rButton = DirectButton(parent=frame, relief=None, image=(shuffleArrowUp,
             shuffleArrowDown,
             shuffleArrowUp,
             shuffleArrowDisabled), image_scale=halfButtonInvertScale, image1_scale=halfButtonInvertHoverScale, image2_scale=halfButtonInvertHoverScale, pos=(0.2, 0, 0), command=self.swapAccessory, extraArgs=[kind, 1])
            self.accessoryButtons[kind] = (frame, lButton, rButton)
        self.accessoryFrame.hide()
        # Shuffle for the accessories, in the clothes Shuffle button's place
        # while they are showing. A shuffle leaves each kind off about a
        # third of the time, so a toon isn't always wearing all four.
        self.accessoryShuffleMsg = 'AccessoryShuffle'
        self.accessoryShuffle = ShuffleButton.ShuffleButton(AccessoryShuffleOwner(self), self.accessoryShuffleMsg)
        self.accessoryShuffle.setChoicePool([[0] * max(1, len(choices) // 2) + list(range(1, len(choices)))
                                             for choices, choice in (self.accessories[kind] for kind, label, styles in ACCESSORY_KINDS)])
        self.accessoryShuffle.parentFrame.hide()
        # The same button as Shuffle, just under it.
        self.accessoriesButton = DirectButton(parent=self.parentFrame, relief=None, pos=(0, 0, 0.15), hpr=(0, 0, 5), image=(shuffleUp, shuffleDown, shuffleUp), image_scale=(-0.9, 0.6, 0.6), image1_scale=(-0.93, 0.6, 0.6), image2_scale=(-0.93, 0.6, 0.6), text=TTLocalizer.MakeAToonAccessories, text_font=ToontownGlobals.getInterfaceFont(), text_scale=TTLocalizer.SBshuffleBtn * 0.75, text_pos=(0, -0.02), text_fg=(1, 1, 1, 1), text_shadow=(0, 0, 0, 1), command=self.toggleAccessories)

    def unload(self):
        self.ignore(self.accessoryShuffleMsg)
        self.accessoryShuffle.unload()
        del self.accessoryShuffle
        self.accessoriesButton.destroy()
        del self.accessoriesButton
        for frame, lButton, rButton in self.accessoryButtons.values():
            lButton.destroy()
            rButton.destroy()
            frame.destroy()
        del self.accessoryButtons
        self.accessoryFrame.destroy()
        del self.accessoryFrame
        del self.clothesFrames
        ClothesGUI.ClothesGUI.unload(self)

    def enter(self, toon):
        ClothesGUI.ClothesGUI.enter(self, toon)
        for kind in self.accessories:
            self.swapAccessory(kind, 0)
        self.accept(self.accessoryShuffleMsg, self.shuffleAccessories)
        self.acceptOnce('MAT-newToonCreated', self.accessoryShuffle.cleanHistory)
        self.showAccessories(self.showingAccessories)

    def toggleAccessories(self):
        self.showAccessories(not self.showingAccessories)

    def showAccessories(self, show):
        self.showingAccessories = show
        for frame in self.clothesFrames:
            if show:
                frame.hide()
            else:
                frame.show()
        if show:
            self.accessoryFrame.show()
            self.shuffleButton.parentFrame.hide()
            self.accessoryShuffle.parentFrame.show()
            self.accessoriesButton['text'] = TTLocalizer.MakeAToonClothes
        else:
            self.accessoryFrame.hide()
            self.shuffleButton.parentFrame.show()
            self.accessoryShuffle.parentFrame.hide()
            self.accessoriesButton['text'] = TTLocalizer.MakeAToonAccessories

    def swapAccessory(self, kind, offset):
        choices, choice = self.accessories[kind]
        choice = max(0, min(len(choices) - 1, choice + offset))
        self.accessories[kind][1] = choice
        frame, lButton, rButton = self.accessoryButtons[kind]
        self.updateScrollButtons(choice, len(choices), 0, lButton, rButton)
        if not getattr(self, 'toon', None):
            return
        idx, textureIdx, colorIdx = choices[choice]
        if kind == 'hat':
            self.toon.setHat(idx, textureIdx, colorIdx)
        elif kind == 'glasses':
            self.toon.setGlasses(idx, textureIdx, colorIdx)
        elif kind == 'backpack':
            self.toon.setBackpack(idx, textureIdx, colorIdx)
        else:
            self.toon.setShoes(idx, textureIdx, colorIdx)
        messenger.send('wakeup')

    def getAccessoryChoices(self):
        return [self.accessories[kind][1] for kind, label, styles in ACCESSORY_KINDS]

    def shuffleAccessories(self):
        for (kind, label, styles), choice in zip(ACCESSORY_KINDS, self.accessoryShuffle.getCurrChoice()):
            self.accessories[kind][1] = choice
            self.swapAccessory(kind, 0)

    def getAccessories(self):
        """(hat, glasses, backpack, shoes) as picked here."""
        return tuple(self.accessories[kind][0][self.accessories[kind][1]] for kind, label, styles in ACCESSORY_KINDS)

    def setupScrollInterface(self):
        self.dna = self.toon.getStyle()
        gender = self.dna.getGender()
        if gender != self.gender:
            self.topStyles = ToonDNA.getTopStyles(gender, tailorId=ToonDNA.MAKE_A_TOON)
            self.tops = ToonDNA.getTops(gender, tailorId=ToonDNA.MAKE_A_TOON)
            self.bottomStyles = ToonDNA.getBottomStyles(gender, tailorId=ToonDNA.MAKE_A_TOON)
            self.bottoms = ToonDNA.getBottoms(gender, tailorId=ToonDNA.MAKE_A_TOON)
            self.gender = gender
            self.topChoice = 0
            self.topColorChoice = 0
            self.topStyleChoice = 0
            self.bottomStyleChoice = 0
            self.bottomColorChoice = 0
            self.bottomChoice = 0
        self.setupButtons()

    def setupButtons(self):
        ClothesGUI.ClothesGUI.setupButtons(self)
        if len(self.dna.torso) == 1:
            if self.gender == 'm':
                torsoStyle = 's'
            elif self.girlInShorts == 1:
                torsoStyle = 's'
            else:
                torsoStyle = 'd'
            self.toon.swapToonTorso(self.dna.torso[0] + torsoStyle)
            self.toon.loop('neutral', 0)
            self.toon.swapToonColor(self.dna)
            self.swapTop(0)
            self.swapBottom(0)
        return None


class AccessoryShuffleOwner:
    """What ShuffleButton asks of the shop it sits in, for the accessories."""

    def __init__(self, shop):
        self.shop = shop
        self.parentFrame = shop.parentFrame

    def getCurrToonSetting(self):
        return self.shop.getAccessoryChoices()
