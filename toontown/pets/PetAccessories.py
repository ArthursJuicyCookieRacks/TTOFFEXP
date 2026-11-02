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

import math
from panda3d.core import Texture, NodePath, Point3, Vec3, GeomVertexReader, GeomVertexRewriter
from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexWriter, LVecBase4f
from toontown.toon import ToonDNA

HAT, GLASSES, BACKPACK = range(3)
KINDS = (HAT, GLASSES, BACKPACK)
NoAccessories = [0, 0, 0, 0, 0, 0]

HEAD_JOINT = 'joint_neck'
SCARF = 26
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


_prices = {}


def getPrice(kind, pair):
    # What a doodle pays to wear it, in jellybeans: what the catalog sells
    # the same toon accessory for. Looks the catalog doesn't sell cost what
    # the catalog asks for others of that model, or a middling price.
    if not pair or pair[0] == 0:
        return 0
    if not _prices:
        from toontown.catalog import CatalogAccessoryItemGlobals as Cat
        kinds = {Cat.AHat: HAT, Cat.ABoysHat: HAT, Cat.AGirlsHat: HAT,
                 Cat.AGlasses: GLASSES, Cat.ABoysGlasses: GLASSES, Cat.AGirlsGlasses: GLASSES,
                 Cat.ABackpack: BACKPACK, Cat.ABoysBackpack: BACKPACK, Cat.AGirlsBackpack: BACKPACK}
        for article, code, price in [entry[:3] for entry in Cat.AccessoryTypes.values()]:
            k = kinds.get(article)
            style = styleDict(k).get(code) if k is not None else None
            if not style or price < 100:
                continue
            for key in ((k, style[0], style[1]), (k, style[0], None)):
                _prices[key] = min(_prices.get(key, price), price)
    model, texture = pair
    return _prices.get((kind, model, texture), _prices.get((kind, model, None), DEFAULT_PRICE))


DEFAULT_PRICE = 800


def getCost(accessories, wearing=None):
    # Jellybeans for these accessories. A doodle keeps what it already
    # wears (wearing) for free, and taking something off costs nothing.
    wearing = wearing or NoAccessories
    cost = 0
    for kind in KINDS:
        pair = getPair(accessories, kind)
        if pair != getPair(wearing, kind):
            cost += getPrice(kind, pair)
    return cost


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
              8: (0.0, -0.12, 1.0, 0.0),      # sandbag, settled over the tip of the head
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
              54: (-0.08, 0.08, 0.8, 0.0),    # dinosaur, its teeth over the eyes
              16: (0.0, -0.075, 1.0, 0.0),     # pirate hat, down on the head
              22: (0.0, -0.035, 1.0, 0.0),     # antenna headband
              28: (0.0, -0.08, 1.0, 0.0),      # fedora, down on the head
              34: (0.0, -0.055, 1.0, 0.0),     # roman helmet
              35: (0.0, -0.035, 1.0, 0.0),     # spider antenna headband
              40: (0.0, -0.025, 1.0, 0.0),     # conquistador helmet
              41: (0.02, -0.07, 1.0, 0.0),     # firefighter helmet
              50: (0.0, -0.06, 1.0, 0.0),      # bobby hat
              10: (-0.05, -0.061, 1.0, -14.0),  # fez, centred on the head tip, tipped back with it, its rim resting on the head
              12: (-0.06, -0.015, 1.0, 0.0),    # party hat, on the top of the head
              56: (-0.03, -0.087, 1.0, -28.0),  # bird nest: its pot's rim rests round the head tip, tipped back with it
              61: (-0.03, -0.087, 1.0, -28.0),  # bird nest B
              62: (-0.05, -0.061, 1.0, -14.0),  # fez B
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
        BACKPACK: {21: (-0.05, -0.25, 0.6, 0.0)}}    # dinosaur tail, out of the rump
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
    26: ((0.0, 0.2, -0.3), (180.0, 24.0, 0.0), (1.65, 1.65, 1.3)),   # scarf, round the neck under the mouth, its lower edge flared (SCARF_FLARE), its ends hanging (SCARF_DRAPE)
    27: ((0.0, 0.68, -0.17), (0.0, 0.0, 0.0), 0.24)}}    # bow tie, under the mouth, its knot on the chest
