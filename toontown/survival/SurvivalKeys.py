"""Survival Mode's own key bindings (pause menu > Settings > Key Bindings).

Survival listens for its own keys (the BO1 layout in SurvivalPlayer), not
the regular game's, so it keeps its own bindings, saved in settings.json
under "survival" > "keys" as {name: key}. Each action has one key the
player picks; the arrow keys always walk, the mouse wheel always swaps gags
and the right mouse button always bonks too. Binding a key another action
has gives that action the old key (the two swap), so no key does two things.
"""

# (name, label, default key). name is a SurvivalPlayer KEYS token or ACTIONS action.
BINDABLE = [
    ('forward', 'Walk Forward', 'w'),
    ('reverse', 'Walk Back', 's'),
    ('slideLeft', 'Walk Left', 'a'),
    ('slideRight', 'Walk Right', 'd'),
    ('jump', 'Jump', 'space'),
    ('sprint', 'Sprint', 'shift'),
    ('fire', 'Throw Gag', 'mouse1'),
    ('reload', 'Reload', 'r'),
    ('use', 'Use', 'e'),
    ('swap', 'Swap Gags', 'tab'),
    ('gag1', 'Gag 1', '1'),
    ('gag2', 'Gag 2', '2'),
    ('gag3', 'Gag 3', '3'),
    ('bonk', 'Bonk', 'v'),
    ('tnt', 'TNT', 'g'),
    ('grenade', 'Presentation', 'q'),
    # A big map's Rakes and Marbles (BO1's Claymores and Bouncing Betties).
    ('trap', 'Rakes / Marbles', '4'),
    ('pause', 'Pause', 'escape'),
]
DEFAULTS = dict((name, key) for name, label, key in BINDABLE)
LABELS = dict((name, label) for name, label, key in BINDABLE)
# Keys that always do their action as well as the chosen one.
EXTRAS = {
    'forward': ('arrow_up',),
    'reverse': ('arrow_down',),
    'slideLeft': ('arrow_left',),
    'slideRight': ('arrow_right',),
    'swap': ('wheel_up', 'wheel_down'),
    'bonk': ('mouse3',),
    # Esc always pauses, whatever else is picked.
    'pause': ('escape',),
}
# Use also answers to F while it is on E (as before there were bindings).
DEFAULT_EXTRAS = {'use': ('f',)}
# A modifier key sends its left/right name as well as its own.
MODIFIER_NAMES = {'shift': ('shift', 'lshift', 'rshift'), 'control': ('control', 'lcontrol', 'rcontrol'),
                  'alt': ('alt', 'lalt', 'ralt')}
NORMALIZE = {'lshift': 'shift', 'rshift': 'shift', 'lcontrol': 'control', 'rcontrol': 'control', 'lalt': 'alt',
             'ralt': 'alt'}
# Never bindable: the walk arrows (always walk) and keys the game itself needs.
RESERVED = {'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right', 'wheel_up', 'wheel_down', 'mouse3', 'enter'}
SETTING = ('survival', 'keys')

_keys = None


def load():
    global _keys
    _keys = dict(DEFAULTS)
    try:
        saved = base.settings.settings.getOption(SETTING[0], SETTING[1], {}) or {}
    except Exception:
        saved = {}
    if isinstance(saved, dict):
        for name, key in saved.items():
            if name in DEFAULTS and isinstance(key, str) and key:
                _keys[name] = key
    return _keys


def save():
    try:
        base.settings.settings.updateSetting(SETTING[0], SETTING[1], dict(_keys))
    except Exception:
        pass


def getKey(name):
    if _keys is None:
        load()
    return _keys.get(name, DEFAULTS[name])


def setKey(name, key):
    """Binds name to key; whatever had key gets name's old key."""
    if _keys is None:
        load()
    key = NORMALIZE.get(key, key)
    old = _keys[name]
    for other, k in list(_keys.items()):
        if other != name and k == key:
            _keys[other] = old
    _keys[name] = key
    save()


def resetKeys():
    global _keys
    _keys = dict(DEFAULTS)
    save()


def keysFor(name):
    """Every key event name that does this action."""
    key = getKey(name)
    keys = list(MODIFIER_NAMES.get(key, (key,)))
    extras = EXTRAS.get(name, ())
    if key == DEFAULTS[name]:
        extras = extras + DEFAULT_EXTRAS.get(name, ())
    taken = set(getKey(other) for other in DEFAULTS if other != name)
    for extra in extras:
        if extra not in keys and extra not in taken:
            keys.append(extra)
    return tuple(keys)


def label(key):
    names = {'space': 'Space', 'mouse1': 'Left Click', 'mouse2': 'Middle Click', 'mouse3': 'Right Click',
             'escape': 'Esc', 'tab': 'Tab', 'shift': 'Shift', 'control': 'Ctrl', 'alt': 'Alt',
             'backspace': 'Backspace', 'delete': 'Delete', 'insert': 'Insert', 'home': 'Home', 'end': 'End',
             'page_up': 'Page Up', 'page_down': 'Page Down', 'caps_lock': 'Caps Lock'}
    if key in names:
        return names[key]
    return key.upper() if len(key) <= 3 else key.replace('_', ' ').title()
