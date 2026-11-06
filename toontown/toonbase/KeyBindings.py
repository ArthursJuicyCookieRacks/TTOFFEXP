"""Key bindings for the keyboard and the controller (Shticker Book Settings).

The game listens for fixed key names everywhere (w to walk, space to jump,
f8 for the book...). A binding does not change all those places: it renames
the key presses on their way in. When Jump is bound to J, a press of J
reaches the game as "space", and Space itself does nothing any more (the
same holds for -up, -repeat and shift-/control-/alt- versions). The arrow
keys always walk, whatever the bindings say; the controller and the touch
stick walk with them.

The controller's buttons each press one action's key (A jumps by pressing
the Jump key, and so on), so the controller follows the keyboard bindings
and can be set up on its own.

Saved in settings.json under "controls":
    keys: {action: key name}
    pad: {controller button: action}
    cursor-speed: 1..10 (the controller's on-screen pointer)
"""

import json
import os

from direct.directnotify import DirectNotifyGlobal

notify = DirectNotifyGlobal.directNotify.newCategory('KeyBindings')

# (action, label, the key the game itself listens for)
KEY_ACTIONS = [
    ('forward', 'Walk Forward', 'w'),
    ('reverse', 'Walk Back', 's'),
    ('turnLeft', 'Turn Left', 'a'),
    ('turnRight', 'Turn Right', 'd'),
    ('jump', 'Jump', 'space'),
    ('book', 'Shticker Book', 'f8'),
    ('friends', 'Friends List', 'f7'),
    ('tasks', 'ToonTasks', 'end'),
    ('gags', 'Gags', 'home'),
    ('map', 'Street Map', 'alt'),
    ('camera', 'Change Camera', 'tab'),
    ('chat', 'Throw Pie', 'delete'),
    ('screenshot', 'Screenshot', 'f9'),
]
DEFAULT_KEYS = dict((a, k) for a, label, k in KEY_ACTIONS)
KEY_LABELS = dict((a, label) for a, label, k in KEY_ACTIONS)
KEY_LABELS['chat'] = 'Delete (Pie / Map)'

# Controller actions: keyboard actions, plus a few the controller has of
# its own.
PAD_EXTRA = [
    ('none', 'Nothing', ()),
    ('run', 'Run (toggle)', ()),
    ('click', 'Click', ()),
    ('escape', 'Options / Back', ('escape',)),
    ('shiftEscape', 'Shift + Escape', ('shift', 'escape')),
    ('control', 'Control', ('control',)),
    ('pageUp', 'Camera Up (Page Up)', ('page_up',)),
    ('pageDown', 'Camera Down (Page Down)', ('page_down',)),
    ('marker', 'F2', ('f2',)),
]
PAD_LABELS = dict((a, KEY_LABELS[a]) for a, label, k in KEY_ACTIONS)
PAD_LABELS.update(dict((a, label) for a, label, keys in PAD_EXTRA))
PAD_EXTRA_KEYS = dict((a, keys) for a, label, keys in PAD_EXTRA)
PAD_ACTION_ORDER = ['none', 'jump', 'run', 'click', 'escape', 'shiftEscape', 'book', 'friends', 'tasks', 'gags',
                    'map', 'camera', 'chat', 'control', 'pageUp', 'pageDown', 'marker', 'screenshot']

# (button, label, default action). Matches the layout Arthur asked for.
PAD_BUTTONS = [
    ('face_a', 'A', 'jump'),
    ('face_b', 'B', 'chat'),
    ('face_x', 'X', 'map'),
    ('face_y', 'Y', 'tasks'),
    ('start', 'Start', 'escape'),
    ('back', 'Select', 'shiftEscape'),
    ('lshoulder', 'LB', 'control'),
    ('rshoulder', 'RB', 'camera'),
    ('ltrigger', 'LT', 'click'),
    ('rtrigger', 'RT', 'click'),
    ('lstick', 'L3', 'run'),
    ('rstick', 'R3', 'marker'),
    ('dpad_up', 'D-pad Up', 'pageUp'),
    ('dpad_right', 'D-pad Right', 'tasks'),
    ('dpad_left', 'D-pad Left', 'gags'),
    ('dpad_down', 'D-pad Down', 'pageDown'),
]
DEFAULT_PAD = dict((b, a) for b, label, a in PAD_BUTTONS)
PAD_BUTTON_LABELS = dict((b, label) for b, label, a in PAD_BUTTONS)

CURSOR_SPEED_DEFAULT = 5

# Keys that cannot be bound: the menus and typing need them as they are.
RESERVED = {'escape', 'enter', 'backspace', 'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right',
            'shift', 'lshift', 'rshift', 'control', 'lcontrol', 'rcontrol', 'lalt', 'ralt', 'meta',
            'lmeta', 'rmeta', 'mouse1', 'mouse2', 'mouse3', 'wheel_up', 'wheel_down', 'print_screen'}
MODIFIERS = ('shift', 'control', 'alt', 'meta')

_keys = dict(DEFAULT_KEYS)
_pad = dict(DEFAULT_PAD)
_cursorSpeed = CURSOR_SPEED_DEFAULT
# physical key -> the key the game hears ('' = nothing)
_rename = {}
# the key the game listens for -> the physical key that now gives it
_physical = {}
_installed = False


def _settingsFile():
    try:
        from otp.otpbase.Settings import Settings
        return Settings()
    except Exception:
        return None


