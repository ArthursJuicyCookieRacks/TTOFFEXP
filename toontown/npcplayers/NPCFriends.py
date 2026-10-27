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


def whispered(doId):
    """The player whispered to doId; an NPC toon comes to help."""
    if doId not in npcFriends():
        return False
    return bool(_call('summon', doId))


def needHelpAvailable():
    """Whether the Need Help! button belongs in the player's battle."""
    return bool(_call('needHelpAvailable'))


def needHelp():
    """The player pressed Need Help!: NPC toons join their battle."""
    return bool(_call('needHelp'))
