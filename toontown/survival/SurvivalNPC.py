"""The NPC toons who play Survival Mode alongside the player.

Each is a Toon actor with a random look and a Toontown name. They play
like another player would: they roam the playground hunting cogs, earn
their own jellybeans, buy gags from the accessory trunk and tonics from
Fisherman Freddy, go sad when the cogs get them and can be helped up, and
run over to help a sad teammate up in turn.
"""

import math
import random

from direct.interval.IntervalGlobal import Func, LerpPosInterval, Sequence, Wait
from panda3d.core import Point3, TextNode, Vec3

from toontown.battle import BattleProps
from toontown.survival import SurvivalGlobals as G
from toontown.toon import Toon, ToonDNA
from toontown.toonbase import ToontownGlobals

NAMES = ('Flippy', 'Daffy Zippenwhip', 'Loopy Fiddlefoot', 'Ziggy Nickelbounce', 'Trixie Sparklemuffin',
         'Buster Wackycrunch', 'Fluffy Pickleberry', 'Skipper Jellyjumper', 'Bonnie Dizzyswirl', 'Max Mcwhistle')
ENGAGE_NEAR = 9.0
ENGAGE_FAR = 24.0
HELP_RANGE = 60.0
REPATH = 1.5
SHOP_TIME = 1.6
SHOP_CHECK = 3.0
SHOP_SAFE = 18.0
BROKE_AMMO = 40
WALK_SPEED = 13.0
RUN_SPEED = 17.0
AIM_RANGE = 45.0
THROW_TIME = (1.1, 1.9)
THROW_FLIGHT = 0.45
HIT_CHANCE = 0.8
HP = 100


