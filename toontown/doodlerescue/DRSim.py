"""Doodle Rescue, the rules: Disney's Toontown 2.0 prototype minigame
("DoodleAI"), rebuilt from the scripts and the scene of its Unity web
player.

An astronaut toon has one minute to free the doodles a Cog base holds in
a pen. Doodles run from the toon; one that runs onto a spring plant is
flung into the air as a sparkling rocket doodle, and each rocket that
comes down on the far side of the pen wall is one doodle saved. Twenty-
four saved wins. The wall closes in twice on the way.

Every number here is Disney's (PlayerController, CameraController,
DoodleFlingerBot/Old, Fire, Rocket, DoodleFree, clockScript, ActivateWall,
PenWallControl and the UnitySteer flocking library), in Unity's own units
and axes (x right, y up, z forward) and Unity's own order of work: fixed
0.02 s physics steps, then the scripts once a frame, then the camera.
Unity's physics engine itself is stood in for by a small one written for
this arena (flat ground, round bodies, wall prisms).

Nothing here draws anything: DRGame does, from the state and the events
list.
"""

import math
import random

FIXED = 0.02
GRAVITY = 9.81
GAME_SECONDS = 60.0          # clockScript.startTime
MIDDLE_RING = 30.0           # ActivateWall.middleRingTimer
INNER_RING = 45.0            # ActivateWall.innerRingTimer
INNER_SPEED = 0.25           # PenWallControl.SetInnerRing
WIN_COUNT = 23               # DoodleFree.winCount: more than this many saved wins
OVERTIME = 20.0              # see Sim.__clock

# What the playground changes. Disney's prototype asked for 24 of the 29 doodles in its one minute, which next to nobody manages (a toon
# standing still sees about 14 fling themselves out, one herding well about 17). On the trolley the pen asks for fewer everywhere, and for
# more playground by playground, as Toontown's own trolley games get harder: doodles to save, for difficulty 0 (Toontown Central) to 1
# (Donald's Dreamland). The minute, the walls and the doodles themselves are Disney's everywhere.
NEED = ((0.0, 14), (0.2, 15), (0.4, 16), (0.6, 17), (0.8, 18), (1.0, 20))


def need(difficulty):
    """How many doodles a playground asks for: the row of NEED nearest its difficulty."""
    return min(NEED, key=lambda row: abs(row[0] - difficulty))[1]
# The prototype turned the toon three degrees a frame; its web player ran at 60 frames a second.
FRAMES = 60.0

# Doodle (prefab DoodleBounce): Rigidbody and colliders
D_MASS = 15.0
D_DRAG = 2.0
D_RADIUS = 0.948346
D_HEIGHT = 3.215295
D_CENTRE_Y = 1.60179
D_CENTRE_Z = -0.178546
D_REST = D_HEIGHT * 0.5 - D_CENTRE_Y          # the body's own height when its capsule stands on the ground
D_BOX = (1.63136 * 0.5, 3.19 * 0.5, 1.49243 * 0.5)
D_BOX_Y = 1.48436
D_FRICTION = 1.0             # Rubber, combined by "maximum"
D_BOUNCE_GROUND = 0.25       # Rubber 0.5 averaged with the ground's 0
D_BOUNCE_DOODLE = 0.5
# UnitySteer on each DoodleBounce
V_MAX_SPEED = 200.0
V_MAX_FORCE = 200.0
V_RADIUS = 1.0
TICK_STEPS = 6               # a tick lapse of 0.1 s, tested with "next tick < now" every 0.02 s
RADAR = 10.0
SEPARATION = (12.0, 3.0, 7.5, -0.707)
ALIGNMENT = (8.0, 3.0, 7.5, 0.7)
COHESION = (12.0, 3.0, 7.5, -0.15)
TETHER = (20.0, 40.0)
AVOID = (1.0, 0.75, 2.0)

# Rocket doodle (prefab DoodleRocket): a free Rigidbody with a capsule, material Bouncy
R_SCALE = 1.00781
R_MASS = 1.0
R_CENTRE_Y = 1.34144 * R_SCALE
R_RADIUS = 0.68 * R_SCALE
R_HALF = (2.29193 * 0.5 - 0.68) * R_SCALE       # from the middle to the middle of each round end
R_BOUNCE = 1.0               # Bouncy, combined by "maximum"
R_FRICTION = 0.35            # Bouncy 0.3 averaged with the 0.4 of things that have no material
R_FRICTION_DOODLE = 1.0      # against Rubber, combined by "maximum"
R_SPIN = 7.0                 # Unity's limit on a body's spin
R_SPIN_DRAG = 0.05
R_BOUNCES = 10               # Rocket.numOfBounces


def capsuleInertia(mass, radius, length):
    cyl = math.pi * radius * radius * length
    ball = 4.0 / 3.0 * math.pi * radius ** 3
    mc, ms = mass * cyl / (cyl + ball), mass * ball / (cyl + ball)
    along = mc * radius * radius * 0.5 + ms * 0.4 * radius * radius
    across = mc * (length * length / 12.0 + radius * radius * 0.25) + ms * (0.4 * radius * radius + length * length * 0.25 + 0.375 * length * radius)
    return (across, along)


R_INERTIA = capsuleInertia(R_MASS, R_RADIUS, R_HALF * 2.0)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    cx, cy, cz = y * vz - z * vy + w * vx, z * vx - x * vz + w * vy, x * vy - y * vx + w * vz
    return (vx + 2.0 * (y * cz - z * cy), vy + 2.0 * (z * cx - x * cz), vz + 2.0 * (x * cy - y * cx))


def qeuler(pitch, yaw):
    """Unity's Quaternion.Euler(pitch, yaw, 0), in degrees."""
    p, y = math.radians(pitch) * 0.5, math.radians(yaw) * 0.5
    return qmul((0.0, math.sin(y), 0.0, math.cos(y)), (math.sin(p), 0.0, 0.0, math.cos(p)))


def qslerp(a, b, t):
    t = clamp(t, 0.0, 1.0)
    d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    if d < 0.0:
        b = (-b[0], -b[1], -b[2], -b[3])
        d = -d
    if d > 0.9995:
        q = tuple(a[i] + (b[i] - a[i]) * t for i in range(4))
    else:
        th = math.acos(d)
        s = math.sin(th)
        wa, wb = math.sin((1.0 - t) * th) / s, math.sin(t * th) / s
        q = tuple(a[i] * wa + b[i] * wb for i in range(4))
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return tuple(c / n for c in q)


def ccw(poly):
    area = 0.0
    for i in range(len(poly)):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % len(poly)]
        area += ax * bz - bx * az
    return [tuple(p) for p in (poly if area >= 0 else poly[::-1])]


