"""Field of view and volume, set from the Shticker Book's Settings page.

Saved in settings.json under "game": "fov" (degrees), "music-volume" and
"sfx-volume" (0..100). These are separate from the old "music-vol" and
"sfx-vol" keys, which set Panda's master volume before the window opens.
"""

from direct.directnotify import DirectNotifyGlobal

notify = DirectNotifyGlobal.directNotify.newCategory('GameSettings')

FOV_DEFAULT = 52
FOV_MIN = 40
FOV_MAX = 100
MUSIC_BASE = 0.65
VOLUME_DEFAULT = 100


def _settings():
    display = getattr(base, 'display', None)
    return getattr(display, 'settings', None)


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


def install():
    applyFov(getFov())
    applyMusicVolume(getMusicVolume())
    applySfxVolume(getSfxVolume())
