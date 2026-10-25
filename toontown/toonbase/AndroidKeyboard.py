"""Typing into the game's own text boxes with a phone's keyboard.

The game's window takes no typing from an on-screen keyboard, so on Android
the system keyboard types into an invisible text field of the activity's
(see tools/offline/panda3d-patches/android-text-input.patch). While it is up,
what it holds is copied into the game's DirectEntry every frame, so the
player sees their words where they would on a computer, with no box of
Android's over the game.
"""

import sys

from direct.directnotify import DirectNotifyGlobal

notify = DirectNotifyGlobal.directNotify.newCategory('AndroidKeyboard')

TASK_NAME = 'androidKeyboard'

_current = None


def available():
    if sys.platform != 'android':
        return False
    try:
        import android_support
    except ImportError:
        return False
    return hasattr(android_support, 'ask_text')


def start(entry, maxLength=0, onSend=None, onClose=None, onChange=None):
    """Brings up the keyboard to type into entry. onSend(text) is called when
    the keyboard's send key is pressed, onClose(text) when the keyboard is
    put away, and onChange(text) as the text changes. Returns whether the
    keyboard came up."""
    global _current
    if not available():
        return False
    import android_support
    stop(quiet=True)
    try:
        android_support.ask_text('', entry.get(plain=True), maxLength)
    except (AttributeError, NotImplementedError, TypeError) as e:
        notify.warning('no Android keyboard: %r' % e)
        return False
    _current = (entry, onSend, onClose, onChange, [entry.get(plain=True)])
    taskMgr.remove(TASK_NAME)
    taskMgr.add(_poll, TASK_NAME)
    return True


def stop(quiet=False):
    """Puts the keyboard away without sending."""
    global _current
    taskMgr.remove(TASK_NAME)
    if _current is None:
        return
    _current = None
    try:
        import android_support
        android_support.ask_text('', '', -1)
    except Exception:
        if not quiet:
            notify.warning('could not put the keyboard away')


def isActive():
    return _current is not None


def _poll(task):
    global _current
    if _current is None:
        return task.done
    entry, onSend, onClose, onChange, last = _current
    import android_support
    state = android_support.typed_text() or 'E:'
    kind, text = state[:2], state[2:]
    if entry.isEmpty():
        stop(quiet=True)
        return task.done
    if text != last[0]:
        last[0] = text
        entry.enterText(text)
        if onChange:
            onChange(text)
    if kind == 'S:':
        _current = None
        if onSend:
            onSend(text)
        return task.done
    if kind == 'C:':
        _current = None
        if onClose:
            onClose(text)
        return task.done
    return task.cont
