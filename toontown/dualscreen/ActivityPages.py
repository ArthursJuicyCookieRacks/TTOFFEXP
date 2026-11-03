"""The bottom screen while fishing or golfing (see BottomScreenPages).

Fishing (Arthur): the bottom screen is the fishing rod's control, a big
cast pad to drag back and let go of like the top screen's Cast button.
Each catch is shown there (the same panel the top screen shows, with its X)
instead of on the top screen, and closing it brings the cast pad back. A
small Fish Bingo card in the top right corner brings up the whole bingo
card on the bottom screen, cells and BINGO! button working by touch.

Golf: aim left and right, a Swing button to hold and let go of (with the
power bar), a Top View button, and the tee pick before each hole. Each time
the scorecard pops up it is shown on the bottom screen with its X, and the
scorecard in the top right corner brings it up any time.

Leaving the pond or the golf course brings back the usual pages.
"""

import math

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel, DirectWaitBar
from direct.interval.IntervalGlobal import Func, Sequence, Wait
from panda3d.core import CardMaker, NodePath, Point3, TextNode, TransparencyAttrib

from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer

notify = DirectNotifyGlobal.directNotify.newCategory('BottomScreen')

WHITE = (1, 1, 1, 1)
INK = (0.16, 0.22, 0.48, 1)
SOFT = (0.38, 0.42, 0.55, 1)
CREAM = (1, 0.97, 0.86, 1)
GOLD = (1, 0.92, 0.6, 1)
SKY = (0.78, 0.89, 1, 1)
MINT = (0.78, 0.95, 0.78, 1)
ROSE = (1, 0.82, 0.8, 1)

# Dragging this far on the bottom screen (in its own units, the screen is 2
# tall) is a full-power cast. On the top screen half the mouse's travel up
# or down is, which is a quarter of the screen: this is a little more.
FULL_CAST = 0.6
# The cast pad.
PAD_Z = 0.0
PAD_SIZE = 0.95
# Where the catch panels and the bingo card go, and how big they may be.
OVERLAY_Z = 0.0
OVERLAY_HEIGHT = 1.45


def localFishingSpot():
    avatar = getattr(base, 'localAvatar', None)
    cr = getattr(base, 'cr', None)
    if avatar is None or cr is None:
        return None
    for do in list(cr.doId2do.values()):
        if do.__class__.__name__ == 'DistributedFishingSpot' and getattr(do, 'localToonFishing', 0) and \
                getattr(do, 'avId', 0) == avatar.doId and getattr(do, 'madeGui', 0):
            return do
    return None


def localGolfCourse():
    avatar = getattr(base, 'localAvatar', None)
    cr = getattr(base, 'cr', None)
    if avatar is None or cr is None:
        return None
    for do in list(cr.doId2do.values()):
        if do.__class__.__name__ == 'DistributedGolfCourse' and avatar.doId in (getattr(do, 'avIdList', None) or ()) \
                and not do.isDisabled():
            return do
    return None


def currentActivity():
    """'fishing', 'golf' or None."""
    try:
        if localFishingSpot() is not None:
            return 'fishing'
        if localGolfCourse() is not None:
            return 'golf'
    except Exception:
        return None
    return None


def pressButton(button):
    """What clicking a DirectButton on the top screen does."""
    if button is None or button.isEmpty() or button['state'] != DGG.NORMAL:
        return
    command = button['command']
    if command is not None:
        command(*button['extraArgs'])


