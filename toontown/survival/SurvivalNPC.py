"""The NPC toons who play Survival Mode alongside the player.

Each is a Toon actor with a random look and a Toontown name. They keep
near the player, throw at the nearest cog, go sad when the cogs get them
and can be helped up, and help the player up in turn.
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
FOLLOW_NEAR = 8.0
FOLLOW_FAR = 16.0
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
        player = self.game.player
        playerPos = player.getPos()
        # Health comes back after a moment, like the player's.
        if self.hp < self.maxHp and now - self.lastHurt > G.REGEN_DELAY:
            self.hp = min(self.maxHp, self.hp + G.REGEN_RATE * dt)
        goal = None
        speed = WALK_SPEED
        # A sad teammate nearby comes first: walk over and help them up.
        if player.down:
            self.helping = player
        elif self.helping is player:
            self.helping = None
        if self.helping is not None:
            helpPos = self.helping.getPos()
            flat = self.__flat(helpPos) - self.__flat(self.pos)
            if flat.length() > 3.0:
                goal = helpPos
                speed = RUN_SPEED
            else:
                self.helping.reviveProgress += dt
                self.__face(helpPos)
                self.__loop('pushbutton')
                if self.helping.reviveProgress >= G.REVIVE_TIME:
                    self.game.revive(self.helping, self)
                    self.helping = None
                return
        else:
            toPlayer = self.__flat(playerPos) - self.__flat(self.pos)
            dist = toPlayer.length()
            if dist > FOLLOW_FAR:
                goal = playerPos
                speed = RUN_SPEED
            elif dist > FOLLOW_NEAR and self.wanderGoal is None:
                goal = playerPos
            else:
                # Spread out a little instead of standing on the player.
                if self.wanderGoal is None and now >= self.nextWander:
                    angle = random.uniform(0, 2 * math.pi)
                    r = random.uniform(3.0, FOLLOW_NEAR)
                    spot = Point3(playerPos[0] + r * math.cos(angle), playerPos[1] + r * math.sin(angle), playerPos[2])
                    if self.arena.walkable(self.pos, spot):
                        self.wanderGoal = spot
                    self.nextWander = now + random.uniform(2.0, 5.0)
                if self.wanderGoal is not None:
                    goal = self.wanderGoal
                    if (self.__flat(goal) - self.__flat(self.pos)).length() < 1.0:
                        self.wanderGoal = None
                        goal = None
        if goal is not None:
            self.__stepTo(goal, speed, dt)
            self.__loop('run' if speed > WALK_SPEED else 'walk')
        else:
            self.__loop('neutral')
        self.__fight(now)

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
            # Slide along the wall.
            side = Vec3(-d[1], d[0], 0) * (1 if random.random() < 0.5 else -1)
            nxt = Point3(self.pos[0] + side[0] * step, self.pos[1] + side[1] * step, self.pos[2])
        z = self.arena.groundZ(nxt[0], nxt[1])
        if z is None or z < self.pos[2] - 4 or z > self.pos[2] + 4:
            return
        self.pos = Point3(nxt[0], nxt[1], z)
        self.toon.setPos(self.pos)
        self.toon.setH(math.degrees(math.atan2(-d[0], d[1])))

    def __fight(self, now):
        if now < self.nextThrow or self.throwTrack:
            return
        cog = self.__nearestCog()
        if cog is None:
            return
        self.target = cog
        self.__face(cog.pos)
        self.nextThrow = now + random.uniform(*THROW_TIME)
        self.throwTrack = Sequence(Func(self.toon.play, 'throw'), Wait(0.55), Func(self.__release, cog), Wait(0.6), Func(self.__thrown))
        self.throwTrack.start()
        self.anim = None

    def __thrown(self):
        self.throwTrack = None

    def __nearestCog(self):
        best, bestDist = None, AIM_RANGE
        for cog in self.game.cogs:
            if cog.dead or cog.state != 'chase':
                continue
            dist = (self.__flat(cog.pos) - self.__flat(self.pos)).length()
            if dist < bestDist and self.arena.clearLine(Point3(self.pos[0], self.pos[1], self.pos[2] + 2.5), Point3(cog.pos[0], cog.pos[1], cog.pos[2] + 3)):
                best, bestDist = cog, dist
        return best

    def __release(self, cog):
        if cog.dead or self.down:
            return
        prop = BattleProps.globalPropPool.getProp('tart')
        prop.reparentTo(self.arena.root)
        hand = self.toon.getRightHands()[0] if self.toon.getRightHands() else self.toon
        prop.setPos(hand.getPos(self.arena.root))
        prop.setScale(1.0)
        target = Point3(cog.pos[0], cog.pos[1], cog.pos[2] + cog.height * 0.6)
        hit = random.random() < HIT_CHANCE
        if not hit:
            target += Vec3(random.uniform(-3, 3), random.uniform(-3, 3), 0)
        Sequence(LerpPosInterval(prop, THROW_FLIGHT, target), Func(self.__land, prop, cog, hit)).start()

    def __land(self, prop, cog, hit):
        prop.removeNode()
        if hit and not cog.dead:
            self.game.damageCog(cog, G.npcDamage(self.game.roundNum), byNPC=True)

    # --- Being helped ---

    def helpPrompt(self):
        left = max(0.0, G.REVIVE_TIME - self.reviveProgress)
        return 'Hold Use: help %s up (%.1f s)' % (self.name, left)

    def destroy(self):
        self.__stopThrow()
        self.toon.stopBlink()
        self.toon.delete()
