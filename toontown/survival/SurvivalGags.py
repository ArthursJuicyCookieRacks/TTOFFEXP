"""The gags of Survival Mode, carried and fired like BO1's guns.

A toon holds up to two gags. Throw and Squirt gags fly where the player
aims, Drop gags fall onto the aim point and Sound gags blast a cone in
front. Each has a clip and a reserve, reloads, and can be upgraded by
Mickey (more damage; a level 6 becomes the track's level 7). The
Presentation is the grenade: it lures every cog nearby and then pops.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpPosHprInterval, LerpPosInterval, LerpScaleInterval, Parallel,
                                            Sequence, SoundInterval, Wait)
from panda3d.core import CullFaceAttrib, LMatrix4, NodePath, Point2, Point3, Quat, Vec3, Vec4

from toontown.battle import BattleProps
from toontown.battle.BattleSounds import globalBattleSoundCache
from toontown.survival import SurvivalGlobals as G
from toontown.toonbase import ToontownBattleGlobals

FIRE_SOUNDS = {
    (G.THROW, 0): 'AA_tart_only.ogg', (G.THROW, 1): 'AA_slice_only.ogg', (G.THROW, 2): 'AA_wholepie_only.ogg',
    (G.THROW, 3): 'AA_slice_only.ogg', (G.THROW, 4): 'AA_wholepie_only.ogg', (G.THROW, 5): 'AA_wholepie_only.ogg',
    (G.THROW, 6): 'AA_throw_wedding_cake.ogg',
    (G.SQUIRT, 0): 'AA_squirt_flowersquirt.ogg', (G.SQUIRT, 1): 'AA_squirt_glasswater.ogg',
    (G.SQUIRT, 2): 'AA_squirt_neonwatergun.ogg', (G.SQUIRT, 3): 'AA_squirt_seltzer.ogg',
    (G.SQUIRT, 4): 'firehose_spray.ogg', (G.SQUIRT, 5): 'AA_throw_stormcloud.ogg', (G.SQUIRT, 6): 'AA_squirt_Geyser.ogg',
    (G.SOUND, 0): 'AA_sound_bikehorn.ogg', (G.SOUND, 1): 'AA_sound_whistle.ogg', (G.SOUND, 2): 'AA_sound_bugle.ogg',
    (G.SOUND, 3): 'AA_sound_aoogah.ogg', (G.SOUND, 4): 'AA_sound_elephant.ogg', (G.SOUND, 5): 'SZ_DD_foghorn.ogg',
    (G.SOUND, 6): 'AA_sound_Opera_Singer.ogg',
    (G.DROP, 0): 'AA_drop_flowerpot.ogg', (G.DROP, 1): 'AA_drop_sandbag.ogg', (G.DROP, 2): 'AA_drop_anvil.ogg',
    (G.DROP, 3): 'AA_drop_bigweight.ogg', (G.DROP, 4): 'AA_drop_safe.ogg', (G.DROP, 5): 'AA_drop_piano.ogg',
    (G.DROP, 6): 'AA_drop_boat.ogg',
}
SPLAT_COLORS = {G.THROW: Vec4(1, 1, 1, 1), G.SQUIRT: Vec4(0.55, 0.75, 1, 1)}
# Where a held gag sits in the player's view, and how big, per track.
VIEW_POS = {G.THROW: (Point3(0.9, 3.0, -1.0), 0.12), G.SQUIRT: (Point3(1.1, 2.8, -1.0), 0.45),
            G.SOUND: (Point3(0.8, 2.0, -0.7), 0.5), G.DROP: (Point3(1.0, 2.6, -0.9), 0.35), G.LURE: (Point3(0.9, 2.4, -0.75), 0.4)}
VIEW_SCALE = {'ship': 0.05, 'piano': 0.15, 'safe': 0.3, 'weight': 0.35, 'anvil': 0.4, 'geyser': 0.12, 'stormcloud': 0.3,
              'firehose': 0.3, 'wedding-cake': 0.35, 'birthday-cake': 0.4, 'singing': 0.4, 'fog_horn': 0.4,
              'elephant': 0.4, '1dollar': 0.4}
CONE_HALF_ANGLE = 32.0
# The cone is this much wider (feet) right at the toon, so a cog up close
# to one side is still hit.
SOUND_NEAR_WIDTH = 1.0
# Drop gags fall at the size a battle drops them on a cog, and lie there a
# moment; the Storm Cloud grows over its cog and rains.
DROP_SCALE = {}
DROP_STAY = 0.9
# The frame of each drop's battle animation where it lies flat on the
# ground, and how far that pose sits below its origin (feet, at scale 1).
DROP_REST_FRAME = {'piano': 30, 'safe': 30, 'weight': 30, 'anvil': 2, 'flowerpot': 15, 'sandbag': 4}
DROP_REST_LIFT = {'piano': 0.6, 'flowerpot': 0.9, 'sandbag': 0.6}
CLOUD_GROW = 0.5
CLOUD_RAIN = 1.4
# Over the cog's head, low enough to stay in a first-person view.
CLOUD_ABOVE = 1.3
TNT_IN_HAND = 0.85
TNT_GLOVE = Point3(0.85, 4.4, -0.55)
TNT_IN_VIEW_HPR = Vec3(0, 10, -20)
TNT_FUSE_SOUND = 'phase_5/audio/sfx/TL_dynamite.ogg'
TNT_BOOM = 'phase_4/audio/sfx/firework_explosion_0%d.ogg'
MELEE_HIT_SOUND = 'MG_sfx_vine_game_bat_hit.ogg'
MELEE_MISS_SOUND = 'AA_pie_throw_only.ogg'


# Where each fire sound's noise really starts, seconds into the file.
SOUND_START = {(G.SOUND, 6): 0.8}


def soundFor(key):
    name = FIRE_SOUNDS.get(key)
    return globalBattleSoundCache.getSound(name) if name else None

# How a toon handles each gag in a real cog battle (toontown/battle/Movie*):
# the animation, the frame it holds between shots, the frames one shot
# plays, and the hand the gag sits in. Where a battle puts the gag on the
# chest or presses a button (flower, storm cloud, geyser, drop, lure), the
# button is in the left hand like the battle and the gag rides the right
# so the player still sees it.
RIGHT, LEFT = 'right', 'left'
BATTLE_POSES = {
    G.THROW: ('throw', 38, 45, 84, RIGHT),
    (G.SQUIRT, 0): ('throw', 38, 38, 52, RIGHT),
    (G.SQUIRT, 1): ('spit', 20, 20, 95, RIGHT),
    # Held aimed (see aimHeld): the arm stays put and the gun kicks (KICKS).
    (G.SQUIRT, 2): ('water-gun', 44, 44, 44, RIGHT),
    (G.SQUIRT, 3): ('hold-bottle', 44, 44, 96, RIGHT),
    (G.SQUIRT, 4): ('firehose', 30, 30, 72, RIGHT),
    (G.SQUIRT, 5): ('throw', 38, 38, 52, RIGHT),
    (G.SQUIRT, 6): ('throw', 38, 38, 52, RIGHT),
    # The megaphone is held out in the fist like the fire hose's nozzle (the
    # battle holds it at the mouth, its wrist bent back: from the eyes that
    # bend looked broken). The blast pushes it forward (see shoot).
    G.SOUND: ('firehose', 30, 30, 30, RIGHT),
    G.DROP: ('throw', 38, 38, 52, RIGHT),
    G.LURE: ('throw', 38, 38, 52, RIGHT),
}
# Where the glove that holds the gag sits in the view (camera space), per
# hand, so the gag is big and low on the right like a BO1 view model.
# Where the glove that holds the gag sits in the view (camera space) and
# how far the toon leans back under the camera, per animation: the gag is
# big and low on the right like a BO1 view model, the shoulder stays below
# the frame.
VIEW_POSE = {'throw': (Point3(0.85, 4.8, -1.05), 15), 'water-gun': (Point3(1.0, 3.8, -0.95), 25),
             'hold-bottle': (Point3(1.0, 4.0, -0.6), 10), 'spit': (Point3(1.0, 4.0, -0.7), 5),
             'firehose': (Point3(1.1, 4.6, -1.3), -10), 'sound': (Point3(0.8, 4.6, -0.72), 10),
             'pushbutton': (Point3(0.7, 4.4, -1.2), 20)}
ARMS_SCALE = 0.8
# First person (sound gags): the eyes over the neck joint, toon units, and
# where the camera sits from the eyes (camera space).
EYE_OVER_NECK = 0.6
SOUND_HAND_AT = Vec3(0.6, 3.4, -0.85)
# Only the arm, the glove and the gag show, like a BO1 view model: the arm
# comes in from the lower right of the frame toward the glove, and runs on
# past the frame's edge, so its cut-off shoulder is never in view.
ARM_FROM = Vec3(0.55, -0.35, -0.76)
# Holds whose gag rests on the palm: the arm is rolled so the palm faces up
# (tipped a little to the player) and the gag sits in it.
PALM_UP_ANIMS = ('throw',)
PALM_UP = Vec3(0, -0.35, 1)
# The arm comes in flatter for those, so the rolled palm can face up.
PALM_ARM_FROM = Vec3(0.85, -0.5, -0.12)
# Gags rest in the hold joint (the palm) as the battle puts a pie there.
PALM_HOLD = True
# Heading in the palm per gag, and how deep it sinks (fraction of height).
# The piano model lies on its back (it drops keys first): stood on its legs.
HOLD_HPR = {'squirting-flower': (0, 0, 70), 'piano': (0, 90, 0)}
HOLD_SINK = {'stormcloud': 0.35, 'geyser': 0.2}
# Gags held another way, moved in the view (camera space) off the glove.
VIEW_NUDGE = {}
# Gags gripped as the battle holds them (prop: its animation frame on the
# toon's hold frame). The glass pops in from nothing over its first frames.
BATTLE_GRIP = {'glass': 20}
# Gags in the palm moved in the view (camera space) before they are kept
# clear of the glove.
HOLD_NUDGE = {'squirting-flower': Vec3(0, -0.15, -0.03), 'ship': Vec3(-0.2, 0.05, -0.03), 'fruitpie-slice': Vec3(-0.15, 0, -0.1),
              'creampie-slice': Vec3(-0.15, 0, -0.1)}
CLEAR_GAP = 0.005
# Gags centred on the glove's own middle rather than the hold joint.
CENTRE_ON_GLOVE = ('ship',)
CENTRE_PULL = 1.0
# Gags kept wholly on the glove (seen from above the palm): at least
# PALM_EDGE_ROOM of the glove's width in from its edge all round, at the
# first of FIT_SIZES (of its size) that fits somewhere.
KEEP_ON_GLOVE = ('ship',)
# Parts of a prop that are not the thing itself: the ship carries a flat
# drop shadow bigger than its hull, which kept it off the near side of the
# palm (Arthur: "move it down towards the left a little more").
NOT_SOLID = ('shadow',)
# Where on the glove such a gag's middle goes, from the middle of the palm,
# in glove widths along the hand's x and y (-x toward the fingers, -y the
# side nearer the eye).
# Tall, the ship hid the far half of the palm and seemed to sit up on its
# far edge (Arthur: "it should sit where the blue dot is", then "down
# towards the left a little more"). It never goes nearer the glove's edge
# than AIM_EDGE_ROOM, and is drawn smaller (FIT_SIZES) only when it cannot
# come within AIM_REACH of the wanted spot.
GLOVE_AIM = {'ship': (-0.15, -0.2)}
AIM_EDGE_ROOM = 0.02
# How near the wanted spot it must come before it is drawn smaller.
AIM_REACH = 0.03
PALM_EDGE_ROOM = 0.1
# The turns (degrees about the palm's up) it may take to fit, first first.
FIT_TURNS = (-90,)
FIT_SIZES = (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5)
# The storm cloud's bounds reach below what shows (HOLD_SINK sets it).
CLEAR_SKIP = ('stormcloud',)
# Where the hose nozzle points: out at the cogs past the crosshair (camera space).
HOSE_AIM_AT = Point3(0, 30, 0.5)
# Where the glove on the hose sits in the view (camera space).
HOSE_GLOVE_AT = Point3(0.8, 3.4, -0.9)
# The same for the squirt gun and the sound gags' megaphone.
GUN_GLOVE_AT = Point3(0.9, 4.0, -0.95)
SOUND_GLOVE_AT = Point3(0.8, 3.4, -0.75)
SOUND_ARM_SIZE = 1.0
SOUND_TWIST = 0
# The forearm (rolled by the elbow) comes in from the lower right (Arthur),
# the hand wrapping the megaphone from that side.
SOUND_ROLL_BY = 'shoulder'
SOUND_ARM_FROM = None
# The hold mirrored left to right about the megaphone (Arthur: that grip,
# the arm coming up from the right).
SOUND_MIRROR = True
# How much of the battle hold's bent wrist is straightened (1: the forearm
# carries on in line with the hand).
SOUND_WRIST_STRAIGHT = 0.5
# How much of that swing the glove's cuff follows (1: all, with the sleeve).
CUFF_FOLLOW = 1.0
# Mirrored, the body is cut away inward of the holding shoulder, from this
# far out (0 the middle between the shoulders, 1 the holding shoulder):
# these parts. Only the holding arm is left.
BODY_CLIP_AT = 0.75
BODY_CLIP_PARTS = ('sleeves', 'arms', 'torso-top', 'torso-bot')
# The gun aims at a nearer point, turned in so its side shows.
GUN_AIM_AT = Point3(0, 8, 0.6)
GUN_ARM_SIZE = 1.0
GUN_IN_FIST = Vec3(0, 0.05, -0.15)
GUN_SCALE = 0.75
GUN_CANT = 0
# How far (camera units) the gun goes back along the line of sight into the
# fist; further and the fingertips poke out over the barrel.
GUN_SINK = 0.05
# The arms' kick when an aimed gag fires: (pos, hpr) of the swing, camera space.
KICKS = {'shout': ((0, 0.15, 0.03), (0, 3, 0)), 'gun': ((0, -0.1, 0.04), (0, 5, 0))}
# The shoulder must end up at least this far outside the frame (film units,
# the frame is -1..1).
SHOULDER_OUT = 1.15
# How much the arm may be grown about the glove to reach past the edge.
MAX_ARM_GROW = 2.6
PIE_IN_VIEW_HPR = Vec3(0, 28, 0)
# ...and sits a little past the glove, so the glove shows under its near edge.
PIE_PAST_GLOVE = Vec3(0.1, 0.7, 0.05)
# How deep a carried gag sits into the glove, as a share of its height.
PALM_SINK = 0.05
# Gags that need to sit deeper in the glove (a slice balanced on the
# fingertips looked wrong, Arthur): how deep, and a nudge in camera space.
PALM_FIT = {'fruitpie-slice': (0.2, Vec3(0.13, 0, 0)), 'creampie-slice': (0.2, Vec3(0.13, 0, 0)),
            # Arthur: these sat on the fingertips; settled into the glove like the pies.
            **{name: (0.2, Vec3(0.1, 0, 0)) for name in ('geyser', 'flowerpot', 'sandbag', 'anvil', 'piano', 'ship')}}
GLOVE_TOP = 0.12
# How far from the palm joint (toon units) a hands vertex still counts as the glove.
GLOVE_REACH = 0.9
# Of a gag's footprint, the middle part whose glove must stay under it
# (the fingertips past its edge may curl up round it).
CLEAR_FOOT = 0.85
# Thin gags settle lower into the cupped palm, the curled fingers round their edge.
CLEAR_FOOTS = {'fruitpie-slice': 0.5, 'creampie-slice': 0.5}
# Gags carried on the palm that come in all sizes (a safe, a piano, a storm
# cloud, a geyser...) are fitted to one size in the view, a pie's.
FIT_SIZE = 0.85
DROP_FIT_SIZE = 0.7
# Drop gags drawn at their own size (the long, low ship looked tiny at 0.7).
DROP_FIT_SIZES = {'ship': 0.95, 'anvil': 0.6, 'piano': 0.55}
# Facing the player a little, so a drop gag shows its front and its top.
DROP_IN_VIEW_HPR = Vec3(-25, 12, 0)
FIT_TRACKS = (G.DROP, G.LURE)
FIT_PROPS = ('squirting-flower', 'stormcloud', 'geyser')
ARMS_H = 14
# The arms rig (camera space): where the arms ease to in each state, and
# the bobs as (strides a second, side, up, roll degrees, sway) per gait.
# Walk and run follow BO1's weapon bob: a slow figure of eight on a walk, a
# faster and wider one on a sprint with the gag carried lower and tilted in.
RIG_POSES = {'idle': ((0, 0, 0), (0, 0, 0)), 'walk': ((0, 0, -0.02), (0, 0, 0)),
             'run': ((0.12, -0.05, -0.18), (5, -5, -7)), 'lowered': ((0.25, 0, -1.3), (10, -22, 4))}
BOBS = {'idle': (0.45, 0.012, 0.01, 0.5, 0.0), 'walk': (1.8, 0.1, 0.06, 1.4, 0.0), 'run': (2.6, 0.12, 0.08, 2.0, 0.03)}
RIG_EASE = 7.0
RIG_EASE_DOWN = 9.0
RIG_BOB_EASE = 5.0
SWITCH_DOWN = 0.3
# The melee swing (camera space, about the camera): drawn back up and to
# the right, then swung down across to the left, then back to the hold.
WHACK_BACK = ((0.1, -0.2, 0.15), (-12, 12, -10))
WHACK_THROUGH = ((-0.2, 0.35, 0.05), (24, 0, 15))
WHACK_WINDUP = 0.1
WHACK_STRIKE = 0.11
WHACK_HOLD = 0.06
WHACK_RECOVER = 0.3
SWITCH_UP = 0.3
# Battle offsets for props that do not sit square in the hand.
PROP_IN_HAND = {'water-gun': (Point3(0.28, 0.1, 0.08), (85.6, -4.44, 94.43))}
# The fire hose's nozzle in the glove as MovieSquirt's hydrant and hose put
# it at the toon's firehose frame 30 (hose root in the glove, then the nozzle
# joint on the hose's own frame 30), measured. The hose itself is left in its
# bind pose, laid out straight behind the nozzle, so in first person it runs
# back out of the view instead of looping up past the player's face.
HOSE_ROOT_IN_HAND = ((-1.614, -1.543, 0.1), (10.93, -12.68, 57.7))
HOSE_NOZZLE_ON_ROOT = ((0.7807, 2.0188, 2.0038), (-1.046, -6.595, -8.24))
HOSE_NOZZLE_BIND = (1.74885, 4.94567, 0.877083)


# The megaphone is a cone: its axis (narrow mouthpiece end to wide end) and
# the point on it, near the mouthpiece, where the fist closes round it, in
# its own frame (measured from its vertices).
MEGAPHONE_AXIS = Vec3(-0.6659, -0.7457, 0.0199)
MEGAPHONE_GRIP = Point3(0.188, 0.398, 0.151)
# How far along its axis from MEGAPHONE_GRIP the fist holds it, and a turn
# about its axis (degrees).
MEGAPHONE_GRIP_ALONG = 0.15
MEGAPHONE_ROLL = 0
MEGAPHONE_FLIP = False
# Where along the fist's grip line (the hose's, in the nozzle's frame) the
# megaphone is held: the fist closes round the line about here.
FIST_ON_LINE = -0.77
# The megaphone slid in the view (camera space) so the glove holds its right side.
MEGAPHONE_VIEW_SHIFT = Vec3(0, 0, 0)


def megaphoneInFist(scale):
    """The megaphone in the glove: held round its narrow end the way the
    fist holds the fire hose's nozzle, its cone along the grip line and
    opening forward."""
    from panda3d.core import Quat, TransformState, lookAt
    line = TransformState.makePosHpr(Point3(*HOSE_ROOT_IN_HAND[0]), Vec3(*HOSE_ROOT_IN_HAND[1])).compose(
        TransformState.makePosHpr(Point3(*HOSE_NOZZLE_ON_ROOT[0]), Vec3(*HOSE_NOZZLE_ON_ROOT[1])))
    axis = Vec3(MEGAPHONE_AXIS)
    axis.normalize()
    side = axis.cross(Vec3(0, 0, 1))
    up = side.cross(axis)
    src = Quat()
    lookAt(src, axis, up)
    srcInv = Quat(src)
    srcInv.invertInPlace()
    roll = Quat()
    roll.setHpr(Vec3(0, 0, MEGAPHONE_ROLL))
    flip = Quat()
    # Turned end for end in the fist (its mouth out of the little-finger side
    # of the fist): the same grip seen from the other side.
    flip.setHpr(Vec3(180 if MEGAPHONE_FLIP else 0, 0, 0))
    quat = srcInv * roll * flip * line.getQuat()
    grip = Point3(MEGAPHONE_GRIP) + axis * MEGAPHONE_GRIP_ALONG
    at = line.getMat().xformPoint(Point3(0, FIST_ON_LINE, 0))
    pos = at - quat.xform(Vec3(grip) * scale)
    return TransformState.makePosQuatScale(pos, quat, Vec3(scale))


def convexHull(points):
    """The convex hull of 2D points, counter-clockwise (monotone chain)."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def heightIn(tri, x, y):
    """The height of triangle tri (three points) above (x, y), or None if
    (x, y) is not under it."""
    a, b, c = tri
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12:
        return None
    l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
    l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
    l3 = 1.0 - l1 - l2
    if l1 < -1e-6 or l2 < -1e-6 or l3 < -1e-6:
        return None
    return l1 * a[2] + l2 * b[2] + l3 * c[2]