def polyNear(poly, px, pz):
    """(inside, distance to the edge, the nearest point on the edge) of a convex outline seen from above."""
    inside = True
    best = 1e30
    bx = bz = 0.0
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        cx, cz = poly[i + 1 - n]
        ex, ez = cx - ax, cz - az
        if ex * (pz - az) - ez * (px - ax) < 0.0:
            inside = False
        t = ((px - ax) * ex + (pz - az) * ez) / (ex * ex + ez * ez or 1.0)
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        qx, qz = ax + ex * t, az + ez * t
        d = (px - qx) * (px - qx) + (pz - qz) * (pz - qz)
        if d < best:
            best, bx, bz = d, qx, qz
    return inside, math.sqrt(best), bx, bz


def polyBox(poly):
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    return (min(xs), max(xs), min(zs), max(zs))


def polysTouch(a, b):
    """Two convex outlines overlap (separating axes)."""
    for one, two in ((a, b), (b, a)):
        n = len(one)
        for i in range(n):
            ax, az = one[i]
            cx, cz = one[i + 1 - n]
            nx, nz = cz - az, ax - cx           # outward for a counter-clockwise outline
            if all((px - ax) * nx + (pz - az) * nz > 0.0 for px, pz in two):
                return False
    return True


class Prism:
    """A solid with a convex outline seen from above and a flat bottom and top."""

    def __init__(self, poly, y, kind, index):
        self.kind = kind
        self.index = index
        self.y0, self.y1 = y
        self.set(poly)

    def set(self, poly):
        self.poly = ccw(poly)
        self.box = polyBox(self.poly)

    def ball(self, x, y, z, r):
        """Contact of a ball with the solid: (depth, nx, ny, nz, px, py, pz) or None."""
        b = self.box
        if x < b[0] - r or x > b[1] + r or z < b[2] - r or z > b[3] + r or y < self.y0 - r or y > self.y1 + r:
            return None
        inside, d, qx, qz = polyNear(self.poly, x, z)
        if inside:
            if y >= self.y1:
                depth = r - (y - self.y1)
                return (depth, 0.0, 1.0, 0.0, x, self.y1, z) if depth > 0.0 else None
            if y <= self.y0:
                depth = r - (self.y0 - y)
                return (depth, 0.0, -1.0, 0.0, x, self.y0, z) if depth > 0.0 else None
            # the middle of the ball is in the solid: out by the nearest face
            top, bottom = self.y1 - y, y - self.y0
            if top <= d and top <= bottom:
                return (top + r, 0.0, 1.0, 0.0, x, self.y1, z)
            if bottom <= d:
                return (bottom + r, 0.0, -1.0, 0.0, x, self.y0, z)
            nx, nz = qx - x, qz - z
            n = math.hypot(nx, nz) or 1.0
            return (d + r, nx / n, 0.0, nz / n, qx, y, qz)
        qy = clamp(y, self.y0, self.y1)
        dx, dy, dz = x - qx, y - qy, z - qz
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist >= r or dist == 0.0:
            return None
        return (r - dist, dx / dist, dy / dist, dz / dist, qx, qy, qz)

    def circle(self, x, z, r):
        """Push of an upright round body out of the solid's side: (depth, nx, nz) or None."""
        b = self.box
        if x < b[0] - r or x > b[1] + r or z < b[2] - r or z > b[3] + r:
            return None
        inside, d, qx, qz = polyNear(self.poly, x, z)
        if inside:
            nx, nz = qx - x, qz - z
            n = math.hypot(nx, nz)
            if n == 0.0:
                return None
            return (d + r, nx / n, nz / n)
        if d >= r or d == 0.0:
            return None
        return (r - d, (x - qx) / d, (z - qz) / d)


class Doodle:
    def __init__(self, ident, pos, fwd, old, runSpeed=450.0, aware=15.0, scared=10.0):
        self.id = ident
        self.old = old
        self.x, self.y, self.z = pos
        self.fx, self.fy, self.fz = fwd
        self.runSpeed = runSpeed
        self.aware = aware
        self.scaredAt = scared
        self.vx = self.vy = self.vz = 0.0           # the Rigidbody's velocity
        self.Fx = self.Fy = self.Fz = 0.0           # forces added since the last physics step
        self.speed = 0.0                            # the steering vehicle's own speed, along forward
        self.sx = self.sy = self.sz = 0.0           # its smoothed acceleration
        self.scared = False
        self.alive = True
        self.anim = 'idle' if old else 'walkHappy'
        self.vehicles = []
        self.obstacles = []
        self.forces = [(0.0, 0.0, 0.0)] * 5
        self.tick = 1 + ident % TICK_STEPS          # (Unity ticked every doodle in the same step; spread out here so no step carries them all)

    def centre(self):
        """The middle of the capsule, seen from above."""
        h = math.hypot(self.fx, self.fz)
        if h < 1e-6:
            return self.x, self.z
        return self.x + self.fx / h * D_CENTRE_Z, self.z + self.fz / h * D_CENTRE_Z

    def box(self):
        """The trigger box seen from above."""
        h = math.hypot(self.fx, self.fz)
        fx, fz = (self.fx / h, self.fz / h) if h > 1e-6 else (0.0, 1.0)
        rx, rz = fz, -fx
        hx, hz = D_BOX[0], D_BOX[2]
        return [(self.x - rx * hx - fx * hz, self.z - rz * hx - fz * hz), (self.x + rx * hx - fx * hz, self.z + rz * hx - fz * hz),
                (self.x + rx * hx + fx * hz, self.z + rz * hx + fz * hz), (self.x - rx * hx + fx * hz, self.z - rz * hx + fz * hz)]


