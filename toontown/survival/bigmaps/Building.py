"""What the big indoor maps build their rooms from: walls round a room,
doorways and what fills them (doors, junk, gates, shutters), wall lamps,
teleporter pads, and the flash of a teleport. Textures and colours are the
game's own."""

import math

from direct.interval.IntervalGlobal import Func, Sequence, Wait
from panda3d.core import Point3, TextNode, Vec3

from toontown.survival.bigmaps.BigMap import BigMap
from toontown.survival.previewmaps.MapKit import heading, rng

# Textures (all the game's own).
WALLPAPER = 'phase_3.5/maps/wall_paper_a2.jpg'
WAINSCOT = 'phase_11/maps/LB_WoodPanel2.jpg'
DARK_PANEL = 'phase_11/maps/LB_WoodPanel.jpg'
COFFER = 'phase_12/maps/BQ_WoodPanel.jpg'
MOLDING = 'phase_3.5/maps/molding_wood2.jpg'
CARPET = 'phase_3.5/maps/carpet.jpg'
PLANKS = 'phase_3.5/maps/floor_wood.jpg'
OLD_PLANKS = 'phase_9/maps/WoodPlanks1.jpg'
BOARDS = 'phase_6/maps/outdoor_zone_wood_boards.jpg'
WOOD = 'phase_3.5/maps/wood1.jpg'
MARBLE = 'phase_11/maps/LB_Marble4.jpg'
TILE = 'phase_5.5/maps/tile1_neutral.jpg'
PLASTER = 'phase_5.5/maps/smoothwall_1.jpg'
CEMENT = 'phase_9/maps/WallCement.jpg'
BRICK = 'phase_9/maps/WallBricksBig.jpg'
BRICK2 = 'phase_9/maps/bricks.jpg'
SMALL_BRICK = 'phase_9/maps/WallBricks.jpg'
COBBLE = 'phase_6/maps/brick_floor_grey.jpg'
CURTAIN = 'phase_3.5/maps/rug_string.jpg#solid'
METAL = 'phase_9/maps/WallMetalPlateLargeRivets.jpg'
GRATE = 'phase_9/maps/FloorGrate.jpg'
RUST = 'phase_9/maps/rustyWallStomperRm.jpg'
CEILING = 'phase_11/maps/LB_Ceiling2.jpg'

# Colours: faded, dusty, muted reds and browns.
PAPER = (0.54, 0.43, 0.4, 1)
PAPER_DARK = (0.48, 0.38, 0.36, 1)
PANEL = (0.78, 0.66, 0.58, 1)
RED_CARPET = (0.62, 0.2, 0.18, 1)
OLD_WOOD = (0.72, 0.6, 0.5, 1)
GREY_WOOD = (0.58, 0.54, 0.5, 1)
BRICK_C = (0.78, 0.62, 0.55, 1)
PLASTER_C = (0.8, 0.74, 0.66, 1)
VELVET = (0.72, 0.16, 0.14, 1)
DUSTY = (0.7, 0.66, 0.6, 1)

AMBER = (1.0, 0.72, 0.42)
DIM_AMBER = (0.85, 0.55, 0.32)
COLD = (0.55, 0.62, 0.8)


