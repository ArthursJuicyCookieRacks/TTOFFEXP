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

from panda3d.core import Texture, NodePath
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
FITS = {HAT: {4: (0.0, -0.02, (0.85, 0.55, 1.0), 0.0),   # heart headband, over the narrow top
              6: (0.0, -0.04, 1.0, 0.0),      # anvil
              7: (0.0, -0.08, 1.0, 0.0),      # flower pot
              8: (0.0, -0.03, 1.0, 0.0),      # sandbag
              9: (0.0, -0.04, 1.0, 0.0),      # weight
              11: (0.0, -0.01, 1.0, 0.0),     # golf hat
              14: (0.0, -0.07, 1.0, 0.0),     # crown
              19: (0.0, 0.04, 0.85, 0.0),     # sombrero, eyes show under the brim
              21: (0.0, 0.08, 1.0, -12.0),    # sun hat, tipped back so the eyes show
              23: (0.0, -0.04, 0.9, 0.0),     # beehive hairdo
              30: (0.0, 0.02, (0.75, 0.75, 1.0), 0.0),   # feather headband
              31: (-0.03, -0.14, 0.85, 0.0),  # pompadour
              33: (0.0, -0.03, 1.0, 0.0),     # robin hood hat
              36: (0.0, 0.02, 1.0, 0.0),      # tiara
              42: (0.0, 0.03, 0.85, 0.0),     # foil pyramid
              47: (0.0, -0.03, 1.0, 0.0),     # rainbow afro
              54: (0.0, 0.16, 1.0, 0.0),      # dinosaur
              # The extra models were made about 3.6 times smaller.
              57: (0.0, -0.02, 3.6, 0.0),     # ball hat
              58: (0.0, -0.03, 3.6, 0.0),     # elf hat
              59: (0.0, 0.08, 1.0, -12.0),    # sun hat B, tipped back
              60: (0.0, 0.01, 3.6, 0.0)},     # winter hat
        GLASSES: {21: (0.0, -0.02, 0.75, 0.0)},   # alien glasses, as wide as the eyes
        BACKPACK: {8: (0.0, -0.05, 0.6, 0.0),     # backpack with toys
                   17: (0.05, -0.1, 0.6, 0.0),    # toy airplane, wings under the head
                   19: (0.16, 0.2, 0.7, 0.0),    # super toon cape, along the back
                   20: (0.16, 0.2, 0.7, 0.0),    # vampire cape
                   21: (0.0, 0.3, 0.75, 0.0),     # dinosaur tail
                   22: (0.05, 0.05, 0.45, 0.0),   # drum
                   23: (0.0, 0.0, 0.7, 0.0),      # gag pack
                   29: (0.0, 0.0, 0.85, 0.0),     # jellybean jar
                   # The extra models were made at other sizes.
                   25: (0.05, 0.05, 2.6, 0.0),    # santa's sack
                   31: (0.1, -0.05, 0.6, 0.0)}}   # oil jar

# Models placed on their own instead: (x, y, z), (h, p, r), scale.
# The moustaches face forward from the middle of the head, so they hang
# under the eyes, over the doodle's mouth.
OVERRIDES = {HAT: {}, GLASSES: {
    17: ((-0.06, 0.51, 0.06), (180.0, 0.0, 0.0), 0.18),  # monocle, on one eye
    20: ((0.09, 0.38, 0.26), (180.0, 0.0, 0.0), 0.21),   # eye patch, over one whole eye
    22: ((0.0, 0.33, 0.25), (0.0, 0.0, 0.0), 0.55)}, BACKPACK: {   # snow goggles
    26: ((0.0, 0.13, -0.32), (180.0, 0.0, 0.0), 1.55),   # scarf, round the neck
    27: ((0.0, 0.5, -0.2), (0.0, 0.0, 0.0), 0.27),     # bow tie, under the mouth
    32: ((0.0, -0.5, 0.0), (0.0, 8.0, 0.0), 0.84)}}    # trash can lid, flat on the back
for _model, (_top, _back, _s) in {23: (-0.16, 0.42, 0.5), 24: (-0.21, 0.43, 0.42),
                                  25: (-0.21, 0.47, 0.5)}.items():
    OVERRIDES[GLASSES][_model] = ((0.0, 0.62 - _back * _s, 0.12 - _top * _s), (0.0, 0.0, 0.0), _s)

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
    pos, hpr, scale = getPlacement(kind, model)
    geom.setPos(*pos)
    geom.setHpr(*hpr)
    if isinstance(scale, tuple):
        geom.setScale(*scale)
    else:
        geom.setScale(scale)
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
