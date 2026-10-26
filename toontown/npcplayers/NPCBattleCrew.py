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
  * Level 7 gags are kept for the big fights: three or more cogs of level 10
    and up, or a level 12 cog.
  * In a battle of NPCs alone they choose at the last moment, as the timer
    runs out, the way many players did; with a player they choose straight
    after the player.

The NPCs fight on their own too, when they walk into a cog.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task

from panda3d.core import ConfigVariableBool

from otp.local.ExecutionContext import getClientBuiltin

from toontown.battle.BattleBase import (attackAffectsGroup, HEAL, TRAP, LURE, SOUND, THROW, SQUIRT, DROP,
                                        NO_TRAP, PASS, NPCSOS, FIRE, TOON_ID_COL, TOON_TRACK_COL, TOON_LVL_COL,
                                        TOON_TGT_COL, SERVER_BUFFER_TIME)
from toontown.chat import ResistanceChat
from toontown.toon import NPCToons
from toontown.battle.DistributedBattleAI import DistributedBattleAI
from toontown.toonbase.ToontownBattleGlobals import getAvPropDamage, MAX_LEVEL_INDEX

TICK = 0.3
# How long the NPCs think after the players have chosen.
CHOOSE_DELAY = 1.0
# When no player has a choice to wait for.
ALONE_DELAY = 3.0
# In a battle of NPCs alone they choose when the timer shows this many
# seconds (a new pick each round).
LAST_SECOND = (1.0, 2.5)
# With no player in the battle, how long the NPCs give a movie when the
# player's game isn't playing it: per gag, per cog attack, and the reward.
MOVIE_PER_ATTACK = 3.0
MOVIE_PER_SUIT = 3.0
REWARD_TIME = 4.0
# Level 7 gags: for three cogs of this level or more, or one of UBER_ONE.
UBER_LEVEL = 10
UBER_COUNT = 3
UBER_ONE = 12
HEAL_BELOW = 0.5
# A real player gets a toon-up sooner.
PLAYER_HEAL_BELOW = 0.6
CRITICAL_BELOW = 0.25
DAMAGE_TRACKS = (THROW, SQUIRT, DROP, SOUND)
# The extras a player can bring to a battle, and how likely an NPC is to
# carry one when it first joins a battle; most carry none. An NPC keeps what
# it has left from battle to battle, so a used one is gone. Each NPC uses each
# it has at most once a battle, only one is used every SPECIAL_GAP rounds, and
# only when there's a good reason (see __special and __maybeUnite).
SPECIAL_CHANCES = (('fire', 0.15), ('sos', 0.2), ('unite', 0.25))
SPECIAL_GAP = 3
# A big cog, for the extras: a battle wants one with two of these, or one of
# BIG_ALONE or more among three cogs.
BIG_COG = 9
BIG_ALONE = 11
# A player this low wants a toon-up SOS card or unite.
EXTRA_HEAL_BELOW = 0.35
# SOS cards up to this many stars; the five star ones were rare online.
SOS_MAX_STARS = 4
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
        # What extras each NPC has left this battle, and the round the last
        # one was used.
        self.specials = {}
        self.lastSpecialRound = -SPECIAL_GAP
        self.round = 0
        self.stateAt = globalClock.getFrameTime()
        self.lastSecond = LAST_SECOND[0]
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
            npc.needsRefill = True
            if ConfigVariableBool('npc-specials', True).getValue():
                if getattr(npc, 'specialStock', None) is None:
                    npc.specialStock = dict((kind, 1) for kind, chance in SPECIAL_CHANCES if random.random() < chance)
                self.specials[npc.doId] = set(kind for kind, left in npc.specialStock.items() if left > 0)
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
            self.stateAt = globalClock.getFrameTime()
            self.playersDoneAt = None
            if state == 'WaitForInput':
                self.lastSecond = random.uniform(*LAST_SECOND)
                self.roundLured = set(battle.battleCalc.currentlyLuredSuits.keys())
                self.round += 1
                self.__maybeUnite()
            elif state == 'PlayMovie':
                self.recordRound()
        for npc in self.members[:]:
            if npc.isDeleted() or npc.doId not in battle.toons:
                self.release(npc)
        if not self.members:
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
            if self.__playersIn() or self.__movieOver():
                self.__answer(battle.movieDone, afterPlayers=True)
        elif state in REWARD_STATES:
            if self.__playersIn() or globalClock.getFrameTime() - self.stateAt > REWARD_TIME:
                self.__answer(battle.rewardDone, afterPlayers=True)
        return Task.again

    def __playersIn(self):
        return [t for t in self.battle.toons if not isNPC(self.air.doId2do.get(t))]

    def __movieOver(self):
        """For a battle of NPCs alone: whether its movie has played out on the
        player's screen, or would have by now if the player isn't watching."""
        battle = self.battle
        since = globalClock.getFrameTime() - self.stateAt
        base = getClientBuiltin('base')
        cr = getattr(base, 'cr', None)
        client = cr.doId2do.get(battle.doId) if cr is not None else None
        if client is not None and getattr(client, 'movie', None) is not None:
            if since < 1.0:
                return False
            playing = client.fsm.getCurrentState().getName() == 'PlayMovie' and client.movie.track is not None
            return not playing
        return since > MOVIE_PER_ATTACK * len(battle.activeToons) + MOVIE_PER_SUIT * len(battle.activeSuits)

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
        now = globalClock.getFrameTime()
        delay = CHOOSE_DELAY if players else ALONE_DELAY
        if not players and isinstance(battle, DistributedBattleAI) and battle.timer.isStarted():
            # NPCs alone choose at the last moment: what the timer shows,
            # less a tick for each NPC still to choose after this one. With
            # a player in the battle they choose as soon as the player has.
            shown = battle.timer.getT() - SERVER_BUFFER_TIME
            if shown > self.lastSecond + TICK * (len(waiting) - 1):
                return
        else:
            playersDone = all(battle.responses.get(t, 0) > 0 for t in players)
            if not playersDone:
                self.playersDoneAt = None
                return
            if self.playersDoneAt is None:
                self.playersDoneAt = now
            if now - self.playersDoneAt < delay:
                return
        # One at a time, each seeing what the others chose.
        npc = waiting[0]
        planner = RoundPlanner(battle, self.air)
        special = self.__special(npc, planner)
        if special is not None:
            track, level, target = special
        else:
            track, level, target = planner.choose(npc)
        npc.asSender(battle.requestAttack, track, level, target)
        if battle.timer.isStarted():
            self.notify.info('NPC %s chooses with %.1f s on the timer' % (npc.doId, battle.timer.getT() - SERVER_BUFFER_TIME))
        self.playersDoneAt = now - delay + 0.3


    # --- SOS cards, pink slips and unites ---

    def __canUseSpecial(self, npc, kind):
        return kind in self.specials.get(npc.doId, ()) and self.round - self.lastSpecialRound >= SPECIAL_GAP

    def __used(self, npc, kind):
        self.specials[npc.doId].discard(kind)
        npc.specialStock[kind] -= 1
        self.lastSpecialRound = self.round
        self.manager.stats['special ' + kind] = self.manager.stats.get('special ' + kind, 0) + 1
        self.notify.info('NPC %s uses %s in battle %d' % (npc.doId, kind, self.battle.doId))

    def __players(self):
        players = []
        for toonId in self.battle.activeToons:
            toon = self.air.doId2do.get(toonId)
            if toon is not None and not isNPC(toon):
                players.append(toon)
        return players

    def __hard(self, planner):
        # A battle worth an extra: two big cogs, or a very big one in a
        # crowd.
        suits = planner.suits
        big = [s for s in suits if s.getActualLevel() >= BIG_COG]
        return len(big) >= 2 or (len(suits) >= 3 and any(s.getActualLevel() >= BIG_ALONE for s in suits))

    def __playerInTrouble(self):
        return any(p.getHp() < p.getMaxHp() * EXTRA_HEAL_BELOW for p in self.__players())

    def __special(self, npc, planner):
        """A pink slip or an SOS card for this NPC's turn, or None."""
        battle = self.battle
        if not planner.suits or SOUND in planner.playerTracks():
            # Everyone sounds with the player.
            return None
        hard = self.__hard(planner)
        if self.__canUseSpecial(npc, 'sos') and (hard or self.__playerInTrouble()):
            card = self.__pickCard(planner)
            if card is not None:
                npc.NPCFriendsDict[card] = 1
                self.__used(npc, 'sos')
                return NPCSOS, -1, card
        if self.__canUseSpecial(npc, 'fire') and hard:
            hp = planner.predictedHp()
            # Never the player's cog, and only a big one that this round
            # won't take down already.
            taken = planner.playerTargets() | set(a[3] for a in planner.attacks if a[1] == FIRE)
            targets = [s for s in planner.suits if hp.get(s.doId, 0) > 0 and s.doId not in taken
                       and s.getActualLevel() >= BIG_COG]
            if targets:
                suit = max(targets, key=lambda s: (s.getActualLevel(), s.getHP()))
                npc.b_setPinkSlips(npc.getPinkSlips() + 1)
                self.__used(npc, 'fire')
                return FIRE, -1, suit.doId
        return None

    def __pickCard(self, planner):
        battle = self.battle
        players = self.__players()
        hurt = self.__playerInTrouble()
        taken = set(battle.npcAttacks.keys())
        cards = [c for c in NPCToons.npcFriendsMinMaxStars(1, SOS_MAX_STARS) if c not in taken]
        if hurt:
            cards = [c for c in cards if NPCToons.getNPCTrack(c) == HEAL] or cards
        else:
            # Something that hits (not an SOS lure, which could spoil a
            # trap or a sound plan).
            hitting = (DROP, THROW, SQUIRT)
            if not (planner.lured or planner.lureThisRound()):
                # Sound would wake lured cogs.
                hitting += (SOUND,)
            cards = [c for c in cards if NPCToons.getNPCTrack(c) in hitting]
        return random.choice(cards) if cards else None

    def __maybeUnite(self):
        # A unite is said, not played as a turn: a toon-up when a player is
        # hurt, otherwise a gag restock when a player is running low.
        for npc in self.members:
            if not self.__canUseSpecial(npc, 'unite') or npc.doId not in self.battle.activeToons:
                continue
            players = self.__players()
            if not players:
                return
            if self.__playerInTrouble():
                menu, items = ResistanceChat.RESISTANCE_TOONUP, (2, 3, 4)
            elif any(p.inventory.totalProps < p.getMaxCarry() // 4 for p in players):
                menu, items = ResistanceChat.RESISTANCE_RESTOCK, (7,)
            else:
                continue
            textId = ResistanceChat.encodeId(menu, random.choice(items))
            npc.addResistanceMessage(textId)
            npc.d_setSCResistance(textId, [p.doId for p in players])
            self.__used(npc, 'unite')
            return


class RoundPlanner:
    notify = DirectNotifyGlobal.directNotify.newCategory('RoundPlanner')
    """Works out one NPC's gag from what everyone else has chosen."""

    def __init__(self, battle, air):
        self.battle = battle
        self.air = air
        self.suits = [s for s in battle.activeSuits if s.getHP() > 0]
        # Level 7 gags only in a big fight.
        self.uberOk = (len([s for s in self.suits if s.getActualLevel() >= UBER_LEVEL]) >= UBER_COUNT or
                       any(s.getActualLevel() >= UBER_ONE for s in self.suits))
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

    def playerTracks(self):
        return set(a[1] for a in self.attacks if not isNPC(a[0]))

    def playerTargets(self):
        return set(a[3] for a in self.attacks if not isNPC(a[0]) and a[3] not in (-1, None))

    # Gags the NPC has.

    def has(self, npc, track, level):
        return npc.hasTrackAccess(track) and npc.inventory.numItem(track, level) > 0

    def levels(self, npc, track, group=None, uber=False):
        levels = [l for l in range(MAX_LEVEL_INDEX + 1) if self.has(npc, track, l)]
        if not (self.uberOk or uber):
            levels = [l for l in levels if l < MAX_LEVEL_INDEX]
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
            if track == FIRE:
                # Fired: gone before anyone else's gag lands.
                if target in hp:
                    hp[target] = 0
                continue
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
        if SOUND in self.playerTracks():
            # The player sounds, so every NPC sounds with them.
            levels = self.levels(npc, SOUND) or self.levels(npc, SOUND, uber=True)
            if levels:
                wanted = max(a[2] for a in self.attacks if a[1] == SOUND and not isNPC(a[0]))
                return (SOUND, self.closestLevel(levels, wanted), -1)
        track, level, target = (self.chooseHeal(npc) or self.chooseLure(npc) or self.chooseAttack(npc)
                                or (PASS, -1, -1))
        if track == PASS and not self.uberOk:
            # Nothing else left: a level 7 gag, rather than nothing.
            self.uberOk = True
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
            if ratio < (HEAL_BELOW if isNPC(toon) else PLAYER_HEAL_BELOW):
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
            return (LURE, self.lureFor(groupLevels, candidates), -1)
        singleLevels = self.levels(npc, LURE, group=False) or groupLevels
        if not singleLevels:
            return None
        playerTargets = [t for (toon, track, level, t) in self.attacks if not isNPC(toon) and track in DAMAGE_TRACKS]
        for choice in trapped + playerTargets + candidates:
            if choice in candidates:
                level = self.lureFor(singleLevels, [choice])
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
                wanted = reference[1] if reference and reference[0] == SOUND else self.biggest(levels)
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

    def lureFor(self, levels, targets):
        # A lure as big as those cogs need, and no bigger: weak cogs (the
        # rest, while a big one is fired) get a small one.
        cogLevel = max([s.getActualLevel() for s in self.suits if s.doId in targets] or [1])
        wanted = min(MAX_LEVEL_INDEX - 1, max(0, cogLevel // 2 - 1))
        enough = [l for l in levels if l >= wanted]
        return min(enough) if enough else self.biggest(levels)

    def biggest(self, levels):
        # The biggest gag, but a level 7 one only when nothing else is left.
        lower = [l for l in levels if l < MAX_LEVEL_INDEX]
        return max(lower or levels)

    def closestLevel(self, levels, wanted):
        below = [l for l in levels if l <= wanted]
        return max(below) if below else min(levels)
