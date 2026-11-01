"""More Survival maps made from the game's own places.

Three playgrounds loaded straight from their DNA like Toontown Central
(The Brrrgh, Minnie's Melodyland, Donald's Dock) and two Cog HQ courtyards
loaded from their models (Sellbot HQ, Bossbot HQ). Each says who upgrades
the gag there instead of Mickey, and where that one, Fisherman Freddy, the
accessory trunk and the player stand.

Preview maps: none of them is in Map Select (SurvivalArena.MAP_ORDER) yet;
`survival-map <key>` in a prc picks one.
"""

import math

from panda3d.core import (BitMask32, CollisionNode, CollisionPolygon, CollisionTube, NodePath, Point3, TextNode,
                          TransparencyAttrib, Vec3, Vec4)

from toontown.toonbase import ToontownGlobals

# The Toon Resistance's outfit: the purple bandolier shirt with the oil
# splashes from the Resistance hideout, its sleeves and shorts, in white
# (no tint).
RESISTANCE_SHIRT = 214
RESISTANCE_SLEEVE = 108
RESISTANCE_SHORTS = 95
RESISTANCE_SKIRT = 137
WHITE = 27


def resistanceToon(name, seed, gender, head, color):
    """A regular toon in the Toon Resistance's outfit."""
    def make(who):
        from otp.nametag.NametagGroup import NametagGroup
        from toontown.toon import Toon, ToonDNA
        dna = ToonDNA.ToonDNA()
        dna.newToonRandom(seed, gender, 1)
        dna.head = head
        dna.armColor = dna.legColor = dna.headColor = color
        dna.topTex, dna.topTexColor = RESISTANCE_SHIRT, WHITE
        dna.sleeveTex, dna.sleeveTexColor = RESISTANCE_SLEEVE, WHITE
        dna.botTex = RESISTANCE_SHORTS if gender == 'm' else RESISTANCE_SKIRT
        dna.botTexColor = WHITE
        toon = Toon.Toon()
        toon.setName(who)
        toon.setPickable(0)
        toon.setPlayerType(NametagGroup.CCNonPlayer)
        toon.setDNAString(dna.makeNetString())
        toon.animFSM.request('neutral')
        return toon
    return ('toon', make, name)


def wall(parent, a, b, low=-2.0, high=30.0, name='survivalWall'):
    """An invisible wall from a to b (x, y). Thick capsules stacked up,
    not a flat polygon: a toon moving a long way in one slow frame can
    step its centre past a flat wall, and then its back face pushes the
    toon on through."""
    node = CollisionNode(name)
    z = low + 1.5
    while z < high:
        node.addSolid(CollisionTube(a[0], a[1], z, b[0], b[1], z, 2.0))
        z += 3.0
    node.setIntoCollideMask(ToontownGlobals.WallBitmask)
    node.setFromCollideMask(BitMask32.allOff())
    return parent.attachNewNode(node)


def stashAll(geom, *patterns):
    for pattern in patterns:
        for node in geom.findAllMatches('**/' + pattern):
            node.stash()


# --- Donald's Dock: the harbour drained, the boat run aground ---

# Where Donald's boat ended up when the water went: in the east harbour,
# nose down in the mud with its bow toward the south docks, its stern up
# in the air (world space; the boat's bow is its +y).
DD_BOAT_AGROUND = (Point3(15, -10, -0.5), Vec3(200, -40, 9))
# The harbour bed, dried out: from a wet blue to mud.
DD_MUD = Vec4(1.0, 0.8, 0.58, 1)
DD_DRY_WALL = Vec4(1.0, 0.72, 0.5, 1)
# The film of water left in the harbour: just above the bed (-12.333),
# mostly see-through so the mud shows under it.
DD_PUDDLE_Z = -12.2
DD_PUDDLE_TINT = Vec4(1, 1, 1, 0.22)
# The bridges let right down, their far ends on the harbour bed, as ramps
# up from the dry harbour onto the docks (their far ends 17 feet down).
DD_PIER_PITCH = -44.5


