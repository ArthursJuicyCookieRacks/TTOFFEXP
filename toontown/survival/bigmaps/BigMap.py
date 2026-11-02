"""The big Survival maps: buildings with rooms, floors and doors.

The other maps are one open space that cogs fall into from the sky. A big
map is a building (or a compound of them) split into zones: the player
starts in one, buys doors to open the next, turns on the power, and the
cogs come in through boarded windows, holes in the ceiling and off the
roofs of the zones that are open, the way Black Ops 1's maps work.

A map here is built in code from the game's own models and textures (the
preview maps' MapKit) and, while it builds, registers everything that
does something: doors, windows, the power switch and what it opens, wall
gags, tonic machines, traps, turrets, teleporters and the trunk's spots.
SurvivalGame turns those into stations (bigmaps/Fixtures.py) and
SurvivalArena finds its way over the floors with bigmaps/LayeredNav.py.
"""

import math

from panda3d.core import (BitMask32, CollisionBox, CollisionCapsule, CollisionNode, CollisionSphere, NodePath, Point3, PointLight, TextNode, TransparencyAttrib,
                          Vec3, Vec4)

from toontown.survival.previewmaps.MapKit import FLOOR, WALL, CAMERA, Mesh, heading, rng
from toontown.survival.previewmaps.PreviewMap import PreviewMap
from toontown.toonbase import ToontownGlobals


def capsuleWall(node, length, thick, z0, z1):
    """The solid of a straight wall along x (centred on 0), thick through,
    from z0 to z1: rounded bars lying along it, stacked so they overlap.
    Not a CollisionBox: a box let a toon sink into it at a corner or a
    slant and held it there, or threw it out through the far side
    (Arthur: stuck all over the theater)."""
    r = max(0.3, thick / 2.0)
    half = length / 2.0 - r
    if z1 - z0 < 2 * r:
        z0, z1 = (z0 + z1) / 2.0 - r, (z0 + z1) / 2.0 + r
    z = z0 + r
    while True:
        if half > 0.01:
            node.addSolid(CollisionCapsule(Point3(-half, 0, z), Point3(half, 0, z), r))
        else:
            node.addSolid(CollisionSphere(0, 0, z, max(r, length / 2.0)))
        if z >= z1 - r - 1e-4:
            break
        z = min(z1 - r, z + r * 1.6)


class Zone:

    def __init__(self, name, title, boxes, startOpen=False):
        self.name = name
        self.title = title
        # (x0, y0, z0, x1, y1, z1) boxes.
        self.boxes = boxes
        self.startOpen = startOpen

    def contains(self, p):
        for x0, y0, z0, x1, y1, z1 in self.boxes:
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 - 1 <= p[2] <= z1:
                return True
        return False


class Spawner:
    """Where a cog comes in: 'window' (it flies up outside a boarded window
    and tears the boards off), 'ceiling' (it drops through a hole), 'roof'
    (it lands on a roof's edge and jumps down) or 'sky' (an open yard)."""

    def __init__(self, kind, zone, pos, h=0.0, inside=None, top=None, window=None):
        self.kind = kind
        self.zone = zone
        self.pos = Point3(pos)
        self.h = h
        self.inside = Point3(inside) if inside is not None else Point3(pos)
        self.top = Point3(top) if top is not None else None
        self.window = window


