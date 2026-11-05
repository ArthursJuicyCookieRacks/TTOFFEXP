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
# Marbles set in the rim: each marble is found from its own polygons (joined
# where they share corners), not from where the build placed it.
gone = set()
MARBLE = {}

# A marble this close to a cut rim end bulges over the end's face.
END_CLEAR = 1.0

def crossesDock(p):
    for (ex, ey), (rx_, ry_), (fx, fy) in docks:
        u = (p[0] - ex) * rx_ + (p[1] - ey) * ry_
        al = (p[0] - ex) * fx + (p[1] - ey) * fy
        if abs(u) < W + END_CLEAR and -6 < al < 16:
            return True
    return False

def findGone(root):
    """Every marble that reaches past a cut rim end (over a dock) goes, so
    each marble left is seen only from above the rim (Arthur)."""
    polys = []
    def collect(node, inMarble):
        for c in node.getChildren():
            if isinstance(c, EggPolygon):
                if inMarble:
                    polys.append(c)
            elif isinstance(c, EggGroupNode):
                collect(c, inMarble or c.getName().startswith('kit-gen:marble') or 'marble_sheen' in c.getName())
    collect(root, False)
    # Marbles stand several feet apart along the rim: every polygon goes
    # with the marble whose middle (in plan) is within 2 ft of its own.
    seeds = []
    big = {}
    for poly in polys:
        n = poly.getNumVertices()
        cx_ = sum(poly.getVertex(k).getPos3()[0] for k in range(n)) / n
        cy_ = sum(poly.getVertex(k).getPos3()[1] for k in range(n)) / n
        for si, (sx, sy) in enumerate(seeds):
            if math.hypot(cx_ - sx, cy_ - sy) < 2.0:
                big[si].append(poly)
                break
        else:
            seeds.append((cx_, cy_))
            big[len(seeds) - 1] = [poly]
    comps = big
    mids = {}
    for r, ps in big.items():
        for p in ps:
            MARBLE[pkey(p)] = r
        if any(crossesDock(p.getVertex(k).getPos3()) for p in ps for k in range(p.getNumVertices())):
            gone.add(r)
    print('marbles', len(big), 'pieces', len(comps))
    for r, ps in sorted(big.items()):
        pts = [p.getVertex(k).getPos3() for p in ps for k in range(p.getNumVertices())]
        print('  ', r, len(ps), 'mid', [round(v, 1) for v in mids.get(r, (0, 0))], 'z', round(min(q[2] for q in pts), 2), round(max(q[2] for q in pts), 2), 'gone' if r in gone else '')

def pkey(poly):
    return tuple((round(p[0], 3), round(p[1], 3), round(p[2], 3)) for p in (poly.getVertex(k).getPos3() for k in range(poly.getNumVertices())))

RIM_TOP = 1.6

def insideRim(p):
    a = math.atan2(p[1] / RY, p[0] / RX)
    r = math.hypot(p[0], p[1])
    ri = math.hypot(RX * math.cos(a), RY * math.sin(a))
    ro = math.hypot((RX + 3) * math.cos(a), (RY + 3 * RY / RX) * math.sin(a))
    return ri + 0.04 <= r <= ro - 0.04

TOPS = []

def collectTops(node, inMarble=False):
    """The rim's top faces as they are after the trim (plan outlines)."""
    for c in node.getChildren():
        if isinstance(c, EggPolygon):
            if not inMarble and isRim(c):
                ps = [c.getVertex(k).getPos3() for k in range(c.getNumVertices())]
                if all(p[2] > 1.5 for p in ps):
                    TOPS.append([(p[0], p[1]) for p in ps])
        elif isinstance(c, EggGroupNode):
            collectTops(c, inMarble or isMarbleGroup(c.getName()))

def inPoly(x, y, poly):
    inside = False
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside

def underTop(p):
    """Whether a point is under the rim's top, a little in from every edge."""
    if not insideRim(p):
        return False
    for dx, dy in ((0, 0), (0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05)):
        if not any(inPoly(p[0] + dx, p[1] + dy, t) for t in TOPS):
            return False
    return True

