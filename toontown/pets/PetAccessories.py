"""
Toon accessories that a doodle can wear: a hat, glasses and a backpack.

A doodle's accessories are six numbers, saved on the doodle (setAccessories):
[hat, hatTexture, glasses, glassesTexture, backpack, backpackTexture], with
the model and texture numbers of ToonDNA's accessory lists (0 = nothing).

Every accessory model was made for a toon's head or back. The doodle wears
it on its neck joint, which carries its eyes (so it follows the face in
every animation) or on its back, through a shared base placement for each kind
(BASE) and the small corrections that one model needs (FITS).
"""

from panda3d.core import Texture, NodePath, Point3, Vec3, GeomVertexRewriter
from toontown.toon import ToonDNA

HAT, GLASSES, BACKPACK = range(3)
KINDS = (HAT, GLASSES, BACKPACK)
NoAccessories = [0, 0, 0, 0, 0, 0]

HEAD_JOINT = 'joint_neck'
BACK_JOINT = 'joint_Backspine2'
JOINTS = {HAT: HEAD_JOINT, GLASSES: HEAD_JOINT, BACKPACK: BACK_JOINT}
# Back items that are worn round the neck instead, so they follow the head.
NECK_ITEMS = {BACKPACK: (26, 27)}


def getJointName(kind, model):
    if model in NECK_ITEMS.get(kind, ()):
        return HEAD_JOINT
    return JOINTS[kind]


def modelList(kind):
    return (ToonDNA.HatModels, ToonDNA.GlassesModels, ToonDNA.BackpackModels)[kind]


def textureList(kind):
    return (ToonDNA.HatTextures, ToonDNA.GlassesTextures, ToonDNA.BackpackTextures)[kind]


def styleDict(kind):
    return (ToonDNA.HatStyles, ToonDNA.GlassesStyles, ToonDNA.BackpackStyles)[kind]


_choices = {}


def getChoices(kind):
    # Every look of this kind that a toon can wear: (model, texture) pairs
    # from ToonDNA's styles, in model order, starting with "nothing".
    if kind not in _choices:
        seen = set()
        for model, texture, color in styleDict(kind).values():
            if model and model < len(modelList(kind)):
                seen.add((model, texture))
        _choices[kind] = [(0, 0)] + sorted(seen)
    return _choices[kind]


def isValid(accessories):
    if len(accessories) != 6:
        return False
    for kind in KINDS:
        pair = (accessories[kind * 2], accessories[kind * 2 + 1])
        if pair not in getChoices(kind):
            return False
    return True


def getPair(accessories, kind):
    return (accessories[kind * 2], accessories[kind * 2 + 1])


def setPair(accessories, kind, pair):
    accessories = list(accessories)
    accessories[kind * 2], accessories[kind * 2 + 1] = pair
    return accessories


# Base placement on the joint: (x, y, z), (h, p, r), scale.
BASE = {HAT: ((0.0, 0.19, 0.41), (180.0, 8.0, 0.0), 0.2),
        GLASSES: ((0.0, 0.38, 0.24), (180.0, 0.0, 0.0), 0.16),
        BACKPACK: ((0.0, -0.55, 0.0), (180.0, 0.0, 0.0), 0.28)}

