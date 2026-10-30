"""The places to spend jellybeans in Survival Mode.

Mickey stands in front of the Loopy Lane tunnel and upgrades the held gag
(BO1's Pack-a-Punch). The accessory trunk by the fisherman at the gazebo
hands out a random gag (the Mystery Box, Doodle included). Fisherman
Freddy sells the Toon Tonics (the perks). Each is used by walking up
and pressing Use.
"""

import random

from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import Func, LerpColorScaleInterval, LerpHprInterval, LerpPosInterval, LerpScaleInterval, Parallel, Sequence, Wait
from direct.gui.DirectGui import DGG, DirectButton, DirectFrame, OnscreenText
from panda3d.core import Point3, TextNode, Vec3, Vec4

from toontown.battle import BattleProps
from toontown.char import Char, CharDNA
from toontown.survival import SurvivalGlobals as G
from toontown.toon import NPCToons
from toontown.toonbase import ToontownGlobals

USE_RANGE = 7.0
FISHERMAN_ID = 2012


class Station:
    """Something in the playground the player can use."""

    def __init__(self, game, pos, h, name):
        self.game = game
        self.name = name
        self.node = game.arena.root.attachNewNode('station-' + name)
        self.node.setPos(pos)
        self.node.setH(h)
        self.busy = False
        self.sign = None

    def near(self, pos):
        return (Point3(pos[0], pos[1], 0) - Point3(self.node.getX(), self.node.getY(), 0)).length() < USE_RANGE

    def prompt(self):
        return ''

    def use(self):
        return False

    def tick(self, dt, now):
        pass

    def destroy(self):
        self.node.removeNode()

    def floatText(self, text, color=(1, 0.95, 0.4, 1), height=8.0):
        node = TextNode('stationSay')
        node.setFont(ToontownGlobals.getSignFont())
        node.setAlign(TextNode.ACenter)
        node.setText(text)
        node.setTextColor(*color)
        np = self.node.attachNewNode(node)
        np.setBillboardPointEye()
        np.setScale(1.5)
        np.setPos(0, 0, height)
        np.setLightOff()
        np.setColorScaleOff()
        Sequence(LerpPosInterval(np, 1.6, Point3(0, 0, height + 2.5), blendType='easeOut'),
                 Func(np.removeNode)).start()


class MickeyStation(Station):
    """Pack-a-Punch: Mickey upgrades the held gag for 5000 jellybeans."""

    def __init__(self, game):
        pos, h = game.arena.mickeySpot()
        Station.__init__(self, game, pos, h, 'mickey')
        self.char = Char.Char()
        dna = CharDNA.CharDNA()
        dna.newChar('mk')
        self.char.setDNA(dna)
        self.char.setName('Mickey')
        self.char.reparentTo(self.node)
        self.char.loop('neutral')
        self.char.nametag3d.stash()

    def prompt(self):
        gag = self.game.gags.gag
        if gag is None:
            return ''
        if gag.upgraded:
            return 'Mickey: that %s is already upgraded!' % gag.name
        return 'Use: Mickey upgrades your %s for %d jellybeans' % (gag.name, G.MICKEY_COST)

    def use(self):
        gag = self.game.gags.gag
        if gag is None or gag.upgraded or self.busy:
            return False
        if not self.game.spend(G.MICKEY_COST):
            self.floatText('Not enough jellybeans!', (1, 0.4, 0.4, 1))
            return False
        self.busy = True
        self.working = gag
        self.game.gags.cancelReload()
        self.game.gags.hideHeld()
        # Mickey only has walk, run and neutral: he paces while he works.
        self.char.loop('walk')
        self.floatText('Hocus pocus!')
        self.game.hud.say('Mickey is working on your %s...' % gag.name, G.MICKEY_TIME)
        Sequence(Wait(G.MICKEY_TIME), Func(self.__done)).start()
        return True

    def __done(self):
        self.busy = False
        if self.char is not None and not self.char.isEmpty():
            self.char.loop('neutral')
        gag = getattr(self, 'working', None) or self.game.gags.gag
        self.working = None
        self.game.gags.upgradeGag(gag)
        self.game.gags.showHeld()
        self.game.hud.say('Upgraded: %s!' % gag.name, 2.5)
        self.game.count('upgrades')

    def destroy(self):
        self.char.delete()
        Station.destroy(self)