def dryDock(arena):
    """Donald's Dock with the water gone from the harbour and the fishing
    pond, Donald's boat nose down in the harbour mud, and both bridges
    (the piers that swing up for the boat) always down."""
    geom = arena.geom
    for water in geom.findAllMatches('**/water'):
        # The harbour water, let down to a thin film over the mud (Arthur:
        # a very thin layer, too shallow to swim in). Only the picture of
        # it: anything to collide with goes, so toons walk the bed.
        bottom = water.getTightBounds(render)
        if bottom is None:
            water.stash()
            continue
        water.setZ(render, water.getZ(render) + DD_PUDDLE_Z - bottom[0][2])
        stashAll(water, '+CollisionNode')
        water.setColorScale(DD_PUDDLE_TINT)
        water.setTransparency(TransparencyAttrib.MAlpha)
        water.setDepthWrite(False)
    for bed in geom.findAllMatches('**/under_water_surface'):
        bed.setColorScale(DD_MUD)
    # The harbour walls and pilings are painted wet-blue below the old
    # waterline: dried out, they read as the water still being there.
    for pattern in ('boardwalk_supports', 'pylons'):
        for node in geom.findAllMatches('**/' + pattern):
            node.setColorScale(DD_DRY_WALL)
    for pond in geom.findAllMatches('**/fishing_pond_1'):
        for node in pond.findAllMatches('**/*water*'):
            node.stash()
    # Bridges down, as DistributedBoat lowers them when the boat docks.
    for name, h in (('east_pier', 90), ('west_pier', -90)):
        for pier in geom.findAllMatches('**/' + name):
            pier.setHpr(h, DD_PIER_PITCH, 0)
    boat = geom.find('**/donalds_boat')
    if not boat.isEmpty():
        boat.unstash()
        pos, hpr = DD_BOAT_AGROUND
        boat.setPos(render, pos)
        boat.setHpr(render, hpr)
        wheel = boat.find('**/wheel')
        if not wheel.isEmpty():
            wheel.hide()
        # Its deck isn't a floor to stand on any more, and it no longer
        # needs to carry toons: just the walls round it.
        stashAll(boat, 'donalds_boat_floor', 'pole-tube')


# --- The Cog HQs ---

TROLLEY_MODEL = 'phase_4/models/modules/trolley_station_TT'


def addTrolley(arena):
    """A trolley to escape on, where the map puts it."""
    spot = arena.map.get('trolley')
    if spot is None:
        return
    pos, h = spot
    station = loader.loadModel(TROLLEY_MODEL)
    holder = arena.geom.attachNewNode('prop_trolley_station_DNARoot')
    station.reparentTo(holder)
    # Just the trolley, its platform and awning: the green Toontown hill
    # and its tunnels behind it belong to a playground, not a Cog HQ.
    stashAll(station, 'hill_1', 'tunnelL', 'tunnelR')
    holder.setPos(pos)
    holder.setH(h)


SELLBOT_TUNNEL_WALLS = (((-40, -256), (40, -256)), ((140, -195), (140, -115)))


def sellbotCourtyard(arena):
    geom = arena.geom
    # The tunnels and doors lead nowhere: walls across them.
    stashAll(geom, '*tunnel_sphere*', '*Tunnel*sphere*', '*door_trigger*', '*trigger*')
    from toontown.toonbase import ToontownGlobals as TG
    for hole in geom.findAllMatches('**/doorFrameHole*'):
        hole.hide()
    signs = loader.loadModel('phase_4/models/props/sign_sellBotHeadHQ')
    sign = signs.find('**/sign_sellBotHeadHQ')
    for x, y, z, h in ((0.0, -291.5, 29, 180.0), (148.625, -155, 27, -90.0)):
        copy = sign.copyTo(geom)
        copy.setPosHprScale(x, y, z, h, 0, 0, 1.5, 1.5, 1.5 * 0.81)
    signs.removeNode()
    # Invisible walls across the tunnel mouths (to Daisy Gardens and to the
    # factory), so nobody walks off down them.
    for a, b in SELLBOT_TUNNEL_WALLS:
        wall(geom, a, b)


