"""Survival Mode's screen: the round bottom-left in red, the laff meter
top-right as health, the jellybean box bottom-right, the held gag at the
bottom, and the cards for pausing, going sad and game over."""

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectWaitBar, OnscreenText
from direct.interval.IntervalGlobal import Func, LerpColorScaleInterval, LerpPosInterval, LerpScaleInterval, Parallel, Sequence, Wait
from panda3d.core import Point3, TextNode, Vec4

from toontown.survival import SurvivalGlobals as G
from toontown.toon import LaffMeter
from toontown.toonbase import ToontownBattleGlobals, ToontownGlobals

RED = (0.85, 0.08, 0.08, 1)
PANEL = (0.75, 0.05, 0.05, 0.55)


class SurvivalHUD:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalHUD')

    def __init__(self, game, dna):
        self.game = game
        self.root = aspect2d.attachNewNode('survivalHUD')
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        # Round: ImpressBT, red, bottom left.
        self.roundText = OnscreenText(parent=base.a2dBottomLeft, text='', font=sign, fg=RED, shadow=(0, 0, 0, 1),
                                      scale=0.16, pos=(0.12, 0.1), align=TextNode.ALeft, mayChange=True)
        self.roundLabel = OnscreenText(parent=base.a2dBottomLeft, text='Round', font=sign, fg=RED, shadow=(0, 0, 0, 1),
                                       scale=0.07, pos=(0.12, 0.27), align=TextNode.ALeft)
        # Laff meter as health, top right.
        self.laff = LaffMeter.LaffMeter(dna, G.PLAYER_HP, G.PLAYER_HP)
        self.laff.reparentTo(base.a2dTopRight)
        self.laff.setPos(-0.17, 0, -0.17)
        self.laff.setScale(0.1)
        self.laff.start()
        self.laff.show()
        # Tonics under it.
        self.tonicText = OnscreenText(parent=base.a2dTopRight, text='', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                      scale=0.045, pos=(-0.05, -0.36), align=TextNode.ARight, mayChange=True)
        # Jellybeans, bottom right, a little up from the bottom.
        self.beanBox = DirectFrame(parent=base.a2dBottomRight, relief=DGG.FLAT, frameColor=PANEL,
                                   frameSize=(-0.42, 0.02, -0.08, 0.08), pos=(-0.08, 0, 0.3))
        jar = loader.loadModel('phase_3.5/models/gui/jar_gui')
        self.beanIcon = DirectLabel(parent=self.beanBox, relief=None, image=jar.find('**/Jar'), image_scale=0.14, pos=(-0.34, 0, -0.01))
        jar.removeNode()
        self.beanText = OnscreenText(parent=self.beanBox, text='0', font=sign, fg=(1, 0.95, 0.4, 1), shadow=(0, 0, 0, 1),
                                     scale=0.08, pos=(-0.04, -0.028), align=TextNode.ARight, mayChange=True)
        # The held gag, bottom middle.
        self.gagBox = DirectFrame(parent=base.a2dBottomCenter, relief=DGG.FLAT, frameColor=(0, 0, 0, 0.45),
                                  frameSize=(-0.36, 0.36, -0.09, 0.09), pos=(0, 0, 0.13))
        self.invModel = loader.loadModel('phase_3.5/models/gui/inventory_icons')
        self.gagIcon = DirectLabel(parent=self.gagBox, relief=None, pos=(-0.27, 0, 0), image=None, image_scale=0.5)
        self.gagName = OnscreenText(parent=self.gagBox, text='', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                    scale=0.05, pos=(-0.16, 0.02), align=TextNode.ALeft, mayChange=True)
        self.ammoText = OnscreenText(parent=self.gagBox, text='', font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                     scale=0.075, pos=(0.33, -0.05), align=TextNode.ARight, mayChange=True)
        self.slotText = OnscreenText(parent=self.gagBox, text='', font=face, fg=(0.8, 0.8, 0.8, 1), shadow=(0, 0, 0, 1),
                                     scale=0.04, pos=(-0.16, -0.045), align=TextNode.ALeft, mayChange=True)
        self.reloadBar = DirectWaitBar(parent=self.gagBox, relief=DGG.FLAT, range=1.0, value=0,
                                       frameSize=(-0.34, 0.34, -0.005, 0.005), pos=(0, 0, -0.085),
                                       barColor=(1, 0.9, 0.3, 1), frameColor=(0, 0, 0, 0))
        self.reloadBar.hide()
        self.grenadeText = OnscreenText(parent=self.gagBox, text='', font=face, fg=(1, 0.85, 0.4, 1), shadow=(0, 0, 0, 1),
                                        scale=0.04, pos=(0.33, 0.045), align=TextNode.ARight, mayChange=True)
        # Power-ups along the top.
        self.powerText = OnscreenText(parent=base.a2dTopCenter, text='', font=sign, fg=(1, 0.9, 0.3, 1), shadow=(0, 0, 0, 1),
                                      scale=0.06, pos=(0, -0.09), mayChange=True)
        # Crosshair and prompts.
        self.crosshair = OnscreenText(parent=aspect2d, text='+', font=face, fg=(1, 1, 1, 0.85), shadow=(0, 0, 0, 1), scale=0.08, pos=(0, -0.02))
        self.prompt = OnscreenText(parent=aspect2d, text='', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                   scale=0.06, pos=(0, -0.3), mayChange=True, wordwrap=22)
        self.notice = OnscreenText(parent=aspect2d, text='', font=sign, fg=(1, 0.9, 0.3, 1), shadow=(0, 0, 0, 1),
                                   scale=0.09, pos=(0, 0.45), mayChange=True)
        self.noticeTrack = None
        self.bigRound = OnscreenText(parent=aspect2d, text='', font=sign, fg=RED, shadow=(0, 0, 0, 1), scale=0.5, pos=(0, -0.1), mayChange=True)
        self.bigRound.hide()
        self.hurtFrame = DirectFrame(parent=render2d, relief=DGG.FLAT, frameColor=(0.8, 0, 0, 0), frameSize=(-1, 1, -1, 1), state=DGG.NORMAL)
        self.hurtFrame.hide()
        self.hurtTrack = None
        self.card = None
        self.setLaff(G.PLAYER_HP, G.PLAYER_HP)

    def destroy(self):
        for track in (self.noticeTrack, self.hurtTrack):
            if track:
                track.finish()
        self.closeCard()
        self.laff.stop()
        self.laff.destroy()
        for widget in (self.roundText, self.roundLabel, self.tonicText, self.beanBox, self.gagBox, self.powerText,
                       self.crosshair, self.prompt, self.notice, self.bigRound, self.hurtFrame):
            widget.destroy()
        self.invModel.removeNode()
        self.root.removeNode()

    # --- Numbers ---

    def setRound(self, roundNum):
        self.roundText.setText(str(roundNum))
        self.bigRound.setText(str(roundNum))
        self.bigRound.show()
        self.bigRound.setColorScale(1, 1, 1, 1)
        Sequence(LerpScaleInterval(self.bigRound, 0.3, 0.6, startScale=0.3, blendType='easeOut'), Wait(1.4),
                 LerpColorScaleInterval(self.bigRound, 0.8, Vec4(1, 1, 1, 0)), Func(self.bigRound.hide)).start()

    def setLaff(self, hp, maxHp):
        self.laff.adjustFace(int(round(hp)), int(maxHp), quietly=1)

    def setBeans(self, beans):
        self.beanText.setText(str(int(beans)))

    def setTonics(self, tonics):
        names = [name for key, name, cost, blurb in G.TONICS if key in tonics]
        self.tonicText.setText('\n'.join(names))

    def setGag(self, gag, index, count):
        if gag is None:
            self.gagIcon['image'] = None
            self.gagName.setText('')
            self.ammoText.setText('')
            return
        icon = self.invModel.find('**/' + ToontownBattleGlobals.AvPropsNew[gag.track][gag.level])
        self.gagIcon['image'] = icon
        self.gagIcon['image_scale'] = 0.55
        self.gagName.setText(gag.name)
        self.ammoText.setText('%d / %d' % (gag.clip, gag.reserve))
        self.slotText.setText(' '.join(('[%d]' if i == index else '%d') % (i + 1) for i in range(count)))
        gifts = getattr(self.game.gags, 'presentations', 0) if self.game.gags else 0
        self.grenadeText.setText(('Presentation x%d' % gifts) if gifts else '')

    def setReloading(self, seconds):
        if seconds <= 0:
            self.reloadBar.hide()
            return
        self.reloadBar.show()
        self.reloadBar['value'] = 0
        Sequence(self.reloadBar.interval(0, 0) if False else Wait(0),
                 Func(self.__animateReload, seconds)).start()

    def __animateReload(self, seconds):
        from direct.interval.LerpInterval import LerpFunc
        LerpFunc(lambda v: self.reloadBar.__setitem__('value', v), fromData=0, toData=1, duration=seconds).start()
        Sequence(Wait(seconds), Func(self.reloadBar.hide)).start()

    def setPowers(self, powers, now):
        parts = []
        for key, until in powers.items():
            left = until - now
            if left > 0:
                parts.append('%s %d' % (G.POWERUP_NAMES[key], int(left + 0.99)))
        self.powerText.setText('   '.join(parts))

    # --- Moments ---

    def say(self, text, seconds=2.0):
        self.notice.setText(text)
        self.notice.setColorScale(1, 1, 1, 1)
        if self.noticeTrack:
            self.noticeTrack.finish()
        self.noticeTrack = Sequence(Wait(seconds), LerpColorScaleInterval(self.notice, 0.5, Vec4(1, 1, 1, 0)))
        self.noticeTrack.start()

    def setPrompt(self, text):
        self.prompt.setText(text or '')

    def flashHurt(self):
        self.hurtFrame.show()
        if self.hurtTrack:
            self.hurtTrack.finish()
        self.hurtTrack = Sequence(Func(self.hurtFrame.__setitem__, 'frameColor', (0.8, 0, 0, 0.35)), Wait(0.1),
                                  LerpColorScaleInterval(self.hurtFrame, 0.5, Vec4(1, 1, 1, 0), startColorScale=Vec4(1, 1, 1, 1)),
                                  Func(self.hurtFrame.hide), Func(self.hurtFrame.setColorScale, 1, 1, 1, 1))
        self.hurtTrack.start()

    def lowLaff(self, low):
        # A standing red edge while the laff is low.
        if low:
            self.hurtFrame.show()
            self.hurtFrame['frameColor'] = (0.6, 0, 0, 0.18)
        elif not self.hurtTrack or not self.hurtTrack.isPlaying():
            self.hurtFrame.hide()

    def ring(self, reach):
        pass

    def shake(self):
        if self.game.player is None:
            return
        head = self.game.player.head
        Sequence(LerpPosInterval(head, 0.05, Point3(0, 0, G.EYE_HEIGHT - 0.25)), LerpPosInterval(head, 0.1, Point3(0, 0, G.EYE_HEIGHT))).start()

    def bonk(self):
        Sequence(LerpScaleInterval(self.crosshair, 0.08, 1.6), LerpScaleInterval(self.crosshair, 0.12, 1.0)).start()

    def hitMarker(self, killed=False):
        self.crosshair.setColorScale(1, 0.3, 0.3, 1) if killed else self.crosshair.setColorScale(1, 1, 0.5, 1)
        Sequence(Wait(0.12), Func(self.crosshair.setColorScale, 1, 1, 1, 1)).start()

    # --- Cards ---

    def closeCard(self):
        if self.card:
            self.card.destroy()
            self.card = None

    def showCard(self, title, lines, buttons):
        """A dark card in the middle: a title, some lines and buttons
        [(label, command)]."""
        self.closeCard()
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        card = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.05, 0.05, 0.08, 0.9),
                           frameSize=(-0.75, 0.75, -0.55, 0.55), pos=(0, 0, 0), sortOrder=100, state=DGG.NORMAL)
        OnscreenText(parent=card, text=title, font=sign, fg=RED, shadow=(0, 0, 0, 1), scale=0.14, pos=(0, 0.36))
        OnscreenText(parent=card, text='\n'.join(lines), font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), scale=0.055, pos=(0, 0.2), wordwrap=24)
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        y = -0.42 + 0.0
        x0 = -0.3 * (len(buttons) - 1) / 1.0
        for i, (label, command) in enumerate(buttons):
            DirectButton(parent=card, relief=None, image=(up, down, over), image_scale=(1.1, 1, 1.2), text=label, text_font=sign,
                         text_fg=(1, 0.95, 0.4, 1), text_scale=0.07, text_pos=(0, -0.02), pos=(x0 + 0.6 * i, 0, y), command=command)
        gui.removeNode()
        self.card = card
        return card
