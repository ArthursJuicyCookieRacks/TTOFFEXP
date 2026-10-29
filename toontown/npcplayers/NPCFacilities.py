"""What the NPC players do in the Cog HQ facilities besides fighting.

A mint, a DA office or a country club asks more of a toon than battles:
moles to whack and a hedge maze to run in the back nine, Bust-A-Cog boards
on the golf green, platforms that move, gaps to jump and stompers to slip
past. The NPCs in a player's party do all of that here:

- Jobs: a mole field, golf green game or maze in the NPC's zone gives it a
  job (MoleJob, GreenJob, MazeJob) that drives its walks and what its client
  would send until the puzzle is over.
- Trails: where no straight walk reaches the player (a gap, a platform that
  is elsewhere), the NPC follows the player's own footsteps, jumping where
  the player was in the air and waiting where the ground is missing until
  it comes back. Standing on something that moves, it moves with it.

The district knows no geometry; the client's scene (NPCNav) answers for the
ground and the walls, and the client's copies of the entities give the
positions of hills, screens and maze walls.
"""

import heapq
import math
import random

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import Point3, Vec3

from otp.local.ExecutionContext import getClientBuiltin
from toontown.coghq import MoleFieldBase
from toontown.coghq.DistributedGolfGreenGameAI import DistributedGolfGreenGameAI
from toontown.coghq.DistributedMazeAI import DistributedMazeAI
from toontown.coghq.DistributedMoleFieldAI import DistributedMoleFieldAI
from toontown.npcplayers.NPCNav import getNav
from toontown.toonbase import ToontownGlobals

RUN_SPEED = ToontownGlobals.ToonForwardSpeed
# A toon's jump: how far it carries, how high, how long.
JUMP_RANGE = 17.0
JUMP_HEIGHT = 3.0
JUMP_TIME = 0.9
# The player's footsteps are kept this far apart, this many of them.
TRAIL_STEP = 0.8
TRAIL_LENGTH = 500
# Above the ground by this much the player is in the air.
AIR_HEIGHT = 0.8
# How long an NPC waits for missing ground (a platform away) before it gives
# up on the trail and teleports to the player instead.
TRAIL_PATIENCE = 8.0
# The maze is searched on a grid of cells this wide, for at most this long
# per tick.
MAZE_CELL = 5.0
MAZE_BUDGET = 0.006
# How long an NPC spends on one Bust-A-Cog board.
BOARD_TIME = (24.0, 50.0)
# A stomper this close to the floor is down; the NPC keeps clear until it
# rises.
STOMPER_CLEARANCE = 3.0


def clientObject(doId):
    base = getClientBuiltin('base')
    if base is None or not hasattr(base, 'cr'):
        return None
    return base.cr.doId2do.get(doId)


