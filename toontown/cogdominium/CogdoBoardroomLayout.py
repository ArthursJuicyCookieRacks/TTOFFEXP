"""The boardroom table's layout, made from a seed and the difficulty, so
the AI and every client lay out the same table without sending it all."""
import math
import random

from toontown.cogdominium import CogdoBoardroomGameConsts as Consts

# Obstacle kinds.
PILE = 'pile'          # A pile of paperwork: go round it, or up a ramp.
PENCIL = 'pencil'      # A giant pencil lying across the table: hop it.
RAMP = 'ramp'          # A ramp up onto a pile, with memos on top.

# No two memos closer than this (ft): no heaps.
MemoSpacing = 3.5

INVULNERABLE = 0
HOP = 1


class Obstacle:

    def __init__(self, kind, x, y, w, l, h, angle=0.0):
        self.kind = kind
        self.x = x
        self.y = y
        # Half sizes across and along the table, and the height.
        self.w = w
        self.l = l
        self.h = h
        self.angle = angle

    def bounds(self, margin=0.0):
        return (self.x - self.w - margin, self.x + self.w + margin,
                self.y - self.l - margin, self.y + self.l + margin)

    def contains(self, x, y, margin=0.0):
        x0, x1, y0, y1 = self.bounds(margin)
        return x0 <= x <= x1 and y0 <= y <= y1