class SurvivalNPC:

    def __init__(self, game, index, start):
        self.game = game
        self.arena = game.arena
        self.index = index
        self.name = NAMES[index % len(NAMES)]
        self.toon = Toon.Toon()
        dna = ToonDNA.ToonDNA()
        dna.newToonRandom(seed=random.randint(0, 999999), gender=random.choice(('m', 'f')))
        self.toon.setDNA(dna)
        self.toon.setName(self.name)
        self.toon.setPickable(0)
        self.toon.reparentTo(self.arena.root)
        self.toon.setPos(start)
        self.toon.setH(random.uniform(0, 360))
        self.toon.loop('neutral')
        self.toon.startBlink()
        self.pos = Point3(start)
        self.hp = HP
        self.maxHp = HP
        self.down = False
        self.downSince = 0.0
        self.reviveProgress = 0.0
        self.lastHurt = -100.0
        self.anim = None
        self.nextThrow = 0.0
        self.target = None
        self.helping = None
        self.wanderGoal = None
        self.nextWander = 0.0
        self.throwTrack = None
        # Their own game: jellybeans, a gag with its ammo, tonics.
        self.beans = G.START_BEANS
        self.gag = (G.THROW, 0)
        self.ammo = BROKE_AMMO
        self.tonics = []
        self.shop = None
        self.shopUntil = 0.0
        self.nextShopCheck = 0.0
        self.path = []
        self.pathGoal = None
        self.nextPath = 0.0
        self.strafe = random.choice((-1, 1))
        self.nextStrafe = 0.0
        self.__loop('neutral')

    # --- What the cogs and the game need ---

    def alive(self):
        return not self.down

    def getPos(self):
        return self.pos

    def hurt(self, damage, cog=None):
        if self.down or self.game.over:
            return
        self.hp -= damage
        self.lastHurt = globalClock.getFrameTime()
        if self.hp <= 0:
            self.hp = 0
            self.goDown()

    def goDown(self):
        self.down = True
        self.downSince = globalClock.getFrameTime()
        self.reviveProgress = 0.0
        self.helping = None
        self.__stopThrow()
        self.__loop('lose', once=True)
        self.game.hud.say('%s went sad! Hold Use next to them to help.' % self.name, 3.0)
        self.game.count('npc downs')

    def getUp(self):
        self.down = False
        # Like the player, getting back up costs the tonics.
        self.tonics = []
        self.maxHp = HP
        self.hp = self.maxHp
        self.reviveProgress = 0.0
        self.__loop('neutral')
        self.game.hud.say('%s is back up!' % self.name, 2.0)

    # --- Animation ---

    def __loop(self, anim, rate=1.0, once=False):
        if self.anim == (anim, rate, once):
            return
        self.anim = (anim, rate, once)
        if once:
            self.toon.play(anim)
        else:
            self.toon.setPlayRate(rate, anim)
            self.toon.loop(anim)

    def __stopThrow(self):
        if self.throwTrack:
            self.throwTrack.finish()
            self.throwTrack = None

    # --- Each frame ---

    def tick(self, dt, now):
        if self.down:
            if self.toon.getCurrentAnim() is None:
                self.toon.pose('lose', self.toon.getNumFrames('lose') - 1)
            return
        # Health comes back after a moment, like the player's.
        if self.hp < self.maxHp and now - self.lastHurt > G.REGEN_DELAY:
            self.hp = min(self.maxHp, self.hp + G.REGEN_RATE * dt)
        speed = RUN_SPEED * (1.25 if 'sprint' in self.tonics else 1.0)
        # A sad teammate comes first: run over and help them up.
        self.__pickHelp()
        if self.helping is not None:
            helpPos = self.helping.getPos()
            if (self.__flat(helpPos) - self.__flat(self.pos)).length() > 3.0:
                self.__walk(helpPos, speed, dt, now)
            else:
                self.helping.reviveProgress += dt
                self.__face(helpPos)
                self.__loop('pushbutton')
                if self.helping.reviveProgress >= G.REVIVE_TIME:
                    self.game.revive(self.helping, self)
                    self.helping = None
            return
        cog, cogDist = self.__nearestCog(anyRange=True)
        # Shopping: out of ammo, or beans to spend and no cog close.
        if self.shop is None and now >= self.nextShopCheck and (cog is None or cogDist > SHOP_SAFE or self.ammo <= 0):
            self.nextShopCheck = now + SHOP_CHECK
            self.shop = self.__wantShop()
        if self.shop is not None:
            if self.__shopping(dt, now, speed):
                return
        if cog is not None:
            self.__hunt(cog, cogDist, dt, now, speed)
        else:
            # Nothing to fight: roam the playground like a player would.
            if self.pathGoal is None or (self.__flat(self.pathGoal) - self.__flat(self.pos)).length() < 2.0:
                self.pathGoal = self.arena.randomSpot()
                self.path = []
            if self.pathGoal is not None:
                self.__walk(self.pathGoal, WALK_SPEED, dt, now)
            else:
                self.__loop('neutral')

    def __pickHelp(self):
        if self.helping is not None and not self.helping.down:
            self.helping = None
        if self.helping is not None:
            return
        best, bestDist = None, HELP_RANGE
        for toon in [self.game.player] + self.game.npcs:
            if toon is self or not toon.down:
                continue
            dist = (self.__flat(toon.getPos()) - self.__flat(self.pos)).length()
            # The player comes first wherever they are.
            if toon is self.game.player:
                dist *= 0.5
            if dist < bestDist:
                best, bestDist = toon, dist
        if best is not None:
            self.helping = best
            self.path = []

    def __hunt(self, cog, dist, dt, now, speed):
        seen = self.arena.clearLine(Point3(self.pos[0], self.pos[1], self.pos[2] + 2.5), Point3(cog.pos[0], cog.pos[1], cog.pos[2] + 3))
        if dist > ENGAGE_FAR or not seen:
            self.__walk(cog.pos, speed, dt, now)
        elif dist < ENGAGE_NEAR:
            # Too close: back off while throwing.
            away = self.__flat(self.pos) - self.__flat(cog.pos)
            away.normalize()
            self.__stepTo(self.pos + away * 3.0, WALK_SPEED, dt)
            self.__face(cog.pos)
            self.__loop('walk', -1.0)
        else:
            # In range: circle the cog a little and keep throwing.
            if now >= self.nextStrafe:
                self.strafe = random.choice((-1, 0, 1))
                self.nextStrafe = now + random.uniform(1.0, 2.5)
            if self.strafe:
                to = self.__flat(cog.pos) - self.__flat(self.pos)
                side = Vec3(-to[1], to[0], 0) * self.strafe
                side.normalize()
                self.__stepTo(self.pos + side * 3.0, WALK_SPEED * 0.6, dt)
                self.__loop('walk')
            else:
                self.__loop('neutral')
            self.__face(cog.pos)
        if seen and dist <= AIM_RANGE:
            self.__fight(now, cog)

    def __walk(self, goal, speed, dt, now):
        """Follow a path over the playground's open cells to the goal,
        asking for a new one now and then as the goal moves."""
        if not self.path or now >= self.nextPath or (self.__flat(self.path[-1]) - self.__flat(goal)).length() > 6.0:
            self.path = self.arena.path(self.pos, goal)
            self.nextPath = now + REPATH
        while self.path and (self.__flat(self.path[0]) - self.__flat(self.pos)).length() < 1.5:
            self.path.pop(0)
        if not self.path:
            self.__loop('neutral')
            return
        self.__stepTo(self.path[0], speed, dt)
        self.__loop('run' if speed > WALK_SPEED else 'walk')

    # --- Buying gags and tonics ---

    def __station(self, kind):
        for station in self.game.stations:
            if station.__class__.__name__ == kind:
                return station
        return None

    def __wantShop(self):
        trunk = self.__station('TrunkStation')
        freddy = self.__station('FishermanStation')
        if trunk is not None:
            cost = trunk.cost()
            if self.ammo <= 0 and self.beans >= cost:
                return trunk
            # A better gag when the beans allow and the gag is a weak one.
            if self.beans >= cost + 400 and self.gag[1] < 4 and random.random() < 0.5:
                return trunk
        if freddy is not None and len(self.tonics) < 3:
            for key, name, cost, blurb in G.TONICS:
                if key in self.tonics or key == 'wind':
                    continue
                if self.beans >= cost + 300:
                    return freddy
        if self.ammo <= 0:
            # Broke and out of gags: back to a stack of cupcakes.
            self.gag = (G.THROW, 0)
            self.ammo = BROKE_AMMO
        return None

    def __shopping(self, dt, now, speed):
        """Walks to the station and buys there; True while busy with it."""
        target = self.shop.node.getPos(self.arena.root)
        if (self.__flat(target) - self.__flat(self.pos)).length() > 4.5:
            if self.shopUntil:
                self.shopUntil = 0.0
            self.__walk(target, speed, dt, now)
            return True
        if not self.shopUntil:
            self.shopUntil = now + SHOP_TIME
            self.__face(target)
            self.__loop('pushbutton')
            return True
        if now < self.shopUntil:
            return True
        self.__buy(self.shop)
        self.shop = None
        self.shopUntil = 0.0
        self.path = []
        return False

    def __buy(self, station):
        if station.__class__.__name__ == 'TrunkStation':
            cost = station.cost()
            if self.beans < cost:
                return
            self.beans -= cost
            choices = [k for k in G.TRUNK_GAGS if k != self.gag and k in G.GAGS]
            offer = random.choice(choices)
            # A weaker gag than the one in hand is left in the trunk, but
            # the old gag gets its ammo back.
            if G.GAGS[offer][0] >= G.GAGS[self.gag][0] or self.ammo <= 0:
                self.gag = offer
            clip, reserve = G.GAGS[self.gag][1], G.GAGS[self.gag][2]
            self.ammo = clip + reserve
            name = G.gagName(*self.gag)
            station.floatText('%s: %s' % (self.name.split()[0], name), height=6.0)
            self.game.count('npc trunk gags')
        else:
            for key, name, cost, blurb in G.TONICS:
                if key in self.tonics or key == 'wind' or self.beans < cost:
                    continue
                self.beans -= cost
                self.tonics.append(key)
                if key == 'toonup':
                    self.maxHp = G.TONIC_HP * HP // G.PLAYER_HP
                    self.hp = self.maxHp
                station.floatText('%s: %s' % (self.name.split()[0], name))
                self.game.count('npc tonics')
                break

    # --- Moving ---

    def __flat(self, p):
        return Vec3(p[0], p[1], 0)

    def __face(self, point):
        d = point - self.pos
        if abs(d[0]) + abs(d[1]) > 0.01:
            self.toon.setH(math.degrees(math.atan2(-d[0], d[1])))

    def __stepTo(self, goal, speed, dt):
        d = self.__flat(goal) - self.__flat(self.pos)
        dist = d.length()
        if dist < 0.1:
            return
        d.normalize()
        step = min(dist, speed * dt)
        nxt = Point3(self.pos[0] + d[0] * step, self.pos[1] + d[1] * step, self.pos[2])
        if not self.arena.clearLine(Point3(self.pos[0], self.pos[1], self.pos[2] + 1.5), Point3(nxt[0], nxt[1], nxt[2] + 1.5)):
            # Slide along the wall, and look for a new way soon.
            side = Vec3(-d[1], d[0], 0) * (1 if random.random() < 0.5 else -1)
            nxt = Point3(self.pos[0] + side[0] * step, self.pos[1] + side[1] * step, self.pos[2])
            self.nextPath = 0.0
        z = self.arena.groundZ(nxt[0], nxt[1])
        if z is None or z < self.pos[2] - 4 or z > self.pos[2] + 4:
            self.nextPath = 0.0
            return
        self.pos = Point3(nxt[0], nxt[1], z)
        self.toon.setPos(self.pos)
        self.toon.setH(math.degrees(math.atan2(-d[0], d[1])))

    # --- Throwing ---

    def __fight(self, now, cog):
        if now < self.nextThrow or self.throwTrack or self.ammo <= 0:
            return
        self.target = cog
        self.__face(cog.pos)
        wait = random.uniform(*THROW_TIME)
        if 'seltzer' in self.tonics:
            wait *= 0.6
        self.nextThrow = now + wait
        self.ammo -= 1
        self.throwTrack = Sequence(Func(self.toon.play, 'throw'), Wait(0.55), Func(self.__release, cog), Wait(0.6), Func(self.__thrown))
        self.throwTrack.start()
        self.anim = None

    def __thrown(self):
        self.throwTrack = None

    def __nearestCog(self, anyRange=False):
        best, bestDist = None, None
        for cog in self.game.cogs:
            if cog.dead or cog.state != 'chase':
                continue
            dist = (self.__flat(cog.pos) - self.__flat(self.pos)).length()
            if bestDist is None or dist < bestDist:
                best, bestDist = cog, dist
        return best, bestDist

    def __release(self, cog):
        if cog.dead or self.down:
            return
        try:
            prop = BattleProps.globalPropPool.getProp(G.GAGS[self.gag][5])
        except Exception:
            prop = BattleProps.globalPropPool.getProp('tart')
        prop.reparentTo(self.arena.root)
        hand = self.toon.getRightHands()[0] if self.toon.getRightHands() else self.toon
        prop.setPos(hand.getPos(self.arena.root))
        low, high = prop.getTightBounds()
        if low is not None:
            size = max(high[0] - low[0], high[1] - low[1], high[2] - low[2])
            prop.setScale(min(1.0, 1.5 / max(size, 0.01)))
        target = Point3(cog.pos[0], cog.pos[1], cog.pos[2] + cog.height * 0.6)
        hit = random.random() < HIT_CHANCE
        if not hit:
            target += Vec3(random.uniform(-3, 3), random.uniform(-3, 3), 0)
        Sequence(LerpPosInterval(prop, THROW_FLIGHT, target), Func(self.__land, prop, cog, hit)).start()

    def __land(self, prop, cog, hit):
        prop.removeNode()
        if hit and not cog.dead:
            # Better gags hit harder: a wedding cake about four tarts.
            damage = int(G.npcDamage(self.game.roundNum) * math.sqrt(G.GAGS[self.gag][0] / 30.0))
            result = self.game.damageCog(cog, damage, byNPC=True)
            if result:
                earned = G.BEANS_KILL if result == 2 else G.BEANS_HIT
                self.beans += earned * (2 if self.game.power('doublebeans') else 1)

    # --- Being helped ---

    def helpPrompt(self):
        left = max(0.0, G.REVIVE_TIME - self.reviveProgress)
        return 'Hold Use: help %s up (%.1f s)' % (self.name, left)

    def destroy(self):
        self.__stopThrow()
        self.toon.stopBlink()
        self.toon.delete()
