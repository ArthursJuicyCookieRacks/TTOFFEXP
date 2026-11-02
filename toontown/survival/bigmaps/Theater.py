"""Kino der Toonen: an old Toontown picture theater the cogs took over.

Black Ops 1's Kino der Toten, laid out the way Arthur described it, built
from Toontown's own walls, floors and props. Feet; +y runs from the lobby
to the stage.

- The lobby (start): ground floor with the ticket counter, two stairs up
  to a balcony along the back, the teleporter's return pad in the middle.
- Indoor route (upstairs door): upper hall, the portrait room, the foyer
  (a gallery over a tiled lounge), the dressing room, onto the stage.
- Alley route (downstairs door): lower hall with the fire trap, the
  brick alley outside, the fenced stairs, the storage room up high, down
  onto the stage.
- The stage: the power, the teleporter, the big curtain that rises with
  the power over the auditorium, whose back passage leads to the lobby.
- The projection booth over the auditorium's back door, only by the
  teleporter, with Mickey's gag upgrade; and four rooms the teleporter
  sometimes drops a toon in on the way back.
"""

import math
import random

from direct.interval.IntervalGlobal import Func, LerpColorScaleInterval, LerpPosInterval, Sequence, Wait
from panda3d.core import Point3, TextNode, TransparencyAttrib, Vec3, Vec4

from toontown.survival import SurvivalGlobals as G
from toontown.survival.bigmaps.BigMap import BigMap
from toontown.survival.bigmaps.Building import *  # noqa: F401,F403 (the shared textures and colours)
from toontown.survival.bigmaps.Building import Building
from toontown.survival.previewmaps.MapKit import heading, rng


# Where the four rooms the teleporter can drop a toon in are: far below
# the theater, out of everyone's way.
ROOMS_Z = -200.0
ROOMS = (('bedroom', Point3(0, 400, ROOMS_Z)), ('ruined', Point3(60, 400, ROOMS_Z)),
         ('dentist', Point3(120, 400, ROOMS_Z)), ('meeting', Point3(180, 400, ROOMS_Z)))
BOOTH_PAD = Point3(-9, -51.5, 22)
LOBBY_PAD = Point3(0, -84, 0)
STAGE_PAD = Point3(0, 52, 4)


# Smaller gaps in the roof, just for the moonlight and the creepers (no
# cogs come through these): group -> [(rect, ceiling z, floor z, vines)].
CRACKS = {
    'lobby': [((10, -93, 14, -88.5), 30, 0, 3), ((-14, -71, -11.5, -67), 30, 14, 1), ((22, -75, 26, -72.5), 30, 14, 0),
              ((-24, -90, -22, -87.5), 30, 0, 2)],
    'upper': [((-53, -88, -50, -85.5), 26, 14, 2)],
    'portrait': [((-65, -61, -62, -58), 27, 14, 4), ((-84, -40, -82.5, -38.5), 27, 14, 0)],
    'foyer': [((-81, 0, -78, 4), 27, 0, 5), ((-62, -31, -60, -28.5), 27, 14, 1), ((-66, 4, -64, 6.5), 27, 0, 0)],
    'dressing': [((-84, 36, -81, 40), 15, 4, 2), ((-58, 18, -56.5, 19.5), 15, 4, 0)],
    'storage': [((82, 34.5, 85, 37), 24, 12, 1), ((58, 48, 61, 52), 24, 12, 4)],
    'stage': [((-40, 50, -35, 54), 36, 4, 3), ((6, 72, 9, 76), 36, 4, 0), ((36, 64, 38, 66.5), 36, 4, 5)],
    'aud': [((-36, 10, -32.5, 14), 31, 0, 4), ((32, -40, 36, -36), 31, 0, 0), ((-10, -46, -7, -43), 31, 0, 2),
            ((14, 26, 16, 28.5), 31, 0, 6), ((-18, -2, -16.5, 0), 31, 0, 1)],
    'lowerhall': [((60, -77, 62, -75), 11, 0, 1)],
}


