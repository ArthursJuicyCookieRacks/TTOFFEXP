"""The town's particle effects: the two explosions of the Toon Hall
take-over, the red haze that hangs round the Cog building afterwards, and
the spray round the fountain's foot.

The prototype used Unity's particle systems (the Detonator explosion kit
and a 2,500-particle haze). These are the same pictures on a few dozen
camera-facing cards, which a phone draws without noticing. Nothing here
runs on its own: TownLife calls update(dt) every frame.
"""

import math
import random

from panda3d.core import (BoundingSphere, CardMaker, ColorBlendAttrib, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat,
                          GeomVertexData, GeomVertexFormat, GeomVertexWriter, InternalName, NodePath, Point3, Shader,
                          TransparencyAttrib, Vec3, Vec4)

from toontown.toontropolis import TownShader

MAPS = 'phase_4/maps/toontropolis/'
# Unity units to feet.
SCALE = 2.6


def makeRoot(parent):
    """Where effects hang: drawn plainly (the town's own shader and night
    tint are not for them), after everything solid."""
    root = parent.attachNewNode('townFx')
    root.setShaderOff(100)
    root.setLightOff(100)
    root.setFogOff(100)
    root.setColorScaleOff(100)
    root.setDepthWrite(False)
    root.setBin('fixed', 30)
    return root


def card(parent, picture, tile=None, glow=True, flat=False):
    maker = CardMaker('fx')
    maker.setFrame(-0.5, 0.5, -0.5, 0.5)
    if tile is not None:
        maker.setUvRange((tile[0], 0.0), (tile[1], 1.0))
    node = parent.attachNewNode(maker.generate())
    node.setTexture(loader.loadTexture(MAPS + picture))
    node.setTwoSided(True)
    if glow:
        node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    else:
        node.setTransparency(TransparencyAttrib.MAlpha)
    if flat:
        node.setP(-90)
    else:
        node.setBillboardPointEye()
    return node


class Puff:
    """One card that moves, grows and fades."""

    def __init__(self, node, life, start, end, colour, alpha, velocity=(0, 0, 0), delay=0.0):
        self.node = node
        self.life = life
        self.start = start
        self.end = end
        self.colour = colour
        self.alpha = alpha
        self.velocity = Vec3(*velocity)
        self.age = -delay
        node.hide()

    def update(self, dt):
        self.age += dt
        if self.age < 0.0:
            return True
        if self.age >= self.life:
            self.node.removeNode()
            return False
        k = self.age / self.life
        self.node.show()
        self.node.setPos(self.node.getPos() + self.velocity * dt)
        # Fast at first, then easing out, as an explosion spreads.
        spread = 1.0 - (1.0 - k) ** 2
        self.node.setScale(max(self.start + (self.end - self.start) * spread, 0.01))
        a0, a1 = self.alpha
        self.node.setColor(self.colour[0], self.colour[1], self.colour[2], a0 + (a1 - a0) * k)
        return True


def explosion(root, pos, size=8.0 * SCALE, colour=(0.93, 0.79, 0.02), rnd=None):
    """Disney's Detonator-Wide (size 8 units, that orange): a flash, a
    shock wave along the ground, fireballs and smoke. -> the puffs."""
    rnd = rnd or random
    pos = Point3(pos)
    puffs = []
    flash = card(root, 'fx_glow.jpg')
    flash.setPos(pos + Vec3(0, 0, size * 0.3))
    puffs.append(Puff(flash, 0.5, size * 0.6, size * 4.0, (1.0, 0.75, 0.3), (1.0, 0.0)))
    wave = card(root, 'fx_shockwave.jpg', flat=True)
    wave.setPos(pos + Vec3(0, 0, 0.6))
    puffs.append(Puff(wave, 0.75, size * 0.3, size * 5.0, (1.0, 0.8, 0.45), (0.9, 0.0)))
    for k in range(8):
        ball = card(root, 'fx_fireball.png', tile=(0.0, 0.5) if k % 2 else (0.5, 1.0))
        angle = rnd.uniform(0, 2 * math.pi)
        out = rnd.uniform(0.2, 1.0) * size
        ball.setPos(pos + Vec3(math.cos(angle) * out * 0.2, math.sin(angle) * out * 0.2, size * 0.25))
        ball.setR(rnd.uniform(0, 360))
        puffs.append(Puff(ball, rnd.uniform(0.9, 1.5), size * 0.5, size * rnd.uniform(1.2, 1.9), colour, (1.0, 0.0),
                          velocity=(math.cos(angle) * out * 0.9, math.sin(angle) * out * 0.9, rnd.uniform(0.3, 1.1) * size),
                          delay=rnd.uniform(0.0, 0.12)))
    for k in range(6):
        smoke = card(root, 'fx_smoke.png', tile=(0.0, 0.5) if k % 2 else (0.5, 1.0), glow=False)
        angle = rnd.uniform(0, 2 * math.pi)
        out = rnd.uniform(0.1, 0.7) * size
        smoke.setPos(pos + Vec3(math.cos(angle) * out, math.sin(angle) * out, size * 0.4))
        puffs.append(Puff(smoke, rnd.uniform(2.6, 3.6), size * 0.7, size * rnd.uniform(1.8, 2.6), (0.22, 0.2, 0.2), (0.7, 0.0),
                          velocity=(math.cos(angle) * 2.0, math.sin(angle) * 2.0, rnd.uniform(0.5, 0.9) * size * 0.5),
                          delay=rnd.uniform(0.15, 0.5)))
    return puffs


