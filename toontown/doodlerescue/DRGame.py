"""Doodle Rescue on the screen: Disney's Toontown 2.0 prototype minigame
("DoodleAI", "Escape from Planet Doodle"), rebuilt from its Unity web
player.

DRSim plays the game (Disney's scripts, in Unity's own units); this draws
what it says: the Cog base and its pen, the bulb plants and spring plants,
the astronaut, the doodles and the sparkling rocket doodles, the clock and
the count of doodles saved, the sounds, and the two pictures the prototype
ended on. Nothing here decides anything about the game.

Unity (x right, y up, z forward) becomes Panda (x, z, y).
"""

import json
import math
import random
import struct

from panda3d.core import (CardMaker, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat, GeomVertexWriter, InternalName, Mat4,
                          NodePath, OmniBoundingVolume, PartSubset, Point3, Quat, SamplerState, TextureStage, TransparencyAttrib, Vec3)

from toontown.asteroidchicken import ACText
from toontown.asteroidchicken.ACGame import Puppet, readJson

from . import DRShader, DRSim

MODELS = 'phase_4/models/doodlerescue/'
MAPS = 'phase_4/maps/doodlerescue/'
SOUNDS = 'phase_4/audio/sfx/doodlerescue/dr_%s.ogg'
# The prototype's web player window was 1024 x 768, and its HUD was measured in the window's pixels.
PIXEL = 2.0 / 768.0
MUSIC_VOLUME = 0.6
POSTER_SECONDS = 2.5        # the prototype's title poster, before the clock starts (there it stayed until a click)
END_SECONDS = 6.0           # the prototype's last picture stayed until a click
# Unity's "Mouse X": a tenth of the pixels the mouse moved.
MOUSE = 0.1
# The words in Toontown's fonts (ACText), measured off the prototype's own: how tall its capitals stood in the window's pixels, and
# how far under a line's anchor its baseline lay. The count of doodles was Comic Sans bold, the Cog's lines Minnie and Comic Sans.
# (The sign font's capitals are measured with their grey rim, so the count is set a little taller, about the same middle: its
# white digits come out 34 pixels tall where Comic Sans had 39.)
SCORE_CAP = 46.0
SCORE_BASELINE = -59.5
END_FONTS = {'Minnie': (35.0, -15.0), 'comic': (22.0, -12.5)}
END_MARGIN = 60.0
CLIPS = {'doodle': ('walkHappy', 'idle', 'run'), 'rocket': ('walkHappy',), 'player': ('idle', 'walk', 'run', 'jumpCapeFly'), 'plant': ('Take_001', 'idle', 'spring', 'toonSpring')}
LOSE_LINES = (('Minnie', 0.85925, 'You Failed Toon'), ('Minnie', 0.70645, 'Now all the Doodles '), ('Minnie', 0.60404, 'Will be ground up'), ('Minnie', 0.5014, 'to make'),
              ('Minnie', 0.39912, 'Cog Cosmetics'), ('comic', 0.2895, '"They Make Cogs Alluringly Lifelike"'))
WIN_LINES = (('Minnie', 0.85925, 'You Stole My Doodles'), ('Minnie', 0.70645, 'You Stinky Toon!!!'), ('Minnie', 0.60404, 'I was going '), ('Minnie', 0.5014, 'to make'),
             ('Minnie', 0.39912, 'Cog Cosmetics'), ('comic', 0.29843, '"They Make Cog\'s Sparkle"'))
# The rocket doodle's two sparkle emitters (prefab DoodleRocket, "Sparkle Rising"): a hundred sparkles a second each, three seconds long.
SPARKLES = (
    dict(picture='Sparkles1', size=(0.5, 0.5), grow=0.0, keys=((255, 112, 0, 0), (241, 215, 221, 181), (0, 0, 0, 255), (255, 255, 255, 181), (255, 255, 255, 0))),
    dict(picture='Sparkles2', size=(0.3, 0.8), grow=0.03, keys=((255, 155, 0, 0), (241, 215, 221, 181), (110, 184, 255, 255), (243, 215, 221, 181), (255, 255, 255, 0))))
SPARKLE_RATE = 100.0
SPARKLE_LIFE = 3.0
SPARKLE_REACH = 1.0078
CHUNK = 128
CHUNKS = 3
_sparkleFormat = []


