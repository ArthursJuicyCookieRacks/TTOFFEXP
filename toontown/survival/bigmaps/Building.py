"""What the big indoor maps build their rooms from: walls round a room,
doorways and what fills them (doors, junk, gates, shutters), wall lamps,
teleporter pads, and the flash of a teleport. Textures and colours are the
game's own."""

import math

from direct.interval.IntervalGlobal import (Func, LerpColorScaleInterval, LerpHprInterval, LerpPosInterval, LerpScaleInterval,
                                            Parallel, Sequence, Wait)
from panda3d.core import Point3, TextNode, TransparencyAttrib, Vec3, Vec4

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
GEAR_SHAFT = 'phase_9/maps/GearShaft2.jpg'
CEILING = 'phase_11/maps/LB_Ceiling2.jpg'
# Detail pictures.
SOFT_SPOT = 'phase_3/maps/drop-shadow.jpg'
SOFT_GLOW = 'phase_4/maps/particleGlow.jpg'
CHECKS = 'phase_10/maps/BlackWhiteChecks.jpg'
CHAIN = 'phase_9/maps/hq_chain.jpg'
MACHINE_PANEL = 'phase_9/maps/pipe_frame4.jpg'
RIVET_PLATE = 'phase_9/maps/CrossBeamx4.jpg'
PIPE_JOINT = 'phase_9/maps/PipeJoint.jpg'
PAPER_TOP = 'phase_11/maps/LB_paper_stacks_top.jpg'
LIGHT_TUBES = 'phase_10/maps/CBStationLightTubes.jpg'
BELT = 'phase_12/maps/ConveyorBelt.jpg'
RAILS = 'phase_5/maps/TracksA.jpg'
DUCT = 'phase_9/maps/Duct3.jpg'

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
            # Not a walk through the walls: the guard starts from here.
            game.player.safePos = game.player.body.getPos()
            game.player.setLook(h, 0)
            base.transitions.fadeIn(0.35)
            base.playSfx(base.loader.loadSfx('phase_5/audio/sfx/teleport_reappear.ogg'), volume=0.7)
            if then:
                then()
        Sequence(Wait(0.3), Func(arrive)).start()

    # --- Detail: what makes a room look lived in. Everything here lies flat
    # on a floor or flat on a wall, or hangs overhead: nothing a toon walks
    # into. (Floor pieces are a few hundredths of a foot thick at most.) ---

    def floorPic(self, center, w, d, tex, group, color=(1, 1, 1, 1), rot=0.0, z=0.0, lift=0.04, uv=None):
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = []
        for dx, dy in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            pts.append((center[0] + dx * cr - dy * sr, center[1] + dx * sr + dy * cr, z + lift))
        self.kit.quad(pts, tex, uv or [(0, 0), (1, 0), (1, 1), (0, 1)], color, group)

    def wallPic(self, pos, h, w, hgt, tex, group, color=(1, 1, 1, 1), off=0.06, uv=None):
        """A flat picture on a wall: pos is its bottom middle on the wall's
        face, h the way it faces (into the room)."""
        f = heading(h)
        right = Vec3(-f[1], f[0], 0)
        c = Point3(pos[0], pos[1], pos[2]) + f * off
        a, b = c - right * (w / 2.0), c + right * (w / 2.0)
        up = Vec3(0, 0, hgt)
        self.kit.quad([a, b, b + up, a + up], tex, uv or [(0, 0), (1, 0), (1, 1), (0, 1)], color, group)

    def grime(self, center, size, group, z=0.0, color=(0.12, 0.1, 0.09, 0.5), rot=0.0, lift=0.04):
        """A dark soft stain on the floor (oil, soot, a damp patch)."""
        self.floorPic(center, size, size * 0.8, SOFT_SPOT, group, color=color, rot=rot, z=z, lift=lift)

    def scatterGrime(self, x0, y0, x1, y1, z, group, n, seed, color=(0.12, 0.1, 0.09, 0.45), size=(2.0, 6.0)):
        r = rng(seed)
        for i in range(n):
            self.grime((r.uniform(x0 + 1, x1 - 1), r.uniform(y0 + 1, y1 - 1)), r.uniform(*size), group, z=z, color=color,
                       rot=r.uniform(0, 180), lift=0.035 + 0.002 * (i % 5))

    def papers(self, x0, y0, x1, y1, z, group, n, seed, color=(0.9, 0.88, 0.82, 1)):
        """Loose sheets of paper about the floor."""
        r = rng(seed)
        for i in range(n):
            w = r.uniform(0.8, 1.3)
            self.floorPic((r.uniform(x0, x1), r.uniform(y0, y1)), w, w * 1.3, PAPER_TOP, group, color=color, rot=r.uniform(0, 180),
                          z=z, lift=0.05 + 0.003 * (i % 4), uv=[(0.1, 0.1), (0.45, 0.1), (0.45, 0.55), (0.1, 0.55)])

    def drain(self, center, size, group, z=0.0, rot=0.0):
        """A grated drain in the floor: dark under the grate."""
        self.floorPic(center, size, size, SOFT_SPOT, group, color=(0.03, 0.03, 0.03, 0.85), rot=rot, z=z, lift=0.03)
        self.floorPic(center, size, size, GRATE, group, color=(0.75, 0.72, 0.7, 1), rot=rot, z=z, lift=0.05,
                      uv=[(0, 0), (2, 0), (2, 2), (0, 2)])

    def hazard(self, a, b, width, group, z=0.0, color=(1, 1, 1, 1)):
        """Black and yellow warning checks painted along the floor."""
        a, b = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        d = b - a
        length = d.length()
        u = d / length
        n = Vec3(-u[1], u[0], 0) * (width / 2.0)
        lift = Vec3(0, 0, z + 0.045)
        reps = length / width
        self.kit.quad([a - n + lift, b - n + lift, b + n + lift, a + n + lift], CHECKS, [(0, 0), (reps, 0), (reps, 1), (0, 1)], color,
                      group)

    def floorCable(self, pts, z, group, color=(0.12, 0.12, 0.13, 1), thick=0.16):
        """A cable snaking over the floor (flat: nobody trips)."""
        for a, b in zip(pts, pts[1:]):
            self.kit.beam((a[0], a[1], z + thick / 2 + 0.01), (b[0], b[1], z + thick / 2 + 0.01), thick, CEMENT, color=color, tile=2,
                          group=group, depth=thick * 0.5)

    def vent(self, pos, h, w, hgt, group, color=(0.7, 0.68, 0.66, 1)):
        """A grille in a wall with dark behind it."""
        self.wallPic(pos, h, w, hgt, SOFT_SPOT, group, color=(0.02, 0.02, 0.02, 0.9), off=0.05)
        self.wallPic(pos, h, w, hgt, GRATE, group, color=color, off=0.08)
        f = heading(h)
        right = Vec3(-f[1], f[0], 0)
        p = Point3(*pos) + f * 0.12
        for a, b in (((-w / 2, 0), (w / 2, 0)), ((-w / 2, hgt), (w / 2, hgt)), ((-w / 2, 0), (-w / 2, hgt)), ((w / 2, 0), (w / 2, hgt))):
            self.kit.beam(p + right * a[0] + Vec3(0, 0, a[1]), p + right * b[0] + Vec3(0, 0, b[1]), 0.18, METAL, color=color,
                          tile=1, group=group)

    def panel(self, pos, h, w, hgt, tex, group, color=(1, 1, 1, 1), frame=None):
        """A flat plate on a wall (riveted steel, a machine's face)."""
        self.wallPic(pos, h, w, hgt, tex, group, color=color, off=0.07)
        if frame:
            f = heading(h)
            right = Vec3(-f[1], f[0], 0)
            p = Point3(*pos) + f * 0.1
            for a, b in (((-w / 2, 0), (w / 2, 0)), ((-w / 2, hgt), (w / 2, hgt)), ((-w / 2, 0), (-w / 2, hgt)),
                         ((w / 2, 0), (w / 2, hgt))):
                self.kit.beam(p + right * a[0] + Vec3(0, 0, a[1]), p + right * b[0] + Vec3(0, 0, b[1]), 0.15, METAL, color=frame,
                              tile=1, group=group)

    def sign(self, pos, h, text, group, plate=(0.86, 0.7, 0.18, 1), ink=(0.12, 0.08, 0.06, 1), w=None, scale=0.85, tex=CEMENT):
        """A painted warning sign on a wall."""
        lines = text.split('\n')
        w = w or max(len(l) for l in lines) * scale * 0.62 + 0.8
        hgt = len(lines) * scale * 1.15 + 0.5
        self.wallPic((pos[0], pos[1], pos[2] - hgt / 2), h, w, hgt, tex, group, color=plate, off=0.07)
        f = heading(h)
        np = self.text(text, Point3(pos[0], pos[1], pos[2] + hgt / 2 - 0.25 - scale * 0.8) + f * 0.12, h + 180, scale,
                       color=ink, font='sign')
        return np

    def conduit(self, pos, h, z0, z1, group, color=(0.5, 0.48, 0.46, 1), box=True):
        """A pipe up a wall, a junction box on it."""
        f = heading(h)
        p = Point3(pos[0], pos[1], 0) + f * 0.3
        self.kit.beam((p[0], p[1], z0), (p[0], p[1], z1), 0.32, GEAR_SHAFT, color=color, tile=2, group=group)
        if box:
            zb = z0 + (z1 - z0) * 0.45
            q = Point3(pos[0], pos[1], zb) + f * 0.35
            self.kit.beam(q - Vec3(0, 0, 0.6), q + Vec3(0, 0, 0.6), 1.0, METAL, color=color, tile=1, group=group, depth=0.6)

    def chainHang(self, top, length, group, color=(0.7, 0.68, 0.66, 1)):
        """A chain hanging from the ceiling (two crossed cards)."""
        x, y, z = top
        for dx, dy in ((0.25, 0), (0, 0.25)):
            self.kit.quad([(x - dx, y - dy, z - length), (x + dx, y + dy, z - length), (x + dx, y + dy, z), (x - dx, y - dy, z)], CHAIN,
                          [(0, 0), (1, 0), (1, length / 0.5), (0, length / 0.5)], color, group)
            self.kit.quad([(x + dx, y + dy, z - length), (x - dx, y - dy, z - length), (x - dx, y - dy, z), (x + dx, y + dy, z)], CHAIN,
                          [(0, 0), (1, 0), (1, length / 0.5), (0, length / 0.5)], color, group)

    # --- Things that move: the room is alive. They hang off the map's root,
    # not the flattened scenery, and stop when the map goes. ---

    def keepLooping(self, ival):
        if not hasattr(self, 'loops'):
            self.loops = []
        self.loops.append(ival)
        ival.loop()
        return ival

    def spinningGear(self, pos, h, size, seconds, color=(0.8, 0.76, 0.72, 1), backwards=False):
        """A cog wheel turning on a wall (the Mint's gear)."""
        holder = self.root.attachNewNode('wallGear')
        holder.setPos(Point3(*pos) + heading(h) * 0.25)
        holder.setH(h)
        upright = holder.attachNewNode('upright')
        upright.setP(90)
        gear = self.kit.model('phase_10/models/cashbotHQ/MintGear', parent=upright, scale=size / 2.0, color=color)
        self.keepLooping(LerpHprInterval(gear, seconds, Vec3(-360 if backwards else 360, 0, 0), startHpr=Vec3(0, 0, 0)))
        return holder

    def blinker(self, pos, h, color, on=0.6, off=0.6, size=0.35, phase=0.0):
        """A little lamp on a panel blinking."""
        node = self.root.attachNewNode('blinker')
        node.setPos(Point3(*pos) + heading(h) * 0.12)
        node.setH(h)
        self.boxNode(node, (-size / 2, -0.1, -size / 2), (size / 2, 0.1, size / 2), CEMENT, color=(1, 1, 1, 1), tile=1)
        node.setLightOff(1)
        dim = Vec4(color[0] * 0.25, color[1] * 0.25, color[2] * 0.25, 1)
        lit = Vec4(color[0] * 3.0, color[1] * 3.0, color[2] * 3.0, 1)
        node.setColorScale(dim)
        self.keepLooping(Sequence(Wait(phase), Func(node.setColorScale, lit), Wait(on), Func(node.setColorScale, dim), Wait(off)))
        return node

    def steam(self, pos, every=2.2, size=2.5, rise=6.0, color=(0.85, 0.85, 0.85, 0.5)):
        """Puffs of steam (or smoke) drifting up and fading."""
        proto = self.kit.models.get('phase_4/models/props/tt_m_efx_smoke')
        if proto is None:
            proto = self.kit.models['phase_4/models/props/tt_m_efx_smoke'] = loader.loadModel('phase_4/models/props/tt_m_efx_smoke')
        p = Point3(*pos)
        ivals = []
        for k in range(3):
            puff = proto.copyTo(self.root)
            puff.setBillboardPointEye()
            puff.setTransparency(TransparencyAttrib.MAlpha)
            puff.setDepthWrite(False)
            puff.setLightOff(1)
            puff.setBin('fixed', 5)
            puff.setPos(p)
            puff.setScale(0.01)
            c0 = Vec4(color[0], color[1], color[2], color[3])
            c1 = Vec4(color[0], color[1], color[2], 0)
            one = Sequence(Func(puff.setPos, p), Func(puff.setScale, size * 0.3),
                           Parallel(LerpPosInterval(puff, every * 3, p + Vec3(0.6, 0.3, rise)),
                                    LerpScaleInterval(puff, every * 3, size, startScale=size * 0.3),
                                    LerpColorScaleInterval(puff, every * 3, c1, startColorScale=c0)))
            self.keepLooping(one)
            one.setT(every * k)
            ivals.append(one)
        return ivals

    def swingingLamp(self, top, length, group, color=(1.0, 0.8, 0.5), angle=4.0, seconds=3.0, reach=24.0):
        """A shaded bulb on a cord, swaying a little."""
        pivot = self.root.attachNewNode('swingLamp')
        pivot.setPos(Point3(*top))
        self.boxNode(pivot, (-0.05, -0.05, -length), (0.05, 0.05, 0), CEMENT, color=(0.1, 0.1, 0.1, 1), tile=1)
        shade = pivot.attachNewNode('shade')
        shade.setZ(-length)
        self.kit.model('phase_11/models/lawbotHQ/LB_torch_lampB', parent=shade, pos=(0, 0, -0.2), scale=(0.35, 0.35, 0.06),
                       color=(0.5, 0.48, 0.45, 1))
        bulb = self.boxNode(shade, (-0.25, -0.25, -0.75), (0.25, 0.25, -0.25), CEMENT, color=(1, 1, 1, 1), tile=1)
        bulb.setLightOff(1)
        bulb.setColorScale(color[0] * 3, color[1] * 3, color[2] * 3, 1)
        self.keepLooping(Sequence(LerpHprInterval(pivot, seconds / 2, Vec3(0, angle, angle * 0.5), startHpr=Vec3(0, -angle, -angle * 0.5),
                                                  blendType='easeInOut'),
                                  LerpHprInterval(pivot, seconds / 2, Vec3(0, -angle, -angle * 0.5), startHpr=Vec3(0, angle, angle * 0.5),
                                                  blendType='easeInOut')))
        return self.lamp(Point3(top[0], top[1], top[2] - length - 0.8), color, reach, groups=(group,))

    # --- Second pass: structure overhead and along the walls ---

    def ceilingBeams(self, x0, y0, x1, y1, z, group, every=8.0, axis='x', depth=1.2, color=(0.4, 0.4, 0.42, 1), tex=None):
        """Steel beams just under a ceiling, every `every` feet."""
        tex = tex or METAL
        if axis == 'x':
            y = y0 + every / 2.0
            while y < y1:
                self.kit.beam((x0, y, z - depth / 2), (x1, y, z - depth / 2), 0.7, tex, color=color, tile=3, group=group, depth=depth)
                y += every
        else:
            x = x0 + every / 2.0
            while x < x1:
                self.kit.beam((x, y0, z - depth / 2), (x, y1, z - depth / 2), 0.7, tex, color=color, tile=3, group=group, depth=depth)
                x += every

    def duct(self, a, b, z, size, group, color=(0.62, 0.62, 0.64, 1)):
        """An air duct run overhead, banded every few feet."""
        a3, b3 = Vec3(a[0], a[1], z), Vec3(b[0], b[1], z)
        self.kit.beam(a3, b3, size, DUCT, color=color, tile=4, group=group)
        d = b3 - a3
        n = int(d.length() / 6.0)
        for i in range(1, n + 1):
            p = a3 + d * (float(i) / (n + 1))
            u = Vec3(d)
            u.normalize()
            self.kit.beam(p - u * 0.2, p + u * 0.2, size + 0.25, METAL, color=(0.45, 0.45, 0.47, 1), tile=1, group=group)

    def tubeLight(self, pos, h, group, length=6.0, flicker=False):
        """A strip light hanging under the ceiling: a housing and a glowing
        tube (one in a few flickers)."""
        x, y, z = pos
        f = heading(h)
        a, b = Point3(x, y, z) - f * (length / 2), Point3(x, y, z) + f * (length / 2)
        self.kit.beam(a + Vec3(0, 0, 0.25), b + Vec3(0, 0, 0.25), 0.9, METAL, color=(0.35, 0.35, 0.37, 1), tile=2, group=group,
                      depth=0.35)
        node = self.root.attachNewNode('tube')
        node.setPos(Point3(x, y, z))
        node.setH(h)
        self.boxNode(node, (-0.25, -length / 2 + 0.2, -0.12), (0.25, length / 2 - 0.2, 0.08), CEMENT, color=(1, 1, 1, 1), tile=1)
        node.setLightOff(1)
        lit, off = Vec4(2.6, 2.7, 2.5, 1), Vec4(0.5, 0.5, 0.5, 1)
        node.setColorScale(lit)
        if flicker:
            r = rng(int(x * 13 + y * 7))
            self.keepLooping(Sequence(Wait(1.5 + r.random() * 3), Func(node.setColorScale, off), Wait(0.07),
                                      Func(node.setColorScale, lit), Wait(0.1), Func(node.setColorScale, off), Wait(0.3 + r.random() * 0.6),
                                      Func(node.setColorScale, lit), Wait(0.05), Func(node.setColorScale, off), Wait(0.05),
                                      Func(node.setColorScale, lit)))
        return node

    def floorSeams(self, x0, y0, x1, y1, z, group, every=8.0, color=(0.08, 0.08, 0.08, 0.5)):
        """Dark joins between the floor's plates or slabs."""
        x = x0 + every
        while x < x1 - 0.5:
            self.floorPic((x, (y0 + y1) / 2.0), 0.18, y1 - y0, SOFT_GLOW, group, color=color, z=z, lift=0.032)
            x += every
        y = y0 + every
        while y < y1 - 0.5:
            self.floorPic(((x0 + x1) / 2.0, y), x1 - x0, 0.18, SOFT_GLOW, group, color=color, z=z, lift=0.033)
            y += every

    def rails(self, a, b, group, z=0.0):
        """Cart rails set into the floor."""
        a3, b3 = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        d = b3 - a3
        length = d.length()
        u = d / length
        n = Vec3(-u[1], u[0], 0) * 1.2
        lift = Vec3(0, 0, z + 0.04)
        self.kit.quad([a3 - n + lift, b3 - n + lift, b3 + n + lift, a3 + n + lift], RAILS, [(0, 0), (0, length / 2.4), (1, length / 2.4), (1, 0)],
                      (0.75, 0.72, 0.7, 1), group)

    def ladder(self, pos, h, z0, z1, group, color=(0.45, 0.45, 0.47, 1)):
        """A steel ladder up a wall (flat against it)."""
        f = heading(h)
        side = Vec3(-f[1], f[0], 0)
        p = Point3(pos[0], pos[1], 0) + f * 0.35
        for s_ in (-0.8, 0.8):
            q = p + side * s_
            self.kit.beam((q[0], q[1], z0), (q[0], q[1], z1), 0.15, METAL, color=color, tile=1, group=group)
        zz = z0 + 0.8
        while zz < z1:
            self.kit.beam(p - side * 0.8 + Vec3(0, 0, zz), p + side * 0.8 + Vec3(0, 0, zz), 0.1, METAL, color=color, tile=1, group=group)
            zz += 1.0

    def pillars(self, a, b, every, z0, z1, group, h, tex=None, color=(0.5, 0.5, 0.52, 1), width=1.2, depth=0.7):
        """Pillars standing flat against a wall from a to b, sticking out
        `depth` feet toward h (into the room)."""
        tex = tex or METAL
        a3, b3 = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        d = b3 - a3
        length = d.length()
        u = d / length
        f = heading(h)
        t = every / 2.0
        while t < length:
            c = a3 + u * t + f * (depth / 2.0)
            lo = (min(c[0] - abs(u[0]) * width / 2 - abs(f[0]) * depth / 2, c[0] + abs(u[0]) * width / 2 + abs(f[0]) * depth / 2),
                  min(c[1] - abs(u[1]) * width / 2 - abs(f[1]) * depth / 2, c[1] + abs(u[1]) * width / 2 + abs(f[1]) * depth / 2))
            hi = (max(c[0] - abs(u[0]) * width / 2 - abs(f[0]) * depth / 2, c[0] + abs(u[0]) * width / 2 + abs(f[0]) * depth / 2),
                  max(c[1] - abs(u[1]) * width / 2 - abs(f[1]) * depth / 2, c[1] + abs(u[1]) * width / 2 + abs(f[1]) * depth / 2))
            self.kit.box((lo[0], lo[1], z0), (hi[0], hi[1], z1), side=tex, top=tex, tile=3, color=color, collide='wall', group=group)
            t += every

    def ceilingFan(self, pos, group, size=3.0, seconds=1.6):
        """A fan under the ceiling, turning."""
        x, y, z = pos
        self.kit.beam((x, y, z), (x, y, z - 1.2), 0.15, METAL, color=(0.3, 0.3, 0.32, 1), tile=1, group=group)
        hub = self.root.attachNewNode('fan')
        hub.setPos(x, y, z - 1.3)
        self.boxNode(hub, (-0.35, -0.35, -0.3), (0.35, 0.35, 0.1), METAL, color=(0.4, 0.38, 0.36, 1), tile=1)
        for i in range(4):
            blade = hub.attachNewNode('blade')
            blade.setH(90 * i)
            self.boxNode(blade, (0.3, -0.3, -0.12), (size, 0.3, -0.06), WOOD, color=(0.5, 0.42, 0.35, 1), tile=2)
        self.keepLooping(LerpHprInterval(hub, seconds, Vec3(360, 0, 0), startHpr=Vec3(0, 0, 0)))
        return hub

    def conveyor(self, a, b, z, group, items=None, width=3.0, height=3.0, seconds=10.0, count=5):
        """A conveyor belt along a wall from a to b carrying things along.
        The belt has a solid side (it stands against the wall); the treads
        scroll and the things on it ride from one end to the other."""
        from direct.interval.IntervalGlobal import LerpFunctionInterval
        a3, b3 = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        d = b3 - a3
        length = d.length()
        u = d / length
        n = Vec3(-u[1], u[0], 0) * (width / 2.0)
        hgt = Vec3(0, 0, z + height)
        # The frame (with legs) and the solid it makes.
        corners = [a3 - n, b3 - n, b3 + n, a3 + n]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        self.kit.box((min(xs), min(ys), z), (max(xs), max(ys), z + height - 0.25), side=METAL, top=None, tile=3,
                     color=(0.36, 0.36, 0.38, 1), collide='wall', group=group)
        for side in (-1, 1):
            p0, p1 = a3 + n * side * 1.08, b3 + n * side * 1.08
            self.kit.beam(p0 + hgt, p1 + hgt, 0.22, METAL, color=(0.85, 0.7, 0.2, 1), tile=2, group=group, depth=0.5)
        # The treads, scrolling.
        belt = self.root.attachNewNode('belt')
        from toontown.survival.previewmaps.MapKit import Mesh
        m = Mesh()
        top = Vec3(0, 0, z + height - 0.05)
        m.quad([a3 - n + top, b3 - n + top, b3 + n + top, a3 + n + top], [(0, 0), (length / 3.0, 0), (length / 3.0, 1), (0, 1)],
               Vec4(0.8, 0.8, 0.8, 1))
        np = belt.attachNewNode(m.node('belt'))
        np.setTexture(self.kit.tex(BELT), 1)
        stage = np.findTextureStage('*') or None
        from panda3d.core import TextureStage
        ts = TextureStage.getDefault()

        def scroll(t, np=np, ts=ts):
            np.setTexOffset(ts, -t, 0)
        self.keepLooping(LerpFunctionInterval(scroll, duration=seconds / (length / 3.0) * 1.0, fromData=0, toData=1))
        # What rides on it.
        items = items or ['phase_3.5/models/props/tart']
        for k in range(count):
            path = items[k % len(items)]
            rider = self.root.attachNewNode('rider')
            self.kit.model(path, parent=rider, scale=1.0)
            rider.setH(math.degrees(math.atan2(u[1], u[0])) - 90)
            start, end = a3 + top + Vec3(0, 0, 0.05), b3 + top + Vec3(0, 0, 0.05)
            ival = Sequence(LerpPosInterval(rider, seconds, end, startPos=start))
            self.keepLooping(ival)
            ival.setT(seconds * k / float(count))
        return belt

    def trolley(self, a, b, z, group, seconds=14.0, load=None):
        """An overhead crane trolley running along a rail, a load swinging
        on its chain, back and forth all game (high over everyone)."""
        a3, b3 = Point3(a[0], a[1], z), Point3(b[0], b[1], z)
        self.kit.beam(a3 + Vec3(0, 0, 0.6), b3 + Vec3(0, 0, 0.6), 0.9, METAL, color=(0.85, 0.7, 0.2, 1), tile=3, group=group, depth=1.0)
        car = self.root.attachNewNode('trolley')
        self.boxNode(car, (-1.2, -1.0, -0.6), (1.2, 1.0, 0.1), METAL, color=(0.4, 0.4, 0.42, 1), tile=1)
        hang = car.attachNewNode('hang')
        hang.setZ(-0.6)
        self.boxNode(hang, (-0.08, -0.08, -5.0), (0.08, 0.08, 0), METAL, color=(0.25, 0.25, 0.25, 1), tile=1)
        self.kit.model(load or 'phase_9/models/cogHQ/metal_crateB', parent=hang, pos=(0, 0, -8.0), scale=0.5, color=(0.8, 0.78, 0.75, 1))
        car.setPos(a3)
        self.keepLooping(Sequence(LerpPosInterval(car, seconds / 2, b3, startPos=a3, blendType='easeInOut'), Wait(1.5),
                                  LerpPosInterval(car, seconds / 2, a3, startPos=b3, blendType='easeInOut'), Wait(1.5)))
        self.keepLooping(Sequence(LerpHprInterval(hang, 1.6, Vec3(0, 3, 0), startHpr=Vec3(0, -3, 0), blendType='easeInOut'),
                                  LerpHprInterval(hang, 1.6, Vec3(0, -3, 0), startHpr=Vec3(0, 3, 0), blendType='easeInOut')))
        return car

    def destroy(self):
        for ival in getattr(self, 'loops', ()):
            ival.finish()
        self.loops = []
        BigMap.destroy(self)
