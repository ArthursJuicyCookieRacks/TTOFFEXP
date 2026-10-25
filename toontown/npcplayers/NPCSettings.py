"""The player's choices about NPC players, from the launcher's settings."""

from otp.otpbase.Settings import Settings

NPCS_PER_AREA = 12
MAX_NPCS_PER_AREA = 100


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
