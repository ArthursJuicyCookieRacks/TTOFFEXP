"""Asteroid Chicken on the screen: Disney's Toontown 2.0 prototype
minigame, rebuilt from its Unity web player.

ACSim plays the game (every one of Disney's scripts, in Unity's own
units); this draws what it says: the cockpit and its astronaut, the
pinatas and candies, eggs and rubber chickens, explosions and confetti,
the HUD, and the sounds. Nothing here decides anything about the game.

Unity (x right, y up, z forward) becomes Panda (x, z, y).
"""

import json
import math
import random

from panda3d.core import (Filename, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, GlobPattern, NodePath, PartSubset, Point3,
                          Quat, TransparencyAttrib, Vec3, VirtualFileSystem, getModelPath)

from toontown.toontropolis.UnityAnim import UAnimation

from . import ACFx, ACShader, ACSim, ACText

MODELS = 'phase_4/models/asteroidchicken/'
MAPS = 'phase_4/maps/asteroidchicken/'
SOUNDS = 'phase_4/audio/sfx/asteroidchicken/ac_%s.ogg'
PREFAB = {'donkey': 'Asteroid', 'mine': 'Asterpinata', 'star': 'StarPinata', 'hard': 'YellowHardCandy', 'lolly': 'Lolly', 'whistle': 'BlueWhistle',
          'heart': 'Jellybean', 'wrapper': 'PinkHardCandyWrapperOpen', 'chicken': 'RubberChickenB'}
SOUND_NAMES = ('flak_hit', 'anvil_miss', 'slice', 'whistle', 'tick', 'lose', 'far_explosion', 'pop', 'near_explosion', 'squawk', 'incoming', 'win')
# Unity's sounds fell off with distance (about 1 / distance); the loudest
# thing in the mix, a shot from the ship's own gun, was 7.6 units from the
# listener. Everything is turned up by the same six times, so the mix is
# Disney's and a shot is about as loud as any other trolley game's sounds.
GAIN = 6.0
MUSIC_VOLUME = 0.044 * GAIN
# The time left as whole seconds (False: every decimal, as the prototype showed it).
WHOLE_SECONDS = True
HUD_HALF = 190.0                # the GUI camera's half height
HUD_SIDE = 190.0 * 4.0 / 3.0    # half the width of the prototype's 600 x 450 window
# The HUD in Toontown's sign font (ACText), in the GUI camera's units: where the prototype's top line of text had its middle, how
# far in from the window's sides its two ends are (clear of the corner buttons and the frame rate box), and how tall the capitals are.
HUD_ROW = 156.7
HUD_INSET = 72.0
HUD_CAP = 22.0
HUD_COUNT_CAP = 18.0
HUD_OVER_CAP = 20.0
HUD_OVER_MIDDLE = 150.6         # the middle of the prototype's "Game Over!!!" picture
HUD_GAP = 12.0
HUD_BLUE = (123 / 255.0, 212 / 255.0, 1.0, 1.0)     # the blue of the prototype's "score" and "left"
_bundles = {}
_masks = {}


def readJson(path):
    vfs = VirtualFileSystem.getGlobalPtr()
    name = Filename(path)
    vfs.resolveFilename(name, getModelPath().getValue())
    return json.loads(vfs.readFile(name, True).decode('utf-8'))


def P(v):
    """A Unity point or direction in Panda's axes."""
    return (v[0], v[2], v[1])


def PQ(q):
    """A Unity rotation (w, x, y, z) in Panda's axes."""
    return Quat(q[0], -q[1], -q[3], -q[2])


