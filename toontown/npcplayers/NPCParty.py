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
from panda3d.core import Point3

from toontown.building.DistributedElevatorAI import DistributedElevatorAI
from toontown.building.DistributedElevatorFSMAI import DistributedElevatorFSMAI
from toontown.golf.DistributedGolfCourseAI import DistributedGolfCourseAI
from toontown.npcplayers.NPCBattleCrew import isNPC
from toontown.suit.DistributedBossCogAI import DistributedBossCogAI
from toontown.npcplayers.NPCNav import getNav
from toontown.minigame.DistributedMinigameAI import DistributedMinigameAI
from toontown.safezone.DistributedGolfKartAI import DistributedGolfKartAI
from toontown.safezone.DistributedTrolleyAI import DistributedTrolleyAI
from toontown.toonbase import ToontownGlobals

TELEPORT_TIME = 2.6
RUN_SPEED = ToontownGlobals.ToonForwardSpeed
FOLLOW_DISTANCE = 10.0
CATCH_UP_DISTANCE = 45.0

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

    def getElevators(self):
        return [obj for obj in list(self.air.doId2do.values())
                if isinstance(obj, (DistributedElevatorAI, DistributedElevatorFSMAI, DistributedGolfKartAI, DistributedTrolleyAI))]

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
                for npc in npcs:
                    npc.asSender(elevator.requestExit)
                    npc.busy = False
                continue
            if not players or None not in seats:
                continue
            if getattr(elevator, 'npcBoarding', 0) > globalClock.getFrameTime():
                continue
            player = players[0]
            npc = self.pickBoarder(elevator, player)
            if npc is not None:
                elevator.npcBoarding = globalClock.getFrameTime() + 1.0
                self.board(npc, elevator, player)

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
        self.take(npc, player)
        npc.walk = None
        npc.busy = True
        playerPos = self.manager.getPlayerPos(player)
        spot = self.spotNear(playerPos, 6.0)
        if npc.zoneId != elevator.zoneId:
            npc.b_setLocation(self.air.districtId, elevator.zoneId)
        npc.placeAt(spot[0], spot[1], spot[2], random.uniform(-180, 180))
        npc.b_setAnimState('TeleportIn', 1.0)

        def getOn(task):
            if npc.isDeleted() or elevator.isDeleted():
                return Task.done
            npc.b_setAnimState('Happy', 1.0)
            if isAccepting(elevator) and None in seatsOf(elevator):
                npc.asSender(elevator.requestBoard)
            # Seated or not, the boarding is over; a seated toon stays put
            # (see follow) until the elevator leaves.
            npc.busy = False
            return Task.done

        taskMgr.doMethodLater(TELEPORT_TIME, getOn, 'npcBoard-%d' % npc.doId)

    def spotNear(self, pos, distance):
        nav = getNav()
        for i in range(8):
            angle = random.uniform(0, 2 * math.pi)
            spot = Point3(pos[0] + distance * math.cos(angle), pos[1] + distance * math.sin(angle), pos[2])
            ground = nav.groundZ(spot[0], spot[1], spot[2])
            if ground is not None and nav.clearLine(Point3(pos), Point3(spot[0], spot[1], ground)):
                return Point3(spot[0], spot[1], ground)
        return Point3(pos)

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
            if player.zoneId != npc.zoneId:
                if getAreaId(player.zoneId) is not None:
                    # Back out in town: the trip is over.
                    self.disband(npc)
                    continue
                if npc.busy:
                    continue
                self.notify.info('NPC %s follows %d to zone %d' % (npc.doId, player.doId, player.zoneId))
                npc.b_setLocation(self.air.districtId, player.zoneId)
                spot = self.spotNear(self.manager.getPlayerPos(player), 5.0)
                npc.placeAt(spot[0], spot[1], spot[2], random.uniform(-180, 180))
                npc.b_setAnimState('Happy', 1.0)
                npc.walk = None
                continue
            if npc.busy or npc.walk is not None:
                continue
            if self.isPlaying(npc):
                # A golf course or a trolley game puts each toon where it
                # wants them.
                continue
            if [e for e in self.getElevators() if player.doId in seatsOf(e)]:
                continue
            playerPos = self.manager.getPlayerPos(player)
            distance = (npc.getPos() - playerPos).length()
            if distance <= FOLLOW_DISTANCE:
                continue
            target = self.spotNear(playerPos, 4.0 + random.uniform(0, 3))
            path = getNav().walkable(npc.getPos(), target) if distance < CATCH_UP_DISTANCE else None
            if path:
                npc.walk = [path, RUN_SPEED, None, None]
            else:
                npc.placeAt(target[0], target[1], target[2], npc.getH())

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

    def isPlaying(self, npc):
        return any(isinstance(obj, (DistributedGolfCourseAI, DistributedMinigameAI)) and npc.doId in obj.avIdList
                   for obj in self.air.doId2do.values() if getattr(obj, 'zoneId', None) == npc.zoneId)

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