class BoardroomLayout:

    def __init__(self, seed, difficulty):
        self.seed = seed
        self.difficulty = difficulty
        rng = random.Random(seed)
        self.obstacles = []
        self.memos = []
        self.powerUps = []
        self.seats = []
        self.oilCans = []
        self.minions = []
        self._layTable(rng)
        self._layMeeting(rng)

    # --- The table ---

    def _layTable(self, rng):
        start = Consts.TableStart + Consts.ClearStart
        end = Consts.TableEnd - Consts.ClearEnd
        # Laid out on the table's old width, then spread out to the real
        # one (_widen): the obstacles keep their places relative to the
        # table and the toons get the extra room (Arthur).
        half = Consts.LayoutHalfWidth - 1.2
        y = start
        segments = []
        while y + Consts.SegmentLength <= end + 0.01:
            segments.append(y)
            y += Consts.SegmentLength
        kinds = []
        # Each kind comes up a fair share, in a shuffled order, and never the
        # same twice in a row.
        pool = ['pile', 'pile2', 'pencil', 'ramp', 'slalom']
        double = Consts.lerpDifficulty(Consts.DoubleObstacleRange, self.difficulty)
        for i in range(len(segments)):
            choices = [k for k in pool if not kinds or k != kinds[-1]]
            kinds.append(rng.choice(choices))
        for y0, kind in zip(segments, kinds):
            mid = y0 + Consts.SegmentLength / 2.0
            tops = []
            if kind == 'pile':
                # One pile off to a side: the way round is on the other.
                w = rng.uniform(3.5, 5.0)
                x = rng.choice((-1, 1)) * rng.uniform(half - w - 4.0, half - w)
                h = rng.uniform(*Consts.PileHeight)
                pile = Obstacle(PILE, x, mid, w, rng.uniform(2.5, 3.5), h)
                self.obstacles.append(pile)
                tops.append(pile)
            elif kind == 'pile2':
                # Two piles with a gap between them, somewhere across.
                gap = rng.uniform(-4.5, 4.5)
                for side in (-1, 1):
                    edge = gap + side * Consts.FairGap / 2.0
                    far = side * half
                    w = abs(far - edge) / 2.0
                    if w < 1.5:
                        continue
                    pile = Obstacle(PILE, (edge + far) / 2.0, mid + rng.uniform(-1.5, 1.5), w,
                                    rng.uniform(2.0, 3.0), rng.uniform(*Consts.PileHeight))
                    self.obstacles.append(pile)
            elif kind == 'slalom':
                # Two piles on opposite sides, one after the other: weave.
                side = rng.choice((-1, 1))
                for k, dy in enumerate((-7.0, 7.0)):
                    w = rng.uniform(3.0, 4.0)
                    x = side * (1 if k == 0 else -1) * (half - w - rng.uniform(0.0, 1.0))
                    self.obstacles.append(Obstacle(PILE, x, mid + dy, w, rng.uniform(1.8, 2.4), rng.uniform(*Consts.PileHeight)))
            elif kind == 'pencil':
                # A pencil the width of the table, lying a little crooked.
                angle = rng.uniform(-10, 10)
                self.obstacles.append(Obstacle(PENCIL, 0, mid, half, 0.7, Consts.PencilHeight, angle))
            else:
                # A ramp up onto a pile; memos wait on top.
                w = rng.uniform(4.0, 5.0)
                x = rng.uniform(-half + w + 1.0, half - w - 1.0)
                h = rng.uniform(4.5, 6.0)
                pile = Obstacle(PILE, x, mid + 3.0, w, 3.0, h)
                self.obstacles.append(pile)
                self.obstacles.append(Obstacle(RAMP, x, mid - 4.5, w * 0.8, 4.5, h))
                tops.append(pile)
            # A second obstacle in the stretch now and then (more often in
            # the harder offices), always far enough from the first for a
            # good slider to hop the one and steer round the other.
            if kind == 'pile' and rng.random() < double:
                # A pencil rolled across the start of this stretch too.
                self.obstacles.append(Obstacle(PENCIL, 0, y0 + 1.5, half, 0.7, Consts.PencilHeight, rng.uniform(-6, 6)))
            elif kind == 'pencil' and rng.random() < double:
                # And a pile well past the pencil, off to a side, to steer
                # round after landing.
                w = rng.uniform(3.0, 3.8)
                self.obstacles.append(Obstacle(PILE, rng.choice((-1, 1)) * (half - w), mid + 10.0, w, 2.0,
                                               rng.uniform(*Consts.PileHeight)))
        self._widen(half)
        self._layRoute(rng, start, end)

    def _widen(self, half):
        # From the layout's width out to the table's: a pile against the
        # table's edge stays against it, the rest move out in proportion,
        # so the gaps between things (the room to slide) widen and the
        # obstacles stay their size. Memos on a pile's top go with it.
        new = Consts.TableHalfWidth - 1.2
        if abs(new - half) < 1e-6:
            return
        r = new / half
        tops = {}
        for i, (mx, my, mz) in enumerate(self.memos):
            if mz > Consts.TableTop + 0.01:
                for ob in self.obstacles:
                    if ob.kind == PILE and abs(ob.x - mx) < 1e-6 and abs(ob.y - my) < 1e-6:
                        tops[i] = ob
        for ob in self.obstacles:
            if ob.kind == PENCIL:
                ob.w = new
                ob.x *= r
            elif abs(ob.x) + ob.w >= half - 0.05:
                ob.x = math.copysign(new - ob.w, ob.x)
            else:
                ob.x *= r
        # A ramp goes where its pile went (just in front of it).
        for i, ob in enumerate(self.obstacles):
            if ob.kind == RAMP and i > 0 and self.obstacles[i - 1].kind == PILE:
                ob.x = self.obstacles[i - 1].x
        memos = []
        for i, (mx, my, mz) in enumerate(self.memos):
            if i in tops:
                memos.append((tops[i].x, my, mz))
                continue
            nx = mx * r
            memos.append((nx if not self.blockedAt(nx, my, 1.2) else mx, my, mz))
        self.memos = memos
        self.powerUps = [(kind, px * r if not self.blockedAt(px * r, py, 1.6) else px, py) for kind, px, py in self.powerUps]

    # --- The memos and power-ups ---

    def _walkable(self, x, y):
        # Can a sliding toon be here? On the table, not inside a pile (up
        # on a ramp's pile is fine: it slides up the ramp onto it).
        if abs(x) > Consts.TableHalfWidth - 1.3:
            return False
        for ob in self._pilesNear(y):
            if ob.contains(x, y, 1.0) and not self._rampPile(ob, x):
                return False
        return True

    def _pilesNear(self, y):
        # The piles by 10 ft stretch of table, for speed (the route checks
        # thousands of spots, on phones too).
        grid = getattr(self, '_pileGrid', None)
        if grid is None:
            grid = self._pileGrid = {}
            for ob in self.obstacles:
                if ob.kind == PILE:
                    for k in range(int((ob.y - ob.l - 1.5) // 10), int((ob.y + ob.l + 1.5) // 10) + 1):
                        grid.setdefault(k, []).append(ob)
        return grid.get(int(y // 10), ())

    def _rampPile(self, pile, x):
        # A pile with a ramp up to it, and x within the ramp's width.
        ramp = getattr(pile, 'ramp', 0)
        if ramp == 0:
            ramp = pile.ramp = next((ob for ob in self.obstacles if ob.kind == RAMP and abs(ob.x - pile.x) < 0.01
                                     and abs(ob.y - pile.y) < 10.0), None)
        return ramp is not None and abs(x - ramp.x) <= ramp.w - 0.6

    def _clearLeg(self, x0, y0, x1, y1):
        n = max(2, int(abs(y1 - y0) / 0.5))
        for i in range(n + 1):
            f = i / float(n)
            if not self._walkable(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f):
                return False
        return True

    def _layRoute(self, rng, start, end):
        """One line down the table a toon can slide at the normal speed,
        steering no harder than it easily can: round the piles, up the
        ramps, over the pencils. Every memo and power-up is laid along it,
        so all of them can be had in one run (Arthur), at a natural spacing:
        no heaps in one place and bare stretches in another. The line is new
        every game (the layout's seed is)."""
        # A grid down the table, a row every DY ft and a column every DX ft
        # across; from each row a toon can move at most `step` columns over
        # (no harder steering than it easily can at the normal speed).
        DY, DX = 1.5, 0.6
        reach = Consts.SteerSpeed * 0.55 / Consts.SlideSpeed
        step = max(1, int(reach * DY / DX))
        half = Consts.TableHalfWidth - 1.6
        cols = int(2 * half / DX) + 1
        xs = [-half + j * DX for j in range(cols)]
        rows = int((end - start) / DY) + 1
        ys = [start + i * DY for i in range(rows)]
        walk = [[self._walkable(x, y) for x in xs] for y in ys]
        # Working back from the far end: from which spots can the end still
        # be reached? (A greedy walk got boxed in behind wide piles.)
        ok = [None] * rows
        ok[-1] = walk[-1]
        def leg(i, j, k):
            # Clear all the way from row i, column j to row i+1, column k
            # (not just at both ends: a corner of a pile can be in between).
            return k == j or self._clearLeg(xs[j], ys[i], xs[k], ys[i + 1])

        for i in range(rows - 2, -1, -1):
            nxt = ok[i + 1]
            ok[i] = [walk[i][j] and any(nxt[k] and leg(i, j, k) for k in range(max(0, j - step), min(cols, j + step + 1)))
                     for j in range(cols)]
        # And forward from the start: a spot is reachable if a toon can get
        # to it from the start AND still go on to the end from it. Only those
        # spots get memos or power-ups (none behind a wall of piles, none up
        # on a pile with no ramp to it).
        good = [None] * rows
        good[0] = ok[0]
        for i in range(1, rows):
            prev = good[i - 1]
            good[i] = [ok[i][k] and any(prev[j] and leg(i - 1, j, k) for j in range(max(0, k - step), min(cols, k + step + 1)))
                       for k in range(cols)]
        self._reach = (start, DY, DX, half, good)
        self.route = []
        # The memos: scattered across the table stretch by stretch, as they
        # were (Arthur liked that spread: every toon in the party finds its
        # own), each stretch its own random count and spots, never two right
        # on top of each other. Memos wait on the ramped piles' tops too.
        self.memos = []
        y0 = start
        while y0 < end:
            y1 = min(end, y0 + Consts.SegmentLength)
            for k in range(rng.randint(*Consts.MemosPerSegment)):
                for tries in range(40):
                    mx = rng.uniform(-half, half)
                    my = rng.uniform(y0 + 1.0, y1 - 1.0)
                    if self.reachable(mx, my) and not self._nearPencil(mx, my, 1.8) \
                            and not self._nearMemo(mx, my, MemoSpacing):
                        self.memos.append((mx, my, self.heightAt(mx, my)))
                        break
            for ob in self._pilesNear((y0 + y1) / 2.0):
                if y0 <= ob.y < y1 and self._rampPile(ob, ob.x) and rng.random() < 0.85 \
                        and self.reachable(ob.x, ob.y) and not self._nearMemo(ob.x, ob.y, MemoSpacing):
                    self.memos.append((ob.x, ob.y, Consts.TableTop + ob.h))
            y0 = y1
        # The power-ups: spread evenly along the table, out in the open,
        # away from the memos.
        kinds = [INVULNERABLE] * Consts.NumInvulnerable + [HOP] * Consts.NumHop
        rng.shuffle(kinds)
        span = (end - start) / float(len(kinds) + 1)
        self.powerUps = []
        for i, kind in enumerate(kinds):
            base = start + span * (i + 1)
            for tries in range(80):
                py = base + rng.uniform(-span * 0.4, span * 0.4)
                px = rng.uniform(-half + 1.0, half - 1.0)
                if self.reachable(px, py) and not self._nearMemo(px, py, 2.8) and not self._nearPencil(px, py, 2.0) \
                        and abs(self.heightAt(px, py) - Consts.TableTop) < 0.01:
                    self.powerUps.append((kind, px, py))
                    break

    def reachable(self, x, y):
        # On the table where a sliding toon can get to (see _layRoute).
        start, DY, DX, half, good = self._reach
        i = int(round((y - start) / DY))
        j = int(round((x + half) / DX))
        if not (0 <= i < len(good) and 0 <= j < len(good[0])):
            return False
        return good[i][j] and self._walkable(x, y)

    def _nearPencil(self, x, y, r):
        for ob in self.obstacles:
            if ob.kind == PENCIL:
                line = ob.y + (x - ob.x) * math.tan(math.radians(ob.angle))
                if abs(y - line) < r:
                    return True
        return False

    def routeX(self, y):
        route = self.route
        for (x0, y0), (x1, y1) in zip(route, route[1:]):
            if y0 <= y <= y1:
                return x0 + (x1 - x0) * (y - y0) / max(1e-6, y1 - y0)
        return route[-1][0]

    def _nearMemo(self, x, y, r):
        return any(math.hypot(x - m[0], y - m[1]) < r for m in self.memos)

    def blockedAt(self, x, y, margin=0.0):
        # Anything a toon can't just walk over (the ramps are walked up).
        for ob in self.obstacles:
            if ob.kind != RAMP and ob.contains(x, y, margin):
                return ob
        return None

    def heightAt(self, x, y):
        # The height of what is under (x, y): the table, a pile's top or
        # partway up a ramp.
        z = Consts.TableTop
        for ob in self.obstacles:
            if not ob.contains(x, y):
                continue
            if ob.kind == PILE:
                z = max(z, Consts.TableTop + ob.h)
            elif ob.kind == RAMP:
                t = (y - (ob.y - ob.l)) / (2.0 * ob.l)
                z = max(z, Consts.TableTop + ob.h * max(0.0, min(1.0, t)))
        return z

    # --- The meeting ---

    def _layMeeting(self, rng):
        d = self.difficulty
        perSide = int(round(Consts.lerpDifficulty(Consts.SeatsPerSideRange, d)))
        chairs = []
        y = Consts.TableStart + Consts.SeatSpacing * 0.75
        while y < Consts.TableEnd - 6:
            chairs.append(y)
            y += Consts.SeatSpacing
        for side in (-1, 1):
            # Every chair down both sides has a Boss Cog in it (Arthur: no
            # empty chairs). perSide still draws from the rng, so the rest
            # of the layout stays as it was for a seed.
            ys = list(chairs)
            rng.shuffle(ys)
            for cy in chairs:
                offset = side * 0.5 * Consts.SeatSpacing / 2.0
                self.seats.append((side, cy + offset, True))
        # The oil cans stand at the table's edges; the minions overhead
        # each fly their own loop up and down the table.
        count = int(round(Consts.lerpDifficulty(Consts.OilCansRange, d)))
        start = Consts.TableStart + 30
        end = Consts.TableEnd - 30
        for i in range(count):
            cy = start + (end - start) * (i + 0.5) / count + rng.uniform(-6, 6)
            side = rng.choice((-1, 1))
            cx = side * (Consts.TableHalfWidth - 1.6)
            self.oilCans.append((cx, cy))
        count = int(round(Consts.lerpDifficulty(Consts.MinionsRange, d)))
        for i in range(count):
            self.minions.append({'y0': Consts.TableStart + 30 + (Consts.TableEnd - Consts.TableStart - 60) * (i + 0.5) / count,
                                 'ySwing': rng.uniform(30, 55), 'yRate': rng.uniform(0.12, 0.22),
                                 'xSwing': rng.uniform(6, Consts.TableHalfWidth - 2), 'xRate': rng.uniform(0.35, 0.6),
                                 'phase': rng.uniform(0, 2 * math.pi), 'name': rng.choice(Consts.MinionCogNames)})

    def minionPos(self, index, t):
        # Where minion `index` flies, `t` seconds into the game.
        m = self.minions[index]
        y = m['y0'] + m['ySwing'] * math.sin(m['yRate'] * t + m['phase'])
        y = max(Consts.TableStart + 6, min(Consts.TableEnd - 6, y))
        x = m['xSwing'] * math.sin(m['xRate'] * t + m['phase'] * 1.7)
        return (x, y, Consts.TableTop + Consts.MinionHeight)

    def bossSeats(self):
        return [i for i, seat in enumerate(self.seats) if seat[2]]

    def seatPos(self, index):
        side, y, taken = self.seats[index]
        return (side * Consts.SeatSideX, y, 0)

    def slickAt(self, can):
        # The spill reaches in from the can at the table's edge, never past
        # a couple of feet short of the middle: the rest of the table stays
        # dry to steer round it (Arthur: always a way to dodge the oil).
        cx, cy = self.oilCans[can]
        side = 1 if cx > 0 else -1
        return (side * (Consts.TableHalfWidth - Consts.SlickRadius), cy, Consts.SlickRadius)

    def canDodge(self, x0, y0, flight, hits, react=None):
        """Whether a toon sliding at the normal speed from (x0, y0) can keep
        clear of something landing `flight` seconds from now, which hits
        where hits(x, y) says: after a moment to react, some steer and some
        speed (slow, normal or fast) that keeps it off the piles and out of
        the hit when it comes down. The Boss Cogs only throw what can be
        dodged (Arthur: harder, never impossible)."""
        react = Consts.DodgeReact if react is None else react
        dt = 0.05
        for speed in (Consts.SlideSpeed, Consts.SlideSlowSpeed, Consts.SlideFastSpeed):
            for k in (0, -8, 8, -4, 4, -6, 6, -2, 2, -7, 7, -5, 5, -3, 3, -1, 1):
                steer = Consts.SteerSpeed * k / 8.0
                x, y, v, t = x0, y0, Consts.SlideSpeed, 0.0
                clear = True
                while t < flight - 1e-6:
                    if t >= react:
                        v = min(speed, v + Consts.SlideAccel * dt) if v < speed else max(speed, v - Consts.SlideAccel * dt)
                        x += steer * dt
                    y += v * dt
                    t += dt
                    if not self._walkable(x, y):
                        clear = False
                        break
                if clear and not hits(x, y):
                    return True
        return False

    def laneClear(self, slicks, y0, y1, lane=None):
        """Whether every row of the table from y0 to y1 still has a dry,
        clear stretch at least `lane` ft wide across: not under any of the
        slicks (x, y, radius) and not blocked by a pile (pencils are hopped,
        ramps slid up). The oil is only spilt or thrown where it leaves
        one, so a toon can always dodge it."""
        lane = lane or Consts.OilFreeLane
        half = Consts.TableHalfWidth - 1.0
        step = 0.5
        xs = [-half + i * step for i in range(int(2 * half / step) + 1)]
        y = y0
        while y <= y1:
            near = [(sx, sy, r) for sx, sy, r in slicks if abs(sy - y) < r]
            piles = [ob for ob in self._pilesNear(y) if ob.kind == PILE]
            run = best = 0.0
            for x in xs:
                wet = any((x - sx) ** 2 + (y - sy) ** 2 < r * r for sx, sy, r in near)
                if wet or any(ob.contains(x, y, 0.8) for ob in piles):
                    run = 0.0
                else:
                    run += step
                    best = max(best, run)
            if best < lane:
                return False
            y += 1.0
        return True
