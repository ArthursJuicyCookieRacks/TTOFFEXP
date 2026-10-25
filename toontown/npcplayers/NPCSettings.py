"""The player's choices about NPC players, from the launcher's settings."""

from otp.otpbase.Settings import Settings

NPCS_PER_AREA = 12
MAX_NPCS_PER_AREA = 100


# How many places (playgrounds, streets, Cog HQs) keep their NPC toons
# after the player leaves, so going back finds the same toons already built
# instead of making new ones. 0 makes each place start afresh.
KEEP_AREAS = 4


def keepAreas():
    from panda3d.core import ConfigVariableInt
    return max(0, ConfigVariableInt('npc-keep-areas', KEEP_AREAS).getValue())


def npcsPerArea(settings=None):
    """How many NPC players each place gets."""
    settings = settings or Settings()
    return max(0, min(MAX_NPCS_PER_AREA, settings.getInt('game', 'npc-toons', NPCS_PER_AREA)))


# Whether each player asked for other players on the trolley (the game and
# its districts share one process, so the choice is read straight from here).
_trolleyCompany = {}


def setTrolleyCompany(avId, company):
    _trolleyCompany[avId] = company


def wantsTrolleyCompany(avId):
    return _trolleyCompany.get(avId, True)


# The trolley game each player picked from the trolley's list, if any.
_trolleyGame = {}


def setTrolleyGame(avId, gameId):
    if gameId is None:
        _trolleyGame.pop(avId, None)
    else:
        _trolleyGame[avId] = gameId


def takeTrolleyGame(avId):
    """The game the player picked, once: the next ride is random again."""
    return _trolleyGame.pop(avId, None)
