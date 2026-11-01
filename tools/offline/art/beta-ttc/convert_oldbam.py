"""Turns a version 3.x BAM (see oldbam.py) into a modern Panda3D scene.

The old scene graph kept a node's transform and render state on the arc
from its parent; here they go on the node (or, for a node instanced
under more than one parent with different states, on a node in between).
Old Geoms are rebuilt as modern GeomTriangles/GeomLines/GeomPoints with
the attributes resolved per vertex, so every old binding (overall, per
primitive, per strip triangle, per vertex) and every separate index
array comes out as the original drew it.

Textures keep their own files: each old texture name is rewritten with
`texturePrefix` in front (where the beta's maps are copied) and loaded
from there, so the written BAM points at the beta's own pictures.
"""

import math

from panda3d.core import (BillboardEffect, BitMask32, ColorAttrib, CollisionNode, CollisionPlane, CollisionPolygon,
                          CollisionSphere, CullBinAttrib, CullFaceAttrib, DecalEffect, DepthTestAttrib, DepthWriteAttrib,
                          Filename, Geom, GeomLines, GeomNode, GeomPoints, GeomTriangles, GeomVertexArrayFormat,
                          GeomVertexData, GeomVertexFormat, GeomVertexWriter, InternalName, LMatrix4f, LODNode,
                          ModelNode, ModelRoot, NodePath, PandaNode, Plane, Point3, RenderState, SamplerState,
                          SequenceNode, Texture, TextureAttrib, TexturePool, TextureStage, TextureStageCollection,
                          TransformState, TransparencyAttrib, Vec3)

import oldbam

G_OFF, G_OVERALL, G_PER_PRIM, G_PER_COMPONENT, G_PER_VERTEX = range(5)
B_COORD, B_COLOR, B_NORMAL, B_TEXCOORD = range(4)

# Plain alpha becomes dual, as the game's own models are built: the opaque
# part is drawn with the scene and only the soft edge is sorted and blended.
# With plain alpha a sign's picture was blended as one piece against its
# board and came out with a dark, stepped rim.
TRANSPARENCY = {0: TransparencyAttrib.MNone, 1: TransparencyAttrib.MDual, 2: TransparencyAttrib.MAlpha,
                3: TransparencyAttrib.MMultisample, 4: TransparencyAttrib.MMultisampleMask, 5: TransparencyAttrib.MBinary}
CULLFACE = {0: CullFaceAttrib.MCullNone, 1: CullFaceAttrib.MCullClockwise, 2: CullFaceAttrib.MCullCounterClockwise,
            3: CullFaceAttrib.MCullClockwise}
DEPTHTEST = {0: DepthTestAttrib.MNone, 1: DepthTestAttrib.MNever, 2: DepthTestAttrib.MLess, 3: DepthTestAttrib.MEqual,
             4: DepthTestAttrib.MLessEqual, 5: DepthTestAttrib.MGreater, 6: DepthTestAttrib.MNotEqual,
             7: DepthTestAttrib.MGreaterEqual, 8: DepthTestAttrib.MAlways}
TEXAPPLY = {0: TextureStage.MModulate, 1: TextureStage.MDecal, 2: TextureStage.MBlend, 3: TextureStage.MReplace,
            4: TextureStage.MAdd}
FILTERS = [SamplerState.FT_nearest, SamplerState.FT_linear, SamplerState.FT_nearest_mipmap_nearest,
           SamplerState.FT_linear_mipmap_nearest, SamplerState.FT_nearest_mipmap_linear,
           SamplerState.FT_linear_mipmap_linear]

# Old collide masks are the same bits Toontown still uses.


