"""Reads Panda3D version 3.x BAM files (the 2001 scene graph).

Toontown's beta 1.0.5 install keeps its models as version 3.3 BAMs, from
the days of Panda's old scene graph: Nodes joined by RenderRelation arcs,
each arc carrying "transitions" (transform, texture, transparency...) and
GeomNodes holding the old Geom primitives with their own index arrays.
Panda 1.10 only reads 6.14 and newer, so this reads the old files itself.

Every field layout here follows the write_datagram/fillin pair of that
class in Panda's own source from 2001 (panda3d git, the parent of
fc6db22bb, when the BAM version was 3.3).

read_bam(path) gives back an OldBam: .objects maps an object id to a
plain record (a dict with 'type' and its fields) and .root is the id of
the first object, the model's root node.
"""

import struct


class OldBamError(Exception):
    pass


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def remaining(self):
        return len(self.d) - self.p

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def bool(self):
        return self.u8() != 0

    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]
        self.p += 2
        return v

    def i16(self):
        v = struct.unpack_from('<h', self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]
        self.p += 4
        return v

    def f32(self):
        v = struct.unpack_from('<f', self.d, self.p)[0]
        self.p += 4
        return v

    def floats(self, n):
        v = struct.unpack_from('<%df' % n, self.d, self.p)
        self.p += 4 * n
        return v

    def string(self):
        n = self.u16()
        v = self.d[self.p:self.p + n].decode('latin-1')
        self.p += n
        return v


class OldBam:
    def __init__(self, path):
        self.path = path
        data = open(path, 'rb').read()
        if data[:6] != b'pbj\x00\n\r':
            raise OldBamError('%s is not a BAM file' % path)
        self.datagrams = []
        p = 6
        while p < len(data):
            n = struct.unpack_from('<I', data, p)[0]
            p += 4
            self.datagrams.append(data[p:p + n])
            p += n
        header = Reader(self.datagrams[0])
        self.major = header.u16()
        self.minor = header.u16()
        if self.major != 3:
            raise OldBamError('%s is BAM %d.%d, not 3.x' % (path, self.major, self.minor))
        self.types = {}      # index -> name
        self.parents = {}    # name -> [parent names]
        self.ptas = {}       # pta id -> list
        self.objects = {}
        self.root = None
        self.unknown = set()
        for dg in self.datagrams[1:]:
            self.readObject(Reader(dg))

    # Type handles: an index, followed the first time by the name and
    # the handles of the parent classes.
    def handle(self, r):
        i = r.u16()
        if i == 0:
            return None
        if i in self.types:
            return self.types[i]
        name = r.string()
        n = r.u8()
        parents = [self.handle(r) for _ in range(n)]
        self.types[i] = name
        self.parents[name] = parents
        return name

    def isA(self, name, base):
        if name == base:
            return True
        for parent in self.parents.get(name, ()):
            if parent and self.isA(parent, base):
                return True
        return False

    def readObject(self, r):
        typeName = self.handle(r)
        objId = r.u16()
        if typeName is None:
            return
        if self.root is None:
            self.root = objId
        rec = {'type': typeName, 'id': objId}
        self.objects[objId] = rec
        reader = self.findReader(typeName)
        if reader is None:
            self.unknown.add(typeName)
            rec['unknown'] = True
            return
        reader(self, r, rec)
        if r.remaining():
            rec['leftover'] = r.remaining()

    def findReader(self, typeName):
        if typeName in READERS:
            return READERS[typeName]
        return None

    # A PointerToArray: an id, then (the first time, or when the id is 0)
    # a 32-bit count and the elements.
    def pta(self, r, elemReader):
        i = r.u16()
        if i != 0 and i in self.ptas:
            return self.ptas[i]
        n = r.u32()
        arr = [elemReader(r) for _ in range(n)]
        if i != 0:
            self.ptas[i] = arr
        return arr


# --- graph -----------------------------------------------------------------

def readNode(bam, r, rec):
    conns = []
    for _ in range(r.u16()):
        graphType = bam.handle(r)
        arcs = [r.u16() for _ in range(r.u16())]
        conns.append((graphType, arcs))
    rec['connections'] = conns


def readNamedNode(bam, r, rec):
    readNode(bam, r, rec)
    rec['name'] = r.string()


def readModelNode(bam, r, rec):
    readNamedNode(bam, r, rec)
    rec['preserve'] = r.bool() if bam.minor >= 2 else False


def readGeomNode(bam, r, rec):
    readNamedNode(bam, r, rec)
    rec['geoms'] = [r.u16() for _ in range(r.u16())]


def readCollisionNode(bam, r, rec):
    readNamedNode(bam, r, rec)
    rec['solids'] = [r.u16() for _ in range(r.u16())]
    rec['fromMask'] = r.u32()
    rec['intoMask'] = r.u32()
    rec['collideGeom'] = r.bool()


def readLODNode(bam, r, rec):
    readNamedNode(bam, r, rec)
    rec['center'] = r.floats(3)
    rec['switches'] = [r.floats(2) for _ in range(r.u16())]


def readSequenceNode(bam, r, rec):
    readNamedNode(bam, r, rec)
    rec['cycleTime'] = r.f32()
    rec['elementCount'] = r.u16()


def readRelation(bam, r, rec):
    rec['graphType'] = bam.handle(r)
    rec['parent'] = r.u16()
    rec['child'] = r.u16()
    rec['sort'] = r.u16()
    rec['transitions'] = [r.u16() for _ in range(r.u16())]


