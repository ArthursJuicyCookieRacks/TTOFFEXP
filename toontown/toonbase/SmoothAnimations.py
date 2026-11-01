"""Frame interpolation for every animated thing in the game.

The game asks each Actor for interpolation one by one, with
setBlend(frameBlend=...), and only for the parts the Actor has at that
moment. Anything that loads its model afterwards (the classic characters,
toon heads that change), every copy of a prop out of the battle prop pool,
the playground's dancing props, and every Actor that never asks at all
kept the model file's own setting: off. Those animations stepped from frame
to frame at the rate they were made at (Arthur, 2026-11-01: the dog ears,
and "check EVERY animation").

install() makes every part of every Actor interpolate, whenever it is
loaded or copied, as long as the Smooth Animations setting is on (it is by
default).
"""

from direct.actor.Actor import Actor
from panda3d.core import ConfigVariableBool, loadPrcFileData

_installed = False


def wanted():
    return ConfigVariableBool('want-smooth-animations', True).getValue()


def smooth(actor):
    if not wanted():
        return
    try:
        for bundle in actor.getPartBundles():
            bundle.setFrameBlendFlag(True)
    except Exception:
        pass


def install():
    global _installed
    if _installed:
        return
    _installed = True
    if wanted():
        # Bundles made from now on start interpolated.
        loadPrcFileData('smooth animations', 'interpolate-frames 1')

    loadModel = Actor.loadModel

    def smoothLoadModel(self, *args, **kw):
        result = loadModel(self, *args, **kw)
        smooth(self)
        return result

    copyActor = Actor.copyActor

    def smoothCopyActor(self, *args, **kw):
        result = copyActor(self, *args, **kw)
        smooth(self)
        return result

    setBlend = Actor.setBlend

    def smoothSetBlend(self, animBlend=None, frameBlend=None, blendType=None, partName=None):
        # Code that asks for no interpolation was reading the old
        # want-smooth-animations default before the setting loaded.
        if frameBlend is not None and not frameBlend and wanted():
            frameBlend = True
        return setBlend(self, animBlend=animBlend, frameBlend=frameBlend, blendType=blendType, partName=partName)

    Actor.loadModel = smoothLoadModel
    Actor.copyActor = smoothCopyActor
    Actor.setBlend = smoothSetBlend
