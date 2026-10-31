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
from toontown.cogdominium import CogdoCraneGameConsts, CogdoFlyingGameGlobals, CogdoMazeGameGlobals
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
        self.dropPlayers(list(self.players))

    def dropPlayers(self, keys):
        for key in keys:
            player = self.players.pop(key, None)
            if player is not None and hasattr(player, 'destroy'):
                player.destroy()

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
            self.dropPlayers(list(self.players))
            return
        byZone = {}
        for npc in members:
            byZone.setdefault(npc.zoneId, []).append(npc)
        live = set()
        for obj in self.manager.party._objectsOfType((DistributedMinigameAI, DistCogdoGameAI, PurchaseManagerAI)):
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
        self.dropPlayers([key for key in self.players if key not in live])

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
    """The Sellbot maze, played as a toon would on its own: fill up with
    water at a cooler, find a big cog through the corridors and soak it,
    pick up the memos the cogs drop, and run for the exit once it opens.
    Each NPC picks its own cooler, cog and memo, so they spread out."""

    def play(self, now):
        game = self.game
        client = self.client()
        mazeGame = getattr(client, 'game', None) if client is not None else None
        maze = getattr(mazeGame, 'maze', None)
        if maze is None:
            return
        speed = Globals_ToonRunSpeed() * self.memo.setdefault('pace', random.uniform(0.85, 1.0))
        if game.doorOpen:
            if self.npc.doId in game.toonsOut:
                return
            if self.goTo(maze, ('exit',), maze.exitPos, speed) and self.after('exit', (0.3, 1.5), now):
                self.send('requestAction', CogdoMazeGameGlobals.GameActions.EnterDoor, 0)
            return
        here = self.npc.getPos()
        # Memos lying near by come first.
        memos = [(n, pickup.getPos(clientRender())) for n, pickup in enumerate(mazeGame.pickups)
                 if n not in game.pickups and not pickup.isEmpty()]
        memos = [m for m in memos if (m[1] - here).length() < 30 and not self.claimed(('memo', m[0]))]
        if memos:
            n, pos = min(memos, key=lambda m: (m[1] - here).length())
            if self.goTo(maze, ('memo', n), pos, speed, near=1.5):
                self.send('requestPickUp', n)
                self.memo.pop('goal', None)
            return
        bosses = [suit for suit in mazeGame.shakers if suit.serialNum not in game.bossesDefeated and not suit.suit.isEmpty()]
        if not bosses:
            self.wander(maze, speed, now)
            return
        if not self.memo.get('water'):
            coolers = maze.getWaterCoolers()
            if not coolers:
                return
            mine = self.memo.get('cooler')
            if mine is None or mine >= len(coolers):
                # The nearest cooler no other NPC is heading for, mostly;
                # now and then the next one.
                order = sorted(range(len(coolers)), key=lambda c: (coolers[c].getPos(clientRender()) - here).length())
                order = [c for c in order if not self.claimed(('cooler', c))] or order
                mine = order[0] if random.random() < 0.75 or len(order) == 1 else order[1]
                self.memo['cooler'] = mine
            cooler = coolers[mine]
            if self.goTo(maze, ('cooler', mine), cooler.getPos(clientRender()), speed, near=3.0):
                self.send('requestGag', cooler.serialNum)
                self.memo['water'] = 1
                self.memo.pop('cooler', None)
                self.memo.pop('goal', None)
            return
        # Small cogs close by get soaked too: they drop the memos.
        minion = self.nearMinion(mazeGame, here)
        if minion is not None:
            pos = minion.suit.getPos(clientRender())
            if (pos - here).length() > CogdoMazeGameGlobals.ThrowDistance * 0.7:
                self.goTo(maze, ('minion', minion.serialNum), Point3(pos[0], pos[1], 0), speed, near=3.0, replan=0.8)
                return
            if self.after(('throw', self.memo.get('throws', 0)), (0.2, 0.6), now):
                self.throwAt(here, pos, minion.type, minion.serialNum)
            return
        # Soak a big cog: each NPC keeps to the one it picked.
        target = self.memo.get('boss')
        if target not in [suit.serialNum for suit in bosses]:
            target = random.choice(bosses).serialNum
            self.memo['boss'] = target
        suit = [suit for suit in bosses if suit.serialNum == target][0]
        pos = suit.suit.getPos(clientRender())
        distance = (pos - here).length()
        if distance > CogdoMazeGameGlobals.ThrowDistance * 0.8:
            # Each NPC comes at the cog from its own side.
            side = self.memo.setdefault('side', random.uniform(0, 2 * math.pi))
            spot = Point3(pos[0] + 8.0 * math.cos(side), pos[1] + 8.0 * math.sin(side), 0)
            self.goTo(maze, ('boss', target), spot, speed, near=3.0, replan=1.0)
            return
        if not self.after(('throw', self.memo.get('throws', 0)), (0.3, 0.9), now):
            return
        self.throwAt(here, pos, CogdoMazeGameGlobals.SuitTypes.Boss, target)

    def throwAt(self, here, pos, suitType, suitNum):
        # Faces the cog and throws the balloon (every toon's client shows
        # the throw); most throws hit.
        self.memo['throws'] = self.memo.get('throws', 0) + 1
        delta = pos - here
        h = -math.degrees(math.atan2(delta[0], delta[1]))
        self.npc.moveTo(here[0], here[1], here[2], h)
        self.send('requestUseGag', here[0], here[1], h, globalClockDelta.getRealNetworkTime(bits=16))
        if random.random() < 0.8:
            self.send('requestSuitHitByGag', suitType, suitNum)
        self.memo['water'] = 0
        self.memo.pop('goal', None)

    def nearMinion(self, mazeGame, here):
        # The small cog it is after, or a new one near by (each NPC has
        # its own taste for them, and they don't all chase the same one).
        keen = self.memo.setdefault('keen', random.uniform(10.0, 22.0))
        minions = [suit for suit in mazeGame.suitsById.values()
                   if suit.type != CogdoMazeGameGlobals.SuitTypes.Boss and not suit.suit.isEmpty()
                   and getattr(suit, 'hp', 1) > 0]
        mine = self.memo.get('minion')
        for suit in minions:
            if suit.serialNum == mine and (suit.suit.getPos(clientRender()) - here).length() < keen * 1.6:
                return suit
        minions = [suit for suit in minions if not self.claimed(('minion', suit.serialNum))
                   and (suit.suit.getPos(clientRender()) - here).length() < keen]
        if not minions:
            self.memo.pop('minion', None)
            return None
        suit = min(minions, key=lambda m: (m.suit.getPos(clientRender()) - here).length())
        self.memo['minion'] = suit.serialNum
        return suit

    def claimed(self, goal):
        return any(p.memo.get('goal') == goal for p in self.minigames.players.values()
                   if p.game is self.game and p is not self)

    def wander(self, maze, speed, now):
        goal = self.memo.get('goal')
        if goal is None or goal[0] != 'wander':
            tile = (random.randrange(1, maze.width), random.randrange(1, maze.height))
            goal = ('wander', tile)
        pos = maze.tile2world(*goal[1])
        if self.goTo(maze, goal, Point3(pos[0], pos[1], 0), speed):
            self.memo.pop('goal', None)

    def goTo(self, maze, goal, pos, speed, near=2.0, replan=None):
        """A step along the corridors toward pos; True once there."""
        here = self.npc.getPos()
        if (Point3(pos[0], pos[1], 0) - Point3(here[0], here[1], 0)).length() <= near:
            return True
        now = globalClock.getRealTime()
        path = self.memo.get('path')
        if self.memo.get('goal') != goal or not path or (replan and now - self.memo.get('planned', 0) > replan):
            self.memo['goal'] = goal
            self.memo['planned'] = now
            start = tuple(maze.world2tileClipped(here[0], here[1]))
            end = tuple(maze.world2tileClipped(pos[0], pos[1]))
            route = self.route(maze, start, end)
            if route is None:
                # Nowhere to go from here; try another goal later.
                self.memo.pop('goal', None)
                self.memo.pop('cooler', None)
                self.memo.pop('boss', None)
                return False
            path = [maze.tile2world(*tile) for tile in route[1:]] + [(pos[0], pos[1])]
            self.memo['path'] = path
        if self.moveTo(Point3(path[0][0], path[0][1], 0), speed=speed):
            path.pop(0)
        return False

    def route(self, maze, start, end):
        # Tiles a toon fits through, else any open tiles.
        for walkable in (maze.isWalkable, maze.isAccessible):
            frontier = [start]
            came = {start: None}
            while frontier:
                nextFrontier = []
                for tile in frontier:
                    if tile == end or (abs(tile[0] - end[0]) + abs(tile[1] - end[1]) <= 1 and tile != start):
                        route = []
                        while tile is not None:
                            route.append(tile)
                            tile = came[tile]
                        route.reverse()
                        return route
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = (tile[0] + dx, tile[1] + dy)
                        if n not in came and walkable(n[0], n[1]):
                            came[n] = tile
                            nextFrontier.append(n)
                frontier = nextFrontier
        return None