# --- transitions -----------------------------------------------------------

def readNodeTransition(bam, r, rec):
    rec['priority'] = r.u16()


def readOnOff(bam, r, rec):
    readNodeTransition(bam, r, rec)
    rec['direction'] = r.u8()   # 0 identity, 1 on, 2 off


def readMatrixTransition(bam, r, rec):
    readNodeTransition(bam, r, rec)
    rec['matrix'] = r.floats(16)


def readTextureTransition(bam, r, rec):
    readOnOff(bam, r, rec)
    rec['texture'] = r.u16()


def readModeTransition(bam, r, rec):
    # TransparencyTransition, CullFaceTransition, TextureApplyTransition,
    # DepthTestTransition: an OnTransition plus a one-byte mode.
    readNodeTransition(bam, r, rec)
    rec['mode'] = r.u8()


def readColorTransition(bam, r, rec):
    readOnOff(bam, r, rec)
    rec['color'] = r.floats(4)
    rec['real'] = r.bool()


def readBillboard(bam, r, rec):
    readNodeTransition(bam, r, rec)
    rec['up'] = r.floats(3)
    rec['eyeRelative'] = r.u8() != 0
    rec['axial'] = r.u8() != 0


def readGeomBin(bam, r, rec):
    readOnOff(bam, r, rec)
    rec['bin'] = r.string()
    rec['drawOrder'] = r.i32()


# --- geometry --------------------------------------------------------------

def readGeom(bam, r, rec):
    v3 = lambda rr: rr.floats(3)
    v4 = lambda rr: rr.floats(4)
    v2 = lambda rr: rr.floats(2)
    us = lambda rr: rr.u16()
    rec['coords'] = bam.pta(r, v3)
    rec['norms'] = bam.pta(r, v3)
    rec['colors'] = bam.pta(r, v4)
    rec['texcoords'] = bam.pta(r, v2)
    rec['vindex'] = bam.pta(r, us)
    rec['nindex'] = bam.pta(r, us)
    rec['cindex'] = bam.pta(r, us)
    rec['tindex'] = bam.pta(r, us)
    rec['numprims'] = r.u16()
    rec['primlengths'] = bam.pta(r, lambda rr: rr.u32())
    # coord, color, normal, texcoord: off, overall, per prim,
    # per component, per vertex.
    rec['bind'] = [r.u8() for _ in range(4)]


def readGeomWidth(bam, r, rec):
    readGeom(bam, r, rec)
    rec['width'] = r.u32()


def readTexture(bam, r, rec):
    rec['name'] = r.string()
    rec['alphaName'] = r.string()
    r.u32()
    rec['wrapu'] = r.u8()
    rec['wrapv'] = r.u8()
    rec['minfilter'] = r.u8()
    rec['magfilter'] = r.u8()
    r.u16()
    rec['anisotropic'] = r.i16()
    if r.remaining() > 0:
        if r.bool():
            rec['format'] = r.u8()
            if r.remaining() > 0:
                rec['components'] = r.u8()


# --- collisions ------------------------------------------------------------

def readCollisionSolid(bam, r, rec):
    rec['tangible'] = r.u8() != 0


def readCollisionPolygon(bam, r, rec):
    readCollisionSolid(bam, r, rec)
    rec['plane'] = r.floats(4)
    rec['points'] = [r.floats(2) for _ in range(r.u16())]
    rec['median'] = r.floats(2)
    rec['axis'] = r.u8()
    rec['reversed'] = r.u8() != 0


def readCollisionPlane(bam, r, rec):
    readCollisionSolid(bam, r, rec)
    rec['plane'] = r.floats(4)


def readCollisionSphere(bam, r, rec):
    readCollisionSolid(bam, r, rec)
    rec['center'] = r.floats(3)
    rec['radius'] = r.f32()


READERS = {
    'Node': readNode,
    'NamedNode': readNamedNode,
    'ModelNode': readModelNode,
    'ModelRoot': readModelNode,
    'GeomNode': readGeomNode,
    'CollisionNode': readCollisionNode,
    'LODNode': readLODNode,
    'SwitchNodeOne': readNamedNode,
    'SequenceNode': readSequenceNode,
    'RenderRelation': readRelation,
    'NodeRelation': readRelation,
    'TransformTransition': readMatrixTransition,
    'TextureTransition': readTextureTransition,
    'TransparencyTransition': readModeTransition,
    'CullFaceTransition': readModeTransition,
    'TextureApplyTransition': readModeTransition,
    'DepthTestTransition': readModeTransition,
    'DepthWriteTransition': readOnOff,
    'ColorTransition': readColorTransition,
    'BillboardTransition': readBillboard,
    'GeomBinTransition': readGeomBin,
    'PruneTransition': readNodeTransition,
    'DecalTransition': readOnOff,
    'Geom': readGeom,
    'GeomTri': readGeom,
    'GeomTristrip': readGeom,
    'GeomTrifan': readGeom,
    'GeomQuad': readGeom,
    'GeomPolygon': readGeom,
    'GeomLine': readGeomWidth,
    'GeomLinestrip': readGeomWidth,
    'GeomPoint': readGeomWidth,
    'Texture': readTexture,
    'CollisionPolygon': readCollisionPolygon,
    'CollisionPlane': readCollisionPlane,
    'CollisionSphere': readCollisionSphere,
}


def read_bam(path):
    return OldBam(path)