class Theater(Building):
    KEY = 'theater'
    TITLE = 'Toon Theater'
    DESCRIPTION = 'An old picture theater the cogs turned into a laboratory.'
    PLAYER_START = (Point3(0, -94, 0), 0)
    MICKEY_SPOT = (Point3(10, -52, 22), 90)
    TRUNK_SPOT = (Point3(28, -62.5, 14), 0)
    FISHERMAN_SPOT = (Point3(0, -94, 0), 0)
    REACH_CENTER = Point3(0, -10, 0)
    REACH_SPAN = 110.0
    NAV_TOP = 60.0
    NAV_LOWEST = -5.0
    SPAWN_RING = (0.0, 300.0)
    NO_LANDING = ()
    NIGHT_SCALE = Vec4(0.95, 0.9, 0.86, 1)
    SKY_FILE = 'phase_3.5/models/props/BR_sky'
    SKY_COLOR = Vec4(0.16, 0.17, 0.26, 1)
    BACKGROUND = Vec4(0.03, 0.03, 0.05, 1)
    FOG = ((0.07, 0.06, 0.06), 0.0045)
    LIGHT = ((0.24, 0.21, 0.2), (0.26, 0.28, 0.38), (-25, -60, 0))
    CAMERA_FAR = 900.0

    # --- Building ---

    def ceiling(self, x0, y0, x1, y1, z, tex, tile=10.0, color=(1, 1, 1, 1), group='static', holes=()):
        extra = [c[0] for c in CRACKS.get(group, ()) if abs(c[1] - z) < 0.01]
        return Building.ceiling(self, x0, y0, x1, y1, z, tex, tile=tile, color=color, group=group, holes=list(holes) + extra)

    def dressCracks(self):
        seed = 600
        for group, cracks in CRACKS.items():
            for rect, cz, fz, vines in cracks:
                seed += 7
                self.roofHole(rect, cz, fz, group, seed, vines=vines)

    def build(self):
        self.rand = rng(1963)
        self.boothTime = 0.0
        self.lobby()
        self.upperHall()
        self.portraitRoom()
        self.foyer()
        self.dressingRoom()
        self.lowerHall()
        self.alley()
        self.storage()
        self.stage()
        self.auditorium()
        self.booth()
        self.returnRooms()
        self.outside()
        self.dressIndoor()
        self.dressBack()
        self.dress2Indoor()
        self.dress2Back()
        self.dressCracks()

    # --- The lobby ---

    def lobby(self):
        g = 'lobby'
        self.zone('lobby', 'the lobby', (-40, -100, -1, 40, -60, 32), startOpen=True)
        lower = (WAINSCOT, 4.0, PANEL)
        trim = (MOLDING, (0.75, 0.6, 0.45, 1))
        # Floor: worn red carpet with a wood border; coffered ceiling.
        self.floor(-40, -100, 40, -60, 0, PLANKS, tile=6, color=OLD_WOOD, group=g)
        self.kit.quad([(-34, -96, 0.03), (34, -96, 0.03), (34, -78, 0.03), (-34, -78, 0.03)], CARPET,
                      [(0, 0), (8, 0), (8, 2), (0, 2)], RED_CARPET, g)
        self.ceiling(-40, -100, 40, -60, 30, COFFER, tile=8, color=(0.7, 0.6, 0.55, 1), group=g, holes=[(-36, -71, -30, -65)])
        self.ceilingHole('lobby', Point3(-33, -68, 14), 16)
        # Walls: the street front, the doors out at either side, the
        # passage to the auditorium under the balcony.
        self.shell(-40, -100, 40, -60, 0, 30, WALLPAPER, ops={
            's': [(-28, 6, 2, 8), (28, 6, 2, 8)],
            'n': [(0, 10, 0, 10)],
            'w': [(-71, 6, 14, 23)],
            'e': [(-75, 6, 0, 9)],
        }, group=g, lower=lower, trim=trim, outside={'s': (BRICK, BRICK_C)})
        # The front doors (nailed shut) between the two windows.
        for x in (-4.2, 0.2):
            self.kit.box((x, -100.2, 0), (x + 4.0, -99.8, 10), side=DARK_PANEL, top=DARK_PANEL, tile=5, color=(0.7, 0.55, 0.45, 1),
                         collide=False, group=g)
        self.kit.beam((-5, -99.6, 10.4), (5, -99.6, 10.4), 0.6, MOLDING, color=(0.75, 0.6, 0.45, 1), tile=3, group=g)
        for z in (3.2, 6.5):
            self.kit.beam((-5, -99.5, z), (5, -99.5, z + 0.6), 0.45, BOARDS, color=GREY_WOOD, tile=3, group=g)
        self.window('lobby', (-28, -100, 0), 0)
        self.window('lobby', (28, -100, 0), 0)
        # The balcony along the back, its railing, and the two stairs up
        # the side walls (kept tight to the walls so the floor stays open)
        # onto a landing at each end of it.
        self.floor(-40, -76, 40, -60, 14, PLANKS, tile=6, color=OLD_WOOD, group=g, thick=1.0, under=COFFER)
        for x0, x1 in ((-40, -33), (33, 40)):
            self.floor(x0, -78, x1, -76, 14, PLANKS, tile=6, color=OLD_WOOD, group=g, thick=1.0, under=COFFER)
        self.kit.railing([(-33, -78), (-33, -76), (33, -76), (33, -78)], 14, texPath=MOLDING, color=(0.7, 0.55, 0.42, 1))
        for x in (-36.5, 36.5):
            self.kit.stairs((x, -94, 0), 0, 7, 14, run=16, steps=14, side=DARK_PANEL, tread=CARPET, color=(0.72, 0.52, 0.45, 1),
                            railTex=MOLDING)
        for x in (-32, -10, 10, 32):
            self.kit.cylinder((x, -76.5, 0), 0.9, 13.0, MARBLE, sides=12, color=(0.75, 0.68, 0.6, 1), tile=4, group=g)
        # The ticket counter (BO1's reception bar) on the west side.
        # It stands under the balcony, out of the way.
        self.kit.model('phase_3.5/models/modules/counter', pos=(-33, -68, 0), h=-90, scale=(1.0, 1.4, 1.6), color=(0.7, 0.55, 0.45, 1))
        self.kit.wallBox((-35.5, -75, 0), (-31.5, -61, 3.4))
        self.kit.model('phase_3.5/models/modules/lamp_short', pos=(-34, -63, 3.2), scale=0.8, color=(0.9, 0.8, 0.7, 1))
        self.kit.model('phase_11/models/lawbotHQ/LB_CardBoardBox', pos=(-37.5, -97.5, 0), h=20, scale=0.35)
        # The marquee sign over the doors, inside; broken seats and dust.
        self.text('TOON THEATER', (0, -99.4, 12.4), 180, 1.5, (0.95, 0.75, 0.4, 1), parent=self.root)
        # Outside, over the street: the marquee with the name on it.
        self.kit.model('phase_5/models/props/marquee', pos=(0, -100.9, 3.8), h=0, scale=1.0, color=(0.75, 0.62, 0.52, 1))
        self.text('TOON THEATER', (0, -106.0, 13.2), 0, 1.4, (1.0, 0.85, 0.5, 1), parent=self.root)
        self.text('NOW SHOWING: NOTHING', (0, -106.0, 11.7), 0, 0.8, (0.9, 0.3, 0.25, 1), parent=self.root)
        self.poster((-20, -99.4, 4.5), 0)
        self.poster((21, -99.4, 4.5), 0)
        self.poster((-15, -59.5, 18), 180)
        # The return pad in the middle of the floor.
        self.pad(LOBBY_PAD, 'lobby', glow=(0.6, 0.85, 1.0))
        self.teleporter('mainframe', LOBBY_PAD, 0, role='mainframe')
        # What the lobby sells.
        self.tonic('wind', (-12, -98.4, 0), 0, needsPower=False)
        self.wallGag((G.SOUND, 2), (14, -100, 0), 0, 500, 'lobby')     # Olympia: Bugle
        self.wallGag((G.THROW, 2), (-20, -60, 14), 180, 500, 'lobby')  # M14: Cream Pie Slice
        self.boxSpot('lobby balcony', (28, -62.5, 14), 0, start=True)
        # The lights: a chandelier glow in the middle, sconces round.
        self.lamp((0, -84, 22), AMBER, 55.0, groups=(g, 'static'))
        for p, hh in (((-39.5, -97, 7), -90), ((39.5, -97, 7), 90), ((-39.5, -66, 19), -90), ((39.5, -66, 19), 90)):
            self.sconce(p, hh, g, light=False)
        self.chandelier((0, -84, 29.5))

    def chandelier(self, top, scale=1.0):
        """A brass ring of lamps on a rod, swaying a little in the draught
        from the broken roof."""
        pivot = self.root.attachNewNode('chandelier')
        pivot.setPos(Point3(top))
        brass = (0.85, 0.7, 0.35, 1)
        self.boxNode(pivot, (-0.08, -0.08, -4 * scale), (0.08, 0.08, 0), METAL, color=(0.5, 0.45, 0.35, 1), tile=2)
        rz = -4.5 * scale
        rad = 2.6 * scale
        for i in range(12):
            a = 360.0 * i / 12
            seg = pivot.attachNewNode('ring')
            seg.setPos(0, 0, rz)
            seg.setH(a)
            half = rad * math.tan(math.pi / 12) + 0.05
            self.boxNode(seg, (rad - 0.18, -half, 0), (rad + 0.18, half, 0.5), MOLDING, color=brass, tile=2)
        for i in range(4):
            arm = pivot.attachNewNode('arm')
            arm.setPos(0, 0, rz + 0.2)
            arm.setH(45 * i)
            self.boxNode(arm, (-rad, -0.06, 0), (rad, 0.06, 0.12), METAL, color=brass, tile=2)
        for i in range(8):
            a = 2 * math.pi * i / 8
            self.kit.model('phase_11/models/lawbotHQ/LB_torch_lampA', parent=pivot,
                           pos=(math.cos(a) * rad, math.sin(a) * rad, rz + 0.5), scale=0.45, color=(1, 0.9, 0.75, 1))
        r = rng(int(top[0] * 7 + top[1] * 3))
        swing = 1.2 + r.random() * 0.8
        secs = 4.5 + r.random() * 1.5
        self.keepLooping(Sequence(LerpHprInterval(pivot, secs / 2, Vec3(0, swing, swing * 0.6), startHpr=Vec3(0, -swing, -swing * 0.6),
                                                  blendType='easeInOut'),
                                  LerpHprInterval(pivot, secs / 2, Vec3(0, -swing, -swing * 0.6), startHpr=Vec3(0, swing, swing * 0.6),
                                                  blendType='easeInOut')))

    # --- Indoor route: upper hall, portrait room, foyer, dressing room ---

    def upperHall(self):
        g = 'upper'
        z = 14
        self.zone('upper', 'the upper hall', (-72, -92, 13, -42, -68, 27))
        self.floor(-72, -92, -42, -68, z, PLANKS, tile=6, color=OLD_WOOD, group=g, thick=1.0)
        self.kit.quad([(-70, -84, z + 0.03), (-44, -84, z + 0.03), (-44, -76, z + 0.03), (-70, -76, z + 0.03)], CARPET,
                      [(0, 0), (4, 0), (4, 1), (0, 1)], RED_CARPET, g)
        self.ceiling(-72, -92, -42, -68, z + 12, CEILING, color=(0.6, 0.55, 0.5, 1), group=g)
        self.shell(-72, -92, -42, -68, z, 12, WALLPAPER, color=PAPER_DARK, ops={
            'e': [(-71, 6, 0, 9)],
            'n': [(-63, 6, 0, 9)],
            's': [(-57, 6, 2, 8)],
        }, group=g, lower=(WAINSCOT, 4.0, PANEL), trim=(MOLDING, (0.75, 0.6, 0.45, 1)), outside={'s': (BRICK, BRICK_C)})
        self.threshold(-42, -74, -40, -68, z)
        d = self.door('upstairs', 750, (-41, -74), (-41, -68), z, z + 9, ['upper', 'portrait'], title='the upstairs door')
        self.leaves(d)
        self.window('upper', (-57, -92, z), 0, hover=True)
        self.wallGag((G.SQUIRT, 0), (-50, -68, z), 180, 1000, 'upper')  # PM63: Squirting Flower
        self.boxSpot('upper hall', (-69.5, -78, z), 90)
        # The electric trap where the hall meets the portrait room.
        self.trap('upper', 'electric', (-66, -69, -60, -65), (-56, -68, z), 180, z=(z, z + 10),
                  line=(Point3(-66, -67, z), Point3(-60, -67, z)))
        self.lamp((-57, -80, z + 10), DIM_AMBER, 24.0, groups=(g,), flicker=True)
        self.sconce((-71.5, -80, z + 6), -90, g, light=False)
        self.kit.model('phase_3.5/models/modules/couch_2person', pos=(-66, -91, z), h=0, scale=0.9, color=(0.6, 0.45, 0.4, 1))
        self.kit.wallBox((-70, -92, z), (-62, -89, z + 3))
        self.poster((-42.6, -86, z + 4), 90)

    def portraitRoom(self):
        g = 'portrait'
        z = 14
        self.zone('portrait', 'the portrait room', (-86, -66, 13, -56, -36, 28))
        self.floor(-86, -66, -56, -36, z, PLANKS, tile=6, color=GREY_WOOD, group=g, thick=1.0)
        self.ceiling(-86, -66, -56, -36, z + 13, CEILING, color=(0.55, 0.5, 0.46, 1), group=g, holes=[(-80, -52, -74, -46)])
        self.ceilingHole('portrait', Point3(-77, -49, z), 13)
        self.shell(-86, -66, -56, -36, z, 13, WALLPAPER, color=(0.68, 0.55, 0.5, 1), ops={
            's': [(-63, 6, 0, 9)],
            'n': [(-66, 6, 0, 9)],
            'w': [(-50, 6, 2, 8)],
        }, group=g, lower=(DARK_PANEL, 4.0, PANEL), trim=(MOLDING, (0.7, 0.55, 0.42, 1)), outside={'w': (BRICK, BRICK_C)})
        self.threshold(-66, -68, -60, -66, z)
        self.window('portrait', (-86, -50, z), -90, hover=True)
        # The portraits: the cogs' own paintings, hung crooked and torn.
        # (Game models face their own -y.)
        for path, pos, hh, rr in (('tt_m_ara_crg_paintingMoverShaker', (-56.6, -51, z + 6.8), -90, 6),
                                  ('tt_m_ara_crg_paintingLegalEagle', (-76, -65.0, z + 6.8), 180, -9)):
            np = self.kit.model('phase_5/models/cogdominium/' + path, pos=pos, h=hh, r=rr, scale=0.36,
                                color=(0.78, 0.7, 0.64, 1))
            np.find('**/shadow').removeNode()
        self.kit.model('phase_5.5/models/estate/West_bisonPortrait', pos=(-85.6, -60, z + 7), h=90, r=12, scale=1.2,
                       color=(0.8, 0.7, 0.6, 1))
        self.tonic('tracks', (-57.4, -44, z), 90)                       # Mule Kick
        self.lamp((-71, -51, z + 10), DIM_AMBER, 22.0, groups=(g,), flicker=True)
        # Fallen plaster and a toppled bookcase.
        # One bookcase still stands against the wall, leaning; its twin has
        # fallen flat on its face.
        shelf = self.kit.model('phase_11/models/lawbotHQ/LB_bookshelfA', pos=(-79, -37.4, z), h=0, r=4, scale=0.7,
                               color=(0.62, 0.52, 0.46, 1))
        shelf.find('**/shadow').removeNode()
        self.kit.wallBox((-83.2, -38.4, z), (-74.8, -36, z + 4.6))
        fallen = self.kit.model('phase_11/models/lawbotHQ/LB_bookshelfA', pos=(-82, -47, z + 0.96), h=-80, p=-90, scale=0.7,
                                color=(0.55, 0.46, 0.4, 1))
        fallen.find('**/shadow').removeNode()
        self.kit.wallBox((-84, -51, z), (-80, -43, z + 1.2))
        r = rng(7)
        for i in range(8):
            x, y = r.uniform(-82, -60), r.uniform(-62, -40)
            self.kit.box((x, y, z), (x + r.uniform(0.6, 1.6), y + r.uniform(0.6, 1.6), z + r.uniform(0.2, 0.6)), side=PLASTER,
                         top=PLASTER, tile=2, color=(0.52, 0.47, 0.42, 1), collide=False, group=g)
        d = self.door('portrait', 1000, (-69, -35), (-63, -35), z, z + 9, ['foyer', 'dressing'], kind='junk', title='the junk')
        self.junk(d)

    def foyer(self):
        g = 'foyer'
        self.zone('foyer', 'the foyer', (-96, -34, -1, -56, 10, 28))
        # The gallery (upstairs) and the lounge below it.
        self.floor(-96, -34, -56, -18, 14, PLANKS, tile=6, color=OLD_WOOD, group=g, thick=1.0, under=COFFER)
        self.floor(-96, -18, -56, 10, 0, MARBLE, tile=8, color=(0.8, 0.74, 0.66, 1), group=g)
        self.ceiling(-96, -34, -56, 10, 27, COFFER, tile=8, color=(0.6, 0.52, 0.48, 1), group=g, holes=[(-74, -30, -68, -24)])
        self.ceilingHole('foyer', Point3(-71, -27, 14), 13)
        self.shell(-96, -34, -56, 10, 0, 27, WALLPAPER, color=PAPER, ops={
            's': [(-66, 6, 14, 23)],
            'w': [(-2, 6, 2, 8)],
            'n': [(-77, 6, 4, 13)],
        }, group=g, lower=(WAINSCOT, 4.0, PANEL), trim=(MOLDING, (0.75, 0.6, 0.45, 1)), outside={'w': (BRICK, BRICK_C)})
        self.threshold(-69, -36, -63, -34, 14)
        # Under the gallery: a panelled wall so nobody walks under it.
        self.wall((-96, -18), (-56, -18), 0, 13, DARK_PANEL, tile=4, color=PANEL, faces='left', group=g)
        self.kit.railing([(-96, -18), (-90, -18)], 14, texPath=MOLDING, color=(0.7, 0.55, 0.42, 1))
        self.kit.railing([(-82, -18), (-56, -18)], 14, texPath=MOLDING, color=(0.7, 0.55, 0.42, 1))
        # Stairs down from the gallery to the lounge along the west wall.
        self.kit.stairs((-86, 4, 0), 180, 8, 14, run=22, steps=14, side=WAINSCOT, tread=CARPET, color=(0.72, 0.52, 0.45, 1),
                        railTex=MOLDING)
        self.window('foyer', (-96, -2, 0), -90)
        self.wallGag((G.SOUND, 3), (-72, -34, 14), 0, 1500, 'foyer')   # Stakeout: Aoogah
        self.wallGag((G.THROW, 3), (-56, -6, 0), 90, 1000, 'foyer')    # MP40: Whole Fruit Pie
        self.tonic('seltzer', (-62, 8.6, 0), 180)                     # Speed Cola
        self.boxSpot('foyer', (-58.5, -13, 0), -90)
        # The lounge: tables (one with the pie cannon), the bar.
        for x, y in ((-74, -6), (-66, 2)):
            self.kit.model('phase_11/models/lawbotHQ/LB_endtableA', pos=(x, y, 0), scale=1.0, color=(0.65, 0.5, 0.42, 1))
            self.kit.wallTube((x, y, 0), 2.0, 2.4)
            for a in (0, 120, 240):
                cx = x + 3.3 * math.cos(math.radians(a))
                cy = y + 3.3 * math.sin(math.radians(a))
                self.kit.model('phase_5.5/models/estate/deskChair', pos=(cx, cy, 0), h=a + 90 + self.rand.uniform(-20, 20),
                               scale=0.9, color=(0.6, 0.45, 0.4, 1))
        self.turret((-74, -6, 2.4), 0, (-77.5, -17.4, 0), 0)
        self.kit.model('phase_3.5/models/modules/counter', pos=(-94, -16, 0), h=180, scale=(1.0, 1.3, 1.6), color=(0.55, 0.42, 0.36, 1))
        self.kit.wallBox((-96, -16.6, 0), (-81, -13.6, 3.3))
        self.lamp((-74, -4, 10), AMBER, 30.0, groups=(g,))
        self.lamp((-76, -26, 24), DIM_AMBER, 22.0, groups=(g,), flicker=True)
        self.chandelier((-74, -4, 26.5), 0.8)
        self.poster((-95.4, -26, 18), -90)

    def dressingRoom(self):
        g = 'dressing'
        z = 4
        self.zone('dressing', 'the dressing room', (-90, 12, -1, -52, 48, 16))
        self.floor(-90, 12, -52, 48, z, OLD_PLANKS, tile=6, color=OLD_WOOD, group=g)
        self.ceiling(-90, 12, -52, 48, z + 11, CEILING, color=(0.5, 0.46, 0.42, 1), group=g, holes=[(-72, 26, -64, 34)])
        self.ceilingHole('dressing', Point3(-68, 30, z), 11)
        self.shell(-90, 12, -52, 48, z, 11, PLASTER, color=(0.72, 0.62, 0.55, 1), ops={
            's': [(-77, 6, 0, 9)],
            'e': [(45, 6, 0, 9)],
            'w': [(22, 6, 2, 8)],
        }, group=g, lower=(DARK_PANEL, 3.5, PANEL), outside={'w': (BRICK, BRICK_C)})
        # Up from the lounge: four steps in the doorway.
        self.threshold(-80, 10, -74, 12, z)
        self.kit.stairs((-77, 4, 0), 0, 6, 4, run=6, steps=4, side=WOOD, tread=CARPET, color=(0.72, 0.52, 0.45, 1), rails=True)
        self.window('dressing', (-90, 22, z), -90, hover=True)
        # Mirrors, racks, partitions and a heap of costumes.
        for x in (-86, -78, -70):
            self.kit.model('phase_3.5/models/modules/coatrack', pos=(x, 45, z), scale=1.0, color=(0.7, 0.6, 0.5, 1))
        self.kit.wallBox((-89, 43, z), (-67, 47, z + 5))
        for y in (20, 34):
            self.kit.box((-89.5, y - 3, z), (-88.5, y + 3, z + 7), side=CEMENT, top=CEMENT, tile=4, color=(0.6, 0.6, 0.62, 1), collide='wall')
        self.kit.model('phase_3.5/models/modules/desk', pos=(-63, 13, z), h=180, scale=0.9, color=(0.7, 0.58, 0.5, 1))
        self.kit.wallBox((-67, 12, z), (-59, 15, z + 3))
        # The make-up mirrors along the south wall, ringed with bulbs, a
        # few of them dead, over a long dressing table.
        vanity = self.kit.visual.attachNewNode('vanity')
        self.boxNode(vanity, (-89.6, 12, z), (-81, 14.2, z + 2.8), WOOD, color=(0.55, 0.42, 0.34, 1), tile=3)
        self.kit.wallBox((-89.6, 12, z), (-81, 14.4, z + 2.8))
        bulbs = vanity.attachNewNode('bulbs')
        r = rng(41)
        for cx in (-87.4, -83.2):
            self.boxNode(vanity, (cx - 1.7, 12.02, z + 3.4), (cx + 1.7, 12.25, z + 7.4), WOOD, color=(0.35, 0.26, 0.2, 1), tile=2)
            glass = self.boxNode(vanity, (cx - 1.4, 12.26, z + 3.7), (cx + 1.4, 12.3, z + 7.1), MARBLE, color=(0.55, 0.62, 0.66, 1), tile=6)
            glass.setLightOff(1)
            for i in range(5):
                for bx, bz in ((cx - 1.55, z + 3.7 + i * 0.85), (cx + 1.55, z + 3.7 + i * 0.85)):
                    lit = r.random() > 0.25
                    b = self.boxNode(bulbs, (bx - 0.13, 12.25, bz - 0.13), (bx + 0.13, 12.5, bz + 0.13), CEMENT,
                                     color=(1.0, 0.92, 0.65, 1) if lit else (0.25, 0.23, 0.2, 1), tile=1)
                    if lit:
                        b.setLightOff(1)
        # Folding screens.
        for x, y, hh in ((-72, 22, 30), (-62, 40, -20)):
            self.kit.box((x - 3, y - 0.2, z), (x + 3, y + 0.2, z + 6), side=CURTAIN, top=WOOD, tile=4, color=(0.6, 0.38, 0.32, 1))
        self.mannequins(((-84, 30), (-82, 38), (-58, 30)), z)
        self.wallGag((G.SQUIRT, 2), (-90, 34, z), -90, 1000, 'dressing')  # MP5K: Squirt Gun
        self.boxSpot('dressing room', (-54.5, 22, z), -90)
        self.trap('dressing', 'electric', (-55, 42, -48, 48), (-52, 39, z), 90, z=(z, z + 10),
                  line=(Point3(-51, 42, z), Point3(-51, 48, z)))
        self.lamp((-71, 30, z + 9), DIM_AMBER, 24.0, groups=(g,), flicker=True)
        self.threshold(-52, 42, -50, 48, z)
        d = self.door('dressing', 1250, (-51, 42), (-51, 48), z, z + 9, ['stage'], title='the stage door')
        self.leaves(d)

    # --- Detail: dust, stains, papers, pictures; nothing in the way ---

    def painting(self, path, pos, hf, size=2.6, tilt=0.0, color=(0.8, 0.74, 0.68, 1)):
        """One of the game's framed pictures on a wall, facing hf."""
        f = heading(hf)
        self.kit.model('phase_5.5/models/estate/' + path, pos=Point3(*pos) + f * 0.1, h=hf - 180, r=tilt, scale=size,
                       color=color)

    def damp(self, pos, hf, w, hgt, group, color=(0.2, 0.15, 0.1, 0.35)):
        """A damp patch spreading on the wallpaper."""
        self.wallPic(pos, hf, w, hgt, SOFT_SPOT, group, color=color, off=0.04)

    def dust(self, top, floorZ, every=2.2, color=(0.8, 0.74, 0.66, 0.55)):
        """Plaster dust sifting down from a hole in the ceiling."""
        self.steam((top[0], top[1], top[2] - 0.5), every=every, size=3.2, rise=-(top[2] - 0.5 - floorZ - 1.0), color=color)

    def dressIndoor(self):
        dustC = (0.2, 0.16, 0.12, 0.4)
        # The lobby.
        g = 'lobby'
        self.scatterGrime(-39, -99, 39, -61, 0, g, 18, 201, color=dustC)
        self.papers(-36, -98, 36, -64, 0, g, 16, 202, color=(0.85, 0.8, 0.7, 1))
        self.kit.model('phase_5.5/models/estate/popcornCart', pos=(24, -64, 0), h=200, scale=1.0, color=(0.75, 0.68, 0.62, 1))
        self.kit.wallTube((24, -64, 0), 2.5, 5)
        r = rng(203)
        for i in range(30):
            a, d = r.uniform(0, 2 * math.pi), r.uniform(1.5, 5.0)
            self.floorPic((24 + math.cos(a) * d, -66 + math.sin(a) * d * 0.7), 0.45, 0.45, SOFT_GLOW, g,
                          color=(1.0, 0.95, 0.75, 1), z=0, lift=0.06 + 0.001 * (i % 5))
        self.kit.model('phase_3.5/models/modules/umbrella_stand', pos=(6.2, -98.6, 0), scale=1.0, color=(0.75, 0.7, 0.62, 1))
        self.kit.wallTube((6.2, -98.6, 0), 1.0, 3)
        self.kit.model('phase_3.5/models/modules/paper_trashcan', pos=(-17, -98.6, 0), r=0, scale=1.0, color=(0.75, 0.7, 0.62, 1))
        self.kit.wallTube((-17, -98.6, 0), 1.0, 2)
        self.painting('modernistMickey', (-5, -60, 18.2), 180, 2.8, tilt=-4)
        self.painting('degasHorseStar', (7, -60, 18.2), 180, 2.6, tilt=6)
        self.painting('cezanne_toon', (-39.9, -66, 18.5), -90, 2.6, tilt=3)
        for p, hf, w, hgt in (((-30, -99.9, 14), 0, 9, 12), ((30, -60, 20), 180, 8, 8), ((39.9, -88, 16), 90, 10, 10),
                              ((-39.9, -70, 4), -90, 6, 9)):
            self.damp(p, hf, w, hgt, g)
        self.dust((-33, -68, 30), 0)
        self.grime((0, -84), 6, g, color=(0.08, 0.06, 0.05, 0.5))
        # The upper hall.
        g = 'upper'
        z = 14
        self.scatterGrime(-71, -91, -43, -69, z, g, 8, 211, color=dustC)
        self.papers(-70, -90, -44, -70, z, g, 6, 212, color=(0.85, 0.8, 0.7, 1))
        self.painting('cezanne_toon', (-72, -86, z + 4.6), -90, 2.4, tilt=-5)
        self.painting('degasHorseStar', (-72, -74, z + 4.6), -90, 2.2, tilt=8)
        self.kit.model('phase_3.5/models/modules/lamp_tall', pos=(-44, -90, z), scale=1.0, color=(0.6, 0.55, 0.5, 1))
        self.kit.wallTube((-44, -90, z), 1.0, 6)
        self.kit.model('phase_3.5/models/modules/umbrella_stand', pos=(-70.5, -70, z), scale=1.0, color=(0.7, 0.65, 0.6, 1))
        self.kit.wallTube((-70.5, -70, z), 1.0, 3)
        self.damp((-50, -92, z + 6), 0, 8, 6, g)
        self.damp((-42, -80, z + 3), 90, 6, 9, g)
        # The portrait room.
        g = 'portrait'
        self.scatterGrime(-85, -65, -57, -37, z, g, 8, 221, color=dustC)
        self.papers(-84, -64, -58, -38, z, g, 14, 222, color=(0.8, 0.75, 0.65, 1))
        self.dust((-77, -49, z + 13), z)
        for p, hf, w, hgt in (((-70, -36, z + 6), 180, 10, 7), ((-56, -60, z + 2), 90, 7, 10)):
            self.damp(p, hf, w, hgt, g, color=(0.18, 0.13, 0.1, 0.45))
        self.kit.model('phase_3.5/models/modules/trophy_frame', pos=(-64, -42, z + 0.12), p=-90, h=30, scale=1.3, color=(0.7, 0.62, 0.5, 1))
        # The foyer: the gallery up top, the lounge below.
        g = 'foyer'
        self.scatterGrime(-95, -33, -57, -19, 14, g, 7, 231, color=dustC)
        self.scatterGrime(-95, -17, -57, 9, 0, g, 12, 232, color=(0.14, 0.11, 0.08, 0.4))
        self.papers(-94, -32, -58, -20, 14, g, 6, 233, color=(0.85, 0.8, 0.7, 1))
        self.papers(-92, -16, -58, 8, 0, g, 8, 234, color=(0.85, 0.8, 0.7, 1))
        self.kit.model('phase_3.5/models/modules/rug', pos=(-70, -2, 0.03), h=90, scale=1.1, color=(0.62, 0.45, 0.42, 1))
        self.painting('modernistMickey', (-90, -34, 18.6), 0, 2.6, tilt=4)
        self.painting('cezanne_toon', (-82, -34, 18.6), 0, 2.6, tilt=-3)
        self.painting('degasHorseStar', (-58, -34, 18.6), 0, 2.4, tilt=10)
        self.kit.model('phase_5.5/models/estate/RADIO_A', pos=(-90, -15, 3.3), h=180, scale=1.4, color=(0.6, 0.65, 0.55, 1))
        self.dust((-71, -27, 27), 14)
        self.damp((-96, -10, 8), -90, 9, 10, g)
        self.damp((-56, 4, 6), 90, 8, 8, g)
        # The dressing room.
        g = 'dressing'
        z = 4
        self.scatterGrime(-89, 13, -53, 47, z, g, 10, 241, color=dustC)
        self.papers(-88, 16, -56, 44, z, g, 8, 242, color=(0.85, 0.8, 0.7, 1))
        self.dust((-68, 30, z + 11), z)
        for i, (x, y, rot, c) in enumerate(((-76, 30, 20, (0.6, 0.2, 0.2, 1)), (-66, 18, 70, (0.3, 0.3, 0.55, 1)),
                                            (-60, 36, 130, (0.55, 0.5, 0.25, 1)))):
            # Costume cloth dropped on the floor.
            self.floorPic((x, y), 2.4, 1.6, CURTAIN, g, color=c, rot=rot, z=z, lift=0.06 + 0.01 * i,
                          uv=[(0, 0), (1.2, 0), (1.2, 0.8), (0, 0.8)])
        self.painting('degasHorseStar', (-52, 30, z + 4.4), 90, 2.2, tilt=-6)
        self.damp((-80, 48, z + 5), 180, 8, 6, g)

    # --- Second pass: the building's bones, light, life ---

    def shaft(self, top, floorZ, w=4.0, color=(1.0, 0.95, 0.85), alpha=0.13):
        """Pale daylight (or moonlight) falling through a hole in the roof:
        crossed soft cards, slowly breathing."""
        from panda3d.core import ColorBlendAttrib
        from toontown.survival.previewmaps.MapKit import Mesh
        node = self.root.attachNewNode('shaft')
        node.setPos(top[0], top[1], 0)
        a, b = top[2], floorZ
        # The moon is low in the sky: the light leans as it falls, and it
        # spreads wide by the time it reaches the floor.
        lean = Vec3(0.11, 0.07, 0) * (a - b)
        m = Mesh()
        for k in range(3):
            ang = math.pi * k / 3
            dx, dy = math.cos(ang) * w / 2, math.sin(ang) * w / 2
            pts = [Point3(-dx, -dy, a), Point3(dx, dy, a), Point3(dx * 2.9, dy * 2.9, b) + lean, Point3(-dx * 2.9, -dy * 2.9, b) + lean]
            m.quad(pts, [(0.1, 0.45), (0.9, 0.45), (0.9, 0.55), (0.1, 0.55)], Vec4(1, 1, 1, 1))
            m.quad([pts[1], pts[0], pts[3], pts[2]], [(0.9, 0.45), (0.1, 0.45), (0.1, 0.55), (0.9, 0.55)], Vec4(1, 1, 1, 1))
        np = node.attachNewNode(m.node('shaft'))
        np.setTexture(self.kit.tex(SOFT_GLOW), 1)
        node.setLightOff(1)
        node.setDepthWrite(False)
        node.setTwoSided(True)
        node.setBin('fixed', 5)
        node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        lo, hi = Vec4(color[0], color[1], color[2], alpha * 0.6), Vec4(color[0], color[1], color[2], alpha)
        node.setColorScale(hi)
        secs = 5.0 + (abs(top[0]) % 3)
        self.keepLooping(Sequence(LerpColorScaleInterval(node, secs, lo, startColorScale=hi, blendType='easeInOut'),
                                  LerpColorScaleInterval(node, secs, hi, startColorScale=lo, blendType='easeInOut')))
        # The pool of light where it lands, with a fainter wide spill round it.
        cx, cy = top[0] + lean[0], top[1] + lean[1]
        self.floorPic((cx, cy), w * 3.4, w * 3.0, SOFT_GLOW, 'static', color=(color[0], color[1], color[2], 0.24), z=floorZ, lift=0.07)
        self.floorPic((cx, cy), w * 6.5, w * 6.0, SOFT_GLOW, 'static', color=(color[0], color[1], color[2], 0.1), z=floorZ, lift=0.068)

    def vine(self, top, length, seed=1, count=None, rect=None):
        """Creepers hanging in through a hole and stirring in the draught.
        They hang from the hole's edges, some long, some short, a few
        creeping along the underside of the ceiling."""
        from panda3d.core import CardMaker
        r = rng(seed)
        tex = loader.loadTexture('phase_4/maps/swinging_vine.jpg', 'phase_4/maps/swinging_vine_a.rgb')
        if count is None:
            count = r.choice((1, 2, 2, 3, 4, 5))
        if rect is None:
            rect = (top[0] - 2.5, top[1] - 2.5, top[0] + 2.5, top[1] + 2.5)
        x0, y0, x1, y1 = rect

        def edgePoint(far=0.0):
            if far and r.random() < 0.55:
                # Rooted out on the ceiling, having crept from the hole.
                cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                ang = r.uniform(0, 2 * math.pi)
                d = max(x1 - x0, y1 - y0) / 2.0 + r.uniform(1.0, far)
                return cx + math.cos(ang) * d, cy + math.sin(ang) * d
            t = r.random()
            side = r.randrange(4)
            if side == 0:
                return x0 + (x1 - x0) * t, y0 + 0.2
            if side == 1:
                return x0 + (x1 - x0) * t, y1 - 0.2
            if side == 2:
                return x0 + 0.2, y0 + (y1 - y0) * t
            return x1 - 0.2, y0 + (y1 - y0) * t

        roots = []
        for k in range(count):
            x, y = edgePoint(far=6.0)
            roots.append((x, y))
            piv = self.root.attachNewNode('vine')
            piv.setPos(x, y, top[2] + 0.4)
            h0 = r.uniform(0, 180)
            piv.setH(h0)
            ln = length * r.uniform(0.3, 1.1)
            wd = r.uniform(0.5, 1.3)
            shade = r.uniform(0.75, 1.15)
            # A hanging strand, sometimes doubled (two cards crossed).
            for cross in ((0,) if r.random() < 0.6 else (0, 90)):
                cm = CardMaker('v')
                cm.setFrame(-wd / 2, wd / 2, -ln, 0)
                cm.setUvRange((0, 0), (1, ln / (2.0 + wd)))
                c = piv.attachNewNode(cm.generate())
                c.setH(cross)
                c.setTexture(tex, 1)
                c.setTransparency(TransparencyAttrib.MAlpha)
                c.setTwoSided(True)
                c.setColorScale(0.5 * shade, 0.64 * shade, 0.36 * shade, 1)
            sw, secs = r.uniform(2, 7), r.uniform(3.0, 6.5)
            seq = Sequence(LerpHprInterval(piv, secs / 2, Vec3(h0, 0, sw), startHpr=Vec3(h0, 0, -sw), blendType='easeInOut'),
                           LerpHprInterval(piv, secs / 2, Vec3(h0, 0, -sw), startHpr=Vec3(h0, 0, sw), blendType='easeInOut'))
            self.keepLooping(seq)
        # Some of it creeps along the ceiling from the hole.
        for k in range(r.randrange(1, count + 3) if count else 0):
            x, y = edgePoint()
            ang = math.atan2(y - (y0 + y1) / 2, x - (x0 + x1) / 2) + r.uniform(-0.7, 0.7)
            ln = r.uniform(3.0, 9.0)
            cm = CardMaker('vc')
            cm.setFrame(-0.45, 0.45, 0, ln)
            cm.setUvRange((0, 0), (1, ln / 3.0))
            c = self.root.attachNewNode(cm.generate())
            c.setPos(x, y, top[2] - 0.08)
            c.setHpr(math.degrees(ang) - 90, -90, 0)
            c.setTexture(tex, 1)
            c.setTransparency(TransparencyAttrib.MAlpha)
            c.setTwoSided(True)
            c.setColorScale(0.45, 0.58, 0.33, 1)

    def jagged(self, rect, z, group, seed):
        """Broken laths and plaster hanging down round a hole's edges."""
        r = rng(seed)
        x0, y0, x1, y1 = rect
        for k in range(r.randrange(3, 7)):
            side = r.randrange(4)
            t = r.random()
            if side < 2:
                p, out = Point3(x0 + (x1 - x0) * t, y0 if side == 0 else y1, z), Vec3(0, -1 if side == 0 else 1, 0)
            else:
                p, out = Point3(x0 if side == 2 else x1, y0 + (y1 - y0) * t, z), Vec3(-1 if side == 2 else 1, 0, 0)
            ln = r.uniform(0.8, 2.6)
            drop = Vec3(0, 0, -ln * r.uniform(0.5, 0.95))
            tip = p + drop - out * r.uniform(0.2, 1.0)
            self.kit.beam(p + Vec3(0, 0, -0.05), tip, r.uniform(0.25, 0.5), r.choice((OLD_PLANKS, BOARDS, PLASTER)),
                          color=(0.45, 0.38, 0.32, 1), tile=1, group=group, depth=0.1)

    def roofHole(self, rect, ceilZ, floorZ, group, seed, vines=None, vineLen=None, color=(0.85, 0.9, 1.0)):
        """A smaller gap in the roof (no cogs come through it): moonlight,
        a few broken laths, perhaps vines, plaster fallen below."""
        x0, y0, x1, y1 = rect
        c = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        w = min(x1 - x0, y1 - y0)
        self.shaft((c[0], c[1], ceilZ), floorZ, w=w * 0.85, color=color, alpha=0.08 + 0.015 * w)
        self.jagged(rect, ceilZ, group, seed)
        if vines != 0:
            self.vine((c[0], c[1], ceilZ), vineLen or (ceilZ - floorZ) * 0.45, seed=seed, count=vines, rect=rect)
        self.rubble(c, floorZ, group, seed + 1, spread=max(1.2, w * 0.5), n=int(3 + w))

    def rubble(self, c, z, group, seed, spread=3.5, n=9):
        """Chunks of fallen plaster under a hole, low enough to walk over."""
        r = rng(seed)
        for i in range(n):
            x, y = c[0] + r.uniform(-spread, spread), c[1] + r.uniform(-spread, spread)
            w = r.uniform(0.3, 1.1)
            self.kit.box((x, y, z), (x + w, y + r.uniform(0.3, 1.1), z + r.uniform(0.12, 0.35)), side=PLASTER, top=PLASTER, tile=1,
                         color=(0.62, 0.56, 0.5, 1), collide=False, group=group)
        self.floorPic(c, spread * 2.6, spread * 2.6, SOFT_GLOW, group, color=(0.75, 0.7, 0.62, 0.35), z=z, lift=0.05)

    def pilaster(self, c, h, z0, z1, group, color=(0.72, 0.62, 0.52, 1), width=1.6):
        """A flat column against the wall with a base and a capital."""
        f = heading(h)
        side = Vec3(-f[1], f[0], 0)
        p = Point3(c[0], c[1], 0)
        for d, wd, za, zb, tex in ((0.35, width, z0, z1, MARBLE), (0.55, width + 0.6, z0, z0 + 1.0, MOLDING),
                                   (0.55, width + 0.6, z1 - 0.9, z1, MOLDING)):
            lo = p - side * (wd / 2)
            hi = p + side * (wd / 2) + f * d
            self.kit.box((min(lo[0], hi[0]), min(lo[1], hi[1]), za), (max(lo[0], hi[0]), max(lo[1], hi[1]), zb), side=tex, top=tex,
                         tile=2, color=color, collide=('wall' if tex == MARBLE else False), group=group)

    def crown(self, x0, y0, x1, y1, z, group, color=(0.72, 0.58, 0.44, 1)):
        """Moulding round the top of a room's walls."""
        for a, b in (((x0, y0 + 0.3), (x1, y0 + 0.3)), ((x0, y1 - 0.3), (x1, y1 - 0.3)), ((x0 + 0.3, y0), (x0 + 0.3, y1)),
                     ((x1 - 0.3, y0), (x1 - 0.3, y1))):
            self.kit.beam((a[0], a[1], z), (b[0], b[1], z), 0.6, MOLDING, color=color, tile=6, group=group, depth=0.7)

    def torn(self, pos, hf, w, hgt, group, seed):
        """Wallpaper peeled away, the plaster (and a lath or two) behind."""
        self.wallPic(pos, hf, w, hgt, PLASTER, group, color=(0.5, 0.44, 0.38, 1), off=0.045,
                     uv=[(0, 0), (w / 4.0, 0), (w / 4.0, hgt / 4.0), (0, hgt / 4.0)])
        self.wallPic(pos, hf, w * 1.25, hgt * 1.25, SOFT_SPOT, group, color=(0.15, 0.1, 0.08, 0.3), off=0.04)
        r = rng(seed)
        f = heading(hf)
        side = Vec3(-f[1], f[0], 0)
        for k in range(2):
            zz = pos[2] + r.uniform(-hgt / 4, hgt / 4)
            q = Point3(pos[0], pos[1], zz) + f * 0.08
            self.kit.beam(q - side * (w * 0.4), q + side * (w * 0.4), 0.3, BOARDS, color=(0.5, 0.4, 0.32, 1), tile=1, group=group,
                          depth=0.08)

    def boards(self, pos, hf, w, hgt, group, seed):
        """Planks nailed crooked over a hole in the wall."""
        r = rng(seed)
        f = heading(hf)
        side = Vec3(-f[1], f[0], 0)
        self.wallPic(pos, hf, w * 0.9, hgt * 0.9, SOFT_SPOT, group, color=(0.02, 0.02, 0.02, 0.85), off=0.04)
        for k in range(3):
            zz = pos[2] - hgt / 2 + hgt * (k + 0.5) / 3 + r.uniform(-0.3, 0.3)
            tilt = r.uniform(-0.5, 0.5)
            q = Point3(pos[0], pos[1], zz) + f * 0.12
            self.kit.beam(q - side * (w * 0.6) + Vec3(0, 0, -tilt), q + side * (w * 0.6) + Vec3(0, 0, tilt), 0.7, BOARDS,
                          color=(0.55, 0.45, 0.36, 1), tile=1, group=group, depth=0.12)

    def dress2Indoor(self):
        # The lobby: columns, a cornice, light through the broken roof,
        # vines hanging in, the paper torn off the walls.
        g = 'lobby'
        for x in (-23, -9, 9, 23):
            self.pilaster((x, -100), 0, 0, 29.4, g)
        for x in (-30, 15, 30):
            self.pilaster((x, -60), 180, 14, 29.4, g)
        self.crown(-40, -100, 40, -60, 29.0, g)
        self.kit.beam((-40, -99.5, 13.6), (40, -99.5, 13.6), 0.5, MOLDING, color=(0.72, 0.58, 0.44, 1), tile=12, group=g, depth=0.5)
        self.shaft((-33, -68, 30), 14, w=4.5)
        self.vine((-33, -68, 30), 10, seed=1, count=4, rect=(-36, -71, -30, -65))
        self.jagged((-36, -71, -30, -65), 30, g, 501)
        self.rubble((-33, -68), 14, g, 401)
        for p, hf, w, hgt, sd in (((-16, -99.9, 20), 0, 5, 4, 1), ((34, -99.9, 22), 0, 4, 6, 2), ((-39.9, -84, 22), -90, 6, 5, 3),
                                  ((39.9, -70, 8), 90, 4, 4, 4)):
            self.torn(p, hf, w, hgt, g, sd)
        self.boards((16, -99.85, 21), 0, 4, 3.5, g, 5)
        for p, hh in (((-9, -99.4, 18), 0), ((9, -99.4, 18), 0)):
            self.sconce(p, hh, g, light=False)
        # The upper hall.
        g = 'upper'
        z = 14
        self.crown(-72, -92, -42, -68, z + 11.4, g)
        for x in (-66, -48):
            self.pilaster((x, -92), 0, z, z + 11.6, g, width=1.2)
        self.torn((-60, -68, z + 7), 180, 4, 4, g, 11)
        self.boards((-72, -78, z + 7), -90, 3.5, 3, g, 12)
        self.sconce((-42.6, -78, z + 6), 90, g, light=False)
        # The portrait room.
        g = 'portrait'
        self.crown(-86, -66, -56, -36, z + 12.4, g)
        self.shaft((-77, -49, z + 13), z, w=3.6)
        self.vine((-77, -49, z + 13), 8, seed=2, count=2, rect=(-80, -52, -74, -46))
        self.jagged((-80, -52, -74, -46), z + 13, g, 502)
        self.rubble((-77, -49), z, g, 402)
        self.torn((-66, -66, z + 6), 0, 5, 5, g, 13)
        self.torn((-86, -42, z + 8), -90, 4, 5, g, 14)
        # The foyer.
        g = 'foyer'
        self.crown(-96, -34, -56, 10, 26.4, g)
        for x in (-90, -68):
            self.pilaster((x, 10), 180, 0, 26.4, g)
        for y in (-28, -22):
            self.pilaster((-56, y), 90, 14, 26.4, g, width=1.2)
        self.shaft((-71, -27, 27), 14, w=3.6)
        self.vine((-71, -27, 27), 10, seed=3, count=6, rect=(-74, -30, -68, -24))
        self.jagged((-74, -30, -68, -24), 27, g, 503)
        self.rubble((-71, -27), 14, g, 403)
        self.torn((-96, -26, 22), -90, 4, 4, g, 15)
        self.boards((-56, -10, 9), 90, 3, 3, g, 16)
        for p, hh in (((-95.4, 4, 7), -90), ((-56.6, 6, 7), 90)):
            self.sconce(p, hh, g, light=False)
        # The dressing room.
        g = 'dressing'
        z = 4
        self.shaft((-68, 30, z + 11), z, w=4.0, color=(0.9, 0.95, 1.0))
        self.vine((-68, 30, z + 11), 5, seed=4, count=1, rect=(-72, 26, -64, 34))
        self.jagged((-72, 26, -64, 34), z + 11, g, 504)
        self.rubble((-68, 30), z, g, 404)
        self.torn((-52, 20, z + 6), 90, 4, 3.5, g, 17)
        self.boards((-74, 48, z + 6), 180, 3, 3, g, 18)

    def streetWindow(self, pos, hf, w, hgt, lit=False, seed=1):
        """A window in a neighbouring building: a frame, a sill, glass,
        dark or with someone's lamp on behind it."""
        f = heading(hf)
        side = Vec3(-f[1], f[0], 0)
        node = self.root.attachNewNode('streetWindow')
        c = Point3(*pos) + f * 0.05
        lo, hi = c - side * (w / 2), c + side * (w / 2) + f * 0.06
        glass = self.boxNode(node, (min(lo[0], hi[0]), min(lo[1], hi[1]), pos[2]), (max(lo[0], hi[0]), max(lo[1], hi[1]), pos[2] + hgt),
                             CEMENT, color=(1, 1, 1, 1), tile=1)
        glass.setLightOff(1)
        r = rng(seed)
        if lit:
            glass.setColorScale(1.1, 0.82, 0.45, 1)
        else:
            glass.setColorScale(0.06, 0.07, 0.1, 1)
        frame = (0.32, 0.26, 0.22, 1)
        q = Point3(*pos) + f * 0.15
        for a, b in (((-w / 2 - 0.2, 0), (w / 2 + 0.2, 0)), ((-w / 2 - 0.2, hgt), (w / 2 + 0.2, hgt)), ((0, 0), (0, hgt)),
                     ((-w / 2, 0), (-w / 2, hgt)), ((w / 2, 0), (w / 2, hgt)), ((-w / 2, hgt / 2), (w / 2, hgt / 2))):
            self.kit.beam(q + side * a[0] + Vec3(0, 0, a[1]), q + side * b[0] + Vec3(0, 0, b[1]), 0.22, WOOD, color=frame, tile=1,
                          group='static', depth=0.2)
        self.kit.beam(q + side * (-w / 2 - 0.4) + f * 0.2 + Vec3(0, 0, -0.2), q + side * (w / 2 + 0.4) + f * 0.2 + Vec3(0, 0, -0.2),
                      0.3, CEMENT, color=(0.5, 0.48, 0.46, 1), tile=1, group='static', depth=0.6)
        if lit and r.random() < 0.5:
            # Somebody walks past the lamp now and then.
            dim = Vec4(0.5, 0.36, 0.2, 1)
            self.keepLooping(Sequence(Wait(r.uniform(4, 9)), LerpColorScaleInterval(glass, 0.4, dim), Wait(r.uniform(0.6, 1.4)),
                                      LerpColorScaleInterval(glass, 0.5, Vec4(1.1, 0.82, 0.45, 1))))
        return node

    def fireEscape(self, x, hf, y0, y1, levels, group):
        """An iron fire escape up a wall: landings with railings and a
        ladder between them, the bottom ladder pulled up out of reach."""
        f = heading(hf)
        iron = (0.2, 0.19, 0.19, 1)
        xa, xb = (x, x + f[0] * 3.2)
        lo, hi = min(xa, xb), max(xa, xb)
        for z in levels:
            self.kit.box((lo, y0, z - 0.25), (hi, y1, z), side=METAL, top=GRATE, tile=2, color=iron, collide=False, group=group)
            for yy in (y0, y1):
                self.kit.beam((xb, yy, z), (xb, yy, z + 3.2), 0.12, METAL, color=iron, tile=1, group=group)
                self.kit.beam((xa, yy, z + 3.2), (xb, yy, z + 3.2), 0.12, METAL, color=iron, tile=1, group=group)
            self.kit.beam((xb, y0, z + 3.2), (xb, y1, z + 3.2), 0.12, METAL, color=iron, tile=2, group=group)
            self.kit.beam((xb, y0, z + 1.6), (xb, y1, z + 1.6), 0.08, METAL, color=iron, tile=2, group=group)
            for t in range(int(y1 - y0) + 1):
                self.kit.beam((xb, y0 + t, z), (xb, y0 + t, z + 3.2), 0.05, METAL, color=iron, tile=1, group=group)
            # Brackets under the landing.
            for yy in (y0 + 0.5, y1 - 0.5):
                self.kit.beam((xa, yy, z - 2.4), (xb, yy, z - 0.3), 0.12, METAL, color=iron, tile=1, group=group)
        for k, z in enumerate(levels):
            top = levels[k + 1] if k + 1 < len(levels) else None
            yy = y0 + 1.2 if k % 2 == 0 else y1 - 1.2
            if top is not None:
                self.ladder((x + f[0] * 2.4, yy), hf, z, top, group, color=iron)
        self.ladder((x + f[0] * 2.4, (y0 + y1) / 2), hf, levels[0] - 4.5, levels[0], group, color=iron)

    def neon(self, label, pos, h, scale, color, group):
        """A neon sign on a bracket, buzzing and stuttering."""
        f = heading(h)
        plate = self.root.attachNewNode('neonPlate')
        np = self.text(label, Point3(*pos) + f * 0.25, h + 180, scale, (1, 1, 1, 1), parent=self.root)
        np.setLightOff(1)
        lit = Vec4(color[0] * 2.2, color[1] * 2.2, color[2] * 2.2, 1)
        dim = Vec4(color[0] * 0.35, color[1] * 0.35, color[2] * 0.35, 1)
        np.setColorScale(lit)
        self.keepLooping(Sequence(Wait(3.1), Func(np.setColorScale, dim), Wait(0.07), Func(np.setColorScale, lit), Wait(0.12),
                                  Func(np.setColorScale, dim), Wait(0.3), Func(np.setColorScale, lit), Wait(5.5)))
        w = len(label) * scale * 0.7 + 1.0
        self.wallPic((pos[0], pos[1], pos[2] - 0.6), h, w, scale + 1.2, CEMENT, group, color=(0.12, 0.1, 0.1, 1), off=0.08)
        self.floorPic((pos[0] + f[0] * 2, pos[1] + f[1] * 2), w * 1.2, 5, SOFT_GLOW, group,
                      color=(color[0], color[1], color[2], 0.18), z=0, lift=0.07)

    def dress2Back(self):
        # The lower hall: a bare bulb, torn plaster, boarded patch, pipes.
        g = 'lowerhall'
        self.tubeLight((62, -80, 10.6), 0, g, length=4.0, flicker=True)
        self.torn((42, -86, 6), -90, 4, 3.5, g, 21)
        self.boards((70, -76, 6), 90, 3, 3, g, 22)
        for x in (44.6, 69.4):
            self.kit.beam((x, -91.4, 0), (x, -91.4, 10.1), 0.4, RUST, color=(0.5, 0.44, 0.4, 1), tile=3, group=g)
        # The alley: a fire escape up each building, windows (a few
        # lit), drainpipes, power lines across, a neon sign.
        g = 'alley'
        self.fireEscape(92.5, 90, -22, -10, (8, 14.5), g)
        self.fireEscape(55.5, -90, -64, -54, (9, 15.5), g)
        r = rng(271)
        # (The brick walls' faces are half a foot in from their lines.)
        for x, hf in ((56.0, -90), (92.0, 90)):
            for y in (-66, -46, -36, -26, -6, 4):
                for z in (7.5, 14):
                    if (hf == 90 and -23 < y < -9) or (hf == -90 and -65 < y < -53):
                        continue
                    if hf == -90 and y in (-46, -36) and z < 10:
                        continue                                 # the posters are there
                    if r.random() < 0.8:
                        self.streetWindow((x, y, z), hf, 3.0, 3.6, lit=r.random() < 0.25, seed=int(y * 7 + z))
        for x, y, hf in ((56.0, -16, -90), (92.0, -40, 90), (92.0, 6, 90)):
            self.kit.beam((x + heading(hf)[0] * 0.4, y, 0), (x + heading(hf)[0] * 0.4, y, 20), 0.45, METAL,
                          color=(0.38, 0.38, 0.4, 1), tile=4, group=g)
        for y0, y1, z in ((-56, -60, 18), (-4, 2, 17.5)):
            self.kit.beam((56, y0, z), (92, y1, z - 0.5), 0.06, METAL, color=(0.1, 0.1, 0.1, 1), tile=1, group=g)
        # The storage room: rafters, daylight through the roof, vines.
        g = 'storage'
        self.ceilingBeams(52, 30, 92, 56, 24, g, every=6, axis='y', depth=0.9, color=(0.4, 0.32, 0.26, 1), tex=OLD_PLANKS)
        self.shaft((73, 43, 24), 12, w=3.6, color=(0.85, 0.9, 1.0))
        self.vine((73, 43, 24), 8, seed=5, count=3, rect=(70, 40, 76, 46))
        self.jagged((70, 40, 76, 46), 24, g, 505)
        self.rubble((73, 43), 12, g, 405, spread=2.5, n=6)
        self.boards((52, 36, 18), -90, 3, 3, g, 23)
        # The stage: the fly gallery's beams, light through the roof,
        # hanging vines, a ladder up the wall, sandbags overhead.
        g = 'stage'
        z = 4
        self.ceilingBeams(-50, 41, 50, 80, 35.2, g, every=8, axis='x', depth=1.0, color=(0.32, 0.28, 0.25, 1), tex=OLD_PLANKS)
        for c in ((-21, 69), (23, 59)):
            self.shaft((c[0], c[1], 36), z, w=4.0, color=(0.85, 0.9, 1.0))
            self.vine((c[0], c[1], 36), 14 if c[0] < 0 else 9, seed=int(c[0]) + 50, count=6 if c[0] < 0 else 2,
                      rect=(c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3))
            self.jagged((c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3), 36, g, int(c[0]) + 506)
        self.ladder((49.6, 60), 90, z, 34, g)
        for x, length in ((-30, 6), (-10, 9), (12, 5), (32, 8)):
            self.kit.beam((x, 72, 35), (x, 72, 35 - length), 0.1, WOOD, color=(0.75, 0.68, 0.55, 1), tile=1, group=g)
            self.kit.model('phase_5/models/props/sandbag-mod', pos=(x, 72, 35 - length - 1.4), h=x * 7, scale=1.0,
                           color=(0.72, 0.64, 0.54, 1))
        self.torn((-50, 52, 14), -90, 6, 5, g, 24)
        # The auditorium: daylight down through the three holes, vines,
        # the cornice, the wallpaper hanging off between the pilasters.
        g = 'aud'
        for c in ((-27, -21), (27, 9), (0, 22)):
            self.shaft((c[0], c[1], 31), 0, w=4.5, color=(0.85, 0.9, 1.0), alpha=0.12)
            self.vine((c[0], c[1], 31), {-27: 13, 27: 7, 0: 16}[c[0]], seed=int(c[0] * 3 + c[1]) + 90,
                      count={-27: 5, 27: 1, 0: 7}[c[0]], rect=(c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3))
            self.jagged((c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3), 31, g, int(c[0]) + 507)
        self.crown(-44, -56, 44, 39, 30.4, g)
        for p, hf, w, hgt, sd in (((-43.9, -17, 20), -90, 6, 6, 31), ((43.9, 19, 21), 90, 6, 5, 32), ((-43.9, 1, 9), -90, 4, 3.5, 33),
                                  ((43.9, -35, 18), 90, 5, 6, 34), ((-30, -56, 18), 0, 6, 5, 35)):
            self.torn(p, hf, w, hgt, g, sd)
        self.boards((43.9, 1, 16), 90, 4, 3.5, g, 36)
        self.boards((30, -56, 14), 0, 4, 3.5, g, 37)
        # The booth: a shelf of film cans, a poster, the old schedule.
        g = 'booth'
        z = 22
        self.torn((-16, -51, z + 5), -90, 3, 2.5, g, 38)
        self.sign((-10, -55.9, z + 5.2), 0, 'SHOWTIMES\n7:00  9:00\nMIDNIGHT', g, plate=(0.85, 0.82, 0.75, 1), scale=0.45)

    def projectorLight(self):
        """The projector's beam from the booth's middle window over the
        seats to the curtain: two crossed soft cards, shown with the power."""
        from panda3d.core import ColorBlendAttrib
        from toontown.survival.previewmaps.MapKit import Mesh
        node = self.root.attachNewNode('projectorBeam')
        a, b = Point3(0, -47.2, 25.5), Point3(0, 40.5, 15)
        m = Mesh()
        for w0, w1, d in ((0.5, 22.0, 'h'), (0.5, 14.0, 'v')):
            if d == 'h':
                pts = [a + Vec3(-w0, 0, 0), a + Vec3(w0, 0, 0), b + Vec3(w1, 0, 0), b + Vec3(-w1, 0, 0)]
            else:
                pts = [a + Vec3(0, 0, -w0), a + Vec3(0, 0, w0), b + Vec3(0, 0, w1), b + Vec3(0, 0, -w1)]
            uvs = [(0.45, 0.0), (0.55, 0.0), (1.0, 1.0), (0.0, 1.0)]
            m.quad(pts, uvs, Vec4(1, 1, 1, 1))
            m.quad([pts[1], pts[0], pts[3], pts[2]], uvs, Vec4(1, 1, 1, 1))
        np = node.attachNewNode(m.node('beam'))
        np.setTexture(self.kit.tex(SOFT_GLOW), 1)
        node.setLightOff(1)
        node.setDepthWrite(False)
        node.setTwoSided(True)
        node.setBin('fixed', 6)
        node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        node.setColorScale(1, 0.95, 0.85, 0.18)
        node.stash()
        self.projectorBeam = node

    def dressBack(self):
        dustC = (0.2, 0.16, 0.12, 0.4)
        wet = (0.18, 0.22, 0.3, 0.55)
        # The lower hall: puddles, a leaking pipe, the fuse box blinking.
        g = 'lowerhall'
        self.scatterGrime(43, -91, 69, -73, 0, g, 8, 251, color=dustC)
        self.grime((62, -86), 5, g, color=wet, lift=0.05)
        self.papers(56, -90, 68, -74, 0, g, 4, 252, color=(0.8, 0.75, 0.65, 1))
        self.steam((62, -90.2, 10.1), every=1.4, size=1.0, rise=-8.5, color=(0.7, 0.8, 0.9, 0.5))
        self.blinker((44.05, -88.5, 7.0), -90, (1, 0.3, 0.2), on=0.3, off=1.2, size=0.3)
        self.sign((69.5, -76, 7.5), 90, 'STAFF ONLY', g, plate=(0.85, 0.82, 0.75, 1), scale=0.6)
        self.damp((70, -88, 1), 90, 6, 7, g)
        self.drain((60, -80), 1.8, g)
        # The alley: puddles, rubbish, steam from the street grate, a
        # washing line across overhead.
        g = 'alley'
        self.scatterGrime(57, -69, 91, 9, 0, g, 18, 261, color=(0.1, 0.1, 0.1, 0.4))
        for c, sz in (((66, -50), 6), ((80, -30), 7), ((70, -6), 5), ((84, -62), 4)):
            self.grime(c, sz, g, color=wet, lift=0.05)
        self.papers(58, -68, 90, 8, 0, g, 14, 262, color=(0.75, 0.72, 0.66, 1))
        self.drain((74, -40), 2.6, g)
        self.steam((74, -40, 0.2), every=1.8, size=3.4, rise=9.0, color=(0.8, 0.8, 0.82, 0.45))
        self.drain((64, -10), 2.2, g)
        for x, y in ((57.4, -2), (90.8, -44)):
            self.kit.model('phase_5/models/props/trashcan_TT', pos=(x, y, 0), scale=0.8, color=(0.55, 0.55, 0.52, 1))
            self.kit.wallTube((x, y, 0), 1.3, 4)
        self.sign((56.0, -32.3, 8.8), -90, 'NO LOITERING', g, plate=(0.8, 0.14, 0.1, 1), ink=(1, 0.95, 0.85, 1), scale=0.6)
        self.conduit((56.0, -60), -90, 0, 22, g)
        self.conduit((92.0, -14), 90, 0, 20, g)
        self.vent((92.0, -36, 10), 90, 3.2, 2.2, g)
        self.damp((56.0, -12, 2), -90, 10, 9, g, color=(0.1, 0.1, 0.1, 0.35))
        self.kit.beam((56, -20, 16), (92, -26, 15), 0.06, METAL, color=(0.2, 0.2, 0.2, 1), tile=1, group=g)
        r = rng(263)
        for i, (t, c) in enumerate(((0.2, (0.85, 0.82, 0.78, 1)), (0.35, (0.55, 0.25, 0.22, 1)), (0.55, (0.4, 0.45, 0.6, 1)),
                                    (0.75, (0.8, 0.75, 0.55, 1)))):
            x, y, zz = 56 + 36 * t, -20 - 6 * t, 16 - 1 * t
            cloth = self.root.attachNewNode('washing')
            cloth.setPos(x, y, zz)
            cloth.setH(-9.5)
            self.boxNode(cloth, (-0.9, -0.03, -2.4), (0.9, 0.03, 0), CURTAIN, color=c, tile=3)
            sway = 6 + r.random() * 6
            secs = 2.6 + r.random()
            self.keepLooping(Sequence(LerpHprInterval(cloth, secs / 2, Vec3(-9.5, sway, 0), startHpr=Vec3(-9.5, -sway * 0.4, 0),
                                                      blendType='easeInOut'),
                                      LerpHprInterval(cloth, secs / 2, Vec3(-9.5, -sway * 0.4, 0), startHpr=Vec3(-9.5, sway, 0),
                                                      blendType='easeInOut')))
        # The fenced stairs and the storage room.
        g = 'storage'
        self.scatterGrime(64, 11, 80, 29, 0, g, 6, 271, color=(0.1, 0.1, 0.1, 0.35))
        self.scatterGrime(53, 31, 91, 55, 12, g, 10, 272, color=dustC)
        self.papers(56, 32, 90, 54, 12, g, 8, 273, color=(0.8, 0.75, 0.65, 1))
        self.dust((73, 43, 24), 12)
        self.sign((60, 55.5, 20), 180, 'PROPERTY OF KINO DER TOONEN', g, plate=(0.85, 0.82, 0.75, 1), scale=0.55)
        self.damp((92, 34, 14), 90, 6, 8, g)
        # The stage: tape marks, scripts, a ghost light.
        g = 'stage'
        z = 4
        self.scatterGrime(-49, 42, 49, 79, z, g, 14, 281, color=dustC)
        self.papers(-46, 44, 46, 78, z, g, 14, 282, color=(0.88, 0.85, 0.78, 1))
        for x, y in ((-16, 48), (16, 48), (-6, 56), (8, 58), (-28, 52), (28, 54)):
            for rot in (45, -45):
                self.floorPic((x, y), 1.4, 0.18, SOFT_GLOW, g, color=(0.9, 0.85, 0.3, 1), rot=rot, z=z, lift=0.06)
        self.dust((-21, 69, 36), z)
        self.dust((23, 59, 36), z)
        # The ghost light: a bare bulb on a stand, left burning.
        self.kit.cylinder((-44, 46, z), 0.8, 0.3, METAL, sides=10, color=(0.25, 0.25, 0.27, 1), collide=False)
        self.kit.cylinder((-44, 46, z + 0.3), 0.08, 5.2, METAL, sides=6, color=(0.3, 0.3, 0.32, 1), collide=False)
        self.kit.wallTube((-44, 46, z), 0.8, 6)
        bulb = self.root.attachNewNode('ghostLight')
        bulb.setPos(-44, 46, z + 5.8)
        self.boxNode(bulb, (-0.25, -0.25, -0.3), (0.25, 0.25, 0.3), CEMENT, color=(1, 1, 1, 1), tile=1)
        bulb.setLightOff(1)
        lit, dim = Vec4(3, 2.8, 2.2, 1), Vec4(1.2, 1.1, 0.9, 1)
        bulb.setColorScale(lit)
        self.keepLooping(Sequence(Wait(2.3), Func(bulb.setColorScale, dim), Wait(0.08), Func(bulb.setColorScale, lit), Wait(0.15),
                                  Func(bulb.setColorScale, dim), Wait(0.05), Func(bulb.setColorScale, lit), Wait(4.0)))
        self.lamp((-44, 47, z + 6), (1.0, 0.9, 0.7), 18.0, groups=(g,))
        # The auditorium: popcorn and tickets in the aisles, dust down from
        # the holes, damp on the walls, the projector's beam.
        g = 'aud'
        self.scatterGrime(-43, -55, 43, 38, 0, g, 20, 291, color=(0.12, 0.05, 0.04, 0.45))
        self.papers(-42, -54, 42, 30, 0, g, 22, 292, color=(0.85, 0.8, 0.7, 1))
        r = rng(293)
        for i in range(70):
            x = r.choice((r.uniform(-10, 10), r.uniform(-43, -38), r.uniform(38, 43), r.uniform(-30, 30)))
            y = r.uniform(-54, 32)
            self.floorPic((x, y), 0.4, 0.4, SOFT_GLOW, g, color=(1.0, 0.95, 0.75, 1), z=0, lift=0.06 + 0.001 * (i % 5))
        for c in ((-27, -21), (27, 9), (0, 22)):
            self.dust((c[0], c[1], 31), 0)
        for p, hf in (((-43.9, -35, 6), -90), ((-43.9, 18, 14), -90), ((43.9, -17, 8), 90), ((43.9, 30, 18), 90),
                      ((-20, -55.9, 6), 0), ((24, -55.9, 10), 0)):
            self.damp(p, hf, 8, 9, g)
        self.projectorLight()
        # The booth: film run off the reels across the floor.
        g = 'booth'
        z = 22
        self.scatterGrime(-15, -55, 15, -48, z, g, 5, 301, color=dustC)
        for i, (x, y, rot) in enumerate(((4, -52, 20), (8, -53.4, -35), (-4, -54, 80))):
            self.floorPic((x, y), 3.6, 0.5, 'phase_10/maps/Tracks.jpg', g, color=(0.25, 0.22, 0.2, 1), rot=rot, z=z,
                          lift=0.05 + 0.01 * i, uv=[(0, 0), (4, 0), (4, 1), (0, 1)])
        # The four rooms.
        for key, c in ROOMS:
            g = 'room-' + key
            self.scatterGrime(c[0] - 11, c[1] - 9, c[0] + 11, c[1] + 9, c[2], g, 6, int(c[0]) + 311, color=dustC)
            self.papers(c[0] - 10, c[1] - 8, c[0] + 10, c[1] + 4, c[2], g, 4 if key != 'meeting' else 10, int(c[0]) + 312,
                        color=(0.88, 0.85, 0.78, 1))

    def mannequins(self, spots, z):
        """Dress forms: a pillar on a stand with a torso of cloth on it."""
        for x, y in spots:
            self.kit.cylinder((x, y, z), 0.9, 0.25, WOOD, sides=10, color=(0.5, 0.4, 0.32, 1), collide=False)
            self.kit.cylinder((x, y, z + 0.25), 0.12, 3.0, METAL, sides=6, color=(0.5, 0.5, 0.5, 1), collide=False)
            self.kit.cylinder((x, y, z + 3.2), 0.9, 1.8, CURTAIN, sides=10, color=(0.75, 0.68, 0.6, 1), collide=False, radiusTop=1.05)
            self.kit.dome((x, y, z + 5.0), 1.05, CURTAIN, rings=3, sides=10, color=(0.75, 0.68, 0.6, 1))
            self.kit.wallTube((x, y, z), 1.0, 6)

    # --- Alley route: lower hall, the alley, the fenced stairs, storage ---

    def lowerHall(self):
        g = 'lowerhall'
        self.zone('lowerhall', 'the lower hall', (42, -92, -1, 70, -72, 12))
        self.floor(42, -92, 70, -72, 0, TILE, tile=4, color=(0.4, 0.37, 0.35, 1), group=g)
        self.ceiling(42, -92, 70, -72, 11, CEILING, color=(0.42, 0.39, 0.36, 1), group=g)
        self.shell(42, -92, 70, -72, 0, 11, PLASTER, color=(0.48, 0.43, 0.39, 1), ops={
            'w': [(-75, 6, 0, 9)],
            'n': [(63, 6, 0, 9)],
            's': [(58, 6, 2, 8)],
        }, group=g, lower=(CEMENT, 3.5, (0.6, 0.6, 0.6, 1)), outside={'s': (BRICK, BRICK_C), 'n': (BRICK2, BRICK_C), 'e': (BRICK2, BRICK_C)})
        self.threshold(40, -78, 42, -72, 0)
        d = self.door('downstairs', 750, (41, -78), (41, -72), 0, 9, ['lowerhall', 'alley'], title='the downstairs door')
        self.leaves(d)
        self.window('lowerhall', (58, -92, 0), 0)
        self.wallGag((G.SQUIRT, 1), (70, -82, 0), 90, 1000, 'lowerhall')  # MPL: Glass of Water
        self.boxSpot('lower hall', (66, -74.5, 0), 0)
        # The fire trap across the floor.
        self.trap('fire', 'fire', (49, -91, 55, -73), (52, -72, 0), 180, z=(0, 10), line=(Point3(52, -91, 0), Point3(52, -73, 0)))
        self.lamp((56, -82, 9), (0.95, 0.7, 0.5), 22.0, groups=(g,), flicker=True)
        for x in (46, 66):
            self.kit.box((x, -91.6, 0), (x + 2.5, -90.0, 6), side=BOARDS, top=BOARDS, tile=3, color=GREY_WOOD, collide='wall')
        # Burnt black where the fire trap has gone off before.
        self.kit.box((49.2, -91.8, 0.02), (54.8, -72.2, 0.05), top=TILE, side=TILE, tile=4, color=(0.18, 0.15, 0.13, 1),
                     collide=False, group=g)
        # Old pipes along the ceiling, a fuse box and a fire bucket.
        for y, rad in ((-90.6, 0.35), (-89.6, 0.25)):
            self.kit.box((42, y - rad, 10.1 - rad), (70, y + rad, 10.1 + rad), side=RUST, top=RUST, tile=3,
                         color=(0.5, 0.44, 0.4, 1), collide=False, group=g)
        self.kit.box((43, -90, 4.5), (44, -87, 7.5), side=METAL, top=METAL, tile=2, color=(0.45, 0.47, 0.5, 1), collide=False)
        self.kit.model('phase_6/models/props/small_round_barrel', pos=(68.5, -89, 0), scale=0.7, color=(0.75, 0.25, 0.2, 1))
        self.kit.wallTube((68.5, -89, 0), 1.0, 2)

    def alley(self):
        g = 'alley'
        self.zone('alley', 'the alley', (56, -70, -1, 92, 10, 22))
        self.floor(56, -70, 92, 10, 0, COBBLE, tile=10, color=(0.62, 0.6, 0.62, 1), group=g)
        # Brick buildings on both sides, the lower hall at the south end.
        self.wall((55.5, -70), (55.5, 10.5), 0, 22, BRICK, faces='right', tile=12, color=BRICK_C, group=g)
        self.wall((92.5, 10.5), (92.5, -70), 0, 20, BRICK2, faces='right', tile=12, color=BRICK_C, group=g)
        self.wall((56, 10.5), (64, 10.5), 0, 14, BRICK, faces='both', tile=12, color=BRICK_C, group=g)
        self.wall((80, 10.5), (92.5, 10.5), 0, 14, BRICK, faces='both', tile=12, color=BRICK_C, group=g)
        self.threshold(60, -72, 66, -70, 0, COBBLE, (0.62, 0.6, 0.62, 1), g)
        self.wall((70.5, -70.5), (92.5, -70.5), 0, 20, BRICK2, faces='left', tile=12, color=BRICK_C, group=g)
        # Rubbish: crates, barrels, an old poster wall.
        for x, y, hh in ((60, -20, 10), (62, -16, 40), (89, -60, -10), (88, -8, 20)):
            self.kit.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, 0), h=hh, scale=0.55, color=(0.7, 0.62, 0.55, 1))
            self.kit.wallTube((x, y, 0), 2.3, 3)
        for x, y in ((90, -36), (89, -32)):
            self.kit.model('phase_6/models/props/small_round_barrel', pos=(x, y, 0), scale=1.0, color=(0.6, 0.55, 0.5, 1))
            self.kit.wallTube((x, y, 0), 1.3, 2)
        self.poster((56.1, -40, 5), -90, 1.4)
        self.poster((56.1, -46, 5), -90, 1.4)
        self.wallGag((G.SQUIRT, 3), (92, -24, 0), 90, 1200, 'alley')   # AK-74u: Seltzer Bottle
        self.boxSpot('alley', (89.5, -46, 0), -90)
        # Cogs come over the roofs on either side.
        self.roofEdge('alley', Point3(55.5, -26, 22.5), Point3(61, -26, 0), -90)
        self.roofEdge('alley', Point3(92.5, -4, 20.5), Point3(87, -4, 0), 90)
        self.roofEdge('alley', Point3(92.5, -54, 20.5), Point3(87, -54, 0), 90)
        # Cold street lamps.
        self.kit.model('phase_6/models/karting/GoofyStadium_Lamppost_Base1', pos=(90.5, -16, 0), scale=0.6, color=(0.5, 0.5, 0.55, 1))
        self.lamp((88, -16, 12), COLD, 45.0, groups=(g, 'static'))
        self.lamp((60, -60, 10), COLD, 30.0, groups=(g,), flicker=True)
        # The gate to the fenced stairs.
        d = self.door('gate', 1000, (64, 10.5), (80, 10.5), 0, 9, ['storage'], kind='gate', title='the gate')
        self.gate(d)

    def storage(self):
        g = 'storage'
        z = 12
        self.zone('storage', 'the storage room', (52, 10, -1, 92, 56, 26))
        # The fenced stairs up.
        self.floor(55.5, 10.5, 92.5, 30, 0, COBBLE, tile=10, color=(0.5, 0.49, 0.52, 1), group=g)
        self.kit.stairs((72, 13, 0), 0, 16, 12, run=17, steps=12, side=CEMENT, tread=CEMENT, color=(0.55, 0.55, 0.56, 1), rails=False)
        # The yards each side behind the railings, shut in by the buildings.
        self.wall((55.5, 10.5), (55.5, 30), 0, 26, BRICK, faces='right', tile=12, color=BRICK_C, group=g)
        self.wall((92.5, 30), (92.5, 10.5), 0, 26, BRICK2, faces='right', tile=12, color=BRICK_C, group=g)
        iron = (0.22, 0.21, 0.21, 1)
        for x in (63.6, 80.4):
            # Nobody gets past the railings, whatever the height.
            self.kit.wallBox((x - 0.2, 10.5, -1), (x + 0.2, 30, 34))
            self.kit.box((x - 0.3, 10.5, 0), (x + 0.3, 13, 1.6), side=SMALL_BRICK, top=CEMENT, tile=4, color=BRICK_C, collide=False)
            y = 10.8
            while y < 30:
                base = max(0.0, (y - 13) / 17.0 * 12.0)
                self.kit.box((x - 0.07, y - 0.07, base), (x + 0.07, y + 0.07, base + 8.0), side=METAL, top=METAL, tile=1,
                             color=iron, collide=False, group=g)
                # Spear tips.
                self.kit.box((x - 0.13, y - 0.13, base + 8.0), (x + 0.13, y + 0.13, base + 8.35), side=METAL, top=METAL, tile=1,
                             color=(0.4, 0.36, 0.25, 1), collide=False, group=g)
                y += 0.7
            # The rails, stepped up the slope.
            for i in range(17):
                y0, y1 = 13 + i, 14 + i
                for zz in (0.8, 4.0, 7.6):
                    b0 = (y0 - 13) / 17.0 * 12.0
                    self.kit.box((x - 0.1, y0, b0 + zz), (x + 0.1, y1, b0 + zz + 0.18), side=METAL, top=METAL, tile=1,
                                 color=iron, collide=False, group=g)
            for zz in (0.8, 4.0, 7.6):
                self.kit.box((x - 0.1, 10.5, zz), (x + 0.1, 13, zz + 0.18), side=METAL, top=METAL, tile=1, color=iron,
                             collide=False, group=g)
        # Junk in the yards behind the railings.
        for x, y, hh in ((59, 14, 15), (59.5, 18, 70), (88, 24, -20)):
            self.kit.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, 0), h=hh, scale=0.55, color=(0.6, 0.55, 0.5, 1))
        self.kit.model('phase_6/models/props/small_round_barrel', pos=(89, 14, 0), scale=1.0, color=(0.5, 0.47, 0.44, 1))
        self.lamp((72, 20, 16), COLD, 26.0, groups=(g,))
        # The storage room, up high.
        self.floor(52, 30, 92, 56, z, OLD_PLANKS, tile=6, color=GREY_WOOD, group=g, thick=1.0)
        self.ceiling(52, 30, 92, 56, z + 12, CEILING, color=(0.5, 0.46, 0.42, 1), group=g, holes=[(70, 40, 76, 46)])
        self.ceilingHole('storage', Point3(73, 43, z), 12)
        self.shell(52, 30, 92, 56, z, 12, BRICK2, color=BRICK_C, ops={
            's': [(72, 14, -12, 9)],
            'w': [(47, 6, 0, 9)],
            'e': [(44, 6, 2, 8)],
        }, group=g, outside={'e': (BRICK2, BRICK_C), 's': (BRICK2, BRICK_C)}, tile=12)
        self.window('storage', (92, 44, z), 90, hover=True)
        # Shelves, loose letters off the marquee, crates.
        for y in (33, 41):
            self.kit.model('phase_10/models/cashbotHQ/shelf_A1', pos=(55, y, z), h=-90, scale=0.55, color=(0.6, 0.55, 0.5, 1))
            self.kit.wallBox((52, y - 3, z), (57, y + 3, z + 6))
        for x, y, letter, hh, lean in ((76, 55.2, 'K', 0, 14), (80.5, 55.2, 'I', 0, 10), (85, 55.2, 'N', 0, 16),
                                       (64, 54.0, 'O', 25, 70), (91.2, 40, 'T', -90, 12), (68, 52, 'D', 160, 90)):
            self.marqueeLetter(letter, (x, y, z), hh, lean)
        for x, y in ((89, 52), (84, 52.5), (62, 52)):
            self.kit.model('phase_9/models/cogHQ/woodCrate_cube', pos=(x, y, z), h=self.rand.uniform(0, 90), scale=1.2,
                           color=(0.7, 0.62, 0.55, 1))
            self.kit.wallBox((x - 1.3, y - 1.3, z), (x + 1.3, y + 1.3, z + 2.4))
        self.boxSpot('storage', (85, 32.5, z), 180)
        self.trap('storage', 'electric', (60, 31, 70, 55), (70, 55.5, z), 180, z=(z, z + 11),
                  line=(Point3(65, 31, z), Point3(65, 55, z)))
        self.lamp((72, 43, z + 10), DIM_AMBER, 26.0, groups=(g,), flicker=True)
        self.threshold(50, 44, 52, 50, z)
        d = self.door('storage', 1250, (51, 44), (51, 50), z, z + 9, ['stage'], kind='junk', title='the junk')
        self.junk(d)
        # Down to the stage: short stairs on the stage side.
        self.kit.stairs((38, 47, 4), -90, 6, 8, run=12, steps=8, side=WOOD, tread=OLD_PLANKS, color=(0.6, 0.5, 0.42, 1))

    def marqueeLetter(self, letter, pos, h, lean):
        """One of the marquee's letters on its white board, propped against
        a wall (lean in degrees back from upright; 90 is flat on the floor)."""
        node = self.kit.visual.attachNewNode('letter')
        node.setPos(Point3(*pos))
        node.setHpr(h, -lean, 0)
        self.boxNode(node, (-1.6, -0.12, 0), (1.6, 0.12, 4.2), PLASTER, color=(0.85, 0.82, 0.74, 1), tile=4)
        self.text(letter, (0, -0.14, 0.75), 0, 3.6, (0.12, 0.1, 0.1, 1), parent=node)
        if lean >= 80:
            node.setZ(pos[2] + 0.13)

    # --- The stage and the auditorium ---

    def stage(self):
        g = 'stage'
        z = 4
        self.zone('stage', 'the stage', (-50, 41, 3, 50, 80, 36))
        self.floor(-50, 41, 50, 80, z, OLD_PLANKS, tile=6, color=OLD_WOOD, group=g, thick=4.0)
        self.ceiling(-50, 41, 50, 80, 36, OLD_PLANKS, tile=8, color=(0.35, 0.32, 0.3, 1), group=g,
                     holes=[(-24, 66, -18, 72), (20, 56, 26, 62)])
        self.ceilingHole('stage', Point3(-21, 69, z), 32)
        self.ceilingHole('stage', Point3(23, 59, z), 32)
        self.shell(-50, 41, 50, 80, z, 32, BRICK2, color=(0.6, 0.5, 0.46, 1), ops={
            'w': [(45, 6, 0, 9)],
            'e': [(47, 6, 8, 17)],
            's': [(0, 76, 0, 24)],
            'n': [(30, 6, 2, 8)],
        }, group=g, tile=12, outside={'n': (BRICK2, BRICK_C)})
        self.window('stage', (30, 80, z), 180, hover=True)
        # Backstage: flats, ropes, crates and a piano to run round.
        self.kit.box((-12, 62, z), (12, 64, z + 14), side=BOARDS, top=WOOD, tile=6, color=(0.62, 0.55, 0.48, 1))
        self.kit.box((-14, 66, z), (-2, 67, z + 10), side=BOARDS, top=WOOD, tile=6, color=(0.55, 0.5, 0.45, 1))
        self.kit.model('phase_6/models/props/piano', pos=(-34, 70, z + 1.8), h=30, scale=0.55, color=(0.55, 0.5, 0.45, 1))
        self.kit.wallTube((-34, 70, z), 3.5, 4)
        for x, y in ((34, 74), (37, 70), (30, 76)):
            self.kit.model('phase_9/models/cogHQ/woodCrateB', pos=(x, y, z), h=self.rand.uniform(0, 90), scale=0.45,
                           color=(0.68, 0.6, 0.52, 1))
            self.kit.wallTube((x, y, z), 1.9, 3)
        # The fly lines down the side walls, each tied off with a sandbag.
        for x in (-46, -40, 40, 46):
            self.kit.beam((x, 78, 36), (x, 78, z + 3.6), 0.12, WOOD, color=(0.75, 0.68, 0.55, 1), tile=2)
            self.kit.model('phase_5/models/props/sandbag-mod', pos=(x, 78, z + 0.1), h=self.rand.uniform(0, 360), scale=1.1,
                           color=(0.75, 0.68, 0.58, 1))
        # The old painted backdrop, a sunset sky gone brown, high on the
        # back wall over the flats.
        self.kit.quad([(-40, 79.6, 15), (40, 79.6, 15), (40, 79.6, 33), (-40, 79.6, 33)], 'phase_6/maps/lateday_sky3.jpg',
                      [(0, 0), (1, 0), (1, 1), (0, 1)], (0.42, 0.34, 0.3, 1), g)
        self.kit.beam((-41, 79.2, 33.2), (41, 79.2, 33.2), 0.35, WOOD, color=(0.5, 0.42, 0.35, 1), tile=3)
        self.kit.beam((-41, 79.2, 14.8), (41, 79.2, 14.8), 0.35, WOOD, color=(0.5, 0.42, 0.35, 1), tile=3)
        # Footlights along the front edge and a batten of stage lights
        # over it: dead until the power comes on.
        self.powerBulbs = []
        self.powerLamps = []
        lights = self.kit.visual.attachNewNode('stageLights')
        for i in range(19):
            x = -36 + i * 4
            self.boxNode(lights, (x - 0.9, 41.6, z), (x + 0.9, 42.6, z + 0.5), METAL, color=(0.3, 0.28, 0.26, 1), tile=1)
            bulb = self.boxNode(lights, (x - 0.6, 42.2, z + 0.1), (x + 0.6, 42.7, z + 0.55), CEMENT, color=(0.25, 0.22, 0.18, 1),
                                tile=1)
            self.powerBulbs.append(bulb)
        self.kit.beam((-34, 47, 30), (34, 47, 30), 0.3, METAL, color=(0.3, 0.3, 0.32, 1), tile=2)
        for x in (-30, -15, 0, 15, 30):
            self.kit.beam((x, 47, 36), (x, 47, 30), 0.08, METAL, color=(0.3, 0.3, 0.32, 1), tile=1)
        for x in (-24, -8, 8, 24):
            can = lights.attachNewNode('can')
            can.setPos(x, 47, 29.4)
            can.setP(-35)
            self.boxNode(can, (-0.8, -1.4, -0.8), (0.8, 1.0, 0.8), METAL, color=(0.25, 0.25, 0.27, 1), tile=1)
            lens = self.boxNode(can, (-0.6, -1.5, -0.6), (0.6, -1.38, 0.6), CEMENT, color=(0.25, 0.22, 0.18, 1), tile=1)
            self.powerBulbs.append(lens)
            self.powerLamps.append((self.lamp((x, 44, 20), (0, 0, 0), 34.0, groups=(g, 'aud')), Vec4(1.0, 0.86, 0.62, 1)))
        self.powerLamps.append((self.lamp((0, 40, 7), (0, 0, 0), 30.0, groups=(g, 'aud')), Vec4(1.0, 0.8, 0.55, 1)))
        # The power, the M16 and the Rakes on the back wall.
        self.switch((-20, 80, z), 180)
        self.wallGag((G.DROP, 1), (-11, 80, z), 180, 1200, 'stage')    # M16: Sandbag
        self.wallGag('rake', (-50, 70, z), -90, 1000, 'stage')        # Claymores: Rakes
        self.boxSpot('backstage', (-29, 77.5, z), 0)
        # The teleporter at the front and the podium's pie cannon.
        self.pad(STAGE_PAD, g, glow=(1.0, 0.6, 0.4))
        self.teleporter('stage', STAGE_PAD, 180, role='stage')
        self.kit.model('phase_4/models/events/election_stagePodium', pos=(20, 50, z), h=180, scale=0.85, color=(0.7, 0.6, 0.55, 1))
        self.kit.wallTube((20, 50, z), 2.0, 4.8)
        self.turret((20, 50.5, z + 4.85), 180, (24.5, 50, z), 180)
        # The curtain, down until the power comes on.
        d = self.door('curtain', 0, (-38, 41.2), (38, 41.2), z, z + 24, ['aud'], kind='curtain', title='the curtain', power=True)
        self.curtain(d)
        self.lamp((0, 60, 26), (1.0, 0.8, 0.6), 60.0, groups=(g,))
        self.lamp((-30, 72, 12), DIM_AMBER, 24.0, groups=(g,), flicker=True)

    def curtain(self, entry):
        """Velvet in folds across the proscenium."""
        a, b = entry['a'], entry['b']
        z0, z1 = entry['z']
        node = entry['visual']
        node.setPos(0, a[1], z0)
        width = b[0] - a[0]
        from toontown.survival.previewmaps.MapKit import Mesh
        m = Mesh()
        folds = 38
        for i in range(folds):
            xa = a[0] + width * i / folds
            xb = a[0] + width * (i + 1) / folds
            ya = 0.5 if i % 2 == 0 else -0.5
            yb = -ya
            pts = [Point3(xa, ya, -0.3), Point3(xb, yb, -0.3), Point3(xb, yb, z1 - z0 + 4), Point3(xa, ya, z1 - z0 + 4)]
            m.quad(pts, [(i * 0.5, 0), ((i + 1) * 0.5, 0), ((i + 1) * 0.5, 3), (i * 0.5, 3)], Vec4(*VELVET))
            m.quad([pts[1], pts[0], pts[3], pts[2]], [(i * 0.5, 0), ((i + 1) * 0.5, 0), ((i + 1) * 0.5, 3), (i * 0.5, 3)], Vec4(*VELVET))
        np = node.attachNewNode(m.node('curtain'))
        np.setTexture(self.kit.tex(CURTAIN), 1)
        np.setX(0)
        # A gold fringe at the bottom.
        self.boxNode(node, (a[0], -0.7, -0.3), (b[0], 0.7, 0.5), MOLDING, color=(0.9, 0.7, 0.3, 1), tile=2)

    def auditorium(self):
        g = 'aud'
        self.zone('aud', 'the auditorium', (-44, -56, -1, 44, 39, 31))
        self.floor(-44, -56, 44, 39, 0, CARPET, tile=10, color=(0.45, 0.17, 0.16, 1), group=g)
        self.ceiling(-44, -56, 44, 39, 31, COFFER, tile=10, color=(0.55, 0.48, 0.44, 1), group=g,
                     holes=[(-30, -24, -24, -18), (24, 6, 30, 12), (-4, 18, 4, 26)])
        self.ceilingHole('aud', Point3(-27, -21, 0), 31)
        self.ceilingHole('aud', Point3(27, 9, 0), 31)
        self.ceilingHole('aud', Point3(0, 22, 0), 31)
        self.shell(-44, -56, 44, 39, 0, 31, WALLPAPER, color=(0.7, 0.56, 0.52, 1), ops={
            'n': [(0, 76, 4, 28)],
            's': [(0, 10, 0, 10)],
        }, group=g, lower=(DARK_PANEL, 5.0, PANEL), trim=(MOLDING, (0.75, 0.6, 0.45, 1)),
            outside={'e': (BRICK, BRICK_C), 'w': (BRICK, BRICK_C)})
        # The proscenium's front: gold trim round the opening.
        self.kit.beam((-38, 38.7, 28.2), (38, 38.7, 28.2), 1.2, MOLDING, color=(0.85, 0.65, 0.3, 1), tile=3)
        for x in (-38.4, 38.4):
            self.kit.beam((x, 38.7, 4), (x, 38.7, 28.8), 1.0, MOLDING, color=(0.85, 0.65, 0.3, 1), tile=3)
        self.threshold(-38, 39, 38, 41, 4, OLD_PLANKS, OLD_WOOD, g)
        # Steps up to the stage on both sides; anyone can jump off it.
        for x in (-34, 34):
            self.kit.stairs((x, 33, 0), 0, 6, 4, run=6, steps=4, side=WOOD, tread=CARPET, color=(0.6, 0.45, 0.4, 1))
        for x in (-16, 0, 16):
            self.drop((x, 39.5, 4), (x, 35, 0))
        # Seats: rows of folding velvet theatre seats on iron standards,
        # some gone, some with the back broken off, some knocked flat.
        r = rng(55)
        rows = [y for y in range(-44, 26, 5) if not -16 <= y <= 0]
        iron = (0.2, 0.19, 0.19, 1)
        velvet = (0.36, 0.12, 0.11, 1)
        for bank in ((-37, -11), (11, 37)):
            x0, x1 = bank
            for y in rows:
                if r.random() < 0.08:
                    continue
                n = int((x1 - x0) / 2.6)
                for i in range(n + 1):
                    # The iron standard between two seats.
                    sx = x0 + 0.4 + i * 2.6
                    self.kit.box((sx - 0.1, y - 1.1, 0), (sx + 0.1, y + 0.7, 2.6), side=METAL, top=METAL, tile=1, color=iron,
                                 collide=False, group=g)
                    if i == n:
                        break
                    x = sx + 1.3
                    roll = r.random()
                    if roll < 0.1:
                        continue                                   # torn out
                    self.kit.box((x - 1.1, y - 0.5, 1.4), (x + 1.1, y + 0.8, 1.9), side=CURTAIN, top=CURTAIN, tile=2,
                                 color=velvet, collide=False, group=g)
                    if roll < 0.22:
                        # The back snapped off and lying in the row.
                        self.kit.box((x - 1.0, y + 1.2, 0), (x + 1.2, y + 1.6, 2.4), side=CURTAIN, top=WOOD, tile=2,
                                     color=(0.42, 0.13, 0.12, 1), collide=False, group=g)
                        continue
                    self.kit.box((x - 1.1, y - 1.0, 1.4), (x + 1.1, y - 0.55, 4.2), side=CURTAIN, top=WOOD, tile=2,
                                 color=velvet, collide=False, group=g)
                self.kit.wallBox((x0, y - 1.2, 0), (x1, y + 0.9, 3.6))
        # Fallen beams through the broken ceiling.
        for x, y, hh in ((-27, -21, 30), (27, 9, -55)):
            self.kit.beam((x - 6 * math.cos(math.radians(hh)), y - 6 * math.sin(math.radians(hh)), 0.5),
                          (x + 6 * math.cos(math.radians(hh)), y + 6 * math.sin(math.radians(hh)), 6.5), 0.7, OLD_PLANKS,
                          color=GREY_WOOD, tile=3, group=g)
        # Pilasters down the side walls with a lamp on each.
        for y in (-44, -26, -8, 10, 28):
            for x, hh in ((-43.4, -90), (43.4, 90)):
                self.kit.box((x - 0.6, y - 1.0, 0), (x + 0.6, y + 1.0, 30), side=MOLDING, top=MOLDING, tile=4,
                             color=(0.62, 0.5, 0.4, 1), collide='wall', group=g)
                self.sconce((x - 0.7 if x > 0 else x + 0.7, y, 12), hh, g, light=False)
        # Rubble from the broken ceiling.
        for x, y in ((-27, -21), (27, 9)):
            for i in range(6):
                dx, dy = r.uniform(-4, 4), r.uniform(-4, 4)
                self.kit.box((x + dx, y + dy, 0), (x + dx + r.uniform(0.8, 2), y + dy + r.uniform(0.8, 2), r.uniform(0.3, 1.2)),
                             side=PLASTER, top=PLASTER, tile=2, color=(0.5, 0.45, 0.41, 1), collide=False, group=g)
        self.boxSpot('auditorium', (41.5, -38, 0), -90)
        # The passage back to the lobby, under the booth, opens with the power.
        self.threshold(-5, -59, 5, -57, 0, CARPET, (0.45, 0.17, 0.16, 1), g)
        for x in (-5.5, 5.5):
            self.wall((x, -59), (x, -57), 0, 10, DARK_PANEL, faces='both', color=PANEL, group=g, thick=1.0)
        d = self.door('passage', 0, (-5, -58), (5, -58), 0, 10, ['aud'], kind='shutter', title='the passage', power=True)
        self.shutter(d)
        self.kit.quad([(-5, -57, 10), (5, -57, 10), (5, -59, 10), (-5, -59, 10)], CEILING, [(0, 0), (1, 0), (1, 0.2), (0, 0.2)],
                      (0.5, 0.45, 0.42, 1), g)
        self.trap('passage', 'electric', (-5, -62, 5, -54), (8, -60, 0), 180, z=(0, 10),
                  line=(Point3(-5, -59.5, 0), Point3(5, -59.5, 0)))
        self.lamp((0, -10, 28), DIM_AMBER, 70.0, groups=(g,))
        self.lamp((0, 32, 6), (1.0, 0.75, 0.5), 30.0, groups=(g,), flicker=True)
        self.chandelier((0, -10, 30.5), 1.4)

    # --- The projection booth and the four rooms ---

    def booth(self):
        g = 'booth'
        z = 22
        self.floor(-16, -56, 16, -47, z, PLANKS, tile=6, color=GREY_WOOD, group=g, thick=1.0, under=DARK_PANEL)
        self.shell(-16, -56, 16, -47, z, 8.5, PLASTER, color=(0.62, 0.58, 0.54, 1), ops={
            'n': [(-6, 3, 3, 5), (0, 3, 3, 5), (6, 3, 3, 5)],
        }, sides='new', group=g, lower=(DARK_PANEL, 3.0, PANEL), outside={'n': (DARK_PANEL, PANEL), 'e': (DARK_PANEL, PANEL),
                                                                          'w': (DARK_PANEL, PANEL)})
        self.ceiling(-16, -56, 16, -47, z + 8.5, CEILING, color=(0.5, 0.46, 0.42, 1), group=g)
        # The projector at the middle window, film cans, the clock.
        # The projector: a pedestal, the lamp house, the lens barrel
        # through the middle window, and two film reels on arms on top.
        proj = self.root.attachNewNode('projector')
        proj.setPos(0, -50.2, z)
        steel = (0.55, 0.55, 0.58, 1)
        self.boxNode(proj, (-0.9, -0.9, 0), (0.9, 0.9, 2.6), METAL, color=(0.35, 0.35, 0.37, 1), tile=2)
        self.boxNode(proj, (-1.1, -1.6, 2.6), (1.1, 1.4, 4.4), METAL, color=steel, tile=2)
        self.boxNode(proj, (-0.45, 1.4, 3.0), (0.45, 2.9, 3.9), METAL, color=(0.3, 0.3, 0.32, 1), tile=1)
        self.boxNode(proj, (-0.3, -1.3, 4.4), (0.3, -0.9, 6.0), METAL, color=steel, tile=1)
        self.boxNode(proj, (-0.3, 0.7, 4.4), (0.3, 1.1, 6.0), METAL, color=steel, tile=1)
        for y, zz in ((-1.1, 6.6), (0.9, 6.6)):
            reel = proj.attachNewNode('reel')
            reel.setPos(0, y, zz)
            for a in range(4):
                spoke = self.boxNode(reel, (-0.12, -1.05, -0.44), (0.12, 1.05, 0.44), METAL, color=(0.28, 0.28, 0.3, 1), tile=1)
                spoke.setP(a * 45)
            self.keepLooping(LerpHprInterval(reel, 3.0, Vec3(0, -360, 0), startHpr=Vec3(0, 0, 0)))
        self.kit.wallBox((-1.2, -51.9, z), (1.2, -47.3, z + 4.4))
        # Shaded by hand: the booth lamp's glow, from above.
        proj.setLightOff(1)
        proj.setColorScale(1.5, 1.38, 1.22, 1)
        # Film cans stacked by the wall.
        for i, (x, y) in enumerate(((13.5, -55, ), (13.5, -55), (14.6, -53.6))):
            self.kit.cylinder((x, y, z + (0.5 if i == 1 else 0)), 0.9, 0.5, METAL, sides=14, color=(0.45, 0.43, 0.4, 1), collide=False)
        self.kit.model('phase_13/models/parties/partyClock', pos=(-2, -55.2, z), scale=0.24, color=(0.8, 0.75, 0.7, 1))
        # Nobody climbs out of the little windows.
        self.kit.wallBox((-8, -47.5, z), (8, -46.5, z + 8))
        self.clockText = self.text('', (0, -55.0, z + 6.6), 180, 0.8, (1, 0.3, 0.25, 1), parent=self.root)
        self.pad(BOOTH_PAD, g, glow=(0.6, 0.85, 1.0))
        self.wallGag('tnt', (6, -56, z), 0, 250, 'booth')
        self.lamp((0, -51.5, z + 7), DIM_AMBER, 20.0, groups=(g,), flicker=True)
        # A beam of light from the projector to the screen... long dead.

    def returnRooms(self):
        for key, c in ROOMS:
            g = 'room-' + key
            x0, y0, x1, y1 = c[0] - 12, c[1] - 10, c[0] + 12, c[1] + 10
            z = c[2]
            if key == 'bedroom':
                self.floor(x0, y0, x1, y1, z, PLANKS, tile=6, color=(0.85, 0.75, 0.65, 1), group=g)
                self.shell(x0, y0, x1, y1, z, 10, 'phase_3.5/maps/wall_paper_a1.jpg', color=(0.9, 0.85, 0.85, 1), group=g,
                           lower=(WAINSCOT, 3.0, PANEL))
                self.ceiling(x0, y0, x1, y1, z + 10, CEILING, group=g)
                self.kit.model('phase_5.5/models/estate/regular_bed', pos=(c[0] - 8, c[1] + 9, z), h=0, scale=1.0)
                self.kit.model('phase_5.5/models/estate/cabinetRwood', pos=(c[0] + 8, c[1] + 9, z), h=0, scale=0.75)
                self.kit.model('phase_5.5/models/estate/rugA', pos=(c[0], c[1], z + 0.02), scale=2.0)
                self.kit.model('phase_5.5/models/estate/lampA', pos=(c[0] - 4, c[1] + 9, z))
                self.lamp((c[0], c[1], z + 8), (1.0, 0.85, 0.7), 26.0, groups=(g,))
            elif key == 'ruined':
                self.floor(x0, y0, x1, y1, z, OLD_PLANKS, tile=6, color=(0.5, 0.45, 0.42, 1), group=g)
                self.shell(x0, y0, x1, y1, z, 10, 'phase_3.5/maps/wall_paper_a1.jpg', color=(0.45, 0.42, 0.42, 1), group=g,
                           lower=(WAINSCOT, 3.0, (0.5, 0.45, 0.42, 1)))
                self.ceiling(x0, y0, x1, y1, z + 10, CEILING, color=(0.4, 0.38, 0.36, 1), group=g, holes=[(c[0] - 3, c[1] - 2, c[0] + 4, c[1] + 3)])
                self.kit.model('phase_5.5/models/estate/regular_bed', pos=(c[0] - 8, c[1] + 9, z), h=12, r=8, scale=1.0,
                               color=(0.45, 0.4, 0.38, 1))
                self.kit.model('phase_5.5/models/estate/cabinetRwood', pos=(c[0] + 8, c[1] + 7, z), h=25, r=-70,
                               scale=0.75, color=(0.45, 0.4, 0.38, 1))
                self.kit.model('phase_5.5/models/estate/lampA', pos=(c[0] - 3, c[1] + 2, z), r=90, color=(0.45, 0.4, 0.38, 1))
                self.lamp((c[0], c[1], z + 8), (0.7, 0.75, 0.95), 26.0, groups=(g,), flicker=True)
            elif key == 'dentist':
                self.floor(x0, y0, x1, y1, z, TILE, tile=4, color=(0.8, 0.85, 0.82, 1), group=g)
                self.shell(x0, y0, x1, y1, z, 10, TILE, color=(0.75, 0.82, 0.8, 1), group=g, tile=4)
                self.ceiling(x0, y0, x1, y1, z + 10, CEILING, color=(0.8, 0.8, 0.8, 1), group=g)
                self.kit.model('phase_5.5/models/estate/deskChair', pos=(c[0], c[1] + 3, z), h=180, scale=2.0, color=(0.6, 0.75, 0.75, 1))
                self.kit.model('phase_3.5/models/modules/lamp_tall', pos=(c[0] + 3, c[1] + 6, z), scale=1.0, color=(0.85, 0.85, 0.85, 1))
                self.kit.model('phase_11/models/lawbotHQ/LB_endtableA', pos=(c[0] - 4, c[1] + 5, z), color=(0.8, 0.8, 0.85, 1))
                self.lamp((c[0], c[1] + 2, z + 8), (0.9, 1.0, 1.0), 26.0, groups=(g,))
            else:
                self.floor(x0, y0, x1, y1, z, CARPET, tile=8, color=(0.3, 0.3, 0.38, 1), group=g)
                self.shell(x0, y0, x1, y1, z, 10, DARK_PANEL, color=PANEL, group=g, tile=4)
                self.ceiling(x0, y0, x1, y1, z + 10, CEILING, color=(0.6, 0.6, 0.6, 1), group=g)
                self.kit.box((c[0] - 7, c[1] + 2, z), (c[0] + 7, c[1] + 6, z + 2.6), side=DARK_PANEL, top=MARBLE, tile=4,
                             color=(0.6, 0.5, 0.45, 1))
                for i in range(5):
                    for y, hh in ((c[1] + 0.5, 0), (c[1] + 7.5, 180)):
                        self.kit.model('phase_11/models/lawbotHQ/LB_chairA', pos=(c[0] - 6 + i * 3, y, z), h=hh, scale=0.55)
                self.kit.model('phase_11/models/lawbotHQ/LB_bookshelfA', pos=(c[0], c[1] + 9.5, z), h=0, scale=0.8)
                self.lamp((c[0], c[1] + 4, z + 8), (1.0, 0.95, 0.85), 26.0, groups=(g,))
            self.pad(Point3(c[0], c[1] - 5, z), g)

    def outside(self):
        """The street in front of the lobby and the lane down the west side
        (where the cogs at those windows stand), and brick all round."""
        street = (0.55, 0.55, 0.58, 1)
        g = 'street'
        self.floor(-112, -126, 100, -101, 0, COBBLE, tile=10, color=street, group=g)
        self.floor(-112, -101, -41, -93, 0, COBBLE, tile=10, color=street, group=g)
        self.floor(41, -101, 100, -93, 0, COBBLE, tile=10, color=street, group=g)
        self.floor(-112, -93, -97, 50, 0, COBBLE, tile=10, color=street, group=g)
        facade = (0.55, 0.5, 0.48, 1)
        self.wall((-112, -126), (100, -126), 0, 22, BRICK2, faces='left', tile=12, color=facade, group=g)
        self.wall((-112, 50), (-112, -126), 0, 22, BRICK2, faces='left', tile=12, color=facade, group=g)
        self.wall((100, -126), (100, -93), 0, 22, BRICK2, faces='left', tile=12, color=facade, group=g)
        self.wall((-97, 50), (-112, 50), 0, 22, BRICK2, faces='left', tile=12, color=facade, group=g)
        self.lamp((0, -112, 12), COLD, 40.0, groups=(g, 'static'))
        self.lamp((-104, -20, 12), COLD, 40.0, groups=(g, 'static'))
        for x, y in ((-14, -112), (30, -112), (-104, -20)):
            self.kit.model('phase_6/models/karting/GoofyStadium_Lamppost_Base1', pos=(x, y, 0), scale=0.6, color=(0.5, 0.5, 0.55, 1))

    # --- In the game: the teleporter, the booth and the rooms ---

    def startGame(self, game):
        Building.startGame(self, game)
        self.linked = False
        self.charged = False
        self.inBooth = False
        self.coolUntil = 0.0
        self.boothTask = None

    def setPower(self, on):
        # The lights come up a little everywhere, and the stage lights and
        # the footlights come on.
        self.lampBoost = 1.15
        own = dict((id(np), color) for np, color in self.powerLamps)
        for np, names, color in self.lamps:
            np.node().setColor(own.get(id(np), color * self.lampBoost))
        for bulb in self.powerBulbs:
            bulb.setColorScale(6.0, 5.4, 4.0, 1)
            bulb.setLightOff(1)
        # The projector throws its dusty beam over the seats again.
        beam = getattr(self, 'projectorBeam', None)
        if beam is not None:
            beam.unstash()
            self.keepLooping(Sequence(LerpColorScaleInterval(beam, 0.09, Vec4(1, 0.95, 0.85, 0.16)),
                                      LerpColorScaleInterval(beam, 0.07, Vec4(1, 0.95, 0.85, 0.22)),
                                      LerpColorScaleInterval(beam, 0.12, Vec4(1, 0.95, 0.85, 0.18)),
                                      Wait(0.05)))

    def teleporterPrompt(self, game, pad):
        role = pad.entry.get('role')
        now = globalClock.getFrameTime()
        if role == 'stage':
            if not game.powerOn:
                return 'The teleporter needs the power on'
            if not self.linked:
                if self.charged:
                    return 'Link the teleporter at the mainframe in the lobby'
                return 'Use: get the teleporter ready'
            if now < self.coolUntil:
                return 'The teleporter is cooling down'
            return 'Use: teleport for %d jellybeans' % 1500
        if role == 'mainframe':
            if game.powerOn and self.charged and not self.linked:
                return 'Use: link the teleporter'
        return ''

    def useTeleporter(self, game, pad):
        role = pad.entry.get('role')
        now = globalClock.getFrameTime()
        if role == 'mainframe':
            if game.powerOn and self.charged and not self.linked:
                self.linked = True
                base.playSfx(base.loader.loadSfx('phase_11/audio/sfx/LB_sparks_1.ogg'), volume=0.7)
                game.hud.say('The teleporter is linked!', 3.0)
                return True
            return False
        if role != 'stage' or not game.powerOn:
            return False
        if not self.linked:
            if not self.charged:
                self.charged = True
                game.hud.say('Now link it at the mainframe in the lobby.', 3.0)
                return True
            return False
        if now < self.coolUntil or self.inBooth:
            return False
        if not game.spend(1500):
            pad.say('Not enough jellybeans!')
            return False
        self.toBooth(game)
        return True

    def toBooth(self, game):
        self.inBooth = True
        game.count('teleports')
        self.boothUntil = globalClock.getFrameTime() + 30.0
        self.warp(game, BOOTH_PAD + Vec3(0, 0, 0.8), -90)
        self.boothTask = self.addTask(self.__boothTick, 'booth')

    def __boothTick(self, task):
        game = self.game
        if game.over:
            return task.done
        if game.paused:
            return task.cont
        left = self.boothUntil - globalClock.getFrameTime()
        self.clockText.node().setText('%d' % max(0, int(left + 0.99)))
        if left > 0:
            return task.cont
        self.clockText.node().setText('')
        self.inBooth = False
        self.coolUntil = globalClock.getFrameTime() + 90.0
        if random.random() < 0.25:
            key, c = random.choice(ROOMS)
            pad = Point3(c[0], c[1] - 5, c[2] + 0.8)
            self.warp(game, pad, 0, then=lambda: Sequence(Wait(5.0), Func(self.warp, game, LOBBY_PAD + Vec3(0, -6, 0), 0)).start())
            game.count('teleport rooms')
        else:
            self.warp(game, LOBBY_PAD + Vec3(0, -6, 0), 0)
        return task.done
