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
from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexWriter, LVecBase4f, Plane, PlaneNode, Mat4
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

# Toon looks doodles can't wear: the oil jar (backpack 31) was taken off
# the doodle list. A doodle that already wore one just takes it off.
NOT_FOR_DOODLES = {BACKPACK: (31,)}


def withoutRetired(accessories):
    # These accessories with anything doodles can no longer wear taken off.
    accessories = list(accessories) if accessories else list(NoAccessories)
    if len(accessories) == 6:
        for kind, models in NOT_FOR_DOODLES.items():
            if accessories[kind * 2] in models:
                accessories[kind * 2] = accessories[kind * 2 + 1] = 0
    return accessories


def getChoices(kind):
    # Every look of this kind that a toon can wear: (model, texture) pairs
    # from ToonDNA's styles, in model order, starting with "nothing".
    if kind not in _choices:
        seen = set()
        for model, texture, color in styleDict(kind).values():
            if model and model < len(modelList(kind)) and model not in NOT_FOR_DOODLES.get(kind, ()):
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
    20: ((0.04, 0.36, 0.17), (180.0, 0.0, 0.0), 0.21),   # eye patch, over one whole eye
    22: ((0.0, 0.33, 0.26), (0.0, 0.0, 0.0), (0.55, 0.55, 0.92))}, BACKPACK: {   # snow goggles
    26: ((0.0, 0.2, -0.3), (180.0, 24.0, 0.0), (1.65, 1.65, 1.3)),   # scarf, round the neck under the mouth, its lower edge flared (SCARF_FLARE), its ends hanging (SCARF_DRAPE)
    27: ((0.0, 0.68, -0.17), (0.0, 0.0, 0.0), 0.24),     # bow tie, under the mouth, its knot on the chest
    32: ((0.0, 0.0322, 0.2612), (0.0, 0.0, 0.0), 0.47)}}  # trash lid, up on the back like a shield, flat against the back of the neck, its edge on the hips
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
    1: ('pack', 0.8, -0.013, -0.07, -13.0, {'wide': 0.95, 'hug': 0.008, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # backpack, bent to lie flush on the back
    2: ('wing', 1.09, 0.03, -0.05, -6.0, {'squeeze': 0.1, 'hug': 0.008, 'ease': 0.6, 'lift': 0.02}),  # batWings
    3: ('wing', 0.98, -0.026, 0.0, -36.0, {'squeeze': 0.03, 'spread': 10.0, 'hug': 0.008, 'ease': 0.6, 'lift': 0.03}),  # beeWings
    4: ('wing', 1.09, 0.06, 0.17, -24.0, {'squeeze': 0.1, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # dragonFlyWings
    5: ('pack', 0.8, -0.085, -0.07, -18.0, {'wide': 0.95, 'hug': 0.008, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # scubaTank, bent to lie flush on the back
    6: ('wing', 0.42, -0.2, 0.17, -8.0, {'hug': 0.003, 'lift': 0.02}),  # sharkFin, its base bent to lie on the back, its tip laid along the hips
    7: ('wing', 0.92, -0.022, 0.0, -36.0, {'squeeze': 0.03, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # angelWings
    8: ('pack', 0.8, -0.026, -0.07, -13.0, {'wide': 0.95, 'hug': 0.02, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # backpackWithToys, bent to lie flush on the back
    9: ('wing', 0.92, 0.049, 0.2, -24.0, {'squeeze': 0.06, 'spread': 22.0, 'hug': 0.006, 'ease': 0.6, 'lift': 0.02}),  # butterflyWings, opened into a V
    10: ('wing', 0.98, -0.012, 0.12, -36.0, {'squeeze': 0.1, 'open': 45.0, 'spread': 10.0, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # dragonWing, swung open
    11: ('pack', 0.88, -0.003, -0.07, -18.0, {'wide': 1.05, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # jetPack, bent to lie flush on the back
    12: ('wing', 0.8, 0.04, 0.3, 0.0, 0.1),  # spiderLegs
    13: ('pack', 0.8, -0.026, -0.07, -13.0, {'wide': 0.95, 'hug': 0.006, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # stuffedAnimalBackpackA, bent to lie flush on the back
    14: ('wing', 1.09, 0.009, 0.0, -12.0, {'squeeze': 0.1, 'hug': 0.004, 'ease': 0.6, 'lift': 0.02}),  # birdWings
    15: ('pack', 0.8, -0.025, -0.07, -13.0, {'wide': 0.95, 'hug': 0.008, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # stuffedAnimalBackpackCat, bent to lie flush on the back
    16: ('pack', 0.8, -0.017, -0.07, -13.0, {'wide': 0.95, 'hug': 0.007, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # stuffedAnimalBackpackDog, bent to lie flush on the back
    17: ('wing', 1.27, -0.04, 0.14, -24.0),  # airplane, its body resting on the back
    18: ('pack', 1.0, -0.132, -0.1, -25.0, {'roll': 80.0, 'wide': 0.95}),  # woodenSword, slung across the small of the back
    19: ('cape', 0.7, 0.08, 0.27, -42.0),  # supertoonCape
    20: ('cape', 0.7, 0.08, 0.27, -42.0),  # vampireCape
    22: ('pack', 1.1, -0.031, -0.07, -13.0, {'wide': 1.21, 'hug': 0.024, 'ease': 0.4, 'lift': 0.02, 'smooth': 200, 'deep': 0.8}),  # band, bent to lie flush on the back
    23: ('pack', 0.8, -0.017, -0.05, -13.0, {'wide': 0.95, 'hug': 0.024, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # gags, bent to lie flush on the back
    24: ('pack', 0.65, 0.0452, -0.0149, -6.0, {'wide': 0.77}),  # flunky, one solid piece: its back on the back, its feet on the hips (placed by exact touch tests)
    25: ('pack', 0.8, -0.013, -0.07, -13.0, {'wide': 0.95, 'hug': 0.007, 'ease': 0.4, 'lift': 0.02, 'turn': 180.0, 'smooth': 200}),  # santa, bent to lie flush on the back
    28: ('pack', 0.8, -0.041, -0.07, -13.0, {'wide': 0.95, 'hug': 0.007, 'ease': 0.4, 'lift': 0.02, 'x': 0.06, 'smooth': 200}),  # creamPack, bent to lie flush on the back
    29: ('pack', 0.8, 0.058, 0.0079, -4.0, {'wide': 0.95, 'deep': 0.7}),  # jellybeanJar, one solid piece (glass doesn't bend): against the back of the neck, resting on the hips (placed by exact touch tests)
    30: ('pack', 0.8, 0.0, -0.07, -18.0, {'wide': 0.95, 'hug': 0.008, 'ease': 0.4, 'lift': 0.02, 'smooth': 200}),  # lipstickPack, bent to lie flush on the back
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


# The doodle's head seen from above, round a line going straight up through
# it at y HEAD_AXIS_Y (on the neck joint): how far its surface is from that
# line, measured from the head mesh and its eyes in the neutral pose. Rows go up the
# head (z 0.0, 0.05 .. 0.5), columns round it from straight ahead (0) to
# the side (90) and straight behind (180 degrees), every 10 degrees.
HEAD_AXIS_Y = 0.2
HEAD_RADIUS = (
    (0.376, 0.369, 0.361, 0.362, 0.340, 0.329, 0.330, 0.318, 0.308, 0.308, 0.317, 0.338, 0.350, 0.326, 0.302, 0.289, 0.281, 0.280, 0.288),
    (0.357, 0.345, 0.336, 0.322, 0.301, 0.294, 0.291, 0.281, 0.278, 0.284, 0.299, 0.326, 0.311, 0.285, 0.266, 0.258, 0.249, 0.249, 0.262),
    (0.343, 0.332, 0.331, 0.314, 0.294, 0.284, 0.277, 0.268, 0.267, 0.274, 0.284, 0.270, 0.256, 0.239, 0.231, 0.222, 0.219, 0.223, 0.235),
    (0.328, 0.323, 0.322, 0.298, 0.279, 0.271, 0.260, 0.251, 0.250, 0.256, 0.254, 0.242, 0.239, 0.224, 0.219, 0.220, 0.217, 0.221, 0.231),
    (0.301, 0.303, 0.297, 0.274, 0.258, 0.254, 0.242, 0.233, 0.232, 0.236, 0.228, 0.226, 0.227, 0.212, 0.215, 0.222, 0.219, 0.222, 0.230),
    (0.275, 0.273, 0.272, 0.252, 0.240, 0.237, 0.223, 0.214, 0.212, 0.217, 0.209, 0.209, 0.215, 0.209, 0.212, 0.222, 0.220, 0.221, 0.230),
    (0.238, 0.229, 0.227, 0.222, 0.212, 0.209, 0.200, 0.192, 0.190, 0.194, 0.194, 0.194, 0.200, 0.203, 0.206, 0.215, 0.218, 0.220, 0.228),
    (0.197, 0.190, 0.188, 0.188, 0.180, 0.176, 0.178, 0.169, 0.168, 0.171, 0.179, 0.179, 0.184, 0.196, 0.199, 0.207, 0.215, 0.217, 0.226),
    (0.157, 0.150, 0.149, 0.152, 0.147, 0.144, 0.145, 0.145, 0.144, 0.147, 0.154, 0.163, 0.168, 0.179, 0.191, 0.198, 0.211, 0.213, 0.221),
    (0.103, 0.099, 0.098, 0.099, 0.104, 0.102, 0.103, 0.101, 0.108, 0.115, 0.121, 0.131, 0.145, 0.156, 0.171, 0.188, 0.198, 0.205, 0.213),
    (0.045, 0.043, 0.043, 0.043, 0.045, 0.049, 0.055, 0.061, 0.060, 0.065, 0.075, 0.079, 0.086, 0.094, 0.102, 0.116, 0.133, 0.148, 0.154))


def headRadius(angle, z):
    # Bilinear look-up in HEAD_RADIUS (angle in degrees, 0 ahead).
    if z < 0.0 or z > 0.5:
        return 0.0
    fa, fz = min(max(angle, 0.0), 180.0) / 10.0, z / 0.05
    ia, iz = min(int(fa), 17), min(int(fz), 9)
    ta, tz = fa - ia, fz - iz
    rows = HEAD_RADIUS
    a = rows[iz][ia] * (1 - ta) + rows[iz][ia + 1] * ta
    b = rows[iz + 1][ia] * (1 - ta) + rows[iz + 1][ia + 1] * ta
    return a * (1 - tz) + b * tz


# Glasses that are really things laid on the face (the monocle sits in the
# eye, the eye patch and its strap are cloth): pressed onto the head this
# far off it, following its shape, instead of standing out flat in front.
# (gap, and for straps how far round the head, in degrees from straight
# ahead, their ends are carried, so they go round it instead of stopping
# short at its sides.)
ON_FACE = {17: (0.012, None), 20: (0.012, 175.0)}


def _subdivide(root, longest):
    # Splits every triangle of the model under root into a grid of small
    # ones, none with a side much over longest, so it can be bent smoothly.
    for np_ in root.findAllMatches('**/+GeomNode'):
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
            pos = rows['vertex']
            out = GeomVertexData(vdata.getName(), fmt, Geom.UHStatic)
            writers = dict((name, GeomVertexWriter(out, name)) for name in names)
            tris = GeomTriangles(Geom.UHStatic)
            count = 0
            for k in range(old.getNumPrimitives()):
                prim = old.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start = prim.getPrimitiveStart(t)
                    a, b, c = [prim.getVertex(start + q) for q in range(3)]
                    side = max((pos[a] - pos[b]).length(), (pos[b] - pos[c]).length(), (pos[c] - pos[a]).length())
                    n = max(1, int(math.ceil(side / longest)))
                    index = {}
                    for u in range(n + 1):
                        for v in range(n + 1 - u):
                            for name in names:
                                va, vb, vc = rows[name][a], rows[name][b], rows[name][c]
                                writers[name].addData4(va + (vb - va) * (u / float(n)) + (vc - va) * (v / float(n)))
                            index[u, v] = count
                            count += 1
                    for u in range(n):
                        for v in range(n - u):
                            tris.addVertices(index[u, v], index[u + 1, v], index[u, v + 1])
                            if u + v < n - 1:
                                tris.addVertices(index[u + 1, v], index[u + 1, v + 1], index[u, v + 1])
            geom = Geom(out)
            geom.addPrimitive(tris)
            node.setGeom(i, geom)


def _layOnHead(geom, gap, strapTo=None):
    holder = NodePath('onFace')
    geom.reparentTo(holder)
    holder.flattenStrong()
    if strapTo is not None:
        # A strap's end is its rearmost corners on each side.
        for np_ in holder.findAllMatches('**/+GeomNode'):
            node = np_.node()
            for i in range(node.getNumGeoms()):
                vdata = node.modifyGeom(i).modifyVertexData()
                reader = GeomVertexReader(vdata, 'vertex')
                pts = []
                while not reader.isAtEnd():
                    pts.append(reader.getData3())
                rewriter = GeomVertexRewriter(vdata, 'vertex')
                for side in (1, -1):
                    ys = [q[1] for q in pts if q[0] * side > 0]
                    if not ys:
                        continue
                    back = min(ys) + 0.012
                    for row, q in enumerate(pts):
                        if q[0] * side > 0 and q[1] <= back:
                            reach = headRadius(strapTo, q[2]) or 0.1
                            rewriter.setRow(row)
                            rewriter.setData3(side * reach * math.sin(math.radians(strapTo)),
                                              HEAD_AXIS_Y + reach * math.cos(math.radians(strapTo)), q[2])
    _subdivide(holder, 0.02)
    for np_ in holder.findAllMatches('**/+GeomNode'):
        node = np_.node()
        for i in range(node.getNumGeoms()):
            rewriter = GeomVertexRewriter(node.modifyGeom(i).modifyVertexData(), 'vertex')
            while not rewriter.isAtEnd():
                x, y, z = rewriter.getData3()
                side = 1.0 if x >= 0 else -1.0
                angle = math.degrees(math.atan2(abs(x), y - HEAD_AXIS_Y))
                reach = headRadius(angle, z)
                if reach > 0.0:
                    reach += gap
                    x = side * reach * math.sin(math.radians(angle))
                    y = HEAD_AXIS_Y + reach * math.cos(math.radians(angle))
                rewriter.setData3(x, y, z)
    return holder


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


# Where the solid back items sit, by how much they're made smaller
# (shrunk), so they still rest in the corner between the back of the neck
# and the hips, touching both (found with exact touch tests on the body).
RIGID_SPOTS = {
    24: {1.0: (0.0452, -0.0149), 0.95: (0.0397, -0.0149), 0.9: (0.0352, -0.0306), 0.85: (0.0333, -0.0311),
         0.8: (0.0273, -0.0288), 0.75: (0.0246, -0.0434), 0.7: (0.0241, -0.0432), 0.65: (0.0218, -0.03),
         0.6: (0.0113, -0.0262)},
    29: {1.0: (0.058, 0.0079), 0.95: (0.0514, 0.0104), 0.9: (0.0448, 0.013), 0.85: (0.0367, 0.0129),
         0.8: (0.0278, 0.0118), 0.75: (0.0201, 0.0131), 0.7: (0.0124, 0.0143), 0.65: (0.0042, 0.0146),
         0.6: (-0.0042, 0.0146), 0.55: (-0.0096, 0.0205), 0.5: (-0.0209, 0.0147)}}


def shrunk(spec, shrink):
    # A BACK_FITS spec made smaller by shrink (from where it sits).
    if shrink == 1.0:
        return spec
    way, size, y, z, pitch = spec[:5]
    rest = list(spec[5:])
    if rest and isinstance(rest[0], dict):
        opts = dict(rest[0])
        if way == 'pack':
            opts['wide'] = opts.get('wide', 0.75) * shrink
            opts['deep'] = opts.get('deep', 0.55) * shrink
        rest[0] = opts
    elif way == 'pack':
        rest = [dict(zip(('squeeze', 'turn', 'roll'), rest), wide=0.75 * shrink, deep=0.55 * shrink)]
    return (way, size * shrink, y, z, pitch) + tuple(rest)


def loadAccessory(kind, model, texture, shrink=1.0):
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
        spec = shrunk(BACK_FITS[model], shrink)
        spots = RIGID_SPOTS.get(model)
        if spots:
            # A solid one made smaller goes back into the corner between
            # the back of the neck and the hips, where it rests.
            y, z = spots[min(spots, key=lambda size: abs(size - shrink))]
            spec = spec[:2] + (y, z) + spec[4:]
        return _fitToBack(geom, *spec)
    if kind == BACKPACK and model == SCARF:
        geom = _drapeScarf(geom)
    pos, hpr, scale = getPlacement(kind, model)
    if shrink != 1.0 and kind == BACKPACK and model not in NECK_ITEMS[BACKPACK]:
        # Made smaller about the middle of its side against the back.
        scale = tuple(v * shrink for v in scale) if isinstance(scale, tuple) else scale * shrink
    geom.setPos(*pos)
    geom.setHpr(*hpr)
    if isinstance(scale, tuple):
        geom.setScale(*scale)
    else:
        geom.setScale(scale)
    if kind == GLASSES and model in ON_FACE:
        return _layOnHead(geom, *ON_FACE[model])
    if kind == GLASSES and model not in UNBENT_GLASSES:
        return _wrapArms(geom)
    return geom


# Hats whose brims or sides come down through these glasses' frames
# (found with exact triangle tests on the real models, worn on a doodle):
# with them, the glasses go under the hat (tuckUnderHat). Where the hat
# sits so low it would hide most of them, the pair is given room (how far
# the brim has to go up): the hat is raised a little (at most HAT_RAISE,
# still resting on the head) and the glasses lowered a little on the eyes
# (at most GLASSES_DROP). {hat: {glasses: room}}
HATS_OVER_GLASSES = {
    1: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.035, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.135, 22: 0, 26: 0, 27: 0, 28: 0},
    2: {1: 0.015, 2: 0.01, 3: 0, 4: 0.055, 5: 0, 6: 0, 7: 0, 8: 0.045, 9: 0.02, 10: 0.015, 12: 0.04, 13: 0, 14: 0.015, 15: 0.01, 16: 0.095, 17: 0, 18: 0.015, 19: 0.01, 22: 0.03, 26: 0.015, 27: 0.015, 28: 0.035},
    5: {1: 0, 2: 0, 3: 0, 4: 0.025, 5: 0, 6: 0, 7: 0, 8: 0.01, 9: 0, 10: 0, 11: 0.02, 12: 0.01, 13: 0, 14: 0, 15: 0, 16: 0.06, 17: 0, 18: 0, 19: 0, 21: 0.16, 22: 0, 26: 0, 27: 0, 28: 0},
    6: {22: 0},
    9: {16: 0},
    11: {1: 0, 2: 0, 3: 0, 4: 0.025, 5: 0, 6: 0, 7: 0, 8: 0.01, 9: 0, 10: 0, 12: 0.01, 13: 0, 14: 0, 15: 0, 16: 0.06, 17: 0, 18: 0, 19: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    15: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.005, 17: 0, 18: 0, 19: 0, 21: 0.08, 22: 0, 26: 0, 27: 0, 28: 0},
    16: {1: 0, 2: 0, 3: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 12: 0, 13: 0, 14: 0, 16: 0.05, 18: 0, 19: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    18: {1: 0.01, 2: 0.005, 3: 0, 4: 0.055, 5: 0, 6: 0, 7: 0, 8: 0.035, 9: 0.01, 10: 0.01, 11: 0.045, 12: 0.04, 13: 0, 14: 0.01, 15: 0, 16: 0.09, 17: 0, 18: 0.01, 19: 0.005, 21: 0.185, 22: 0.015, 26: 0.01, 27: 0.005, 28: 0.03},
    19: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.08, 22: 0, 26: 0, 27: 0, 28: 0},
    20: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.02, 17: 0, 18: 0, 19: 0, 21: 0.09, 22: 0, 26: 0, 27: 0, 28: 0},
    21: {4: 0, 8: 0, 11: 0, 12: 0, 16: 0, 19: 0, 21: 0.035, 22: 0, 27: 0, 28: 0},
    23: {4: 0, 12: 0, 16: 0, 21: 0},
    24: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 21: 0.085, 22: 0, 26: 0, 27: 0, 28: 0},
    25: {16: 0, 21: 0},
    26: {1: 0, 2: 0, 4: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 14: 0, 15: 0, 16: 0, 17: 0, 19: 0, 20: 0, 21: 0.09, 22: 0, 26: 0, 27: 0, 28: 0},
    28: {1: 0, 2: 0, 3: 0, 4: 0.02, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0.025, 12: 0.01, 13: 0, 14: 0, 15: 0, 16: 0.065, 17: 0, 18: 0, 19: 0, 21: 0.17, 22: 0, 26: 0, 27: 0, 28: 0},
    29: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.025, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.13, 22: 0, 26: 0, 27: 0, 28: 0},
    30: {2: 0.055, 3: 0.04, 5: 0.045, 6: 0.04, 7: 0.035, 8: 0.085, 9: 0.06, 12: 0.085, 13: 0.045, 14: 0.06, 18: 0.055, 19: 0.055, 22: 0.07, 27: 0.06, 28: 0.08},
    31: {4: 0, 8: 0, 9: 0, 12: 0, 14: 0, 16: 0, 18: 0, 19: 0, 21: 0.085, 22: 0, 27: 0, 28: 0},
    33: {4: 0, 12: 0, 16: 0, 21: 0},
    38: {4: 0, 12: 0, 16: 0, 21: 0, 28: 0},
    39: {4: 0, 12: 0, 16: 0, 21: 0, 28: 0},
    40: {1: 0, 2: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.035, 17: 0, 18: 0, 19: 0, 20: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    41: {2: 0, 3: 0, 5: 0, 6: 0, 7: 0, 8: 0.01, 9: 0, 13: 0, 16: 0.06, 18: 0, 22: 0, 27: 0, 28: 0.005},
    43: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.095, 22: 0, 26: 0, 27: 0, 28: 0},
    45: {1: 0, 2: 0, 3: 0, 4: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    46: {1: 0, 2: 0, 4: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    48: {16: 0},
    50: {1: 0, 4: 0, 8: 0, 10: 0, 11: 0.025, 12: 0, 15: 0, 16: 0.055, 17: 0, 19: 0, 21: 0.17, 26: 0, 28: 0},
    51: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 22: 0, 26: 0, 27: 0, 28: 0},
    54: {1: 0, 2: 0, 4: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 16: 0.005, 17: 0, 18: 0, 19: 0, 21: 0.095, 26: 0, 28: 0},
    55: {1: 0, 2: 0, 4: 0, 5: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0.02, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.12, 22: 0, 26: 0, 27: 0, 28: 0},
    59: {4: 0, 8: 0, 11: 0, 12: 0, 16: 0, 19: 0, 21: 0.035, 22: 0, 27: 0, 28: 0},
    63: {1: 0.01, 2: 0.005, 3: 0, 4: 0.055, 5: 0, 6: 0, 7: 0, 8: 0.03, 9: 0.01, 10: 0.01, 11: 0.045, 12: 0.04, 13: 0, 14: 0.01, 15: 0, 16: 0.09, 17: 0, 18: 0.005, 19: 0.005, 21: 0.185, 22: 0.01, 26: 0.01, 27: 0, 28: 0.03},
    64: {1: 0, 2: 0, 4: 0, 6: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0.095, 22: 0, 26: 0, 27: 0, 28: 0}}


# Back items whose tops would reach into these hats (their backs, brims,
# plumes or strings hang down behind the head over the doodle's short
# back), in the idle, walk and run poses (found with exact triangle tests):
# worn with one, the back item is made smaller, by how much, so it clears
# it. {back item: {hat: size}}
BACKS_UNDER_HATS = {
    1: {1: 0.8, 2: 0.7, 5: (0.75, 9), 6: 0.9, 7: 0.8, 8: 0.85, 9: 0.9, 10: 0.75, 11: 0.8, 12: 0.75, 13: 0.75, 14: 0.85, 15: 0.7, 16: 0.7, 17: 0.75, 18: 0.7, 19: 0.75, 20: 0.75, 21: (0.75, 9), 23: 0.75, 24: 0.75, 25: 0.8, 26: 0.8, 28: 0.75, 29: 0.75, 30: (0.7, 6), 31: (0.7, 6), 32: (0.8, 12), 33: 0.7, 34: (0.65, 9), 36: 0.8, 37: 0.8, 38: 0.85, 39: 0.85, 40: 0.75, 41: 0.7, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.65, 9), 48: 0.8, 49: 0.7, 50: (0.8, 6), 51: 0.8, 52: 0.75, 53: 0.75, 54: 0.5, 55: 0.75, 56: (0.65, 9), 57: 0.85, 58: 0.75, 59: (0.75, 9), 60: 0.8, 61: (0.65, 9), 62: 0.75, 63: 0.7, 64: 0.75},
    2: {2: (0.8, 9), 5: (0.8, 9), 9: 0.9, 11: 0.9, 15: 0.75, 16: 0.7, 18: (0.8, 9), 19: (0.8, 6), 20: 0.8, 21: (0.65, 12), 24: 0.8, 26: 0.7, 28: 0.8, 33: 0.7, 38: 0.75, 39: 0.75, 40: (0.8, 6), 41: (0.7, 9), 43: 0.7, 47: 0.8, 50: (0.85, 12), 51: 0.75, 54: 0.45, 56: 0.75, 57: 0.95, 59: (0.65, 12), 61: 0.75, 63: (0.8, 9), 64: (0.8, 6)},
    3: {1: 0.95, 2: (0.75, 9), 5: (0.8, 9), 9: 0.85, 11: 0.85, 13: 0.95, 15: 0.75, 16: 0.7, 17: 0.95, 18: (0.75, 9), 19: 0.7, 20: 0.8, 21: (0.65, 12), 24: 0.85, 25: 0.95, 26: 0.95, 28: 0.8, 30: (1.0, 6), 32: 0.95, 38: 0.8, 39: 0.8, 40: (0.8, 9), 41: (0.75, 9), 42: 0.8, 43: 0.7, 44: 0.7, 47: (0.85, 9), 49: 0.75, 50: (0.8, 9), 51: 0.75, 52: 0.9, 53: 0.85, 54: 0.4, 56: (0.8, 6), 57: 0.7, 58: 0.8, 59: (0.65, 12), 60: 0.9, 61: (0.8, 6), 63: (0.75, 9), 64: 0.7},
    4: {2: (0.85, 6), 5: (0.85, 6), 15: 0.95, 16: 0.8, 18: (0.85, 6), 19: 0.75, 21: (0.65, 12), 26: 0.85, 30: (0.8, 3), 32: (0.9, 3), 33: 0.8, 34: (0.9, 9), 38: 0.9, 39: 0.9, 40: 0.7, 41: (0.85, 9), 43: 0.8, 44: 0.95, 47: 0.8, 50: (0.8, 6), 51: 0.95, 54: 0.35, 56: 0.75, 59: (0.65, 12), 61: 0.75, 63: (0.85, 6), 64: 0.75},
    5: {1: 0.85, 2: 0.8, 5: 0.7, 6: 0.9, 7: 0.85, 8: 0.85, 9: 0.95, 10: 0.8, 11: 0.8, 12: 0.8, 13: 0.85, 14: 0.9, 15: 0.75, 16: 0.75, 17: 0.8, 18: 0.8, 19: 0.85, 20: 0.8, 21: 0.7, 23: 0.75, 24: 0.85, 25: 0.85, 26: 0.9, 28: 0.8, 29: 0.8, 30: 0.7, 31: (0.75, 9), 32: 0.8, 33: 0.85, 34: (0.7, 9), 37: 0.8, 38: 0.9, 39: 0.9, 40: 0.9, 41: 0.8, 42: 0.8, 43: 0.85, 44: 0.75, 45: 0.8, 46: 0.8, 47: (0.65, 6), 48: 0.8, 49: 0.75, 50: 0.9, 51: 0.9, 52: 0.8, 53: 0.8, 54: 0.6, 55: 0.85, 56: (0.7, 9), 57: 0.9, 58: 0.8, 59: 0.7, 60: 0.85, 61: (0.7, 9), 62: 0.8, 63: 0.8, 64: 0.85},
    6: {54: 0.95},
    7: {2: (0.75, 9), 5: (0.7, 9), 9: 0.8, 11: 0.7, 15: (0.8, 6), 16: (0.75, 9), 18: (0.75, 9), 19: 0.7, 20: (0.85, 6), 21: (0.65, 9), 24: 0.75, 26: 0.8, 28: (0.8, 6), 30: 0.95, 33: 0.7, 34: 0.9, 38: 0.75, 39: 0.75, 40: (0.8, 9), 41: (0.75, 9), 42: 0.7, 43: 0.7, 44: (0.7, 6), 47: (0.7, 9), 48: 0.8, 49: (1.0, 3), 50: (0.75, 9), 51: 0.7, 54: 0.4, 56: 0.7, 57: (0.8, 9), 58: (0.8, 9), 59: (0.65, 9), 60: 0.75, 61: 0.7, 63: (0.75, 9), 64: 0.7},
    8: {1: 0.95, 2: 0.75, 5: 0.7, 11: 0.8, 12: 0.8, 13: 0.8, 15: 0.8, 16: 0.7, 17: 0.8, 18: 0.75, 19: 0.85, 20: 0.8, 21: 0.7, 24: 0.85, 25: 0.8, 26: 0.9, 28: 0.8, 29: 0.9, 30: (0.85, 9), 31: 0.8, 32: 0.8, 33: 0.8, 34: (0.8, 9), 36: 0.95, 37: 0.95, 38: 0.85, 39: 0.85, 40: 0.75, 41: 0.8, 42: 0.8, 43: 0.85, 44: 0.75, 45: 0.9, 46: 0.9, 47: (0.75, 9), 48: 0.8, 49: 0.75, 50: 0.8, 51: 0.85, 52: 0.8, 53: 0.8, 54: 0.6, 55: 0.85, 56: 0.75, 57: 0.8, 58: 0.75, 59: 0.7, 60: 0.8, 61: 0.75, 63: 0.8, 64: 0.85},
    9: {2: (1.0, 6), 16: 0.75, 18: (0.8, 6), 19: 0.9, 21: (0.7, 9), 40: (1.0, 6), 41: 0.7, 43: 0.85, 44: 0.75, 50: (1.0, 6), 57: (0.85, 9), 59: (0.7, 9), 63: (0.8, 6), 64: 0.85},
    10: {2: 0.85, 3: 0.9, 5: 0.75, 11: 0.95, 15: 0.95, 16: 0.75, 18: 0.85, 20: 0.9, 21: 0.7, 28: 0.9, 40: 0.85, 41: 0.85, 42: 0.85, 44: 0.85, 47: (0.8, 6), 49: 0.85, 50: 0.9, 53: 0.95, 54: 0.65, 57: 0.8, 58: 0.9, 59: 0.7, 63: 0.9},
    11: {1: (0.9, 12), 2: (0.8, 9), 4: (1.0, 12), 5: (0.75, 12), 6: (1.0, 12), 7: (0.9, 12), 8: (0.9, 9), 9: (0.95, 12), 10: (0.8, 6), 11: (0.85, 12), 12: (0.8, 9), 13: (0.85, 12), 14: (0.9, 12), 15: (0.85, 12), 16: (0.75, 12), 17: (0.8, 9), 18: (0.85, 12), 19: (0.95, 12), 20: (0.9, 12), 21: (0.75, 9), 22: (1.0, 6), 23: (1.0, 12), 24: (0.9, 9), 25: (0.9, 12), 26: (1.0, 12), 27: (1.0, 9), 28: (0.85, 12), 29: (0.85, 12), 30: (0.7, 9), 31: (0.85, 12), 32: (0.8, 12), 33: (0.9, 12), 34: (0.6, 9), 35: (1.0, 6), 36: (0.8, 12), 37: (0.8, 9), 38: (0.95, 12), 39: (0.95, 12), 40: (0.9, 12), 41: (0.8, 12), 42: (0.8, 12), 43: (0.9, 9), 44: (0.75, 12), 45: (0.85, 12), 46: (0.85, 12), 47: (0.65, 12), 48: (0.85, 12), 49: (0.8, 9), 50: (0.85, 9), 51: (0.95, 12), 52: (0.8, 9), 53: (0.85, 12), 54: 0.5, 55: (0.9, 12), 56: (0.65, 12), 57: (0.9, 12), 58: (0.8, 12), 59: (0.75, 9), 60: (0.85, 12), 61: (0.65, 12), 62: (0.8, 6), 63: (0.85, 12), 64: (0.95, 12)},
    12: {2: (1.0, 12), 5: (0.85, 12), 15: (0.9, 6), 18: (0.85, 12), 19: (0.9, 6), 20: (0.9, 3), 21: (0.6, 12), 24: 0.7, 26: (0.85, 6), 28: (1.0, 3), 30: (1.0, 3), 32: (1.0, 3), 33: (0.85, 9), 34: 0.8, 38: 0.85, 39: 0.85, 40: (0.85, 6), 41: (0.85, 12), 43: (0.85, 6), 47: 0.85, 50: (0.7, 9), 51: (0.9, 6), 54: 0.35, 56: (0.85, 9), 59: (0.6, 12), 61: (0.85, 9), 63: (0.85, 12), 64: (0.85, 6)},
    13: {1: 0.8, 2: 0.75, 5: (0.75, 9), 6: 0.9, 7: 0.85, 8: 0.9, 9: 0.9, 10: 0.8, 11: 0.8, 12: 0.75, 13: 0.8, 14: 0.9, 15: 0.7, 16: 0.7, 17: 0.8, 18: 0.7, 19: 0.8, 20: 0.75, 21: (0.8, 9), 23: 0.8, 24: 0.8, 25: 0.8, 26: 0.85, 28: 0.75, 29: 0.75, 30: (0.75, 9), 31: (0.8, 9), 32: (0.8, 6), 33: 0.8, 34: (0.7, 9), 37: 0.8, 38: 0.85, 39: 0.85, 40: 0.85, 41: 0.75, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.7, 9), 48: 0.8, 49: 0.7, 50: 0.8, 51: 0.8, 52: 0.8, 53: 0.8, 54: 0.5, 55: 0.8, 56: (0.7, 9), 57: 0.95, 58: 0.8, 59: (0.8, 9), 60: 0.85, 61: (0.7, 9), 62: 0.8, 63: 0.75, 64: 0.8},
    14: {2: 0.75, 5: 0.75, 15: 0.95, 16: 0.85, 18: 0.75, 19: (0.8, 9), 20: 0.8, 21: (0.8, 12), 24: 0.95, 26: 0.9, 28: 0.95, 30: 0.75, 32: 0.85, 33: 0.8, 34: 0.95, 38: (0.8, 6), 39: (0.8, 6), 40: 0.85, 41: (0.6, 6), 43: 0.85, 44: 0.9, 47: 0.9, 49: 0.95, 50: (0.85, 6), 51: 0.95, 54: 0.35, 56: 0.9, 59: (0.8, 12), 61: 0.9, 63: 0.75, 64: (1.0, 6)},
    15: {1: 0.8, 2: 0.7, 5: (0.75, 9), 6: 0.95, 7: 0.85, 8: 0.9, 9: 0.9, 10: 0.8, 11: 0.8, 12: 0.8, 13: 0.8, 14: 0.95, 15: 0.7, 16: 0.7, 17: 0.8, 18: 0.7, 19: 0.8, 20: 0.75, 21: (0.75, 9), 23: 0.85, 24: 0.8, 25: 0.8, 26: 0.8, 28: 0.8, 29: 0.8, 30: (0.75, 9), 31: (0.8, 9), 32: (0.8, 6), 33: 0.75, 34: (0.7, 9), 37: 0.8, 38: 0.85, 39: 0.85, 40: 0.8, 41: 0.75, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.7, 6), 48: 0.8, 49: 0.7, 50: (0.9, 9), 51: 0.8, 52: 0.8, 53: 0.8, 54: 0.5, 55: 0.8, 56: (0.7, 6), 58: 0.8, 59: (0.75, 9), 60: 0.85, 61: (0.7, 6), 62: 0.8, 63: 0.7, 64: 0.8},
    16: {1: 0.8, 2: 0.7, 5: (0.75, 9), 6: 0.9, 7: 0.85, 8: 0.9, 9: 0.9, 10: 0.75, 11: 0.8, 12: 0.75, 13: 0.8, 14: 0.9, 15: 0.7, 16: 0.7, 17: 0.8, 18: 0.7, 19: 0.8, 20: 0.75, 21: (0.75, 9), 23: 0.85, 24: 0.8, 25: 0.8, 26: 0.8, 28: 0.75, 29: 0.75, 30: (0.75, 9), 31: 0.7, 32: (0.8, 9), 33: 0.75, 34: (0.7, 12), 37: 0.8, 38: 0.85, 39: 0.85, 40: 0.85, 41: 0.7, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.7, 9), 48: 0.8, 49: 0.7, 50: 0.7, 51: 0.8, 52: 0.8, 53: 0.8, 54: 0.45, 55: 0.8, 56: (0.65, 6), 57: 0.95, 58: 0.75, 59: (0.75, 9), 60: 0.8, 61: (0.65, 6), 62: 0.75, 63: 0.7, 64: 0.8},
    17: {21: 0.95, 54: 0.75, 59: 0.95},
    22: {1: (1.0, 9), 2: (0.65, 12), 5: (0.6, 12), 6: (1.0, 12), 7: (1.0, 9), 8: (1.0, 3), 9: (0.85, 12), 10: (0.95, 12), 11: (0.8, 12), 12: (0.75, 12), 13: (0.75, 9), 14: (1.0, 3), 15: (0.7, 12), 16: (0.65, 12), 17: (0.75, 9), 18: (0.65, 12), 19: (0.8, 12), 20: (0.75, 12), 21: (0.55, 12), 23: (1.0, 12), 24: (0.75, 12), 25: (0.85, 12), 26: (0.75, 12), 28: (0.7, 12), 29: (1.0, 12), 30: (0.6, 12), 31: (0.9, 12), 32: (0.6, 12), 33: (0.7, 12), 34: (0.75, 12), 36: (0.95, 12), 37: (0.95, 9), 38: (0.85, 12), 39: (0.85, 12), 40: (0.75, 12), 41: (0.65, 12), 42: (0.7, 9), 43: (0.75, 12), 44: (0.7, 12), 45: (0.8, 12), 46: (0.8, 12), 47: (0.65, 12), 48: (0.8, 12), 49: (0.65, 9), 50: (0.65, 12), 51: (0.75, 12), 52: (0.75, 9), 53: (1.0, 12), 54: 0.35, 55: (0.8, 12), 56: (0.65, 12), 57: (1.0, 12), 58: (0.75, 12), 59: (0.55, 12), 60: (0.75, 9), 61: (0.65, 12), 62: (0.95, 12), 63: (0.65, 12), 64: (0.75, 12)},
    23: {1: 0.9, 2: (0.85, 12), 5: (0.75, 9), 9: 0.85, 10: 0.9, 11: 0.9, 12: 0.9, 13: 0.9, 15: 0.7, 16: 0.7, 17: 0.9, 18: (0.85, 12), 19: 0.75, 20: 0.75, 21: (0.7, 9), 24: 0.75, 25: 0.9, 26: 0.75, 28: 0.8, 29: 0.85, 30: (0.8, 3), 31: 0.85, 32: (0.8, 9), 33: (0.8, 6), 34: (0.8, 9), 37: 0.9, 38: 0.85, 39: 0.85, 40: 0.75, 41: (0.8, 9), 42: 0.85, 43: 0.75, 44: 0.8, 45: 0.9, 46: 0.9, 47: 0.75, 48: 0.9, 49: 0.8, 50: (0.75, 9), 51: 0.75, 52: 0.9, 53: 0.9, 54: 0.45, 55: 0.9, 56: 0.7, 58: 0.85, 59: (0.7, 9), 60: 0.95, 61: 0.7, 62: 0.9, 63: (0.85, 12), 64: 0.75},
    24: {1: 0.95, 2: 0.85, 4: 0.9, 5: (0.8, 3), 11: 0.95, 12: 0.9, 13: 0.95, 15: 0.85, 16: 0.8, 17: 0.9, 18: 0.85, 19: 0.9, 20: 0.9, 21: (0.8, 3), 23: 0.95, 24: 0.9, 26: 0.95, 28: 0.9, 29: 0.95, 30: (0.8, 6), 31: 0.85, 32: (0.8, 3), 33: 0.9, 34: (0.8, 6), 40: 0.95, 41: 0.85, 42: 0.95, 43: 0.95, 44: 0.8, 45: 0.95, 46: 0.95, 47: (0.8, 9), 49: 0.8, 50: 0.9, 51: 0.95, 52: 0.9, 53: 0.9, 54: 0.6, 55: 0.9, 56: (0.8, 6), 58: 0.9, 59: (0.8, 3), 61: (0.8, 6), 63: 0.85, 64: 0.95},
    25: {1: 0.9, 2: 0.7, 5: (0.8, 9), 7: 0.95, 9: 0.9, 10: 0.9, 11: 0.9, 12: 0.85, 13: 0.9, 15: 0.75, 16: 0.7, 17: 0.9, 18: 0.7, 19: 0.8, 20: 0.75, 21: (0.75, 9), 23: 0.95, 24: 0.8, 25: 0.9, 26: 0.85, 28: 0.75, 29: 0.85, 30: (0.8, 6), 31: 0.8, 32: (0.95, 9), 33: 0.8, 34: (0.8, 12), 36: 0.9, 37: 0.9, 38: 0.85, 39: 0.85, 40: 0.8, 41: 0.7, 42: 0.85, 43: 0.8, 44: 0.8, 45: 0.9, 46: 0.9, 47: (0.8, 9), 48: 0.9, 49: 0.8, 50: 0.8, 51: 0.8, 52: 0.9, 53: 0.9, 54: 0.55, 55: 0.9, 56: (0.75, 6), 57: 0.8, 58: 0.85, 59: (0.75, 9), 60: 0.9, 61: (0.75, 6), 62: 0.9, 63: (0.8, 3), 64: 0.8},
    26: {32: (1.0, 3), 34: (1.0, 3)},
    28: {1: 0.8, 2: 0.75, 5: (0.75, 9), 6: 0.95, 7: 0.85, 8: 0.95, 9: 0.95, 10: 0.8, 11: 0.8, 12: 0.75, 13: 0.8, 14: 0.95, 15: 0.7, 16: 0.7, 17: 0.8, 18: 0.75, 19: 0.8, 20: 0.75, 21: (0.8, 9), 23: 0.9, 24: 0.8, 25: 0.8, 26: 0.85, 28: 0.75, 29: 0.75, 30: (0.8, 9), 31: 0.7, 32: (0.8, 3), 33: 0.8, 34: (0.7, 9), 37: 0.8, 38: 0.9, 39: 0.9, 40: 0.85, 41: 0.75, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.75, 9), 48: 0.8, 49: 0.7, 50: 0.8, 51: 0.85, 52: 0.8, 53: 0.8, 54: 0.5, 55: 0.75, 56: (0.7, 6), 58: 0.75, 59: (0.8, 9), 60: 0.85, 61: (0.7, 6), 62: 0.8, 63: 0.8, 64: 0.85},
    29: {2: (0.8, 3), 4: 0.95, 5: (0.85, 6), 11: 0.95, 12: 0.9, 15: 0.85, 16: 0.8, 18: (0.8, 3), 19: 0.85, 20: 0.9, 21: (0.9, 15), 24: 0.85, 26: 0.85, 28: 0.9, 29: 0.95, 30: (0.9, 9), 31: 0.8, 32: (0.8, 3), 33: (0.85, 3), 34: (0.8, 9), 40: 0.85, 41: (0.9, 6), 43: 0.85, 44: 0.9, 47: (0.8, 9), 49: 0.8, 50: (0.9, 9), 51: 0.9, 53: 0.95, 54: 0.5, 56: (0.8, 6), 58: 0.95, 59: (0.9, 15), 61: (0.8, 6), 63: (0.8, 3), 64: 0.85},
    30: {1: 0.8, 2: 0.75, 5: (0.75, 6), 6: 0.85, 7: 0.8, 8: 0.85, 9: 0.9, 10: 0.75, 11: 0.75, 12: 0.75, 13: 0.8, 14: 0.9, 15: 0.7, 16: 0.7, 17: 0.8, 18: 0.75, 19: 0.8, 20: 0.75, 21: (0.8, 9), 23: 0.95, 24: 0.8, 25: 0.8, 26: 0.85, 28: 0.75, 29: 0.75, 30: (0.75, 9), 31: 0.75, 32: (0.8, 9), 33: 0.8, 34: (0.65, 9), 36: 0.8, 37: 0.8, 38: 0.85, 39: 0.85, 40: 0.8, 41: 0.75, 42: 0.75, 43: 0.8, 44: 0.7, 45: 0.8, 46: 0.8, 47: (0.7, 9), 48: 0.8, 49: 0.7, 50: 0.8, 51: 0.8, 52: 0.8, 53: 0.8, 54: 0.55, 55: 0.8, 56: (0.65, 6), 57: 0.9, 58: 0.75, 59: (0.8, 9), 60: 0.8, 61: (0.65, 6), 62: 0.75, 63: 0.75, 64: 0.8},
    32: {5: (1.0, 3), 30: (1.0, 3), 31: (1.0, 9), 34: (1.0, 12), 47: (0.9, 12), 54: 0.6, 56: (0.9, 12), 61: (0.9, 12)}}


# Hats with something hanging down behind the head (the princess hat's
# ribbon, the roman helmet's neck guard): worn with a back item, that part
# is trimmed off where it would reach down into it, under this plane
# (normal, a point on it; on the neck joint, y forward, z up).
HAT_TRIMS = {
    32: ((0, 0.5, 1), (0, -0.16, 0.37)),
    34: ((0, 0.5, 1), (0, -0.1, 0.28))}


# Left as they were (Arthur's pick): the monocle and eye patch are never
# cut under a hat, and the dinosaur hat is never tipped or raised.
UNTUCKED_GLASSES = (17, 20)
UNTIPPED_HATS = (54,)


def trimHat(hatGeom, hat):
    # Takes off what hangs down behind the hat (HAT_TRIMS), which would
    # come down into a back item. hatGeom must be on its holder already.
    trim = HAT_TRIMS.get(hat)
    if trim:
        normal, point = trim
        plane = Plane(-Vec3(*normal), Point3(*point))
        _cutAbove(hatGeom, _movePlane(plane, hatGeom.getParent().getMat(hatGeom)))


# Hats with ties hanging down to the neck (the winter hat's pom-poms): worn
# with the scarf, the ties are shortened so the pom-poms rest on top of it
# instead of in it. (everything below z goes up by lift; the ties between
# z and z + span are squeezed to make up for it)
OVER_SCARF = {
    57: (0.035, 0.21, 0.19)}


def liftHatEnds(hatGeom, z0, span, lift):
    holder = hatGeom.getParent()
    for np_ in hatGeom.findAllMatches('**/+GeomNode'):
        mat = np_.getMat(holder)
        back = Mat4(mat)
        back.invertInPlace()
        node = np_.node()
        for i in range(node.getNumGeoms()):
            rewriter = GeomVertexRewriter(node.modifyGeom(i).modifyVertexData(), 'vertex')
            while not rewriter.isAtEnd():
                q = mat.xformPoint(rewriter.getData3())
                if q[2] < z0 + span:
                    q[2] += lift * min(1.0, (z0 + span - q[2]) / span)
                rewriter.setData3(back.xformPoint(q))


def backUnderHat(back, hat):
    # How much smaller the back item is made, and how far (degrees) the hat
    # is tipped forward, when they're worn together.
    fit = BACKS_UNDER_HATS.get(back, {}).get(hat, 1.0)
    if isinstance(fit, tuple):
        return fit
    return fit, 0


def tipHat(hatGeom, degrees):
    # Tips the hat forward about the bottom of its front, which stays where
    # it is on the head, so its back comes up off the back of the neck,
    # like a hat pushed forward.
    if not degrees:
        return
    holder = hatGeom.getParent()
    pts = _points(hatGeom, holder)
    if not pts:
        return
    pivot = Vec3(0, max(q[1] for q in pts), min(q[2] for q in pts))
    turn = Mat4.translateMat(-pivot) * Mat4.rotateMat(-degrees, Vec3(1, 0, 0)) * Mat4.translateMat(pivot)
    hatGeom.setMat(hatGeom.getMat() * turn)


def dressPet(pet, accessories):
    # Puts the accessories on a Pet (or takes them off), replacing what it
    # wore before.
    for node in getattr(pet, 'accessoryNodes', []):
        node.removeNode()
    pet.accessoryNodes = []
    if not hasattr(pet, 'accessoryJoints'):
        pet.accessoryJoints = {}
    accessories = withoutRetired(accessories)
    if not isValid(accessories):
        accessories = NoAccessories
    hatOn = accessories[0] != 0
    hatGeom = glassesGeom = None
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
        shrink = 1.0
        if kind == BACKPACK:
            shrink, tip = backUnderHat(model, accessories[0])
        geom = loadAccessory(kind, model, texture, shrink)
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
        if kind == HAT:
            hatGeom = geom
        if kind == GLASSES:
            glassesGeom = geom
    tip = 0
    if hatGeom is not None and accessories[4]:
        if getJointName(BACKPACK, accessories[4]) != 'joint_neck':
            trimHat(hatGeom, accessories[0])
        if accessories[0] not in UNTIPPED_HATS:
            tip = backUnderHat(accessories[4], accessories[0])[1]
            tipHat(hatGeom, tip)
        if accessories[4] == SCARF and accessories[0] in OVER_SCARF:
            liftHatEnds(hatGeom, *OVER_SCARF[accessories[0]])
    room = HATS_OVER_GLASSES.get(accessories[0], {}).get(accessories[2])
    if accessories[2] in UNTUCKED_GLASSES:
        room = None
    elif room is None and tip:
        # Tipped forward, the hat can come down over glasses it would
        # otherwise clear.
        room = 0
    if hatGeom is not None and glassesGeom is not None and room is not None:
        raise_ = 0 if accessories[0] in UNTIPPED_HATS else min(room, HAT_RAISE)
        hatGeom.getParent().setZ(raise_)
        glassesGeom.getParent().setZ(-min(room - raise_, GLASSES_DROP))
        tuckUnderHat(hatGeom, glassesGeom)


def _movePlane(plane, mat):
    # The plane carried by mat (which may stretch), keeping its up side up.
    base = plane.getPoint()
    normal = plane.getNormal()
    side = Vec3(1, 0, 0) if abs(normal[0]) < 0.9 else Vec3(0, 1, 0)
    u = normal.cross(side)
    v = normal.cross(u)
    a, b, c = (mat.xformPoint(q) for q in (base, base + u, base + v))
    moved = Plane(a, b, c)
    if moved.distToPlane(mat.xformPoint(base + normal)) < 0:
        moved = Plane(a, c, b)
    return moved


def _cutAbove(root, plane):
    # Cuts away every bit of the model under root that lies above plane
    # (given in root's space, its normal pointing up): triangles across it
    # are cut along it, so its edge is clean. Returns how much was cut.
    cut = 0
    for np_ in root.findAllMatches('**/+GeomNode'):
        node = np_.node()
        local = _movePlane(plane, root.getMat(np_))
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
            pos = rows['vertex']
            height = [local.distToPlane(Point3(v[0], v[1], v[2])) for v in pos]
            out = GeomVertexData(vdata.getName(), fmt, Geom.UHStatic)
            writers = dict((name, GeomVertexWriter(out, name)) for name in names)
            tris = GeomTriangles(Geom.UHStatic)
            count = [0]

            def add(a, b=None, t=0.0):
                for name in names:
                    va = rows[name][a]
                    writers[name].addData4(va if b is None else va + (rows[name][b] - va) * t)
                count[0] += 1
                return count[0] - 1

            for k in range(old.getNumPrimitives()):
                prim = old.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start = prim.getPrimitiveStart(t)
                    corners = [prim.getVertex(start + q) for q in range(3)]
                    if all(height[c] <= 0.0 for c in corners):
                        made = [add(c) for c in corners]
                    else:
                        cut += 1
                        made = []
                        for q in range(3):
                            a, b = corners[q], corners[(q + 1) % 3]
                            if height[a] <= 0.0:
                                made.append(add(a))
                            if (height[a] <= 0.0) != (height[b] <= 0.0):
                                made.append(add(a, b, height[a] / (height[a] - height[b])))
                    for q in range(1, len(made) - 1):
                        tris.addVertices(made[0], made[q], made[q + 1])
            geom = Geom(out)
            geom.addPrimitive(tris)
            node.setGeom(i, geom)
    return cut


TUCK_GAP = 0.004
TUCK_FRONT = 0.07
HAT_RAISE = 0.03
GLASSES_DROP = 0.02


def _points(root, ref):
    # Every vertex of the model under root, in ref's space.
    pts = []
    for np_ in root.findAllMatches('**/+GeomNode'):
        mat = np_.getMat(ref)
        node = np_.node()
        for i in range(node.getNumGeoms()):
            reader = GeomVertexReader(node.getGeom(i).getVertexData(), 'vertex')
            while not reader.isAtEnd():
                pts.append(mat.xformPoint(reader.getData3()))
    return pts


def _hatBottomOver(hatGeom, x0, x1, y0, y1):
    # How low (in the hat's own space, z up) the hat comes down over the
    # box x0..x1, y0..y1: each triangle is cut down to the box first, since
    # a brim is a few big ones whose corners lie outside it.
    low = None
    for np_ in hatGeom.findAllMatches('**/+GeomNode'):
        mat = np_.getMat(hatGeom)
        node = np_.node()
        for i in range(node.getNumGeoms()):
            geom = node.getGeom(i)
            reader = GeomVertexReader(geom.getVertexData(), 'vertex')
            verts = []
            while not reader.isAtEnd():
                verts.append(mat.xformPoint(reader.getData3()))
            for k in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start = prim.getPrimitiveStart(t)
                    a, b, c = [verts[prim.getVertex(start + q)] for q in range(3)]
                    if max(a[0], b[0], c[0]) < x0 or min(a[0], b[0], c[0]) > x1 or \
                       max(a[1], b[1], c[1]) < y0 or min(a[1], b[1], c[1]) > y1:
                        continue
                    # The triangle cut down to the box; its lowest corner.
                    poly = [a, b, c]
                    for axis, edge, keep in ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1)):
                        cut = []
                        for q in range(len(poly)):
                            p0, p1 = poly[q], poly[(q + 1) % len(poly)]
                            d0, d1 = (p0[axis] - edge) * keep, (p1[axis] - edge) * keep
                            if d0 >= 0:
                                cut.append(p0)
                            if (d0 >= 0) != (d1 >= 0):
                                cut.append(p0 + (p1 - p0) * (d0 / (d0 - d1)))
                        poly = cut
                        if not poly:
                            break
                    for q in poly:
                        if low is None or q[2] < low:
                            low = q[2]
    return low


def tuckUnderHat(hatGeom, glassesGeom):
    # Glasses worn under a hat whose brim would cut through them go under
    # it, like real ones: whatever of their frames would come up past the
    # bottom of the hat over them is cut away there (it would be under the
    # hat). Only the part of the hat over the front of the glasses counts,
    # not its sideburns, jaw or feathers lower down elsewhere.
    joint = glassesGeom.getParent()
    pts = _points(glassesGeom, joint)
    if not pts:
        return
    front = max(q[1] for q in pts) - TUCK_FRONT
    mat = joint.getMat(hatGeom)
    over = [mat.xformPoint(q) for q in pts if q[1] >= front]
    low = _hatBottomOver(hatGeom, min(q[0] for q in over), max(q[0] for q in over),
                         min(q[1] for q in over), max(q[1] for q in over))
    if low is None:
        return
    # Worked out on the joint, where a distance is a distance: a hair under
    # the hat, so the cut edge doesn't touch it.
    plane = _movePlane(Plane(Vec3(0, 0, 1), Point3(0, 0, low)), hatGeom.getMat(joint))
    normal = plane.getNormal()
    normal.normalize()
    plane = Plane(normal, plane.getPoint() - normal * TUCK_GAP)
    _cutAbove(glassesGeom, _movePlane(plane, joint.getMat(glassesGeom)))
