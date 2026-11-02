"""Field of view and volume, set from the Shticker Book's Settings page.

Saved in settings.json under "game": "fov" (degrees), "music-volume" and
"sfx-volume" (0..100), and the Double XP switches "double-xp-gags",
"double-xp-gardening" and "double-xp-doodles" (true/false). These are separate from the old "music-vol" and
"sfx-vol" keys, which set Panda's master volume before the window opens.
"""

import builtins

from direct.directnotify import DirectNotifyGlobal

notify = DirectNotifyGlobal.directNotify.newCategory('GameSettings')

FOV_DEFAULT = 52
FOV_MIN = 40
FOV_MAX = 100
MUSIC_BASE = 0.65
VOLUME_DEFAULT = 100


_store = None


def _settings():
    # The game's settings.json. The in-process server code runs without
    # "base" (Double XP is read there), so the client's copy is kept here.
    global _store
    display = getattr(builtins.__dict__.get('base'), 'display', None)
    settings = getattr(display, 'settings', None)
    if settings is not None:
        _store = settings
    return _store


def _get(name, default, low, high):
    s = _settings()
    value = s.getOption('game', name, default) if s is not None else default
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _set(name, value):
    s = _settings()
    if s is None:
        return
    try:
        s.updateSetting('game', name, value)
    except OSError:
        notify.warning('could not save %s' % name)


def getFov():
    return _get('fov', FOV_DEFAULT, FOV_MIN, FOV_MAX)


def getMusicVolume():
    return _get('music-volume', VOLUME_DEFAULT, 0, 100)


def getSfxVolume():
    return _get('sfx-volume', VOLUME_DEFAULT, 0, 100)


def setFov(fov, save=True):
    fov = max(FOV_MIN, min(FOV_MAX, int(round(fov))))
    applyFov(fov)
    if save:
        _set('fov', fov)


def setMusicVolume(level, save=True):
    level = max(0, min(100, int(round(level))))
    applyMusicVolume(level)
    if save:
        _set('music-volume', level)


def setSfxVolume(level, save=True):
    level = max(0, min(100, int(round(level))))
    applySfxVolume(level)
    if save:
        _set('sfx-volume', level)


def applyFov(fov):
    # The game sets the camera's field of view from DefaultCameraFov in
    # many places (walking, battles, minigames, cog HQs): they all read the
    # player's choice from there.
    from otp.otpbase import OTPGlobals
    from toontown.toonbase import ToontownGlobals
    old = OTPGlobals.DefaultCameraFov
    OTPGlobals.DefaultCameraFov = float(fov)
    ToontownGlobals.DefaultCameraFov = float(fov)
    av = getattr(base, 'localAvatar', None)
    if av is not None and getattr(av, 'fov', None) == old:
        av.fov = float(fov)
    # Change the view now unless a scene has its own (a cutscene, a game).
    lens = base.camLens
    if lens is not None and abs(lens.getMinFov() - old / (4. / 3.)) < 0.5:
        lens.setMinFov(float(fov) / (4. / 3.))


def applyMusicVolume(level):
    if getattr(base, 'musicManager', None) is not None:
        base.musicManager.setVolume(MUSIC_BASE * level / 100.0)


def applySfxVolume(level):
    for mgr in getattr(base, 'sfxManagerList', []) or []:
        mgr.setVolume(level / 100.0)


# Double XP: each kind of experience has its own on/off switch.
DOUBLE_XP_GAGS = 'gags'
DOUBLE_XP_GARDENING = 'gardening'
DOUBLE_XP_DOODLES = 'doodles'
DOUBLE_XP_KINDS = (DOUBLE_XP_GAGS, DOUBLE_XP_GARDENING, DOUBLE_XP_DOODLES)


def getDoubleXp(kind):
    s = _settings()
    if s is None:
        return False
    value = s.getOption('game', 'double-xp-' + kind, False)
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def setDoubleXp(kind, on):
    _set('double-xp-' + kind, bool(on))
    notify.info('double %s xp %s' % (kind, 'on' if on else 'off'))


def getXpMultiplier(kind):
    # 2 while that kind's Double XP is on, otherwise 1.
    return 2 if getDoubleXp(kind) else 1


def isPlayerToon(av):
    # Double XP is for the player's own toon, not the NPC players.
    return av is not None and not getattr(av, 'isNPCPlayer', lambda: False)()


def install():
    applyFov(getFov())
    applyMusicVolume(getMusicVolume())
    applySfxVolume(getSfxVolume())
