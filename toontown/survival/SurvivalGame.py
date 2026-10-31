"""Survival Mode: the game itself.

Toontown Central after dark, the player in first person with up to three
NPC toons, cogs falling from the sky in rounds. This module is the
director: it owns the arena, the player, the cogs, the gags, the HUD, the
stations and the NPC toons, runs the rounds and the jellybeans, hands out
power-ups and decides when the game is over. Everything happens on the
client; no district is involved.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import Func, LerpColorScaleInterval, LerpPosInterval, Sequence, Wait
from direct.showbase.DirectObject import DirectObject
from direct.showbase.PythonUtil import Functor
from panda3d.core import ClockObject, CollisionTraverser, Point3, TextNode, Vec3, Vec4

from toontown.survival import SurvivalGlobals as G
from toontown.survival.SurvivalArena import SurvivalArena
from toontown.survival.SurvivalCog import SurvivalCog
from toontown.survival.SurvivalGags import GagHandler
from toontown.survival.SurvivalHUD import SurvivalHUD
from toontown.survival.SurvivalNPC import SurvivalNPC
from toontown.survival.SurvivalPlayer import SurvivalPlayer
from toontown.survival.SurvivalStations import FishermanStation, MickeyStation, TrunkStation
from toontown.suit import SuitDNA
from toontown.toonbase import ToontownGlobals

MUSIC = 'phase_8/audio/bgm/DL_nbrhood.ogg'
SNATCHER_SOUND = 'phase_5/audio/sfx/lightning_1.ogg'
# The round changes to the jingle a trolley game ends with (Arthur).
ROUND_SOUND = 'phase_4/audio/sfx/MG_win.ogg'
BEAN_SOUND = 'phase_4/audio/sfx/SZ_DD_treasure.ogg'
POWER_SOUND = 'phase_4/audio/sfx/MG_pairing_match.ogg'
REVIVE_SOUND = 'phase_5/audio/sfx/AA_heal_tickle.ogg'
PICKUP_RANGE = 3.5
# The player's body can't go into a cog's: it is pushed out to this far
# past the cog's radius.
PLAYER_RADIUS = 1.3
# Only the nearest few cogs are heard stepping.
STEP_COGS = 5
TOUCH_SETTING = ('survival', 'best-round')
# Model, piece and scale of the picture over each drop.
POWER_ICONS = {'maxgags': ('phase_3.5/models/gui/inventory_icons', '**/inventory_cake', 1.2),
               'instapop': ('phase_3.5/models/gui/inventory_icons', '**/inventory_tnt', 1.2),
               'toonado': ('phase_3.5/models/gui/inventory_icons', '**/inventory_storm_cloud', 1.2),
               'doublebeans': ('phase_3.5/models/gui/jar_gui', None, 1.2),
               'trunksale': ('phase_3.5/models/gui/inventory_icons', '**/inventory_screen', 1.2)}
POWER_COLORS = {'maxgags': (0.4, 0.9, 1, 1), 'instapop': (1, 0.5, 0.2, 1), 'toonado': (1, 1, 0.3, 1),
                'doublebeans': (1, 0.3, 0.3, 1), 'trunksale': (0.6, 1, 0.5, 1)}


class PowerDrop:
    """A power-up on the ground where a cog popped."""

    def __init__(self, game, key, pos, now):
        self.game = game
        self.key = key
        self.pos = Point3(pos)
        self.until = now + G.DROP_LIFE
        self.node = game.arena.root.attachNewNode('drop-' + key)
        self.node.setPos(pos)
        text = TextNode('dropText')
        text.setFont(ToontownGlobals.getSignFont())
        text.setAlign(TextNode.ACenter)
        text.setText(G.POWERUP_NAMES[key].upper())
        text.setTextColor(*POWER_COLORS[key])
        text.setShadow(0.05, 0.05)
        text.setShadowColor(0, 0, 0, 1)
        self.label = self.node.attachNewNode(text)
        self.label.setBillboardPointEye()
        self.label.setScale(1.1)
        self.label.setZ(2.0)
        self.label.setLightOff()
        self.label.setColorScaleOff()
        self.label.setDepthWrite(0)
        self.label.setBin('fixed', 50)
        self.glow = loader.loadModel('phase_3/models/props/drop_shadow')
        self.glow.reparentTo(self.node)
        self.glow.setScale(0.35)
        self.glow.setColor(*POWER_COLORS[key])
        self.glow.setZ(0.1)
        # A spinning picture of the power-up hangs over the glow, as BO1's
        # power-ups do, with its name above.
        self.icon = None
        try:
            model, part, scale = POWER_ICONS[key]
            icons = loader.loadModel(model)
            icon = icons.find(part) if part else icons
            if not icon.isEmpty():
                self.icon = icon.copyTo(self.node)
                # GUI icons are a few inches across: fit the picture to a
                # fixed size in feet.
                low, high = self.icon.getTightBounds()
                size = max(high[0] - low[0], high[2] - low[2]) if low is not None else 1.0
                self.icon.setScale(scale / max(size, 0.001))
                self.icon.setZ(1.4)
                # The icon is a flat card facing -Y; it spins upright (tick
                # turns its heading), never lies flat, or it is seen edge-on.
                self.icon.setLightOff()
                self.icon.setColorScaleOff()
                self.icon.setTransparency(1)
                self.icon.setTwoSided(1)
                self.icon.setBin('fixed', 49)
                self.icon.setDepthWrite(0)
            icons.removeNode()
        except Exception:
            self.icon = None
        self.label.setZ(2.9)
        self.label.setScale(0.8)
        self.phase = random.uniform(0, 6.28)

    def tick(self, now):
        bob = 0.3 * math.sin(now * 3 + self.phase)
        self.label.setZ(2.9 + bob)
        if self.icon is not None:
            self.icon.setZ(1.4 + bob)
            self.icon.setH(now * 90 % 360)
        left = self.until - now
        if left < G.DROP_BLINK:
            self.node.setColorScale(1, 1, 1, 0.3 + 0.7 * (0.5 + 0.5 * math.sin(now * 12)))
        return left > 0

    def destroy(self):
        self.node.removeNode()


class SurvivalGame(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalGame')

    def __init__(self, dna, name, npcCount, doneEvent):
        DirectObject.__init__(self)
        self.dna = dna
        self.name = name
        self.npcCount = max(0, min(3, int(npcCount)))
        self.doneEvent = doneEvent
        self.over = False
        self.paused = False
        self.menuStation = None
        self.frozenAt = None
        self.roundNum = 0
        self.snatcherRound = False
        self.nextSnatcherRound = random.randint(*G.FIRST_SNATCHER_ROUND)
        self.lastPop = None
        self.beans = G.START_BEANS
        self.tonics = []
        self.secondWindBuys = 0
        # While a Second Wind runs: when the player gets back up.
        self.secondWindAt = None
        self.powers = {}
        self.cogs = []
        self.drops = []
        self.dropsThisRound = 0
        self.stats = {}
        self.lure = None
        self.startTime = globalClock.getFrameTime()
        self.player = None
        self.npcs = []
        self.hud = None
        self.gags = None
        self.stations = []
        # Round bookkeeping.
        self.toSpawn = 0
        self.nextSpawn = 0.0
        self.roundState = 'idle'
        self.roundChangeAt = 0.0
        self.cogSerial = 0
        self.lastBonk = -10.0
        self.music = None
        self.stepCogs = set()
        self.nextStepPick = 0.0
        self.nextPrompt = 0.0
        self.card = None
        self.build()

    # --- Setting up and tearing down ---

    def build(self):
        base.setBackgroundColor(Vec4(0.05, 0.05, 0.1, 1))
        # From Pick-A-Toon there is no collision traverser yet.
        self.ownTrav = not isinstance(base.cTrav, CollisionTraverser)
        if self.ownTrav:
            base.cTrav = CollisionTraverser('survival')
        self.arena = SurvivalArena()
        # The toon's arms hang close to the camera.
        base.camLens.setNear(0.3)
        start, h = G.PLAYER_START if hasattr(G, 'PLAYER_START') else (Point3(0, -20, 0), 0)
        start, h = self.arena.placeOnGround(start[0], start[1], h)
        self.arena.buildReach(start)
        self.player = SurvivalPlayer(self, start, h)
        self.hud = SurvivalHUD(self, self.dna)
        self.gags = GagHandler(self, self.player)
        self.stations = [MickeyStation(self), TrunkStation(self), FishermanStation(self)]
        for i in range(self.npcCount):
            angle = math.radians(120 * i - 60)
            spot, sh = self.arena.placeOnGround(start[0] + 5 * math.sin(angle), start[1] + 5 * math.cos(angle) + 3, 0)
            self.npcs.append(SurvivalNPC(self, i, spot))
        self.hud.setLaff(self.player.hp, self.player.maxHp)
        self.hud.setBeans(self.beans)
        self.hud.setTonics(self.tonics)
        self.gags.showHeld()
        self.hud.setGag(self.gags.gag, self.gags.current, len(self.gags.gags))
        self.music = base.loader.loadMusic(MUSIC)
        if self.music:
            self.music.setLoop(True)
            self.music.setVolume(0.5)
            self.music.play()
        self.player.enable()
        self.player.setLook(0, 0)
        taskMgr.add(self.__tick, 'survivalGame')
        self.hud.say('Cogs incoming! Hold on to your laff.', 3.0)
        self.roundState = 'intermission'
        self.roundChangeAt = globalClock.getFrameTime() + 4.0

    def destroy(self):
        self.thawClock()
        self.over = True
        taskMgr.remove('survivalGame')
        self.ignoreAll()
        if self.music:
            self.music.stop()
            self.music = None
        for cog in list(self.cogs):
            cog.dead = True
            cog.destroy()
        self.cogs = []
        for drop in self.drops:
            drop.destroy()
        self.drops = []
        for npc in self.npcs:
            npc.destroy()
        self.npcs = []
        for station in self.stations:
            station.destroy()
        self.stations = []
        if self.gags:
            self.gags.destroy()
            self.gags = None
        if self.player:
            self.player.destroy()
            self.player = None
        if self.hud:
            self.hud.destroy()
            self.hud = None
        camera.reparentTo(render)
        camera.setPosHpr(0, 0, 0, 0, 0, 0)
        base.camLens.setNear(ToontownGlobals.DefaultCameraNear)
        self.arena.destroy()
        if self.ownTrav:
            base.cTrav = 0
        base.setBackgroundColor(ToontownGlobals.DefaultBackgroundColor)

    def count(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    # --- The rounds ---

    def startRound(self):
        self.roundNum += 1
        self.roundState = 'spawning'
        self.snatcherRound = self.roundNum == self.nextSnatcherRound
        if self.snatcherRound:
            self.nextSnatcherRound = self.roundNum + random.randint(*G.SNATCHER_ROUND_GAP)
            self.toSpawn = G.snatchersInRound(self.roundNum, self.npcCount)
            self.count('snatcher rounds')
        else:
            self.toSpawn = G.cogsInRound(self.roundNum, self.npcCount)
        self.nextSpawn = globalClock.getFrameTime() + 1.0
        self.dropsThisRound = 0
        self.gags.addTnt(G.TNT_PER_ROUND)
        self.hud.setRound(self.roundNum)
        self.arena.setFog(self.snatcherRound)
        if self.snatcherRound:
            self.hud.say('Gag-Snatchers!', 3.0)
            base.playSfx(base.loader.loadSfx(SNATCHER_SOUND), volume=0.8)
        else:
            base.playSfx(base.loader.loadSfx(ROUND_SOUND), volume=0.7)
        self.notify.info('round %d: %d cogs, %d HP each, cap %d' % (self.roundNum, self.toSpawn, G.cogHp(self.roundNum), G.aliveCap(self.roundNum, self.npcCount)))

    def endRound(self):
        self.roundState = 'intermission'
        self.roundChangeAt = globalClock.getFrameTime() + G.INTERMISSION
        self.hud.say('Round %d cleared!' % self.roundNum, 3.0)
        if self.snatcherRound:
            # BO1: a Max Ammo where the last hound fell.
            self.arena.setFog(False)
            pos = self.lastPop if self.lastPop is not None else self.player.getPos()
            self.drops.append(PowerDrop(self, 'maxgags', pos, globalClock.getFrameTime()))
        self.count('rounds cleared')
        # BO1: the fallen get up between rounds.
        for npc in self.npcs:
            if npc.down:
                npc.getUp()

    def __spawnOne(self, now):
        alive = [c for c in self.cogs if not c.dead]
        if len(alive) >= G.aliveCap(self.roundNum, self.npcCount):
            return
        toons = [self.player.getPos()] + [n.getPos() for n in self.npcs]
        landing = self.arena.pickLanding(toons, self.player.getEye(), self.player.getForward())
        if landing is None:
            return
        looks = G.COG_LOOKS[0][1]
        for minRound, names in G.COG_LOOKS:
            if self.roundNum >= minRound:
                looks = names
        name = random.choice(looks)
        if self.snatcherRound:
            name = random.choice(G.SNATCHER_LOOKS)
        self.cogSerial += 1
        cog = SurvivalCog(self, name, landing, self.roundNum, snatcher=self.snatcherRound)
        self.cogs.append(cog)
        if self.lure:
            # A cog dropping in during a Presentation can't look away either.
            cog.lureTo(*self.lure)
        elif self.secondWindAt is not None:
            cog.fleeFrom(self.player.getPos(), self.secondWindAt)
        self.toSpawn -= 1
        self.nextSpawn = now + G.spawnDelay(self.roundNum) * random.uniform(0.7, 1.3)

    # --- Each frame ---

    def __tick(self, task):
        if self.over or self.paused:
            return task.cont
        dt = globalClock.getDt()
        now = globalClock.getFrameTime()
        if self.roundState == 'intermission' and now >= self.roundChangeAt:
            self.startRound()
        elif self.roundState == 'spawning':
            if self.toSpawn > 0:
                if now >= self.nextSpawn:
                    self.__spawnOne(now)
            elif not any(not c.dead for c in self.cogs):
                self.endRound()
        if now >= self.nextStepPick:
            self.nextStepPick = now + 0.3
            eye = self.player.getPos()
            near = sorted((c for c in self.cogs if not c.dead and c.state == 'chase'),
                          key=lambda c: (c.pos[0] - eye[0]) ** 2 + (c.pos[1] - eye[1]) ** 2)
            self.stepCogs = set(near[:STEP_COGS])
        for cog in list(self.cogs):
            if not cog.dead:
                cog.tick(dt, now)
        self.__keepOutOfCogs()
        for npc in self.npcs:
            npc.tick(dt, now)
        for station in self.stations:
            station.tick(dt, now)
        self.gags.tick(dt)
        # Power-ups time out, on the ground and in effect.
        for drop in list(self.drops):
            if not drop.tick(now):
                drop.destroy()
                self.drops.remove(drop)
                continue
            for toon in [self.player] + self.npcs:
                if toon.alive() and (Vec3(toon.getPos() - drop.pos)).length() < PICKUP_RANGE:
                    self.__pickUp(drop, now)
                    break
        if self.powers:
            for key, until in list(self.powers.items()):
                if now >= until:
                    del self.powers[key]
            self.hud.setPowers(self.powers, now)
        if self.lure and now >= self.lure[1]:
            self.lure = None
        if self.player.using:
            self.__holdUse(dt)
        if now >= self.nextPrompt:
            self.nextPrompt = now + 0.2
            self.hud.setPrompt(self.__prompt())
            self.hud.lowLaff(self.player.hp < G.LOW_HP and not self.player.down)
        return task.cont

    def __keepOutOfCogs(self):
        """The player can't walk through a cog: a body that ends up inside
        one is pushed back out, the way the walls push."""
        player = self.player
        if player is None:
            return
        body = player.body
        pos = body.getPos(render)
        moved = False
        for cog in self.cogs:
            if cog.dead or cog.state not in ('chase', 'swing'):
                continue
            if abs(cog.pos[2] - pos[2]) > cog.height:
                continue
            away = Vec3(pos[0] - cog.pos[0], pos[1] - cog.pos[1], 0)
            room = cog.radius + PLAYER_RADIUS
            d = away.length()
            if d >= room:
                continue
            if d < 0.01:
                away = -player.getFlatForward()
                d = 1.0
            away *= (room - d) / d
            pos = Point3(pos[0] + away[0], pos[1] + away[1], pos[2])
            moved = True
        if moved:
            body.setPos(render, pos)

    # --- What the cogs ask ---

    def wantCogSteps(self, cog):
        return cog in self.stepCogs

    def nearestToon(self, pos):
        best, bestDist = None, 1e9
        for toon in [self.player] + self.npcs:
            if not toon.alive():
                continue
            p = toon.getPos()
            d = (Vec3(p[0] - pos[0], p[1] - pos[1], 0)).length()
            if d < bestDist:
                best, bestDist = toon, d
        return best

    def power(self, key):
        return key in self.powers

    def hasTonic(self, key):
        return key in self.tonics

    def cogPopped(self, cog, head=False, bonk=False):
        self.count('cogs popped')
        self.lastPop = Point3(cog.pos)
        bonus = G.BEANS_BONK_KILL if bonk else (G.BEANS_HEAD_KILL if head else G.BEANS_KILL)
        if getattr(cog, 'lastHitByNPC', False):
            bonus = bonus // 2
        self.earn(bonus)
        self.hud.hitMarker(killed=True)
        self.__maybeDrop(cog.pos)

    def cogGone(self, cog):
        if cog in self.cogs:
            self.cogs.remove(cog)

    # --- What the gags ask ---

    def damageCog(self, cog, damage, head=False, bonk=False, byNPC=False):
        if cog.dead:
            return 0
        cog.lastHitByNPC = byNPC
        result = cog.hurt(damage, head, bonk)
        if result and not byNPC:
            self.earn(G.BEANS_HIT)
            if result == 1:
                self.hud.hitMarker(killed=False)
        self.count('hits')
        return result

    def damageArea(self, point, radius, damage, head=False):
        hit = 0
        for cog in list(self.cogs):
            if cog.dead:
                continue
            d = (Vec3(cog.pos[0] - point[0], cog.pos[1] - point[1], 0)).length()
            if d <= radius + cog.radius:
                falloff = 1.0 if d < radius * 0.5 else 0.6
                self.damageCog(cog, int(damage * falloff), head=head)
                hit += 1
        return hit

    def startLure(self, point, until):
        self.lure = (Point3(point), until)
        for cog in self.cogs:
            if not cog.dead:
                cog.lureTo(point, until)
        self.hud.say('Presentation! The cogs can\'t look away.', 2.5)
        self.count('presentations')

    # --- Jellybeans ---

    def earn(self, amount, silent=False):
        if self.power('doublebeans'):
            amount *= 2
        self.beans += amount
        self.hud.setBeans(self.beans)
        self.count('beans earned', amount)

    def spend(self, cost):
        if self.beans < cost:
            return False
        self.beans -= cost
        self.hud.setBeans(self.beans)
        base.playSfx(base.loader.loadSfx(BEAN_SOUND), volume=0.5)
        return True

    def giveTonic(self, key):
        if key == 'wind':
            self.secondWindBuys += 1
        if key not in self.tonics:
            self.tonics.append(key)
        if key == 'toonup':
            self.player.setMaxHp(G.TONIC_HP)
        self.hud.setTonics(self.tonics)
        base.playSfx(base.loader.loadSfx(REVIVE_SOUND), volume=0.6)

    def loseTonics(self, keepWind=False):
        self.tonics = [t for t in self.tonics if keepWind and t == 'wind']
        self.player.setMaxHp(G.PLAYER_HP)
        self.hud.setTonics(self.tonics)

    # --- Power-ups ---

    def __maybeDrop(self, pos):
        if self.dropsThisRound >= G.DROPS_PER_ROUND:
            return
        chance = G.DROP_CHANCE + (G.DROP_CHANCE_STEP if not self.drops else 0)
        if random.random() >= chance:
            return
        key = random.choice(G.POWERUPS)
        if key == 'trunksale' and self.power('trunksale'):
            key = 'doublebeans'
        now = globalClock.getFrameTime()
        self.drops.append(PowerDrop(self, key, pos, now))
        self.dropsThisRound += 1

    def __pickUp(self, drop, now):
        key = drop.key
        drop.destroy()
        self.drops.remove(drop)
        base.playSfx(base.loader.loadSfx(POWER_SOUND), volume=0.7)
        self.hud.say(G.POWERUP_NAMES[key] + '!', 2.0)
        self.count('power-ups')
        if key == 'maxgags':
            self.gags.maxGags()
        elif key == 'toonado':
            # BO1's Nuke: every cog on the ground pops; 400 beans.
            for cog in list(self.cogs):
                if not cog.dead and cog.state == 'chase':
                    cog.lastHitByNPC = False
                    cog.hurt(cog.hp + 1)
            self.earn(G.BEANS_TOONADO)
        else:
            self.powers[key] = now + G.POWER_TIME
            self.hud.setPowers(self.powers, now)

    # --- What the player does ---

    def inMenu(self):
        # Freddy's tonic menu is up: the game carries on around the player
        # (cogs keep coming and hitting), but the player's hands are busy.
        return self.menuStation is not None

    def playerFires(self, held=False):
        if self.over or self.paused or self.inMenu():
            return False
        return self.gags.fire(held)

    def playerUses(self):
        if self.over or self.paused or self.inMenu() or self.player.down:
            return
        pos = self.player.getPos()
        for station in self.stations:
            if station.near(pos):
                station.use()
                return

    def __holdUse(self, dt):
        if self.player.down:
            return
        pos = self.player.getPos()
        for npc in self.npcs:
            if npc.down and (Vec3(npc.getPos() - pos)).length() < 5.0:
                npc.reviveProgress += dt
                if npc.reviveProgress >= G.REVIVE_TIME:
                    self.revive(npc, self.player)
                return

    def playerAction(self, action):
        if self.over:
            return
        if action == 'pause':
            self.togglePause()
            return
        if self.paused or self.inMenu() or self.player.down:
            return
        if action == 'reload':
            self.gags.reload()
        elif action == 'gag1':
            self.gags.switchTo(0)
        elif action == 'gag2':
            self.gags.switchTo(1)
        elif action == 'swap':
            pos = self.player.getPos()
            for station in self.stations:
                if isinstance(station, FishermanStation) and station.near(pos):
                    station.nextChoice()
                    return
            self.gags.swap()
        elif action == 'bonk':
            now = globalClock.getFrameTime()
            if now - self.lastBonk >= G.BONK_TIME:
                self.lastBonk = now
                self.gags.bonk()
        elif action == 'grenade':
            self.gags.throwPresentation()
        elif action == 'tnt':
            self.gags.throwTnt()

    def __prompt(self):
        if self.player.down:
            if self.secondWindAt is not None:
                left = self.secondWindAt - globalClock.getFrameTime()
                return 'Second Wind in %d...' % max(0, int(left + 0.99))
            if any(not n.down for n in self.npcs):
                return 'You went sad! Your friends are coming...'
            return ''
        if self.inMenu():
            return ''
        pos = self.player.getPos()
        for npc in self.npcs:
            if npc.down and (Vec3(npc.getPos() - pos)).length() < 5.0:
                return npc.helpPrompt()
        for station in self.stations:
            if station.near(pos):
                return station.prompt()
        return ''

    # --- Going sad and getting up ---

    def playerWentDown(self):
        self.count('player downs')
        if self.menuStation is not None:
            station = self.menuStation
            self.menuStation = None
            station.closeMenu()
        self.gags.cancelReload()
        self.beans = int(self.beans * (1 - G.DOWN_LOSS))
        self.hud.setBeans(self.beans)
        if self.hasTonic('wind'):
            # Second Wind: every cog runs off and every tonic is spent, then
            # the toon gets back up on its own.
            now = globalClock.getFrameTime()
            self.secondWindAt = now + G.SECOND_WIND_DELAY
            self.loseTonics()
            for cog in self.cogs:
                if not cog.dead:
                    cog.fleeFrom(self.player.getPos(), self.secondWindAt)
            self.hud.say('Second Wind! The cogs scatter. Your tonics are gone.', 3.0)
        elif any(not n.down for n in self.npcs):
            self.hud.say('You went sad! Hold on for your friends.', 3.0)
        else:
            self.gameOver()

    def playerDownTick(self, dt):
        if self.over:
            return
        now = globalClock.getFrameTime()
        since = now - self.player.downSince
        if self.secondWindAt is not None:
            # Nothing ends the game while a Second Wind runs (before, a toon
            # with no friends left still lost on the first frame down).
            if now >= self.secondWindAt:
                self.secondWindAt = None
                self.player.getUp(G.PLAYER_HP)
                self.hud.say('Second Wind! Back on your feet.', 3.0)
                self.count('second winds')
            return
        if since >= G.BLEED_OUT or not any(not n.down for n in self.npcs):
            self.gameOver()

    def revive(self, toon, by):
        base.playSfx(base.loader.loadSfx(REVIVE_SOUND), volume=0.6)
        if toon is self.player:
            self.secondWindAt = None
            self.loseTonics(keepWind=True)
            self.player.getUp(G.PLAYER_HP // 2)
            self.hud.say('%s helped you up! Your tonics are gone.' % by.name, 3.0)
        else:
            toon.getUp()
        self.count('revives')

    # --- Pausing and ending ---

    def togglePause(self):
        if self.paused:
            self.resume()
            return
        self.paused = True
        self.freezeClock()
        for npc in self.npcs:
            npc.stopSteps()
        self.player.grabMouse(False)
        self.showPauseCard()

    def showPauseCard(self):
        self.hud.showCard('Paused', ['Round %d' % self.roundNum, '%d cogs popped' % self.stats.get('cogs popped', 0)],
                          [('Resume', self.resume), ('Settings', self.showSettings), ('Quit', self.quit)])

    def showSettings(self):
        from toontown.survival.SurvivalPlayer import saveSensitivity

        def changed(level):
            self.player.setSensitivity(level)
            saveSensitivity(level)
        self.hud.showSettings(self.player.sensitivity, changed, self.showPauseCard)

    def freezeClock(self):
        # The pause stops the game clock itself, so every animation, gag in
        # flight, cog attack, reload and timer holds on the exact frame and
        # carries on from it: nothing catches up when the game resumes.
        if self.frozenAt is not None:
            return
        self.frozenAt = globalClock.getFrameTime()
        globalClock.setMode(ClockObject.MSlave)
        globalClock.setFrameTime(self.frozenAt)
        globalClock.setDt(0)

    def thawClock(self):
        if self.frozenAt is None:
            return
        globalClock.setRealTime(self.frozenAt)
        globalClock.setMode(ClockObject.MNormal)
        self.frozenAt = None

    def resume(self):
        self.thawClock()
        self.paused = False
        self.hud.closeCard()
        if self.menuStation is not None:
            station = self.menuStation
            self.menuStation = None
            station.closeMenu()
        self.player.grabMouse(True)

    # A station's menu (Freddy's tonics) frees the mouse but does not stop
    # the game: the cogs keep spawning and can hit the player there.

    def menuOpened(self, station):
        self.menuStation = station
        self.player.grabMouse(False)

    def menuClosed(self, station):
        if self.menuStation is station:
            self.menuStation = None
            if not self.over:
                self.resume()

    def gameOver(self):
        if self.over:
            return
        self.over = True
        self.paused = True
        for npc in self.npcs:
            npc.stopSteps()
        self.player.grabMouse(False)
        best = self.loadBest()
        reached = self.roundNum
        newBest = reached > best
        if newBest:
            self.saveBest(reached)
        lines = ['You made it to round %d.' % reached,
                 '%d cogs popped, %d jellybeans earned.' % (self.stats.get('cogs popped', 0), self.stats.get('beans earned', 0)),
                 'New best round!' if newBest else 'Best round: %d' % best]
        self.notify.info('game over: ' + ' / '.join(lines))
        if self.music:
            self.music.stop()
        self.hud.showCard('Game Over', lines, [('Again', self.playAgain), ('Quit', self.quit)])

    def playAgain(self):
        messenger.send(self.doneEvent, [{'mode': 'again', 'npcs': self.npcCount}])

    def quit(self):
        self.thawClock()
        messenger.send(self.doneEvent, [{'mode': 'quit'}])

    @staticmethod
    def loadBest():
        try:
            return int(base.settings.settings.getOption('survival', 'best-round', 0))
        except Exception:
            return 0

    @staticmethod
    def saveBest(roundNum):
        try:
            base.settings.settings.updateSetting('survival', 'best-round', int(roundNum))
        except Exception:
            SurvivalGame.notify.warning('could not save the best round')