class TrunkStation(Station):
    """The Mystery Box: the accessory trunk gives a random gag. The lid
    swings open, the gags rise out of the trunk one after another, slower
    and slower, and the last one up is the offer."""

    TRUNK_MODEL = 'phase_5.5/models/estate/tt_m_ara_est_accessoryTrunkBoy'
    SHOW_SCALE = {'ship': 0.12, 'piano': 0.35, 'safe': 0.55, 'weight': 0.6, 'anvil': 0.7, 'geyser': 0.25, 'stormcloud': 0.6,
                  'firehose': 0.6, 'sandbag': 0.9, 'flowerpot': 0.9, 'bikehorn': 1.2, 'whistle': 1.6, 'bugle': 1.2,
                  'aoogah': 1.1, 'elephant': 1.0, 'fog_horn': 0.9, 'glass': 1.4, 'water-gun': 1.2, 'bottle': 1.2}
    STEPS = 14
    # The biggest side of any shown gag, in feet: within the trunk's lid.
    SHOW_SIZE = 1.6

    def __init__(self, game):
        pos, h = game.arena.trunkSpot()
        Station.__init__(self, game, pos, h, 'trunk')
        self.model = loader.loadModel(self.TRUNK_MODEL)
        self.model.reparentTo(self.node)
        self.model.setLightOff()
        self.model.setColorScaleOff()
        for name in ('**/collision', '**/dropShadow'):
            piece = self.model.find(name)
            if not piece.isEmpty():
                piece.stash()
        # The lid turns about its hinge, the way DistributedTrunk opens it.
        self.lid = self.model.find('**/lid')
        self.lidOrigin = self.model.find('**/lid_origin')
        if self.lidOrigin.isEmpty():
            self.lidOrigin = self.model.attachNewNode('lid_origin')
            self.lidOrigin.setPos(0, 1, 1.97)
        if not self.lid.isEmpty():
            self.lid.wrtReparentTo(self.lidOrigin)
        self.lidTrack = None
        # Where the gags rise to: above the open trunk, facing the playground.
        self.stage = self.node.attachNewNode('trunkStage')
        self.stage.setPos(0, 0, 1.6)
        self.uses = 0
        self.offer = None
        self.offerUntil = 0.0
        self.shutUntil = 0.0
        self.readyAt = 0.0
        self.shown = None
        self.shownKey = None
        self.cycleTrack = None
        self.bell = base.loader.loadSfx('phase_4/audio/sfx/MG_sfx_travel_game_bell_for_trolley.ogg')
        self.tick_ = base.loader.loadSfx('phase_3/audio/sfx/GUI_rollover.ogg')

    def cost(self):
        return G.TRUNK_SALE_COST if self.game.power('trunksale') else G.TRUNK_COST

    def prompt(self):
        now = globalClock.getFrameTime()
        if now < self.shutUntil:
            return 'The trunk is shut for %d more seconds' % int(self.shutUntil - now + 0.99)
        if self.offer is not None:
            track, level = self.offer
            return 'Use: take the %s (%d s)' % (G.gagName(track, level), int(self.offerUntil - now + 0.99))
        if self.busy:
            return ''
        return 'Use: open the trunk for %d jellybeans' % self.cost()

    def use(self):
        now = globalClock.getFrameTime()
        if now < self.shutUntil or now < self.readyAt:
            return False
        if self.offer is not None:
            track, level = self.offer
            if self.offer == G.PRESENTATION:
                # Not a gag slot: it goes in the Presentation pocket.
                gags = self.game.gags
                if gags.presentations >= G.PRESENTATION_MAX:
                    self.floatText('Your pockets are full!', (1, 0.4, 0.4, 1))
                    return False
                self.__clearOffer()
                gags.presentations += 1
                self.game.hud.setGag(gags.gag, gags.current, len(gags.gags))
                self.game.hud.say('Got a Presentation! Press the Presentation button to throw it.', 2.5)
                self.game.count('trunk gags')
                self.readyAt = now + G.TRUNK_REUSE
                return True
            self.__clearOffer()
            gag = self.game.gags.give(track, level)
            self.game.hud.say('Got a %s!' % gag.name, 2.0)
            self.game.count('trunk gags')
            self.readyAt = now + G.TRUNK_REUSE
            return True
        if self.busy:
            return False
        if not self.game.spend(self.cost()):
            self.floatText('Not enough jellybeans!', (1, 0.4, 0.4, 1))
            return False
        self.busy = True
        self.uses += 1
        self.__openLid(True)
        base.playSfx(self.bell, volume=0.4)
        # The gags come up out of the trunk one after another, each a
        # little slower than the last (BO1's box spins down the same way),
        # and the last one up stays.
        self.cycleTrack = Sequence(Wait(0.5))
        total = sum(0.5 + 0.09 * i for i in range(self.STEPS))
        last = None
        for i in range(self.STEPS):
            key = random.choice([k for k in G.TRUNK_GAGS if k != last] or G.TRUNK_GAGS)
            last = key
            self.cycleTrack.append(Func(self.__show, key))
            self.cycleTrack.append(Wait(G.TRUNK_CYCLE * (0.5 + 0.09 * i) / total))
        self.cycleTrack.append(Func(self.__landed))
        self.cycleTrack.start()
        return True

    def __openLid(self, open):
        if self.lidOrigin.isEmpty():
            return
        if self.lidTrack:
            self.lidTrack.finish()
        self.lidTrack = LerpHprInterval(self.lidOrigin, 0.5, Vec3(0, -80 if open else 0, 0), blendType='easeOut')
        self.lidTrack.start()

    def __show(self, key):
        if self.shown is not None:
            self.shown.removeNode()
        track, level = key
        name = '1dollar' if key == G.PRESENTATION else G.GAGS[key][5]
        prop = BattleProps.globalPropPool.getProp(name)
        prop.reparentTo(self.stage)
        # Every gag shown the same size, fitted to the trunk's opening.
        prop.setScale(1.0)
        low, high = prop.getTightBounds()
        size = max(high[0] - low[0], high[1] - low[1], high[2] - low[2]) if low is not None else 1.0
        prop.setScale(self.SHOW_SIZE / max(size, 0.01))
        prop.setH(random.uniform(-40, 40))
        if key == G.PRESENTATION:
            # The flat bill turns to face whoever looks at the trunk.
            prop.setBillboardPointEye()
        # Up out of the trunk and hanging there.
        prop.setPos(0, 0, 0)
        LerpPosInterval(prop, 0.18, Point3(0, 0, 1.6), startPos=Point3(0, 0, 0), blendType='easeOut').start()
        base.playSfx(self.tick_, volume=0.5)
        self.shown = prop
        self.shownKey = key

    def __landed(self):
        self.cycleTrack = None
        now = globalClock.getFrameTime()
        doodle = False
        for limit, odds in G.DOODLE_ODDS:
            if self.uses <= limit:
                doodle = self.uses > 3 and random.random() < odds
                break
        if doodle:
            # A Doodle pops out instead: the beans come back and the trunk
            # shuts for a while.
            if self.shown is not None:
                self.shown.removeNode()
                self.shown = None
            self.floatText('A Doodle! Not now...', (0.6, 0.9, 1, 1))
            self.game.earn(self.cost(), silent=True)
            self.shutUntil = now + G.DOODLE_SHUT
            self.busy = False
            self.__openLid(False)
            self.game.count('doodles')
            return
        self.offer = self.shownKey
        self.offerUntil = now + G.TRUNK_OFFER
        self.busy = False
        track, level = self.offer
        self.floatText(G.gagName(track, level), height=6.0)
        if self.shown is not None:
            Sequence(LerpScaleInterval(self.shown, 0.3, self.shown.getScale() * 1.3), LerpScaleInterval(self.shown, 0.3, self.shown.getScale())).start()

    def __clearOffer(self):
        self.offer = None
        if self.shown is not None:
            self.shown.removeNode()
            self.shown = None
        self.__openLid(False)

    def tick(self, dt, now):
        if self.offer is not None and now >= self.offerUntil:
            # Not taken: it sinks back in.
            self.__clearOffer()
            self.readyAt = now + G.TRUNK_REUSE
        if self.shown is not None and not self.shown.isEmpty():
            self.shown.setH(self.shown.getH() + 90 * dt)

    def destroy(self):
        if self.cycleTrack:
            self.cycleTrack.finish()
        if self.lidTrack:
            self.lidTrack.finish()
        if self.shown is not None:
            self.shown.removeNode()
        self.model.removeNode()
        Station.destroy(self)


