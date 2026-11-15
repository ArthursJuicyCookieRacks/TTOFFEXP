"""The shaders Asteroid Chicken is drawn with: the Unity materials of
Disney's prototype (Diffuse, VertexLit, Vertex Colored, Unlit Transparent
and the two particle shaders), each worked out the way Unity's own shader
did, so the pieces come out in the original's colours. One directional
light and no ambient, as in the prototype's scene. Runs the same on a PC
and on a phone (OpenGL ES 2).

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
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 uv;
varying vec4 vc;
varying vec3 vlit;
varying vec3 vspec;
varying float ndl;
void main(void) {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  uv = p3d_MultiTexCoord0 * uTS.xy + uTS.zw;
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
    vec3 v = normalize(-(p3d_ModelViewMatrix * p3d_Vertex).xyz);
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
varying vec2 uv;
varying vec4 vc;
varying vec3 vlit;
varying vec3 vspec;
varying float ndl;
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
#ifdef KIND_ADD
  rgb = tex.rgb * uTint.rgb * 2.0;
  a = tex.a * uTint.a * 2.0;
#endif
#ifdef CUT
  if (a <= uCut) discard;
#endif
  gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), clamp(a, 0.0, 1.0) * uFade);
}
"""

KINDS = {'diff': 'KIND_DIFF', 'vc': 'KIND_VC', 'vl': 'KIND_VL', 'ut': 'KIND_UT', 'add': 'KIND_ADD', 'pab': 'KIND_ADD', 'vcu': 'KIND_UT', 'vcd': 'KIND_DIFF'}
_made = {}


def make(kind, vcol=False, cut=False, notex=False, es=None):
    if es is None:
        es = isES()
    define = KINDS.get(kind, 'KIND_DIFF')
    key = (define, vcol, cut, notex, es)
    if key not in _made:
        d = '#define %s\n' % define
        if define in ('KIND_DIFF', 'KIND_VC', 'KIND_VL'):
            d += '#define LIT\n'
        if vcol:
            d += '#define VCOL\n'
        if cut:
            d += '#define CUT\n'
        if notex:
            d += '#define NOTEX\n'
        _made[key] = Shader.make(Shader.SL_GLSL, head(es) + d + VERTEX, head(es) + d + FRAGMENT)
    return _made[key]


def light(root, direction, colour, ambient=(0.0, 0.0, 0.0)):
    """The scene's one light: direction is the way it shines, in the root's
    space; Unity's ambient counts half in its lighting sums."""
    root.setShaderInput('uLdir', (-direction[0], -direction[1], -direction[2]))
    root.setShaderInput('uLcol', tuple(colour))
    root.setShaderInput('uAmb', (ambient[0] * 0.5, ambient[1] * 0.5, ambient[2] * 0.5))
    root.setShaderInput('uFade', 1.0)


def dress(root):
    """Give every tagged piece under root its shader and blending."""
    for g in root.findAllMatches('**/=am'):
        i = json.loads(g.getTag('am'))
        kind, blend = i['k'], i['b']
        vcol = kind in ('vc', 'vcu', 'vcd') and not i.get('novc')
        g.setShader(make(kind, vcol=vcol, cut=blend == 2, notex=g.findAllTextures().getNumTextures() == 0))
        g.setShaderInput('uColor', tuple(i['c']))
        g.setShaderInput('uEmis', tuple(i['e']) + (0.0,))
        spec = i['s']
        g.setShaderInput('uSpec', (spec[0], spec[1], spec[2], max(i['sh'] * 128.0, 1.0) if max(spec) > 0 else 0.0))
        g.setShaderInput('uTint', tuple(i['t']))
        g.setShaderInput('uTS', tuple(i['ts']))
        g.setShaderInput('uCut', i['cut'])
        if kind in ('add', 'pab', 'ut'):
            g.setTwoSided(True)
        if blend == 1:
            g.setTransparency(TransparencyAttrib.MAlpha)
            g.setDepthWrite(False)
            g.setBin('transparent', 0)
        elif blend == 3:
            g.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
            g.setDepthWrite(False)
            g.setBin('fixed', 10)
