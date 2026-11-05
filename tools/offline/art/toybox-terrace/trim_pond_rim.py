"""Trim the pond rim where it runs into each dock (Arthur 2026-11-05)."""
import math, sys
from panda3d.egg import EggData, EggPolygon, EggGroupNode, EggVertex
from panda3d.core import Filename, Point3D, LTexCoordd, LVecBase4f, LVector3d
src, dst = sys.argv[1], sys.argv[2]
RX, RY, W = 30.0, 21.0, 5.4
docks = []
for d in (20.0, 75.0, 140.0):
    a = math.radians(d)
    ex, ey = (RX + 1.5) * math.cos(a), (RY + 1.5) * math.sin(a)
    l = math.hypot(ex, ey); fx, fy = -ex / l, -ey / l
    docks.append(((ex, ey), (fy, -fx), (fx, fy)))  # edge, right, inward

def q(p):
    return (p[0] / RX) ** 2 + (p[1] / RY) ** 2

def isRim(poly):
    for i in range(poly.getNumVertices()):
        p = poly.getVertex(i).getPos3()
        if not (0.985 <= q(p) <= 1.25 and -0.2 <= p[2] <= 1.8):
            return False
    return True

CUTS = {}

def lerpV(pool, a, b, t):
    v = EggVertex(a)
    v.setPos(a.getPos3() + (b.getPos3() - a.getPos3()) * t)
    if a.hasUv() and b.hasUv():
        v.setUv(a.getUv() + (b.getUv() - a.getUv()) * t)
    if a.hasNormal() and b.hasNormal():
        n = a.getNormal() + (b.getNormal() - a.getNormal()) * t
        n.normalize(); v.setNormal(n)
    if a.hasColor() and b.hasColor():
        v.setColor(a.getColor() + (b.getColor() - a.getColor()) * t)
    return pool.createUniqueVertex(v)

stats = {'trimmed': 0, 'removed': 0, 'marblePolys': 0}
# Marbles set in the rim (every third of 72 rim pieces, ToyboxTerrace.__pond):
# drop the ones that would sit over a dock's edge.
gone = []
for i in range(0, 72, 3):
    a0, a1 = 2 * math.pi * i / 72, 2 * math.pi * (i + 1) / 72
    pts = [(RX + rr) * math.cos(a) for a, rr in ((a0, 0), (a1, 0), (a1, 3), (a0, 3))], [(RY + rr * RY / RX) * math.sin(a) for a, rr in ((a0, 0), (a1, 0), (a1, 3), (a0, 3))]
    mx, my = sum(pts[0]) / 4, sum(pts[1]) / 4
    for (ex, ey), (rx_, ry_), (fx, fy) in docks:
        u = (mx - ex) * rx_ + (my - ey) * ry_
        al = (mx - ex) * fx + (my - ey) * fy
        if abs(u) < W + 1.3 and -6 < al < 16:
            gone.append((mx, my))
print('marbles dropped', len(gone))

def isGoneMarble(poly):
    ps = [poly.getVertex(i).getPos3() for i in range(poly.getNumVertices())]
    return any(all(math.sqrt((p[0] - mx) ** 2 + (p[1] - my) ** 2 + (p[2] - 1.5) ** 2) < 1.75 for p in ps) for mx, my in gone)
def clip(poly):
    pts = [poly.getVertex(i) for i in range(poly.getNumVertices())]
    for (ex, ey), (rx_, ry_), (fx, fy) in docks:
        def u(v):
            p = v.getPos3(); return (p[0] - ex) * rx_ + (p[1] - ey) * ry_
        def along(v):
            p = v.getPos3(); return (p[0] - ex) * fx + (p[1] - ey) * fy
        us = [u(v) for v in pts]
        if not any(abs(x) < W and -4.5 < along(v) < 16 for x, v in zip(us, pts)):
            continue
        side = 1 if sum(us) > 0 else -1
        # keep side*u >= W
        f = [side * x - W for x in us]
        if all(x >= -1e-4 for x in f):
            continue
        pool = pts[0].getPool()
        out = []
        cut = CUTS.setdefault((docks.index(((ex, ey), (rx_, ry_), (fx, fy))), side), {'pts': [], 'poly': poly, 'pool': pool})
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            fa, fb = f[i], f[(i + 1) % n]
            if fa >= 0:
                out.append(a)
            if (fa >= 0) != (fb >= 0):
                nv = lerpV(pool, a, b, fa / (fa - fb))
                out.append(nv)
                cut['pts'].append(nv)
        pts = out
        if len(pts) < 3:
            return None
        stats['trimmed'] += 1
    return pts

def walk(node):
    for c in list(node.getChildren()):
        if isinstance(c, EggPolygon):
            if not isRim(c):
                if isGoneMarble(c):
                    node.removeChild(c); stats['marblePolys'] += 1
                continue
            pts = clip(c)
            if pts is None:
                node.removeChild(c); stats['removed'] += 1
            elif [c.getVertex(i) for i in range(c.getNumVertices())] != pts:
                c.clear()
                for v in pts:
                    c.addVertex(v)
        elif isinstance(c, EggGroupNode):
            walk(c)

def hull(ps):
    ps = sorted(set(ps))
    if len(ps) < 3:
        return ps
    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in ps:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 1e-9:
            lo.pop()
        lo.append(p)
    for p in reversed(ps):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 1e-9:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def caps():
    # Close each cut end of the rim with a flat face toward the dock.
    for (di, side), cut in CUTS.items():
        (ex, ey), (rx_, ry_), (fx, fy) = docks[di]
        u0 = side * W
        byKey = {}
        for vv in cut['pts']:
            p = vv.getPos3()
            byKey[(round((p[0] - ex) * fx + (p[1] - ey) * fy, 4), round(p[2], 4))] = vv
        ps = list(byKey)
        h = hull(ps)
        if len(h) < 3:
            continue
        tpl = cut['poly']
        poly = EggPolygon(tpl)
        poly.clear()
        nx, ny = -side * rx_, -side * ry_
        # (along, z) is right-handed seen from +right; facing -side*right flips it.
        if side < 0:
            h = list(reversed(h))
        h = list(reversed(h))
        pool = cut['pool']
        for key in h:
            v = EggVertex(byKey[key])
            v.setNormal(LVector3d(nx, ny, 0))
            poly.addVertex(pool.createUniqueVertex(v))
        poly.setBfaceFlag(True)
        tpl.getParent().addChild(poly)
        stats['caps'] = stats.get('caps', 0) + 1

e = EggData(); e.read(Filename.fromOsSpecific(src)); walk(e); caps()
e.writeEgg(Filename.fromOsSpecific(dst)); print(stats)