class TonicMenu:
    """Fisherman Freddy's menu: the four Toon Tonics, each with its price
    and what it does, and a Buy button. The game waits while it is open."""

    def __init__(self, station):
        self.station = station
        self.game = station.game
        sign = ToontownGlobals.getSignFont()
        face = ToontownGlobals.getInterfaceFont()
        self.frame = DirectFrame(parent=aspect2d, relief=DGG.FLAT, frameColor=(0.05, 0.05, 0.08, 0.92),
                                 frameSize=(-0.95, 0.95, -0.62, 0.62), pos=(0, 0, 0), sortOrder=100, state=DGG.NORMAL)
        OnscreenText(parent=self.frame, text="Fisherman Freddy's Toon Tonics", font=sign, fg=(1, 0.3, 0.3, 1),
                     shadow=(0, 0, 0, 1), scale=0.1, pos=(0, 0.47))
        self.beansText = OnscreenText(parent=self.frame, text='', font=face, fg=(1, 0.95, 0.4, 1), shadow=(0, 0, 0, 1),
                                      scale=0.05, pos=(0, 0.39))
        self.rows = []
        gui = loader.loadModel('phase_3/models/gui/quit_button')
        up, down, over = gui.find('**/QuitBtn_UP'), gui.find('**/QuitBtn_DN'), gui.find('**/QuitBtn_RLVR')
        colors = {'toonup': (0.3, 0.75, 0.35, 1), 'seltzer': (0.35, 0.6, 1, 1), 'wind': (1, 0.6, 0.25, 1), 'sprint': (0.85, 0.4, 0.9, 1)}
        for i, (key, name, cost, blurb) in enumerate(G.TONICS):
            z = 0.26 - i * 0.19
            row = DirectFrame(parent=self.frame, relief=DGG.FLAT, frameColor=(1, 1, 1, 0.08), frameSize=(-0.88, 0.88, -0.08, 0.08), pos=(0, 0, z))
            bottle = DirectFrame(parent=row, relief=DGG.FLAT, frameColor=colors.get(key, (1, 1, 1, 1)), frameSize=(-0.035, 0.035, -0.055, 0.055), pos=(-0.8, 0, 0))
            OnscreenText(parent=row, text=name, font=sign, fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), scale=0.06, pos=(-0.72, 0.015), align=TextNode.ALeft)
            OnscreenText(parent=row, text=blurb, font=face, fg=(0.85, 0.85, 0.85, 1), scale=0.04, pos=(-0.72, -0.045), align=TextNode.ALeft, wordwrap=26)
            price = OnscreenText(parent=row, text='%d' % cost, font=sign, fg=(1, 0.95, 0.4, 1), shadow=(0, 0, 0, 1), scale=0.06, pos=(0.5, -0.02), align=TextNode.ARight)
            button = DirectButton(parent=row, relief=None, image=(up, down, over, up), image_scale=(0.42, 1, 0.75), image3_color=(0.5, 0.5, 0.5, 0.6),
                                  text='Buy', text_font=sign, text_fg=(1, 0.95, 0.4, 1), text3_fg=(0.7, 0.7, 0.7, 1), text_scale=0.045, text_pos=(0, -0.015),
                                  pos=(0.72, 0, 0), command=self.buy, extraArgs=[key])
            self.rows.append((key, cost, button, price))
        DirectButton(parent=self.frame, relief=None, image=(up, down, over), image_scale=(1.0, 1, 1.1), text='Close', text_font=sign,
                     text_fg=(1, 0.95, 0.4, 1), text_scale=0.065, text_pos=(0, -0.02), pos=(0, 0, -0.53), command=self.close)
        gui.removeNode()
        self.refresh()

    def refresh(self):
        game = self.game
        self.beansText.setText('You have %d jellybeans. %d of %d tonics.' % (game.beans, len(game.tonics), G.TONIC_LIMIT))
        for key, cost, button, price in self.rows:
            owned = key in game.tonics
            soldOut = key == 'wind' and game.secondWindBuys >= G.SECOND_WIND_BUYS
            full = len(game.tonics) >= G.TONIC_LIMIT
            can = not owned and not soldOut and not full and game.beans >= cost
            button['state'] = DGG.NORMAL if can else DGG.DISABLED
            button['text'] = 'Got it' if owned else ('Sold out' if soldOut else 'Buy')
            price.setFg((1, 0.95, 0.4, 1) if game.beans >= cost or owned else (1, 0.45, 0.45, 1))

    def buy(self, key):
        if self.station.buy(key):
            self.refresh()

    def close(self):
        if self.frame is None:
            return
        self.frame.destroy()
        self.frame = None
        self.station.menuClosed()


