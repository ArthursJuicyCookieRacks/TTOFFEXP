"""Plays the NPC players' part in a boss fight.

The boss fights trust each toon's client to say what its toon did: a pie that
landed, a safe swung into the CFO, a juror fired into a chair, a plate served.
This says it for the NPCs, at a pace and with a hit rate a decent player
would have, and shows their pies flying on the player's screen.

The cog rounds of each fight are ordinary battles; NPCBattleCrew plays those.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from panda3d.core import Point3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.npcplayers.NPCNav import getNav
from toontown.toonbase import ToontownGlobals

TICK = 0.5
# Seconds between one NPC's throws.
THROW_TIME = (1.6, 3.2)
# Seconds between one NPC's goes at slower jobs: a safe swung on a crane, a
# toon fired from a cannon, a plate carried, a golf swing.
SLOW_TIME = (3.0, 6.0)
SLOW_JOBS = (('l', 'BattleTwo'), ('c', 'BattleTwo'))
# Swinging a crane over to a safe or a goon, and from there to the CFO.
CRANE_TIME = (4.0, 7.0)
# Aiming a banquet table's water pitcher at the CEO.
PITCHER_TIME = (4.0, 6.0)
PITCHER_HIT_CHANCE = 0.45
# How many NPCs take a pitcher; the rest golf, fetch toon-up food or keep
# out of his way.
PITCHERS = 3
GOLF_TIME = (4.0, 6.0)
# Chances a pie does what it was thrown for.
HIT_CHANCE = 0.4
# The VP's underside opens while he shoots gears out of it; a pie thrown
# into the opening stuns him. A stunner standing ready in front of him
# throws as soon as the doors open, and keeps throwing while they are
# open: this often a throw, and this often one goes in.
STUN_CHANCE = 0.5
STUN_THROW_TIME = (1.2, 2.0)
# While he is dizzy everyone runs in close, from all sides, and pies his
# body as fast as it can; close up most pies land.
DIZZY_THROW_TIME = (1.0, 2.0)
DIZZY_RANGE = (12.0, 17.0)
DIZZY_HIT_CHANCE = 0.65
# The gears he shoots from the opening: how often one hits a toon standing
# in front of him (the stunners' risk), and how far they reach.
STRAFE_HIT_CHANCE = 0.3
STRAFE_REACH = 45.0
# A toon the VP aims a gear at runs sideways out of its way, usually.
SIDESTEP_CHANCE = 0.7
SIDESTEP = (8.0, 12.0)
# Out of pies: a run to the cage to refill, close enough to touch it.
CAGE_NEAR = 9.0
# One evidence throw after another at the CJ's scale, and faster still
# during the witness bonus, when evidence counts double.
EVIDENCE_TIME = (1.5, 2.5)
BONUS_TIME = (0.8, 1.4)
# The witness stand (courtroom coordinates), where a toon out of evidence
# runs to refill: the floor just in front of the stand (its own floor is a
# raised step at y 84-100), close enough to touch its rail.
WITNESS_STAND = (55, 78)
WITNESS_NEAR = 10.0
# Evidence on the CJ's scale pan, a big target.
EVIDENCE_HIT_CHANCE = 0.55
# The courtroom floor the toons throw from (the scale stands on the bench at
# y 89): where they are spread out at the start of the round, and the middle
# of their wandering.
COURTROOM_X = (-45.0, 45.0)
COURTROOM_Y = (-5.0, 55.0)
COURTROOM_FLOOR = (0.0, 25.0)
# One or two toons have the lawyers as their job: pies that stun them for
# a while so they stop loading the cogs' pan.
LAWYER_STUNNERS = (1, 2)
LAWYER_HIT_CHANCE = 0.5
# The VP: only a few toons go for his stun (the rest wait to hit him while
# he is dizzy), and they give him a while on his feet before trying again.
STUNNERS = (2, 3)
STUN_REST = (4.0, 8.0)
# The CFO: how likely a safe swung at him lands, and how long one crane is
# kept free for the player at the start.
CRANE_HIT_CHANCE = 0.4
CRANE_FOR_PLAYER = 30.0
# The CFO's floor toons: they jump on the goons' heads to stun them for the
# craners, and pick up the treasures the stunned goons leave when hurt.
GOON_STOMP_RANGE = 6.0
GOON_STOMP_CHANCE = 0.6
TREASURE_BELOW = 0.6
TREASURE_NEAR = 4.0
# The CJ: how likely a toon fired from a cannon lands in a chair.
CANNON_HIT_CHANCE = 0.3
# The CEO: how many NPCs take a golf spot, and how likely a ball hits him.
GOLFERS = 2
GOLF_HIT_CHANCE = 0.45
# Between goes the NPCs move about the arena on their own, as players do,
# rather than following the player: how often, and how far from the boss.
ROAM_TIME = (1.0, 4.0)
ROAM_RANGE = (14.0, 40.0)
# In the pie round the toons not stunning him keep moving, as players do.
PIE_ROAM_TIME = (0.5, 2.5)
PIE_ROAM_RANGE = (16.0, 34.0)
# The stunners go up to the open ground in front of him and throw from
# there, this far from his middle (he swats within about 14).
STUN_SPOT = (18.0, 24.0)
STUN_SPOT_NEAR = 5.0
# Within this of him an NPC counts as near, for his gear attacks.
NEAR_BOSS = 40.0
# No roaming path passes nearer the boss than this.
BOSS_CLEAR = 11.0
# Now and then an NPC stops to emote instead of walking.
ROAM_EMOTE_CHANCE = 0.15
# Every stretch where the player's toon is let loose: the goes against the
# boss, and the breaks after each cog fight and after the win.
ROAM_STATES = (('s', 'RollToBattleTwo'), ('s', 'BattleTwo'), ('s', 'BattleThree'), ('s', 'NearVictory'),
               ('s', 'Victory'), ('s', 'Reward'),
               ('m', 'PrepareBattleThree'), ('m', 'BattleThree'), ('m', 'Victory'), ('m', 'Reward'),
               ('l', 'RollToBattleTwo'), ('l', 'BattleTwo'), ('l', 'BattleThree'), ('l', 'NearVictory'),
               ('l', 'Victory'), ('l', 'Reward'),
               ('c', 'BattleTwo'), ('c', 'PrepareBattleFour'), ('c', 'BattleFour'), ('c', 'Victory'),
               ('c', 'Reward'))
# The boss's attacks on the NPCs: how close to his middle counts as touching
# him, how often a jump clears an attack that can be jumped, how often a toon
# in reach gets out of the way of a swat, and how long a hit toon is left alone
# (as a stunned player is).
BOSS_BODY = 9.0
JUMP_CHANCE = 0.55
DODGE_CHANCE = 0.3
HIT_REST = 3.0
JUMPABLE = (ToontownGlobals.BossCogAreaAttack, ToontownGlobals.BossCogGavelStomp,
            ToontownGlobals.BossCogGolfAreaAttack)
DIRECTED = (ToontownGlobals.BossCogDirectedAttack, ToontownGlobals.BossCogSlowDirectedAttack,
            ToontownGlobals.BossCogGearDirectedAttack)
HIT_STATES = ('BattleThree', 'BattleFour', 'RollToBattleTwo')
# Toon-up pies for the player: only once it is really hurt, and one healer
# at a time with a breather between heals, not a constant shower of them.
HEAL_PLAYER_BELOW = 0.25
HEAL_HIT_CHANCE = 0.7
HEAL_REST = 9.0
# After a zap or a jump the toon's walk animation is started again (the
# slip and jump leave it posed, so it would slide about otherwise).
ANIM_REFRESH_AFTER = 2.5
# A pie that misses lands on the floor this far from what it was thrown at.
MISS_BY = (4.0, 9.0)


def isNPCId(air, avId):
    toon = air.doId2do.get(avId) if avId else None
    return toon is not None and getattr(toon, 'isNPCPlayer', lambda: False)()


class NPCBossCrew:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCBossCrew')

    def __init__(self, manager, boss):
        self.manager = manager
        self.air = manager.air
        self.boss = boss
        self.dept = boss.dna.dept
        self.nextAction = {}
        self.lastAttack = None
        self.safeUntil = {}
        self.pieSequence = {}
        self.foodNum = 1000
        self.stateSince = (None, 0)
        self.stunners = None
        self.lawyerStunners = None
        self.stunOffsets = {}
        self.chasing = {}
        self.dizzy = False
        self.stunRestUntil = 0
        self.nextRoam = {}
        self.placed = False
        self.nextHeal = 0
        self.animRefresh = {}
        self.doorWasOpen = False
        self.taskName = 'npcBossCrew-%d' % boss.doId
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    def destroy(self):
        taskMgr.remove(self.taskName)
        self.boss = None

    def count(self, key):
        self.manager.stats[key] = self.manager.stats.get(key, 0) + 1

    def members(self):
        boss = self.boss
        members = [npc for npc in self.manager.party.members
                   if not npc.isDeleted() and npc.doId in boss.involvedToons and npc.crew is None]
        for npc in members:
            # Laff and gags fill up once out of the boss fight altogether.
            npc.needsRefill = True
        return members

    def players(self):
        return [self.air.doId2do[t] for t in self.boss.involvedToons
                if t in self.air.doId2do and not getattr(self.air.doId2do[t], 'isNPCPlayer', lambda: False)()]

    def __tick(self, task):
        boss = self.boss
        if boss is None or boss.isDeleted():
            self.manager.bossCrewDone(self)
            return Task.done
        state = boss.getCurrentOrNextState()
        now = globalClock.getFrameTime()
        if state != self.stateSince[0]:
            self.stateSince = (state, now)
            # A new stretch: everyone gets going straight away.
            self.nextRoam = {}
            self.placed = False
        try:
            members = self.members()
            pieRound = self.dept == 's' and state == 'BattleThree'
            if self.dept == 'l' and state == 'BattleThree' and not self.placed:
                self.placed = True
                self.placeCourtroom(members)
            if pieRound:
                self.watchDizzy(now)
                self.markNear(members)
            self.takeHits(members)
            self.refreshAnims(members, now)
            if (self.dept, state) in ROAM_STATES:
                for npc in members:
                    if pieRound:
                        if self.refillTrip(npc, now):
                            continue
                        if self.dizzy:
                            self.closeIn(npc, now)
                        elif self.isStunner(npc):
                            self.goToStunSpot(npc, now)
                        else:
                            self.roam(npc, now)
                    elif self.dept == 'm' and state == 'BattleThree':
                        if not self.floorJob(npc, now):
                            self.roam(npc, now)
                    elif self.dept == 'l' and state == 'BattleThree':
                        if not self.witnessTrip(npc, now):
                            self.roam(npc, now)
                    else:
                        self.roam(npc, now)
            play = getattr(self, 'play%s%s' % (self.dept.upper(), state), None)
            if play is not None:
                pace = SLOW_TIME if (self.dept, state) in SLOW_JOBS else THROW_TIME
                if (self.dept, state) == ('m', 'BattleThree'):
                    pace = CRANE_TIME
                elif self.dept == 's' and boss.attackCode == ToontownGlobals.BossCogDizzyNow:
                    pace = DIZZY_THROW_TIME
                elif self.dept == 's' and state == 'BattleThree':
                    pace = STUN_THROW_TIME
                elif self.dept == 'l' and state == 'BattleThree':
                    pace = BONUS_TIME if getattr(boss, 'bonusState', False) else EVIDENCE_TIME
                for npc in members:
                    if now >= self.nextAction.get(npc.doId, 0):
                        self.nextAction[npc.doId] = now + random.uniform(*pace)
                        play(npc)
                        key = 'boss %s' % self.dept
                        self.manager.stats[key] = self.manager.stats.get(key, 0) + 1
        except Exception:
            self.notify.warning('boss crew failed')
            import traceback
            traceback.print_exc()
        return Task.again

    # --- Moving about ---

    def inBattle(self, npc):
        # A boss's cog battles are torn down, not finished: a toon keeps the
        # battle's id after the battle itself is gone.
        battleId = npc.getBattleId()
        return battleId > 0 and battleId in self.air.doId2do

    def isStationed(self, npc):
        # On a crane, in a cannon, at a golf spot or a table's pitcher, where the
        # game holds it.
        boss = self.boss
        for objects in (getattr(boss, 'cranes', None), getattr(boss, 'cannons', None),
                        getattr(boss, 'golfSpots', None), getattr(boss, 'tables', None)):
            for obj in objects or []:
                if getattr(obj, 'avId', 0) == npc.doId:
                    return True
        return False

    def canRoam(self, npc, now):
        if npc.walk is not None or npc.busy or now < self.nextRoam.get(npc.doId, 0):
            return False
        if self.isStationed(npc) or self.inBattle(npc) or getattr(npc, 'crew', None) is not None:
            # Held by the game, or fighting the cogs.
            self.nextRoam[npc.doId] = now + 1.0
            return False
        return True

    def roam(self, npc, now):
        if not self.canRoam(npc, now):
            return
        pieRound = self.dept == 's' and self.boss.getCurrentOrNextState() == 'BattleThree'
        self.nextRoam[npc.doId] = now + random.uniform(*(PIE_ROAM_TIME if pieRound else ROAM_TIME))
        center = self.bossPos()
        if center is None:
            return
        if self.dept == 'l' and self.boss.getCurrentOrNextState() == 'BattleThree':
            # The courtroom floor in front of the bench, not the bench.
            center = Point3(COURTROOM_FLOOR[0], COURTROOM_FLOOR[1], 0)
        self.syncPos(npc)
        if not pieRound and random.random() < ROAM_EMOTE_CHANCE:
            from toontown.npcplayers.NPCPlayerManagerAI import IDLE_EMOTES
            npc.b_setEmoteState(random.choice(IDLE_EMOTES), 1.0)
            return
        nav = getNav()
        pos = npc.getPos()
        for i in range(6):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(*(PIE_ROAM_RANGE if pieRound else ROAM_RANGE))
            target = Point3(center[0] + dist * math.cos(angle), center[1] + dist * math.sin(angle), pos[2])
            path = nav.walkable(pos, target)
            if path and not self.nearBoss(path, center):
                self.startWalk(npc, path)
                return
        # Nowhere to go from here this time; try again next tick.
        self.nextRoam[npc.doId] = now

    def startWalk(self, npc, path):
        # The scenes leave toons posed (a slip, a jump, the elevator ride),
        # and a posed toon slides along; a fresh Happy state runs again.
        self.wakeAnim(npc)
        npc.walk = [path, ToontownGlobals.ToonForwardSpeed, None, None]

    def wakeAnim(self, npc):
        npc.b_setAnimState('neutral', 1.0)
        npc.b_setAnimState('Happy', 1.0)

    def refreshAnims(self, members, now):
        for npc in members:
            due = self.animRefresh.get(npc.doId)
            if due is not None and now >= due:
                del self.animRefresh[npc.doId]
                self.wakeAnim(npc)

    def stunSpot(self, npc=None):
        """The open ground in front of him (he faces -Y in his own frame)
        where this stunner stands: each keeps its own place there, so it
        walks up once and holds it as he turns, instead of chasing a new
        random point every moment."""
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        if boss is None or boss.isEmpty():
            return None
        node = getattr(boss, 'rotateNode', boss)
        if npc is None:
            offset = (random.uniform(-5, 5), random.uniform(*STUN_SPOT))
        else:
            offset = self.stunOffsets.get(npc.doId)
            if offset is None:
                offset = (random.uniform(-4, 4), random.uniform(*STUN_SPOT))
                self.stunOffsets[npc.doId] = offset
        return base.render.getRelativePoint(node, Point3(offset[0], -offset[1], 0))

    def goToStunSpot(self, npc, now):
        """A stunner heads for its place in front of the VP, where a player
        stands to throw under him, and keeps to it as he turns; while he is
        dizzy or the stunners rest it roams like the others."""
        if self.dizzy or now < self.stunRestUntil:
            self.roam(npc, now)
            return
        if npc.busy:
            return
        spot = self.stunSpot(npc)
        if spot is None:
            return
        self.syncPos(npc)
        pos = npc.getPos()
        flat = (Point3(pos[0], pos[1], 0) - Point3(spot[0], spot[1], 0)).length()
        if npc.walk is not None:
            # On the way: let it finish unless he has turned away meanwhile.
            goal = npc.walk[0][-1]
            if (Point3(goal[0], goal[1], 0) - Point3(spot[0], spot[1], 0)).length() > 6.0:
                npc.walk = None
            else:
                return
        if flat < STUN_SPOT_NEAR:
            # In place: squared up to the opening, ready for the doors.
            self.faceBoss(npc)
            self.nextRoam[npc.doId] = now + 0.5
            return
        if now < self.nextRoam.get(npc.doId, 0):
            return
        self.nextRoam[npc.doId] = now + 0.5
        if not self.walkToward(npc, pos, spot, ToontownGlobals.ToonForwardSpeed):
            self.roam(npc, now)

    def atStunSpot(self, npc):
        """In front of him and near enough to throw into the opening."""
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        client = base.cr.doId2do.get(npc.doId) if base else None
        if boss is None or boss.isEmpty() or client is None or client.isEmpty():
            return False
        rel = client.getPos(getattr(boss, 'rotateNode', boss))
        return abs(rel[0]) < 12 and -STUN_SPOT[1] - 8 < rel[1] < -10

    def markNear(self, members):
        """The VP aims his gears at the toons near him; a player's client
        reports being near, so the NPC toons report it here."""
        center = self.bossPos()
        near = getattr(self.boss, 'nearToons', None)
        if center is None or near is None:
            return
        for npc in members:
            pos = npc.getPos()
            close = math.hypot(pos[0] - center[0], pos[1] - center[1]) < NEAR_BOSS
            if close and npc.doId not in near:
                near.append(npc.doId)
            elif not close and npc.doId in near:
                near.remove(npc.doId)

    def faceBoss(self, npc):
        center = self.bossPos()
        if center is None:
            return
        pos = npc.getPos()
        wanted = -math.degrees(math.atan2(center[0] - pos[0], center[1] - pos[1]))
        if abs((wanted - npc.getH() + 180) % 360 - 180) > 8:
            npc.faceH = wanted

    def watchDizzy(self, now):
        dizzy = self.boss.attackCode == ToontownGlobals.BossCogDizzyNow
        if dizzy == self.dizzy:
            return
        self.dizzy = dizzy
        # Everyone moves at once: in to pie him, or back out as he gets up.
        self.nextRoam = {}
        if dizzy:
            self.count('vp dizzy spells')
        else:
            # Back on his feet; the stunners give him a moment.
            self.stunRestUntil = now + random.uniform(*STUN_REST)

    def walkToward(self, npc, pos, target, speed=None):
        """Start a walk to target, or part of the way there when no
        straight path goes all the way (the arena's ramps and levels).
        True when a walk started."""
        nav = getNav()
        for share in (1.0, 0.5, 0.25):
            mid = Point3(pos[0] + (target[0] - pos[0]) * share, pos[1] + (target[1] - pos[1]) * share, pos[2])
            path = nav.walkable(pos, mid)
            if path:
                self.startWalk(npc, path)
                if speed is not None:
                    npc.walk[1] = speed
                return True
        return False

    def closeIn(self, npc, now):
        """While the VP is dizzy every toon runs in close, from whichever
        side it is on, and throws at his body from there."""
        if not self.canRoam(npc, now):
            return
        center = self.bossPos()
        if center is None:
            return
        self.syncPos(npc)
        pos = npc.getPos()
        flat = math.hypot(pos[0] - center[0], pos[1] - center[1])
        self.nextRoam[npc.doId] = now + random.uniform(*PIE_ROAM_TIME)
        if DIZZY_RANGE[0] - 2 <= flat <= DIZZY_RANGE[1] + 3:
            self.faceBoss(npc)
            return
        nav = getNav()
        here = math.atan2(pos[1] - center[1], pos[0] - center[0])
        for i in range(6):
            angle = here + random.uniform(-0.6, 0.6)
            dist = random.uniform(*DIZZY_RANGE)
            target = Point3(center[0] + dist * math.cos(angle), center[1] + dist * math.sin(angle), pos[2])
            path = nav.walkable(pos, target)
            if path and not self.nearBoss(path, center):
                self.startWalk(npc, path)
                npc.walk[1] = ToontownGlobals.ToonForwardSpeed
                return
        # No straight way in from here: part of the way, then look again.
        angle = here
        dist = DIZZY_RANGE[1]
        target = Point3(center[0] + dist * math.cos(angle), center[1] + dist * math.sin(angle), pos[2])
        if self.walkToward(npc, pos, target, ToontownGlobals.ToonForwardSpeed):
            self.nextRoam[npc.doId] = now + 0.3
        else:
            self.nextRoam[npc.doId] = now + 0.5

    def cagePoint(self):
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        cage = getattr(boss, 'cage', None) if boss is not None and not boss.isEmpty() else None
        if cage is None or cage.isEmpty():
            return None
        return cage.getPos(base.render)

    def refillTrip(self, npc, now):
        """Out of pies, a toon runs over to the cage for more and touches it,
        as a player has to, then goes back to its job."""
        if not getattr(npc, 'refilling', False):
            return False
        if npc.walk is not None or npc.busy:
            return True
        cage = self.cagePoint()
        if cage is None:
            npc.refilling = False
            npc.asSender(self.boss.touchCage)
            return False
        self.syncPos(npc)
        pos = npc.getPos()
        if math.hypot(pos[0] - cage[0], pos[1] - cage[1]) < CAGE_NEAR:
            npc.refilling = False
            npc.asSender(self.boss.touchCage)
            self.count('vp cage refills')
            self.nextRoam[npc.doId] = now
            return False
        if now < self.nextRoam.get(npc.doId, 0):
            return True
        nav = getNav()
        for i in range(6):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(2.0, CAGE_NEAR - 2.0)
            target = Point3(cage[0] + dist * math.cos(angle), cage[1] + dist * math.sin(angle), pos[2])
            path = nav.walkable(pos, target)
            if path:
                self.startWalk(npc, path)
                npc.walk[1] = ToontownGlobals.ToonForwardSpeed
                self.nextRoam[npc.doId] = now + 0.5
                return True
        if self.walkToward(npc, pos, Point3(cage[0], cage[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
            self.nextRoam[npc.doId] = now + 0.5
            return True
        # No way over there from here: the pies come anyway.
        npc.refilling = False
        npc.asSender(self.boss.touchCage)
        return False

    def floorJob(self, npc, now):
        """A CFO floor toon (no crane): stomps a goon when one walks near,
        and goes for a treasure when hurt. True while it is on such a job."""
        if self.isStationed(npc) or npc.busy:
            return False
        base = getClientBuiltin('base')
        if base is None:
            return False
        boss = self.boss
        self.syncPos(npc)
        pos = npc.getPos()
        job = self.chasing.get(npc.doId)
        if job is not None:
            kind, doId = job
            if kind == 'goon':
                goon = boss.air.doId2do.get(doId) if hasattr(boss, 'air') else self.air.doId2do.get(doId)
                client = base.cr.doId2do.get(doId)
                if goon is None or client is None or client.isEmpty() or goon.state not in ('Walk', 'Battle'):
                    del self.chasing[npc.doId]
                    return False
                target = client.getPos(base.render)
                if math.hypot(pos[0] - target[0], pos[1] - target[1]) < GOON_STOMP_RANGE:
                    del self.chasing[npc.doId]
                    npc.walk = None
                    self.jump(npc)
                    npc.asSender(goon.requestStunned, 0)
                    self.count('cfo goon stomps')
                    self.nextRoam[npc.doId] = now + 1.5
                    return True
            else:
                treasure = boss.treasures.get(doId)
                if treasure is None:
                    del self.chasing[npc.doId]
                    return False
                target = treasure.pos
                if math.hypot(pos[0] - target[0], pos[1] - target[1]) < TREASURE_NEAR:
                    del self.chasing[npc.doId]
                    npc.walk = None
                    npc.asSender(treasure.requestGrab)
                    self.count('cfo treasures')
                    self.nextRoam[npc.doId] = now + 1.0
                    return True
            if npc.walk is not None and (Point3(npc.walk[0][-1]) - Point3(target[0], target[1], npc.walk[0][-1][2])).length() < 4.0:
                return True
            if now < self.nextRoam.get(npc.doId, 0):
                return True
            self.nextRoam[npc.doId] = now + 0.5
            if self.walkToward(npc, pos, Point3(target[0], target[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
                return True
            del self.chasing[npc.doId]
            return False
        if npc.walk is not None or now < self.nextRoam.get(npc.doId, 0):
            return False
        # Hurt: a treasure, when one lies about. Else a goon walking near.
        if npc.hp < npc.maxHp * TREASURE_BELOW and getattr(boss, 'treasures', None):
            nearest = min(boss.treasures.values(), key=lambda t: math.hypot(pos[0] - t.pos[0], pos[1] - t.pos[1]))
            self.chasing[npc.doId] = ('treasure', nearest.doId)
            return True
        goons = [g for g in (boss.goons or []) if g.state in ('Walk', 'Battle')]
        random.shuffle(goons)
        for goon in goons:
            client = base.cr.doId2do.get(goon.doId)
            if client is None or client.isEmpty():
                continue
            gpos = client.getPos(base.render)
            if math.hypot(pos[0] - gpos[0], pos[1] - gpos[1]) < 30 and random.random() < GOON_STOMP_CHANCE:
                self.chasing[npc.doId] = ('goon', goon.doId)
                return True
        return False

    def placeCourtroom(self, members):
        """The cannon round lands each toon wherever its own shot went, on
        the player's screen only; the district has no idea where. For the
        evidence round every NPC gets a spot of its own on the courtroom
        floor, spread out in front of the bench, the way the players land
        all over it."""
        nav = getNav()
        taken = []
        for npc in members:
            spot = None
            for i in range(12):
                x = random.uniform(*COURTROOM_X)
                y = random.uniform(*COURTROOM_Y)
                if any(math.hypot(x - t[0], y - t[1]) < 7 for t in taken):
                    continue
                z = nav.standZ(x, y, 1.0)
                if z is not None and abs(z) < 3.0:
                    spot = Point3(x, y, z)
                    break
            if spot is None:
                spot = Point3(random.uniform(-20, 20), random.uniform(10, 30), 0)
            taken.append(spot)
            npc.walk = None
            self.manager.teleportTo(npc, None, spot, h=random.uniform(-30, 30))
            self.wakeClient(npc)
            self.nextRoam[npc.doId] = globalClock.getFrameTime() + random.uniform(2.0, 5.0)

    def wakeClient(self, npc):
        """The cannon stops the toon's smoothing on the player's screen when
        it climbs in, and only a player's own toon gets it back: an NPC left
        that way ignores every walk the district sends and stands where the
        round left it. Smooth it again, out in the room."""
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(npc.doId) if base is not None and getattr(base, 'cr', None) else None
        if client is None or client.isEmpty():
            return
        from otp.local import ExecutionContext
        contexts = ExecutionContext.contexts
        if contexts is None:
            return
        # The smoothing task belongs to the client's task manager, with the
        # client's builtins, not to the district's.
        with contexts.use(contexts.client):
            if client.getParent() != base.render:
                client.wrtReparentTo(base.render)
            if not getattr(client, 'smoothStarted', 1):
                client.startSmooth()

    def witnessTrip(self, npc, now):
        """Out of evidence, a CJ toon runs to the witness stand, touches it
        and runs back to its spot. True while it is on the run."""
        if not getattr(npc, 'fetchingEvidence', False):
            return False
        if npc.walk is not None or npc.busy:
            return True
        self.syncPos(npc)
        pos = npc.getPos()
        if math.hypot(pos[0] - WITNESS_STAND[0], pos[1] - WITNESS_STAND[1]) < WITNESS_NEAR:
            npc.fetchingEvidence = False
            npc.asSender(self.boss.touchWitnessStand)
            self.count('cj witness refills')
            self.nextRoam[npc.doId] = now
            return False
        if now < self.nextRoam.get(npc.doId, 0):
            return True
        self.nextRoam[npc.doId] = now + 0.5
        if self.walkToward(npc, pos, Point3(WITNESS_STAND[0], WITNESS_STAND[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
            return True
        # No way over there from here: the evidence comes anyway.
        npc.fetchingEvidence = False
        npc.asSender(self.boss.touchWitnessStand)
        return False

    def isLawyerStunner(self, npc):
        if self.lawyerStunners is None:
            members = self.members()
            count = min(len(members), random.randint(*LAWYER_STUNNERS))
            self.lawyerStunners = set(n.doId for n in random.sample(members, count))
        return npc.doId in self.lawyerStunners

    def sideStep(self, npc, bossClient, now):
        """A gear aimed at this toon: it runs sideways out of the line."""
        base = getClientBuiltin('base')
        center = bossClient.getPos(base.render)
        self.syncPos(npc)
        pos = npc.getPos()
        away = Point3(pos[0] - center[0], pos[1] - center[1], 0)
        if away.length() < 0.1:
            return False
        away.normalize()
        side = Point3(-away[1], away[0], 0) * random.choice((-1, 1))
        nav = getNav()
        for sign in (1, -1):
            dist = random.uniform(*SIDESTEP)
            target = pos + side * (dist * sign)
            path = nav.walkable(pos, Point3(target[0], target[1], pos[2]))
            if path and not self.nearBoss(path, center):
                self.startWalk(npc, path)
                self.nextRoam[npc.doId] = now + 1.5
                return True
        return False

    def doorOpening(self):
        """Where the VP's front doors are open, the opening's spot (a pie
        thrown in there stuns him); None while they are shut."""
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        if boss is None or boss.isEmpty():
            return None
        door = getattr(boss, 'doorA', None)
        if door is None or door.state not in ('Opening', 'Opened'):
            return None
        axle = getattr(boss, 'axle', None)
        if axle is None or axle.isEmpty():
            return None
        return base.render.getRelativePoint(axle, Point3(0, -2.5, 2.75))

    def nearBoss(self, path, center):
        for point in path:
            if (Point3(point[0], point[1], 0) - Point3(center[0], center[1], 0)).length() < BOSS_CLEAR:
                return True
        return False

    # --- Being hit ---

    def takeHits(self, members):
        """The boss's attacks on the NPCs, where the player's game shows them:
        an NPC that touches him (or that he rolls over) is zapped as a
        player is; one in reach of a swat or his front is hit; and for an
        attack that can be jumped, the NPCs try to jump it, not always in
        time."""
        boss = self.boss
        if boss.getCurrentOrNextState() not in HIT_STATES:
            return
        base = getClientBuiltin('base')
        bossClient = base.cr.doId2do.get(boss.doId) if base is not None and getattr(base, 'cr', None) else None
        if bossClient is None or bossClient.isEmpty():
            return
        now = globalClock.getFrameTime()
        attack = (boss.attackCode, boss.attackAvId)
        newAttack = attack != self.lastAttack
        self.lastAttack = attack
        code, target = attack
        door = getattr(bossClient, 'doorA', None)
        doorOpen = door is not None and door.state in ('Opening', 'Opened')
        gearsOut = doorOpen and not self.doorWasOpen
        self.doorWasOpen = doorOpen
        for npc in members:
            client = base.cr.doId2do.get(npc.doId)
            if client is None or client.isEmpty() or now < self.safeUntil.get(npc.doId, 0):
                continue
            rel = client.getPos(bossClient.rotateNode)
            flat = math.hypot(rel[0], rel[1])
            hit = None
            if flat < BOSS_BODY:
                # Walked into him, or he rolled over it.
                hit = ToontownGlobals.BossCogElectricFence
            elif newAttack and code in (ToontownGlobals.BossCogSwatLeft, ToontownGlobals.BossCogSwatRight):
                side = 10 if code == ToontownGlobals.BossCogSwatLeft else -10
                if math.hypot(rel[0] - side, rel[1] + 5) < 12 and random.random() > DODGE_CHANCE:
                    hit = code
            elif newAttack and code == ToontownGlobals.BossCogFrontAttack:
                if math.hypot(rel[0], rel[1] + 25) < 14 and random.random() > DODGE_CHANCE:
                    hit = code
            elif newAttack and code in DIRECTED and target == npc.doId:
                # A gear aimed at it: most run sideways out of its way.
                if not (random.random() < SIDESTEP_CHANCE and self.sideStep(npc, bossClient, now)):
                    hit = code
            elif newAttack and code in JUMPABLE and not target:
                # Everyone in reach tries to jump it.
                self.jump(npc)
                if random.random() > JUMP_CHANCE:
                    hit = code
            elif gearsOut and rel[1] < -8 and abs(rel[0]) < 0.6 * -rel[1] + 3 and flat < STRAFE_REACH:
                # Gears out of his front: the toons standing in front of him
                # (the stunners, mostly) jump them, not always in time.
                self.jump(npc)
                if random.random() < STRAFE_HIT_CHANCE:
                    hit = ToontownGlobals.BossCogStrafeAttack
            if hit is None:
                continue
            self.safeUntil[npc.doId] = now + HIT_REST
            self.animRefresh[npc.doId] = now + ANIM_REFRESH_AFTER
            npc.walk = None
            pos = npc.getPos()
            npc.asSender(boss.zapToon, pos[0], pos[1], pos[2], npc.getH(), 0, 0, 0, 0, hit,
                         globalClockDelta.getFrameNetworkTime(bits=16))
            self.count('boss hits on npcs')
            if npc.hp <= 0:
                # Gone sad, out of the fight.
                npc.asSender(boss.avatarExit)
                self.manager.party.disband(npc)

    def jump(self, npc):
        npc.b_setAnimState('jump', 1.0)
        self.animRefresh[npc.doId] = globalClock.getFrameTime() + 1.2

    # --- Pies, for the look of it ---

    def bossPos(self):
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        if boss is None or boss.isEmpty():
            return None
        return boss.getPos(base.render) + Point3(0, 0, 8)

    def throwAt(self, npc, target, pieCode, hit=True):
        # The toss and the splat, as the thrower's client would send them. A
        # miss splats on the floor beside the target, so only the pies that
        # count are seen to land.
        if target is None:
            return
        self.syncPos(npc)
        if not hit:
            angle = random.uniform(0, 2 * math.pi)
            miss = random.uniform(*MISS_BY)
            floor = npc.getPos()[2]
            target = Point3(target[0] + miss * math.cos(angle), target[1] + miss * math.sin(angle), floor)
            pieCode = ToontownGlobals.PieCodeNotBossCog
        pos = npc.getPos()
        direction = target - pos
        h = -math.degrees(math.atan2(direction[0], direction[1]))
        npc.setH(h)
        sequence = self.pieSequence[npc.doId] = (self.pieSequence.get(npc.doId, 0) + 1) % 256
        now = globalClockDelta.getFrameNetworkTime(bits=32)
        npc.sendUpdate('tossPie', [pos[0], pos[1], pos[2], h, sequence, 60, 0, now])
        npc.sendUpdate('pieSplat', [target[0], target[1], target[2], sequence, pieCode, now + 30])

    def syncPos(self, npc):
        """Where the player's game shows the NPC. The boss fight's scenes move
        every toon about on the clients (into the elevator, onto the
        battle spots, down off the boss's platform); a walk or a throw from
        where the district last put the toon would start from somewhere
        else, high over the arena."""
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(npc.doId) if base is not None and getattr(base, 'cr', None) else None
        if client is None or client.isEmpty():
            return
        pos = client.getPos(base.render)
        if (pos - npc.getPos()).length() > 0.5:
            npc.setPosHpr(pos[0], pos[1], pos[2], client.getH(base.render), 0, 0)

    def makePieThrower(self, npc):
        if npc.numPies <= 0:
            npc.b_setPieType(4)
            npc.b_setNumPies(ToontownGlobals.FullPies)

    def healPlayer(self, npc):
        # Pies at a toon heal it; the player comes first, but only when really
        # hurt, and not from everyone at once.
        now = globalClock.getFrameTime()
        if now < self.nextHeal:
            return False
        for player in self.players():
            if player.maxHp and float(player.hp) / player.maxHp < HEAL_PLAYER_BELOW:
                self.nextHeal = now + HEAL_REST
                base = getClientBuiltin('base')
                client = base.cr.doId2do.get(player.doId) if base else None
                target = client.getPos(base.render) + Point3(0, 0, 3) if client is not None else None
                hit = random.random() < HEAL_HIT_CHANCE
                self.throwAt(npc, target, ToontownGlobals.PieCodeToon, hit)
                if hit:
                    npc.asSender(self.boss.hitToon, player.doId)
                return True
        return False

    # --- The VP ---

    def isStunner(self, npc):
        if self.stunners is None:
            members = self.members()
            count = min(len(members), random.randint(*STUNNERS))
            self.stunners = set(n.doId for n in random.sample(members, count))
        return npc.doId in self.stunners

    def playSBattleThree(self, npc):
        """The pie round, played as players play it: the stunners wait in
        front of him and throw into his underside when its doors open; once
        he is dizzy everyone pies his body from close up; nobody wastes
        pies on his body while he is on his feet (they do nothing then)."""
        boss = self.boss
        now = globalClock.getFrameTime()
        if npc.numPies <= 0:
            if not getattr(npc, 'refilling', False):
                npc.refilling = True
                npc.walk = None
                self.nextRoam[npc.doId] = now
            return
        if getattr(npc, 'refilling', False):
            return
        if self.healPlayer(npc):
            return
        target = self.bossPos()
        if target is None:
            return
        if self.dizzy:
            self.syncPos(npc)
            pos = npc.getPos()
            if math.hypot(pos[0] - target[0], pos[1] - target[1]) > DIZZY_RANGE[1] + 6:
                # Still running in; throws from close up.
                self.nextAction[npc.doId] = now + 0.5
                return
            hit = random.random() < DIZZY_HIT_CHANCE
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossCog, hit)
            if hit:
                npc.asSender(boss.hitBoss, 1)
                self.count('vp body hits')
            if npc.numPies != ToontownGlobals.FullPies:
                npc.setNumPies(npc.numPies - 1)
        elif self.isStunner(npc) and now >= self.stunRestUntil and self.atStunSpot(npc):
            opening = self.doorOpening()
            if opening is None:
                # Doors shut: nothing to throw at yet. Ready for them.
                self.nextAction[npc.doId] = now + 0.5
                return
            stun = random.random() < STUN_CHANCE
            self.throwAt(npc, opening, ToontownGlobals.PieCodeBossInsides, stun)
            self.count('vp stun tries')
            if random.random() < 0.5:
                self.stunOffsets.pop(npc.doId, None)
            if npc.numPies != ToontownGlobals.FullPies:
                npc.setNumPies(npc.numPies - 1)
            if stun:
                npc.asSender(boss.hitBossInsides)
                self.count('vp stuns')
                self.manager.stats['vp stunners'] = len(self.stunners)

    def playSNearVictory(self, npc):
        self.throwAt(npc, self.bossPos(), ToontownGlobals.PieCodeBossCog)
        if globalClock.getFrameTime() - self.stateSince[1] > 4:
            npc.asSender(self.boss.finalPieSplat)

    # --- The CFO ---

    def playMBattleThree(self, npc):
        boss = self.boss
        crane = None
        for c in boss.cranes or []:
            if c.avId == npc.doId:
                crane = c
        if crane is None:
            cranes = list(boss.cranes or [])
            free = [c for c in cranes if c.avId == 0]
            players = set(p.doId for p in self.players())
            playerOnCrane = [c for c in cranes if c.avId in players]
            if not playerOnCrane and globalClock.getFrameTime() - self.stateSince[1] < CRANE_FOR_PLAYER:
                # One crane stays free for the player a while; after that
                # an NPC takes it.
                free = free[:-1]
            if free:
                npc.asSender(random.choice(free).requestControl)
                onCranes = len([c for c in cranes if isNPCId(self.air, c.avId)])
                self.manager.stats['cfo npc cranes'] = max(self.manager.stats.get('cfo npc cranes', 0), onCranes)
                if globalClock.getFrameTime() - self.stateSince[1] < CRANE_FOR_PLAYER:
                    self.manager.stats['cfo npc cranes early'] = max(
                        self.manager.stats.get('cfo npc cranes early', 0), onCranes)
            return
        held = None
        for obj in list(boss.safes or []) + list(boss.goons or []):
            if getattr(obj, 'avId', 0) == npc.doId and obj.state in ('Grabbed',):
                held = obj
        if held is not None:
            if random.random() < CRANE_HIT_CHANCE:
                npc.asSender(held.hitBoss, random.uniform(0.3, 0.8))
                self.count('cfo crane hits')
            else:
                npc.asSender(held.requestDrop)
            return
        # A safe knocks his helmet off, or hurts him while he is dizzy; a
        # goon hurts him while his helmet is off.
        wantSafe = boss.heldObject is not None or boss.attackCode == ToontownGlobals.BossCogDizzy
        kinds = [list(boss.safes or []), list(boss.goons or [])]
        if not wantSafe:
            kinds.reverse()
        for objects in kinds:
            for obj in objects:
                if obj.state not in ('Grabbed', 'Off') and obj is not boss.heldObject:
                    npc.asSender(obj.requestGrab)
                    return

    # --- The CJ ---

    def playLBattleTwo(self, npc):
        # Fires toons into the jury chairs from a cannon.
        boss = self.boss
        cannons = list(getattr(boss, 'cannons', None) or [])
        if not cannons:
            return
        mine = [c for c in cannons if getattr(c, 'avId', 0) == npc.doId]
        if not mine:
            free = [c for c in cannons if getattr(c, 'avId', 0) in (0, None)]
            if free:
                npc.asSender(random.choice(free).requestEnter)
            return
        cannon = mine[0]
        chairs = [chair for chair in boss.chairs or [] if chair.state != 'ToonJuror']
        self.count('cj cannon shots')
        if chairs and random.random() < CANNON_HIT_CHANCE:
            npc.asSender(boss.hitChair, random.choice(chairs).index, cannon.index)

    def playLBattleThree(self, npc):
        boss = self.boss
        if npc.numPies <= 0:
            if not getattr(npc, 'fetchingEvidence', False):
                # Off to the witness stand for more (witnessTrip walks it).
                npc.fetchingEvidence = True
                npc.walk = None
                self.nextRoam[npc.doId] = globalClock.getFrameTime()
            return
        if getattr(npc, 'fetchingEvidence', False):
            return
        if self.healPlayer(npc):
            return
        lawyers = [l for l in getattr(boss, 'lawyers', None) or [] if not l.isDeleted() and not l.stunned]
        if lawyers and self.isLawyerStunner(npc):
            # The lawyer stunners' job: a pie at a lawyer stops its evidence
            # landing on the cogs' pan, and with every lawyer stunned the
            # toons' evidence weighs more. With all of them down they throw
            # at the scale like everyone else.
            lawyer = random.choice(lawyers)
            hit = random.random() < LAWYER_HIT_CHANCE
            where = self.lawyerPos(lawyer)
            if where is not None:
                self.throwAt(npc, where, ToontownGlobals.PieCodeLawyer, hit)
            if hit:
                npc.asSender(lawyer.hitByToon)
                self.count('cj lawyer stuns')
            if npc.numPies != ToontownGlobals.FullPies:
                npc.setNumPies(npc.numPies - 1)
            return
        target = self.bossPos()
        # Evidence on the scale's pan. (Nobody stuns the CJ.)
        hit = random.random() < EVIDENCE_HIT_CHANCE
        self.throwAt(npc, target, ToontownGlobals.PieCodeDefensePan, hit)
        if npc.numPies != ToontownGlobals.FullPies:
            npc.setNumPies(npc.numPies - 1)
        if hit:
            npc.asSender(boss.hitBoss, 1)
            self.count('cj evidence hits')

    def lawyerPos(self, lawyer):
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(lawyer.doId) if base else None
        if client is None or client.isEmpty():
            return None
        return client.getPos(base.render) + Point3(0, 0, 3)

    def playLNearVictory(self, npc):
        self.playSNearVictory(npc)

    # --- The CEO ---

    def playCBattleTwo(self, npc):
        # Runs plates from the belts to the hungry diners.
        boss = self.boss
        if not boss.toonFoodStatus.get(npc.doId):
            self.foodNum += 1
            npc.asSender(boss.requestGetFood, random.randrange(2), 0, self.foodNum)
            return
        for table in boss.tables:
            for chairIndex in range(table.numDiners):
                if table.getDinerStatus(chairIndex) in (table.HUNGRY, table.ANGRY):
                    npc.asSender(boss.requestServeFood, table.index, chairIndex)
                    return

    def playCBattleFour(self, npc):
        boss = self.boss
        if self.healPlayer(npc):
            return
        if npc.hp < npc.maxHp * 0.5:
            self.foodNum += 1
            npc.asSender(boss.requestGetToonup, random.randrange(2), random.randrange(3), self.foodNum)
            return
        if self.playGolf(npc):
            return
        self.playPitcher(npc)

    def playPitcher(self, npc):
        # The banquet tables' water pitchers are what hurt him; one toon to
        # a table. One stays free for the player a while.
        boss = self.boss
        tables = list(boss.tables or [])
        mine = [t for t in tables if t.avId == npc.doId]
        if not mine:
            if len([t for t in tables if isNPCId(self.air, t.avId)]) >= PITCHERS:
                return
            free = [t for t in tables if t.avId == 0 and t.state == 'Free']
            players = set(p.doId for p in self.players())
            if not [t for t in tables if t.avId in players] and \
                    globalClock.getFrameTime() - self.stateSince[1] < CRANE_FOR_PLAYER:
                free = free[:-1]
            if free:
                npc.asSender(random.choice(free).requestControl)
            return
        self.nextAction[npc.doId] = globalClock.getFrameTime() + random.uniform(*PITCHER_TIME)
        self.count('ceo pitcher shots')
        if random.random() < PITCHER_HIT_CHANCE:
            npc.asSender(boss.hitBoss, random.randint(1, 3))

    def playGolf(self, npc):
        # A few take a golf spot, and slow him down with golf balls.
        boss = self.boss
        spots = list(getattr(boss, 'golfSpots', None) or [])
        mine = [spot for spot in spots if spot.avId == npc.doId]
        if not mine:
            golfers = [spot for spot in spots if isNPCId(self.air, spot.avId)]
            free = [spot for spot in spots if spot.avId == 0 and spot.state != 'Off']
            if len(golfers) < GOLFERS and free and random.random() < 0.5:
                npc.asSender(random.choice(free).requestControl)
                return bool([spot for spot in spots if spot.avId == npc.doId])
            return False
        now = globalClock.getFrameTime()
        self.nextAction[npc.doId] = now + random.uniform(*GOLF_TIME)
        self.count('ceo golf swings')
        if random.random() < GOLF_HIT_CHANCE:
            npc.asSender(boss.ballHitBoss, random.randint(2, 5))
        return True
