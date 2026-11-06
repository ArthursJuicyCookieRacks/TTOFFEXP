"""The loading screen while a Survival map is built (Arthur 2026-11-06).

A map is built in one go: its toys, then the walking map the cogs use
(SurvivalArena.buildReach). On a phone Toybox Terrace took about a minute,
and all that time the game drew nothing and read no touches, so Android
put up "isn't responding" again and again. The game's own loading screen
(the one between playgrounds) now shows instead, its bar moving, and a
frame is drawn at least every TICK seconds through the build: that frame
is also when Android's waiting touches and messages are read.
"""

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import TTLocalizer

notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalLoading')

# Seconds between frames while loading (the playground loading screen's own).
TICK = 0.2

_active = False
_last = 0.0
_start = 0.0
_value = 0.0
# The cameras turned off while loading.
_paused = []


def begin(title):
    """Puts the loading screen up for the map named title."""
    global _active, _last, _start, _value
    if _active:
        return
    try:
        screen = base.loader.loadingScreen
        screen.begin(100, TTLocalizer.HeadingToMinigameTitle % title, 1, TTLocalizer.TIP_GENERAL)
    except Exception:
        notify.warning('no loading screen to show')
        return
    _active = True
    # Behind the loading screen the half-built map isn't drawn: drawing it
    # took a third of the load.
    global _paused
    _paused = [cam for cam in _cameras() if cam.node().isActive()]
    for cam in _paused:
        cam.node().setActive(False)
    _start = _last = globalClock.getRealTime()
    _value = 0.0
    _draw(0.0)


def step(fraction=None):
    """Called often while building: draws a frame (and so reads Android's
    waiting touches) when the last one was TICK seconds ago. fraction, 0 to
    1, is how far the build is; the bar never goes back."""
    global _last, _value
    if not _active:
        return
    if fraction is not None:
        _value = max(_value, min(1.0, fraction))
    now = globalClock.getRealTime()
    if now - _last < TICK:
        return
    _last = now
    _draw(_value)


def end():
    global _active
    if not _active:
        return
    _active = False
    global _paused
    for cam in _paused:
        if not cam.isEmpty():
            cam.node().setActive(True)
    _paused = []
    notify.info('loaded in %.1fs' % (globalClock.getRealTime() - _start))
    try:
        base.loader.loadingScreen.end()
    except Exception:
        pass


def _cameras():
    # The 3-D view's camera (the loading screen is on the 2-D one).
    try:
        return [base.cam] if base.cam and not base.cam.isEmpty() else []
    except Exception:
        return []


def _draw(fraction):
    # The bar's update draws the frame.
    try:
        base.loader.loadingScreen.waitBar.update(int(round(fraction * 100)))
    except Exception:
        base.graphicsEngine.renderFrame()
