"""Two-Face Theater: an old picture palace on a Donald's Dreamland street,
shut up for years and now running the Cogs' own late show. The street out
front, the lobby, the big auditorium with its stage and screen, the dressing
rooms backstage and the alley round the side make one loop.
"""

from panda3d.core import Fog, TransparencyAttrib, Vec4

from toontown.survival.maps.MapKit import BASE_STORAGE, MapKit

STORAGE = BASE_STORAGE + ('phase_8/dna/storage_DL.xml', 'phase_8/dna/storage_DL_town.xml')

DL_STREET = 'street_street_DL_tex'
DL_SIDEWALK = 'street_sidewalk_DL_tex'
WALLPAPER = 'phase_3.5/maps/wall_paper_a2.jpg'
WAINSCOT = 'phase_11/maps/LB_WoodPanel2.jpg'
PANEL = 'phase_11/maps/LB_WoodPanel.jpg'
CEILING = 'phase_11/maps/LB_Ceiling2.jpg'
CARPET = 'phase_5.5/maps/flooring_carpetA_neutral.jpg'
ROBE = 'phase_11/maps/LB_Robe.jpg'
STAGE_FLOOR = 'phase_9/maps/WoodPlanks1.jpg'
MARBLE = 'phase_11/maps/LB_Marble4.jpg'
CONCRETE = 'phase_11/maps/LB_CementGround_2.jpg'

RED_VELVET = (0.95, 0.22, 0.2)
CARPET_RED = (0.75, 0.2, 0.22)
SEAT_RED = (0.85, 0.2, 0.2, 1)
DL_WALL = (0.55, 0.5, 0.72)
NIGHT = Vec4(0.52, 0.5, 0.72, 1)
INSIDE = Vec4(0.72, 0.62, 0.6, 1)

# Room bounds (x0, y0, x1, y1).
PLAZA = (-45, -78, 80, -30)
LOBBY = (-30, -30, 30, 0)
HALL = (-40, 0, 40, 100)
STAGE = (-32, 72, 32, 100, 4)
BACKSTAGE = (40, 60, 64, 100)
ALLEY = (40, -30, 80, 60)