def clientRender():
    return getClientBuiltin('base').render


def Globals_ToonRunSpeed():
    return CogdoMazeGameGlobals.ToonRunSpeed


# Milliseconds a tick (for the whole game) spent planning NPC flights.
PLAN_BUDGET = 0.005
# How much a flyer pays per grid step for each unit away from its lane.
LANE_PULL = 0.12


class FlightNav:
    """Lines of flight checked against the client's flying level, the way
    the player's own collisions would stop it: the scenery and platforms of
    the quadrants around (memos and obstacles share the wall mask, so those
    are left out; the moving obstacles are dodged by where they are)."""

    def __init__(self):
        from panda3d.core import CollisionTraverser, CollisionHandlerQueue, CollisionNode, CollisionSegment, BitMask32
        from otp.otpbase import OTPGlobals
        from toontown.toonbase import ToontownGlobals
        self.segment = CollisionSegment(0, 0, 0, 0, 1, 0)
        node = CollisionNode('npcFlightCheck')
        node.addSolid(self.segment)
        node.setFromCollideMask(OTPGlobals.WallBitmask | OTPGlobals.FloorBitmask | ToontownGlobals.CeilingBitmask)
        node.setIntoCollideMask(BitMask32.allOff())
        self.np = clientRender().attachNewNode(node)
        self.queue = CollisionHandlerQueue()
        self.trav = CollisionTraverser('npcFlight')
        self.trav.addCollider(self.np, self.queue)

    def destroy(self):
        self.trav.clearColliders()
        self.np.removeNode()

    def roots(self, level, lo, hi):
        roots = [level.startPlatform.getModel(), level.endPlatform.getModel()]
        for quadrant in level.quadrants:
            y = level.convertQuadNumToY(quadrant.serialNum)
            if y - level.quadLengthUnits < hi and y + level.quadLengthUnits > lo:
                # Its scenery, even while the quadrant is stashed out of
                # sight: an NPC ahead of the player still has to go around.
                roots.append(quadrant._model)
        return [root for root in roots if not root.isEmpty()]

    def blocked(self, level, a, b, roots=None):
        if self.np.isEmpty():
            return False
        if roots is None:
            roots = self.roots(level, min(a[1], b[1]), max(a[1], b[1]))
        self.segment.setPointA(a)
        self.segment.setPointB(b)
        for root in roots:
            self.queue.clearEntries()
            self.trav.traverse(root)
            if self.queue.getNumEntries():
                return True
        return False

    def floorAt(self, level, p, above=10.0, below=6.0):
        # The top of whatever is under p (a platform's floor), or None.
        a = Point3(p[0], p[1], p[2] + above)
        b = Point3(p[0], p[1], p[2] - below)
        self.segment.setPointA(a)
        self.segment.setPointB(b)
        best = None
        for root in self.roots(level, p[1] - 1.0, p[1] + 1.0):
            self.queue.clearEntries()
            self.trav.traverse(root)
            for i in range(self.queue.getNumEntries()):
                z = self.queue.getEntry(i).getSurfacePoint(clientRender())[2]
                if best is None or z > best:
                    best = z
        return best

    def nearObstacle(self, level, a, b, radius=4.5):
        from toontown.cogdominium.CogdoFlyingObstacles import CogdoFlyingWhirlwind, CogdoFlyingMinion
        ab = Vec3(b - a)
        length = ab.length()
        if length < 0.01:
            return False
        ab /= length
        for quadrant in level.quadrants:
            y = level.convertQuadNumToY(quadrant.serialNum)
            if abs(y - a[1]) > level.quadLengthUnits:
                continue
            for obstacle in quadrant.obstacles:
                if not isinstance(obstacle, (CogdoFlyingWhirlwind, CogdoFlyingMinion)):
                    continue
                node = getattr(obstacle, 'suit', None) if isinstance(obstacle, CogdoFlyingMinion) else obstacle.model
                if node is None or node.isEmpty():
                    continue
                pos = node.getPos(clientRender())
                if isinstance(obstacle, CogdoFlyingMinion):
                    pos.setZ(pos[2] + 3.0)
                t = max(0.0, min(length, Vec3(pos - a).dot(ab)))
                flat = Vec3(pos - (a + ab * t))
                if isinstance(obstacle, CogdoFlyingWhirlwind):
                    # A tall tube: only how far to the side counts.
                    flat.setZ(0)
                if flat.length() < radius:
                    return True
        return False


