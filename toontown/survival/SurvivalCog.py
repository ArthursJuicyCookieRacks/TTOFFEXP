"""A cog in Survival Mode: falls from the sky, walks at the nearest toon
and swings at it until it is popped.

The cog is the game's own Suit actor with a small brain of its own: no
battles, no district. Its health is the round's, its speed is rolled the
way BO1 rolls a zombie's (walker, jogger or sprinter), and hits on the
top of it count as headshots.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpColorScaleInterval, LerpPosInterval,
                                            LerpScaleInterval, Parallel, Sequence, SoundInterval, Wait)
from panda3d.core import Point3, TextNode, Vec3, Vec4

from toontown.battle import BattleParticles, BattleProps
from toontown.survival import SurvivalGlobals as G
from toontown.suit import Suit, SuitDNA
from toontown.toonbase import ToontownGlobals

FLY_TIME = 3.2
FLY_HEIGHT = 60.0
# A cog in the way of another steps round it.
CROWD_RADIUS = 3.0
# How long a heading chosen to get round a wall is kept.
STUCK_TIME = 15.0
DETOUR_TIME = 0.8
GROUND_EVERY = 0.1
HEAD_FRACTION = 0.72
POP_TIME = 0.35
HURT_FLASH = 0.12


class SurvivalCog:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalCog')
    gearSounds = None

    def __init__(self, game, name, landing, roundNum, snatcher=False):
        self.game = game
        self.snatcher = snatcher
        self.arena = game.arena
        self.suit = Suit.Suit()
        dna = SuitDNA.SuitDNA()
        dna.newSuit(name)
        self.suit.setDNA(dna)
        self.suit.setPickable(0)
        self.suit.hideName()
        self.suit.nametag3d.stash()
        self.suit.reparentTo(self.arena.root)
        self.suit.setColorScale(1, 1, 1, 1)
        self.name = name
        self.maxHp = G.cogHp(roundNum)
        self.speedClass = G.cogSpeedClass(roundNum, random.random())
        if snatcher:
            # Gag-Snatchers: small, quick and easier to pop.
            self.maxHp = max(50, int(self.maxHp * G.SNATCHER_HP))
            self.speedClass = 2
            self.suit.setScale(G.SNATCHER_SCALE)
        self.hp = self.maxHp
        self.speed = G.COG_SPEEDS[self.speedClass]
        self.radius = self.suit.getRadius()
        self.height = self.suit.height
        self.state = 'landing'
        self.target = None
        self.lure = None
        self.lureUntil = 0.0
        self.nextTargetPick = 0.0
        self.nextSwing = 0.0
        self.swingAt = None
        self.detour = None
        self.detourUntil = 0.0
        self.nextGround = 0.0
        self.anim = None
        self.track = None
        self.dead = False
        self.pos = Point3(landing)
        self.bestDist = 1e9
        self.lastProgress = 0.0
        self.suit.setPos(landing)
        self.suit.setH(random.uniform(0, 360))
        self.__flyIn(landing)

    # --- Arriving ---

    def __flyIn(self, landing):
        suit = self.suit
        prop = BattleProps.globalPropPool.getProp('propeller')
        head = suit.find('**/joint_head')
        prop.reparentTo(head)
        self.prop = prop
        sky = Point3(landing[0], landing[1], landing[2] + FLY_HEIGHT)
        dur = suit.getDuration('landing')
        sound = base.loader.loadSfx('phase_5/audio/sfx/ENC_propeller_in.ogg')
        suit.pose('landing', 0)
        suit.setTransparency(1)
        self.track = Sequence(
            Parallel(LerpPosInterval(suit, FLY_TIME, landing, startPos=sky, blendType='easeIn'),
                     LerpColorScaleInterval(suit, 0.8, Vec4(1, 1, 1, 1), startColorScale=Vec4(1, 1, 1, 0)),
                     SoundInterval(sound, duration=FLY_TIME + 0.5, node=suit, volume=0.6),
                     ActorInterval(prop, 'propeller', constrainedLoop=1, duration=FLY_TIME + 0.4),
                     Sequence(Wait(max(0, FLY_TIME - dur * 0.6)), ActorInterval(suit, 'landing', duration=dur * 0.6))),
            Func(self.__landed))
        self.track.start()

    def __landed(self):
        if self.dead:
            return
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None
        self.suit.clearTransparency()
        self.state = 'chase'
        self.__loop('walk' if self.speedClass == 0 else 'run', 1.0 if self.speedClass < 2 else 1.6)

    def __loop(self, anim, rate=1.0):
        if self.anim != (anim, rate):
            self.anim = (anim, rate)
            self.suit.setPlayRate(rate, anim)
            self.suit.loop(anim)

    # --- Each tick ---

    def tick(self, dt, now):
        if self.dead or self.state == 'landing':
            return
        if self.lure is not None and now > self.lureUntil:
            self.lure = None
        if self.state == 'swing':
            if self.swingAt is not None and now >= self.swingAt:
                self.swingAt = None
                self.__hit()
            if now >= self.nextSwing - G.COG_SWING_TIME + 0.9:
                self.state = 'chase'
            return
        goal = self.__goal(now)
        if goal is None:
            self.__loop('neutral')
            return
        to = Point3(goal[0], goal[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        dist = to.length()
        reach = G.COG_REACH + (self.radius if self.lure is None else 0.5)
        if dist <= reach and self.lure is None:
            self.__face(goal)
            if now >= self.nextSwing:
                self.__swing(now)
            else:
                self.__loop('neutral')
            return
        if dist <= 1.0:
            self.__loop('neutral')
            return
        # A cog that gets nowhere for a while (a fence, a hedge, a corner)
        # flies back in somewhere nearer, as BO1's zombies respawn.
        if dist < self.bestDist - 1.0:
            self.bestDist = dist
            self.lastProgress = now
        elif not self.lastProgress:
            self.lastProgress = now
        elif now - self.lastProgress > STUCK_TIME and dist > 10.0 and self.lure is None:
            self.__reland(goal)
            return
        self.__step(to / max(dist, 0.001), min(dist, self.speed * dt), now)

    def __reland(self, goal):
        player = self.game.player
        landing = self.arena.landingNear(goal, player.getEye(), player.getForward())
        if landing is None:
            self.lastProgress = globalClock.getFrameTime()
            return
        self.bestDist = 1e9
        self.lastProgress = 0.0
        self.detour = None
        self.pos = landing
        self.state = 'landing'
        self.anim = None
        self.suit.setPos(landing)
        self.game.count('cogs relanded')
        self.__flyIn(landing)

    def __goal(self, now):
        if self.lure is not None:
            return self.lure
        if now >= self.nextTargetPick or self.target is None or not self.target.alive():
            self.nextTargetPick = now + 0.5
            self.target = self.game.nearestToon(self.pos)
        if self.target is None:
            return None
        return self.target.getPos()

    def __step(self, direction, length, now):
        pos = self.pos
        if self.detour is not None and now < self.detourUntil:
            direction = self.detour
        ahead = Point3(pos + direction * max(length, 2.5))
        if not self.arena.clearLine(Point3(pos[0], pos[1], pos[2] + 2), Point3(ahead[0], ahead[1], pos[2] + 2)):
            # A wall: try the ways round it and keep the first that is clear.
            found = None
            for angle in (45, -45, 90, -90, 135, -135):
                a = math.radians(angle)
                turned = Vec3(direction[0] * math.cos(a) - direction[1] * math.sin(a),
                              direction[0] * math.sin(a) + direction[1] * math.cos(a), 0)
                probe = Point3(pos + turned * 4.0)
                if self.arena.clearLine(Point3(pos[0], pos[1], pos[2] + 2), Point3(probe[0], probe[1], pos[2] + 2)):
                    found = turned
                    break
            if found is None:
                self.__loop('neutral')
                return
            self.detour = found
            self.detourUntil = now + DETOUR_TIME
            direction = found
        # Not through another cog.
        for other in self.game.cogs:
            if other is self or other.dead or other.state == 'landing':
                continue
            gap = Point3(other.pos[0], other.pos[1], 0) - Point3(pos[0], pos[1], 0)
            if gap.length() < CROWD_RADIUS and gap.dot(direction) > 0:
                side = Vec3(-gap[1], gap[0], 0)
                side.normalize()
                direction = (direction + side * 0.8)
                direction.normalize()
                break
        new = Point3(pos + direction * length)
        if now >= self.nextGround:
            self.nextGround = now + GROUND_EVERY
            z = self.arena.nav.groundZ(new[0], new[1], pos[2])
            if z is not None:
                new.setZ(z)
            else:
                new.setZ(pos[2])
        else:
            new.setZ(pos[2])
        self.pos = new
        self.suit.setPos(new)
        self.__face(new + direction)
        self.__loop('walk' if self.speedClass == 0 else 'run', 1.0 if self.speedClass < 2 else 1.6)

    def __face(self, point):
        d = point - self.pos
        if abs(d[0]) + abs(d[1]) > 0.01:
            self.suit.setH(-math.degrees(math.atan2(d[0], d[1])))

    # --- Hitting toons ---

    def __swing(self, now):
        self.state = 'swing'
        self.nextSwing = now + G.COG_SWING_TIME
        self.swingAt = now + 0.45
        anim = 'finger-wag' if 'finger-wag' in self.suit.getAnimNames() else 'neutral'
        self.anim = None
        self.suit.setPlayRate(1.4 if anim != 'neutral' else 1.0, anim)
        self.suit.play(anim)

    def __hit(self):
        if self.target is None or not self.target.alive():
            return
        flat = Point3(self.target.getPos()[0], self.target.getPos()[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        if flat.length() <= G.COG_REACH + self.radius + 1.0:
            self.target.hurt(G.COG_HIT, self)

    # --- Being hit ---

    def hitTest(self, origin, direction, maxDist):
        """Where a line from origin along direction crosses this cog:
        (distance, headshot) or None."""
        if self.dead or self.state == 'landing':
            return None
        rel = self.pos - origin
        # The closest approach of the line to the cog's upright axis, in
        # the ground plane.
        flatDir = Vec3(direction[0], direction[1], 0)
        flatLen = flatDir.length()
        if flatLen < 0.001:
            return None
        flatDir /= flatLen
        along = rel[0] * flatDir[0] + rel[1] * flatDir[1]
        if along < 0:
            return None
        perp = abs(rel[0] * flatDir[1] - rel[1] * flatDir[0])
        if perp > self.radius * 1.15:
            return None
        t = along / flatLen
        if t > maxDist:
            return None
        hitZ = origin[2] + direction[2] * t
        if hitZ < self.pos[2] - 0.5 or hitZ > self.pos[2] + self.height + 0.5:
            return None
        return t, hitZ > self.pos[2] + self.height * HEAD_FRACTION

    def hurt(self, damage, head=False, bonk=False):
        if self.dead:
            return 0
        if self.game.power('instapop'):
            damage = self.hp
        self.hp -= damage
        self.__flash()
        if self.hp <= 0:
            self.pop(head, bonk)
            return 2
        return 1

    def __flash(self):
        suit = self.suit
        Sequence(Func(suit.setColorScale, 1, 0.45, 0.45, 1), Wait(HURT_FLASH), Func(suit.setColorScale, 1, 1, 1, 1)).start()

    def pop(self, head=False, bonk=False):
        """Gears everywhere, the way a cog goes in battle, but quick."""
        if self.dead:
            return
        self.dead = True
        self.state = 'dead'
        if self.track:
            self.track.finish()
            self.track = None
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None
        self.game.cogPopped(self, head, bonk)
        suit = self.suit
        suit.stop()
        BattleParticles.loadParticles()
        gears = BattleParticles.createParticleEffect('BigGearExplosion', numParticles=18)
        point = Point3(self.pos[0], self.pos[1], self.pos[2] + self.height * 0.6)
        gears.setPos(point)
        gears.setDepthWrite(False)
        explosion = loader.loadModel('phase_3.5/models/props/explosion')
        explosion.setBillboardPointEye()
        explosion.setDepthWrite(False)
        explosion.reparentTo(self.arena.root)
        explosion.setPos(point)
        explosion.setScale(0.5)
        if SurvivalCog.gearSounds is None:
            SurvivalCog.gearSounds = base.loader.loadSfx('phase_3.5/audio/sfx/ENC_cogfall_apart.ogg')
        from direct.interval.ParticleInterval import ParticleInterval
        self.track = Sequence(
            Parallel(LerpScaleInterval(suit, POP_TIME, 0.05, blendType='easeIn'),
                     SoundInterval(SurvivalCog.gearSounds, node=suit, volume=0.5, duration=1.2),
                     ParticleInterval(gears, self.arena.root, worldRelative=0, duration=1.0, cleanup=True),
                     Sequence(Wait(0.5), Func(explosion.removeNode))),
            Func(self.__gone))
        self.track.start()

    def __gone(self):
        self.track = None
        self.destroy()

    def destroy(self):
        if self.track:
            self.track.finish()
            self.track = None
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None
        if self.suit is not None:
            self.suit.cleanup()
            self.suit.removeNode()
            self.suit = None
        self.game.cogGone(self)

    # --- The lure ---

    def lureTo(self, point, until):
        self.lure = Point3(point)
        self.lureUntil = until