class FishermanStation(Station):
    """Perk-a-Cola: Fisherman Freddy sells the Toon Tonics from a menu."""

    def __init__(self, game):
        pos, h = game.arena.fishermanSpot()
        Station.__init__(self, game, pos, h, 'fisherman')
        self.toon = NPCToons.createLocalNPC(FISHERMAN_ID)
        self.toon.reparentTo(self.node)
        self.toon.setPos(0, 0, 0)
        self.toon.setH(0)
        self.toon.loop('neutral')
        self.toon.startBlink()
        self.menu = None

    def forSale(self):
        owned = self.game.tonics
        choices = [t for t in G.TONICS if t[0] not in owned]
        if 'wind' in owned or self.game.secondWindBuys >= G.SECOND_WIND_BUYS:
            choices = [t for t in choices if t[0] != 'wind']
        return choices

    def prompt(self):
        if not self.forSale():
            return 'Freddy: you have every tonic I sell!'
        if len(self.game.tonics) >= G.TONIC_LIMIT:
            return 'Freddy: four tonics is all a toon can hold.'
        return "Use: see Fisherman Freddy's Toon Tonics"

    def nextChoice(self):
        pass

    def use(self):
        if self.menu is not None:
            return False
        self.menu = TonicMenu(self)
        self.game.menuOpened(self)
        return True

    def buy(self, key):
        for tonicKey, name, cost, blurb in self.forSale():
            if tonicKey != key:
                continue
            if len(self.game.tonics) >= G.TONIC_LIMIT:
                return False
            if not self.game.spend(cost):
                return False
            self.game.giveTonic(key)
            self.floatText(name + '!')
            if 'wave' in self.toon.getAnimNames():
                Sequence(Func(self.toon.play, 'wave'), Wait(2.5), Func(self.toon.loop, 'neutral')).start()
            self.game.count('tonics')
            return True
        return False

    def closeMenu(self):
        if self.menu is not None:
            menu = self.menu
            self.menu = None
            menu.close()

    def menuClosed(self):
        self.menu = None
        self.game.menuClosed(self)

    def destroy(self):
        self.closeMenu()
        self.toon.stopBlink()
        self.toon.delete()
        Station.destroy(self)
