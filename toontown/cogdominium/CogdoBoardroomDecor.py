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
RoamersPerSide = 8
RoamX = (40, 92)
# How much floor each body type takes up (for standing pairs apart).
BodyRadius = {'a': 2.2, 'b': 1.7, 'c': 1.6}
# How fast a cog turns round, degrees a second.
TurnRate = 220.0
WalkerNames = ('f', 'p', 'ym', 'mm', 'ds', 'hh', 'cr')
DinerNames = ('ym', 'mm', 'hh', 'cr', 'tbc', 'f')
# The round banquet table's chairs, and which way each faces (as the CEO
# battle seats its diners).
DinerSeats = ((0, 90), (1, 90), (2, 0), (3, 0), (4, -90), (5, -90), (6, 180), (7, 180))


class CogdoBoardroomDecor:
    """The rest of the hall beside the meeting: Bossbots walking about the
    floor on business, cogs standing at their work, others dining at the
    old banquet tables, golf carts parked, and putting greens with their
    flags. All for show: none of it is in the toons' way.

    The cogs are only made for the part of the hall in view (cull): each
    cog's place is a "slot" (an empty node where it sits, stands or walks)
    and a cog of that kind is taken from a pool when the slot comes into
    view, and given back when it leaves. All of them were made at load,
    about 600 cogs, which froze the load for seconds, took hundreds of MB,
    and ticked and cast shadow rays every frame hidden or not (perf audit:
    the office's lag, worst on phones)."""

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
        # Every cog's place, and the cogs not in use, by name.
        self.slots = []
        self.free = {}
        self._poseTops = {}
        self._bodies = {}

    def load(self, parent, bins=None):
        rng = random.Random(self.layout.seed * 7 + 3)
        self.root = parent.attachNewNode('hallDecor')
        # The tables, carts, greens and trophies: sorted into stretches of
        # the hall (drawn only near the camera) and each stretch flattened
        # into a few pieces (they were hundreds of separate ones).
        self.bins = bins
        self.propRoot = self.root.attachNewNode('props')
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
                cx, cy = side * rng.uniform(80, 95), y0 + rng.uniform(40, 120)
                c = cart.copyTo(self._at(cy))
                c.setPos(cx, cy, 0)
                c.setH(rng.choice((0, 180)) + rng.uniform(-20, 20))
                self.blockers.append((c.getX(), c.getY(), 8.0))
                if (hall + (side > 0)) % 2 == 0:
                    gx, gy = side * rng.uniform(70, 82), y0 + rng.uniform(220, 300)
                    g = green.copyTo(self._at(gy))
                    g.setPos(gx, gy, 0.05)
                    g.setScale(0.14)
                    self.blockers.append((gx, gy, 9.0))
                    fl = flag.copyTo(self._at(gy))
                    fl.setPos(gx, gy, 0)
                    fl.setScale(0.45)
                # Cogs walking up and down the floor on business, and some
                # standing at their work.
                for k in range(6):
                    name = rng.choice(WalkerNames)
                    node = self.root.attachNewNode('walker')
                    a = y0 + rng.uniform(10, 200)
                    b = a + rng.uniform(60, 140)
                    x = side * rng.uniform(22, 36)
                    w = {'node': node, 'x': x, 'a': a, 'b': b, 'speed': rng.uniform(4.0, 5.5),
                         'phase': rng.uniform(0, 1), 'pause': rng.uniform(2.0, 4.0), 'anim': None}
                    w['slot'] = self._slot(name, 'walker', node, mover=w, span=(a, b))
                    self.walkers.append(w)
                name = rng.choice(WalkerNames)
                node = self.root.attachNewNode('stander')
                node.setPos(*self._standSpot(rng, side, 26, 40, y0 + 40, y0 + 300, 1.5))
                node.setH(90 * side + rng.uniform(-40, 40))
                self.blockers.append((node.getX(), node.getY(), 3.0))
                anims = IdleAnims.get(name, ('neutral',))
                self.standers.append(self._slot(name, 'stander', node, anim=rng.choice(anims)))
                # Cogs stopped to talk shop, face to face: three groups of
                # two or three along each side, taking turns to speak.
                for lo, hi in ((40, 140), (150, 240), (250, 330)):
                    names = [rng.choice(WalkerNames) for k in range(rng.choice((2, 2, 3)))]
                    # Far enough apart for their sizes (a big A-body and a
                    # small one stood inside each other), round a spot, and
                    # turned to face each other (the pairs were turned away
                    # from each other: Arthur).
                    big = max(BodyRadius.get(self._body(n), 1.8) for n in names)
                    ring = big + 0.4 if len(names) == 2 else big * 1.25 + 0.6
                    px, py, pz = self._standSpot(rng, side, 24, 40, y0 + lo, y0 + hi, ring + 2.0)
                    start = rng.uniform(0, 360)
                    group = []
                    for k, name in enumerate(names):
                        ang = math.radians(start + k * 360.0 / len(names))
                        node = self.root.attachNewNode('talker')
                        node.setPos(px + math.cos(ang) * ring, py + math.sin(ang) * ring, 0)
                        group.append(self._slot(name, 'stander', node, anim='neutral'))
                    self.standers.extend(group)
                    for k, slot in enumerate(group):
                        other = group[(k + 1) % len(group)]
                        if len(group) == 2:
                            slot['node'].headsUp(other['node'])
                        else:
                            slot['node'].headsUp(PM.Point3(px, py, 0))
                        slot['partner'] = other
                    self.blockers.append((px, py, ring + 2.0))
                self._bossbotProps(rng, props, side, y0)
        for hall in range(Consts.NumHalls):
            for side in (-1, 1):
                for k in range(RoamersPerSide):
                    self._roamer(rng, side, hall * Consts.HallLength)
        for model in (table, cart, flag, green, food) + props:
            model.removeNode()
        if self.bins is not None:
            self.bins.flatten(self.propRoot)
        self._warmPool()
        return self.root

    def _at(self, y):
        # Where a prop at this point along the hall goes.
        if self.bins is None:
            return self.propRoot
        return self.bins.get(self.propRoot, y)

    # --- The cogs, made only for the part in view ---

    def _body(self, name):
        if name not in self._bodies:
            dna = SuitDNA.SuitDNA()
            dna.newSuit(name)
            self._bodies[name] = dna.body
        return self._bodies[name]

    def _slot(self, name, kind, node, anim=None, mover=None, span=None):
        y = node.getY(render)
        slot = {'name': name, 'kind': kind, 'node': node, 'anim': anim, 'mover': mover, 'suit': None,
                'partner': None, 'y': y, 'span': span or (y, y)}
        self.slots.append(slot)
        return slot

    def _take(self, name):
        free = self.free.get(name)
        if free:
            return free.pop()
        return self.makeSuit(name)

    def _give(self, suit):
        suit._shadowToken = getattr(suit, '_shadowToken', 0) + 1
        suit.stop()
        suit.setActiveShadow(0)
        suit.clearChat()
        suit.nametag3d.stash()
        suit.nametag.setTicking(False)
        suit._lastSaid = -99
        suit._replyAt = 0
        suit.talkPartner = None
        suit._decorSlot = None
        suit.detachNode()
        self.free.setdefault(suit.style.name, []).append(suit)

    def _warmPool(self):
        # As many of each kind of cog as are ever in view at once, made now
        # (behind the loading screen) so none has to be made mid-slide.
        lo = Consts.TableStart - 60
        need = {}
        while lo < Consts.TableEnd + 60:
            count = {}
            for slot in self.slots:
                a, b = slot['span']
                if b > lo - 60 and a < lo + Consts.ShowCogsWithin + 20:
                    count[slot['name']] = count.get(slot['name'], 0) + 1
            for name, n in count.items():
                need[name] = max(need.get(name, 0), n)
            lo += 25
        for name, n in need.items():
            have = len(self.free.get(name, ()))
            for k in range(n + 1 - have):
                self._give(self.makeSuit(name))

    def _poseTop(self, name, anim):
        # How high a seated cog's head is above its seat place, in a pose.
        key = (name, anim)
        if key not in self._poseTops:
            suit = self._take(name)
            holder = PM.NodePath('holder')
            suit.reparentTo(holder)
            if suit.getAnimControl(anim) is not None:
                suit.pose(anim, 0)
            bounds = suit.getTightBounds(holder)
            self._poseTops[key] = bounds[1][2] if bounds else None
            self._give(suit)
            holder.removeNode()
        return self._poseTops[key]

    def slotY(self, slot, now):
        mover = slot['mover']
        if mover is None:
            return slot['y']
        if slot['kind'] == 'walker':
            return self._walkerAt(mover, now)[1]
        return self._roamerAt(mover, now)[1]

    def cull(self, y, now):
        # Cogs coming into view are taken from the pool, those gone out of
        # it (a little further, so none flickers at the edge) go back.
        for slot in self.slots:
            dy = self.slotY(slot, now) - y
            if slot['suit'] is None:
                if -40 < dy < Consts.ShowCogsWithin:
                    self._show(slot, now)
            elif not -55 < dy < Consts.ShowCogsWithin + 20:
                self._hide(slot)

    def _show(self, slot, now):
        suit = self._take(slot['name'])
        suit.reparentTo(slot['node'])
        suit.setPosHpr(0, 0, 0, 0, 0, 0)
        suit.unstash()
        suit._decorSlot = slot
        suit.decorAnim = slot['anim']
        slot['suit'] = suit
        partner = slot['partner']
        suit.talkPartner = partner['suit'] if partner else None
        for other in self.slots if partner else ():
            if other['partner'] is slot and other['suit'] is not None:
                other['suit'].talkPartner = suit
        mover = slot['mover']
        if mover is not None:
            # Straight to where it is on its walk now, facing its way.
            x, y, h, anim = self._walkerAt(mover, now) if slot['kind'] == 'walker' else self._roamerAt(mover, now)
            slot['node'].setPos(x, y, 0)
            if h is not None:
                slot['node'].setH(h)
            mover['anim'] = anim
            suit.loop(anim)
            suit.setActiveShadow(1)
        else:
            # Sat or standing still: its shadow placed once.
            self.startSuit(suit)
            from toontown.cogdominium.DistCogdoBoardroomGame import placeShadowOnce
            placeShadowOnce(suit)

    def _hide(self, slot):
        suit = slot['suit']
        slot['suit'] = None
        for other in self.slots if slot['partner'] else ():
            if other['partner'] is slot and other['suit'] is not None:
                other['suit'].talkPartner = None
        self._give(suit)

    def releaseAll(self):
        for slot in self.slots:
            if slot['suit'] is not None:
                self._hide(slot)

    def _banquetTable(self, rng, table, food, side, ty):
        tx = side * rng.uniform(48, 62)
        t = table.copyTo(self._at(ty))
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
            name = rng.choice(DinerNames)
            body = self._body(name)
            # Seated as the meeting's cogs are (CogdoBoardroomRoom): the
            # heading is the table's, not the chair's own (the chair nodes
            # are turned and scaled, which sat the cogs behind their chairs,
            # or sunk in the table).
            turn = t.attachNewNode('correctHeading')
            turn.setPos(chair.getPos(t))
            turn.setH(heading)
            # (Off the table, which is flattened with the rest.)
            turn.wrtReparentTo(self.root)
            node = PM.NodePath('diner')
            sit = CogdoBoardroomRoom.sitCog(node, turn, body)
            anim = 'sit-eat-loop' if body != 'b' else 'neutral'
            # Lifted up its seat till its head shows over the table, as
            # CogdoBoardroomRoom.liftOverTable does for a cog sat there.
            top = self._poseTop(name, anim)
            if top is not None:
                short = Consts.TableTop + Consts.SeatedHeadClear - (node.getZ(render) + top)
                if short > 0:
                    sit.setZ(sit.getZ() + short)
            self.diners.append(self._slot(name, 'diner', node, anim=anim))

    def _bossbotProps(self, rng, models, side, y0):
        # Bossbot things about the hall: a trophy cabinet's worth of golf
        # trophies on side tables, a food conveyor from the CEO's banquet
        # along the wall, and buckets of golf balls by the greens.
        trophy, belt, ball, sideTable = models
        for k in range(2):
            ty = y0 + rng.uniform(30, 310)
            st = sideTable.copyTo(self._at(ty))
            st.setPos(side * rng.uniform(70, 86), ty, 0)
            st.setH(90 * side)
            tr = trophy.copyTo(self._at(ty))
            tr.setPos(st.getX(), ty, 3.6)
            tr.setScale(rng.uniform(1.6, 2.2))
            tr.setH(rng.uniform(0, 360))
            self.blockers.append((st.getX(), ty, 3.5))
        if rng.random() < 0.6:
            by = y0 + rng.uniform(60, 260)
            b = belt.copyTo(self._at(by))
            b.setPos(side * 97.0, by, 0)
            b.setH(0)
            b.setScale(0.6)
            self.blockers.append((b.getX(), b.getY(), 12.0))
        gx, gy = side * rng.uniform(66, 80), y0 + rng.uniform(20, 320)
        for k in range(rng.randint(8, 14)):
            gb = ball.copyTo(self._at(gy))
            gb.setPos(gx + rng.uniform(-1.2, 1.2), gy + rng.uniform(-1.2, 1.2), 0.25)
            gb.setScale(1.2)
        self.blockers.append((gx, gy, 3.0))

    def _standSpot(self, rng, side, x0, x1, y0, y1, r):
        # Somewhere to stand that is out of the walkers' beats (they walked
        # straight through the cogs stood talking) and clear of the props.
        for tries in range(40):
            x, y = side * rng.uniform(x0, x1), rng.uniform(y0, y1)
            if any(abs(w['x'] - x) < r + 1.8 and w['a'] - r - 2 < y < w['b'] + r + 2 for w in self.walkers):
                continue
            if self._clear((x, y), (x, y), r):
                return x, y, 0
        return x, y, 0

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
        name = rng.choice(WalkerNames)
        node = self.root.attachNewNode('roamer')
        legs = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            idle = self._idle(rng, name)
            legs.append((a, b, math.hypot(b[0] - a[0], b[1] - a[1]), rng.uniform(3.0, 6.0) if idle != 'neutral' else rng.uniform(0.8, 3.0), idle))
        speed = rng.uniform(4.0, 5.5)
        cycle = sum(d / speed + pause for a, b, d, pause, idle in legs)
        w = {'node': node, 'legs': legs, 'speed': speed, 'cycle': cycle,
             'phase': rng.uniform(0, cycle), 'anim': None}
        ys = [p[1] for p in pts]
        w['slot'] = self._slot(name, 'roamer', node, mover=w, span=(min(ys), max(ys)))
        self.roamers.append(w)

    def _turn(self, suit, h, dt):
        # Turned round over a moment, not snapped to the new heading.
        cur = suit.getH()
        d = (h - cur + 180.0) % 360.0 - 180.0
        step = TurnRate * dt
        suit.setH(cur + max(-step, min(step, d)))

    def _idle(self, rng, name):
        # Now and then a cog stopped on its walk does something (a call on
        # its phone, a look at its rolodex...), or else just looks about.
        anims = [a for a in IdleAnims.get(name, ()) if a not in ('golf-club-swing', 'magic1', 'magic2', 'pickpocket')]
        return rng.choice(anims) if anims and rng.random() < 0.45 else 'neutral'

    def _roamerAt(self, w, now):
        # Where a roamer is on its loop now: (x, y, heading or None, anim).
        t = (now + w['phase']) % w['cycle']
        legs = w['legs']
        h = None
        for i, (a, b, d, pause, idle) in enumerate(legs):
            walk = d / w['speed']
            h = -math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
            if t < walk:
                f = t / walk
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, h, 'walk'
            t -= walk
            if t < pause:
                if t > 0.6 * pause or idle == 'neutral':
                    # Turning to set off on the next leg.
                    n = legs[(i + 1) % len(legs)]
                    h = -math.degrees(math.atan2(n[1][0] - n[0][0], n[1][1] - n[0][1]))
                return b[0], b[1], h, idle
            t -= pause
        return legs[0][0][0], legs[0][0][1], h, 'neutral'

    def _walkerAt(self, w, now):
        # Where a walker is on its beat now: (x, y, heading, anim).
        length = w['b'] - w['a']
        leg = length / w['speed']
        cycle = 2 * (leg + w['pause'])
        t = (now + w['phase'] * cycle) % cycle
        if t < leg:
            return w['x'], w['a'] + w['speed'] * t, 0, 'walk'
        elif t < leg + w['pause']:
            return w['x'], w['b'], 180 if w['x'] > 0 else -180, 'neutral'
        elif t < 2 * leg + w['pause']:
            return w['x'], w['b'] - w['speed'] * (t - leg - w['pause']), 180, 'walk'
        return w['x'], w['a'], 0, 'neutral'

    def _updateRoamers(self, now, dt):
        for w in self.roamers:
            suit = w['slot']['suit']
            if suit is None:
                continue
            x, y, h, anim = self._roamerAt(w, now)
            w['node'].setPos(x, y, 0)
            self._turn(w['node'], h, dt)
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
        # The cogs in view (made from the pool).
        return [slot['suit'] for slot in self.slots if slot['suit'] is not None]

    def startSuit(self, suit):
        anim = getattr(suit, 'decorAnim', None)
        if anim and self._has(suit, anim):
            suit.loop(anim, fromFrame=random.randrange(10))
        elif getattr(suit, '_decorSlot', None) is not None and suit._decorSlot['kind'] == 'diner':
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
        dt = max(0.0, min(0.5, now - getattr(self, '_lastUpdate', now)))
        self._lastUpdate = now
        self._updateRoamers(now, dt)
        for w in self.walkers:
            suit = w['slot']['suit']
            if suit is None:
                continue
            x, y, h, anim = self._walkerAt(w, now)
            w['node'].setPos(x, y, 0)
            self._turn(w['node'], h, dt)
            if w['anim'] != anim:
                w['anim'] = anim
                suit.loop(anim)

    def destroy(self):
        self.releaseAll()
        for free in self.free.values():
            for suit in free:
                suit.cleanup()
                suit.removeNode()
                suit.delete()
        self.free = {}
        self.slots = []
        self.roamers = []
        self.walkers = []
        self.standers = []
        self.diners = []
        if self.root:
            self.root.removeNode()
        self.root = None