class Rocket:
    """A rocket doodle: a free rigid capsule (two round ends and the middle between them are what touch things)."""

    def __init__(self, ident, pos, q, vel):
        self.id = ident
        self.q = q
        up = qrot(q, (0.0, R_CENTRE_Y, 0.0))
        self.x, self.y, self.z = pos[0] + up[0], pos[1] + up[1], pos[2] + up[2]     # the middle of the capsule
        self.vx, self.vy, self.vz = vel
        self.wx = self.wy = self.wz = 0.0
        self.bounces = 0
        self.touching = set()
        self.alive = True
        self.age = 0.0

    def origin(self):
        up = qrot(self.q, (0.0, R_CENTRE_Y, 0.0))
        return (self.x - up[0], self.y - up[1], self.z - up[2])

    def balls(self):
        ax, ay, az = qrot(self.q, (0.0, R_HALF, 0.0))
        return ((self.x - ax, self.y - ay, self.z - az), (self.x + ax, self.y + ay, self.z + az), (self.x, self.y, self.z))

    def hit(self, px, py, pz, nx, ny, nz, bounce, friction):
        """A touch at a point of the capsule, against something that does not give: Unity's bounce and friction, as impulses."""
        rx, ry, rz = px - self.x, py - self.y, pz - self.z
        ux, uy, uz = self.vx + self.wy * rz - self.wz * ry, self.vy + self.wz * rx - self.wx * rz, self.vz + self.wx * ry - self.wy * rx
        vn = ux * nx + uy * ny + uz * nz
        if vn >= 0.0:
            return
        jn = -(1.0 + bounce) * vn / self.__k(rx, ry, rz, nx, ny, nz)
        self.__impulse(rx, ry, rz, nx * jn, ny * jn, nz * jn)
        ux, uy, uz = self.vx + self.wy * rz - self.wz * ry, self.vy + self.wz * rx - self.wx * rz, self.vz + self.wx * ry - self.wy * rx
        vn = ux * nx + uy * ny + uz * nz
        tx, ty, tz = ux - vn * nx, uy - vn * ny, uz - vn * nz
        slide = math.sqrt(tx * tx + ty * ty + tz * tz)
        if slide > 1e-6:
            tx, ty, tz = tx / slide, ty / slide, tz / slide
            jt = min(slide / self.__k(rx, ry, rz, tx, ty, tz), friction * jn)
            self.__impulse(rx, ry, rz, -tx * jt, -ty * jt, -tz * jt)

    def __inertia(self, x, y, z):
        """The inverse inertia tensor (in the world) times a vector."""
        q = self.q
        lx, ly, lz = qrot((-q[0], -q[1], -q[2], q[3]), (x, y, z))
        return qrot(q, (lx / R_INERTIA[0], ly / R_INERTIA[1], lz / R_INERTIA[0]))

    def __k(self, rx, ry, rz, nx, ny, nz):
        ax, ay, az = self.__inertia(ry * nz - rz * ny, rz * nx - rx * nz, rx * ny - ry * nx)
        cx, cy, cz = ay * rz - az * ry, az * rx - ax * rz, ax * ry - ay * rx
        return 1.0 / R_MASS + cx * nx + cy * ny + cz * nz

    def __impulse(self, rx, ry, rz, jx, jy, jz):
        self.vx += jx / R_MASS
        self.vy += jy / R_MASS
        self.vz += jz / R_MASS
        ax, ay, az = self.__inertia(ry * jz - rz * jy, rz * jx - rx * jz, rx * jy - ry * jx)
        self.wx += ax
        self.wy += ay
        self.wz += az


class Axis:
    """Unity's Input.GetAxis for a pair of keys: gravity 3, sensitivity 3, snap."""

    def __init__(self):
        self.value = 0.0

    def update(self, raw, dt):
        if raw:
            if self.value * raw < 0.0:
                self.value = 0.0
            self.value = clamp(self.value + raw * 3.0 * dt, -1.0, 1.0)
        elif self.value > 0.0:
            self.value = max(0.0, self.value - 3.0 * dt)
        elif self.value < 0.0:
            self.value = min(0.0, self.value + 3.0 * dt)
        return self.value