class Haze:
    """Disney's Haze particle system: glowing dark red smoke that drifts
    down in an ellipsoid round the Cog building, each wisp living 10 to
    15 seconds and swelling as it goes."""

    # Colour and strength through a wisp's life (Disney's five keys).
    KEYS = ((43, 22, 22, 10), (73, 40, 40, 78), (88, 30, 14, 170), (43, 21, 13, 84), (26, 18, 18, 10))
    RADII = (18.97 * SCALE, 18.72 * SCALE, 5.31 * SCALE)
    COUNT = 28
    LARGEST = 30.0

    def __init__(self, root, centre, floor, rnd=None):
        self.rnd = rnd or random
        self.centre = Point3(centre)
        self.floor = floor
        self.wisps = []
        for k in range(self.COUNT):
            node = card(root, 'fx_haze.jpg')
            wisp = dict(node=node, age=0.0, life=1.0, size=1.0, fall=0.0)
            self.__spawn(wisp, wait=k * 1.6 / self.COUNT)
            self.wisps.append(wisp)

    def __spawn(self, wisp, wait=0.0):
        rnd = self.rnd
        # A point somewhere inside the ellipsoid.
        while True:
            p = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))
            if p[0] ** 2 + p[1] ** 2 + p[2] ** 2 <= 1.0:
                break
        z = max(self.centre[2] + p[2] * self.RADII[2], self.floor + 1.0)
        wisp['node'].setPos(self.centre[0] + p[0] * self.RADII[0], self.centre[1] + p[1] * self.RADII[1], z)
        wisp['node'].setR(rnd.uniform(0, 360))
        wisp['age'] = -wait
        wisp['life'] = rnd.uniform(10.0, 15.0)
        wisp['size'] = rnd.uniform(0.1, 5.0) * SCALE
        wisp['fall'] = 0.0
        wisp['node'].hide()

    def update(self, dt):
        for wisp in self.wisps:
            wisp['age'] += dt
            if wisp['age'] < 0.0:
                continue
            if wisp['age'] >= wisp['life']:
                self.__spawn(wisp)
                continue
            node = wisp['node']
            node.show()
            k = wisp['age'] / wisp['life'] * (len(self.KEYS) - 1)
            i = min(int(k), len(self.KEYS) - 2)
            f = k - i
            a, b = self.KEYS[i], self.KEYS[i + 1]
            r, g, bl, al = [(a[j] + (b[j] - a[j]) * f) / 255.0 for j in range(4)]
            # Unity's additive particles count double; fewer wisps here, so a little more each.
            node.setColor(min(r * 3.0, 1.0), min(g * 3.0, 1.0), min(bl * 3.0, 1.0), al)
            wisp['size'] = min(wisp['size'] * (1.0 + 0.86 * dt), self.LARGEST)
            node.setScale(wisp['size'])
            wisp['fall'] += 2.0 * SCALE * dt
            z = max(node.getZ() - wisp['fall'] * dt, self.floor + 1.0)
            node.setZ(z)

    def destroy(self):
        for wisp in self.wisps:
            wisp['node'].removeNode()
        self.wisps = []


# ---- The fountain's splash ----
#
# Disney's fountain has a particle emitter on the flat ring round its foot
# (MeshParticleEmitter 'splashmesh'): 400 to 1,000 particles a second, each
# at one of the ring's 126 corners, each living one second without moving,
# 0.3 to 1.5 units across, fading in and out, drawn with the water picture
# through Unity's Particles/Alpha Blended shader (twice the tint). Here all
# 700 are one piece whose corners the graphics card moves and fades itself,
# so they cost the game's own code nothing.