def propTriangles(prop, space):
    """The prop's triangles, in space's coordinates."""
    from panda3d.core import GeomVertexReader
    tris = []
    for np in prop.findAllMatches('**/+GeomNode'):
        if np.isHidden() or np.getName() in NOT_SOLID:
            continue
        mat = np.getMat(space)
        node = np.node()
        for i in range(node.getNumGeoms()):
            geom = node.getGeom(i)
            reader = GeomVertexReader(geom.getVertexData(), 'vertex')
            points = []
            while not reader.isAtEnd():
                points.append(mat.xformPoint(reader.getData3()))
            for k in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(k).decompose()
                for t in range(prim.getNumPrimitives()):
                    start, end = prim.getPrimitiveStart(t), prim.getPrimitiveEnd(t)
                    if end - start == 3:
                        tris.append(tuple(points[prim.getVertex(j)] for j in range(start, end)))
    return tris


def insideConvex(hull, p):
    """Whether 2D point p is inside a counter-clockwise convex hull."""
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < 0:
            return False
    return True


def hoseInHand():
    from panda3d.core import TransformState
    root = TransformState.makePosHpr(Point3(*HOSE_ROOT_IN_HAND[0]), Vec3(*HOSE_ROOT_IN_HAND[1]))
    nozzle = TransformState.makePosHpr(Point3(*HOSE_NOZZLE_ON_ROOT[0]), Vec3(*HOSE_NOZZLE_ON_ROOT[1]))
    bind = TransformState.makePos(Point3(*HOSE_NOZZLE_BIND))
    return root.compose(nozzle).compose(bind.getInverse())
# Each level's instrument in the glove, as MovieSound places it (pos, hpr,
# the scale it blasts at).
INSTRUMENT_IN_HAND = {0: ((-1.1, -1.4, 0.1), (145, 0, 0), 0.65), 1: ((-1.2, -1.3, 0.1), (145, 0, 85), 0.2),
                      2: ((-1.3, -1.4, 0.1), (145, 0, 85), 0.4), 3: ((-1.0, -1.5, 0.2), (145, 0, 85), 0.5),
                      4: ((-0.6, -0.9, 0.15), (145, 0, 85), 0.15), 5: ((-0.8, -0.9, 0.2), (145, 0, 0), 0.15),
                      6: ((-1.04, -1.17, 0.26), (145, 0, 90), 1.1)}
# Sound gags ride inside the megaphone the way the battle shows them.
INSTRUMENT_IN_MEGAPHONE = (Point3(-1.1, -1.4, 0.1), (145, 0, 0))
# The megaphone is a big prop; this close to the camera it is shrunk.
MEGAPHONE_SCALE = 0.7
INSTRUMENT_SCALE = {'bikehorn': 0.5, 'whistle': 0.6, 'bugle': 0.6, 'aoogah': 0.6, 'elephant': 0.5, 'fog_horn': 0.5, 'singing': 0.5}
HAND_SCALE = {'ship': 0.05, 'piano': 0.1, 'safe': 0.22, 'weight': 0.25, 'anvil': 0.3, 'sandbag': 0.6, 'flowerpot': 0.6,
              'geyser': 0.1, 'stormcloud': 0.25, 'firehose': 1.0, 'wedding-cake': 1.0, 'birthday-cake': 1.0,
              '1dollar': 0.8, 'fruitpie-slice': 1.25, 'creampie-slice': 1.25, 'glass': 1.0, 'bottle': 1.0, 'water-gun': 1.0, 'squirting-flower': 1.0}
LEFT_ARM_JOINTS = ('def_left_shoulder', 'def_left_elbow', 'def_left_forearm', 'def_left_wrist', 'def_left_palm',
                   'def_left_sleeve_short', 'def_left_sleeve_long', 'def_left_forSleeve', 'def_left_neg_sleeve',
                   'def_left_collar', 'def_left_midA', 'def_left_midB', 'def_left_thumbB', 'def_left_thumbC',
                   'def_joint_left_hold')
RIGHT_ARM_JOINTS = tuple(j.replace('left', 'right') for j in LEFT_ARM_JOINTS)
ARM_JOINTS = {LEFT: LEFT_ARM_JOINTS, RIGHT: RIGHT_ARM_JOINTS}


def battlePose(track, level):
    return BATTLE_POSES.get((track, level)) or BATTLE_POSES.get(track) or BATTLE_POSES[G.THROW]


