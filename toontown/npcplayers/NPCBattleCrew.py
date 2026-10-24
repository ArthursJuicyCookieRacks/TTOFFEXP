"""Plays the NPC players' part in one battle.

The battle waits on every toon in it at each step: each joining toon, the
adjusting, the gag choices, the end of the movie and the reward. A real
player's client answers for its toon; this answers for the NPCs, through the
same messages.

Gag choices follow how good players played together online:
  * Toon-up goes to the real players first, then to the NPCs, so everyone
    stays standing.
  * Someone lures each round while there are cogs that aren't lured, and
    always when a player has set a trap.
  * Nobody lures in a round with sound in it, since sound wakes lured cogs.
  * The NPCs hit the cog the player hits, with the same gag, unless that cog
    is going down already; then they take the next one, just as hard as it
    needs.
  * No drops on lured cogs, which they would miss.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task

from toontown.battle.BattleBase import (attackAffectsGroup, HEAL, TRAP, LURE, SOUND, THROW, SQUIRT, DROP,
                                        NO_TRAP, PASS, TOON_ID_COL, TOON_TRACK_COL, TOON_LVL_COL, TOON_TGT_COL)
from toontown.battle.DistributedBattleAI import DistributedBattleAI
from toontown.toonbase.ToontownBattleGlobals import getAvPropDamage, MAX_LEVEL_INDEX

TICK = 0.3
# How long the NPCs think after the players have chosen.
CHOOSE_DELAY = 1.0
# When no player has a choice to wait for.
ALONE_DELAY = 3.0
HEAL_BELOW = 0.5
CRITICAL_BELOW = 0.25
DAMAGE_TRACKS = (THROW, SQUIRT, DROP, SOUND)
REWARD_STATES = ('Reward', 'BuildingReward', 'FactoryReward', 'MintReward', 'StageReward', 'CountryClubReward')


def isNPC(toon):
    return toon is not None and getattr(toon, 'isNPCPlayer', lambda: False)()


class NPCBattleCrew:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCBattleCrew')

    def __init__(self, manager, battle):
        self.manager = manager
        self.air = manager.air
        self.battle = battle
        self.members = []
        self.playersDoneAt = None
        self.lastState = None
        # What each round's gags were, for the tests: (lured before, attacks).
        self.history = []
        self.roundLured = set()
        manager.lastHistory = self.history
        self.taskName = 'npcBattleCrew-%d' % battle.doId
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    def destroy(self):
        taskMgr.remove(self.taskName)
        for npc in self.members[:]:
            self.release(npc)
        self.battle = None

    def add(self, npc):
        if npc not in self.members:
            self.members.append(npc)
            npc.crew = self
            self.notify.info('NPC %s fights in battle %d' % (npc.doId, self.battle.doId))

    def release(self, npc):
        if npc in self.members:
            self.members.remove(npc)
        if getattr(npc, 'crew', None) is self:
            npc.crew = None
        self.manager.npcLeftBattle(npc, self.battle)

    def join(self, npc, x, y, z):
        battle = self.battle
        if battle is None or not battle.toonCanJoin():
            return False
        if npc.zoneId != battle.zoneId:
            npc.b_setLocation(self.air.districtId, battle.zoneId)
        self.add(npc)
        npc.asSender(battle.toonRequestJoin, x, y, z)
        if npc.doId not in battle.toons:
            self.release(npc)
            return False
        return True

    def __tick(self, task):
        battle = self.battle
        if battle is None or battle.isDeleted() or battle.fsm is None:
            self.manager.crewDone(self)
            return Task.done
        state = battle.fsm.getCurrentState().getName()
        if state != self.lastState:
            self.lastState = state
            self.playersDoneAt = None
            if state == 'WaitForInput':
                self.roundLured = set(battle.battleCalc.currentlyLuredSuits.keys())
            elif state == 'PlayMovie':
                self.recordRound()
        for npc in self.members[:]:
            if npc.isDeleted() or npc.doId not in battle.toons:
                self.release(npc)
        if not self.members:
            return Task.again
        if not [t for t in battle.toons if not isNPC(self.air.doId2do.get(t))]:
            # The players are gone; the NPCs don't fight on alone.
            self.__runAway()
            return Task.again
        self.__answerJoins()
        self.__answerAdjust()
        if state == 'FaceOff' and not isinstance(battle, DistributedBattleAI):
            # Inside, every toon faces off; on the street only the one who
            # walked into the cog does.
            self.__answer(battle.faceOffDone)
        elif state == 'WaitForInput':
            self.__chooseAttacks()
        elif state == 'PlayMovie':
            self.__answer(battle.movieDone, afterPlayers=True)
        elif state in REWARD_STATES:
            self.__answer(battle.rewardDone, afterPlayers=True)
        return Task.again

    def recordRound(self):
        battle = self.battle
        attacks = []
        for toonId in battle.activeToons:
            attack = battle.toonAttacks.get(toonId)
            if attack is not None:
                attacks.append((toonId, isNPC(self.air.doId2do.get(toonId)), attack[TOON_TRACK_COL],
                                attack[TOON_LVL_COL], attack[TOON_TGT_COL]))
        self.history.append((sorted(self.roundLured), attacks))
        # How many NPCs fought in each kind of battle, for the tests.
        kind = battle.__class__.__name__
        npcs = len([a for a in attacks if a[1]])
        self.manager.stats[kind] = max(self.manager.stats.get(kind, 0), npcs)
        self.notify.info('round %d in battle %d: cogs %s, lured %s, attacks %s' % (
            len(self.history), battle.doId, [(s.doId, s.getHP()) for s in battle.activeSuits],
            sorted(self.roundLured), attacks))

    def __answerJoins(self):
        battle = self.battle
        for avId, responses in list(battle.joinResponses.items()):
            for npc in self.members:
                if responses.get(npc.doId) == 0:
                    npc.asSender(battle.joinDone, avId)

    def __answerAdjust(self):
        battle = self.battle
        if battle.adjustFsm.getCurrentState().getName() != 'Adjusting':
            return
        for npc in self.members:
            if battle.adjustingResponses.get(npc.doId) == 0:
                npc.asSender(battle.adjustDone)

    def __answer(self, method, afterPlayers=False):
        battle = self.battle
        if afterPlayers:
            # The first toon to say its movie is done starts a short timer
            # for the rest, so the NPCs wait for the players' clients to
            # finish theirs.
            players = [t for t in battle.responses if not isNPC(self.air.doId2do.get(t))]
            if not all(battle.responses.get(t, 0) > 0 for t in players):
                return
        for npc in self.members:
            if battle.responses.get(npc.doId) == 0 and not battle.ignoreResponses:
                npc.asSender(method)

    def __runAway(self):
        battle = self.battle
        if not battle.isRunable():
            return
        for npc in self.members[:]:
            if npc.doId in battle.activeToons:
                npc.asSender(battle.toonRequestRun)

    # --- Choosing gags ---

    def __chooseAttacks(self):
        battle = self.battle
        if battle.ignoreResponses:
            return
        waiting = [npc for npc in self.members
                   if npc.doId in battle.activeToons and battle.responses.get(npc.doId) == 0]
        if not waiting:
            return
        players = [t for t in battle.activeToons if not isNPC(self.air.doId2do.get(t))]
        self.notify.debug('waiting %s players %s responses %s' % ([n.doId for n in waiting], players, battle.responses))
        playersDone = all(battle.responses.get(t, 0) > 0 for t in players)
        now = globalClock.getFrameTime()
        if not playersDone:
            self.playersDoneAt = None
            return
        if self.playersDoneAt is None:
            self.playersDoneAt = now
        delay = CHOOSE_DELAY if players else ALONE_DELAY
        if now - self.playersDoneAt < delay:
            return
        # One at a time, each seeing what the others chose.
        npc = waiting[0]
        track, level, target = RoundPlanner(battle, self.air).choose(npc)
        npc.asSender(battle.requestAttack, track, level, target)
        self.playersDoneAt = now - delay + 0.3


class RoundPlanner:
    notify = DirectNotifyGlobal.directNotify.newCategory('RoundPlanner')
    """Works out one NPC's gag from what everyone else has chosen."""

    def __init__(self, battle, air):
        self.battle = battle
        self.air = air
        self.suits = [s for s in battle.activeSuits if s.getHP() > 0]
        self.lured = set(battle.battleCalc.currentlyLuredSuits.keys())
        self.attacks = []
        for toonId in battle.activeToons:
            attack = battle.toonAttacks.get(toonId)
            if attack is None or battle.responses.get(toonId, 0) == 0:
                continue
            toon = self.air.doId2do.get(toonId)
            self.attacks.append((toon, attack[TOON_TRACK_COL], attack[TOON_LVL_COL], attack[TOON_TGT_COL]))

    def tracksUsed(self):
        return set(a[1] for a in self.attacks)

    # Gags the NPC has.

    def has(self, npc, track, level):
        return npc.hasTrackAccess(track) and npc.inventory.numItem(track, level) > 0

    def levels(self, npc, track, group=None):
        levels = [l for l in range(MAX_LEVEL_INDEX + 1) if self.has(npc, track, l)]
        if group is not None:
            levels = [l for l in levels if bool(attackAffectsGroup(track, l)) == group]
        return levels

    def damage(self, toon, track, level):
        if toon is None:
            return 0
        return getAvPropDamage(track, level, toon.experience.getExp(track))

    # What is going to happen this round.

    def lureThisRound(self):
        lured = set()
        for toon, track, level, target in self.attacks:
            if track == LURE:
                if attackAffectsGroup(track, level):
                    lured.update(s.doId for s in self.suits)
                else:
                    lured.add(target)
        return lured

    def predictedHp(self):
        hp = dict((s.doId, s.getHP()) for s in self.suits)
        lured = self.lured | self.lureThisRound()
        for toon, track, level, target in self.attacks:
            if track not in DAMAGE_TRACKS and track != TRAP:
                continue
            if track == TRAP and target not in self.lureThisRound():
                continue
            amount = self.damage(toon, track, level)
            if track in (THROW, SQUIRT) and target in lured:
                amount = int(amount * 1.5)
            if track == DROP and target in lured:
                amount = 0
            targets = list(hp.keys()) if attackAffectsGroup(track, level) else [target]
            for t in targets:
                if t in hp:
                    hp[t] -= amount
        return hp

    def choose(self, npc):
        track, level, target = (self.chooseHeal(npc) or self.chooseLure(npc) or self.chooseAttack(npc)
                                or (PASS, -1, -1))
        if track == PASS:
            self.notify.info('NPC %s passes: tracks %s, inventory %s, suits %s, attacks %s' % (
                npc.doId, npc.trackArray, npc.inventory.inventory, [(s.doId, s.getHP()) for s in self.suits],
                self.attacks))
        if track != PASS and attackAffectsGroup(track, level):
            target = -1
        return track, level, target

    def chooseHeal(self, npc):
        battle = self.battle
        healing = {}
        for toon, track, level, target in self.attacks:
            if track == HEAL:
                amount = self.damage(toon, track, level)
                targets = [t for t in battle.activeToons if t != toon.doId] if attackAffectsGroup(track, level) else [target]
                for t in targets:
                    healing[t] = healing.get(t, 0) + amount
        needy = []
        for toonId in battle.activeToons:
            toon = self.air.doId2do.get(toonId)
            if toon is None or toon.maxHp <= 0:
                continue
            ratio = float(toon.hp + healing.get(toonId, 0)) / toon.maxHp
            if ratio < HEAL_BELOW:
                needy.append((isNPC(toon), ratio, toon))
        if not needy:
            return None
        healers = len([a for a in self.attacks if a[1] == HEAL])
        critical = [n for n in needy if n[1] < CRITICAL_BELOW]
        if healers >= (2 if critical else 1):
            return None
        # Real players first, then whoever is lowest.
        needy.sort(key=lambda n: (n[0], n[1]))
        others = [n for n in needy if n[2] is not npc]
        if len(others) >= 2 or (len(others) == 1 and len(needy) == 2):
            groupLevels = self.levels(npc, HEAL, group=True)
            if groupLevels and len(battle.activeToons) >= 2:
                missing = max(n[2].maxHp - n[2].hp for n in needy)
                return (HEAL, self.bestLevel(npc, HEAL, groupLevels, missing), -1)
        if not others:
            return None
        patient = others[0][2]
        singleLevels = self.levels(npc, HEAL, group=False)
        if not singleLevels:
            singleLevels = self.levels(npc, HEAL, group=True)
            if not singleLevels:
                return None
            return (HEAL, self.bestLevel(npc, HEAL, singleLevels, patient.maxHp - patient.hp), -1)
        return (HEAL, self.bestLevel(npc, HEAL, singleLevels, patient.maxHp - patient.hp), patient.doId)

    def bestLevel(self, npc, track, levels, needed):
        # The smallest gag that does the job, or the biggest there is.
        for level in sorted(levels):
            if self.damage(npc, track, level) >= needed:
                return level
        return max(levels)

    def chooseLure(self, npc):
        used = self.tracksUsed()
        if SOUND in used or LURE in used:
            return None
        if not self.levels(npc, LURE):
            return None
        unlured = [s.doId for s in self.suits if s.doId not in self.lured]
        if not unlured:
            return None
        trapped = [t for (toon, track, level, t) in self.attacks if track == TRAP and t in unlured]
        trapped += [s.doId for s in self.suits if s.doId in unlured and s.battleTrap != NO_TRAP]
        hp = self.predictedHp()
        if not trapped and all(hp.get(s, 1) <= 0 for s in unlured):
            # Those cogs are going down anyway.
            return None
        dropTargets = set(t for (toon, track, level, t) in self.attacks if track == DROP)
        candidates = [s for s in unlured if s not in dropTargets]
        if not candidates:
            return None
        groupLevels = self.levels(npc, LURE, group=True)
        if len(candidates) >= 2 and groupLevels and not dropTargets & set(unlured):
            return (LURE, max(groupLevels), -1)
        singleLevels = self.levels(npc, LURE, group=False) or groupLevels
        if not singleLevels:
            return None
        playerTargets = [t for (toon, track, level, t) in self.attacks if not isNPC(toon) and track in DAMAGE_TRACKS]
        for choice in trapped + playerTargets + candidates:
            if choice in candidates:
                level = max(singleLevels)
                if attackAffectsGroup(LURE, level) and dropTargets & set(unlured):
                    return None
                return (LURE, level, choice if not attackAffectsGroup(LURE, level) else -1)
        return None

    def chooseAttack(self, npc):
        if not self.suits:
            return None
        used = self.tracksUsed()
        hp = self.predictedHp()
        lured = self.lured | self.lureThisRound()
        reference = None
        for toon, track, level, target in self.attacks:
            if not isNPC(toon) and track in DAMAGE_TRACKS:
                reference = (track, level, target)
                break

        if SOUND in used:
            # Everyone sounds together, which keeps the cogs from waking
            # up between hits.
            levels = self.levels(npc, SOUND)
            if levels:
                wanted = reference[1] if reference and reference[0] == SOUND else max(levels)
                return (SOUND, self.closestLevel(levels, wanted), -1)

        alive = [s.doId for s in self.suits if hp.get(s.doId, 0) > 0]
        if not alive:
            alive = [s.doId for s in self.suits]

        if reference is not None and reference[0] in (THROW, SQUIRT, DROP):
            track, level, target = reference
            levels = self.levels(npc, track)
            if levels and attackAffectsGroup(track, level):
                # A gag on every cog; the same again, while any are left.
                anyLeft = [s for s in self.suits if hp.get(s.doId, 0) > 0]
                if anyLeft and (track != DROP or not lured):
                    return (track, self.closestLevel(levels, level), -1)
            elif levels and not (track == DROP and target in lured):
                if target in alive:
                    return (track, self.closestLevel(levels, level), target)
                # That cog is going down; the same gag on the next one, as
                # big as it needs.
                for other in self.ordered(alive, hp, lured):
                    if track == DROP and other in lured:
                        continue
                    return (track, self.bestLevel(npc, track, levels, hp[other]), other)

        for target in self.ordered(alive, hp, lured):
            for track in self.tracksFor(npc, target in lured):
                levels = self.levels(npc, track)
                if levels:
                    needed = hp.get(target, 0)
                    if track in (THROW, SQUIRT) and target in lured:
                        needed = int(math.ceil(needed / 1.5))
                    return (track, self.bestLevel(npc, track, levels, needed), target)
        return None

    def ordered(self, targets, hp, lured):
        # Lured cogs first (the knockback), then the weakest.
        return sorted(targets, key=lambda t: (t not in lured, hp.get(t, 0)))

    def tracksFor(self, npc, lured):
        if lured:
            return (THROW, SQUIRT)
        tracks = [THROW, SQUIRT]
        if not self.lureThisRound():
            tracks.insert(0, DROP)
        return tracks

    def closestLevel(self, levels, wanted):
        below = [l for l in levels if l <= wanted]
        return max(below) if below else min(levels)
