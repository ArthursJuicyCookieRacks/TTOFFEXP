import collections

from panda3d.core import Datagram, DatagramIterator
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.MsgTypes import *

# Not in Panda3D's MsgTypes, but part of Astron's control protocol.
CONTROL_SET_CON_NAME = 9012
CONTROL_SET_CON_URL = 9013


class MDParticipant:
    """
    Anything that can be subscribed to channels on the LocalMessageDirector.
    """

    def __init__(self, md):
        self.md = md
        self.postRemoves = collections.defaultdict(list)

    def handleDatagram(self, dg, channels, sender, msgType, di):
        """
        Called with every datagram routed to this participant. `di` is
        positioned right after the message type. `channels` is the full list
        of recipient channels in the header.
        """
        raise NotImplementedError

    def subscribe(self, channel):
        self.md.subscribe(self, channel)

    def unsubscribe(self, channel):
        self.md.unsubscribe(self, channel)

    def subscribeRange(self, low, high):
        self.md.subscribeRange(self, low, high)

    def unsubscribeRange(self, low, high):
        self.md.unsubscribeRange(self, low, high)

    def send(self, dg):
        self.md.route(dg, self)


class LocalMessageDirector:
    """
    Routes Astron server datagrams between participants, in order, through a
    single FIFO queue. Like Astron's Message Director, a datagram is delivered
    once to every participant subscribed to at least one of its channels, and
    never back to the participant that sent it.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('LocalMessageDirector')

    def __init__(self, trace=False):
        self.subscriptions = collections.defaultdict(set)
        self.ranges = []
        self.queue = collections.deque()
        # Logs every routed message (local-md-trace), for debugging.
        self.trace = trace

    def subscribe(self, participant, channel):
        self.subscriptions[channel].add(participant)

    def unsubscribe(self, participant, channel):
        subscribers = self.subscriptions.get(channel)
        if subscribers is None:
            return
        subscribers.discard(participant)
        if not subscribers:
            del self.subscriptions[channel]

    def subscribeRange(self, participant, low, high):
        self.ranges.append((low, high, participant))

    def unsubscribeRange(self, participant, low, high):
        self.ranges = [r for r in self.ranges if r != (low, high, participant)]

    def removeParticipant(self, participant):
        """
        Drops every subscription of `participant` and runs its post-removes,
        just like Astron does when a participant's connection closes.
        """
        for channel in list(self.subscriptions.keys()):
            self.unsubscribe(participant, channel)
        self.ranges = [r for r in self.ranges if r[2] is not participant]

        postRemoves = participant.postRemoves
        participant.postRemoves = collections.defaultdict(list)
        for channel in postRemoves:
            for data in postRemoves[channel]:
                self.route(Datagram(data), None)

    def route(self, dg, origin):
        """
        Queues a datagram for delivery. The datagram is copied, so the caller
        may keep using its own.
        """
        self.queue.append((bytes(dg.getMessage()), origin))

    def hasPending(self):
        return bool(self.queue)

    def flush(self, limit=None):
        """
        Delivers queued datagrams. Datagrams queued while flushing are
        delivered in the same call, until the queue is empty or `limit`
        datagrams were processed. Returns the number processed.
        """
        processed = 0
        while self.queue and (limit is None or processed < limit):
            data, origin = self.queue.popleft()
            processed += 1
            try:
                self.deliver(data, origin)
            except Exception:
                self.notify.warning('Exception while routing a datagram:')
                raise
        return processed

    def deliver(self, data, origin):
        dg = Datagram(data)
        di = DatagramIterator(dg)
        count = di.getUint8()
        channels = [di.getUint64() for _ in range(count)]

        if count == 1 and channels[0] == CONTROL_CHANNEL:
            self.handleControl(di, origin)
            return

        sender = di.getUint64()
        msgType = di.getUint16()
        headerEnd = di.getCurrentIndex()

        receivers = []
        seen = set()
        for channel in channels:
            for participant in self.subscriptions.get(channel, ()):
                if participant not in seen:
                    seen.add(participant)
                    receivers.append(participant)
            for low, high, participant in self.ranges:
                if low <= channel <= high and participant not in seen:
                    seen.add(participant)
                    receivers.append(participant)

        if self.trace:
            self.notify.info('%s -> %s: msgType %d, %d bytes, %d receivers' % (
                sender, channels, msgType, len(data) - headerEnd,
                len([p for p in receivers if p is not origin])))

        for participant in receivers:
            if participant is origin:
                continue
            participantDi = DatagramIterator(dg, headerEnd)
            participant.handleDatagram(dg, channels, sender, msgType, participantDi)

    def handleControl(self, di, origin):
        msgType = di.getUint16()
        if origin is None:
            self.notify.warning('Control message %d with no origin dropped.' % msgType)
            return

        if msgType == CONTROL_ADD_CHANNEL:
            self.subscribe(origin, di.getUint64())
        elif msgType == CONTROL_REMOVE_CHANNEL:
            self.unsubscribe(origin, di.getUint64())
        elif msgType == CONTROL_ADD_RANGE:
            low = di.getUint64()
            high = di.getUint64()
            self.subscribeRange(origin, low, high)
        elif msgType == CONTROL_REMOVE_RANGE:
            low = di.getUint64()
            high = di.getUint64()
            self.unsubscribeRange(origin, low, high)
        elif msgType == CONTROL_ADD_POST_REMOVE:
            sender = di.getUint64()
            origin.postRemoves[sender].append(bytes(di.getBlob()))
        elif msgType == CONTROL_CLEAR_POST_REMOVES:
            sender = di.getUint64()
            origin.postRemoves.pop(sender, None)
        elif msgType in (CONTROL_SET_CON_NAME, CONTROL_SET_CON_URL):
            pass
        else:
            self.notify.warning('Unknown control message %d.' % msgType)