for _model, (_top, _back, _s) in {23: (-0.22, 0.42, 0.5), 24: (-0.33, 0.43, 0.42),
                                  25: (-0.21, 0.47, 0.5)}.items():
    OVERRIDES[GLASSES][_model] = ((0.0, 0.57 - _back * _s, 0.12 - _top * _s), (0.0, 0.0, 0.0), _s)

# A doodle sits up like a toon: its back is the back of its upright body,
# from the top of its hips (a ledge at z 0.03, behind it the hips stick out)
# up to its head. Packs sit low, their bottoms settled a little into that
# ledge and leaning back on the back (the back is short, so a pack standing
# on the ledge would reach above the head); wings and fins come out of the
# middle of the back, capes hang from the middle of it over the hips.
# model: (way, size, y, z, pitch[, squeeze[, turn[, roll]]]) in the back joint's space: size is how
# tall it is (packs) or its longest side (the rest); (y, z) is where its
# contact point goes: a pack's bottom back edge, a wing's root, a cape's
# top edge. A pack's y was measured by moving it onto the body until
# nothing above the ledge went in (its strap side may touch); the rest by
# eye from the side and behind. squeeze moves a pair of wings that
# far in toward each other (see _squeeze). turn spins it round first (for
# the few made facing the other way), and roll leans it to one side.
BACK_FITS = {
    1: ('pack', 0.8, -0.013, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # backpack, bent to lie flush on the back
    2: ('wing', 1.09, 0.03, -0.05, -6.0, {'squeeze': 0.1, 'hug': 0.008, 'ease': 0.6, 'lift': 0.02}),  # batWings
    3: ('wing', 0.98, -0.026, 0.0, -36.0, {'squeeze': 0.03, 'spread': 10.0, 'hug': 0.008, 'ease': 0.6, 'lift': 0.03}),  # beeWings
    4: ('wing', 1.09, 0.06, 0.17, -24.0, {'squeeze': 0.1, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # dragonFlyWings
    5: ('pack', 0.8, -0.085, -0.02, -18.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # scubaTank, bent to lie flush on the back
    6: ('wing', 0.42, -0.2, 0.17, -8.0, {'hug': 0.003, 'lift': 0.02}),  # sharkFin, its base bent to lie on the back, its tip laid along the hips
    7: ('wing', 0.92, -0.022, 0.0, -36.0, {'squeeze': 0.03, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # angelWings
    8: ('pack', 0.8, -0.026, -0.02, -8.0, {'wide': 0.95, 'hug': 0.015, 'ease': 0.4, 'lift': 0.02}),  # backpackWithToys, bent to lie flush on the back
    9: ('wing', 0.92, 0.049, 0.2, -24.0, {'squeeze': 0.06, 'spread': 22.0, 'hug': 0.006, 'ease': 0.6, 'lift': 0.02}),  # butterflyWings, opened into a V
    10: ('wing', 0.98, -0.012, 0.12, -36.0, {'squeeze': 0.1, 'open': 45.0, 'spread': 10.0, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # dragonWing, swung open
    11: ('pack', 0.8, -0.003, -0.02, -18.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # jetPack, bent to lie flush on the back
    12: ('wing', 0.8, 0.04, 0.3, 0.0, 0.1),  # spiderLegs
    13: ('pack', 0.8, -0.026, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # stuffedAnimalBackpackA, bent to lie flush on the back
    14: ('wing', 1.09, 0.009, 0.0, -12.0, {'squeeze': 0.1, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # birdWings
    15: ('pack', 0.8, -0.025, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # stuffedAnimalBackpackCat, bent to lie flush on the back
    16: ('pack', 0.8, -0.017, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # stuffedAnimalBackpackDog, bent to lie flush on the back
    17: ('wing', 1.27, -0.04, 0.14, -24.0),  # airplane, its body resting on the back
    18: ('pack', 1.0, -0.132, -0.1, -25.0, {'roll': 80.0, 'wide': 0.95}),  # woodenSword, slung across the small of the back
    19: ('cape', 0.7, 0.08, 0.27, -42.0),  # supertoonCape
    20: ('cape', 0.7, 0.08, 0.27, -42.0),  # vampireCape
    22: ('pack', 0.8, -0.031, -0.02, -8.0, {'wide': 0.95, 'hug': 0.02, 'ease': 0.4, 'lift': 0.02}),  # band, bent to lie flush on the back
    23: ('pack', 0.8, -0.017, 0.0, -8.0, {'wide': 0.95, 'hug': 0.032, 'ease': 0.4, 'lift': 0.02}),  # gags, bent to lie flush on the back
    24: ('pack', 0.8, 0.0, -0.02, -8.0, {'wide': 0.95, 'hug': 0.016, 'ease': 0.4, 'lift': 0.02}),  # flunky, bent to lie flush on the back
    25: ('pack', 0.8, -0.013, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02, 'turn': 180.0}),  # santa, bent to lie flush on the back
    28: ('pack', 0.8, -0.041, -0.02, -8.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02, 'x': 0.06}),  # creamPack, bent to lie flush on the back
    29: ('pack', 0.8, 0.0, -0.02, -8.0, {'wide': 0.95, 'hug': 0.014, 'ease': 0.4, 'lift': 0.02, 'deep': 0.7}),  # jellybeanJar, bent to lie flush on the back
    30: ('pack', 0.8, 0.0, -0.02, -18.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02}),  # lipstickPack, bent to lie flush on the back
    31: ('pack', 0.8, 0.0, -0.02, 0.0, {'wide': 0.95, 'hug': 0.017, 'ease': 0.4, 'lift': 0.02, 'deep': 0.7}),  # oilJar, bent to lie flush on the back
    32: ('pack', 0.8, -0.008, -0.02, -8.0, {'wide': 0.95, 'hug': 0.002, 'ease': 0.4, 'lift': 0.02, 'turn': 180.0, 'extend': True}),  # trashLid, bent to lie flush on the back
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

def _squeeze(geom, shift, spread=0.0, open_=0.0):
    # Pairs of wings are made for a toon's wide back. A doodle's back is
    # narrow, so move each wing in toward the middle until their roots meet
    # on its back instead of standing out at its sides. spread then opens
    # the pair into a V (degrees each side, about their lowest point), so
    # tall narrow wings reach out past the doodle's sides, and open_ swings
    # each wing out sideways (degrees, about its front edge), for wings that
    # are made folded back.
    holder = NodePath('squeeze')
    geom.reparentTo(holder)
    holder.flattenStrong()
    bounds = holder.getTightBounds()
    low = bounds[0][2] if bounds else 0.0
    front = bounds[1][1] if bounds else 0.0
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
                side = 1 if x > 0 else -1
                x = max(0.0, abs(x) - shift)
                if spread:
                    a = math.radians(spread)
                    x, z = (x * math.cos(a) + (z - low) * math.sin(a),
                            low - x * math.sin(a) + (z - low) * math.cos(a))
                if open_:
                    b = math.radians(open_)
                    x, y = (x * math.cos(b) - (y - front) * math.sin(b),
                            front + (y - front) * math.cos(b) + x * math.sin(b))
                rewriter.setRow(row)
                rewriter.setData3(x * side, y, z)
    return holder


def _fitToBack(geom, way, size, y, z, pitch, *extra):
    # extra is a dict of options: squeeze, turn, roll and x (a sideways
    # shift, for the few whose middle isn't the middle of their bounds).
    opts = extra[0] if extra and isinstance(extra[0], dict) else dict(zip(('squeeze', 'turn', 'roll'), extra))
    squeeze = opts.get('squeeze', 0.0)
    turn = opts.get('turn', 0.0)
    roll = opts.get('roll', 0.0)
    holder = NodePath('fit')
    tilt = holder.attachNewNode('tilt')
    geom.reparentTo(tilt)
    geom.setHpr(180 + turn, 0, roll)
    bounds = geom.getTightBounds(tilt)
    if bounds:
        lo, hi = bounds
        if way == 'pack':
            # No taller, wider or deeper than a doodle's back can carry.
            scale = min(size / (hi[2] - lo[2]), opts.get('wide', 0.75) / (hi[0] - lo[0]),
                        opts.get('deep', 0.55) / (hi[1] - lo[1]))
        else:
            scale = size / max(hi[0] - lo[0], hi[2] - lo[2])
        geom.setScale(scale)
        if squeeze or opts.get('spread') or opts.get('open'):
            geom = _squeeze(geom, squeeze, opts.get('spread', 0.0), opts.get('open', 0.0))
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
    tilt.setPos(opts.get('x', 0.0), y, z)
    if opts.get('hug') is not None:
        return _hugBack(holder, pitch, y, z, opts['hug'], opts.get('ease', 3.0), opts.get('lift', 0.0),
                        opts.get('extend', False), opts.get('smooth', 0))
    return holder


# Where the doodle's back is (how far back it reaches), on the back joint,
# the furthest back of all its idle frames. Rows go up the back (z 0.04,
# 0.08 .. 0.64), columns out to the side (x 0.0, 0.04 .. 0.16). Measured by
# casting lines onto the body mesh from behind.
BACK_Y = (
    (-0.096, -0.078, -0.059, -0.042, -0.027),
    (-0.069, -0.056, -0.041, -0.027, -0.013),
    (-0.048, -0.038, -0.028, -0.014, 0.000),
    (-0.028, -0.018, -0.008, 0.002, 0.014),
    (-0.007, 0.003, 0.013, 0.023, 0.035),
    (0.016, 0.030, 0.044, 0.051, 0.065),
    (0.038, 0.051, 0.063, 0.074, 0.087),
    (0.040, 0.050, 0.061, 0.072, 0.087),
    (0.040, 0.050, 0.059, 0.070, 0.086),
    (0.041, 0.050, 0.059, 0.069, 0.086),
    (0.041, 0.050, 0.060, 0.069, 0.089),
    (0.043, 0.052, 0.062, 0.071, 0.093),
    (0.045, 0.054, 0.064, 0.073, 0.097),
    (0.048, 0.057, 0.066, 0.078, 0.104),
    (0.054, 0.064, 0.072, 0.086, 0.114),
    (0.071, 0.079, 0.094, 0.115, 0.166))


def backY(x, z, extend=False):
    if extend and abs(x) > 0.16:
        # Past the last column the body keeps curving forward, about as fast
        # as it does between the last two columns.
        return backY(0.16, z) + (abs(x) - 0.16) * (backY(0.16, z) - backY(0.12, z)) / 0.04
    fz = min(max((z - 0.04) / 0.04, 0.0), len(BACK_Y) - 1.0)
    fx = min(abs(x) / 0.04, len(BACK_Y[0]) - 1.0)
    iz, ix = min(int(fz), len(BACK_Y) - 2), min(int(fx), len(BACK_Y[0]) - 2)
    tz, tx = fz - iz, fx - ix
    row0 = BACK_Y[iz][ix] * (1 - tx) + BACK_Y[iz][ix + 1] * tx
    row1 = BACK_Y[iz + 1][ix] * (1 - tx) + BACK_Y[iz + 1][ix + 1] * tx
    return row0 * (1 - tz) + row1 * tz


def _along(corners, u):
    # Straight-line reading between the corners of a sorted (u, v) list.
    if u <= corners[0][0]:
        return corners[0][1]
    for (u1, v1), (u2, v2) in zip(corners, corners[1:]):
        if u <= u2:
            return v1 + (v2 - v1) * (u - u1) / max(u2 - u1, 1e-9)
    return corners[-1][1]


# The top of the doodle's body behind its back (the slope of the lower
# back, then the hips), on the back joint: how high it reaches at each
# spot, the highest of all its idle frames. Rows go back from the back
# (y -0.04, -0.06 .. -0.64), columns out to the side (x 0.0, 0.04 .. 0.16).
# Measured by dropping lines onto the body mesh.
HIP_TOP = (
    (0.136, 0.117, 0.083, 0.044, 0.013),
    (0.098, 0.069, 0.038, 0.011, -0.007),
    (0.062, 0.037, 0.010, -0.009, -0.026),
    (0.034, 0.008, -0.010, -0.027, -0.044),
    (0.006, -0.010, -0.026, -0.041, -0.057),
    (-0.007, -0.023, -0.038, -0.054, -0.064),
    (-0.020, -0.035, -0.049, -0.060, -0.070),
    (-0.033, -0.045, -0.055, -0.066, -0.076),
    (-0.025, -0.034, -0.044, -0.054, -0.067),
    (-0.012, -0.022, -0.032, -0.046, -0.062),
    (0.000, -0.010, -0.026, -0.042, -0.058),
    (0.011, -0.002, -0.018, -0.034, -0.050),
    (0.020, 0.010, -0.006, -0.022, -0.041),
    (0.029, 0.022, 0.006, -0.012, -0.032),
    (0.037, 0.033, 0.017, -0.003, -0.023),
    (0.046, 0.045, 0.026, 0.006, -0.014),
    (0.053, 0.054, 0.034, 0.015, -0.005),
    (0.054, 0.060, 0.040, 0.021, 0.001),
    (0.056, 0.064, 0.047, 0.027, 0.006),
    (0.057, 0.064, 0.053, 0.033, 0.012),
    (0.059, 0.064, 0.059, 0.039, 0.016),
    (0.061, 0.069, 0.065, 0.045, 0.020),
    (0.063, 0.073, 0.072, 0.050, 0.024),
    (0.065, 0.078, 0.077, 0.056, 0.029),
    (0.065, 0.074, 0.069, 0.050, 0.026),
    (0.057, 0.065, 0.059, 0.043, 0.018),
    (0.047, 0.055, 0.048, 0.036, 0.010),
    (0.036, 0.045, 0.037, 0.029, 0.002),
    (0.025, 0.035, 0.027, 0.022, -0.006),
    (0.015, 0.025, 0.013, 0.015, -0.016))


def hipTop(x, y):
    fy = min(max((-0.04 - y) / 0.02, 0.0), len(HIP_TOP) - 1.0)
    fx = min(abs(x) / 0.04, len(HIP_TOP[0]) - 1.0)
    iy, ix = min(int(fy), len(HIP_TOP) - 2), min(int(fx), len(HIP_TOP[0]) - 2)
    ty, tx = fy - iy, fx - ix
    row0 = HIP_TOP[iy][ix] * (1 - tx) + HIP_TOP[iy][ix + 1] * tx
    row1 = HIP_TOP[iy + 1][ix] * (1 - tx) + HIP_TOP[iy + 1][ix + 1] * tx
    return row0 * (1 - ty) + row1 * ty


def _subdivide(holder, longest):
    # Cuts every triangle into smaller ones whose sides are at most
    # longest, so that bending the model bends it smoothly. Returns the
    # new vertex datas.
    datas = []
    for np_ in holder.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            old = node.getGeom(i)
            vdata = old.getVertexData()
            fmt = vdata.getFormat()
            names = []
            for a in range(fmt.getNumArrays()):
                array = fmt.getArray(a)
                for c in range(array.getNumColumns()):
                    names.append(str(array.getColumn(c).getName()))
            rows = {}
            for name in names:
                reader = GeomVertexReader(vdata, name)
                values = []
                while not reader.isAtEnd():
                    values.append(LVecBase4f(reader.getData4()))
                rows[name] = values
            corners = []
            for k in range(old.getNumPrimitives()):
                prim = old.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start = prim.getPrimitiveStart(t)
                    corners.append([prim.getVertex(start + q) for q in range(3)])
            out = GeomVertexData(vdata.getName(), fmt, Geom.UHStatic)
            writers = dict((name, GeomVertexWriter(out, name)) for name in names)
            tris = GeomTriangles(Geom.UHStatic)
            count = 0
            pos = rows['vertex']
            # The same number of cuts everywhere, so that two triangles
            # sharing a side cut it at the same points (no cracks).
            edge = max(max((pos[a] - pos[b]).getXyz().length(),
                           (pos[b] - pos[c]).getXyz().length(),
                           (pos[c] - pos[a]).getXyz().length())
                       for a, b, c in corners) if corners else 0.0
            n = max(1, int(math.ceil(edge / longest)))
            for a, b, c in corners:
                index = {}
                for u in range(n + 1):
                    for v in range(n + 1 - u):
                        fu, fv = u / float(n), v / float(n)
                        for name in names:
                            va, vb, vc = rows[name][a], rows[name][b], rows[name][c]
                            writers[name].addData4(va + (vb - va) * fu + (vc - va) * fv)
                        index[(u, v)] = count
                        count += 1
                for u in range(n):
                    for v in range(n - u):
                        tris.addVertices(index[(u, v)], index[(u + 1, v)], index[(u, v + 1)])
                        if u + v < n - 1:
                            tris.addVertices(index[(u + 1, v)], index[(u + 1, v + 1)], index[(u, v + 1)])
            geom = Geom(out)
            geom.addPrimitive(tris)
            node.setGeom(i, geom)
            datas.append(node.modifyGeom(i).modifyVertexData())
    return datas


def _hugBack(holder, pitch, y0, z0, gap, ease=3.0, lift=0.0, extend=False, smooth=0):
    # A shark fin is a shell open at the front, made to sit on a toon's
    # back. A doodle's back bends (sloping above the hips, upright higher
    # up), so the fin is bent a little to match: it is cut into thin
    # slices, and each slice is slid along the fin's front-to-back line
    # until the first bit of it to reach the back just touches it (gap
    # away) without going in.
    holder.flattenStrong()
    p = math.radians(pitch)
    ny, nz = math.cos(p), math.sin(p)

    def local(x, y, z):
        # (across, front-to-back, up) in the fin's own upright frame.
        dy, dz = y - y0, z - z0
        return x, dy * ny + dz * nz, dz * ny - dy * nz

    datas = []
    tris = []
    for np_ in holder.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            geom = node.modifyGeom(i)
            vdata = geom.modifyVertexData()
            if not any(vdata == other for other in datas):
                datas.append(vdata)
            reader = GeomVertexReader(vdata, 'vertex')
            verts = []
            while not reader.isAtEnd():
                v = reader.getData3()
                verts.append(local(v[0], v[1], v[2]))
            for k in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start = prim.getPrimitiveStart(t)
                    tris.append([verts[prim.getVertex(start + q)] for q in range(3)])
    if not tris:
        return holder
    lows = [min(v[2] for v in tri) for tri in tris]
    highs = [max(v[2] for v in tri) for tri in tris]
    step = 0.01
    slides = []
    for key in range(int(math.floor(min(lows) / step)), int(math.ceil(max(highs) / step)) + 1):
        lz = min(max(key * step, min(lows) + 1e-4), max(highs) - 1e-4)
        best = None
        for tri, lo, hi in zip(tris, lows, highs):
            if lo > lz or hi < lz:
                continue
            # Where this slice crosses the triangle's edges.
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                if (a[2] - lz) * (b[2] - lz) > 0 or a[2] == b[2]:
                    continue
                t = (lz - a[2]) / (b[2] - a[2])
                x, ly = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                ry, rz = y0 + ly * ny - lz * nz, z0 + ly * nz + lz * ny
                s = 0.0
                for _ in range(8):
                    s = (backY(x, rz + s * nz, extend) - gap - ry) / ny
                # Nor so far that it runs into the top of the hips.
                t = 0.0
                while t < s and not lift:
                    t = min(s, t + 0.005)
                    if rz + t * nz < hipTop(x, ry + t * ny) + gap:
                        s = t - 0.005
                        break
                if best is None or s < best:
                    best = s
        if best is not None:
            slides.append((lz, best))
    # Never more than the least of its neighbours, so nothing between two
    # slices goes in either, and never much more than any slice near it
    # (where the hips hold one slice back, the ones beside it ease back
    # too instead of tearing the model into strips).
    slides = [(u, min(v for w, v in slides[max(0, i - 1):i + 2]))
              for i, (u, _) in enumerate(slides)]
    slides = [(u, min(v + ease * abs(u - w) for w, v in slides)) for u, _ in slides]
    # Round off the bend: average each slice with its neighbours, never
    # past where it touches, so a pack lying over a dip curves into it
    # instead of folding at one spot.
    if smooth:
        most = [v for _, v in slides]
        cur = most[:]
        for _ in range(smooth):
            cur = [min(most[i], (cur[max(i - 1, 0)] + cur[i] + cur[min(i + 1, len(cur) - 1)]) / 3.0)
                   for i in range(len(cur))]
        slides = [(u, v) for (u, _), v in zip(slides, cur)]
    # Its triangles are big and flat; cut them small so its edge can
    # follow the curve of the back instead of cutting straight across it.
    datas = _subdivide(holder, 0.02)
    for vdata in datas:
        rewriter = GeomVertexRewriter(vdata, 'vertex')
        while not rewriter.isAtEnd():
            x, y, z = rewriter.getData3()
            s = _along(slides, local(x, y, z)[2])
            y, z = y + s * ny, z + s * nz
            if lift:
                # Whatever ends up low over the hips is laid onto them,
                # easing in over the last bit above them (lift) so it bends
                # smoothly along their top instead of going in.
                above = z - hipTop(x, y) - gap
                if above < lift:
                    z += lift * math.exp((above - lift) / lift) - above
            rewriter.setData3(x, y, z)
    return holder


# The scarf is stiff, made for a toon's thin neck. On a doodle its back
# end would hang into the hips and its front end stick out from the
# chest, so each end is swung about where it leaves the ring (easing in
# over the first bit, like cloth) and made shorter.
# (angle, length kept) for the front and the back end, in the scarf's own
# space: its front end runs off toward -y and down, its back end hangs
# down from +y.
SCARF_DRAPE = {'front': (30.0, 0.65),   # down in front of the chest
               'back': (35.0, 0.6)}     # back over the hips, lying on them
_SCARF_ENDS = {'front': ((-0.22, -0.05), (-0.81, -0.58)),   # where it leaves the ring, which way it runs
               'back': ((0.3, 0.0), (0.0, -1.0))}
_SCARF_EASE = 0.06


def _scarfEnd(y, z):
    if y < _SCARF_ENDS['front'][0][0]:
        return 'front'
    if y > _SCARF_ENDS['back'][0][0] - 0.08 and z < _SCARF_ENDS['back'][0][1]:
        return 'back'
    return None


def drapeScarfPoint(y, z):
    end = _scarfEnd(y, z)
    if not end:
        return y, z
    angle, keep = SCARF_DRAPE[end]
    (hy, hz), (dy, dz) = _SCARF_ENDS[end]
    oy, oz = y - hy, z - hz
    along = oy * dy + oz * dz
    if along <= 0.0:
        return y, z
    # Shorten along the end's length, then swing it.
    oy += dy * along * (keep - 1.0)
    oz += dz * along * (keep - 1.0)
    a = math.radians(angle) * min(1.0, along / _SCARF_EASE)
    c, s_ = math.cos(a), math.sin(a)
    return hy + oy * c - oz * s_, hz + oy * s_ + oz * c


# The ring's lower edge is flared out a little so it rests on the doodle's
# shoulders instead of cutting into them when it breathes: (height where
# the flare starts, how far down it reaches its full width, how much wider
# it gets there). In the scarf model's own units; the ring's middle is at
# _SCARF_MIDDLE.
SCARF_FLARE = (0.1, 0.17, 0.35)
_SCARF_MIDDLE = (0.0, 0.096)


def flareScarfPoint(x, y, z):
    top, reach, more = SCARF_FLARE
    w = min(max((top - z) / reach, 0.0), 1.0)
    # Fade out again down the hanging ends, which already lie on the body.
    w *= min(max((z + 0.2) / 0.13, 0.0), 1.0)
    f = 1.0 + more * w
    mx, my = _SCARF_MIDDLE
    return mx + (x - mx) * f, my + (y - my) * f


def _drapeScarf(geom):
    for np_ in geom.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            vdata = node.modifyGeom(i).modifyVertexData()
            rewriter = GeomVertexRewriter(vdata, 'vertex')
            while not rewriter.isAtEnd():
                x, y, z = rewriter.getData3()
                y, z = drapeScarfPoint(y, z)
                x, y = flareScarfPoint(x, y, z)
                rewriter.setData3(x, y, z)
    return geom


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
    if kind == BACKPACK and model == SCARF:
        geom = _drapeScarf(geom)
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
