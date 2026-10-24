"""
Lets the client, the UberDOG and each AI district share one Python process.

When they ran as separate processes, each had its own messenger, task
manager, interval manager and builtins (base on the client, simbase on the
servers). Their event names, task names and interval names overlap all the
time (they are often built from the same doId), so in one process they must
stay apart.

Panda3D modules capture `messenger`, `taskMgr` and `ivalMgr` at import time,
so install() replaces those globals with facades that forward to whichever
ExecutionContext is current. The client context uses the real global objects;
every server context gets its own. Server code only ever runs inside its own
context: its datagrams, tasks and intervals are all driven from
LocalServer.step(), which enters the context first.

install() must run before ShowBase (or anything else from direct) is imported.
"""

import builtins
import contextlib

_REMOVED = object()


class ContextManager:

    def __init__(self, clientContext):
        self.client = clientContext
        self.current = clientContext
        self.contexts = [clientContext]
        self.broadcastCppEvents = 0

    def addContext(self, context):
        self.contexts.append(context)

    def removeContext(self, context):
        if context in self.contexts:
            self.contexts.remove(context)

    def switch(self, context):
        """
        Makes `context` current and returns the previous one.
        """
        previous = self.current
        if context is previous:
            return previous
        if previous is not self.client:
            previous.leave()
            self.current = self.client
        if context is not self.client:
            context.enter()
            self.current = context
        return previous

    @contextlib.contextmanager
    def use(self, context):
        previous = self.switch(context)
        try:
            yield context
        finally:
            self.switch(previous)


class ExecutionContext:
    """
    One "process": its messenger, task manager, interval manager and the
    builtins it expects (as name -> value, or _REMOVED to hide a name).
    """

    def __init__(self, name, messenger, taskMgr, ivalMgr, builtinsOverlay=None):
        self.name = name
        self.messenger = messenger
        self.taskMgr = taskMgr
        self.ivalMgr = ivalMgr
        self.builtinsOverlay = builtinsOverlay or {}
        self._saved = {}

    def enter(self):
        self._saved = {}
        for name, value in self.builtinsOverlay.items():
            self._saved[name] = builtins.__dict__.get(name, _REMOVED)
            if value is _REMOVED:
                builtins.__dict__.pop(name, None)
            else:
                builtins.__dict__[name] = value

    def leave(self):
        for name, value in self._saved.items():
            if name in self.builtinsOverlay and self.builtinsOverlay[name] is not _REMOVED:
                # Keep anything server code stored in its own builtins.
                current = builtins.__dict__.get(name, _REMOVED)
                if current is not _REMOVED:
                    self.builtinsOverlay[name] = current
            if value is _REMOVED:
                builtins.__dict__.pop(name, None)
            else:
                builtins.__dict__[name] = value
        self._saved = {}

    def __repr__(self):
        return '<ExecutionContext %s>' % self.name


class _Facade:
    """
    Forwards every attribute to the current context's object.
    """
    __slots__ = ('_attr',)

    def __init__(self, attr):
        object.__setattr__(self, '_attr', attr)

    def _target(self):
        return getattr(contexts.current, object.__getattribute__(self, '_attr'))

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        setattr(self._target(), name, value)

    def __delattr__(self, name):
        delattr(self._target(), name)

    def __repr__(self):
        return '<%s facade for %r>' % (object.__getattribute__(self, '_attr'), self._target())


class MessengerFacade(_Facade):
    __slots__ = ()

    def send(self, event, sentArgs=[], taskChain=None):
        if contexts.broadcastCppEvents and contexts.current is contexts.client:
            # C++ events (window, collision, ...) are global: deliver them to
            # every context that listens for them.
            for context in list(contexts.contexts):
                if context is contexts.client or context.messenger.whoAccepts(event):
                    with contexts.use(context):
                        context.messenger.send(event, sentArgs, taskChain)
            return
        self._target().send(event, sentArgs, taskChain)


class IntervalManagerFacade(_Facade):
    __slots__ = ()

    def addInterval(self, interval):
        manager = self._target()
        if contexts.current is not contexts.client and hasattr(interval, 'setManager'):
            # Make sure the interval keeps reporting to this context's manager.
            interval.setManager(manager)
        manager.addInterval(interval)


contexts = None


def install():
    """
    Replaces direct's messenger, taskMgr and ivalMgr globals with facades.
    Safe to call more than once.
    """
    global contexts
    if contexts is not None:
        return contexts

    from direct.showbase import MessengerGlobal
    realMessenger = MessengerGlobal.messenger
    messengerFacade = MessengerFacade('messenger')
    MessengerGlobal.messenger = messengerFacade

    from direct.task import TaskManagerGlobal
    realTaskMgr = TaskManagerGlobal.taskMgr
    taskMgrFacade = _Facade('taskMgr')
    TaskManagerGlobal.taskMgr = taskMgrFacade

    from direct.interval import IntervalManager
    realIvalMgr = IntervalManager.ivalMgr
    ivalMgrFacade = IntervalManagerFacade('ivalMgr')
    IntervalManager.ivalMgr = ivalMgrFacade

    # Modules that were imported along the way captured the real objects:
    import sys
    for module in list(sys.modules.values()):
        moduleDict = getattr(module, '__dict__', None)
        if not moduleDict or module is IntervalManager or module is MessengerGlobal \
                or module is TaskManagerGlobal or moduleDict.get('__name__') == __name__:
            continue
        if moduleDict.get('messenger') is realMessenger:
            moduleDict['messenger'] = messengerFacade
        if moduleDict.get('taskMgr') is realTaskMgr:
            moduleDict['taskMgr'] = taskMgrFacade
        if moduleDict.get('ivalMgr') is realIvalMgr:
            moduleDict['ivalMgr'] = ivalMgrFacade

    contexts = ContextManager(ExecutionContext('client', realMessenger, realTaskMgr, realIvalMgr))

    # C++ events arrive through the global event manager on the client.
    from direct.showbase import EventManagerGlobal
    eventMgr = EventManagerGlobal.eventMgr

    def wrap(method):
        def processGlobalEvent(event):
            contexts.broadcastCppEvents += 1
            try:
                return method(event)
            finally:
                contexts.broadcastCppEvents -= 1
        return processGlobalEvent

    eventMgr.processEvent = wrap(eventMgr.processEvent)
    eventMgr.processEventPstats = wrap(eventMgr.processEventPstats)
    return contexts


def createServerContext(name, builtinsOverlay):
    """
    Creates a context with its own messenger, task manager and interval
    manager, sharing the global clock.
    """
    from panda3d.core import AsyncTaskManager, ClockObject
    from direct.showbase.Messenger import Messenger
    from direct.task import Task
    from direct.interval.IntervalManager import IntervalManager

    taskMgr = Task.TaskManager()
    taskMgr.mgr = AsyncTaskManager(name)
    taskMgr.setClock(ClockObject.getGlobalClock())

    context = ExecutionContext(name, Messenger(), taskMgr, IntervalManager(), builtinsOverlay)
    contexts.addContext(context)
    return context


def getClientBuiltin(name, default=None):
    """
    What the client has under a builtin name (base, localAvatar), from
    whichever context is current. Only for code that knows the client shares
    its process, like the offline game's NPC players.
    """
    if contexts is None or contexts.current is contexts.client:
        value = builtins.__dict__.get(name, _REMOVED)
    else:
        value = contexts.current._saved.get(name, _REMOVED)
    return default if value is _REMOVED else value
