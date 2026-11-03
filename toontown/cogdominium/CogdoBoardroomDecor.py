import math
import random

from panda3d import core as PM
from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
from toontown.suit import Suit, SuitDNA
from toontown.cogdominium.CogdoBoardroomRoom import CogdoBoardroomRoom

# What each cog does when it stands about (its own animations; not every
# cog has every one).
IdleAnims = {'f': ('phone', 'shredder'), 'p': ('pencil-sharpener', 'finger-wag', 'hold-pencil'),
             'ym': ('smile', 'golf-club-swing'), 'mm': ('speak', 'effort', 'magic1'),
             'ds': ('magic1', 'magic2'), 'hh': ('roll-o-dex', 'glower'), 'cr': ('glower', 'pickpocket'),
             'tbc': ('cigar-smoke', 'song-and-dance')}
WalkerNames = ('f', 'p', 'ym', 'mm', 'ds', 'hh', 'cr')
DinerNames = ('ym', 'mm', 'hh', 'cr', 'tbc', 'f')
# The round banquet table's chairs, and which way each faces (as the CEO
# battle seats its diners).
DinerSeats = ((0, 90), (1, 90), (2, 0), (3, 0), (4, -90), (5, -90), (6, 180), (7, 180))


class CogdoBoardroomDecor:
    """The rest of the hall beside the meeting: Bossbots walking about the
    floor on business, cogs standing at their work, others dining at the
    old banquet tables, golf carts parked, and putting greens with their
    flags. All for show: none of it is in the toons' way."""

    def __init__(self, layout, makeSuit):
        self.layout = layout
        self.makeSuit = makeSuit
        self.root = None
        self.walkers = []
        self.standers = []
        self.diners = []

    def load(self, parent):
        rng = random.Random(self.layout.seed * 7 + 3)
        self.root = parent.attachNewNode('hallDecor')
        table = loader.loadModel('phase_12/models/bossbotHQ/BanquetTableChairs')
        cart = loader.loadModel('phase_12/models/bossbotHQ/Coggolf_cart3')
        flag = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_flag')
        green = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_green')
        food = loader.loadModel('phase_12/models/bossbotHQ/canoffood')
        for hall in range(Consts.NumHalls):
            y0 = hall * Consts.HallLength
            for side in (-1, 1):
                # A banquet table with cogs at dinner.
                ty = y0 + rng.uniform(150, 300)
                tx = side * rng.uniform(48, 62)
                t = table.copyTo(self.root)
                t.setPos(tx, ty, 0)
                t.setH(rng.uniform(0, 90))
                for k in range(rng.randint(2, 3)):
                    f = food.copyTo(t)
                    f.setPos(rng.uniform(-3, 3), rng.uniform(-3, 3), 3.62)
                    f.setScale(0.6)
                # A cog in every chair round the table (no empty chairs).
                for index, heading in DinerSeats:
                    chair = t.find('**/chair_%d' % (index + 1))
                    if chair.isEmpty():
                        continue
                    suit = self.makeSuit(rng.choice(DinerNames))
                    # Seated as the meeting's cogs are (CogdoBoardroomRoom):
                    # the heading is the table's, not the chair's own (the
                    # chair nodes are turned and scaled, which sat the cogs
                    # behind their chairs, or sunk in the table).
                    turn = t.attachNewNode('correctHeading')
                    turn.setPos(chair.getPos(t))
                    turn.setH(heading)
                    CogdoBoardroomRoom.sitCog(suit, turn, suit.style.body)
                    suit.decorAnim = 'sit-eat-loop' if suit.style.body != 'b' else 'neutral'
                    CogdoBoardroomRoom.liftOverTable(suit, suit.decorAnim)
                    self.diners.append(suit)
                # A golf cart parked against the wall, and now and then a
                # putting green with its flag.
                c = cart.copyTo(self.root)
                c.setPos(side * rng.uniform(80, 95), y0 + rng.uniform(40, 120), 0)
                c.setH(rng.choice((0, 180)) + rng.uniform(-20, 20))
                if (hall + (side > 0)) % 2 == 0:
                    g = green.copyTo(self.root)
                    gx, gy = side * rng.uniform(70, 82), y0 + rng.uniform(220, 300)
                    g.setPos(gx, gy, 0.05)
                    g.setScale(0.14)
                    fl = flag.copyTo(self.root)
                    fl.setPos(gx, gy, 0)
                    fl.setScale(0.45)
                # Cogs walking up and down the floor on business, and some
                # standing at their work.
                for k in range(4):
                    suit = self.makeSuit(rng.choice(WalkerNames))
                    suit.reparentTo(self.root)
                    a = y0 + rng.uniform(10, 200)
                    b = a + rng.uniform(60, 140)
                    x = side * rng.uniform(22, 36)
                    self.walkers.append({'suit': suit, 'x': x, 'a': a, 'b': b, 'speed': rng.uniform(4.0, 5.5),
                                         'phase': rng.uniform(0, 1), 'pause': rng.uniform(2.0, 4.0),
                                         'anim': None})
                suit = self.makeSuit(rng.choice(WalkerNames))
                suit.reparentTo(self.root)
                suit.setPos(side * rng.uniform(26, 40), y0 + rng.uniform(40, 300), 0)
                suit.setH(90 * side + rng.uniform(-40, 40))
                anims = IdleAnims.get(suit.style.name, ('neutral',))
                suit.decorAnim = rng.choice(anims)
                self.standers.append(suit)
                # Two cogs stopped to talk shop, face to face.
                px, py = side * rng.uniform(24, 38), y0 + rng.uniform(60, 320)
                for k, dx in enumerate((-1.6, 1.6)):
                    suit = self.makeSuit(rng.choice(WalkerNames))
                    suit.reparentTo(self.root)
                    suit.setPos(px + dx, py, 0)
                    suit.setH(90 if dx < 0 else -90)
                    suit.decorAnim = 'neutral'
                    self.standers.append(suit)
        for model in (table, cart, flag, green, food):
            model.removeNode()
        for suit in self.diners + self.standers + [w['suit'] for w in self.walkers]:
            suit.stash()
        return self.root

    def allSuits(self):
        return self.diners + self.standers + [w['suit'] for w in self.walkers]

    def startSuit(self, suit):
        anim = getattr(suit, 'decorAnim', None)
        if anim and self._has(suit, anim):
            suit.loop(anim, fromFrame=random.randrange(10))
        elif suit in self.diners:
            suit.loop('sit')
        else:
            suit.loop('neutral')

    def _has(self, suit, anim):
        try:
            return suit.getAnimControl(anim) is not None
        except Exception:
            return False

    def update(self, now):
        # The walkers go back and forth along their beat, stopping at each
        # end a moment to look about.
        for w in self.walkers:
            suit = w['suit']
            if suit.isStashed():
                continue
            length = w['b'] - w['a']
            leg = length / w['speed']
            cycle = 2 * (leg + w['pause'])
            t = (now + w['phase'] * cycle) % cycle
            if t < leg:
                y, h, anim = w['a'] + w['speed'] * t, 0, 'walk'
            elif t < leg + w['pause']:
                y, h, anim = w['b'], 180 if w['x'] > 0 else -180, 'neutral'
            elif t < 2 * leg + w['pause']:
                y, h, anim = w['b'] - w['speed'] * (t - leg - w['pause']), 180, 'walk'
            else:
                y, h, anim = w['a'], 0, 'neutral'
            suit.setPos(w['x'], y, 0)
            suit.setH(h)
            if w['anim'] != anim:
                w['anim'] = anim
                suit.loop(anim)

    def destroy(self):
        for suit in self.allSuits():
            suit.cleanup()
            suit.removeNode()
            suit.delete()
        self.walkers = []
        self.standers = []
        self.diners = []
        if self.root:
            self.root.removeNode()
        self.root = None
