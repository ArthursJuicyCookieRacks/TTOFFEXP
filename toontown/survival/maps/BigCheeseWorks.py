"""Big Cheese Works: the Cogs' own factory, where new Cogs are put together
and sent out by teleporter. A smoky yard with a giant statue of the Big
Cheese, the furnace room with the power switch, and the mainframe hall
where the big teleporter hums under the catwalks. Smaller pads in the yard
and the furnace room link back to the mainframe.
"""

from panda3d.core import Fog, TransparencyAttrib, Vec4

from toontown.survival.maps.MapKit import BASE_STORAGE, MapKit

STORAGE = BASE_STORAGE + ('phase_8/dna/storage_DL_town.xml',)

FLOOR = 'phase_9/maps/CementFloorx4Warm.jpg'
PLATE = 'phase_9/maps/FootFactoryMetalPlate.jpg'
BRICK = 'phase_9/maps/WallBricks.jpg'
FACTORY_WALL = 'phase_9/maps/FootFactory_Wall1.jpg'
RIVETS = 'phase_9/maps/WallMetalPlateLargeRivets.jpg'
CEMENT = 'phase_10/maps/CBWallsCement.jpg'
BLOCKS = 'phase_10/maps/CBMintBigBlocks.jpg'
HAZARD = 'phase_10/maps/CBStationStripes2.jpg'
ROLLUP = 'phase_10/maps/RollUpDoors.jpg'
CEILING = 'phase_9/maps/FootFactoryMetalPlate.jpg'
GRATE = ('phase_9/maps/FloorGrate.jpg', 'phase_9/maps/FloorGrate_a.rgb')

YARD = (-50, -70, 50, 0)
FURNACE = (-50, 0, -10, 60)
MAINFRAME = (-10, 0, 50, 70)
SMOKE = Vec4(0.78, 0.76, 0.74, 1)
INSIDE = Vec4(0.8, 0.74, 0.68, 1)


