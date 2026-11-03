"""Toontown Central after dark: the playground of Survival Mode.

Only the playground is loaded, straight from its DNA, with no district,
no Place and no doors or tunnels that do anything. The sky is the dark
one and the whole scene is dimmed to moonlight. The stations (Mickey by
the Loopy Lane tunnel, the trunk and the fisherman at the gazebo) stand
where the real playground has those landmarks.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import (Fog, BitMask32, CollisionHandlerQueue, CollisionNode, CollisionPolygon, CollisionRay, CollisionSegment, CollisionTraverser, CollisionTube,
                          CompassEffect, ConfigVariableDouble, ModelPool, NodePath, Point3, TexturePool, Vec3, Vec4)

from toontown.dna.DNAStorage import DNAStorage
from toontown.hood import SkyUtil
from toontown.npcplayers.NPCNav import getNav
from toontown.toonbase import ToontownGlobals

STORAGE_FILES = ('phase_4/dna/storage.xml', 'phase_4/dna/storage_TT.xml', 'phase_4/dna/storage_TT_sz.xml')
DNA_FILE = 'phase_4/dna/toontown_central_sz.xml'
SKY_FILE = 'phase_3.5/models/props/BR_sky'
# Moonlight over the playground.
NIGHT_SCALE = Vec4(0.42, 0.46, 0.62, 1)
SKY_COLOR = Vec4(0.22, 0.24, 0.36, 1)
# Maps that can be played in the daytime keep their own lighting and the
# playground's blue sky.
DAY_SKY_FILE = 'phase_3.5/models/props/TT_sky'

# Where things are in the playground (from its DNA).
LOOPY_LANE_TUNNEL = (Point3(-239.67, 64.08, -6.18), -90)
FISHERMAN = (Point3(-68, -2, -1.975), 27)
GAZEBO = (Point3(-60.94, -8.8, -2), -178)
# Where the accessory trunk stands: beside the fisherman (on his right,
# the player's left facing him) and a step ahead, clear of the gazebo's
# railing behind him so the open lid never reaches it.
TRUNK_BESIDE = 6.0
TRUNK_AHEAD = 3.0
# The gazebo's base is a hexagon about 7 feet from its middle to each panel;
# the panel facing away from the fisherman is centred on this heading
# (measured with rays round the gazebo).
TRUNK_PANEL_ANGLE = 302.0
TRUNK_FROM_GAZEBO = 10.5
TRUNK_RADIUS = 1.7
# The player starts on the grass in front of Toon Hall.
PLAYER_START = (Point3(0, -20, 0), 0)
# Cogs land out of sight, this far out from the middle and this far from
# every toon.
SPAWN_RING = (45.0, 130.0)
SPAWN_CLEAR = 30.0
VIEW_HALF_ANGLE = 60.0
# Cogs never land in or around these: the gazebo (railings and steps all
# round, Arthur saw cogs stuck in it) and the stations' corners.
NO_LANDING = ((GAZEBO[0], 22.0), (FISHERMAN[0], 12.0), (LOOPY_LANE_TUNNEL[0], 16.0))
# The playgrounds Survival can be played in. 'ttc' is today's Toontown
# Central. 'beta_ttc' is the Toontown Central of the beta 1.0.5 release
# (round, with the pond, the gazebo in the middle and tunnels to Daisy's,
# Donald's and Minnie's), converted by tools/offline/art/beta-ttc into
# resources-overlay/phase_4/beta105. Map Select offers it as
# "Old School Toontown".
BETA_DNA = 'phase_4/beta105/dna/'
MAPS = {
    'ttc': {
        'title': 'Toontown Central',
        'description': 'The playground after dark. Cogs fall from the sky in rounds, more of them each round, tougher and faster. '
                       'Mickey upgrades your gag by the Loopy Lane tunnel, the trunk by the gazebo hands out a random one, '
                       'and Fisherman Freddy sells Toon Tonics.',
        'picture': 'phase_4/maps/survival_map_ttc.jpg',
        'storage': STORAGE_FILES,
        'dna': DNA_FILE,
        'offset': Point3(0, 0, 0),
        'mickeyTunnel': None,
        'mickeyStep': 9.0,
        'loopyLane': LOOPY_LANE_TUNNEL,
        'fisherman': FISHERMAN,
        'gazebo': GAZEBO,
        'trunkPanelAngle': TRUNK_PANEL_ANGLE,
        'playerStart': PLAYER_START,
        # Invisible posts filling pockets a toon could walk into and not
        # out of: (where, radius, height). The slot between Freddy and the
        # gazebo steps' side, up on the stringer outside the railing.
        'blockers': ((Point3(-66.1, -4.0, -1.975), 1.3, 4.5),),
    },
    'beta_ttc': {
        'title': 'Old School Toontown',
        'description': 'Toontown Central as it looked in the 2001 beta: a round playground with a pond, the gazebo in the middle '
                       'and tunnels to Daisy\'s, Donald\'s and Minnie\'s. Mickey waits at the Donald\'s Dock tunnel.',
        'picture': 'phase_4/maps/survival_map_beta_ttc.jpg',
        # Map Select asks Day Time or Night Time for this one.
        'dayAndNight': True,
        'storage': (BETA_DNA + 'storage.xml', BETA_DNA + 'storage_TT.xml', BETA_DNA + 'storage_TT_sz.xml'),
        'dna': BETA_DNA + 'toontown_central_sz.xml',
        # The beta's playground is centred on (110, -30); moved so its
        # gazebo is at the middle, where the cogs' landing ring is.
        'offset': Point3(-110, 30, 0),
        # Mickey stands inside the tunnel to Donald's Dock, across the
        # playground from the trolley and the pond.
        'mickeyTunnel': 'linktunnel_tt_2301',
        # The tunnel's origin is its mouth, under the Donald's Dock sign;
        # this far out he stands just in front of it.
        'mickeyStep': 2.0,
        # Turn from looking straight out of the tunnel (survival-mickey-turn
        # in a prc overrides it).
        'mickeyTurn': 0.0,
        'blockTunnels': True,
        'loopyLane': (Point3(81.4, -47.4, 6.1), 61),
        # On the pond's east bank, looking over the water.
        'fisherman': (Point3(-19, 14, -1.33), 90),
        'gazebo': (Point3(0, 0, -1.33), 180),
        'trunkPanelAngle': 300.0,
        # On the path south of the gazebo, facing it and Toon Hall.
        'playerStart': (Point3(0, -50, 0), 0),
    },
}

# The parody maps (toontown/survival/maps) are built by their own class
# instead of from a playground's DNA, in the map's own daylight. One left
# out of MAP_ORDER can still be picked with survival-map in a prc.
MAPS['downsizer'] = {
    'title': 'Downsizer Drive',
    'description': 'A pretend Toontown street the Cogs built out in Sellbot country to test their Downsizers, '
                   'with two toon houses, fenced yards and a cul-de-sac. Mickey waits by the crates at the closed end, '
                   'the trunk and Fisherman Freddy stand by the fountain.',
    'picture': 'phase_4/maps/survival_map_downsizer.jpg',
    'parody': ('toontown.survival.maps.DownsizerDrive', 'DownsizerDrive'),
    # Finer cells: the gaps between the fences, garages and karts are a
    # few feet, and five-foot cells routed cogs into ones they can't fit.
    'reachStep': 2.5,
}
# The night maps built in code (toontown/survival/previewmaps).
MAPS['farewell_fair'] = {
    'title': 'Farewell Fair',
    'description': 'A Toontown fair, closed for years and left to rot. Booths line the boardwalk to the old ToonFest tower, '
                   'the Ferris wheel still creaks round and the carousel turns by itself. Mickey waits by the stage, '
                   'Fisherman Freddy at the duck tank, and the trunk on the plaza by the tower.',
    'picture': 'phase_4/maps/survival_map_farewell_fair.jpg',
    'preview': 'farewell_fair',
}
# Test only (not in MAP_ORDER until Arthur says): pick it with
# survival-map toybox_terrace in a prc.
MAPS['toybox_terrace'] = {
    'title': 'Toybox Terrace',
    'description': 'A playground built from giant wooden toys round a board-game plaza. Jack pops out of the clock tower, '
                   'Mickey waits in front of it, Fisherman Freddy by the marble pond, and the trunk in the toy yard.',
    'picture': 'phase_4/maps/survival_map_farewell_fair.jpg',
    'preview': 'toybox_terrace',
}
# The other playgrounds, straight from their DNA like Toontown Central,
# and two Cog HQs loaded from their models (toontown/survival/HoodMaps.py
# has them all). Each names who upgrades the gag there instead of Mickey.
from toontown.survival.HoodMaps import HOOD_MAPS
MAPS.update(HOOD_MAPS)
# Around each station on a parody map no cog lands.
MAP_STATION_CLEAR = 10.0

# The order the Map Select menu lists them in.
MAP_ORDER = ('ttc', 'beta_ttc', 'downsizer', 'farewell_fair', 'brrrgh', 'melodyland', 'dock', 'sellbot_hq', 'bossbot_hq')


def mapName():
    from panda3d.core import ConfigVariableString
    name = ConfigVariableString('survival-map', 'ttc').getValue()
    return name if name in MAPS else 'ttc'


# Heights over the feet a cog's body is checked at (bodyClear): above the
# gazebo's half-foot curb, under its two-foot railing's top.
BODY_HEIGHTS = (0.9, 1.9, 3.2)
# How far either side of a walk between two cells there must be room, so
# no cell joins a neighbour past a tree trunk or a fence post.
CELL_SIDE = 0.6
# The most the ground may rise or fall at once between two joined cells
# (off the stairs), checked this many times between them.
REACH_JUMP = 2.0
REACH_SAMPLES = 6

# A landing cell needs this many rings of open cells round it, so a cog
# (a big one is 3 feet across) never lands against a wall, fence or tree.
LANDING_CLEARANCE = 1

# How far into the ground a blocker post (addBlocker) reaches.
BLOCKER_BELOW = 3.0


class SurvivalArena:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalArena')

    def __init__(self, name=None, night=True):
        self.mapName = name if name in MAPS else mapName()
        self.night = night or not self.map_allowsDay(self.mapName)
        self.map = MAPS[self.mapName]
        self.parody = None
        self.preview = False
        self.mapFog = None
        self.skyFile = SKY_FILE
        self.skyColor = SKY_COLOR
        self.background = Vec4(0.05, 0.05, 0.1, 1)
        self.spawnRing = SPAWN_RING
        self.spawnMiddle = Point3(0, 0, 0)
        if self.map.get('preview'):
            self.__buildPreview(self.map['preview'])
        elif self.map.get('models'):
            self.__buildModels()
        elif self.map.get('parody'):
            self.__buildParody(*self.map['parody'])
        else:
            self.__buildPlayground()
        if 'reachSpan' in self.map:
            self.reachSpan = self.map['reachSpan']
        if 'reachCenter' in self.map:
            self.reachCenter = Point3(self.map['reachCenter'])
        if 'spawnRing' in self.map:
            self.spawnRing = self.map['spawnRing']
        if 'reachStep' in self.map:
            # Finer cells, for a map whose ways up and down are narrow
            # (Melodyland's horn slides).
            self.REACH_STEP = self.map['reachStep']
        if 'spawnMiddle' in self.map:
            self.spawnMiddle = Point3(self.map['spawnMiddle'])
        self.nav = getNav()
        self.nav.sceneOverride = None
        self.__makeTraversers()

    def __buildParody(self, moduleName, className):
        """One of the parody maps, lit the way it is built (Arthur: not dark
        and gloomy), under its own sky, with the stations where it puts them."""
        import importlib
        cls = getattr(importlib.import_module(moduleName), className)
        self.night = False
        self.root = render.attachNewNode('survivalArena')
        self.dnaStore = None
        self.animProps = []
        self.sky = None
        self.skyTask = None
        self.parody = cls()
        self.parody.build(survival=True)
        self.parody.root.reparentTo(self.root)
        self.geom = self.parody.root
        x0, y0, x1, y1 = cls.SITE
        # Cogs land anywhere on the map out of sight, never on a station.
        self.spawnMiddle = Point3((x0 + x1) * 0.5, (y0 + y1) * 0.5, 0)
        self.spawnRing = (0.0, math.hypot(x1 - x0, y1 - y0))
        self.noLanding = tuple((Point3(*spot[0]), MAP_STATION_CLEAR)
                               for spot in (cls.MICKEY_SPOT, cls.TRUNK_SPOT, cls.FISHERMAN_SPOT))
        self.reachCenter = self.spawnMiddle
        self.reachSpan = max(x1 - x0, y1 - y0) * 0.5 + 10
        gsg = base.win.getGsg()
        if gsg:
            self.geom.prepareScene(gsg)

    def __buildPreview(self, key):
        """One of the night maps built in code: its own sky, fog, light and
        colour, with the stations where it puts them (some up on terraces)."""
        from toontown.survival.previewmaps import getPreviewMap
        cls = getPreviewMap(key)
        self.night = True
        self.preview = True
        self.root = render.attachNewNode('survivalArena')
        self.dnaStore = None
        self.animProps = []
        self.parody = cls(self.root)
        self.geom = self.root
        self.spawnRing = cls.SPAWN_RING
        self.noLanding = tuple((Point3(spot[0], spot[1], 0), radius) for spot, radius in cls.NO_LANDING)
        self.reachSpan = cls.REACH_SPAN
        self.skyFile = cls.SKY_FILE
        self.skyColor = cls.SKY_COLOR
        self.background = cls.BACKGROUND
        if cls.FOG:
            color, density = cls.FOG
            self.mapFog = Fog('mapFog')
            self.mapFog.setColor(*color)
            self.mapFog.setExpDensity(density)
            self.root.setFog(self.mapFog)
        self.root.setColorScale(cls.NIGHT_SCALE)
        gsg = base.win.getGsg()
        if gsg:
            self.geom.prepareScene(gsg)
        self.sky = None
        self.skyTask = None
        self.startSky()

    def __spotsNoLanding(self):
        spots = self.map['spots']
        out = [(Point3(spots[k][0]), 12.0) for k in ('upgrader', 'fisherman', 'trunk')]
        out += [(Point3(p), r) for p, r in self.map.get('noLanding', ())]
        return tuple(out)

    def __buildPlayground(self):
        if self.map.get('spots'):
            self.noLanding = self.__spotsNoLanding()
        else:
            gazebo = self.map['gazebo'][0]
            self.noLanding = ((gazebo, 22.0), (self.map['fisherman'][0], 12.0), (self.map['loopyLane'][0], 16.0))
        self.skyFile = self.map.get('sky', SKY_FILE)
        self.daySkyFile = self.map.get('daySky', DAY_SKY_FILE)
        self.root = render.attachNewNode('survivalArena')
        self.dnaStore = DNAStorage()
        for name in self.map['storage']:
            loader.loadDNA(name).store(self.dnaStore)
        self.dnaStore.storeFont(ToontownGlobals.getInterfaceFont(), 'humanist')
        self.dnaStore.storeFont(ToontownGlobals.getSignFont(), 'mickey')
        self.dnaStore.storeFont(ToontownGlobals.getSuitFont(), 'suit')
        tree = loader.loadDNA(self.map['dna'])
        node = tree.generate(self.dnaStore)
        if node.getNumParents() == 1:
            self.geom = NodePath(node.getParent(0))
        else:
            self.geom = NodePath(node)
        self.geom.reparentTo(self.root)
        self.geom.setPos(self.map['offset'])
        # Nothing leads anywhere: the tunnels' triggers go, the doors are
        # plain geometry without a DistributedDoor behind them.
        for trigger in self.geom.findAllMatches('**/tunnel_trigger*'):
            trigger.stash()
        for trigger in self.geom.findAllMatches('**/door_trigger*'):
            trigger.stash()
        # What a DistributedDoor does to a door's parts when it generates
        # (hideDoorParts): the black "hole" behind each leaf shows only
        # while the door swings, and a door drawn on a flat keeps its leaves
        # hidden. Without doors here nothing did this, so Toon HQ's doorway
        # was a black hole.
        for hole in self.geom.findAllMatches('**/doorFrameHole*'):
            hole.hide()
        for flat in self.geom.findAllMatches('**/door_flat*'):
            suffix = flat.getName()[len('door_flat'):]
            building = flat.getParent()
            for leaf in ('leftDoor', 'rightDoor'):
                for door in building.findAllMatches('**/%s%s' % (leaf, suffix)):
                    door.hide()
        for origin in self.geom.findAllMatches('**/suit_building_origin'):
            origin.removeNode()
        # The playground's moving props, as SafeZoneLoader makes them: the
        # trash cans, hydrants and mailboxes dance, the Pet Shop's fish
        # swims, Toon HQ's periscope and telescope look about.
        self.animProps = self.__makeAnimatedProps()
        # A map's own changes to its playground (Donald's Dock: no water,
        # the boat aground, the bridges down).
        setup = self.map.get('setup')
        if setup:
            from toontown.survival import HoodMaps
            getattr(HoodMaps, setup)(self)
        self.geom.flattenMedium()
        # Every playground's tunnels are walled off (Arthur: Donald's Dock,
        # the Brrrgh, Melodyland and Toontown Central all let toons in).
        self.blockTunnels()
        gsg = base.win.getGsg()
        if gsg:
            self.geom.prepareScene(gsg)
        for prop in self.animProps:
            try:
                prop.enter()
            except Exception:
                self.notify.warning('could not start %s' % prop.__class__.__name__)
        if self.night:
            self.root.setColorScale(self.map.get('nightScale', NIGHT_SCALE))
        self.sky = None
        self.skyTask = None
        self.startSky()

    def __buildModels(self):
        """A Cog HQ courtyard: its models as the game loads them, under
        its own sky and fog, with a trolley put down for the way out."""
        from toontown.survival import HoodMaps
        self.noLanding = self.__spotsNoLanding()
        self.root = render.attachNewNode('survivalArena')
        self.dnaStore = None
        self.animProps = []
        self.night = True
        self.geom = self.root.attachNewNode('survivalModels')
        for path, pos, hpr, scale in self.map['models']:
            model = loader.loadModel(path)
            model.reparentTo(self.geom)
            model.setPosHprScale(pos, hpr, scale)
        HoodMaps.addTrolley(self)
        getattr(HoodMaps, self.map['setup'])(self)
        gsg = base.win.getGsg()
        if gsg:
            self.geom.prepareScene(gsg)
        self.skyFile = self.map['sky']
        self.skyColor = None
        self.background = self.map.get('background', self.background)
        if self.map.get('fog'):
            color, density = self.map['fog']
            self.mapFog = Fog('mapFog')
            self.mapFog.setColor(*color)
            self.mapFog.setExpDensity(density)
            self.root.setFog(self.mapFog)
        if self.map.get('nightScale'):
            self.root.setColorScale(self.map['nightScale'])
        self.sky = None
        self.skyTask = None
        self.startSky()
        self.sky.setScale(self.map.get('skyScale', 1.0))

    def __makeTraversers(self):
        # A ray from high up, for the ground anywhere in the playground.
        self.groundTrav = CollisionTraverser('survivalGround')
        self.groundQueue = CollisionHandlerQueue()
        self.groundRay = CollisionRay()
        rayNode = CollisionNode('survivalGroundRay')
        rayNode.addSolid(self.groundRay)
        rayNode.setFromCollideMask(ToontownGlobals.FloorBitmask)
        rayNode.setIntoCollideMask(BitMask32.allOff())
        self.groundRayPath = self.root.attachNewNode(rayNode)
        self.groundTrav.addCollider(self.groundRayPath, self.groundQueue)
        # A segment along the aim line, for the wall or floor a gag lands on.
        self.aimTrav = CollisionTraverser('survivalAim')
        self.aimQueue = CollisionHandlerQueue()
        self.aimSegment = CollisionSegment()
        segNode = CollisionNode('survivalAimSegment')
        segNode.addSolid(self.aimSegment)
        segNode.setFromCollideMask(ToontownGlobals.WallBitmask | ToontownGlobals.FloorBitmask | ToontownGlobals.CameraBitmask)
        segNode.setIntoCollideMask(BitMask32.allOff())
        self.aimSegmentPath = self.root.attachNewNode(segNode)
        self.aimTrav.addCollider(self.aimSegmentPath, self.aimQueue)
        # Segments at a cog's knees, waist and chest, for whether its body
        # fits along a walk (bodyClear). The one line at chest height the
        # cogs used before passed over Old School Toontown's two-foot gazebo
        # railing, its trees and its stone wall (Arthur).
        self.bodyChecks = {}
        for wide in (False, True):
            trav = CollisionTraverser('survivalBody')
            queue = CollisionHandlerQueue()
            segments = [CollisionSegment() for h in BODY_HEIGHTS for side in ((0,) if not wide else (0, 1, -1))]
            node = CollisionNode('survivalBodySegments')
            for segment in segments:
                node.addSolid(segment)
            node.setFromCollideMask(ToontownGlobals.WallBitmask)
            node.setIntoCollideMask(BitMask32.allOff())
            path = self.root.attachNewNode(node)
            trav.addCollider(path, queue)
            self.bodyChecks[wide] = (trav, queue, segments)

    def blockTunnels(self):
        """Nobody goes into a tunnel: they lead nowhere here. An invisible
        wall stands across each mouth, a little out in front of it, on
        every playground map. It used to be a flat two-sided polygon a
        foot inside the mouth, on some maps only: a toon walked in, and
        on a slow frame its centre passed the polygon, the back face
        pushed it on and the front face pushed it back, a jitter in the
        tunnel (Arthur). Thick capsules stacked up, like HoodMaps.wall,
        hold from either side whatever the frame rate.
        The tunnel_origin's +y faces out into the playground."""
        half, height, out, radius = 15.0, 24.0, 1.5, 1.2
        mickeys = [prop.find('**/tunnel_origin') for prop in self.geom.findAllMatches('**/%s*' % self.map['mickeyTunnel'])] \
            if self.map.get('mickeyTunnel') else []
        for origin in self.geom.findAllMatches('**/tunnel_origin'):
            # Where Mickey stands in a tunnel's mouth, the wall goes just
            # behind him.
            y = -1.0 if origin in mickeys else out
            node = CollisionNode('survivalTunnelBlock')
            z = -1.0
            while z < height:
                node.addSolid(CollisionTube(-half, y, z, half, y, z, radius))
                z += 1.6
            node.setIntoCollideMask(ToontownGlobals.WallBitmask | ToontownGlobals.CameraBitmask)
            node.setFromCollideMask(BitMask32.allOff())
            origin.attachNewNode(node)

    def __makeAnimatedProps(self):
        import importlib
        props = []
        for node in self.geom.findAllMatches('**/animated_prop_*'):
            name = node.getName()
            if name.startswith('animated_prop_generic'):
                className = 'GenericAnimatedProp'
            else:
                className = name[len('animated_prop_'):-len('_DNARoot')]
            try:
                module = importlib.import_module('toontown.hood.' + className)
                props.append(getattr(module, className)(node))
            except Exception:
                self.notify.warning('no animated prop for %s' % name)
        self.notify.info('%d animated props' % len(props))
        return props

    @staticmethod
    def map_allowsDay(name):
        return bool(MAPS.get(name, {}).get('dayAndNight'))

    def startSky(self):
        self.sky = loader.loadModel(self.skyFile if self.night else getattr(self, 'daySkyFile', DAY_SKY_FILE))
        self.sky.setTag('sky', 'Survival')
        # The day sky is a 500-foot dome; the camera only draws 400 feet
        # out, so at full size it was cut away and the sky showed black.
        self.sky.setScale(1.0 if self.night else 0.6)
        self.sky.setDepthTest(0)
        self.sky.setDepthWrite(0)
        self.sky.setBin('background', 100)
        if self.night and self.skyColor is not None:
            self.sky.setColor(self.skyColor)
        self.sky.reparentTo(camera)
        self.sky.setZ(0.0)
        self.sky.setHpr(0.0, 0.0, 0.0)
        self.sky.node().setEffect(CompassEffect.make(NodePath(), CompassEffect.PRot | CompassEffect.PZ))
        self.skyTask = taskMgr.add(self.__spinSky, 'survivalSky')
        self.skyTask.h = 0
        self.skyTask.cloud1 = self.sky.find('**/cloud1')
        self.skyTask.cloud2 = self.sky.find('**/cloud2')

    def __spinSky(self, task):
        task.h += globalClock.getDt() * 0.25
        if not task.cloud1.isEmpty():
            task.cloud1.setH(task.h)
        if not task.cloud2.isEmpty():
            task.cloud2.setH(-task.h * 0.8)
        return task.cont

    def setFog(self, on):
        """The Gag-Snatcher rounds come in a fog (BO1's hound rounds)."""
        if on:
            fog = Fog('snatcherFog')
            fog.setColor(0.18, 0.16, 0.22)
            fog.setExpDensity(0.012)
            # Over the parody maps' own fog.
            self.root.setFog(fog, 1)
            if self.sky:
                self.sky.setColorScale(0.6, 0.55, 0.7, 1)
        else:
            if self.mapFog is not None:
                self.root.setFog(self.mapFog)
            else:
                self.root.clearFog()
            if self.sky:
                self.sky.clearColorScale()

    def destroy(self):
        for prop in getattr(self, 'animProps', ()):
            try:
                prop.exit()
                prop.delete()
            except Exception:
                pass
        self.animProps = []
        if self.skyTask:
            taskMgr.remove(self.skyTask)
            self.skyTask = None
        if self.sky:
            self.sky.removeNode()
            self.sky = None
        if self.parody is not None:
            self.parody.destroy()
            self.parody = None
        self.root.removeNode()
        if self.dnaStore is not None:
            try:
                self.dnaStore.reset()
            except Exception:
                # The repo's DNAStorage.reset trips over itself; the store goes
                # away with us either way.
                pass
        self.dnaStore = None
        ModelPool.garbageCollect()
        TexturePool.garbageCollect()

    # --- Ground ---

    def groundZ(self, x, y, top=80.0):
        """The highest floor under (x, y) (below height top), or None off the playground."""
        self.groundRay.setOrigin(x, y, top)
        self.groundRay.setDirection(0, 0, -1)
        self.groundQueue.clearEntries()
        self.groundTrav.traverse(self.root)
        best = None
        for i in range(self.groundQueue.getNumEntries()):
            hitZ = self.groundQueue.getEntry(i).getSurfacePoint(render).getZ()
            if best is None or hitZ > best:
                best = hitZ
        return best

    def rayHit(self, origin, direction, maxDist):
        """The first wall or floor along the line: (distance, point) or None."""
        end = origin + direction * maxDist
        self.aimSegment.setPointA(origin)
        self.aimSegment.setPointB(end)
        self.aimQueue.clearEntries()
        self.aimTrav.traverse(self.root)
        best = None
        for i in range(self.aimQueue.getNumEntries()):
            point = self.aimQueue.getEntry(i).getSurfacePoint(render)
            dist = (point - origin).length()
            if best is None or dist < best[0]:
                best = (dist, point)
        return best

    def spawnZ(self, x, y):
        z = self.groundZ(x, y)
        if z is None or z < self.map.get('lowest', -8) or self.nav.onStairs(x, y, z):
            return None
        return z

    def clearLine(self, a, b):
        return self.nav.clearLine(a, b)

    def bodyClear(self, a, b, side=0.0):
        """Whether a cog's body gets from a to b (both on the ground):
        nothing solid at its knees, waist or chest anywhere along the way,
        and with side, nothing that far to either side of the way either.
        Each line rises and falls with the ground, so steps and slopes are
        no wall."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        flat = math.hypot(dx, dy)
        if flat < 1e-3:
            return True
        trav, queue, segments = self.bodyChecks[bool(side)]
        offsets = (0,) if not side else (0, side, -side)
        sx, sy = -dy / flat, dx / flat
        i = 0
        for h in BODY_HEIGHTS:
            for off in offsets:
                segments[i].setPointA(a[0] + sx * off, a[1] + sy * off, a[2] + h)
                segments[i].setPointB(b[0] + sx * off, b[1] + sy * off, b[2] + h)
                i += 1
        queue.clearEntries()
        trav.traverse(self.root)
        for i in range(queue.getNumEntries()):
            entry = queue.getEntry(i)
            if not entry.getInto().isTangible():
                continue
            into = entry.getIntoNodePath()
            # Toons and cogs walk about; only the scenery counts.
            if into.findNetTag('avatarDoId').isEmpty() and into.findNetPythonTag('avatar').isEmpty():
                return False
        return True

    def walkable(self, a, b):
        return self.nav.walkable(a, b)

    # --- Where the stations stand ---

    def parodySpot(self, spot):
        pos, h = spot
        if self.preview:
            # On whatever floor is at the stated height (a terrace, a deck),
            # not a roof above it.
            z = self.groundZ(pos[0], pos[1], pos[2] + 3)
            return Point3(pos[0], pos[1], pos[2] if z is None else z), h
        return self.placeOnGround(pos[0], pos[1], h)

    def mickeyScale(self):
        return getattr(self.parody, 'MICKEY_SCALE', 1.0) if self.parody is not None else 1.0

    def upgrader(self):
        """Who upgrades the gag here: ('char', code, name) for a classic
        character, ('toon', dna maker, name) for a toon."""
        return self.map.get('upgrader', ('char', 'mk', 'Mickey'))

    def spot(self, key):
        """A station's spot a map states outright, on the ground there."""
        spots = self.map.get('spots')
        if not spots or key not in spots:
            return None
        pos, h = spots[key]
        z = self.groundZ(pos[0], pos[1], pos[2] + 4)
        return Point3(pos[0], pos[1], pos[2] if z is None else z), h

    def mickeySpot(self):
        if self.parody is not None:
            return self.parodySpot(self.parody.MICKEY_SPOT)
        if self.spot('upgrader'):
            return self.spot('upgrader')
        # Just inside the playground from the Loopy Lane tunnel mouth,
        # facing the toons who walk up.
        # The tunnel prop's own origin is far back inside the hill; the
        # playground end is its tunnel_origin node, the one facing east.
        tunnel = self.map['mickeyTunnel']
        if tunnel:
            # This playground names the tunnel he stands in.
            for prop in self.geom.findAllMatches('**/%s*' % tunnel):
                node = prop.find('**/tunnel_origin')
                if not node.isEmpty():
                    pos, h = node.getPos(render), node.getH(render)
                    forward = Vec3(-math.sin(math.radians(h)), math.cos(math.radians(h)), 0)
                    step = ConfigVariableDouble('survival-mickey-step', self.map['mickeyStep']).getValue()
                    spot = pos + forward * step
                    turn = float(ConfigVariableDouble('survival-mickey-turn', self.map.get('mickeyTurn', 0.0)).getValue())
                    return self.placeOnGround(spot[0], spot[1], h + turn)
        best = None
        for node in self.geom.findAllMatches('**/tunnel_origin'):
            h = node.getH(render)
            off = abs((h + 90 + 180) % 360 - 180)
            if best is None or off < best[0]:
                best = (off, node.getPos(render), h)
        if best is not None and best[0] < 30:
            pos, h = best[1], best[2]
            forward = Vec3(-math.sin(math.radians(h)), math.cos(math.radians(h)), 0)
            spot = pos + forward * 9.0
            return self.placeOnGround(spot[0], spot[1], h)
        origin, h = self.map['loopyLane']
        pos, h = self.placeOnGround(origin[0] + 14.0, origin[1], -90)
        if self.groundZ(pos[0], pos[1]) is None:
            pos = Point3(pos[0], pos[1], origin[2])
        return pos, h

    def fishermanSpot(self):
        if self.parody is not None:
            return self.parodySpot(self.parody.FISHERMAN_SPOT)
        if self.spot('fisherman'):
            return self.spot('fisherman')
        origin, h = self.map['fisherman']
        return self.placeOnGround(origin[0], origin[1], h)

    def trunkSpot(self):
        if self.parody is not None:
            return self.parodySpot(self.parody.TRUNK_SPOT)
        if self.spot('trunk'):
            return self.spot('trunk')
        # Centred in front of the gazebo's base panel on the far side from
        # the fisherman (Arthur circled it), far enough out that the trunk
        # and its open lid stay clear of the gazebo.
        middle = self.map['gazebo'][0]
        a = math.radians(self.map['trunkPanelAngle'])
        away = Vec3(math.cos(a), math.sin(a), 0)
        spot = middle + away * TRUNK_FROM_GAZEBO
        # Heading 0 faces +y; the trunk's back (+y) toward the gazebo.
        h = math.degrees(math.atan2(away[0], -away[1]))
        return self.placeOnGround(spot[0], spot[1], h)

    def addBlocker(self, pos, radius, height=3.0):
        """Something solid where the playground had nothing (the trunk):
        a wall the toons walk round and the cogs' way-finding sees."""
        # Down into the ground too: a toon stepping up from lower ground
        # (onto Donald's pier from the drained harbour) came in under the
        # post's foot and ended up inside it.
        tube = CollisionTube(0, 0, -BLOCKER_BELOW, 0, 0, height, radius)
        node = CollisionNode('survivalBlocker')
        node.addSolid(tube)
        node.setIntoCollideMask(ToontownGlobals.WallBitmask)
        node.setFromCollideMask(BitMask32.allOff())
        path = self.root.attachNewNode(node)
        path.setPos(pos)
        return path

    def playerStart(self):
        if self.parody is not None:
            return self.parodySpot(self.parody.PLAYER_START)
        if self.spot('start'):
            return self.spot('start')
        start, h = self.map['playerStart']
        return self.placeOnGround(start[0], start[1], h)

    def placeOnGround(self, x, y, h=0.0):
        z = self.groundZ(x, y)
        if z is None:
            z = 0.0
        return Point3(x, y, z), h

    # --- Where cogs land ---

    def inView(self, spot, eye, forward):
        d = Vec3(spot - eye)
        flat = math.hypot(d[0], d[1])
        if flat < 1:
            return True
        angle = math.degrees(math.atan2(d[0], d[1]))
        facing = math.degrees(math.atan2(forward[0], forward[1]))
        if abs((angle - facing + 180) % 360 - 180) > VIEW_HALF_ANGLE:
            return False
        return self.clearLine(eye, Point3(spot[0], spot[1], spot[2] + 3))

    REACH_STEP = 5.0
    REACH_SPAN = 150.0

    def buildReach(self, start):
        """Flood the playground from where the player starts, one cell at
        a time, over ground a toon can walk: the open playground. Cells
        inside buildings, behind fences, on the hill or off the edge never
        join, so cogs only ever land where the player could stand."""
        step = self.REACH_STEP
        center = getattr(self, 'reachCenter', Point3(0, 0, 0))
        span = getattr(self, 'reachSpan', self.REACH_SPAN)
        lo = (int((center[0] - span) / step), int((center[1] - span) / step))
        hi = (int((center[0] + span) / step), int((center[1] + span) / step))
        z0 = self.spawnZ(start[0], start[1])
        if z0 is None:
            z0 = start[2]
        origin = (int(round(start[0] / step)), int(round(start[1] / step)))
        self.reach = {origin: Point3(origin[0] * step, origin[1] * step, z0)}
        self.reachZ = {}
        self.stairs = set()
        frontier = [origin]
        while frontier:
            cell = frontier.pop()
            here = self.reach[cell]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + di, cell[1] + dj)
                if nxt in self.reach or not (lo[0] <= nxt[0] <= hi[0] and lo[1] <= nxt[1] <= hi[1]):
                    continue
                x, y = nxt[0] * step, nxt[1] * step
                if nxt in self.reachZ:
                    # Tried before from another side (and blocked there, a
                    # crate or a railing between): it may still join from
                    # this one. Before, a cell was only ever tried once.
                    z = self.reachZ[nxt]
                else:
                    # Steps and stairs join the walk (a cog follows the player
                    # up into the gazebo) but are never landed on.
                    z = self.groundZ(x, y)
                    # Below this is water or off the map (Melodyland's bowl
                    # floor is lower than that).
                    if z is not None and z < self.map.get('lowest', -8):
                        z = None
                    if z is not None and self.nav.onStairs(x, y, z):
                        self.stairs.add(nxt)
                    self.reachZ[nxt] = z
                # A step up onto the gazebo is a bit more than three feet
                # from cell to cell; anywhere else three is the most.
                rise = 3.6 if (nxt in self.stairs or cell in self.stairs) else 3.0
                # A playground with steeper ramps (Melodyland's) says so.
                rise = max(rise, self.map.get('reachRise', 0.0))
                if z is None or abs(z - here[2]) > rise:
                    continue
                there = Point3(x, y, z)
                if not self.__joins(cell, nxt, here, there):
                    continue
                self.reach[nxt] = there
                frontier.append(nxt)
        self.reachList = [p for c, p in self.reach.items() if c not in self.stairs]
        self.landingList = []
        ring = max(LANDING_CLEARANCE, int(round(LANDING_CLEARANCE * 5.0 / step)))
        for cell, point in self.reach.items():
            if cell in self.stairs:
                continue
            if any((cell[0] + di, cell[1] + dj) not in self.reach
                   for di in range(-ring, ring + 1) for dj in range(-ring, ring + 1)):
                continue
            if any((Point3(point[0], point[1], 0) - Point3(spot[0], spot[1], 0)).length() < radius for spot, radius in self.noLanding):
                continue
            self.landingList.append(point)
        # Which side-by-side cells join. The flood only tried a cell from
        # the first side it reached it by; two cells both reached from
        # elsewhere were taken as joined, through Old School Toontown's
        # stone wall, so the cogs' routes led them into it.
        self.links = set()
        for cell, point in self.reach.items():
            for di, dj in ((1, 0), (0, 1)):
                c = (cell[0] + di, cell[1] + dj)
                there = self.reach.get(c)
                if there is not None and self.__joins(cell, c, point, there):
                    self.links.add((cell, c))
        self.flows = {}
        # Corner-to-corner steps the cogs' routes may take, worked out now
        # rather than in the middle of a round.
        self.diagonals = {}
        for cell in self.reach:
            for di, dj in ((1, 1), (1, -1)):
                c = (cell[0] + di, cell[1] + dj)
                if c in self.reach:
                    self.diagonalOpen(cell, c)
        self.notify.info('reach: %d cells, %d open for landing' % (len(self.reachList), len(self.landingList)))

    def __joins(self, cell, nxt, here, there):
        """Whether a cog walks between two side-by-side cells."""
        rise = 3.6 if (nxt in self.stairs or cell in self.stairs) else 3.0
        rise = max(rise, self.map.get('reachRise', 0.0))
        if abs(there[2] - here[2]) > rise:
            return False
        if not self.clearLine(here, there) or not self.__roomBetween(here, there):
            return False
        return nxt in self.stairs or cell in self.stairs or self.__gentle(here, there)

    def linked(self, a, b):
        """Whether side-by-side cells a and b join (see buildReach)."""
        links = getattr(self, 'links', None)
        if links is None:
            return True
        return ((a, b) if a < b else (b, a)) in links

    def __gentle(self, a, b):
        """Whether the ground from a to b climbs no more than a step at a
        time. Two cells either side of a low wall (Brrrgh's snow ledges)
        looked joined, both being on the ground, so cogs walked into the
        wall for the toon standing behind it until they flew off."""
        if abs(b[2] - a[2]) <= REACH_JUMP:
            return True
        last = a[2]
        for i in range(1, REACH_SAMPLES + 1):
            t = i / float(REACH_SAMPLES + 1)
            z = self.groundZ(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, max(a[2], b[2]) + 2.0)
            if z is None:
                # A crack between floor pieces: nothing to say there.
                continue
            if abs(z - last) > REACH_JUMP:
                return False
            last = z
        return abs(b[2] - last) <= REACH_JUMP

    def __roomBetween(self, a, b):
        """A cog's body fits from a to b: the middle line and one a little
        to either side. Both ways: a wall is solid from its front only, so
        Old School Toontown's stone wall let the flood out through its back
        to a strip of cells outside, and cogs landed there pushed into its
        front for good."""
        return self.bodyClear(a, b, CELL_SIDE) and self.bodyClear(b, a, CELL_SIDE)

    def diagonalOpen(self, a, b):
        """Whether the cells a and b, corner to corner, join (cached)."""
        key = (a, b) if a < b else (b, a)
        open_ = self.diagonals.get(key)
        if open_ is None:
            open_ = self.__roomBetween(self.reach[a], self.reach[b])
            self.diagonals[key] = open_
        return open_

    def nearestCell(self, p):
        step = self.REACH_STEP
        cell = (int(round(p[0] / step)), int(round(p[1] / step)))
        reach = getattr(self, 'reach', None) or {}
        if cell in reach:
            return cell
        best, bestDist = None, None
        for r in range(1, 4):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    c = (cell[0] + di, cell[1] + dj)
                    if c in reach:
                        d = di * di + dj * dj
                        if bestDist is None or d < bestDist:
                            best, bestDist = c, d
            if best is not None:
                return best
        return None

    def path(self, a, b):
        """Points to walk from a to b over the open playground's cells
        (breadth first, eight ways), ending at b itself; [b] when the way
        is clear or the grid doesn't know either end."""
        if self.walkable(a, b):
            return [Point3(b)]
        reach = getattr(self, 'reach', None) or {}
        start, goal = self.nearestCell(a), self.nearestCell(b)
        if start is None or goal is None or start == goal:
            return [Point3(b)]
        came = {start: None}
        frontier = [start]
        while frontier and goal not in came:
            nxt = []
            for cell in frontier:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    c = (cell[0] + di, cell[1] + dj)
                    if c in came or c not in reach:
                        continue
                    if not (di and dj) and not self.linked(cell, c):
                        continue
                    if di and dj and ((cell[0] + di, cell[1]) not in reach or (cell[0], cell[1] + dj) not in reach
                                      or not self.diagonalOpen(cell, c)):
                        continue
                    came[c] = cell
                    nxt.append(c)
            frontier = nxt
        if goal not in came:
            return [Point3(b)]
        cells = []
        c = goal
        while c is not None:
            cells.append(c)
            c = came[c]
        cells.reverse()
        points = [reach[c] for c in cells[1:-1]]
        # Skip the corners a straight walk can cut.
        out = []
        here = Point3(a)
        i = 0
        while i < len(points):
            j = len(points) - 1
            while j > i and not self.walkable(here, points[j]):
                j -= 1
            out.append(points[j])
            here = points[j]
            i = j + 1
        out.append(Point3(b))
        return out

    def randomSpot(self):
        spots = getattr(self, 'reachList', None) or []
        return Point3(random.choice(spots)) if spots else None

    def landingSpots(self):
        # Only open cells: never against a wall or in the gazebo.
        return getattr(self, 'landingList', None) or getattr(self, 'reachList', None) or []

    # --- Finding the way (for the cogs) ---

    def flowTo(self, goal):
        """A map from every open cell to the next cell on the shortest way
        to goal (breadth first over the playground's cells, eight ways, no
        cutting corners), refreshed at most every `every` seconds per goal
        cell. One map serves every cog chasing the same toon, so the cogs
        walk round the gazebo, fences and trees instead of into them."""
        reach = getattr(self, 'reach', None)
        if not reach:
            return None, None
        cell = self.nearestCell(goal)
        if cell is None:
            return None, None
        cached = self.flows.get(cell)
        if cached is not None:
            return cached, cell
        came = {cell: None}
        frontier = [cell]
        while frontier:
            nxt = []
            for here in frontier:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    c = (here[0] + di, here[1] + dj)
                    if c in came or c not in reach:
                        continue
                    if not (di and dj) and not self.linked(here, c):
                        continue
                    if di and dj and ((here[0] + di, here[1]) not in reach or (here[0], here[1] + dj) not in reach
                                      or not self.diagonalOpen(here, c)):
                        continue
                    came[c] = here
                    nxt.append(c)
            frontier = nxt
        if len(self.flows) >= 40:
            del self.flows[next(iter(self.flows))]
        self.flows[cell] = came
        return came, cell

    def cellPoint(self, cell):
        return self.reach.get(cell)

    def pickLanding(self, toons, eye, forward, tries=20):
        """A spot on the open playground the player cannot see, away from
        every toon; None when none turns up this time."""
        spots = self.landingSpots()
        for i in range(tries):
            if spots:
                cell = random.choice(spots)
                x = cell[0] + random.uniform(-1.5, 1.5)
                y = cell[1] + random.uniform(-1.5, 1.5)
                dist = math.hypot(x - self.spawnMiddle[0], y - self.spawnMiddle[1])
                if not self.spawnRing[0] <= dist <= self.spawnRing[1]:
                    continue
            else:
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(*self.spawnRing)
                x, y = dist * math.cos(angle), dist * math.sin(angle)
            z = self.spawnZ(x, y)
            if z is None:
                continue
            spot = Point3(x, y, z)
            if any((Point3(t[0], t[1], 0) - Point3(x, y, 0)).length() < SPAWN_CLEAR for t in toons):
                continue
            if self.inView(spot, eye, forward):
                continue
            return spot
        return None

    def landingNear(self, goal, eye, forward, near=14.0, far=30.0, tries=24):
        """An open spot near a goal, out of the player's view, with a clear
        walk to the goal; None if there is none this time."""
        spots = self.landingSpots()
        for i in range(tries):
            if spots:
                cell = random.choice(spots)
                x, y = cell[0], cell[1]
                if not near <= math.hypot(x - goal[0], y - goal[1]) <= far:
                    continue
            else:
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(near, far)
                x, y = goal[0] + dist * math.cos(angle), goal[1] + dist * math.sin(angle)
            z = self.spawnZ(x, y)
            if z is None:
                continue
            # On the goal's own level (not the harbour bed under its dock).
            if len(goal) > 2 and abs(z - goal[2]) > 3.5:
                continue
            spot = Point3(x, y, z)
            if self.inView(spot, eye, forward):
                continue
            if self.clearLine(Point3(x, y, z + 2), Point3(goal[0], goal[1], z + 2)):
                return spot
        return None