SPLASH_VERTEX = """
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float osg_FrameTime;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec2 seed;
varying vec2 uv;
varying float alpha;
varying float dist;
float hash(float x) { return fract(sin(x * 12.9898) * 43758.5453); }
void main(void) {
  // Each particle lives one second, then starts again at another size.
  float t = osg_FrameTime + seed.x;
  float life = floor(t);
  float age = t - life;
  float size = mix(SMALL, LARGE, hash(fract(life * 0.61803) + seed.y));
  vec4 eye = p3d_ModelViewMatrix * p3d_Vertex;
  dist = length(eye.xyz);
  // Unity draws no particle larger than a quarter of the screen.
  size = min(size, 0.5 * dist / p3d_ProjectionMatrix[1][1]);
  eye.xy += (p3d_MultiTexCoord0 - vec2(0.5)) * size;
  gl_Position = p3d_ProjectionMatrix * eye;
  uv = p3d_MultiTexCoord0;
  // Disney's five colours over the life: nearly clear, most of the way, full, most, nearly clear.
  float k = age * 4.0;
  float low = 10.0 / 255.0;
  float mid = 180.0 / 255.0;
  alpha = k < 1.0 ? mix(low, mid, k) : (k < 2.0 ? mix(mid, 1.0, k - 1.0) : (k < 3.0 ? mix(1.0, mid, k - 2.0) : mix(mid, low, k - 3.0)));
}
"""

SPLASH_FRAGMENT = """
uniform sampler2D p3d_Texture0;
uniform vec4 uTint;
uniform struct p3d_FogParameters {
  vec4 color;
  float density;
  float start;
  float end;
  float scale;
} p3d_Fog;
varying vec2 uv;
varying float alpha;
varying float dist;
void main(void) {
  vec4 t = texture2D(p3d_Texture0, uv);
  vec3 rgb = clamp(t.rgb * uTint.rgb * 2.0, 0.0, 1.0);
  float d = dist * p3d_Fog.density;
  rgb = mix(p3d_Fog.color.rgb, rgb, exp(-d * d));
  gl_FragColor = vec4(rgb, clamp(t.a * uTint.a * 2.0 * alpha, 0.0, 1.0));
}
"""


class Splash:
    COUNT = 700
    SIZE = (0.3 * SCALE, 1.5 * SCALE)
    TINT = (0.3115, 0.9, 0.7222, 0.1804)
    PICTURE = 'Water_fallback_50079.jpg'

    def __init__(self, parent, corners, rnd=None):
        """corners: where the ring's corners are, in the town's space."""
        rnd = rnd or random
        array = GeomVertexArrayFormat()
        array.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
        array.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
        array.addColumn(InternalName.make('seed'), 2, Geom.NTFloat32, Geom.COther)
        form = GeomVertexFormat()
        form.addArray(array)
        data = GeomVertexData('splash', GeomVertexFormat.registerFormat(form), Geom.UHStatic)
        data.setNumRows(self.COUNT * 4)
        vertex = GeomVertexWriter(data, 'vertex')
        texcoord = GeomVertexWriter(data, 'texcoord')
        seed = GeomVertexWriter(data, 'seed')
        triangles = GeomTriangles(Geom.UHStatic)
        for k in range(self.COUNT):
            x, y, z = rnd.choice(corners)
            phase, which = rnd.random(), rnd.random()
            for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
                vertex.addData3(x, y, z)
                texcoord.addData2(u, v)
                seed.addData2(phase, which)
            triangles.addVertices(k * 4, k * 4 + 1, k * 4 + 2)
            triangles.addVertices(k * 4, k * 4 + 2, k * 4 + 3)
        geom = Geom(data)
        geom.addPrimitive(triangles)
        node = GeomNode('fountainSplash')
        node.addGeom(geom)
        # The corners spread out on the graphics card: say how far, so the piece is not dropped while in view.
        middle = Point3(sum(c[0] for c in corners) / len(corners), sum(c[1] for c in corners) / len(corners),
                        sum(c[2] for c in corners) / len(corners))
        reach = max((Point3(*c) - middle).length() for c in corners) + self.SIZE[1]
        node.setBounds(BoundingSphere(middle, reach))
        node.setFinal(True)
        self.node = parent.attachNewNode(node)
        es = TownShader.isES()
        define = '#define SMALL %.4f\n#define LARGE %.4f\n' % self.SIZE
        self.node.setShader(Shader.make(Shader.SL_GLSL, TownShader.head(es) + define + SPLASH_VERTEX,
                                        TownShader.head(es) + SPLASH_FRAGMENT), 100)
        self.node.setShaderInput('uTint', self.TINT)
        self.node.setTexture(loader.loadTexture(MAPS + self.PICTURE), 100)
        self.node.setTransparency(TransparencyAttrib.MAlpha, 100)
        self.node.setTwoSided(True)
        self.node.setLightOff(100)
        self.node.setColorScaleOff(100)
        self.node.setDepthWrite(False)
        self.node.setBin('fixed', 29)

    def destroy(self):
        self.node.removeNode()
