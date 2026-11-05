"""Smooth toy shapes for the code-built Survival maps.

MapKit makes flat-sided boxes, ramps and cards. A toy town needs round
things too: balls, rings, cones, springs and flat cut-out pieces (jigsaw
pieces, a key's bow). Geo writes them into MapKit meshes (or a mesh of its
own, for a piece that moves) through a placement matrix, with smooth
normals so a ball looks round under the map's soft light.
"""

import math

from panda3d.core import Mat4, NodePath, Point3, TextNode, TransparencyAttrib, Vec3, Vec4

from toontown.survival.previewmaps.MapKit import Mesh


def _v(p):
    return Vec3(p[0], p[1], p[2])


class Geo:
    """Draws shapes into meshes, placed by a matrix. `getMesh(tex)` gives
    the mesh for a texture (a MapKit's, or a Part's)."""

    def __init__(self, getMesh, mat=None):
        self.getMesh = getMesh
        self.mat = Mat4(mat) if mat is not None else Mat4(Mat4.identMat())

    def at(self, pos=(0, 0, 0), hpr=(0, 0, 0), scale=1.0):
        """The same, placed somewhere inside this one."""
        np = NodePath('xf')
        np.setPos(*pos)
        np.setHpr(*hpr)
        if isinstance(scale, (tuple, list)):
            np.setScale(*scale)
        else:
            np.setScale(scale)
        return Geo(self.getMesh, np.getMat() * self.mat)

    # --- Raw triangles ---

    def tri(self, tex, pts, nrms, uvs, color):
        mesh = self.getMesh(tex)
        c = Vec4(*color)
        for p, n, uv in zip(pts, nrms, uvs):
            wp = self.mat.xformPoint(Point3(p[0], p[1], p[2]))
            wn = self.mat.xformVec(_v(n))
            if wn.length() > 0:
                wn.normalize()
            mesh.vw.addData3(wp)
            mesh.nw.addData3(wn)
            mesh.cw.addData4(c)
            mesh.tw.addData2(uv[0], uv[1])
        i = mesh.count
        mesh.tris.addVertices(i, i + 1, i + 2)
        mesh.count += 3

    def quad(self, tex, pts, uvs, color, nrms=None):
        if nrms is None:
            a, b, c = _v(pts[0]), _v(pts[1]), _v(pts[2])
            n = (b - a).cross(c - a)
            if n.length() > 0:
                n.normalize()
            nrms = [n] * 4
        self.tri(tex, [pts[0], pts[1], pts[2]], [nrms[0], nrms[1], nrms[2]], [uvs[0], uvs[1], uvs[2]], color)
        self.tri(tex, [pts[0], pts[2], pts[3]], [nrms[0], nrms[2], nrms[3]], [uvs[0], uvs[2], uvs[3]], color)

    # --- Boxes ---

    def box(self, lo, hi, tex, color, tile=8.0, faces='nsewtb', topTex=None, topColor=None, frontColor=None):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        t = float(tile)
        fc = frontColor or color
        if 's' in faces:
            self.quad(tex, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                      [(x0 / t, z0 / t), (x1 / t, z0 / t), (x1 / t, z1 / t), (x0 / t, z1 / t)], fc)
        if 'n' in faces:
            self.quad(tex, [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
                      [(-x1 / t, z0 / t), (-x0 / t, z0 / t), (-x0 / t, z1 / t), (-x1 / t, z1 / t)], color)
        if 'e' in faces:
            self.quad(tex, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
                      [(y0 / t, z0 / t), (y1 / t, z0 / t), (y1 / t, z1 / t), (y0 / t, z1 / t)], color)
        if 'w' in faces:
            self.quad(tex, [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
                      [(-y1 / t, z0 / t), (-y0 / t, z0 / t), (-y0 / t, z1 / t), (-y1 / t, z1 / t)], color)
        if 't' in faces:
            self.quad(topTex or tex, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                      [(x0 / t, y0 / t), (x1 / t, y0 / t), (x1 / t, y1 / t), (x0 / t, y1 / t)], topColor or color)
        if 'b' in faces:
            self.quad(tex, [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
                      [(x0 / t, y1 / t), (x1 / t, y1 / t), (x1 / t, y0 / t), (x0 / t, y0 / t)], color)

    def trimBox(self, lo, hi, tex, color, trim, t=0.8, tile=8.0, faces='nsewt', trimTex=None, topColor=None):
        """A painted box with thick rounded-off trim along every edge, the
        way the playground buildings have their corner boards."""
        self.box(lo, hi, tex, color, tile=tile, faces=faces, topColor=topColor)
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        h = t * 0.5
        tt = trimTex or tex
        # Uprights at the four corners.
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            self.box((x - h, y - h, z0), (x + h, y + h, z1 + h * 0.2), tt, trim, tile=4, faces='nsewt')
        # Top and bottom rims.
        for z in (z1 - h, z0 + h):
            zz0, zz1 = z - h, z + h
            if z == z0 + h and z0 > 0.5:
                zz0 = z0
            self.box((x0 - h, y0 - h, zz0), (x1 + h, y0 + h, zz1), tt, trim, tile=4, faces='nstb')
            self.box((x0 - h, y1 - h, zz0), (x1 + h, y1 + h, zz1), tt, trim, tile=4, faces='nstb')
            self.box((x0 - h, y0 - h, zz0), (x0 + h, y1 + h, zz1), tt, trim, tile=4, faces='ewtb')
            self.box((x1 - h, y0 - h, zz0), (x1 + h, y1 + h, zz1), tt, trim, tile=4, faces='ewtb')

    def prism(self, lo, hi, tex, color, gable=None, tile=8.0, overhang=0.0, roofTex=None):
        """A gable roof (a triangular block) over lo..hi, its ridge along x."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        ym = (y0 + y1) * 0.5
        o = overhang
        t = float(tile)
        rt = roofTex or tex
        # Two slopes.
        self.quad(rt, [(x0 - o, y0 - o, z0), (x1 + o, y0 - o, z0), (x1 + o, ym, z1), (x0 - o, ym, z1)],
                  [(x0 / t, 0), (x1 / t, 0), (x1 / t, (z1 - z0 + ym - y0) / t), (x0 / t, (z1 - z0 + ym - y0) / t)], color)
        self.quad(rt, [(x1 + o, y1 + o, z0), (x0 - o, y1 + o, z0), (x0 - o, ym, z1), (x1 + o, ym, z1)],
                  [(x1 / t, 0), (x0 / t, 0), (x0 / t, (z1 - z0 + y1 - ym) / t), (x1 / t, (z1 - z0 + y1 - ym) / t)], color)
        # Undersides of the overhang.
        if o:
            self.quad(rt, [(x0 - o, ym, z1), (x1 + o, ym, z1), (x1 + o, y0 - o, z0), (x0 - o, y0 - o, z0)],
                      [(0, 0), (1, 0), (1, 1), (0, 1)], color)
            self.quad(rt, [(x1 + o, ym, z1), (x0 - o, ym, z1), (x0 - o, y1 + o, z0), (x1 + o, y1 + o, z0)],
                      [(0, 0), (1, 0), (1, 1), (0, 1)], color)
        g = gable or color
        for x, sign in ((x0, -1), (x1, 1)):
            pts = [(x, y0, z0), (x, y1, z0), (x, ym, z1)] if sign > 0 else [(x, y1, z0), (x, y0, z0), (x, ym, z1)]
            n = (sign, 0, 0)
            self.tri(tex, pts, [n, n, n], [(p[1] / t, p[2] / t) for p in pts], g)

    # --- Round things ---

    def cyl(self, r, h, tex, color, z0=0.0, sides=20, rTop=None, caps='t', capTex=None, capColor=None, tile=8.0,
            arc=(0.0, 360.0), inside=False):
        rt = r if rTop is None else rTop
        circ = 2 * math.pi * r
        a0d, a1d = arc
        slope = (r - rt) / h if h else 0.0
        for i in range(sides):
            a0 = math.radians(a0d + (a1d - a0d) * i / sides)
            a1 = math.radians(a0d + (a1d - a0d) * (i + 1) / sides)
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            n0 = (c0, s0, slope)
            n1 = (c1, s1, slope)
            u0 = circ * i / sides / tile
            u1 = circ * (i + 1) / sides / tile
            pts = [(r * c0, r * s0, z0), (r * c1, r * s1, z0), (rt * c1, rt * s1, z0 + h), (rt * c0, rt * s0, z0 + h)]
            uvs = [(u0, z0 / tile), (u1, z0 / tile), (u1, (z0 + h) / tile), (u0, (z0 + h) / tile)]
            if inside:
                self.quad(tex, pts[::-1], uvs[::-1], color, [(-c0, -s0, 0), (-c0, -s0, 0), (-c1, -s1, 0), (-c1, -s1, 0)][::-1])
            else:
                self.quad(tex, pts, uvs, color, [n0, n1, n1, n0])
        cc = capColor or color
        ct = capTex or tex
        for which in caps:
            z = z0 + h if which == 't' else z0
            rr = rt if which == 't' else r
            if rr <= 0:
                continue
            for i in range(sides):
                a0 = math.radians(a0d + (a1d - a0d) * i / sides)
                a1 = math.radians(a0d + (a1d - a0d) * (i + 1) / sides)
                p0 = (rr * math.cos(a0), rr * math.sin(a0), z)
                p1 = (rr * math.cos(a1), rr * math.sin(a1), z)
                uv = lambda p: (0.5 + p[0] / (2 * rr), 0.5 + p[1] / (2 * rr))
                if which == 't':
                    self.tri(ct, [(0, 0, z), p0, p1], [(0, 0, 1)] * 3, [(0.5, 0.5), uv(p0), uv(p1)], cc)
                else:
                    self.tri(ct, [(0, 0, z), p1, p0], [(0, 0, -1)] * 3, [(0.5, 0.5), uv(p1), uv(p0)], cc)

    def sphere(self, center, radii, tex, color, rings=10, sides=18, uvScale=(1, 1), lat=(-90.0, 90.0)):
        cx, cy, cz = center
        if not isinstance(radii, (tuple, list)):
            radii = (radii, radii, radii)
        rx, ry, rz = radii
        la0, la1 = lat
        for j in range(rings):
            t0 = math.radians(la0 + (la1 - la0) * j / rings)
            t1 = math.radians(la0 + (la1 - la0) * (j + 1) / rings)
            for i in range(sides):
                a0 = 2 * math.pi * i / sides
                a1 = 2 * math.pi * (i + 1) / sides
                pts, nrms, uvs = [], [], []
                for t, a, (ui, vj) in ((t0, a0, (i, j)), (t0, a1, (i + 1, j)), (t1, a1, (i + 1, j + 1)), (t1, a0, (i, j + 1))):
                    ux, uy, uz = math.cos(t) * math.cos(a), math.cos(t) * math.sin(a), math.sin(t)
                    pts.append((cx + rx * ux, cy + ry * uy, cz + rz * uz))
                    nrms.append((ux / rx, uy / ry, uz / rz))
                    uvs.append((float(ui) / sides * uvScale[0], float(vj) / rings * uvScale[1]))
                self.quad(tex, pts, uvs, color, nrms)

    def torus(self, R, r, tex, color, seg=24, sides=10, arc=(0.0, 360.0)):
        """A ring lying in the local XY plane round the origin."""
        a0d, a1d = arc
        for i in range(seg):
            u0 = math.radians(a0d + (a1d - a0d) * i / seg)
            u1 = math.radians(a0d + (a1d - a0d) * (i + 1) / seg)
            for j in range(sides):
                v0 = 2 * math.pi * j / sides
                v1 = 2 * math.pi * (j + 1) / sides
                pts, nrms, uvs = [], [], []
                for u, v, uv in ((u0, v0, (i, j)), (u1, v0, (i + 1, j)), (u1, v1, (i + 1, j + 1)), (u0, v1, (i, j + 1))):
                    nx, ny, nz = math.cos(v) * math.cos(u), math.cos(v) * math.sin(u), math.sin(v)
                    pts.append(((R + r * math.cos(v)) * math.cos(u), (R + r * math.cos(v)) * math.sin(u), r * math.sin(v)))
                    nrms.append((nx, ny, nz))
                    uvs.append((float(uv[0]) / seg * 4, float(uv[1]) / sides))
                self.quad(tex, pts, uvs, color, nrms)

    def tube(self, path, r, tex, color, sides=8, plane=None):
        """A round tube along a list of points (a spring's coil). A tube
        lying in one plane (an arch's trim) gives that plane's normal, so
        its sides never twist where the path turns upright."""
        frames = []
        for k, p in enumerate(path):
            a = _v(path[max(0, k - 1)])
            b = _v(path[min(len(path) - 1, k + 1)])
            d = b - a
            d.normalize()
            if plane is not None:
                up = _v(plane)
            else:
                up = Vec3(0, 0, 1) if abs(d[2]) < 0.9 else Vec3(1, 0, 0)
            s1 = d.cross(up)
            s1.normalize()
            s2 = s1.cross(d)
            frames.append((_v(p), s1, s2))
        for k in range(len(path) - 1):
            pa, a1, a2 = frames[k]
            pb, b1, b2 = frames[k + 1]
            for j in range(sides):
                v0 = 2 * math.pi * j / sides
                v1 = 2 * math.pi * (j + 1) / sides
                na0 = a1 * math.cos(v0) + a2 * math.sin(v0)
                na1 = a1 * math.cos(v1) + a2 * math.sin(v1)
                nb0 = b1 * math.cos(v0) + b2 * math.sin(v0)
                nb1 = b1 * math.cos(v1) + b2 * math.sin(v1)
                self.quad(tex, [pa + na0 * r, pb + nb0 * r, pb + nb1 * r, pa + na1 * r],
                          [(0, 0), (1, 0), (1, 1), (0, 1)], color, [na0, nb0, nb1, na1])

    # --- Flat cut-out pieces ---

    def extrude(self, poly, z0, z1, tex, color, topColor=None, tile=4.0, sideColor=None, bottom=True):
        """A flat piece cut to the outline `poly` (x, y anticlockwise),
        z0..z1 thick, rounded off at the edges with smooth side normals."""
        n = len(poly)
        sc = sideColor or color
        for k in range(n):
            a = poly[k]
            b = poly[(k + 1) % n]
            pa = poly[(k - 1) % n]
            nb = poly[(k + 2) % n]
            na = _edgeNormal(pa, a, b)
            nbv = _edgeNormal(a, b, nb)
            self.quad(tex, [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)],
                      [(0, 0), (1, 0), (1, 0.3), (0, 0.3)], sc, [na, nbv, nbv, na])
        tris = earClip(poly)
        tc = topColor or color
        for i, j, k in tris:
            pts = [poly[i], poly[j], poly[k]]
            self.tri(tex, [(p[0], p[1], z1) for p in pts], [(0, 0, 1)] * 3, [(p[0] / tile, p[1] / tile) for p in pts], tc)
            if bottom:
                self.tri(tex, [(p[0], p[1], z0) for p in pts[::-1]], [(0, 0, -1)] * 3,
                         [(p[0] / tile, p[1] / tile) for p in pts[::-1]], color)


def _edgeNormal(a, b, c):
    """The outward normal at b, averaging its two edges (anticlockwise)."""
    e1 = Vec3(b[0] - a[0], b[1] - a[1], 0)
    e2 = Vec3(c[0] - b[0], c[1] - b[1], 0)
    n1 = Vec3(e1[1], -e1[0], 0)
    n2 = Vec3(e2[1], -e2[0], 0)
    if n1.length():
        n1.normalize()
    if n2.length():
        n2.normalize()
    n = n1 + n2
    if n.length() < 1e-4:
        n = n2
    n.normalize()
    return n


def earClip(poly):
    """Triangles filling a simple polygon (anticlockwise)."""
    idx = list(range(len(poly)))
    out = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        found = False
        for k in range(len(idx)):
            i, j, l = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i], poly[j], poly[l]
            if cross(a, b, c) <= 1e-9:
                continue
            if any(inside(poly[m], a, b, c) for m in idx if m not in (i, j, l)):
                continue
            out.append((i, j, l))
            idx.pop(k)
            found = True
            break
        if not found:
            break
    if len(idx) == 3:
        out.append(tuple(idx))
    return out


class Part:
    """Meshes of their own, made into one node: a piece that moves (a
    spinning top, the clock's hands, Jack on his spring)."""

    def __init__(self, kit, name):
        self.kit = kit
        self.name = name
        self.meshes = {}
        self.geo = Geo(self.mesh)

    def mesh(self, tex):
        m = self.meshes.get(tex)
        if m is None:
            m = self.meshes[tex] = Mesh()
        return m

    def make(self, parent):
        np = parent.attachNewNode(self.name)
        for tex, mesh in self.meshes.items():
            g = np.attachNewNode(mesh.node('%s-%s' % (self.name, tex or 'plain')))
            t = self.kit.tex(tex)
            if t is not None:
                g.setTexture(t, 1)
            else:
                g.setTextureOff(1)
        np.flattenStrong()
        return np


def signText(parent, text, pos, h, scale, color, font='sign', maxWidth=None, align=TextNode.ACenter, p=0, r=0):
    """Words in the playground signs' lettering, flat on a board."""
    from toontown.toonbase import ToontownGlobals
    tn = TextNode('toySign')
    tn.setFont(ToontownGlobals.getSignFont() if font == 'sign' else ToontownGlobals.getInterfaceFont())
    tn.setAlign(align)
    tn.setText(text)
    tn.setTextColor(*color)
    np = parent.attachNewNode(tn.generate())
    np.setPos(*pos)
    np.setHpr(h, p, r)
    if maxWidth and tn.getWidth() * scale > maxWidth:
        scale = maxWidth / tn.getWidth()
    np.setScale(scale)
    np.setDepthOffset(2)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np