class BigMap(PreviewMap):
    BIG = True
    NAV_STEP = 3.0
    NAV_TOP = 80.0
    NAV_LOWEST = -20.0
    REACH_CENTER = Point3(0, 0, 0)
    # The upgrade: ('char', code, name) or ('npc', npc id, name).
    UPGRADER = ('char', 'mk', 'Mickey')
    MICKEY_SCALE = 1.0
    FISHERMAN_SPOT = None
    # Where each room's own lamps glow (pos, colour, reach).
    CAMERA_FAR = 600.0

    def __init__(self, root):
        self.zones = []
        self.spawners = []
        self.doors = []
        self.windows = []
        self.powerGates = []
        self.wallGags = []
        self.tonics = []
        self.traps = []
        self.turrets = []
        self.teleporters = []
        self.extras = []
        self.boxSpots = []
        self.navLinks = []
        self.powerSwitch = None
        self.lamps = []
        self.flickers = []
        self.dynamic = []
        # Nav blockers that are areas (a bridge that comes down): (name,
        # (x0, y0, x1, y1), (z0, z1)); solids shut now that open later; and
        # solids that only come later (the bridge's floor).
        self.navAreas = []
        self.shutSolids = []
        self.laterSolids = []
        PreviewMap.__init__(self, root)
        # The trunk starts on the box spot marked start.
        for spot in self.boxSpots:
            if spot['start']:
                self.TRUNK_SPOT = (Point3(spot['pos']), spot['h'])

    # --- Registering what does something ---

    def zone(self, name, title, *boxes, **kw):
        z = Zone(name, title, list(boxes), kw.get('startOpen', False))
        self.zones.append(z)
        return z

    def zoneAt(self, p):
        best = None
        for z in self.zones:
            if z.contains(p):
                best = z
        return best

    def door(self, name, cost, a, b, z0, z1, zones, kind='door', title=None, usePoints=None, power=False):
        """A doorway shut until bought (or, power=True, until the power
        comes on): a line across the floor from a to b, between z0 and z1.
        Its look is whatever the map puts in self.doorVisual(name) before
        finish; the solid wall across it comes from here."""
        node = CollisionNode('door-' + name)
        node.setIntoCollideMask(WALL | CAMERA)
        node.setFromCollideMask(BitMask32.allOff())
        a3, b3 = Vec3(a[0], a[1], 0), Vec3(b[0], b[1], 0)
        d = b3 - a3
        length = d.length()
        capsuleWall(node, length, 1.2, z0, z1)
        solid = self.kit.solid.attachNewNode(node)
        mid = (a3 + b3) / 2.0
        solid.setPos(mid[0], mid[1], 0)
        solid.setH(math.degrees(math.atan2(d[1], d[0])))
        visual = self.root.attachNewNode('doorVisual-' + name)
        entry = {'name': name, 'cost': cost, 'a': Point3(a[0], a[1], z0), 'b': Point3(b[0], b[1], z0), 'z': (z0, z1),
                 'zones': zones, 'solid': solid, 'visual': visual, 'kind': kind, 'title': title or 'the door',
                 'power': power, 'usePoints': usePoints}
        if power:
            self.powerGates.append(entry)
        else:
            self.doors.append(entry)
        return entry

    def window(self, zone, pos, h, width=6.0, sill=2.0, height=6.0, boards=6, hover=False, wallTex=None):
        """A boarded window in a wall, facing heading h (into the room). The
        wall's own hole is the map's to leave; this puts in the frame, the
        boards, the solid across it and the spawner outside."""
        f = heading(h)
        right = Vec3(f[1], -f[0], 0)
        p = Point3(pos)
        win = {'zone': zone, 'pos': p, 'h': h, 'width': width, 'sill': sill, 'height': height, 'boards': boards}
        # Solid for toons: nobody climbs out (cogs are moved through by hand).
        node = CollisionNode('window')
        node.setIntoCollideMask(WALL | CAMERA)
        node.setFromCollideMask(BitMask32.allOff())
        capsuleWall(node, width, 1.4, -sill - 0.5, height + 0.5)
        np = self.kit.solid.attachNewNode(node)
        np.setPos(p[0], p[1], p[2] + sill)
        np.setH(h)
        # The frame: dark wood round the opening.
        frameTex = 'phase_3.5/maps/wood1.jpg'
        c = (0.42, 0.3, 0.22, 1)
        for side in (-1, 1):
            q = p + right * (side * (width / 2.0 + 0.25))
            self.kit.box((q[0] - 0.3, q[1] - 0.3, p[2] + sill), (q[0] + 0.3, q[1] + 0.3, p[2] + sill + height), side=frameTex, top=frameTex,
                         tile=3, color=c, collide=False)
        lo = p - right * (width / 2.0 + 0.55)
        hi = p + right * (width / 2.0 + 0.55)
        for zz in (p[2] + sill - 0.35, p[2] + sill + height):
            self.kit.beam((lo[0], lo[1], zz), (hi[0], hi[1], zz), 0.5, frameTex, color=c, tile=3)
        win['inside'] = Point3(p + f * 3.0)
        win['outside'] = Point3(p - f * 3.5)
        win['hover'] = hover
        self.windows.append(win)
        self.spawners.append(Spawner('window', zone, win['outside'], h, inside=win['inside'], window=win))
        return win

    def ceilingHole(self, zone, pos, height):
        """A cog drops through a hole in the ceiling at pos (on the floor)."""
        self.spawners.append(Spawner('ceiling', zone, pos, top=Point3(pos[0], pos[1], pos[2] + height)))

    def roofEdge(self, zone, top, landing, h=0.0):
        """A cog lands on a roof's edge at top and jumps down to landing."""
        self.spawners.append(Spawner('roof', zone, landing, h, top=top))

    def skySpawn(self, zone, pos):
        self.spawners.append(Spawner('sky', zone, pos))

    def wallGag(self, key, pos, h, cost, zone):
        """A gag hung on the wall for sale. key is (track, level) or a
        special: 'tnt', 'rake', 'marbles', 'cane'."""
        self.wallGags.append({'key': key, 'pos': Point3(pos), 'h': h, 'cost': cost, 'zone': zone})

    def tonic(self, key, pos, h, cost=None, needsPower=True):
        # The machine is solid (the way-finding sees it too).
        self.kit.wallTube(pos, 1.9, 7.0)
        self.tonics.append({'key': key, 'pos': Point3(pos), 'h': h, 'cost': cost, 'power': needsPower})

    def trap(self, name, kind, area, switch, switchH, cost=1000, z=(0, 12), line=None):
        """kind 'electric' or 'fire'. area (x0, y0, x1, y1) on the floor
        between heights z; line (a, b) is where the bolts or flames are
        drawn (across the doorway)."""
        self.traps.append({'name': name, 'kind': kind, 'area': area, 'switch': Point3(switch), 'h': switchH, 'cost': cost,
                           'z': z, 'line': line})

    def turret(self, pos, h, button, buttonH, cost=1500):
        # The button stands on a little post.
        b = Point3(button)
        self.kit.box((b[0] - 0.35, b[1] - 0.35, b[2]), (b[0] + 0.35, b[1] + 0.35, b[2] + 3.0), side='phase_9/maps/WallMetalPlateLargeRivets.jpg',
                     top='phase_9/maps/WallMetalPlateLargeRivets.jpg', tile=2, color=(0.45, 0.45, 0.48, 1), collide='wall')
        self.turrets.append({'pos': Point3(pos), 'h': h, 'button': Point3(button), 'buttonH': buttonH, 'cost': cost})

    def teleporter(self, name, pos, h, **kw):
        entry = {'name': name, 'pos': Point3(pos), 'h': h}
        entry.update(kw)
        self.teleporters.append(entry)
        return entry

    def boxSpot(self, name, pos, h, start=False):
        self.boxSpots.append({'name': name, 'pos': Point3(pos), 'h': h, 'start': start})

    def drop(self, high, low):
        """Toons can drop from high to low; cogs fly both ways."""
        self.navLinks.append((Point3(high), Point3(low), 'drop'))

    def switch(self, pos, h):
        """The power switch."""
        self.powerSwitch = (Point3(pos), h)

    # --- In the game ---

    def startGame(self, game):
        """The game has its stations: the map's own start (sounds)."""
        self.game = game

    def setPower(self, on):
        """The map's own show when the power comes on (lights, curtains)."""
        pass

    def teleporterPrompt(self, game, pad):
        return ''

    def useTeleporter(self, game, pad):
        return False

    def upgradeOpen(self, game):
        return True

    # --- Building helpers ---

    def area(self, name):
        """Geometry for one room goes in its own group, lit by its own lamps."""
        return name

    def lamp(self, pos, color=(1.0, 0.78, 0.45), reach=40.0, groups=(), flicker=False):
        light = PointLight('lamp')
        light.setColor(Vec4(color[0], color[1], color[2], 1))
        light.setAttenuation(Vec3(0.6, 0.0, 1.6 / (reach * reach)))
        np = self.root.attachNewNode(light)
        np.setPos(Point3(pos))
        self.lamps.append((np, tuple(groups), Vec4(color[0], color[1], color[2], 1)))
        if flicker:
            self.flickers.append(np)
        return np

    def solidBox(self, lo, hi):
        return self.kit.wallBox(lo, hi)

    def floor(self, x0, y0, x1, y1, z, tex, tile=8.0, color=(1, 1, 1, 1), group='static', thick=0.0, under=None, name='floor'):
        """A floor at height z (and its underside, for upper floors)."""
        self.kit.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], tex,
                      [(x0 / tile, y0 / tile), (x1 / tile, y0 / tile), (x1 / tile, y1 / tile), (x0 / tile, y1 / tile)], color, group)
        self.kit.floorPoly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], name)
        if thick > 0:
            zb = z - thick
            ut = under or tex
            self.kit.quad([(x0, y1, zb), (x1, y1, zb), (x1, y0, zb), (x0, y0, zb)], ut,
                          [(x0 / tile, y1 / tile), (x1 / tile, y1 / tile), (x1 / tile, y0 / tile), (x0 / tile, y0 / tile)], color, group)
            for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                self.kit.quad([(a[0], a[1], zb), (b[0], b[1], zb), (b[0], b[1], z), (a[0], a[1], z)], ut,
                              [(0, 0), (1, 0), (1, thick / tile), (0, thick / tile)], color, group)
                self.kit.quad([(b[0], b[1], zb), (a[0], a[1], zb), (a[0], a[1], z), (b[0], b[1], z)], ut,
                              [(0, 0), (1, 0), (1, thick / tile), (0, thick / tile)], color, group)

    def ceiling(self, x0, y0, x1, y1, z, tex, tile=10.0, color=(1, 1, 1, 1), group='static', holes=()):
        """A ceiling facing down, no collisions; holes are (x0, y0, x1, y1)
        cut out (a broken ceiling)."""
        rects = [(x0, y0, x1, y1)]
        for hx0, hy0, hx1, hy1 in holes:
            out = []
            for rx0, ry0, rx1, ry1 in rects:
                if hx1 <= rx0 or hx0 >= rx1 or hy1 <= ry0 or hy0 >= ry1:
                    out.append((rx0, ry0, rx1, ry1))
                    continue
                if hy0 > ry0:
                    out.append((rx0, ry0, rx1, hy0))
                if hy1 < ry1:
                    out.append((rx0, hy1, rx1, ry1))
                cy0, cy1 = max(ry0, hy0), min(ry1, hy1)
                if hx0 > rx0:
                    out.append((rx0, cy0, hx0, cy1))
                if hx1 < rx1:
                    out.append((hx1, cy0, rx1, cy1))
            rects = out
        for rx0, ry0, rx1, ry1 in rects:
            self.kit.quad([(rx0, ry1, z), (rx1, ry1, z), (rx1, ry0, z), (rx0, ry0, z)], tex,
                          [(rx0 / tile, ry1 / tile), (rx1 / tile, ry1 / tile), (rx1 / tile, ry0 / tile), (rx0 / tile, ry0 / tile)], color, group)

    def wall(self, a, b, z0, z1, tex, openings=(), tile=10.0, color=(1, 1, 1, 1), thick=1.0, group='static', lower=None,
             faces='both', collide=True, backTex=None, backColor=None, trim=None):
        """A straight wall along the floor from a to b (x or y aligned or
        not), z0 to z1, thick feet thick, with openings cut in it:
        (centre along the wall from a, width, bottom, top) in feet from z0.
        lower = (tex, height, color): a wainscot below the wallpaper.
        faces: 'both', 'left' or 'right' (the side to the left walking a
        to b). trim = (tex, color): a strip along the top of the wainscot."""
        a = Vec3(a[0], a[1], 0)
        b = Vec3(b[0], b[1], 0)
        d = b - a
        length = d.length()
        if length < 0.01:
            return
        u = d / length
        n = Vec3(-u[1], u[0], 0)
        height = z1 - z0
        # The solid pieces: split along the wall by the openings.
        pieces = []
        cuts = sorted(openings, key=lambda o: o[0])
        x = 0.0
        for centre, width, bottom, top in cuts:
            s, e = centre - width / 2.0, centre + width / 2.0
            if s > x:
                pieces.append((x, s, 0.0, height))
            if bottom > 0:
                pieces.append((s, e, 0.0, bottom))
            if top < height:
                pieces.append((s, e, top, height))
            x = e
        if x < length:
            pieces.append((x, length, 0.0, height))
        half = thick / 2.0
        for s, e, lo, hi in pieces:
            pa = a + u * s
            pb = a + u * e
            for side in (1, -1):
                if faces == 'left' and side < 0 or faces == 'right' and side > 0:
                    continue
                off = n * (half * side)
                t = tex if side > 0 or backTex is None else backTex
                c = color if side > 0 or backColor is None else backColor
                # The wainscot and its trim are the inside's; an outside face
                # is its own texture top to bottom.
                inner = side > 0 or backTex is None
                self.__face(pa + off, pb + off, z0 + lo, z0 + hi, t, tile, c, group, side, lower if inner else None,
                            trim if inner else None)
            # The cut edges of an opening show the wall's thickness.
            for edge in ((s, lo, hi), (e, lo, hi)):
                p = a + u * edge[0]
                if any(abs(edge[0] - (o[0] - o[1] / 2.0)) < 0.01 or abs(edge[0] - (o[0] + o[1] / 2.0)) < 0.01 for o in cuts):
                    for sgn in (1, -1):
                        p0, p1 = p + n * half, p - n * half
                        if sgn < 0:
                            p0, p1 = p1, p0
                        self.kit.quad([Point3(p0[0], p0[1], z0 + edge[1]), Point3(p1[0], p1[1], z0 + edge[1]),
                                       Point3(p1[0], p1[1], z0 + edge[2]), Point3(p0[0], p0[1], z0 + edge[2])], tex,
                                      [(0, 0), (thick / tile, 0), (thick / tile, (edge[2] - edge[1]) / tile), (0, (edge[2] - edge[1]) / tile)],
                                      color, group)
            for zz, sgn in ((z0 + lo, -1), (z0 + hi, 1)):
                # Sills and lintels.
                if (lo > 0 and sgn < 0) or (hi < height and sgn > 0):
                    p0, p1 = pa + n * half, pb + n * half
                    p2, p3 = pb - n * half, pa - n * half
                    pts = [Point3(p0[0], p0[1], zz), Point3(p1[0], p1[1], zz), Point3(p2[0], p2[1], zz), Point3(p3[0], p3[1], zz)]
                    if sgn > 0:
                        pts.reverse()
                    self.kit.quad(pts, tex, [(0, 0), (1, 0), (1, thick / tile), (0, thick / tile)], color, group)
            if collide:
                self.__wallSolid(pa, pb, z0 + lo, z0 + hi, thick)

    def __face(self, pa, pb, z0, z1, tex, tile, color, group, side, lower, trim):
        def quad(p, q, za, zb, t, c, tl):
            s0 = 0.0
            length = (q - p).length()
            pts = [Point3(p[0], p[1], za), Point3(q[0], q[1], za), Point3(q[0], q[1], zb), Point3(p[0], p[1], zb)]
            uvs = [(s0, za / tl), (length / tl, za / tl), (length / tl, zb / tl), (s0, zb / tl)]
            # Seen from the side it is on: the left side's quad turned round.
            if side > 0:
                pts = [pts[1], pts[0], pts[3], pts[2]]
                uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
            self.kit.quad(pts, t, uvs, c, group)
        if lower is not None:
            ltex, lh, lcolor = lower
            split = min(z1, max(z0, self.__floorZ(z0) + lh))
            if split > z0:
                quad(pa, pb, z0, split, ltex, lcolor, max(lh, 0.01) if ltex else tile)
            if trim is not None and z0 < split < z1:
                ttex, tcolor = trim
                quad(pa, pb, split - 0.15, split + 0.35, ttex, tcolor, 0.5)
            if z1 > split:
                quad(pa, pb, split, z1, tex, color, tile)
        else:
            quad(pa, pb, z0, z1, tex, color, tile)

    def __floorZ(self, z):
        # A wainscot is measured from the floor the wall stands on: the
        # wall's own bottom for the room's floor level.
        base = getattr(self, '_wallBase', None)
        return z if base is None else base

    def __wallSolid(self, pa, pb, z0, z1, thick):
        node = CollisionNode('wall')
        node.setIntoCollideMask(WALL | CAMERA)
        node.setFromCollideMask(BitMask32.allOff())
        d = pb - pa
        length = d.length()
        if length < 0.05 or z1 - z0 < 0.05:
            return
        capsuleWall(node, length, max(thick, 0.6), z0, z1)
        np = self.kit.solid.attachNewNode(node)
        mid = (pa + pb) / 2.0
        np.setPos(mid[0], mid[1], 0)
        np.setH(math.degrees(math.atan2(d[1], d[0])))

    def room(self, x0, y0, x1, y1, z, height, wallTex, floorTex, ceilTex=None, openings=None, tile=10.0, color=(1, 1, 1, 1),
             floorColor=(1, 1, 1, 1), ceilColor=(1, 1, 1, 1), group='static', lower=None, floorTile=8.0, holes=(), sides='nsew',
             thick=1.0, trim=None, floorThick=0.0, outsideTex=None, outsideColor=None):
        """A box room: floor, ceiling and four walls (sides picks which),
        walls on the outside of the rectangle. openings: {'n': [...], ...}
        in feet along each wall from its west or south end."""
        openings = openings or {}
        self._wallBase = z
        if floorTex:
            self.floor(x0, y0, x1, y1, z, floorTex, tile=floorTile, color=floorColor, group=group, thick=floorThick)
        if ceilTex:
            self.ceiling(x0, y0, x1, y1, z + height, ceilTex, color=ceilColor, group=group, holes=holes)
        h = thick / 2.0
        walls = {
            # Each wall's a and b so the room is on its left.
            's': ((x0 - h, y0 - h), (x1 + h, y0 - h)),
            'e': ((x1 + h, y0 - h), (x1 + h, y1 + h)),
            'n': ((x1 + h, y1 + h), (x0 - h, y1 + h)),
            'w': ((x0 - h, y1 + h), (x0 - h, y0 - h)),
        }
        for side in sides:
            a, b = walls[side]
            ops = openings.get(side, ())
            # Openings are given from the west/south end; n and w walls run
            # the other way.
            if side in 'nw':
                length = (Vec3(b[0], b[1], 0) - Vec3(a[0], a[1], 0)).length()
                ops = [(length - (c + h), w, bo, to) for c, w, bo, to in ops]
            else:
                ops = [(c + h, w, bo, to) for c, w, bo, to in ops]
            self.wall(a, b, z, z + height, wallTex, ops, tile=tile, color=color, thick=thick, group=group, lower=lower,
                      faces='both' if outsideTex else 'left', backTex=outsideTex, backColor=outsideColor, trim=trim)
        self._wallBase = None

    def text(self, text, pos, h, scale, color=(1, 1, 1, 1), font='sign', parent=None, wrap=None, align='center'):
        tn = TextNode('mapText')
        tn.setFont(ToontownGlobals.getSignFont() if font == 'sign' else (ToontownGlobals.getInterfaceFont() if font == 'face' else loader.loadFont(font)))
        tn.setAlign({'center': TextNode.ACenter, 'left': TextNode.ALeft, 'right': TextNode.ARight}[align])
        if wrap:
            tn.setWordwrap(wrap)
        tn.setText(text)
        tn.setTextColor(*color)
        np = (parent or self.root).attachNewNode(tn)
        np.setPos(Point3(pos))
        np.setH(h)
        np.setScale(scale)
        np.setTwoSided(False)
        np.setDepthOffset(2)
        np.setDepthWrite(False)
        self.dynamic.append(np)
        return np

    def boxNode(self, parent, lo, hi, tex, color=(1, 1, 1, 1), tile=4.0):
        """A loose textured box that can move on its own (a board, a door
        leaf, a shutter), not flattened into the map."""
        m = Mesh()
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        quads = [
            ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (x1 - x0, z1 - z0)),
            ([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (x1 - x0, z1 - z0)),
            ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (y1 - y0, z1 - z0)),
            ([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (y1 - y0, z1 - z0)),
            ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (x1 - x0, y1 - y0)),
            ([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], (x1 - x0, y1 - y0)),
        ]
        for pts, (w, hgt) in quads:
            m.quad([Point3(*p) for p in pts], [(0, 0), (w / tile, 0), (w / tile, hgt / tile), (0, hgt / tile)], Vec4(*color))
        np = parent.attachNewNode(m.node('box'))
        t = self.kit.tex(tex)
        if t is not None:
            np.setTexture(t, 1)
        return np

    # --- Finishing ---

    def afterFinish(self):
        # Each lamp lights the groups it was given (every lit group when
        # none): a room's own warm light doesn't leak through its walls.
        groups = dict(self.kit.groups)
        for np, names, color in self.lamps:
            targets = [groups[n] for n in names if n in groups] if names else [g for k, g in groups.items() if k not in ('glow', 'decal')]
            for g in targets:
                g.setLight(np)
        for np in getattr(self, 'litModels', []):
            for lamp, names, color in self.lamps:
                pass
        if self.flickers:
            self.addTask(self.__flicker, 'flicker')
        self.afterBuild()

    def afterBuild(self):
        pass

    # Surfaces that lie flat on another one (a rug on the floor, a molding
    # strip over the wallpaper, a light pool, a prop's shadow, a box flush
    # with a bigger box) used to fight for the same depth and flicker
    # (Arthur). Each is given a depth offset that puts it in front: decals
    # over trim over small things over big things over the room itself.
    # Kept small: on a phone's coarser depth a big offset would show a
    # thing through a wall in front of it.
    DECAL_WORDS = (('particleglow', 18), ('paper_stacks', 16), ('shadow', 14), ('grime', 14), ('crack', 14),
                   ('poster', 14), ('decal', 14))
    TRIM_WORDS = (('molding', 7), ('woodpanel', 6), ('wood_panel', 6), ('carpet', 6), ('rug', 6),
                  ('boards', 6), ('planks', 6), ('wood1', 6), ('smoothwall', 6))

    def layerDepths(self):
        from panda3d.core import DepthOffsetAttrib, TextureAttrib
        root = self.root
        for i, gnp in enumerate(root.findAllMatches('**/+GeomNode')):
            path = str(gnp).lower()
            if '__actor_modelroot' in path:
                continue
            name = gnp.getName().lower()
            if name == 'collision' and not gnp.isHidden():
                # A model's stand-in for its solid, never meant to be seen.
                gnp.hide()
                continue
            texName = ''
            ta = gnp.getNetState().getAttrib(TextureAttrib)
            if ta is not None and ta.getNumOnStages():
                tex = ta.getOnTexture(ta.getOnStage(0))
                texName = (tex.getFilename().getBasename() or tex.getName()).lower()
            look = name + ' ' + texName
            rank = None
            for word, r in self.DECAL_WORDS:
                if word in look:
                    rank = r
                    break
            if rank is not None and '/kitstatic/' not in path and '/kitdecals/' not in path:
                # The same decal laid again by a room of its own; two
                # shadows overlapping told apart by their order.
                rank += 1
            if rank is not None and '/kitdecals/' not in path and not name.startswith('kit-'):
                rank += i % 3
            if rank is None and name.startswith('kit-'):
                # Two rooms' walls or floors meeting flush: one always wins
                # (which one doesn't matter, so long as it never changes).
                import zlib
                rank = zlib.crc32(path.encode()) % 6
                for word, r in self.TRIM_WORDS:
                    if word in look:
                        # Trim over the walls; a room's own over the building's.
                        rank = r + (0 if '/kitstatic/' in path else 1)
                        break
            if rank is None:
                # A loose box or a prop's part: the smaller in front, and
                # two the same size (a chandelier's crossed arms) told
                # apart by their order.
                bounds = gnp.getTightBounds(root)
                if bounds is None:
                    continue
                size = (bounds[1] - bounds[0]).length()
                step = 2 if size < 3.0 else 1 if size < 10.0 else 0
                rank = 9 + step + (i % 3)
            old = gnp.getNetState().getAttrib(DepthOffsetAttrib)
            have = old.getOffset() if old is not None else 0
            if rank > have:
                gnp.setDepthOffset(rank)

    def __flicker(self, task):
        import random
        now = globalClock.getFrameTime()
        if not hasattr(self, 'flickState'):
            self.flickState = {}
            self.flickBase = dict((id(n), c) for n, g, c in self.lamps)
        for np in self.flickers:
            light = np.node()
            state = self.flickState.get(id(np))
            if state is None or now >= state[0]:
                on = random.random() < 0.82
                self.flickState[id(np)] = (now + (random.uniform(0.04, 0.18) if not on else random.uniform(0.3, 2.5)), on)
                color = self.flickBase[id(np)] * getattr(self, 'lampBoost', 1.0)
                light.setColor(color if on else color * random.uniform(0.15, 0.4))
        return task.cont

    def destroy(self):
        for np in self.dynamic:
            if not np.isEmpty():
                np.removeNode()
        self.dynamic = []
        PreviewMap.destroy(self)