class ToonArms:
    """The player's toon from the shoulders down to the gloves, hung in
    front of the camera so the gag sits in its own hand (BO1 shows the
    player's arms the same way)."""

    def __init__(self, dna):
        from toontown.toon import Toon
        self.toon = Toon.Toon()
        self.toon.setDNA(dna)
        self.toon.useLOD('1000')
        self.toon.hideName()
        try:
            self.toon.nametag3d.stash()
        except Exception:
            pass
        # A toon's parts hang off each other (torso under the legs' hips,
        # head under the torso's neck), so only the geometry is hidden,
        # never a whole part node.
        for lod in self.toon.getLODNames():
            torso = self.toon.getPart('torso', lod)
            if torso is None or torso.isEmpty():
                continue
            for part in ('head', 'legs'):
                node = self.toon.getPart(part, lod)
                if node is None or node.isEmpty():
                    continue
                for geom in node.findAllMatches('**/+GeomNode'):
                    # The head hangs under the torso's neck, so it is hidden
                    # whole; of the legs only what is not the torso.
                    if part == 'head' or not torso.isAncestorOf(geom):
                        geom.hide()
            for name in ('**/torso-top', '**/torso-bot*', '**/neck'):
                for piece in torso.findAllMatches(name):
                    piece.hide()
        # Only the arm holding the gag shows; the other folds away (fold()).
        self.folded = []
        self.foldedSide = None
        self.fold(LEFT)
        shadow = getattr(self.toon, 'dropShadow', None)
        if shadow is not None and not shadow.isEmpty():
            shadow.hide()
        # The toon hangs off a rig under the camera; the rig carries the
        # idle sway, the walk and run bobs and the reload/switch put-away,
        # the toon under it keeps the hold pose (see animate()).
        self.rig = camera.attachNewNode('survivalArmsRig')
        # Between the rig and the toon: the melee swing (whack()).
        self.swing = self.rig.attachNewNode('survivalArmsSwing')
        self.swingTrack = None
        self.toon.reparentTo(self.swing)
        self.toon.setScale(ARMS_SCALE)
        self.toon.setHpr(ARMS_H, 0, 0)
        self.toon.setDepthTest(1)
        self.toon.setBin('fixed', 40)
        self.toon.setLightOff()
        self.toon.setColorScaleOff()
        self.track = None
        self.anim = None
        self.kick = None
        self.hold = 0
        self.grow = 1.0
        # Motion: the pose the rig eases toward ('idle', 'walk', 'run',
        # 'lowered'), its current eased offset, and the bob's phase/weight.
        self.motion = 'idle'
        self.lowered = False
        self.rigPos = Vec3(0)
        self.rigHpr = Vec3(0)
        self.bobPhase = 0.0
        self.bobWeight = {'idle': 1.0, 'walk': 0.0, 'run': 0.0}
        self.motionTrack = None

    # --- Motion (idle sway, walk and run bobs, put-away) ---

    def animate(self, dt, moveState):
        """Every frame: ease the rig toward its pose and add the bob. The
        bobs run on one phase, so walking into a run only changes the
        pace and the stride, never jumps."""
        dt = min(dt, 0.1)
        if self.rig.isEmpty():
            return
        state = 'lowered' if self.lowered else (moveState if moveState in ('walk', 'run') else 'idle')
        self.motion = state
        pos, hpr = RIG_POSES[state]
        k = min(1.0, dt * (RIG_EASE_DOWN if state == 'lowered' else RIG_EASE))
        self.rigPos += (Vec3(*pos) - self.rigPos) * k
        self.rigHpr += (Vec3(*hpr) - self.rigHpr) * k
        # The bob: each gait's weight eases in and out, the phase keeps going.
        want = state if state in ('walk', 'run') else 'idle'
        if state == 'lowered':
            want = None
        for gait in self.bobWeight:
            target = 1.0 if gait == want else 0.0
            self.bobWeight[gait] += (target - self.bobWeight[gait]) * min(1.0, dt * RIG_BOB_EASE)
        pace = sum(BOBS[gait][0] * self.bobWeight[gait] for gait in self.bobWeight)
        self.bobPhase = (self.bobPhase + dt * pace * 2 * math.pi) % (2 * math.pi)
        bobPos = Vec3(0)
        bobHpr = Vec3(0)
        for gait, weight in self.bobWeight.items():
            if weight < 1e-3:
                continue
            pace, side, up, roll, sway = BOBS[gait]
            # Side to side once a stride, up and down twice (a figure of
            # eight, the way the shoulders swing on a walk).
            bobPos += Vec3(math.sin(self.bobPhase) * side, 0, math.sin(self.bobPhase * 2) * up + abs(math.sin(self.bobPhase * 0.5)) * sway) * weight
            bobHpr += Vec3(0, math.sin(self.bobPhase * 2 + 0.6) * roll * 0.5, math.sin(self.bobPhase) * roll) * weight
        self.rig.setPos(self.rigPos + bobPos)
        self.rig.setHpr(self.rigHpr + bobHpr)

    def putAway(self, downTime, hold, upTime, atBottom=None):
        """Lower the arms out of the view, do something (switch gags), and
        bring them back: the reload and the gag switch (BO1 puts the gun
        down and brings it back up)."""
        if self.motionTrack:
            self.motionTrack.finish()
        def lower():
            self.lowered = True
        def raise_():
            self.lowered = False
        steps = [Func(lower), Wait(downTime + hold)]
        if atBottom is not None:
            steps.append(Func(atBottom))
        steps += [Func(raise_), Wait(upTime)]
        self.motionTrack = Sequence(*steps)
        self.motionTrack.start()

    def bringBack(self):
        """A put-away cut short (the reload was cancelled): straight back up."""
        if self.motionTrack:
            self.motionTrack.pause()
            self.motionTrack = None
        self.lowered = False

    def joint(self, side, name):
        try:
            node = self.toon.exposeJoint(None, 'torso', 'def_%s_%s' % (side, name), lodName='1000')
        except TypeError:
            node = self.toon.exposeJoint(None, 'torso', 'def_%s_%s' % (side, name))
        return node

    def aimArm(self, side):
        """Turn the toon about the glove so the arm comes in from the lower
        right of the frame (ARM_FROM, in camera space)."""
        shoulder = self.joint(side, 'shoulder')
        glove = self.hand(side)
        if shoulder is None or shoulder.isEmpty():
            return
        self.toon.update(force=True)
        want = Vec3(PALM_ARM_FROM if self.anim in PALM_UP_ANIMS else ARM_FROM)
        want.normalize()
        for i in range(3):
            have = shoulder.getPos(camera) - glove.getPos(camera)
            if have.length() < 1e-4:
                return
            have.normalize()
            axis = have.cross(want)
            angle = math.degrees(math.acos(max(-1.0, min(1.0, have.dot(want)))))
            if axis.length() < 1e-5 or angle < 0.05:
                break
            axis.normalize()
            # A turn in the camera's frame (the toon's parent) goes after
            # the toon's own transform.
            self.toon.setMat(self.toon.getMat() * LMatrix4.rotateMat(angle, axis))
            self.toon.update(force=True)

    def turnAbout(self, pivot, angle, axis):
        """Turn the toon by angle about axis through pivot, both in the
        toon's parent's coordinates."""
        self.toon.setMat(self.toon.getMat() * LMatrix4.translateMat(-pivot) * LMatrix4.rotateMat(angle, axis)
                         * LMatrix4.translateMat(pivot))
        self.toon.update(force=True)

    def aimNozzle(self, hose, side=RIGHT):
        """The fire hose, in its battle grip: its nozzle out at the cogs."""
        nozzle = hose.find('**/joint_water_stream')
        if nozzle.isEmpty():
            return
        glove = self.hand(side)
        self.aimHeld(side, HOSE_GLOVE_AT, lambda parent: nozzle.getPos(parent) - glove.getPos(parent))

    def aimHeld(self, side, gloveAt, pointing, size=1.0, aimAt=None, upright=None, armFrom=None, rollBy='shoulder',
                cant=0, twist=0):
        """Turn the arm, with its gag in the battle's grip, about the glove
        so the gag points out at the cogs (HOSE_AIM_AT, camera space),
        then roll it about that line so the arm still comes in from the
        lower right (or, given upright(parent), so the gag's up is the
        view's up), and grow it until its shoulder is out of view. size
        draws the arm (and so the gag) that much bigger.
        pointing(parent) is the way the gag points, in the toon's parent's
        coordinates."""
        parent = self.toon.getParent()
        glove = self.hand(side)
        shoulder = self.joint(side, 'shoulder')
        if shoulder is None or shoulder.isEmpty():
            return
        self.toon.setScale(ARMS_SCALE * size)
        self.grow = size
        self.placeGlove(side, gloveAt)
        pivot = glove.getPos(parent)
        want = parent.getRelativePoint(camera, aimAt or HOSE_AIM_AT) - pivot
        want.normalize()
        have = Vec3(pointing(parent))
        if have.length() < 1e-4:
            return
        have.normalize()
        axis = have.cross(want)
        if axis.length() > 1e-5:
            axis.normalize()
            self.turnAbout(pivot, math.degrees(math.acos(max(-1.0, min(1.0, have.dot(want))))), axis)
        def flat(v):
            v = Vec3(v) - want * want.dot(v)
            if v.length() < 1e-4:
                return None
            v.normalize()
            return v
        if upright is not None:
            # Rolled so the gag's own up is the view's up.
            arm = flat(upright(parent))
            # Canted in (its top toward the middle of the view) by cant degrees.
            goal = flat(parent.getRelativeVector(camera, Vec3(-math.sin(math.radians(cant)), 0,
                                                              math.cos(math.radians(cant)))))
        else:
            # The shoulder, or the elbow when the forearm is what shows.
            arm = flat(self.joint(side, rollBy).getPos(parent) - pivot)
            goal = flat(parent.getRelativeVector(camera, armFrom or ARM_FROM))
        if arm is not None and goal is not None:
            self.turnAbout(pivot, math.degrees(math.atan2(arm.cross(goal).dot(want), arm.dot(goal))), want)
        if twist:
            # Turned further about the aim line: which side the hand wraps from.
            self.turnAbout(pivot, twist, want)
        at = glove.getPos(camera)
        while self.shoulderInView(side) and self.grow < MAX_ARM_GROW:
            self.grow *= 1.08
            self.toon.setScale(self.toon.getScale() * 1.08)
            self.placeGlove(side, at)

    def mirrorAbout(self, node, axis=None, side=RIGHT):
        """Mirror the arm (and what the glove holds) left to right about
        node's middle, the way a picture of it flipped over would look.
        The mirror stands on a plane through the eye: one beside the camera
        (as first done) mirrors the arm in the world, but seen from the eye
        the hand turned another face to the view and the arm swung off to
        the side, not the hold flipped (Arthur: "THE EXACT WAY you had it,
        just flipped"). Given axis (the way the gag points, camera space),
        the plane holds it too, so the gag still points where it did and
        only the hand and arm cross over to its other side."""
        self.toon.update(force=True)
        low, high = node.getTightBounds(camera)
        if low is None:
            return
        middle = Vec3((low + high) * 0.5)
        along = Vec3(axis) if axis is not None else Vec3(0, 0, 1)
        normal = middle.cross(along)
        if normal.length() < 1e-5:
            return
        normal.normalize()
        flip = LMatrix4(LMatrix4.identMat())
        for i in range(3):
            for j in range(3):
                flip.setCell(i, j, (1.0 if i == j else 0.0) - 2.0 * normal[i] * normal[j])
        parent = self.toon.getParent()
        self.toon.setMat(self.toon.getMat() * parent.getMat(camera) * flip * camera.getMat(parent))
        # Mirrored, the faces wind the other way round.
        self.toon.setAttrib(CullFaceAttrib.makeReverse())
        self.mirrored = True
        self.toon.update(force=True)
        # The sleeve's top, between the shoulder and the neck, came round
        # into the bottom of the view once mirrored: the body is cut away
        # inward of the holding shoulder.
        self.clipBody(side)
        # The arm now crosses the view another way: grown about the glove
        # until its cut-off shoulder is out of the frame again.
        self.growOut(side)

    def straightenWrist(self, side, amount):
        """Swing the forearm about the wrist, the hand (and what it holds)
        staying just where it is, until the forearm carries on in line with
        the hand (amount 1; less leaves some of the bend). The battle hold
        bends the wrist hard to one side (Arthur: "straighten out" the arm)."""
        lod = '1000'
        try:
            wrist = self.toon.exposeJoint(None, 'torso', 'def_%s_wrist' % side, lodName=lod)
            elbow = self.toon.exposeJoint(None, 'torso', 'def_%s_elbow' % side, lodName=lod)
            knuckle = self.toon.exposeJoint(None, 'torso', 'def_%s_midA' % side, lodName=lod)
            joint = self.toon.getPartBundle('torso', lod).findChild('def_%s_wrist' % side)
        except Exception:
            return
        if joint is None or wrist.isEmpty() or elbow.isEmpty() or knuckle.isEmpty():
            return
        self.toon.update(force=True)
        at = wrist.getPos(camera)
        along = at - knuckle.getPos(camera)
        arm = elbow.getPos(camera) - at
        if along.length() < 1e-5 or arm.length() < 1e-5:
            return
        along.normalize()
        arm.normalize()
        axis = arm.cross(along)
        if axis.length() < 1e-5:
            return
        axis.normalize()
        bend = math.degrees(math.acos(max(-1.0, min(1.0, arm.dot(along)))))
        local = LMatrix4(joint.getTransformState().getMat())
        net = wrist.getMat(camera)
        above = LMatrix4(local)
        above.invertInPlace()
        above = above * net
        aboveInv = LMatrix4(above)
        aboveInv.invertInPlace()
        parent = self.toon.getParent()
        start = self.toon.getMat()
        # The glove's cuff (the collar joint, under the wrist) turns with the
        # sleeve, so no gap opens between them (Arthur: "a weird invisible
        # line" on the glove).
        collar = self.toon.getPartBundle('torso', lod).findChild('def_%s_collar' % side)
        cuff = LMatrix4(collar.getTransformState().getMat()) if collar is not None else None
        netInv = LMatrix4(net)
        netInv.invertInPlace()
        self.releaseWrist()
        nodes = []
        cuffs = []
        for name in self.toon.getLODNames():
            for joint, into in (('wrist', nodes), ('collar', cuffs)):
                if joint == 'collar' and cuff is None:
                    continue
                try:
                    node = self.toon.controlJoint(None, 'torso', 'def_%s_%s' % (side, joint), lodName=name)
                except Exception:
                    node = None
                if node is not None and not node.isEmpty():
                    into.append(node)
                    self.wristHeld.append(('def_%s_%s' % (side, joint), name, node))
        # As straight as it goes with the cut-off shoulder still out of the
        # frame (grown to hide it, the glove would come out bigger).
        steps = 10
        for step in range(steps, -1, -1):
            angle = bend * amount * step / float(steps)
            turn = LMatrix4.translateMat(-at) * LMatrix4.rotateMat(angle, axis) * LMatrix4.translateMat(at)
            back = LMatrix4.translateMat(-at) * LMatrix4.rotateMat(-angle, axis) * LMatrix4.translateMat(at)
            # The arm swings about the wrist; the wrist turns back by as
            # much, so the hand stays put.
            self.toon.setMat(start * parent.getMat(camera) * turn * camera.getMat(parent))
            for node in nodes:
                node.setMat(local * above * back * aboveInv)
            if cuffs:
                follow = LMatrix4.translateMat(-at) * LMatrix4.rotateMat(angle * CUFF_FOLLOW, axis) \
                    * LMatrix4.translateMat(at)
                for node in cuffs:
                    node.setMat(cuff * net * follow * netInv)
            self.toon.update(force=True)
            if not self.shoulderInView(side):
                break

    def releaseWrist(self):
        held = getattr(self, 'wristHeld', None) or []
        # (releaseJoint lets go in every detail level at once.)
        for joint in set(joint for joint, lod, node in held):
            self.toon.releaseJoint('torso', joint)
        for joint, lod, node in held:
            if not node.isEmpty():
                node.removeNode()
        self.wristHeld = []
        if held and self.anim:
            # Let go, the wrist keeps the turned value until its animation
            # changes frame: posed one frame over and back, it takes the
            # hold's own wrist again (else each sound gag picked turned the
            # hand a little more).
            frames = max(1, self.toon.getNumFrames(self.anim) or 1)
            other = self.hold + 1 if self.hold + 1 < frames else max(0, self.hold - 1)
            for frame in (other, self.hold):
                self.toon.pose(self.anim, frame)
                for lod in range(len(self.toon.getLODNames())):
                    self.toon.update(lod=lod, force=True)

    def growOut(self, side):
        """Grow the arm about the glove until its cut-off shoulder is out of
        the frame."""
        parent = self.toon.getParent()
        at = self.hand(side).getPos(camera)
        while self.shoulderInView(side) and self.grow < MAX_ARM_GROW:
            self.grow *= 1.08
            grow = LMatrix4.translateMat(-at) * LMatrix4.scaleMat(1.08) * LMatrix4.translateMat(at)
            self.toon.setMat(self.toon.getMat() * parent.getMat(camera) * grow * camera.getMat(parent))
            self.toon.update(force=True)

    def clipBody(self, side):
        """Cut away the body inward of this side's shoulder (the sleeve's
        top, the collar, the other arm), leaving the holding arm whole."""
        from panda3d.core import Plane, PlaneNode
        self.unclipBody()
        other = LEFT if side == RIGHT else RIGHT
        keep = self.joint(side, 'shoulder')
        fold = self.joint(other, 'shoulder')
        if keep is None or fold is None or keep.isEmpty() or fold.isEmpty():
            return
        self.toon.update(force=True)
        a = keep.getPos(self.toon)
        b = fold.getPos(self.toon)
        normal = Vec3(a - b)
        if normal.length() < 1e-4:
            return
        normal.normalize()
        middle = (a + b) * 0.5
        at = Point3(middle + (a - middle) * BODY_CLIP_AT)
        plane = self.toon.attachNewNode(PlaneNode('bodyClip', Plane(normal, at)))
        nodes = []
        for name in BODY_CLIP_PARTS:
            for np in self.toon.findAllMatches('**/%s' % name):
                np.setClipPlane(plane)
                nodes.append(np)
        self.bodyClip = (plane, nodes)

    def unclipBody(self):
        clip = getattr(self, 'bodyClip', None)
        if clip:
            plane, nodes = clip
            for np in nodes:
                if not np.isEmpty():
                    np.clearClipPlane()
            if not plane.isEmpty():
                plane.removeNode()
        self.bodyClip = None

    def rollPalm(self, side, want):
        """Roll the toon about its arm (shoulder to glove) until the palm,
        the hold joint's up, faces as near the view's `want` as it can, so
        a gag rests in the open palm instead of against the glove's back."""
        shoulder = self.joint(side, 'shoulder')
        glove = self.hand(side)
        if shoulder is None or shoulder.isEmpty():
            return
        self.toon.update(force=True)
        axis = glove.getPos(camera) - shoulder.getPos(camera)
        if axis.length() < 1e-4:
            return
        axis.normalize()
        def flat(v):
            v = Vec3(v) - axis * axis.dot(v)
            return v if v.length() > 1e-4 else None
        up = flat(glove.getQuat(camera).getUp())
        goal = flat(Vec3(want))
        if up is None or goal is None:
            return
        up.normalize()
        goal.normalize()
        angle = math.degrees(math.atan2(up.cross(goal).dot(axis), up.dot(goal)))
        pivot = glove.getPos(camera)
        self.toon.setMat(self.toon.getMat() * LMatrix4.translateMat(-pivot) * LMatrix4.rotateMat(angle, axis)
                         * LMatrix4.translateMat(pivot))
        self.toon.update(force=True)

    def shoulderInView(self, side):
        """Whether this side's shoulder (where the arm's sleeve is cut off)
        shows on the screen."""
        shoulder = self.joint(side, 'shoulder')
        lens = base.camLens
        p = shoulder.getPos(base.cam)
        if p[1] <= lens.getNear():
            return False
        film = Point2()
        lens.project(p, film)
        return abs(film[0]) < SHOULDER_OUT and abs(film[1]) < SHOULDER_OUT

    def placeGlove(self, side, glove):
        self.toon.update(force=True)
        here = self.hand(side).getPos(camera)
        self.toon.setPos(self.toon.getPos() + (glove - here))
        self.toon.update(force=True)

    def fold(self, side):
        """Fold the arm on this side into its shoulder, so only the arm
        holding the gag is in view (BO1 shows one arm for one-handed
        weapons); the other arm animates again."""
        if side == self.foldedSide:
            return
        for joint, lod, node in self.folded:
            try:
                self.toon.releaseJoint('torso', joint, lodName=lod)
            except TypeError:
                self.toon.releaseJoint('torso', joint)
            except Exception:
                pass
        self.folded = []
        self.foldedSide = side
        if side is None:
            return
        for joint in ARM_JOINTS[side]:
            for lod in self.toon.getLODNames():
                try:
                    node = self.toon.controlJoint(None, 'torso', joint, lodName=lod)
                except Exception:
                    node = None
                if node is not None and not node.isEmpty():
                    node.setScale(0.001)
                    self.folded.append((joint, lod, node))

    def gloveVerts(self, side, space):
        """The glove's vertices as drawn now (posed), in space's
        coordinates: only those within GLOVE_REACH of its palm joint."""
        from panda3d.core import GeomVertexReader, Thread
        palm = self.hand(side).getPos(self.toon)
        found = list(self.toon.findAllMatches('**/hands'))
        # The detail level the arms are drawn at first.
        found.sort(key=lambda np: '/1000/' not in str(np))
        verts = []
        for np in found:
            if np.isHidden() or not np.node().isGeomNode():
                continue
            mat = np.getMat(space)
            toToon = np.getMat(self.toon)
            node = np.node()
            for i in range(node.getNumGeoms()):
                vdata = node.getGeom(i).getVertexData().animateVertices(True, Thread.getCurrentThread())
                reader = GeomVertexReader(vdata, 'vertex')
                while not reader.isAtEnd():
                    v = reader.getData3()
                    if (toToon.xformPoint(v) - palm).length() <= GLOVE_REACH:
                        verts.append(mat.xformPoint(v))
            if verts:
                break
        return verts

    def gloveTriangles(self, side, space):
        """The glove's triangles as drawn now (posed), in space's
        coordinates: those within GLOVE_REACH of its palm joint."""
        from panda3d.core import GeomVertexReader, Thread
        palm = self.hand(side).getPos(self.toon)
        found = list(self.toon.findAllMatches('**/hands'))
        found.sort(key=lambda np: '/1000/' not in str(np))
        tris = []
        for np in found:
            if np.isHidden() or not np.node().isGeomNode():
                continue
            mat = np.getMat(space)
            toToon = np.getMat(self.toon)
            node = np.node()
            for i in range(node.getNumGeoms()):
                geom = node.getGeom(i)
                vdata = geom.getVertexData().animateVertices(True, Thread.getCurrentThread())
                reader = GeomVertexReader(vdata, 'vertex')
                points = []
                near = []
                while not reader.isAtEnd():
                    v = reader.getData3()
                    points.append(mat.xformPoint(v))
                    near.append((toToon.xformPoint(v) - palm).length() <= GLOVE_REACH)
                for k in range(geom.getNumPrimitives()):
                    prim = geom.getPrimitive(k).decompose()
                    for t in range(prim.getNumPrimitives()):
                        start, end = prim.getPrimitiveStart(t), prim.getPrimitiveEnd(t)
                        if end - start != 3:
                            continue
                        idx = [prim.getVertex(j) for j in range(start, end)]
                        if all(near[j] for j in idx):
                            tris.append(tuple(points[j] for j in idx))
            if tris:
                break
        return tris

    def hand(self, side=RIGHT):
        hands = self.toon.getLeftHands() if side == LEFT else self.toon.getRightHands()
        return hands[0] if hands else self.toon

    def holdPose(self, track, level=0):
        anim, hold, start, end, side = battlePose(track, level)
        self.kick = 'shout' if track == G.SOUND else 'gun' if (track, level) == (G.SQUIRT, 2) else None
        if self.track:
            self.track.finish()
            self.track = None
        self.fold(RIGHT if side == LEFT else LEFT)
        self.side = side
        self.anim = anim
        self.hold = hold
        self.start = start
        self.end = min(end, max(1, self.toon.getNumFrames(anim) or 1) - 1)
        self.toon.pose(anim, hold)
        if getattr(self, 'hiddenHead', None) is not None:
            self.hiddenHead.show()
            self.hiddenHead = None
        # The arm is aimed and grown for the rig at rest: a new gag arrives
        # while the arms are lowered (a switch, the trunk), and aiming
        # against the lowered, tilted rig left the arm bent and stretched
        # once it came back up.
        if self.swingTrack:
            self.swingTrack.finish()
            self.swingTrack = None
        rigMat = self.rig.getMat()
        self.rig.clearTransform()
        # Sound gags too: the megaphone in the glove like any other gag,
        # the arm coming in from the corner of the screen. (Put at the mouth
        # in first person, the arm hung in the middle of the view with its
        # cut-off shoulder showing, Arthur: "floats in front of you".)
        glove, pitch = VIEW_POSE.get(anim, VIEW_POSE['throw'])
        self.toon.setPosHpr(0, 0, 0, ARMS_H, pitch, 0)
        self.toon.setScale(ARMS_SCALE)
        if getattr(self, 'mirrored', False):
            self.toon.clearAttrib(CullFaceAttrib)
            self.unclipBody()
            self.mirrored = False
        self.releaseWrist()
        self.aimArm(side)
        if anim in PALM_UP_ANIMS:
            self.rollPalm(side, PALM_UP)
        # Place the toon so the glove lands where the view wants it, and
        # grow the arm about the glove until its shoulder is out of the
        # frame (the gag keeps its size: see grow).
        self.placeGlove(side, glove)
        self.grow = 1.0
        while self.shoulderInView(side) and self.grow < MAX_ARM_GROW:
            self.grow *= 1.08
            self.toon.setScale(self.toon.getScale() * 1.08)
            self.placeGlove(side, glove)
        self.rig.setMat(rigMat)

    def firstPerson(self):
        # Turned to face where the camera looks.
        self.toon.setPosHpr(0, 0, 0, 0, 0, 0)
        self.toon.setScale(ARMS_SCALE)
        self.grow = 1.0
        self.toon.update(force=True)
        head = self.toon.find('**/1000/**/__Actor_head')
        if head.isEmpty():
            head = self.toon.find('**/__Actor_head')
        # The camera is the toon's eyes: the head would fill the view, so
        # it is hidden and the toon slides until the hand holding the
        # megaphone to the mouth sits low in front of the camera.
        if not head.isEmpty():
            self.hiddenHead = head
            head.hide()
        hand = self.hand().getPos(self.swing)
        self.toon.setPos(self.toon.getPos() - hand + SOUND_HAND_AT)

    def shoot(self, rate):
        """The arm goes through the battle motion (throw, squirt, shout,
        button press) and comes back to the hold, within the gag's rate."""
        if self.anim is None:
            return
        if self.track:
            self.track.finish()
        duration = min(max(rate * 0.8, 0.15), 0.6)
        self.track = Sequence(ActorInterval(self.toon, self.anim, startFrame=self.start, endFrame=self.end, duration=duration),
                              Func(self.toon.pose, self.anim, self.hold))
        if self.kick:
            # The shout pushes the megaphone forward and it settles back, as
            # the battle toon leans into the blast; the squirt gun kicks up
            # and back. Small, so the arm's cut-off shoulder stays out of view.
            if self.swingTrack:
                self.swingTrack.finish()
            self.swing.setPosHpr(0, 0, 0, 0, 0, 0)
            kickPos, kickHpr = KICKS[self.kick]
            self.swingTrack = Sequence(LerpPosHprInterval(self.swing, duration * 0.3, kickPos, kickHpr, blendType='easeOut'),
                                       LerpPosHprInterval(self.swing, duration * 0.7, (0, 0, 0), (0, 0, 0), blendType='easeInOut'))
            self.swingTrack.start()
        self.track.start()

    def whack(self, hit=None):
        """The melee: the gag drawn back to the right and swung across the
        view like a club, then back to the hold. hit() runs as it lands."""
        if self.swingTrack:
            self.swingTrack.finish()
        windUp = LerpPosHprInterval(self.swing, WHACK_WINDUP, Point3(*WHACK_BACK[0]), Vec3(*WHACK_BACK[1]), blendType='easeOut')
        strike = LerpPosHprInterval(self.swing, WHACK_STRIKE, Point3(*WHACK_THROUGH[0]), Vec3(*WHACK_THROUGH[1]), blendType='easeIn')
        settle = LerpPosHprInterval(self.swing, WHACK_RECOVER, Point3(0, 0, 0), Vec3(0, 0, 0), blendType='easeInOut')
        steps = [windUp, strike]
        if hit is not None:
            steps.append(Func(hit))
        steps += [Wait(WHACK_HOLD), settle]
        self.swingTrack = Sequence(*steps)
        self.swingTrack.start()

    def destroy(self):
        if self.swingTrack:
            self.swingTrack.finish()
            self.swingTrack = None
        if self.motionTrack:
            self.motionTrack.pause()
            self.motionTrack = None
        if self.track:
            self.track.finish()
            self.track = None
        self.toon.delete()
        if not self.rig.isEmpty():
            self.rig.removeNode()


