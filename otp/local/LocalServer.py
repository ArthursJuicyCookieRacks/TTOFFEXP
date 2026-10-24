import atexit
import builtins
import json
import os
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from direct.showbase import DConfig as config
from panda3d.core import Filename, ConfigVariableList
from panda3d.direct import DCFile

from otp.local import ExecutionContext
from otp.local.LocalClientAgent import LocalClientAgent
from otp.local.LocalConnection import LocalClientConnection, LocalInternalConnection
from otp.local.LocalDatabase import LocalDatabaseServer, YAMLBackend
from otp.local.LocalMessageDirector import LocalMessageDirector
from otp.local.LocalSimBase import LocalSimBase
from otp.local.LocalStateServer import LocalStateServer
from otp.local import PySmoothNodeBase

# The UberDOG global objects astrond knew about (astron/config/astrond-*.yml):
# (doId, class name, whether clients may talk to it before logging in)
UBERDOGS = [
    (4688, 'CentralLogger', False),
    (4665, 'ClientServicesManager', True),
    (4681, 'ChatAgent', False),
    (4501, 'FriendManager', False),
    (4686, 'AvatarFriendsManager', False),
    (4687, 'PlayerFriendsManager', False),
    (4666, 'TTRFriendsManager', False),
    (4712, 'TTSpeedchatRelay', False),
    (4683, 'DistributedDeliveryManager', False),
    (4695, 'TTCodeRedemptionMgr', False),
    (4477, 'GlobalPartyManager', False),
]

STATESERVER_CONTROL = 4002
DATABASE_CONTROL = 4003
DATABASE_MIN_ID = 100000000
DATABASE_MAX_ID = 399999999
CLIENT_MIN_CHANNEL = 1000000000
CLIENT_MAX_CHANNEL = 1009999999
UBERDOG_BASE_CHANNEL = 1000000
AI_BASE_CHANNEL = 420000000
AI_CHANNEL_SPACING = 1000000

instance = None


class ServerGame:

    def __init__(self, name):
        self.name = name
        self.process = 'server'


class LocalEventLogger:
    """
    Writes server events (what astrond's Event Logger used to receive) to
    logs/events/events-<date>.jsonl, one JSON object per line.
    """

    def __init__(self, directory):
        self.file = None
        if not directory:
            return
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, time.strftime('events-%y%m%d_%H%M%S.jsonl'))
        self.file = open(path, 'a')

    def write(self, event):
        if self.file is None:
            return
        try:
            self.file.write(json.dumps(event, default=repr) + '\n')
            self.file.flush()
        except Exception:
            pass

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None