def load():
    global _cursorSpeed
    s = _settingsFile()
    controls = s.settings.get('controls', {}) if s is not None else {}
    _keys.clear()
    _keys.update(DEFAULT_KEYS)
    for action, key in (controls.get('keys') or {}).items():
        if action in _keys and isinstance(key, str) and key:
            _keys[action] = key
    _pad.clear()
    _pad.update(DEFAULT_PAD)
    for button, action in (controls.get('pad') or {}).items():
        if button in _pad and action in PAD_LABELS:
            _pad[button] = action
    try:
        _cursorSpeed = max(1, min(10, int(controls.get('cursor-speed', CURSOR_SPEED_DEFAULT))))
    except (TypeError, ValueError):
        _cursorSpeed = CURSOR_SPEED_DEFAULT
    _rebuild()


def save():
    s = _settingsFile()
    if s is None:
        return
    controls = {'keys': dict((a, k) for a, k in _keys.items() if k != DEFAULT_KEYS[a]),
                'pad': dict((b, a) for b, a in _pad.items() if a != DEFAULT_PAD[b]),
                'cursor-speed': _cursorSpeed}
    s.settings['controls'] = controls
    try:
        with open(s.fileName, 'w+') as f:
            json.dump(s.settings, f)
    except OSError:
        notify.warning('could not save the controls')


def _rebuild():
    _rename.clear()
    _physical.clear()
    bound = {}
    for action, key in _keys.items():
        bound[key] = action
    for action, key in _keys.items():
        default = DEFAULT_KEYS[action]
        if key != default:
            _rename[key] = default
            _physical[default] = key
            # The old key no longer does this, unless it is bound to
            # something else (then that rename wins).
            if default not in bound:
                _rename.setdefault(default, '')


def getKey(action):
    return _keys.get(action, DEFAULT_KEYS.get(action))


def setKey(action, key):
    """Binds the action to key. An action that had this key gets the
    action's old key (the two swap), so no key is ever bound twice."""
    old = _keys[action]
    for other, k in _keys.items():
        if other != action and k == key:
            _keys[other] = old
    _keys[action] = key
    _rebuild()
    save()


def resetKeys():
    _keys.clear()
    _keys.update(DEFAULT_KEYS)
    _rebuild()
    save()


def getPad(button):
    return _pad.get(button, DEFAULT_PAD.get(button))


def setPad(button, action):
    _pad[button] = action
    save()


def resetPad():
    _pad.clear()
    _pad.update(DEFAULT_PAD)
    save()


def getCursorSpeed():
    return _cursorSpeed


def setCursorSpeed(level):
    global _cursorSpeed
    _cursorSpeed = max(1, min(10, int(level)))
    save()


def cursorSpeedFactor():
    # 5 is the speed the pointer always had; 1 is a fifth of it, 10 double.
    return _cursorSpeed / 5.0


def padKeys(button):
    """The game keys the controller button presses (already turned into
    the physical keys, so the renaming gives back the game's keys)."""
    action = getPad(button)
    if action in DEFAULT_KEYS:
        keys = (DEFAULT_KEYS[action],)
    else:
        keys = PAD_EXTRA_KEYS.get(action, ())
    return tuple(physical(k) for k in keys)


def physical(gameKey):
    return _physical.get(gameKey, gameKey)


def forwardKeys():
    # The events the game hears for Walk Forward. A rebound key reaches the
    # game already renamed to 'w' (processEvent below), so listening for
    # the physical key (as this did) heard nothing once Walk Forward was
    # moved off W, and a double tap never sprinted.
    return {'arrow_up', 'w'}


def keyLabel(key):
    if not key:
        return '-'
    names = {'space': 'Space', 'arrow_up': 'Up', 'arrow_down': 'Down', 'arrow_left': 'Left',
             'arrow_right': 'Right', 'page_up': 'Page Up', 'page_down': 'Page Down', 'delete': 'Delete',
             'insert': 'Insert', 'home': 'Home', 'end': 'End', 'tab': 'Tab', 'alt': 'Alt'}
    if key in names:
        return names[key]
    return key.upper() if len(key) <= 3 else key.replace('_', ' ').title()


def translate(name):
    """The event name the game should hear for a raw key event, or None to
    leave it as it is ('' drops it)."""
    if not _rename or not name:
        return None
    suffix = ''
    base_ = name
    for end in ('-up', '-repeat'):
        if base_.endswith(end) and len(base_) > len(end):
            suffix = end
            base_ = base_[:-len(end)]
            break
    mods = []
    parts = base_.split('-')
    while len(parts) > 1 and parts[0] in MODIFIERS:
        mods.append(parts.pop(0))
    key = '-'.join(parts)
    if key not in _rename:
        return None
    new = _rename[key]
    if not new:
        return ''
    return '-'.join(mods + [new]) + suffix


# Survival Mode has keys of its own: the game's bindings rest while it runs.
_suspended = False


def setSuspended(on):
    global _suspended
    _suspended = bool(on)


def install():
    """Renames the key events on their way to the game."""
    global _installed
    load()
    if _installed:
        return
    _installed = True
    mgr = base.eventMgr
    original = mgr.processEvent

    def processEvent(event):
        if _rename and event.name and not _suspended:
            new = translate(event.name)
            if new is not None:
                if new:
                    params = [mgr.parseEventParameter(event.getParameter(i)) for i in range(event.getNumParameters())]
                    messenger.send(new, params)
                return
        return original(event)

    mgr.processEvent = processEvent
    if getattr(mgr, 'processEventPstats', None) is not None:
        mgr.processEventPstats = processEvent