class Sim:
    def __init__(self, data, seed=None, need=None):
        self.rng = random.Random(seed)
        # More than this many saved wins (no need given: the prototype's own 23).
        self.winCount = WIN_COUNT if need is None else int(need) - 1
        self.data = data
        self.time = 0.0             # Unity's Time.time
        self.steps = 0
        self.carry = 0.0
        self.events = []
        self.score = 0
        self.state = 'play'         # 'play', 'won', 'lost'
        self.timeRemaining = GAME_SECONDS
        self.percent = 100.0
        self.clockPaused = False
        self.overtime = None
        self.villain = False
        self.nextId = 0

        p = data['player']
        self.px, self.py, self.pz = p['pos']
        self.yaw = math.degrees(math.atan2(p['fwd'][0], p['fwd'][2]))
        self.pr = p['radius']
        self.pheight = p['height']
        self.pbox = p['box'][0] * 0.5
        self.pvy = 0.0
        self.moveX = self.moveZ = 0.0
        self.grounded = True
        self.bounce = False
        self.pvel = (0.0, 0.0, 0.0)             # CharacterController.velocity
        self.jumpHeld = False
        self.axisH = Axis()
        self.axisV = Axis()
        self.panim = 'idle'
        self.padTouch = set()
        self.plantTouch = set()

        c = data['camera']
        f = qrot(c['q'], (0.0, 0.0, 1.0))
        self.camX = math.degrees(math.atan2(f[0], f[2]))
        self.camY = -math.degrees(math.asin(clamp(f[1], -1.0, 1.0)))
        self.camQ = tuple(c['q'])
        self.camPos = tuple(c['pos'])
        self.camDistance = 4.0

        self.doodles = []
        for d in data['doodles']:
            self.doodles.append(Doodle(self.__id(), d['pos'], d['fwd'], d['old'], d['runSpeed'], d['aware'], d['scared']))
        self.rockets = []

        self.sphereR = data['sphere']['r']
        self.wallClip = 'middleRing'
        self.wallFrame = 0.0
        self.wallsMoving = None     # (clip, seconds into it)
        self.middleDone = False
        self.innerDone = False
        self.walls = [Prism(w['frames']['middleRing'][0], w['y'], 'wall', i) for i, w in enumerate(data['walls'])]
        self.counters = [Prism(c['frames']['middleRing'][0], c['y'], 'counter', i) for i, c in enumerate(data['counters'])]
        self.wallPos = [None] * len(self.walls)
        self.counterPos = [None] * len(self.counters)
        self.__placeWalls()
        self.wallReach = self.__wallReach()

        self.pads = data['pads']
        self.padBox = []
        self.padGrid = {}
        self.padTimers = []         # (time, pad, clip): Fire's "ten seconds later, play idle"
        for i, pad in enumerate(self.pads):
            box = Prism(pad['box']['quad'], pad['box']['y'], 'pad', i)
            self.padBox.append(box)
            pad['trigPoly'] = ccw(pad['trig']['quad'])
            b = box.box
            for gx in range(int((b[0] - 2.0) // 4), int((b[1] + 2.0) // 4) + 1):
                for gz in range(int((b[2] - 2.0) // 4), int((b[3] + 2.0) // 4) + 1):
                    self.padGrid.setdefault((gx, gz), []).append(i)
            self.padTimers.append((pad['stagger'], i, 'idle'))          # Fire.Start
            # what a doodle's radar makes of the pad's three colliders (see __radar)
            cx = sum(q[0] for q in box.poly) * 0.25
            cz = sum(q[1] for q in box.poly) * 0.25
            cy = (box.y0 + box.y1) * 0.5
            ext = max((b[1] - b[0]) * 0.5, (b[3] - b[2]) * 0.5, (box.y1 - box.y0) * 0.5)
            disc = pad['disc']
            rr = max(disc['r'])
            pad['aabbs'] = [((b[0], box.y0, b[2]), (b[1], box.y1, b[3])),
                            ((disc['c'][0] - rr, disc['y'][0], disc['c'][1] - rr), (disc['c'][0] + rr, disc['y'][1], disc['c'][1] + rr)),
                            ((min(q[0] for q in pad['trigPoly']), pad['trig']['y'][0], min(q[1] for q in pad['trigPoly'])),
                             (max(q[0] for q in pad['trigPoly']), pad['trig']['y'][1], max(q[1] for q in pad['trigPoly'])))]

            def ball(origin):
                return (origin[0], origin[1], origin[2], math.sqrt((origin[0] - cx) ** 2 + (origin[1] - cy) ** 2 + (origin[2] - cz) ** 2) + ext)
            root = ball(pad['pos'])
            pad['balls'] = [ball(pad['plantPos']), (root[0], root[1], root[2], max(root[3], rr)), ball(pad['launcher']['pos'][:1] + [pad['trig']['y'][0]] + pad['launcher']['pos'][2:])]
        self.padTimers.sort()
        self.obstacleCache = {}

    def __id(self):
        self.nextId += 1
        return self.nextId

    # ---- the pen wall
    def __placeWalls(self):
        clip, frame = self.wallClip, self.wallFrame
        i = int(frame)
        t = frame - i
        for group, prisms, where in ((self.data['walls'], self.walls, self.wallPos), (self.data['counters'], self.counters, self.counterPos)):
            for k, w in enumerate(group):
                frames = w['frames'][clip]
                a = frames[min(i, len(frames) - 1)]
                if t > 0.0 and i + 1 < len(frames):
                    b = frames[i + 1]
                    a = [(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t) for p, q in zip(a, b)]
                prisms[k].set(a)

    def __wallReach(self):
        """The nearest any wall comes to the middle (nothing inside this needs testing against the walls)."""
        best = 1e9
        for w in self.walls:
            inside, d, qx, qz = polyNear(w.poly, 0.0, 0.0)
            best = min(best, d)
        return best

    def __walls(self, dt):
        """ActivateWall and PenWallControl: at 30 s the middle ring clip, at 45 s the inner ring clip at a quarter speed."""
        if not self.middleDone and self.time > MIDDLE_RING:
            self.middleDone = True
            self.wallsMoving = ['middleRing', 0.0, 1.0]
            self.events.append(('gears',))
            self.events.append(('walls', 'middleRing'))
        elif self.middleDone and not self.innerDone and self.time > INNER_RING:
            self.innerDone = True
            self.wallsMoving = ['innerRing', 0.0, INNER_SPEED]
            self.events.append(('gears',))
            self.events.append(('gears',))          # ActivateWall plays the sound and so does SetInnerRing
            self.events.append(('walls', 'innerRing'))
        if self.wallsMoving is None:
            return
        clip, t, speed = self.wallsMoving
        rate = self.data['pen']['rate'][clip]
        last = self.data['pen']['clips'][clip] - 1
        t += dt * speed
        self.wallsMoving[1] = t
        self.wallClip = clip
        self.wallFrame = min(t * rate, float(last))
        if t * rate >= last:
            self.wallsMoving = None
        self.__placeWalls()
        self.wallReach = self.__wallReach()

    # ---- one frame
    def update(self, dt, left=False, right=False, up=False, down=False, jump=False, mouse=(0.0, 0.0)):
        """A frame of dt seconds. mouse: how far the mouse moved, in Unity's "Mouse X / Mouse Y" units."""
        del self.events[:]
        if self.state != 'play':
            return
        dt = min(dt, 0.1)
        self.carry += dt
        while self.carry >= FIXED:
            self.carry -= FIXED
            self.steps += 1
            self.time = self.steps * FIXED
            self.__fixed()
            if self.state != 'play':
                return
        self.__player(dt, (1 if right else 0) - (1 if left else 0), (1 if up else 0) - (1 if down else 0), jump, mouse[0])
        self.__flee(dt)
        self.__pads()
        self.__clock(dt)
        self.__camera(dt, mouse)
        self.doodles = [d for d in self.doodles if d.alive]
        self.rockets = [r for r in self.rockets if r.alive]

    # ---- physics step
    def __fixed(self):
        self.__walls(FIXED)
        for d in self.doodles:
            if d.alive and not d.old:
                self.__steer(d)
        for d in self.doodles:
            if d.alive:
                self.__doodleBody(d)
        self.__doodlePairs()
        for d in self.doodles:
            if d.alive:
                self.__doodleTouch(d)
        for r in self.rockets:
            if r.alive:
                self.__rocket(r)
        if self.score > self.winCount and self.state == 'play':          # DoodleFree.Update
            self.state = 'won'
            self.events.append(('won',))

    # ---- UnitySteer: Radar, the five steering behaviours, AutonomousVehicle
    def __radar(self, d):
        """RadarPing: every collider on the doodle and obstacle layers whose bounding box comes within 10 of the doodle."""
        x, y, z = d.x, d.y, d.z
        r2 = RADAR * RADAR
        vehicles = []
        for o in self.doodles:
            if o is d or o.old or not o.alive:
                continue
            dx, dz = abs(o.x - x) - 1.2, abs(o.z - z) - 1.2
            dy = max(o.y + D_BOX_Y - D_BOX[1] - y, y - (o.y + D_CENTRE_Y + D_HEIGHT * 0.5), 0.0)
            if (dx * dx if dx > 0.0 else 0.0) + (dz * dz if dz > 0.0 else 0.0) + dy * dy <= r2:
                vehicles.append(o)

        def near(lo, hi):
            ax = lo[0] - x if x < lo[0] else x - hi[0] if x > hi[0] else 0.0
            ay = lo[1] - y if y < lo[1] else y - hi[1] if y > hi[1] else 0.0
            az = lo[2] - z if z < lo[2] else z - hi[2] if z > hi[2] else 0.0
            return ax * ax + ay * ay + az * az <= r2

        cache = self.obstacleCache
        obstacles = []
        for i, pad in enumerate(self.pads):
            p = pad['pos']
            if abs(p[0] - x) > 13.5 or abs(p[2] - z) > 13.5:
                continue
            for k, (lo, hi) in enumerate(pad['aabbs']):
                if near(lo, hi):
                    obstacles.append(pad['balls'][k])
        s = self.sphereR
        if near((-s, -s, -s), (s, s, s)):
            obstacles.append((0.0, 0.0, 0.0, s))
        if math.hypot(x, z) > self.wallReach - RADAR - 1.0:
            for group, prisms, name in ((self.data['walls'], self.walls, 'w'), (self.data['counters'], self.counters, 'c')):
                for k, prism in enumerate(prisms):
                    if name == 'c' and group[k]['layer'] != 10:
                        continue
                    b = prism.box
                    if near((b[0], prism.y0, b[2]), (b[1], prism.y1, b[3])):
                        key = (name, k)
                        if key not in cache:
                            # SphericalObstacle.GetObstacle: around the object's own origin, far enough out to hold its collider's bounding box. Worked out once and kept, as Unity's cache did.
                            ox, oy, oz = self.__origin(name, k)
                            cx, cy, cz = (b[0] + b[1]) * 0.5, (prism.y0 + prism.y1) * 0.5, (b[2] + b[3]) * 0.5
                            ext = max((b[1] - b[0]) * 0.5, (prism.y1 - prism.y0) * 0.5, (b[3] - b[2]) * 0.5)
                            cache[key] = (ox, oy, oz, math.sqrt((ox - cx) ** 2 + (oy - cy) ** 2 + (oz - cz) ** 2) + ext)
                        obstacles.append(cache[key])
        d.vehicles = vehicles
        d.obstacles = obstacles

    def __origin(self, name, k):
        """Where a wall piece's (or counting slab's) own origin is now: the piece's present outline against its first one gives its move."""
        group = self.data['walls'] if name == 'w' else self.data['counters']
        o = group[k]['origin']
        first = ccw(group[k]['frames']['middleRing'][0])
        now = (self.walls if name == 'w' else self.counters)[k].poly
        # the move is a 2D affine map; three corners fix it
        (x0, z0), (x1, z1), (x2, z2) = first[0], first[1], first[2]
        det = (x1 - x0) * (z2 - z0) - (x2 - x0) * (z1 - z0)
        if abs(det) < 1e-9:
            return tuple(o)
        a = ((o[0] - x0) * (z2 - z0) - (x2 - x0) * (o[2] - z0)) / det
        b = ((x1 - x0) * (o[2] - z0) - (o[0] - x0) * (z1 - z0)) / det
        return (now[0][0] + a * (now[1][0] - now[0][0]) + b * (now[2][0] - now[0][0]), o[1], now[0][1] + a * (now[1][1] - now[0][1]) + b * (now[2][1] - now[0][1]))

    def __neighbours(self, d, rule, kind):
        """SteerForNeighbors.CalculateForce with the three rules' contributions."""
        weight, rmin, rmax, cos = rule
        sx = sy = sz = 0.0
        n = 0
        for o in d.vehicles:
            if not o.alive:
                continue
            dx, dy, dz = o.x - d.x, o.y - d.y, o.z - d.z
            dd = dx * dx + dy * dy + dz * dz
            if dd >= rmin * rmin:
                if dd > rmax * rmax:
                    continue
                m = math.sqrt(dd)
                if (d.fx * dx + d.fy * dy + d.fz * dz) / m <= cos:
                    continue
            if kind == 0:                       # separation
                if dd == 0.0:
                    continue
                sx -= dx / dd
                sy -= dy / dd
                sz -= dz / dd
            elif kind == 1:                     # alignment
                sx += o.fx
                sy += o.fy
                sz += o.fz
            else:                               # cohesion (the neighbour's place itself, not the way to it: Disney's copy of the library has it so)
                sx += o.x
                sy += o.y
                sz += o.z
            n += 1
        if n == 0:
            return (0.0, 0.0, 0.0)
        m = math.sqrt(sx * sx + sy * sy + sz * sz)
        if m < 1e-5:
            return (0.0, 0.0, 0.0)
        return (sx / m * weight, sy / m * weight, sz / m * weight)

    def __tether(self, d):
        weight, far = TETHER
        if math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z) > far:
            return ((-d.x - d.fx * d.speed) * weight, (-d.y - d.fy * d.speed) * weight, (-d.z - d.fz * d.speed) * weight)
        return (0.0, 0.0, 0.0)

    def __avoid(self, d):
        """SteerForSphericalObstacleAvoidance.CalculateForce."""
        weight, factor, seconds = AVOID
        if not d.obstacles:
            return (0.0, 0.0, 0.0)
        lx, ly, lz = d.fx * d.speed * seconds, d.fy * d.speed * seconds, d.fz * d.speed * seconds
        a = lx * lx + ly * ly + lz * lz
        line = math.sqrt(a)
        hit = False
        dist = float('inf')
        centre = None
        for ox, oy, oz, radius in d.obstacles:
            vx, vy, vz = d.x - ox, d.y - oy, d.z - oz
            b = 2.0 * (lx * vx + ly * vy + lz * vz)
            c = vx * vx + vy * vy + vz * vz - (radius + V_RADIUS) ** 2
            disc = b * b - 4.0 * a * c
            hit2 = False
            dist2 = float('inf')
            if disc >= 0.0:
                hit2 = True
                if a == 0.0:
                    dist2 = float('nan')
                elif disc == 0.0:
                    dist2 = abs(-b / (2.0 * a)) * line
                else:
                    root = math.sqrt(disc)
                    t1, t2 = (-b + root) / (2.0 * a), (-b - root) / (2.0 * a)
                    if t1 < 0.0 and t2 < 0.0:
                        hit2 = False
                    else:
                        dist2 = abs(t2 if abs(t1) >= abs(t2) else t1) * line
            if not hit or (hit2 and dist2 < dist):
                hit, dist, centre = hit2, dist2, (ox, oy, oz)
        if hit and dist < line:
            sx, sy, sz = d.x - centre[0], d.y - centre[1], d.z - centre[2]
            along = sx * d.fx + sy * d.fy + sz * d.fz
            px, py, pz = sx - d.fx * along, sy - d.fy * along, sz - d.fz * along
            m = math.sqrt(px * px + py * py + pz * pz)
            if m > 1e-5:
                px, py, pz = px / m * V_MAX_FORCE, py / m * V_MAX_FORCE, pz / m * V_MAX_FORCE
            else:
                px = py = pz = 0.0
            k = V_MAX_FORCE * factor
            return ((px + d.fx * k) * weight, (py + d.fy * k) * weight, (pz + d.fz * k) * weight)
        return (0.0, 0.0, 0.0)

    def __steer(self, d):
        """AutonomousVehicle.FixedUpdate."""
        d.tick -= 1
        if d.tick <= 0:
            d.tick = TICK_STEPS
            self.__radar(d)
            d.forces = [self.__neighbours(d, SEPARATION, 0), self.__neighbours(d, ALIGNMENT, 1), self.__neighbours(d, COHESION, 2), self.__tether(d), self.__avoid(d)]
        fx = fy = fz = 0.0
        for f in d.forces:
            fx += f[0]
            fy += f[1]
            fz += f[2]
        m = math.sqrt(fx * fx + fy * fy + fz * fz)
        if m > V_MAX_FORCE:
            fx, fy, fz = fx / m * V_MAX_FORCE, fy / m * V_MAX_FORCE, fz / m * V_MAX_FORCE
        ax, ay, az = fx / D_MASS, fy / D_MASS, fz / D_MASS
        d.sx += (ax - d.sx) * 0.4
        d.sy += (ay - d.sy) * 0.4
        d.sz += (az - d.sz) * 0.4
        vx, vy, vz = d.fx * d.speed + d.sx * FIXED, d.fy * d.speed + d.sy * FIXED, d.fz * d.speed + d.sz * FIXED
        m = math.sqrt(vx * vx + vy * vy + vz * vz)
        if m > V_MAX_SPEED:
            vx, vy, vz = vx / m * V_MAX_SPEED, vy / m * V_MAX_SPEED, vz / m * V_MAX_SPEED
        vy = d.fy * d.speed                     # planar
        speed = math.sqrt(vx * vx + vy * vy + vz * vz)
        d.speed = speed
        d.x += vx * FIXED                       # Rigidbody.MovePosition
        d.y += vy * FIXED
        d.z += vz * FIXED
        if speed > 0.0 and speed * speed > 0.01:
            nx, ny, nz = vx / speed, d.fy, vz / speed
            m = math.sqrt(nx * nx + ny * ny + nz * nz)
            if m > 1e-6:
                d.fx, d.fy, d.fz = nx / m, ny / m, nz / m

    # ---- the doodle's Rigidbody
    def __doodleBody(self, d):
        d.vx += d.Fx / D_MASS * FIXED
        d.vy += d.Fy / D_MASS * FIXED - GRAVITY * FIXED
        d.vz += d.Fz / D_MASS * FIXED
        d.Fx = d.Fy = d.Fz = 0.0
        k = max(0.0, 1.0 - D_DRAG * FIXED)
        d.vx *= k
        d.vy *= k
        d.vz *= k
        d.x += d.vx * FIXED
        d.y += d.vy * FIXED
        d.z += d.vz * FIXED
        if d.y <= D_REST:
            d.y = D_REST
            if d.vy < 0.0:
                push = -d.vy
                d.vy = push * D_BOUNCE_GROUND if push > 2.0 else 0.0
                # friction of the ground: as much as the push into it (and the body's weight) allows
                grip = D_FRICTION * max(push, GRAVITY * FIXED)
                h = math.hypot(d.vx, d.vz)
                if h <= grip:
                    d.vx = d.vz = 0.0
                else:
                    d.vx -= d.vx / h * grip
                    d.vz -= d.vz / h * grip

    def __push(self, d, depth, nx, nz, bounce=0.0, share=1.0):
        d.x += nx * depth * share
        d.z += nz * depth * share
        vn = d.vx * nx + d.vz * nz
        if vn < 0.0:
            d.vx -= (1.0 + bounce) * vn * nx
            d.vz -= (1.0 + bounce) * vn * nz

    def __doodleTouch(self, d):
        """The doodle against the solid things of the pen."""
        low, high = d.y + D_CENTRE_Y - D_HEIGHT * 0.5, d.y + D_CENTRE_Y + D_HEIGHT * 0.5
        cx, cz = d.centre()
        far = math.hypot(cx, cz)
        # the Cog base's middle (a ball with its middle at the ground)
        s = self.sphereR + D_RADIUS
        up = low + D_RADIUS
        if up < s:
            reach = math.sqrt(s * s - up * up)
            if far < reach and far > 1e-6:
                self.__push(d, reach - far, cx / far, cz / far, D_BOUNCE_GROUND)
        if far + D_RADIUS > self.wallReach - 0.5:
            for wall in self.walls:
                if low < wall.y1 and high > wall.y0:
                    hit = wall.circle(cx, cz, D_RADIUS)
                    if hit:
                        self.__push(d, hit[0], hit[1], hit[2], D_BOUNCE_GROUND)
                        cx, cz = d.centre()
            for slab in self.counters:
                if low < slab.y1 and high > slab.y0 and slab.circle(cx, cz, D_RADIUS):
                    # DoodleFlingerBot.OnCollisionEnter: a doodle that touches a counting slab is gone (and not counted)
                    d.alive = False
                    self.events.append(('gone', d.id))
                    return
        # the toon: a solid the doodle cannot move
        if low < self.py + self.pheight and high > self.py:
            dx, dz = cx - self.px, cz - self.pz
            m = math.hypot(dx, dz)
            reach = D_RADIUS + self.pr
            if m < reach and m > 1e-6:
                self.__push(d, reach - m, dx / m, dz / m, D_BOUNCE_GROUND)
        # Fire.OnTriggerEnter on a spring plant: the doodle's trigger box on the plant's solid box
        blow, bhigh = d.y + D_BOX_Y - D_BOX[1], d.y + D_BOX_Y + D_BOX[1]
        pads = self.padGrid.get((int(d.x // 4), int(d.z // 4)))
        if pads:
            box = None
            for i in pads:
                pb = self.padBox[i]
                if blow < pb.y1 and bhigh > pb.y0:
                    box = box or d.box()
                    if polysTouch(box, pb.poly):
                        self.__launch(d, i)
                        return

    def __doodlePairs(self):
        reach = D_RADIUS * 2.0
        live = [d for d in self.doodles if d.alive]
        spots = [d.centre() for d in live]
        for i in range(len(live)):
            a = live[i]
            ax, az = spots[i]
            for j in range(i + 1, len(live)):
                bx, bz = spots[j]
                dx, dz = bx - ax, bz - az
                if dx > reach or dx < -reach or dz > reach or dz < -reach:
                    continue
                m = math.hypot(dx, dz)
                b = live[j]
                if m >= reach or m < 1e-6 or abs(a.y - b.y) > D_HEIGHT:
                    continue
                nx, nz = dx / m, dz / m
                depth = (reach - m) * 0.5
                a.x -= nx * depth
                a.z -= nz * depth
                b.x += nx * depth
                b.z += nz * depth
                closing = (a.vx - b.vx) * nx + (a.vz - b.vz) * nz
                if closing > 0.0:
                    k = (1.0 + D_BOUNCE_DOODLE) * closing * 0.5
                    a.vx -= k * nx
                    a.vz -= k * nz
                    b.vx += k * nx
                    b.vz += k * nz
                spots[i] = a.centre()
                spots[j] = b.centre()
                ax, az = spots[i]

    def __launch(self, d, i):
        """Fire.OnTriggerEnter with a doodle: the plant springs, a rocket doodle leaves the launcher at 21 a second, the doodle is gone."""
        pad = self.pads[i]
        la = pad['launcher']
        up = la['up']
        speed = pad['speed']
        rocket = Rocket(self.__id(), la['pos'], tuple(la['q']), (up[0] * speed, up[1] * speed, up[2] * speed))
        self.rockets.append(rocket)
        d.alive = False
        self.padTimers.append((self.time + 10.0, i, 'idle'))
        self.padTimers.sort()
        self.events.append(('padAnim', i, 'spring'))
        self.events.append(('launch', i, d.id, rocket.id))

    # ---- the rocket doodle's Rigidbody
    def __rocket(self, r):
        r.age += FIXED
        r.vy -= GRAVITY * FIXED
        k = max(0.0, 1.0 - R_SPIN_DRAG * FIXED)
        r.wx *= k
        r.wy *= k
        r.wz *= k
        w = math.sqrt(r.wx * r.wx + r.wy * r.wy + r.wz * r.wz)
        if w > R_SPIN:
            r.wx, r.wy, r.wz = r.wx / w * R_SPIN, r.wy / w * R_SPIN, r.wz / w * R_SPIN
            w = R_SPIN
        r.x += r.vx * FIXED
        r.y += r.vy * FIXED
        r.z += r.vz * FIXED
        if w > 1e-5:
            half = w * FIXED * 0.5
            s = math.sin(half) / w
            q = qmul((r.wx * s, r.wy * s, r.wz * s, math.cos(half)), r.q)
            n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
            r.q = (q[0] / n, q[1] / n, q[2] / n, q[3] / n)
        # what it touches: (thing, depth, the way out, the point of the capsule that touches, friction)
        R = R_RADIUS
        contacts = []
        low = r.y - R_HALF - R
        far = math.hypot(r.x, r.z)
        nearWalls = far + R_HALF + R > self.wallReach - 0.5
        nearBase = far < self.sphereR + R_HALF + R + 0.5
        pads = self.padGrid.get((int(r.x // 4), int(r.z // 4))) if low < 3.0 else None
        doodles = ()
        if low < D_HEIGHT + 0.5:
            doodles = [d for d in self.doodles if d.alive and abs(d.x - r.x) < 3.5 and abs(d.z - r.z) < 3.5]
        others = [o for o in self.rockets if o is not r and o.alive and abs(o.x - r.x) < 4.0 and abs(o.z - r.z) < 4.0 and abs(o.y - r.y) < 4.0]
        for bx, by, bz in r.balls():
            if by < R:
                contacts.append((('ground',), R - by, 0.0, 1.0, 0.0, bx, by - R, bz, R_FRICTION))
            if nearWalls:
                for group in (self.counters, self.walls):
                    for prism in group:
                        hit = prism.ball(bx, by, bz, R)
                        if hit:
                            contacts.append(((prism.kind, prism.index), hit[0], hit[1], hit[2], hit[3], bx - hit[1] * R, by - hit[2] * R, bz - hit[3] * R, R_FRICTION))
            if nearBase:
                s = self.sphereR + R
                m = math.sqrt(bx * bx + by * by + bz * bz)
                if m < s and m > 1e-6:
                    nx, ny, nz = bx / m, by / m, bz / m
                    contacts.append((('base',), s - m, nx, ny, nz, bx - nx * R, by - ny * R, bz - nz * R, R_FRICTION))
            if pads:
                for i in pads:
                    hit = self.padBox[i].ball(bx, by, bz, R)
                    if hit:
                        contacts.append((('pad', i), hit[0], hit[1], hit[2], hit[3], bx - hit[1] * R, by - hit[2] * R, bz - hit[3] * R, R_FRICTION))
            for d in doodles:
                cx, cz = d.centre()
                dx, dz = bx - cx, bz - cz
                dy = by - clamp(by, d.y + D_CENTRE_Y - D_HEIGHT * 0.5 + D_RADIUS, d.y + D_CENTRE_Y + D_HEIGHT * 0.5 - D_RADIUS)
                m = math.sqrt(dx * dx + dy * dy + dz * dz)
                if m < D_RADIUS + R and m > 1e-6:
                    nx, ny, nz = dx / m, dy / m, dz / m
                    contacts.append((('doodle', d.id), D_RADIUS + R - m, nx, ny, nz, bx - nx * R, by - ny * R, bz - nz * R, R_FRICTION_DOODLE))
            if low < self.py + self.pheight:
                dx, dz = bx - self.px, bz - self.pz
                dy = by - clamp(by, self.py + self.pr, self.py + self.pheight - self.pr)
                m = math.sqrt(dx * dx + dy * dy + dz * dz)
                if m < self.pr + R and m > 1e-6:
                    nx, ny, nz = dx / m, dy / m, dz / m
                    contacts.append((('toon',), self.pr + R - m, nx, ny, nz, bx - nx * R, by - ny * R, bz - nz * R, R_FRICTION))
            for o in others:
                for ox, oy, oz in o.balls():
                    dx, dy, dz = bx - ox, by - oy, bz - oz
                    m = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if m < R * 2.0 and m > 1e-6:
                        nx, ny, nz = dx / m, dy / m, dz / m
                        contacts.append((('rocket', o.id), (R * 2.0 - m) * 0.5, nx, ny, nz, bx - nx * R, by - ny * R, bz - nz * R, R_FRICTION))
        touching = set()
        moved = {}
        for key, depth, nx, ny, nz, px, py, pz, friction in contacts:
            touching.add(key)
            # out of the solid (once for each thing, by its deepest touch)
            if depth > moved.get(key, 0.0):
                more = depth - moved.get(key, 0.0)
                moved[key] = depth
                r.x += nx * more
                r.y += ny * more
                r.z += nz * more
            r.hit(px, py, pz, nx, ny, nz, R_BOUNCE, friction)
            if key not in r.touching:
                # Rocket.OnCollisionEnter (and DoodleFree.OnCollisionEnter on a counting slab)
                r.touching.add(key)
                r.bounces += 1
                self.events.append(('bounce', r.id, key[0]))
                if key[0] == 'counter':
                    self.score += 1
                    r.alive = False
                    self.events.append(('saved', r.id, self.score, (px, py, pz)))
                    break
                if r.bounces > R_BOUNCES:
                    r.alive = False
                    d = Doodle(self.__id(), (px, max(py, D_REST), pz), (0.0, 0.0, 1.0), False)
                    self.doodles.append(d)
                    self.events.append(('reform', r.id, d.id))
                    break
        r.touching = touching

    # ---- once a frame: PlayerController, PlayerAnimation
    def __player(self, dt, h, v, jump, mouseX):
        p = self.data['player']
        H = self.axisH.update(h, dt)
        V = self.axisV.update(v, dt)
        self.jumpHeld = jump
        if self.grounded:
            self.yaw += (H * dt * FRAMES + mouseX) * p['turnSpeed']
            fx, fz = math.sin(math.radians(self.yaw)), math.cos(math.radians(self.yaw))
            speed = V * (p['forwardSpeed'] if V > 0.0 else p['backwardSpeed'] if V < 0.0 else 1.0)
            self.moveX, self.moveZ = fx * speed, fz * speed
            self.pvy = 0.0
            if jump:
                self.pvy = float(p['jumpSpeed'])
            if self.bounce:
                self.pvy = p['boing']
                self.bounce = False
                self.events.append(('boing',))
        self.pvy -= p['gravity'] * dt
        ox, oy, oz = self.px, self.py, self.pz
        self.__move(self.moveX * dt, self.pvy * dt, self.moveZ * dt)
        self.pvel = ((self.px - ox) / dt, (self.py - oy) / dt, (self.pz - oz) / dt) if dt > 0.0 else (0.0, 0.0, 0.0)
        flat = math.hypot(self.pvel[0], self.pvel[2])
        self.panim = 'run' if flat > 5.0 else 'walk' if flat > 0.1 else 'jump' if jump else 'idle'
        # the springs: PlayerController.OnTriggerEnter with anything named "spring", Fire.OnTriggerEnter with the toon
        touch = set()
        plants = set()
        low, high = self.py, self.py + max(self.pheight, self.pbox * 2.0)
        for gx in (int((self.px - 1.0) // 4), int((self.px + 1.0) // 4)):
            for gz in (int((self.pz - 1.0) // 4), int((self.pz + 1.0) // 4)):
                for i in self.padGrid.get((gx, gz), ()):
                    pad = self.pads[i]
                    disc = pad['disc']
                    trig = pad['trig']
                    on = False
                    if low < trig['y'][1] and high > trig['y'][0]:
                        inside, d, qx, qz = polyNear(pad['trigPoly'], self.px, self.pz)
                        on = inside or d < self.pbox
                    if not on and low < disc['y'][1] and high > disc['y'][0]:
                        on = math.hypot(self.px - disc['c'][0], self.pz - disc['c'][1]) < self.pbox + (disc['r'][0] + disc['r'][1]) * 0.5
                    if on:
                        touch.add(i)
                    pb = self.padBox[i]
                    if low < pb.y1 and high > pb.y0:
                        inside, d, qx, qz = polyNear(pb.poly, self.px, self.pz)
                        if inside or d < self.pbox:
                            plants.add(i)
        if touch - self.padTouch:
            self.bounce = True
        for i in plants - self.plantTouch:
            self.padTimers.append((self.time + 10.0, i, 'idle'))
            self.padTimers.sort()
            self.events.append(('padAnim', i, 'toonSpring'))
        self.padTouch = touch
        self.plantTouch = plants

    def __move(self, dx, dy, dz):
        """CharacterController.Move: slide along what is in the way, stand on what is below."""
        r = self.pr
        self.px += dx
        self.pz += dz
        self.py += dy
        self.grounded = False
        ground = 0.0
        step = self.data['player']['step']
        prisms = []
        if math.hypot(self.px, self.pz) + r > self.wallReach - 0.5:
            prisms += self.walls + self.counters
        for gx in (int((self.px - 1.0) // 4), int((self.px + 1.0) // 4)):
            for gz in (int((self.pz - 1.0) // 4), int((self.pz + 1.0) // 4)):
                for i in self.padGrid.get((gx, gz), ()):
                    if self.padBox[i] not in prisms:
                        prisms.append(self.padBox[i])
        for prism in prisms:
            hit = prism.circle(self.px, self.pz, r)
            if not hit or self.py >= prism.y1 + 1e-4 and dy > 0.0:
                continue
            if self.py + self.pheight <= prism.y0:
                continue
            if self.py >= prism.y1 - step - 1e-4:
                inside, d, qx, qz = polyNear(prism.poly, self.px, self.pz)
                if inside or d < r * 0.5:
                    ground = max(ground, prism.y1)          # on top of it
                    continue
                if self.py >= prism.y1:
                    continue
            self.px += hit[1] * hit[0]
            self.pz += hit[2] * hit[0]
        # the Cog base's middle
        s = self.sphereR + r
        cy = self.py + r
        m = math.sqrt(self.px * self.px + cy * cy + self.pz * self.pz)
        if m < s and m > 1e-6:
            nx, ny, nz = self.px / m, cy / m, self.pz / m
            self.px += nx * (s - m)
            self.pz += nz * (s - m)
            self.py += ny * (s - m)
            if ny > 0.7071:                                 # slope limit 45
                self.grounded = True
        # doodles stand in the way
        for d in self.doodles:
            if not d.alive or self.py >= d.y + D_CENTRE_Y + D_HEIGHT * 0.5 or self.py + self.pheight <= d.y:
                continue
            cx, cz = d.centre()
            ex, ez = self.px - cx, self.pz - cz
            if ex > 1.5 or ex < -1.5 or ez > 1.5 or ez < -1.5:
                continue
            m = math.hypot(ex, ez)
            if m < r + D_RADIUS and m > 1e-6:
                self.px += ex / m * (r + D_RADIUS - m)
                self.pz += ez / m * (r + D_RADIUS - m)
        if self.py <= ground:
            self.py = ground
            self.grounded = True

    # ---- once a frame: DoodleFlingerBot / DoodleFlingerOld
    def __flee(self, dt):
        px, py, pz = self.px, self.py, self.pz
        for d in self.doodles:
            if not d.alive:
                continue
            dx, dy, dz = px - d.x, py - d.y, pz - d.z
            m = math.sqrt(dx * dx + dy * dy + dz * dz)
            if m < d.scaredAt:
                d.scared = True
            elif m > d.aware:
                d.scared = False
            if not d.scared:
                d.anim = 'idle' if d.old else 'walkHappy'
                continue
            if m > 1e-6:
                # LookAt the toon, then half a turn about: away from the toon, and tipped up as far as the toon is above
                d.fx, d.fy, d.fz = -dx / m, dy / m, -dz / m
            k = 40.0 * d.runSpeed * dt
            d.Fx += d.fx * k
            d.Fy += d.fy * k
            d.Fz += d.fz * k
            d.anim = 'run'

    def __pads(self):
        """Fire's waits: the stagger before the first idle, and idle again ten seconds after a spring."""
        while self.padTimers and self.padTimers[0][0] <= self.time:
            when, i, clip = self.padTimers.pop(0)
            self.events.append(('padAnim', i, clip))

    # ---- once a frame: clockScript
    def __clock(self, dt):
        if not self.clockPaused:
            self.timeRemaining = GAME_SECONDS - self.time
            self.percent = self.timeRemaining / GAME_SECONDS * 100.0
            if self.timeRemaining < 0.0:
                self.timeRemaining = 0.0
                self.clockPaused = True
                self.villain = True
                self.events.append(('timeUp',))
                if self.score < self.winCount:
                    self.state = 'lost'
                    self.events.append(('lost',))
                else:
                    # One short of a win (the prototype's 23) when the clock ran out: the prototype neither won nor lost and played on for ever.
                    # Here play goes on while one more doodle can still be saved, for at most OVERTIME seconds.
                    self.overtime = self.time + OVERTIME
        elif self.overtime is not None and self.state == 'play':
            if self.time > self.overtime or not (self.rockets or self.doodles):
                self.state = 'lost'
                self.events.append(('lost',))

    # ---- last in a frame: CameraController
    def __camera(self, dt, mouse):
        target = (self.px, self.py + self.data['player']['target'][1], self.pz)
        self.camX += mouse[0] * 250.0 * 0.02
        self.camY = clamp(self.camY - mouse[1] * 120.0 * 0.02, -20.0, 80.0)
        if self.axisV.value != 0.0 or self.axisH.value != 0.0:
            q = qslerp(self.camQ, qeuler(self.camY, self.yaw), dt * 3.0)
            self.camX = self.yaw
        else:
            q = qslerp(self.camQ, qeuler(self.camY, self.camX), dt * 3.0)
        back = qrot(q, (0.0, 0.0, -self.camDistance))
        self.camQ = q
        self.camPos = (back[0] + target[0], back[1] + target[1], back[2] + target[2])

    def clockText(self):
        return '%d:%02d' % (int(self.timeRemaining / 60.0), int(self.timeRemaining % 60.0))
