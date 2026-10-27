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


def preloadNPCs():
    """Whether NPC toons are put in a place before the player gets there.

    They are then built behind the loading screen, all at once, instead of
    coming in one at a time once the player can already see the place.
    """
    from panda3d.core import ConfigVariableBool
    return ConfigVariableBool('npc-preload', True).getValue()


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


# --- How the NPC toons help the player (the Setup screen) ---

# normal: NPC toons join the player's battles and elevators as they please.
# turnbased: at each thing other toons could join (a street battle, an
#   elevator into a building, field office, factory, mint, office, golf
#   course or boss fight) the player is asked: Solo or Need Help!
# solo: no NPC toon ever helps.
HELP_MODES = ('normal', 'turnbased', 'solo')
HELP_NORMAL, HELP_TURN_BASED, HELP_SOLO = HELP_MODES

_helpMode = [None]


def helpMode():
    if _helpMode[0] is None:
        mode = Settings().getString('game', 'npc-help', HELP_NORMAL)
        _helpMode[0] = mode if mode in HELP_MODES else HELP_NORMAL
    return _helpMode[0]


def setHelpMode(mode, settings=None):
    if mode not in HELP_MODES:
        return
    _helpMode[0] = mode
    (settings or Settings()).updateSetting('game', 'npc-help', mode)
    # A fresh choice forgets the answers given under the old one.
    _helpAnswers.clear()
    del _helpQuestions[:]
    _helpForced.clear()


# Turn based: the player's answers, by (avId, the battle's or elevator's
# doId), and the questions waiting for the player's game to show them.
_helpAnswers = {}
_helpQuestions = []


# Things the player pressed Need Help! for in a battle (any Setup), by the
# battle's or boss's doId: NPC toons help there whatever the Setup says.
_helpForced = set()


def forceHelp(key):
    _helpForced.add(key)


def helpForced(key):
    return key in _helpForced


def canAskHelp(avId, key):
    """Whether the Need Help! button belongs in avId's battle key: the Setup
    is Solo, or Turn based and the player said Solo, and they have not
    pressed it yet."""
    if key in _helpForced:
        return False
    mode = helpMode()
    if mode == HELP_SOLO:
        return True
    return mode == HELP_TURN_BASED and _helpAnswers.get((avId, key)) is False


def wantsHelp(avId, key):
    """Whether NPC toons may help avId with the thing key names: True, False,
    or None while the player has yet to be asked or to answer (turn based)."""
    if key in _helpForced:
        return True
    mode = helpMode()
    if mode == HELP_NORMAL:
        return True
    if mode == HELP_SOLO:
        return False
    answer = _helpAnswers.get((avId, key))
    if answer is None and (avId, key) not in _helpQuestions:
        _helpQuestions.append((avId, key))
    return answer


def takeHelpQuestion(avId):
    """The key of a thing the player's game should ask about, if any."""
    for item in _helpQuestions:
        if item[0] == avId:
            return item[1]
    return None


def setHelpAnswer(avId, key, wantHelp):
    _helpAnswers[(avId, key)] = bool(wantHelp)
    if (avId, key) in _helpQuestions:
        _helpQuestions.remove((avId, key))


def forgetHelpAnswer(key):
    """The thing is over (the player got off the elevator): asked afresh next time."""
    _helpForced.discard(key)
    for item in [k for k in _helpAnswers if k[1] == key]:
        del _helpAnswers[item]
    for item in [q for q in _helpQuestions if q[1] == key]:
        _helpQuestions.remove(item)
