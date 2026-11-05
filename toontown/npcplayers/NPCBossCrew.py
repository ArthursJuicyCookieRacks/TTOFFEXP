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
from panda3d.core import Vec3, Point3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.npcplayers import NPCBanquetOperator, NPCCraneOperator
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
PITCHER_TIME_EVEN = (2.5, 4.0)
PITCHER_TIME_BEHIND = (1.4, 2.4)
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
# How near a crane, pitcher or golf spot an NPC walks before it takes it.
STATION_REACH = 5.0
# At a crane: how near the magnet comes to a safe or goon to pick it up, and
# how near the CFO's head a swinging magnet lets go (wide: far off, a miss).
CRANE_GRAB_REACH = 4.0
CRANE_LET_GO = 16.0
# How far ahead of the arm the swinging safe is let go (ft).
CRANE_RELEASE_AHEAD = 1.5
CRANE_HOLD_MAX = 40.0
# How near his head the arm's full reach must come before a swing.
CRANE_SWING_RANGE = 30.0
# How far along a belt a plate is out of the wall it comes from.
BELT_IN_WALL = 12.0
CRANE_LET_GO_WIDE = 30.0
# The CFO's floor toons: they jump on the goons' heads to stun them for the
# craners, and pick up the treasures the stunned goons leave when hurt.
GOON_STOMP_RANGE = 5.0
# A goon walks out of the CFO for this long before anyone goes for it; a
# jump takes GOON_JUMP_TIME, and lands on its head within GOON_HEAD_REACH.
GOON_OUT_TIME = 3.0
GOON_JUMP_TIME = 0.5
GOON_HEAD_REACH = 2.0
GOON_STOMP_CHANCE = 0.6
TREASURE_BELOW = 0.6
TREASURE_NEAR = 4.0
# The CJ: how likely a toon fired from a cannon lands in a chair.
CANNON_HIT_CHANCE = 0.3
# The CEO's banquet: how close a waiter must come to a plate or a chair,
# and how far beside a belt or chair it walks to.
WAITER_REACH = 7.0
WAITER_BESIDE = 6.5
# Where a waiter stands to serve: just outside the chair.
DINER_BESIDE = 3.5
# Waiters on a belt keep this far apart.
WAITER_SPACING = 6.0
# A player this near a table is working it.
WAITER_TABLE_NEAR = 16.0
# The CEO: how many NPCs take a golf spot, and how likely a ball hits him.
GOLFERS = 2
GOLF_HIT_CHANCE = 0.45
# Between goes the NPCs move about the arena on their own, as players do,
# rather than following the player: how often, and how far from the boss.
# The boss's damage is mostly the players' doing: the NPC toons help with
# about 30% of it (a new share each fight, a little more or less), never
# carrying the fight. While behind their share they aim better; once at it
# their hits stop counting (the pie or the swing misses).
NPC_SHARE = (0.30, 0.04, 0.22, 0.38)
# The Chief Justice's scale needs ~1350 evidence from a group of eight, so
# with one player it dragged on (31 minutes of scale, 52 in all). With NPCs
# along (Arthur): they do about half of it, and every toon's evidence weighs
# CJ_WEIGHT times as much.
CJ_NPC_SHARE = (0.50, 0.04, 0.44, 0.56)
CJ_WEIGHT = 2
# Early on, before anyone has done much, they may do this much of his
# health on their own.
NPC_SHARE_SLACK = 0.04
# Past their share, at least this many of their hits still count.
SHARE_FLOOR = 0.25
# No headway for this long: the NPCs may take this much more of a share.
STALL_TIME = 150.0
STALL_EXTRA_SHARE = 0.05
# Off by this much from where the player sees it, an NPC standing about is
# moved (on the district) to there.
SYNC_GAP = 4.0
# How long after a boss state change the clients take to place the toons.
RESYNC_DELAY = 1.0
# A walking NPC this far from where the player's game shows it was put there.
PLACED_GAP = 25.0
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
        self.resyncAt = None
        self.progress = []
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
        self.waiterTarget = {}
        self.waiterSide = {}
        self.waiterTable = {}
        self.waiterSpot = {}
        self.unreachable = {}
        self.stomping = {}
        self.craneWork = {}
        if self.dept == 'm':
            NPCCraneOperator.install(self.air)
        if self.dept == 'c':
            NPCBanquetOperator.install(self.air)
        self.goonOutSince = {}
        share = CJ_NPC_SHARE if self.dept == 'l' else NPC_SHARE
        self.npcShare = min(max(random.gauss(share[0], share[1]), share[2]), share[3])
        if self.dept == 'l':
            self.hookWeights()
        self.dealt = {'npc': 0, 'player': 0}
        self.hookDamage()
        self.taskName = 'npcBossCrew-%d' % boss.doId
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    # --- Sharing the work ---

    def hookDamage(self):
        # Who took his health: every boss's hits end in b_setBossDamage, sent
        # by the toon that made them.
        boss = self.boss
        orig = boss.b_setBossDamage
        crew = self

        def b_setBossDamage(bossDamage, *rest):
            before = getattr(boss, 'bossDamage', 0) or 0
            result = orig(bossDamage, *rest)
            delta = (getattr(boss, 'bossDamage', 0) or 0) - before
            # (The CJ's scale jumps to its starting weight in his scenes.)
            if 0 < delta <= 0.15 * crew.maxDamage():
                avId = crew.air.getAvatarIdFromSender()
                if avId in boss.involvedToons:
                    crew.dealt['npc' if isNPCId(crew.air, avId) else 'player'] += delta
            return result

        boss.b_setBossDamage = b_setBossDamage

    def hookWeights(self):
        # Each toon's evidence weight (1 plus its cannon's jurors) is set as
        # the scale round starts.
        boss = self.boss
        orig = boss.calculateWeightPerToon

        def calculateWeightPerToon(*args):
            result = orig(*args)
            for avId in list(boss.weightPerToon.keys()):
                boss.weightPerToon[avId] = boss.weightPerToon[avId] * CJ_WEIGHT
            return result

        boss.calculateWeightPerToon = calculateWeightPerToon

    def maxDamage(self):
        return float(getattr(self.boss, 'bossMaxDamage', 0) or 100)

    def share(self):
        total = self.dealt['npc'] + self.dealt['player']
        return self.dealt['npc'] / total if total else 0.0

    def stalled(self):
        """The fight going nowhere: his health no lower than a while ago (the
        CJ's scale tips back, the player falls behind). The NPCs then help
        past their share a little, so a fight can always be won."""
        now = globalClock.getFrameTime()
        damage = getattr(self.boss, 'bossDamage', 0) or 0
        marks = self.progress
        if not marks or now - marks[-1][0] > 5.0:
            marks.append((now, damage))
            while len(marks) > 2 and now - marks[1][0] > STALL_TIME:
                marks.pop(0)
        old = marks[0]
        return now - old[0] >= STALL_TIME * 0.9 and damage <= old[1] + 0.02 * self.maxDamage()

    def mayHurt(self):
        """Whether this NPC hit may count: the NPCs keep pace with the
        player's damage at their share (Arthur: never stop helping). Behind
        it, every hit counts; ahead of it they ease off smoothly, down to
        SHARE_FLOOR of their hits, never none."""
        share = self.npcShare
        if self.stalled():
            share = min(0.62 if self.dept == 'l' else 0.5, share + STALL_EXTRA_SHARE)
        allowed = share / (1.0 - share) * self.dealt['player'] + NPC_SHARE_SLACK * self.maxDamage()
        npc = self.dealt['npc']
        if npc < allowed:
            return True
        # How far past it, in boss health: a tenth of his health over
        # leaves only the floor.
        over = (npc - allowed) / (0.10 * self.maxDamage())
        return random.random() < max(SHARE_FLOOR, 1.0 - over * (1.0 - SHARE_FLOOR))

    def aim(self, chance):
        # Behind their share they hit more often; past it, less.
        share = self.share()
        if share < self.npcShare - 0.10:
            return min(0.95, chance * 2.2)
        if share < self.npcShare - 0.05:
            return min(0.95, chance * 1.5)
        if share > self.npcShare + 0.03:
            return chance * 0.6
        return chance

    def hits(self, chance):
        return random.random() < self.aim(chance) and self.mayHurt()

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
            NPCCraneOperator.npcIds.add(npc.doId)
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
            self.resyncAt = now + RESYNC_DELAY
            self.progress = []
            for npc in self.members():
                npc.walk = None
        try:
            members = self.members()
            if self.resyncAt is not None:
                if now < self.resyncAt:
                    # The clients are still putting the toons where this
                    # stretch begins: nobody sets off from the old places.
                    return Task.cont
                self.resyncAt = None
                for npc in members:
                    # From where the player's game shows each toon, told to
                    # every client, so no walk starts from a stale place.
                    npc.walk = None
                    self.syncPos(npc, 0.0)
                    pos = npc.getPos()
                    npc.moveTo(pos[0], pos[1], pos[2], npc.getH())
                    npc.stopMoving()
            for npc in members:
                if npc.walk is None:
                    # The boss's scenes move the toons on the clients only;
                    # catch up, or the next step from the old place (being
                    # kept apart, a hit) shows the toon jumping back there.
                    self.syncPos(npc, SYNC_GAP)
                elif self.clientGap(npc) > PLACED_GAP:
                    # Far from where it walks: the player's game has put it
                    # somewhere (the CJ's cannons line up once the player
                    # reads the witness's words). Stay there, not walk on
                    # from the old place.
                    npc.walk = None
                    self.syncPos(npc, 0.0)
                    pos = npc.getPos()
                    npc.moveTo(pos[0], pos[1], pos[2], npc.getH())
                    npc.stopMoving()
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
                        if not self.craneJob(npc, now) and not self.floorJob(npc, now):
                            self.roam(npc, now)
                    elif self.dept == 'l' and state == 'BattleThree':
                        if not self.witnessTrip(npc, now):
                            self.roam(npc, now)
                    elif self.dept == 'c' and state == 'BattleTwo':
                        if not self.waiterJob(npc, now):
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
                share = self.share()
                if share < self.npcShare - 0.08:
                    # Well behind their part: they keep at it harder.
                    pace = (pace[0] * 0.6, pace[1] * 0.6)
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
        # Round the tables, belts and walls in the way.
        path = nav.findPath(pos, Point3(target[0], target[1], pos[2]))
        if path:
            self.count('boss walks round')
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
                goon = self.air.doId2do.get(doId)
                client = base.cr.doId2do.get(doId)
                if goon is None or client is None or client.isEmpty() or goon.state not in ('Walk', 'Battle'):
                    del self.chasing[npc.doId]
                    self.stomping.pop(npc.doId, None)
                    return False
                gpos = client.getPos(base.render)
                stomp = self.stomping.get(npc.doId)
                if stomp is not None:
                    # In the air: did it come down on the goon's head (as
                    # the player's game draws them both)?
                    if now < stomp:
                        return True
                    del self.stomping[npc.doId]
                    del self.chasing[npc.doId]
                    me = base.cr.doId2do.get(npc.doId)
                    mpos = me.getPos(base.render) if me is not None else pos
                    if math.hypot(mpos[0] - gpos[0], mpos[1] - gpos[1]) < GOON_HEAD_REACH:
                        npc.asSender(goon.requestStunned, 0)
                        self.count('cfo goon stomps')
                    else:
                        self.count('cfo goon stomp misses')
                    self.nextRoam[npc.doId] = now + 1.0
                    return True
                fwd = base.render.getRelativeVector(client, Point3(0, 1, 0))
                fwd.setZ(0)
                if fwd.length() > 0.01:
                    fwd.normalize()
                if math.hypot(pos[0] - gpos[0], pos[1] - gpos[1]) < GOON_STOMP_RANGE:
                    # A jump onto where its head will be, with a toon's aim.
                    lead = getattr(goon, 'velocity', 4) * GOON_JUMP_TIME if goon.state == 'Walk' else 0.0
                    land = Point3(gpos[0] + fwd[0] * lead + random.uniform(-1.2, 1.2),
                                  gpos[1] + fwd[1] * lead + random.uniform(-1.2, 1.2), pos[2])
                    self.jump(npc)
                    dist = math.hypot(land[0] - pos[0], land[1] - pos[1])
                    self.startWalk(npc, [Point3(pos), land])
                    npc.walk[1] = max(dist / GOON_JUMP_TIME, 1.0)
                    self.stomping[npc.doId] = now + GOON_JUMP_TIME
                    return True
                # Up beside it (out of its light), a step ahead of it.
                side = Point3(-fwd[1], fwd[0], 0)
                if (pos[0] - gpos[0]) * side[0] + (pos[1] - gpos[1]) * side[1] < 0:
                    side = -side
                target = Point3(gpos[0] + fwd[0] * 2.0 + side[0] * 3.0, gpos[1] + fwd[1] * 2.0 + side[1] * 3.0, pos[2])
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
        for g in boss.goons or []:
            if g.state in ('Walk', 'Battle'):
                self.goonOutSince.setdefault(g.doId, now)
            else:
                self.goonOutSince.pop(g.doId, None)
        # A goon that has come out a little way (not one still leaving the
        # CFO), and that no one else is after.
        taken = set(job[1] for other, job in self.chasing.items() if other != npc.doId)
        goons = [g for g in (boss.goons or []) if g.state in ('Walk', 'Battle') and g.doId not in taken
                 and now - self.goonOutSince.get(g.doId, now) >= GOON_OUT_TIME]
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
        """Out of evidence, a CJ toon walks to the witness stand, touches it
        and walks back to where it was fighting (Arthur: no evidence from
        afar). True while it is on the way there or back."""
        returning = getattr(npc, 'returnSpot', None)
        if npc.numPies <= 0 and not getattr(npc, 'fetchingEvidence', False) and returning is None \
                and not npc.busy:
            # Out: straight off towards the stand, not at its next throw.
            self.startFetch(npc)
        if not getattr(npc, 'fetchingEvidence', False) and returning is None:
            return False
        if npc.walk is not None or npc.busy:
            return True
        self.syncPos(npc)
        pos = npc.getPos()
        if returning is not None:
            if math.hypot(pos[0] - returning[0], pos[1] - returning[1]) < 6.0:
                self.count('cj back to fight')
                npc.returnSpot = None
                self.faceBoss(npc)
                # Back in place: straight on with the fight.
                self.nextAction[npc.doId] = min(self.nextAction.get(npc.doId, now), now + random.uniform(0.3, 1.0))
                return False
            if now < self.nextRoam.get(npc.doId, 0):
                return True
            self.nextRoam[npc.doId] = now + 0.5
            if self.walkToward(npc, pos, Point3(returning[0], returning[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
                return True
            # No way back from here: it fights from where it stands.
            self.count('cj no way back')
            npc.returnSpot = None
            self.faceBoss(npc)
            self.nextAction[npc.doId] = min(self.nextAction.get(npc.doId, now), now + random.uniform(0.3, 1.0))
            return False
        if math.hypot(pos[0] - WITNESS_STAND[0], pos[1] - WITNESS_STAND[1]) < WITNESS_NEAR:
            npc.fetchingEvidence = False
            npc.asSender(self.boss.touchWitnessStand)
            self.count('cj witness refills')
            spot = getattr(npc, 'fightSpot', None)
            self.notify.info('NPC %d touched the witness stand at (%.0f, %.0f), %.0f s after leaving (%s)' % (
                npc.doId, pos[0], pos[1], now - getattr(npc, 'fetchSince', now),
                '%.0f, %.0f' % (spot[0], spot[1]) if spot is not None else '?'))
            npc.returnSpot = spot
            self.nextRoam[npc.doId] = now + random.uniform(0.3, 0.8)
            return True
        if now < self.nextRoam.get(npc.doId, 0):
            return True
        self.nextRoam[npc.doId] = now + 0.5
        if self.walkToward(npc, pos, Point3(WITNESS_STAND[0], WITNESS_STAND[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
            return True
        # No straight way over from here: a step to one side and on towards
        # the stand, else it moves about (roam) and tries again; never any
        # evidence without touching the stand.
        self.count('cj witness detours')
        nav = getNav()
        toward = math.atan2(WITNESS_STAND[1] - pos[1], WITNESS_STAND[0] - pos[0])
        for turn in (30, -30, 60, -60, 90, -90):
            angle = toward + math.radians(turn)
            dist = random.uniform(12.0, 22.0)
            target = Point3(pos[0] + math.cos(angle) * dist, pos[1] + math.sin(angle) * dist, pos[2])
            path = nav.walkable(pos, target)
            if path:
                self.startWalk(npc, path)
                npc.walk[1] = ToontownGlobals.ToonForwardSpeed
                return True
        return False

    def startFetch(self, npc):
        npc.fetchingEvidence = True
        npc.returnSpot = None
        self.syncPos(npc)
        npc.fightSpot = npc.getPos()
        npc.fetchSince = globalClock.getFrameTime()
        npc.walk = None
        self.nextRoam[npc.doId] = globalClock.getFrameTime()

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
            # The zap puts the toon where it is said to be on every client:
            # from where the player sees it, or it would jump there (the
            # district's place for it can be a scene or a walk behind).
            self.syncPos(npc)
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

    def stationPoint(self, obj):
        """Where a toon stands to use a crane, a banquet table's pitcher or a
        golf spot, from the player's game."""
        base = getClientBuiltin('base')
        do = base.cr.doId2do.get(obj.doId)
        if do is None:
            return None
        for name in ('controls', 'waterPitcherNode', 'root'):
            node = getattr(do, name, None)
            if node is not None and not node.isEmpty():
                return node.getPos(base.render)
        return None

    def pickStation(self, npc, free):
        """The free station this NPC heads for: the one it picked before
        while that is still free, else a new one."""
        goal = getattr(npc, 'stationGoal', None)
        for obj in free:
            if obj.doId == goal:
                return obj
        obj = random.choice(free)
        npc.stationGoal = obj.doId
        return obj

    def approach(self, npc, obj):
        """A player walks up to a crane (a pitcher, a golf spot) before
        taking it; true once the NPC is there. (Taking one from across the
        room drew it as a jump onto the controls.)"""
        if npc.walk is not None:
            return False
        spot = self.stationPoint(obj)
        if spot is None:
            return True
        self.syncPos(npc)
        pos = npc.getPos()
        if math.hypot(spot[0] - pos[0], spot[1] - pos[1]) <= STATION_REACH:
            return True
        if self.walkToward(npc, pos, Point3(spot[0], spot[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
            return False
        # No walk there from here (blocked all ways): takes it from here.
        return True

    def clientGap(self, npc):
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(npc.doId) if base is not None and getattr(base, 'cr', None) else None
        if client is None or client.isEmpty():
            return 0.0
        return (client.getPos(base.render) - npc.getPos()).length()

    def syncPos(self, npc, gap=0.5):
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
        if (pos - npc.getPos()).length() > gap:
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
            hit = self.hits(DIZZY_HIT_CHANCE)
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
                target = self.pickStation(npc, free)
                if not self.approach(npc, target):
                    return
                npc.asSender(target.requestControl)
                onCranes = len([c for c in cranes if isNPCId(self.air, c.avId)])
                self.manager.stats['cfo npc cranes'] = max(self.manager.stats.get('cfo npc cranes', 0), onCranes)
                if globalClock.getFrameTime() - self.stateSince[1] < CRANE_FOR_PLAYER:
                    self.manager.stats['cfo npc cranes early'] = max(
                        self.manager.stats.get('cfo npc cranes early', 0), onCranes)
            return
        # At the controls: craneJob works the crane, every tick.
        return

    def craneJob(self, npc, now):
        """An NPC at a crane works it as a player does (NPCCraneOperator
        moves it on the player's screen): swings the magnet over a safe or
        a goon, picks it up, swings it at the CFO and lets go; the flight
        and the hit are the game's own. True while at a crane."""
        boss = self.boss
        crane = None
        for c in boss.cranes or []:
            if c.avId == npc.doId:
                crane = c
        if crane is None:
            NPCCraneOperator.targets.pop(getattr(npc, 'craneDoId', None), None)
            return False
        npc.craneDoId = crane.doId
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(crane.doId) if base else None
        if client is None or getattr(client, 'npcWorked', None) != npc.doId:
            return True
        work = self.craneWork.setdefault(npc.doId, {'next': 0, 'last': None})
        magnet = NPCCraneOperator.magnetPos(client)
        if now - work.get('logged', 0) > 10:
            work['logged'] = now
            self.notify.info('crane %d (NPC %d): magnet (%.1f, %.1f, %.1f), arm y %.1f h %.1f, target %s, after %s (gap %s), next in %.1f' % (
                crane.doId, npc.doId, magnet[0], magnet[1], magnet[2], client.crane.getY(), client.arm.getH(),
                NPCCraneOperator.targets.get(crane.doId), work.get('obj'), work.get('gap'), work['next'] - now))
        held = None
        for obj in list(boss.safes or []) + list(boss.goons or []):
            if getattr(obj, 'avId', 0) == npc.doId and obj.state == 'Grabbed':
                held = obj
        if held is not None:
            # His head (where a safe has to land), as the player's screen
            # has it; his body is far bigger than his middle.
            bossClient = base.cr.doId2do.get(boss.doId)
            target = getattr(bossClient, 'headTarget', None)
            head = target.getPos(base.render) if target is not None and not target.isEmpty() else self.bossPos()
            if now - work.get('headLogged', 0) > 30:
                work['headLogged'] = now
                self.notify.info('CFO head at (%.1f, %.1f, %.1f), middle %s' % (head[0], head[1], head[2], self.bossPos()))
            if head is None:
                return True
            if work.get('heldObj') != held.doId:
                work['heldObj'] = held.doId
                work['heldSince'] = now
                work['closest'] = None
                work['closestAt'] = now
            if held in (boss.goons or []) and boss.heldObject is not None:
                # A goon does nothing to a helmet: put it down, as a player
                # would, and go for a safe.
                npc.asSender(held.requestDrop)
                self.count('cfo goons put down')
                work['next'] = now + random.uniform(0.5, 1.2)
                return True
            # A player's swing: draw the arm back facing him, let the cable
            # settle, then slide out at full speed and let go as it stops, so
            # the safe flies on into him. Whether it hits is the swing's.
            helmetOff = boss.heldObject is not None and held in (boss.safes or [])
            if work.get('wideFor') != held.doId:
                # Decided once per swing: the share is a chance now.
                work['wideFor'] = held.doId
                work['wide'] = not self.mayHurt()
                work['phase'] = 'back'
                work['aimH'] = None
            wide = not helmetOff and work['wide']
            h = self.headingTo(client, head)
            if work['aimH'] is None:
                err = random.gauss(0, 2.5)
                if wide:
                    err += random.choice((-1, 1)) * random.uniform(12, 22)
                work['aimH'] = err
            aimH = max(min(h + work['aimH'], client.armMaxH), client.armMinH)
            phase = work['phase']
            if phase == 'back':
                NPCCraneOperator.targets[crane.doId] = (client.craneMinY, aimH)
                if abs(client.arm.getH() - aimH) < 2.5 and client.crane.getY() < client.craneMinY + 0.6:
                    work['phase'] = 'settle'
                    work['until'] = now + random.uniform(0.6, 1.2)
            elif phase == 'settle':
                # Waits, as a player does, for him to come near enough that
                # the arm's full reach swings the safe into him.
                hr = math.radians(aimH)
                tip = base.render.getRelativePoint(client.arm.getParent(), Point3(
                    -client.craneMaxY * math.sin(hr), client.craneMaxY * math.cos(hr), 0))
                near = math.hypot(tip[0] - head[0], tip[1] - head[1])
                work['near'] = near
                if now - work.get('nearLogged', 0) > 8:
                    work['nearLogged'] = now
                    self.notify.info('NPC %d waits on crane %d: full reach %.0f ft from him' % (npc.doId, crane.doId, near))
                if now >= work['until'] and near <= CRANE_SWING_RANGE:
                    work['phase'] = 'swing'
                    work['until'] = now + random.uniform(0.0, 0.25)
                    work['outAt'] = None
                    work['lastOff'] = None
                    work.pop('stopAt', None)
            elif phase == 'swing':
                NPCCraneOperator.targets[crane.doId] = (client.craneMaxY, aimH)
                d = math.hypot(magnet[0] - head[0], magnet[1] - head[1])
                if d < CRANE_LET_GO and work.get('outAt') is None:
                    # Close while still sliding out: let go on the move.
                    work['outAt'] = now
                if client.crane.getY() >= client.craneMaxY - 0.5 and work.get('outAt') is None:
                    # The arm's out; the safe still swings on below it. Let go
                    # as it swings through under the arm and on forwards (its
                    # fastest), as a player times a throw.
                    slider = client.crane.getPos(base.render)
                    ahead = base.render.getRelativeVector(client.arm, Vec3(0, 1, 0))
                    off = (magnet[0] - slider[0]) * ahead[0] + (magnet[1] - slider[1]) * ahead[1]
                    lastOff = work.get('lastOff')
                    work['lastOff'] = off
                    work.setdefault('stopAt', now)
                    if (lastOff is not None and off > lastOff and off >= CRANE_RELEASE_AHEAD) or now - work['stopAt'] > 3.0:
                        work['outAt'] = now
                if work.get('outAt') is not None:
                    if now >= work['outAt']:
                        npc.asSender(held.requestDrop)
                        self.count('cfo crane swings' if not wide else 'cfo crane wide swings')
                        self.notify.info('NPC %d swings %s at the CFO from crane %d (%s), %.0f ft off (reach end %.0f ft off, swing %.1f ft ahead)' % (
                            npc.doId, held.doId, crane.doId, 'wide' if wide else 'aimed',
                            math.hypot(magnet[0] - head[0], magnet[1] - head[1]), work.get('near', -1), work.get('lastOff') or 0))
                        work['wideFor'] = None
                        work['heldObj'] = None
                        work['next'] = now + random.uniform(1.0, 2.5)
                        return True
            if now - work['heldSince'] > CRANE_HOLD_MAX:
                npc.asSender(held.requestDrop)
                self.count('cfo crane give-ups')
                work['wideFor'] = None
                work['heldObj'] = None
                work['next'] = now + random.uniform(1.0, 2.5)
            return True
        work['last'] = None
        if now < work['next']:
            return True
        # A safe knocks his helmet off, or hurts him while he is dizzy; a
        # goon hurts him while his helmet is off.
        wantSafe = boss.heldObject is not None or boss.attackCode == ToontownGlobals.BossCogDizzy
        kinds = [list(boss.safes or []), list(boss.goons or [])]
        if not wantSafe:
            kinds.reverse()
        taken = set(w.get('obj') for k, w in self.craneWork.items() if k != npc.doId)
        best = None
        for rank, objects in enumerate(kinds):
            for obj in objects:
                if obj.state in ('Grabbed', 'Off') or obj is boss.heldObject or obj.doId in taken:
                    continue
                oc = base.cr.doId2do.get(obj.doId)
                if oc is None or oc.isEmpty():
                    continue
                where = oc.getPos(base.render)
                reach = NPCCraneOperator.reachFor(client, where)
                if reach is None:
                    continue
                d = math.hypot(where[0] - magnet[0], where[1] - magnet[1]) + rank * 60
                if best is None or d < best[0]:
                    best = (d, obj, oc, reach)
        if best is None:
            work['obj'] = None
            NPCCraneOperator.targets[crane.doId] = (client.initialArmPosition[1], 0)
            return True
        d, obj, oc, reach = best
        work['obj'] = obj.doId
        NPCCraneOperator.targets[crane.doId] = reach
        where = oc.getPos(base.render)
        work['gap'] = math.hypot(where[0] - magnet[0], where[1] - magnet[1])
        if math.hypot(where[0] - magnet[0], where[1] - magnet[1]) < CRANE_GRAB_REACH:
            # The magnet over it, as it comes down onto it.
            npc.asSender(obj.requestGrab)
            if obj.state == 'Grabbed' and obj.avId == npc.doId:
                self.count('cfo crane grabs')
            work['next'] = now + random.uniform(0.3, 0.8)
        return True

    def headingTo(self, client, point):
        base = getClientBuiltin('base')
        p = client.arm.getParent().getRelativePoint(base.render, point)
        return math.degrees(math.atan2(-p[0], p[1]))

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
            if not getattr(npc, 'fetchingEvidence', False) and getattr(npc, 'returnSpot', None) is None:
                # Off to the witness stand for more (witnessTrip walks it).
                self.startFetch(npc)
            return
        if getattr(npc, 'fetchingEvidence', False) or getattr(npc, 'returnSpot', None) is not None:
            return
        if self.healPlayer(npc):
            return
        lawyers = [l for l in getattr(boss, 'lawyers', None) or [] if not l.isDeleted() and not l.stunned]
        if lawyers and (self.isLawyerStunner(npc) or not self.mayHurt()):
            # (Past their share of the scale, the rest help this way too:
            # it holds the cogs' side back without weighing for the toons.)
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
        hit = self.hits(EVIDENCE_HIT_CHANCE)
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
        # The waiting is all walking (waiterJob): to the belt for a plate,
        # then to a hungry diner.
        return

    def waiterJob(self, npc, now):
        """The CEO's banquet, as a player does it: walk to a conveyor belt,
        take a plate by reaching it as it passes, walk to a hungry diner's
        chair and serve it there. Nothing from afar. True while busy."""
        boss = self.boss
        base = getClientBuiltin('base')
        bossClient = base.cr.doId2do.get(boss.doId) if base else None
        if bossClient is None or npc.busy:
            return False
        if npc.walk is not None and now < self.nextRoam.get(npc.doId, 0):
            self.waiterReach(npc, bossClient)
            return True
        self.syncPos(npc)
        pos = npc.getPos()
        if self.waiterReach(npc, bossClient):
            return True
        self.nextRoam[npc.doId] = now + 1.5
        if boss.toonFoodStatus.get(npc.doId):
            target = self.dinerSpot(npc, bossClient)
        else:
            target = self.beltSpot(npc, pos, bossClient)
        if target is None:
            return False
        if math.hypot(target[0] - pos[0], target[1] - pos[1]) < 1.5:
            return True
        if self.walkToward(npc, pos, Point3(target[0], target[1], pos[2]), ToontownGlobals.ToonForwardSpeed):
            return True
        self.count('ceo waiter detours')
        plate = self.waiterTarget.get(npc.doId)
        if plate is not None and not boss.toonFoodStatus.get(npc.doId):
            # That plate can't be reached from here: another one.
            self.unreachable[(npc.doId,) + tuple(plate)] = now + 10.0
            self.waiterTarget.pop(npc.doId, None)
        if self.manager.stats.get('ceo waiter detours', 0) % 50 == 1:
            self.notify.info('waiter %d: no way from (%.1f, %.1f, %.1f) to (%.1f, %.1f): %s' % (
                npc.doId, pos[0], pos[1], pos[2], target[0], target[1], getNav().whyNot(pos, Point3(target[0], target[1], pos[2]))))
        return False

    def waiterReach(self, npc, bossClient):
        """A plate or a diner within reach of where the NPC is now (on the
        player's screen): taken or served, as a player touching it."""
        boss = self.boss
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(npc.doId)
        if client is None:
            return False
        pos = client.getPos(base.render)
        if not boss.toonFoodStatus.get(npc.doId):
            for food in self.beltFoods(bossClient):
                beltIndex, foodIndex, foodNum, where = food
                if math.hypot(where[0] - pos[0], where[1] - pos[1]) < WAITER_REACH:
                    npc.asSender(boss.requestGetFood, beltIndex, foodIndex, foodNum)
                    if boss.toonFoodStatus.get(npc.doId):
                        self.count('ceo plates taken')
                        self.waiterTarget.pop(npc.doId, None)
                        npc.walk = None
                        return True
            return False
        mine = self.waiterTableOf(npc)
        for table in boss.tables:
            if mine is not None and table is not mine:
                continue
            tableClient = base.cr.doId2do.get(table.doId)
            if tableClient is None:
                continue
            for chairIndex in range(table.numDiners):
                if table.getDinerStatus(chairIndex) not in (table.HUNGRY, table.ANGRY):
                    continue
                chair = self.chairPos(tableClient, chairIndex)
                if chair is not None and math.hypot(chair[0] - pos[0], chair[1] - pos[1]) < DINER_BESIDE + 2.5:
                    npc.asSender(boss.requestServeFood, table.index, chairIndex)
                    if not boss.toonFoodStatus.get(npc.doId):
                        self.count('ceo plates served')
                        self.waiterTarget.pop(npc.doId, None)
                        npc.walk = None
                        return True
        return False

    def beltFoods(self, bossClient):
        base = getClientBuiltin('base')
        foods = []
        for belt in getattr(bossClient, 'belts', None) or []:
            if belt is None or belt.state != 'On':
                continue
            for foodIndex, model in belt.foodModelDict.items():
                if model.isStashed() or model.getParent().isEmpty():
                    continue
                col = model.find('**/FoodCol*')
                try:
                    foodNum = int(col.getTag('foodNum'))
                except Exception:
                    continue
                foods.append((belt.index, foodIndex, foodNum, model.getPos(base.render)))
        return foods

    def tableFinished(self, table):
        return not [i for i in range(table.numDiners)
                    if table.getDinerStatus(i) in (table.HUNGRY, table.ANGRY, table.EATING)]

    def tableSide(self, table):
        base = getClientBuiltin('base')
        tableClient = base.cr.doId2do.get(table.doId) if base else None
        if tableClient is None:
            return None
        return 0 if tableClient.tableGroup.getX(base.render) < 0 else 1

    def waiterSideOf(self, npc):
        """Arthur: four toons work each belt (the player counted on the
        side they're on); each NPC keeps its side."""
        side = self.waiterSide.get(npc.doId)
        if side is not None:
            return side
        base = getClientBuiltin('base')
        counts = [0, 0]
        for k, v in self.waiterSide.items():
            counts[v] += 1
        for p in self.players():
            client = base.cr.doId2do.get(p.doId) if base else None
            if client is not None:
                counts[0 if client.getX(base.render) < 0 else 1] += 1
        if counts[0] != counts[1]:
            side = 0 if counts[0] < counts[1] else 1
        else:
            side = 0 if npc.getX() < 0 else 1
        self.waiterSide[npc.doId] = side
        return side

    def waiterTableOf(self, npc):
        """Arthur: two toons to a table, staying on it until every diner
        there is done; then the next table on their side."""
        boss = self.boss
        side = self.waiterSideOf(npc)
        current = self.waiterTable.get(npc.doId)
        base = getClientBuiltin('base')

        def center(t):
            tc = base.cr.doId2do.get(t.doId) if base else None
            return tc.tableGroup.getPos(base.render) if tc is not None else None

        def playersAt(t):
            # Arthur: a real player working a table takes one of its two
            # spots (near it, or carrying a plate to it).
            c = center(t)
            if c is None:
                return 0
            n = 0
            for p in self.players():
                pc = base.cr.doId2do.get(p.doId)
                if pc is not None and math.hypot(pc.getX(base.render) - c[0], pc.getY(base.render) - c[1]) < WAITER_TABLE_NEAR:
                    n += 1
            return n

        def npcsAt(t):
            return [k for k, v in self.waiterTable.items() if v == t.index]

        for table in boss.tables:
            if table.index == current and not self.tableFinished(table):
                crew = npcsAt(table)
                if len(crew) + playersAt(table) <= 2:
                    return table
                # One too many: the NPC furthest from it moves on.
                c = center(table)
                far = max(crew, key=lambda k: math.hypot(self.air.doId2do[k].getX() - c[0], self.air.doId2do[k].getY() - c[1])
                          if k in self.air.doId2do and c is not None else 0)
                if far != npc.doId:
                    return table
                self.count('ceo waiters moved for the player')
                self.notify.info('waiter %d: the player took a spot at table %d, moving on' % (npc.doId, table.index))
        self.waiterTable.pop(npc.doId, None)
        open_ = [t for t in boss.tables if not self.tableFinished(t)]
        mine = [t for t in open_ if self.tableSide(t) == side] or open_
        if not mine:
            return None
        def crew(t):
            return len(npcsAt(t)) + playersAt(t)
        pos = npc.getPos()

        def dist(t):
            tc = base.cr.doId2do.get(t.doId)
            if tc is None:
                return 999
            c = tc.tableGroup.getPos(base.render)
            return math.hypot(c[0] - pos[0], c[1] - pos[1])
        # A partner first, then an empty table, nearest; only a third when
        # every table on this side already has two.
        for want in (1, 0):
            pick = [t for t in mine if crew(t) == want]
            if pick:
                table = min(pick, key=dist)
                break
        else:
            table = min(mine, key=lambda t: (crew(t), dist(t)))
        self.waiterTable[npc.doId] = table.index
        self.notify.info('waiter %d: %s belt, table %d (with %s)' % (
            npc.doId, 'left' if side == 0 else 'right', table.index,
            [k for k, v in self.waiterTable.items() if v == table.index and k != npc.doId]))
        return table

    def beltSpot(self, npc, pos, bossClient):
        """Beside a belt, a little ahead of the nearest plate coming along
        (on the NPC's side of it); each NPC its own plate."""
        base = getClientBuiltin('base')
        taken = set(v for k, v in self.waiterTarget.items() if k != npc.doId)
        best = None
        side = self.waiterSideOf(npc)
        belts = [belt for belt in getattr(bossClient, 'belts', None) or [] if belt is not None and belt.state == 'On']
        if [belt for belt in belts if belt.index == side]:
            belts = [belt for belt in belts if belt.index == side]
        # Not on top of the others working this belt.
        others = [v for k, v in self.waiterSpot.items() if k != npc.doId]
        for belt in belts:
            start = belt.startLocator.getPos(base.render)
            end = belt.endLocator.getPos(base.render)
            along = Point3(end[0] - start[0], end[1] - start[1], 0)
            if along.length() < 1:
                continue
            beltLength = along.length()
            along.normalize()
            across = Point3(-along[1], along[0], 0)
            if not getattr(self, 'beltsLogged', None):
                self.beltsLogged = set()
            if belt.index not in self.beltsLogged:
                self.beltsLogged.add(belt.index)
                self.notify.info('belt %d runs (%.1f, %.1f) -> (%.1f, %.1f)' % (belt.index, start[0], start[1], end[0], end[1]))
            for b, foodIndex, foodNum, where in self.beltFoods(bossClient):
                if b != belt.index or (b, foodNum) in taken:
                    continue
                # Plates come out of the wall: only once out in the room.
                gone = (where[0] - start[0]) * along[0] + (where[1] - start[1]) * along[1]
                if gone < BELT_IN_WALL or self.unreachable.get((npc.doId, b, foodNum), 0) > globalClock.getFrameTime():
                    continue
                side = 1 if (pos[0] - where[0]) * across[0] + (pos[1] - where[1]) * across[1] >= 0 else -1
                dist = math.hypot(where[0] - pos[0], where[1] - pos[1])
                lead = min(dist / ToontownGlobals.ToonForwardSpeed, 4.0) * belt.BeltSpeed
                spot = Point3(where[0] + along[0] * lead + across[0] * side * WAITER_BESIDE,
                              where[1] + along[1] * lead + across[1] * side * WAITER_BESIDE, pos[2])
                # Not past the end of the belt.
                if (spot[0] - end[0]) * along[0] + (spot[1] - end[1]) * along[1] > 0:
                    continue
                if [o for o in others if math.hypot(o[0] - spot[0], o[1] - spot[1]) < WAITER_SPACING]:
                    continue
                d = math.hypot(spot[0] - pos[0], spot[1] - pos[1])
                if best is None or d < best[0]:
                    best = (d, spot, (b, foodNum))
        if best is None:
            return None
        self.waiterTarget[npc.doId] = best[2]
        self.waiterSpot[npc.doId] = best[1]
        return best[1]

    def chairPos(self, tableClient, chairIndex):
        base = getClientBuiltin('base')
        loc = tableClient.chairLocators.get(chairIndex)
        if loc is None or loc.isEmpty():
            return None
        return loc.getPos(base.render)

    def dinerSpot(self, npc, bossClient):
        """Just outside a hungry diner's chair (angry ones first), the
        nearest one no other NPC is heading for."""
        boss = self.boss
        base = getClientBuiltin('base')
        taken = set(v for k, v in self.waiterTarget.items() if k != npc.doId)
        pos = npc.getPos()
        best = None
        mine = self.waiterTableOf(npc)
        for table in boss.tables:
            if mine is not None and table is not mine:
                continue
            tableClient = base.cr.doId2do.get(table.doId)
            if tableClient is None:
                continue
            center = tableClient.tableGroup.getPos(base.render)
            for chairIndex in range(table.numDiners):
                status = table.getDinerStatus(chairIndex)
                if status not in (table.HUNGRY, table.ANGRY) or ('diner', table.index, chairIndex) in taken:
                    continue
                chair = self.chairPos(tableClient, chairIndex)
                if chair is None:
                    continue
                out = Point3(chair[0] - center[0], chair[1] - center[1], 0)
                if out.length() > 0.1:
                    out.normalize()
                spot = Point3(chair[0] + out[0] * DINER_BESIDE, chair[1] + out[1] * DINER_BESIDE, pos[2])
                d = math.hypot(spot[0] - pos[0], spot[1] - pos[1]) - (30 if status == table.ANGRY else 0)
                if best is None or d < best[0]:
                    best = (d, spot, ('diner', table.index, chairIndex))
        if best is None:
            return None
        self.waiterTarget[npc.doId] = best[2]
        self.waiterSpot[npc.doId] = best[1]
        return best[1]

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
                target = self.pickStation(npc, free)
                if self.approach(npc, target):
                    npc.asSender(target.requestControl)
            return
        # As often as a player squirts when the NPCs are behind their
        # share, slower once they're past it (never stopping).
        share = self.share()
        pace = PITCHER_TIME_BEHIND if share < self.npcShare - 0.05 else (
            PITCHER_TIME if share > self.npcShare + 0.03 else PITCHER_TIME_EVEN)
        self.nextAction[npc.doId] = globalClock.getFrameTime() + random.uniform(*pace)
        # Turned and fired on the player's screen (NPCBanquetOperator):
        # only the water that reaches him counts. Past their share they aim
        # wide.
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(mine[0].doId) if base else None
        if client is not None and NPCBanquetOperator.wantShot(client, npc.doId, wide=not self.mayHurt()):
            self.count('ceo pitcher shots')

    def playGolf(self, npc):
        # A few take a golf spot, and slow him down with golf balls.
        boss = self.boss
        spots = list(getattr(boss, 'golfSpots', None) or [])
        mine = [spot for spot in spots if spot.avId == npc.doId]
        if not mine:
            golfers = [spot for spot in spots if isNPCId(self.air, spot.avId)]
            free = [spot for spot in spots if spot.avId == 0 and spot.state != 'Off']
            goal = getattr(npc, 'stationGoal', None)
            heading = goal is not None and any(spot.doId == goal for spot in free)
            if len(golfers) < GOLFERS and free and (heading or random.random() < 0.5):
                target = self.pickStation(npc, free)
                if not self.approach(npc, target):
                    return True
                npc.asSender(target.requestControl)
                return bool([spot for spot in spots if spot.avId == npc.doId])
            return False
        now = globalClock.getFrameTime()
        self.nextAction[npc.doId] = now + random.uniform(*GOLF_TIME)
        # Turned and swung on the player's screen (NPCBanquetOperator): only
        # a ball that reaches him counts.
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(mine[0].doId) if base else None
        if client is not None and NPCBanquetOperator.wantShot(client, npc.doId, wide=random.random() > GOLF_HIT_CHANCE * 1.6):
            self.count('ceo golf swings')
        return True