class LocalServer:
    """
    Runs the whole Toontown server side inside the game process: the local
    Astron roles, the UberDOG and the AI districts. Call start() once the
    client's ShowBase exists; 'localServerReady' is sent when logging in is
    possible.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalServer')

    def __init__(self):
        global instance
        if instance is not None:
            raise RuntimeError('Only one LocalServer can run at a time.')
        instance = self

        self.contexts = ExecutionContext.install()
        PySmoothNodeBase.install()
        self.catchExceptions = config.ConfigVariableBool('local-server-catch-exceptions', True).getValue()
        self.started = False
        self.ready = False
        self.servers = []
        self.uberdog = None
        self.districts = []

        self.dcFile = DCFile()
        for dcFileName in ConfigVariableList('dc-file'):
            if not self.dcFile.read(Filename.fromOsSpecific(dcFileName)):
                self.notify.error('Could not read DC file %s.' % dcFileName)

        self.md = LocalMessageDirector(trace=config.ConfigVariableBool('local-md-trace', False).getValue())
        dbDirectory = config.ConfigVariableString('local-db-directory', 'astron/databases/astrondb').getValue()
        self.database = YAMLBackend(self.dcFile, dbDirectory, DATABASE_MIN_ID, DATABASE_MAX_ID)
        self.databaseServer = LocalDatabaseServer(self.md, self.dcFile, self.database, DATABASE_CONTROL)
        self.stateServer = LocalStateServer(self.md, self.dcFile, STATESERVER_CONTROL, self.database,
                                            DATABASE_MIN_ID, DATABASE_MAX_ID)
        self.clientAgent = LocalClientAgent(
            self.md, self.dcFile, self.stateServer, UBERDOGS, CLIENT_MIN_CHANNEL, CLIENT_MAX_CHANNEL,
            version=config.ConfigVariableString('server-version', '').getValue(),
            strict=config.ConfigVariableBool('local-ca-strict', False).getValue())
        self.eventLogger = LocalEventLogger(config.ConfigVariableString('local-event-log-directory', 'logs/events').getValue())

        atexit.register(self.shutdown)

    # Startup:

    def start(self):
        if self.started:
            return
        self.started = True
        self.loader = builtins.loader

        # Panda3D won't poll one task manager from inside another's task, so
        # the servers run between the client's frames instead of in a task.
        clientTaskMgr = self.contexts.client.taskMgr
        clientStep = clientTaskMgr.step

        def step():
            clientStep()
            self.step()

        clientTaskMgr.step = step

        self.notify.info('Starting the UberDOG...')
        self.uberdog = self.startUberDog()

        names = config.ConfigVariableString('local-districts', 'Developers Dreams').getValue()
        for index, name in enumerate([n.strip() for n in names.split(',') if n.strip()]):
            self.notify.info('Starting the AI for %s...' % name)
            self.districts.append(self.startDistrict(index, name))

        self.flush()
        self.ready = True
        self.notify.info('Server now ready. Have fun on Toontown Rewritten Offline!')
        messenger.send('localServerReady')

    def createServer(self, name, gameName):
        context = ExecutionContext.createServerContext(name, {})
        simbase = LocalSimBase(context, self.loader)
        context.builtinsOverlay.update({
            'simbase': simbase,
            'game': ServerGame(gameName),
            'base': ExecutionContext._REMOVED,
            'localAvatar': ExecutionContext._REMOVED,
            'hidden': simbase.hidden,
            'bboard': simbase.bboard,
            'jobMgr': simbase.jobMgr,
        })
        return context, simbase

    def startUberDog(self):
        context, simbase = self.createServer('uberdog', 'uberDog')
        with self.contexts.use(context):
            from toontown.uberdog.ToontownUberRepository import ToontownUberRepository
            simbase.air = ToontownUberRepository(UBERDOG_BASE_CHANNEL, STATESERVER_CONTROL)
            simbase.air.connect('local')
        self.servers.append((context, simbase))
        return simbase.air

    def startDistrict(self, index, name):
        context, simbase = self.createServer('ai-%d' % index, 'toontown')
        with self.contexts.use(context):
            from toontown.ai.ToontownAIRepository import ToontownAIRepository
            simbase.air = ToontownAIRepository(AI_BASE_CHANNEL + index * AI_CHANNEL_SPACING,
                                               STATESERVER_CONTROL, name)
            simbase.air.connect('local')
        self.servers.append((context, simbase))
        self.flush()
        return simbase.air

    # Connections:

    def connectInternal(self, repository):
        return LocalInternalConnection(self.md)

    def connectClient(self):
        return LocalClientConnection(self.clientAgent)

    # Running:

    def flush(self, maxRounds=64):
        """
        Delivers everything in flight between the local roles and the server
        repositories, without running any of their other tasks.
        """
        for _ in range(maxRounds):
            delivered = self.md.flush()
            for context, simbase in self.servers:
                air = simbase.air
                if air is not None and air.isLocal() and air._localConn.inbox:
                    with self.contexts.use(context):
                        while air.readerPollOnce():
                            delivered += 1
            if not delivered:
                break

    def step(self):
        self.flush()
        for context, simbase in self.servers:
            with self.contexts.use(context):
                try:
                    context.taskMgr.mgr.poll()
                    context.ivalMgr.step()
                except Exception:
                    if not self.catchExceptions:
                        raise
                    self.reportException(context)
        self.flush()
        self.database.update()

    def reportException(self, context):
        self.notify.warning('INTERNAL-EXCEPTION in %s:\n%s' % (context.name, traceback.format_exc()))

    def handleRepositoryException(self, repository):
        """
        Called by server repositories when a message handler raises. Like the
        separate AI and UberDOG processes did, log it and keep running.
        """
        if not self.catchExceptions:
            return False
        self.notify.warning('INTERNAL-EXCEPTION in %s:\n%s' % (self.contexts.current.name, traceback.format_exc()))
        return True

    def writeServerEvent(self, sender, logtype, args, kwargs):
        event = {'type': logtype, 'sender': sender, 'time': time.time()}
        for i, value in enumerate(args):
            event['_%d' % (i + 1)] = value
        event.update(kwargs)
        self.eventLogger.write(event)

    def shutdown(self):
        try:
            self.database.flush()
        except Exception:
            self.notify.warning('Could not save the database:\n%s' % traceback.format_exc())
        self.eventLogger.close()


def getInstance():
    return instance