# Corrections for single models, by kind and model number:
# (dy, dz, scale, pitch) added to (or, for scale, multiplied with) BASE.
FITS = {HAT: {3: (-0.17, -0.02, 1.0, 0.0),    # bow, on top of the head, not the forehead
              4: (-0.1, -0.02, (0.85, 0.55, 1.0), 0.0),  # heart headband, across the top
              6: (0.0, -0.04, 1.0, 0.0),      # anvil
              7: (-0.09, -0.065, 1.0, 0.0),   # flower pot, centred on the top of the head
              8: (0.0, -0.03, 1.0, 0.0),      # sandbag
              9: (-0.13, 0.01, 1.0, 0.0),     # weight, centred on the top of the head
              11: (0.0, -0.01, 1.0, 0.0),     # golf hat
              14: (-0.05, -0.055, 1.0, 10.0),  # crown, level, on the top of the head
              19: (0.0, 0.04, 0.85, 0.0),     # sombrero, eyes show under the brim
              21: (-0.02, -0.015, 0.72, -15.0),   # sun hat, tipped back so the eyes show
              23: (0.0, -0.14, (0.8, 0.85, 0.9), 0.0),  # beehive hairdo, narrowed to the head, curls at the brow
              30: (0.0, -0.118, (0.9, 1.25, 1.0), 0.0),  # feather headband, round the forehead (the head is deeper than wide)
              31: (-0.02, -0.22, 0.6, 12.0),  # pompadour
              33: (0.0, -0.09, 1.0, 0.0),     # robin hood hat
              36: (-0.12, 0.0, 1.0, 0.0),     # tiara, on top of the head
              38: (0.0, 0.02, 0.85, 0.0),     # witch hat
              39: (0.0, 0.02, 0.85, 0.0),     # wizard hat
              42: (0.0, 0.03, 0.85, 0.0),     # foil pyramid
              47: (-0.05, -0.1, (0.7, 0.8, 0.95), 0.0),  # rainbow afro, narrowed so it sits down on the head
              54: (0.0, 0.16, 1.0, 0.0),      # dinosaur
              16: (0.0, -0.075, 1.0, 0.0),     # pirate hat, down on the head
              22: (0.0, -0.035, 1.0, 0.0),     # antenna headband
              28: (0.0, -0.08, 1.0, 0.0),      # fedora, down on the head
              34: (0.0, -0.055, 1.0, 0.0),     # roman helmet
              35: (0.0, -0.035, 1.0, 0.0),     # spider antenna headband
              40: (0.0, -0.025, 1.0, 0.0),     # conquistador helmet
              41: (0.0, -0.025, 1.0, 0.0),     # firefighter helmet
              50: (0.0, -0.06, 1.0, 0.0),      # bobby hat
              10: (-0.09, 0.0, 1.0, 0.0),      # fez, on the top of the head
              12: (-0.06, -0.015, 1.0, 0.0),    # party hat, on the top of the head
              56: (-0.09, 0.02, 1.0, 0.0),      # bird nest, on the top of the head
              61: (-0.09, 0.02, 1.0, 0.0),      # bird nest B
              62: (-0.09, 0.0, 1.0, 0.0),       # fez B
              # The extra models were made about 3.6 times smaller.
              57: (-0.04, -0.04, 4.0, 0.0),     # ball hat, round the whole head top
              58: (0.0, -0.03, 3.6, 0.0),     # elf hat
              59: (-0.02, -0.015, 0.72, -15.0),   # sun hat B, tipped back
              60: (0.0, 0.01, 3.6, 0.0)},     # winter hat
        # Glasses: each frame is sized to the doodle's eyes (outline and all)
        # and centred on them, stretched taller where it has to be, then set
        # back until it rests on the front of the eyes without them showing
        # through. Measured from renders of the real eye shapes.
        GLASSES: {1: (-0.07, -0.025, (0.662, 1.0, 1.205), 0.0),  # round glasses
                  2: (-0.08, -0.02, (0.714, 1.0, 1.571), 0.0),  # shutter shades
                  3: (-0.09, -0.038, (0.65, 1.0, 1.43), 0.0),  # narrow glasses
                  4: (-0.07, -0.022, (0.733, 1.0, 1.613), 0.0),  # star glasses
                  5: (-0.09, -0.045, (0.784, 1.0, 1.726), 0.0),  # 3D glasses
                  6: (-0.11, -0.044, (0.674, 1.0, 1.483), 0.0),  # aviators
                  7: (-0.09, -0.039, (0.554, 1.0, 1.218), 0.0),  # cat eye glasses
                  8: (-0.09, -0.01, (0.7, 1.0, 1.75), 0.0),  # nerd glasses
                  9: (-0.09, -0.022, (0.661, 1.0, 1.316), 0.0),  # Jackie O shades
                  10: (-0.07, -0.077, (0.654, 1.0, 1.167), 0.0),  # scuba mask
                  11: (-0.07, -0.091, (0.696, 1.0, 1.429), 0.0),  # goggles
                  12: (-0.05, -0.2, (0.7, 1.0, 1.5), 0.0),  # Groucho glasses
                  13: (-0.1, -0.132, (0.601, 1.0, 1.322), 0.0),  # heart glasses
                  14: (-0.05, -0.152, (0.687, 1.0, 1.51), 0.0),  # insect eye glasses
                  15: (0.12, -0.158, (0.455, 1.0, 0.954), 0.0),  # domino mask
                  16: (0.03, -0.145, (0.5, 1.0, 0.564), 0.0),  # masquerade mask
                  18: (-0.05, -0.133, (0.695, 1.0, 1.53), 0.0),  # lips glasses
                  19: (-0.08, -0.025, (0.646, 1.0, 1.32), 0.0),  # square rims
                  21: (-0.03, -0.083, (0.484, 1.0, 1.066), 0.0),  # alien glasses
                  26: (-0.07, -0.025, (0.662, 1.0, 1.205), 0.0),  # round glasses B
                  27: (-0.09, -0.044, (0.537, 1.0, 1.181), 0.0),  # starry cat eyes
                  28: (-0.05, -0.146, (0.674, 1.0, 1.483), 0.0)},  # starry round glasses
        # Only the dinosaur tail: the rest of the back items use BACK_FITS.
        BACKPACK: {21: (-0.13, -0.3, 0.6, 0.0)}}    # dinosaur tail, out of the rump
