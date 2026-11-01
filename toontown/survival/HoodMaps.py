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
    """An invisible two-sided wall from a to b (x, y)."""
    corners = [Point3(a[0], a[1], low), Point3(b[0], b[1], low), Point3(b[0], b[1], high), Point3(a[0], a[1], high)]
    node = CollisionNode(name)
    node.addSolid(CollisionPolygon(*corners))
    node.addSolid(CollisionPolygon(*reversed(corners)))
    node.setIntoCollideMask(ToontownGlobals.WallBitmask)
    node.setFromCollideMask(BitMask32.allOff())
    return parent.attachNewNode(node)


def stashAll(geom, *patterns):
    for pattern in patterns:
        for node in geom.findAllMatches('**/' + pattern):
            node.stash()


# --- Donald's Dock: the harbour drained, the boat run aground ---

# The boat's place by the east pier (DDSafeZoneLoader puts it there and
# the boat's mopaths start there), in the playground's own space.
DD_BOAT_AGROUND = (Point3(-6, -14, -16.5), Vec3(28, -24, -7))


def dryDock(arena):
    """Donald's Dock with the water gone from the harbour and the fishing
    pond, Donald's boat nose down in the harbour mud, and both bridges
    (the piers that swing up for the boat) always down."""
    geom = arena.geom
    for water in geom.findAllMatches('**/water'):
        # The surfaces and the camera's water plane; the harbour bed and
        # its floor collision stay.
        water.stash()
    for pond in geom.findAllMatches('**/fishing_pond_1'):
        for node in pond.findAllMatches('**/*water*'):
            node.stash()
    # Bridges down, as DistributedBoat lowers them when the boat docks.
    for name, h in (('east_pier', 90), ('west_pier', -90)):
        for pier in geom.findAllMatches('**/' + name):
            pier.setHpr(h, 0.25, 0)
    boat = geom.find('**/donalds_boat')
    if not boat.isEmpty():
        boat.unstash()
        pos, hpr = DD_BOAT_AGROUND
        boat.setPos(boat.getParent(), pos)
        boat.setHpr(hpr)
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
    holder.setPos(pos)
    holder.setH(h)


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


def bossbotCourtyard(arena):
    geom = arena.geom
    stashAll(geom, '*tunnel_sphere*', '*door_trigger*', '*trigger*')
    for hole in geom.findAllMatches('**/doorFrameHole*'):
        hole.hide()


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
            'upgrader': (Point3(-79, 58.7, 6.2), -90),
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
        'description': 'The musical playground after dark, round the sunken pond. Minnie upgrades your gag, '
                       'the trunk waits by the stage and Fisherman Freddy sells Toon Tonics.',
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
        'spots': {
            'upgrader': (Point3(40, 60, 6.5), 180),
            'fisherman': (Point3(-40, -40, -14), 90),
            'trunk': (Point3(30, -60, -14), 0),
            'start': (Point3(0, 60, 6.5), 180),
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
        'upgrader': ('char', 'd', 'Donald'),
        'spots': {
            'upgrader': (Point3(-60, -60, 5.7), 45),
            'fisherman': (Point3(-20, 160, 3.3), 180),
            'trunk': (Point3(40, -60, 5.7), 0),
            'start': (Point3(0, -80, 5.7), 0),
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
        'sky': 'phase_9/models/cogHQ/cog_sky',
        'skyScale': 2.0,
        'upgrader': resistanceToon('Agent Ace Fizzlesprocket', 4001, 'm', 'dls', 6),
        'spots': {
            'upgrader': (Point3(-40, -150, 0), 0),
            'fisherman': (Point3(40, -150, 0), 0),
            'trunk': (Point3(0, -120, 0), 180),
            'start': (Point3(0, -200, 0), 0),
        },
        'trolley': (Point3(-60, -230, 0), 90),
        'reachSpan': 260.0,
        'spawnRing': (40.0, 260.0),
    },
    'bossbot_hq': {
        'title': 'Bossbot HQ',
        'description': "The Bossbots' golf course in the rain. A Toon Resistance agent upgrades your gag, "
                       'Fisherman Freddy came along with his tonics, and the trunk sits by the fountain.',
        'picture': 'phase_4/maps/survival_map_bossbot_hq.jpg',
        'models': (('phase_12/models/bossbotHQ/CogGolfExterior', Point3(0, 0, 0), Vec3(0, 0, 0), 1.0),),
        'setup': 'bossbotCourtyard',
        'sky': 'phase_12/models/bossbotHQ/ttr_m_bossbothq_sky',
        'fog': ((0.15, 0.15, 0.15), 0.004),
        'upgrader': resistanceToon('Agent Penny Pinwheel', 4002, 'f', 'cls', 12),
        'spots': {
            'upgrader': (Point3(-40, 0, 0), 90),
            'fisherman': (Point3(40, 0, 0), -90),
            'trunk': (Point3(0, 40, 0), 180),
            'start': (Point3(0, -40, 0), 0),
        },
        'trolley': (Point3(0, -100, 0), 0),
        'reachSpan': 260.0,
        'spawnRing': (40.0, 260.0),
    },
}