class BigCheeseWorks:
    NAME = 'Big Cheese Works'
    PLAYER_START = ((0, -55, 0), 0)
    SHOTS = [
        ('overview', (-120, -160, 140), (0, -5, 0)),
        ('yard', (0, -68, 10), (0, -10, 14)),
        ('statue', (-15, -50, 6), (0, -32, 16)),
        ('yard_pad', (20, -40, 8), (38, -58, 2)),
        ('furnace', (-30, 8, 14), (-30, 50, 4)),
        ('mainframe', (40, 4, 14), (18, 42, 10)),
        ('teleporter', (20, 18, 7), (20, 42, 8)),
        ('catwalk', (45, 4, 20), (10, 60, 10)),
    ]

    def __init__(self):
        self.root = render.attachNewNode('bigCheeseWorks')
        self.outside = self.root.attachNewNode('outside')
        self.inside = self.root.attachNewNode('inside')
        self.kit = MapKit(self.root, STORAGE)

    def build(self):
        self.buildYard()
        self.buildFurnace()
        self.buildMainframe()
        self.buildSky()
        self.outside.setColorScale(SMOKE)
        self.inside.setColorScale(INSIDE)

    def destroy(self):
        self.kit.destroy()

    # A teleporter: a gear-plate pad, four posts, a beam of light and sparks.
    def teleporter(self, pos, size=1.0, parent=None):
        kit = self.kit
        parent = parent or self.inside
        pad = parent.attachNewNode('teleporter')
        pad.setPos(*pos)
        kit.model('phase_9/models/cogHQ/platform1', pos=(0, 0, 0), scale=(size, size, 1.2), parent=pad)
        kit.model('phase_9/models/cogHQ/FactoryGearB', pos=(0, 0, 0.9), scale=(4.2 * size, 4.2 * size, 1), parent=pad)
        for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            kit.model('phase_9/models/cogHQ/FactoryGearBpost', pos=(x * 4.6 * size, y * 4.6 * size, 0), scale=(1, 1, 0.5 * size), parent=pad)
        beam = kit.model('phase_9/models/cogHQ/alphaCone2', pos=(0, 0, 0.6), p=-90, scale=(0.45 * size, 0.6 * size, 0.45 * size), parent=pad)
        beam.setColorScale(0.6, 0.9, 1.0, 0.55)
        beam.setTransparency(TransparencyAttrib.MAlpha)
        beam.setDepthWrite(False)
        beam.setBin('fixed', 10)
        beam.setTwoSided(True)
        for h in (0, 120, 240):
            bolt = kit.model('phase_10/models/cogHQ/CBLightning', pos=(0, 0, 6 * size), h=h, scale=(2 * size, 1, 4 * size), parent=pad)
            bolt.setColorScale(0.7, 0.9, 1.0, 1)
            bolt.setBillboardAxis()
        return pad

    # The yard -------------------------------------------------------------
    def buildYard(self):
        kit = self.kit
        out = self.outside
        x0, y0, x1, y1 = YARD
        kit.rect(-400, -400, 400, 400, z=-0.1, tex='phase_9/maps/ground7.jpg', tile=30, parent=out, name='ground')
        kit.rect(x0, y0, x1, y1, z=0.0, tex=FLOOR, tile=16, parent=out, name='yardFloor')
        # A railway along the west side, with a boxcar on it.
        kit.rect(-46, y0, -34, -10, z=0.02, tex='phase_10/maps/Tracks.jpg', tile=12, parent=out, name='tracks')
        kit.model('phase_10/models/cogHQ/CashBotBoxCar', pos=(-40, -66, 0), h=90, scale=0.42, parent=out)
        # High factory walls round the yard; the factory itself is to the north.
        wall = [(0, 30, BRICK, 20, None), (30, 32, HAZARD, 4, None)]
        kit.wall((x0, y0), (x1, y0), wall, parent=out)
        kit.wall((x0, y0), (x0, y1), wall, parent=out)
        kit.wall((x1, y0), (x1, y1), wall, parent=out)
        front = [(0, 6, BLOCKS, 8, None), (6, 40, FACTORY_WALL, 12, None), (40, 42, HAZARD, 4, None)]
        kit.wall((x0, y1), (x1, y1), front, gaps=[(10, 20, 14), (65, 80, 18)], parent=out)
        # Hazard stripes round the doorways.
        kit.wallQuad((x0 + 9, y1 - 0.2), (x0 + 21, y1 - 0.2), 14, 15.2, tex=HAZARD, tile=4, parent=out)
        kit.wallQuad((x0 + 64, y1 - 0.2), (x0 + 81, y1 - 0.2), 18, 19.2, tex=HAZARD, tile=4, parent=out)
        # A big Cog door over the way to the mainframe.
        kit.model('phase_9/models/cogHQ/CogDoorHandShake', pos=(22.5, y1 - 1.3, 18), h=180, scale=0.6, parent=out)
        # The sign over it all.
        kit.text('BIG CHEESE WORKS', pos=(0, y1 - 0.5, 31), h=0, scale=5.0, color=(0.95, 0.85, 0.25, 1), font='suit', parent=out)
        kit.text('NEW COGS MADE DAILY', pos=(0, y1 - 0.5, 27), h=0, scale=2.2, color=(0.6, 0.1, 0.1, 1), font='suit', parent=out)
        # The giant: a statue of the Big Cheese on a block in the middle.
        kit.stone(kit.model('phase_9/models/cogHQ/cube_tenfoot', pos=(-7, -39, 0), scale=(1.4, 1.4, 0.6), parent=out))
        statue = kit.cogStatue('tbc', (0, -32, 6), 180)
        statue.reparentTo(out)
        statue.setScale(2.4)
        kit.stone(statue)
        # Machinery about the yard.
        kit.model('phase_10/models/cashbotHQ/crates_A', pos=(44, -10, 0), parent=out)
        kit.model('phase_10/models/cashbotHQ/crates_E', pos=(-26, -64, 0), h=30, parent=out)
        kit.model('phase_10/models/cashbotHQ/crates_G1', pos=(44, -30, 0), h=-90, parent=out)
        kit.model('phase_10/models/cashbotHQ/gears_B2', pos=(-24, -8, 0), parent=out)
        kit.model('phase_10/models/cashbotHQ/pipes_C', pos=(20, -66, 0), h=0, scale=0.6, parent=out)
        kit.model('phase_9/models/cogHQ/PaintMixer', pos=(-28, -30, 0), scale=0.7, parent=out)
        kit.model('phase_9/models/cogHQ/ttr_m_prp_gen_gagTank', pos=(30, -8, 0), scale=1.6, parent=out)
        kit.model('phase_9/models/cogHQ/ttr_m_prp_gen_gagTank', pos=(34, -8, 0), scale=1.6, parent=out)
        # Smokestacks and water towers over the walls.
        for pos in ((-75, -40), (78, -20), (-70, 70), (30, 110), (80, 60), (-20, 105)):
            kit.prop('prop_cog_smoke_stack', pos=(pos[0], pos[1], 0), scale=0.9, parent=out)
        kit.prop('prop_cog_water_tower', pos=(75, -60, 0), scale=1.4, parent=out)
        kit.prop('prop_cog_water_tower', pos=(-75, 20, 0), scale=1.2, parent=out)
        # A teleporter pad by the east wall.
        self.teleporter((38, -56, 0), size=0.8, parent=out)

    # The furnace room -------------------------------------------------------
    def buildFurnace(self):
        kit = self.kit
        inn = self.inside
        x0, y0, x1, y1 = FURNACE
        h = 30
        kit.rect(x0, y0, x1, y1, z=0.0, tex=PLATE, tile=10, parent=inn, name='furnaceFloor')
        ceil = kit.rect(x0, y0, x1, y1, z=h, tex=CEILING, tile=10, parent=inn)
        ceil.setTwoSided(True)
        layers = [(0, 8, RIVETS, 8, None), (8, h, CEMENT, 12, None)]
        kit.wall((x0, y0 + 0.2), (x1, y0 + 0.2), layers, gaps=[(10, 20, 14)], parent=inn)
        kit.wall((x0, y0), (x0, y1), layers, parent=inn)
        kit.wall((x0, y1), (x1, y1), layers, parent=inn)
        kit.wall((x1, y0), (x1, y1), layers, gaps=[(25, 37, 14)], parent=inn)
        # The furnaces: boilers in a row with a glowing pit in front.
        for i, x in enumerate((-44, -32, -20)):
            kit.model('phase_10/models/cashbotHQ/boiler_B1' if i % 2 else 'phase_10/models/cashbotHQ/boiler_A1',
                      pos=(x, 54, 0), h=180, parent=inn)
        pit = kit.rect(-48, 40, -14, 46, z=0.05, color=(1.0, 0.45, 0.1, 1), parent=inn, name='furnaceGlow')
        pit.setLightOff()
        kit.wallQuad((-48, 40), (-14, 40), 0, 1.2, tex=HAZARD, tile=4, parent=inn)
        # Pipes and gears.
        kit.model('phase_10/models/cashbotHQ/pipes_B', pos=(-48, 20, 0), h=90, parent=inn)
        kit.model('phase_10/models/cashbotHQ/gears_C1', pos=(-45, 32, 0), h=90, parent=inn)
        kit.model('phase_10/models/cashbotHQ/boiler_A2', pos=(-15, 52, 0), h=200, parent=inn)
        # The power switch: crane controls with a big lever.
        kit.model('phase_10/models/cogHQ/CBCraneControls', pos=(-46, 8, 0), h=-90, scale=1.6, parent=inn)
        lever = kit.model('phase_13/models/parties/partyLeverStick', pos=(-46.5, 11, 3), r=-25, scale=0.7, parent=inn)
        kit.text('POWER', pos=(-49.6, 10, 9), h=90, scale=2.0, color=(0.85, 0.75, 0.1, 1), font='suit', parent=inn)
        # A teleporter pad in the corner.
        self.teleporter((-20, 12, 0), size=0.7)

    # The mainframe hall -------------------------------------------------------
    def buildMainframe(self):
        kit = self.kit
        inn = self.inside
        x0, y0, x1, y1 = MAINFRAME
        h = 44
        kit.rect(x0, y0, x1, y1, z=0.0, tex=FLOOR, tile=12, parent=inn, name='mainFloor')
        ceil = kit.rect(x0, y0, x1, y1, z=h, tex=CEILING, tile=10, parent=inn)
        ceil.setTwoSided(True)
        layers = [(0, 10, RIVETS, 8, None), (10, 12, HAZARD, 4, None), (12, h, FACTORY_WALL, 12, None)]
        kit.wall((x0, y0 + 0.2), (x1, y0 + 0.2), layers, gaps=[(25, 40, 18)], parent=inn)
        kit.wall((x0 + 0.2, y0), (x0 + 0.2, y1), layers, gaps=[(25, 37, 14)], parent=inn)
        kit.wall((x0, y1), (x1, y1), layers, parent=inn)
        kit.wall((x1, y0), (x1, y1), layers, parent=inn)
        # The mainframe: a big teleporter on a raised round stage.
        cx, cy = 20, 42
        kit.disc(cx, cy, 16, z=1.0, tex=PLATE, tile=8, parent=inn, name='mainframeBase')
        kit.ring(cx, cy, 16, 16.01, z=0, parent=inn)
        base = kit.model('phase_10/models/cashbotHQ/MintGear', pos=(cx, cy, 0), scale=(16.5, 16.5, 3.4), parent=inn)
        self.teleporter((cx, cy, 1.0), size=1.4)
        # The mainframe itself: four big pipes holding up a gear canopy, with
        # the emitter hanging over the pad.
        for dx, dy in ((-11, -11), (11, -11), (11, 11), (-11, 11)):
            kit.model('phase_10/models/cashbotHQ/pipes_D4', pos=(cx + dx, cy + dy, 1), scale=(0.5, 0.5, 0.75), parent=inn)
        kit.model('phase_10/models/cashbotHQ/MintGear', pos=(cx, cy, 24), scale=(17, 17, 4), parent=inn)
        kit.model('phase_10/models/cogHQ/CBMagnet', pos=(cx, cy, 23.5), scale=3.0, parent=inn)
        kit.model('phase_10/models/cashbotHQ/gears_C2', pos=(cx, cy, 25), scale=0.8, parent=inn)
        # Consoles round the mainframe.
        for dx, dy, hh in ((-12, -12, 45), (12, -12, -45)):
            kit.model('phase_10/models/cogHQ/CBCraneControls', pos=(cx + dx, cy + dy, 1), h=hh + 180, scale=1.5, parent=inn)
        kit.model('phase_10/models/cogHQ/CashBotHQCshRegister', pos=(cx - 14, cy + 6, 1), h=100, scale=1.2, parent=inn) if False else None
        # Conveyor belts bringing parts in along the east wall.
        kit.model('phase_9/models/cogHQ/cube_tenfoot', pos=(42, 12, 0), scale=(0.6, 4.0, 0.45), parent=inn, color=(0.45, 0.42, 0.4, 1))
        kit.rect(42, 12, 48, 52, z=4.55, tex=ROLLUP, tile=6, parent=inn, name='belt')
        for y in (18, 26, 34, 42):
            kit.model('phase_10/models/cashbotHQ/CBMetalCrate', pos=(45, y, 4.6), scale=0.35, parent=inn)
        # Stompers hanging over the belt.
        for y in (22, 38):
            kit.model('phase_9/models/cogHQ/square_stomper', pos=(45, y, 16), p=90, scale=(3, 3, 3), parent=inn)
            kit.model('phase_10/models/cashbotHQ/MintGearPost', pos=(45, y, 18), scale=(1, 1, 3), parent=inn)
        # Catwalks round the walls with stairs up.
        cz = 16
        for x in range(-5, 50, 10):
            kit.model('phase_9/models/cogHQ/platform1', pos=(x, 65, cz), parent=inn)
        for y in range(5, 66, 10):
            kit.model('phase_9/models/cogHQ/platform1', pos=(-5, y, cz), parent=inn)
        kit.model('phase_9/models/cogHQ/StairTen3060', pos=(0, 10, 0), h=90, scale=(1, 1, 1.6), parent=inn)
        for x in range(-10, 51, 4):
            kit.model('phase_10/models/cashbotHQ/MintGearPost', pos=(x, 60, cz), scale=(0.25, 0.25, 0.12), parent=inn)
        # Gears on the walls.
        for pos in ((30, 69.5, 24), (6, 69.5, 30), (-9.5, 50, 26)):
            g = kit.model('phase_9/models/cogHQ/FactoryGearB', pos=pos, p=90, scale=(6, 6, 2), parent=inn)
        kit.model('phase_10/models/cashbotHQ/boiler_A2', pos=(44, 64, 0), h=200, parent=inn)
        kit.model('phase_10/models/cashbotHQ/crates_C1', pos=(-4, 4, 0), parent=inn)

    def buildSky(self):
        self.sky = self.kit.model('phase_9/models/cogHQ/cog_sky', parent=self.outside)
        self.sky.setBin('background', 100)
        self.sky.setDepthWrite(0)
        self.sky.setLightOff()
        fog = Fog('bigCheeseFog')
        fog.setColor(0.55, 0.53, 0.5)
        fog.setLinearRange(150, 700)
        self.outside.setFog(fog)
