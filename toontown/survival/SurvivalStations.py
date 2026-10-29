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
        self.game.gags.upgradeHeld()
        self.game.gags.showHeld()
        self.game.hud.say('Upgraded: %s!' % self.game.gags.gag.name, 2.5)
        self.game.count('upgrades')

    def destroy(self):
        self.char.delete()
        Station.destroy(self)


class TrunkStation(Station):
    """The Mystery Box: the accessory trunk gives a random gag."""

    def __init__(self, game):
        pos, h = game.arena.trunkSpot()
        Station.__init__(self, game, pos, h, 'trunk')
        self.model = loader.loadModel('phase_4/models/minigames/treasure_chest')
        self.model.reparentTo(self.node)
        self.model.setScale(0.7)
        self.lid = self.model.find('**/lid*')
        if self.lid.isEmpty():
            self.lid = self.model.find('**/*top*')
        self.uses = 0
        self.offer = None
        self.offerUntil = 0.0
        self.shutUntil = 0.0
        self.readyAt = 0.0
        self.shown = None
        self.cycleTrack = None

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
        base.playSfx(base.loader.loadSfx('phase_4/audio/sfx/MG_sfx_travel_game_bell_for_trolley.ogg'), volume=0.4)
        # The gags whirl by above the trunk, then one stays.
        self.cycleTrack = Sequence()
        steps = 10
        for i in range(steps):
            key = random.choice(G.TRUNK_GAGS)
            self.cycleTrack.append(Func(self.__show, key))
            self.cycleTrack.append(Wait(G.TRUNK_CYCLE / steps * (0.6 + 0.08 * i)))
        self.cycleTrack.append(Func(self.__landed))
        self.cycleTrack.start()
        return True

    def __openLid(self, open):
        if self.lid.isEmpty():
            return
        LerpHprInterval(self.lid, 0.4, Vec3(0, -100 if open else 0, 0)).start()

    def __show(self, key):
        if self.shown is not None:
            self.shown.removeNode()
        track, level = key
        prop = BattleProps.globalPropPool.getProp(G.GAGS[key][5])
        prop.reparentTo(self.node)
        prop.setPos(0, 0, 4.0)
        scale = {'ship': 0.1, 'piano': 0.3, 'safe': 0.5, 'weight': 0.5, 'geyser': 0.2, 'stormcloud': 0.5, 'firehose': 0.5}.get(G.GAGS[key][5], 0.8)
        prop.setScale(scale)
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
        if self.shown is not None:
            self.shown.removeNode()
        self.model.removeNode()
        Station.destroy(self)


class FishermanStation(Station):
    """Perk-a-Cola: Fisherman Freddy sells the Toon Tonics."""

    def __init__(self, game):
        pos, h = game.arena.fishermanSpot()
        Station.__init__(self, game, pos, h, 'fisherman')
        self.toon = NPCToons.createLocalNPC(FISHERMAN_ID)
        self.toon.reparentTo(self.node)
        self.toon.setPos(0, 0, 0)
        self.toon.setH(0)
        self.toon.loop('neutral')
        self.toon.startBlink()
        self.pick = 0

    def nextTonic(self):
        owned = self.game.tonics
        choices = [t for t in G.TONICS if t[0] not in owned]
        if 'wind' in owned or self.game.secondWindBuys >= G.SECOND_WIND_BUYS:
            choices = [t for t in choices if t[0] != 'wind']
        return choices

    def prompt(self):
        choices = self.nextTonic()
        if not choices:
            return 'Freddy: you have every tonic I sell!'
        if len(self.game.tonics) >= G.TONIC_LIMIT:
            return 'Freddy: four tonics is all a toon can hold.'
        key, name, cost, blurb = choices[self.pick % len(choices)]
        return 'Use: buy %s for %d jellybeans (Swap: next tonic)\n%s' % (name, cost, blurb)

    def nextChoice(self):
        self.pick += 1

    def use(self):
        choices = self.nextTonic()
        if not choices or len(self.game.tonics) >= G.TONIC_LIMIT:
            return False
        key, name, cost, blurb = choices[self.pick % len(choices)]
        if not self.game.spend(cost):
            self.floatText('Not enough jellybeans!', (1, 0.4, 0.4, 1))
            return False
        self.game.giveTonic(key)
        self.floatText(name + '!')
        if 'wave' in self.toon.getAnimNames():
            Sequence(Func(self.toon.play, 'wave'), Wait(2.5), Func(self.toon.loop, 'neutral')).start()
        self.game.count('tonics')
        return True

    def destroy(self):
        self.toon.stopBlink()
        self.toon.delete()
        Station.destroy(self)
