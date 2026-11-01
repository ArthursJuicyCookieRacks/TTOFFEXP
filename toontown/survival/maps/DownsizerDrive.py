"""Downsizer Drive: a pretend Toontown street the Cogs built out in Sellbot
country to try out their Downsizers. Two toon houses face each other
across a little cul-de-sac, the yards are fenced, the cars are parked, and
Skelecog test dummies stand about the lawns. Past the board fence there is
only sand, Cog buildings and the factory's smoke.
"""

from panda3d.core import Fog, Vec4

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
    SHOTS = [
        ('overview', (-170, -170, 130), (-10, 0, 0)),
        ('overview_high', (0, -20, 260), (0, 0, 0)),
        ('street_west', (-80, 0, 6), (20, 0, 4)),
        ('street_east', (40, -4, 6), (-40, 0, 6)),
        ('house_north', (-12, -6, 7), (-14, 50, 10)),
        ('house_south', (-18, 6, 7), (-16, -50, 10)),
        ('welcome_sign', (-82, 0, 12), (-109, 0, 16)),
        ('cul_de_sac', (22, -4, 9), (60, 8, 2)),
        ('backyard_north', (-70, 92, 10), (-20, 60, 4)),
        ('backyard_south', (40, -95, 10), (-20, -60, 4)),
    ]

    def __init__(self):
        self.root = render.attachNewNode('downsizerDrive')
        self.kit = MapKit(self.root)
        # The street signs' font, which the Toontown Central storage leaves out.
        self.kit.store.storeFont(loader.loadFont('phase_3/models/fonts/Comedy'), 'TT_Comedy')

    def build(self):
        self.buildGround()
        self.buildHouses()
        self.buildYards()
        self.buildStreetProps()
        self.buildCars()
        self.buildDummies()
        self.buildEdges()
        self.buildSky()

    def destroy(self):
        self.kit.destroy()

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
        kit.rect(x0, y0, x1, y1, z=0.01, tex=GRASS_TEX, tile=20, name='siteLawn')
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
            kit.boxBuilding((x, y, 0), h, 18, 20, front, side, roofTex=ROOF_TEX)

    def picket(self, a, b):
        self.kit.wallQuad(a, b, 0, 4, tex=PICKET_TEX[0], alpha=PICKET_TEX[1], tile=8, tileZ=4, name='picket')

    def buildYards(self):
        kit = self.kit
        # White picket fences along the front of each yard, with gaps for the paths and drives.
        for y in (20.5, -20.5):
            self.picket((-110, y), (-36, y))
            self.picket((-24, y), (2, y))
        # And between the front and back yards.
        self.picket((30, 30), (30, 90))
        self.picket((30, -30), (30, -90))
        # Mailboxes by the curb.
        kit.model('phase_5.5/models/estate/mailboxHouse', pos=(-38, 21.5, 0), h=180)
        kit.model('phase_5.5/models/estate/mailboxHouse', pos=(-22, -21.5, 0), h=0)
        # Trees.
        kit.prop('prop_tree_large_ur', pos=(-75, 40, 0))
        kit.prop('prop_tree_fat_ur', pos=(55, 70, 0))
        kit.prop('prop_tree_large_ul', pos=(-75, -45, 0))
        kit.prop('prop_tree_small_ur', pos=(60, -70, 0))
        kit.prop('prop_tree_small_ul', pos=(-5, 75, 0))
        kit.prop('prop_tree_fat_ul', pos=(-95, -80, 0))
        # Gardens and yard things.
        kit.model('phase_5.5/models/estate/planterA', pos=(-55, 26, 0), h=0)
        kit.model('phase_5.5/models/estate/planterA', pos=(-5, -26, 0), h=180)
        kit.model('phase_5.5/models/estate/wheelbarrel', pos=(-60, 78, 0), h=40)
        kit.model('phase_5.5/models/estate/flowerBasket', pos=(-45, -30, 0), h=0)
        kit.model('phase_5.5/models/estate/candySwingSet', pos=(50, 55, 0), h=200, scale=1.1)
        kit.model('phase_5.5/models/estate/cakeSlide', pos=(70, 45, 0), h=-60)
        kit.model('phase_6/models/golf/picnic_table', pos=(50, -55, 0), h=20)
        kit.model('phase_6/models/golf/picnic_table', pos=(-10, 82, 0), h=-10)
        kit.model('phase_5.5/models/estate/target', pos=(-80, -70, 0), h=30, scale=0.8)
        kit.model('phase_5.5/models/estate/popcornCart', pos=(70, -45, 0), h=-120)

    def buildStreetProps(self):
        kit = self.kit
        for x in (-90, -50, -10, 25):
            kit.prop('prop_post_one_light', pos=(x, 17, 0), h=180)
            kit.prop('prop_post_one_light', pos=(x + 20, -17, 0), h=0)
        kit.model('phase_5/models/char/tt_r_ara_ttc_hydrant', pos=(-62, 16, 0), h=180)
        kit.model('phase_5/models/char/tt_r_ara_ttc_trashcan', pos=(5, -16, 0), h=0)
        kit.model('phase_5/models/char/tt_r_ara_ttc_mailbox', pos=(30, 16, 0), h=200)

    def buildCars(self):
        kit = self.kit
        # The trolley, parked in the cul-de-sac like a bus with nowhere to go.
        kit.model('phase_4/models/modules/trolley_station_TT', find='trolley_car', pos=(54, 12, 0.12), h=200)
        # A kart in each driveway and one left in the street.
        kit.model('phase_6/models/karting/Kart3_Final', pos=(13, 17, 0.05), h=90, scale=2.6, color=(0.5, 0.85, 0.5, 1))
        kit.model('phase_6/models/karting/Kart1_Final', pos=(13, -16, 0.05), h=-90, scale=2.6, color=(1.0, 0.85, 0.4, 1))
        kit.model('phase_12/models/bossbotHQ/Coggolf_cart3', pos=(-70, -5, 0.05), h=75)

    def buildDummies(self):
        kit = self.kit
        spots = [('f', (-45, 30, 0), 200), ('p', (-48, 34, 0), 160), ('cc', (-12, -30, 0), 20),
                 ('tm', (-55, -32, 0), -20), ('nd', (30, 8, 0), 120), ('ym', (-85, 4, 0), -90),
                 ('ac', (62, -14, 0), 30), ('bf', (-15, 62, 0), 180), ('sc', (45, 70, 0), 160),
                 ('mh', (-70, -75, 0), 10)]
        for name, pos, h in spots:
            kit.cogStatue(name, pos, h, skeleton=True)

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
  <baseline code="TT_Comedy" kern="0.06" wiggle="3" stumble="0.04" stomp="0.02" width="25" height="25" flags="d">
    <color r="0.75" g="0.1" b="0.1" a="1" /><pos x="0" y="0" z="0.05" /><scale x="1.4" y="1" z="1.6" />
    <text>Downsizer Drive</text>
  </baseline>
  <baseline code="TT_Comedy" kern="0.03" width="40" height="40">
    <color r="0.2" g="0.2" b="0.25" a="1" /><pos x="0" y="0" z="-1.15" /><scale x="0.7" y="1" z="0.7" />
    <text>A Cog Testing Community</text>
  </baseline>
</sign>""")
        sign.setPosHprScale(-109, 0, 17, 90, 0, 0, 1.6, 1, 1.4)
        # The street is closed off where it meets the fence.
        for i, y in enumerate((-10, -4, 2, 8)):
            kit.model('phase_6/models/karting/cone', pos=(-104, y, 0), h=i * 30, scale=1.5)
        kit.prop('prop_construction_sign', pos=(-102, 15, 0), h=90)
        for pos in ((-108, -8, 0), (-108, 0, 0), (-108, 8, 0), (-108, 4, 5)):
            kit.model('phase_6/models/karting/krate', pos=pos, h=0, scale=2.5)
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