# Models placed on their own instead: (x, y, z), (h, p, r), scale.
# The moustaches face forward from the middle of the head, so they hang
# under the eyes, over the doodle's mouth.
# Glasses whose back parts are not plain arms (the masks and the scuba
# mask's snorkel) or that have none (moustaches): left unbent.
UNBENT_GLASSES = (10, 15, 16, 23, 24, 25)
OVERRIDES = {HAT: {}, GLASSES: {
    17: ((-0.095, 0.56, 0.03), (180.0, 0.0, 0.0), 0.215),  # monocle, on one eye
    20: ((0.09, 0.36, 0.17), (180.0, 0.0, 0.0), 0.21),   # eye patch, over one whole eye
    22: ((0.0, 0.33, 0.26), (0.0, 0.0, 0.0), (0.55, 0.55, 0.92))}, BACKPACK: {   # snow goggles
    26: ((0.0, 0.18, -0.32), (180.0, 0.0, 0.0), 1.6),   # scarf, round the neck
    27: ((0.0, 0.6, -0.17), (0.0, 0.0, 0.0), 0.27)}}    # bow tie, under the mouth
for _model, (_top, _back, _s) in {23: (-0.22, 0.42, 0.5), 24: (-0.33, 0.43, 0.42),
                                  25: (-0.21, 0.47, 0.5)}.items():
    OVERRIDES[GLASSES][_model] = ((0.0, 0.57 - _back * _s, 0.12 - _top * _s), (0.0, 0.0, 0.0), _s)

