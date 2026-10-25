"""Tells the district where the player's game is going, before it gets there.

The client calls heading() just before it asks for the new zone. The
district puts that place's NPC toons in at once, so the client builds them
while its loading screen is still up rather than one by one afterwards.
Offline only: the district runs in the client's own process.
"""

import builtins

from otp.local import LocalServer


def heading(zoneId):
    server = LocalServer.getInstance()
    if server is None or not server.ready:
        return
    avatar = getattr(builtins, 'localAvatar', None)
    if avatar is None:
        return
    avId = avatar.doId
    # The new place's scenery: loaded by now, but not under render yet.
    hood = getattr(base.cr.playGame, 'hood', None)
    geom = getattr(getattr(hood, 'loader', None), 'geom', None)
    scene = geom if geom is not None and not geom.isEmpty() else None
    for context, simbase in server.servers:
        air = simbase.air
        manager = getattr(air, 'npcPlayerManager', None)
        player = air.doId2do.get(avId) if manager is not None else None
        if player is None:
            continue
        with server.contexts.use(context):
            try:
                manager.headingTo(zoneId, player, scene)
            except Exception:
                manager.notify.warning('preloading failed')
                import traceback
                traceback.print_exc()
    server.flush()
