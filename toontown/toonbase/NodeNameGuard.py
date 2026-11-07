"""Keeps a model that is already gone from closing the game when it is renamed.

Every model in the game (a toon, a cog, a doodle, a GUI frame...) is a
NodePath, and `thing.name` is the name of its node. Once the model is taken
off the screen for good (removeNode, or delete()), the node is gone and the
NodePath is empty. Setting or reading `name` then fails a Panda3D check
(nodePath.I: !is_empty()). On a computer that is a Python AssertionError; on
Android, Panda3D used to close the app on the spot (see
tools/offline/panda3d-patches/android-assert-no-abort.patch), with nothing in
the log to say which piece of the game did it.

install() gives every Python class built on NodePath a `name` that does what
Panda3D's own does while the model is there. On a model that is gone, a new
name is not kept (there is no node to keep it on) and reading the name gives
'': both are written to the log once, with where in the game they came from,
so the cause can be fixed where it is.
"""

import sys
import traceback

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import NodePath

notify = DirectNotifyGlobal.directNotify.newCategory('NodeNameGuard')

TASK_NAME = 'nodeNameGuard'
# Classes made after install() (modules the game only imports later) get the
# guard on the next check.
CHECK_EVERY = 2.0
_HEAPTYPE = 1 << 9

_getName = NodePath.getName
_setName = NodePath.setName
_isEmpty = NodePath.isEmpty
_reported = set()
_guarded = set()


def _report(what, obj):
    stack = traceback.extract_stack()[:-2]
    where = tuple((frame.filename, frame.lineno) for frame in stack[-3:])
    if where in _reported:
        return
    _reported.add(where)
    notify.warning('%s the name of a %s that is gone (removed or deleted):\n%s' % (
        what, obj.__class__.__name__, ''.join(traceback.format_list(stack[-8:]))))


def _get(self):
    if _isEmpty(self):
        _report('read', self)
        return ''
    return _getName(self)


def _set(self, name):
    if _isEmpty(self):
        _report('set', self)
        return
    _setName(self, name)


_property = property(_get, _set, doc='The name of the node (see NodeNameGuard).')


def guardClasses():
    """Puts the guard on every Python class made straight from NodePath
    (the ones made from those get it from them)."""
    for cls in NodePath.__subclasses__():
        if cls in _guarded:
            continue
        _guarded.add(cls)
        if not cls.__flags__ & _HEAPTYPE:
            # Panda3D's own C++ classes: never empty-renamed by the game.
            continue
        mro = cls.__mro__
        if any('name' in base.__dict__ for base in mro[:mro.index(NodePath)]):
            # The class (or one it is made from) has a name of its own.
            continue
        try:
            cls.name = _property
        except (TypeError, AttributeError):
            pass
    return len(_guarded)


def _check(task):
    guardClasses()
    return task.again


def install():
    guardClasses()
    if 'taskMgr' in sys.modules['builtins'].__dict__:
        taskMgr.remove(TASK_NAME)
        taskMgr.doMethodLater(CHECK_EVERY, _check, TASK_NAME)
