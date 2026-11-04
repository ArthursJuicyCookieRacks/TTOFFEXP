"""The boardroom table's layout, made from a seed and the difficulty, so
the AI and every client lay out the same table without sending it all."""
import math
import random

from toontown.cogdominium import CogdoBoardroomGameConsts as Consts

# Obstacle kinds.
PILE = 'pile'          # A pile of paperwork: go round it, or up a ramp.
PENCIL = 'pencil'      # A giant pencil lying across the table: hop it.
RAMP = 'ramp'          # A ramp up onto a pile, with memos on top.

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
            # The memos for this stretch: on the table round the obstacle,
            # and on top of a pile now and then.
            count = rng.randint(*Consts.MemosPerSegment)
            for i in range(count):
                for tries in range(20):
                    mx = rng.uniform(-half + 1.0, half - 1.0)
                    my = rng.uniform(y0 + 2.0, y0 + Consts.SegmentLength - 2.0)
                    if not self.blockedAt(mx, my, 1.4):
                        self.memos.append((mx, my, Consts.TableTop))
                        break
            for pile in tops:
                if rng.random() < 0.85:
                    self.memos.append((pile.x, pile.y, Consts.TableTop + pile.h))
        # The power-ups, spread out along the table, in the open.
        kinds = [INVULNERABLE] * Consts.NumInvulnerable + [HOP] * Consts.NumHop
        rng.shuffle(kinds)
        span = (end - start) / float(len(kinds) + 1)
        for i, kind in enumerate(kinds):
            for tries in range(30):
                px = rng.uniform(-half + 2.0, half - 2.0)
                py = start + span * (i + 1) + rng.uniform(-span * 0.3, span * 0.3)
                if not self.blockedAt(px, py, 2.0) and not self._nearMemo(px, py, 2.5):
                    self.powerUps.append((kind, px, py))
                    break

        self._widen(half)

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
        # The spill reaches in from the can at the table's edge.
        cx, cy = self.oilCans[can]
        return (cx * 0.55, cy, Consts.SlickRadius)