class FlightPlanner:
    """A way through the level from one platform to the next: a search over
    a coarse grid of the corridor, each step checked against the scenery,
    then pulled straight wherever the way is clear. It runs a few
    milliseconds a tick, so a long search never stalls the game; the toons
    wait on their platform meanwhile, as a player would look ahead."""

    GRID = 5.0
    # Greedier than a shortest-path search: a good way, found fast.
    WEIGHT = 1.8
    MAX_NODES = 6000
    MOVES = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
             if (dx, dy, dz) != (0, 0, 0) and abs(dx) + abs(dy) + abs(dz) <= 2]

    def __init__(self, nav, level, start, goal, lane=None):
        # lane: (x, z) the toon likes to fly at, so each finds its own way.
        self.lane = lane
        self.nav = nav
        self.level = level
        self.start = Point3(start)
        self.goal = Point3(goal)
        (left, right), (back, forward), (down, up) = level.getBounds()
        lo, hi = min(start[1], goal[1]) - 20.0, max(start[1], goal[1]) + 20.0
        self.limits = ((left + 2.0, right - 2.0), (lo, hi), (down + 2.0, up - 2.0))
        self.roots = nav.roots(level, lo, hi)
        self.path = None
        self.failed = False
        self.seen = 0
        self.work = self.search()

    def step(self, budget):
        if self.path is not None or self.failed:
            return True
        deadline = globalClock.getRealTime() + budget
        try:
            while globalClock.getRealTime() < deadline:
                next(self.work)
        except StopIteration:
            pass
        return self.path is not None or self.failed

    def clear(self, a, b):
        return not self.nav.blocked(self.level, a, b, self.roots)

    def point(self, cell):
        return Point3(cell[0] * self.GRID, cell[1] * self.GRID, cell[2] * self.GRID)

    def inside(self, cell):
        p = self.point(cell)
        (x0, x1), (y0, y1), (z0, z1) = self.limits
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1

    def cellOf(self, p):
        return (int(round(p[0] / self.GRID)), int(round(p[1] / self.GRID)), int(round(p[2] / self.GRID)))

    def search(self):
        import heapq
        if self.clear(self.start, self.goal):
            self.path = [self.start, self.goal]
            return
        yield
        # Toons take off straight up and come straight down onto a
        # platform: the grid starts and ends a little above each.
        startRise = self.rise(self.start)
        goalRise = self.rise(self.goal)
        yield
        startCells = self.near(startRise)
        yield
        goalCells = set(self.near(goalRise))
        yield
        if not startCells or not goalCells:
            self.failed = True
            return
        goalPoint = self.goal
        frontier = []
        came = {}
        cost = {}
        for cell in startCells:
            g = (self.point(cell) - startRise).length()
            cost[cell] = g
            came[cell] = None
            heapq.heappush(frontier, (g + self.WEIGHT * (self.point(cell) - goalPoint).length(), cell))
        seen = 0
        while frontier:
            f, cell = heapq.heappop(frontier)
            if cell in goalCells:
                path = [self.goal, goalRise]
                while cell is not None:
                    path.append(self.point(cell))
                    cell = came[cell]
                path.append(startRise)
                path.append(self.start)
                path.reverse()
                yield
                self.path = self.smooth(path)
                return
            seen += 1
            self.seen = seen
            if seen > self.MAX_NODES:
                break
            here = self.point(cell)
            for move in self.MOVES:
                nxt = (cell[0] + move[0], cell[1] + move[1], cell[2] + move[2])
                if not self.inside(nxt):
                    continue
                g = cost[cell] + self.GRID * math.sqrt(move[0] ** 2 + move[1] ** 2 + move[2] ** 2)
                if self.lane is not None:
                    g += LANE_PULL * (abs(nxt[0] * self.GRID - self.lane[0]) + abs(nxt[2] * self.GRID - self.lane[1]))
                if g >= cost.get(nxt, 1e9):
                    continue
                there = self.point(nxt)
                if not self.clear(here, there):
                    continue
                cost[nxt] = g
                came[nxt] = cell
                heapq.heappush(frontier, (g + self.WEIGHT * (there - goalPoint).length(), nxt))
            yield
        self.failed = True

    def rise(self, p):
        for height in (12.0, 9.0, 6.0, 3.0):
            q = Point3(p[0], p[1], p[2] + height)
            if self.clear(p, q):
                return q
        return Point3(p)

    def near(self, p):
        base = self.cellOf(p)
        cells = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1, 2):
                    cell = (base[0] + dx, base[1] + dy, base[2] + dz)
                    if self.inside(cell) and self.clear(p, self.point(cell)):
                        cells.append(cell)
        return cells

    def smooth(self, path):
        out = [path[0]]
        i = 0
        while i < len(path) - 1:
            j = len(path) - 1
            while j > i + 1 and not self.clear(path[i], path[j]):
                j -= 1
            out.append(path[j])
            i = j
        return out


