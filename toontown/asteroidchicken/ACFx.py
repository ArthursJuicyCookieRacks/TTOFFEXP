"""Asteroid Chicken's particles: the Detonator explosions, the confetti a
burst pinata throws, the sparkle of an unwrapped candy and the star field.

The prototype used Unity's particle systems. Here each burst is one small
model whose corners carry where the particle starts, how fast it goes, how
big it is and how long it lives; the graphics card works out the rest
(Unity's damping, force, growth and five colours over the life), so a
burst costs the game's own code nothing after it is made.
All in the game's own space: Unity units, Panda's axes (Unity x, z, y).
"""

import math
import random

from panda3d.core import (BoundingSphere, ColorBlendAttrib, Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, InternalName, OmniBoundingVolume, Point3, Shader, TransparencyAttrib)

from toontown.toontropolis.TownShader import head, isES

MAPS = 'phase_4/maps/asteroidchicken/'

VERTEX = """
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float osg_FrameTime;
uniform float uStart;
uniform vec4 uPhys;
uniform vec3 uForce;
uniform vec4 uKey0;
uniform vec4 uKey1;
uniform vec4 uKey2;
uniform vec4 uKey3;
uniform vec4 uKey4;
uniform vec4 uUV;
uniform float uStretch;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec3 vel;
attribute vec4 par;
varying vec2 uv;
varying vec4 col;
void main(void) {
  float t = osg_FrameTime - uStart - par.z;
  float life = par.y;
  uv = uUV.xy + p3d_MultiTexCoord0 * uUV.zw;
  if (t < 0.0 || t >= life) {
    gl_Position = vec4(0.0, 0.0, -2.0, 1.0);
    col = vec4(0.0);
    return;
  }
  float k = uPhys.x;
  vec3 p;
  vec3 v;
  if (k < -0.0001) {
    float e = exp(k * t);
    p = p3d_Vertex.xyz + (vel + uForce / k) * ((e - 1.0) / k) - uForce * (t / k);
    v = (vel + uForce / k) * e - uForce / k;
  } else {
    p = p3d_Vertex.xyz + vel * t + uForce * (0.5 * t * t);
    v = vel + uForce * t;
  }
  float size = par.x;
  if (uPhys.y < 0.5) size *= exp(uPhys.z * t);
  else size *= 1.0 + 9.0 * (1.0 - 1.0 / (1.0 + 3.0 * t));
  vec4 eye = p3d_ModelViewMatrix * vec4(p, 1.0);
  float dist = length(eye.xyz);
  size = min(size, uPhys.w * 2.0 * dist / p3d_ProjectionMatrix[1][1]);
  vec2 c = p3d_MultiTexCoord0 - vec2(0.5);
  if (uStretch > 0.0) {
    vec2 d = (p3d_ModelViewMatrix * vec4(v, 0.0)).xy;
    d = d / max(length(d), 0.0001);
    eye.xy += d * (c.y * size * uStretch) + vec2(-d.y, d.x) * (c.x * size);
  } else {
    float a = par.w * (1.0 + t);
    float sn = sin(a);
    float cs = cos(a);
    eye.xy += vec2(c.x * cs - c.y * sn, c.x * sn + c.y * cs) * size;
  }
  gl_Position = p3d_ProjectionMatrix * eye;
  float q = t / life * 4.0;
  col = q < 1.0 ? mix(uKey0, uKey1, q) : (q < 2.0 ? mix(uKey1, uKey2, q - 1.0) : (q < 3.0 ? mix(uKey2, uKey3, q - 2.0) : mix(uKey3, uKey4, q - 3.0)));
}
"""

FRAGMENT = """
uniform sampler2D p3d_Texture0;
uniform vec4 uTint;
uniform vec2 uMode;
varying vec2 uv;
varying vec4 col;
void main(void) {
  vec4 t = texture2D(p3d_Texture0, uv);
  vec4 c;
  if (uMode.x > 0.5) c = vec4(t.rgb * uTint.rgb, t.a * step(0.001, col.a));
  else c = clamp(t * col * uTint * 2.0, 0.0, 1.0);
  if (c.a <= uMode.y) discard;
  gl_FragColor = c;
}
"""

