"""What moves in Toontropolis, and what answers when a toon walks up to it.

Every living thing in the town model is one of Disney's own characters
with its own clips: the shops that sway, look around and fall asleep, the
hydrants, mailboxes and trash cans, the owl, the fountain, the Cog Pinata.
Which clip plays when is decided by Disney's scripts, ported line for line
in Behaviours.py and ShopControl.py on top of UnityAnim.py (Unity's
Animation component). This class binds the clips, runs the scripts and
poses the characters every frame; it also carries the prototype's
triggers: the horn and the anvil by the Gag Shop, the cymbals and the
piano keys of the music shop, and the power switch that turns day into
night and sends the shops to sleep. The smaller things Disney scripted by
hand (Gimmicks.py) are moved from here too: the power building's
pinwheels, the four light bulbs that sputter on at night, the lamp glows
that ride the bulbs and the bubbles the sleeping Gag Shop snores out of
its chimney.
"""

import json
import math
import random

from panda3d.core import (Filename, GlobPattern, LMatrix4, LVecBase3,
                          PandaNode, PartSubset, Point3, TransformState,
                          Vec3, Vec4, VirtualFileSystem, getModelPath)

from toontown.toontropolis import Behaviours, Gimmicks, TownFx
from toontown.toontropolis.Behaviours import Actor, Bouncing, CogPinata, Pet, Shop
from toontown.toontropolis.Town import MODELS, SCALE

SFX = 'phase_4/audio/sfx/toontropolis/%s.ogg'
PINATA = 'tt_a_ara_ttc_cogPinata'
TOON_HALL = 'ToonHall'
COG_BUILDING = 'CogBuildingAnim'
GAG_SHOP = 'tt_a_ara_ttc_gagShop'
MUSIC_SHOP = 'tt_a_ara_ttc_musicShop'
# The power switch puts these to sleep and wakes them (Disney's six, and the
# three shops built from Disney's sketches, which live the same way).
SLEEPERS = ('t2_r_ara_ttp_powerBuilding', 'tt_a_ara_ttc_petshop', 'tt_a_ara_ttc_clothesShop', GAG_SHOP, PINATA, MUSIC_SHOP,
            'oodles_alive', 'kaboomery_alive', 'potf_alive')
# What a script asks to hear: (Disney's clip, volume). Unity never plays
# louder than 1, whatever the AudioSource says (the horn is set to 10).
SOUNDS = {
    'honk': ('m_match_trumpet', 1.0),
    'anvil': ('AA_drop_anvil_miss', 0.5),
    'cymbal1': ('SZ_MM_cymbal', 1.0),
    'cymbal2': ('AA_drop_anvil_miss', 1.0),
    'cymbal3': ('monkey_exclaim_c', 1.0),
    'cymbal4': ('monkey_short_a', 1.0),
    'cymbal5': ('m_match_guitar_1', 1.0),
}
# Disney's trigger boxes that do something here.
TRIGGERS = ('HonkHornTrigger', 'AnvilDropTrigger', 'Cymbal1Trigger', 'Cymbal2Trigger', 'Cymbal3Trigger', 'Cymbal4Trigger', 'Cymbal5Trigger',
            'ToonHall', 'PowerSwitch')
# Every AudioSource in the scene has Unity's roll-off factor 0.1.
ROLLOFF = 0.1
# A toon's body, for stepping into Disney's trigger boxes (the prototype's
# player was 0.31 units round).
BODY = 0.31 * SCALE
# How far a toon walks on one piano key before its next step sounds again.
STRIDE = 2.4
# Characters further away than this are posed every other frame, and every
# fourth frame from twice as far: nobody can tell, and a phone has less to do.
NEAR = 220.0


def readJson(path):
    vfs = VirtualFileSystem.getGlobalPtr()
    name = Filename(path)
    vfs.resolveFilename(name, getModelPath().getValue())
    return json.loads(vfs.readFile(name, True).decode('utf-8'))


def pingPong(t, length):
    """Unity's Mathf.PingPong."""
    u = t % (2.0 * length)
    return u if u <= length else 2.0 * length - u


class Thing:
    """One character of the town."""

    def __init__(self, node, info):
        self.node = node
        self.name = node.getName()
        self.info = info
        self.bundle = node.node().getBundle(0)
        self.ctrls = {}
        self.rate = {}
        self.frames = {}
        self.length = {}
        self.actor = None
        self.clip = None
        self.offset = 0.0
        self.effect = {}
        self.gos = json.loads(node.getTag('ugos')) if node.hasTag('ugos') else []
        self.centre = Point3(0, 0, 0)
        self.radius = 10.0


