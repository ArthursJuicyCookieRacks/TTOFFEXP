"""Downsizer Drive: a pretend Toontown street the Cogs built out in Sellbot
country to try out their Downsizers. Two toon houses face each other
across a little cul-de-sac, the yards are fenced, the cars are parked, and
Skelecog test dummies stand about the lawns. Past the board fence there is
only sand, Cog buildings and the factory's smoke.
"""

import math

from panda3d.core import Fog, Point3, Vec4

from toontown.survival.maps.MapKit import MapKit

STREET_TEX = 'street_street_TT_tex'
SIDEWALK_TEX = 'street_sidewalk_TT_tex'
GRASS_TEX = 'phase_4/maps/grass.jpg'
SAND_TEX = 'phase_4/maps/sandextension2.jpg'
PICKET_TEX = ('phase_6/maps/fence_white_picketB.jpg', 'phase_6/maps/fence_white_picketB_a.rgb')
ROOF_TEX = 'phase_6/maps/estateHouseroof2_tile.jpg'

# The test site's board fence, as the streets build theirs.
SITE = (-110, -100, 90, 100)
GREEN_HOUSE = (0.55, 0.74, 0.5)
YELLOW_HOUSE = (1.0, 0.86, 0.38)


class DownsizerDrive:
    NAME = 'Downsizer Drive'
    PLAYER_START = ((-40, 0, 0), -90)
    # Survival's stations (Arthur placed them). Played in Survival the
    # working ones stand here; the preview shows them standing still.
    # The accessory trunk (the Mystery Box), by the cul-de-sac facing the fountain.
    TRUNK_SPOT = ((75, 10, 0), -70)
    # Fisherman Freddy (the Toon Tonics) on the grass past the cul-de-sac,
    # facing the fountain.
    FISHERMAN_SPOT = ((80, 24, 0), 127)
    # Mickey (the gag upgrades) at the closed end of the street, facing up it.
    MICKEY_SPOT = ((-93, 4, 0), -90)
    MICKEY_SCALE = 1.2
    # Where the trolley out is: the one parked by the cul-de-sac.
    ESCAPE_NAME = 'Downsizer Drive'
    # The sky reaches 500 feet up and the factory stands 800 feet out:
    # Survival's camera draws this far here, not its usual 400.
    CAMERA_FAR = 1000.0
    # The cul-de-sac's fountain, and the mailbox on the sidewalk round it.
    FOUNTAIN = (48, 0)
    MAILBOX_SPOT = (31.1, 24.2, 0.04)
    # The toons' ground: inside the board fence.
    SITE = (-110, -100, 90, 100)
    SHOTS = [
        ('overview', (-170, -170, 130), (-10, 0, 0)),
        ('overview_high', (0, -20, 260), (0, 0, 0)),
        ('street_west', (-80, 0, 6), (20, 0, 4)),
        ('street_east', (40, -4, 6), (-40, 0, 6)),
        ('house_north', (-12, -6, 7), (-14, 50, 10)),
        ('house_south', (-18, 6, 7), (-16, -50, 10)),
        ('welcome_sign', (-82, 0, 12), (-109, 0, 16)),
        ('cul_de_sac', (22, -4, 9), (60, 8, 2)),
        ('fountain', (22, -16, 10), (50, 0, 3)),
        ('backyard_north', (-70, 92, 10), (-20, 60, 4)),
        ('backyard_south', (40, -95, 10), (-20, -60, 4)),
    ]

    def __init__(self):
        self.root = render.attachNewNode('downsizerDrive')
        self.kit = MapKit(self.root)
        self.actors = []
        # The street signs' font, which the Toontown Central storage leaves out.
        self.kit.store.storeFont(loader.loadFont('phase_3/models/fonts/Comedy'), 'TT_Comedy')

    def build(self, survival=False):
        # In Survival the stations are the real thing: leave out the
        # standing-still copies.
        self.survival = survival
        self.buildGround()
        self.buildHouses()
        self.buildYards()
        self.buildStreetProps()
        self.buildCars()
        self.buildDummies()
        self.buildEdges()
        self.buildSky()
        self.buildStations()
        self.buildSolids()

    def destroy(self):
        for actor in getattr(self, 'actors', []):
            actor.delete()
        self.actors = []
        self.kit.destroy()

    def buildStations(self):
        if self.survival:
            return
        from toontown.char import Char, CharDNA
        from toontown.toon import NPCToons
        kit = self.kit
        kit.model('phase_5.5/models/estate/tt_m_ara_est_accessoryTrunkBoy', pos=self.TRUNK_SPOT[0], h=self.TRUNK_SPOT[1])
        freddy = NPCToons.createLocalNPC(2012)
        freddy.reparentTo(self.root)
        freddy.setPosHpr(self.FISHERMAN_SPOT[0], (self.FISHERMAN_SPOT[1], 0, 0))
        freddy.loop('neutral')
        freddy.nametag3d.stash()
        mickey = Char.Char()
        dna = CharDNA.CharDNA()
        dna.newChar('mk')
        mickey.setDNA(dna)
        mickey.reparentTo(self.root)
        mickey.setPosHpr(self.MICKEY_SPOT[0], (self.MICKEY_SPOT[1], 0, 0))
        mickey.setScale(self.MICKEY_SCALE)
        mickey.loop('neutral')
        mickey.nametag3d.stash()
        self.actors += [freddy, mickey]

    # Things without collisions of their own get a box round them. (The
    # trolley toaster's own is a post a foot across: toons walked through it.)
    SOLID_MODELS = ('flowerBasket', 'picnic_table', 'target', 'watering_cans', 'shovels', 'Kart3_Final', 'Kart1_Final',
                    'Coggolf_cart3', 'ttr_r_prp_est_trolleyToaster')

    def buildSolids(self):
        kit = self.kit
        for child in self.root.getChildren():
            kind = child.getName().split('.')[0]
            if kind in self.SOLID_MODELS:
                # The flower basket is a flat card: give it a toon's width.
                kit.solid(child, minSize=1.6 if kind == 'flowerBasket' else None)
        # The trolley's own collisions are only its seats: a box round it.
        kit.solid(self.trolley, shrink=0.85)
        # The board fence all round. Its flats' own walls are pairs of
        # polygons back to back, which a toon walks through (Arthur).
        x0, y0, x1, y1 = SITE
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            kit.collideWall(a, b, 14, name='fenceCollide', thick=1.0)
        # The flats' camera barriers face out and pushed a toon at the fence
        # through it: they only keep the camera in now.
        from toontown.toonbase import ToontownGlobals
        for barrier in self.root.findAllMatches('**/wall_camera_barrier*'):
            barrier.node().setIntoCollideMask(barrier.node().getIntoCollideMask() & ToontownGlobals.CameraBitmask)
        # The fountain's pond walls face in: a toon who stepped over the rim
        # couldn't get out without jumping. Without them the rim is a slope
        # to walk up and down either way; the statue in the middle stays solid.
        for walls in self.fountain.findAllMatches('**/collide_water_walls'):
            walls.stash()
        # The statue's own solid is a capsule standing on the rim's level
        # with a rounded foot: a toon down in the basin came in under the
        # curve, which pushed it up instead of out, and it walked right
        # through the statue to stand inside it. An upright post from
        # under the basin floor instead.
        for tube in self.fountain.findAllMatches('**/collide_tube'):
            tube.stash()
        kit.collideTube((self.FOUNTAIN[0], self.FOUNTAIN[1], -4.0), 4.2, 15.0, name='fountainStatue')
        # Far away the trolley switched to its low-detail models, which
        # are missing pieces: always draw the full one.
        for lod in self.root.findAllMatches('**/+LODNode'):
            lod.node().forceSwitch(0)

    # The street, the cul-de-sac and the yards.
    def buildGround(self):
        kit = self.kit
        kit.rect(-600, -600, 600, 600, z=-0.05, tex=SAND_TEX, tile=30, name='desert')
        # The street runs west to east and ends in a cul-de-sac.
        kit.rect(-110, -12, 42, 12, z=0.02, tex=STREET_TEX, tile=20, name='street')
        kit.disc(48, 0, 26, z=0.02, tex=STREET_TEX, tile=20, name='culDeSac')
        # Sidewalks along both sides and round the end.
        kit.rect(-110, 12, 30, 20, z=0.04, tex=SIDEWALK_TEX, tile=8, name='walkN')
        kit.rect(-110, -20, 30, -12, z=0.04, tex=SIDEWALK_TEX, tile=8, name='walkS')
        kit.ring(48, 0, 25.8, 33, z=0.04, tex=SIDEWALK_TEX, tile=8, a0=-150, a1=150, name='walkEnd')
        # Grass right out to the board fence, so no sand shows inside the site.
        x0, y0, x1, y1 = SITE
        kit.rect(x0, y0, x1, y1, z=-0.02, tex=GRASS_TEX, tile=20, name='siteLawn')
        # One flat floor for walking on, the whole site.
        kit.collideFloor(x0, y0, x1, y1)
        # The lawns, front and back.
        kit.rect(-100, 20, 30, 90, z=0.03, tex=GRASS_TEX, tile=20, name='yardN')
        kit.rect(-100, -90, 30, -20, z=0.03, tex=GRASS_TEX, tile=20, name='yardS')
        kit.rect(30, 30, 82, 90, z=0.03, tex=GRASS_TEX, tile=20, name='yardNE')
        kit.rect(30, -90, 82, -30, z=0.03, tex=GRASS_TEX, tile=20, name='yardSE')
        # Driveways to the garages and front paths to the doors.
        kit.rect(6, 20, 20, 22.5, z=0.045, tex=SIDEWALK_TEX, tile=8, name='driveN')
        kit.rect(6, -22.5, 20, -20, z=0.045, tex=SIDEWALK_TEX, tile=8, name='driveS')
        kit.rect(-34, 20, -26, 38, z=0.045, tex=SIDEWALK_TEX, tile=8, name='pathN')
        kit.rect(-34, -38, -26, -20, z=0.045, tex=SIDEWALK_TEX, tile=8, name='pathS')

    def buildHouses(self):
        kit = self.kit
        # The green house to the north and the yellow one to the south, front
        # doors facing each other across the street.
        self.houseN = kit.estateHouse('phase_5.5/models/estate/houseB', pos=(-30, 52, 0.03), h=-90, scale=1.3)
        self.houseS = kit.estateHouse('phase_5.5/models/estate/houseA', pos=(-30, -52, 0.03), h=90, scale=1.3,
                                      color=YELLOW_HOUSE)
        for (x, y, h, color) in ((4, 22, 0, GREEN_HOUSE), (22, -22, 180, YELLOW_HOUSE)):
            front = [{'code': 'wall_md_board_ur', 'height': 12, 'color': color, 'door': 'door_garage_ur',
                      'doorColor': (0.92, 0.92, 0.92), 'cornice': ('cornice_shingles_ur', (0.45, 0.32, 0.22))}]
            side = [{'code': 'wall_md_board_ur', 'height': 12, 'color': color,
                     'windows': ('window_sm_square_ur', 1, (0.95, 0.95, 0.95))}]
            garage = kit.boxBuilding((x, y, 0), h, 18, 20, front, side, roofTex=ROOF_TEX)
            # Its flats' own walls are back-to-back pairs that cancel out
            # and its camera barriers only keep the camera out: toons and
            # cogs walked straight through the garages. A wall all round.
            corners = [self.root.getRelativePoint(garage, Point3(cx, cy, 0)) for cx, cy in ((0, 0), (18, 0), (18, 20), (0, 20))]
            for i in range(4):
                a, b = corners[i], corners[(i + 1) % 4]
                kit.collideWall((a[0], a[1]), (b[0], b[1]), 12, name='garageCollide', thick=0.6)
            # The garage door's trigger is a ball in front of the door that
            # stopped a toon there like an invisible post.
            for trigger in garage.findAllMatches('**/door_*_trigger*'):
                trigger.stash()

    def picket(self, a, b):
        self.kit.wallQuad(a, b, 0, 4, tex=PICKET_TEX[0], alpha=PICKET_TEX[1], tile=8, tileZ=4, name='picket')
        self.kit.collideWall(a, b, 4, name='picketCollide')

    def buildYards(self):
        kit = self.kit
        # White picket fences along the front of each yard, with gaps for the paths and drives.
        # Wide openings in each so players can get onto the lawns easily.
        self.picket((-110, 20.5), (-68, 20.5))
        self.picket((-50, 20.5), (-36, 20.5))
        self.picket((-110, -20.5), (-56, -20.5))
        for y in (20.5, -20.5):
            self.picket((-24, y), (4, y))
            # Close the corner up to the garage wall.
            self.picket((4, y), (4, y + (1.6 if y > 0 else -1.6)))
        # And between the front and back yards.
        self.picket((30, 30), (30, 100))
        self.picket((30, -30), (30, -100))
        # Mailboxes by the curb.
        # Back from the picket fence's end, where a toon wedged beside it.
        kit.model('phase_5.5/models/estate/mailboxHouse', pos=(-41, 23.5, 0), h=180)
        kit.model('phase_5.5/models/estate/mailboxHouse', pos=(-22, -21.5, 0), h=0)
        # Trees.
        kit.prop('prop_tree_large_ur', pos=(-75, 40, 0))
        kit.prop('prop_tree_fat_ur', pos=(55, 70, 0))
        kit.prop('prop_tree_large_ul', pos=(-75, -45, 0))
        kit.prop('prop_tree_small_ur', pos=(60, -70, 0))
        kit.prop('prop_tree_small_ul', pos=(-5, 75, 0))
        kit.prop('prop_tree_fat_ul', pos=(-95, -80, 0))
        # Gardens and yard things.
        kit.model('phase_5.5/models/estate/planterA', pos=(-45, 56, 0), h=90)
        kit.model('phase_5.5/models/estate/planterA', pos=(-5, -26, 0), h=180)
        kit.model('phase_5.5/models/estate/wheelbarrel', pos=(-60, 78, 0), h=40)
        kit.model('phase_5.5/models/estate/flowerBasket', pos=(-45, -30, 0), h=0)
        kit.model('phase_5.5/models/estate/candySwingSet', pos=(50, 55, 0), h=200, scale=1.1)
        kit.model('phase_5.5/models/estate/cakeSlide', pos=(70, 45, 0), h=-60)
        kit.model('phase_6/models/golf/picnic_table', pos=(50, -55, 0), h=20)
        kit.model('phase_6/models/golf/picnic_table', pos=(-10, 82, 0), h=-10)
        kit.model('phase_5.5/models/estate/target', pos=(-80, -70, 0), h=30, scale=0.8)
        kit.model('phase_5.5/models/estate/popcornCart', pos=(70, -45, 0), h=-120)
        # Flower gardens, planters and garden tools so the lawns look lived in.
        kit.model('phase_5.5/models/estate/planterB', pos=(-62, 62, 0), h=-90)
        kit.model('phase_5.5/models/estate/planterB', pos=(-14, 26, 0), h=0)
        kit.model('phase_5.5/models/estate/planterC', pos=(-30, -65.5, 0), h=0)
        kit.model('phase_5.5/models/estate/planterD', pos=(-90, 26, 0), h=0)
        kit.model('phase_5.5/models/estate/planterD', pos=(-90, -26, 0), h=180)
        kit.model('phase_5.5/models/estate/watering_cans', pos=(-56, 70, 0), h=30)
        kit.model('phase_5.5/models/estate/shovels', pos=(-58, -58, 0), h=-20)
        kit.model('phase_5.5/models/estate/flowerBasket', pos=(-15, 30, 0), h=180)
        # Two feet further from the picket fence: the gap between them was
        # just too narrow for a toon, which wedged in it.
        kit.model('phase_5.5/models/estate/west_barrelStand', pos=(24, 50, 0), h=-90)
        kit.model('phase_5.5/models/estate/ttr_r_prp_est_trolleyToaster', pos=(-8, 50, 0), h=-120)
        kit.model('phase_5.5/models/estate/wheelbarrel', pos=(20, -60, 0), h=-30)
        kit.model('phase_6/models/golf/picnic_table', pos=(-85, 70, 0), h=60)
        kit.prop('prop_tree_small_ur', pos=(-100, 40, 0))
        kit.prop('prop_tree_fat_ur', pos=(-94, 80, 0))
        kit.prop('prop_tree_small_ul', pos=(40, -90, 0))
        kit.prop('prop_tree_large_ul', pos=(-40, 90, 0))
        # Off the board fence: the gap between them wedged toons.
        kit.prop('prop_big_planter', pos=(80, 0, 0))
        # A few more trees in the open lawns.
        kit.prop('prop_tree_large_ur', pos=(82, 38, 0))
        kit.prop('prop_tree_fat_ul', pos=(80, -42, 0))
        kit.prop('prop_tree_small_ul', pos=(-78, 92, 0))
        kit.prop('prop_tree_large_ur', pos=(15, -92, 0))
        kit.prop('prop_tree_small_ur', pos=(35, -48, 0))
        kit.prop('prop_tree_fat_ur', pos=(12, 92, 0))
        # The yellow house's back yard: a picnic, a slide and a barrel.
        kit.model('phase_6/models/golf/picnic_table', pos=(-5, -80, 0), h=-20)
        kit.model('phase_5.5/models/estate/cakeSlide', pos=(-95, -45, 0), h=60)
        kit.model('phase_5.5/models/estate/west_barrelStand', pos=(-35, -88, 0), h=90)
        kit.model('phase_5.5/models/estate/flowerBasket', pos=(-48, -84, 0), h=0)
        kit.prop('prop_tree_small_ur', pos=(-20, -70, 0))

    def buildStreetProps(self):
        kit = self.kit
        for x in (-90, -50, -10, 25):
            kit.prop('prop_post_one_light', pos=(x, 17, 0), h=180)
            kit.prop('prop_post_one_light', pos=(x + 20, -17, 0), h=0)
        # The hydrants, trash cans and mailboxes dance the way Toontown
        # Central's do (its own idle animations).
        self.animProp('hydrant', 'idle0', (-45, 16, 0), 180)
        self.animProp('trashcan', 'idleHiccup0', (5, -16, 0), 0)
        # The mailbox's slot is on its -y side. This one stands on the
        # cul-de-sac's sidewalk, slot to the street: it used to stand on
        # the grass corner facing the yard, a few feet from a lamp post, and
        # toons and cogs got wedged between the two (Arthur).
        self.animProp('mailbox', 'idle0', self.MAILBOX_SPOT, self.facing(self.MAILBOX_SPOT, self.FOUNTAIN, back=True))
        self.animProp('hydrant', 'idle0', (-25, -16, 0), 0)
        self.animProp('trashcan', 'idleHiccup0', (-82, 16, 0), 180)
        self.animProp('mailbox', 'idle0', (-95, -16, 0), 200)
        # The cul-de-sac's fountain, a smaller copy of the one in Toontown Central.
        self.fountain = kit.prop('prop_toontown_central_fountain', pos=(self.FOUNTAIN[0], self.FOUNTAIN[1], 0.03), scale=0.8)
        # Benches round the cul-de-sac, facing the fountain (a bench's seat
        # is on its +y side; they had their backs to it).
        for spot in ((47.6, -28.2, 0.04), (47.6, 28.2, 0.04)):
            bench = kit.prop('prop_playground_bench', pos=spot, h=self.facing(spot, self.FOUNTAIN))
            # Its origin is at one end: turned round, it would swing out
            # onto the grass. Keep the middle of it where it was.
            lo, hi = bench.getTightBounds(self.root)
            bench.setPos(bench.getPos() + Point3(spot[0] - (lo[0] + hi[0]) * 0.5, spot[1] - (lo[1] + hi[1]) * 0.5, 0))
        kit.prop('prop_playground_bench', pos=(-40, 17.5, 0.04), h=0)
        kit.prop('prop_playground_bench', pos=(-40, -17.5, 0.04), h=180)

    @staticmethod
    def facing(spot, target, back=False):
        """The heading that turns a model's +y (or its -y, back) at target."""
        dx, dy = target[0] - spot[0], target[1] - spot[1]
        if back:
            dx, dy = -dx, -dy
        return math.degrees(math.atan2(-dx, dy))

    def animProp(self, kind, anim, pos, h):
        from direct.actor.Actor import Actor
        prop = Actor('phase_5/models/char/tt_r_ara_ttc_%s' % kind, {'idle': 'phase_5/models/char/tt_a_ara_ttc_%s_%s' % (kind, anim)})
        prop.reparentTo(self.root)
        prop.setPosHpr(pos[0], pos[1], pos[2], h, 0, 0)
        prop.loop('idle')
        # Not all in step.
        prop.pose('idle', hash((pos[0], pos[1])) % max(1, prop.getNumFrames('idle')))
        prop.loop('idle', restart=0)
        self.actors.append(prop)
        return prop

    def buildCars(self):
        kit = self.kit
        # The trolley, parked on the edge of the cul-de-sac like a bus with nowhere to go.
        # Under a node named like a trolley station, so Survival finds it for the way out.
        station = self.root.attachNewNode('trolley_station_downsizer')
        self.trolley = kit.model('phase_4/models/modules/trolley_station_TT', find='trolley_car', pos=(66, -16, 0.12), h=135,
                                 parent=station)
        # A kart in each driveway and one left in the street.
        # Pulled right up to the garage doors: the two-foot gap behind them
        # was a pocket cogs walked into and got stuck in.
        kit.model('phase_6/models/karting/Kart3_Final', pos=(13, 18.9, 0.05), h=90, scale=2.6, color=(0.5, 0.85, 0.5, 1))
        kit.model('phase_6/models/karting/Kart1_Final', pos=(16.5, -18.9, 0.05), h=-90, scale=2.6, color=(1.0, 0.85, 0.4, 1))
        kit.model('phase_12/models/bossbotHQ/Coggolf_cart3', pos=(-70, -5, 0.05), h=75)

    def buildDummies(self):
        kit = self.kit
        spots = [('f', (-45, 30, 0), 200), ('cc', (-12, -30, 0), 20),
                 ('tm', (-55, -32, 0), -20), ('nd', (-90, -35, 0), 60), ('ym', (-99, -2, 0), -90),
                 ('ac', (-72, 30, 0), 200), ('bf', (-15, 62, 0), 180), ('sc', (45, 70, 0), 160),
                 ('mh', (-70, -75, 0), 10), ('gh', (-72, -16.5, 0), 0), ('ms', (84, 82, 0), 225),
                 ('rb', (-20, 16.5, 0), 180), ('dt', (-95, 60, 0), -60), ('bs', (-104, -94, 0), -45),
                 ('tw', (86, -90, 0), 45), ('sd', (-104, 94, 0), -135), ('pp', (65, 40, 0), 220)]
        for name, pos, h in spots:
            # A bit over game size, to match the scaled-up houses and karts.
            kit.cogStatue(name, pos, h, skeleton=True).setScale(1.25)
            # Solid, like any statue.
            kit.collideTube(pos, 1.3, 6.0, name='dummyCollide')

    def buildEdges(self):
        kit = self.kit
        x0, y0, x1, y1 = SITE
        # A tall board fence all the way round the test site.
        fence = [{'code': 'wall_fence_wood_ur', 'height': 14, 'color': (0.86, 0.72, 0.52)}]
        x = x0
        while x < x1:
            # A flat runs along its own +x, so the south side (turned 180)
            # starts from its east end to cover x..x+20 like the north side.
            kit.flat(x + 20, y0, 180, 20, fence).setTwoSided(True)
            kit.flat(x, y1, 0, 20, fence).setTwoSided(True)
            x += 20
        y = y0
        while y < y1:
            kit.flat(x0, y + 20, 270, 20, fence).setTwoSided(True)
            kit.flat(x1, y, 90, 20, fence).setTwoSided(True)
            y += 20
        # The welcome sign over the closed end of the street.
        sign = kit.dna("""
<sign code="sign_general1">
  <color r="1" g="0.88" b="0.56" a="1" />
  <baseline code="TT_Comedy" kern="0.04" width="30" height="30" flags="d">
    <color r="0.75" g="0.1" b="0.1" a="1" /><pos x="0" y="0" z="1.3" /><scale x="0.95" y="1" z="1.2" />
    <text>Downsizer Drive</text>
  </baseline>
  <baseline code="TT_Comedy" kern="0.02" width="36" height="36">
    <color r="0.2" g="0.2" b="0.25" a="1" /><pos x="0" y="0" z="-0.45" /><scale x="0.98" y="1" z="1.1" />
    <text>A Cog Testing Community</text>
  </baseline>
</sign>""")
        sign.setPosHprScale(-109, 0, 15.8, 90, 0, 0, 1.6, 1, 1.4)
        # The street is closed off where it meets the fence.
        for i, y in enumerate((-10, -4, 2, 8)):
            kit.model('phase_6/models/karting/cone', pos=(-104, y, 0), h=i * 30, scale=1.5)
        # Its own blocker is one polygon facing the road: a toon walked
        # through the board from behind. A wall all round it instead.
        board = kit.prop('prop_construction_sign', pos=(-102, 15, 0), h=90)
        for col in board.findAllMatches('**/+CollisionNode'):
            col.stash()
        kit.solid(board, shrink=1.0, minSize=1.2)
        # A solid row of crates along the fence: with gaps between them a
        # toon squeezed into the pocket between two, and the crates' own
        # boxes push a toon the wrong way from inside (it walked into
        # them). Walls round each one instead.
        for pos in ((-108, -8, 0), (-108, -4, 0), (-108, 0, 0), (-108, 4, 0), (-108, 8, 0), (-108, 4, 4.0)):
            crate = kit.model('phase_6/models/karting/krate', pos=pos, h=0, scale=2.5)
            for col in crate.findAllMatches('**/+CollisionNode'):
                col.stash()
            if pos[2] == 0:
                kit.solid(crate, shrink=1.0)
        # The Cogs' buildings out in the sand, watching.
        kit.prop('suit_landmark_s1', pos=(-200, 210, 0), h=-135)
        kit.prop('suit_landmark_s3', pos=(220, 190, 0), h=135)
        kit.prop('suit_landmark_s2', pos=(240, -180, 0), h=45)
        kit.prop('suit_landmark_s4', pos=(-210, -220, 0), h=-45)
        kit.prop('suit_landmark_s5', pos=(-280, 0, 0), h=-90)
        for pos in ((-160, 120), (150, 140), (170, -110), (-140, -150), (-170, 60), (190, 30)):
            kit.model('phase_5.5/models/estate/sand_mound', pos=(pos[0], pos[1], -1), scale=5)

    def buildSky(self):
        kit = self.kit
        # The Cogs' grey sky over Sellbot country, the factory on the horizon.
        self.sky = kit.model('phase_9/models/cogHQ/cog_sky', scale=1.0)
        self.sky.setBin('background', 100)
        self.sky.setDepthWrite(0)
        self.sky.setLightOff()
        kit.model('phase_9/models/cogHQ/SellbotFactoryExterior', pos=(0, 560, -2), h=180, scale=0.6)
        fog = Fog('downsizerFog')
        fog.setColor(0.6, 0.6, 0.6)
        fog.setLinearRange(250, 900)
        self.root.setFog(fog)
