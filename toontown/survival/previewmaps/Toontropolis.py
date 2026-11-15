"""Toontropolis: the plaza from Disney's Toontown 2.0 prototype.

The whole town comes from the prototype's own Unity scene, converted piece
for piece (toontown/toontropolis): the living shops, the fountain, the
street props, Disney's walls and floors, and its day and night. In
Survival the round starts at night, the way every Survival map does, with
the town asleep, its windows lit and the moon up. Nothing here is built
from the game's own pieces, so the kit only carries the stations.
"""

from direct.showbase.DirectObject import DirectObject
from panda3d.core import BitMask32, CollisionNode, CollisionPolygon, Fog, FogAttrib, Point3, Vec3, Vec4

from toontown.toonbase import ToontownGlobals

from toontown.survival.previewmaps.PreviewMap import PreviewMap
from toontown.toontropolis.Town import Town
from toontown.toontropolis.TownLife import TownLife

# What the night does to the toons and the cogs (the town's own night is
# in its model): Disney's night turns the ambient light blue.
NIGHT_TINT = Vec4(0.62, 0.62, 1.0, 1)
DAY_TINT = Vec4(1, 1, 1, 1)


# In front of the door of the Cog building that lands on Toon Hall.
COG_DOOR = (134.0, 111.0, 9.0)
# The ground that building stands on once it is down (it is Disney's own
# size, a good deal wider than Toon Hall): its four corners, going round
# with the inside on the left, and how far its walls reach down and up.
# Where its cogs come out, to either side of the middle of the door
# (Disney's four Flunkies, and the Big Cheese in the middle, a step in
# front), the order later ones try those places in, and how much room one
# needs.
COG_DOOR_SIDE = (-7.5, -2.5, 2.5, 7.5, 0.0)
COG_DOOR_ORDER = (4, 1, 2, 0, 3)
COG_DOOR_ROOM = 3.5
COG_BASE = ((84.4, 116.4), (184.9, 121.4), (183.3, 151.3), (82.8, 145.3))
COG_WALL = (-12.0, 45.0)