class Gag:
    """One gag in a slot."""

    def __init__(self, track, level, upgraded=False):
        self.track = track
        self.level = level
        self.fromLevel = level
        self.upgraded = upgraded
        damage, clip, reserve, rate, splash, prop = G.GAGS[(track, level)]
        self.clipSize = clip
        self.clip = clip
        self.reserve = int(reserve * (G.UPGRADE_RESERVE if upgraded else 1))
        self.rate = rate
        self.splash = splash
        self.prop = prop

    @property
    def damage(self):
        return G.gagDamage(self.track, self.level, self.upgraded)

    @property
    def name(self):
        name = G.gagName(self.track, self.level)
        return name + ' +' if self.upgraded else name

    def upgrade(self):
        """Mickey's: more damage, and a level 6 becomes the level 7."""
        if self.level == 5:
            self.level = 6
            damage, clip, reserve, rate, splash, prop = G.GAGS[(self.track, 6)]
            self.clipSize = clip
            self.rate = rate
            self.splash = splash
            self.prop = prop
        self.upgraded = True
        damage, clip, reserve, rate, splash, prop = G.GAGS[(self.track, self.level)]
        self.clip = self.clipSize
        self.reserve = int(reserve * G.UPGRADE_RESERVE)

    def maxOut(self):
        damage, clip, reserve, rate, splash, prop = G.GAGS[(self.track, self.level)]
        self.reserve = int(reserve * (G.UPGRADE_RESERVE if self.upgraded else 1))