class Converter:
    def __init__(self, bam, texturePrefix='', textureLoader=None, log=None):
        self.bam = bam
        self.objs = bam.objects
        self.texturePrefix = texturePrefix
        self.textureLoader = textureLoader
        self.log = log or (lambda msg: None)
        self.nodes = {}
        self.textures = {}
        self.missingTextures = set()
        self.parentCount = {}
        self.skipped = set()

    # --- entry ----------------------------------------------------------
    def convert(self):
        for rec in self.objs.values():
            if rec['type'] in ('RenderRelation', 'NodeRelation'):
                self.parentCount[rec['child']] = self.parentCount.get(rec['child'], 0) + 1
        root = self.makeNode(self.bam.root)
        return NodePath(root)

    # --- nodes ----------------------------------------------------------
    def makeNode(self, objId):
        if objId in self.nodes:
            return self.nodes[objId]
        rec = self.objs[objId]
        t = rec['type']
        name = rec.get('name', '')
        if t == 'ModelRoot':
            node = ModelRoot(name)
        elif t == 'ModelNode':
            node = ModelNode(name)
            if rec.get('preserve'):
                node.setPreserveTransform(ModelNode.PTLocal)
        elif t == 'GeomNode':
            node = GeomNode(name)
            for geomId in rec['geoms']:
                geom = self.makeGeom(geomId)
                if geom is not None:
                    node.addGeom(geom)
        elif t == 'CollisionNode':
            node = CollisionNode(name)
            for solidId in rec['solids']:
                solid = self.makeSolid(solidId)
                for one in (solid if isinstance(solid, list) else [solid]):
                    if one is not None:
                        node.addSolid(one)
            node.setFromCollideMask(BitMask32(rec['fromMask']))
            node.setIntoCollideMask(BitMask32(rec['intoMask']))
        elif t == 'LODNode':
            node = LODNode(name)
            node.setCenter(Point3(*rec['center']))
            # The old LODSwitch kept its distances squared (LOD.I,
            # get_in() is sqrtf(_in)), and wrote them out that way.
            for sin, sout in rec['switches']:
                node.addSwitch(math.sqrt(max(sin, 0.0)), math.sqrt(max(sout, 0.0)))
        elif t == 'SequenceNode' and sum(len(arcs) for g, arcs in rec.get('connections', ())) <= 1:
            # A one-frame sequence (the beta's sign pictures sit under one)
            # is only a group.
            node = PandaNode(name)
        elif t == 'SequenceNode':
            node = SequenceNode(name)
            if rec['cycleTime'] > 0:
                node.setFrameRate(1.0 / rec['cycleTime'])
        elif t in ('NamedNode', 'Node', 'SwitchNodeOne') or self.bam.isA(t, 'NamedNode'):
            if self.bam.isA(t, 'NamedNode') and t not in ('NamedNode', 'SwitchNodeOne'):
                self.skipped.add(t)
            node = PandaNode(name)
        else:
            self.skipped.add(t)
            node = PandaNode(name)
        self.nodes[objId] = node
        arcs = []
        for graphType, arcIds in rec.get('connections', ()):
            if graphType not in ('RenderRelation', None):
                continue
            for arcId in arcIds:
                arc = self.objs.get(arcId)
                if arc:
                    arcs.append(arc)
        for arc in sorted(arcs, key=lambda a: a['sort']):
            self.attach(node, arc)
        return node

    def attach(self, parent, arc):
        child = self.makeNode(arc['child'])
        state, transform, effects, pruned, decal = self.arcState(arc)
        target = child
        hasState = (state != RenderState.makeEmpty() or not transform.isIdentity() or effects or decal)
        if hasState and self.parentCount.get(arc['child'], 1) > 1:
            # The same node under more than one parent: its arc's
            # state goes on a node of its own.
            target = PandaNode(child.getName())
            target.addChild(child)
        if hasState:
            target.setState(target.getState().compose(state))
            target.setTransform(transform)
            for effect in effects:
                target.setEffect(effect)
            if decal:
                target.setEffect(DecalEffect.make())
        # A PruneTransition kept the subtree from being drawn; the
        # collision traverser still walked it (the gazebo's collisions
        # sit under one), so it is hidden rather than stashed.
        if pruned:
            target.setOverallHidden(True)
        parent.addChild(target, arc['sort'])

    def arcState(self, arc):
        state = RenderState.makeEmpty()
        transform = TransformState.makeIdentity()
        effects = []
        pruned = False
        decal = False
        for tid in arc['transitions']:
            tr = self.objs.get(tid)
            if tr is None:
                continue
            t = tr['type']
            if t == 'TransformTransition':
                transform = TransformState.makeMat(LMatrix4f(*tr['matrix']))
            elif t == 'TextureTransition':
                if tr['direction'] == 2:
                    state = state.addAttrib(TextureAttrib.makeAllOff())
                elif tr['direction'] == 1:
                    tex = self.makeTexture(tr['texture'])
                    if tex is not None:
                        state = state.addAttrib(TextureAttrib.make(tex))
            elif t == 'TransparencyTransition':
                state = state.addAttrib(TransparencyAttrib.make(TRANSPARENCY.get(tr['mode'], TransparencyAttrib.MAlpha)))
            elif t == 'CullFaceTransition':
                state = state.addAttrib(CullFaceAttrib.make(CULLFACE.get(tr['mode'], CullFaceAttrib.MCullClockwise)))
            elif t == 'DepthTestTransition':
                state = state.addAttrib(DepthTestAttrib.make(DEPTHTEST.get(tr['mode'], DepthTestAttrib.MLess)))
            elif t == 'DepthWriteTransition':
                if tr['direction'] == 2:
                    state = state.addAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
                elif tr['direction'] == 1:
                    state = state.addAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOn))
            elif t == 'ColorTransition':
                if tr['direction'] == 1:
                    state = state.addAttrib(ColorAttrib.makeFlat(tuple(tr['color'])))
                elif tr['direction'] == 2:
                    state = state.addAttrib(ColorAttrib.makeVertex())
            elif t == 'GeomBinTransition':
                if tr['direction'] == 1:
                    state = state.addAttrib(CullBinAttrib.make(tr['bin'], tr['drawOrder']))
            elif t == 'BillboardTransition':
                up = Vec3(*tr['up'])
                if tr['axial']:
                    effects.append(BillboardEffect.make(up, tr['eyeRelative'], True, 0, NodePath(), Point3(0, 0, 0)))
                else:
                    effects.append(BillboardEffect.make(up, tr['eyeRelative'], False, 0, NodePath(), Point3(0, 0, 0)))
            elif t == 'PruneTransition':
                pruned = True
            elif t == 'DecalTransition':
                decal = tr['direction'] == 1
            elif t == 'TextureApplyTransition':
                mode = TEXAPPLY.get(tr['mode'], TextureStage.MModulate)
                if mode != TextureStage.MModulate:
                    tex = state.getAttrib(TextureAttrib)
                    self.log('texture apply mode %d kept as modulate' % tr['mode'])
            else:
                self.skipped.add(t)
        return state, transform, effects, pruned, decal

    # --- textures -------------------------------------------------------
    def makeTexture(self, texId):
        if texId in self.textures:
            return self.textures[texId]
        rec = self.objs.get(texId)
        tex = None
        if rec is not None:
            name = rec['name']
            alpha = rec['alphaName']
            if self.textureLoader:
                tex = self.textureLoader(name, alpha)
            if tex is None:
                self.missingTextures.add(name)
            else:
                tex.setWrapU(SamplerState.WM_repeat if rec['wrapu'] else SamplerState.WM_clamp)
                tex.setWrapV(SamplerState.WM_repeat if rec['wrapv'] else SamplerState.WM_clamp)
                if rec['minfilter'] < len(FILTERS):
                    tex.setMinfilter(FILTERS[rec['minfilter']])
                if rec['magfilter'] < len(FILTERS):
                    tex.setMagfilter(FILTERS[rec['magfilter']])
                if rec['anisotropic'] > 1:
                    tex.setAnisotropicDegree(rec['anisotropic'])
        self.textures[texId] = tex
        return tex

    # --- collisions -----------------------------------------------------
    def makeSolid(self, solidId):
        rec = self.objs.get(solidId)
        if rec is None:
            return None
        t = rec['type']
        if t == 'CollisionPolygon':
            a, b, c, d = rec['plane']
            pts = []
            for u, v in rec['points']:
                if rec['axis'] == 0:
                    pts.append(Point3(-(b * u + c * v + d) / a, u, v))
                elif rec['axis'] == 1:
                    pts.append(Point3(u, -(a * u + c * v + d) / b, v))
                else:
                    pts.append(Point3(u, v, -(a * u + b * v + d) / c))
            if rec['reversed']:
                pts.reverse()
            solid = self.polygon(pts)
        elif t == 'CollisionSphere':
            solid = CollisionSphere(Point3(*rec['center']), rec['radius'])
        elif t == 'CollisionPlane':
            solid = CollisionPlane(Plane(*rec['plane']))
        else:
            self.skipped.add(t)
            return None
        if not rec.get('tangible', True):
            for one in (solid if isinstance(solid, list) else [solid]):
                if one is not None:
                    one.setTangible(False)
        return solid

    def polygon(self, pts):
        if len(pts) < 3:
            return None
        # CollisionPolygon takes 3 or 4 points, or a whole list.
        try:
            if len(pts) == 3:
                return CollisionPolygon(*pts)
            if len(pts) == 4:
                return CollisionPolygon(*pts)
            poly = CollisionPolygon(pts[0], pts[1], pts[2])
            poly.setupPoints(pts)  # not exposed in every build
            return poly
        except Exception:
            # A fan of triangles over the same plane is the same wall.
            self.log('collision polygon with %d points split up' % len(pts))
            return [CollisionPolygon(pts[0], pts[i], pts[i + 1]) for i in range(1, len(pts) - 1)]

    # --- geometry -------------------------------------------------------
    def makeGeom(self, geomId):
        rec = self.objs.get(geomId)
        if rec is None or rec.get('unknown'):
            return None
        t = rec['type']
        bind = rec['bind']
        lengths = rec['primlengths']
        n = rec['numprims']
        # Each old primitive as a list of vertex numbers, and the
        # "component" (strip triangle) each modern triangle comes from.
        prims = []
        pos = 0
        if t == 'GeomTri':
            for _ in range(n):
                prims.append(('tris', 3))
        elif t == 'GeomQuad':
            for _ in range(n):
                prims.append(('fan', 4))
        elif t in ('GeomTristrip', 'GeomTrifan', 'GeomPolygon', 'GeomLinestrip'):
            kind = {'GeomTristrip': 'strip', 'GeomTrifan': 'fan', 'GeomPolygon': 'fan', 'GeomLinestrip': 'linestrip'}[t]
            for i in range(n):
                prims.append((kind, lengths[i] if i < len(lengths) else 0))
        elif t == 'GeomLine':
            for _ in range(n):
                prims.append(('line', 2))
        elif t == 'GeomPoint':
            for _ in range(n):
                prims.append(('point', 1))
        else:
            self.skipped.add(t)
            return None

        def fetch(values, index, k):
            if not values:
                return None
            if index:
                if k >= len(index):
                    return None
                k = index[k]
            if k >= len(values):
                return None
            return values[k]

        hasColor = bind[B_COLOR] != G_OFF and rec['colors']
        hasNormal = bind[B_NORMAL] != G_OFF and rec['norms']
        hasUV = bind[B_TEXCOORD] != G_OFF and rec['texcoords']

        counters = {B_COORD: 0, B_COLOR: 0, B_NORMAL: 0, B_TEXCOORD: 0}
        arrays = {B_COORD: (rec['coords'], rec['vindex']), B_COLOR: (rec['colors'], rec['cindex']),
                  B_NORMAL: (rec['norms'], rec['nindex']), B_TEXCOORD: (rec['texcoords'], rec['tindex'])}

        # Walk every primitive, gathering the vertices with their
        # attributes, then cut them into triangles/lines/points.
        out = []   # (kind, [vertex tuples])
        for kind, length in prims:
            primAttr = {}
            for a in (B_COLOR, B_NORMAL, B_TEXCOORD):
                if bind[a] == G_OVERALL:
                    primAttr[a] = fetch(*arrays[a], 0)
                elif bind[a] == G_PER_PRIM:
                    primAttr[a] = fetch(*arrays[a], counters[a])
                    counters[a] += 1
            verts = []
            compAttr = []
            for v in range(length):
                attrs = {B_COORD: fetch(*arrays[B_COORD], counters[B_COORD])}
                counters[B_COORD] += 1
                for a in (B_COLOR, B_NORMAL, B_TEXCOORD):
                    if bind[a] == G_PER_VERTEX:
                        attrs[a] = fetch(*arrays[a], counters[a])
                        counters[a] += 1
                    elif a in primAttr:
                        attrs[a] = primAttr[a]
                verts.append(attrs)
            if kind in ('strip', 'fan', 'tris'):
                ncomp = max(length - 2, 0) if kind != 'tris' else 1
            elif kind == 'linestrip':
                ncomp = max(length - 1, 0)
            else:
                ncomp = 1
            for c in range(ncomp):
                ca = {}
                for a in (B_COLOR, B_NORMAL, B_TEXCOORD):
                    if bind[a] == G_PER_COMPONENT:
                        ca[a] = fetch(*arrays[a], counters[a])
                        counters[a] += 1
                compAttr.append(ca)
            out.append((kind, verts, compAttr))

        fmt = GeomVertexArrayFormat()
        fmt.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
        if hasNormal:
            fmt.addColumn(InternalName.getNormal(), 3, Geom.NTFloat32, Geom.CNormal)
        if hasColor:
            fmt.addColumn(InternalName.getColor(), 4, Geom.NTUint8, Geom.CColor)
        if hasUV:
            fmt.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
        vformat = GeomVertexFormat.registerFormat(GeomVertexFormat(fmt))
        vdata = GeomVertexData(rec['type'], vformat, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, 'vertex')
        nw = GeomVertexWriter(vdata, 'normal') if hasNormal else None
        cw = GeomVertexWriter(vdata, 'color') if hasColor else None
        tw = GeomVertexWriter(vdata, 'texcoord') if hasUV else None
        rows = [0]

        def emit(attrs, comp):
            p = attrs.get(B_COORD) or (0, 0, 0)
            vw.addData3f(*p)
            if nw:
                v = comp.get(B_NORMAL) or attrs.get(B_NORMAL) or (0, 0, 1)
                nw.addData3f(*v)
            if cw:
                v = comp.get(B_COLOR) or attrs.get(B_COLOR) or (1, 1, 1, 1)
                cw.addData4f(*v)
            if tw:
                v = comp.get(B_TEXCOORD) or attrs.get(B_TEXCOORD) or (0, 0)
                tw.addData2f(*v)
            rows[0] += 1
            return rows[0] - 1

        tris = GeomTriangles(Geom.UHStatic)
        lines = GeomLines(Geom.UHStatic)
        points = GeomPoints(Geom.UHStatic)
        for kind, verts, comps in out:
            if kind == 'tris':
                if len(verts) == 3:
                    tris.addVertices(emit(verts[0], comps[0]), emit(verts[1], comps[0]), emit(verts[2], comps[0]))
            elif kind == 'strip':
                for i in range(len(verts) - 2):
                    comp = comps[i]
                    if i % 2 == 0:
                        tri = (verts[i], verts[i + 1], verts[i + 2])
                    else:
                        tri = (verts[i + 1], verts[i], verts[i + 2])
                    tris.addVertices(*(emit(v, comp) for v in tri))
            elif kind == 'fan':
                for i in range(len(verts) - 2):
                    comp = comps[i]
                    tri = (verts[0], verts[i + 1], verts[i + 2])
                    tris.addVertices(*(emit(v, comp) for v in tri))
            elif kind == 'linestrip':
                for i in range(len(verts) - 1):
                    lines.addVertices(emit(verts[i], comps[i]), emit(verts[i + 1], comps[i]))
            elif kind == 'line':
                if len(verts) == 2:
                    lines.addVertices(emit(verts[0], comps[0]), emit(verts[1], comps[0]))
            elif kind == 'point':
                points.addVertex(emit(verts[0], comps[0]))
        geom = Geom(vdata)
        for prim in (tris, lines, points):
            if prim.getNumVertices():
                geom.addPrimitive(prim)
        if not geom.getNumPrimitives():
            return None
        return geom


def convert(path, texturePrefix='', textureLoader=None, log=None):
    bam = oldbam.read_bam(path)
    conv = Converter(bam, texturePrefix, textureLoader, log)
    np = conv.convert()
    return np, conv
