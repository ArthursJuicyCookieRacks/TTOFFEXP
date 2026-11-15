"""The shaders Doodle Rescue is drawn with: the Unity materials of
Disney's prototype (Diffuse, VertexLit, Vertex Colored, the tree leaf
shader the bulb plants use, the terrain's four ground pictures, Unlit and
the additive particle shader), each worked out the way Unity's own shader
did, with the scene's one light, its ambient light and its black fog.
Runs the same on a PC and on a phone (OpenGL ES 2).

A piece carries its material in the tag 'am' (written by the build
script); dress(root) reads the tags once.
"""

import json

from panda3d.core import ColorBlendAttrib, Shader, TransparencyAttrib

from toontown.toontropolis.TownShader import head, isES

VERTEX = """
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ViewMatrix;
uniform mat3 p3d_NormalMatrix;
uniform vec4 uTS;
uniform vec3 uLdir;
uniform vec3 uLcol;
uniform vec3 uAmb;
uniform vec4 uColor;
uniform vec4 uEmis;
uniform vec4 uSpec;
uniform vec4 uTile;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 uv;
varying vec4 vc;
varying vec3 vlit;
varying vec3 vspec;
varying float ndl;
varying float dist;
#ifdef KIND_GROUND
varying vec4 guv;
varying vec4 guv2;
#endif
void main(void) {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  vec3 eye = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
  dist = length(eye);
  uv = p3d_MultiTexCoord0 * uTS.xy + uTS.zw;
#ifdef KIND_GROUND
  guv = vec4(p3d_MultiTexCoord0 * uTile.x, p3d_MultiTexCoord0 * uTile.y);
  guv2 = vec4(p3d_MultiTexCoord0 * uTile.z, p3d_MultiTexCoord0 * uTile.w);
#endif
#ifdef VCOL
  vc = p3d_Color;
#else
  vc = vec4(1.0);
#endif
  vlit = vec3(1.0);
  vspec = vec3(0.0);
  ndl = 0.0;
#ifdef LIT
  vec3 n = normalize(p3d_NormalMatrix * p3d_Normal);
  vec3 l = normalize((p3d_ViewMatrix * vec4(uLdir, 0.0)).xyz);
  ndl = max(dot(n, l), 0.0);
#ifdef KIND_VL
  vec3 matc = uColor.rgb;
#else
  vec3 matc = vc.rgb;
#endif
  vlit = clamp(uEmis.rgb + matc * (uAmb + uLcol * ndl), 0.0, 1.0);
  if (ndl > 0.0 && uSpec.a > 0.0) {
    vec3 v = normalize(-eye);
    vspec = uLcol * uSpec.rgb * pow(max(dot(n, normalize(l + v)), 0.0), uSpec.a);
  }
#endif
}
"""