class PetWorld:
    """Where the plaza's doodle stands, for Disney's pet scripts (Unity
    units, z up; headings clockwise from +y)."""

    def __init__(self, life, thing):
        self.life = life
        self.thing = thing
        self.node = thing.node
        self.root = life.town.root
        self.baseH = self.node.getH(self.root)
        self.steps = 0
        self.floor = None
        # How far the doodle's own middle sits above the floor.
        self.lift = None

    def pos(self):
        p = self.node.getPos(self.root)
        return (p[0] / SCALE, p[1] / SCALE, p[2] / SCALE)

    def setHeading(self, degrees):
        self.node.setH(self.root, self.baseH - degrees)

    def owner(self):
        if self.life.ownerAt is None:
            return None
        found = self.life.ownerAt()
        if found is None:
            return None
        p, speed = found
        return ((p[0] / SCALE, p[1] / SCALE, p[2] / SCALE), speed / SCALE)

    def move(self, dx, dy):
        life = self.life
        if life.openAt is None:
            return
        p = self.node.getPos(self.root)
        # Blocked straight ahead, it slides along whatever is in the way.
        for ax, ay in ((dx, dy), (dx, 0.0), (0.0, dy)):
            x, y = p[0] + ax * SCALE, p[1] + ay * SCALE
            if not life.openAt(x, y, p[2]):
                continue
            z = p[2]
            if life.groundAt is not None:
                # The floor costs a ray: a few times a second, eased between.
                if self.floor is None or self.steps % 6 == 0:
                    self.floor = life.groundAt(x, y, p[2] + 3.0)
                    if self.lift is None and self.floor is not None:
                        self.lift = min(max(p[2] - self.floor, -1.0), 2.0)
                self.steps += 1
                if self.floor is not None:
                    z += (self.floor + self.lift - z) * 0.35
            self.node.setPos(self.root, x, y, z)
            self.thing.centre = Point3(x, y, z)
            return

    def jump(self, x, y, z, anywhere=False):
        """Disney's heel: the doodle is put down by its owner (a spot it
        can stand on, at the owner's height; with anywhere, any spot that
        has a floor). -> whether it went."""
        life = self.life
        x, y, z = x * SCALE, y * SCALE, z * SCALE
        if life.openAt is None or not (anywhere or life.openAt(x, y, z)):
            return False
        floor = life.groundAt(x, y, z + 6.0) if life.groundAt is not None else None
        if floor is None:
            return False
        if self.lift is None:
            p = self.node.getPos(self.root)
            under = life.groundAt(p[0], p[1], p[2] + 3.0)
            self.lift = 0.0 if under is None else min(max(p[2] - under, -1.0), 2.0)
        z = floor + self.lift
        self.node.setPos(self.root, x, y, z)
        self.thing.centre = Point3(x, y, z)
        self.floor = None
        return True


