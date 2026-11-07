"""Typing with a phone's keyboard, into every text box of the game.

On Android, Panda's window turns what the system keyboard types into typed
keys, the same keys a computer's keyboard gives (see
tools/offline/panda3d-patches/android-text-input.patch): letters, backspace
and Enter go straight into whichever DirectEntry has the focus, which
handles them exactly as it does on a computer (the cursor, the length
limit, its own command on Enter, the chat's filter). Nothing here copies
any text.

All this module does is bring the keyboard up and put it away: it is up
while a text box that can be seen has the focus, so every DirectEntry gets
it without asking. Tapping a box brings the keyboard back after the player
put it away with the back button.
"""

import sys
import weakref

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.showbase.DirectObject import DirectObject

notify = DirectNotifyGlobal.directNotify.newCategory('AndroidKeyboard')

TASK_NAME = 'androidKeyboard'

# The roots of what is on the screen; a box under anything else (hidden,
# or not parented yet) is not on it.
SHOWN_ROOTS = ('render2d', 'render2dp')

_support = None
_installed = False
# id -> (weak reference to the box, its press event).
_entries = {}
_listener = DirectObject()
# The keyboard is up (as far as the game asked); the box it is up for; the
# box whose keyboard the player put away.
_shown = False
_owner = None
_dismissed = None


def _androidSupport():
    global _support
    if _support is None:
        if sys.platform != 'android':
            _support = False
        else:
            try:
                import android_support
            except ImportError:
                android_support = None
            if android_support is not None and hasattr(android_support, 'show_keyboard'):
                _support = android_support
            else:
                _support = False
    return _support or None


def available():
    return _androidSupport() is not None


def install(support=None):
    """Watches every text box from now on. support stands in for Android's
    android_support module (for tests on a computer)."""
    global _installed, _support
    if support is not None:
        _support = support
    if _installed or not available():
        return
    _installed = True
    from direct.gui.DirectEntry import DirectEntry
    originalInit = DirectEntry.__init__

    def __init__(self, *args, **kw):
        originalInit(self, *args, **kw)
        _watch(self)

    # Only the boxes made from now on are known, so this is installed as the
    # game starts, before any box is made.
    DirectEntry.__init__ = __init__
    taskMgr.add(_update, TASK_NAME, sort=-45)


def _watch(entry):
    ref = weakref.ref(entry)
    event = DGG.B1PRESS + entry.guiId
    _entries[id(entry)] = (ref, event)
    # The press event can come before the box takes the focus; the next
    # frame sees the focus either way.
    _listener.accept(event, _tapped, [ref])


def _tapped(ref, *args):
    global _dismissed
    entry = ref()
    if entry is None:
        return
    # A tap on a box asks for the keyboard again, even if the player put it
    # away, or the keyboard's own button hid it.
    _dismissed = None
    if _owner is entry and _focused(entry):
        _show(True, force=True)


def _visible(entry):
    if entry.isEmpty() or entry.isHidden():
        return False
    node = entry
    while not node.isEmpty():
        if node.isStashed():
            return False
        top = node
        node = node.getParent()
    return top.getName() in SHOWN_ROOTS


def _focused(entry):
    item = getattr(entry, 'guiItem', None)
    if item is None or entry.isEmpty():
        return False
    try:
        return item.getFocus() and item.getActive() and _visible(entry)
    except Exception:
        return False


def _focusedEntry():
    found = None
    for key, (ref, event) in list(_entries.items()):
        entry = ref()
        if entry is None or getattr(entry, 'guiItem', None) is None or entry.isEmpty():
            # Destroyed.
            del _entries[key]
            _listener.ignore(event)
            continue
        if found is None and _focused(entry):
            found = entry
    return found


def _show(show, force=False):
    global _shown
    if show == _shown and not force:
        return
    _shown = show
    try:
        _androidSupport().show_keyboard(show)
    except Exception as e:
        notify.warning('could not %s the keyboard: %r' % ('show' if show else 'hide', e))


def _update(task):
    global _owner, _dismissed, _shown
    support = _androidSupport()
    entry = _focusedEntry()
    # Only the keyboard's own back button sends news, so with no keyboard up
    # and no box wanting one there is nothing to ask Android each frame.
    while _shown or entry is not None:
        try:
            news = support.poll_keyboard()
        except Exception:
            news = ''
        if not news:
            break
        if news.startswith('C:'):
            # The player put the keyboard away (the back button): it stays
            # away for this box until the box is tapped.
            _dismissed = entry if entry is not None else _owner
            _shown = False
    if entry is not _owner:
        _owner = entry
        if entry is not _dismissed:
            _dismissed = None
    _show(entry is not None and entry is not _dismissed)
    return task.cont


def isActive():
    return _shown


def stop(quiet=False):
    """Puts the keyboard away now (it comes back if a box that can be seen
    still has the focus)."""
    if available() and _shown:
        _show(False)