class Puppet:
    """A converted character and Unity's Animation component for it."""

    def __init__(self, node):
        self.node = node
        info = json.loads(node.getTag('uchar'))
        folder = node.getTag('uchardir')
        self.bundle = node.node().getBundle(0)
        self.bundle.setFrameBlendFlag(True)
        sig = info['sig']
        if sig not in _masks:
            try:
                _masks[sig] = readJson('%s/%s.masks.json' % (folder, sig))
            except Exception:
                _masks[sig] = None
        mask = _masks[sig]
        self.ctrls = {}
        self.rate = {}
        self.frames = {}
        self.effect = {}
        clips = {}
        for clip, frames in info['clips'].items():
            key = (sig, clip)
            if key not in _bundles:
                model = loader.loadModel('%s/%s_%s.bam' % (folder, sig, clip))
                _bundles[key] = model.find('**/+AnimBundleNode').node().getBundle()
            subset = PartSubset()
            if mask is not None and clip in mask['clips']:
                driven = mask['clips'][clip]
                if not driven:
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
            control = self.bundle.bindAnim(_bundles[key], 7, subset)
            if not control:
                continue
            self.ctrls[clip] = control
            self.rate[clip] = float(info.get('rate', {}).get(clip, info.get('fps', 24)))
            self.frames[clip] = frames
            clips[clip] = (max(frames - 1, 0) / self.rate[clip], info.get('wrap', {}).get(clip, 0))
        self.length = dict((clip, value[0]) for clip, value in clips.items())
        self.anim = UAnimation(clips, awrap=info.get('awrap', 0), default=info.get('udefault'), auto=info.get('auto', False))
        self.bundle.setAnimBlendFlag(True)
        for control in self.ctrls.values():
            self.bundle.setControlEffect(control, 0.0)
        self.anim.start()
        self.update(0.0)

    def update(self, dt):
        self.anim.update(dt)
        playing = dict((clip, (u, w)) for clip, u, w in self.anim.sample())
        for clip, control in self.ctrls.items():
            state = playing.get(clip)
            if state is None:
                if self.effect.get(clip, 0.0) != 0.0:
                    self.bundle.setControlEffect(control, 0.0)
                    self.effect[clip] = 0.0
                continue
            control.pose(min(state[0] * self.rate[clip], self.frames[clip] - 1))
            if self.effect.get(clip) != state[1]:
                self.bundle.setControlEffect(control, state[1])
                self.effect[clip] = state[1]


class Label:
    """A line of the prototype's own font (Unity's TextMesh, anchored at its upper left)."""

    def __init__(self, parent, font, texture, layout):
        self.font = font
        self.layout = layout
        self.text = None
        self.node = parent.attachNewNode(GeomNode('label'))
        self.node.setTexture(texture)
        self.node.setTransparency(TransparencyAttrib.MAlpha)

    def set(self, text):
        if text == self.text:
            return
        self.text = text
        node = self.node.node()
        node.removeAllGeoms()
        chars = self.font['chars']
        x0, z0 = self.layout['pos']
        ax, ay = self.layout['ax'], self.layout['ay']
        data = GeomVertexData('label', GeomVertexFormat.getV3t2(), Geom.UHDynamic)
        vertex = GeomVertexWriter(data, 'vertex')
        texcoord = GeomVertexWriter(data, 'texcoord')
        triangles = GeomTriangles(Geom.UHDynamic)
        cursor = 0.0
        count = 0
        for ch in text:
            c = chars.get(ch)
            if c is None:
                continue
            u, v, uw, vh, gx, gy, gw, gh, advance = c
            if gw and gh:
                for cx, cy, tu, tv in ((0, 0, u, v + vh), (1, 0, u + uw, v + vh), (1, 1, u + uw, v), (0, 1, u, v)):
                    lx = (cursor + gx + gw * cx) * 0.1
                    ly = (gy + gh * cy) * 0.1
                    vertex.addData3(x0 + ax[0] * lx + ay[0] * ly, 0.0, z0 + ax[1] * lx + ay[1] * ly)
                    texcoord.addData2(tu, tv)
                triangles.addVertices(count, count + 2, count + 1)
                triangles.addVertices(count, count + 3, count + 2)
                count += 4
            cursor += advance
        if count:
            geom = Geom(data)
            geom.addPrimitive(triangles)
            node.addGeom(geom)