STAR_VERTEX = """
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform vec2 uShip;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 par;
varying vec2 uv;
varying vec4 col;
void main(void) {
  // FaceCamera: each star drifts back at 0 to 20 units a second (10 on average) and, 200 behind the ship, starts again ahead of it.
  float span = p3d_Vertex.y + 200.0;
  float rel = mod(p3d_Vertex.y - par.z * uShip.y - uShip.x + 200.0, span) - 200.0;
  vec4 eye = p3d_ModelViewMatrix * vec4(p3d_Vertex.x, uShip.x + rel, p3d_Vertex.z, 1.0);
  eye.xy += (p3d_MultiTexCoord0 - vec2(0.5)) * par.xy;
  gl_Position = p3d_ProjectionMatrix * eye;
  uv = p3d_MultiTexCoord0;
  col = vec4(1.0);
}
"""

_shader = {}


def shader(star=False):
    key = (star, isES())
    if key not in _shader:
        _shader[key] = Shader.make(Shader.SL_GLSL, head(key[1]) + (STAR_VERTEX if star else VERTEX), head(key[1]) + FRAGMENT)
    return _shader[key]


def _format():
    array = GeomVertexArrayFormat()
    array.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
    array.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
    array.addColumn(InternalName.make('vel'), 3, Geom.NTFloat32, Geom.COther)
    array.addColumn(InternalName.make('par'), 4, Geom.NTFloat32, Geom.COther)
    form = GeomVertexFormat()
    form.addArray(array)
    return GeomVertexFormat.registerFormat(form)


_form = []


def quads(name, particles):
    """particles: (pos, vel, (a, b, c, d)) -> a GeomNode of camera-facing quads."""
    if not _form:
        _form.append(_format())
    data = GeomVertexData(name, _form[0], Geom.UHStatic)
    data.setNumRows(len(particles) * 4)
    vertex = GeomVertexWriter(data, 'vertex')
    texcoord = GeomVertexWriter(data, 'texcoord')
    vel = GeomVertexWriter(data, 'vel')
    par = GeomVertexWriter(data, 'par')
    triangles = GeomTriangles(Geom.UHStatic)
    for k, (p, v, a) in enumerate(particles):
        for u, w in ((0, 0), (1, 0), (1, 1), (0, 1)):
            vertex.addData3(p[0], p[1], p[2])
            texcoord.addData2(u, w)
            vel.addData3(v[0], v[1], v[2])
            par.addData4(a[0], a[1], a[2], a[3])
        triangles.addVertices(k * 4, k * 4 + 1, k * 4 + 2)
        triangles.addVertices(k * 4, k * 4 + 2, k * 4 + 3)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


def ALPHA(colour):
    """Detonator's default colours over a particle's life: the colour with its strength times 0.7, 1, 0.5, 0.3, 0."""
    r, g, b, a = colour
    return [(r, g, b, a * k) for k in (0.7, 1.0, 0.5, 0.3, 0.0)]


WHITE5 = [(1.0, 1.0, 1.0, k / 255.0) for k in (10, 180, 255, 180, 10)]
ORANGE = (1.0, 0.423, 0.0, 0.5)


def mix(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(4))


