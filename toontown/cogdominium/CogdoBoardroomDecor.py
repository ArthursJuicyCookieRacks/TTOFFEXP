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
# Cogs roaming the open floor, per side of each hall, and where.
RoamersPerSide = 5
RoamX = (40, 92)
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
        self.roamers = []
        self.standers = []
        self.diners = []
        # Cogs roaming the open floor between the tables, carts and greens
        # on looping routes (Arthur: lots of empty space), and what they
        # walk round: (x, y, radius).
        self.roamers = []
        self.blockers = []

    def load(self, parent):
        rng = random.Random(self.layout.seed * 7 + 3)
        self.root = parent.attachNewNode('hallDecor')
        table = loader.loadModel('phase_12/models/bossbotHQ/BanquetTableChairs')
        cart = loader.loadModel('phase_12/models/bossbotHQ/Coggolf_cart3')
        flag = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_flag')
        green = loader.loadModel('phase_12/models/bossbotHQ/bust_a_cog_golf_green')
        food = loader.loadModel('phase_12/models/bossbotHQ/canoffood')
        props = (loader.loadModel('phase_6/models/golf/golfTrophy'),
                 loader.loadModel('phase_12/models/bossbotHQ/food_belt1_model'),
                 loader.loadModel('phase_6/models/golf/golf_ball'),
                 self._sideTable())
        for hall in range(Consts.NumHalls):
            y0 = hall * Consts.HallLength
            for side in (-1, 1):
                # Banquet tables with cogs at dinner: one, and in every other
                # hall a second further along (Arthur: more tables).
                spans = [(150, 300)] + ([(20, 120)] if (hall + (side > 0)) % 2 == 1 else [])
                for lo, hi in spans:
                    self._banquetTable(rng, table, food, side, y0 + rng.uniform(lo, hi))
                # A golf cart parked against the wall, and now and then a
                # putting green with its flag.
                c = cart.copyTo(self.root)
                c.setPos(side * rng.uniform(80, 95), y0 + rng.uniform(40, 120), 0)
                c.setH(rng.choice((0, 180)) + rng.uniform(-20, 20))
                self.blockers.append((c.getX(), c.getY(), 8.0))
                if (hall + (side > 0)) % 2 == 0:
                    g = green.copyTo(self.root)
                    gx, gy = side * rng.uniform(70, 82), y0 + rng.uniform(220, 300)
                    g.setPos(gx, gy, 0.05)
                    g.setScale(0.14)
                    self.blockers.append((gx, gy, 9.0))
                    fl = flag.copyTo(self.root)
                    fl.setPos(gx, gy, 0)
                    fl.setScale(0.45)
                # Cogs walking up and down the floor on business, and some
                # standing at their work.
                for k in range(6):
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
                # Cogs stopped to talk shop, face to face: a pair, and a
                # second pair further down.
                for lo, hi in ((60, 180), (200, 320)):
                    px, py = side * rng.uniform(24, 38), y0 + rng.uniform(lo, hi)
                    for k, dx in enumerate((-1.6, 1.6)):
                        suit = self.makeSuit(rng.choice(WalkerNames))
                        suit.reparentTo(self.root)
                        suit.setPos(px + dx, py, 0)
                        suit.setH(90 if dx < 0 else -90)
                        suit.decorAnim = 'neutral'
                        suit.talkPartner = True
                        self.standers.append(suit)
                self._bossbotProps(rng, props, side, y0)
        for hall in range(Consts.NumHalls):
            for side in (-1, 1):
                for k in range(RoamersPerSide):
                    self._roamer(rng, side, hall * Consts.HallLength)
        for model in (table, cart, flag, green, food) + props:
            model.removeNode()
        for suit in self.allSuits():
            suit.stash()
        return self.root

    def _banquetTable(self, rng, table, food, side, ty):
        tx = side * rng.uniform(48, 62)
        t = table.copyTo(self.root)
        t.setPos(tx, ty, 0)
        t.setH(rng.uniform(0, 90))
        self.blockers.append((tx, ty, 13.0))
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
            # Seated as the meeting's cogs are (CogdoBoardroomRoom): the
            # heading is the table's, not the chair's own (the chair nodes
            # are turned and scaled, which sat the cogs behind their chairs,
            # or sunk in the table).
            turn = t.attachNewNode('correctHeading')
            turn.setPos(chair.getPos(t))
            turn.setH(heading)
            CogdoBoardroomRoom.sitCog(suit, turn, suit.style.body)
            suit.decorAnim = 'sit-eat-loop' if suit.style.body != 'b' else 'neutral'
            CogdoBoardroomRoom.liftOverTable(suit, suit.decorAnim)
            self.diners.append(suit)

    def _bossbotProps(self, rng, models, side, y0):
        # Bossbot things about the hall: a trophy cabinet's worth of golf
        # trophies on side tables, a food conveyor from the CEO's banquet
        # along the wall, and buckets of golf balls by the greens.
        trophy, belt, ball, sideTable = models
        for k in range(2):
            ty = y0 + rng.uniform(30, 310)
            st = sideTable.copyTo(self.root)
            st.setPos(side * rng.uniform(70, 86), ty, 0)
            st.setH(90 * side)
            tr = trophy.copyTo(self.root)
            tr.setPos(st.getX(), ty, 3.6)
            tr.setScale(rng.uniform(1.6, 2.2))
            tr.setH(rng.uniform(0, 360))
            self.blockers.append((st.getX(), ty, 3.5))
        if rng.random() < 0.6:
            b = belt.copyTo(self.root)
            b.setPos(side * 97.0, y0 + rng.uniform(60, 260), 0)
            b.setH(0)
            b.setScale(0.6)
            self.blockers.append((b.getX(), b.getY(), 12.0))
        gx, gy = side * rng.uniform(66, 80), y0 + rng.uniform(20, 320)
        for k in range(rng.randint(8, 14)):
            gb = ball.copyTo(self.root)
            gb.setPos(gx + rng.uniform(-1.2, 1.2), gy + rng.uniform(-1.2, 1.2), 0.25)
            gb.setScale(1.2)
        self.blockers.append((gx, gy, 3.0))

    def _clear(self, a, b, pad=2.0):
        # Is the straight walk from a to b clear of every blocker?
        ax, ay = a
        dx, dy = b[0] - ax, b[1] - ay
        ll = dx * dx + dy * dy or 1.0
        for x, y, r in self.blockers:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
            if math.hypot(ax + dx * t - x, ay + dy * t - y) < r + pad:
                return False
        return True

    def _roamer(self, rng, side, y0):
        # A loop of a few spots out on the open floor, each leg clear of
        # the tables and props; a short stop at each to look about.
        for attempt in range(40):
            pts = []
            for k in range(rng.randint(3, 5)):
                for tries in range(30):
                    p = (side * rng.uniform(RoamX[0], RoamX[1]), y0 + rng.uniform(15, Consts.HallLength - 15))
                    if self._clear(p, p) and (not pts or (self._clear(pts[-1], p)
                                                          and math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > 15)):
                        pts.append(p)
                        break
            if len(pts) >= 3 and self._clear(pts[-1], pts[0]):
                break
        else:
            return
        suit = self.makeSuit(rng.choice(WalkerNames))
        suit.reparentTo(self.root)
        legs = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            legs.append((a, b, math.hypot(b[0] - a[0], b[1] - a[1]), rng.uniform(0.8, 3.0)))
        speed = rng.uniform(4.0, 5.5)
        cycle = sum(d / speed + pause for a, b, d, pause in legs)
        self.roamers.append({'suit': suit, 'legs': legs, 'speed': speed, 'cycle': cycle,
                             'phase': rng.uniform(0, cycle), 'anim': None})

    def _updateRoamers(self, now):
        for w in self.roamers:
            suit = w['suit']
            if suit.isStashed():
                continue
            t = (now + w['phase']) % w['cycle']
            for a, b, d, pause in w['legs']:
                walk = d / w['speed']
                h = -math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
                if t < walk:
                    f = t / walk
                    x, y, anim = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, 'walk'
                    break
                t -= walk
                if t < pause:
                    x, y, anim = b[0], b[1], 'neutral'
                    break
                t -= pause
            else:
                (x, y), anim = w['legs'][0][0], 'neutral'
            suit.setPos(x, y, 0)
            suit.setH(h)
            if w['anim'] != anim:
                w['anim'] = anim
                suit.loop(anim)

    def _sideTable(self):
        # A small dark-wood display table for the trophies.
        from toontown.cogdominium.CogdoBoardroomGolf import _box
        root = PM.NodePath('sideTable')
        _box(root, -1.4, -1.0, 1.4, 1.0, 3.3, 3.6, (0.3, 0.18, 0.1, 1))
        for x in (-1.2, 1.2):
            for y in (-0.8, 0.8):
                _box(root, x - 0.12, y - 0.12, x + 0.12, y + 0.12, 0.0, 3.3, (0.22, 0.13, 0.07, 1))
        return root

    def allSuits(self):
        return self.diners + self.standers + [w['suit'] for w in self.walkers + self.roamers]

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
        self._updateRoamers(now)
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