FRAGMENT = """
uniform sampler2D p3d_Texture0;
uniform vec4 uColor;
uniform vec4 uTint;
uniform vec3 uLcol;
uniform vec3 uAmb;
uniform float uCut;
uniform float uFade;
uniform float uFog;
varying vec2 uv;
varying vec4 vc;
varying vec3 vlit;
varying vec3 vspec;
varying float ndl;
varying float dist;
#ifdef KIND_GROUND
uniform sampler2D uS0;
uniform sampler2D uS1;
uniform sampler2D uS2;
uniform sampler2D uS3;
varying vec4 guv;
varying vec4 guv2;
#endif
void main(void) {
#ifdef NOTEX
  vec4 tex = vec4(1.0);
#else
  vec4 tex = texture2D(p3d_Texture0, uv);
#endif
  vec3 rgb;
  float a;
#ifdef KIND_DIFF
  vec3 alb = tex.rgb * uColor.rgb;
  rgb = clamp(alb * uAmb * 2.0, 0.0, 1.0) + clamp(alb * uLcol * (2.0 * ndl), 0.0, 1.0);
  a = tex.a * uColor.a;
#endif
#ifdef KIND_GROUND
  vec3 alb = tex.r * texture2D(uS0, guv.xy).rgb + tex.g * texture2D(uS1, guv.zw).rgb + tex.b * texture2D(uS2, guv2.xy).rgb + tex.a * texture2D(uS3, guv2.zw).rgb;
  rgb = clamp(alb * uAmb * 2.0, 0.0, 1.0) + clamp(alb * uLcol * (2.0 * ndl), 0.0, 1.0);
  a = 1.0;
#endif
#ifdef KIND_VC
  rgb = tex.rgb * vlit * uColor.rgb * 2.0 + vspec;
  a = tex.a * vc.a * uColor.a;
#endif
#ifdef KIND_VL
  rgb = tex.rgb * vlit * 2.0 + vspec;
  a = tex.a * uColor.a;
#endif
#ifdef KIND_UT
  rgb = tex.rgb * uColor.rgb;
  a = tex.a * uColor.a;
#endif
#ifdef KIND_TVC
  rgb = tex.rgb * clamp(vc.rgb * 4.0 * uColor.rgb, 0.0, 1.0) * 2.0;
  a = tex.a;
#endif
#ifdef KIND_ADD
  rgb = tex.rgb * uTint.rgb * 2.0;
  a = tex.a * uTint.a * 2.0;
#endif
#ifdef CUT
  if (a <= uCut) discard;
#endif
  float fd = dist * uFog;
  rgb = clamp(rgb, 0.0, 1.0) * exp(-fd * fd);
  gl_FragColor = vec4(rgb, clamp(a, 0.0, 1.0) * uFade);
}
"""

# Rocket doodles' sparkles: each corner knows where and when its sparkle was born; the card faces the camera.
SPARK_VERTEX = """
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float uTime;
uniform float uFrom;
uniform vec4 uLife;
uniform vec4 uKey0;
uniform vec4 uKey1;
uniform vec4 uKey2;
uniform vec4 uKey3;
uniform vec4 uKey4;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 born;
attribute vec4 drift;
varying vec2 uv;
varying vec4 tint;
varying float dist;
void main(void) {
  float age = uTime - born.x;
  float k = age / uLife.x;
  uv = p3d_MultiTexCoord0;
  if (born.x < uFrom || k < 0.0 || k >= 1.0) {
    gl_Position = vec4(0.0, 0.0, -2.0, 1.0);
    tint = vec4(0.0);
    dist = 0.0;
    return;
  }
  vec3 at = p3d_Vertex.xyz + drift.xyz * age + born.yzw * (0.5 * age * age);
  vec4 eye = p3d_ModelViewMatrix * vec4(at, 1.0);
  float size = drift.w * pow(1.0 + uLife.y, age);
  size = min(size, -eye.z * uLife.z);
  eye.xy += (p3d_MultiTexCoord0 - 0.5) * size;
  gl_Position = p3d_ProjectionMatrix * eye;
  dist = length(eye.xyz);
  float s = k * 4.0;
  vec4 c = mix(uKey0, uKey1, clamp(s, 0.0, 1.0));
  c = mix(c, uKey2, clamp(s - 1.0, 0.0, 1.0));
  c = mix(c, uKey3, clamp(s - 2.0, 0.0, 1.0));
  tint = mix(c, uKey4, clamp(s - 3.0, 0.0, 1.0));
}
"""

SPARK_FRAGMENT = """
uniform sampler2D p3d_Texture0;
uniform vec4 uTint;
uniform float uFog;
varying vec2 uv;
varying vec4 tint;
varying float dist;
void main(void) {
  vec4 tex = texture2D(p3d_Texture0, uv);
  vec4 c = 2.0 * tint * uTint * tex;
  float fd = dist * uFog;
  gl_FragColor = vec4(clamp(c.rgb, 0.0, 1.0) * exp(-fd * fd), clamp(c.a, 0.0, 1.0));
}
"""