def fitMarbles(root):
    """Shrink each marble left about the middle of its top until nothing of
    it below the rim's top pokes out of the rim's inner or outer face: from
    the side only the rim shows, the marble only from above (Arthur)."""
    groups = {}
    def collect(node):
        for c in node.getChildren():
            if isinstance(c, EggPolygon):
                r = MARBLE.get(pkey(c))
                if r is not None and r not in gone:
                    groups.setdefault(r, []).append(c)
            elif isinstance(c, EggGroupNode):
                collect(c)
    collect(root)
    for r, polys in groups.items():
        verts = {}
        for p in polys:
            for k in range(p.getNumVertices()):
                v = p.getVertex(k)
                verts[(v.getPool().getName(), v.getIndex())] = v
        vs = list(verts.values())
        pos = [Point3D(v.getPos3()) for v in vs]
        cx_ = sum(p[0] for p in pos) / len(pos)
        cy_ = sum(p[1] for p in pos) / len(pos)
        scale = 1.0
        while scale >= 0.6:
            ok = True
            for p in pos:
                q_ = Point3D(cx_ + (p[0] - cx_) * scale, cy_ + (p[1] - cy_) * scale, RIM_TOP + (p[2] - RIM_TOP) * scale)
                if q_[2] < RIM_TOP - 0.05 and not underTop(q_):
                    ok = False
                    break
            if ok:
                break
            scale -= 0.02
        if scale < 0.6:
            # It can't sit inside the rim here (by a cut end): it goes.
            for p in polys:
                p.getParent().removeChild(p)
            stats['marblesNoRoom'] = stats.get('marblesNoRoom', 0) + 1
            continue
        for v, p in zip(vs, pos):
            v.setPos(Point3D(cx_ + (p[0] - cx_) * scale, cy_ + (p[1] - cy_) * scale, RIM_TOP + (p[2] - RIM_TOP) * scale))
        stats.setdefault('scales', []).append(round(scale, 2))

def isGoneMarble(poly):
    return MARBLE.get(pkey(poly)) in gone

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

def isMarbleGroup(name):
    return name.startswith('kit-gen:marble') or 'marble_sheen' in name

def walk(node, inMarble=False):
    for c in list(node.getChildren()):
        if isinstance(c, EggPolygon):
            if inMarble or not isRim(c):
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
            walk(c, inMarble or isMarbleGroup(c.getName()))

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

def caps(root):
    """Close every open end of the rim: wherever its top stops (a dock cut,
    or where the build left a gap by a dock) a face goes down to the ground,
    so no end is see-through (Arthur)."""
    tops = []
    def collect(node, inMarble):
        for c in node.getChildren():
            if isinstance(c, EggPolygon):
                if not inMarble and isRim(c):
                    ps = [c.getVertex(k) for k in range(c.getNumVertices())]
                    if all(v.getPos3()[2] > 1.5 for v in ps):
                        tops.append(c)
            elif isinstance(c, EggGroupNode):
                collect(c, inMarble or isMarbleGroup(c.getName()))
    collect(root, False)
    key = lambda p: (round(p[0], 2), round(p[1], 2))
    count = {}
    for t in tops:
        n = t.getNumVertices()
        for k in range(n):
            a, b = key(t.getVertex(k).getPos3()), key(t.getVertex((k + 1) % n).getPos3())
            e = (min(a, b), max(a, b))
            count[e] = count.get(e, 0) + 1
    for t in tops:
        n = t.getNumVertices()
        for k in range(n):
            va, vb = t.getVertex(k), t.getVertex((k + 1) % n)
            pa, pb = va.getPos3(), vb.getPos3()
            a, b = key(pa), key(pb)
            if count[(min(a, b), max(a, b))] != 1:
                continue
            # An end runs across the rim (inner edge to outer edge); the
            # long sides run along it.
            # (Judged by direction, since a short piece of an end barely
            # changes the distance out from the pond's middle.)
            mx, my = (pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5
            gx, gy = mx / (RX * RX), my / (RY * RY)
            gl = math.hypot(gx, gy) or 1.0
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            dl = math.hypot(dx, dy) or 1.0
            if abs(dx * gx + dy * gy) / (gl * dl) < 0.6:
                continue
            poly = EggPolygon(t)
            poly.clear()
            pool = va.getPool()
            nx, ny = pb[1] - pa[1], -(pb[0] - pa[0])
            ln = math.hypot(nx, ny) or 1.0
            for v, z in ((vb, None), (va, None), (va, 0.0), (vb, 0.0)):
                nv = EggVertex(v)
                if z is not None:
                    p = v.getPos3()
                    nv.setPos(Point3D(p[0], p[1], z))
                nv.setNormal(LVector3d(nx / ln, ny / ln, 0))
                poly.addVertex(pool.createUniqueVertex(nv))
            poly.setBfaceFlag(True)
            t.getParent().addChild(poly)
            stats['caps'] = stats.get('caps', 0) + 1

e = EggData(); e.read(Filename.fromOsSpecific(src)); findGone(e); print('marbles dropped', sorted(gone)); walk(e); caps(e); collectTops(e); fitMarbles(e)
e.writeEgg(Filename.fromOsSpecific(dst)); print(stats)