class GagHandler:
    """Carries, shows and fires the player's gags."""
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalGags')

    def __init__(self, game, player):
        self.game = game
        self.player = player
        self.gags = [Gag(*G.STARTING_GAG)]
        self.current = 0
        self.nextShot = 0.0
        self.reloading = None
        self.viewProp = None
        self.viewTrack = None
        self.arms = None
        try:
            if getattr(game, 'dna', None) is not None:
                self.arms = ToonArms(game.dna)
        except Exception:
            GagHandler.notify.warning('no toon arms in view')
            import traceback
            traceback.print_exc()
            self.arms = None
        self.bonkReady = 0.0
        self.presentations = 0
        # Once the trunk has given the Presentation, Max Gags refills it.
        self.hasPresentation = False
        self.tnt = 0
        self.throwingTnt = False
        self.tntHeld = False
        self.tntReady = False
        self.tntBoomAt = 0.0
        self.tntFuse = None
        self.tntTrack = None
        self.grenades = []
        self.flying = []
        self.pendingSwitch = None
        self.showHeld()

    def destroy(self):
        if self.tntTrack:
            self.tntTrack.pause()
            self.tntTrack = None
        self.__clearView()
        for item in self.flying:
            item['np'].removeNode()
        self.flying = []
        for item in self.grenades:
            item['np'].removeNode()
            if item.get('fuse'):
                item['fuse'].stop()
        self.grenades = []
        if self.tntFuse:
            self.tntFuse.stop()
            self.tntFuse = None
        if self.reloading:
            taskMgr.remove(self.reloading)
            self.reloading = None
        if self.arms is not None:
            self.arms.destroy()
            self.arms = None

    # --- What is held ---

    def keepOnGlove(self, prop, hand, name=None):
        """Put the prop where all of it stands on the glove (Arthur: "the
        FULL SHIP needs to be ON THE PALM"): seen from above the palm, its
        footprint must lie inside the glove's own shape (the gap between
        thumb and fingers is not glove) with PALM_EDGE_ROOM of the glove's
        width to spare all round. Its turn is kept; it slides to where it
        has the most room, drawn smaller only if it fits nowhere. (Against
        the glove's convex outline, the ship's back stood over the gap by the
        thumb and past the glove's far edge.)"""
        from panda3d.core import GeomVertexReader
        glove = self.arms.gloveVerts(RIGHT, hand)
        shape = [tuple((v[0], v[1]) for v in tri) for tri in self.arms.gloveTriangles(RIGHT, hand)]
        if len(glove) < 3 or not shape:
            return
        # The glove from above on a fine grid, each cell with how far it is
        # inside the glove's edge.
        xs = [q[0] for t in shape for q in t]
        ys = [q[1] for t in shape for q in t]
        width = min(max(xs) - min(xs), max(ys) - min(ys))
        cell = width / 60.0
        if cell <= 0:
            return
        x0, y0 = min(xs) - cell * 2, min(ys) - cell * 2
        cols = int((max(xs) - x0) / cell) + 3
        rows = int((max(ys) - y0) / cell) + 3
        far = 1e9
        grid = [[0.0] * cols for _ in range(rows)]
        for a, b, c in shape:
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-12:
                continue
            for r in range(max(0, int((min(a[1], b[1], c[1]) - y0) / cell)),
                           min(rows, int((max(a[1], b[1], c[1]) - y0) / cell) + 1)):
                py = y0 + (r + 0.5) * cell
                for k in range(max(0, int((min(a[0], b[0], c[0]) - x0) / cell)),
                               min(cols, int((max(a[0], b[0], c[0]) - x0) / cell) + 1)):
                    px = x0 + (k + 0.5) * cell
                    l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
                    l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
                    if l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1 + 1e-9:
                        grid[r][k] = far
        # Distance to the edge (chamfer, two passes).
        diag = cell * 1.4142
        for r in range(rows):
            for k in range(cols):
                if grid[r][k]:
                    best = grid[r][k]
                    if r > 0:
                        best = min(best, grid[r - 1][k] + cell)
                        if k > 0:
                            best = min(best, grid[r - 1][k - 1] + diag)
                        if k + 1 < cols:
                            best = min(best, grid[r - 1][k + 1] + diag)
                    if k > 0:
                        best = min(best, grid[r][k - 1] + cell)
                    grid[r][k] = best
        for r in range(rows - 1, -1, -1):
            for k in range(cols - 1, -1, -1):
                if grid[r][k]:
                    best = grid[r][k]
                    if r + 1 < rows:
                        best = min(best, grid[r + 1][k] + cell)
                        if k + 1 < cols:
                            best = min(best, grid[r + 1][k + 1] + diag)
                        if k > 0:
                            best = min(best, grid[r + 1][k - 1] + diag)
                    if k + 1 < cols:
                        best = min(best, grid[r][k + 1] + cell)
                    grid[r][k] = best

        def room(points):
            # How far inside the glove's edge the nearest point is.
            worst = far
            for p in points:
                k = int((p[0] - x0) / cell)
                r = int((p[1] - y0) / cell)
                if r < 0 or k < 0 or r >= rows or k >= cols or not grid[r][k]:
                    return -cell
                worst = min(worst, grid[r][k])
            return worst
        # The prop from above the palm: its outline, its edges as well as its
        # corners (the glove's shape is not convex).
        own = []
        for np in prop.findAllMatches('**/+GeomNode'):
            if np.isHidden() or np.getName() in NOT_SOLID:
                continue
            mat = np.getMat(hand)
            node = np.node()
            for i in range(node.getNumGeoms()):
                reader = GeomVertexReader(node.getGeom(i).getVertexData(), 'vertex')
                while not reader.isAtEnd():
                    own.append(mat.xformPoint(reader.getData3()))
        if not own:
            return
        low = min(v[2] for v in own)
        foot = convexHull([(v[0], v[1]) for v in own])
        foot = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                for a, b in zip(foot, foot[1:] + foot[:1]) for t in (0.0, 0.25, 0.5, 0.75)]
        cx = sum(p[0] for p in foot) / len(foot)
        cy = sum(p[1] for p in foot) / len(foot)
        need = PALM_EDGE_ROOM * width
        aim = GLOVE_AIM.get(name)
        closest = [None]

        def spots(size, turn, least, step):
            # Every place the prop, this big and turned so, keeps least room.
            c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            shaped = [((p[0] - cx) * c - (p[1] - cy) * s_, (p[0] - cx) * s_ + (p[1] - cy) * c) for p in foot]
            found = []
            for r in range(0, rows, step):
                for k in range(0, cols, step):
                    if grid[r][k] < least:
                        continue
                    x = x0 + (k + 0.5) * cell
                    y = y0 + (r + 0.5) * cell
                    have = room([(x + p[0] * size, y + p[1] * size) for p in shaped])
                    if have >= least:
                        found.append((have, x, y, size, turn))
                    if closest[0] is None or have > closest[0][0]:
                        closest[0] = (have, x, y, size, turn)
            return found

        best = None
        if aim:
            # The middle of the palm (the deepest spot of the glove's shape),
            # moved by the aim: as big as it still fits there (Arthur: "move
            # it down towards the left a little more"), it goes as near to it
            # as it can with AIM_EDGE_ROOM of the glove's width to spare.
            deep = max((grid[r][k], r, k) for r in range(rows) for k in range(cols))
            tx = x0 + (deep[2] + 0.5) * cell + aim[0] * width
            ty = y0 + (deep[1] + 0.5) * cell + aim[1] * width
            reach = AIM_REACH * width
            for size in FIT_SIZES:
                if not any(spots(size, turn, need, 2) for turn in FIT_TURNS):
                    continue
                near = [f for turn in FIT_TURNS for f in spots(size, turn, AIM_EDGE_ROOM * width, 1)]
                if not near:
                    continue
                spot = min(near, key=lambda f: (f[1] - tx) ** 2 + (f[2] - ty) ** 2)
                if best is None:
                    best = spot
                if (spot[1] - tx) ** 2 + (spot[2] - ty) ** 2 <= reach * reach:
                    best = spot
                    break
        else:
            for size in FIT_SIZES:
                fits = [f for turn in FIT_TURNS for f in spots(size, turn, need, 2)]
                if fits:
                    best = max(fits)
                    break
        best = best or closest[0]
        # Fitting nowhere, it goes where it comes nearest (above).
        if best is None:
            return
        have, x, y, size, turn = best
        mat = prop.getMat(hand)
        mat = mat * LMatrix4.translateMat(-cx, -cy, -low) * LMatrix4.rotateMat(turn, Vec3(0, 0, 1)) \
            * LMatrix4.scaleMat(size) * LMatrix4.translateMat(x, y, low)
        self.keptTurn = turn
        prop.setMat(hand, mat)
        self.keptScale = size

    def restOnGlove(self, prop, hand):
        """Stand the prop on the glove's surface itself, measured point by
        point both ways: no corner of the prop below the glove under it, no
        bit of glove above the prop's underside (Arthur: the ship sank into
        the hand where the palm curves up; the old lift only looked at the
        glove's corners under the middle of its box)."""
        glove = self.arms.gloveTriangles(RIGHT, hand)
        own = propTriangles(prop, hand)
        if not glove or not own:
            return
        need = None
        # The prop's corners against the glove's top, and the glove's
        # corners against the prop's underside.
        for points, faces, sign in (([p for t in own for p in t], glove, 1),
                                    ([p for t in glove for p in t], own, -1)):
            boxes = [(min(q[0] for q in t), max(q[0] for q in t), min(q[1] for q in t), max(q[1] for q in t), t)
                     for t in faces]
            for p in points:
                for x0, x1, y0, y1, t in boxes:
                    if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
                        continue
                    z = heightIn(t, p[0], p[1])
                    if z is None:
                        continue
                    # How far the prop must rise for this pair to clear.
                    gap = (z - p[2]) if sign > 0 else (p[2] - z)
                    if need is None or gap > need:
                        need = gap
        if need is not None:
            prop.setPos(hand, prop.getPos(hand) + Vec3(0, 0, need + CLEAR_GAP))

    def seatInHold(self, prop, name):
        """Stand the prop in the open palm: upright on the hold joint (the
        way the battle holds a pie), centred on it, its bottom just in."""
        hand = self.arms.hand(RIGHT)
        self.arms.toon.update(force=True)
        prop.setHpr(hand, *HOLD_HPR.get(name, (0, 0, 0)))
        low, high = prop.getTightBounds(hand)
        if low is None:
            return
        centre = (low + high) * 0.5
        sink = HOLD_SINK.get(name, PALM_SINK)
        shift = Vec3(-centre[0], -centre[1], -low[2] - sink * (high[2] - low[2]))
        prop.setPos(hand, prop.getPos(hand) + shift)
        if name in CENTRE_ON_GLOVE:
            # Centred on the middle of the glove itself (the hold joint sits
            # off to one side of it), keeping its turn: a long gag then
            # overhangs both sides of the palm alike.
            verts = self.arms.gloveVerts(RIGHT, hand)
            if verts:
                n = float(len(verts))
                cx = sum(v[0] for v in verts) / n
                cy = sum(v[1] for v in verts) / n
                low, high = prop.getTightBounds(hand)
                mid = (low + high) * 0.5
                prop.setPos(hand, prop.getPos(hand) + Vec3(cx - mid[0], cy - mid[1], 0) * CENTRE_PULL)
        if name in HOLD_NUDGE:
            prop.setPos(camera, prop.getPos(camera) + HOLD_NUDGE[name])
        if name in KEEP_ON_GLOVE:
            self.keepOnGlove(prop, hand, name)
            self.restOnGlove(prop, hand)
            return
        # Nothing of the glove pokes up through the gag: its bottom is
        # lifted to the highest bit of glove under its middle.
        low, high = prop.getTightBounds(hand)
        half = (high - low) * 0.5 * CLEAR_FOOTS.get(name, CLEAR_FOOT)
        mid = (low + high) * 0.5
        under = [v[2] for v in self.arms.gloveVerts(RIGHT, hand)
                 if abs(v[0] - mid[0]) <= half[0] and abs(v[1] - mid[1]) <= half[1]]
        if under and max(under) > low[2] and name not in CLEAR_SKIP:
            prop.setPos(hand, prop.getPos(hand) + Vec3(0, 0, max(under) - low[2] + CLEAR_GAP))

    def seatOnPalm(self, prop):
        """Rest the prop on the glove: its bottom on the palm, centred over
        the hand, instead of floating past it."""
        hand = self.arms.hand(RIGHT)
        low, high = prop.getTightBounds(camera)
        if low is None:
            return
        palm = hand.getPos(camera)
        centre = (low + high) * 0.5
        # Over the palm in the view's x/y, bottom a little into the glove.
        # The glove's top is about GLOVE_TOP toon units over the palm joint;
        # resting there, the fingers show under the gag's near edge.
        gloveTop = GLOVE_TOP * self.arms.toon.getScale()[0]
        sink, nudge = PALM_FIT.get(getattr(prop, 'propName', None) or prop.getName(), (PALM_SINK, Vec3(0)))
        lift = Vec3(palm[0] - centre[0], palm[1] - centre[1],
                    palm[2] + gloveTop - low[2] - sink * (high[2] - low[2])) + nudge
        prop.setPos(camera, prop.getPos(camera) + lift)

    @property
    def gag(self):
        return self.gags[self.current] if self.gags else None

    def showHeld(self):
        self.__clearView()
        gag = self.gag
        if gag is None:
            return
        prop = BattleProps.globalPropPool.getProp(gag.prop)
        if self.arms is not None:
            # In the toon's own glove, the way the battle holds it.
            self.arms.holdPose(gag.track, gag.level)
            extras = []
            if gag.track == G.SOUND:
                # Megaphone and instrument in the glove exactly as MovieSound
                # puts them, at the size the instrument has when it blasts.
                megaphone = BattleProps.globalPropPool.getProp('megaphone')
                megaphone.reparentTo(self.arms.hand(RIGHT))
                extras.append(megaphone)
                prop.reparentTo(self.arms.hand(RIGHT))
                pos, hpr, scale = INSTRUMENT_IN_HAND.get(gag.level, INSTRUMENT_IN_HAND[0])
                prop.setPosHpr(Point3(*pos), Vec3(*hpr))
                prop.setScale(Vec3(*scale) if isinstance(scale, tuple) else scale)
                if gag.level == 6:
                    # The Opera Singer's helmet sits over the eyes in first
                    # person and hides the crosshair: only the megaphone shows.
                    prop.hide()
                # The instrument rides inside the megaphone as in the battle.
                self.arms.toon.update(force=True)
                prop.wrtReparentTo(megaphone)
                # The megaphone's handle stays in the fist, the megaphone
                # turned to lie along the fist the way the hose's nozzle
                # does, and the arm turns with it to point it at the cogs.
                megaphone.setTransform(megaphoneInFist(megaphone.getScale()[0] * MEGAPHONE_SCALE))
                self.arms.aimHeld(RIGHT, SOUND_GLOVE_AT,
                                  lambda parent: parent.getRelativeVector(megaphone, MEGAPHONE_AXIS), SOUND_ARM_SIZE,
                                  armFrom=SOUND_ARM_FROM, rollBy=SOUND_ROLL_BY, twist=SOUND_TWIST)
                if SOUND_MIRROR:
                    self.arms.mirrorAbout(megaphone, camera.getRelativeVector(megaphone, MEGAPHONE_AXIS)
                                          if SOUND_MIRROR == 'aim' else None)
                if SOUND_WRIST_STRAIGHT:
                    self.arms.straightenWrist(RIGHT, SOUND_WRIST_STRAIGHT)
                # Slid over in the view so the glove holds its right side.
                self.arms.toon.update(force=True)
                megaphone.setPos(camera, megaphone.getPos(camera) + MEGAPHONE_VIEW_SHIFT)
                # Smaller than in a battle so the arm holding it shows.
                megaphone.setScale(megaphone.getScale() * MEGAPHONE_SCALE / SOUND_ARM_SIZE)
            else:
                prop.reparentTo(self.arms.hand(RIGHT))
                pos, hpr = PROP_IN_HAND.get(gag.prop, (Point3(0, 0, 0), (0, 0, 0)))
                prop.setPosHpr(pos, Vec3(*hpr))
                prop.setScale(HAND_SCALE.get(gag.prop, 1.0) / self.arms.grow)
                if gag.prop in BATTLE_GRIP:
                    # Gripped exactly as the battle's hand holds it, at its size.
                    prop.pose(gag.prop, BATTLE_GRIP[gag.prop])
                    prop.setScale(1.0)
                if gag.track in FIT_TRACKS or gag.prop in FIT_PROPS:
                    self.arms.toon.update(force=True)
                    prop.setScale(1.0)
                    low, high = prop.getTightBounds(camera)
                    if low is not None:
                        size = max(high - low)
                        if size > 1e-4:
                            prop.setScale(FIT_SIZE / size)
                if gag.track == G.DROP:
                    # A drop gag stands upright on the open palm, a little
                    # smaller than the glove so the fingers show round it.
                    self.arms.toon.update(force=True)
                    prop.setHpr(camera, DROP_IN_VIEW_HPR)
                    low, high = prop.getTightBounds(camera)
                    if low is not None:
                        size = max(high - low)
                        if size > 1e-4:
                            prop.setScale(prop.getScale() * (DROP_FIT_SIZES.get(gag.prop, DROP_FIT_SIZE) / size))
                    self.seatInHold(prop, gag.prop) if PALM_HOLD else self.seatOnPalm(prop)
                elif gag.track == G.THROW or self.arms.anim == 'throw':
                    # A pie (or a gag carried the same way) sits on the
                    # glove's palm, tipped so the player sees its top.
                    self.arms.toon.update(force=True)
                    prop.setHpr(camera, PIE_IN_VIEW_HPR)
                    self.seatInHold(prop, gag.prop) if PALM_HOLD else self.seatOnPalm(prop)
                if gag.prop == 'water-gun':
                    # The battle's grip, its barrel (the gun's forward) out at the cogs.
                    prop.setScale(GUN_SCALE)
                    self.arms.aimHeld(RIGHT, GUN_GLOVE_AT, lambda parent: parent.getRelativeVector(prop, Vec3(0, 1, 0)), GUN_ARM_SIZE,
                                      GUN_AIM_AT, lambda parent: parent.getRelativeVector(prop, Vec3(0, 0, 1)),
                                      cant=GUN_CANT)
                    # Slid in its own frame so its grip sits inside the fist
                    # rather than poking out in front of the glove.
                    prop.setPos(prop, GUN_IN_FIST)
                    # Then pushed back along the line of sight (the same
                    # place and size on screen) so the thumb wraps in front
                    # of the grip rather than the grip's edge cutting across
                    # it (Arthur: "it clips ever so slightly into the glove").
                    at = prop.getPos(camera)
                    ray = Vec3(at)
                    ray.normalize()
                    prop.setPos(camera, at + ray * GUN_SINK)
                if gag.prop == 'firehose':
                    # The hose keeps the battle's grip (its size the glove's)
                    # and the arm and hose turn together to aim it.
                    prop.setTransform(hoseInHand())
                    self.arms.aimNozzle(prop)
                if gag.prop in VIEW_NUDGE:
                    self.arms.toon.update(force=True)
                    prop.setPos(camera, prop.getPos(camera) + VIEW_NUDGE[gag.prop])
            for node in [prop] + extras:
                node.setBin('fixed', 41)
                node.setLightOff()
                node.setColorScaleOff()
            self.viewExtras = extras
        else:
            pos, scale = VIEW_POS.get(gag.track, VIEW_POS[G.THROW])
            scale = VIEW_SCALE.get(gag.prop, scale)
            prop.reparentTo(camera)
            prop.setPos(pos)
            prop.setHpr(-20, 10, 0)
            prop.setScale(scale)
            prop.setDepthTest(0)
            prop.setDepthWrite(0)
            prop.setBin('fixed', 50)
            prop.setLightOff()
        self.viewProp = prop
        self.game.hud.setGag(gag, self.current, len(self.gags))

    def hideHeld(self):
        """The held gag out of view (Mickey has it)."""
        self.__clearView()

    def __clearView(self):
        if self.viewTrack:
            self.viewTrack.finish()
            self.viewTrack = None
        if self.viewProp:
            if hasattr(self.viewProp, 'cleanup'):
                self.viewProp.cleanup()
            self.viewProp.removeNode()
            self.viewProp = None
        for node in getattr(self, 'viewExtras', ()):
            if hasattr(node, 'cleanup'):
                node.cleanup()
            node.removeNode()
        self.viewExtras = []

    def __kick(self):
        if self.arms is not None:
            gag = self.gag
            self.arms.shoot(gag.rate if gag else 0.4)
            if gag is not None and gag.track == G.THROW and self.viewProp is not None and not self.viewProp.isEmpty():
                # The pie leaves the glove for the throw and the next one
                # is there when the arm comes back.
                if self.viewTrack:
                    self.viewTrack.finish()
                prop = self.viewProp
                self.viewTrack = Sequence(Func(prop.hide), Wait(min(max(gag.rate * 0.7, 0.12), 0.5)), Func(prop.show))
                self.viewTrack.start()
            return
        if self.viewProp is None or self.viewProp.isEmpty():
            return
        if self.viewTrack:
            self.viewTrack.finish()
        pos = self.viewProp.getPos()
        self.viewTrack = Sequence(LerpPosInterval(self.viewProp, 0.06, pos + Point3(0, -0.5, 0.2)),
                                  LerpPosInterval(self.viewProp, 0.18, pos))
        self.viewTrack.start()

    def switchTo(self, index):
        if 0 <= index < len(self.gags) and index != self.current:
            self.cancelReload()
            if self.arms is not None:
                # Down with this gag, up with the new one.
                self.pendingSwitch = index
                self.arms.putAway(SWITCH_DOWN, 0.0, SWITCH_UP, atBottom=self.__switched)
            else:
                self.current = index
                self.showHeld()

    def __switched(self):
        index = self.pendingSwitch
        self.pendingSwitch = None
        if index is not None and 0 <= index < len(self.gags):
            self.current = index
            self.showHeld()
            self.reloadIfEmpty()

    def swap(self):
        if len(self.gags) > 1:
            self.switchTo((self.current + 1) % len(self.gags))

    def slots(self):
        # Training Tracks: room for a third gag.
        return G.GAG_SLOTS + (1 if self.game.hasTonic('tracks') else 0)

    def dropExtraGags(self):
        """Down with Training Tracks: the third gag is gone."""
        if len(self.gags) <= G.GAG_SLOTS:
            return
        lost = self.gags[G.GAG_SLOTS:]
        del self.gags[G.GAG_SLOTS:]
        if self.current >= len(self.gags):
            self.cancelReload()
            self.current = 0
            self.showHeld()
        else:
            self.game.hud.setGag(self.gag, self.current, len(self.gags))
        return lost

    def give(self, track, level):
        """A gag from the trunk: into a free slot, or in place of the held one."""
        gag = Gag(track, level)
        if len(self.gags) < self.slots():
            self.gags.append(gag)
            self.current = len(self.gags) - 1
        else:
            self.gags[self.current] = gag
        self.cancelReload()
        self.showHeld()
        return gag

    def upgradeHeld(self):
        return self.upgradeGag(self.gag)

    def upgradeGag(self, gag):
        if gag is None or gag.upgraded or gag not in self.gags:
            return False
        gag.upgrade()
        if gag is self.gag:
            self.showHeld()
        self.game.hud.setGag(self.gag, self.current, len(self.gags))
        return True

    def holds(self, key):
        """Whether the toon already has this gag (BO1's box never hands out
        a gun you're carrying). An upgraded Birthday Cake that became a
        Wedding Cake still counts as the Birthday Cake it came from."""
        if key == G.PRESENTATION:
            return self.hasPresentation
        track, level = key
        for gag in self.gags:
            if gag.track == track and (gag.level == level or (gag.upgraded and gag.fromLevel == level)):
                return True
        return False

    def maxGags(self):
        for gag in self.gags:
            gag.maxOut()
        if self.hasPresentation:
            self.presentations = G.PRESENTATION_MAX
        self.tnt = G.TNT_MAX
        # An empty gag starts reloading at once; one put away empty reloads
        # the moment it comes out (reloadIfEmpty).
        self.cancelReload()
        self.reloadIfEmpty()
        self.game.hud.setGag(self.gag, self.current, len(self.gags))

    def givePresentations(self):
        self.hasPresentation = True
        self.presentations = G.PRESENTATION_MAX
        self.game.hud.setGag(self.gag, self.current, len(self.gags))

    def addTnt(self, n):
        self.tnt = min(G.TNT_MAX, self.tnt + n)
        self.game.hud.setGag(self.gag, self.current, len(self.gags))

    def __switchIfEmpty(self):
        """Out of ammo in this gag (clip and reserve): over to the other one,
        if it has any left."""
        gag = self.gag
        if gag is None or gag.clip > 0 or gag.reserve > 0 or self.pendingSwitch is not None:
            return
        for i, other in enumerate(self.gags):
            if i != self.current and (other.clip > 0 or other.reserve > 0):
                self.switchTo(i)
                return

    # --- Reloading ---

    def reload(self):
        gag = self.gag
        if gag is None or self.reloading or gag.clip == gag.clipSize or gag.reserve <= 0:
            return
        time = G.RELOAD_TIME * (0.5 if self.game.hasTonic('seltzer') else 1.0)
        self.reloading = 'survivalReload'
        self.game.hud.setReloading(time)
        taskMgr.doMethodLater(time, self.__reloaded, self.reloading)
        if self.arms is not None:
            # The gag goes down for the reload and comes back up as it ends.
            self.arms.putAway(time * 0.3, time * 0.35, time * 0.35)

    def reloadIfEmpty(self):
        gag = self.gag
        if gag is not None and gag.clip == 0 and gag.reserve > 0 and not self.throwingTnt:
            self.reload()

    def __reloaded(self, task):
        self.reloading = None
        gag = self.gag
        if gag is not None:
            need = gag.clipSize - gag.clip
            take = min(need, gag.reserve)
            gag.clip += take
            gag.reserve -= take
        self.game.hud.setGag(gag, self.current, len(self.gags))
        return task.done

    def cancelReload(self):
        if self.reloading:
            taskMgr.remove(self.reloading)
            self.reloading = None
            self.game.hud.setReloading(0)
            if self.arms is not None:
                self.arms.bringBack()

    # --- Firing ---

    def fire(self, held=False):
        gag = self.gag
        now = globalClock.getFrameTime()
        # Downed, the toon still shoots (BO1's last stand), for no beans.
        if gag is None or self.reloading or now < self.nextShot or self.throwingTnt:
            return False
        if self.arms is not None and (self.arms.lowered or self.pendingSwitch is not None):
            # The arms are down (a switch under way): no firing from the hip.
            return False
        if gag.clip <= 0:
            # An empty clip reloads by itself, held button or not (before,
            # holding fire on an empty gag never reloaded it).
            if gag.reserve <= 0:
                self.__switchIfEmpty()
            else:
                self.reload()
            return False
        # Held down, every gag keeps firing at its own rate (Arthur).
        gag.clip -= 1
        rate = gag.rate * (0.75 if self.game.power('instapop') else 1.0)
        if self.game.hasTonic('organic'):
            rate *= G.ORGANIC_RATE
        self.nextShot = now + rate
        self.__kick()
        sound = soundFor((gag.track, gag.level))
        if sound:
            # Some battle sounds open on a stretch of silence (the Opera
            # Singer's first 0.8 s): they start where the noise does.
            base.playSfx(sound, volume=0.6, time=SOUND_START.get((gag.track, gag.level), 0.0))
        eye = self.player.getEye()
        forward = self.player.getForward()
        if gag.track == G.SOUND:
            self.__blast(gag, eye, forward)
        elif gag.prop == 'stormcloud':
            self.__cloud(gag, eye, forward)
        elif gag.track == G.DROP:
            self.__drop(gag, eye, forward)
        else:
            self.__launch(gag, eye, forward)
        self.game.hud.setGag(gag, self.current, len(self.gags))
        if gag.clip == 0:
            if gag.reserve > 0:
                self.reload()
            else:
                self.__switchIfEmpty()
        return True

    def shotDamage(self, gag):
        """One shot's damage: Organic Gags makes each one count as two."""
        damage = gag.damage
        if self.game.hasTonic('organic'):
            damage *= G.ORGANIC_DAMAGE
        return damage

    def aimPoint(self, eye, forward, maxDist=G.MAX_RANGE):
        """Where the aim line lands: the first cog, else the wall or ground."""
        best = None
        hitCog = None
        for cog in self.game.cogs:
            hit = cog.hitTest(eye, forward, maxDist)
            if hit is not None and (best is None or hit[0] < best):
                best = hit[0]
                hitCog = cog
        wall = self.game.arena.rayHit(eye, forward, best if best is not None else maxDist)
        if wall is not None and (best is None or wall[0] < best):
            return wall[1], wall[0], None
        if hitCog is not None:
            return eye + forward * best, best, hitCog
        return eye + forward * maxDist, maxDist, None

    def __launch(self, gag, eye, forward):
        # A thrown pie or a squirt: the prop flies along the aim line and
        # splats on the first cog or wall in the way.
        if gag.track == G.SQUIRT:
            np = BattleProps.globalPropPool.getProp('spray')
            np.setScale(0.35 if gag.level < 5 else 0.8)
            np.setColor(0.6, 0.8, 1, 1)
            speed = G.PROJECTILE_SPEED * 1.6
        else:
            np = BattleProps.globalPropPool.getProp(gag.prop)
            np.setScale(VIEW_SCALE.get(gag.prop, 0.6) * 1.4)
            speed = G.PROJECTILE_SPEED
        np.reparentTo(render)
        start = eye + forward * 1.5 + Vec3(0.4, 0, -0.4)
        np.setPos(start)
        np.lookAt(start + forward)
        point, dist, cog = self.aimPoint(eye, forward)
        self.flying.append({'np': np, 'pos': Point3(start), 'dir': Vec3(forward), 'speed': speed, 'left': dist - 1.5,
                            'gag': gag, 'target': cog, 'end': point, 'spin': gag.track == G.THROW})

    def tick(self, dt):
        if self.arms is not None:
            self.arms.animate(dt, getattr(self.player, 'moveState', 'idle'))
        if self.throwingTnt and self.tntHeld and globalClock.getFrameTime() >= self.tntBoomAt:
            self.__tntInHandBoom()
        if self.grenades:
            self.__tickGrenades(dt)
        if not self.flying:
            return
        done = []
        for item in self.flying:
            step = item['speed'] * dt
            item['pos'] += item['dir'] * step
            item['left'] -= step
            np = item['np']
            np.setPos(item['pos'])
            if item['spin']:
                np.setR(np.getR() + 720 * dt)
            if item['left'] <= 0:
                done.append(item)
        for item in done:
            self.flying.remove(item)
            item['np'].removeNode()
            self.__land(item['gag'], item['end'], item['target'])

    def __land(self, gag, point, cog):
        self.__splat(point, gag.track)
        if gag.splash > 0:
            self.game.damageArea(point, gag.splash + 1.5, self.shotDamage(gag), head=False)
        elif cog is not None and not cog.dead:
            head = point[2] > cog.pos[2] + cog.height * cog.headFraction
            self.game.damageCog(cog, self.shotDamage(gag), head=head)

    def __splat(self, point, track):
        splat = BattleProps.globalPropPool.getProp('splat')
        splat.setColor(SPLAT_COLORS.get(track, Vec4(1, 1, 1, 1)))
        splat.reparentTo(render)
        splat.setPos(point)
        splat.setBillboardPointEye()
        splat.setScale(0.6)
        Sequence(ActorInterval(splat, 'splat'), Func(splat.cleanup), Func(splat.removeNode)).start()

    def __blast(self, gag, eye, forward):
        # A cone in front of the player: every cog in it is hit, the ones
        # behind other cogs too (the noise goes through them); only walls
        # stop it. A cog counts as in the cone if any of its body is, so a
        # big cog right in front is never missed.
        reach = gag.splash
        flat = Vec3(forward[0], forward[1], 0)
        if flat.lengthSquared() < 1e-6:
            flat = render.getRelativeVector(self.player.body, Vec3(0, 1, 0))
        flat.normalize()
        spread = math.tan(math.radians(CONE_HALF_ANGLE))
        hits = 0
        for cog in list(self.game.cogs):
            if cog.dead or cog.state == 'landing':
                continue
            rel = Vec3(cog.pos[0] - eye[0], cog.pos[1] - eye[1], 0)
            along = rel.dot(flat)
            if along < -cog.radius or along - cog.radius > reach:
                continue
            side = abs(rel[0] * flat[1] - rel[1] * flat[0])
            if side > max(0.0, along) * spread + cog.radius + SOUND_NEAR_WIDTH:
                continue
            if not self.game.arena.clearLine(eye, Point3(cog.pos[0], cog.pos[1], cog.pos[2] + 2)):
                continue
            damage = self.shotDamage(gag)
            if gag.level == 6 and gag.upgraded:
                damage = cog.hp
            self.game.damageCog(cog, damage)
            hits += 1
        self.game.hud.ring(reach)
        return hits

    def __drop(self, gag, eye, forward):
        point, dist, cog = self.aimPoint(eye, forward)
        if cog is not None:
            point = Point3(cog.pos)
        else:
            z = self.game.arena.groundZ(point[0], point[1])
            if z is not None:
                point = Point3(point[0], point[1], z)
        prop = BattleProps.globalPropPool.getProp(gag.prop)
        prop.reparentTo(render)
        # The size the battle drops them at next to a cog (Arthur: the piano
        # was far too small).
        scale = DROP_SCALE.get(gag.prop, 1.0)
        prop.setScale(scale)
        above = Point3(point[0], point[1], point[2] + 30)
        prop.setPos(above)
        prop.setH(self.player.getH() + 180)
        shadow = loader.loadModel('phase_3/models/props/drop_shadow')
        shadow.reparentTo(render)
        shadow.setPos(point[0], point[1], point[2] + 0.1)
        shadow.setScale(0.1)
        shadow.setColor(0, 0, 0, 0.5)
        shadow.setTransparency(1)
        # Animated drops (the piano, the safe...): the battle animation does
        # its own fall from high up, then lies on the ground a while. The
        # prop is held in that lying pose, flat (Arthur: the piano came down
        # tipped up, the model's pose before any animation).
        land = Wait(DROP_STAY)
        if hasattr(prop, 'getNumFrames') and prop.getNumFrames(gag.prop):
            prop.pose(gag.prop, DROP_REST_FRAME.get(gag.prop, 0))
        lift = DROP_REST_LIFT.get(gag.prop, 0.0) * scale
        point = Point3(point[0], point[1], point[2] + lift)
        Sequence(Parallel(LerpPosInterval(prop, G.DROP_FALL, point, blendType='easeIn'),
                          LerpScaleInterval(shadow, G.DROP_FALL, gag.splash * 0.4 + 0.5)),
                 Func(self.__dropped, gag, point),
                 Func(shadow.removeNode),
                 land,
                 LerpScaleInterval(prop, 0.3, 0.01),
                 Func(prop.removeNode)).start()

    def __cloud(self, gag, eye, forward):
        """The Storm Cloud, as in a battle: it appears over the cog (or the
        aim point), grows, and rains on everything under it."""
        point, dist, cog = self.aimPoint(eye, forward)
        if cog is not None:
            point = Point3(cog.pos)
            height = cog.height
        else:
            z = self.game.arena.groundZ(point[0], point[1])
            if z is not None:
                point = Point3(point[0], point[1], z)
            height = 6.0
        cloud = BattleProps.globalPropPool.getProp('stormcloud')
        cloud.reparentTo(render)
        cloud.setPos(point[0], point[1], point[2] + height + CLOUD_ABOVE)
        cloud.setScale(0.01)
        cloud.setLightOff()
        cloud.pose('stormcloud', 0)
        steps = [LerpScaleInterval(cloud, CLOUD_GROW, Point3(3, 3, 3), startScale=0.01), Func(self.__rained, gag, point)]
        rain = None
        try:
            from toontown.battle import BattleParticles
            from direct.interval.ParticleInterval import ParticleInterval
            BattleParticles.loadParticles()
            rain = BattleParticles.createParticleEffect(file='liquidate')
            steps.append(Parallel(ParticleInterval(rain, cloud, worldRelative=0, duration=CLOUD_RAIN, cleanup=True),
                                  ActorInterval(cloud, 'stormcloud', startTime=1, duration=CLOUD_RAIN)))
        except Exception:
            steps.append(ActorInterval(cloud, 'stormcloud', startTime=1, duration=CLOUD_RAIN))
        steps += [LerpScaleInterval(cloud, 0.4, 0.01), Func(cloud.cleanup), Func(cloud.removeNode)]
        Sequence(*steps).start()

    def __rained(self, gag, point):
        self.game.damageArea(point, gag.splash + 1.5, self.shotDamage(gag), head=False)

    def __dropped(self, gag, point):
        self.game.damageArea(point, gag.splash + 1.5, self.shotDamage(gag), head=True)
        self.game.hud.shake()

    # --- The bonk and the Presentation ---

    def bonk(self):
        """The melee: a whack with the held gag, which uses none of it."""
        now = globalClock.getFrameTime()
        if now < self.bonkReady or self.player.down or self.throwingTnt:
            return False
        if self.arms is not None and (self.arms.lowered or self.pendingSwitch is not None):
            return False
        self.bonkReady = now + G.BONK_TIME
        # The whack lands the moment it is pressed, as BO1's knife does: a
        # cog that a melee pops can't finish the swing it started (Arthur:
        # one he popped with a melee still knocked him down while the club
        # was on its way).
        eye = self.player.getEye()
        forward = self.player.getForward()
        point, dist, cog = self.aimPoint(eye, forward, G.BONK_REACH + 8.0)
        # The reach counts from the cog's own body, not its middle (a big
        # cog's middle is far inside it): a whack lands from about as far
        # as a cog can swing at the toon.
        if cog is not None and dist - cog.radius > G.BONK_REACH:
            cog = None
        if cog is not None:
            self.game.damageCog(cog, G.BONK_DAMAGE, bonk=True)

        def land():
            self.game.hud.bonk()
            if cog is not None:
                base.playSfx(globalBattleSoundCache.getSound(MELEE_HIT_SOUND), volume=0.8)
            else:
                base.playSfx(globalBattleSoundCache.getSound(MELEE_MISS_SOUND), volume=0.5)
        if self.arms is not None:
            self.arms.whack(land)
        else:
            land()
        return True

    # --- TNT (the frag grenade) ---

    def throwTnt(self):
        """BO1's frag: pressed, the toon swaps the gag for a lit stick of
        TNT and the fuse starts; held, it cooks in the glove; let go, it is
        thrown overhand with what is left of the fuse. Held too long, it
        goes off in the toon's hand."""
        if self.tnt <= 0 or self.player.down or self.throwingTnt or self.pendingSwitch is not None:
            return False
        self.tnt -= 1
        self.throwingTnt = True
        self.tntHeld = True
        self.tntReady = False
        now = globalClock.getFrameTime()
        self.tntBoomAt = now + G.TNT_FUSE
        self.cancelReload()
        self.game.hud.setGag(self.gag, self.current, len(self.gags))
        # The fuse hisses from the moment it is lit (the battle's dynamite,
        # past its lighting).
        self.tntFuse = base.loader.loadSfx(TNT_FUSE_SOUND)
        if self.tntFuse:
            self.tntFuse.setVolume(0.5)
            self.tntFuse.setTime(0.8)
            self.tntFuse.setLoop(True)
            self.tntFuse.play()
        steps = []
        if self.arms is not None:
            steps += [Func(self.arms.putAway, 0.1, 0.0, 0.12, self.__tntInHand), Wait(0.22)]
        steps.append(Func(self.__tntCooking))
        self.tntTrack = Sequence(*steps)
        self.tntTrack.start()
        return True

    def __tntCooking(self):
        self.tntTrack = None
        self.tntReady = True
        if not self.tntHeld:
            # Let go before it was even in the glove: thrown at once.
            self.__throwCooked()

    def letGoTnt(self):
        """The TNT button let go: the cooked stick is thrown."""
        if not self.throwingTnt or not self.tntHeld:
            return
        self.tntHeld = False
        if self.tntReady:
            self.__throwCooked()

    def dropTnt(self):
        """The toon went down holding a lit stick: it falls at its feet,
        fuse still burning."""
        if not self.throwingTnt or not self.tntHeld:
            return
        self.tntHeld = False
        self.tntReady = False
        if self.tntTrack:
            self.tntTrack.pause()
            self.tntTrack = None
        self.__releaseTnt(drop=True)
        self.__tntThrown()

    def __throwCooked(self):
        self.tntReady = False
        steps = []
        if self.arms is not None:
            steps += [Func(self.arms.shoot, 0.75), Wait(0.28)]
        steps += [Func(self.__releaseTnt), Wait(0.3), Func(self.__tntThrown)]
        self.tntTrack = Sequence(*steps)
        self.tntTrack.start()

    def __tntInHandBoom(self):
        """Cooked too long: it goes off in the glove and the toon goes
        down, whatever its laff (BO1)."""
        self.tntHeld = False
        self.tntReady = False
        if self.tntTrack:
            self.tntTrack.pause()
            self.tntTrack = None
        fuse, self.tntFuse = getattr(self, 'tntFuse', None), None
        if self.viewProp is not None and not self.viewProp.isEmpty():
            self.viewProp.hide()
        point = self.player.getPos() + self.player.getFlatForward() * 1.5
        self.__boom(point, fuse, selfDamage=False)
        self.game.count('tnt cooked off')
        self.throwingTnt = False
        self.showHeld()
        if not self.player.down:
            self.player.hurt(self.player.hp + 1)

    def __tntInHand(self):
        self.__clearView()
        self.arms.holdPose(G.THROW, 0)
        # Higher and further in than a pie, clear of the gag box, so the
        # stick is seen in the glove before it goes.
        rigMat = self.arms.rig.getMat()
        self.arms.rig.clearTransform()
        self.arms.placeGlove(RIGHT, TNT_GLOVE)
        self.arms.rig.setMat(rigMat)
        prop = BattleProps.globalPropPool.getProp('tnt')
        prop.reparentTo(self.arms.hand(RIGHT))
        self.arms.toon.update(force=True)
        # The stick is an Actor, whose bounds can't be trusted for fitting:
        # it gets a fixed size in the glove, as the battle holds it.
        prop.setScale(TNT_IN_HAND / self.arms.grow)
        prop.setHpr(camera, TNT_IN_VIEW_HPR)
        self.seatOnPalm(prop)
        prop.setBin('fixed', 41)
        prop.setLightOff()
        prop.setColorScaleOff()
        self.viewProp = prop

    def __releaseTnt(self, drop=False):
        eye = self.player.getEye()
        forward = self.player.getForward()
        # It leaves from the glove (never from inside the camera), at least
        # a couple of feet out so it doesn't fill the view.
        start = eye + forward * 2.5 + render.getRelativeVector(camera, Vec3(0.6, 0, -0.2))
        if self.viewProp is not None and not self.viewProp.isEmpty():
            hand = self.viewProp.getPos(render)
            if (hand - eye).length() > 0.5:
                start = hand + forward * 1.5
            self.viewProp.hide()
        np = BattleProps.globalPropPool.getProp('tnt')
        np.reparentTo(render)
        np.setScale(0.9)
        np.setPos(start)
        # Never hidden by the ground or behind the camera's near plane: the
        # thrown stick always shows where it lies (Arthur).
        np.setLightOff()
        vel = forward * G.TNT_THROW_SPEED + Vec3(0, 0, G.TNT_THROW_UP)
        if drop:
            start = self.player.getPos() + self.player.getFlatForward() * 1.0 + Vec3(0, 0, 1.0)
            vel = Vec3(0, 0, 0)
        fuse, self.tntFuse = getattr(self, 'tntFuse', None), None
        boomAt = getattr(self, 'tntBoomAt', None) or globalClock.getFrameTime() + G.TNT_FUSE
        self.grenades.append({'np': np, 'pos': Point3(start), 'vel': vel, 'boom': boomAt,
                              'rest': False, 'fuse': fuse})
        self.game.count('tnt thrown')

    def __tntThrown(self):
        self.tntTrack = None
        self.throwingTnt = False
        self.showHeld()
        self.reloadIfEmpty()

    def __tickGrenades(self, dt):
        now = globalClock.getFrameTime()
        arena = self.game.arena
        for item in list(self.grenades):
            np = item['np']
            if not item['rest']:
                vel = item['vel']
                vel.setZ(vel[2] - G.TNT_GRAVITY * dt)
                old = item['pos']
                new = old + vel * dt
                hit = arena.rayHit(old, Vec3(new - old).normalized(), (new - old).length() + 0.3) if (new - old).length() > 1e-4 else None
                if hit is not None and hit[0] < (new - old).length() + 0.3:
                    # A wall or the ground: bounce, losing most of the speed.
                    point = hit[1]
                    ground = arena.groundZ(point[0], point[1])
                    if ground is not None and abs(point[2] - ground) < 0.6:
                        vel.setZ(-vel[2] * 0.3)
                        vel.setX(vel[0] * 0.5)
                        vel.setY(vel[1] * 0.5)
                        new = Point3(new[0], new[1], max(new[2], ground + 0.25))
                        if abs(vel[2]) < 2.0:
                            item['rest'] = True
                            new.setZ(ground + 0.25)
                    else:
                        vel.setX(-vel[0] * 0.35)
                        vel.setY(-vel[1] * 0.35)
                        new = Point3(old)
                if not item['rest']:
                    # A fast stick can pass the floor between two frames:
                    # never below the ground, where it can't be seen.
                    floor = arena.groundZ(new[0], new[1])
                    if floor is not None and new[2] < floor + 0.25 and old[2] >= floor - 0.5:
                        new.setZ(floor + 0.25)
                        vel.setZ(abs(vel[2]) * 0.3)
                        vel.setX(vel[0] * 0.5)
                        vel.setY(vel[1] * 0.5)
                        if abs(vel[2]) < 2.0:
                            item['rest'] = True
                item['pos'] = new
                np.setPos(new)
                if item['rest']:
                    # Lying on its side on the ground, in plain sight.
                    np.setHpr(np.getH(), 0, 90)
                else:
                    np.setHpr(np.getH() + 400 * dt, np.getP() + 300 * dt, 0)
            if now >= item['boom']:
                self.grenades.remove(item)
                self.__boom(item['pos'], item.get('fuse'))
                np.removeNode()

    def __boom(self, point, fuse=None, selfDamage=True):
        damage = G.tntDamage(self.game.roundNum)
        radius = G.TNT_RADIUS
        for cog in list(self.game.cogs):
            if cog.dead or cog.state == 'landing':
                continue
            d = (Vec3(cog.pos[0] - point[0], cog.pos[1] - point[1], 0)).length() - cog.radius
            if d > radius:
                continue
            # Full in the middle, a quarter at the edge.
            share = 1.0 - 0.75 * max(0.0, d) / radius
            self.game.damageCog(cog, int(damage * share))
        me = self.player.getPos()
        d = (Vec3(me - point)).length()
        if selfDamage and d < G.TNT_SELF_RADIUS and not self.player.down:
            self.player.hurt(int(G.TNT_SELF_DAMAGE * (1.0 - d / G.TNT_SELF_RADIUS)) + 1)
        explosion = loader.loadModel('phase_3.5/models/props/explosion')
        explosion.setBillboardPointEye()
        explosion.setDepthWrite(False)
        explosion.setLightOff()
        explosion.reparentTo(render)
        explosion.setPos(point + Vec3(0, 0, 1.5))
        explosion.setScale(1.0)
        Sequence(LerpScaleInterval(explosion, 0.35, 6.0, startScale=1.0), Func(explosion.removeNode)).start()
        try:
            from toontown.battle import BattleParticles
            BattleParticles.loadParticles()
            smoke = BattleParticles.createParticleEffect('BigGearExplosion', numParticles=10)
            smoke.setPos(point)
            from direct.interval.ParticleInterval import ParticleInterval
            ParticleInterval(smoke, render, worldRelative=0, duration=0.8, cleanup=True).start()
        except Exception:
            pass
        if fuse is not None:
            fuse.stop()
        boom = base.loader.loadSfx(TNT_BOOM % random.randint(1, 3))
        if boom:
            base.playSfx(boom, volume=1.0)
        dist = (camera.getPos(render) - point).length()
        if dist < radius * 2:
            self.game.hud.shake()

    def __playPresentation(self, music):
        if music:
            base.playSfx(music, volume=0.8)

    def throwPresentation(self):
        if self.presentations <= 0 or self.player.down:
            return False
        self.presentations -= 1
        eye = self.player.getEye()
        forward = self.player.getForward()
        point, dist, cog = self.aimPoint(eye, forward, 35.0)
        z = self.game.arena.groundZ(point[0], point[1])
        if z is not None:
            point = Point3(point[0], point[1], z)
        # The battle's own Presentation: the slide show flies out small,
        # lands, opens up to full size and plays its music.
        prop = BattleProps.globalPropPool.getProp('slideshow')
        prop.reparentTo(render)
        start = eye + forward * 1.5
        prop.setPos(start)
        prop.setScale(0.1)
        prop.setH(self.player.getH())
        now = globalClock.getFrameTime()
        music = base.loader.loadSfx('phase_5/audio/sfx/TL_presentation.ogg')
        Sequence(Parallel(LerpPosInterval(prop, 0.6, point, startPos=start, blendType='easeOut'),
                          LerpScaleInterval(prop, 0.6, 0.25, startScale=0.1)),
                 Func(self.game.startLure, point, now + 0.6 + G.PRESENTATION_LURE),
                 Func(self.__playPresentation, music),
                 LerpScaleInterval(prop, 0.8, 1.0, startScale=0.25),
                 Wait(max(0.0, G.PRESENTATION_LURE - 1.2)),
                 LerpScaleInterval(prop, 0.4, Point3(1.0, 1.0, 0.1)),
                 Func(self.game.damageArea, point, G.PRESENTATION_POP, G.PRESENTATION_DAMAGE, False),
                 Func(self.__splat, point, G.THROW),
                 Func(prop.removeNode)).start()
        self.game.hud.setGag(self.gag, self.current, len(self.gags))
        return True
