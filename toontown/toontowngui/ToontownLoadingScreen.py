from direct.gui.DirectGui import *
from panda3d.core import *
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
import random

# How many times the background tile repeats across and down the screen.
BACKGROUND_TILES = (20.0, 8.6)
LOGO_POS = (0, 0, 0.6)
LOGO_SCALE = 0.155

class ToontownLoadingScreen:

    def __init__(self):
        self.__expectedCount = 0
        self.__count = 0
        self.gui = loader.loadModel('phase_3/models/gui/progress-background')
        # The background picture is a small tile, repeated over the screen.
        background = self.gui.find('**/+GeomNode')
        if not background.isEmpty():
            background.setTexScale(TextureStage.getDefault(), BACKGROUND_TILES[0], BACKGROUND_TILES[1])
        # The game's logo over the top, as the original loading screen had it.
        logo = loader.loadModel('phase_3/models/gui/toontown-logo', okMissing=True)
        self.logo = logo.find('**/logo') if logo else NodePath()
        if not self.logo.isEmpty():
            self.logo = self.logo.copyTo(self.gui)
            self.logo.setPos(*LOGO_POS)
            self.logo.setScale(LOGO_SCALE)
        else:
            self.logo = self.gui.attachNewNode('logo')
        if logo:
            logo.removeNode()
        # The scroll the tips are written on. A missing model or scroll only
        # loses the tip, never the loading screen.
        council = loader.loadModel('phase_3/models/gui/toon_council', okMissing=True)
        scroll = council.find('**/scroll') if council else NodePath()
        if scroll.isEmpty():
            self.banner = self.gui.attachNewNode('banner')
        else:
            self.banner = scroll
            self.banner.reparentTo(self.gui)
        if council:
            council.removeNode()
        self.banner.setScale(0.4, 0.4, 0.4)
        self.tip = DirectLabel(guiId='ToontownLoadingScreenTip', parent=self.banner, relief=None, text='', text_scale=getattr(TTLocalizer, 'TLStip', 0.18), textMayChange=1, pos=(-1.2, 0.0, 0.1), text_fg=(0.4, 0.3, 0.2, 1), text_wordwrap=13, text_align=TextNode.ALeft)
        self.title = DirectLabel(guiId='ToontownLoadingScreenTitle', parent=self.gui, relief=None, pos=(-1.06, 0, -0.77), text='', textMayChange=1, text_scale=0.08, text_fg=(0, 0, 0.5, 1), text_align=TextNode.ALeft)
        self.waitBar = DirectWaitBar(guiId='ToontownLoadingScreenWaitBar', parent=self.gui, frameSize=(-1.06,
         1.06,
         -0.03,
         0.03), pos=(0, 0, -0.85), text='')

        # This will bring up the placer panel, which is useful for positioning objects but also rather buggy.
        if ConfigVariableBool('want-placer-panel', False).getValue():
            self.gui.place()
        return

    def destroy(self):
        self.tip.destroy()
        self.title.destroy()
        self.waitBar.destroy()
        self.logo.removeNode()
        self.banner.removeNode()
        self.gui.removeNode()

    def getTip(self, tipCategory):
        # A category without tips (TIP_NONE, or one this language leaves
        # out) shows no tip rather than failing the load.
        tips = [tip for tip in TTLocalizer.TipDict.get(tipCategory) or () if tip]
        if not tips:
            return ''
        return TTLocalizer.TipTitle + '\n' + random.choice(tips)

    def begin(self, range, label, gui, tipCategory):
        self.waitBar['range'] = range
        self.title['text'] = label
        tip = self.getTip(tipCategory)
        self.tip['text'] = tip
        if tip:
            self.banner.show()
        else:
            self.banner.hide()
        self.__count = 0
        self.__expectedCount = range
        if gui:
            self.waitBar.reparentTo(self.gui)
            self.title.reparentTo(self.gui)
            self.gui.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
        else:
            self.waitBar.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
            self.title.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
            self.gui.reparentTo(hidden)
        self.waitBar.update(self.__count)

    def end(self):
        self.waitBar.finish()
        self.__putAway()
        return (self.__expectedCount, self.__count)

    def abort(self):
        # The bar and title may be on the screen by themselves (a load
        # without the background); they go away too.
        self.__putAway()

    def __putAway(self):
        self.waitBar.reparentTo(self.gui)
        self.title.reparentTo(self.gui)
        self.gui.reparentTo(hidden)

    def tick(self):
        self.__count = self.__count + 1
        self.waitBar.update(self.__count)