class Building(BigMap):
    """A BigMap made of rooms."""

    # A box of walls round a rectangle, the room on the inside. ops gives
    # each side's openings as (where along x or y, width, bottom, top),
    # where in the map's own feet, bottom and top over the room's floor.
    def shell(self, x0, y0, x1, y1, z, height, tex, color=PAPER, ops=None, group='static', lower=None, trim=None,
              sides='nsew', outside=None, tile=None, thick=1.0):
        ops = ops or {}
        outside = outside or {}
        if tile is None:
            tile = 6.0 if tex == WALLPAPER else 10.0
        h = thick / 2.0
        self._wallBase = z
        for side in sides:
            if side == 's':
                a, b = (x0 - h, y0 - h), (x1 + h, y0 - h)
                conv = lambda w: w - (x0 - h)
            elif side == 'e':
                a, b = (x1 + h, y0 - h), (x1 + h, y1 + h)
                conv = lambda w: w - (y0 - h)
            elif side == 'n':
                a, b = (x1 + h, y1 + h), (x0 - h, y1 + h)
                conv = lambda w: (x1 + h) - w
            else:
                a, b = (x0 - h, y1 + h), (x0 - h, y0 - h)
                conv = lambda w: (y1 + h) - w
            openings = [(conv(c), w, bo, to) for c, w, bo, to in ops.get(side, ())]
            back = outside.get(side)
            self.wall(a, b, z, z + height, tex, openings, tile=tile, color=color, thick=thick, group=group, lower=lower,
                      faces='both' if back else 'left', backTex=back[0] if back else None, backColor=back[1] if back else None,
                      trim=trim)
        self._wallBase = None

    def threshold(self, x0, y0, x1, y1, z, tex=PLANKS, color=OLD_WOOD, group='static'):
        self.floor(x0, y0, x1, y1, z, tex, tile=6.0, color=color, group=group)

    def leaves(self, entry, tex=DARK_PANEL, color=(0.7, 0.55, 0.45, 1)):
        """A pair of wooden doors filling a doorway (they fade when bought)."""
        a, b = entry['a'], entry['b']
        z0, z1 = entry['z']
        d = Vec3(b - a)
        width = d.length()
        h = math.degrees(math.atan2(d[1], d[0]))
        node = entry['visual']
        node.setPos(Point3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z0))
        node.setH(h)
        for side in (-1, 1):
            leaf = self.boxNode(node, (0, -0.2, 0), (width / 2.0 - 0.05, 0.2, z1 - z0), tex, color=color, tile=4)
            leaf.setX(-width / 2.0 if side < 0 else 0.05)
            knob = self.boxNode(node, (-0.15, -0.35, 3.3), (0.15, 0.35, 3.6), METAL, color=(0.8, 0.7, 0.35, 1), tile=1)
            knob.setX(-0.6 if side < 0 else 0.6)
        # A cost plate over the doors.
        self.doorPlate(node, entry, z1 - z0)

    def junk(self, entry):
        """A heap of broken seats, boards and crates in a doorway."""
        a, b = entry['a'], entry['b']
        z0, z1 = entry['z']
        d = Vec3(b - a)
        width = d.length()
        node = entry['visual']
        node.setPos(Point3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z0))
        node.setH(math.degrees(math.atan2(d[1], d[0])))
        r = rng(int(a[0] * 31 + a[1] * 17))
        for i in range(9):
            x = r.uniform(-width / 2 + 0.8, width / 2 - 0.8)
            z = r.uniform(0, (z1 - z0) * 0.7)
            w = r.uniform(2.5, width * 0.8)
            board = self.boxNode(node, (-w / 2, -0.25, -0.35), (w / 2, 0.25, 0.35), OLD_PLANKS, color=OLD_WOOD, tile=3)
            board.setPos(x, r.uniform(-0.8, 0.8), z + 0.4)
            board.setHpr(r.uniform(-20, 20), r.uniform(-15, 15), r.uniform(-35, 35))
        for i in range(3):
            crate = self.boxNode(node, (-1.2, -1.2, 0), (1.2, 1.2, 2.4), BOARDS, color=GREY_WOOD, tile=2.4)
            crate.setPos(r.uniform(-width / 2 + 1.5, width / 2 - 1.5), r.uniform(-0.6, 0.6), 0 if i < 2 else 2.4)
            crate.setH(r.uniform(-25, 25))
        self.doorPlate(node, entry, 7.0)

    def doorPlate(self, node, entry, height):
        for side, hh in ((-1, 0), (1, 180)):
            tn = TextNode('doorCost')
            from toontown.toonbase import ToontownGlobals
            tn.setFont(ToontownGlobals.getSignFont())
            tn.setAlign(TextNode.ACenter)
            tn.setText(format(entry['cost'], ','))
            tn.setTextColor(1, 0.85, 0.35, 1)
            tn.setShadow(0.05, 0.05)
            tn.setShadowColor(0, 0, 0, 1)
            np = node.attachNewNode(tn)
            np.setPos(0, side * 0.9, min(height, 9.5) + 0.3)
            np.setH(hh)
            np.setScale(0.8)
            np.setLightOff()
            np.setDepthWrite(False)

    def sconce(self, pos, h, group, color=AMBER, reach=26.0, flicker=False, light=True):
        """A brass wall lamp: the Lawbot torch lamp on a little shelf."""
        p = Point3(pos)
        f = heading(h)
        side = Vec3(f[1], -f[0], 0)
        # A brass bracket out of the wall, the lamp standing on it.
        a, b = p + f * 0.05 - side * 0.5, p + f * 1.1 + side * 0.5
        self.kit.box((min(a[0], b[0]), min(a[1], b[1]), p[2] - 0.25), (max(a[0], b[0]), max(a[1], b[1]), p[2]), side=MOLDING,
                     top=MOLDING, tile=1, color=(0.8, 0.62, 0.3, 1), collide=False)
        self.kit.beam(p + Vec3(0, 0, -1.4), p + f * 0.7 + Vec3(0, 0, -0.2), 0.15, MOLDING, color=(0.8, 0.62, 0.3, 1), tile=1)
        self.kit.model('phase_11/models/lawbotHQ/LB_torch_lampA', pos=p + f * 0.6, h=h, scale=0.8, color=(1, 0.92, 0.8, 1))
        if light:
            return self.lamp(p + f * 2.0 + Vec3(0, 0, 1.5), color, reach, groups=(group,), flicker=flicker)
        return None

    def poster(self, pos, h, scale=1.0):
        """A torn old poster: the Cog HQ's Mickey poster, faded."""
        self.kit.model('phase_9/models/cogHQ/poster_mickey', pos=pos, h=h + 90, scale=scale * 3.2, color=(0.85, 0.78, 0.7, 1))

    def pad(self, pos, group, glow=(0.6, 0.85, 1.0)):
        """A teleporter pad: a round grated plate on a riveted base, an
        arch of pipes over it."""
        p = Point3(pos)
        self.kit.cylinder(p, 4.2, 0.7, METAL, sides=24, color=(0.55, 0.55, 0.6, 1), tile=3, cap=GRATE, collide=False, group=group)
        for i in range(12):
            a0, a1 = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
            self.kit.floorPoly([(p[0], p[1], p[2] + 0.7), (p[0] + 4.2 * math.cos(a0), p[1] + 4.2 * math.sin(a0), p[2] + 0.7),
                                (p[0] + 4.2 * math.cos(a1), p[1] + 4.2 * math.sin(a1), p[2] + 0.7)], 'padFloor')
        # Four coils round the rim, each with a glass bulb on top.
        for i in range(4):
            a = 2 * math.pi * i / 4 + math.pi / 4
            post = p + Vec3(math.cos(a) * 4.7, math.sin(a) * 4.7, 0)
            self.kit.cylinder(post, 0.4, 3.2, METAL, sides=10, color=(0.6, 0.6, 0.65, 1), tile=2, collide=True)
            for k in range(4):
                self.kit.cylinder(post + Vec3(0, 0, 0.9 + k * 0.55), 0.55, 0.22, RUST, sides=10, color=(0.95, 0.6, 0.3, 1), tile=1,
                                  collide=False)
            self.kit.cylinder(post + Vec3(0, 0, 3.2), 0.5, 0.8, GRATE, sides=10, color=(glow[0], glow[1], glow[2], 1), tile=1,
                              collide=False, group='glow')

    def gate(self, entry):
        a, b = entry['a'], entry['b']
        z0, z1 = entry['z']
        node = entry['visual']
        node.setPos(Point3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z0))
        node.setH(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
        width = (Vec3(b - a)).length()
        for i in range(int(width / 0.8) + 1):
            x = -width / 2 + i * 0.8
            self.boxNode(node, (x - 0.08, -0.08, 0), (x + 0.08, 0.08, z1 - z0), METAL, color=(0.35, 0.33, 0.32, 1), tile=1)
        for zz in (0.6, (z1 - z0) / 2, z1 - z0 - 0.4):
            self.boxNode(node, (-width / 2, -0.12, zz - 0.15), (width / 2, 0.12, zz + 0.15), METAL, color=(0.35, 0.33, 0.32, 1), tile=2)
        self.doorPlate(node, entry, z1 - z0)

    def shutter(self, entry):
        a, b = entry['a'], entry['b']
        z0, z1 = entry['z']
        node = entry['visual']
        node.setPos(Point3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z0))
        node.setH(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
        width = (Vec3(b - a)).length()
        self.boxNode(node, (-width / 2, -0.2, 0), (width / 2, 0.2, z1 - z0), RUST, color=(0.6, 0.55, 0.5, 1), tile=3)
        for zz in range(1, int(z1 - z0)):
            self.boxNode(node, (-width / 2, -0.3, zz - 0.05), (width / 2, 0.3, zz + 0.05), METAL, color=(0.4, 0.4, 0.4, 1), tile=2)

    def warp(self, game, pos, h, then=None):
        """Out in a flash and in somewhere else."""
        base.playSfx(base.loader.loadSfx('phase_5/audio/sfx/teleport_disappear.ogg'), volume=0.7)
        base.transitions.fadeOut(0.25)

        def arrive():
            game.player.body.setPos(game.arena.root, pos)
            game.player.setLook(h, 0)
            base.transitions.fadeIn(0.35)
            base.playSfx(base.loader.loadSfx('phase_5/audio/sfx/teleport_reappear.ogg'), volume=0.7)
            if then:
                then()
        Sequence(Wait(0.3), Func(arrive)).start()
