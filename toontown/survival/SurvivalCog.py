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
FLEE_DISTANCE = 45.0
# A cog that hasn't got closer for this long, or hasn't moved a few feet
# in STILL_TIME, is stuck and flies back in somewhere better.
STUCK_TIME = 20.0
STILL_TIME = 4.0
STILL_DISTANCE = 3.0
# How often a cog looks again for its way to the toon.
ROUTE_EVERY = 0.35
# How far ahead along its route a cog looks for a corner it can cut.
ROUTE_LOOKAHEAD = 5
# Footsteps: heard this far, by the nearest few cogs.
STEP_SOUND = 'phase_5/audio/sfx/ENC_cogside_step.ogg'
STEP_HEAR = 45.0
STEP_VOLUME = 0.35
# How long a heading chosen to get round a wall is kept.
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
        self.route = None
        self.routed = False
        self.nextRoute = 0.0
        self.stillFrom = None
        self.stillSince = 0.0
        self.stepPhase = random.random()
        self.stepSound = None
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
        self.__moveAnim(self.speed if self.lure is None else max(self.speed, G.COG_SPEEDS[-1]))

    def __moveAnim(self, speed):
        """Walk or run with the feet keeping up with the ground: the cycle
        plays as fast as the cog really moves, never faster."""
        if speed <= G.COG_SPEEDS[0] * 1.2:
            self.__loop('walk', round(speed / G.COG_WALK_STRIDE, 2))
        else:
            self.__loop('run', round(speed / G.COG_RUN_STRIDE, 2))

    def __footstep(self, speed, dt):
        # A step sound every half cycle, from the nearest few cogs only.
        if not self.game.wantCogSteps(self):
            return
        stride = G.COG_WALK_STRIDE if speed <= G.COG_SPEEDS[0] * 1.2 else G.COG_RUN_STRIDE
        self.stepPhase += dt * speed / stride * 2.0
        if self.stepPhase < 1.0:
            return
        self.stepPhase -= 1.0
        if self.stepSound is None:
            self.stepSound = base.loader.loadSfx(STEP_SOUND)
        if self.stepSound:
            dist = (camera.getPos(render) - self.suit.getPos(render)).length()
            volume = STEP_VOLUME * max(0.0, 1.0 - dist / STEP_HEAR)
            if volume > 0.01:
                self.stepSound.setVolume(volume)
                self.stepSound.setPlayRate(random.uniform(0.9, 1.1))
                self.stepSound.play()

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
            # Standing to swing isn't being stuck.
            self.stillSince = now
            if self.swingAt is not None and now >= self.swingAt:
                self.swingAt = None
                self.__hit()
            if now >= self.nextSwing - G.COG_SWING_TIME + 0.9:
                self.state = 'chase'
            return
        goal = self.__goal(now)
        if goal is None:
            self.stillSince = now
            self.__loop('neutral')
            return
        to = Point3(goal[0], goal[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        dist = to.length()
        reach = G.COG_REACH + (self.radius if self.lure is None else 0.5)
        if dist <= reach and self.lure is None:
            self.stillSince = now
            self.__face(goal)
            if now >= self.nextSwing:
                self.__swing(now)
            else:
                self.__loop('neutral')
            return
        if dist <= 1.0:
            self.stillSince = now
            self.__loop('neutral')
            return
        # A cog that gets nowhere for a while (a fence, a hedge, a corner)
        # flies back in somewhere nearer, as BO1's zombies respawn.
        if dist < self.bestDist - 1.0:
            self.bestDist = dist
            self.lastProgress = now
        elif not self.lastProgress:
            self.lastProgress = now
        if self.stillFrom is None or (Point3(self.pos) - self.stillFrom).length() > STILL_DISTANCE:
            self.stillFrom = Point3(self.pos)
            self.stillSince = now
        # (Getting no closer is not enough: a cog chasing a toon who runs
        # off gets further away while walking fine.)
        if self.lure is None and dist > 10.0 and now - self.stillSince > STILL_TIME:
            self.__reland(goal)
            return
        # A Presentation pulls hard: every cog hurries to it, so the ones
        # across the playground get there before it pops.
        speed = self.speed if self.lure is None else max(self.speed, G.COG_SPEEDS[-1])
        way = self.__waypoint(goal, now)
        toWay = Point3(way[0], way[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        wayDist = toWay.length()
        if wayDist < 0.05:
            toWay, wayDist = to, dist
        self.__step(toWay / max(wayDist, 0.001), min(wayDist if way is goal else max(wayDist, speed * dt), speed * dt), now,
                    routed=self.routed)
        self.__moveAnim(speed)
        self.__footstep(speed, dt)

    def __clearWide(self, a, b):
        """A walk from a to b with room for the cog's body: the middle line
        and one either side of it."""
        arena = self.arena
        lift = 2.0
        pa = Point3(a[0], a[1], a[2] + lift)
        pb = Point3(b[0], b[1], a[2] + lift)
        if not arena.clearLine(pa, pb):
            return False
        d = Vec3(pb - pa)
        d.setZ(0)
        if d.lengthSquared() < 0.01:
            return True
        d.normalize()
        side = Vec3(-d[1], d[0], 0) * max(0.8, self.radius * 0.7)
        return arena.clearLine(pa + side, pb + side) and arena.clearLine(pa - side, pb - side)

    def __waypoint(self, goal, now):
        """Where to walk next: straight at the goal when there is room,
        otherwise the furthest open cell along the playground's shortest
        way to it (round the gazebo, the fences, the trees)."""
        if now < self.nextRoute:
            return self.route if self.route is not None else goal
        self.nextRoute = now + ROUTE_EVERY * random.uniform(0.85, 1.15)
        self.route = None
        self.routed = True
        if self.__clearWide(self.pos, goal):
            return goal
        flow, goalCell = self.arena.flowTo(goal)
        cell = self.arena.nearestCell(self.pos)
        if not flow or cell is None or cell not in flow:
            # Off the map: feel along the walls the old way.
            self.routed = False
            return goal
        chain = []
        c = flow.get(cell)
        while c is not None and len(chain) < ROUTE_LOOKAHEAD:
            chain.append(c)
            c = flow.get(c)
        if not chain:
            # In the toon's own cell: straight at it.
            return goal
        pick = chain[0]
        for c in reversed(chain[1:]):
            if self.arena.clearLine(Point3(self.pos[0], self.pos[1], self.pos[2] + 2), Point3(self.arena.cellPoint(c)) + Vec3(0, 0, 2)):
                pick = c
                break
        self.route = Point3(self.arena.cellPoint(pick))
        return self.route

    def __reland(self, goal):
        player = self.game.player
        landing = self.arena.landingNear(goal, player.getEye(), player.getForward())
        if landing is None:
            toons = [t.getPos() for t in [player] + self.game.npcs]
            landing = self.arena.pickLanding(toons, player.getEye(), player.getForward())
        if landing is None:
            # Nowhere out of sight this time: try again in a moment.
            self.stillSince = globalClock.getFrameTime() - STILL_TIME + 1.0
            return
        self.bestDist = 1e9
        self.lastProgress = 0.0
        self.stillFrom = None
        self.route = None
        self.nextRoute = 0.0
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

    def __step(self, direction, length, now, routed=False):
        pos = self.pos
        if routed:
            # The way was checked (a clear walk, or the playground's cells):
            # no feeling for walls, which mistook Toon Hall's steps for one.
            self.detour = None
        elif self.detour is not None and now < self.detourUntil:
            direction = self.detour
        ahead = Point3(pos + direction * max(length, 2.5))
        if not routed and not self.arena.clearLine(Point3(pos[0], pos[1], pos[2] + 2), Point3(ahead[0], ahead[1], pos[2] + 2)):
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
            if gap.length() < CROWD_RADIUS + 1.0:
                # Waiting behind the crowd isn't being stuck.
                self.stillSince = now
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

    def fleeFrom(self, point, until):
        # Second Wind: run straight away from the downed toon until it's up.
        away = Vec3(self.pos[0] - point[0], self.pos[1] - point[1], 0)
        if away.lengthSquared() < 0.01:
            away = Vec3(1, 0, 0)
        away.normalize()
        self.lureTo(Point3(self.pos) + away * FLEE_DISTANCE, until)

    def lureTo(self, point, until):
        self.lure = Point3(point)
        self.lureUntil = until