def bossbotCourtyard(arena):
    geom = arena.geom
    stashAll(geom, '*tunnel_sphere*', '*door_trigger*', '*trigger*')
    for hole in geom.findAllMatches('**/doorFrameHole*'):
        hole.hide()
    # An invisible wall just inside the tunnel to Chip 'n Dale's Acorn
    # Acres, so nobody walks off down it.
    wall(geom, (415, -30), (415, 35), low=-14.0)
    # The courtyard moving the way BossbotCogHQLoader makes it move.
    arena.animProps.append(BossbotMotion(geom))


class BossbotMotion:
    """Bossbot HQ's moving parts, as BossbotCogHQLoader starts them: the
    fountain's three gear tiers turning (17 seconds a turn, the middle one
    the other way), oil spouting from its four geysers, and the geysers
    out on the grounds rising up and sinking back, five at a time. Kept
    with the arena's animated props, which stop it with the map."""
    GEAR_TIME = 17.0
    ACTIVE = 5
    MODEL = 'phase_12/models/bossbotHQ/ttr_m_ara_bbhq_geyser'

    def __init__(self, geom):
        from direct.interval.IntervalGlobal import LerpHprInterval
        self.geom = geom
        self.lerps = []
        for name, turn in (('Top', 360), ('Middle', -360), ('Bottom', 360)):
            for gear in geom.findAllMatches('**/Fountain_Geom:' + name):
                self.lerps.append(LerpHprInterval(gear, self.GEAR_TIME, (turn, 0, 0), (0, 0, 0)))
        geyser = loader.loadModel(self.MODEL)
        for i in range(1, 5):
            spot = geom.find('**/Fountain_Geom:fountain_geyser%d' % i)
            if not spot.isEmpty():
                geyser.copyTo(spot)
        self.spouts = []
        for spot in geom.findAllMatches('**/geyser*'):
            copy = geyser.copyTo(spot)
            copy.setScale(0.001)
            self.spouts.append(copy)
        geyser.removeNode()
        self.active = []
        self.tasks = []
        self.tracks = []
        for lerp in self.lerps:
            lerp.loop()
        if self.spouts:
            for i in range(min(self.ACTIVE, len(self.spouts))):
                name = 'survivalGeyser-%d-%d' % (id(self), i)
                taskMgr.doMethodLater(i * 2.0, self.__spout, name)
                self.tasks.append(name)

    def __spout(self, task):
        import random
        from direct.interval.IntervalGlobal import Func, Sequence
        free = [g for g in self.spouts if g not in self.active and not g.isEmpty()]
        if not free:
            task.delayTime = 3.0
            return task.again
        geyser = random.choice(free)
        scale = random.randint(5, 18) / 10.0
        length = random.randint(5, 12)
        bob = Sequence()
        t = 0.0
        while t < length:
            bob.append(geyser.scaleInterval(1.25, scale + 0.1, blendType='easeInOut'))
            bob.append(geyser.scaleInterval(1.25, scale, blendType='easeInOut'))
            t += 2.5
        track = Sequence(Func(self.active.append, geyser),
                         geyser.scaleInterval(1.5, scale, startScale=0.001, blendType='easeOut'), bob,
                         geyser.scaleInterval(1.5, 0.001, blendType='easeIn'),
                         Func(self.__done, geyser))
        self.tracks.append(track)
        track.start()
        task.delayTime = length + 3 + 3
        return task.again

    def __done(self, geyser):
        if geyser in self.active:
            self.active.remove(geyser)
        self.tracks = [t for t in self.tracks if t.isPlaying()]

    def enter(self):
        pass

    def exit(self):
        for name in self.tasks:
            taskMgr.remove(name)
        self.tasks = []
        for track in self.tracks + self.lerps:
            track.pause()
        self.tracks = []
        self.lerps = []

    def delete(self):
        self.exit()