class TownLife:

    def __init__(self, town, seed=11):
        self.town = town
        self.meta = readJson(MODELS + 'town.json')
        self.table = readJson(MODELS + 'behaviour.json')
        self.seed = seed
        self.rnd = random.Random(seed)
        self.t = 0.0
        self.frame = 0
        self.things = []
        self.byName = {}
        self.sounds = {}
        self.procs = []
        self.floatNodes = {}
        self.inside = {}
        self.keyUnder = {}
        self.listener = Point3(0, 0, 0)
        # Called with no arguments when a toon flips the power switch.
        self.onPower = None
        self.powerArmed = True
        # ground(x, y, z) -> the height of the floor under a point of the
        # town (the map sets it; the bubbles land on it).
        self.groundAt = None
        # open(x, y, z) -> whether a toon could stand there; owner() -> the
        # player's place in the town and speed in feet a second (the map
        # sets both; the plaza's doodle walks by them).
        self.openAt = None
        self.ownerAt = None
        self.pet = None
        self.mute = False
        # The Toon Hall take-over: onCog(k) is called for each of the five
        # Cogs that come out (four Flunkies, then the Big Cheese), and
        # onTakeover() when the Cogs' music would start.
        self.onCog = None
        self.onLanded = None
        self.onTakeover = None
        self.takenOver = False
        # hallTrigger: whether a toon walking up to Toon Hall sets the
        # take-over off, as in Disney's plaza (Survival starts it itself,
        # with its Gag-Snatcher rounds). onOpen() is called when the
        # landed building's first Cog would come out. restore() gives
        # Toon Hall back, and then it can be taken again.
        self.hallTrigger = True
        self.onOpen = None
        self.takeovers = 0
        self.later = []
        self.puffs = []
        self.haze = None
        self.fxRoot = None
        self.laterCount = 0
        Behaviours.WORLD['fear'] = False
        self.__bind()
        self.__behave()
        self.__effects()
        self.__triggers()
        self.__gimmicks()

    # --- Binding Disney's clips ---

    def __bind(self):
        bundles = {}
        masks = {}
        for node in self.town.chars.findAllMatches('**/+Character'):
            if not node.hasTag('uchar'):
                continue
            info = json.loads(node.getTag('uchar'))
            folder = node.getTag('uchardir')
            thing = Thing(node, info)
            thing.bundle.setFrameBlendFlag(True)
            sig = info['sig']
            if sig not in masks:
                try:
                    masks[sig] = readJson('%s/%s.masks.json' % (folder, sig))
                except Exception:
                    masks[sig] = None
            mask = masks[sig]
            thing.mask = mask
            floatOnly = []
            for clip in info['clips']:
                key = (sig, clip)
                if key not in bundles:
                    model = loader.loadModel('%s/%s_%s.bam' % (folder, sig, clip))
                    bundles[key] = model.find('**/+AnimBundleNode').node().getBundle()
                # A clip only drives the joints Unity stored curves for; the
                # others stay with the other clips (a horn honk over a sway).
                subset = PartSubset()
                if mask is not None and clip in mask['clips']:
                    driven = mask['clips'][clip]
                    if not driven:
                        floatOnly.append(clip)
                        continue
                    if len(driven) < len(mask['joints']) - 1:
                        included = [False] * len(mask['joints'])
                        for i, joint in enumerate(mask['joints']):
                            included[i] = joint in driven
                            parent = included[mask['parent'][i]] if mask['parent'][i] >= 0 else False
                            if included[i] and not parent:
                                subset.addIncludeJoint(GlobPattern(joint))
                            elif parent and not included[i]:
                                subset.addExcludeJoint(GlobPattern(joint))
                control = thing.bundle.bindAnim(bundles[key], 7, subset)
                if control:
                    thing.ctrls[clip] = control
            fps = float(info.get('fps', 24))
            rates = info.get('rate', {})
            for clip in list(thing.ctrls) + floatOnly:
                thing.rate[clip] = float(rates.get(clip, fps))
                thing.frames[clip] = info['clips'][clip]
                thing.length[clip] = max(thing.frames[clip] - 1, 0) / thing.rate[clip]
            # A thing with no script loops one clip (the doodles in the pet
            # shop's pen each have their own).
            pick = [node.getTag('uclip') if node.hasTag('uclip') else None, 'idle0', 'idle', 'Idle', 'bankidle', 'Take_001']
            thing.clip = next((c for c in pick if c in thing.ctrls), None)
            if thing.clip is None and not node.hasTag('uclip') and info.get('auto') and info.get('udefault') in thing.ctrls:
                thing.clip = info['udefault']
            thing.offset = self.rnd.random() * 10.0
            bounds = node.getTightBounds(self.town.root)
            if bounds is not None:
                thing.centre = Point3((bounds[0] + bounds[1]) * 0.5)
                thing.radius = (bounds[1] - bounds[0]).length() * 0.5
            if node.hasTag('uhidden'):
                # Waits out of sight until the game calls for it (the Cog
                # building that drops on Toon Hall).
                node.hide()
            self.things.append(thing)
            self.byName.setdefault(thing.name, []).append(thing)

    def __behave(self):
        """Disney's scripts on every character that has one. A script is
        matched to its character by the Unity object it sat on (there are
        fourteen trash cans, each with its own)."""
        table = self.table
        shops = {x['on']: x for x in table['things'] if 'idle' in x}
        fix = lambda clip: clip.replace(' ', '_')
        for k, thing in enumerate(self.things):
            node = thing.node
            info = thing.info
            clips = {c: (thing.length[c], info.get('wrap', {}).get(c, 0)) for c in thing.length}
            source = node.getTag('ubehave') if node.hasTag('ubehave') else thing.name
            scripts = []
            if source in shops:
                row = shops[source]
                idle = [dict(a, anim=fix(a['anim'])) for a in row['idle']]
                sleep = [dict(a, anim=fix(a['anim'])) for a in row['sleep']]
                if any(a['anim'] not in thing.ctrls for a in idle + sleep):
                    continue
                scripts.append(('Shop', dict(idle=idle, sleep=sleep, cls=row['cls'])))
            else:
                for row in table.get('scripts', []):
                    if row['cls'] not in Behaviours.SCRIPTS or not row.get('active', 1) or row.get('go') not in thing.gos:
                        continue
                    scripts.append((row['cls'], {key: (fix(value['name']) if isinstance(value, dict) and value.get('name') else value)
                                                 for key, value in row.items()}))
                if thing.name == PINATA:
                    scripts.append(('CPN_CogPinataControl', {}))
                if thing.name == COG_BUILDING:
                    scripts.append(('cogdoAanim', {}))
                if thing.name == 'TT_pets' and thing.gos:
                    # The doodle that lives on the plaza.
                    scripts.append(('PetControlsMulti', {}))
                if not scripts and not (info.get('auto') and info.get('udefault') in thing.length):
                    continue
                if thing.name == 'TT_pets' and not thing.gos:
                    continue
            thing.actor = Actor(clips, info.get('awrap', 0), info.get('udefault'), bool(info.get('auto')), scripts, seed=self.seed + k)
            for script in thing.actor.scripts:
                if hasattr(script, 'emit'):
                    script.emit = (lambda name, thing=thing: self.__emit(name, thing))
                if isinstance(script, Pet):
                    self.pet = script
                    script.world = PetWorld(self, thing)
            thing.bundle.setAnimBlendFlag(True)
            for control in thing.ctrls.values():
                thing.bundle.setControlEffect(control, 0.0)

    # --- Things Disney's scripts move by hand ---

    def __effects(self):
        root = self.town.root
        # LookAt: the lamp glows and the moon turn to face whoever looks.
        self.lookers = [n for n in self.town.dyn.getChildren() if n.getTag('tdyn') == 'lookat']
        self.switch = next((n for n in self.town.dyn.getChildren() if n.getTag('tdyn') == 'pivot'), None)
        # coloranim and UVScroller: the fountain's water flickers between
        # two colours and its two bursts scroll their texture.
        self.colours = []
        self.scrollers = []
        for row in self.table.get('scripts', []):
            if row['cls'] not in ('coloranim', 'UVScroller') or not row.get('enabled', 1) or not row.get('active', 1):
                continue
            for thing in self.things:
                if row.get('go') not in thing.gos:
                    continue
                for node in thing.node.findAllMatches('**/%s.0' % row['on']):
                    if row['cls'] == 'coloranim':
                        self.colours.append((node, Vec4(*row['colorStart']), Vec4(*row['colorEnd']), row['duration']))
                    else:
                        self.scrollers.append((node, row['scrollSpeed']))
        # bouncing: the fountain's two water jets, four joints each.
        k = 0
        for row in self.table.get('scripts', []):
            if row['cls'] != 'bouncing' or not row.get('enabled', 1):
                continue
            k += 1
            ids = [row['joint%d' % q]['pid'] for q in (1, 2, 3, 4)]
            for thing in self.things:
                if thing.mask is None or not all(i in thing.gos for i in ids):
                    continue
                nodes = []
                rest = []
                for i in ids:
                    joint = thing.mask['joints'][thing.gos.index(i)]
                    part = thing.bundle.findChild(joint)
                    mat = LMatrix4(part.getDefaultValue())
                    node = PandaNode('proc_' + joint)
                    thing.bundle.controlJoint(joint, node)
                    nodes.append((node, mat))
                    # Panda (x, z up) to Unity (x, y up).
                    rest.append((mat.getCell(3, 0), mat.getCell(3, 2), mat.getCell(3, 1)))
                self.procs.append((Bouncing(row, rest, random.Random(self.seed * 31 + k)), nodes, thing))

    def __gimmicks(self):
        root = self.town.root
        # The spray round the fountain's foot.
        self.splash = None
        corners = self.meta.get('splash')
        if corners:
            self.splash = TownFx.Splash(root, corners, random.Random(self.seed + 5))
        power = next((t for t in self.byName.get('t2_r_ara_ttp_powerBuilding', ())), None)
        # The eight pinwheels: Disney's script turns their joints itself.
        self.pinwheels = None
        self.pinNodes = []
        if power is not None:
            for k in range(len(Gimmicks.PINWHEELS)):
                joint = 'pwr:def_pinwheel_%d' % (k + 1)
                if power.bundle.findChild(joint) is None:
                    self.pinNodes = []
                    break
                node = PandaNode('proc_' + joint)
                power.bundle.controlJoint(joint, node)
                self.pinNodes.append(node)
            if self.pinNodes:
                self.pinwheels = Gimmicks.Pinwheels(random.Random(self.seed * 7 + 1))
        # The four light bulbs.
        self.bulbs = Gimmicks.Bulbs(random.Random(self.seed * 7 + 2))
        self.bulbLevels = None
        # The glows on the power building's bulbs ride the bulbs' joints
        # (and turn to the camera with the street lamps' glows).
        for node in list(self.town.dyn.getChildren()):
            joint = node.getTag('tjoint')
            if not joint:
                continue
            for thing in self.things:
                part = thing.bundle.findChild(joint)
                if part is None:
                    continue
                thing.node.node().forceUpdate()
                holder = thing.node.attachNewNode(PandaNode('ride_' + joint))
                part.addNetTransform(holder.node())
                node.wrtReparentTo(holder)
                break
        # The Gag Shop's chimney and the bubble Disney's scene keeps as the
        # one to copy.
        self.bubbles = None
        self.bubbleNodes = {}
        self.bubbleModel = self.town.dyn.find('Sphere')
        gag = next((t for t in self.byName.get(GAG_SHOP, ()) if t.actor is not None), None)
        if not self.bubbleModel.isEmpty():
            self.bubbleModel.hide()
            part = gag.bundle.findChild('gagS:def_chimney_A4') if gag is not None and 'sleepSnore2' in gag.actor.a else None
            if part is not None:
                gag.node.node().forceUpdate()
                self.chimney = gag.node.attachNewNode(PandaNode('ride_chimney'))
                part.addNetTransform(self.chimney.node())
                self.bubbleRoot = root.attachNewNode('bubbles')
                self.bubbles = Gimmicks.Bubbles(random.Random(self.seed * 7 + 3))

    def __triggers(self):
        self.boxes = {}
        for row in self.meta.get('triggers', []):
            if row['name'] in TRIGGERS:
                self.boxes[row['name']] = (Point3(*row['lo']), Point3(*row['hi']))
        self.keys = []
        for row in self.meta.get('keys', []):
            tris = [[Point3(*p) for p in tri] for tri in row['tris']]
            if not tris:
                continue
            xs = [p[0] for tri in tris for p in tri]
            ys = [p[1] for tri in tris for p in tri]
            centre = Point3(sum(xs) / len(xs), sum(ys) / len(ys), sum(p[2] for tri in tris for p in tri) / (3.0 * len(tris)))
            self.keys.append((row['name'], row.get('note'), tris, (min(xs), min(ys), max(xs), max(ys)), centre))

    # --- Every frame ---

    def update(self, dt, eye=None, forward=None):
        """Run the scripts and pose what can be seen. eye and forward are
        the camera's place and direction in the town's own space."""
        self.t += dt
        self.frame += 1
        t = self.t
        if eye is not None:
            self.listener = Point3(eye)
        for bounce, nodes, thing in self.procs:
            for (node, mat), (x, y, z) in zip(nodes, bounce.sample(t)):
                moved = LMatrix4(mat)
                moved.setRow(3, LVecBase3(x, z, y))
                node.setTransform(TransformState.makeMat(moved))
        self.__runGimmicks(dt)
        while self.later and self.later[0][0] <= t:
            self.later.pop(0)[2]()
        if self.puffs:
            self.puffs = [puff for puff in self.puffs if puff.update(dt)]
        if self.haze is not None:
            self.haze.update(dt)
        for k, thing in enumerate(self.things):
            actor = thing.actor
            now = actor.sample(t) if actor is not None else None
            if thing.node.isHidden():
                continue
            if eye is not None:
                away = thing.centre - eye
                distance = away.length()
                if forward is not None and distance > thing.radius + 20.0 and away.dot(forward) < -thing.radius:
                    continue
                if distance > NEAR + thing.radius and (self.frame + k) % (4 if distance > 2 * NEAR + thing.radius else 2):
                    continue
            if actor is None:
                control = thing.ctrls.get(thing.clip)
                if control is not None:
                    control.pose(((t + thing.offset) * thing.rate[thing.clip]) % max(thing.frames[thing.clip] - 1, 1))
                continue
            playing = {clip: (u, w) for clip, u, w in now}
            effect = thing.effect
            for clip, control in thing.ctrls.items():
                state = playing.get(clip)
                if state is None:
                    if effect.get(clip, 0.0) != 0.0:
                        thing.bundle.setControlEffect(control, 0.0)
                        effect[clip] = 0.0
                    continue
                control.pose(min(state[0] * thing.rate[clip], thing.frames[clip] - 1))
                if effect.get(clip) != state[1]:
                    thing.bundle.setControlEffect(control, state[1])
                    effect[clip] = state[1]
            if thing.info.get('floats'):
                for clip, (u, w) in playing.items():
                    if w >= 1e-3:
                        self.__floats(thing, clip, u)
        if eye is not None:
            for node in self.lookers:
                if not node.isHidden():
                    node.lookAt(self.town.root, eye)
        for node, start, end, duration in self.colours:
            k = pingPong(globalClock.getFrameTime(), duration) / duration
            node.setShaderInput('uTint', start + (end - start) * k)
        for node, speed in self.scrollers:
            offset = t * speed
            node.setShaderInput('uTS', (1.0, 1.0, offset / 10.0, offset))

    def __runGimmicks(self, dt):
        if self.pinwheels is not None:
            self.pinwheels.update(dt)
            for node, angle in zip(self.pinNodes, self.pinwheels.angle):
                # Unity turns about x the other way round.
                node.setTransform(TransformState.makeHpr(LVecBase3(0.0, -angle, 0.0)))
        self.bulbs.update(dt, self.__bulbSound)
        levels = self.bulbs.levels()
        if levels != self.bulbLevels:
            self.bulbLevels = levels
            self.town.setBulbs(levels)
        if self.bubbles is not None:
            gag = self.actor(GAG_SHOP)
            state = gag.a['sleepSnore2']
            snore = (state.time / state.length, state.length) if state.enabled and state.length > 0 else None
            self.bubbles.update(dt, not gag.script(Shop).awake, snore, self.__chimney, self.__ground,
                                self.__bubbleNew, self.__bubblePop, self.__bubbleGone)
            for bubble, node in self.bubbleNodes.items():
                if bubble.popped is None:
                    node.setPos(bubble.pos[0] * SCALE, bubble.pos[1] * SCALE, bubble.pos[2] * SCALE)
                    node.setScale(bubble.scale / Gimmicks.Bubble.START_SCALE)

    def __bulbSound(self, index, sound):
        # Disney's bulbs are heard at half volume wherever the listener is,
        # an octave up.
        self.play(sound, 0.5, rate=2.0)

    def __chimney(self):
        return self.chimney.getPos(self.town.root) / SCALE

    def __ground(self, x, y, z):
        if self.groundAt is None:
            return None
        floor = self.groundAt(x * SCALE, y * SCALE, z * SCALE)
        return None if floor is None else floor / SCALE

    def __bubbleNew(self, bubble):
        node = self.bubbleModel.copyTo(self.bubbleRoot)
        node.show()
        self.bubbleNodes[bubble] = node

    def __bubblePop(self, bubble):
        node = self.bubbleNodes.get(bubble)
        if node is not None:
            node.hide()
        # Disney's pop was set to be heard at full volume all over town; a
        # string of bubbles pops every few seconds all night, so here it
        # fades with distance like every other sound of the town.
        self.play('GUI_balloon_popup', 1.0, Point3(bubble.pos[0] * SCALE, bubble.pos[1] * SCALE, bubble.pos[2] * SCALE))

    def __bubbleGone(self, bubble):
        node = self.bubbleNodes.pop(bubble, None)
        if node is not None:
            node.removeNode()

    def __floats(self, thing, clip, u):
        """A clip's material curves (the owl's glasses scroll their
        texture)."""
        for curve in thing.info['floats'].get(clip, []):
            keys = curve['keys']
            if not keys or curve.get('attribute') not in ('_MainTex.offset.x', '_MainTex.offset.y'):
                continue
            i = max(j for j in range(len(keys)) if keys[j][0] <= u + 1e-9) if u >= keys[0][0] else 0
            if i >= len(keys) - 1:
                value = keys[-1][1]
            else:
                (t0, v0, _, o0), (t1, v1, i1, _) = keys[i], keys[i + 1]
                h = t1 - t0
                x = (u - t0) / h
                value = ((2 * x ** 3 - 3 * x ** 2 + 1) * v0 + (x ** 3 - 2 * x ** 2 + x) * h * o0
                         + (-2 * x ** 3 + 3 * x ** 2) * v1 + (x ** 3 - x ** 2) * h * i1)
            key = (id(thing), curve['path'])
            if key not in self.floatNodes:
                last = curve['path'].split('/')[-1]
                self.floatNodes[key] = [g for g in thing.node.findAllMatches('**/+GeomNode') if g.getName() == last + '.0']
            for node in self.floatNodes[key]:
                scale = [float(v) for v in node.getTag('tts').split()] if node.hasTag('tts') else [1.0, 1.0, 0.0, 0.0]
                scale[2 if curve['attribute'].endswith('x') else 3] = value
                node.setShaderInput('uTS', tuple(scale))

    # --- Messages (Unity's BroadcastMessage) ---

    def actor(self, name):
        for thing in self.byName.get(name, ()):
            if thing.actor is not None:
                return thing.actor
        return None

    def send(self, name, message, *args):
        for thing in self.byName.get(name, ()):
            if thing.actor is not None:
                thing.actor.send(message, *args)

    def settle(self, seconds):
        """Let the town live for a while before anybody sees it."""
        self.t += seconds
        for thing in self.things:
            if thing.actor is not None:
                thing.actor.sample(self.t)
        self.mute = True
        if self.pinwheels is not None:
            self.pinwheels.update(seconds)
        self.bulbs.update(seconds, self.__bulbSound)
        self.mute = False

    def toggleSleepWake(self):
        """What the power switch does to the shops (BuildingAnimStart)."""
        for name in SLEEPERS:
            self.send(name, 'ToggleSleepWake')
        if self.switch is not None:
            self.switch.setH(self.switch, 180)
        if self.pinwheels is not None:
            self.pinwheels.toggleSleepWake()
        self.bulbs.toggleSleepWake()

    # --- The Cogs take Toon Hall (triggerCogBuilding) ---

    def after(self, seconds, call):
        self.laterCount += 1
        self.later.append((self.t + seconds, self.laterCount, call))
        self.later.sort(key=lambda entry: entry[:2])

    def takeover(self):
        """A toon walked into the plaza's far side: a moment later a Cog
        building drops on Toon Hall, two explosions go off, a red haze
        rises, the Bank and the Library cower, and when the building has
        landed five Cogs come out, a second apart."""
        if self.takenOver:
            return
        hall = self.actor(TOON_HALL)
        if hall is None:
            return
        self.takenOver = True
        self.takeovers += 1
        self.__then(2.25, self.__drop)

    def __then(self, seconds, call):
        """after(), for the steps of a take-over: one that Toon Hall was won back from before the step came up is dropped."""
        serial = self.takeovers
        self.after(seconds, lambda: call() if self.takenOver and serial == self.takeovers else None)

    def restore(self):
        """The toons have Toon Hall back: the Cog building goes in two
        puffs of smoke, the haze clears, Toon Hall idles again and the
        Bank and the Library calm down. -> whether there was anything
        to give back."""
        if not self.takenOver:
            return False
        self.takenOver = False
        hall = self.actor(TOON_HALL)
        if hall is not None:
            hall.send('restore')
        shown = False
        for thing in self.byName.get(COG_BUILDING, ()):
            shown = shown or not thing.node.isHidden()
            thing.node.hide()
            if thing.actor is not None:
                thing.actor.send('Leave')
        if shown:
            places = self.meta.get('places', {})
            where = Point3(*places['CogBuildingLoc']) if 'CogBuildingLoc' in places else None
            self.play('FarExplosionA', 1.0, where, rolloff=0.007)
            self.__bomb('BombA')
            self.__bomb('BombB')
        if self.haze is not None:
            self.haze.destroy()
            self.haze = None
        Behaviours.WORLD['fear'] = False
        return True

    def __drop(self):
        hall = self.actor(TOON_HALL)
        hall.send('takeover')
        landing = hall.a['drop'].length if 'drop' in hall.a else 8.5
        for thing in self.byName.get(COG_BUILDING, ()):
            thing.node.show()
            if thing.actor is not None:
                thing.actor.send('Begin')
        places = self.meta.get('places', {})
        if self.fxRoot is None:
            self.fxRoot = TownFx.makeRoot(self.town.root)
        where = Point3(*places['CogBuildingLoc']) if 'CogBuildingLoc' in places else None
        # Disney's bomb sound barely fades with distance.
        self.__then(2.2, lambda: self.play('FarExplosionA', 1.0, where, rolloff=0.007))
        self.__then(2.2, lambda: self.onLanded() if self.onLanded is not None else None)
        self.__then(2.3, lambda: self.__bomb('BombA'))
        self.__then(2.4, lambda: self.__bomb('BombB'))
        self.__then(2.5, self.__haze)
        self.__then(2.6, self.__fear)
        self.__then(2.6 + landing, lambda: self.onOpen() if self.onOpen is not None else None)
        for k in range(5):
            self.__then(2.6 + landing + k, lambda k=k: self.onCog(k) if self.onCog is not None else None)

    def __floor(self, spot):
        floor = self.groundAt(spot[0], spot[1], spot[2] + 30.0) if self.groundAt is not None else None
        return spot[2] if floor is None else floor

    def __bomb(self, name):
        spot = self.meta.get('places', {}).get(name)
        if spot is None:
            return
        self.puffs += TownFx.explosion(self.fxRoot, Point3(spot[0], spot[1], self.__floor(spot)), rnd=self.rnd)

    def __haze(self):
        spot = self.meta.get('places', {}).get('Haze')
        if spot is not None and self.haze is None:
            floor = self.__floor(spot)
            self.haze = TownFx.Haze(self.fxRoot, Point3(spot[0], spot[1], floor + TownFx.Haze.RADII[2] * 0.5), floor, rnd=self.rnd)

    def __fear(self):
        Behaviours.WORLD['fear'] = True
        if self.onTakeover is not None:
            self.onTakeover()

    # --- Sounds ---

    def __emit(self, name, thing):
        if name in SOUNDS:
            clip, volume = SOUNDS[name]
            self.play(clip, volume, thing.centre)

    def play(self, clip, volume, where=None, rate=1.0, rolloff=ROLLOFF):
        if self.mute:
            return
        sound = self.sounds.get(clip)
        if sound is None:
            sound = self.sounds[clip] = loader.loadSfx(SFX % clip)
        if not sound:
            return
        if where is not None:
            # Unity's logarithmic roll-off, least distance 1 unit.
            distance = (where - self.listener).length() / SCALE
            volume *= 1.0 / (1.0 + rolloff * max(distance - 1.0, 0.0))
        sound.setVolume(min(volume, 1.0))
        sound.setPlayRate(rate)
        sound.play()

    # --- Toons walking about ---

    def walkers(self, spots):
        """Where the toons' feet are this frame (the player first), in the
        town's own space: whoever steps into one of Disney's trigger boxes
        sets it off, and a step on a piano key plays its note."""
        for k, feet in enumerate(spots):
            for name, (lo, hi) in self.boxes.items():
                if name == 'PowerSwitch' or (name == 'ToonHall' and k):
                    # The switch is below; only the player sets off Toon Hall.
                    continue
                key = (k, name)
                inside = (lo[0] - BODY <= feet[0] <= hi[0] + BODY and lo[1] - BODY <= feet[1] <= hi[1] + BODY
                          and lo[2] - 5.0 <= feet[2] <= hi[2] + 1.0)
                if inside and not self.inside.get(key):
                    self.__enter(name)
                self.inside[key] = inside
            self.__piano(k, feet)
        if spots and 'PowerSwitch' in self.boxes:
            # Only the player's own body flips the switch (Disney's
            # PlayerCollisions), once per touch.
            lo, hi = self.boxes['PowerSwitch']
            feet = spots[0]
            reach = BODY + 1.0
            touching = (lo[0] - reach <= feet[0] <= hi[0] + reach and lo[1] - reach <= feet[1] <= hi[1] + reach
                        and lo[2] - 6.0 <= feet[2] <= hi[2] + 1.0)
            if touching and self.powerArmed:
                self.powerArmed = False
                if self.onPower is not None:
                    self.onPower()
            elif not touching:
                far = 4.0
                if not (lo[0] - far <= feet[0] <= hi[0] + far and lo[1] - far <= feet[1] <= hi[1] + far):
                    self.powerArmed = True

    def __enter(self, name):
        gagShop = self.actor(GAG_SHOP)
        pinata = self.actor(PINATA)
        if name == 'HonkHornTrigger' and gagShop is not None:
            shop = gagShop.script(Shop)
            if not gagShop.a['anvilDrop'].enabled and not gagShop.a['honkHorn1'].enabled and shop.awake:
                gagShop.send('HonkHorn')
                if pinata is not None:
                    pinata.send('HonkHorn')
        elif name == 'AnvilDropTrigger' and gagShop is not None:
            shop = gagShop.script(Shop)
            if not gagShop.a['anvilDrop'].enabled and not gagShop.a['honkHorn1'].enabled and shop.awake:
                if pinata is None or (not pinata.a['anvilDrop3'].enabled and not pinata.a['honkHorn'].enabled):
                    gagShop.send('AnvilDrop')
                    if pinata is not None:
                        pinata.send('AnvilDrop')
        elif name == 'ToonHall':
            if self.hallTrigger:
                self.takeover()
        elif name.startswith('Cymbal') and name.endswith('Trigger'):
            self.send(MUSIC_SHOP, 'PlayCymbal', int(name[6]))

    def __piano(self, k, feet):
        found = None
        for name, note, tris, (x0, y0, x1, y1), centre in self.keys:
            if not (x0 <= feet[0] <= x1 and y0 <= feet[1] <= y1):
                continue
            for a, b, c in tris:
                d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(d) < 1e-9:
                    continue
                w0 = ((b[1] - c[1]) * (feet[0] - c[0]) + (c[0] - b[0]) * (feet[1] - c[1])) / d
                w1 = ((c[1] - a[1]) * (feet[0] - c[0]) + (a[0] - c[0]) * (feet[1] - c[1])) / d
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = w0 * a[2] + w1 * b[2] + w2 * c[2]
                if abs(feet[2] - z) < 1.0 and (found is None or z > found[0]):
                    found = (z, name, note, centre)
        last = self.keyUnder.get(k)
        if found is None:
            self.keyUnder[k] = None
            return
        z, name, note, centre = found
        if last is None or last[0] != name:
            self.keyUnder[k] = [name, Point3(feet)]
        elif (Point3(feet) - last[1]).length() >= STRIDE:
            last[1] = Point3(feet)
        else:
            return
        if note:
            self.play(note, 1.0, centre)

    def destroy(self):
        for sound in self.sounds.values():
            if sound:
                sound.stop()
        self.sounds = {}
        self.things = []
        self.byName = {}
        self.procs = []
        self.onPower = None
        self.groundAt = None
        self.openAt = None
        self.ownerAt = None
        self.pet = None
        self.onCog = None
        self.onTakeover = None
        self.later = []
        self.puffs = []
        if self.haze is not None:
            self.haze.destroy()
            self.haze = None
        if getattr(self, 'splash', None) is not None:
            self.splash.destroy()
            self.splash = None
        Behaviours.WORLD['fear'] = False
        self.bubbleNodes = {}
        self.pinNodes = []
