"""Plays the NPC players' part in the trolley games and the gag shop after.

Each trolley game waits on every toon's client, and most games score what
each client says its toon did: a fruit caught, a treasure grabbed, a ring
swum through. This says it for the NPCs, at the pace a decent player would
manage, and moves their toons about so the player sees them play.

The NPCs see the game the way their client would: through the player's
client, which offline runs in the same process and holds the same game.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from panda3d.core import Point3, Vec3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.minigame import DistributedMinigameAI as MinigameAI
from toontown.minigame import CannonGameGlobals, CatchGameGlobals, CogThiefGameGlobals
from toontown.minigame import PatternGameGlobals, PhotoGameGlobals, RaceGameGlobals, TugOfWarGameGlobals
from toontown.minigame import VineGameGlobals, ToonBlitzGlobals, TravelGameGlobals
from toontown.cogdominium import CogdoFlyingGameGlobals, CogdoMazeGameGlobals
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.minigame.DistributedMinigameAI import DistributedMinigameAI
from toontown.minigame.CatchGameGlobals import Name2DropObjectType
from toontown.shtiker import PurchaseManagerConstants as Purchase
from toontown.shtiker.PurchaseManagerAI import PurchaseManagerAI

TICK = 0.1
RUN_SPEED = 14.0


def isNPC(av):
    return av is not None and getattr(av, 'isNPCPlayer', lambda: False)()


def clientSend(npc, obj, field, *args):
    """Sends a field update as the NPC's client would: to the AI's handler
    if the AI hears it, and on to the other clients if it is broadcast."""
    dcField = obj.dclass.getFieldByName(field)
    if dcField is None:
        raise KeyError(field)
    if dcField.isBroadcast():
        obj.sendUpdate(field, list(args))
    if dcField.isAirecv():
        return npc.asSender(getattr(obj, field), *args)


class NPCMinigames:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCMinigames')

    def __init__(self, manager):
        self.manager = manager
        self.air = manager.air
        self.players = {}
        self.taskName = 'npcMinigames'
        taskMgr.doMethodLater(TICK, self.__tick, self.taskName)

    def destroy(self):
        taskMgr.remove(self.taskName)
        self.players = {}

    def __tick(self, task):
        try:
            self.update()
        except Exception:
            self.notify.warning('minigame tick failed')
            import traceback
            traceback.print_exc()
        return Task.again

    def update(self):
        members = [npc for npc in self.manager.party.members if not npc.isDeleted()]
        if not members:
            self.players = {}
            return
        byZone = {}
        for npc in members:
            byZone.setdefault(npc.zoneId, []).append(npc)
        live = set()
        for obj in list(self.air.doId2do.values()):
            npcs = byZone.get(getattr(obj, 'zoneId', None))
            if not npcs:
                continue
            if isinstance(obj, DistributedMinigameAI):
                for npc in npcs:
                    if npc.doId not in obj.avIdList:
                        continue
                    key = (obj.doId, npc.doId)
                    live.add(key)
                    player = self.players.get(key)
                    if player is None:
                        player = self.players[key] = makePlayer(self, npc, obj)
                    player.tick(globalClock.getFrameTime())
            elif isinstance(obj, DistCogdoGameAI):
                for npc in npcs:
                    if npc.doId not in obj.toons:
                        continue
                    key = (obj.doId, npc.doId)
                    live.add(key)
                    player = self.players.get(key)
                    if player is None:
                        cls = COGDO_PLAYERS.get(type(obj).__name__, CogdoPlayer)
                        player = self.players[key] = cls(self, npc, obj)
                    player.tick(globalClock.getFrameTime())
            elif isinstance(obj, PurchaseManagerAI):
                for npc in npcs:
                    self.shop(npc, obj)
        for key in list(self.players):
            if key not in live:
                del self.players[key]

    # --- The gag shop ---

    def shop(self, npc, manager):
        if npc.doId not in manager.playerIds:
            return
        if getattr(manager, 'npcLogged', None) is None:
            manager.npcLogged = True
            self.notify.info('minigame %s points: %s' % (manager.previousMinigameId,
                             dict(zip(manager.playerIds, manager.minigamePoints))))
        index = manager.playerIds.index(npc.doId)
        players = [i for i, avId in enumerate(manager.playerIds)
                   if avId > 3 and not isNPC(self.air.doId2do.get(avId))]
        if manager.receivingButtons and manager.playerStates[index] == Purchase.PURCHASE_WAITING_STATE:
            # Do what the player does: play again with them, or leave.
            states = [manager.playerStates[i] for i in players]
            if Purchase.PURCHASE_PLAYAGAIN_STATE in states:
                npc.asSender(manager.requestPlayAgain)
            elif not states or Purchase.PURCHASE_EXIT_STATE in states or Purchase.PURCHASE_DISCONNECTED_STATE in states:
                npc.asSender(manager.requestExit)
        elif not manager.receivingButtons and manager.playersReported[index] == Purchase.PURCHASE_UNREPORTED_STATE:
            # A full set of gags, bought with the beans just won.
            npc.restock()
            npc.asSender(manager.setInventory, npc.inventory.makeNetString(), npc.getMoney(), 1)


def makePlayer(minigames, npc, game):
    cls = PLAYERS.get(type(game).__name__, GamePlayer)
    return cls(minigames, npc, game)


class GamePlayer:
    """One NPC in one trolley game. This much is the same in every game:
    joining, being ready after the rules, and leaving at the end."""

    def __init__(self, minigames, npc, game):
        self.minigames = minigames
        self.air = minigames.air
        self.npc = npc
        self.game = game
        self.nextAt = {}
        self.memo = {}

    # --- What the NPC's client would know ---

    def client(self):
        base = getClientBuiltin('base')
        return base.cr.doId2do.get(self.game.doId) if base else None

    def players(self):
        return [avId for avId in self.game.avIdList if not isNPC(self.air.doId2do.get(avId))]

    def npcs(self):
        return [avId for avId in self.game.avIdList if isNPC(self.air.doId2do.get(avId))]

    def playerPos(self):
        base = getClientBuiltin('base')
        for avId in self.players():
            toon = base.cr.doId2do.get(avId) if base else None
            if toon is not None and not toon.isEmpty():
                return toon.getPos(base.render)
        return None

    def gameTime(self):
        return self.game.getCurrentGameTime()

    def gameState(self):
        fsm = getattr(self.game, 'gameFSM', None)
        state = fsm.getCurrentState() if fsm is not None else None
        return state.getName() if state is not None else None

    def send(self, field, *args):
        stats = self.minigames.manager.stats
        key = 'minigame %s' % type(self.game).__name__
        stats[key] = stats.get(key, 0) + 1
        return clientSend(self.npc, self.game, field, *args)

    def after(self, key, delay, now):
        # True once, `delay` seconds after the first time it is asked.
        when = self.nextAt.get(key)
        if when is None:
            self.nextAt[key] = now + (random.uniform(*delay) if isinstance(delay, tuple) else delay)
            return False
        if when is False or now < when:
            return False
        self.nextAt[key] = False
        return True

    def moveTo(self, pos, h=None, speed=RUN_SPEED, dt=TICK, flat=True):
        # A step toward pos, as the toon's client would send it. Swimmers
        # (flat=False) move up and down at the same pace.
        cur = self.npc.getPos()
        delta = Vec3(pos) - cur
        if flat:
            delta.setZ(0)
        distance = delta.length()
        if h is None:
            h = -math.degrees(math.atan2(delta[0], delta[1])) if distance > 0.1 else self.npc.getH()
        if distance <= speed * dt:
            step = Point3(pos[0], pos[1], pos[2])
        else:
            delta.normalize()
            step = cur + delta * speed * dt
            if flat:
                step.setZ(pos[2])
        # Each game animates the toons itself, from how they move.
        self.npc.moveTo(step[0], step[1], step[2], h)
        return distance <= speed * dt

    # --- The framework ---

    def tick(self, now):
        game = self.game
        state = game.frameworkFSM.getCurrentState()
        state = state.getName() if state else None
        mine = game.stateDict.get(self.npc.doId)
        players = [game.stateDict.get(avId) for avId in self.players()]
        if state == 'frameworkWaitClientsJoin':
            if mine == MinigameAI.EXPECTED and all(s in (MinigameAI.JOINED, MinigameAI.READY) for s in players):
                npcSend(self, game.setAvatarJoined)
        elif state == 'frameworkWaitClientsReady':
            # Everyone reads the rules; the NPCs are done when the player is.
            if mine != MinigameAI.READY and all(s == MinigameAI.READY for s in players):
                npcSend(self, game.setAvatarReady)
        elif state == 'frameworkGame':
            self.play(now)
            self.answerDone()
        elif state == 'frameworkWaitClientsExit':
            if mine != MinigameAI.EXITED and all(s == MinigameAI.EXITED for s in players):
                npcSend(self, game.setAvatarExited)

    def play(self, now):
        pass

    def answerDone(self):
        # Games that end when every client says its toon is done wait for
        # the player's client, then the NPCs'.
        barrier = getattr(self.game, 'doneBarrier', None)
        if barrier is None or not hasattr(self.game, 'reportDone'):
            return
        if self.npc.doId in barrier.pendingToons and not [p for p in self.players() if p in barrier.pendingToons]:
            self.send('reportDone')


def npcSend(player, method, *args):
    return player.npc.asSender(method, *args)


# --- The board games ---

class RacePlayer(GamePlayer):
    """The race: pick a card each turn, a different one from the others."""

    def play(self, now):
        game = self.game
        if self.gameState() != 'waitClientsChoices' or game.avatarChoices.get(self.npc.doId, -1) != -1:
            self.nextAt.pop('choose', None)
            return
        if not self.after('choose', (2.0, 5.0), now):
            return
        taken = set(game.avatarChoices.values())
        choices = [c for c in RaceGameGlobals.ValidChoices if c > 0 and c not in taken] or \
                  [c for c in RaceGameGlobals.ValidChoices if c > 0]
        self.send('setAvatarChoice', random.choice(choices))


class TravelPlayer(GamePlayer):
    """The Trolley Tracks board: vote some beans for a way to go."""

    def play(self, now):
        game = self.game
        choice = game.avatarChoices.get(self.npc.doId)
        if self.gameState() != 'waitClientsChoices' or choice not in (None, (-1, 0), -1):
            self.nextAt.pop('vote', None)
            return
        if not self.after('vote', (3.0, 7.0), now):
            return
        votes = game.currentVotes.get(self.npc.doId, 0)
        spend = random.randint(0, max(0, votes // 3))
        self.send('setAvatarChoice', spend, random.randrange(TravelGameGlobals.MaxDirections))


class PatternPlayer(GamePlayer):
    """Match: watch the dance, then press it back."""
    ACCURACY = 0.9

    def play(self, now):
        game = self.game
        state = self.gameState()
        if state == 'waitClientsReady':
            self.memo.pop('presses', None)
            if self.npc.doId not in game.readyClients and all(p in game.readyClients for p in self.players()):
                self.send('reportPlayerReady')
        elif state == 'waitForResults':
            index = game.avIdList.index(self.npc.doId)
            if game.results[index] is not None:
                return
            presses = self.memo.get('presses')
            if presses is None:
                pattern = list(game.pattern)
                if random.random() > self.ACCURACY:
                    wrong = random.randrange(len(pattern))
                    pattern[wrong] = (pattern[wrong] + random.randint(1, 3)) % 4
                # Watching the pattern, then a press every half second.
                start = now + len(pattern) * 0.6 + random.uniform(1.0, 2.0)
                presses = self.memo['presses'] = [pattern, start, 0]
            pattern, start, done = presses
            if done < len(pattern) and now >= start + done * random.uniform(0.35, 0.6):
                wrong = int(pattern[done] != game.pattern[done]) if done < len(game.pattern) else 1
                self.send('reportButtonPress', pattern[done], wrong)
                presses[2] = done + 1
                if wrong:
                    # A wrong press ends the turn.
                    pattern[:] = pattern[:done + 1]
            if presses[2] >= len(pattern):
                self.send('reportPlayerPattern', pattern, min(now - start + 0.5, PatternGameGlobals.InputTime))


class TugPlayer(GamePlayer):
    """Tug-of-war: keep tapping at the rate the meter asks for."""

    def play(self, now):
        game = self.game
        client = self.client()
        state = self.gameState()
        if client is None or not hasattr(client, 'sides') or self.npc.doId not in client.sides:
            return
        if state == 'waitClientsReady':
            if self.npc.doId not in game.readyClients and self.npc.doId not in game.side:
                self.send('reportPlayerReady', client.sides[self.npc.doId])
        elif state == 'waitForResults':
            if not self.after('report', TugOfWarGameGlobals.SEND_UPDATE, now):
                return
            self.nextAt.pop('report')
            ideal = getattr(client, 'idealRate', 2.0)
            keyRate = max(0, int(round(random.gauss(ideal + 0.5, 0.7))))
            stdDev = 0.25 * ideal
            advantage = getattr(client, 'advantage', 1.0)
            force = advantage * (4 + 0.4 * ideal) * math.exp(-(keyRate - ideal) ** 2 / (2.0 * stdDev ** 2))
            self.send('reportCurrentKeyRate', keyRate, force)


class IcePlayer(GamePlayer):
    """Ice slide: aim the tire at the middle and push about the right amount."""

    def play(self, now):
        game = self.game
        client = self.client()
        state = self.gameState()
        if state == 'waitClientsChoices':
            if game.avatarChoices.get(self.npc.doId, (-1, 0))[0] != -1:
                return
            if not self.after(('aim', game.curMatch, game.curRound), (3.0, 7.0), now):
                return
            pos = Point3(0, 0, 0)
            if client is not None and self.npc.doId in getattr(client, 'tireDict', {}):
                pos = Point3(client.tireDict[self.npc.doId]['tireBody'].getPosition())
            heading = math.degrees(math.atan2(pos[0], -pos[1])) + random.gauss(0, 6)
            distance = Vec3(pos[0], pos[1], 0).length()
            force = max(15, min(100, distance * 2.6 + random.gauss(0, 8)))
            self.send('setForceArrowInfo', self.npc.doId, heading, force)
            self.send('setAvatarChoice', force, heading)
        elif state == 'waitEndingPositions':
            # Every client works out where the tires stop; the NPC agrees
            # with the player's.
            ending = game.avatarEndingPositions
            if self.npc.doId not in ending:
                theirs = [ending[p] for p in self.players() if p in ending]
                if theirs:
                    self.send('endingPositions', theirs[0])
        elif state == 'scoreMatch':
            barrier = game.scoringMovieDoneBarrier
            if barrier and self.npc.doId in barrier.pendingToons and \
                    not [p for p in self.players() if p in barrier.pendingToons]:
                self.send('reportScoringMovieDone')


# --- Games on a timer ---

class CatchPlayer(GamePlayer):
    """Catching fruit: run under the next one coming down, not the anvils."""
    CATCH_CHANCE = 0.85

    def play(self, now):
        game = self.game
        client = self.client()
        if self.gameState() != 'play' or client is None or not hasattr(client, 'dropSchedule'):
            return
        schedule = self.memo.get('schedule')
        if schedule is None:
            # The whole drop schedule, before the client starts using it up.
            if not client.dropSchedule:
                return
            schedule = self.memo['schedule'] = [(t, name, client.grid2world(*coords)) for t, name, coords in client.dropSchedule]
        t = self.gameTime()
        target = self.memo.get('target')
        if target is not None:
            objNum, landT, pos, good = target
            arrived = self.moveTo(Point3(pos[0], pos[1], 0))
            if t >= landT:
                del self.memo['target']
                if arrived and objNum < len(game.caughtList) and not game.caughtList[objNum] \
                        and random.random() < self.CATCH_CHANCE:
                    self.send('claimCatch', objNum, CatchGameGlobals.Name2DOTypeId[schedule[objNum][1]])
            return
        claimed = set(p.memo.get('target', (None,))[0] for p in self.minigames.players.values() if p.game is game)
        here = self.npc.getPos()
        playerPos = self.playerPos()
        best = None
        for objNum, (dropT, name, pos) in enumerate(schedule):
            if not Name2DropObjectType[name].good or objNum in claimed:
                continue
            landT = dropT + Name2DropObjectType[name].fallDuration
            if landT <= t + 0.3 or landT > t + 6:
                continue
            if objNum < len(game.caughtList) and game.caughtList[objNum]:
                continue
            spot = Point3(pos[0], pos[1], 0)
            if playerPos is not None and (spot - Point3(playerPos[0], playerPos[1], 0)).length() < 4:
                # The player's fruit.
                continue
            runTime = (spot - here).length() / RUN_SPEED
            if runTime > landT - t:
                continue
            if best is None or landT < best[1]:
                best = (objNum, landT, pos, True)
        if best is not None:
            self.memo['target'] = best


class MazePlayer(GamePlayer):
    """The maze: walk the corridors to the nearest treasure left."""

    def play(self, now):
        game = self.game
        client = self.client()
        if self.gameState() != 'play' or client is None or not hasattr(client, 'maze') or not hasattr(client, 'treasures'):
            return
        maze = client.maze
        path = self.memo.get('path')
        if path:
            if self.moveTo(Point3(path[0][0], path[0][1], 0), speed=getattr(client, 'TOON_SPEED', 8.0) * 0.9):
                path.pop(0)
            if not path:
                treasure = self.memo.pop('treasure')
                if not game.takenTable[treasure]:
                    self.send('claimTreasure', treasure)
            return
        here = self.npc.getPos()
        start = maze.world2tileClipped(here[0], here[1])
        goals = {}
        for i, pos in enumerate(maze.treasurePosList):
            if not game.takenTable[i]:
                goals[tuple(maze.world2tileClipped(pos[0], pos[1]))] = i
        others = set(p.memo.get('treasure') for p in self.minigames.players.values() if p.game is game and p is not self)
        route = self.bfs(maze, tuple(start), dict((k, v) for k, v in goals.items() if v not in others) or goals)
        if route:
            tiles, treasure = route
            self.memo['treasure'] = treasure
            self.memo['path'] = [maze.tile2world(*tile) for tile in tiles[1:]] + [maze.treasurePosList[treasure]]

    def bfs(self, maze, start, goals):
        if not goals:
            return None
        frontier = [start]
        came = {start: None}
        while frontier:
            nextFrontier = []
            for tile in frontier:
                if tile in goals:
                    route = []
                    while tile is not None:
                        route.append(tile)
                        tile = came[tile]
                    route.reverse()
                    return route, goals[route[-1]]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (tile[0] + dx, tile[1] + dy)
                    if n not in came and maze.isWalkable(n[0], n[1]):
                        came[n] = tile
                        nextFrontier.append(n)
            frontier = nextFrontier
        return None


class TagPlayer(GamePlayer):
    """Tag: grab treasures and keep away from It; when It, chase someone."""
    ARENA = 42.0

    def play(self, now):
        game = self.game
        if self.gameState() != 'play':
            return
        base = getClientBuiltin('base')
        here = self.npc.getPos()
        toons = {}
        for avId in game.avIdList:
            av = self.air.doId2do.get(avId)
            if avId == self.npc.doId or av is None:
                continue
            client = base.cr.doId2do.get(avId) if base else None
            toons[avId] = client.getPos(base.render) if client is not None and not client.isEmpty() else av.getPos()
        if game.itAvId == self.npc.doId:
            if not toons:
                return
            target, pos = min(toons.items(), key=lambda kv: (kv[1] - here).length())
            self.moveTo(Point3(pos[0], pos[1], 0), speed=RUN_SPEED * 1.05)
            if (pos - here).length() < 3.0 and game.tagBack:
                self.send('tag', target)
            return
        itPos = toons.get(game.itAvId)
        if itPos is not None and (itPos - here).length() < 18:
            away = here - itPos
            away.setZ(0)
            if away.length() < 0.1:
                away = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), 0)
            away.normalize()
            spot = here + away * 10
            if Vec3(spot[0], spot[1], 0).length() > self.ARENA:
                spot = Point3(-spot[1], spot[0], 0) * 0.6
            self.moveTo(Point3(spot[0], spot[1], 0))
            return
        treasure = self.nearestTreasure(here)
        if treasure is not None:
            pos = Point3(*treasure.getPosition())
            if self.moveTo(Point3(pos[0], pos[1], 0)):
                self.npc.asSender(treasure.requestGrab)

    def nearestTreasure(self, here):
        best = None
        for obj in list(self.air.doId2do.values()):
            if obj.zoneId == self.game.zoneId and type(obj).__name__.endswith('TreasureAI') and hasattr(obj, 'requestGrab'):
                distance = (Point3(*obj.getPosition()) - here).length()
                if best is None or distance < best[0]:
                    best = (distance, obj)
        return best[1] if best else None


class RingPlayer(GamePlayer):
    """Swimming through rings: one ring group after another, alongside the player."""
    SUCCESS = 0.85

    def play(self, now):
        game = self.game
        if self.gameState() != 'swimming':
            return
        progress = game._DistributedRingGameAI__nextRingGroup
        mine = progress.get(self.npc.doId, 0)
        theirs = [progress.get(p, 0) for p in self.players()]
        if theirs and mine < min(theirs) and self.after(('ring', mine), (0.1, 0.6), now):
            self.send('setToonGotRing', int(random.random() < self.SUCCESS))
        pos = self.playerPos()
        if pos is not None:
            offset = (self.npcs().index(self.npc.doId) + 1) * (4 if self.npcs().index(self.npc.doId) % 2 else -4)
            self.moveTo(Point3(pos[0] + offset, pos[1], pos[2]), h=0, speed=30)


class CannonPlayer(GamePlayer):
    """The cannon game: aim, fire, and learn from the misses."""

    def play(self, now):
        client = self.client()
        if self.gameState() != 'play' or client is None or self.npc.doId not in getattr(client, 'cannonDict', {}):
            return
        if not self.after(('shot', self.memo.get('shots', 0)), (4.0, 8.0) if self.memo.get('shots') else (5.0, 9.0), now):
            return
        shots = self.memo['shots'] = self.memo.get('shots', 0) + 1
        hit = self.findHit(client)
        zRot, angle = hit if hit else (random.uniform(-20, 20), random.uniform(30, 60))
        if hit and random.random() > min(0.9, 0.3 + 0.25 * shots):
            # Not quite yet.
            zRot += random.choice((-1, 1)) * random.uniform(2, 5)
            angle += random.choice((-1, 1)) * random.uniform(2, 5)
        zRot = max(CannonGameGlobals.CANNON_ROTATION_MIN, min(CannonGameGlobals.CANNON_ROTATION_MAX, zRot))
        angle = max(CannonGameGlobals.CANNON_ANGLE_MIN, min(CannonGameGlobals.CANNON_ANGLE_MAX, angle))
        self.send('setCannonPosition', zRot, angle)
        self.send('setCannonLit', zRot, angle)
        fireTime = self.game.getCurrentGameTime() + CannonGameGlobals.FUSE_TIME
        impact, water = self.flight(client, zRot, angle, fireTime)
        if water:
            self.send('setToonWillLandInWater', impact)

    def flight(self, client, zRot, angle, launchTime):
        old = list(client.cannonPositionDict[self.npc.doId])
        client.cannonPositionDict[self.npc.doId] = [zRot, angle]
        client._DistributedCannonGame__updateCannonPosition(self.npc.doId)
        try:
            results = client._DistributedCannonGame__calcFlightResults(self.npc.doId, launchTime)
        finally:
            client.cannonPositionDict[self.npc.doId] = old
            client._DistributedCannonGame__updateCannonPosition(self.npc.doId)
        return results[4], results[5] == client.HIT_WATER

    def findHit(self, client):
        found = self.memo.get('hit')
        if found:
            return found
        for zRot in range(CannonGameGlobals.CANNON_ROTATION_MIN, CannonGameGlobals.CANNON_ROTATION_MAX + 1):
            for angle in range(CannonGameGlobals.CANNON_ANGLE_MIN, CannonGameGlobals.CANNON_ANGLE_MAX + 1):
                if self.flight(client, zRot, angle, 0)[1]:
                    self.memo['hit'] = (zRot + 0.5, angle + 0.5) if self.flight(client, zRot + 0.5, angle + 0.5, 0)[1] \
                        else (zRot, angle)
                    return self.memo['hit']
        return None


class PairingPlayer(GamePlayer):
    """Matching cards: turn up a card, and remember what it was."""

    def play(self, now):
        game = self.game
        client = self.client()
        if self.gameState() != 'play':
            return
        seen = self.memo.setdefault('seen', {})
        # Every card turned up is seen by all.
        for cards in game.faceUpDict.values():
            for index in cards:
                seen[index] = game.cards[index].rank
        done = set(game.inactiveList)
        if len(done) >= len(game.cards):
            return
        if not self.after(('flip', game.flips), (1.6, 3.2), now):
            return
        faceUp = [c for cards in game.faceUpDict.values() for c in cards]
        choice = None
        for up in faceUp:
            match = [i for i, rank in seen.items() if rank == game.cards[up].rank and i != up and i not in done and i not in faceUp]
            if match and random.random() < 0.9:
                choice = match[0]
                break
        if choice is None:
            pairs = {}
            for i, rank in seen.items():
                if i not in done and i not in faceUp:
                    pairs.setdefault(rank, []).append(i)
            known = [cards for cards in pairs.values() if len(cards) > 1]
            if known and random.random() < 0.8:
                choice = known[0][0]
            else:
                unseen = [i for i in range(len(game.cards)) if i not in seen and i not in done and i not in faceUp]
                choice = random.choice(unseen) if unseen else None
        if choice is None:
            return
        glow = getattr(client, 'bonusGlowCard', 0) if client is not None else 0
        self.send('openCardRequest', choice, glow)



class TargetPlayer(GamePlayer):
    """Toon Slingshot: aim for a target worth something, each round."""

    def play(self, now):
        game = self.game
        if self.gameState() != 'fly' or not game.barrierScore or self.npc.doId not in game.barrierScore.pendingToons:
            return
        if not self.after(('fly', game.round), (6.0, 14.0), now):
            return
        targets = list(game.targetsPlaced)
        if targets and random.random() < 0.8:
            x, y, kind = max(random.sample(targets, min(3, len(targets))), key=lambda t: game.targetValue[t[2]])
            spread = game.targetSize[kind] * 0.8
            x += random.uniform(-spread, spread)
            y += random.uniform(-spread, spread)
        else:
            x, y = random.uniform(-60, 60), random.uniform(50, 300)
        self.send('setScore', int(x), int(y))
        self.send('setPlayerDone')


class PhotoPlayer(GamePlayer):
    """Photo fun: take the pictures asked for, some better than others."""

    def play(self, now):
        game = self.game
        if self.gameState() != 'play':
            return
        index = game.avIdList.index(self.npc.doId)
        if game.filmCountList[index] >= game.data['FILMCOUNT']:
            return
        if not self.after(('photo', game.filmCountList[index]), (3.0, 7.0), now):
            return
        subject, pose = random.choice(game.assignmentData)[:2]
        score = round(random.uniform(1.0, PhotoGameGlobals.NUMSTARS), 2)
        self.send('newClientPhotoScore', subject, pose, score)


class VinePlayer(GamePlayer):
    """Jungle vines: swing from vine to vine to the end."""

    def play(self, now):
        game = self.game
        if self.gameState() != 'play':
            return
        info = game.toonInfo.get(self.npc.doId)
        vine = info[0] if info else 0
        if vine >= VineGameGlobals.NumVines - 1:
            return
        # About the pace that gets a good player to the end in time.
        pace = VineGameGlobals.GameDuration * 0.8 / VineGameGlobals.NumVines
        if not self.after(('vine', vine), (pace * 0.6, pace * 1.3), now):
            return
        self.send('setNewVine', self.npc.doId, vine + 1, 0.5, 1)


class CogThiefPlayer(GamePlayer):
    """Cog thief: throw pies at the cogs going for the barrels."""
    HIT_CHANCE = 0.7

    def play(self, now):
        game = self.game
        client = self.client()
        if self.gameState() != 'play' or client is None or not hasattr(client, 'cogInfo'):
            return
        base = getClientBuiltin('base')
        here = self.npc.getPos()
        best = None
        for cogIndex, info in client.cogInfo.items():
            cog = info.get('suit')
            if cog is None or cog.suit is None:
                continue
            pos = cog.suit.getPos(base.render)
            if abs(pos[0]) > CogThiefGameGlobals.StageHalfWidth + 8 or abs(pos[1]) > CogThiefGameGlobals.StageHalfHeight + 8:
                continue
            distance = (pos - here).length()
            # The ones carrying a barrel off come first.
            score = distance - (30 if game.cogInfo[cogIndex]['barrel'] >= 0 else 0)
            if best is None or score < best[0]:
                best = (score, cogIndex, pos, distance)
        if best is None:
            self.moveTo(Point3(random.uniform(-5, 5), random.uniform(-5, 5), 0), speed=CogThiefGameGlobals.ToonSpeed)
            return
        _, cogIndex, pos, distance = best
        if distance > 14:
            self.moveTo(Point3(pos[0], pos[1], 0), speed=CogThiefGameGlobals.ToonSpeed)
            return
        if not self.after(('throw', self.memo.get('throws', 0)), (0.8, 1.6), now):
            return
        self.memo['throws'] = self.memo.get('throws', 0) + 1
        delta = pos - here
        heading = -math.degrees(math.atan2(delta[0], delta[1]))
        self.npc.moveTo(here[0], here[1], here[2], heading)
        stamp = globalClockDelta.localToNetworkTime(globalClock.getFrameTime(), bits=32)
        self.send('throwingPie', self.npc.doId, stamp, heading, here[0], here[1], here[2])
        if random.random() < self.HIT_CHANCE:
            self.send('pieHitSuit', self.npc.doId, stamp, cogIndex, pos[0], pos[1], pos[2])


class TwoDPlayer(GamePlayer):
    """Toon Blitz: run the course with the player, grabbing treasures and
    shooting the enemies on the way."""

    def play(self, now):
        game = self.game
        if self.gameState() != 'play':
            return
        duration = ToonBlitzGlobals.GameDuration[game.getSafezoneId()]
        sections = len(game.sectionsSelected)
        progress = min(sections, self.gameTime() / (duration * 0.85) * sections)
        if self.after(('claim', int(self.gameTime() / 3)), (0.5, 2.5), now):
            reached = [s for s in range(sections) if s < progress]
            if reached:
                section = random.choice(reached[-2:])
                if random.random() < 0.6:
                    left = [i for i, taken in enumerate(game.treasureTakenTable[section]) if not taken]
                    if left:
                        self.send('claimTreasure', section, random.choice(left))
                else:
                    alive = [i for i, health in enumerate(game.enemyHealthTable[section]) if health > 0]
                    if alive:
                        self.send('showShootGun', self.npc.doId, globalClockDelta.getFrameNetworkTime())
                        self.send('claimEnemyShot', section, random.choice(alive))
        if progress >= sections and not self.memo.get('won'):
            self.memo['won'] = True
            self.send('toonVictory', self.npc.doId, globalClockDelta.getFrameNetworkTime())
        pos = self.playerPos()
        if pos is not None:
            offset = -3 * (self.npcs().index(self.npc.doId) + 1)
            self.moveTo(Point3(pos[0] + offset, pos[1], pos[2]))


class DivingPlayer(GamePlayer):
    """Treasure dive: down to a chest, back up to the boat with it."""
    BOAT_Z = -2.0

    def play(self, now):
        game = self.game
        client = self.client()
        if self.gameState() != 'swimming' or client is None or not getattr(client, 'treasures', None):
            return
        holding = self.npc.doId in game.treasureHolders
        if holding:
            if self.moveTo(Point3(random.uniform(-2, 2), 0, self.BOAT_Z), h=0, speed=8.0, flat=False):
                self.send('treasureRecovered')
            return
        target = self.memo.get('chest')
        if target is None or game.treasureHolders[target]:
            free = [i for i, holder in enumerate(game.treasureHolders) if not holder]
            if not free:
                return
            here = self.npc.getPos()
            target = self.memo['chest'] = min(free, key=lambda i: abs(client.treasures[i].treasureNode.getX() - here[0]))
        node = client.treasures[target].treasureNode
        if self.moveTo(Point3(node.getX(), 0, node.getZ() + 1), h=0, speed=8.0, flat=False):
            self.send('pickupTreasure', target)
            self.memo.pop('chest', None)


PLAYERS = {
    'DistributedRaceGameAI': RacePlayer,
    'DistributedTravelGameAI': TravelPlayer,
    'DistributedPatternGameAI': PatternPlayer,
    'DistributedTugOfWarGameAI': TugPlayer,
    'DistributedIceGameAI': IcePlayer,
    'DistributedCatchGameAI': CatchPlayer,
    'DistributedMazeGameAI': MazePlayer,
    'DistributedTagGameAI': TagPlayer,
    'DistributedRingGameAI': RingPlayer,
    'DistributedCannonGameAI': CannonPlayer,
    'DistributedPairingGameAI': PairingPlayer,
    'DistributedTargetGameAI': TargetPlayer,
    'DistributedPhotoGameAI': PhotoPlayer,
    'DistributedVineGameAI': VinePlayer,
    'DistributedCogThiefGameAI': CogThiefPlayer,
    'DistributedTwoDGameAI': TwoDPlayer,
    'DistributedDivingGameAI': DivingPlayer,
}


# --- The field office games ---

class CogdoPlayer(GamePlayer):
    """One NPC in a field office game: ready after the rules, as the
    player is, then playing its part."""

    def players(self):
        return [avId for avId in self.game.toons if not isNPC(self.air.doId2do.get(avId))]

    def npcs(self):
        return [avId for avId in self.game.toons if isNPC(self.air.doId2do.get(avId))]

    def gameTime(self):
        return globalClock.getRealTime() - (self.game.startTime or 0)

    def tick(self, now):
        game = self.game
        if game.finished or self.npc.doId in game.sadToons:
            return
        if not game.started:
            if self.npc.doId not in game.readyToons and all(p in game.readyToons for p in self.players()):
                npcSend(self, game.setAvatarReady)
            return
        self.play(now)

    def follow(self, spread=4.0):
        pos = self.playerPos()
        if pos is None:
            return
        index = self.npcs().index(self.npc.doId)
        angle = index * 2.1
        spot = Point3(pos[0] + spread * math.cos(angle), pos[1] + spread * math.sin(angle), pos[2])
        if (self.npc.getPos() - spot).length() > 1.5:
            self.moveTo(spot, flat=False)


class CogdoMazePlayer(CogdoPlayer):
    """The Sellbot maze: pick up memos, soak the big cogs with water
    coolers, and run for the exit once it opens."""

    def play(self, now):
        game = self.game
        client = self.client()
        self.follow()
        if game.doorOpen:
            if self.npc.doId not in game.toonsOut and self.after('exit', (2.0, 6.0), now):
                self.send('requestAction', CogdoMazeGameGlobals.GameActions.EnterDoor, 0)
            return
        if not self.after(('act', self.memo.get('acts', 0)), (3.0, 6.0), now):
            return
        self.memo['acts'] = self.memo.get('acts', 0) + 1
        bosses = [n for n in range(game.numSuits[0]) if n not in game.bossesDefeated]
        pickups = len(client.game.pickups) if client is not None and getattr(client, 'game', None) else 0
        free = [n for n in range(pickups) if n not in game.pickups]
        if bosses and random.random() < 0.55:
            here = self.npc.getPos()
            self.send('requestUseGag', here[0], here[1], self.npc.getH(), globalClockDelta.getRealNetworkTime(bits=16))
            if random.random() < 0.8:
                self.send('requestSuitHitByGag', CogdoMazeGameGlobals.SuitTypes.Boss, random.choice(bosses))
        elif free:
            self.send('requestPickUp', random.choice(free))


class CogdoFlyingPlayer(CogdoPlayer):
    """The Lawbot flight: fly along with the player picking up memos, and
    land on the far platform once the player is there."""

    def play(self, now):
        game = self.game
        client = self.client()
        Actions = CogdoFlyingGameGlobals.AI.GameActions
        self.follow(spread=6.0)
        players = self.players()
        if self.npc.doId not in game.landed:
            if players and all(p in game.landed for p in players) and self.after('land', (1.0, 4.0), now):
                self.send('requestAction', Actions.LandOnWinPlatform, 0)
            elif self.after(('memo', self.memo.get('memos', 0)), (4.0, 9.0), now):
                self.memo['memos'] = self.memo.get('memos', 0) + 1
                memo = self.freeMemo(client)
                if memo is not None:
                    self.send('requestPickUp', memo, CogdoFlyingGameGlobals.Level.GatherableTypes.Memo)
            return
        if self.npc.doId not in game.winDone and all(p in game.winDone for p in players):
            self.send('requestAction', Actions.WinStateFinished, 0)

    def freeMemo(self, client):
        level = getattr(getattr(client, 'game', None), 'level', None)
        if level is None:
            return None
        memos = [g.serialNum for quadrant in level.quadrants for g in quadrant.gatherables
                 if g.type == CogdoFlyingGameGlobals.Level.GatherableTypes.Memo and g.serialNum not in self.game.memoPickups]
        return random.choice(memos) if memos else None


COGDO_PLAYERS = {
    'DistCogdoMazeGameAI': CogdoMazePlayer,
    'DistCogdoFlyingGameAI': CogdoFlyingPlayer,
}
