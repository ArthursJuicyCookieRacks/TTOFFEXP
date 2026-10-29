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
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpPosInterval, LerpScaleInterval, Parallel,
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
    G.SOUND: ('sound', 36, 40, 84, RIGHT),
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
FIT_TRACKS = (G.DROP, G.LURE)
FIT_PROPS = ('squirting-flower', 'stormcloud', 'geyser', 'firehose')
ARMS_H = 14
# Battle offsets for props that do not sit square in the hand.
PROP_IN_HAND = {'water-gun': (Point3(0.28, 0.1, 0.08), (85.6, -4.44, 94.43))}
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
        self.toon.reparentTo(camera)
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
        self.track.start()

    def destroy(self):
        if self.arms is not None:
            self.arms.destroy()
            self.arms = None
        if self.track:
            self.track.finish()
            self.track = None
        self.toon.delete()


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
        self.showHeld()

    def destroy(self):
        self.__clearView()
        for item in self.flying:
            item['np'].removeNode()
        self.flying = []
        if self.reloading:
            taskMgr.remove(self.reloading)
            self.reloading = None

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
                megaphone = BattleProps.globalPropPool.getProp('megaphone')
                megaphone.reparentTo(self.arms.hand(RIGHT))
                megaphone.setScale(MEGAPHONE_SCALE / self.arms.grow)
                extras.append(megaphone)
                prop.reparentTo(self.arms.hand(RIGHT))
                pos, hpr = INSTRUMENT_IN_MEGAPHONE
                prop.setPosHpr(pos * MEGAPHONE_SCALE / self.arms.grow, Vec3(*hpr))
                prop.setScale(INSTRUMENT_SCALE.get(gag.prop, 0.5) * MEGAPHONE_SCALE / self.arms.grow)
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
                if gag.track == G.THROW or self.arms.anim == 'throw':
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
        gag = self.gag
        if gag is None or gag.upgraded:
            return False
        gag.upgrade()
        self.showHeld()
        return True

    def maxGags(self):
        for gag in self.gags:
            gag.maxOut()
        self.presentations = min(self.presentations + 1, 2) if self.presentations else self.presentations
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

    # --- Firing ---

    def fire(self, held=False):
        gag = self.gag
        now = globalClock.getFrameTime()
        if gag is None or self.reloading or now < self.nextShot or self.player.down:
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
        now = globalClock.getFrameTime()
        if now < self.bonkReady or self.player.down:
            return False
        self.bonkReady = now + G.BONK_TIME
        eye = self.player.getEye()
        forward = self.player.getForward()
        point, dist, cog = self.aimPoint(eye, forward, G.BONK_REACH)
        self.game.hud.bonk()
        base.playSfx(globalBattleSoundCache.getSound('AA_heal_tickle.ogg'), volume=0.3)
        if cog is not None:
            self.game.damageCog(cog, G.BONK_DAMAGE, bonk=True)
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
