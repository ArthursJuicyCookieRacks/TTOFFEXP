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
from panda3d.core import LMatrix4, NodePath, Point2, Point3, Vec3, Vec4

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
MELEE_HIT_SOUND = 'MG_sfx_vine_game_bat_hit.ogg'
MELEE_MISS_SOUND = 'AA_pie_throw_only.ogg'


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
    (G.SQUIRT, 2): ('water-gun', 44, 44, 93, RIGHT),
    (G.SQUIRT, 3): ('hold-bottle', 44, 44, 96, RIGHT),
    (G.SQUIRT, 4): ('firehose', 30, 30, 72, RIGHT),
    (G.SQUIRT, 5): ('throw', 38, 38, 52, RIGHT),
    (G.SQUIRT, 6): ('throw', 38, 38, 52, RIGHT),
    # The megaphone is at the mouth on the frame the battle blasts (tSound).
    G.SOUND: ('sound', 59, 50, 72, RIGHT),
    G.DROP: ('throw', 38, 38, 52, RIGHT),
    G.LURE: ('throw', 38, 38, 52, RIGHT),
}
# Where the glove that holds the gag sits in the view (camera space), per
# hand, so the gag is big and low on the right like a BO1 view model.
# Where the glove that holds the gag sits in the view (camera space) and
# how far the toon leans back under the camera, per animation: the gag is
# big and low on the right like a BO1 view model, the shoulder stays below
# the frame.
VIEW_POSE = {'throw': (Point3(1.25, 4.8, -1.35), 15), 'water-gun': (Point3(1.0, 3.8, -0.95), 25),
             'hold-bottle': (Point3(1.0, 4.0, -0.6), 10), 'spit': (Point3(1.0, 4.0, -0.7), 5),
             'firehose': (Point3(1.1, 4.6, -1.3), -10), 'sound': (Point3(1.4, 5.6, -1.5), 0),
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
GLOVE_TOP = 0.12
# Gags carried on the palm that come in all sizes (a safe, a piano, a storm
# cloud, a geyser...) are fitted to one size in the view, a pie's.
FIT_SIZE = 0.85
DROP_FIT_SIZE = 0.7
# Facing the player a little, so a drop gag shows its front and its top.
DROP_IN_VIEW_HPR = Vec3(-25, 12, 0)
FIT_TRACKS = (G.DROP, G.LURE)
FIT_PROPS = ('squirting-flower', 'stormcloud', 'geyser', 'firehose')
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
# Each level's instrument in the glove, as MovieSound places it (pos, hpr,
# the scale it blasts at).
INSTRUMENT_IN_HAND = {0: ((-1.1, -1.4, 0.1), (145, 0, 0), 0.65), 1: ((-1.2, -1.3, 0.1), (145, 0, 85), 0.2),
                      2: ((-1.3, -1.4, 0.1), (145, 0, 85), 0.4), 3: ((-1.0, -1.5, 0.2), (145, 0, 85), 0.5),
                      4: ((-0.6, -0.9, 0.15), (145, 0, 85), 0.15), 5: ((-0.8, -0.9, 0.2), (145, 0, 0), 0.15),
                      6: ((-1.04, -1.17, 0.26), (145, 0, 90), 1.1)}
# Sound gags ride inside the megaphone the way the battle shows them.
INSTRUMENT_IN_MEGAPHONE = (Point3(-1.1, -1.4, 0.1), (145, 0, 0))
# The megaphone is a big prop; this close to the camera it is shrunk.
MEGAPHONE_SCALE = 0.6
INSTRUMENT_SCALE = {'bikehorn': 0.5, 'whistle': 0.6, 'bugle': 0.6, 'aoogah': 0.6, 'elephant': 0.5, 'fog_horn': 0.5, 'singing': 0.5}
HAND_SCALE = {'ship': 0.05, 'piano': 0.1, 'safe': 0.22, 'weight': 0.25, 'anvil': 0.3, 'sandbag': 0.6, 'flowerpot': 0.6,
              'geyser': 0.1, 'stormcloud': 0.25, 'firehose': 1.0, 'wedding-cake': 1.0, 'birthday-cake': 1.0,
              '1dollar': 0.8, 'glass': 1.4, 'bottle': 1.0, 'water-gun': 1.0, 'squirting-flower': 1.0}
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
        want = Vec3(ARM_FROM)
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

    def hand(self, side=RIGHT):
        hands = self.toon.getLeftHands() if side == LEFT else self.toon.getRightHands()
        return hands[0] if hands else self.toon

    def holdPose(self, track, level=0):
        anim, hold, start, end, side = battlePose(track, level)
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
        if anim == 'sound':
            # Sound gags are used the battle's way, the megaphone up at the
            # mouth: the toon is put where its own eyes are the camera, so
            # the view is the battle pose in first person.
            self.firstPerson()
            self.rig.setMat(rigMat)
            return
        glove, pitch = VIEW_POSE.get(anim, VIEW_POSE['throw'])
        self.toon.setPosHpr(0, 0, 0, ARMS_H, pitch, 0)
        self.toon.setScale(ARMS_SCALE)
        self.aimArm(side)
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
        if self.anim == 'sound':
            # The shout pushes the megaphone forward from the mouth and
            # it settles back, as the battle toon leans into the blast.
            if self.swingTrack:
                self.swingTrack.finish()
            self.swing.setPosHpr(0, 0, 0, 0, 0, 0)
            self.swingTrack = Sequence(LerpPosHprInterval(self.swing, duration * 0.3, (0, 0.35, 0.05), (0, 4, 0), blendType='easeOut'),
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
        self.upgraded = upgraded
        damage, clip, reserve, rate, splash, prop = G.GAGS[(track, level)]
        self.clipSize = clip
        self.clip = clip
        self.reserve = int(reserve * (1.5 if upgraded else 1))
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
        self.reserve = int(reserve * 1.5)

    def maxOut(self):
        damage, clip, reserve, rate, splash, prop = G.GAGS[(self.track, self.level)]
        self.reserve = int(reserve * (1.5 if self.upgraded else 1))


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
        self.flying = []
        self.pendingSwitch = None
        self.showHeld()

    def destroy(self):
        self.__clearView()
        for item in self.flying:
            item['np'].removeNode()
        self.flying = []
        if self.reloading:
            taskMgr.remove(self.reloading)
            self.reloading = None
        if self.arms is not None:
            self.arms.destroy()
            self.arms = None

    # --- What is held ---

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
        lift = Vec3(palm[0] - centre[0], palm[1] - centre[1],
                    palm[2] + gloveTop - low[2] - PALM_SINK * (high[2] - low[2]))
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
            else:
                prop.reparentTo(self.arms.hand(RIGHT))
                pos, hpr = PROP_IN_HAND.get(gag.prop, (Point3(0, 0, 0), (0, 0, 0)))
                prop.setPosHpr(pos, Vec3(*hpr))
                prop.setScale(HAND_SCALE.get(gag.prop, 1.0) / self.arms.grow)
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
                            prop.setScale(prop.getScale() * (DROP_FIT_SIZE / size))
                    self.seatOnPalm(prop)
                elif gag.track == G.THROW or self.arms.anim == 'throw':
                    # A pie (or a gag carried the same way) sits on the
                    # glove's palm, tipped so the player sees its top.
                    self.arms.toon.update(force=True)
                    prop.setHpr(camera, PIE_IN_VIEW_HPR)
                    self.seatOnPalm(prop)
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

    def swap(self):
        if len(self.gags) > 1:
            self.switchTo((self.current + 1) % len(self.gags))

    def give(self, track, level):
        """A gag from the trunk: into a free slot, or in place of the held one."""
        gag = Gag(track, level)
        if len(self.gags) < G.GAG_SLOTS:
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

    def maxGags(self):
        for gag in self.gags:
            gag.maxOut()
        self.presentations = min(self.presentations + 1, G.PRESENTATION_MAX) if self.presentations else self.presentations
        self.game.hud.setGag(self.gag, self.current, len(self.gags))

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
        if gag is None or self.reloading or now < self.nextShot or self.player.down:
            return False
        if self.arms is not None and (self.arms.lowered or self.pendingSwitch is not None):
            # The arms are down (a switch under way): no firing from the hip.
            return False
        if gag.clip <= 0:
            if not held:
                self.reload()
            return False
        if held and gag.track not in (G.SQUIRT,) and gag.rate > 0.3:
            # Only the squirt gags spray while the button is held.
            return False
        gag.clip -= 1
        self.nextShot = now + gag.rate * (0.75 if self.game.power('instapop') else 1.0)
        self.__kick()
        sound = soundFor((gag.track, gag.level))
        if sound:
            base.playSfx(sound, volume=0.6)
        eye = self.player.getEye()
        forward = self.player.getForward()
        if gag.track == G.SOUND:
            self.__blast(gag, eye, forward)
        elif gag.track == G.DROP:
            self.__drop(gag, eye, forward)
        else:
            self.__launch(gag, eye, forward)
        self.game.hud.setGag(gag, self.current, len(self.gags))
        if gag.clip == 0 and gag.reserve > 0:
            self.reload()
        return True

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
            self.game.damageArea(point, gag.splash + 1.5, gag.damage, head=False)
        elif cog is not None and not cog.dead:
            eye = self.player.getEye()
            head = point[2] > cog.pos[2] + cog.height * 0.72
            self.game.damageCog(cog, gag.damage, head=head)

    def __splat(self, point, track):
        splat = BattleProps.globalPropPool.getProp('splat')
        splat.setColor(SPLAT_COLORS.get(track, Vec4(1, 1, 1, 1)))
        splat.reparentTo(render)
        splat.setPos(point)
        splat.setBillboardPointEye()
        splat.setScale(0.6)
        Sequence(ActorInterval(splat, 'splat'), Func(splat.cleanup), Func(splat.removeNode)).start()

    def __blast(self, gag, eye, forward):
        # A cone in front of the player; everything in it is hit.
        reach = gag.splash
        flat = Vec3(forward[0], forward[1], 0)
        flat.normalize()
        hits = 0
        for cog in list(self.game.cogs):
            if cog.dead or cog.state == 'landing':
                continue
            d = Vec3(cog.pos[0] - eye[0], cog.pos[1] - eye[1], 0)
            dist = d.length()
            if dist > reach or dist < 0.01:
                continue
            d /= dist
            if math.degrees(math.acos(max(-1.0, min(1.0, d.dot(flat))))) > CONE_HALF_ANGLE:
                continue
            if not self.game.arena.clearLine(eye, Point3(cog.pos[0], cog.pos[1], cog.pos[2] + 2)):
                continue
            damage = gag.damage
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
        scale = {'ship': 1.0, 'piano': 1.0}.get(gag.prop, 1.0)
        prop.setScale(scale)
        above = Point3(point[0], point[1], point[2] + 30)
        prop.setPos(above)
        shadow = loader.loadModel('phase_3/models/props/drop_shadow')
        shadow.reparentTo(render)
        shadow.setPos(point[0], point[1], point[2] + 0.1)
        shadow.setScale(0.1)
        shadow.setColor(0, 0, 0, 0.5)
        shadow.setTransparency(1)
        Sequence(Parallel(LerpPosInterval(prop, G.DROP_FALL, point, blendType='easeIn'),
                          LerpScaleInterval(shadow, G.DROP_FALL, gag.splash * 0.4 + 0.5)),
                 Func(self.__dropped, gag, point),
                 Wait(0.6), Func(prop.removeNode), Func(shadow.removeNode)).start()

    def __dropped(self, gag, point):
        self.game.damageArea(point, gag.splash + 1.5, gag.damage, head=True)
        self.game.hud.shake()

    # --- The bonk and the Presentation ---

    def bonk(self):
        """The melee: a whack with the held gag, which uses none of it."""
        now = globalClock.getFrameTime()
        if now < self.bonkReady or self.player.down:
            return False
        if self.arms is not None and (self.arms.lowered or self.pendingSwitch is not None):
            return False
        self.bonkReady = now + G.BONK_TIME
        def land():
            eye = self.player.getEye()
            forward = self.player.getForward()
            point, dist, cog = self.aimPoint(eye, forward, G.BONK_REACH + 8.0)
            # The reach counts from the cog's own body, not its middle (a big
            # cog's middle is far inside it): a whack lands from about as
            # far as a cog can swing at the toon.
            if cog is not None and dist - cog.radius > G.BONK_REACH:
                cog = None
            self.game.hud.bonk()
            if cog is not None:
                base.playSfx(globalBattleSoundCache.getSound(MELEE_HIT_SOUND), volume=0.8)
                self.game.damageCog(cog, G.BONK_DAMAGE, bonk=True)
            else:
                base.playSfx(globalBattleSoundCache.getSound(MELEE_MISS_SOUND), volume=0.5)
        if self.arms is not None:
            self.arms.whack(land)
        else:
            land()
        return True

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
        prop = BattleProps.globalPropPool.getProp('1dollar')
        prop.reparentTo(render)
        prop.setScale(0.6)
        start = eye + forward * 1.5
        prop.setPos(start)
        prop.setBillboardAxis()
        now = globalClock.getFrameTime()
        Sequence(LerpPosInterval(prop, 0.6, point, startPos=start, blendType='easeOut'),
                 Func(self.game.startLure, point, now + 0.6 + G.PRESENTATION_LURE),
                 Wait(G.PRESENTATION_LURE),
                 Func(self.game.damageArea, point, G.PRESENTATION_POP, G.PRESENTATION_DAMAGE, False),
                 Func(self.__splat, point, G.THROW),
                 Func(prop.removeNode)).start()
        self.game.hud.setGag(self.gag, self.current, len(self.gags))
        return True