KINDS = {'diff': 'KIND_DIFF', 'vc': 'KIND_VC', 'vl': 'KIND_VL', 'ut': 'KIND_UT', 'add': 'KIND_ADD', 'pab': 'KIND_ADD', 'vcu': 'KIND_UT', 'vcd': 'KIND_DIFF', 'tvc': 'KIND_TVC', 'ground': 'KIND_GROUND'}
_made = {}


def make(kind, vcol=False, cut=False, notex=False, es=None):
    if es is None:
        es = isES()
    define = KINDS.get(kind, 'KIND_DIFF')
    key = (define, vcol, cut, notex, es)
    if key not in _made:
        d = '#define %s\n' % define
        if define in ('KIND_DIFF', 'KIND_VC', 'KIND_VL', 'KIND_GROUND'):
            d += '#define LIT\n'
        if vcol:
            d += '#define VCOL\n'
        if cut:
            d += '#define CUT\n'
        if notex:
            d += '#define NOTEX\n'
        _made[key] = Shader.make(Shader.SL_GLSL, head(es) + d + VERTEX, head(es) + d + FRAGMENT)
    return _made[key]


def sparkle(es=None):
    if es is None:
        es = isES()
    key = ('sparkle', es)
    if key not in _made:
        _made[key] = Shader.make(Shader.SL_GLSL, head(es) + SPARK_VERTEX, head(es) + SPARK_FRAGMENT)
    return _made[key]


def light(root, direction, colour, ambient=(0.0, 0.0, 0.0), fog=0.0):
    """The scene's one light (direction is the way it shines, in the root's
    space; Unity's ambient counts half in its lighting sums) and its fog:
    black, thickening with the square of the distance."""
    root.setShaderInput('uLdir', (-direction[0], -direction[1], -direction[2]))
    root.setShaderInput('uLcol', tuple(colour))
    root.setShaderInput('uAmb', (ambient[0] * 0.5, ambient[1] * 0.5, ambient[2] * 0.5))
    root.setShaderInput('uFade', 1.0)
    root.setShaderInput('uFog', fog)
    plain(root)


def plain(node):
    """Inputs every piece's shader reads, for pieces that carry no material of their own."""
    node.setShaderInput('uColor', (1.0, 1.0, 1.0, 1.0))
    node.setShaderInput('uEmis', (0.0, 0.0, 0.0, 0.0))
    node.setShaderInput('uSpec', (0.0, 0.0, 0.0, 0.0))
    node.setShaderInput('uTint', (0.5, 0.5, 0.5, 0.5))
    node.setShaderInput('uTS', (1.0, 1.0, 0.0, 0.0))
    node.setShaderInput('uTile', (1.0, 1.0, 1.0, 1.0))
    node.setShaderInput('uCut', 0.0)


def dress(root):
    """Give every tagged piece under root its shader and blending."""
    for g in root.findAllMatches('**/=am'):
        i = json.loads(g.getTag('am'))
        kind, blend = i['k'], i['b']
        vcol = kind in ('vc', 'vcu', 'vcd', 'tvc') and not i.get('novc')
        g.setShader(make(kind, vcol=vcol, cut=blend == 2, notex=g.findAllTextures().getNumTextures() == 0))
        g.setShaderInput('uColor', tuple(i['c']))
        g.setShaderInput('uEmis', tuple(i['e']) + (0.0,))
        spec = i['s']
        g.setShaderInput('uSpec', (spec[0], spec[1], spec[2], max(i['sh'] * 128.0, 1.0) if max(spec) > 0 else 0.0))
        g.setShaderInput('uTint', tuple(i['t']))
        g.setShaderInput('uTS', tuple(i['ts']))
        g.setShaderInput('uCut', i['cut'])
        if kind in ('add', 'pab', 'ut', 'tvc'):
            g.setTwoSided(True)
        if blend == 1:
            g.setTransparency(TransparencyAttrib.MAlpha)
            g.setDepthWrite(False)
            g.setBin('transparent', 0)
        elif blend == 3:
            additive(g)


def additive(node):
    node.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    node.setDepthWrite(False)
    node.setBin('fixed', 10)
