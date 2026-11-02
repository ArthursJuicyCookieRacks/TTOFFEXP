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
# How long a cog stays under (or over) a toon it can't reach before it
# flies back in on the toon's level.
OFF_LEVEL_TIME = 5.0
# How often a cog looks again for its way to the toon.
ROUTE_EVERY = 0.35
# How far ahead along its route a cog looks for a corner it can cut.
ROUTE_LOOKAHEAD = 5
# A cog dropping through a big map's ceiling lands with a thud.
CEILING_SOUND = 'phase_5/audio/sfx/cogbldg_land.ogg'
# Footsteps: heard this far, by the nearest few cogs.
STEP_SOUND = 'phase_5/audio/sfx/ENC_cogside_step.ogg'
# Arthur: cogs behind the toon couldn't be heard. Louder, heard further,
# and fading slowly so the ones just behind are clear.
STEP_HEAR = 70.0
STEP_VOLUME = 1.0
# Arthur (again): still hard to tell when a cog is behind you. One that
# is behind the toon (out of sight) and close steps at full loudness, and
# when it first gets this close it calls out, as BO1's zombies growl.
BEHIND_RANGE = 30.0
BEHIND_ANGLE = 75.0
BEHIND_WARN = 15.0
BEHIND_WARN_EVERY = 5.0
# Now and then a cog talks the way it does on the streets (its murmurs,
# statements and questions), loudest close by.
VOICE_EVERY = (4.0, 11.0)
VOICE_HEAR = 55.0
VOICE_VOLUME = 0.7
# How far past its middle a cog's front is checked: its radius, up to this.
BODY_LEAD = 1.2
# How long a heading chosen to get round a wall is kept.
DETOUR_TIME = 0.8
GROUND_EVERY = 0.1
HEAD_FRACTION = 0.72
# The neck counts as the head, a little below where the head joint is.
NECK_MARGIN = 0.04
POP_TIME = 0.35
HURT_FLASH = 0.12