# A doodle sits up like a toon: its back is the back of its upright body,
# from the top of its hips (a ledge at z 0.03, behind it the hips stick out)
# up to its head. Packs stand on that ledge against the back, wings and
# fins come out of the middle of the back, capes hang from the top of it.
# model: (way, size, y, z, pitch[, squeeze]) in the back joint's space: size is how
# tall it is (packs) or its longest side (the rest); (y, z) is where its
# contact point goes: a pack's bottom back edge, a wing's root, a cape's
# top edge. The y and z were measured by moving each one onto the body
# until it touched without going in. squeeze moves a pair of wings that
# far in toward each other (see _squeeze).
BACK_FITS = {
    1: ('pack', 0.7, -0.02, -0.17, -18.0),  # backpack
    2: ('wing', 0.8, 0.04, 0.2, 0.0, 0.1),  # batWings
    3: ('wing', 0.8, 0.04, 0.3, 0.0, 0.1),  # beeWings
    4: ('wing', 0.8, 0.04, 0.3, 0.0, 0.1),  # dragonFlyWings
    5: ('pack', 0.7, -0.13, -0.08, -30.0),  # scubaTank
    6: ('wing', 0.6, 0.04, 0.12, 0.0),  # sharkFin
    7: ('wing', 0.8, -0.03, 0.2, 0.0, 0.1),  # angelWings
    8: ('pack', 0.7, 0.02, -0.01, -18.0),  # backpackWithToys
    9: ('wing', 0.8, 0.06, 0.4, 0.0, 0.06),  # butterflyWings
    10: ('wing', 0.8, 0.04, 0.35, 0.0, 0.1),  # dragonWing
    11: ('pack', 0.7, -0.01, -0.1, -18.0),  # jetPack
    12: ('wing', 0.8, 0.04, 0.3, 0.0, 0.1),  # spiderLegs
    13: ('pack', 0.7, -0.09, -0.08, -30.0),  # stuffedAnimalBackpackA
    14: ('wing', 0.8, -0.04, 0.2, 0.0, 0.1),  # birdWings
    15: ('pack', 0.7, -0.09, -0.08, -30.0),  # stuffedAnimalBackpackCat
    16: ('pack', 0.7, -0.08, -0.08, -30.0),  # stuffedAnimalBackpackDog
    17: ('wing', 1.1, 0.02, 0.14, 0.0),  # airplane
    18: ('pack', 0.6, -0.2, -0.18, -35.0),  # woodenSword
    19: ('cape', 0.7, 0.08, 0.4, -30.0),  # supertoonCape
    20: ('cape', 0.7, 0.08, 0.4, -30.0),  # vampireCape
    22: ('pack', 0.7, -0.1, -0.08, -30.0),  # band
    23: ('pack', 0.7, -0.06, -0.08, -30.0),  # gags
    24: ('pack', 0.7, -0.02, -0.08, -30.0),  # flunky
    25: ('pack', 0.7, -0.04, -0.08, -30.0),  # santa
    28: ('pack', 0.7, -0.08, -0.08, -30.0),  # creamPack
    29: ('pack', 0.7, 0.07, -0.08, -30.0),  # jellybeanJar
    30: ('pack', 0.7, 0.01, -0.04, -18.0),  # lipstickPack
    31: ('pack', 0.7, 0.13, -0.08, -30.0),  # oilJar
    32: ('pack', 0.7, 0.01, -0.08, -30.0),  # trashLid
}


# How far the doodle's head reaches to each side (half its width), on the
# neck joint, measured by slicing the head mesh in its neutral pose.
# Rows go up the head (z 0.0, 0.05 .. 0.5), columns from the back of the
# head to the front (y 0.0, 0.05 .. 0.45).
HEAD_HALF_WIDTH = (
    (0.275, 0.322, 0.316, 0.312, 0.308, 0.304, 0.300, 0.295, 0.261, 0.225),
    (0.177, 0.313, 0.304, 0.294, 0.284, 0.274, 0.263, 0.251, 0.217, 0.180),
    (0.091, 0.188, 0.250, 0.285, 0.274, 0.262, 0.249, 0.237, 0.206, 0.172),
    (0.085, 0.162, 0.223, 0.247, 0.256, 0.244, 0.232, 0.220, 0.182, 0.148),
    (0.090, 0.151, 0.206, 0.219, 0.236, 0.226, 0.214, 0.198, 0.156, 0.122),
    (0.096, 0.147, 0.189, 0.202, 0.217, 0.206, 0.196, 0.176, 0.134, 0.053),
    (0.090, 0.139, 0.173, 0.187, 0.194, 0.184, 0.173, 0.140, 0.093, 0.0),
    (0.081, 0.130, 0.158, 0.171, 0.171, 0.161, 0.139, 0.098, 0.0, 0.0),
    (0.068, 0.119, 0.141, 0.155, 0.147, 0.136, 0.097, 0.0, 0.0, 0.0),
    (0.043, 0.104, 0.120, 0.123, 0.115, 0.083, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.017, 0.058, 0.074, 0.065, 0.0, 0.0, 0.0, 0.0, 0.0))


