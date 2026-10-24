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
from toontown.toonbase import ToontownGlobals

TICK = 0.5
# Seconds between one NPC's throws.
THROW_TIME = (1.2, 2.6)
# Chances a pie does what it was thrown for.
STUN_CHANCE = 0.3
HIT_CHANCE = 0.8
# Chances an NPC is caught by the boss's attacks.
AREA_HIT_CHANCE = 0.25
DIRECTED_HIT_CHANCE = 0.6
HEAL_PLAYER_BELOW = 0.4


class NPCBossCrew:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCBossCrew')

    def __init__(self, manager, boss):
        self.manager = manager
        self.air = manager.air
        self.boss = boss
        self.dept = boss.dna.dept
        self.nextAction = {}
        self.lastAttack = None
        self.pieSequence = {}
        self.foodNum = 1000
        self.stateSince = (None, 0)
        self.taskName = 'npcBossCrew-%d' % boss.doId
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    def destroy(self):
        taskMgr.remove(self.taskName)
        self.boss = None

    def members(self):
        boss = self.boss
        return [npc for npc in self.manager.party.members
                if not npc.isDeleted() and npc.doId in boss.involvedToons and npc.crew is None]

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
            play = getattr(self, 'play%s%s' % (self.dept.upper(), state), None)
            if play is not None:
                for npc in members:
                    if now >= self.nextAction.get(npc.doId, 0):
                        self.nextAction[npc.doId] = now + random.uniform(*THROW_TIME)
                        play(npc)
                        key = 'boss %s' % self.dept
                        self.manager.stats[key] = self.manager.stats.get(key, 0) + 1
        except Exception:
            self.notify.warning('boss crew failed')
            import traceback
            traceback.print_exc()
        return Task.again

    # --- Being hit ---

    def takeHits(self, members):
        boss = self.boss
        attack = (boss.attackCode, boss.attackAvId)
        if attack == self.lastAttack:
            return
        self.lastAttack = attack
        code, target = attack
        damage = ToontownGlobals.BossCogDamageLevels.get(code)
        if not damage or boss.getCurrentOrNextState() not in ('BattleThree', 'BattleFour', 'RollToBattleTwo'):
            return
        for npc in members:
            chance = DIRECTED_HIT_CHANCE if target == npc.doId else AREA_HIT_CHANCE
            if target and target != npc.doId:
                continue
            if random.random() < chance:
                pos = npc.getPos()
                npc.asSender(boss.zapToon, pos[0], pos[1], pos[2], npc.getH(), 0, 0, 0, 0, code,
                             globalClockDelta.getFrameNetworkTime(bits=16))
                if npc.hp <= 0:
                    # Gone sad, out of the fight.
                    npc.asSender(boss.avatarExit)
                    self.manager.party.disband(npc)

    # --- Pies, for the look of it ---

    def bossPos(self):
        base = getClientBuiltin('base')
        boss = base.cr.doId2do.get(self.boss.doId) if base else None
        if boss is None or boss.isEmpty():
            return None
        return boss.getPos(base.render) + Point3(0, 0, 8)

    def throwAt(self, npc, target, pieCode):
        # The toss and the splat, as the thrower's client would send them.
        if target is None:
            return
        pos = npc.getPos()
        direction = target - pos
        h = -math.degrees(math.atan2(direction[0], direction[1]))
        npc.setH(h)
        sequence = self.pieSequence[npc.doId] = (self.pieSequence.get(npc.doId, 0) + 1) % 256
        now = globalClockDelta.getFrameNetworkTime(bits=32)
        npc.sendUpdate('tossPie', [pos[0], pos[1], pos[2], h, sequence, 60, 0, now])
        npc.sendUpdate('pieSplat', [target[0], target[1], target[2], sequence, pieCode, now + 30])

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
                self.throwAt(npc, target, ToontownGlobals.PieCodeToon)
                npc.asSender(self.boss.hitToon, player.doId)
                return True
        return False

    # --- The VP ---

    def playSBattleThree(self, npc):
        boss = self.boss
        if npc.numPies <= 0:
            npc.asSender(boss.touchCage)
            return
        if self.healPlayer(npc):
            return
        target = self.bossPos()
        if boss.attackCode == ToontownGlobals.BossCogDizzyNow:
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossCog)
            if random.random() < HIT_CHANCE:
                npc.asSender(boss.hitBoss, 1)
        else:
            # A pie under his front, while he faces the toon, stuns him.
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossInsides)
            if random.random() < STUN_CHANCE:
                npc.asSender(boss.hitBossInsides)

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
            free = [c for c in boss.cranes or [] if c.avId == 0]
            if free:
                npc.asSender(free[0].requestControl)
            return
        held = None
        for obj in list(boss.safes or []) + list(boss.goons or []):
            if getattr(obj, 'avId', 0) == npc.doId and obj.state in ('Grabbed',):
                held = obj
        if held is not None:
            if random.random() < HIT_CHANCE:
                npc.asSender(held.hitBoss, random.uniform(0.6, 1.0))
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
        cannon = cannons[hash(npc.doId) % len(cannons)]
        if getattr(cannon, 'avId', 0) in (0, None):
            npc.asSender(cannon.requestEnter)
        for chair in boss.chairs or []:
            if chair.state != 'ToonJuror' and random.random() < 0.5:
                npc.asSender(boss.hitChair, chair.index, cannon.index)
                return

    def playLBattleThree(self, npc):
        boss = self.boss
        if npc.numPies <= 0:
            npc.asSender(boss.touchWitnessStand)
            return
        if self.healPlayer(npc):
            return
        target = self.bossPos()
        if boss.attackCode != ToontownGlobals.BossCogDizzyNow and random.random() < 0.15:
            self.throwAt(npc, target, ToontownGlobals.PieCodeBossInsides)
            if random.random() < STUN_CHANCE:
                npc.asSender(boss.hitBossInsides)
            return
        # Evidence on the scale's pan.
        self.throwAt(npc, target, ToontownGlobals.PieCodeDefensePan)
        if random.random() < HIT_CHANCE:
            npc.asSender(boss.hitBoss, 1)

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
        roll = random.random()
        if roll < 0.25 and getattr(boss, 'golfSpots', None):
            # A golf ball slows him down.
            npc.asSender(boss.ballHitBoss, random.randint(2, 6))
            return
        self.throwAt(npc, self.bossPos(), ToontownGlobals.PieCodeBossCog)
        if roll < 0.25 + HIT_CHANCE * 0.75:
            npc.asSender(boss.hitBoss, 1)