class Game:
    """One game of Asteroid Chicken.

    load() builds it, start() begins the countdown, update(dt) runs it (a
    task does when start() was given none of its own), destroy() puts the
    camera back. finished is set, and onFinished(won, score) called, where
    Disney's prototype reloaded itself."""

    def __init__(self, seed=None, onFinished=None, music=True, own=True, difficulty=None):
        self.seed = seed
        # The playground's settings (None: the prototype's own game, for the tests).
        self.tune = ACSim.tuning(difficulty) if difficulty is not None else None
        self.cracks = []
        self.onFinished = onFinished
        self.wantMusic = music
        self.own = own
        self.sim = None
        self.root = None
        self.finished = False
        self.keys = set()
        self.firePressed = False
        self.wobble = None
        self.saved = None
        self.music = None
        self.sfx = {}
        self.sfxNext = {}
        self.accepting = []
        self.task = None
        self.running = False
        self.pilot = None

    # ---- loading
    def load(self):
        self.info = readJson(MODELS + 'game.json')
        self.root = render.attachNewNode('asteroidChicken')
        self.root.setLightOff(100)
        self.root.setFogOff(100)
        self.root.setColorScaleOff(100)
        light = self.info['light']
        ACShader.light(self.root, light['dir'], light['color'], self.info['ambient'])

        prefabs = loader.loadModel(MODELS + 'prefabs.bam')
        ACShader.dress(prefabs)
        self.prefabs = {}
        for kind, name in list(PREFAB.items()) + [('egg', 'EggBeam')]:
            self.prefabs[kind] = prefabs.find(name)
        for name in ('lollipop2', 'lollipop3'):
            self.prefabs['lolly'].find('**/' + name).hide()

        # The ship: the pivot runs forward, the ship on it only shakes when hit.
        self.pivot = self.root.attachNewNode('shipPivot')
        self.ship = self.pivot.attachNewNode('ship')
        model = loader.loadModel(MODELS + 'ship.bam')
        ACShader.dress(model)
        self.cockpit = {}
        for name in ('CockpitLowerPlane', 'daiserCylinder', 'Windshield1', 'Windshield2', 'Astronaut', 'crosshair'):
            self.cockpit[name] = model.find(name)
            self.cockpit[name].reparentTo(self.ship)
        self.cockpit['Windshield1'].hide()
        self.cockpit['Windshield2'].hide()
        # Disney's windshield cracks twice. In the easier playgrounds it takes more: the same two cracks again.
        self.crackNames = ['Windshield1', 'Windshield2']
        for k in range(3, (self.tune['cracks'] if self.tune else ACSim.CRACKS) + 1):
            name = 'Windshield%d' % k
            self.cockpit[name] = self.cockpit['Windshield%d' % (2 - k % 2)].copyTo(self.ship)
            self.cockpit[name].setName(name)
            self.crackNames.append(name)
        # DaiserBarrel: the gun turns about its own middle to follow the crosshair.
        self.gun = self.ship.attachNewNode('gun')
        self.gun.setPos(1.19034, 16.29616, -2.46781)
        self.cockpit['daiserCylinder'].wrtReparentTo(self.gun)
        self.astronaut = Puppet(self.cockpit['Astronaut'].find('**/+Character'))
        self.chickens = {}
        # (Reads the rubber chicken's clips now, not at the first chicken shot.)
        Puppet(self.prefabs['chicken'].copyTo(NodePath('warm')).find('**/+Character'))

        sky = loader.loadModel(MODELS + 'sky.bam')
        sky.setShader(ACShader.make('ut'))
        sky.setShaderInput('uColor', (1.0, 1.0, 1.0, 1.0))
        sky.setShaderInput('uTS', (1.0, 1.0, 0.0, 0.0))
        sky.setShaderInput('uFade', 1.0)
        for name in ('uLdir', 'uLcol', 'uAmb'):
            sky.setShaderInput(name, (0.0, 0.0, 0.0))
        for name in ('uEmis', 'uSpec', 'uTint'):
            sky.setShaderInput(name, (0.0, 0.0, 0.0, 0.0))
        sky.setShaderInput('uCut', 0.0)
        sky.setScale(500.0)
        sky.setBin('background', 0)
        sky.setDepthWrite(False)
        sky.setDepthTest(False)
        sky.reparentTo(self.pivot)
        self.sky = sky

        self.fx = ACFx.Fx(self.root, random.Random(self.seed))
        self.fx.starField(self.root, (0.4776, 0.8466, 1.0, 0.502))
        gsg = base.win.getGsg() if base.win is not None else None
        self.fx.preload(gsg)
        if gsg is not None:
            prefabs.prepareScene(gsg)
            self.root.prepareScene(gsg)
        self.drift = 0.0

        self.__loadHud()
        for name in SOUND_NAMES:
            self.sfx[name] = [loader.loadSfx(SOUNDS % name) for k in range(1 if name in ('win', 'lose') else 3)]
            self.sfxNext[name] = 0
        if self.wantMusic:
            self.music = loader.loadMusic(SOUNDS % 'music')

        self.sim = ACSim.Sim(self.seed, clipLengths=self.astronaut.length, tune=self.tune)
        self.nodes = {}
        self.last = {}
        self.beams = {}
        self.__events()
        self.__place()
        self.root.hide()
        self.hud.hide()

    def __loadHud(self):
        info = self.info['hud']
        self.hud = aspect2d.attachNewNode('asteroidChickenHud')
        model = loader.loadModel(MODELS + 'hud.bam')
        ACShader.dress(model)
        self.hud.setShaderInput('uFade', 1.0)
        self.hud.setShaderInput('uLdir', (0.0, 0.0, 1.0))
        self.hud.setShaderInput('uLcol', (0.0, 0.0, 0.0))
        self.hud.setShaderInput('uAmb', (0.0, 0.0, 0.0))
        font = readJson(MODELS + 'font.json')
        texture = loader.loadTexture(MAPS + 'font.png')
        # The prototype's window was 4 : 3; on a wider screen the left things stay by the left edge and the right ones by the right.
        self.hudParts = {}
        for side, anchor, shift in (('left', base.a2dTopLeft, HUD_SIDE), ('centre', base.a2dTopCenter, 0.0), ('right', base.a2dTopRight, -HUD_SIDE)):
            holder = self.hud.attachNewNode(side)
            holder.setScale(1.0 / HUD_HALF)
            part = holder.attachNewNode('at')
            part.setPos(shift, 0.0, -HUD_HALF)
            self.hudParts[side] = (holder, anchor, part)
        self.__hudLayout()
        for name, side in (('Score', 'left'), ('EnemysLeft', 'right'), ('GameOver', 'centre')):
            node = model.find(name)
            node.reparentTo(self.hudParts[side][2])
            node.setY(0.0)
            self.hudParts[name] = node
        self.hudParts['GameOver'].hide()
        self.toonFonts = ACText.wantToonFonts()
        if self.toonFonts:
            self.__loadToonHud()
            return
        texts = info['texts']
        self.scoreText = Label(self.hudParts['left'][2], font, texture, texts['ScoreText'])
        self.timeText = Label(self.hudParts['right'][2], font, texture, texts['EnemiesLeftText'])
        self.readyText = Label(self.hudParts['centre'][2], font, texture, texts['ReadyToPlay'])
        self.countText = Label(self.hudParts['centre'][2], font, texture, texts['ReadyToPlayText'])
        self.readyText.set('Countdown')

    def __loadToonHud(self):
        """The prototype's words and numbers in Toontown's sign font, as every other trolley game writes its own: the same words in
        the same places and colours, each group measured so that the two sides sit evenly and nothing runs into anything."""
        sign = ACText.signFont()
        left, centre, right = (self.hudParts[side][2] for side in ('left', 'centre', 'right'))
        for name in ('Score', 'EnemysLeft'):
            self.hudParts[name].hide()      # the pictures of the words "score" and "left"
        base_ = HUD_ROW - HUD_CAP * 0.5
        # "Score" and the score, from the left.
        word = ACText.ToonText(left, sign, HUD_CAP, 'left', HUD_BLUE, 'Score')
        word.place(-HUD_SIDE + HUD_INSET, base_)
        self.scoreText = ACText.ToonText(left, sign, HUD_CAP, 'left')
        self.scoreText.place(-HUD_SIDE + HUD_INSET + word.width() + HUD_GAP, base_)
        # "Left" and the seconds left: as far from the right side, with the clock's three digits, as the score is from the left.
        word = ACText.ToonText(right, sign, HUD_CAP, 'left', HUD_BLUE, 'Left')
        self.timeText = ACText.ToonText(right, sign, HUD_CAP, 'left')
        digits = self.timeText.width('120')
        x = HUD_SIDE - HUD_INSET - digits - HUD_GAP - word.width()
        word.place(x, base_)
        self.timeWordX = x
        self.timeText.place(x + word.width() + HUD_GAP, base_)
        # "Countdown 3" in the middle (the digit after a fixed word, so the word does not shift as it counts), and "Game Over!!!"
        # on its two lines. __centreLayout puts them.
        self.readyText = ACText.ToonText(centre, sign, HUD_COUNT_CAP, 'left', text='Countdown')
        self.countText = ACText.ToonText(centre, sign, HUD_COUNT_CAP, 'left')
        self.overText = ACText.ToonText(centre, sign, HUD_OVER_CAP, 'centre', HUD_BLUE, 'Game\nOver!!!')
        self.overText.node.hide()
        self.centreKey = None
        self.__centreLayout()

    def __centreLayout(self):
        """The middle words sit in the top line, between the score and the clock, as they did in the prototype, wherever the window
        is wide enough for that. Where it is not (the sign font is wider than the prototype's, and the score grows), they go on a
        line of their own just beneath, so nothing ever runs into anything."""
        key = (self.scoreText.text, round(base.getAspectRatio(), 3))
        if key == self.centreKey:
            return
        self.centreKey = key
        # (The two sides slide outward with the window's width; the middle does not.)
        side = base.getAspectRatio() * HUD_HALF - HUD_SIDE
        room = 2.0 * (min(side - self.scoreText.bounds()[1], side + self.timeWordX) - HUD_GAP)
        under = HUD_ROW - HUD_CAP * 0.5 - HUD_GAP       # the top of a line beneath the top one
        wide = self.readyText.width() + HUD_GAP + self.countText.width('3')
        baseline = HUD_ROW - HUD_COUNT_CAP * 0.5 if wide <= room else under - HUD_COUNT_CAP
        self.readyText.place(-wide * 0.5, baseline)
        self.countText.place(-wide * 0.5 + self.readyText.width() + HUD_GAP, baseline)
        self.overText.centreOn(0.0, HUD_OVER_MIDDLE)
        left, right, bottom, top = self.overText.bounds()
        if right - left > room:
            self.overText.centreOn(0.0, under - (top - bottom) * 0.5)

    def __crackPlace(self, x, z):
        """Where a crack is drawn. Disney's two sit where the pinatas struck (the glass is narrow: many strike the same corner);
        with more than two, a crack that would cover an earlier one moves to the nearest clear place on the glass."""
        spots = [(x, z)] + [(min(max(x + dx, -1.3), 1.3), min(max(z + dz, -2.0), 1.8))
                            for dx, dz in ((0.9, 0.0), (-0.9, 0.0), (0.0, 0.9), (0.0, -0.9), (0.9, 0.9), (-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9),
                                           (1.8, 0.0), (-1.8, 0.0), (0.0, 1.8), (0.0, -1.8))]
        clear = lambda p: min([(p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 for c in self.cracks] or [99.0])
        best = next((p for p in spots if clear(p) >= 0.8 ** 2), None) or max(spots, key=clear)
        self.cracks.append(best)
        return best[0], 0.0, best[1]

    def __showGameOver(self):
        if self.toonFonts:
            self.overText.node.show()
        else:
            self.hudParts['GameOver'].show()

    def __hudLayout(self):
        for side in ('left', 'centre', 'right'):
            holder, anchor, part = self.hudParts[side]
            holder.setPos(anchor.getPos(aspect2d))
        if getattr(self, 'toonFonts', False):
            self.__centreLayout()

    # ---- running
    def show(self):
        """On the stage, waiting: the cockpit and the pinata field are there, the astronaut fidgets, nothing moves yet."""
        if self.saved is not None:
            return
        lens = base.camLens
        self.saved = (camera.getParent(), camera.getTransform(), lens.getMinFov(), lens.getNear(), lens.getFar(), base.getBackgroundColor())
        cam = self.info['camera']
        camera.reparentTo(self.ship)
        pos = Point3(*cam['pos'])
        camera.setPos(pos)
        camera.lookAt(pos + Vec3(*cam['fwd']), Vec3(*cam['up']))
        lens.setMinFov(cam['fov'])
        # (The prototype's near plane was 0.01; nothing is nearer the camera than the console, and 0.5 keeps far things from flickering.)
        lens.setNearFar(0.5, cam['far'])
        base.setBackgroundColor(0, 0, 0, 1)
        self.root.show()
        self.hud.show()
        self.__accept('aspectRatioChanged', self.__hudLayout)
        self.__hudLayout()
        if self.own:
            self.task = taskMgr.add(self.__task, 'asteroidChicken', sort=30)

    def start(self):
        """The countdown begins."""
        self.show()
        self.running = True
        if self.music is not None:
            self.music.setLoop(True)
            self.music.setVolume(MUSIC_VOLUME)
            self.music.play()
        for token, key in (('left', 'arrow_left'), ('right', 'arrow_right'), ('up', 'arrow_up'), ('down', 'arrow_down'),
                           ('left', 'a'), ('right', 'd'), ('up', 'w'), ('down', 's')):
            self.__accept(key, self.__key, [token, True])
            self.__accept(key + '-up', self.__key, [token, False])
        self.__accept('space', self.__fire)
        self.__accept('mouse1', self.__fire)

    def __accept(self, event, method, extra=()):
        base.accept(event, method, list(extra))
        self.accepting.append(event)

    def __key(self, token, down):
        if down:
            self.keys.add(token)
        else:
            self.keys.discard(token)

    def __fire(self):
        self.firePressed = True

    def __task(self, task):
        if self.pilot is not None:
            # A test flies the ship.
            mouse, fire = self.pilot(self)
            self.update(globalClock.getDt(), mouse, fire)
        else:
            self.update(globalClock.getDt())
        return task.cont

    def update(self, dt, mouse=None, fire=False):
        """One frame. mouse and fire: a test's own aiming, in place of the player's."""
        sim = self.sim
        if sim is None:
            return
        if mouse is None and base.mouseWatcherNode.hasMouse():
            mouse = (base.mouseWatcherNode.getMouseX(), base.mouseWatcherNode.getMouseY())
        sim.aspect = base.getAspectRatio()
        fire, self.firePressed = fire or self.firePressed, False
        if self.running and not self.finished:
            sim.update(dt, self.keys, mouse, fire)
        self.__events()
        self.__place()
        self.astronaut.update(dt)
        for puppet in self.chickens.values():
            puppet.update(dt)
        self.drift += 10.0 * dt
        self.fx.setShip(sim.shipZ, self.drift)
        self.fx.update()
        self.__hud()
        if self.wobble is not None:
            self.__shake()

    def __place(self):
        sim = self.sim
        self.pivot.setY(sim.shipZ)
        cross = P(sim.crosshair)
        self.cockpit['crosshair'].setPos(*cross)
        self.gun.lookAt(self.ship, Point3(*cross))
        last = self.last
        for b in sim.bodies:
            node = b.node
            if node is None:
                continue
            key = (b.x, b.y, b.z, b.q)
            if last.get(b.id) == key:
                continue
            last[b.id] = key
            node.setPosQuat((b.x, b.z, b.y), PQ(b.q))
        for beam in sim.beams:
            node = beam['node']
            if node is not None:
                node.setPos(beam['x'], beam['z'], beam['y'])

    def __events(self):
        sim = self.sim
        events, sim.events = sim.events, []
        self.lastEvents = events
        for event in events:
            name = event[0]
            if name == 'spawn':
                self.__spawn(event[1])
            elif name == 'gone':
                b = event[1]
                if b.node is not None:
                    b.node.removeNode()
                    b.node = None
                self.last.pop(b.id, None)
                self.chickens.pop(b.id, None)
            elif name == 'beam':
                beam = event[1]
                node = self.prefabs['egg'].copyTo(self.root)
                node.setScale(1.15)
                node.setPosQuat((beam['x'], beam['z'], beam['y']), PQ(beam['q']))
                beam['node'] = node
            elif name == 'beamGone':
                beam = event[1]
                if beam['node'] is not None:
                    beam['node'].removeNode()
                    beam['node'] = None
            elif name == 'explosion':
                pos = P(event[1])
                self.fx.explosion(pos, event[2], tiny=event[3] == 'tiny', distance=(Point3(*pos) - camera.getPos(self.root)).length())
            elif name == 'confetti':
                for kind in event[3]:
                    self.fx.confetti(P(event[1]), kind)
            elif name == 'sparkle':
                self.fx.sparkle(P(event[1]))
            elif name == 'stage':
                self.__stage(event[1])
            elif name == 'sound':
                self.__sound(event[1], event[2], event[3])
            elif name == 'astro':
                clip = event[1]
                if clip in ('gameOver', 'victoryDance'):
                    self.astronaut.anim.Play(clip)
                else:
                    self.astronaut.anim.CrossFade(clip)
            elif name == 'crack':
                node = self.cockpit['Windshield%d' % event[1]]
                node.setPos(*self.__crackPlace(event[2], event[3]))
                node.show()
            elif name == 'shipHit':
                self.wobble = [globalClock.getFrameTime(), random.uniform(-1.0, 1.0), random.uniform(0.6, 1.0)]
            elif name == 'chickenFall':
                puppet = self.chickens.get(event[1].id)
                if puppet is not None:
                    puppet.anim.Play('fall')
            elif name == 'over':
                self.__showGameOver()
            elif name == 'musicOff':
                if self.music is not None:
                    self.music.stop()
            elif name == 'shipGone':
                for part in ['CockpitLowerPlane', 'Astronaut', 'daiserCylinder', 'crosshair'] + self.crackNames:
                    self.cockpit[part].hide()
            elif name == 'finished':
                self.finished = True
                if self.onFinished is not None:
                    self.onFinished(event[1], sim.gameScore)

    def __spawn(self, b):
        node = self.prefabs[b.kind].copyTo(self.root)
        node.setScale(b.scale)
        node.setPosQuat((b.x, b.z, b.y), PQ(b.q))
        b.node = node
        if b.kind == 'chicken':
            self.chickens[b.id] = Puppet(node.find('**/+Character'))

    def __stage(self, b):
        node = b.node
        if node is None:
            return
        if b.kind == 'hard':
            node.find('**/PCANDY:wrapper').hide()
        elif b.kind == 'lolly':
            node.find('**/lollipop1').hide()
            if b.stage == 1:
                node.find('**/lollipop2').show()
            else:
                node.find('**/lollipop2').hide()
                node.find('**/lollipop3').show()

    def __sound(self, name, pos, volume):
        sounds = self.sfx.get(name)
        if not sounds:
            return
        if pos is not None:
            ear = ACSim.LISTENER
            d = math.sqrt((pos[0] - ear[0]) ** 2 + (pos[1] - ear[1]) ** 2 + (pos[2] - ear[2] - self.sim.shipZ) ** 2)
            volume = volume * min(1.0, GAIN / max(d, 0.001))
        else:
            # The tunes and the score's tick played at the HUD's own camera, 1,545 units from the listener (not heard in the prototype).
            volume = min(1.0, volume * (3.0 if name == 'tick' else 1.0))
        if volume < 0.012:
            return
        k = self.sfxNext[name]
        self.sfxNext[name] = (k + 1) % len(sounds)
        sounds[k].setVolume(volume)
        sounds[k].play()

    def __shake(self):
        """A knock on the ship: a small shake that dies away in about a second."""
        start, side, power = self.wobble
        t = globalClock.getFrameTime() - start
        if t > 1.2:
            self.wobble = None
            self.ship.setHpr(0, 0, 0)
            return
        k = math.exp(-4.0 * t) * power
        self.ship.setHpr(0.0, 2.0 * k * math.sin(t * 22.0), 1.0 * k * side * math.sin(t * 17.0))

    def __hud(self):
        sim = self.sim
        self.scoreText.set(str(sim.shownScore))
        if self.toonFonts:
            self.__centreLayout()
        # The prototype printed the raw number ("104.0007"), which ran off the edge of the screen; whole seconds fit.
        self.timeText.set(str(int(math.ceil(sim.timeLeft - 1e-6))) if WHOLE_SECONDS else sim.timeText())
        waiting = not sim.readyToPlay and not sim.gameOver
        if waiting:
            self.readyText.node.show()
            self.countText.node.show()
            self.countText.set(str(sim.countdown))
        else:
            self.readyText.node.hide()
            self.countText.node.hide()

    # ---- the end
    def destroy(self):
        if self.task is not None:
            taskMgr.remove(self.task)
            self.task = None
        for event in self.accepting:
            base.ignore(event)
        self.accepting = []
        if self.music is not None:
            self.music.stop()
            self.music = None
        for sounds in self.sfx.values():
            for sound in sounds:
                sound.stop()
        self.sfx = {}
        if self.saved is not None:
            parent, transform, fov, near, far, colour = self.saved
            camera.reparentTo(parent)
            camera.setTransform(transform)
            base.camLens.setMinFov(fov)
            base.camLens.setNearFar(near, far)
            base.setBackgroundColor(colour)
            self.saved = None
        if self.root is not None:
            self.fx.destroy()
            self.root.removeNode()
            self.root = None
            self.hud.removeNode()
        self.chickens = {}
        self.astronaut = None
        self.sim = None