HOOD_MAPS = {
    'brrrgh': {
        'title': 'The Brrrgh',
        'description': 'The frozen playground after dark, snow piled high round the frozen pond. '
                       'Pluto upgrades your gag by Toon HQ, the trunk waits by the snowman '
                       'and Fisherman Freddy sells Toon Tonics at the pond.',
        'picture': 'phase_4/maps/survival_map_brrrgh.jpg',
        'dayAndNight': True,
        'storage': ('phase_4/dna/storage.xml', 'phase_8/dna/storage_BR.xml', 'phase_8/dna/storage_BR_sz.xml'),
        'dna': 'phase_8/dna/the_burrrgh_sz.xml',
        'offset': Point3(0, 0, 0),
        'daySky': 'phase_3.5/models/props/BR_sky',
        'blockTunnels': True,
        'upgrader': ('char', 'p', 'Pluto'),
        'spots': {
            # Right in front of Toon HQ's door (Arthur), looking out over the playground.
            'upgrader': (Point3(-88.6, 60.7, 6.2), -90),
            # On the bank of the fishing hole, facing the playground.
            'fisherman': (Point3(-40, -38, 6.2), -125),
            # Beside the snowman, its lid facing the player's way in.
            'trunk': (Point3(20, 12, 6.2), 0),
            'start': (Point3(0, -60, 6.2), 0),
        },
        'reachSpan': 220.0,
        'spawnRing': (40.0, 220.0),
    },
    'melodyland': {
        'title': "Minnie's Melodyland",
        'description': 'The musical playground after dark: a deep bowl round the piano-key pond, horn slides down from '
                       'the rim. Minnie upgrades your gag at Toon HQ, Fisherman Freddy sells Toon Tonics at the pond.',
        'picture': 'phase_4/maps/survival_map_melodyland.jpg',
        'dayAndNight': True,
        'storage': ('phase_4/dna/storage.xml', 'phase_6/dna/storage_MM.xml', 'phase_6/dna/storage_MM_sz.xml'),
        'dna': 'phase_6/dna/minnies_melody_land_sz.xml',
        'offset': Point3(0, 0, 0),
        'daySky': 'phase_6/models/props/MM_sky',
        'blockTunnels': True,
        'upgrader': ('char', 'mn', 'Minnie'),
        # The ramps down into the bowl are steeper than a reach cell's
        # usual three feet.
        'reachRise': 4.5,
        # The horn slides are only a few feet wide.
        'reachStep': 2.5,
        # The bowl's floor is at about -15.
        'lowest': -20,
        'spots': {
            # Against Toon HQ's north door, centred on it, looking out.
            'upgrader': (Point3(76.4, -10.5, -13.5), 0),
            # At the edge of the fishing pond in the middle, facing out.
            'fisherman': (Point3(-15, -50, -13), 139),
            # Out on the bowl's floor, the lid toward the pond.
            'trunk': (Point3(-35, 35, -15), 32.5),
            'start': (Point3(0, 40, -15), 180),
        },
        'reachSpan': 220.0,
        'spawnRing': (40.0, 220.0),
    },
    'dock': {
        'title': "Donald's Dock",
        'description': "The harbour's run dry and Donald's boat lies nose down in the mud. The bridges stay down, "
                       'so you can run across them or down into the old harbour. Donald upgrades your gag, '
                       'Fisherman Freddy sells Toon Tonics by the empty fishing pond.',
        'picture': 'phase_4/maps/survival_map_dock.jpg',
        'dayAndNight': True,
        'storage': ('phase_4/dna/storage.xml', 'phase_6/dna/storage_DD.xml', 'phase_6/dna/storage_DD_sz.xml'),
        'dna': 'phase_6/dna/donalds_dock_sz.xml',
        'offset': Point3(0, 0, 0),
        'daySky': 'phase_3.5/models/props/BR_sky',
        'blockTunnels': True,
        'setup': 'dryDock',
        # The dry harbour bed is at about -12.
        'lowest': -20,
        'upgrader': ('dockChar', 'dw', 'Donald'),
        'spots': {
            # Against Toon HQ's east door (the HQ is a ship in the north
            # channel), centred on it, looking out.
            'upgrader': (Point3(-5.2, 104.6, 1.7), -90),
            # Where the real fisherman stands, at the head of the dry pond.
            'fisherman': (Point3(-12.5, 178, 3.3), 180),
            # On the little island in the middle of the dry harbour.
            'trunk': (Point3(-24, 0, 6), 0),
            # On the south boardwalk, looking out over the dry harbour.
            'start': (Point3(-30, -75, 6), -20),
        },
        'reachSpan': 230.0,
        'spawnRing': (40.0, 230.0),
    },
    'sellbot_hq': {
        'title': 'Sellbot HQ',
        'description': "The Sellbots' own courtyard. A Toon Resistance agent upgrades your gag, "
                       'Fisherman Freddy came along with his tonics, and the trunk sits by the factory road.',
        'picture': 'phase_4/maps/survival_map_sellbot_hq.jpg',
        'models': (('phase_9/models/cogHQ/SellbotHQExterior', Point3(0, 0, 0), Vec3(0, 0, 0), 1.0),),
        'setup': 'sellbotCourtyard',
        # The crater in the middle of the courtyard goes down to about -20.
        'lowest': -30,
        'sky': 'phase_9/models/cogHQ/cog_sky',
        'skyScale': 2.0,
        'upgrader': resistanceToon('Agent Ace Fizzlesprocket', 4001, 'm', 'dls', 6),
        'spots': {
            # In front of the tunnel back to Daisy Gardens, the way the
            # toons came in, like Mickey at Toontown Central's tunnel.
            'upgrader': (Point3(0, -246, 0), 0),
            'fisherman': (Point3(-95, -130, 0), -90),
            'trunk': (Point3(72, -120, 0), -90),
            # On the courtyard in front of the Sellbot towers, looking out
            # over the crater.
            'start': (Point3(0, -95, 0), 180),
        },
        'reachSpan': 260.0,
        'spawnRing': (40.0, 260.0),
    },
    'bossbot_hq': {
        'title': 'Bossbot HQ',
        'description': "The Bossbots' golf grounds round the fountain. A Toon Resistance agent upgrades your gag, "
                       'Fisherman Freddy came along with his tonics, and the trunk sits by the fountain.',
        'picture': 'phase_4/maps/survival_map_bossbot_hq.jpg',
        'models': (('phase_12/models/bossbotHQ/CogGolfExterior', Point3(0, 0, 0), Vec3(0, 0, 0), 1.0),),
        'setup': 'bossbotCourtyard',
        'lowest': -30,
        'sky': 'phase_12/models/bossbotHQ/ttr_m_bossbothq_sky',
        'fog': ((0.15, 0.15, 0.15), 0.002),
        'upgrader': resistanceToon('Agent Penny Pinwheel', 4002, 'f', 'cls', 12),
        'spots': {
            # East of the fountain, facing the tunnel from Chip 'n Dale's
            # Acorn Acres, the way the toons came in.
            'upgrader': (Point3(27, 0, 0), -90),
            'fisherman': (Point3(-27, 0, 0), 90),
            'trunk': (Point3(0, -27, 0), 0),
            'start': (Point3(130, 0, 0), 90),
        },
        'reachSpan': 200.0,
        'spawnRing': (40.0, 200.0),
    },
}
