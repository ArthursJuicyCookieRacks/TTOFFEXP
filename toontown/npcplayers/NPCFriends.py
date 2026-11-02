"""The NPC toons around the player, as the player's friends.

Offline there is nobody else to be friends with, so every NPC toon in the
place the player is in shows on the friends list, online. Whispering one of
them (typed or SpeedChat) asks it for help: it says OK and teleports
straight to the player, into the player's battle if there is one, and
sticks with the player from then on.

Client side; it asks the district directly, which runs in the client's own
process offline (see NPCPreload).
"""

import builtins
import math

from otp.local import LocalServer

# How long a list is good for before the district is asked again.
REFRESH = 1.0
_cache = [-REFRESH, []]


def _call(method, *args):
    server = LocalServer.getInstance()
    if server is None or not server.ready:
        return None
    avatar = getattr(builtins, 'localAvatar', None)
    if avatar is None:
        return None
    for context, simbase in server.servers:
        air = simbase.air
        manager = getattr(air, 'npcPlayerManager', None)
        player = air.doId2do.get(avatar.doId) if manager is not None else None
        if player is None:
            continue
        with server.contexts.use(context):
            try:
                result = getattr(manager, method)(player, *args)
            except Exception:
                manager.notify.warning('%s failed' % method)
                import traceback
                traceback.print_exc()
                result = None
        server.flush()
        return result
    return None


def npcFriends():
    """The doIds of the NPC toons the player's game can see in its place."""
    now = globalClock.getFrameTime()
    if now - _cache[0] >= REFRESH:
        _cache[0] = now
        ids = _call('friendsFor') or []
        _cache[1] = [doId for doId in ids if doId in base.cr.doId2do]
    return _cache[1]


def isNPCFriend(doId):
    return doId in npcFriends()


def whispered(doId, text=None):
    """The player whispered text to doId: an NPC toon answers, and comes to
    help unless it was something mean or a goodbye (see NPCChatReplies)."""
    if doId not in npcFriends():
        return False
    if text is None:
        return bool(_call('summon', doId))
    return bool(_call('chatReply', doId, text, True))


# Saying something aloud reaches the NPC toon the player is looking at:
# within this distance, and this many degrees of where the toon or the
# camera faces.
TALK_RANGE = 22.0
TALK_HALF_ANGLE = 35.0


def lookedAt():
    """The doId of the NPC toon the player is looking at, or None."""
    avatar = getattr(builtins, 'localAvatar', None)
    if avatar is None or avatar.isEmpty():
        return None
    render = builtins.base.render
    pos = avatar.getPos(render)
    facings = [avatar.getQuat(render).getForward()]
    camera = getattr(builtins.base, 'camera', None)
    if camera is not None and not camera.isEmpty():
        facings.append(camera.getQuat(render).getForward())
    best = None
    for doId in npcFriends():
        toon = builtins.base.cr.doId2do.get(doId)
        if toon is None or toon.isEmpty() or toon.isHidden():
            continue
        offset = toon.getPos(render) - pos
        offset.setZ(0)
        distance = offset.length()
        if distance > TALK_RANGE or distance < 0.01:
            continue
        offset /= distance
        angle = TALK_HALF_ANGLE + 1
        for facing in facings:
            facing.setZ(0)
            if facing.normalize():
                angle = min(angle, math.degrees(math.acos(max(-1.0, min(1.0, offset.dot(facing))))))
        if angle > TALK_HALF_ANGLE:
            continue
        # Nearer and straighter ahead wins.
        score = distance / TALK_RANGE + angle / TALK_HALF_ANGLE
        if best is None or score < best[0]:
            best = (score, doId)
    return best[1] if best else None


def saidAloud(text):
    """The player said text aloud: the NPC toon they look at answers it."""
    doId = lookedAt()
    if doId is None:
        return False
    return bool(_call('chatReply', doId, text, False))


def needHelpAvailable():
    """Whether the Need Help! button belongs in the player's battle."""
    return bool(_call('needHelpAvailable'))


def needHelp():
    """The player pressed Need Help!: NPC toons join their battle."""
    return bool(_call('needHelp'))
