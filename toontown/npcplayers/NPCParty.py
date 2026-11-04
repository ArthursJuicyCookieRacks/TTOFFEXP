"""NPC players who go along with the player: into elevators, cog buildings,
factories, mints, offices, country clubs and boss fights.

When the player takes a seat, NPCs take the other seats. Those NPCs are then
the player's party: they go wherever the player goes until the player is back
in a playground or on a street, follow the player around inside, join the
player's battles, and answer the handshakes the places they are in wait for
from each toon (the way a client answers for its own toon).
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from panda3d.core import Point3, Vec3

from toontown.building.DistributedElevatorAI import DistributedElevatorAI
from toontown.building.DistributedElevatorExtAI import DistributedElevatorExtAI
from otp.local.ExecutionContext import getClientBuiltin
from toontown.building.DistributedElevatorFSMAI import DistributedElevatorFSMAI
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium.DistributedCogdoInteriorAI import DistributedCogdoInteriorAI
from toontown.building.DistributedSuitInteriorAI import DistributedSuitInteriorAI
from toontown.golf.DistributedGolfCourseAI import DistributedGolfCourseAI
from toontown.npcplayers.NPCSettings import wantsTrolleyCompany, wantsHelp, forgetHelpAnswer
from toontown.npcplayers.NPCBattleCrew import isNPC
from toontown.suit.DistributedBossCogAI import DistributedBossCogAI
from toontown.npcplayers.NPCNav import getNav
from toontown.npcplayers.NPCPathfinder import getPathfinder, WALK, JUMP, DROP, BOARD, RIDE, CELL
from toontown.minigame.DistributedMinigameAI import DistributedMinigameAI
from toontown.safezone.DistributedGolfKartAI import DistributedGolfKartAI
from toontown.racing.DistributedRaceAI import DistributedRaceAI
from toontown.safezone.DistributedTrolleyAI import DistributedTrolleyAI
from toontown.toonbase import ToontownGlobals

TELEPORT_TIME = 2.6
RUN_SPEED = ToontownGlobals.ToonForwardSpeed
FOLLOW_DISTANCE = 10.0
CATCH_UP_DISTANCE = 45.0
# An NPC this close to the player gets on an elevator from where it is,
# after a moment; one further off teleports in this far from the player.
WALK_ON_DISTANCE = 70.0
WALK_ON_DELAY = (0.4, 1.5)
TELEPORT_IN_DISTANCE = (9.0, 14.0)
# How long the run out of a won building's elevator takes on the clients.
WALK_OUT_TIME = 6.0
# Inside a place (a factory, a mint, an office, a golf course, a cog
# building) each toon finds its own way (NPCPathfinder): to a spot of its own
# near the player, or to the player's battle, which it joins once it is this
# close.
JOIN_REACH = 20.0
SPREAD = (5.0, 9.0)
# A new route when the player has gone this far from where the old one ends.
REROUTE = 12.0
# Only a toon with no way at all to the player for this long (it fell
# somewhere it can't get out of) is brought back by teleport.
LAST_RESORT = 60.0
# How long a toon waits for a platform to come, and to ride it across.
BOARD_PATIENCE = 30.0
# A hop from one moving platform to the next: when its middle is this near
# (a paint mixer is 10 across: its edge is then a short jump away).
HOP_REACH = 11.0
# The widest gap between two platforms' edges a toon jumps (a running
# jump carries about 15).
HOP_GAP = 13.5
LEG_DEBUG = True
# Stuck this long, a toon looks for a crate to push (NPCFacilities.planCrate).
CRATE_AFTER = 6.0
RIDE_PATIENCE = 40.0
CELL_JUMP = 4.0
# How far apart toons on one route run.
LANE_WIDTH = 1.6

# For each place that waits on every toon in it: the state it waits in, and
# what the toon's client sends there. A place is matched by its class or the
# classes it is made from.
HANDSHAKES = {
    'DistributedSuitInteriorAI': {
        'WaitForAllToonsInside': 'setAvatarJoined',
        'Elevator': 'elevatorDone',
        'ReservesJoining': 'reserveJoinDone',
    },
    'DistributedCogdoInteriorAI': {
        'WaitForAllToonsInside': 'setAvatarJoined',
        'Elevator': 'elevatorDone',
        'ReservesJoining': 'reserveJoinDone',
    },
}


def seatsOf(elevator):
    # The trolley calls its seats slots, and is boardable rather than
    # accepting.
    if isinstance(elevator, DistributedTrolleyAI):
        return elevator.slots
    return elevator.seats


def isAccepting(elevator):
    if isinstance(elevator, DistributedTrolleyAI):
        return elevator.boardable
    return elevator.accepting


def stateOf(obj):
    fsm = getattr(obj, 'fsm', None)
    if fsm is not None and hasattr(fsm, 'getCurrentState'):
        state = fsm.getCurrentState()
        return state.getName() if state else None
    return getattr(obj, 'state', None)


def handshakesFor(obj):
    for cls in type(obj).__mro__:
        table = HANDSHAKES.get(cls.__name__)
        if table is not None:
            return table
    return None


class NPCParty:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCParty')

    def __init__(self, manager):
        self.manager = manager
        self.air = manager.air
        self.members = []

    def destroy(self):
        for npc in self.members[:]:
            self.manager.despawn(npc, quietly=True)
        self.members = []

    def partyOf(self, player):
        return [npc for npc in self.members if npc.party == player.doId and not npc.isDeleted()]

    def take(self, npc, player):
        area = getattr(npc, 'area', None)
        if area is not None and npc in area.npcs:
            area.npcs.remove(npc)
        npc.area = None
        npc.party = player.doId
        if npc not in self.members:
            self.members.append(npc)

    def disband(self, npc):
        if npc in self.members:
            self.members.remove(npc)
        npc.party = None
        self.manager.despawn(npc, quietly=True)

    # --- Seats ---

    ELEVATOR_CLASSES = (DistributedElevatorAI, DistributedElevatorFSMAI, DistributedGolfKartAI, DistributedTrolleyAI)
    ACTIVITY_CLASSES = (DistributedGolfCourseAI, DistributedMinigameAI, DistributedRaceAI, DistCogdoGameAI)
    INTERIOR_CLASSES = (DistributedSuitInteriorAI, DistributedCogdoInteriorAI)
    # A building's states in which every toon rides in its elevator: the
    # NPCs stay in their seats beside the player (the clients put them
    # there) instead of walking or teleporting off.
    RIDE_STATES = ('WaitForAllToonsInside', 'Elevator')

    def _objectsOfType(self, classes):
        # Scanning every distributed object several times per NPC per tick
        # showed up in profiles (a few ms per tick in a field office), so the
        # typed lists are cached.
        # Rebuilt when an object comes or goes, or after half a second.
        key = (len(self.air.doId2do), int(globalClock.getFrameTime() * 2))
        cache = getattr(self, '_typedCache', None)
        if cache is None or cache[0] != key:
            cache = self._typedCache = (key, {})
        found = cache[1].get(classes)
        if found is None:
            found = cache[1][classes] = [obj for obj in list(self.air.doId2do.values()) if isinstance(obj, classes)]
        return found

    def getElevators(self):
        return list(self._objectsOfType(self.ELEVATOR_CLASSES))

    def fillSeats(self):
        for elevator in self.getElevators():
            seats = seatsOf(elevator)
            seated = [self.air.doId2do.get(s) for s in seats if s]
            players = [t for t in seated if t is not None and not isNPC(t)]
            npcs = [t for t in seated if isNPC(t)]
            if not isAccepting(elevator):
                continue
            if npcs and not players:
                # The player got off; so do they.
                self.notify.info('elevator %d: no player aboard (seats %s); its NPCs get off' % (elevator.doId, seats))
                for npc in npcs:
                    npc.asSender(elevator.requestExit)
                    npc.busy = False
                continue
            if not players:
                elevator.npcDeclined = None
                # Asked again (Setup: Turn based) when a player next gets on.
                forgetHelpAnswer(elevator.doId)
                continue
            if getattr(elevator, 'npcDeclined', None) == players[0].doId:
                # The player sent them out (see readyAnswer); they stay out
                # until the player gets off and on again.
                continue
            if None not in seats:
                self.askReady(elevator, players[0])
                continue
            if getattr(elevator, 'npcBoarding', 0) > globalClock.getFrameTime():
                continue
            # No more on the way than there are seats left.
            if len(getattr(elevator, 'npcOnTheWay', ())) >= list(seats).count(None):
                continue
            player = players[0]
            if isinstance(elevator, DistributedTrolleyAI):
                if not wantsTrolleyCompany(player.doId):
                    # The player chose to ride solo.
                    continue
            elif not self.partyOf(player) and wantsHelp(player.doId, elevator.doId) is not True:
                # Setup: Solo, or Turn based with the player yet to say Need
                # Help! (see NPCHelpPrompt). A party already along (they
                # were let in at the first elevator) rides on without asking.
                continue
            npc = self.pickBoarder(elevator, player)
            if npc is not None:
                elevator.npcBoarding = globalClock.getFrameTime() + 1.0
                if not hasattr(elevator, 'npcOnTheWay'):
                    elevator.npcOnTheWay = set()
                elevator.npcOnTheWay.add(npc.doId)
                self.board(npc, elevator, player)

    # --- Ready to go? ---

    def askReady(self, elevator, player):
        """Every seat is taken, by the player and NPCs: the countdown stops
        and the player is asked whether to go now (see NPCReadyPrompt)."""
        if not isinstance(elevator, DistributedElevatorExtAI) or getattr(elevator, 'npcReadyAsked', False):
            return
        if elevator.fsm.getCurrentState().getName() != 'waitCountdown':
            return
        tasks = taskMgr.getTasksNamed(elevator.uniqueName('countdown-timer'))
        if not tasks:
            return
        elevator.npcReadyAsked = True
        elevator.npcTimeLeft = max(1.0, tasks[0].wakeTime - globalClock.getFrameTime())
        taskMgr.remove(elevator.uniqueName('countdown-timer'))
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(elevator.doId) if base is not None and getattr(base, 'cr', None) else None
        if client is not None:
            # The client's elevator shows the question on its next frame.
            client.npcReadyQuestion = True
        self.notify.info('elevator %d is full; asking %d to start' % (elevator.doId, player.doId))

    def readyAnswer(self, player, elevatorId, start):
        elevator = self.air.doId2do.get(elevatorId)
        if elevator is None or not getattr(elevator, 'npcReadyAsked', False):
            return False
        elevator.npcReadyAsked = False
        if elevator.fsm.getCurrentState().getName() != 'waitCountdown':
            return False
        if start:
            elevator.fsm.request('allAboard')
            return True
        # Everyone else walks out, and the countdown goes on.
        elevator.npcDeclined = player.doId
        for avId in list(seatsOf(elevator)):
            npc = self.air.doId2do.get(avId) if avId else None
            if isNPC(npc):
                npc.asSender(elevator.requestExit)
                npc.busy = False
                # Back to wandering the lobby, not the player's party.
                if npc in self.members:
                    self.members.remove(npc)
                npc.party = None
        elevator.setCountdown(elevator.npcTimeLeft)
        return True

    def pickBoarder(self, elevator, player):
        from toontown.npcplayers.NPCPlayerManagerAI import getAreaId
        party = [npc for npc in self.partyOf(player)
                 if npc.crew is None and not npc.busy and npc.doId not in seatsOf(elevator)]
        if party:
            return party[0]
        areaId = getAreaId(elevator.zoneId)
        if areaId is None:
            # Inside, only the toons who came along can get on.
            return None
        area = self.manager.areas.get(areaId)
        if area is None:
            return None
        free = [npc for npc in area.npcs if npc.crew is None and not npc.busy and not npc.isDeleted()
                and self.canBoard(npc, elevator)]
        if not free:
            return None
        return random.choice(free)

    def canBoard(self, npc, elevator):
        check = getattr(elevator, 'checkBoard', None)
        if check is None:
            return True
        try:
            return check(npc) == 0
        except Exception:
            return True

    def board(self, npc, elevator, player):
        self.notify.info('NPC %s boards %s %d with %d' % (npc.doId, elevator.__class__.__name__, elevator.doId, player.doId))
        wasMember = npc in self.members
        self.take(npc, player)
        npc.walk = None
        npc.busy = True
        playerPos = self.manager.getPlayerPos(player)
        delay = TELEPORT_TIME
        if npc.zoneId == elevator.zoneId and (npc.getPos() - Point3(playerPos)).length() < WALK_ON_DISTANCE:
            # Close by: it just gets on, and the elevator walks it to its
            # seat from where it stands.
            delay = random.uniform(*WALK_ON_DELAY)
        else:
            # From elsewhere: it teleports in a little way off, never on top
            # of the player (who is inside the elevator).
            spot = self.spotNear(playerPos, random.uniform(*TELEPORT_IN_DISTANCE), avoid=playerPos)
            if npc.zoneId != elevator.zoneId:
                npc.b_setLocation(self.air.districtId, elevator.zoneId)
            npc.placeAt(spot[0], spot[1], spot[2], random.uniform(-180, 180))
            npc.b_setAnimState('TeleportIn', 1.0)

        def getOn(task):
            getattr(elevator, 'npcOnTheWay', set()).discard(npc.doId)
            if npc.isDeleted() or elevator.isDeleted():
                self.notify.info('NPC %s boarding %s: gone (%s, %s)' % (npc.doId, elevator.doId, npc.isDeleted(), elevator.isDeleted()))
                return Task.done
            npc.b_setAnimState('Happy', 1.0)
            if isAccepting(elevator) and None in seatsOf(elevator):
                npc.asSender(elevator.requestBoard)
            if npc.doId in seatsOf(elevator):
                self.notify.info('NPC %s is on %s: seats %s' % (npc.doId, elevator.doId, seatsOf(elevator)))
            if npc.doId not in seatsOf(elevator):
                self.notify.info('NPC %s did not get on %s: accepting %s, seats %s, check %s, zone %s/%s, hp %s/%s' % (
                    npc.doId, elevator.doId, isAccepting(elevator), seatsOf(elevator),
                    getattr(elevator, 'checkBoard', lambda av: None)(npc), npc.zoneId, elevator.zoneId,
                    npc.hp, getattr(elevator, 'minLaff', None)))
            # The boarding is over; a seated toon stays put (see follow)
            # until the elevator leaves, and one left standing goes back
            # to what it was doing.
            npc.busy = False
            if npc.doId not in seatsOf(elevator) and not wasMember:
                self.disband(npc)
            return Task.done

        taskMgr.doMethodLater(delay, getOn, 'npcBoard-%d' % npc.doId)

    def sameFacility(self, npc, player):
        """Whether the NPC is in the same facility as the player, only in
        another of its rooms (one scene, walkable between)."""
        from toontown.toonbase import ToontownGlobals
        if npc.zoneId < ToontownGlobals.DynamicZonesBegin or player.zoneId < ToontownGlobals.DynamicZonesBegin:
            return False
        # (Its rooms, its battles: zones of their own, all in one scene.)
        from otp.level.DistributedLevelAI import DistributedLevelAI
        inLevel = False
        for obj in list(self.air.doId2do.values()):
            if isinstance(obj, DistributedLevelAI) and player.doId in getattr(obj, 'avIdList', ()) \
                    and npc.doId in getattr(obj, 'avIdList', ()):
                inLevel = True
                break
        return inLevel and (npc.getPos() - self.manager.getPlayerPos(player)).length() < 1500.0

    def facilityFloor(self, npc, player):
        """Which floor (its object) of a mint, office or country club the
        two are on together."""
        for obj in list(self.air.doId2do.values()):
            if obj.__class__.__name__ in ('DistributedStageAI', 'DistributedMintAI', 'DistributedCountryClubAI') and \
                    player.doId in getattr(obj, 'avIds', ()) and npc.doId in getattr(obj, 'avIds', ()):
                return obj.doId
        return None

    def inTheOpen(self, spot, reach=2.5):
        """Whether a toon there could walk off at least three ways."""
        nav = getNav()
        ways = 0
        for k in range(4):
            a = k * math.pi / 2
            if nav.clearLine(spot, Point3(spot[0] + reach * math.cos(a), spot[1] + reach * math.sin(a), spot[2])):
                ways += 1
        return ways >= 3

    def spotNear(self, pos, distance, avoid=None):
        nav = getNav()
        for i in range(8):
            angle = random.uniform(0, 2 * math.pi)
            spot = Point3(pos[0] + distance * math.cos(angle), pos[1] + distance * math.sin(angle), pos[2])
            ground = nav.groundZ(spot[0], spot[1], spot[2])
            if ground is not None and nav.clearLine(Point3(pos), Point3(spot[0], spot[1], ground)) and \
                    not self.covered(spot[0], spot[1], ground):
                return Point3(spot[0], spot[1], ground)
        if avoid is not None:
            # From inside an elevator every line out hits its walls: a spot
            # with ground under it that far off, in the open (not inside a
            # couch or a desk, whose walls have no floor of their own).
            fallback = None
            for i in range(12):
                angle = random.uniform(0, 2 * math.pi)
                spot = Point3(pos[0] + distance * math.cos(angle), pos[1] + distance * math.sin(angle), pos[2])
                ground = nav.groundZ(spot[0], spot[1], spot[2])
                if ground is not None and not self.covered(spot[0], spot[1], ground):
                    spot = Point3(spot[0], spot[1], ground)
                    if self.inTheOpen(spot):
                        return spot
                    fallback = fallback or spot
            if fallback is not None:
                return fallback
            return Point3(pos[0] + distance, pos[1], pos[2])
        # Somewhere lower round about (the player on a post's cap: the
        # crate tops or the floor beside it), never inside a crate.
        for r in (3.0, 4.5, 6.0):
            for k in range(8):
                angle = random.uniform(0, 2 * math.pi)
                x, y = pos[0] + r * math.cos(angle), pos[1] + r * math.sin(angle)
                ground = nav.groundZ(x, y, pos[2])
                if ground is not None and ground <= pos[2] + 1.0 and not self.covered(x, y, ground):
                    return Point3(x, y, ground)
        # No floor found round about (it is not drawn yet): still not right
        # on top of the player or of another toon sent here.
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(1.6, 2.6)
        return Point3(pos[0] + r * math.cos(angle), pos[1] + r * math.sin(angle), pos[2])

    # --- Going along ---

    def follow(self):
        from toontown.npcplayers.NPCPlayerManagerAI import getAreaId
        for npc in self.members[:]:
            if npc.isDeleted():
                self.members.remove(npc)
                continue
            player = self.air.doId2do.get(npc.party)
            if player is None:
                self.disband(npc)
                continue
            if npc.crew is not None:
                continue
            seated = [e for e in self.getElevators() if npc.doId in seatsOf(e)]
            if seated:
                continue
            helper = getattr(npc, 'helper', False)
            if player.zoneId != npc.zoneId and helper and not npc.busy and \
                    getAreaId(player.zoneId) is not None and getAreaId(player.zoneId) == getAreaId(npc.zoneId) and \
                    (npc.getPos() - self.manager.getPlayerPos(player)).length() < CATCH_UP_DISTANCE:
                # Asked along (see NPCFriends): it walks with the player
                # from one part of the place to the next.
                npc.b_setLocation(self.air.districtId, player.zoneId)
            if player.zoneId != npc.zoneId:
                if getAreaId(player.zoneId) is not None and not helper:
                    # Back out in town: the trip is over.
                    self.disband(npc)
                    continue
                if npc.busy:
                    continue
                if self.sameFacility(npc, player):
                    floor = self.facilityFloor(npc, player)
                    if floor is not None and getattr(npc, 'facilityFloor', floor) != floor:
                        # Up the elevator to the next floor of an office or
                        # a country club with the player: it comes out where
                        # the player does, not where it stood a floor down.
                        npc.facilityFloor = floor
                        self.notify.info('NPC %s rides up with %d to the next floor' % (npc.doId, player.doId))
                        self.manager.teleportTo(npc, player.zoneId, self.spotNear(self.manager.getPlayerPos(player), 4.0))
                        continue
                    npc.facilityFloor = floor
                    # From room to room of a factory, mint or office (each
                    # its own zone): it goes on on foot, from where it is.
                    npc.b_setLocation(self.air.districtId, player.zoneId)
                    continue
                npc.facilityFloor = self.facilityFloor(npc, player)
                self.notify.info('NPC %s follows %d to zone %d' % (npc.doId, player.doId, player.zoneId))
                spot = self.spotNear(self.manager.getPlayerPos(player), 5.0)
                self.manager.teleportTo(npc, player.zoneId, spot)
                continue
            if self.ridingElevator(npc):
                npc.walk = None
                npc.inElevatorRide = True
                continue
            if getattr(npc, 'inElevatorRide', False):
                # Off the elevator with the player: it goes on from where the
                # ride left it, not from where it stood before.
                npc.inElevatorRide = False
                self.syncToClient(npc)
            if npc.busy:
                continue
            if self.manager.facilities.holds(npc):
                # Busy with a puzzle of the place (see NPCFacilities).
                continue
            if self.inBossFight(npc):
                # In a boss fight each toon does its own job (see
                # NPCBossCrew), rather than tagging along.
                continue
            if self.isPlaying(npc):
                # A golf course, a trolley game, a field office game or a
                # race puts each toon where it wants them.
                npc.walk = None
                continue
            if getAreaId(player.zoneId) is None and getattr(npc, 'route', None) is not None \
                    and getattr(npc, 'onMover', None) is None and not self.routeStillGood(npc, player):
                # The player went another way: a new route after this leg.
                npc.route = None
            if npc.walk is None and getattr(npc, 'onMover', None) is None and self.outOfSweep(npc):
                # Never stands where a stomper slams across.
                continue
            if npc.walk is None and getattr(npc, 'onMover', None) is not None and self.makeRoom(npc):
                # Someone came onto its small top right where it stands.
                continue
            if npc.walk is not None:
                continue
            if [e for e in self.getElevators() if player.doId in seatsOf(e)]:
                continue
            if getAreaId(player.zoneId) is None:
                # Inside a place: its own way there, like a player.
                self.goOwnWay(npc, player)
                continue
            playerPos = self.manager.getPlayerPos(player)
            distance = (npc.getPos() - playerPos).length()
            if distance <= FOLLOW_DISTANCE:
                continue
            target = self.spotNear(playerPos, 4.0 + random.uniform(0, 3))
            path = getNav().walkable(npc.getPos(), target) if distance < CATCH_UP_DISTANCE else None
            if path:
                npc.walk = [path, self.paceOf(npc), None, None]
            elif self.manager.facilities.trailWalk(npc, player, playerPos):
                # No straight way there (a gap, a platform): it goes the way
                # the player went, jumps and all.
                pass
            else:
                # Left too far behind to walk: it teleports to the player,
                # the way a friend would.
                self.manager.teleportTo(npc, None, target, npc.getH())

    # --- Finding its own way inside ---

    def ownSpot(self, npc, player, playerPos):
        """Where this toon likes to stand near the player: its own side of
        the player (from its doId), so a group spreads out instead of
        queueing behind."""
        nav = getNav()
        h = math.radians(player.getH())
        small = self.smallTop(playerPos)
        if small:
            # The player is on something with room for one more (a post's
            # cap, a gear's top): the first of the party to get there joins
            # the player, the rest wait their turn round it.
            if self.turnOnTop(npc, player, playerPos):
                for k in range(8):
                    angle = h + math.pi + k * (math.pi / 4)
                    spot = Point3(playerPos[0] - 1.4 * math.sin(angle), playerPos[1] + 1.4 * math.cos(angle), playerPos[2])
                    ground = nav.groundZ(spot[0], spot[1], spot[2])
                    if ground is not None and abs(ground - playerPos[2]) < 0.8 and not self.covered(spot[0], spot[1], ground):
                        return Point3(spot[0], spot[1], ground)
            return self.spotBelow(npc, playerPos) or Point3(playerPos)
        for tries in range(4):
            angle = h + (npc.doId % 7) * (2 * math.pi / 7) + tries * 0.9
            radius = SPREAD[0] + (npc.doId % 5) * (SPREAD[1] - SPREAD[0]) / 4.0
            spot = Point3(playerPos[0] - radius * math.sin(angle), playerPos[1] + radius * math.cos(angle), playerPos[2])
            ground = nav.groundZ(spot[0], spot[1], spot[2])
            if ground is not None and nav.clearLine(Point3(playerPos), Point3(spot[0], spot[1], ground)) and \
                    not self.covered(spot[0], spot[1], ground):
                return Point3(spot[0], spot[1], ground)
        return self.spotBelow(npc, playerPos) or Point3(playerPos)

    def covered(self, x, y, z):
        """Whether there is something to stand on just over (x, y, z): the
        spot is inside a crate or a post (whose walls only face out), or
        under a table, not where a toon can stand."""
        ground = getNav().groundZ(x, y, z + 5.0)
        if ground is not None and ground > z + 1.0:
            return True
        # (A crate taller than that: its walls close round the spot.)
        from toontown.npcplayers.NPCPathfinder import getPathfinder
        return any(g.inSolid(x, y, z, 0.3) for g in list(getPathfinder().grids.values()))

    def smallTop(self, pos):
        """Whether pos is on a top with room for about two (a post's cap):
        floor at its height only close round it."""
        nav = getNav()
        if not nav.available():
            return False
        level = 0
        for k in range(8):
            angle = k * (math.pi / 4)
            x, y = pos[0] + 3.2 * math.cos(angle), pos[1] + 3.2 * math.sin(angle)
            ground = nav.groundZ(x, y, pos[2])
            # (A step up or down a stair counts as more of the same floor.)
            if ground is not None and abs(ground - pos[2]) < 1.3 and not self.covered(x, y, ground):
                level += 1
        return level <= 2

    def turnOnTop(self, npc, player, playerPos):
        """One of the party at a time on a small top with the player: the
        one already up there, else the nearest."""
        mates = [m for m in self.members if getattr(m, 'party', None) == player.doId and not m.isDeleted()]
        def up(m):
            p = m.getPos()
            return math.hypot(p[0] - playerPos[0], p[1] - playerPos[1]) < 3.0 and abs(p[2] - playerPos[2]) < 1.0
        already = [m for m in mates if up(m)]
        if already:
            return npc is min(already, key=lambda m: m.doId)
        return npc is min(mates, key=lambda m: ((m.getPos() - playerPos).length(), m.doId))

    def spotBelow(self, npc, playerPos):
        """A place to wait near the player when there is no room beside it:
        the floor or the crate tops round about, each toon its own side."""
        nav = getNav()
        for r in (3.5, 5.0, 6.5):
            for k in range(8):
                angle = (npc.doId % 7) * (2 * math.pi / 7) + k * (math.pi / 4)
                x, y = playerPos[0] + r * math.cos(angle), playerPos[1] + r * math.sin(angle)
                ground = nav.groundZ(x, y, playerPos[2])
                if ground is None or ground > playerPos[2] + 1.0 or self.covered(x, y, ground):
                    continue
                return Point3(x, y, ground)
        return None

    def spotAround(self, npc, center, radius=None):
        nav = getNav()
        for tries in range(4):
            angle = (npc.doId % 7) * (2 * math.pi / 7) + tries * 0.9
            r = radius if radius is not None else SPREAD[0] + (npc.doId % 5) * (SPREAD[1] - SPREAD[0]) / 4.0
            spot = Point3(center[0] - r * math.sin(angle), center[1] + r * math.cos(angle), center[2])
            ground = nav.groundZ(spot[0], spot[1], spot[2] + 2)
            if ground is not None and abs(ground - center[2]) < 3 and \
                    nav.clearLine(Point3(center), Point3(spot[0], spot[1], ground)):
                return Point3(spot[0], spot[1], ground)
        return Point3(center)

    def lane(self, npc, points, grid):
        """The route's points moved a little to the NPC's own side of the
        way (from its doId), where there is floor and no wall: toons on the
        same route run side by side, not inside each other."""
        if not points:
            return points
        from toontown.npcplayers.NPCPathfinder import cellOf, CHEST
        nav = getNav() if grid is None else None
        if grid is None and not nav.available():
            return points
        # Each member of the party its own lane (by its place in the party,
        # so no two share one): right, left, further right, further left...
        mates = sorted(m.doId for m in self.members if getattr(m, 'party', None) == getattr(npc, 'party', None))
        index = mates.index(npc.doId) if npc.doId in mates else npc.doId % 5
        side = ((index // 2) + 1) * LANE_WIDTH * (1 if index % 2 == 0 else -1)
        out = []
        prev = npc.getPos()
        for p in points:
            d = Vec3(p - prev)
            d.setZ(0)
            if d.length() < 0.5:
                out.append(p)
                prev = p
                continue
            d.normalize()
            q = Point3(p[0] - d[1] * side, p[1] + d[0] * side, p[2])
            if grid is None:
                # (Streets and playgrounds: the scene's own floor.)
                h = nav.groundZ(q[0], q[1], p[2] + 1.0)
                if h is not None and (abs(h - p[2]) > 0.8 or not nav.clearLine(Point3(p), Point3(q[0], q[1], h))):
                    h = None
                if h is not None:
                    out.append(Point3(q[0], q[1], h))
                else:
                    out.append(p)
                prev = p
                continue
            ix, iy = cellOf(q[0], q[1])
            h = grid.heightNear(ix, iy, p[2], 0.8, 0.8)
            if h is not None and not grid.blocked(Point3(p[0], p[1], p[2] + CHEST), Point3(q[0], q[1], h + CHEST)):
                out.append(Point3(q[0], q[1], h))
            else:
                out.append(p)
            prev = p
        return out

    def battlePos(self, battle):
        """Where the battle is in the world. (A facility's battles keep
        their spot relative to the room; the client has the battle placed.)"""
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(battle.doId) if base is not None and hasattr(base, 'cr') else None
        if client is not None and hasattr(client, 'getPos') and not client.isEmpty():
            return Point3(client.getPos(base.render))
        return Point3(battle.pos)

    def goalFor(self, npc, player):
        battle = getattr(npc, 'battleGoal', None)
        if battle is not None:
            if battle.isDeleted() or battle.fsm is None or npc.doId in battle.toons or not battle.toonCanJoin():
                npc.battleGoal = None
            else:
                # Its own spot around the battle, so the toons coming to
                # it don't run in on top of each other.
                return self.spotAround(npc, self.battlePos(battle)), JOIN_REACH * 0.6
        return Point3(self.manager.getPlayerPos(player)), FOLLOW_DISTANCE

    def routeStillGood(self, npc, player):
        goal, reach = self.goalFor(npc, player)
        end = getattr(npc, 'routeGoal', None)
        return end is not None and (end - goal).length() < REROUTE

    def headToBattle(self, npc, battle):
        if getattr(npc, 'battleGoal', None) is not battle:
            npc.battleGoal = battle
            npc.route = None
            npc.nextSearch = 0
            getPathfinder().cancel(npc)

    def goOwnWay(self, npc, player):
        finder = getPathfinder()
        now = globalClock.getFrameTime()
        if getattr(npc, 'route', None):
            self.nextLeg(npc)
            return
        npc.route = None
        goal, reach = self.goalFor(npc, player)
        pos = npc.getPos()
        if (pos - goal).length() <= reach:
            npc.stuckSince = None
            finder.cancel(npc)
            return
        if finder.pending(npc):
            return
        result = finder.result(npc)
        if result is not None:
            if result.path:
                npc.route = finder.legs(pos, result.path, result.grid)
                npc.routeGrid = result.grid
                npc.routeGoal = goal
                npc.stuckSince = None
                self.count('routes')
                self.nextLeg(npc)
                return
            # No way over the floors (the way on is a moving platform, or
            # the toon fell): how the floors carry toons over (the
            # player's crossing) is the way.
            if self.manager.facilities.trailWalk(npc, player, self.manager.getPlayerPos(player)):
                self.count('trail')
                return
            if getattr(npc, 'onMover', None) is not None and 'start' in getattr(result, 'why', ''):
                # Carried along on a platform: a way is found once it stops.
                npc.nextSearch = now + 1.0
                return
            why = getattr(result, 'why', '')
            if getattr(npc, 'onMover', None) is None and npc.walk is None and \
                    ('start' in why or getattr(result, 'visits', 1000) < 400) and self.stepOut(npc):
                # On a lip or in a corner the floors don't join up from:
                # a step off it, and look again.
                npc.nextSearch = now + 1.0
                return
            if getattr(npc, 'stuckSince', None) is not None and now - npc.stuckSince > CRATE_AFTER and \
                    not [m for m in self.members if getattr(m, 'job', None) is not None and
                         m.job.__class__.__name__ == 'CrateJob'] and (self.manager.facilities.buttonJob(npc, player, stuck=True) or
                                                                        self.manager.facilities.planCrate(npc, player)):
                # No way on but over a crate wall: it pushes the crate up
                # against it, as a player would.
                npc.stuckSince = None
                return
            if getattr(npc, 'stuckSince', None) is None:
                npc.stuckSince = now
                self.notify.info('NPC %s has no way from %s to %s yet: %s' % (
                    npc.doId, pos, goal, getattr(result, 'why', '?')))
            if [m for m in self.members if getattr(m, 'job', None) is not None and
                    m.job.__class__.__name__ in ('CrateJob', 'ButtonJob')] or \
                    now - getattr(self.manager.facilities, 'puzzleDoneAt', -100.0) < 20.0:
                # A mate is pushing the crate or pressing the button that
                # opens the way (or just did): wait for it, as players do.
                npc.stuckSince = now
            if now - npc.stuckSince > LAST_RESORT:
                self.notify.info('NPC %s found no way to %s for %d s: teleporting' % (npc.doId, goal, LAST_RESORT))
                self.count('teleport')
                npc.stuckSince = None
                self.manager.teleportTo(npc, None, self.spotNear(goal, 5.0), npc.getH())
                return
            npc.nextSearch = now + 2.0
            return
        if now < getattr(npc, 'nextSearch', 0):
            return
        # Each toon takes its own moment to set off, as players do.
        if getattr(npc, 'setOffAt', None) is None:
            npc.setOffAt = now + 0.2 + (npc.doId % 7) * 0.22
        if now < npc.setOffAt:
            return
        npc.setOffAt = None
        target = goal if getattr(npc, 'battleGoal', None) is not None else self.ownSpot(npc, player, goal)
        trail = self.manager.facilities.trails.get(player.doId)
        way = list(trail['points']) if trail and trail['zoneId'] == player.zoneId else None
        search = finder.request(npc, target, way)
        if search is not None:
            # Its own taste in lines through a room (see Search.taste).
            search.taste = npc.doId
        npc.nextSearch = now + 1.0

    def nextLeg(self, npc):
        route = npc.route
        if not route:
            npc.route = None
            return
        kind, data = route[0]
        if kind == WALK:
            if any(self.manager.facilities.stomperBlocks(npc.zoneId, p) for p in data[:4]) and \
                    not self.manager.facilities.inAnySweep(npc.zoneId, npc.getPos()):
                # A stomper is down in the way: wait for it to go up. (Not
                # standing where one slams across, though: on out of it.)
                return
            if self.manager.facilities.moverWallBlocks(npc.getPos(), data[:3]):
                # A sliding wall is across the way: wait for it to open
                # (they open every few seconds; not for ever).
                now = globalClock.getFrameTime()
                if getattr(npc, 'wallWaitSince', None) is None:
                    npc.wallWaitSince = now
                if now - npc.wallWaitSince < 12.0:
                    return
            npc.wallWaitSince = None
            route.pop(0)
            npc.walk = [self.lane(npc, list(data), getattr(npc, 'routeGrid', None)), self.paceOf(npc), None, None]
        elif kind == BOARD:
            # Wait at the edge for the platform to be here, then get on.
            now = globalClock.getFrameTime()
            if getattr(npc, 'boardSince', None) is None:
                npc.boardSince = now
            if now - npc.boardSince > BOARD_PATIENCE:
                if LEG_DEBUG:
                    self.notify.info('NPC %s gave up boarding %s (closest %s, onMover %s)' % (
                        npc.doId, data.node[:3], getattr(npc, 'hopMin', None), getattr(npc, 'onMover', None) is not None))
                npc.hopMin = None
                npc.boardSince = None
                npc.route = None
                return
            hopping = getattr(npc, 'onMover', None) is not None
            if hopping:
                # Over from one platform to the next once it swings close,
                # as players time it.
                c = data.center()
                p = npc.getPos()
                here = getattr(npc, 'atStop', None)
                # Over when it swings close, or when both wait at the ends
                # the map put side by side.
                bothWaiting = data.present() and here is not None and here.mover is npc.onMover and here.present()
                gap = (math.hypot(c[0] - p[0], c[1] - p[1]), abs(c[2] - p[2]))
                if getattr(npc, 'hopMin', None) is None or gap[0] < npc.hopMin[0]:
                    npc.hopMin = gap
                if LEG_DEBUG and now - getattr(npc, 'hopLogAt', 0) > 1.5:
                    npc.hopLogAt = now
                    hc = here.center() if here is not None else None
                    self.notify.info('NPC %s hop wait: at %s, own platform %s (stop %s present %s), next %s (present %s) walk %s carried %s cells %s/%s' % (
                        npc.doId, p, hc, here and here.node[:3], here and here.present(), c, data.present(),
                        npc.walk is not None, getattr(npc, 'moverMat', None) is not None,
                        here and len(here.cells), len(data.cells)))
                # The paint mixers pass each other going opposite ways: a
                # player waits at the near edge of its own and jumps the gap
                # as the other comes level.
                close = False
                if here is not None and here.mover is npc.onMover:
                    a = here.center()
                    rA = math.sqrt(max(1, len(here.cells))) * 2.5 / 2.0
                    rB = math.sqrt(max(1, len(data.cells))) * 2.5 / 2.0
                    between = math.hypot(c[0] - a[0], c[1] - a[1])
                    edgeGap = between - rA - rB
                    if edgeGap <= HOP_GAP and abs(c[2] - p[2]) <= 2.5:
                        close = True
                    elif npc.walk is None and between > 0.5 and not getattr(npc, 'atHopEdge', False):
                        # To the near edge (its own place along it), to wait.
                        d = Vec3(c[0] - a[0], c[1] - a[1], 0)
                        d.normalize()
                        mates = sorted(m.doId for m in self.members if getattr(m, 'party', None) == getattr(npc, 'party', None))
                        index = mates.index(npc.doId) if npc.doId in mates else npc.doId % 5
                        side = Vec3(-d[1], d[0], 0) * (((index // 2) + 1) * 1.4 * (1 if index % 2 == 0 else -1))
                        if here.mover.capacity <= 3:
                            # A small top (crates up to its rim): only a
                            # little way toward the next one, never to the rim.
                            side = side * (0.6 / side.length())
                            edge = Point3(a[0], a[1], p[2]) + d * max(0.0, min(1.0, here.mover.halfSize - 2.0)) + side
                        else:
                            edge = Point3(a[0], a[1], p[2]) + d * max(0.0, rA - 2.0) + side
                        npc.walk = [[edge], self.paceOf(npc) * 0.5, None, None]
                        npc.atHopEdge = True
                if not bothWaiting and not close and (math.hypot(c[0] - p[0], c[1] - p[1]) > HOP_REACH or abs(c[2] - p[2]) > 3.0):
                    return
                if len(self.aboard(npc, data)) >= getattr(data, 'capacity', data.mover.capacity):
                    # The next top is full: waits on its own for a later pass.
                    return
                npc.atHopEdge = False
            elif not data.present() or len(self.aboard(npc, data)) >= getattr(data, 'capacity', data.mover.capacity):
                # Not here yet, or full (a paint mixer's top holds two:
                # players take it in turns): waits beside it, clear of where
                # it comes down (its post is no wall on the NPCs' map).
                self.clearOfPlatform(npc, data)
                npc.boardSince = now if data.present() else npc.boardSince
                return
            npc.boardSince = None
            route.pop(0)
            self.count('hops' if hopping else 'boards')
            if LEG_DEBUG:
                self.notify.info('NPC %s %s onto %s at %s; next %s' % (npc.doId, 'hops' if hopping else 'boards', data.node[:3], npc.getPos(),
                                                                     [(k, getattr(d, 'node', d) if k in (BOARD, RIDE) else None) for k, d in route[:3]]))
            npc.atStop = data
            npc.boardedAt = globalClock.getFrameTime()
            spot = self.spotOn(npc, data)
            if (npc.getPos() - spot).length() > CELL_JUMP:
                self.manager.facilities.jumpTo(npc, spot)
            else:
                npc.walk = [[spot], self.paceOf(npc), None, None]
            if data.mover.liftDoId:
                lift = self.air.doId2do.get(data.mover.liftDoId)
                if lift is not None:
                    npc.asSender(lift.setAvatarEnter)
            npc.onMover = data.mover
        elif kind == RIDE:
            # Carried along (NPCFacilities.ride) until the platform stops at
            # the other end.
            now = globalClock.getFrameTime()
            if getattr(npc, 'rideSince', None) is None:
                npc.rideSince = now
            if not data.present() or now - npc.rideSince < 0.5:
                if now - npc.rideSince > RIDE_PATIENCE:
                    npc.rideSince = None
                    npc.route = None
                return
            npc.rideSince = None
            route.pop(0)
            self.count('rides')
            if LEG_DEBUG:
                self.notify.info('NPC %s rode to %s at %s; next %s' % (npc.doId, data.node[:3], npc.getPos(),
                                                                     [(k, getattr(d, 'node', d) if k in (BOARD, RIDE) else d) for k, d in route[:2]]))
            npc.atStop = data
            if route and route[0][0] == BOARD:
                # Straight over to the next platform: still carried by this
                # one while it waits for it.
                return
            if data.mover.liftDoId:
                lift = self.air.doId2do.get(data.mover.liftDoId)
                if lift is not None:
                    npc.asSender(lift.setAvatarLeave)
            npc.onMover = None
        elif kind == JUMP:
            route.pop(0)
            self.count('jumps')
            self.manager.facilities.jumpTo(npc, data)
        else:
            route.pop(0)
            npc.walk = [list(data), self.paceOf(npc), None, None]
        if not route:
            npc.route = []

    def paceOf(self, npc):
        """Each toon's own running pace (a little slower or quicker)."""
        # Never quicker than a player (they keep up, not run ahead) and
        # never much slower: 86% to 100% of a player's run, spread by a
        # hash so toons of one party differ, and a little different each
        # leg so they never hold one gap (a train).
        own = 0.88 + ((npc.doId * 7919) % 11) * 0.011
        wobble = 1.0 + 0.02 * math.sin(globalClock.getFrameTime() * 0.7 + npc.doId)
        return RUN_SPEED * min(1.0, own * wobble)

    def stepOut(self, npc):
        """A short step to open floor nearby (off a crate's lip, out of a
        corner), at most once in a while."""
        now = globalClock.getFrameTime()
        if now - getattr(npc, 'steppedOutAt', -100.0) < 8.0:
            return False
        npc.steppedOutAt = now
        nav = getNav()
        if not nav.available():
            return False
        pos = npc.getPos()
        start = (npc.doId % 8) * math.pi / 4
        for r in (2.5, 4.0, 5.5):
            for k in range(8):
                a = start + k * math.pi / 4
                x, y = pos[0] + r * math.cos(a), pos[1] + r * math.sin(a)
                z = nav.groundZ(x, y, pos[2] + 1.5)
                if z is None or z > pos[2] + 1.0 or z < pos[2] - 2.5:
                    continue
                spot = Point3(x, y, z)
                if nav.clearLine(Point3(pos[0], pos[1], pos[2]), spot):
                    npc.walk = [[spot], self.paceOf(npc) * 0.6, None, None]
                    return True
        # Walled in all round (it stands inside a couch's or a desk's
        # walls): a hop over them, onto open floor.
        for r in (3.0, 4.5, 6.0):
            for k in range(8):
                a = start + k * math.pi / 4
                x, y = pos[0] + r * math.cos(a), pos[1] + r * math.sin(a)
                z = nav.groundZ(x, y, pos[2] + 1.5)
                if z is None or abs(z - pos[2]) > 1.0:
                    continue
                spot = Point3(x, y, z)
                if self.inTheOpen(spot):
                    self.manager.facilities.jumpTo(npc, spot)
                    return True
        return False

    def outOfSweep(self, npc):
        """An NPC standing where a stomper slams across (the conveyor past
        the paint mixers) steps out of its way, to the nearer side."""
        facilities = self.manager.facilities
        pos = npc.getPos()
        base = getClientBuiltin('base')
        if base is None:
            return False
        for obj in list(base.cr.doId2do.values()):
            if obj.__class__.__name__ != 'DistributedStomper' or getattr(obj, 'style', None) != 'horizontal' or \
                    getattr(obj, 'model', None) is None or obj.model.isEmpty() or \
                    not facilities.inStomperSweep(obj, pos):
                continue
            lo, hi = facilities.stomperSweep(obj)
            nav = getNav()
            # Out sideways to the way it slams (the way a toon crosses it).
            motion = base.render.getRelativeVector(obj.model.getParent(), Vec3(0, -1, 0))
            if abs(motion[1]) > abs(motion[0]):
                outs = [Point3(lo[0] - 1.8, pos[1], pos[2]), Point3(hi[0] + 1.8, pos[1], pos[2])]
            else:
                outs = [Point3(pos[0], lo[1] - 1.8, pos[2]), Point3(pos[0], hi[1] + 1.8, pos[2])]
            outs.sort(key=lambda o: (o - pos).length())
            for out in outs:
                ground = nav.groundZ(out[0], out[1], pos[2])
                if ground is not None and abs(ground - pos[2]) < 1.5:
                    npc.walk = [[Point3(out[0], out[1], ground)], self.paceOf(npc), None, None]
                    npc.route = None
                    if LEG_DEBUG:
                        self.notify.info('NPC %s steps out of stomper %s to %s' % (npc.doId, obj.doId, out))
                    return True
        return False

    def makeRoom(self, npc):
        """On a small top (a paint mixer), a toon who jumps on right where
        the NPC stands: the NPC steps over to the other side of it, never
        stays standing inside them."""
        stop = getattr(npc, 'atStop', None)
        if stop is None or stop.mover is not npc.onMover or stop.mover.capacity > 3:
            return False
        p = npc.getPos()
        for o in self.aboard(npc, stop):
            q = o.getPos() if o in self.members else self.manager.getPlayerPos(o)
            if math.hypot(q[0] - p[0], q[1] - p[1]) < 1.8 and abs(q[2] - p[2]) < 2.0:
                spot = self.spotOn(npc, stop)
                if math.hypot(spot[0] - p[0], spot[1] - p[1]) > 0.4:
                    npc.walk = [[spot], self.paceOf(npc) * 0.6, None, None]
                    return True
                return False
        return False

    def clearOfPlatform(self, npc, stop):
        if npc.walk is not None:
            return
        c = stop.center()
        p = npc.getPos()
        d = Vec3(p[0] - c[0], p[1] - c[1], 0)
        keep = stop.mover.halfSize + 1.8
        if d.length() >= keep - 0.2:
            return
        if d.length() < 0.1:
            d = Vec3(1, 0, 0)
        d.normalize()
        nav = getNav()
        for turn in (0, 40, -40, 80, -80):
            a = math.atan2(d[1], d[0]) + math.radians(turn)
            x, y = c[0] + keep * math.cos(a), c[1] + keep * math.sin(a)
            ground = nav.groundZ(x, y, p[2])
            if ground is not None and abs(ground - p[2]) < 1.5 and not self.covered(x, y, ground):
                npc.walk = [[Point3(x, y, ground)], self.paceOf(npc) * 0.6, None, None]
                return
        if self.covered(p[0], p[1], p[2]):
            # (Every way out from the middle is under a crate: out the far
            # side, then.)
            for turn in (120, -120, 160, -160, 180):
                a = math.atan2(d[1], d[0]) + math.radians(turn)
                x, y = c[0] + keep * math.cos(a), c[1] + keep * math.sin(a)
                ground = nav.groundZ(x, y, p[2])
                if ground is not None and abs(ground - p[2]) < 1.5 and not self.covered(x, y, ground):
                    npc.walk = [[Point3(x, y, ground)], self.paceOf(npc) * 0.6, None, None]
                    return

    def aboard(self, npc, stop):
        """Who else is on a platform now: the party's NPCs riding it, and
        the player when standing on it."""
        c = stop.center()
        def on(p):
            return math.hypot(p[0] - c[0], p[1] - c[1]) <= stop.mover.halfSize + 0.5 and abs(p[2] - c[2]) < 2.5
        # (Ones it carried and that have since got off do not count.)
        # (One that has just jumped on is in the air, not on it yet: it
        # counts too, so two never take a one-toon top at once.)
        now = globalClock.getFrameTime()
        riders = [m for m in self.members if m is not npc and getattr(m, 'onMover', None) is stop.mover and
                  (on(m.getPos()) or m.walk is not None or now - getattr(m, 'boardedAt', -99) < 4.0)]
        player = self.air.doId2do.get(getattr(npc, 'party', None))
        if player is not None:
            pos = self.manager.getPlayerPos(player)
            if math.hypot(pos[0] - c[0], pos[1] - c[1]) <= stop.mover.halfSize + 0.5 and abs(pos[2] - c[2]) < 2.5:
                riders.append(player)
        return riders

    def spotOn(self, npc, stop):
        """The NPC's own place on a platform or lift (from its doId), so
        riders stand apart."""
        from toontown.npcplayers.NPCPathfinder import cellOf
        center = stop.center()
        # Each rider takes the next free place round the middle.
        aboard = self.aboard(npc, stop)
        slot = len(aboard)
        angle = slot * (2 * math.pi / 5) + (npc.doId % 3) * 0.2
        if stop.mover.capacity <= 3:
            # A small top: across from whoever is on it already, well
            # inside its edge.
            others = [(o.getPos() if o in self.members else self.manager.getPlayerPos(o)) for o in aboard]
            if others:
                p = others[0]
                angle = math.atan2(p[1] - center[1], p[0] - center[0]) + math.pi
            # Alone on it: in the middle. With another: each just off the
            # middle, on opposite sides (a toon is about 2.8 wide, and the
            # crates come right up to its rim).
            r = 0.3 if not others else max(0.6, min(1.5, stop.mover.halfSize - 2.0))
            # A top that slides into a crate at this stop (a paint mixer at
            # its foot, half under the crate beside it): only the part
            # sticking out is stood on, never the part in the crate.
            grid = getattr(stop.mover, 'grid', None)
            solid = grid is not None and grid.solids and stop.cells and \
                any(grid.inSolid(center[0] + 1.5 * math.cos(a), center[1] + 1.5 * math.sin(a), center[2], 1.0)
                    for a in [k * math.pi / 4 for k in range(8)] + [0.0]) or False
            if solid:
                home = stop.worldOf(stop.mover.centerLocal)
                ox = sum(c[0] for c in stop.cells) * CELL / len(stop.cells) - home[0]
                oy = sum(c[1] for c in stop.cells) * CELL / len(stop.cells) - home[1]
                best = None
                for rr in (0.0, 0.5, 1.0, 1.5, 2.0):
                    for k in range(8):
                        a = angle + k * math.pi / 4
                        spot = Point3(center[0] + ox + rr * math.cos(a), center[1] + oy + rr * math.sin(a), center[2])
                        if math.hypot(spot[0] - center[0], spot[1] - center[1]) > stop.mover.halfSize - 0.6:
                            continue
                        if grid.inSolid(spot[0], spot[1], spot[2], 0.9):
                            continue
                        apart = min([math.hypot(spot[0] - o[0], spot[1] - o[1]) for o in others] or [9.0])
                        score = (apart >= 2.2, -rr, apart)
                        if best is None or score > best[0]:
                            best = (score, spot)
                    if best is not None and best[0][0]:
                        break
                if best is not None:
                    return best[1]
                # (No room clear of the crate: as far out of it as it goes.)
                return Point3(center[0] + ox, center[1] + oy, center[2])
            # Its side away from the crates and walls it passes, so the
            # toon stands on it, not half in a crate beside it.
            nav = getNav()
            best = None
            for turn in (0, 45, -45, 90, -90, 135, -135, 180):
                a = angle + math.radians(turn)
                spot = Point3(center[0] + r * math.cos(a), center[1] + r * math.sin(a), center[2])
                reach = Point3(center[0] + (r + 1.6) * math.cos(a), center[1] + (r + 1.6) * math.sin(a), center[2] + 1.5)
                clear = not nav.available() or nav.clearLine(Point3(center[0], center[1], center[2] + 1.5), reach)
                apart = min([math.hypot(spot[0] - o[0], spot[1] - o[1]) for o in others] or [9.0])
                score = (clear, apart >= 2.2, apart)
                if best is None or score > best[0]:
                    best = (score, spot)
                if clear and apart >= 2.8:
                    break
            return best[1]
        # (The cells are where the floor is with the platform at this stop;
        # one swinging past is somewhere else just now.)
        home = stop.worldOf(stop.mover.centerLocal)
        for r in (3.0, 2.4, 1.8, 1.3):
            dx, dy = r * math.cos(angle), r * math.sin(angle)
            if cellOf(home[0] + dx, home[1] + dy) in stop.cells:
                return Point3(center[0] + dx, center[1] + dy, center[2])
        # A small lift: still each on its own side of the middle (a toon
        # is about two wide), never all on the one spot.
        r = 1.1
        return Point3(center[0] + r * math.cos(angle), center[1] + r * math.sin(angle), center[2])

    def count(self, key):
        stats = self.__dict__.setdefault('stats', {})
        stats[key] = stats.get(key, 0) + 1

    def answerHandshakes(self, zoneIndex):
        for npc in self.members:
            if npc.isDeleted():
                continue
            for obj in zoneIndex.get(npc.zoneId, ()):
                self.answerBarriers(npc, obj)
                if isinstance(obj, DistributedBossCogAI) and npc.doId not in obj.looseToons \
                        and npc.doId not in obj.involvedToons:
                    # What a client sends once it is in the boss's zone.
                    npc.asSender(obj.avatarEnter)
                if isinstance(obj, DistributedGolfCourseAI):
                    self.manager.golf.play(npc, obj)
                table = handshakesFor(obj)
                if table is None:
                    continue
                method = table.get(stateOf(obj))
                responses = getattr(obj, 'responses', None)
                if method is None or responses is None or getattr(obj, 'ignoreResponses', 0):
                    continue
                if responses.get(npc.doId) == 0:
                    npc.asSender(getattr(obj, method))

    def inBossFight(self, npc):
        for crew in self.manager.bossCrews.values():
            boss = crew.boss
            if boss is not None and not boss.isDeleted() and boss.zoneId == npc.zoneId and \
                    npc.doId in boss.involvedToons:
                return True
        return False

    def walkOutWith(self, building, victorList):
        """A building the party won hands back its victors: the NPCs go to
        the street with it, so they run out of the elevator beside the
        player, then stay out there as the street's own toons."""
        from toontown.npcplayers.NPCPlayerManagerAI import getAreaId
        zoneId = building.zoneId
        area = self.manager.areas.get(getAreaId(zoneId))
        for avId in victorList:
            npc = self.air.doId2do.get(avId)
            if not isNPC(npc) or npc.isDeleted():
                continue
            if npc in self.members:
                self.members.remove(npc)
            npc.party = None
            npc.crew = None
            npc.walk = None
            npc.inElevatorRide = False
            npc.busy = True
            npc.b_setLocation(self.air.districtId, zoneId)
            if area is not None:
                npc.area = area
                if npc not in area.npcs:
                    area.npcs.append(npc)

            def ready(task, npc=npc):
                if npc.isDeleted():
                    return task.done
                if building.victorResponses is not None and npc.doId in building.victorList:
                    npc.asSender(building.setVictorReady)
                # Out on the street where the run out left it.
                self.syncToClient(npc)
                npc.busy = False
                if npc.area is None:
                    self.manager.despawn(npc)
                return task.done

            taskMgr.doMethodLater(WALK_OUT_TIME, ready, 'npcWalkOut-%d' % npc.doId)

    def ridingElevator(self, npc):
        for obj in self._objectsOfType(self.INTERIOR_CLASSES):
            if getattr(obj, 'zoneId', None) == npc.zoneId and stateOf(obj) in self.RIDE_STATES and \
                    npc.doId in getattr(obj, 'toons', ()):
                return True
        return False

    def syncToClient(self, npc):
        base = getClientBuiltin('base')
        client = base.cr.doId2do.get(npc.doId) if base is not None and getattr(base, 'cr', None) else None
        if client is None or client.isEmpty():
            return
        pos = client.getPos(base.render)
        if (pos - npc.getPos()).length() > 0.5:
            npc.setPosHpr(pos[0], pos[1], pos[2], client.getH(base.render), 0, 0)

    def isPlaying(self, npc):
        for obj in self._objectsOfType(self.ACTIVITY_CLASSES):
            if getattr(obj, 'zoneId', None) != npc.zoneId:
                continue
            if isinstance(obj, (DistributedGolfCourseAI, DistributedMinigameAI)) and npc.doId in obj.avIdList:
                return True
            if isinstance(obj, DistributedRaceAI) and npc.doId in obj.avatars:
                return True
            if isinstance(obj, DistCogdoGameAI) and npc.doId in obj.toons and not obj.isDeleted():
                return True
        return False

    def answerBarriers(self, npc, obj):
        # Many places wait at a barrier for each toon's client to say it is
        # ready (the end of a movie, mostly); the player's client sets the
        # pace, so the NPCs are ready at once.
        barriers = getattr(obj, '_DistributedObjectAI__barriers', None)
        if not barriers:
            return
        for context, barrier in list(barriers.items()):
            if npc.doId in barrier.pendingAvatars:
                npc.asSender(obj.setBarrierReady, context)