def headHalfWidth(y, z):
    # Bilinear look-up in HEAD_HALF_WIDTH; 0 where there is no head.
    if z < 0.0 or z > 0.5:
        return 0.0
    y = min(max(y, 0.05), 0.45)
    fy, fz = y / 0.05, z / 0.05
    iy, iz = min(int(fy), 8), min(int(fz), 9)
    ty, tz = fy - iy, fz - iz
    rows = HEAD_HALF_WIDTH
    a = rows[iz][iy] * (1 - ty) + rows[iz][iy + 1] * ty
    b = rows[iz + 1][iy] * (1 - ty) + rows[iz + 1][iy + 1] * ty
    return a * (1 - tz) + b * tz


def _wrapArms(geom):
    # Toon glasses are made for a toon's wide head, so on a doodle their
    # arms (and straps) would run through its head. Each arm is a straight
    # piece from the frame's outer corner back to its tip, so swing the tip
    # out just far enough that the whole arm rests along the side of the
    # head, touching it where the head is widest, like glasses on a face.
    holder = NodePath('fit')
    geom.reparentTo(holder)
    holder.flattenStrong()
    datas = []
    for np_ in holder.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            vdata = node.modifyGeom(i).modifyVertexData()
            if not any(vdata == other for other in datas):
                datas.append(vdata)

    def points():
        for vdata in datas:
            reader = GeomVertexRewriter(vdata, 'vertex')
            while not reader.isAtEnd():
                yield reader.getData3()
    ys = [v[1] for v in points()]
    if not ys:
        return holder
    # The frame (with its lenses) is the front slab; the arms run back
    # from its outer corners.
    frameBack = max(ys) - 0.12
    corner = {True: (0.0, frameBack), False: (0.0, frameBack)}
    for x, y, z in points():
        if y >= frameBack and abs(x) > corner[x > 0][0]:
            corner[x > 0] = (abs(x), y)
    for vdata in datas:
        rewriter = GeomVertexRewriter(vdata, 'vertex')
        for row in range(vdata.getNumRows()):
            rewriter.setRow(row)
            x, y, z = rewriter.getData3()
            x0, y0 = corner[x > 0]
            if y >= frameBack or y0 - y < 0.02 or headHalfWidth(y, z) <= 0.02:
                continue
            # Only ever move an arm outward.
            reach = abs(x)
            for step in range(1, 21):
                t = step / 20.0
                need = headHalfWidth(y0 + (y - y0) * t, z) + 0.012
                reach = max(reach, x0 + (need - x0) / t)
            rewriter.setRow(row)
            rewriter.setData3(reach if x > 0 else -reach, y, z)
    return holder

def _squeeze(geom, shift):
    # Pairs of wings are made for a toon's wide back. A doodle's back is
    # narrow, so move each wing in toward the middle until their roots meet
    # on its back instead of standing out at its sides.
    holder = NodePath('squeeze')
    geom.reparentTo(holder)
    holder.flattenStrong()
    done = []
    for np_ in holder.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            vdata = node.modifyGeom(i).modifyVertexData()
            if any(vdata == other for other in done):
                continue
            done.append(vdata)
            rewriter = GeomVertexRewriter(vdata, 'vertex')
            for row in range(vdata.getNumRows()):
                rewriter.setRow(row)
                x, y, z = rewriter.getData3()
                x = max(0.0, abs(x) - shift) * (1 if x > 0 else -1)
                rewriter.setRow(row)
                rewriter.setData3(x, y, z)
    return holder


