import collections

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from panda3d.core import Datagram

from otp.local.LocalMessageDirector import MDParticipant


class LocalInternalConnection(MDParticipant):
    """
    Connects an AstronInternalRepository (the UberDOG or an AI) straight to
    the LocalMessageDirector. Replaces its TCP connection to astrond.
    """

    def __init__(self, md):
        MDParticipant.__init__(self, md)
        self.inbox = collections.deque()
        self.connected = True

    def handleDatagram(self, dg, channels, sender, msgType, di):
        self.inbox.append(bytes(dg.getMessage()))

    def sendDatagram(self, dg):
        if self.connected:
            self.md.route(dg, self)

    def disconnect(self):
        if self.connected:
            self.connected = False
            self.md.removeParticipant(self)


class LocalClientConnection:
    """
    Connects the game client to the LocalClientAgent. Replaces its TCP
    connection to astrond's client agent.
    """

    def __init__(self, clientAgent):
        self.inbox = collections.deque()
        self.connected = True
        self.dropped = False
        self.client = clientAgent.connect(self)

    def deliver(self, data):
        self.inbox.append(data)

    def closed(self, dropped):
        self.connected = False
        self.dropped = dropped

    def sendDatagram(self, dg):
        if self.connected:
            self.client.handleClientDatagram(bytes(dg.getMessage()))

    def disconnect(self):
        if self.connected:
            self.client.disconnect()


class LocalConnectionMixin:
    """
    Mixed in front of ConnectionRepository subclasses. Once connectLocal() is
    called, the repository reads and writes datagrams through a local
    connection instead of CConnectionRepository's socket, while keeping the
    exact message handling the C++ layer used to do (header parsing and
    direct field updates).
    """
    localNotify = DirectNotifyGlobal.directNotify.newCategory('LocalConnection')

    _localConn = None
    _localDatagram = None
    _localMsgType = 0
    _localMsgSender = 0
    _localIsClient = False
    _localWasConnected = False

    def connectLocal(self, connection, isClient):
        self._localConn = connection
        self._localIsClient = isClient
        self._localWasConnected = True
        self.startReaderPollTask()

    def isLocal(self):
        return self._localConn is not None

    # ConnectionRepository overrides:

    def connect(self, serverList, successCallback=None, successArgs=[],
                failureCallback=None, failureArgs=[]):
        from otp.local import LocalServer
        localServer = LocalServer.getInstance()
        if localServer is None:
            return super().connect(serverList, successCallback, successArgs,
                                   failureCallback, failureArgs)

        self.notify.info('Connecting to the local server.')
        if serverList:
            self._serverAddress = serverList[0]
        self.connectLocal(localServer.connectClient(), isClient=True)
        if successCallback:
            successCallback(*successArgs)

    # CConnectionRepository overrides:

    def send(self, datagram):
        if self._localConn is None:
            return super().send(datagram)
        if datagram.getLength() > 0:
            self._localConn.sendDatagram(datagram)

    def sendDatagram(self, datagram):
        if self._localConn is None:
            return super().sendDatagram(datagram)
        self._localConn.sendDatagram(datagram)
        return True

    def isConnected(self):
        if self._localConn is None:
            return super().isConnected()
        return self._localConn.connected

    def getMsgType(self):
        if self._localConn is None:
            return super().getMsgType()
        return self._localMsgType

    def getMsgSender(self):
        if self._localConn is None:
            return super().getMsgSender()
        return self._localMsgSender

    def disconnect(self):
        if self._localConn is None:
            return super().disconnect()
        self.notify.info('Closing local connection.')
        self._localWasConnected = False
        self._localConn.disconnect()
        self._localConn = None
        self.stopReaderPollTask()

    def readerPollOnce(self):
        conn = self._localConn
        if conn is None:
            return super().readerPollOnce()

        if not conn.inbox:
            if not conn.connected and self._localWasConnected:
                # The local server closed us (an eject or a drop).
                self._localWasConnected = False
                self.stopReaderPollTask()
                messenger.send(self.uniqueName('lostConnection'), taskChain='default')
            return 0

        # Keep the datagram alive for as long as handlers may hold the iterator.
        self._localDatagram = Datagram(conn.inbox.popleft())
        di = PyDatagramIterator(self._localDatagram)

        if not self._localIsClient:
            count = di.getUint8()
            for _ in range(count):
                di.getUint64()
            self._localMsgSender = di.getUint64()
            self.msgSender = self._localMsgSender
        self._localMsgType = di.getUint16()

        if self._localIsClient:
            if self._localMsgType == CLIENT_OBJECT_SET_FIELD and self.getHandleCUpdates():
                self._handleLocalClientUpdate(di)
            else:
                self.handleDatagram(di)
            return 1

        try:
            if self._localMsgType == STATESERVER_OBJECT_SET_FIELD:
                self._handleLocalServerUpdate(di)
            else:
                self.handleDatagram(di)
        except Exception:
            # The UberDOG and AI used to be separate processes that logged
            # handler exceptions and carried on; keep that behaviour.
            from otp.local import LocalServer
            localServer = LocalServer.getInstance()
            if localServer is None or not localServer.handleRepositoryException(self):
                raise
        return 1

    def _handleLocalServerUpdate(self, di):
        # Same as CConnectionRepository::handle_update_field().
        doId = di.getUint32()
        do = self.doId2do.get(doId)
        if do is not None:
            do.dclass.receiveUpdate(do, di)

    def _handleLocalClientUpdate(self, di):
        # Same as CConnectionRepository::handle_update_field_owner().
        doId = di.getUint32()

        ownerView = self.doId2ownerView.get(doId) if self.hasOwnerView() else None
        if ownerView is not None:
            start = di.getCurrentIndex()
            field = ownerView.dclass.getFieldByIndex(di.getUint16())
            ownerDi = PyDatagramIterator(self._localDatagram, start)
            if field is not None and field.isOwnrecv():
                ownerView.dclass.receiveUpdate(ownerView, ownerDi)
            di = PyDatagramIterator(self._localDatagram, start)

        do = self.doId2do.get(doId)
        if do is not None:
            do.dclass.receiveUpdate(do, di)
