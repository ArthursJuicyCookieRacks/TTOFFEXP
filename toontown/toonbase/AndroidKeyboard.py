"""Typing into the game's own text boxes with a phone's keyboard.

The game's window takes no typing from an on-screen keyboard, so on Android
the system keyboard types into an invisible text field of the activity's
(see tools/offline/panda3d-patches/android-text-input.patch). While it is up,
what it holds is copied into the game's DirectEntry every frame, so the
player sees their words where they would on a computer, with no box of
Android's over the game. It goes the other way too: if the entry changes
some other way (a key that reached the game's window, such as the
keyboard's backspace while the field had lost the focus), the field is
given the entry's text, or the next letter typed would bring back what
the entry no longer holds.
"""

import time

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
    # last: the text both sides last agreed on; seen: whether this time's
    # "E:" has been read yet (an older build's keyboard set it a moment
    # late, so the last time's "S:" or "C:" could be read first); pushed:
    # when the field was last given the entry's text.
    _current = (entry, onSend, onClose, onChange, {'last': entry.get(plain=True), 'seen': False, 'pushed': None, 'pushes': []})
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


def _push(state, text):
    """Gives the keyboard's field the entry's text."""
    import android_support
    now = time.time()
    state['pushes'] = [t for t in state['pushes'] if now - t < 1.0] + [now]
    if len(state['pushes']) > 8:
        # The two keep disagreeing (the entry can't hold what the field
        # does): the field wins, as it did before.
        return False
    try:
        if hasattr(android_support, 'set_typed_text'):
            android_support.set_typed_text(text)
        else:
            android_support.ask_text('', text, ANDROID_KEEP_LENGTH)
    except Exception as e:
        notify.warning('could not give the keyboard the text: %r' % e)
        return False
    state['last'] = text
    state['pushed'] = (text, now)
    return True


# ask_text with 0 keeps no length limit; only an older build needs it.
ANDROID_KEEP_LENGTH = 0


def _poll(task):
    global _current
    if _current is None:
        return task.done
    entry, onSend, onClose, onChange, state = _current
    import android_support
    if entry.isEmpty():
        stop(quiet=True)
        return task.done
    typed = android_support.typed_text() or 'E:'
    kind, text = typed[:2], typed[2:]
    if kind == 'E:':
        state['seen'] = True
    elif not state['seen']:
        # The last time's ending, read before this time's start.
        return task.cont
    shown = entry.get(plain=True)
    if kind == 'E:' and shown != state['last']:
        # The entry changed without the field: the field follows it.
        if _push(state, shown):
            if onChange:
                onChange(shown)
            return task.cont
    pushed = state['pushed']
    if pushed is not None:
        if text == pushed[0] or time.time() - pushed[1] > 0.5 or kind != 'E:':
            state['pushed'] = None
        else:
            # The field has not taken the pushed text yet.
            return task.cont
    if text != state['last'] or text != shown:
        state['last'] = text
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