class Fx:
    """Everything that bursts, under one node."""

    def __init__(self, parent, rnd=None):
        self.rnd = rnd or random.Random()
        self.root = parent.attachNewNode('acFx')
        self.root.setLightOff(100)
        self.root.setFogOff(100)
        self.root.setColorScaleOff(100)
        self.root.setDepthWrite(False)
        self.root.setTwoSided(True)
        self.root.setBin('fixed', 30)
        self.root.setShader(shader(), 50)
        self.live = []
        self.tex = {}
        self.stars = None

    def texture(self, name):
        if name not in self.tex:
            self.tex[name] = loader.loadTexture(MAPS + name + '.png')
        return self.tex[name]

    def preload(self, gsg=None):
        """Loads every picture and readies the shaders now, so the first explosion of a game does not make it stutter."""
        for name in ('Fireball', 'Smoke', 'GlowDot', 'Shockwave', 'Glow', 'Star02', 'ColorFlare', 't2_t_ara_spc_starBlueSmall1'):
            self.texture(name)
        for c in self.CONFETTI.values():
            self.texture(c['picture'])
        if gsg is not None:
            # One of each kind of burst, behind the ship and gone in a moment.
            behind = (0.0, -5000.0, 0.0)
            self.explosion(behind, 1.0)
            for kind in self.CONFETTI:
                self.confetti(behind, kind)
            self.sparkle(behind)
            self.root.prepareScene(gsg)
            for end, node in self.live:
                node.removeNode()
            self.live = []

    def unit(self):
        """Random.insideUnitSphere"""
        rnd = self.rnd
        while True:
            x, y, z = rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)
            if x * x + y * y + z * z <= 1.0:
                return x, y, z

    def burst(self, name, particles, picture, keys, pos, reach, additive=True, uv=(0.0, 0.0, 1.0, 1.0), damping=1.0, force=(0.0, 0.0, 0.0),
              grow=('rate', 0.0), largest=2.0, stretch=0.0, tint=(1.0, 1.0, 1.0, 1.0), unlit=False, cut=0.0, life=None):
        if not particles:
            return None
        node = self.root.attachNewNode(quads(name, particles))
        node.setTexture(self.texture(picture))
        now = globalClock.getFrameTime()
        node.setShaderInput('uStart', now)
        node.setShaderInput('uPhys', (math.log(damping) if damping < 0.9999 else 0.0, 0.0 if grow[0] == 'rate' else 1.0, grow[1], largest))
        node.setShaderInput('uForce', tuple(force))
        for k in range(5):
            node.setShaderInput('uKey%d' % k, tuple(keys[k]))
        node.setShaderInput('uUV', tuple(uv))
        node.setShaderInput('uStretch', stretch)
        node.setShaderInput('uTint', tuple(tint))
        node.setShaderInput('uMode', (1.0 if unlit else 0.0, cut))
        if additive:
            node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
        elif cut <= 0.0:
            node.setTransparency(TransparencyAttrib.MAlpha)
        else:
            node.setDepthWrite(True)
            node.setBin('opaque', 0)
        node.node().setBounds(BoundingSphere(Point3(*pos), reach))
        node.node().setFinal(True)
        end = now + (life if life is not None else max(p[2][1] + p[2][2] for p in particles))
        self.live.append((end, node))
        return node

    def update(self):
        if self.live:
            now = globalClock.getFrameTime()
            if any(end <= now for end, node in self.live):
                for end, node in self.live:
                    if end <= now:
                        node.removeNode()
                self.live = [item for item in self.live if item[0] > now]

    # ---- Detonator
    def __emit(self, pos, s, count, size, sizeVar, speed, radius, life, lifeVar):
        rnd = self.rnd
        out = []
        for k in range(count):
            a = self.unit()
            b = self.unit()
            vx, vy, vz = (speed if isinstance(speed, tuple) else (speed, speed, speed))
            out.append(((pos[0] + a[0] * radius * s, pos[1] + a[1] * radius * s, pos[2] + a[2] * radius * s),
                        (b[0] * vx * s, b[1] * vy * s, b[2] * vz * s),
                        (s * (size + rnd.random() * sizeVar), life + rnd.random() * lifeVar, 0.0, rnd.uniform(-0.5, 0.5))))
        return out

    def explosion(self, pos, size, tiny=False, distance=None):
        """Detonator at pos; size is Detonator.size (the prefab's 30 is 1.0 here). tiny: the TinyExplosion prefab (no shock wave or glow, a third as long)."""
        s = size / 30.0
        ts = 1.0 / 3.0 if tiny else 1.0
        # Nothing of an explosion this small shows from this far (well under a dot on the screen).
        if distance is not None and 140.0 * s / max(distance, 1.0) < 0.0008:
            return
        fire = [mix(ORANGE, (1, 1, 1, 0.5), 0.8), mix(ORANGE, (1, 1, 1, 0.5), 0.5), ORANGE, mix(ORANGE, (0.6, 0.15, 0.15, 0.3), 0.7), (0.1, 0.2, 0.45, 0.0)]
        reach = 200.0 * s + 5.0
        # Smoke and the fire's shadow go down first and the fire is added over them. (Unity drew them in whichever order their middles
        # happened to be from the camera, so the prototype's fire was sometimes hidden by its own smoke.)
        self.burst('fireShadow', self.__emit(pos, s, 2, 13.0, 1.0, 3.0, 6.0, 1.5 * ts, 1.5 * ts), 'Smoke', ALPHA((0.1, 0.1, 0.1, 0.6)), pos, reach, additive=False,
                   uv=(0.0, 0.0, 0.5, 1.0), damping=0.13, grow=('det', 0.0))
        grey = [(0.2, 0.2, 0.2, a) for a in (0.4, 0.7, 0.7, 0.4, 0.0)]
        self.burst('smokeA', self.__emit(pos, s, 2, 25.0, 3.0, (3.0, 4.0, 4.0), 10.0, 4.0 * ts, 0.0), 'Smoke', grey, pos, reach, additive=False, uv=(0.0, 0.0, 0.5, 1.0), damping=0.13,
                   grow=('rate', 0.095))
        self.burst('smokeB', self.__emit(pos, s, 2, 25.0, 3.0, 7.0, 10.0, 4.0, 0.0), 'Smoke', grey, pos, reach, additive=False, uv=(0.5, 0.0, 0.5, 1.0), damping=0.13, grow=('rate', 0.095))
        self.burst('fireA', self.__emit(pos, s, 3, 14.0, 3.0, 5.0, 4.0, 1.5 * ts, 1.5 * ts), 'Fireball', fire, pos, reach, uv=(0.0, 0.0, 0.5, 1.0), damping=0.13, grow=('det', 0.0))
        self.burst('fireB', self.__emit(pos, s, 3, 10.0, 6.0, 19.0, 4.0, 1.5 * ts, 1.5 * ts), 'Fireball', fire, pos, reach, uv=(0.5, 0.0, 0.5, 1.0), damping=0.13, grow=('det', 0.0))
        if s >= 0.1:
            # (Sparks of a smaller explosion are a hundredth of a unit across: they never showed.)
            self.burst('sparks', self.__emit(pos, s, 50, 0.5, 0.25, 155.0, 0.0, 2.0 * ts, 4.0 * ts), 'GlowDot', ALPHA((1.0, 0.71, 0.5, 0.75)), pos, 900.0 * s, damping=0.185,
                       force=(0.0, 0.0, -9.81), grow=('det', 0.0))
        if not tiny:
            self.burst('shockwave', self.__emit(pos, s, 1, 25.0, 0.0, 0.0, 0.0, 0.25, 0.025), 'Shockwave', ALPHA((1.0, 0.71, 0.5, 0.75)), pos, 5000.0, grow=('rate', 202.0))
            c = (0.5, 0.21, 0.0, 0.75)
            glow = [mix(c, (0.5, 0.1, 0.1, 0.9), 0.5)[:3] + (0.9,), mix(c, (0.6, 0.3, 0.3, 0.8), 0.5)[:3] + (0.8,), (0.7, 0.3, 0.3, 0.5), (0.4, 0.3, 0.4, 0.2), (0.1, 0.1, 0.4, 0.0)]
            self.burst('glow', self.__emit(pos, s, 1, 65.0, 0.0, 0.0, 0.0, 3.0, 0.0), 'Glow', glow, pos, 80.0 * s + 5.0)

    # ---- the confetti prefabs (one-shot MeshParticleEmitters on a ball 10 across)
    CONFETTI = {
        'pink': dict(count=(35, 80), size=(0.2, 2.0), life=(3.0, 3.0), stretch=2.5, picture='confetti_pink', tint=(0.52, 0.52, 0.52, 1.0), cut=0.5),
        'blue': dict(count=(10, 35), size=(0.2, 1.3), life=(3.0, 5.0), force=-10.0, damping=0.7, spin=4.0, picture='t2_t_ara_spc_confettiBlue1'),
        'green': dict(count=(15, 35), size=(0.2, 1.3), life=(3.0, 3.0), stretch=2.5, picture='t2_t_ara_spc_confettiGreen'),
        'orange': dict(count=(25, 50), size=(1.0, 1.5), life=(3.0, 3.0), stretch=2.5, picture='confetti_orange'),
        'starPurple': dict(count=(35, 80), size=(0.2, 2.0), life=(3.0, 3.0), picture='t2_t_ara_spc_confettiStarPurple1'),
        'starYellow': dict(count=(35, 80), size=(0.8, 3.0), life=(3.0, 3.0), picture='t2_t_ara_spc_confettiStarYellow1'),
    }

    def confetti(self, pos, kind, scale=10.0):
        c = self.CONFETTI[kind]
        rnd = self.rnd
        radius = 0.5 * scale
        parts = []
        for k in range(rnd.randint(*c['count'])):
            # A point of the ball and the way out from it.
            z = rnd.uniform(-1, 1)
            a = rnd.uniform(0, 2 * math.pi)
            r = math.sqrt(1 - z * z)
            n = (r * math.cos(a), r * math.sin(a), z)
            speed = rnd.uniform(5.0, 10.0)
            parts.append(((pos[0] + n[0] * radius, pos[1] + n[1] * radius, pos[2] + n[2] * radius),
                          (n[0] * speed + rnd.uniform(-1, 1), n[1] * speed + rnd.uniform(-1, 1), n[2] * speed),
                          (rnd.uniform(*c['size']), rnd.uniform(*c['life']), 0.0, rnd.uniform(-1, 1) * c.get('spin', 0.0))))
        self.burst('confetti', parts, c['picture'], WHITE5, pos, 60.0, additive=False, damping=c.get('damping', 1.0), force=(0.0, 0.0, c.get('force', -8.0)), largest=0.5,
                   stretch=c.get('stretch', 0.0), tint=c.get('tint', (1.0, 1.0, 1.0, 1.0)), unlit=True, cut=c.get('cut', 0.0))

    def sparkle(self, pos):
        """YellowHardCandyWrapperSparkle: two bursts on a shell round the candy, drifting up."""
        rnd = self.rnd
        for count, size, life, picture in (((5, 100), (0.3, 3.0), (3.0, 10.0), 'Star02'), ((15, 100), (0.3, 1.2), (3.0, 3.0), 'ColorFlare')):
            parts = []
            for k in range(rnd.randint(*count)):
                z = rnd.uniform(-1, 1)
                a = rnd.uniform(0, 2 * math.pi)
                r = math.sqrt(1 - z * z)
                parts.append(((pos[0] + r * math.cos(a) * 25.0, pos[1] + r * math.sin(a) * 25.0, pos[2] + z * 25.0),
                              (rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 1.0 + rnd.uniform(-0.25, 0.25)),
                              (rnd.uniform(*size), rnd.uniform(*life), 0.0, 0.0)))
            self.burst('sparkle', parts, picture, WHITE5, pos, 60.0, tint=(0.5, 0.5, 0.5, 0.5), largest=0.25)

    # ---- StarField: 500 stars in a box 200 x 200 x 1000 ahead
    def starField(self, parent, tint, seed=7):
        rnd = random.Random(seed)
        parts = []
        for k in range(500):
            x, y, z = rnd.uniform(-100, 100), rnd.uniform(-100, 100), 25.0 + rnd.uniform(0, 1000)
            sx = rnd.uniform(0.5, 3.0)
            sy = rnd.uniform(1.0, 2.0) * sx
            parts.append(((x, z, y), (0.0, 0.0, 0.0), (2.3856 * sx, 2.3856 * sy, rnd.uniform(0.9, 1.1), 0.0)))
        node = parent.attachNewNode(quads('stars', parts))
        node.setShader(shader(star=True), 60)
        node.setTexture(self.texture('t2_t_ara_spc_starBlueSmall1'))
        node.setShaderInput('uTint', tuple(tint))
        node.setShaderInput('uMode', (0.0, 0.0))
        node.setShaderInput('uShip', (0.0, 0.0))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setDepthWrite(False)
        node.setTwoSided(True)
        node.setLightOff(100)
        node.setBin('fixed', 5)
        node.node().setBounds(OmniBoundingVolume())
        node.node().setFinal(True)
        self.stars = node
        return node

    def setShip(self, shipZ, drift):
        """shipZ: how far the ship has come; drift: how far the stars have drifted back on their own (10 units a second)."""
        if self.stars is not None:
            self.stars.setShaderInput('uShip', (shipZ, drift))

    def destroy(self):
        for end, node in self.live:
            node.removeNode()
        self.live = []
        if self.stars is not None:
            self.stars.removeNode()
            self.stars = None
        self.root.removeNode()
