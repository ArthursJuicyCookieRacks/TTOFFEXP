"""Toontropolis: the plaza from Disney's Toontown 2.0 prototype.

The model (phase_4/models/toontropolis/town) is Disney's Unity scene,
converted piece for piece: the town itself, the things that only show at
night (lit windows, lamp glows, the moon), the living buildings and street
props as Panda characters, and Disney's own walls and floors. This class
loads it, puts the town's shader on it and switches day and night the way
the prototype's power switch did (the ambient light, the fog and the sky
change; the sun and the buildings' shadows stay).
"""

import json

from panda3d.core import Fog, NodePath, SamplerState, Vec4

from toontown.toontropolis import TownShader

MODELS = 'phase_4/models/toontropolis/'
# Unity units to Toontown feet (a Flunky is 1.86 units there, 4.88 feet here).
SCALE = 2.6


class Town:

    def __init__(self, parent, night=False):
        self.root = loader.loadModel(MODELS + 'town.bam')
        self.root.reparentTo(parent)
        self.meta = json.loads(self.root.getTag('ttp'))
        self.static = self.root.find('static')
        self.ground = self.root.find('ground')
        self.nightOnly = self.root.find('nightOnly')
        self.dyn = self.root.find('dyn')
        self.chars = self.root.find('chars')
        self.collisions = self.root.find('collisions')
        # Lamp glows and the moon: only there at night.
        self.glows = [n for n in self.dyn.getChildren() if n.getName() in ('Moon', 'streetLampGlow', 't2_m_ara_ttp_lampGlow')]
        self.night = None
        self.fog = None
        self.sky = None
        self.skies = {}
        self.__shade()
        self.setNight(night)

    def __shade(self):
        root = self.root
        TownShader.defaults(root)
        root.setShader(TownShader.make(False))
        # No lights or colour scale of the level's own reach the town: its
        # light is in the model.
        root.setLightOff(100)
        lm = self.meta['lightmap']
        shadow = loader.loadTexture(lm['tex'])
        shadow.setWrapU(SamplerState.WM_clamp)
        shadow.setWrapV(SamplerState.WM_clamp)
        shadow.setMinfilter(SamplerState.FT_linear)
        shadow.setMagfilter(SamplerState.FT_linear)
        self.ground.setShader(TownShader.make(True))
        self.ground.setShaderInput('uShadow', shadow)
        self.ground.setShaderInput('uLM', (lm['origin'][0], lm['origin'][1], 1.0 / lm['size'], 1.0 / lm['size']))
        root.setShaderInput('uShadow', shadow)
        for n in root.findAllMatches('**/=tcut'):
            n.setShaderInput('uCut', float(n.getTag('tcut')))
        for n in root.findAllMatches('**/=tfogblack'):
            n.setShaderInput('uFogBlack', 1.0)
        lights = self.meta['lights']
        for key in ('l0dir', 'l0col', 'l1dir', 'l1col'):
            root.setShaderInput('uL' + key[1:], tuple(lights[key]))
        for n in root.findAllMatches('**/=tspec'):
            n.setShader(TownShader.make(False, spec=True))
            n.setShaderInput('uSpec', tuple(float(v) for v in n.getTag('tspec').split()))
        for n in root.findAllMatches('**/=tadd'):
            n.setShaderInput('uAdd', tuple(float(v) for v in n.getTag('tadd').split()))
        # The pieces a light bulb shines on (uBulb: how bright each of the
        # four bulbs is right now).
        for n in root.findAllMatches('**/=tbulb'):
            n.setShader(TownShader.make(n.hasNetTag('tground'), spec=n.hasTag('tspec'), bulb=True))
        # A texture with its own scale and offset (the owl's glasses).
        for n in root.findAllMatches('**/=tts'):
            n.setShaderInput('uTS', tuple(float(v) for v in n.getTag('tts').split()))

    # --- Day and night ---

    def fogColor(self, night):
        c = self.meta['fog']['night' if night else 'day']
        return Vec4(c[0], c[1], c[2], 1)

    def fogDensity(self):
        return self.meta['fog']['density']

    def setNight(self, night, amount=None):
        """Night or day. amount (0 day .. 1 night) is for the moments in
        between while the power switch turns."""
        night = bool(night)
        self.night = night
        self.root.setShaderInput('uNight', float(night) if amount is None else amount)
        if night:
            self.nightOnly.show()
        else:
            self.nightOnly.hide()
        for n in self.glows:
            n.show() if night else n.hide()
        if self.fog is not None:
            self.fog.setColor(self.fogColor(night))
        if self.sky is not None:
            self.__showSky()

    def setBulbs(self, levels):
        """How bright the four light bulbs are (the power building's left,
        middle and top one, then the pet shop's)."""
        self.root.setShaderInput('uBulb', tuple(levels))

    def makeFog(self):
        """Disney's fog (thicker with the square of the distance), white by
        day and blue by night."""
        self.fog = Fog('toontropolisFog')
        self.fog.setColor(self.fogColor(self.night))
        self.fog.setExpDensity(self.fogDensity())
        return self.fog

    def makeSky(self, parent, size=1.0):
        """Disney's two sky boxes (a Survival arena loads the same model
        itself and hands it over with useSky)."""
        sky = loader.loadModel(MODELS + 'sky.bam')
        sky.reparentTo(parent)
        sky.setScale(size)
        sky.setLightOff(100)
        sky.setFogOff(100)
        sky.setDepthWrite(False)
        sky.setDepthTest(False)
        sky.setBin('background', 0)
        self.useSky(sky)
        return sky

    def useSky(self, sky):
        self.sky = sky
        self.skies = {'day': sky.find('**/day'), 'night': sky.find('**/night')}
        self.__showSky()

    def __showSky(self):
        for name, box in self.skies.items():
            if box.isEmpty():
                continue
            if (name == 'night') == self.night:
                box.show()
            else:
                box.hide()

    def destroy(self):
        self.sky = None
        self.skies = {}
        self.glows = []
        self.root.removeNode()