def P(v):
    """A Unity point or direction in Panda's axes."""
    return (v[0], v[2], v[1])


def PQ(q):
    """A Unity rotation (x, y, z, w) in Panda's axes."""
    return Quat(q[3], -q[0], -q[2], -q[1])


def sparkleFormat():
    if not _sparkleFormat:
        array = GeomVertexArrayFormat()
        array.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
        array.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
        array.addColumn(InternalName.make('born'), 4, Geom.NTFloat32, Geom.COther)
        array.addColumn(InternalName.make('drift'), 4, Geom.NTFloat32, Geom.COther)
        fmt = GeomVertexFormat()
        fmt.addArray(array)
        _sparkleFormat.append(GeomVertexFormat.registerFormat(fmt))
        _sparkleFormat.append(array.getStride())
    return _sparkleFormat


CORNERS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


class Trail:
    """One rocket doodle's sparkles. Each sparkle is written once, when it is born; the graphics card moves and fades it."""

    def __init__(self, parent, textures, maxSize):
        fmt, self.stride = sparkleFormat()
        self.node = parent.attachNewNode('sparkles')
        self.node.setShader(DRShader.sparkle())
        self.node.setShaderInput('uFrom', 0.0)
        DRShader.additive(self.node)
        self.node.setTwoSided(True)
        self.emitters = []
        blank = b''.join(struct.pack('<13f', 0.0, 0.0, 0.0, cx, cy, -1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) for k in range(CHUNK) for cx, cy in CORNERS)
        for which, spec in enumerate(SPARKLES):
            geomNode = GeomNode('emitter%d' % which)
            chunks = []
            for c in range(CHUNKS):
                data = GeomVertexData('sparkles', fmt, Geom.UHDynamic)
                data.setNumRows(CHUNK * 4)
                data.modifyArray(0).modifyHandle().setData(blank)
                triangles = GeomTriangles(Geom.UHStatic)
                for k in range(CHUNK):
                    triangles.addVertices(k * 4, k * 4 + 1, k * 4 + 2)
                    triangles.addVertices(k * 4, k * 4 + 2, k * 4 + 3)
                geom = Geom(data)
                geom.addPrimitive(triangles)
                geomNode.addGeom(geom)
                chunks.append(data)
            geomNode.setBounds(OmniBoundingVolume())
            geomNode.setFinal(True)
            path = self.node.attachNewNode(geomNode)
            path.setTexture(textures[which])
            keys = spec['keys']
            for k in range(5):
                path.setShaderInput('uKey%d' % k, tuple(v / 255.0 for v in keys[k]))
            path.setShaderInput('uLife', (SPARKLE_LIFE, spec['grow'], maxSize, 0.0))
            self.emitters.append(dict(spec=spec, chunks=chunks, next=0, owed=0.0))
        self.node.hide()

    def begin(self, now):
        self.node.setShaderInput('uFrom', now)
        for e in self.emitters:
            e['owed'] = 0.0
        self.node.show()

    def end(self):
        self.node.hide()

    def emit(self, now, dt, pos, velocity, rnd):
        """The sparkles born in this frame, around pos (Panda axes)."""
        for e in self.emitters:
            e['owed'] += SPARKLE_RATE * dt
            count = int(e['owed'])
            if not count:
                continue
            e['owed'] -= count
            lo, hi = e['spec']['size']
            touched = {}
            for k in range(min(count, 12)):
                while True:
                    x, y, z = rnd.uniform(-1.0, 1.0), rnd.uniform(-1.0, 1.0), rnd.uniform(-1.0, 1.0)
                    if x * x + y * y + z * z <= 1.0:
                        break
                born = now - dt * (k + rnd.random()) / count
                size = lo if lo == hi else rnd.uniform(lo, hi)
                row = (pos[0] + x * SPARKLE_REACH, pos[1] + y * SPARKLE_REACH, pos[2] + z * SPARKLE_REACH)
                tail = (born, rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), velocity[0] * 0.05, velocity[1] * 0.05, 1.0 + velocity[2] * 0.05, size)
                slot = e['next']
                e['next'] = (slot + 1) % (CHUNK * CHUNKS)
                chunk, at = divmod(slot, CHUNK)
                handle = touched.get(chunk)
                if handle is None:
                    handle = touched[chunk] = e['chunks'][chunk].modifyArray(0).modifyHandle()
                packed = b''.join(struct.pack('<13f', row[0], row[1], row[2], cx, cy, *tail) for cx, cy in CORNERS)
                handle.setSubdata(at * 4 * self.stride, len(packed), packed)