class CogdoFlyingPlayer(CogdoPlayer):
    """The Lawbot flight, flown by each NPC the way a player flies it: it
    takes the propeller off the start platform, then flies from platform to
    platform on a way clear of the stacks and walls, dodging whirlwinds and
    minions, landing on each platform to refuel, picking up the memos near
    its way, and landing on the far platform at the end."""

    MEMO_REACH = 9.0

    def tick(self, now):
        # The ways are planned during the rules too, before anyone flies.
        if not self.game.started and not self.game.finished:
            client = self.client()
            level = getattr(getattr(client, 'game', None), 'level', None)
            if level is not None:
                self.pump(level, self.flight(level, level._endPlatformModel.getY(clientRender())), now)
        CogdoPlayer.tick(self, now)

    def nav(self):
        nav = self.memo.get('nav')
        if nav is None or nav.np.isEmpty():
            nav = self.memo['nav'] = FlightNav()
        return nav

    def destroy(self):
        nav = self.memo.pop('nav', None)
        if nav is not None:
            nav.destroy()

    def setBlades(self, fuel):
        States = CogdoFlyingGameGlobals.Gameplay.FuelStates
        G = CogdoFlyingGameGlobals.Gameplay
        if fuel is None:
            state = States.FuelNoPropeller
        elif fuel <= 0.0:
            state = States.FuelEmpty
        elif fuel < G.FuelVeryLowAmt:
            state = States.FuelVeryLow
        elif fuel < G.FuelLowAmt:
            state = States.FuelLow
        else:
            state = States.FuelNormal
        if self.memo.get('blades') != state:
            self.memo['blades'] = state
            self.send('requestAction', CogdoFlyingGameGlobals.AI.GameActions.SetBlades, int(state))

    def gatherablesOf(self, level, kind):
        for quadrant in level.quadrants:
            for g in quadrant.gatherables:
                if g.type == kind:
                    try:
                        yield g, g.getPos(clientRender())
                    except Exception:
                        continue

    def flight(self, level, endY):
        """The legs of the flight, shared by the game's NPCs: the start
        platform, a spot on each platform in turn and the far one last, and
        the planned way between each and the next."""
        flights = self.minigames.__dict__.setdefault('flights', {})
        flight = flights.get(self.game.doId)
        if flight is None:
            for doId in list(flights):
                del flights[doId]
            nav = self.nav()
            start = level.startPlatform.getSpawnPosForPlayer(1, clientRender())
            floor = nav.floorAt(level, start)
            spots = [Point3(start[0], start[1], (start[2] if floor is None else floor) + 1.0)]
            middle = []
            for quadrant in level.quadrants:
                for platform in quadrant.platforms.values():
                    spot = platform.getSpawnPosForPlayer(1, clientRender())
                    if spot[1] < endY - 10.0:
                        # Just above the platform's floor, which can sit a
                        # little higher than its spawn mark.
                        floor = nav.floorAt(level, spot)
                        middle.append(Point3(spot[0], spot[1], (spot[2] if floor is None else floor) + 1.0))
            middle.sort(key=lambda p: p[1])
            spots += middle
            spots.append(Point3(0, endY + 2.0, CogdoFlyingGameGlobals.Level.EndPlatformHeight + 1.0))
            flight = flights[self.game.doId] = {'spots': spots, 'plans': {}, 'pumped': None}
        return flight

    def route(self, level, flight):
        """Its own flight: its spot on the start platform, the platforms it
        means to land on (not always every one: some it flies past) and
        its spot on the far one, with the lane it likes to fly in."""
        route = self.memo.get('route')
        if route is None:
            spots = flight['spots']
            npcs = self.npcs()
            index = npcs.index(self.npc.doId) if self.npc.doId in npcs else 0
            rng = random.Random(self.npc.doId * 7 + self.game.doId)

            def own(spot, reach):
                angle = index * 2.1 + 0.5
                return Point3(spot[0] + reach * math.cos(angle), spot[1] + reach * math.sin(angle), spot[2])

            route = [own(spots[0], 1.6)]
            skipped = False
            for spot in spots[1:-1]:
                if not skipped and rng.random() < 0.3:
                    # Flies past this one (never two in a row: fuel).
                    skipped = True
                    continue
                skipped = False
                route.append(own(spot, 1.6))
            route.append(own(spots[-1], 3.5))
            (left, right), _, (down, up) = level.getBounds()
            self.memo['lane'] = (rng.uniform(left * 0.4, right * 0.4), rng.uniform(down + 0.3 * (up - down), down + 0.75 * (up - down)))
            self.memo['route'] = route
            self.memo['plans'] = {}
        return route

    def pump(self, level, flight, now):
        # Plans every flyer's legs ahead of time, a few milliseconds a tick
        # for the whole game, the nearest legs first (from the rules on).
        if flight['pumped'] == now:
            return
        flight['pumped'] = now
        flyers = [p for p in self.minigames.players.values() if p.game is self.game and isinstance(p, CogdoFlyingPlayer)]
        routes = [(p, p.route(level, flight)) for p in flyers]
        legs = max(len(r) for p, r in routes) - 1 if routes else 0
        deadline = globalClock.getRealTime() + PLAN_BUDGET
        for leg in range(legs):
            for p, route in routes:
                if leg >= len(route) - 1:
                    continue
                plan = p.memo['plans'].get(leg)
                if plan is None:
                    plan = p.memo['plans'][leg] = FlightPlanner(p.nav(), level, route[leg], route[leg + 1], p.memo['lane'])
                left = deadline - globalClock.getRealTime()
                if left <= 0 or not plan.step(left):
                    return

    def setAnim(self, name):
        # Up in the air a flyer hangs in its jump pose under the propeller,
        # as the player's own toon does; on a platform it stands.
        if self.memo.get('anim') != name:
            self.memo['anim'] = name
            self.npc.b_setAnimState(name, 1.0)

    def flyTo(self, level, here, aim, speed, climbing=True):
        delta = Vec3(aim - here)
        distance = delta.length()
        if distance <= speed * TICK:
            step = Point3(aim)
        else:
            delta.normalize()
            step = here + delta * speed * TICK
        if delta[2] > 0.3 and self.memo.get('fuel'):
            # Climbing burns fuel, as for a player (it refuels on landing).
            self.memo['fuel'] = max(0.05, self.memo['fuel'] - CogdoFlyingGameGlobals.Gameplay.FuelBurnRate * TICK * 1.5)
            self.setBlades(self.memo['fuel'])
        h = -math.degrees(math.atan2(delta[0], delta[1])) if math.hypot(delta[0], delta[1]) > 0.3 else self.npc.getH()
        self.npc.moveTo(step[0], step[1], step[2], h)
        return distance <= speed * TICK

    def play(self, now):
        game = self.game
        client = self.client()
        G = CogdoFlyingGameGlobals
        Actions = G.AI.GameActions
        players = self.players()
        if self.npc.doId in game.landed:
            if self.npc.doId not in game.winDone and all(p in game.winDone for p in players):
                self.send('requestAction', Actions.WinStateFinished, 0)
            return
        level = getattr(getattr(client, 'game', None), 'level', None)
        if level is None:
            return
        endY = level._endPlatformModel.getY(clientRender())
        flight = self.flight(level, endY)
        self.pump(level, flight, now)
        here = self.npc.getPos()
        if self.gameTime() > G.Gameplay.SecondsUntilGameOver and not self.memo.get('timedOut'):
            # Out of time: like a player, it is put on the far platform and
            # counts as landed, so the game ends instead of waiting on it.
            self.memo['timedOut'] = True
            self.npc.placeAt(random.uniform(-4, 4), endY + random.uniform(0, 4), G.Level.EndPlatformHeight, 0)
            self.send('requestAction', Actions.LandOnWinPlatform, 0)
            return
        speed = G.Gameplay.ToonVelMax['forward'] * self.memo.setdefault('pace', random.uniform(0.85, 1.0))
        mode = self.memo.setdefault('mode', 'propeller')
        if mode == 'propeller':
            # On the start platform first, like everyone: run to a
            # propeller and strap it on.
            if 'fuel' not in self.memo:
                self.memo['fuel'] = None
                self.setBlades(None)
            prop = self.memo.get('prop')
            if prop is None:
                near = [(g.serialNum, p) for g, p in self.gatherablesOf(level, G.Level.GatherableTypes.Propeller)
                        if abs(p[1] - here[1]) < 25.0 and abs(p[2] - here[2]) < 4.0]
                near.sort(key=lambda sp: (sp[1] - here).length())
                prop = self.memo['prop'] = near[0] if near else (None, Point3(here))
            serial, pos = prop
            if self.moveTo(Point3(pos[0], pos[1], here[2]), speed=RUN_SPEED * 0.8) and self.after('strapOn', (0.3, 1.2), now):
                if serial is not None:
                    self.send('requestPickUp', serial, G.Level.GatherableTypes.Propeller)
                self.memo['fuel'] = 1.0
                self.setBlades(1.0)
                self.memo['leg'] = 0
                self.memo['mode'] = 'plan'
            return
        if mode == 'rest':
            self.setAnim('Happy')
            if now >= self.memo.get('restUntil', 0):
                self.memo['mode'] = 'plan'
            return
        leg = self.memo.get('leg', 0)
        route = self.route(level, flight)
        final = leg + 1 >= len(route) - 1
        goal = route[min(leg + 1, len(route) - 1)]
        if mode == 'plan':
            plan = self.memo['plans'].get(leg)
            if plan is None or not (plan.path is not None or plan.failed):
                return
            if plan.failed:
                # No way found: up over everything and across, as a last
                # resort (it still lands on the platform).
                top = level.getBounds()[2][1] - 3.0
                self.memo['path'] = [Point3(here[0], here[1], top), Point3(goal[0], goal[1], top), goal]
            else:
                self.memo['path'] = list(plan.path[1:])
            self.memo['mode'] = 'fly'
            return
        # Flying the leg.
        self.setAnim('jumpAirborne')
        detour = self.memo.get('detour')
        if detour is not None:
            serial, pos, back = detour
            if serial in game.memoPickups or self.flyTo(level, here, pos, speed):
                if serial not in game.memoPickups:
                    self.send('requestPickUp', serial, G.Level.GatherableTypes.Memo)
                # Back to where it left its way, which it knows is clear.
                self.memo['detour'] = None
                self.memo.setdefault('path', []).insert(0, back)
            return
        path = self.memo.get('path') or [goal]
        aim = path[0]
        if self.nav().nearObstacle(level, here, aim if (aim - here).length() < 8.0 else here + (aim - here) * (8.0 / (aim - here).length())):
            # A whirlwind or minion in the way: hold back until it moves.
            if now - self.memo.setdefault('heldSince', now) < 3.0:
                return
        self.memo.pop('heldSince', None)
        if now >= self.memo.get('memoCheck', 0):
            self.memo['memoCheck'] = now + 0.4
            memo = self.nearMemo(level, here)
            if memo is not None:
                self.memo['detour'] = (memo[0], memo[1], Point3(here))
                return
        if self.flyTo(level, here, aim, speed):
            path.pop(0)
            self.memo['path'] = path
            if not path:
                self.npc.placeAt(goal[0], goal[1], goal[2] - 1.0, self.npc.getH())
                self.setAnim('Happy')
                if final:
                    self.memo['mode'] = 'landed'
                    self.send('requestAction', Actions.LandOnWinPlatform, 0)
                    return
                self.memo['fuel'] = 1.0
                self.setBlades(1.0)
                self.memo['leg'] = leg + 1
                self.memo['mode'] = 'rest'
                self.memo['restUntil'] = now + random.uniform(0.3, 1.0)

    def nearMemo(self, level, here):
        # Memos within reach of its way, and not behind anything.
        taken = set(self.game.memoPickups)
        others = set(p.memo.get('detour', (None,))[0] for p in self.minigames.players.values()
                     if p.game is self.game and p is not self and p.memo.get('detour'))
        best = None
        for g, pos in self.gatherablesOf(level, CogdoFlyingGameGlobals.Level.GatherableTypes.Memo):
            if g.serialNum in taken or g.serialNum in others:
                continue
            d = (pos - here).length()
            if d > self.MEMO_REACH or pos[1] < here[1] - 2.0:
                continue
            if best is None or d < best[0]:
                best = (d, g.serialNum, Point3(pos))
        if best is None:
            return None
        nav = self.nav()
        if nav.blocked(level, here, best[2]) or nav.nearObstacle(level, here, best[2]):
            return None
        return best[1], best[2]

    def freeMemo(self, client):
        level = getattr(getattr(client, 'game', None), 'level', None)
        if level is None:
            return None
        memos = [g.serialNum for quadrant in level.quadrants for g in quadrant.gatherables
                 if g.type == CogdoFlyingGameGlobals.Level.GatherableTypes.Memo and g.serialNum not in self.game.memoPickups]
        return random.choice(memos) if memos else None