class TwoFaceTheater:
    NAME = 'Two-Face Theater'
    PLAYER_START = ((0, -15, 0), 0)
    SHOTS = [
        ('overview', (-130, -170, 150), (10, 10, 0)),
        ('front', (0, -74, 8), (0, -30, 12)),
        ('front_high', (-20, -72, 16), (0, -30, 15)),
        ('across', (10, -36, 6), (0, -78, 10)),
        ('lobby', (-12, -28, 8), (14, -6, 3)),
        ('lobby_back', (0, -3, 8), (0, -30, 5)),
        ('hall_from_back', (0, 4, 14), (0, 95, 12)),
        ('hall_from_stage', (0, 80, 14), (0, 10, 4)),
        ('stage', (-20, 52, 9), (-10, 80, 4)),
        ('backstage', (44, 64, 10), (60, 96, 6)),
        ('alley', (60, -25, 7), (60, 55, 6)),
    ]

    def __init__(self):
        self.root = render.attachNewNode('twoFaceTheater')
        self.outside = self.root.attachNewNode('outside')
        self.inside = self.root.attachNewNode('inside')
        self.kit = MapKit(self.root, STORAGE)

    def build(self):
        from toontown.toonbase import ToontownGlobals
        try:
            self.kit.store.storeFont(loader.loadFont('phase_3/models/fonts/JiggeryPokery'), 'DL_JiggeryPokery')
        except Exception:
            pass
        self.buildStreet()
        self.buildFacade()
        self.buildLobby()
        self.buildHall()
        self.buildStage()
        self.buildBackstage()
        self.buildAlley()
        self.buildSky()
        self.outside.setColorScale(NIGHT)
        self.inside.setColorScale(INSIDE)

    def destroy(self):
        self.kit.destroy()

    # Out front ---------------------------------------------------------------
    def buildStreet(self):
        kit = self.kit
        out = self.outside
        x0, y0, x1, y1 = PLAZA
        kit.rect(x0, y0, x1, y1 - 8, z=0.0, tex=DL_STREET, tile=20, parent=out, name='street')
        kit.rect(x0, y1 - 8, x1, y1, z=0.02, tex=DL_SIDEWALK, tile=8, parent=out, name='walk')
        # Shops across the street, Dreamland style.
        across = [
            (20, [{'code': 'wall_md_bricks_ur', 'height': 20, 'color': (0.42, 0.4, 0.62),
                   'windows': ('window_sm_curvedDL_ur', 2, (0.95, 0.85, 0.4)), 'cornice': ('cornice_marble_ur', (0.6, 0.6, 0.75))}]),
            (25, [{'code': 'wall_lg_rock_ur', 'height': 24, 'color': (0.5, 0.45, 0.6),
                   'windows': ('window_md_curvedDL_ur', 2, (0.95, 0.85, 0.4))}]),
            (15, [{'code': 'wall_md_board_ur', 'height': 16, 'color': (0.35, 0.33, 0.5), 'door': 'door_double_curvedDL_ur',
                   'doorColor': (0.6, 0.6, 0.8)}]),
            (25, [{'code': 'wall_md_bricks_ur', 'height': 28, 'color': (0.45, 0.42, 0.66),
                   'windows': ('window_sm_roundDL_ur', 3, (0.95, 0.85, 0.4)), 'cornice': ('cornice_stone_ur', (0.6, 0.6, 0.75))}]),
            (20, [{'code': 'wall_md_pillars_ur', 'height': 18, 'color': (0.4, 0.38, 0.55),
                   'windows': ('window_sm_shutteredDL_ur', 2, (0.95, 0.85, 0.4))}]),
            (20, [{'code': 'wall_lg_brick_ur', 'height': 22, 'color': (0.5, 0.42, 0.58),
                   'windows': ('window_sm_squareDL_ur', 2, (0.95, 0.85, 0.4))}]),
        ]
        x = x1
        kit.rect(-400, -400, 400, 400, z=-0.1, tex=DL_STREET, tile=20, parent=out, name='ground')
        for width, walls in across:
            kit.flat(x, y0, 180, width, walls, parent=out).setTwoSided(True)
            x -= width
        # The west end: a high wall with a locked gate.
        kit.flat(x0, y0, 270, 48, [{'code': 'wall_lg_rock_ur', 'height': 22, 'color': (0.4, 0.38, 0.55)}], parent=out)
        kit.flat(x1, y1 + 0, 90, 0.01, [{'code': 'wall_lg_rock_ur', 'height': 1, 'color': (0, 0, 0)}], parent=out)
        # Spooky streetlights and trees.
        for x in (-35, -10, 15, 50, 72):
            kit.model('phase_3.5/models/props/tt_m_ara_ddl_streetlight_halloween', pos=(x, -40, 0), h=180, parent=out)
        for x in (-25, 30, 62):
            kit.model('phase_3.5/models/props/tt_m_ara_ddl_tree_halloween', pos=(x, -70, 0), h=0, parent=out)
        kit.model('phase_8/models/props/mailbox_DL', pos=(-38, -66, 0), h=0, parent=out)
        kit.prop('prop_trashcan_metal', pos=(40, -36, 0), h=180, parent=out)
        kit.prop('prop_DL_hydrant', pos=(-20, -36, 0), h=180, parent=out)

    def buildFacade(self):
        kit = self.kit
        out = self.outside
        front = {'code': 'wall_md_bricks_ur', 'color': (0.62, 0.32, 0.36)}
        # Left and right of the doors, then over them.
        kit.flat(-40, -30, 0, 34, [dict(front, height=30, windows=('window_md_curvedDL_ur', 2, (0.95, 0.85, 0.45)),
                                         cornice=('cornice_dental_ur', (0.8, 0.7, 0.55)))], parent=out)
        kit.flat(6, -30, 0, 34, [dict(front, height=30, windows=('window_md_curvedDL_ur', 2, (0.95, 0.85, 0.45)),
                                       cornice=('cornice_dental_ur', (0.8, 0.7, 0.55)))], parent=out)
        top = kit.flat(-6, -30, 0, 12, [dict(front, height=16, cornice=('cornice_dental_ur', (0.8, 0.7, 0.55)))], parent=out)
        top.setZ(14)
        # The marquee over the doors.
        marquee = kit.dna('''
<prop name="marquee" code="prop_marquee">
  <pos x="0" y="-31.5" z="15" /><nhpr h="0" p="0" r="0" /><scale x="1.25" y="1.25" z="1.25" />
  <color r="0.5" g="0.5" b="0.5" a="1" />
  <sign>
    <color r="0.25" g="0.25" b="0.25" a="1" />
    <baseline code="DL_JiggeryPokery" kern="0.07" flags="d">
      <color r="0.6" g="0" b="0.2" a="1" /><pos x="0" y="0" z="-0.3" /><scale x="1.2" y="1" z="1.2" />
      <text>TWO-FACE  THEATER</text>
    </baseline>
    <baseline code="DL_JiggeryPokery" kern="0.05" flags="d">
      <color r="0" g="0.3" b="0.55" a="1" /><pos x="0" y="0" z="-1.75" /><scale x="0.9" y="1" z="0.9" />
      <text>TONIGHT: NIGHT OF THE LIVING COGS</text>
    </baseline>
  </sign>
</prop>''', parent=out)
        # A dark doorway: the lobby is just inside.
        kit.wallQuad((-6, -30.3), (6, -30.3), 0, 0.01, parent=out)
        kit.model('phase_8/models/props/streetlight_DL', pos=(-10, -33, 0), h=180, parent=out)
        kit.model('phase_8/models/props/streetlight_DL', pos=(10, -33, 0), h=180, parent=out)
        # Posters either side of the doors.
        kit.model('phase_9/models/cogHQ/poster_mickey', pos=(-16, -30.5, 3), h=-90, scale=(1, 5, 5), parent=out)
        kit.model('phase_9/models/cogHQ/poster_mickey', pos=(16, -30.5, 3), h=-90, scale=(1, 5, 5), parent=out)

    # Inside --------------------------------------------------------------
    def roomLayers(self, height, upper=WALLPAPER, upperColor=None):
        return [(0, 5, WAINSCOT, 6, None), (5, height, upper, 8, upperColor)]

    def buildLobby(self):
        kit = self.kit
        inn = self.inside
        x0, y0, x1, y1 = LOBBY
        h = 18
        kit.rect(x0, y0, x1, y1, z=0.01, tex=kit.tinted(CARPET, CARPET_RED), tile=12, parent=inn, name='lobbyFloor')
        ceil = kit.rect(x0, y0, x1, y1, z=h, tex=CEILING, tile=10, parent=inn, name='lobbyCeiling')
        ceil.setTwoSided(True)
        layers = self.roomLayers(h)
        kit.wall((x0, y0 + 0.2), (x1, y0 + 0.2), layers, gaps=[(24, 36, 13)], parent=inn)
        kit.wall((x0, y1), (x1, y1), layers, gaps=[(6, 16, 12), (44, 54, 12)], parent=inn)
        kit.wall((x0, y0), (x0, y1), layers, parent=inn)
        kit.wall((x1, y0), (x1, y1), layers, parent=inn)
        # Ticket booth and the snack counter.
        kit.model('phase_3.5/models/modules/facade_b', pos=(-25, -14, 0), h=90, scale=1.0, parent=inn)
        kit.model('phase_3.5/models/modules/facade_a', pos=(25, -14, 0), h=-90, scale=1.0, parent=inn)
        kit.model('phase_5.5/models/estate/popcornCart', pos=(22, -4, 0), h=-120, parent=inn)
        kit.model('phase_3.5/models/modules/couch_2person', pos=(-26, -26, 0), h=-45, parent=inn)
        kit.model('phase_3.5/models/modules/umbrella_stand', pos=(-27, -4, 0), parent=inn)
        kit.model('phase_3.5/models/modules/lamp_tall', pos=(26, -27, 0), parent=inn)
        kit.model('phase_3.5/models/modules/rug', pos=(0, -14, 0.03), h=90, scale=2.0, parent=inn)
        # Posters of the coming attractions.
        for x, path in ((-12, 'tt_m_ara_crg_paintingMoverShaker'), (12, 'tt_m_ara_crg_paintingLegalEagle')):
            kit.model('phase_5/models/cogdominium/' + path, pos=(x / 2, -0.3, 6), h=0, scale=0.55, parent=inn)
            kit.model('phase_5/models/cogdominium/' + path, pos=(-x, 0.3, 14), h=180, scale=1.4, parent=inn)

    def buildHall(self):
        kit = self.kit
        inn = self.inside
        x0, y0, x1, y1 = HALL
        h = 34
        kit.rect(x0, y0, x1, y1, z=0.0, tex=kit.tinted(CARPET, CARPET_RED), tile=12, parent=inn, name='hallFloor')
        ceil = kit.rect(x0, y0, x1, y1, z=h, tex=CEILING, tile=12, parent=inn, name='hallCeiling')
        ceil.setTwoSided(True)
        # The roof over it all, as seen from the street.
        kit.rect(-40, -30, 64, 100, z=h + 0.2, tex='phase_9/maps/Roof.jpg', tile=16, parent=self.outside, name='roof')
        dark = (0.55, 0.45, 0.45, 1)
        layers = [(0, 6, PANEL, 6, None), (6, h, WALLPAPER, 10, dark)]
        kit.wall((x0, y0 + 0.1), (x1, y0 + 0.1), layers, gaps=[(16, 26, 12), (54, 64, 12)], parent=inn)
        kit.wall((x0, y0), (x0, y1), layers, parent=inn)
        kit.wall((x1, y0), (x1, y1), layers, gaps=[(78, 88, 15)], parent=inn)
        kit.wall((x0, y1), (x1, y1), layers, parent=inn)
        # Rows of seats in three blocks, with aisles between.
        seats = inn.attachNewNode('seats')
        for row in range(10):
            y = 14 + row * 5
            for block in ((-36, -14), (-9, 9), (14, 36)):
                x = block[0] + 1.5
                while x <= block[1] - 1.5:
                    kit.model('phase_5.5/models/estate/chairAdesat', pos=(x, y, 0), h=180, scale=0.9, parent=seats, color=SEAT_RED)
                    x += 3.2
        seats.flattenStrong()
        # Wall lamps down both sides.
        for y in (15, 35, 55):
            kit.model('phase_11/models/lawbotHQ/LB_torch_lampB', pos=(-36.5, y, 0), parent=inn, scale=1.3)
            kit.model('phase_11/models/lawbotHQ/LB_torch_lampB', pos=(36.5, y, 0), parent=inn, scale=1.3)
        # The projector looking down from the back wall.
        kit.model('phase_5/models/cogdominium/ttr_m_ara_csa_securityCamera', pos=(0, 1, 26), h=180, scale=2.5, parent=inn)

    def buildStage(self):
        kit = self.kit
        inn = self.inside
        sx0, sy0, sx1, sy1, sh = STAGE
        velvet = kit.tinted(ROBE, RED_VELVET, crop=(0.05, 0.62, 0.95, 1.0))
        # The stage: a raised wooden floor with a dark front.
        kit.rect(sx0, sy0, sx1, sy1, z=sh, tex=STAGE_FLOOR, tile=10, parent=inn, name='stageFloor')
        kit.wallQuad((sx0, sy0), (sx1, sy0), 0, sh, tex=PANEL, tile=6, parent=inn, name='stageFront')
        kit.wallQuad((sx0, sy0), (sx0, sy1), 0, sh, tex=PANEL, tile=6, parent=inn)
        kit.wallQuad((sx1, sy0), (sx1, sy1), 0, sh, tex=PANEL, tile=6, parent=inn)
        # Steps up at both ends of the front.
        for x in (-31, 19):
            kit.model('phase_8/models/props/stairs_DG', pos=(x, sy0 - 1.6, 0), h=0, scale=(1, 1, sh / 5.5), parent=inn,
                      color=(0.55, 0.38, 0.3, 1))
        # The proscenium arch and its curtains.
        kit.wall((-40, sy0 + 0.5), (sx0, sy0 + 0.5), [(0, 34, MARBLE, 10, None)], parent=inn)
        kit.wall((sx1, sy0 + 0.5), (40, sy0 + 0.5), [(0, 34, MARBLE, 10, None)], parent=inn)
        kit.wall((sx0, sy0 + 0.5), (sx1, sy0 + 0.5), [(27, 34, MARBLE, 10, None)], parent=inn)
        kit.wallQuad((sx0, sy0 + 1.5), (sx0 + 9, sy0 + 1.5), sh, 27, tex=velvet, tile=9, tileZ=23, parent=inn, name='curtainL')
        kit.wallQuad((sx1 - 9, sy0 + 1.5), (sx1, sy0 + 1.5), sh, 27, tex=velvet, tile=9, tileZ=23, parent=inn, name='curtainR')
        kit.wallQuad((sx0, sy0 + 1.6), (sx1, sy0 + 1.6), 22, 27, tex=velvet, tile=8, tileZ=10, parent=inn, name='valance')
        kit.wallQuad((sx0, sy1 - 0.5), (sx1, sy1 - 0.5), sh, 30, tex=velvet, tile=10, tileZ=26, parent=inn, name='backCurtain')
        # The screen, showing the Cogs' favourite picture.
        screen = kit.wallQuad((-14, sy1 - 1.0), (14, sy1 - 1.0), 9, 24, color=(0.92, 0.92, 0.88, 1), parent=inn, name='screen')
        kit.model('phase_9/models/cogHQ/poster_mickey', pos=(0, sy1 - 1.4, 9.3), h=-90, scale=(1, 10.5, 10.5), parent=inn)
        # Footlights.
        for x in range(-28, 29, 8):
            kit.model('phase_11/models/lawbotHQ/LB_torch_lampC', pos=(x, sy0 + 3, sh), scale=0.5, parent=inn)

    def buildBackstage(self):
        kit = self.kit
        inn = self.inside
        x0, y0, x1, y1 = BACKSTAGE
        h = 18
        z = STAGE[4]
        kit.rect(x0, y0, x1, y1, z=z, tex=STAGE_FLOOR, tile=10, parent=inn, name='backstageFloor')
        kit.wallQuad((x0, y0), (x1, y0), 0, z, tex=PANEL, tile=6, parent=inn)
        ceil = kit.rect(x0, y0, x1, y1, z=z + h, tex=CEILING, tile=10, parent=inn)
        ceil.setTwoSided(True)
        layers = [(z, z + 5, WAINSCOT, 6, None), (z + 5, z + h, 'phase_3.5/maps/wall_paper_a2.jpg', 8, (0.7, 0.6, 0.6, 1))]
        kit.wall((x1, y0), (x1, y1), layers, parent=inn)
        kit.wall((x0, y1), (x1, y1), layers, parent=inn)
        kit.wall((x0, y0), (x1, y0), layers, gaps=[(8, 18, z + 11)], parent=inn)
        # Dressing room things.
        kit.model('phase_3.5/models/modules/trophy_frame', pos=(x1 - 0.5, 80, z + 4), h=-90, scale=1.4, parent=inn)
        kit.model('phase_3.5/models/modules/trophy_frame', pos=(x1 - 0.5, 90, z + 4), h=-90, scale=1.4, parent=inn)
        kit.model('phase_3.5/models/modules/coatrack', pos=(60, 96, z), parent=inn)
        kit.model('phase_3.5/models/modules/coatrack', pos=(46, 96, z), h=40, parent=inn)
        kit.model('phase_5.5/models/estate/tt_m_ara_est_accessoryTrunkBoy', pos=(52, 97, z), h=180, parent=inn)
        kit.model('phase_3.5/models/modules/chair', pos=(60, 85, z), h=-90, parent=inn)
        for pos in ((44, 64, z), (47, 64, z), (44, 64, z + 3)):
            kit.model('phase_10/models/cashbotHQ/CBWoodCrate', pos=pos, scale=0.6, parent=inn)
        # Steps down to the alley.
        kit.model('phase_11/models/lawbotHQ/LB_stair_ramp', pos=(53, y0 - 5, 0), h=0, scale=(0.9, 1.0, 0.45), parent=inn)

    def buildAlley(self):
        kit = self.kit
        out = self.outside
        x0, y0, x1, y1 = ALLEY
        kit.rect(x0, y0, x1, y1, z=0.0, tex=CONCRETE, tile=12, parent=out, name='alleyFloor')
        brick = (0.45, 0.4, 0.55)
        # The theater's side wall and the building across the alley.
        y = PLAZA[1]
        while y < y1:
            if y >= y0:
                kit.flat(x0 + 0.3, y, 90, 20, [{'code': 'wall_md_bricks_ur', 'height': 34, 'color': brick}], parent=out)
            kit.flat(x1, y + 20, 270, 20, [{'code': 'wall_lg_brick_ur', 'height': 26, 'color': (0.38, 0.36, 0.52),
                                             'windows': ('window_sm_shutteredDL_ur', 1, (0.9, 0.8, 0.4))}], parent=out).setTwoSided(True)
            y += 20
        # The end of the alley: the back of the stage, with the stage door up the steps.
        z = STAGE[4]
        kit.flat(x0, y1 - 0.3, 0, 8, [{'code': 'wall_md_bricks_ur', 'height': 34, 'color': brick}], parent=out)
        kit.flat(58, y1 - 0.3, 0, x1 - 58, [{'code': 'wall_md_bricks_ur', 'height': 34, 'color': brick}], parent=out)
        kit.flat(48, y1 - 0.3, 0, 10, [{'code': 'wall_md_bricks_ur', 'height': 34 - (z + 11), 'color': brick}], parent=out).setZ(z + 11)

        # Alley junk.
        kit.prop('prop_trashcan_metal', pos=(76, 10, 0), h=-90, parent=out)
        kit.prop('prop_trashcan_metal', pos=(76, 14, 0), h=-80, parent=out)
        kit.model('phase_10/models/cashbotHQ/CBWoodCrate', pos=(75, 30, 0), parent=out)
        kit.model('phase_10/models/cashbotHQ/CBWoodCrate', pos=(75, 34, 0), h=20, parent=out)
        kit.model('phase_10/models/cashbotHQ/CBWoodCrate', pos=(75, 32, 4), h=5, parent=out)
        kit.prop('prop_cellar_door', pos=(44, -10, 0), h=-90, parent=out)
        kit.model('phase_3.5/models/props/tt_m_ara_ddl_streetlight_halloween', pos=(76, -10, 0), h=-90, parent=out)
        kit.model('phase_3.5/models/props/tt_m_ara_ddl_streetlight_halloween', pos=(76, 45, 0), h=-90, parent=out)

    def buildSky(self):
        self.sky = self.kit.model('phase_8/models/props/DL_sky', parent=self.outside)
        self.sky.setBin('background', 100)
        self.sky.setDepthWrite(0)
        self.sky.setLightOff()