class Text:
    """A line of one of the prototype's fonts, as Unity's GUIText drew it: in window pixels, hung from one of its corners or its middle."""

    def __init__(self, parent, font, texture, anchor='upperLeft'):
        self.font = font
        self.anchor = anchor
        self.text = None
        self.node = parent.attachNewNode(GeomNode('text'))
        self.node.setTexture(texture)
        self.node.setTransparency(TransparencyAttrib.MAlpha)

    def set(self, text):
        if text == self.text:
            return
        self.text = text
        node = self.node.node()
        node.removeAllGeoms()
        chars = self.font['chars']
        pairs = self.font.get('pairs', {})
        width = 0.0
        last = None
        for ch in text:
            c = chars.get(ch)
            if c is None:
                continue
            width += c[8] + (pairs.get(last + ch, 0.0) if last else 0.0)
            last = ch
        x0 = 0.0 if self.anchor == 'upperLeft' else -width if self.anchor == 'upperRight' else -width * 0.5
        y0 = self.font['line'] * 0.5 if self.anchor == 'middle' else 0.0
        data = GeomVertexData('text', GeomVertexFormat.getV3t2(), Geom.UHDynamic)
        vertex = GeomVertexWriter(data, 'vertex')
        texcoord = GeomVertexWriter(data, 'texcoord')
        triangles = GeomTriangles(Geom.UHDynamic)
        cursor = x0
        count = 0
        last = None
        for ch in text:
            c = chars.get(ch)
            if c is None:
                continue
            u, v, uw, vh, gx, gy, gw, gh, advance = c
            if last:
                cursor += pairs.get(last + ch, 0.0)
            last = ch
            if gw and gh:
                for cx, cy, tu, tv in ((0, 0, u, v + vh), (1, 0, u + uw, v + vh), (1, 1, u + uw, v), (0, 1, u, v)):
                    vertex.addData3(cursor + gx + gw * cx, 0.0, y0 + gy + gh * cy)
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
    """One game of Doodle Rescue.

    load() builds it, show() puts it on the stage, start() shows the poster
    and then starts the clock, update(dt) runs it (a task does when the
    game was made with own=True), destroy() puts the camera back. finished
    is set, and onFinished(won, saved) called, a few seconds after the
    prototype's last picture comes up."""

    def __init__(self, seed=None, onFinished=None, music=True, own=True, controls=None, poster=True, difficulty=None):
        # How many doodles the playground asks for (None: the prototype's own 24, for the tests).
        self.need = DRSim.need(difficulty) if difficulty is not None else None
        self.seed = seed
        self.onFinished = onFinished
        self.wantMusic = music
        self.own = own
        self.controls = controls
        self.wantPoster = poster
        self.rnd = random.Random(seed)
        self.sim = None
        self.root = None
        self.hud = None
        self.finished = False
        self.keys = set()
        self.saved = None
        self.music = None
        self.villain = None
        self.sfx = {}
        self.sfxNext = {}
        self.accepting = []
        self.task = None
        self.phase = 'wait'
        self.phaseTime = 0.0
        self.clock = 0.0
        self.pilot = None
        self.lastMouse = None
        self.lastEvents = []

    # ---- loading
    def load(self):
        info = self.info = readJson(MODELS + 'game.json')
        self.fonts = readJson(MODELS + 'fonts.json')
        self.root = render.attachNewNode('doodleRescue')
        self.root.setLightOff(100)
        self.root.setFogOff(100)
        self.root.setColorScaleOff(100)
        light = info['light']
        DRShader.light(self.root, light['dir'], light['color'], info['ambient'], info['fog']['density'])

        arena = loader.loadModel(MODELS + 'arena.bam')
        DRShader.dress(arena)
        arena.reparentTo(self.root)
        self.arena = arena
        ground = arena.find('**/ground')
        g = info['ground']
        control = loader.loadTexture(g['control'])
        control.setWrapU(SamplerState.WM_clamp)
        control.setWrapV(SamplerState.WM_clamp)
        ground.setTexture(control)
        ground.setShader(DRShader.make('ground'))
        for k, name in enumerate(g['splats']):
            splat = loader.loadTexture(name)
            splat.setWrapU(SamplerState.WM_repeat)
            splat.setWrapV(SamplerState.WM_repeat)
            splat.setMinfilter(SamplerState.FT_linear_mipmap_linear)
            splat.setAnisotropicDegree(4)
            ground.setShaderInput('uS%d' % k, splat)
        ground.setShaderInput('uTile', tuple(g['size'][0] / tile[0] for tile in g['tiles']))

        sky = loader.loadModel(MODELS + 'sky.bam')
        sky.setShader(DRShader.make('ut'))
        sky.setShaderInput('uFog', 0.0)
        sky.setScale(800.0)
        sky.setBin('background', 0)
        sky.setDepthWrite(False)
        sky.setDepthTest(False)
        sky.reparentTo(self.root)
        self.sky = sky

        # The characters: one of each, copied as they are needed.
        chars = loader.loadModel(MODELS + 'chars.bam')
        DRShader.dress(chars)
        self.proto = {}
        for name, clips in CLIPS.items():
            holder = chars.find(name)
            char = holder.find('**/+Character')
            data = json.loads(char.getTag('uchar'))
            data['clips'] = dict((clip, frames) for clip, frames in data['clips'].items() if clip in clips)
            char.setTag('uchar', json.dumps(data))
            self.proto[name] = holder
        self.actors = self.root.attachNewNode('actors')

        # The pen: its two closing clips are posed straight from the game's own wall clock.
        pen = chars.find('pen')
        pen.reparentTo(self.root)
        self.pen = pen
        bundle = pen.find('**/+Character').node().getBundle(0)
        bundle.setFrameBlendFlag(True)
        self.penCtrl = {}
        sig = info['pen']['sig']
        for clip in info['pen']['clips']:
            model = loader.loadModel('%sanim/%s_%s.bam' % (MODELS, sig, clip))
            self.penCtrl[clip] = bundle.bindAnim(model.find('**/+AnimBundleNode').node().getBundle(), 7, PartSubset())
        self.penAt = None

        self.sim = DRSim.Sim(info, seed=self.seed, need=self.need)

        # Spring plants.
        self.plants = []
        for pad in info['pads']:
            node = self.proto['plant'].copyTo(self.actors)
            m = pad['plantMat']
            node.setMat(Mat4(*m))
            puppet = Puppet(node.find('**/+Character'))
            self.plants.append(puppet)

        # The astronaut.
        p = info['player']
        self.playerNode = self.proto['player'].copyTo(self.actors)
        self.playerNode.setScale(p['scale'])
        self.player = Puppet(self.playerNode.find('**/+Character'))
        self.player.anim.set_wrap(2)
        self.player.anim.Stop()
        self.player.anim.Play('idle')
        self.playerAnim = 'idle'

        # Doodles, rocket doodles and their sparkles.
        self.doodles = {}
        self.spare = []
        self.rockets = {}
        self.spareRockets = []
        self.spareTrails = []
        self.sparkTextures = []
        for spec in SPARKLES:
            texture = loader.loadTexture(info['fx'][spec['picture']]['file'])
            texture.setWrapU(SamplerState.WM_clamp)
            texture.setWrapV(SamplerState.WM_clamp)
            self.sparkTextures.append(texture)
        self.fx = self.root.attachNewNode('sparkles')
        self.fx.setShaderInput('uTime', 0.0)
        self.maxSparkle = 0.25 * 2.0 * math.tan(math.radians(info['camera']['fov']) * 0.5)
        for d in self.sim.doodles:
            self.__doodle(d)
        for k in range(6):
            self.spareRockets.append(self.__newRocket())
            self.spareTrails.append(Trail(self.fx, self.sparkTextures, self.maxSparkle))

        self.__loadHud()
        for name, copies in (('gears', 2), ('bong', 4)):
            self.sfx[name] = [loader.loadSfx(SOUNDS % name) for k in range(copies)]
            self.sfxNext[name] = 0
        if self.wantMusic:
            self.music = loader.loadMusic(SOUNDS % 'music')
            self.villain = loader.loadMusic(SOUNDS % 'villain')

        gsg = base.win.getGsg() if base.win is not None else None
        if gsg is not None:
            self.root.prepareScene(gsg)
        self.__place(0.0)
        self.root.hide()
        self.hud.hide()

    def __doodle(self, d):
        if self.spare:
            node, puppet = self.spare.pop()
            node.show()
        else:
            node = self.proto['doodle'].copyTo(self.actors)
            puppet = Puppet(node.find('**/+Character'))
        puppet.anim.Play(d.anim)
        self.doodles[d.id] = [node, puppet, None, d.anim]

    def __newRocket(self):
        node = self.proto['rocket'].copyTo(self.actors)
        node.setScale(DRSim.R_SCALE)
        puppet = Puppet(node.find('**/+Character'))
        node.hide()
        return [node, puppet]

    def __loadHud(self):
        info = self.info['hud']
        self.hud = aspect2d.attachNewNode('doodleRescueHud')
        self.hud.setBin('fixed', 20)
        fontTextures = {}
        for name, font in self.fonts.items():
            fontTextures[name] = loader.loadTexture(font['texture'])
            fontTextures[name].setMinfilter(SamplerState.FT_linear)
        self.fontTextures = fontTextures

        def picture(parent, name, x, y, w, h):
            cm = CardMaker(name)
            cm.setFrame(0.0, w, -h, 0.0)
            node = parent.attachNewNode(cm.generate())
            texture = loader.loadTexture(info[name]['file'])
            texture.setWrapU(SamplerState.WM_clamp)
            texture.setWrapV(SamplerState.WM_clamp)
            node.setTexture(texture)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setPos(x, 0.0, -y)
            return node

        # clockScript.OnGUI: the bar's back at (20, 20), its fill at (10, 12) inside that, cut off at the share of the time that is left.
        # (Here 24 lower, clear of the chat buttons Toontown keeps in that corner.)
        self.hudLeft = self.hud.attachNewNode('left')
        self.hudLeft.setScale(PIXEL)
        picture(self.hudLeft, 'clockBG', 20, 44, 256, 64)
        self.clockFill = picture(self.hudLeft, 'clockFG', 30, 56, 256, 32)
        self.fillShown = None
        # The count of doodles saved: its upper right corner 8.2% of the window in from the right edge, 3.8% down.
        self.hudRight = self.hud.attachNewNode('right')
        self.hudRight.setScale(PIXEL)
        self.toonFonts = ACText.wantToonFonts()
        x, y = -(1.0 - 0.9181) * 1024.0, -(1.0 - 0.9624) * 768.0
        if self.toonFonts:
            # In Toontown's sign font, as the other trolley games write their counts: the same height, its right end and baseline where they were.
            self.scoreText = ACText.ToonText(self.hudRight, ACText.signFont(), SCORE_CAP, 'right')
            self.scoreText.place(x, y + SCORE_BASELINE)
        else:
            self.scoreText = Text(self.hudRight, self.fonts['comicbd'], fontTextures['comicbd'], 'upperRight')
            self.scoreText.node.setPos(x, 0.0, y)
        self.scoreX = x
        self.scoreText.set('Save the Doodles!!!')
        # CameraController.OnGUI: the little mark by the middle of the window.
        self.hudCentre = self.hud.attachNewNode('centre')
        self.hudCentre.setScale(PIXEL)
        picture(self.hudCentre, 'center', -32, -20, 16, 10)

        # The poster the prototype opened on, and the picture it ended on.
        self.cards = aspect2d.attachNewNode('doodleRescueCards')
        self.cards.setBin('fixed', 30)
        cm = CardMaker('black')
        cm.setFrame(-4.0, 4.0, -1.0, 1.0)
        self.black = self.cards.attachNewNode(cm.generate())
        self.black.setColor(0, 0, 0, 1)
        self.black.setTransparency(TransparencyAttrib.MAlpha)
        cm = CardMaker('poster')
        cm.setFrame(-1.0, 1.0, -1.0, 1.0)
        self.poster = self.cards.attachNewNode(cm.generate())
        self.poster.setTexture(loader.loadTexture(info['EscapeHero']['file']))
        self.poster.setTransparency(TransparencyAttrib.MAlpha)
        # The Cog's portrait stood on a block that filled the window, lit warm and dim (level2 and level3 of the prototype).
        cm = CardMaker('cog')
        cm.setFrame(-1.0, 1.0, -1.0, 1.0)
        self.cog = self.cards.attachNewNode(cm.generate())
        self.cog.setTexture(loader.loadTexture(info['cogFace1']['file']))
        self.cog.setR(90.0)
        self.cog.setScale(1.6, 1.0, 1.725)
        self.cog.setPos(0.0, 0.0, -0.2)
        self.cog.setColor(1.0, 0.69, 0.62, 1.0)
        self.endLines = self.cards.attachNewNode('lines')
        self.endLines.setScale(PIXEL)
        self.cards.hide()

    def __hudLayout(self):
        self.hudLeft.setPos(base.a2dTopLeft.getPos(aspect2d))
        self.hudRight.setPos(base.a2dTopRight.getPos(aspect2d))
        if self.toonFonts:
            # The opening words stop short of the clock bar (276 pixels in from the left) however narrow the window is.
            self.scoreText.fit(base.getAspectRatio() * 768.0 + self.scoreX - 276.0 - 40.0)
        # The Cog's block filled the prototype's 4 : 3 window with room to spare; on a wider screen it is made to fill that too.
        wide = max(1.0, base.getAspectRatio() / 1.7)
        self.cog.setScale(1.6 * wide, 1.0, 1.725 * wide)

    # ---- running
    def show(self):
        """On the stage, waiting: the pen, the plants and the doodles are there; nothing moves yet."""
        if self.saved is not None:
            return
        lens = base.camLens
        self.saved = (camera.getParent(), camera.getTransform(), lens.getMinFov(), lens.getNear(), lens.getFar(), base.getBackgroundColor())
        cam = self.info['camera']
        camera.reparentTo(self.root)
        lens.setMinFov(cam['fov'])
        lens.setNearFar(cam['near'], cam['far'])
        base.setBackgroundColor(0, 0, 0, 1)
        self.root.show()
        self.hud.show()
        self.__accept('aspectRatioChanged', self.__hudLayout)
        self.__hudLayout()
        self.__place(0.0)
        if self.own:
            self.task = taskMgr.add(self.__task, 'doodleRescue', sort=30)

    def start(self):
        """The poster, then the clock starts."""
        self.show()
        if self.music is not None:
            self.music.setLoop(True)
            self.music.setVolume(MUSIC_VOLUME)
            self.music.play()
        if self.controls is None:
            for token, key in (('left', 'arrow_left'), ('right', 'arrow_right'), ('up', 'arrow_up'), ('down', 'arrow_down'),
                               ('left', 'a'), ('right', 'd'), ('up', 'w'), ('down', 's'), ('jump', 'space'), ('look', 'mouse3')):
                self.__accept(key, self.__key, [token, True])
                self.__accept(key + '-up', self.__key, [token, False])
        else:
            self.__accept('mouse3', self.__key, ['look', True])
            self.__accept('mouse3-up', self.__key, ['look', False])
        if self.wantPoster:
            self.phase = 'poster'
            self.phaseTime = 0.0
            self.cards.show()
            self.cog.hide()
            self.endLines.hide()
            self.poster.show()
            self.black.show()
        else:
            self.phase = 'play'

    def __accept(self, event, method, extra=()):
        base.accept(event, method, list(extra))
        self.accepting.append(event)

    def __key(self, token, down):
        if down:
            self.keys.add(token)
        else:
            self.keys.discard(token)

    def __task(self, task):
        self.update(globalClock.getDt())
        return task.cont

    def __input(self):
        """What the player holds: (left, right, up, down, jump, mouse)."""
        if self.pilot is not None:
            # A test plays.
            held = self.pilot(self)
            return (held.get('left', False), held.get('right', False), held.get('up', False), held.get('down', False), held.get('jump', False), held.get('mouse', (0.0, 0.0)))
        mouse = (0.0, 0.0)
        # The prototype turned the toon and the camera with every move of the mouse; here, while the right mouse button is held.
        watcher = base.mouseWatcherNode
        if 'look' in self.keys and watcher.hasMouse():
            now = (watcher.getMouseX() * base.win.getXSize() * 0.5, watcher.getMouseY() * base.win.getYSize() * 0.5)
            if self.lastMouse is not None:
                mouse = ((now[0] - self.lastMouse[0]) * MOUSE, (now[1] - self.lastMouse[1]) * MOUSE)
            self.lastMouse = now
        else:
            self.lastMouse = None
        c = self.controls
        if c is not None:
            return (c.leftPressed(), c.rightPressed(), c.upPressed(), c.downPressed(), c.jumpPressed(), mouse)
        k = self.keys
        return ('left' in k, 'right' in k, 'up' in k, 'down' in k, 'jump' in k, mouse)

    def update(self, dt):
        """One frame."""
        sim = self.sim
        if sim is None:
            return
        self.phaseTime += dt
        self.lastEvents = []
        if self.phase == 'poster':
            left = POSTER_SECONDS - self.phaseTime
            if left <= 0.0:
                self.cards.hide()
                self.phase = 'play'
            elif left < 0.5:
                self.poster.setAlphaScale(left / 0.5)
                self.black.setAlphaScale(left / 0.5)
        elif self.phase == 'play':
            left, right, up, down, jump, mouse = self.__input()
            sim.update(dt, left, right, up, down, jump, mouse)
            self.lastEvents = list(sim.events)
            self.clock += dt
            self.__events()
        elif self.phase == 'end' and self.phaseTime >= END_SECONDS and not self.finished:
            self.finished = True
            if self.onFinished is not None:
                self.onFinished(sim.state == 'won', sim.score)
        self.__place(dt)
        self.__hud()

    def __events(self):
        sim = self.sim
        for event in sim.events:
            name = event[0]
            if name == 'padAnim':
                self.plants[event[1]].anim.Play(event[2])
            elif name == 'launch':
                entry = self.doodles.pop(event[2], None)
                if entry is not None:
                    entry[0].hide()
                    self.spare.append((entry[0], entry[1]))
                node, puppet = self.spareRockets.pop() if self.spareRockets else self.__newRocket()
                trail = self.spareTrails.pop() if self.spareTrails else Trail(self.fx, self.sparkTextures, self.maxSparkle)
                trail.begin(self.clock)
                puppet.anim.Play('walkHappy')
                node.show()
                self.rockets[event[3]] = [node, puppet, trail]
                pad = sim.pads[event[1]]['pos']
                self.__sound('bong', pad)
            elif name in ('saved', 'reform'):
                entry = self.rockets.pop(event[1], None)
                if entry is not None:
                    # Rocket.Kill: the doodle and its sparkles are gone at once.
                    entry[0].hide()
                    entry[2].end()
                    self.spareRockets.append(entry[:2])
                    self.spareTrails.append(entry[2])
                if name == 'reform':
                    for d in sim.doodles:
                        if d.id == event[2]:
                            self.__doodle(d)
            elif name == 'gone':
                entry = self.doodles.pop(event[1], None)
                if entry is not None:
                    entry[0].hide()
                    self.spare.append((entry[0], entry[1]))
            elif name == 'gears':
                self.__sound('gears', None)
            elif name == 'timeUp':
                self.__villain()
            elif name in ('won', 'lost'):
                self.__end(name == 'won')

    def __villain(self):
        if self.music is not None and self.villain is not None and self.villain.status() != self.villain.PLAYING:
            self.music.stop()
            self.villain.setLoop(True)
            self.villain.setVolume(MUSIC_VOLUME)
            self.villain.play()

    def __end(self, won):
        """The prototype's last picture: the Cog, and what it has to say."""
        self.__villain()
        self.phase = 'end'
        self.phaseTime = 0.0
        self.hud.hide()
        self.cards.show()
        self.black.setAlphaScale(1.0)
        self.black.show()
        self.poster.hide()
        self.cog.show()
        self.endLines.show()
        for font, y, words in (WIN_LINES if won else LOSE_LINES):
            if self.toonFonts:
                # The Cog's lines in Toontown's Minnie font and its slogan in the interface font, each centred on the window.
                cap, baseline = END_FONTS[font]
                line = ACText.ToonText(self.endLines, ACText.sharp(ACText.minnieFont() if font == 'Minnie' else ACText.interfaceFont()), cap, 'centre', text=words.strip())
                line.place(0.0, (y - 0.5) * 768.0 + baseline)
                line.fit(base.getAspectRatio() * 768.0 - 2.0 * END_MARGIN)
                continue
            line = Text(self.endLines, self.fonts[font], self.fontTextures[font], 'middle')
            line.node.setPos(0.0, 0.0, (y - 0.5) * 768.0)
            line.set(words)

    def __sound(self, name, pos):
        sounds = self.sfx.get(name)
        if not sounds:
            return
        volume = 1.0
        if pos is not None:
            # Unity's sounds fell off with distance, about as 1 / distance past the first few units.
            ear = self.sim.camPos
            d = math.sqrt((pos[0] - ear[0]) ** 2 + (pos[1] - ear[1]) ** 2 + (pos[2] - ear[2]) ** 2)
            volume = min(1.0, 10.0 / max(d, 0.001))
            if volume < 0.05:
                return
        k = self.sfxNext[name]
        self.sfxNext[name] = (k + 1) % len(sounds)
        sounds[k].setVolume(volume)
        sounds[k].play()

    def __place(self, dt):
        sim = self.sim
        # camera, sky
        pos = P(sim.camPos)
        if self.saved is not None:
            camera.setPosQuat(self.root, pos, PQ(sim.camQ))
        self.sky.setPos(*pos)
        # the pen
        at = (sim.wallClip, sim.wallFrame)
        if at != self.penAt:
            self.penAt = at
            self.penCtrl[at[0]].pose(at[1])
        # the astronaut
        self.playerNode.setPos(sim.px, sim.pz, sim.py)
        self.playerNode.setH(-sim.yaw)
        clip = {'jump': 'jumpCapeFly'}.get(sim.panim, sim.panim)
        self.player.anim.CrossFade(clip)
        self.player.update(dt)
        for puppet in self.plants:
            puppet.update(dt)
        # doodles
        doodles = self.doodles
        for d in sim.doodles:
            entry = doodles.get(d.id)
            if entry is None:
                continue
            node, puppet = entry[0], entry[1]
            key = (d.x, d.y, d.z, d.fx, d.fy, d.fz)
            if key != entry[2]:
                entry[2] = key
                node.setPos(d.x, d.z, d.y)
                node.lookAt(d.x + d.fx, d.z + d.fz, d.y + d.fy)
            puppet.anim.CrossFade(d.anim)
            puppet.update(dt)
        # rocket doodles and their sparkles
        self.fx.setShaderInput('uTime', self.clock)
        for r in sim.rockets:
            entry = self.rockets.get(r.id)
            if entry is None:
                continue
            node, puppet, trail = entry
            o = r.origin()
            node.setPosQuat((o[0], o[2], o[1]), PQ(r.q))
            puppet.update(dt)
            if dt > 0.0:
                trail.emit(self.clock, dt, (o[0], o[2], o[1]), (r.vx, r.vz, r.vy), self.rnd)

    def __hud(self):
        sim = self.sim
        share = max(0.0, min(1.0, sim.percent / 100.0))
        if share != self.fillShown:
            self.fillShown = share
            if share <= 0.0:
                self.clockFill.hide()
            else:
                self.clockFill.show()
                self.clockFill.setSx(share)
                self.clockFill.setTexScale(TextureStage.getDefault(), share, 1.0)
        if self.phase != 'wait' and self.phase != 'poster':
            self.scoreText.set(str(sim.score))

    # ---- the end
    def destroy(self):
        if self.task is not None:
            taskMgr.remove(self.task)
            self.task = None
        for event in self.accepting:
            base.ignore(event)
        self.accepting = []
        for tune in (self.music, self.villain):
            if tune is not None:
                tune.stop()
        self.music = self.villain = None
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
            self.root.removeNode()
            self.root = None
            self.hud.removeNode()
            self.cards.removeNode()
        self.doodles = {}
        self.rockets = {}
        self.spare = []
        self.spareRockets = []
        self.spareTrails = []
        self.plants = []
        self.player = None
        self.sim = None