class CogdoCranePlayer(CogdoPlayer):
    """The Cashbot field office: walk to a free crane and take its
    controls. Working the crane is the player's client's job (the NPC has
    no client of its own), as it runs the money bags' physics; see
    DistCogdoCrane's pilot."""

    def play(self, now):
        game = self.game
        if game.finished:
            return
        if now - self.memo.get('logAt', 0) > 3:
            self.memo['logAt'] = now
            goal = self.memo.get('goal')
            self.minigames.notify.info('crane NPC %s at %s goal %s' % (self.npc.doId, self.npc.getPos(), goal and (goal.index, goal.state, goal.avId)))
        mine = self.myCrane()
        if mine is not None:
            if not self.memo.get('seated'):
                self.memo['seated'] = True
                self.setAnim('neutral')
                x, y = CogdoCraneGameConsts.craneWorld(mine.index, 0, -4.9)
                self.npc.placeAt(x, y, 0, CogdoCraneGameConsts.CranePosHprs[mine.index][3])
            return
        self.memo['seated'] = False
        if not self.after('start', (1.5, 4.0), now):
            if 'goal' not in self.memo:
                return
        crane = self.memo.get('goal')
        if crane is None or crane.state != 'Free' or crane.avId or crane.isDeleted():
            crane = self.memo['goal'] = self.pickCrane()
            if crane is None:
                self.setAnim('neutral')
                return
        # Round behind the controls, then up to them.
        i = crane.index
        stand = Point3(*CogdoCraneGameConsts.craneWorld(i, 0, -4.9), 0)
        back = Point3(*CogdoCraneGameConsts.craneWorld(i, 0, -9.0), 0)
        self.setAnim('run')
        if self.memo.get('behind') != i:
            if self.moveTo(back, speed=RUN_SPEED * 0.8):
                self.memo['behind'] = i
            return
        if self.moveTo(stand, speed=RUN_SPEED * 0.5) and now >= self.memo.get('askAt', 0):
            self.memo['askAt'] = now + 1.0
            self.setAnim('neutral')
            npcSend(self, crane.requestControl)

    def setAnim(self, name):
        if self.memo.get('anim') != name:
            self.memo['anim'] = name
            self.npc.b_setAnimState(name, 1.0)

    def myCrane(self):
        for crane in self.game.cranes:
            if crane.avId == self.npc.doId and crane.state == 'Controlled':
                return crane
        return None

    def pickCrane(self):
        # A free crane, not one another NPC is heading for, and away from
        # the player's toon so the player can have the one nearest them.
        taken = set()
        for player in self.minigames.players.values():
            if player is not self and player.game is self.game:
                goal = player.memo.get('goal')
                if goal is not None:
                    taken.add(goal.doId)
        playerPos = self.playerPos()
        here = self.npc.getPos()
        best = None
        for crane in self.game.cranes:
            if crane.state != 'Free' or crane.avId or crane.doId in taken:
                continue
            x, y = CogdoCraneGameConsts.craneWorld(crane.index, 0, -4.9)
            cost = math.hypot(x - here[0], y - here[1])
            if playerPos is not None:
                cost -= 0.8 * math.hypot(x - playerPos[0], y - playerPos[1])
            if best is None or cost < best[0]:
                best = (cost, crane)
        return best[1] if best else None


COGDO_PLAYERS = {
    'DistCogdoMazeGameAI': CogdoMazePlayer,
    'DistCogdoFlyingGameAI': CogdoFlyingPlayer,
    'DistCogdoCraneGameAI': CogdoCranePlayer,
}