class Toontropolis(PreviewMap):
    KEY = 'toontropolis'
    TITLE = 'Toontropolis'
    DESCRIPTION = "The big city from Toontown 2.0, with every shop alive."
    PLAYER_START = (Point3(-96.2, 143.5, 12), 191)      # Disney's own start: in the alley, facing out towards the plaza
    MICKEY_SPOT = (Point3(108, 104, 9), 180)             # in front of Toon Hall, to one side of its door
    FISHERMAN_SPOT = (Point3(-49, 0, 9), -90)           # by the fountain
    TRUNK_SPOT = (Point3(-23, 50, 9), 180)              # outside the Clothing Shop
    REACH_SPAN = 320.0
    SPAWN_RING = (40.0, 160.0)
    NO_LANDING = ()
    NIGHT_SCALE = NIGHT_TINT
    SKY_FILE = 'phase_4/models/toontropolis/sky.bam'
    SKY_COLOR = None
    BACKGROUND = Vec4(0, 0, 0.35, 1)
    # The fog is the town's own (see afterFinish).
    FOG = ((0, 0, 1), 0.0019)
    CAMERA_FAR = 1500.0
    # The town is one model, already merged and lit: the arena leaves it be.
    LIGHT = ((1, 1, 1), (0, 0, 0), (0, 0, 0))

    def build(self):
        self.town = Town(self.root, night=True)
        # Held here so the arena's own merging leaves the town alone.
        self.townRoot = self.town.root
        # The toons' and cogs' night tint is the arena's; the town has its own night.
        self.townRoot.setColorScaleOff(1)
        self.sky = None
        self.game = None
        self.keys = DirectObject()
        self.cogWalls = None
        self.doorOpen = False
        self.cogsOut = 0
        # The cogs' walking map with Toon Hall the toons' and with the Cog building on it (worked out the first time it lands).
        self.freeGround = None
        self.takenGround = None
        self.playerSpeed = 0.0
        self.playerWas = None
        # Everything that moves, and Disney's triggers. The round starts at
        # night: the power switch has been thrown and the shops are asleep.
        self.life = TownLife(self.town)
        self.life.onPower = self.__power
        self.life.toggleSleepWake()
        self.life.settle(25.0)

    def setGame(self, game):
        """The Survival game, once its toons are in: they set off the
        town's triggers."""
        self.game = game
        self.life.groundAt = self.__ground
        self.life.openAt = self.__open
        self.life.ownerAt = self.__owner
        self.life.onLanded = self.__landed
        # The Cogs take Toon Hall for the Gag-Snatcher rounds, and only
        # then (in Disney's plaza a toon walking up to it set them off):
        # the round's cogs are the ones that come out of their building,
        # and when the last of them is gone the toons have Toon Hall back.
        self.life.hallTrigger = False
        self.life.onOpen = self.__doorOpens
        # (Disney's two doodle keys, P to make the plaza's doodle heel and H
        # to bring it over, are not part of Survival: the doodle idles and
        # wanders about the plaza on its own, Arthur 2026-11-15.)

    def roundStarted(self, roundNum, snatcher):
        self.doorOpen = False
        self.cogsOut = 0
        if snatcher:
            self.life.takeover()

    def roundEnded(self, roundNum, snatcher):
        """The round's last cog is gone: Toon Hall is the toons' again
        (until the next Gag-Snatcher round)."""
        if not self.life.restore():
            return
        self.doorOpen = False
        if self.cogWalls is not None:
            self.cogWalls.removeNode()
            self.cogWalls = None
        if self.game is not None and self.freeGround is not None:
            # The ground the building stood on, and the ground behind it, can be walked again.
            self.game.arena.setReachState(self.freeGround)

    def __doorOpens(self):
        self.doorOpen = True

    def snatcherDoor(self, alive):
        """Where the round's next cog comes out, as (kind, place, heading):
        out of the door of the Cog building on Toon Hall, the way Disney's
        five did (four Flunkies side by side, then the Big Cheese in front
        of them), and after those five wherever there is room at the door.
        None while the building is still coming down or the doorway is
        full; False if there is no building to come out of."""
        game = self.game
        if game is None or not self.life.takenOver:
            return False
        if not self.doorOpen:
            return None
        arena = game.arena
        k = self.cogsOut
        for slot in ((k,) if k < 5 else COG_DOOR_ORDER):
            door = render.getRelativePoint(self.townRoot, Point3(COG_DOOR[0] + COG_DOOR_SIDE[slot], COG_DOOR[1] - (6.0 if slot == 4 else 0.0), COG_DOOR[2]))
            cell = arena.nearestCell(door)
            if cell is None:
                continue
            spot = arena.cellPoint(cell)
            if any((cog.pos[0] - spot[0]) ** 2 + (cog.pos[1] - spot[1]) ** 2 < COG_DOOR_ROOM ** 2 for cog in alive):
                continue
            self.cogsOut += 1
            return ('tbc' if k == 4 else 'f') if k < 5 else None, spot, 180.0
        return None

    @staticmethod
    def __inBase(x, y, margin=0.0):
        """Whether a spot of the town is under the landed Cog building
        (or within margin of its walls)."""
        n = len(COG_BASE)
        for k in range(n):
            ax, ay = COG_BASE[k]
            bx, by = COG_BASE[(k + 1) % n]
            ex, ey = bx - ax, by - ay
            length = (ex * ex + ey * ey) ** 0.5
            # How far to the left of this side (the inside) the spot is.
            if (ex * (y - ay) - ey * (x - ax)) / length < -margin:
                return False
        return True

    def __landed(self):
        """The Cog building is down on Toon Hall. It is wider than Toon
        Hall was, so from now on its walls are solid, the cogs' walking
        map loses the ground under it, and anybody who stood there is put
        down in front of it."""
        low, high = COG_WALL
        node = CollisionNode('cogBuildingWalls')
        n = len(COG_BASE)
        for k in range(n):
            a, b = COG_BASE[k], COG_BASE[(k + 1) % n]
            node.addSolid(CollisionPolygon(Point3(a[0], a[1], low), Point3(b[0], b[1], low),
                                           Point3(b[0], b[1], high), Point3(a[0], a[1], high)))
        node.setIntoCollideMask(ToontownGlobals.WallBitmask)
        node.setFromCollideMask(BitMask32.allOff())
        self.cogWalls = self.townRoot.attachNewNode(node)
        game = self.game
        if game is None:
            return
        arena = game.arena
        town = self.townRoot

        def under(point, margin=2.0):
            spot = town.getRelativePoint(render, Point3(point))
            return self.__inBase(spot[0], spot[1], margin)

        door = render.getRelativePoint(town, Point3(*COG_DOOR))
        if self.takenGround is None:
            # The ground behind Toon Hall is cut off by the wider building: it goes too.
            self.freeGround = arena.reachState()
            arena.closeCells(under, anchor=door)
            self.takenGround = arena.reachState()
        else:
            arena.setReachState(self.takenGround)
        step = arena.REACH_STEP

        def caught(point):
            if under(point, 1.0):
                return True
            cell = (int(round(point[0] / step)), int(round(point[1] / step)))
            return cell not in arena.reach and arena.nearestCell(point) is None

        def out(point):
            """The open spot nearest to someone caught under or behind it."""
            best, bestDist = None, None
            for spot in arena.reachList:
                d = (spot[0] - point[0]) ** 2 + (spot[1] - point[1]) ** 2
                if bestDist is None or d < bestDist:
                    best, bestDist = spot, d
            return Point3(best) if best is not None else door

        player = getattr(game, 'player', None)
        if player is not None and caught(player.getPos()):
            player.body.setPos(render, out(player.getPos()))
        for npc in game.npcs:
            if caught(npc.getPos()):
                npc.pos = out(npc.getPos())
                npc.toon.setPos(npc.pos)
        for cog in game.cogs:
            if not cog.dead and caught(cog.pos):
                cog.pos = out(cog.pos)
                cog.suit.setPos(cog.pos)
                cog.route = None

    def __open(self, x, y, z):
        """Whether a toon could stand at a point of the town: the cogs'
        walking map knows."""
        arena = self.game.arena
        reach = getattr(arena, 'reach', None)
        if not reach:
            return False
        spot = render.getRelativePoint(self.townRoot, Point3(x, y, z))
        step = arena.REACH_STEP
        there = reach.get((int(round(spot[0] / step)), int(round(spot[1] / step))))
        return there is not None and abs(there[2] - spot[2]) < 6.0

    def __owner(self):
        player = getattr(self.game, 'player', None)
        if player is None:
            return None
        return self.townRoot.getRelativePoint(render, player.getPos()), self.playerSpeed

    def __ground(self, x, y, z):
        """The floor under a point of the town (the Gag Shop's bubbles land
        on it)."""
        spot = render.getRelativePoint(self.townRoot, Point3(x, y, z))
        floor = self.game.arena.groundZ(spot[0], spot[1], spot[2])
        if floor is None:
            return None
        return self.townRoot.getRelativePoint(render, Point3(spot[0], spot[1], floor))[2]

    def __power(self):
        """A toon touched the power switch: day turns to night or night
        to day, and the shops wake up or fall asleep."""
        self.life.toggleSleepWake()
        self.setNight(not self.town.night)

    def afterFinish(self):
        self.addTask(self.__frame, 'frame')

    def __frame(self, task):
        if self.sky is None:
            # The arena makes the sky and the fog after the map: take hold
            # of them once they are there.
            sky = camera.find('**/=sky')
            if not sky.isEmpty() and not sky.find('**/night').isEmpty():
                self.sky = sky
                self.town.useSky(sky)
            attrib = self.root.getAttrib(FogAttrib)
            if attrib is not None and attrib.getFog() is not None:
                fog = attrib.getFog()
                # Disney's fog thickens with the square of the distance.
                fog.setMode(Fog.MExponentialSquared)
                fog.setExpDensity(self.town.fogDensity())
                fog.setMode(Fog.MExponentialSquared)
                self.town.fog = fog
                fog.setColor(self.town.fogColor(self.town.night))
        eye = camera.getPos(self.townRoot)
        forward = self.townRoot.getRelativeVector(camera, Vec3(0, 1, 0))
        self.life.update(globalClock.getDt(), eye, forward)
        game = self.game
        if game is not None and getattr(game, 'player', None) is not None:
            spots = [self.townRoot.getRelativePoint(render, game.player.getPos())]
            dt = globalClock.getDt()
            if self.playerWas is not None and dt > 1e-4:
                self.playerSpeed = (spots[0] - self.playerWas).length() / dt
            self.playerWas = spots[0]
            spots += [self.townRoot.getRelativePoint(render, npc.getPos()) for npc in game.npcs]
            self.life.walkers(spots)
        return task.cont

    def setNight(self, night):
        """Day or night for the whole map: the town, the sky, the fog and
        the tint on the toons and cogs."""
        self.town.setNight(night)
        self.root.setColorScale(NIGHT_TINT if night else DAY_TINT)
        base.setBackgroundColor(Vec4(0, 0, 0.35, 1) if night else Vec4(1, 1, 1, 1))

    def destroy(self):
        PreviewMap.destroy(self)
        self.keys.ignoreAll()
        self.game = None
        self.life.destroy()
        self.town.destroy()