class SurvivalCog:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalCog')
    gearSounds = None

    def __init__(self, game, name, landing, roundNum, snatcher=False, entry=None):
        self.game = game
        self.snatcher = snatcher
        self.arena = game.arena
        self.offLevelSince = None
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
        self.headFraction = HEAD_FRACTION
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
        self.nextVoice = globalClock.getFrameTime() + random.uniform(*VOICE_EVERY)
        self.nextWarn = 0.0
        self.suit.setPos(landing)
        self.suit.setH(random.uniform(0, 360))
        self.prop = None
        # A big map's way in: a window, the ceiling, a roof (see __enter).
        self.entry = entry
        self.enterNext = 0.0
        self.climbing = False
        if entry is not None and entry.kind != 'sky':
            self.__enter(entry)
        else:
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

    # --- Coming in on a big map ---

    def __enter(self, entry):
        """A window: the cog shows up outside it and tears the boards off
        one by one before it climbs in. A hole in the ceiling: it drops
        through. A roof: it flies down onto the edge and jumps off."""
        suit = self.suit
        suit.setTransparency(1)
        if entry.kind == 'window':
            win = entry.window
            self.pos = Point3(win['outside'])
            suit.setPos(self.pos)
            self.__face(Point3(win['inside']))
            self.state = 'entering'
            self.enterNext = globalClock.getFrameTime() + random.uniform(1.0, 1.6)
            if win.get('hover'):
                # An upstairs window: it hangs there on its propeller.
                self.__propeller()
            self.__loop('neutral')
            self.track = Sequence(LerpColorScaleInterval(suit, 0.6, Vec4(1, 1, 1, 1), startColorScale=Vec4(1, 1, 1, 0)),
                                  Func(suit.clearTransparency))
            self.track.start()
            return
        if entry.kind == 'ceiling':
            top, low = Point3(entry.top), Point3(entry.pos)
            self.pos = low
            dur = suit.getDuration('landing')
            suit.pose('landing', 0)
            self.track = Sequence(
                Parallel(LerpColorScaleInterval(suit, 0.3, Vec4(1, 1, 1, 1), startColorScale=Vec4(1, 1, 1, 0)),
                         LerpPosInterval(suit, 0.55, low, startPos=top, blendType='easeIn')),
                Func(lambda: base.playSfx(base.loader.loadSfx(CEILING_SOUND), volume=0.5, node=suit)),
                ActorInterval(suit, 'landing', startTime=dur * 0.55, duration=dur * 0.45),
                Func(self.__landed))
            self.track.start()
            return
        # A roof: down onto the edge on the propeller, then a jump off it.
        top, low = Point3(entry.top), Point3(entry.pos)
        self.pos = low
        self.__propeller()
        sky = Point3(top[0], top[1], top[2] + FLY_HEIGHT * 0.5)
        mid = Point3((top[0] + low[0]) / 2, (top[1] + low[1]) / 2, max(top[2], low[2]) + 2.5)
        sound = base.loader.loadSfx('phase_5/audio/sfx/ENC_propeller_in.ogg')
        suit.setPos(sky)
        d = low - top
        if abs(d[0]) + abs(d[1]) > 0.01:
            suit.setH(-math.degrees(math.atan2(d[0], d[1])))
        self.track = Sequence(
            Parallel(LerpPosInterval(suit, FLY_TIME * 0.6, top, startPos=sky, blendType='easeIn'),
                     LerpColorScaleInterval(suit, 0.8, Vec4(1, 1, 1, 1), startColorScale=Vec4(1, 1, 1, 0)),
                     SoundInterval(sound, duration=FLY_TIME * 0.6, node=suit, volume=0.5),
                     ActorInterval(self.prop, 'propeller', constrainedLoop=1, duration=FLY_TIME * 0.6)),
            Func(self.__dropProp),
            LerpPosInterval(suit, 0.35, mid, startPos=top, blendType='easeOut'),
            LerpPosInterval(suit, 0.35, low, startPos=mid, blendType='easeIn'),
            Func(self.__landed))
        self.track.start()

    def __propeller(self):
        if self.prop is None:
            prop = BattleProps.globalPropPool.getProp('propeller')
            head = self.suit.find('**/joint_head')
            prop.reparentTo(head)
            prop.loop('propeller')
            self.prop = prop

    def __dropProp(self):
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None

    def __tickEntering(self, dt, now):
        """At a boarded window: swing at a toon right inside, otherwise
        pull another board off; once there are none, climb in."""
        if self.climbing:
            return
        win = self.entry.window
        station = win.get('station')
        if self.swingAt is not None and now >= self.swingAt:
            self.swingAt = None
            self.__hit()
        target = self.game.nearestToon(self.pos)
        self.target = target
        if target is not None:
            tp = target.getPos()
            flat = Point3(tp[0], tp[1], 0) - Point3(self.pos[0], self.pos[1], 0)
            if flat.length() <= G.COG_REACH + self.radius + 1.0 and abs(tp[2] - win['pos'][2]) < 4.0:
                # BO1: a zombie at the window hits whoever stands at it.
                if now >= self.nextSwing:
                    self.__face(tp)
                    self.__swing(now)
                    self.state = 'entering'
                return
        if station is None or station.isOpen():
            self.__climbIn(win)
            return
        if now >= self.enterNext:
            self.enterNext = now + random.uniform(1.0, 1.4)
            station.tearBoard()
            anim = 'pickpocket' if 'pickpocket' in self.suit.getAnimNames() else 'neutral'
            self.anim = None
            self.suit.play(anim)

    def __climbIn(self, win):
        self.climbing = True
        start = Point3(self.pos)
        end = Point3(win['inside'])
        mid = Point3((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, max(start[2], end[2]) + win['sill'] + 0.5)
        self.__face(end)
        self.__loop('walk', 1.2)
        self.track = Sequence(LerpPosInterval(self.suit, 0.45, mid, startPos=start, blendType='easeOut'),
                              LerpPosInterval(self.suit, 0.4, end, startPos=mid, blendType='easeIn'),
                              Func(self.__inside, end))
        self.track.start()

    def __inside(self, end):
        self.climbing = False
        self.pos = Point3(end)
        self.__landed()

    def __hop(self, point):
        """Up onto a ledge a toon could only drop from: a short flight on
        the propeller."""
        self.state = 'landing'
        start = Point3(self.pos)
        end = Point3(point)
        self.pos = end
        mid = Point3((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, max(start[2], end[2]) + 3.0)
        self.__propeller()
        self.__face(end)
        self.track = Sequence(LerpPosInterval(self.suit, 0.6, mid, startPos=start, blendType='easeOut'),
                              LerpPosInterval(self.suit, 0.4, end, startPos=mid, blendType='easeIn'),
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
        self.suit.setColorScale(1, 1, 1, 1)
        self.track = None
        self.state = 'chase'
        self.__findNeck()
        self.__moveAnim(self.speed if self.lure is None else max(self.speed, G.COG_SPEEDS[-1]))

    def __findNeck(self):
        """Where the head starts: hits from the neck up are headshots."""
        try:
            self.suit.pose('neutral', 0)
            self.suit.update(force=True)
            head = self.suit.find('**/joint_head')
            if not head.isEmpty() and self.height > 0:
                z = head.getZ(render) - self.pos[2]
                self.headFraction = max(0.5, min(0.85, z / self.height - NECK_MARGIN))
        except Exception:
            pass
        self.anim = None

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
            volume = STEP_VOLUME * max(0.0, 1.0 - dist / STEP_HEAR) ** 0.6
            behind = self.behind()
            if behind is not None:
                # Close behind is as loud as a step can be, and a bit
                # heavier, so it stands out from the ones in front.
                volume = max(volume, STEP_VOLUME * max(0.0, 1.0 - behind / BEHIND_RANGE) ** 0.25)
            if volume > 0.01:
                self.stepSound.setVolume(min(1.0, volume))
                self.stepSound.setPlayRate(random.uniform(0.8, 0.9) if behind is not None else random.uniform(0.9, 1.1))
                self.stepSound.play()

    def behind(self):
        """How far away this cog is, if it is behind the player (out of
        their view) and within BEHIND_RANGE; otherwise None."""
        player = self.game.player
        if player is None:
            return None
        eye = player.getPos()
        to = Vec3(self.pos[0] - eye[0], self.pos[1] - eye[1], 0)
        dist = to.length()
        if dist > BEHIND_RANGE or dist < 0.01:
            return None
        forward = player.getFlatForward()
        forward.setZ(0)
        if forward.lengthSquared() < 1e-6:
            return None
        forward.normalize()
        if to.dot(forward) / dist > math.cos(math.radians(BEHIND_ANGLE)):
            return None
        return dist

    def __warnBehind(self, now):
        """A cog that has just come up close behind the player calls out
        at full loudness (only one at a time, every few seconds)."""
        behind = self.behind()
        if behind is None or behind > BEHIND_WARN or now < self.nextWarn:
            return
        self.nextWarn = now + BEHIND_WARN_EVERY
        if not self.game.mayWarnBehind(now):
            return
        try:
            sounds = [snd for snd in self.suit.getDialogueArray() if snd]
        except Exception:
            sounds = []
        if sounds:
            base.playSfx(random.choice(sounds[:4]), volume=1.0)

    def __talk(self, now):
        if now < self.nextVoice:
            return
        self.nextVoice = now + random.uniform(*VOICE_EVERY)
        # Only the nearest few talk, so a crowd isn't a din.
        if not self.game.wantCogSteps(self):
            return
        try:
            sounds = [snd for snd in self.suit.getDialogueArray() if snd]
        except Exception:
            sounds = []
        if not sounds:
            return
        dist = (camera.getPos(render) - self.suit.getPos(render)).length()
        volume = VOICE_VOLUME * max(0.0, 1.0 - dist / VOICE_HEAR)
        if volume > 0.02:
            base.playSfx(random.choice(sounds[:4]), volume=volume)

    def __loop(self, anim, rate=1.0):
        if self.anim != (anim, rate):
            self.anim = (anim, rate)
            self.suit.setPlayRate(rate, anim)
            self.suit.loop(anim)

    # --- Each tick ---

    def tick(self, dt, now):
        if self.dead or self.state == 'landing':
            return
        if self.state == 'entering':
            self.__tickEntering(dt, now)
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
        level = self.lure is not None or self.__sameLevel(goal)
        if dist <= reach and self.lure is None and level:
            self.stillSince = now
            self.__face(goal)
            if now >= self.nextSwing:
                self.__swing(now)
            else:
                self.__loop('neutral')
            return
        if dist <= 1.0 and level:
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
        # Nor is milling about below or above the toon, unable to reach it
        # (under a dock): after a while it flies in somewhere it can.
        if level or self.lure is not None:
            self.offLevelSince = None
        elif self.offLevelSince is None:
            self.offLevelSince = now
        if self.lure is None and self.offLevelSince is not None and dist < 14.0 and now - self.offLevelSince > OFF_LEVEL_TIME \
                and not self.arena.big:
            self.offLevelSince = None
            self.__reland(goal)
            return
        if self.lure is None and dist > 10.0 and now - self.stillSince > STILL_TIME:
            self.__reland(goal)
            return
        # A Presentation pulls hard: every cog hurries to it, so the ones
        # across the playground get there before it pops.
        speed = self.speed if self.lure is None else max(self.speed, G.COG_SPEEDS[-1])
        way = self.__waypoint(goal, now)
        if way is None:
            # A big map: the toon is somewhere no cog can walk to (the
            # projection booth). It waits where it is.
            self.stillSince = now
            self.__loop('neutral')
            return
        if self.state != 'chase':
            return
        toWay = Point3(way[0], way[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        wayDist = toWay.length()
        if wayDist < 0.05:
            toWay, wayDist = to, dist
        self.__step(toWay / max(wayDist, 0.001), min(wayDist if way is goal else max(wayDist, speed * dt), speed * dt), now,
                    routed=self.routed)
        self.__moveAnim(speed)
        self.__footstep(speed, dt)
        self.__talk(now)
        self.__warnBehind(now)

    def __clearWide(self, a, b):
        """A walk from a to b with room for the cog's body: the middle line
        and one either side of it, at its knees, waist and chest."""
        if self.arena.big:
            return self.__clearWideBig(a, b)
        return self.arena.bodyClear(a, b, max(0.8, self.radius * 0.7))

    def __clearWideBig(self, a, b):
        """A big map's check (its doors, railings and window sills were
        laid out for it): the middle line and one either side of it, at
        the waist."""
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
        big = self.arena.big
        # Straight at the goal only on its level: from the harbour bed
        # under a dock nothing stood between the cog and the toon overhead,
        # so it walked under the toon and stayed there. On a big map, only
        # on the very same floor.
        if abs(goal[2] - self.pos[2]) <= G.COG_REACH_RISE \
                and self.__clearWide(self.pos, goal) and (not big or abs(goal[2] - self.pos[2]) < 1.5):
            return goal
        flow, goalCell = self.arena.flowTo(goal)
        cell = self.arena.nearestCell(self.pos)
        if big:
            return self.__bigWaypoint(goal, flow, cell)
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
            if self.__clearWide(self.pos, self.arena.cellPoint(c)):
                pick = c
                break
        self.route = Point3(self.arena.cellPoint(pick))
        return self.route

    def __bigWaypoint(self, goal, flow, cell):
        """The way over a big map's floors: the next cells along the flow,
        cutting corners only along level floor, hopping (or dropping) where
        the map joins two floors by hand. None when the toon can't be
        reached from here."""
        if not flow or cell is None or cell not in flow:
            return None
        chain = []
        c = cell
        while len(chain) < ROUTE_LOOKAHEAD:
            nxt = flow.get(c)
            if nxt is None:
                break
            kind = self.arena.isSpecial(c, nxt)
            if kind:
                if not chain:
                    if kind == 'hop':
                        self.__hop(self.arena.cellPoint(nxt))
                        return Point3(self.pos)
                    # A drop: walk off the edge toward the floor below.
                    return Point3(self.arena.cellPoint(nxt))
                break
            chain.append(nxt)
            c = nxt
        if not chain:
            return goal
        here = Point3(self.pos[0], self.pos[1], self.pos[2] + 2)
        pick = chain[0]
        for c in reversed(chain[1:]):
            p = self.arena.cellPoint(c)
            if abs(p[2] - self.pos[2]) > 0.6:
                continue
            if all(abs(self.arena.cellPoint(k)[2] - self.pos[2]) <= 0.6 for k in chain[:chain.index(c) + 1]) and \
                    self.arena.clearLine(here, Point3(p) + Vec3(0, 0, 2)):
                pick = c
                break
        self.route = Point3(self.arena.cellPoint(pick))
        return self.route

    def __reland(self, goal):
        if self.arena.big:
            return self.__bigReland(goal)
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

    def __bigReland(self, goal):
        """Stuck on a big map: back out and in again by the nearest way in."""
        entry = self.game.pickEntry(near=goal)
        if entry is None:
            self.stillSince = globalClock.getFrameTime() - STILL_TIME + 1.0
            return
        self.bestDist = 1e9
        self.lastProgress = 0.0
        self.stillFrom = None
        self.route = None
        self.nextRoute = 0.0
        self.detour = None
        self.anim = None
        self.entry = entry
        self.game.count('cogs relanded')
        if entry.kind == 'sky':
            self.pos = Point3(entry.pos)
            self.state = 'landing'
            self.suit.setPos(self.pos)
            self.__flyIn(self.pos)
        else:
            self.state = 'landing'
            self.__enter(entry)

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
            # The way was checked (a clear walk, or the playground's cells).
            self.detour = None
        elif self.detour is not None and now < self.detourUntil:
            direction = self.detour
        if not routed and not self.__fits(direction, max(length, 2.5)):
            # A wall: try the ways round it and keep the first that is clear.
            found = None
            for angle in (45, -45, 90, -90, 135, -135):
                turned = self.__turn(direction, angle)
                if self.__fits(turned, 4.0):
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
        # Whatever the way says, the body itself never goes through
        # anything solid: the step is checked at the cog's knees, waist and
        # chest (Arthur: cogs walked through Old School Toontown's gazebo,
        # trees and stone wall). Blocked, it slides along the wall instead.
        if not self.arena.big and not self.__fits(direction, length):
            for angle in (30, -30, 60, -60, 90, -90):
                turned = self.__turn(direction, angle)
                if self.__fits(turned, length):
                    direction = turned
                    break
            else:
                self.__loop('neutral')
                return
        new = Point3(pos + direction * length)
        if now >= self.nextGround:
            self.nextGround = now + GROUND_EVERY
            z = self.arena.nav.groundZ(new[0], new[1], pos[2])
            if z is None:
                # Off a ledge deeper than a step: down to the floor below
                # (before, the cog kept its height and walked on air).
                low = self.arena.floorUnder(new[0], new[1], pos[2], 1.0)
                if low is not None and low < pos[2]:
                    z = low
            new.setZ(z if z is not None else pos[2])
        else:
            new.setZ(pos[2])
        self.pos = new
        self.suit.setPos(new)
        self.__face(new + direction)

    @staticmethod
    def __turn(direction, angle):
        a = math.radians(angle)
        return Vec3(direction[0] * math.cos(a) - direction[1] * math.sin(a),
                    direction[0] * math.sin(a) + direction[1] * math.cos(a), 0)

    def __fits(self, direction, length):
        """Whether the cog's body can go length along direction: the walk
        and its front edge (the cog's own radius further on)."""
        pos = self.pos
        if self.arena.big:
            ahead = Point3(pos + direction * length)
            return self.arena.clearLine(Point3(pos[0], pos[1], pos[2] + 2), Point3(ahead[0], ahead[1], pos[2] + 2))
        reach = length + min(self.radius, BODY_LEAD)
        return self.arena.bodyClear(pos, Point3(pos[0] + direction[0] * reach, pos[1] + direction[1] * reach, pos[2]),
                                    min(self.radius * 0.6, BODY_LEAD))

    def nudge(self, dx, dy):
        """Pushed aside by a cog it walked into (SurvivalGame keeps them
        from standing in each other)."""
        if abs(dx) + abs(dy) < 0.001:
            # Too small to move, and a line check from a point to itself
            # fails an assertion in Panda.
            return
        a = Point3(self.pos)
        b = Point3(self.pos[0] + dx, self.pos[1] + dy, self.pos[2])
        d = Vec3(dx, dy, 0)
        d.normalize()
        if not self.arena.bodyClear(a, b + d * min(self.radius, BODY_LEAD)):
            return
        self.pos = Point3(self.pos[0] + dx, self.pos[1] + dy, self.pos[2])
        self.suit.setPos(self.pos)

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
        # A cog popped mid-swing never lands its hit (Arthur: one popped by
        # a melee still knocked the toon down).
        if self.dead or self.target is None or not self.target.alive():
            return
        target = self.target.getPos()
        flat = Point3(target[0], target[1], 0) - Point3(self.pos[0], self.pos[1], 0)
        if flat.length() <= G.COG_REACH + self.radius + 1.0 and self.__sameLevel(target):
            self.target.hurt(G.COG_HIT, self)

    def __sameLevel(self, target):
        """Whether the cog can really reach a toon at target: about the
        same height, with no wall or floor edge between them. The reach
        was measured flat, so a cog on the dry harbour bed under Donald's
        Dock's docks, or down in Melodyland's bowl, hit the toon standing
        above it (Arthur: hurt and knocked down out of nowhere)."""
        if self.arena.big:
            # A big map's floors: a toon on the balcony or the stairs
            # overhead is out of reach; railings don't stop a swing.
            return abs(target[2] - self.pos[2]) < 4.0
        if abs(target[2] - self.pos[2]) > G.COG_REACH_RISE:
            return False
        return self.arena.bodyClear(Point3(self.pos), Point3(target))

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
        return t, hitZ > self.pos[2] + self.height * self.headFraction

    def hurt(self, damage, head=False, bonk=False):
        if self.dead:
            return 0
        if self.game.power('instapop'):
            damage = self.hp
        elif head:
            # Neck and up: BO1's headshot damage.
            damage = int(damage * G.HEAD_MULT)
        self.hp -= damage
        self.__flash()
        if self.hp <= 0:
            self.pop(head, bonk)
            return 2
        return 1

    def __flash(self):
        suit = self.suit
        if getattr(self, 'flashTrack', None):
            self.flashTrack.finish()
        self.flashTrack = Sequence(Func(suit.setColorScale, 1, 0.45, 0.45, 1), Wait(HURT_FLASH), Func(suit.setColorScale, 1, 1, 1, 1))
        self.flashTrack.start()

    def pop(self, head=False, bonk=False):
        """Gears everywhere, the way a cog goes in battle, but quick."""
        if self.dead:
            return
        self.dead = True
        self.state = 'dead'
        self.swingAt = None
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
        if getattr(self, 'flashTrack', None):
            self.flashTrack.pause()
            self.flashTrack = None
        if self.track:
            self.track.finish()
            self.track = None
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None
        if self.suit is not None:
            # delete(), not just cleanup(): cleanup() leaves the cog's name
            # tag alive, and each one ran a task every frame for the rest of
            # the session (hundreds after a long game: the lag in Toontown).
            self.suit.delete()
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
