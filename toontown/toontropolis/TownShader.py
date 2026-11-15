"""The shader the Toontropolis town is drawn with.

Disney's Unity prototype lit the town with its own shaders: every texture
is multiplied by the light and then doubled, the ground takes soft shadows
from the buildings, and day and night differ only in the ambient light and
the fog. All of that is worked out once when the town model is built and
stored in the model (two colours per corner: day and night, plus the sun's
share on the ground and, near them, the light of the four light bulbs), so
this shader only has to mix them. It runs the
same on a PC and on a phone (OpenGL ES 2), where Panda's stand-in shader
draws neither fog nor a second texture.
"""

from panda3d.core import Shader

VERTEX = """
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform float uNight;
uniform vec4 uTS;
uniform vec4 uLM;
attribute vec4 p3d_Vertex;
attribute vec4 p3d_Color;
attribute vec4 ncolor;
attribute vec4 lcolor;
attribute vec2 p3d_MultiTexCoord0;
#ifdef BULB
uniform vec4 uBulb;
attribute vec4 bulb;
#endif
varying vec2 uv;
varying vec4 col;
varying vec3 lcol;
varying vec2 lmuv;
varying float dist;
#ifdef SPEC
uniform mat4 p3d_ViewMatrix;
uniform mat3 p3d_NormalMatrix;
uniform vec3 uL0dir;
uniform vec3 uL0col;
uniform vec3 uL1dir;
uniform vec3 uL1col;
uniform vec4 uSpec;
attribute vec3 p3d_Normal;
varying vec3 shine;
#endif
void main(void) {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  uv = p3d_MultiTexCoord0 * uTS.xy + uTS.zw;
  col = mix(p3d_Color, ncolor, uNight);
#ifdef BULB
  float which = bulb.a * 3.0;
  vec4 pick = vec4(step(which, 0.5), step(0.5, which) * step(which, 1.5), step(1.5, which) * step(which, 2.5), step(2.5, which));
  col.rgb += bulb.rgb * dot(pick, uBulb);
#endif
  vec3 eye = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
  dist = length(eye);
#ifdef SPEC
  vec3 n = normalize(p3d_NormalMatrix * p3d_Normal);
  vec3 v = normalize(-eye);
  vec3 l0 = normalize((p3d_ViewMatrix * vec4(uL0dir, 0.0)).xyz);
  vec3 l1 = normalize((p3d_ViewMatrix * vec4(uL1dir, 0.0)).xyz);
  shine = vec3(0.0);
  if (dot(n, l0) > 0.0) shine += uL0col * uSpec.rgb * pow(max(dot(n, normalize(l0 + v)), 0.0), uSpec.a);
  if (dot(n, l1) > 0.0) shine += uL1col * uSpec.rgb * pow(max(dot(n, normalize(l1 + v)), 0.0), uSpec.a);
#endif
#ifdef GROUND
  lcol = lcolor.rgb;
  lmuv = (p3d_Vertex.xy - uLM.xy) * uLM.zw;
#else
  lcol = vec3(0.0);
  lmuv = vec2(0.0);
#endif
}
"""

FRAGMENT = """
uniform sampler2D p3d_Texture0;
uniform sampler2D uShadow;
uniform vec4 p3d_ColorScale;
uniform vec4 uTint;
uniform vec3 uAdd;
uniform float uFogBlack;
uniform float uCut;
uniform struct p3d_FogParameters {
  vec4 color;
  float density;
  float start;
  float end;
  float scale;
} p3d_Fog;
varying vec2 uv;
varying vec4 col;
varying vec3 lcol;
varying vec2 lmuv;
varying float dist;
#ifdef SPEC
varying vec3 shine;
#endif
void main(void) {
  vec4 t = texture2D(p3d_Texture0, uv);
  vec3 lit = col.rgb;
#ifdef GROUND
  lit += lcol * texture2D(uShadow, lmuv).r;
#endif
  vec3 rgb = t.rgb * lit * 2.0 * uTint.rgb + uAdd;
#ifdef SPEC
  rgb += shine;
#endif
  rgb = clamp(rgb, 0.0, 1.0);
  float a = t.a * col.a * uTint.a;
  if (a < uCut) discard;
  float d = dist * p3d_Fog.density;
  float f = exp(-d * d);
  rgb = mix(p3d_Fog.color.rgb * (1.0 - uFogBlack), rgb, f);
  gl_FragColor = vec4(rgb, a) * p3d_ColorScale;
}
"""

_made = {}


def head(es):
    if es:
        return '#version 100\nprecision highp float;\n'
    return '#version 120\n'


def isES():
    pipe = getattr(base, 'pipe', None)
    return pipe is not None and 'ES' in pipe.getInterfaceName()


def make(ground=False, es=None, spec=False, bulb=False):
    """The town's shader; ground=True for the pieces the buildings' shadows
    fall on, spec=True for the few with a sheen that follows the camera,
    bulb=True for the few pieces one of the four light bulbs shines on."""
    if es is None:
        es = isES()
    key = (ground, es, spec, bulb)
    if key not in _made:
        define = ('#define GROUND\n' if ground else '') + ('#define SPEC\n' if spec else '') + ('#define BULB\n' if bulb else '')
        _made[key] = Shader.make(Shader.SL_GLSL, head(es) + define + VERTEX, head(es) + define + FRAGMENT)
    return _made[key]


def defaults(node):
    """The inputs every piece starts from (a piece that scrolls its texture,
    changes colour or cuts holes sets its own)."""
    node.setShaderInput('uNight', 0.0)
    node.setShaderInput('uTS', (1.0, 1.0, 0.0, 0.0))
    node.setShaderInput('uLM', (0.0, 0.0, 1.0, 1.0))
    node.setShaderInput('uTint', (1.0, 1.0, 1.0, 1.0))
    node.setShaderInput('uAdd', (0.0, 0.0, 0.0))
    node.setShaderInput('uFogBlack', 0.0)
    node.setShaderInput('uCut', 0.0)
    node.setShaderInput('uBulb', (0.0, 0.0, 0.0, 0.0))
