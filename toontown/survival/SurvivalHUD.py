"""Survival Mode's screen: the round bottom-left in red, the laff meter
top-right as health, the jellybean box bottom-right, the held gag at the
bottom, and the cards for pausing, going sad and game over."""

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectSlider, DirectWaitBar, OnscreenText
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
                                   frameSize=(-0.72, 0.02, -0.11, 0.11), pos=(-0.08, 0, 0.36))
        jar = loader.loadModel('phase_3.5/models/gui/jar_gui')
        self.beanIcon = DirectLabel(parent=self.beanBox, relief=None, image=jar.find('**/Jar'), image_scale=0.22, pos=(-0.58, 0, -0.01))
        jar.removeNode()
        self.beanText = OnscreenText(parent=self.beanBox, text='0', font=sign, fg=(1, 0.95, 0.4, 1), shadow=(0, 0, 0, 1),
                                     scale=0.1, pos=(-0.04, -0.035), align=TextNode.ARight, mayChange=True)
        # The held gag, bottom right under the jellybeans.
        self.gagBox = DirectFrame(parent=base.a2dBottomRight, relief=DGG.FLAT, frameColor=(0, 0, 0, 0.45),
                                  frameSize=(-0.72, 0.02, -0.09, 0.09), pos=(-0.08, 0, 0.13))
        self.invModel = loader.loadModel('phase_3.5/models/gui/inventory_icons')
        self.gagIcon = DirectLabel(parent=self.gagBox, relief=None, pos=(-0.62, 0, 0), image=None, image_scale=0.5)
        self.gagName = OnscreenText(parent=self.gagBox, text='', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                    scale=0.05, pos=(-0.51, 0.02), align=TextNode.ALeft, mayChange=True)
        self.ammoText = OnscreenText(parent=self.gagBox, text='', font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                                     scale=0.075, pos=(-0.02, -0.05), align=TextNode.ARight, mayChange=True)
        self.slotText = OnscreenText(parent=self.gagBox, text='', font=face, fg=(0.8, 0.8, 0.8, 1), shadow=(0, 0, 0, 1),
                                     scale=0.04, pos=(-0.51, -0.045), align=TextNode.ALeft, mayChange=True)
        self.reloadBar = DirectWaitBar(parent=self.gagBox, relief=DGG.FLAT, range=1.0, value=0,
                                       frameSize=(-0.69, -0.01, -0.005, 0.005), pos=(0, 0, -0.085),
                                       barColor=(1, 0.9, 0.3, 1), frameColor=(0, 0, 0, 0))
        self.reloadBar.hide()
        self.reloadTrack = None
        self.grenadeText = OnscreenText(parent=self.gagBox, text='', font=face, fg=(1, 0.85, 0.4, 1), shadow=(0, 0, 0, 1),
                                        scale=0.045, pos=(-0.02, 0.115), align=TextNode.ARight, mayChange=True)
        # Active power-ups: their pictures along the bottom middle, each
        # with the seconds left in small print just above it (BO1).
        self.powerRow = base.a2dBottomCenter.attachNewNode('survivalPowers')
        self.powerRow.setZ(0.13)
        self.powerIcons = {}
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
        self.downFrames = None
        self.setLaff(G.PLAYER_HP, G.PLAYER_HP)

    def destroy(self):
        self.setDowned(False)
        for track in (self.noticeTrack, self.hurtTrack, self.reloadTrack):
            if track:
                track.finish()
        self.closeCard()
        self.laff.stop()
        self.laff.destroy()
        self.powerRow.removeNode()
        for widget in (self.roundText, self.roundLabel, self.tonicText, self.beanBox, self.gagBox,
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
        gags = self.game.gags
        gifts = getattr(gags, 'presentations', 0) if gags else 0
        tnt = getattr(gags, 'tnt', 0) if gags else 0
        parts = []
        if tnt:
            parts.append('TNT x%d' % tnt)
        if gifts:
            parts.append('Presentation x%d' % gifts)
        self.grenadeText.setText('   '.join(parts))

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
        if self.reloadTrack:
            self.reloadTrack.finish()
        self.reloadTrack = Sequence(LerpFunc(self.__setReload, fromData=0, toData=1, duration=seconds), Func(self.reloadBar.hide))
        self.reloadTrack.start()

    def __setReload(self, value):
        if getattr(self.reloadBar, '_optionInfo', None) is not None:
            self.reloadBar['value'] = value

    def __powerIcon(self, key):
        from toontown.survival.SurvivalGame import POWER_ICONS, POWER_COLORS
        holder = self.powerRow.attachNewNode('power-' + key)
        glow = DirectFrame(parent=holder, relief=DGG.FLAT, frameColor=(0, 0, 0, 0.45), frameSize=(-0.075, 0.075, -0.075, 0.075))
        try:
            model, part, scale = POWER_ICONS[key]
            icons = loader.loadModel(model)
            icon = icons.find(part) if part else icons
            picture = icon.copyTo(holder)
            low, high = picture.getTightBounds()
            size = max(high[0] - low[0], high[2] - low[2]) if low is not None else 1.0
            picture.setScale(0.12 / max(size, 0.001))
            centre = (low + high) * 0.5 * picture.getScale()[0] if low is not None else Point3(0)
            picture.setPos(-centre[0], 0, -centre[2])
            picture.setTransparency(1)
            icons.removeNode()
        except Exception:
            OnscreenText(parent=holder, text=G.POWERUP_NAMES[key][:1], font=ToontownGlobals.getSignFont(), scale=0.08,
                         fg=POWER_COLORS.get(key, (1, 1, 1, 1)))
        timer = OnscreenText(parent=holder, text='', font=ToontownGlobals.getSignFont(), fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1),
                             scale=0.04, pos=(0, 0.09), mayChange=True)
        return holder, timer

    def setPowers(self, powers, now):
        keys = [key for key, until in sorted(powers.items(), key=lambda kv: kv[0]) if until - now > 0]
        for key in list(self.powerIcons):
            if key not in keys:
                self.powerIcons.pop(key)[0].removeNode()
        gap = 0.2
        for i, key in enumerate(keys):
            if key not in self.powerIcons:
                self.powerIcons[key] = self.__powerIcon(key)
            holder, timer = self.powerIcons[key]
            holder.setX((i - (len(keys) - 1) / 2.0) * gap)
            left = powers[key] - now
            timer.setText(str(int(left + 0.99)))
            # The last few seconds blink, as BO1's icons do.
            if left < 5 and int(left * 4) % 2:
                holder.hide()
            else:
                holder.show()

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

    # --- Downed (BO1's last stand) ---

    @staticmethod
    def vignetteTexture(size=128):
        """A red ring, clear in the middle and thick at the edges."""
        from panda3d.core import PNMImage, Texture
        image = PNMImage(size, size, 4)
        half = (size - 1) / 2.0
        for y in range(size):
            for x in range(size):
                dx, dy = (x - half) / half, (y - half) / half
                d = min(1.0, (dx * dx + dy * dy) ** 0.5 / 1.2)
                a = max(0.0, (d - 0.3) / 0.7) ** 1.25
                image.setXelA(x, y, 0.8, 0.0, 0.0, min(0.95, a * 1.1))
        tex = Texture('survivalDownVignette')
        tex.load(image)
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)
        return tex

    def setDowned(self, on):
        """Going sad: the world goes grey and a red edge beats like a heart
        (BO1's downed screen), until the toon is back up."""
        if not on:
            taskMgr.remove('survivalDownPulse')
            if self.downFrames is not None:
                for frame in self.downFrames:
                    frame.destroy()
                self.downFrames = None
            return
        if self.downFrames is not None:
            return
        # Grey over everything, drawn under the HUD (render2d's back).
        grey = DirectFrame(parent=render2d, relief=DGG.FLAT, frameColor=(0.42, 0.42, 0.44, 0.55), frameSize=(-1, 1, -1, 1),
                           sortOrder=-30)
        grey.setBin('background', 0)
        grey.setDepthWrite(0)
        ring = DirectFrame(parent=render2d, relief=DGG.FLAT, frameColor=(1, 1, 1, 1), frameSize=(-1, 1, -1, 1),
                           image=self.vignetteTexture(), image_scale=(1, 1, 1), sortOrder=-29)
        ring.setTransparency(1)
        ring['frameColor'] = (0, 0, 0, 0)
        ring.setBin('background', 1)
        ring.setDepthWrite(0)
        self.downFrames = [grey, ring]
        self.downStart = globalClock.getFrameTime()
        taskMgr.add(self.__downPulse, 'survivalDownPulse')

    def __downPulse(self, task):
        import math
        if self.downFrames is None:
            return task.done
        grey, ring = self.downFrames
        t = globalClock.getFrameTime() - self.downStart
        # A heartbeat: two quick beats, then a rest; quicker as time runs out.
        rate = 0.9 + min(1.0, t / G.BLEED_OUT) * 0.6
        beat = (t * rate) % 1.0
        pulse = math.exp(-((beat - 0.08) / 0.06) ** 2) + 0.7 * math.exp(-((beat - 0.3) / 0.06) ** 2)
        ring.setColorScale(1, 1, 1, 0.45 + 0.55 * min(1.0, pulse))
        ring.setScale(1.0 + 0.04 * pulse)
        grey['frameColor'] = (0.45 + 0.12 * pulse, 0.36, 0.38, 0.5 + 0.08 * pulse)
        return task.cont

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

    def showSettings(self, level, onChange, onBack):
        """The pause menu's Settings: camera sensitivity from 1 (very slow)
        to 10 (very fast), a slider with - and + beside it (easy with a
        controller's pointer too), and Back."""
        self.closeCard()
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        card = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.05, 0.05, 0.08, 0.9),
                           frameSize=(-0.75, 0.75, -0.55, 0.55), pos=(0, 0, 0), sortOrder=sort, state=DGG.NORMAL)
        OnscreenText(parent=card, text='Settings', font=sign, fg=RED, shadow=(0, 0, 0, 1), scale=0.14, pos=(0, 0.36))
        OnscreenText(parent=card, text='Camera Sensitivity', font=face, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), scale=0.065, pos=(0, 0.17))
        valueText = OnscreenText(parent=card, text=str(level), font=sign, fg=(1, 0.95, 0.4, 1), shadow=(0, 0, 0, 1), scale=0.1,
                                 pos=(0, -0.11), mayChange=True)
        OnscreenText(parent=card, text='1 slow          10 fast', font=face, fg=(0.8, 0.8, 0.8, 1), scale=0.045, pos=(0, -0.2))
        state = {'level': int(level)}

        def setLevel(value):
            value = max(1, min(10, int(round(value))))
            valueText.setText(str(value))
            if value != state['level']:
                state['level'] = value
                onChange(value)
            if abs(slider['value'] - value) > 0.01:
                slider['value'] = value

        slider = DirectSlider(parent=card, range=(1, 10), value=level, pageSize=1, scrollSize=1, pos=(0, 0, 0.03), scale=0.45,
                              frameColor=(0.3, 0.3, 0.35, 1), thumb_relief=DGG.FLAT, thumb_frameColor=(1, 0.95, 0.4, 1),
                              thumb_frameSize=(-0.06, 0.06, -0.12, 0.12),
                              command=lambda: setLevel(slider['value']))
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        for label, x, step in (('-', -0.6, -1), ('+', 0.6, 1)):
            DirectButton(parent=card, relief=None, image=(up, down, over), image_scale=(0.35, 1, 1.0), text=label, text_font=sign,
                         text_fg=(1, 0.95, 0.4, 1), text_scale=0.09, text_pos=(0, -0.03), pos=(x, 0, 0.03),
                         command=lambda step=step: setLevel(state['level'] + step))
        DirectButton(parent=card, relief=None, image=(up, down, over), image_scale=(1.1, 1, 1.2), text='Back', text_font=sign,
                     text_fg=(1, 0.95, 0.4, 1), text_scale=0.07, text_pos=(0, -0.02), pos=(0, 0, -0.42), command=onBack)
        gui.removeNode()
        self.card = card
        return card

    def setCinematic(self, on):
        """Hide everything but the cards while the game plays a scene."""
        for widget in (self.roundText, self.roundLabel, self.laff, self.tonicText, self.beanBox, self.gagBox,
                       self.powerRow, self.crosshair, self.prompt, self.notice, self.bigRound):
            if on:
                widget.hide()
            elif widget is not self.bigRound:
                widget.show()

    def showCard(self, title, lines, buttons, sort=100, color=None):
        """A dark card in the middle: a title, some lines and buttons
        [(label, command)]."""
        self.closeCard()
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        card = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.05, 0.05, 0.08, 0.9),
                           frameSize=(-0.75, 0.75, -0.55, 0.55), pos=(0, 0, 0), sortOrder=sort, state=DGG.NORMAL)
        OnscreenText(parent=card, text=title, font=sign, fg=color or RED, shadow=(0, 0, 0, 1), scale=0.14, pos=(0, 0.36))
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
