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
CRANE_TIME = (10.0, 18.0)
# Aiming a banquet table's water pitcher at the CEO.
PITCHER_TIME = (4.0, 6.0)
PITCHER_HIT_CHANCE = 0.45
# How many NPCs take a pitcher; the rest golf, fetch toon-up food or keep
# out of his way.
PITCHERS = 3
GOLF_TIME = (5.0, 9.0)
# Chances a pie does what it was thrown for.
STUN_CHANCE = 0.15
HIT_CHANCE = 0.4
# Seconds between one NPC's throws at a dizzy VP: a player has to get in
# front of him and aim.
DIZZY_THROW_TIME = (1.8, 3.5)
# A run to the witness stand for more evidence, and back.
EVIDENCE_TRIP = (3.0, 6.0)
# Evidence on the CJ's scale pan, a big target.
EVIDENCE_HIT_CHANCE = 0.55
# How often a throw goes at one of the lawyers instead.
LAWYER_CHANCE = 0.2
LAWYER_HIT_CHANCE = 0.5
# The VP: only a few toons go for his stun (the rest wait to hit him while
# he is dizzy), and they give him a while on his feet before trying again.
STUNNERS = (2, 3)
STUN_REST = (4.0, 8.0)
# The CFO: how likely a safe swung at him lands, and how long one crane is
# kept free for the player at the start.
CRANE_HIT_CHANCE = 0.4
CRANE_FOR_PLAYER = 30.0
# The CJ: how likely a toon fired from a cannon lands in a chair.
CANNON_HIT_CHANCE = 0.3
# The CEO: how many NPCs take a golf spot, and how likely a ball hits him.
GOLFERS = 2
GOLF_HIT_CHANCE = 0.45
# Between goes the NPCs move about the arena on their own, as players do,
# rather than following the player: how often, and how far from the boss.
ROAM_TIME = (3.0, 9.0)
ROAM_RANGE = (14.0, 40.0)
# No roaming path passes nearer the boss than this.
BOSS_CLEAR = 11.0
# Now and then an NPC stops to emote instead of walking.
ROAM_EMOTE_CHANCE = 0.3
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
JUMPABLE = (ToontownGlobals.BossCogAreaAttack, ToontownGlobals.BossCogDirectedAttack,
            ToontownGlobals.BossCogSlowDirectedAttack, ToontownGlobals.BossCogGearDirectedAttack,
            ToontownGlobals.BossCogGavelStomp, ToontownGlobals.BossCogGolfAreaAttack)
HIT_STATES = ('BattleThree', 'BattleFour', 'RollToBattleTwo')
HEAL_PLAYER_BELOW = 0.4
HEAL_HIT_CHANCE = 0.7
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
        self.dizzy = False
        self.stunRestUntil = 0
        self.nextRoam = {}
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
        try:
            members = self.members()
            self.takeHits(members)
            if (self.dept, state) in ROAM_STATES:
                for npc in members:
                    self.roam(npc, now)
            play = getattr(self, 'play%s%s' % (self.dept.upper(), state), None)
            if play is not None:
                pace = SLOW_TIME if (self.dept, state) in SLOW_JOBS else THROW_TIME
                if (self.dept, state) == ('m', 'BattleThree'):
                    pace = CRANE_TIME
                elif self.dept == 's' and boss.attackCode == ToontownGlobals.BossCogDizzyNow:
                    pace = DIZZY_THROW_TIME
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

    def roam(self, npc, now):
        if npc.walk is not None or npc.busy or now < self.nextRoam.get(npc.doId, 0):
            return
        self.nextRoam[npc.doId] = now + random.uniform(*ROAM_TIME)
        if self.isStationed(npc) or npc.getBattleId() > 0 or getattr(npc, 'crew', None) is not None:
            # Held by the game, or fighting the cogs.
            return
        center = self.bossPos()
        if center is None:
            return
        self.syncPos(npc)
        if random.random() < ROAM_EMOTE_CHANCE:
            from toontown.npcplayers.NPCPlayerManagerAI import IDLE_EMOTES
            npc.b_setEmoteState(random.choice(IDLE_EMOTES), 1.0)
            return
        nav = getNav()
        pos = npc.getPos()
        for i in range(6):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(*ROAM_RANGE)
            target = Point3(center[0] + dist * math.cos(angle), center[1] + dist * math.sin(angle), pos[2])
            path = nav.walkable(pos, target)
            if path and not self.nearBoss(path, center):
                npc.walk = [path, ToontownGlobals.ToonForwardSpeed, None, None]
                return

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
            elif newAttack and code in JUMPABLE and (not target or target == npc.doId):
                # Everyone in reach tries to jump it.
                self.jump(npc)
                if random.random() > JUMP_CHANCE:
                    hit = code
            if hit is None:
                continue
            self.safeUntil[npc.doId] = now + HIT_REST
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
        taskMgr.doMethodLater(1.2, lambda task: (not npc.isDeleted() and npc.b_setAnimState('neutral', 1.0)) and None,
                              'npcBossJump-%d' % npc.doId)

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
        # Pies at a toon heal it; the player comes first.
        for player in self.players():
            if player.maxHp and float(player.hp) / player.maxHp < HEAL_PLAYER_BELOW:
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
        boss = self.boss
        now = globalClock.getFrameTime()
        dizzy = boss.attackCode == ToontownGlobals.BossCogDizzyNow
        if self.dizzy and not dizzy:
            # Back on his feet; the stunners give him a moment.
            self.stunRestUntil = now + random.uniform(*STUN_REST)
        self.dizzy = dizzy
        if npc.numPies <= 0:
            npc.asSender(boss.touchCage)
            return
        if self.healPlayer(npc):
            return
        target = self.bossPos()
        if dizzy:
            hit = random.random() < HIT_CHANCE
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossCog, hit)
            if hit:
                npc.asSender(boss.hitBoss, 1)
        elif self.isStunner(npc) and now >= self.stunRestUntil:
            # A pie under his front, while he faces the toon, stuns him;
            # most miss.
            stun = random.random() < STUN_CHANCE
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossInsides, stun)
            self.count('vp stun tries')
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
                # Off to the witness stand for more.
                npc.fetchingEvidence = True
                self.nextAction[npc.doId] = globalClock.getFrameTime() + random.uniform(*EVIDENCE_TRIP)
                return
            npc.fetchingEvidence = False
            npc.asSender(boss.touchWitnessStand)
            return
        if self.healPlayer(npc):
            return
        lawyers = [l for l in getattr(boss, 'lawyers', None) or [] if not l.isDeleted() and not l.stunned]
        if lawyers and random.random() < LAWYER_CHANCE:
            # A pie at a lawyer stops its evidence landing on the cogs' pan,
            # and with every lawyer stunned the toons' evidence weighs more.
            if random.random() < LAWYER_HIT_CHANCE:
                npc.asSender(random.choice(lawyers).hitByToon)
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
