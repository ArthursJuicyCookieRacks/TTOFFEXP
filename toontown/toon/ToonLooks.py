"""A toon's looks: up to six ways it can look, one worn at a time.

A look is everything about how the toon looks (species, head, body, legs,
colours, clothes and the four accessories) and nothing else: the toon's
name, laff, gags, tasks, suits and jellybeans are the same whichever look
it wears.

The looks are kept next to the toons, in the database's looks folder (so the
launcher's DATA button exports them with the toons), one file a toon:

    looks/<toon id>.json = {"format": 1, "wearing": 0,
                            "looks": [{"dna": "<hex>", "hat": [0, 0, 0], ...}, None, ...]}

Wearing a look sets the toon's own DNA and accessories through the game's
server, which runs in the client's process offline, so it is saved and
everyone sees it like a change made at the tailor.
"""

import ast
import builtins
import json
import os

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import ConfigVariableString, Filename

from toontown.toon import ToonDNA

notify = DirectNotifyGlobal.directNotify.newCategory('ToonLooks')

FORMAT = 1
SLOTS = 6
FOLDER = 'looks'
ACCESSORIES = ('hat', 'glasses', 'backpack', 'shoes')


def folder():
    path = ConfigVariableString('local-db-directory', 'astron/databases/astrondb').getValue()
    return os.path.join(Filename(path).toOsSpecific(), FOLDER)


def fileFor(avId):
    return os.path.join(folder(), '%d.json' % avId)


def forget(avId):
    """A toon was deleted: its looks go with it (its id can be used again)."""
    try:
        os.remove(fileFor(avId))
    except OSError:
        pass


# --- One look ---

def lookOf(toon):
    """The look a (client side) toon is wearing now."""
    look = {'dna': toon.style.makeNetString().hex()}
    for kind in ACCESSORIES:
        look[kind] = list(getattr(toon, 'get' + kind.capitalize())())
    return look


def dnaOf(look):
    dna = ToonDNA.ToonDNA()
    dna.makeFromNetString(bytes.fromhex(look['dna']))
    return dna


def isValid(look):
    if not isinstance(look, dict) or not isinstance(look.get('dna'), str):
        return False
    try:
        dnaOf(look)
    except Exception:
        return False
    for kind in ACCESSORIES:
        value = look.get(kind, [0, 0, 0])
        if not (isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(v, int) for v in value)):
            return False
    return True


# --- A toon's looks ---

class Looks:

    def __init__(self, avId, wearing=0, looks=None):
        self.avId = avId
        self.wearing = wearing
        self.looks = list(looks or []) + [None] * SLOTS
        self.looks = self.looks[:SLOTS]

    @classmethod
    def load(cls, toon):
        """The toon's looks; the first time, the look it wears is look 1."""
        path = fileFor(toon.doId)
        try:
            with open(path, encoding='utf-8') as file:
                data = json.load(file)
            looks = [look if isValid(look) else None for look in data.get('looks', [])]
            wearing = int(data.get('wearing', 0))
        except (OSError, ValueError, AttributeError, TypeError):
            looks, wearing = [], 0
        result = cls(toon.doId, wearing, looks)
        if not 0 <= result.wearing < SLOTS:
            result.wearing = 0
        # What the toon wears is always its worn look (the tailor, a closet or
        # the catalog may have changed it since).
        result.looks[result.wearing] = lookOf(toon)
        return result

    def save(self):
        os.makedirs(folder(), exist_ok=True)
        path = fileFor(self.avId)
        temporary = path + '.part'
        with open(temporary, 'w', encoding='utf-8') as file:
            json.dump({'format': FORMAT, 'wearing': self.wearing, 'looks': self.looks}, file, indent=1)
        os.replace(temporary, path)

    def count(self):
        return sum(1 for look in self.looks if look)

    def setLook(self, slot, look):
        self.looks[slot] = look
        self.save()

    def remove(self, slot):
        if slot == self.wearing:
            return False
        self.looks[slot] = None
        self.save()
        return True


def savedAccessories(avId):
    """{'hat': (...), 'glasses': (...)} a toon has on in its save, for the
    heads drawn before the toon is in game (Pick-A-Toon)."""
    from otp.local import LocalServer
    from otp.local import LocalDCUtil
    worn = {}
    server = LocalServer.getInstance()
    obj = server.database.get(avId) if server is not None and avId else None
    if obj is None:
        return worn
    for kind in ('hat', 'glasses'):
        name = 'set' + kind.capitalize()
        data = obj.fields.get(name)
        if data is None:
            continue
        try:
            value = ast.literal_eval(LocalDCUtil.formatValue(obj.dclass.getFieldByName(name), data))
            worn[kind] = tuple(value)
        except (ValueError, SyntaxError, TypeError):
            pass
    return worn


# --- Wearing a look ---

def _serverToon(avId):
    """(server, context, the toon's server object), or Nones offline-less."""
    from otp.local import LocalServer
    server = LocalServer.getInstance()
    if server is None or not server.ready:
        return None, None, None
    for context, simbase in server.servers:
        toon = simbase.air.doId2do.get(avId)
        if toon is not None and hasattr(toon, 'b_setDNAString'):
            return server, context, toon
    return server, None, None


def wear(look):
    """Puts the look on the player's toon, saved and seen by everyone."""
    avatar = getattr(builtins, 'localAvatar', None)
    if avatar is None:
        return False
    dnaString = bytes.fromhex(look['dna'])
    server, context, toonAI = _serverToon(avatar.doId)
    if toonAI is None:
        notify.warning('no server toon for %s' % avatar.doId)
        return False
    with server.contexts.use(context):
        toonAI.b_setDNAString(dnaString)
        for kind in ACCESSORIES:
            getattr(toonAI, 'b_set' + kind.capitalize())(*look.get(kind, (0, 0, 0)))
    server.flush()
    # Right away here too, so the laff meter can be made for the new look;
    # the server's own update then finds nothing left to change.
    avatar.setDNAString(dnaString)
    for kind in ACCESSORIES:
        getattr(avatar, 'set' + kind.capitalize())(*look.get(kind, (0, 0, 0)))
    avatar.rebuildLaffMeter()
    messenger.send('toonLookChanged')
    return True