def flat(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def isMover(into):
    """Whether the ground node is a platform that moves (MovingPlatform
    names its floor so: paint mixers, lifts, the Lawbot office platforms)."""
    return into is not None and not into.isEmpty() and into.getName().startswith('MovingPlatform')


class Job:
    done = False

    def __init__(self, facilities, npc, player):
        self.facilities = facilities
        self.manager = facilities.manager
        self.air = facilities.air
        self.npc = npc
        self.player = player
        self.nav = getNav()

    def tick(self, now, dt):
        pass

    def finish(self):
        self.done = True

    def walkTo(self, point, speed=RUN_SPEED, done=None):
        npc = self.npc
        pos = npc.getPos()
        path = self.nav.walkable(pos, point) if self.nav.available() else None
        if not path:
            path = [Point3(point)]
        npc.walk = [path, speed, None, done]

    def send(self, func, *args):
        try:
            self.npc.asSender(func, *args)
        except Exception:
            self.facilities.notify.warning('%s failed for NPC %s' % (getattr(func, '__name__', func), self.npc.doId))
            import traceback
            traceback.print_exc()


class MoleJob(Job):
    """Whack-A-Mole on the tee-off green: the cog moles (HILL_BOMB) are the
    ones to stomp; the plain moles blow up in a toon's face."""

    def __init__(self, facilities, npc, player, field):
        Job.__init__(self, facilities, npc, player)
        self.field = field
        self.target = None
        self.nextPick = 0.0
        self.waitingSince = None

    def hillPos(self, index):
        client = clientObject(self.field.doId)
        if client is None or index >= len(getattr(client, 'moleHills', ())):
            return None
        base = getClientBuiltin('base')
        return Point3(client.moleHills[index].getPos(base.render))

    def gameTime(self):
        start = getattr(self.field, 'gameStartTime', None)
        if start is None:
            return None
        return globalClock.getRealTime() - start

    def popupNum(self, index, startTime):
        return len([e for e in self.field.schedule if e[1] == index and e[0] <= startTime])

    def whackable(self, t):
        """The cog moles up now or about to be, with the time they stay up."""
        field = self.field
        moles = []
        for entry in getattr(field, 'schedule', ()):
            start, index, moveUp, stayUp, moveDown, moleType = entry
            if moleType != MoleFieldBase.HILL_BOMB:
                continue
            upFrom = start + moveUp
            upTo = start + moveUp + stayUp
            if t > upTo - 0.6 or t < start - 2.5:
                continue
            if field.whackedMoles.get(index, 0) >= self.popupNum(index, start):
                continue
            if index in self.facilities.claimedMoles and self.facilities.claimedMoles[index] is not self:
                continue
            moles.append((index, upFrom, upTo))
        return moles

    def tick(self, now, dt):
        field = self.field
        if field.isDeleted() or field.challengeDefeated or not hasattr(field, 'entId'):
            self.release()
            self.finish()
            return
        npc = self.npc
        t = self.gameTime()
        if t is None:
            # Standing on the green starts the game, as a player's step does.
            # (Once the clock has run, only the field restarts it: a second
            # trigger would cost the player laff.)
            if npc.walk is None:
                center = self.fieldCenter()
                if center is not None and flat(npc.getPos(), center) > 12:
                    self.walkTo(self.spotOnField(center))
                elif center is not None:
                    self.send(field.setClientTriggered)
            return
        if self.target is not None:
            index, upFrom, upTo = self.target
            if npc.walk is None:
                if upFrom <= t <= upTo and field.whackedMoles.get(index, 0) < self.popupNum(index, upFrom):
                    self.send(field.whackedMole, index, self.popupNum(index, upFrom))
                    self.facilities.count('moles whacked')
                    self.facilities.jump(npc)
                    self.release()
                    self.nextPick = now + random.uniform(0.4, 1.1)
                elif t > upTo or (self.waitingSince and now - self.waitingSince > 4):
                    # Too late (or it was never this one): off to another.
                    self.release()
                    self.nextPick = now + random.uniform(0.2, 0.6)
                elif self.waitingSince is None:
                    self.waitingSince = now
            return
        if now < self.nextPick or npc.walk is not None:
            return
        moles = self.whackable(t)
        if self.facilities.debug:
            self.facilities.notify.info('NPC %s: t=%.1f schedule %d whackable %s whacked %s' % (
                npc.doId, t, len(getattr(field, 'schedule', ())), moles[:4], field.whackedMoles))
        if not moles:
            return
        pos = npc.getPos()
        choices = []
        for index, upFrom, upTo in moles:
            hill = self.hillPos(index)
            if hill is None:
                continue
            travel = flat(pos, hill) / RUN_SPEED
            arrive = t + travel + 0.3
            if arrive > upTo - 0.3:
                if self.facilities.debug:
                    self.facilities.notify.info('NPC %s: mole %d too far (%.1f s away, down at %.1f)' % (npc.doId, index, travel, upTo - t))
                continue
            choices.append((abs(arrive - upFrom) + travel, index, upFrom, upTo, hill))
        if not choices:
            return
        choices.sort(key=lambda c: c[0])
        # Mostly the handiest mole; now and then a worse pick, as a person
        # misjudges, which is also how a mole gets missed.
        pick = choices[0] if random.random() < 0.8 or len(choices) == 1 else random.choice(choices[1:])
        _, index, upFrom, upTo, hill = pick
        self.target = (index, upFrom, upTo)
        self.waitingSince = None
        self.facilities.claimedMoles[index] = self
        angle = random.uniform(0, 2 * math.pi)
        spot = Point3(hill[0] + 1.2 * math.cos(angle), hill[1] + 1.2 * math.sin(angle), hill[2])
        self.walkTo(spot)

    def fieldCenter(self):
        client = clientObject(self.field.doId)
        if client is None or not hasattr(client, 'centerNode'):
            return None
        base = getClientBuiltin('base')
        return Point3(client.centerNode.getPos(base.render))

    def spotOnField(self, center):
        client = clientObject(self.field.doId)
        half = min(getattr(client, 'dimensionX', 20), getattr(client, 'dimensionY', 20)) * 0.3
        return Point3(center[0] + random.uniform(-half, half), center[1] + random.uniform(-half, half), center[2])

    def release(self):
        if self.target is not None:
            self.facilities.claimedMoles.pop(self.target[0], None)
        self.target = None
        self.waitingSince = None

    def finish(self):
        self.release()
        Job.finish(self)


class GreenJob(Job):
    """Bust-A-Cog on the golf green: the NPC joins at a screen and clears a
    board every so often, which is a board fewer for the player."""

    def __init__(self, facilities, npc, player, game):
        Job.__init__(self, facilities, npc, player)
        self.game = game
        self.state = 'going'
        self.due = 0.0

    def standPoint(self):
        client = clientObject(self.game.doId)
        if client is None or client.isEmpty():
            return None
        base = getClientBuiltin('base')
        index = len(self.game.everJoinedToons)
        if self.npc.doId in self.game.everJoinedToons:
            index = self.game.everJoinedToons.index(self.npc.doId)
        if index > 3:
            return None
        return Point3(base.render.getRelativePoint(client, client.toonPoints[index]))

    def tick(self, now, dt):
        game = self.game
        if game.isDeleted() or game.allBoardsClear or not hasattr(game, 'entId'):
            self.finish()
            return
        npc = self.npc
        if self.state == 'going':
            spot = self.standPoint()
            if spot is None:
                self.finish()
                return
            if npc.walk is None:
                if flat(npc.getPos(), spot) > 2.5:
                    self.walkTo(Point3(spot[0], spot[1] - 2, spot[2]))
                else:
                    self.state = 'joining'
                    self.due = now + random.uniform(0.5, 1.5)
        elif self.state == 'joining':
            if now >= self.due:
                if npc.doId not in game.joinedToons:
                    self.send(game.requestJoin)
                    spot = self.standPoint()
                    if spot is not None:
                        # The clients walk it up to its screen; the district
                        # agrees on where it stands.
                        npc.setPosHpr(spot[0], spot[1], spot[2], 180, 0, 0)
                self.state = 'board'
                self.due = now + random.uniform(1.0, 2.0)
                self.started = False
        elif self.state == 'board':
            if now >= self.due:
                if npc.doId not in game.joinedToons:
                    self.finish()
                    return
                # A new board (0), or the one it had cleared (1) and the next.
                self.send(game.requestBoard, 1 if self.started else 0)
                if self.started:
                    self.facilities.count('boards cleared')
                self.started = True
                self.due = now + random.uniform(*BOARD_TIME)

    def finish(self):
        if not self.game.isDeleted() and self.npc.doId in self.game.joinedToons and not self.game.allBoardsClear:
            self.send(self.game.leaveGame)
        Job.finish(self)


class MazeJob(Job):
    """The hedge maze: in at the entrance, through on a path found in the
    hedges, and out at the finish."""

    def __init__(self, facilities, npc, player, maze):
        Job.__init__(self, facilities, npc, player)
        self.maze = maze
        self.state = 'toEntrance'
        self.due = 0.0
        self.speed = RUN_SPEED * random.uniform(0.75, 0.95)

    def tick(self, now, dt):
        maze = self.maze
        npc = self.npc
        if maze.isDeleted() or not hasattr(maze, 'entId') or npc.doId in maze.finishedList:
            self.finish()
            return
        solver = self.facilities.mazeSolver(maze)
        if solver is None:
            self.finish()
            return
        if self.state == 'toEntrance':
            if npc.walk is None:
                if flat(npc.getPos(), solver.entrance) > 4:
                    self.walkTo(Point3(solver.entrance[0] + random.uniform(-2, 2), solver.entrance[1] + random.uniform(-2, 2), solver.entrance[2]))
                else:
                    self.state = 'waiting'
                    self.due = now + random.uniform(0.5, 2.0)
        elif self.state == 'waiting':
            if not hasattr(maze, 'gameStartTime'):
                # Stepping through the entrance starts the clock.
                if now >= self.due:
                    self.send(maze.setClientTriggered)
                    self.due = now + 3
                return
            if solver.path is None:
                if solver.failed:
                    self.state = 'lost'
                    self.due = now + random.uniform(20, 40)
                return
            if now >= self.due:
                self.state = 'running'
                points = [Point3(p) for p in solver.path]
                npc.walk = [points, self.speed, None, self.arrived]
        elif self.state == 'lost':
            # No way through was found: it wanders a while, then takes the
            # short cut nobody sees.
            if now >= self.due:
                finish = solver.finish
                npc.placeAt(finish[0], finish[1], finish[2], npc.getH())
                self.arrived()

    def arrived(self):
        if not self.maze.isDeleted() and hasattr(self.maze, 'gameStartTime'):
            self.send(self.maze.setFinishedMaze)
            self.facilities.count('mazes run' if self.state == 'running' else 'mazes skipped')
        self.finish()


class MazeSolver:
    """A* over a grid of cells between the maze's entrance and finish, with
    the client's hedge collisions as walls, a little of it each tick."""

    def __init__(self, maze):
        self.maze = maze
        self.path = None
        self.failed = False
        self.ready = False
        self.entrance = None
        self.finish = None

    def setup(self):
        client = clientObject(self.maze.doId)
        room = getattr(client, 'roomHold', None)
        if client is None or room is None:
            return False
        base = getClientBuiltin('base')
        geom = room.getGeom()
        entrance = geom.find('**/ENTRANCE')
        finish = geom.find('**/finish')
        if entrance.isEmpty() or finish.isEmpty():
            return False
        self.entrance = Point3(entrance.getPos(base.render))
        self.finish = Point3(finish.getPos(base.render))
        self.z = self.entrance[2]
        lo = Point3(min(self.entrance[0], self.finish[0]), min(self.entrance[1], self.finish[1]), 0)
        hi = Point3(max(self.entrance[0], self.finish[0]), max(self.entrance[1], self.finish[1]), 0)
        for i in range(4):
            section = geom.find('**/Maze_Inside_%d' % i)
            if section.isEmpty():
                continue
            bounds = section.getTightBounds(base.render)
            if bounds is None:
                continue
            lo = Point3(min(lo[0], bounds[0][0]), min(lo[1], bounds[0][1]), 0)
            hi = Point3(max(hi[0], bounds[1][0]), max(hi[1], bounds[1][1]), 0)
        self.origin = (lo[0] - MAZE_CELL, lo[1] - MAZE_CELL)
        self.cols = int((hi[0] - lo[0]) / MAZE_CELL) + 3
        self.rows = int((hi[1] - lo[1]) / MAZE_CELL) + 3
        self.start = self.cell(self.entrance)
        self.goal = self.cell(self.finish)
        self.open = [(self.heuristic(self.start), 0, self.start)]
        self.gScore = {self.start: 0}
        self.cameFrom = {}
        self.closed = set()
        self.edges = {}
        self.checks = 0
        self.ready = True
        return True

    def cell(self, point):
        return (int(round((point[0] - self.origin[0]) / MAZE_CELL)), int(round((point[1] - self.origin[1]) / MAZE_CELL)))

    def center(self, cell):
        return Point3(self.origin[0] + cell[0] * MAZE_CELL, self.origin[1] + cell[1] * MAZE_CELL, self.z)

    def heuristic(self, cell):
        return abs(cell[0] - self.goal[0]) + abs(cell[1] - self.goal[1])

    def passable(self, a, b):
        key = (a, b) if a < b else (b, a)
        result = self.edges.get(key)
        if result is None:
            nav = getNav()
            self.checks += 1
            result = nav.clearLine(self.center(a), self.center(b))
            self.edges[key] = result
        return result

    def work(self, budget):
        """Searches for up to budget seconds; True once settled."""
        if self.path is not None or self.failed:
            return True
        if not self.ready and not self.setup():
            return False
        deadline = globalClock.getRealTime() + budget
        while self.open:
            if globalClock.getRealTime() > deadline:
                return False
            f, g, current = heapq.heappop(self.open)
            if current in self.closed:
                continue
            if current == self.goal:
                self.path = self.build(current)
                return True
            self.closed.add(current)
            x, y = current
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nx < 0 or ny < 0 or nx >= self.cols or ny >= self.rows or (nx, ny) in self.closed:
                    continue
                if not self.passable(current, (nx, ny)):
                    continue
                tentative = g + 1
                if tentative < self.gScore.get((nx, ny), 1e9):
                    self.gScore[(nx, ny)] = tentative
                    self.cameFrom[(nx, ny)] = current
                    heapq.heappush(self.open, (tentative + self.heuristic((nx, ny)), tentative, (nx, ny)))
        self.failed = True
        return True

    def build(self, cell):
        cells = [cell]
        while cell in self.cameFrom:
            cell = self.cameFrom[cell]
            cells.append(cell)
        cells.reverse()
        # Straight runs need no stops in between.
        points = []
        for i, c in enumerate(cells):
            if 0 < i < len(cells) - 1:
                before, after = cells[i - 1], cells[i + 1]
                if (c[0] - before[0], c[1] - before[1]) == (after[0] - c[0], after[1] - c[1]):
                    continue
            points.append(self.center(c))
        nav = getNav()
        snapped = []
        z = self.z
        for p in points:
            ground = nav.groundZ(p[0], p[1], z)
            if ground is not None:
                z = ground
            snapped.append(Point3(p[0], p[1], z))
        snapped.append(Point3(self.finish[0], self.finish[1], z))
        return snapped


class NPCFacilities:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCFacilities')

    def __init__(self, manager):
        self.manager = manager
        self.air = manager.air
        self.trails = {}
        self.claimedMoles = {}
        self.solvers = {}
        self.animDue = {}
        self.stats = {}
        self.debug = False

    def destroy(self):
        self.trails = {}
        self.solvers = {}

    # --- Each tick ---

    def tick(self, now, dt):
        self.recordTrails(now)
        for npc in self.manager.party.members[:]:
            if npc.isDeleted():
                continue
            job = getattr(npc, 'job', None)
            if job is not None:
                player = self.air.doId2do.get(npc.party)
                if npc.crew is not None or npc.busy or player is None or player.zoneId != npc.zoneId:
                    job.finish()
                if job.done:
                    npc.job = None
                    continue
                try:
                    job.tick(now, dt)
                except Exception:
                    self.notify.warning('job failed for NPC %s' % npc.doId)
                    import traceback
                    traceback.print_exc()
                    job.finish()
                    npc.job = None
                continue
            if npc.crew is None and not npc.busy and npc.walk is None:
                self.ride(npc)
        for npc in self.manager.party.members[:]:
            if getattr(npc, 'job', None) is None and npc.crew is None and not npc.busy and not npc.isDeleted():
                self.findJob(npc)
        for doId, due in list(self.animDue.items()):
            if now >= due:
                del self.animDue[doId]
                npc = self.air.doId2do.get(doId)
                if npc is not None and not npc.isDeleted():
                    npc.b_setAnimState('neutral', 1.0)
                    npc.b_setAnimState('Happy', 1.0)
        for solver in list(self.solvers.values()):
            if solver.maze.isDeleted():
                del self.solvers[solver.maze.doId]
            elif not solver.work(MAZE_BUDGET):
                break

    def count(self, key):
        self.stats[key] = self.stats.get(key, 0) + 1

    def holds(self, npc):
        return getattr(npc, 'job', None) is not None

    def jump(self, npc):
        npc.b_setAnimState('jump', 1.0)
        self.animDue[npc.doId] = globalClock.getFrameTime() + 1.0

    # --- Jobs ---

    def entitiesFor(self, player):
        # The puzzles of the level the player is in (its rooms have zones of
        # their own, so the toon's zone says nothing).
        for obj in self.manager.party._objectsOfType((DistributedMoleFieldAI, DistributedGolfGreenGameAI, DistributedMazeAI)):
            level = getattr(obj, 'level', None)
            if obj.isDeleted() or not hasattr(obj, 'entId') or level is None:
                continue
            if player.doId in getattr(level, 'presentAvIds', ()) or player.doId in getattr(level, 'avIdList', ()):
                yield obj

    def findJob(self, npc):
        player = self.air.doId2do.get(npc.party)
        if player is None or player.zoneId != npc.zoneId or not getNav().available():
            return
        playerPos = self.manager.getPlayerPos(player)
        if flat(npc.getPos(), playerPos) > 45:
            # Still on its way (NPCParty.follow brings it along first).
            return
        for obj in self.entitiesFor(player):
            if isinstance(obj, DistributedMoleFieldAI):
                if obj.challengeDefeated:
                    continue
                client = clientObject(obj.doId)
                center = getattr(client, 'centerNode', None)
                if client is None or center is None:
                    continue
                centerPos = center.getPos(getClientBuiltin('base').render)
                if obj.started or flat(playerPos, centerPos) < max(client.dimensionX, client.dimensionY) * 0.75 + 6:
                    npc.job = MoleJob(self, npc, player, obj)
                    npc.walk = None
                    return
            elif isinstance(obj, DistributedGolfGreenGameAI):
                if obj.allBoardsClear or len(obj.everJoinedToons) >= 4 and npc.doId not in obj.everJoinedToons:
                    continue
                client = clientObject(obj.doId)
                if client is None or client.isEmpty():
                    continue
                gamePos = client.getPos(getClientBuiltin('base').render)
                if player.doId in obj.joinedToons or flat(playerPos, gamePos) < 25:
                    npc.job = GreenJob(self, npc, player, obj)
                    npc.walk = None
                    return
            elif isinstance(obj, DistributedMazeAI):
                if npc.doId in obj.finishedList:
                    continue
                solver = self.mazeSolver(obj)
                if solver is None or solver.entrance is None:
                    continue
                if flat(playerPos, solver.entrance) < 30 or \
                        (hasattr(obj, 'gameStartTime') and flat(playerPos, (solver.entrance + solver.finish) * 0.5) < 150):
                    npc.job = MazeJob(self, npc, player, obj)
                    npc.walk = None
                    return

    def mazeSolver(self, maze):
        solver = self.solvers.get(maze.doId)
        if solver is None:
            solver = MazeSolver(maze)
            if not solver.setup():
                return None
            self.solvers[maze.doId] = solver
        return solver

    # --- Trails ---

    def recordTrails(self, now):
        players = {}
        for npc in self.manager.party.members:
            if not npc.isDeleted() and npc.party:
                players[npc.party] = True
        for doId in list(self.trails.keys()):
            if doId not in players:
                del self.trails[doId]
        nav = getNav()
        for doId in players:
            player = self.air.doId2do.get(doId)
            if player is None:
                continue
            pos = Point3(self.manager.getPlayerPos(player))
            trail = self.trails.get(doId)
            if trail is None or trail['zoneId'] != player.zoneId:
                trail = self.trails[doId] = {'zoneId': player.zoneId, 'points': []}
            points = trail['points']
            if points and (points[-1][0] - pos).length() < TRAIL_STEP:
                continue
            ground = nav.groundZ(pos[0], pos[1], pos[2]) if nav.available() else pos[2]
            air = ground is None or pos[2] - ground > AIR_HEIGHT
            points.append((pos, air))
            if len(points) > TRAIL_LENGTH:
                del points[:len(points) - TRAIL_LENGTH]

    def trailWalk(self, npc, player, playerPos):
        """Sends the NPC along the player's footsteps toward the player;
        False when there is no trail to follow (or patience ran out), and
        the caller teleports it instead."""
        trail = self.trails.get(player.doId)
        now = globalClock.getFrameTime()
        if trail is None or trail['zoneId'] != npc.zoneId or len(trail['points']) < 2:
            return False
        points = trail['points']
        pos = npc.getPos()
        state = getattr(npc, 'trail', None)
        if state is None or state.get('trail') is not trail:
            state = npc.trail = {'trail': trail, 'index': None, 'waitSince': None}
        index = state['index']
        if index is None or index >= len(points) or flat(points[index][0], pos) > 10:
            # Where on the trail it is: the nearest footstep, preferring
            # later ones (the trail may cross itself).
            best = None
            for i in range(len(points) - 1, -1, -1):
                d = flat(points[i][0], pos)
                if d < 6 and (best is None or d < best[0] - 1.5):
                    best = (d, i)
            if best is None:
                return False
            index = best[1]
        nav = getNav()
        riding = getattr(npc, 'ride', None)
        rideNode = riding[0] if riding is not None and not riding[0].isEmpty() else None
        # The next stretch of footsteps on firm ground.
        walk = []
        i = index + 1
        if i < len(points) and flat(points[i][0], pos) > JUMP_RANGE * 1.5:
            # The trail breaks here (the player was moved, not walked).
            state['index'] = None
            return False
        skipped = False
        while i < len(points) and len(walk) < 10:
            point, air = points[i]
            if air:
                break
            if nav.available():
                ground, into = nav.groundHit(point[0], point[1], point[2])
            else:
                ground, into = point[2], None
            if ground is None:
                break
            if self.stomperBlocks(npc.zoneId, point):
                break
            if rideNode is not None and into is not None and into == rideNode:
                # Footsteps taken riding the platform it stands on: it rides
                # too, and goes nowhere.
                skipped = True
                i += 1
                continue
            walk.append(Point3(point[0], point[1], ground))
            i += 1
            if isMover(into) and into != rideNode:
                # One step onto the platform; then it is carried along.
                break
        if walk:
            state['index'] = i - 1
            state['waitSince'] = None
            npc.walk = [walk, RUN_SPEED, None, None]
            return True
        if skipped:
            state['index'] = i - 1
            state['waitSince'] = None
            if i >= len(points):
                return True
        if i < len(points) and points[i][1]:
            # The player took off here: the landing is the next footstep on
            # the ground within a jump.
            j = i
            while j < len(points) and points[j][1]:
                j += 1
            if j < len(points):
                landing = points[j][0]
                ground = nav.groundZ(landing[0], landing[1], landing[2]) if nav.available() else landing[2]
                if ground is not None and flat(pos, landing) <= JUMP_RANGE:
                    self.jumpTo(npc, Point3(landing[0], landing[1], ground))
                    state['index'] = j
                    state['waitSince'] = None
                    return True
        # Nothing to stand on yet (a platform on its way back, a stomper
        # down): wait, riding whatever it stands on.
        if state['waitSince'] is None:
            state['waitSince'] = now
        if now - state['waitSince'] > TRAIL_PATIENCE:
            state['waitSince'] = None
            state['index'] = None
            return False
        return True

    def jumpTo(self, npc, landing):
        pos = Point3(npc.getPos())
        length = max(1.0, (landing - pos).length())
        points = []
        for k in range(1, 6):
            t = k / 5.0
            p = pos + (landing - pos) * t
            p = Point3(p[0], p[1], p[2] + JUMP_HEIGHT * 4 * t * (1 - t))
            points.append(p)
        arc = length * 1.15
        npc.walk = [points, arc / JUMP_TIME, None, None]
        self.jump(npc)

    def ride(self, npc):
        """Standing on something that moves (a platform, a paint mixer), the
        NPC goes along with it."""
        nav = getNav()
        if not nav.available():
            return
        pos = npc.getPos()
        ground, into = nav.groundHit(pos[0], pos[1], pos[2])
        rideState = getattr(npc, 'ride', None)
        if self.debug:
            self.notify.info('ride NPC %s at %s: ground %s under %s; state %s' % (
                npc.doId, pos, ground, into and into.getName(), rideState and rideState[1]))
        if into is None or into.isEmpty():
            npc.ride = None
            # Nothing under it (the platform it waited on has gone): it
            # drops to whatever is below, as a toon would.
            for drop in (6, 12, 20, 30, 45):
                below = nav.groundZ(pos[0], pos[1], pos[2] - drop)
                if below is not None:
                    npc.moveTo(pos[0], pos[1], below, npc.getH())
                    npc.stopMoving()
                    break
            return
        base = getClientBuiltin('base')
        if rideState is not None and rideState[0] == into and not rideState[0].isEmpty():
            world = base.render.getRelativePoint(into, rideState[1])
            moved = Point3(world[0], world[1], world[2])
            if (moved - pos).length() > 0.02:
                npc.moveTo(moved[0], moved[1], moved[2], npc.getH())
                npc.riding = True
            elif getattr(npc, 'riding', False):
                npc.riding = False
                npc.stopMoving()
            return
        local = into.getRelativePoint(base.render, Point3(pos[0], pos[1], ground))
        npc.ride = (into, Point3(local))

    def stomperBlocks(self, zoneId, point):
        """Whether a stomper is down (or coming down) over the spot."""
        base = getClientBuiltin('base')
        if base is None:
            return False
        for obj in list(base.cr.doId2do.values()):
            if obj.__class__.__name__ != 'DistributedStomper' or getattr(obj, 'zoneId', None) not in (zoneId, None):
                continue
            model = getattr(obj, 'model', None)
            if model is None or model.isEmpty():
                continue
            head = model.find('**/head')
            if head.isEmpty():
                continue
            bounds = head.getTightBounds(base.render)
            if bounds is None:
                continue
            lo, hi = bounds
            if lo[0] - 2.5 <= point[0] <= hi[0] + 2.5 and lo[1] - 2.5 <= point[1] <= hi[1] + 2.5:
                # Its head is at toon height over the spot (down, or
                # slamming across the alley).
                if lo[2] < point[2] + STOMPER_CLEARANCE + 1.0:
                    return True
        return False