class ActivityPages:
    """Mixed into BottomScreen: the fishing and golf pages."""

    def initActivity(self):
        self.activity = None
        self.activityModels = {}
        self.controls = None
        self.overlay = None
        self.overlayKind = None
        # Top screen GUI shown on the bottom screen for a while, put back
        # where it was after: (node, parent, sort).
        self.borrowed = []
        self.catchActor = None
        self.catchSound = None
        self.swimCard = None

    def activityModel(self, path):
        model = self.activityModels.get(path)
        if model is None or model.isEmpty():
            model = loader.loadModel(path)
            self.activityModels[path] = model
        return model

    def destroyActivity(self):
        for model in self.activityModels.values():
            if not model.isEmpty():
                model.removeNode()
        self.activityModels = {}

    def clearActivity(self):
        self.ignore('dualScreenCatch')
        self.ignore('dualScreenCatchGone')
        self.closeOverlay()
        self.controls = None

    # --- An overlay: a catch, the bingo card or the scorecard ---

    def borrow(self, node, holder):
        """Shows a top screen GUI node on the bottom screen until
        giveBack."""
        self.borrowed.append((node, node.getParent(), node.getTransform()))
        node.reparentTo(holder)

    def giveBack(self):
        for node, parent, transform in self.borrowed:
            if node.isEmpty():
                continue
            if parent.isEmpty():
                node.detachNode()
            else:
                node.reparentTo(parent, 1 if parent == aspect2d else 0)
                node.setTransform(transform)
        self.borrowed = []

    def openOverlay(self, kind):
        self.closeOverlay()
        self.overlay = self.page.attachNewNode('overlay-' + kind)
        self.overlayKind = kind
        if self.controls is not None and not self.controls.isEmpty():
            self.controls.hide()
        return self.overlay

    def closeOverlay(self):
        self.giveBack()
        if self.catchSound is not None:
            self.catchSound.pause()
            self.catchSound = None
        if self.catchActor is not None:
            self.catchActor.cleanup()
            self.catchActor.removeNode()
            self.catchActor = None
        root = getattr(self, 'catchRoot', None)
        if root is not None and not root.isEmpty():
            root.removeNode()
        self.catchRoot = None
        panel = getattr(self, 'catchPanel', None)
        if panel is not None:
            panel.destroy()
        self.catchPanel = None
        if self.overlay is not None:
            if not self.overlay.isEmpty():
                self.overlay.removeNode()
            self.overlay = None
            self.taps = [tap for tap in self.taps if not tap.node.isEmpty() and tap.node.hasParent()]
        self.overlayKind = None
        if self.controls is not None and not self.controls.isEmpty():
            self.controls.show()

    def fitInto(self, holder, node, z=OVERLAY_Z, height=OVERLAY_HEIGHT, halfWidth=0.62):
        """Scales and moves holder so that node fits the middle of the
        page."""
        bounds = None
        item = getattr(node, 'guiItem', None)
        if item is not None:
            # The GUI's own frame: tight bounds would count hidden parts
            # too (the bingo card's tutorial, for one).
            left, right, bottom, top = item.getFrame()
            if right > left and top > bottom:
                matrix = node.getMat(holder)
                corners = [matrix.xformPoint(Point3(x, 0, z)) for x in (left, right) for z in (bottom, top)]
                bounds = (Point3(min(c[0] for c in corners), 0, min(c[2] for c in corners)),
                          Point3(max(c[0] for c in corners), 0, max(c[2] for c in corners)))
        if bounds is None:
            bounds = node.getTightBounds(holder)
        if not bounds:
            return
        low, high = bounds
        width = max(0.001, high[0] - low[0])
        tall = max(0.001, high[2] - low[2])
        size = min(2 * halfWidth / width, height / tall)
        holder.setScale(size)
        holder.setPos(-(low[0] + high[0]) / 2.0 * size, 0, z - (low[2] + high[2]) / 2.0 * size)

    def closeX(self, parent, pos, command, scale=0.6):
        buttons = self.activityModel('phase_3/models/gui/dialog_box_buttons_gui')
        frame = DirectFrame(parent=parent, relief=None, image=buttons.find('**/CloseBtn_UP'), image_scale=scale, pos=pos,
                            state=DGG.NORMAL)
        frame.setTransparency(TransparencyAttrib.MAlpha)
        return self.tap(frame, command)

    # --- Fishing ---

    def buildFishing(self):
        spot = localFishingSpot()
        self.screen.setSmooth(True)
        self.paper()
        self.title('Fishing', font=self.signFont)
        self.controls = self.page.attachNewNode('controls')
        self.fishingSpot = spot
        gui = self.activityModel('phase_4/models/gui/fishingGui')
        page, self.page = self.page, self.controls
        # Jellybeans and the bucket.
        jarBox = self.panel((-0.3, 0, 0.56), 0.5, 0.17, CREAM)
        jar = jarBox.attachNewNode('jar')
        self.find('jar_gui', 'Jar').copyTo(jar)
        jar.setScale(0.22)
        jar.setPos(-0.15, -1, 0.0)
        self.fishBeans = self.label('', (0.06, 0, -0.025), scale=0.075, parent=jarBox, font=self.signFont)
        bucketBox = self.panel((0.3, 0, 0.56), 0.5, 0.17, CREAM)
        bucket = bucketBox.attachNewNode('bucket')
        bucketModel = gui.find('**/bucket')
        if not bucketModel.isEmpty():
            bucketModel.copyTo(bucket)
            low, high = bucket.getTightBounds(bucketBox) or (Point3(-1), Point3(1))
            size = 0.13 / max(0.001, high[2] - low[2])
            bucket.setScale(size)
            bucket.setPos(-0.14 - (low[0] + high[0]) / 2.0 * size, -1, -(low[2] + high[2]) / 2.0 * size)
        self.fishBucket = self.label('', (0.07, 0, -0.025), scale=0.07, parent=bucketBox, font=self.signFont)
        # The cast pad: a clean rounded button like the page's others.
        pad = self.panel((0, 0, PAD_Z), PAD_SIZE * 0.82, PAD_SIZE * 0.72, ROSE, parent=self.controls, touchable=True,
                         text=TTLocalizer.FishingCast, text_scale=0.15, text_fg=INK, text_font=self.signFont,
                         text_pos=(0, -0.05))
        self.castPad = pad
        self.holdTap(pad, self.castTouch)
        # The aim arrow, as on the top screen.
        self.castArrow = None
        arrow = gui.find('**/arrow')
        if not arrow.isEmpty():
            holder = self.controls.attachNewNode('arrowHolder')
            holder.setPos(0, -2, PAD_Z)
            self.castArrow = arrow.copyTo(holder)
            self.castArrow.setPos(0, 0, 0)
            self.castArrowTail = self.castArrow.find('**/arrowTail')
            self.castArrowHolder = holder
            holder.setScale(1.0)
            holder.hide()
        self.fishHint = self.label('Drag down from the button to cast, sideways to aim, then let go.', (0, 0, -0.5),
                                   scale=0.048, fg=SOFT, wordwrap=24)
        # Exit, the top screen's own button.
        exitButton = DirectFrame(parent=self.controls, relief=None, image=gui.find('**/exit_buttonUp'), image_scale=0.67 * 1.25,
                                 pos=(0.5, 0, -0.8), state=DGG.NORMAL, text=TTLocalizer.FishingExit, text_scale=0.055,
                                 text_fg=WHITE, text_shadow=(0, 0, 0, 1), text_pos=(0, -0.13 * 0.67 * 1.25 - 0.02))
        low, high = exitButton.getTightBounds(exitButton) or (Point3(-0.1), Point3(0.1))
        exitButton['frameSize'] = (low[0], high[0], low[2], high[2])
        exitButton.setTransparency(TransparencyAttrib.MAlpha)
        self.tap(exitButton, self.exitFishing)
        self.page = page
        # The Fish Bingo card in the top right corner.
        self.bingoIcon = None
        pond = getattr(spot, 'pond', None) if spot else None
        if pond is not None and pond.hasPondBingoManager():
            self.makeBingoIcon()
        self.accept('dualScreenCatch', self.showCatch)
        self.accept('dualScreenCatchGone', self.catchGone)
        self.refreshFishing()

    def makeBingoIcon(self):
        # Arthur: just a yellow button that says Bingo.
        icon = self.panel((0.58, 0, 0.82), 0.3, 0.14, GOLD, touchable=True, text='Bingo', text_scale=0.065,
                          text_pos=(0, -0.022), text_fg=INK, text_font=self.signFont)
        self.bingoIcon = icon
        self.tap(icon, self.openBingo)

    def bingoManager(self):
        spot = localFishingSpot()
        pond = getattr(spot, 'pond', None) if spot else None
        if pond is None or not pond.hasPondBingoManager():
            return None
        return pond.getPondBingoManager()

    def refreshFishing(self):
        spot = localFishingSpot()
        if spot is None or self.controls is None or self.controls.isEmpty():
            return
        avatar = base.localAvatar
        self.fishBeans['text'] = '%d' % avatar.getMoney()
        self.fishBucket['text'] = '%d/%d' % (len(avatar.getFishTank()), avatar.getMaxFishTank())
        if self.bingoIcon is None and self.bingoManager() is not None:
            self.makeBingoIcon()
        state = spot.fsm.getCurrentState().getName()
        adjusting = state == 'localAdjusting'
        self.castPad['image_color'] = MINT if adjusting else (ROSE if spot.canCast() else (0.9, 0.9, 0.9, 1))
        self.castPad['text'] = '%d%%' % int(round(spot.power * 100)) if adjusting else TTLocalizer.FishingCast
        if self.castArrow is not None:
            if adjusting and not spot.arrow.isHidden():
                self.castArrowHolder.show()
                self.castArrow.setR(spot.arrow.getR())
                self.castArrow.setColorScale(spot.arrow.getColorScale())
                if not self.castArrowTail.isEmpty():
                    self.castArrowTail.setScale(spot.arrowTail.getScale())
            else:
                self.castArrowHolder.hide()
        if adjusting:
            self.fishHint['text'] = ''
        elif state in ('localCasting', 'fishing'):
            self.fishHint['text'] = 'Waiting for a bite...'
        elif state == 'waitForAI':
            self.fishHint['text'] = 'Reeling in...'
        else:
            self.fishHint['text'] = 'Drag down from the button to cast, sideways to aim, then let go.'

    def castTouch(self, kind, point):
        spot = localFishingSpot()
        if spot is None:
            return
        # The same drag as on the top screen: a full-power cast is a drag
        # of FULL_CAST here, half the mouse's range there.
        mouse = (point[0] * 0.5 / FULL_CAST, point[2] * 0.5 / FULL_CAST)
        if kind == 'down':
            if self.overlay is not None:
                return
            if not spot.dualScreenCastPress(mouse):
                self.say('Not now: wait for the line to come back in.', 2.0)
        elif kind == 'move':
            spot.dualScreenCastDrag(mouse)
        else:
            spot.dualScreenCastRelease(mouse)
        self.refreshFishing()

    def exitFishing(self):
        spot = localFishingSpot()
        if spot is not None and spot.madeGui and spot.exitButton['command']:
            spot.exitButton['command']()

    def showCatch(self, spot, code, fish):
        if self.pageName != 'fishing' or spot is not localFishingSpot():
            return
        from toontown.fishing import FishGlobals
        overlay = self.openOverlay('catch')
        if fish is None:
            # Jellybeans, a boot or a ToonTask item: the top screen's own
            # "You found" panel, moved down here.
            holder = overlay.attachNewNode('item')
            self.borrow(spot.itemGui, holder)
            self.fitInto(holder, spot.itemFrame)
            self.tap(spot.itemGuiCloseButton, self.closeCatch)
            return
        from toontown.fishing import FishPanel
        holder = overlay.attachNewNode('fish')
        panel = FishPanel.FishPanel(fish, parent=holder)
        panel.load()
        if code == FishGlobals.FishItemNewEntry:
            panel.extraLabel['text_fg'] = (0.2, 0.8, 0.4, 1)
            panel.extraLabel['text'] = TTLocalizer.FishingNewEntry
            panel.extraLabel['text_scale'] = TTLocalizer.FPnewEntry
        elif code == FishGlobals.FishItemNewRecord:
            panel.extraLabel['text_fg'] = (1, 0.5, 0, 1)
            panel.extraLabel['text'] = TTLocalizer.FishingNewRecord
            panel.extraLabel['text_scale'] = TTLocalizer.FPnewRecord
        else:
            panel.extraLabel.hide()
        # Where the fish swims (FishPanel's swim bounds and color).
        cards = CardMaker('swim')
        cards.setFrame(-0.3, 0.3, -0.235, 0.25)
        swim = panel.attachNewNode(cards.generate())
        swim.setColor(1.0, 1.0, 0.74901, 1.0)
        swim.setY(-0.1)
        panel.mystery.hide()
        self.fitInto(holder, panel)
        self.catchPanel = panel
        self.tap(panel.cancel, self.closeCatch)
        self.showCatchFish(fish, swim)

    def showCatchFish(self, fish, swim):
        from toontown.fishing import FishGlobals
        low, high = swim.getTightBounds(self.aspect) or (Point3(-0.3, 0, -0.3), Point3(0.3, 0, 0.3))
        actor = fish.getActor()
        actor.setTwoSided(1)
        actor.setDepthTest(True)
        actor.setDepthWrite(True)
        scene = self.screen.sceneRoot()
        root = scene.attachNewNode('catchFish')
        pitch = root.attachNewNode('pitch')
        rotate = pitch.attachNewNode('rotate')
        scale = rotate.attachNewNode('scale')
        actor.reparentTo(scale)
        genus = fish.getGenus()
        info = FishGlobals.FishFileDict.get(genus, FishGlobals.FishFileDict[-1])
        rotate.setH(info[7])
        pitch.setP(info[8])
        bounds = actor.getTightBounds(root)
        if bounds:
            a, b = bounds
            margin = 0.62
            size = min((high[0] - low[0]) * margin / max(0.001, b[0] - a[0]), (high[2] - low[2]) * margin / max(0.001, b[2] - a[2]))
            root.setScale(size)
            root.setPos((low[0] + high[0]) / 2.0 - (a[0] + b[0]) / 2.0 * size, 0,
                        (low[2] + high[2]) / 2.0 - (a[2] + b[2]) / 2.0 * size)
        self.catchActor = actor
        self.catchRoot = root
        # Plays its intro and then swims, as in the top screen's panel.
        try:
            sound, loop, delay, playRate = fish.getSound()
            if playRate is not None:
                actor.setPlayRate(playRate, 'intro')
                actor.setPlayRate(playRate, 'swim')
            actor.play('intro')
            track = Sequence(Wait(actor.getDuration('intro')), Func(actor.loop, 'swim'))
            if sound:
                track = Sequence(Func(track.start), Wait(delay), Func(sound.play))
            track.start()
            self.catchSound = track
        except Exception:
            actor.loop('swim')
        root.reparentTo(scene)

    def closeCatch(self):
        if self.overlayKind != 'catch':
            return
        spot = localFishingSpot()
        self.closeOverlay()
        if spot is not None and spot.madeGui:
            # As the top screen's X does.
            spot.itemGui.detachNode()

    def catchGone(self, spot):
        if self.overlayKind == 'catch':
            self.closeOverlay()

    def openBingo(self):
        manager = self.bingoManager()
        card = getattr(manager, 'card', None) if manager else None
        if card is None or card.isEmpty():
            self.say('There is no Fish Bingo at this pond right now.', 2.5)
            return
        if card.isHidden() or card.getGame() is None and card.nextGameTimer.isHidden():
            self.say('The next Fish Bingo game has not started yet.', 2.5)
            return
        overlay = self.openOverlay('bingo')
        holder = overlay.attachNewNode('bingo')
        self.borrow(card, holder)
        if not card.jpSign.isEmpty():
            self.borrow(card.jpSign, holder)
        # Centered on the blue card itself: the card's GUI frame is not
        # where its picture is, which put it off to one side.
        holder.setPos(0, 0, 0)
        holder.setScale(1)
        low, high = self.pictureBounds(card, holder)
        size = min(2 * 0.66 / max(0.001, high[0] - low[0]), 1.45 / max(0.001, high[2] - low[2]))
        holder.setScale(size)
        holder.setPos(-(low[0] + high[0]) / 2.0 * size, 0, -0.08 - (low[2] + high[2]) / 2.0 * size)
        low, high = self.pictureBounds(card, overlay)
        # The X on the card's top right corner.
        self.closeX(overlay, (high[0] - 0.02, 0, high[2] - 0.02), self.closeBingo, scale=1.5)
        for cell in card.cellGuiList:
            self.tap(cell, pressButton, cell)
        self.tap(card.bingo, pressButton, card.bingo)

    def pictureBounds(self, card, other):
        # A DirectFrame's picture hangs under its state node, which is not
        # in the scene graph: measure it there (the card's own space) and
        # move it over by the card's place by hand.
        picture = card.component('image0')
        low, high = picture.getTightBounds(picture.getTop()) or (Point3(-0.5), Point3(0.5))
        matrix = card.getMat(other)
        corners = [matrix.xformPoint(Point3(x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
        return (Point3(min(c[0] for c in corners), 0, min(c[2] for c in corners)),
                Point3(max(c[0] for c in corners), 0, max(c[2] for c in corners)))

    def closeBingo(self):
        if self.overlayKind == 'bingo':
            self.closeOverlay()

    def updateFishing(self):
        if self.overlayKind == 'bingo':
            manager = self.bingoManager()
            card = getattr(manager, 'card', None) if manager else None
            if card is None or card.isEmpty():
                self.closeOverlay()

    # --- Golf ---

    def golfHole(self):
        course = localGolfCourse()
        if course is None:
            return None, None
        return course, base.cr.doId2do.get(getattr(course, 'curHoleDoId', 0))

    def buildGolf(self):
        self.screen.setSmooth(True)
        self.paper()
        course, hole = self.golfHole()
        self.title('Golf', font=self.signFont)
        self.controls = self.page.attachNewNode('controls')
        page, self.page = self.page, self.controls
        self.golfCourseLabel = self.label('', (0, 0, 0.62), scale=0.06, fg=INK, wordwrap=22)
        self.golfHoleLabel = self.label('', (0, 0, 0.5), scale=0.055, fg=SOFT, wordwrap=24)
        # The power bar, as on the top screen.
        self.golfPower = DirectWaitBar(parent=self.controls, pos=(0, 0, 0.33), relief=DGG.SUNKEN, frameSize=(-2.0, 2.0, -0.2, 0.2),
                                       borderWidth=(0.02, 0.02), scale=0.3, range=100, frameColor=(0.5, 0.5, 0.5, 0.5),
                                       barColor=(1.0, 0.0, 0.0, 1.0), text='', text_scale=0.26, text_fg=WHITE,
                                       text_align=TextNode.ACenter, text_pos=(0, -0.05))
        # Aim left, swing, aim right.
        image = self.find('tt_m_gui_mat_mainGui', 'tt_t_gui_mat_shuffleArrowUp')
        self.golfArrows = []
        for direction, key in ((-1, 'arrow_left'), (1, 'arrow_right')):
            arrow = DirectFrame(parent=self.controls, relief=None, image=image, scale=(-1.1 * direction, 1, 1.1),
                                pos=(direction * 0.53, 0, -0.08), state=DGG.NORMAL)
            arrow.setTransparency(TransparencyAttrib.MAlpha)
            self.holdTap(arrow, self.keyHolder(key))
            self.golfArrows.append(arrow)
        self.golfSwing = self.panel((0, 0, -0.08), 0.62, 0.62, ROSE, touchable=True, text='Swing', text_scale=0.1,
                                    text_pos=(0, -0.03), text_fg=INK, text_font=self.signFont)
        self.holdTap(self.golfSwing, self.keyHolder('space'))
        self.golfTopView = self.textButton('Top View', (0, 0, -0.52), messenger.send, 'tab', width=0.62, height=0.14,
                                           textScale=0.06, tint=SKY)
        self.golfHint = self.label('', (0, 0, -0.72), scale=0.048, fg=SOFT, wordwrap=24)
        self.page = page
        # The scorecard in the top right corner.
        gui = self.activityModel('phase_6/models/golf/golf_gui')
        icon = DirectFrame(parent=self.page, relief=None, image=gui.find('**/score_card_icon'), image_scale=(0.2, 1, 0.2),
                           pos=(0.6, 0, 0.865), state=DGG.NORMAL)
        icon.setTransparency(TransparencyAttrib.MAlpha)
        low, high = icon.getTightBounds(icon) or (Point3(-0.1), Point3(0.1))
        icon['frameSize'] = (low[0], high[0], low[2], high[2])
        self.tap(icon, self.openScorecard)
        self.refreshGolf()

    def keyHolder(self, key):
        def hold(kind, point):
            # The same keys the top screen's controls press.
            if kind == 'down':
                messenger.send(key)
            elif kind == 'up':
                messenger.send(key + '-up')
        return hold

    def refreshGolf(self):
        course, hole = self.golfHole()
        if course is None or self.controls is None or self.controls.isEmpty():
            return
        from toontown.golf import GolfGlobals
        try:
            self.golfCourseLabel['text'] = GolfGlobals.getCourseName(course.courseId)
        except Exception:
            self.golfCourseLabel['text'] = ''
        state = getattr(hole, 'state', None) if hole is not None else None
        mine = hole is not None and hole.currentGolfer == base.localAvatar.doId
        if hole is not None and getattr(hole, 'holeInfo', None):
            try:
                strokes = course.getStrokesForCurHole(base.localAvatar.doId)
            except Exception:
                strokes = 0
            self.golfHoleLabel['text'] = 'Hole %d of %d   Par %d   Strokes %d' % (
                course.curHoleIndex + 1, course.numHoles, hole.holeInfo['par'], strokes)
        else:
            self.golfHoleLabel['text'] = ''
        power = getattr(hole, 'powerBar', None) if hole is not None else None
        if power is not None and not power.isEmpty():
            self.golfPower['value'] = power['value']
            self.golfPower['text'] = power['text']
        teeing = mine and state == 'ChooseTee'
        aiming = mine and state == 'Aim'
        self.golfSwing['text'] = 'Pick Tee' if teeing else 'Swing'
        active = teeing or aiming
        for node in [self.golfSwing] + self.golfArrows:
            node.setColorScale(1, 1, 1, 1 if active else 0.45)
        if teeing:
            self.golfHint['text'] = 'Arrows change the tee spot. Pick Tee to start.'
        elif aiming:
            self.golfHint['text'] = 'Arrows aim. Hold Swing and let go at the power you want.'
        elif hole is not None and hole.currentGolfer and not mine:
            golfer = base.cr.doId2do.get(hole.currentGolfer)
            self.golfHint['text'] = '%s is up.' % golfer.getName() if golfer is not None else ''
        else:
            self.golfHint['text'] = ''

    def openScorecard(self):
        course = localGolfCourse()
        board = getattr(course, 'scoreBoard', None) if course else None
        if board is None:
            return
        board.showBoard()
        self.updateGolf()

    def updateGolf(self):
        course = localGolfCourse()
        board = getattr(course, 'scoreBoard', None) if course else None
        if board is None or board.scoreboard.isEmpty():
            if self.overlayKind == 'scorecard':
                self.closeOverlay()
            return
        shown = not board.scoreboard.isHidden()
        if self.overlayKind == 'scorecard':
            if not shown:
                self.closeOverlay()
            return
        if shown and board.scoreboard.getParent() == aspect2d:
            # Each time the scorecard pops up, it is on the bottom screen
            # until its X is pressed.
            taskMgr.remove('hide score board')
            overlay = self.openOverlay('scorecard')
            holder = overlay.attachNewNode('scorecard')
            self.borrow(board.scoreboard, holder)
            self.fitInto(holder, board.scoreboard, z=0.05, height=1.3, halfWidth=0.74)
            self.tap(board.minimizeB, pressButton, board.minimizeB)
            self.tap(board.exitCourseB, pressButton, board.exitCourseB)

    # --- Every frame ---

    def updateActivity(self):
        if self.activity == 'fishing':
            self.updateFishing()
            self.refreshFishing()
        elif self.activity == 'golf':
            self.updateGolf()
            self.refreshGolf()
