"""The accessories a player picked in Make-A-Toon for the toon being made.

The game and its server share one process, so Make-A-Toon leaves the choice
here, by avatar slot, and the server reads it when it makes the toon."""

_chosen = {}


def choose(index, hat, glasses, backpack, shoes):
    _chosen[index] = (tuple(hat), tuple(glasses), tuple(backpack), tuple(shoes))


def take(index):
    """(hat, glasses, backpack, shoes), each (idx, textureIdx, colorIdx), or None."""
    return _chosen.pop(index, None)