def _fitToBack(geom, way, size, y, z, pitch, squeeze=0.0):
    holder = NodePath('fit')
    tilt = holder.attachNewNode('tilt')
    geom.reparentTo(tilt)
    geom.setHpr(180, 0, 0)
    bounds = geom.getTightBounds(tilt)
    if bounds:
        lo, hi = bounds
        if way == 'pack':
            # No taller, wider or deeper than a doodle's back can carry.
            scale = min(size / (hi[2] - lo[2]), 0.75 / (hi[0] - lo[0]),
                        0.55 / (hi[1] - lo[1]))
        else:
            scale = size / max(hi[0] - lo[0], hi[2] - lo[2])
        geom.setScale(scale)
        if squeeze:
            geom = _squeeze(geom, squeeze)
            geom.reparentTo(tilt)
        lo, hi = geom.getTightBounds(tilt)
        if way == 'pack':
            contactZ = lo[2]
        elif way == 'cape':
            contactZ = hi[2]
        else:
            # The height a toon wears it from (its origin).
            contactZ = min(max(0.0, lo[2]), hi[2])
        geom.setPos(geom.getPos() - Point3((lo[0] + hi[0]) / 2.0, hi[1], contactZ))
    tilt.setP(pitch)
    tilt.setPos(0, y, z)
    return holder


# Head parts the doodle tucks under any hat: they stand up from the top of
# its head, where every hat sits, so they would poke through it.
HIDE_UNDER_HAT = ('feathers', 'horns', 'antennae', 'dogEars', 'catEars', 'rabbitEars')


def getPlacement(kind, model):
    if model in OVERRIDES[kind]:
        return OVERRIDES[kind][model]
    (x, y, z), (h, p, r), scale = BASE[kind]
    dy, dz, s, dp = FITS[kind].get(model, (0.0, 0.0, 1.0, 0.0))
    if isinstance(s, tuple):
        scale = (scale * s[0], scale * s[1], scale * s[2])
    else:
        scale = scale * s
    return (x, y + dy, z + dz), (h, p + dp, r), scale


def loadAccessory(kind, model, texture):
    geom = loader.loadModel(modelList(kind)[model], okMissing=True)
    if not geom:
        return None
    if texture:
        tex = loader.loadTexture(textureList(kind)[texture], okMissing=True)
        if tex:
            tex.setMinfilter(Texture.FTLinearMipmapLinear)
            tex.setMagfilter(Texture.FTLinear)
            geom.setTexture(tex, 1)
    if kind == BACKPACK and model in BACK_FITS:
        return _fitToBack(geom, *BACK_FITS[model])
    pos, hpr, scale = getPlacement(kind, model)
    geom.setPos(*pos)
    geom.setHpr(*hpr)
    if isinstance(scale, tuple):
        geom.setScale(*scale)
    else:
        geom.setScale(scale)
    if kind == GLASSES and model not in UNBENT_GLASSES:
        return _wrapArms(geom)
    return geom


def dressPet(pet, accessories):
    # Puts the accessories on a Pet (or takes them off), replacing what it
    # wore before.
    for node in getattr(pet, 'accessoryNodes', []):
        node.removeNode()
    pet.accessoryNodes = []
    if not hasattr(pet, 'accessoryJoints'):
        pet.accessoryJoints = {}
    accessories = list(accessories) if accessories else NoAccessories
    if not isValid(accessories):
        accessories = NoAccessories
    hatOn = accessories[0] != 0
    for part in HIDE_UNDER_HAT:
        for node in pet.findAllMatches('**/' + part):
            if hatOn:
                node.hide()
            else:
                node.show()
    for kind in KINDS:
        model, texture = getPair(accessories, kind)
        if not model or model >= len(modelList(kind)):
            continue
        jointName = getJointName(kind, model)
        joint = pet.accessoryJoints.get(jointName)
        if joint is None:
            joint = pet.exposeJoint(None, 'modelRoot', jointName)
            pet.accessoryJoints[jointName] = joint
        geom = loadAccessory(kind, model, texture)
        if geom is None:
            continue
        holder = joint.attachNewNode('accessory-%d' % kind)
        geom.reparentTo(holder)
        # Doodles in the 2D screens draw without depth by default.
        holder.setDepthWrite(1)
        holder.setDepthTest(1)
        if kind == GLASSES and not getattr(pet, 'forGui', 0):
            # The doodle's eyes are drawn after the rest of it (Pet.setDNA),
            # so glasses go after the eyes, or the eyes would cover them.
            # A doodle in a 2D screen draws in scene graph order instead,
            # where its accessories already come after its eyes.
            holder.setBin('fixed', 4)
        pet.accessoryNodes.append(holder)
