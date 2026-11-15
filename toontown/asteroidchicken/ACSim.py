"""Asteroid Chicken, the game itself: Disney's scripts from the Toontown 2.0
prototype (GameController, Ship, ShipMoveForward, AsteroidField,
AsteroidBandGenerator, Asteroid, Asterpinata, StarPinata, YellowHardCandy,
Lolly, BlueWhistle, Jellybean, EggBeam, ChickenBeam, AstronautBehavior,
GUIHandler, the WorldEdge scripts and the Detonator's push) over a small
rigid body world that stands in for Unity's physics.

Everything here is in Unity's own units and axes (x right, y up, z forward)
and in pure Python; ACGame draws it. One call a frame:

    sim.update(dt, keys, mouse, fire)

keys: set of 'left' 'right' 'up' 'down' held; mouse: (x, y) in -1..1 across
the window (y up) or None; fire: True on the frame the fire key goes down.
What happened comes back as sim.events (a list the caller empties)."""
import bisect
import math
import operator
import random

FIXED = 0.02                   # Unity's fixed timestep
GAME_LENGTH = 120.0
START_DELAY = 5.0
SHIP_SPEED = 7.0               # ShipMoveForward.speed; it overshoots to 7.7 like the original (see __shipForward)
ROT_SPEED = 20.0               # Ship.daiserRotSpeed, degrees a second
CRACK_DELAY = 3.0
CRACKS = 2                     # the windshield cracks twice; the hit after that ends the game

# What the playground changes. Disney's prototype had one setting, and a hard one: three hits on the windshield, three seconds apart
# or more, ended the game. On the trolley the game is easier everywhere and gets harder playground by playground, as Toontown's own
# trolley games do: (cracks the windshield takes, seconds a fresh crack shields it, share of Disney's homing pinatas that do home),
# for difficulty 0 (Toontown Central) to 1 (Donald's Dreamland).
TUNING = ((0.0, 6, 9.0, 0.25), (0.2, 5, 8.0, 0.4), (0.4, 5, 7.0, 0.55), (0.6, 4, 6.0, 0.7), (0.8, 4, 5.0, 0.85), (1.0, 3, 4.0, 1.0))


def tuning(difficulty):
    """The settings of a playground: the row of TUNING nearest its difficulty."""
    row = min(TUNING, key=lambda row: abs(row[0] - difficulty))
    return dict(cracks=row[1], crackDelay=row[2], homing=row[3])
CHICKEN_MIN, CHICKEN_MAX = 5.0, 15.0
PINATA_RADIUS = 2.5507         # half the diagonal of the mine pinata's bounds: what the generators multiply sizes by
SHIP_BOX = (-7.5, 7.5, -9.0, 9.0, -11.0, 19.0)     # the Ship's BoxCollider (15, 18, 30) about (0, 0, 4)
WINDSHIELD = (1.39, -0.244, 19.81, 8.5)
LAUNCH = (1.2253, -2.4508, 18.97)                  # LaunchPos (and the aiming camera) on the ship
AIM_FOV = 60.0
LISTENER = (1.2289, -0.8, 7.5)                     # the main camera, where the sounds are heard
BOUNCE_THRESHOLD = 2.0
MAX_ANGULAR = 7.0

# kind: mass, drag, angular drag, collider (sphere radius | box size), centre, bouncy, hit points
KINDS = {
    'donkey': dict(m=2.0, drag=0.2, adrag=0.1, sphere=0.8, centre=(-0.1, 0.0, 0.0), hp=4, vel=(2.0, 5.0), beans=9, world=10.0, boom=1.0, sound='flak_hit', confetti=('blue', 'green')),
    'mine': dict(m=2.0, drag=0.2, adrag=0.1, sphere=1.1, centre=(0.0, 0.0, 0.0), hp=4, vel=(1.0, 10.0), beans=9, world=None, boom=1.5, sound='flak_hit', confetti=('pink', 'orange')),
    'star': dict(m=1.0, drag=0.3, adrag=0.4, box=(1.25, 1.2, 0.5), centre=(0.0, 0.1, 0.0), hp=4, vel=(1.0, 10.0), beans=8, world=10.0, boom=2.0, sound='anvil_miss', confetti=('starPurple', 'starYellow')),
    'hard': dict(m=0.3, drag=0.3, adrag=0.3, box=(0.2, 0.15, 0.14), centre=(0.0, 0.0, 0.0), hp=2, vel=(2.0, 1.0), bouncy=True, boom=1.7, sound='flak_hit'),
    'lolly': dict(m=0.4, drag=1.0, adrag=0.4, box=(0.22, 0.4, 0.1), centre=(0.0, -0.1, 0.0), hp=4, vel=(2.0, 1.0), boom=2.0, sound='flak_hit'),
    'whistle': dict(m=0.2, drag=0.6, adrag=0.5, box=(0.2, 0.1, 0.1), centre=(0.05, 0.0, 0.0), hp=3, vel=(2.0, 1.0), boom=7.0, sound='incoming', scale=5.0),
    'heart': dict(m=2.0, drag=0.5, adrag=0.3, sphere=1.0, centre=(0.0, 0.0, 0.0), hp=4),
    'wrapper': dict(m=0.1, drag=0.5, adrag=0.05, sphere=0.05, centre=(0.0, 0.0, 0.0), hp=0, ghost=True),
    'chicken': dict(m=2.0, drag=2.0, adrag=1.0, box=(0.25, 0.5, 0.25), centre=(0.0, 0.0, 0.0), hp=0, scale=6.5),
}
PINATAS = ('donkey', 'mine', 'star')
ZLO = operator.attrgetter('zlo')
CANDIES = ('hard', 'lolly', 'whistle')


# ---- quaternions (w, x, y, z), Unity's handedness
def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def qrot(q, v):
    w, x, y, z = q
    vx, vy, vz = v
    tx, ty, tz = 2.0 * (y * vz - z * vy), 2.0 * (z * vx - x * vz), 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def qinvrot(q, v):
    return qrot((q[0], -q[1], -q[2], -q[3]), v)


def qaxis(x, y, z, degrees):
    a = math.radians(degrees) * 0.5
    s = math.sin(a)
    return (math.cos(a), x * s, y * s, z * s)


def qnorm(q):
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]) or 1.0
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def qlook(dx, dy, dz):
    """Quaternion.LookRotation(d, up): z along d, x level."""
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    if n < 1e-9:
        return (1.0, 0.0, 0.0, 0.0)
    fx, fy, fz = dx / n, dy / n, dz / n
    rx, ry, rz = fz, 0.0, -fx            # up x forward
    rn = math.sqrt(rx * rx + rz * rz)
    if rn < 1e-6:
        rx, ry, rz = 1.0, 0.0, 0.0
    else:
        rx, rz = rx / rn, rz / rn
    ux, uy, uz = fy * rz - fz * ry, fz * rx - fx * rz, fx * ry - fy * rx
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = rx, ux, fx, ry, uy, fy, rz, uz, fz
    t = m00 + m11 + m22
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return qnorm((0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s))
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        return qnorm(((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s))
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        return qnorm(((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s))
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2
    return qnorm(((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s))


def qfromto(d):
    """Quaternion.FromToRotation(forward, d)."""
    dx, dy, dz = d
    w = 1.0 + dz
    if w < 1e-6:
        return (0.0, 0.0, 1.0, 0.0)
    return qnorm((w, -dy, dx, 0.0))


class Body(object):
    """One rigid body with the script that sat on it."""
    __slots__ = ('id', 'kind', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'wx', 'wy', 'wz', 'q', 'm', 'drag', 'adrag', 'scale', 'r', 'box', 'cx', 'cy', 'cz',
                 'bouncy', 'ghost', 'alive', 'hp', 'size', 'velScale', 'force', 'first', 'homing', 'torque', 'onShip', 'walls', 'born', 'stage',
                 'hitAt', 'gravity', 'node', 'name', 'inertia', 'px', 'py', 'pz', 'started', 'asleep', 'pinata', 'off', 'ccx', 'ccy', 'ccz', 'zlo')

    def __init__(self, sim, kind, pos, q=(1.0, 0.0, 0.0, 0.0)):
        k = KINDS[kind]
        self.id = sim.nextId
        sim.nextId += 1
        self.kind = kind
        self.x, self.y, self.z = pos
        self.px, self.py, self.pz = pos
        self.vx = self.vy = self.vz = 0.0
        self.wx = self.wy = self.wz = 0.0
        self.q = q
        self.m = k['m']
        self.drag = k['drag']
        self.adrag = k['adrag']
        self.bouncy = k.get('bouncy', False)
        self.ghost = k.get('ghost', False)
        self.alive = True
        self.hp = k['hp']
        self.size = 1.0
        self.velScale = 1.0
        self.force = (0.0, 0.0, 0.0)
        self.first = True
        self.started = False
        self.homing = False
        self.torque = None
        self.onShip = False
        self.walls = 0
        self.born = sim.time
        self.stage = 0
        self.hitAt = 0.0
        self.gravity = False
        self.node = None
        self.name = kind
        self.asleep = False
        self.pinata = kind in PINATAS
        self.setScale(k.get('scale', 1.0))

    def setScale(self, scale):
        k = KINDS[self.kind]
        self.scale = scale
        if 'sphere' in k:
            self.r = k['sphere'] * scale
            self.box = None
        else:
            b = k['box']
            self.box = (b[0] * scale * 0.5, b[1] * scale * 0.5, b[2] * scale * 0.5)
            # Body against body goes by a ball about the box (its middle half-width).
            self.r = sorted(self.box)[1]
        c = k['centre']
        self.cx, self.cy, self.cz = c[0] * scale, c[1] * scale, c[2] * scale
        self.off = bool(self.cx or self.cy or self.cz)
        self.inertia = max(0.4 * self.m * self.r * self.r, 1e-4)
        if self.off:
            o = qrot(self.q, (self.cx, self.cy, self.cz))
            self.ccx, self.ccy, self.ccz = self.x + o[0], self.y + o[1], self.z + o[2]
        else:
            self.ccx, self.ccy, self.ccz = self.x, self.y, self.z
        self.zlo = self.ccz - self.r

    def centre(self):
        if self.cx or self.cy or self.cz:
            o = qrot(self.q, (self.cx, self.cy, self.cz))
            return (self.x + o[0], self.y + o[1], self.z + o[2])
        return (self.x, self.y, self.z)


class Wall(object):
    """One of the WorldEdges boxes; it rides on the ShipPivot."""

    def __init__(self, name, centre, size, q, enter):
        self.name = name
        self.c = centre
        self.h = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
        self.q = q
        self.enter = enter
        self.bit = 0

    def contact(self, px, py, pz, r, shipZ):
        """(depth, nx, ny, nz) if a ball at p touches the box, else None."""
        lx, ly, lz = qinvrot(self.q, (px - self.c[0], py - self.c[1], pz - self.c[2] - shipZ))
        hx, hy, hz = self.h
        qx = min(max(lx, -hx), hx)
        qy = min(max(ly, -hy), hy)
        qz = min(max(lz, -hz), hz)
        dx, dy, dz = lx - qx, ly - qy, lz - qz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 > r * r:
            return None
        if d2 > 1e-12:
            d = math.sqrt(d2)
            n = (dx / d, dy / d, dz / d)
            depth = r - d
        else:
            # The centre is inside: out through the nearest face.
            gaps = ((hx - lx, (1.0, 0.0, 0.0)), (hx + lx, (-1.0, 0.0, 0.0)), (hy - ly, (0.0, 1.0, 0.0)), (hy + ly, (0.0, -1.0, 0.0)),
                    (hz - lz, (0.0, 0.0, 1.0)), (hz + lz, (0.0, 0.0, -1.0)))
            gap, n = min(gaps)
            depth = r + gap
        wn = qrot(self.q, n)
        return (depth, wn[0], wn[1], wn[2])


def makeWalls():
    # WorldEdges at (0, 0, -158.5) scaled (3, 3, 5); children's places and sizes scaled out here.
    def q(x, y, z, w):
        return (w, x, y, z)
    walls = [
        Wall('Down', (0.0, -358.753, 868.041), (1110.0, 84.0, 2090.0), q(0.14412, 0.0, 0.0, 0.98956), 'up'),
        Wall('Left', (-496.171, 156.0, 762.132), (84.0, 1200.0, 2000.0), q(0.0, 0.20791, 0.0, -0.97815), 'left'),
        Wall('Right', (514.204, 156.0, 750.981), (84.0, 1200.0, 2000.0), q(0.0, 0.20791, 0.0, 0.97815), 'right'),
        Wall('Back', (0.0, 0.0, -233.061), (1110.0, 1200.0, 140.0), q(0.0, 0.0, 0.0, 1.0), 'kill'),
        Wall('Up', (0.0, 413.07, 893.929), (1110.0, 84.0, 2090.0), q(0.12842, 0.0, 0.0, -0.99172), None),
    ]
    for i, wall in enumerate(walls):
        wall.bit = 1 << i
    return walls


class Sim(object):

    def __init__(self, seed=None, clipLengths=None, tune=None):
        self.rng = random.Random(seed)
        # (No tuning: the prototype's own game.)
        tune = tune or {}
        self.cracksMax = int(tune.get('cracks', CRACKS))
        self.crackDelay = float(tune.get('crackDelay', CRACK_DELAY))
        self.homingShare = float(tune.get('homing', 1.0))
        self.tuneRng = random.Random(self.rng.random() if tune else 0)
        self.events = []
        self.time = 0.0                 # Time.time
        self.acc = 0.0
        self.nextId = 1
        self.bodies = []
        self.beams = []
        self.walls = makeWalls()
        self.lastBlocker = [None]
        self.step = 0
        self.speedSteps = 0
        self.dead = False
        self.sleepZ = []
        self.sleepB = []
        self.sleepR = 0.0
        self.ftime = 0.0
        self.frameTime = 0.0
        self.clipLengths = clipLengths or {}
        # ShipPivot / ShipMoveForward
        self.shipZ = 0.0
        self.shipSpeed = 0.0
        # Ship
        self.aim = (1.0, 0.0, 0.0, 0.0)             # LaunchPos' rotation
        self.ray = (0.0, 0.0, 1.0)
        self.crosshair = (LAUNCH[0], LAUNCH[1], LAUNCH[2] + 20.0)
        self.lastFireTime = 0.0
        self.chickenDelay = 10.0
        self.lastTimeCracked = 0.0
        self.nHits = 0
        self.cracks = []
        self.shipGone = False
        # GameController
        self.gameOver = False
        self.won = None
        self.readyToPlay = False
        self.startDelayTime = 0.0
        self.startTime = 0.0
        self.timeLeft = GAME_LENGTH
        self.countdown = int(START_DELAY)
        self.gameScore = 0
        self.gameEnemies = -100
        self.gameLives = 3
        self.finished = False            # the point where Disney reloaded the scene
        self.later = []                  # coroutines: (time, call)
        # GUIHandler
        self.shownScore = 0
        self.tickAt = 0.0
        # AsteroidBandGenerator
        self.genStart = 0.0
        self.bandCount = 0
        # AstronautBehavior
        self.astro = dict(first=True, canAnimate=True, startIdle=0.0, waitFor=10.0, cheerOn=False, duckOn=False, lastCheer=0.0, lastDuck=0.0, over=False)
        self.emit('astro', 'idle')
        self.stats = dict(spawned=0, popped=0, shipHits=0, shots=0, chickens=0, candies=0, wallKills=0)
        self.__field()

    # ---- helpers
    def emit(self, *event):
        self.events.append(event)

    def rand(self, a, b):
        """Random.Range for floats."""
        return a + (b - a) * self.rng.random()

    def randint(self, a, b):
        """Random.Range for ints: b is left out."""
        return self.rng.randrange(a, b)

    def randomRotation(self):
        u1, u2, u3 = self.rng.random(), self.rng.random(), self.rng.random()
        a, b = math.sqrt(1.0 - u1), math.sqrt(u1)
        return (b * math.cos(2 * math.pi * u3), a * math.sin(2 * math.pi * u2), a * math.cos(2 * math.pi * u2), b * math.sin(2 * math.pi * u3))

    def sound(self, name, pos=None, volume=1.0):
        self.emit('sound', name, pos, volume)

    def after(self, seconds, call):
        self.later.append((self.time + seconds, call))

    # ---- Physics.CheckSphere
    def checkSphere(self, x, y, z, r):
        last = self.lastBlocker
        b = last[0]
        if b is not None and b.alive:
            c = b.centre()
            d = r + b.r
            if (c[0] - x) ** 2 + (c[1] - y) ** 2 + (c[2] - z) ** 2 <= d * d:
                return True
        for b in self.bodies:
            c = b.centre()
            d = r + b.r
            if (c[0] - x) ** 2 + (c[1] - y) ** 2 + (c[2] - z) ** 2 <= d * d:
                last[0] = b
                return True
        x0, x1, y0, y1, z0, z1 = SHIP_BOX
        qx, qy, qz = min(max(x, x0), x1), min(max(y, y0), y1), min(max(z - self.shipZ, z0), z1)
        if (x - qx) ** 2 + (y - qy) ** 2 + (z - self.shipZ - qz) ** 2 <= r * r:
            return True
        for wall in self.walls:
            if wall.contact(x, y, z, r, self.shipZ) is not None:
                return True
        # The Front box (a trigger; CheckSphere counts it all the same).
        if abs(z - self.shipZ - 1856.94) <= 70.0 + r and abs(x) <= 555.0 + r and abs(y - 31.33) <= 600.0 + r:
            return True
        return False

    # ---- AsteroidField.GenerateLevel (once, at the origin): worldSize 100, sizes 3..20, x/yDim 2, zDim 600, 1 x 1 x 3 divisions, offset (0, 40, 15), at most 300
    def __field(self):
        half = 50.0
        num = 0
        for zc in range(3):
            div = 1 + zc * 75.0
            dimInc = div * 2.0
            yc = 0
            while yc < div:
                xc = 0
                while xc < div:
                    size = float(self.randint(3, 20))
                    if zc == 0:
                        size = 3.0
                    x = -dimInc / 2 + xc * 2.0 + self.rand(-0.125 * half, 0.125 * half)
                    y = -dimInc / 2 + 40.0 + yc * 2.0 + self.rand(-0.125 * half, 0.125 * half)
                    z = 15.0 + zc * 200.0 + self.rand(-half, half)
                    radius = PINATA_RADIUS * size
                    if not self.checkSphere(x, y, z, radius * (1.0 if zc == 0 else 6.0)):
                        self.__pinata(self.randint(0, 3), (x, y, z), radius, 1.0)
                        num += 1
                        if num > 300:
                            return
                    xc += 1
                yc += 1

    # ---- AsteroidBandGenerator.GenerateLevel: 5 x 5 over 500 x 200, no jitter, sizes 2..20
    def __band(self):
        gz = self.shipZ + 1700.0
        num = 0
        for j in range(5):
            for i in range(5):
                size = float(self.randint(2, 20))
                x = -250.0 + i * 100.0 + self.rand(0.0, 0.0)
                y = -100.0 + j * 40.0 + self.rand(0.0, 0.0)
                z = gz + self.rand(0.0, 0.0)
                radius = PINATA_RADIUS * size
                if not self.checkSphere(x, y, z, radius * 2.0):
                    which = self.randint(0, 3)
                    b = self.__pinata(which, (x, y, z), radius, (2.0, 4.0, 3.0)[which])
                    push = (-50.0 if x > 0 else 50.0, 0.0, -500.0)
                    b.vx += push[0] / b.m
                    b.vy += push[1] / b.m
                    b.vz += push[2] / b.m
                    num += 1
                    if num > 100:
                        return

    def __pinata(self, which, pos, size, velScale):
        """Instantiate + Setup(size, velocityScale) of Asteroid / Asterpinata / StarPinata."""
        kind = PINATAS[which]
        k = KINDS[kind]
        b = Body(self, kind, pos, self.randomRotation())
        b.size = size
        b.velScale = velScale
        b.setScale(size)
        if kind == 'donkey':
            dx, dy = self.rand(-0.5, 0.5), self.rand(-0.5, 0.5)
        else:
            dx = self.rand(-0.25, 0.0) if pos[0] >= 0 else self.rand(0.0, 0.25)
            dy = self.rand(-0.25, 0.0) if pos[1] >= 0 else self.rand(0.0, 0.25)
        dz = self.rand(-1.0, 0.0)
        speed = self.rand(k['vel'][0], k['vel'][1]) * velScale
        tx = self.rand(0.0, 1.0) if kind == 'star' else self.rand(0.0, 20.0)
        ty, tz = self.rand(0.0, 20.0), self.rand(0.0, 20.0)
        num2 = self.randint(0, 20)
        num3 = self.randint(-2, 2)
        if num2 < 2:
            ts = int(self.rand(0.0, 2.0))
        elif num2 < 8:
            ts = int(self.rand(0.0, 1.0))
        else:
            ts = int(self.rand(0.0, 0.5))
        ts = int(num3 * ts * velScale * 8)
        if ts:
            b.torque = (ts * tx, ts * ty, ts * tz)
            self.__addTorque(b)
        b.force = (dx * speed, dy * speed, dz * speed)
        self.bodies.append(b)
        self.stats['spawned'] += 1
        self.emit('spawn', b)
        return b

    def __addTorque(self, b):
        t = b.torque
        k = FIXED / b.inertia
        b.wx += t[0] * k
        b.wy += t[1] * k
        b.wz += t[2] * k

    # ---- candies (Setup of YellowHardCandy / Lolly / BlueWhistle)
    def __candy(self, kind, pos, q, size=None, velScale=1.0):
        b = Body(self, kind, pos, q)
        k = KINDS[kind]
        if size is not None:
            if kind == 'hard':
                scale = min(size * self.rand(2.0, 4.0), 15.0)
                d = (self.rand(-0.5, 0.5), self.rand(-0.5, 0.5), self.rand(-1.0, 0.0))
                speed = (k['vel'][0] + (k['vel'][1] - k['vel'][0]) * self.rng.random()) * velScale
            elif kind == 'lolly':
                scale = size * self.rand(1.0, 2.0)
                d = (self.rand(-1.0, 1.0), self.rand(-1.0, 1.0), self.rand(-1.0, 1.0))
                speed = 0.0                      # Lolly.FixedUpdate is empty: it never moves
                self.rng.random()
            else:
                scale = 5.0 * size * 0.25 * self.rand(1.0, 1.0)
                d = (self.rand(-0.5, 0.5), self.rand(-0.5, 0.5), self.rand(-1.0, 0.0))
                speed = (k['vel'][0] + (k['vel'][1] - k['vel'][0]) * self.rng.random()) * velScale
            b.setScale(scale)
            b.force = (d[0] * speed, d[1] * speed, d[2] * speed)
        self.bodies.append(b)
        self.stats['candies'] += 1
        self.emit('spawn', b)
        return b

    def __spew(self, b):
        k = KINDS[b.kind]
        half = (k['world'] if k['world'] is not None else b.scale) * 0.5
        for i in range(k['beans']):
            p = (b.x + self.rand(-half, half), b.y + self.rand(-half, half), b.z + self.rand(-half, half))
            which = self.randint(0, 4)
            if which == 0:
                if b.kind == 'star':
                    c = Body(self, 'heart', p, b.q)       # the heart candy: no Setup, nothing can shoot it
                    self.bodies.append(c)
                    self.emit('spawn', c)
                elif b.kind == 'mine':
                    self.__candy('hard', p, b.q, b.size, b.velScale)
                else:
                    self.__candy('hard', p, b.q)          # Asteroid makes it without Setup: prefab size, no push
            elif which == 1:
                self.__candy('hard', p, b.q, b.size, b.velScale)
            elif which == 2:
                self.__candy('lolly', p, b.q, b.size, b.velScale)
            else:
                self.__candy('whistle', p, b.q, b.size, b.velScale)

    # ---- Hit() / Explode()
    def __remove(self, b, how):
        if b.alive:
            if b.asleep:
                self.wake(b)
            b.alive = False
            self.dead = True
            self.emit('gone', b, how)

    def __explode(self, b):
        k = KINDS[b.kind]
        if b.kind in PINATAS:
            self.emit('confetti', (b.x, b.y, b.z), b.q, k['confetti'])
        self.__detonate((b.x, b.y, b.z), k['boom'], 'big')
        self.sound(k['sound'], (b.x, b.y, b.z))
        if b.kind in PINATAS:
            self.__spew(b)
            if b.kind == 'mine':
                self.__cheer()
            self.stats['popped'] += 1
        self.gameEnemies -= 1
        self.gameScore += 10
        self.__remove(b, 'popped')

    def hit(self, b):
        """The thing's Hit(): True when the beam is used up."""
        kind = b.kind
        if kind in PINATAS:
            b.hp -= 1
            if b.hp <= 0:
                self.__explode(b)
            return True
        if kind == 'hard':
            b.hp -= 1
            if b.hp == 1:
                w = Body(self, 'wrapper', (b.x, b.y, b.z))
                w.setScale(b.scale)
                self.bodies.append(w)
                self.emit('spawn', w)
                self.emit('sparkle', (b.x, b.y, b.z))
                b.stage = 1
                self.emit('stage', b)
                b.hitAt = self.time
                return False
            if b.hp <= 0 and self.time - b.hitAt > 1.0:
                self.__explode(b)
                return True
            return False
        if kind == 'lolly':
            b.hp -= 1
            if b.hp in (3, 2):
                b.stage = 4 - b.hp
                self.emit('stage', b)
                self.sound('slice', (b.x, b.y, b.z))
                return False
            if b.hp <= 1:
                self.__explode(b)
                return True
            return False
        if kind == 'whistle':
            b.hp -= 1
            if b.hp == 2:
                self.sound('whistle', (b.x, b.y, b.z))
                return False
            if b.hp <= 1:
                self.__explode(b)
                return True
            return False
        return False

    def __detonate(self, pos, size, style):
        """The Detonator: what is seen, and DetonatorForce (radius 50, power 4000, scaled by size/30)."""
        self.emit('explosion', pos, size, style)
        self.after(0.0, lambda: self.__blast(pos, size))

    def __blast(self, pos, size):
        s = size / 30.0
        radius = 50.0 * s
        power = 4000.0 * s
        oy = pos[1] - 3.0 * s
        for b in self.bodies:
            if not b.alive or b.ghost:
                continue
            dx, dy, dz = b.x - pos[0], b.y - pos[1], b.z - pos[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) - b.r
            if d >= radius:
                continue
            d = max(d, 0.0)
            ux, uy, uz = b.x - pos[0], b.y - oy, b.z - pos[2]
            n = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
            dv = power * (1.0 - d / radius) / b.m * FIXED
            if b.asleep:
                self.wake(b)
            b.vx += ux / n * dv
            b.vy += uy / n * dv
            b.vz += uz / n * dv

    # ---- AstronautBehavior
    def __cheer(self):
        a = self.astro
        if self.time - a['lastCheer'] > 8.0:
            a['lastCheer'] = self.time
            a['cheerOn'] = True

    def __duck(self):
        a = self.astro
        if self.time - a['lastDuck'] > 4.0:
            a['duckOn'] = True

    def __astronaut(self):
        a = self.astro
        if a['over']:
            return
        if a['first']:
            a['first'] = False
            a['canAnimate'] = True
            return
        if a['canAnimate']:
            if a['cheerOn']:
                clip = 'cheerR'
                a['cheerOn'] = False
            elif a['duckOn']:
                clip = 'duck'
                a['lastDuck'] = self.time
                a['duckOn'] = False
            else:
                clip = ('pullLever', 'idle', 'tapConsole', 'twistKnobsHi', 'lookR', 'lookL')[self.randint(1, 7) - 1]
            self.emit('astro', clip)
            a['waitFor'] = self.clipLengths.get(clip, 1.0)
            a['startIdle'] = self.time
        a['canAnimate'] = self.time - a['startIdle'] >= a['waitFor']

    # ---- Ship
    def __shipUpdate(self, dt, keys, mouse, fire):
        if self.shipGone:
            return
        step = ROT_SPEED * dt
        if 'left' in keys:
            self.aim = qnorm(qmul(self.aim, qaxis(0.0, 1.0, 0.0, -step)))
        elif 'right' in keys:
            self.aim = qnorm(qmul(self.aim, qaxis(0.0, 1.0, 0.0, step)))
        elif 'up' in keys:
            self.aim = qnorm(qmul(self.aim, qaxis(1.0, 0.0, 0.0, -step)))
        elif 'down' in keys:
            self.aim = qnorm(qmul(self.aim, qaxis(1.0, 0.0, 0.0, step)))
        if mouse is not None:
            self.mouse = mouse
        mx, my = getattr(self, 'mouse', (0.0, 0.0))
        t = math.tan(math.radians(AIM_FOV) * 0.5)
        d = (mx * t * getattr(self, 'aspect', 4.0 / 3.0), my * t, 1.0)
        n = math.sqrt(d[0] * d[0] + d[1] * d[1] + 1.0)
        self.ray = qrot(self.aim, (d[0] / n, d[1] / n, d[2] / n))
        self.crosshair = (LAUNCH[0] + self.ray[0] * 20.0, LAUNCH[1] + self.ray[1] * 20.0, LAUNCH[2] + self.ray[2] * 20.0)
        if fire:
            self.__fire()

    def __fire(self):
        q = qfromto(self.ray)
        pos = (LAUNCH[0], LAUNCH[1], LAUNCH[2] + self.shipZ)
        ship = (0.0, 0.0, self.shipZ)
        if self.time - self.lastFireTime > self.chickenDelay:
            self.sound('squawk', ship)
            b = Body(self, 'chicken', pos, q)
            f = qrot(q, (0.0, 0.0, 1.0))
            u = qrot(q, (0.0, 1.0, 0.0))
            # ChickenBeam.Go: one step of 30 units/s/s upward, then 100 units a second forward.
            b.vx, b.vy, b.vz = f[0] * 100.0 + u[0] * 30.0 * FIXED, f[1] * 100.0 + u[1] * 30.0 * FIXED, f[2] * 100.0 + u[2] * 30.0 * FIXED
            b.first = False
            self.bodies.append(b)
            self.emit('spawn', b)
            self.lastFireTime = self.time
            self.chickenDelay = self.rand(CHICKEN_MIN, CHICKEN_MAX)
            self.stats['chickens'] += 1
        else:
            self.sound('pop', ship)
            f = qrot(q, (0.0, 0.0, 1.0))
            beam = dict(x=pos[0], y=pos[1], z=pos[2], f=f, speed=300.0, born=self.time, q=q, alive=True, node=None, id=self.nextId, seen=set())
            self.nextId += 1
            self.beams.append(beam)
            self.emit('beam', beam)
            self.stats['shots'] += 1

    def __shipHit(self, b, contact):
        """Ship.OnCollisionEnter with one of the three pinatas."""
        if self.gameOver or not self.readyToPlay:
            return
        wx, wy, wz, wr = WINDSHIELD
        c = b.centre()
        d = wr + b.r
        flag = (c[0] - wx) ** 2 + (c[1] - wy) ** 2 + (c[2] - wz - self.shipZ) ** 2 <= d * d
        if self.time - self.lastTimeCracked >= self.crackDelay and flag:
            self.lastTimeCracked = self.time
        else:
            flag = False
        self.__duck()
        pos = (b.x, b.y, b.z)
        self.__detonate(pos, 22.0, 'big')
        self.sound('near_explosion', pos)
        self.stats['shipHits'] += 1
        self.emit('shipHit', pos)
        self.__remove(b, 'ship')
        if flag:
            if self.nHits <= 1:
                self.sound('anvil_miss', pos)
            x = min(max(contact[0], -1.3), 1.3)
            y = min(max(contact[1], -2.0), 1.8)
            if self.nHits < self.cracksMax:
                self.nHits += 1
                self.cracks.append((x, y))
                self.emit('crack', self.nHits, x, y)
            else:
                self.gameOver = True
                self.__timedGameRestart()
                self.gameLives -= 1
                self.gameEnemies -= 1

    # ---- GameController
    def __timedGameRestart(self):
        """The losing end."""
        self.astro['over'] = True
        self.emit('astro', 'gameOver')
        self.sound('lose', None)
        self.gameOver = True
        self.won = False
        self.timeLeft = 0.0
        self.readyToPlay = False
        self.emit('over', False)
        self.after(4.5, self.__explodeShip)

    def __explodeShip(self):
        pos = (1.17, -2.49, 12.54 + self.shipZ)
        self.__detonate(pos, 22.0, 'big')
        self.sound('near_explosion', pos)
        self.shipGone = True
        self.emit('shipGone')
        # Disney waited 10 + 3 seconds on a black, empty cockpit before reloading; the trolley game ends sooner.
        self.after(4.0, self.__finish)

    def __gameOverWin(self):
        """The time ran out."""
        self.gameOver = True
        self.won = True
        self.emit('musicOff')
        self.sound('win', None)
        self.astro['over'] = True
        self.emit('astro', 'victoryDance')
        self.emit('over', True)
        self.after(16.5, self.__finish)

    def __finish(self):
        self.finished = True
        self.emit('finished', self.won)

    def __controller(self):
        if not self.readyToPlay and not self.gameOver:
            self.countdown = int(START_DELAY - (self.time - self.startDelayTime))
            if self.countdown <= 0:
                self.readyToPlay = True
                self.startTime = self.time
                self.emit('ready')

    def __gui(self):
        if self.shownScore != self.gameScore and self.time - self.tickAt >= 0.05:
            self.tickAt = self.time
            self.shownScore += 1 if self.gameScore > self.shownScore else -1
            self.sound('tick', None, 0.1)

    def timeText(self):
        """float.ToString() of timeLeft, as the original's HUD showed it."""
        s = '%.7g' % self.timeLeft
        return s

    # ---- one physics step
    def __place(self, b):
        """Where the body's collider is now (kept on the body: every test reads it)."""
        if b.off:
            o = qrot(b.q, (b.cx, b.cy, b.cz))
            b.ccx, b.ccy, b.ccz = b.x + o[0], b.y + o[1], b.z + o[2]
        else:
            b.ccx, b.ccy, b.ccz = b.x, b.y, b.z
        b.zlo = b.ccz - b.r

    def __sleep(self, b):
        """A candy that has come to rest (Unity puts bodies under 0.15 units a second to sleep)."""
        b.asleep = True
        b.vx = b.vy = b.vz = 0.0
        b.wx = b.wy = b.wz = 0.0
        self.__place(b)
        i = bisect.bisect_left(self.sleepZ, b.zlo)
        self.sleepZ.insert(i, b.zlo)
        self.sleepB.insert(i, b)
        if b.r > self.sleepR:
            self.sleepR = b.r

    def wake(self, b):
        if not b.asleep:
            return
        b.asleep = False
        i = bisect.bisect_left(self.sleepZ, b.zlo)
        while i < len(self.sleepB) and self.sleepB[i] is not b:
            i += 1
        if i < len(self.sleepB):
            del self.sleepB[i]
            del self.sleepZ[i]

    def __fixed(self):
        dt = FIXED
        t = self.time
        self.step += 1
        # ShipMoveForward.FixedUpdate. In the original's single precision ten steps of 0.7 stop just short of 7, so an eleventh is taken: 7.7.
        if not self.shipGone:
            if self.speedSteps < 11:
                self.speedSteps += 1
                self.shipSpeed = 0.7 * self.speedSteps
            self.shipZ += self.shipSpeed * dt
        shipZ = self.shipZ
        # GameController.FixedUpdate
        if not self.gameOver:
            if self.readyToPlay:
                self.timeLeft = GAME_LENGTH - (t - self.startTime)
                if self.timeLeft <= 0:
                    self.timeLeft = 0.0
                    self.__gameOverWin()
            else:
                self.timeLeft = GAME_LENGTH
        # AsteroidBandGenerator.FixedUpdate
        if t - self.genStart > 10.0:
            self.__band()
            self.genStart = t
            self.bandCount += 1
        bodies = self.bodies
        moving = []
        for b in bodies:
            if not b.alive or b.asleep:
                continue
            kind = b.kind
            m = b.m
            pinata = b.pinata
            if pinata:
                f = b.force
                if b.first:
                    b.first = False
                    b.homing = self.randint(0, 7 if kind == 'star' else 5) == 0      # Start(): randInt
                    if b.homing and self.homingShare < 1.0:
                        b.homing = self.tuneRng.random() < self.homingShare
                    b.vx += f[0] / m
                    b.vy += f[1] / m
                    b.vz += f[2] / m
                elif b.homing and b.z - shipZ > 0:
                    dx, dy, dz = -b.x, -b.y, shipZ - b.z
                    n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                    b.q = qlook(dx, dy, dz)
                    k = 5.0 / m * dt / n
                    b.vx += dx * k
                    b.vy += dy * k
                    b.vz += dz * k
                else:
                    k = dt / m
                    b.vx += f[0] * k
                    b.vy += f[1] * k
                    b.vz += f[2] * k
            elif kind == 'chicken':
                if t - b.born > 2.0:
                    if not b.gravity:
                        b.gravity = True
                        self.emit('chickenFall', b)
                    u = qrot(b.q, (0.0, 1.0, 0.0))
                    b.vx -= 3.0 * u[0] / m
                    b.vy -= 3.0 * u[1] / m + 9.81 * dt
                    b.vz -= 3.0 * u[2] / m
            elif b.first:
                b.first = False
                f = b.force
                b.vx += f[0] / m
                b.vy += f[1] / m
                b.vz += f[2] / m
            k = 1.0 - b.drag * dt
            vx, vy, vz = b.vx * k, b.vy * k, b.vz * k
            b.vx, b.vy, b.vz = vx, vy, vz
            b.x += vx * dt
            b.y += vy * dt
            b.z += vz * dt
            wx, wy, wz = b.wx, b.wy, b.wz
            if wx or wy or wz:
                k = 1.0 - b.adrag * dt
                wx, wy, wz = wx * k, wy * k, wz * k
                w2 = wx * wx + wy * wy + wz * wz
                if w2 > MAX_ANGULAR * MAX_ANGULAR:
                    k = MAX_ANGULAR / math.sqrt(w2)
                    wx, wy, wz = wx * k, wy * k, wz * k
                b.wx, b.wy, b.wz = wx, wy, wz
                if w2 > 1e-8 and not (b.homing and b.z - shipZ > 0):
                    h = 0.5 * dt
                    b.q = qnorm(qmul((1.0, wx * h, wy * h, wz * h), b.q))
                else:
                    b.wx = b.wy = b.wz = 0.0
            if not pinata and kind != 'chicken' and vx * vx + vy * vy + vz * vz < 0.0225 and t - b.born > 0.1:
                self.__sleep(b)
                continue
            self.__place(b)
            if b.z < shipZ - 700.0 or b.z > shipZ + 6000.0 or abs(b.x) > 4000.0 or abs(b.y) > 4000.0:
                # Nothing in the original tidies up what drifts away; this far behind or out it can never be seen again.
                self.__remove(b, 'lost')
                continue
            if not b.ghost:
                moving.append(b)
        self.__collide(moving)
        self.__beams(moving)
        if self.dead:
            self.dead = False
            self.bodies = [b for b in self.bodies if b.alive]

    def __bounce(self, b, nx, ny, nz, depth, wallVz, elastic):
        """Push b out along n and take its speed into the surface away."""
        if b.asleep:
            self.wake(b)
        b.x += nx * depth
        b.y += ny * depth
        b.z += nz * depth
        b.ccx += nx * depth
        b.ccy += ny * depth
        b.ccz += nz * depth
        vn = b.vx * nx + b.vy * ny + (b.vz - wallVz) * nz
        if vn < 0:
            e = 1.0 if elastic and -vn > BOUNCE_THRESHOLD else 0.0
            k = -(1.0 + e) * vn
            b.vx += nx * k
            b.vy += ny * k
            b.vz += nz * k

    def __edges(self, b, shipZ):
        """b against the ship and the world's edges."""
        cx, cy, cz, r = b.ccx, b.ccy, b.ccz, b.r
        dz = cz - shipZ
        if not self.shipGone and -11.0 - r < dz < 19.0 + r and abs(cx) < 7.5 + r and abs(cy) < 9.0 + r:
            x0, x1, y0, y1, z0, z1 = SHIP_BOX
            qx, qy, qz = min(max(cx, x0), x1), min(max(cy, y0), y1), min(max(dz, z0), z1)
            ex, ey, ez = cx - qx, cy - qy, dz - qz
            d2 = ex * ex + ey * ey + ez * ez
            if d2 <= r * r:
                first = not b.onShip
                b.onShip = True
                if d2 > 1e-12:
                    d = math.sqrt(d2)
                    self.__bounce(b, ex / d, ey / d, ez / d, r - d, self.shipSpeed, b.bouncy)
                else:
                    self.__bounce(b, 0.0, 0.0, 1.0, r, self.shipSpeed, b.bouncy)
                if first and b.pinata:
                    self.__shipHit(b, (qx, qy))
                    if not b.alive:
                        return
            else:
                b.onShip = False
        else:
            b.onShip = False
        # The edges are only looked at when the ball is out near them.
        if dz < -140.0 + r or cx - r < -135.0 - 0.4452 * dz or cx + r > 150.0 + 0.4452 * dz or cy - r < -60.0 - 0.2975 * dz or cy + r > 135.0 + 0.2635 * dz or b.walls:
            touching = 0
            for wall in self.walls:
                hit = wall.contact(b.ccx, b.ccy, b.ccz, r, shipZ)
                if hit is None:
                    continue
                touching |= wall.bit
                self.__bounce(b, hit[1], hit[2], hit[3], hit[0], self.shipSpeed, True)
                if not b.walls & wall.bit:
                    act = wall.enter
                    if act in ('up', 'kill') and b.kind in ('donkey', 'mine'):
                        self.stats['wallKills'] += 1
                        self.__remove(b, 'edge')
                        return
                    if act == 'up':
                        b.vy += 50.0 / b.m
                        b.vz += 37.5 / b.m
                    elif act == 'kill':
                        b.vz += 150.0 / b.m
                    elif act == 'left':
                        b.vx += 100.0 / b.m
                    elif act == 'right':
                        b.vx -= 100.0 / b.m
            b.walls = touching

    def __pair(self, a, b):
        d = a.r + b.r
        ex, ey, ez = b.ccx - a.ccx, b.ccy - a.ccy, b.ccz - a.ccz
        if ex > d or ex < -d or ey > d or ey < -d:
            return
        d2 = ex * ex + ey * ey + ez * ez
        if d2 > d * d:
            return
        if a.asleep:
            self.wake(a)
        if b.asleep:
            self.wake(b)
        dist = math.sqrt(d2)
        if dist > 1e-9:
            nx, ny, nz = ex / dist, ey / dist, ez / dist
        else:
            nx, ny, nz = 0.0, 1.0, 0.0
        ia, ib = 1.0 / a.m, 1.0 / b.m
        k = (d - dist) / (ia + ib) * 0.8
        ka, kb = k * ia, k * ib
        a.x -= nx * ka
        a.y -= ny * ka
        a.z -= nz * ka
        a.ccx -= nx * ka
        a.ccy -= ny * ka
        a.ccz -= nz * ka
        b.x += nx * kb
        b.y += ny * kb
        b.z += nz * kb
        b.ccx += nx * kb
        b.ccy += ny * kb
        b.ccz += nz * kb
        vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny + (b.vz - a.vz) * nz
        if vn < 0:
            e = 1.0 if (a.bouncy or b.bouncy) and -vn > BOUNCE_THRESHOLD else 0.0
            p = -(1.0 + e) * vn / (ia + ib)
            # A glancing knock sets things turning a little.
            tx, ty, tz = (b.vx - a.vx) - vn * nx, (b.vy - a.vy) - vn * ny, (b.vz - a.vz) - vn * nz
            s = 0.003 * p * a.r / a.inertia
            a.wx += (ny * tz - nz * ty) * s
            a.wy += (nz * tx - nx * tz) * s
            a.wz += (nx * ty - ny * tx) * s
            a.vx -= nx * p * ia
            a.vy -= ny * p * ia
            a.vz -= nz * p * ia
            b.vx += nx * p * ib
            b.vy += ny * p * ib
            b.vz += nz * p * ib

    def __collide(self, moving):
        shipZ = self.shipZ
        for b in moving:
            self.__edges(b, shipZ)
        # What lies asleep is looked at a few at a time: the ship and the edges come to it slowly.
        sleepers = self.sleepB
        n = len(sleepers)
        if n:
            k = self.step % 8
            for b in sleepers[k::8]:
                dz = b.ccz - shipZ
                r = b.r
                if dz < -140.0 + r or (dz < 19.0 + r and dz > -11.0 - r and abs(b.ccx) < 7.5 + r and abs(b.ccy) < 9.0 + r) \
                        or b.ccx - r < -135.0 - 0.4452 * dz or b.ccx + r > 150.0 + 0.4452 * dz or b.ccy - r < -60.0 - 0.2975 * dz or b.ccy + r > 135.0 + 0.2635 * dz:
                    self.__edges(b, shipZ)
        # Body against body: the ones on the move among themselves, then against the sleepers near them.
        moving = [b for b in moving if b.alive]
        moving.sort(key=ZLO)
        n = len(moving)
        pair = self.__pair
        for i in range(n):
            a = moving[i]
            top = a.ccz + a.r
            for j in range(i + 1, n):
                b = moving[j]
                if b.zlo > top:
                    break
                pair(a, b)
        if self.sleepB:
            sz = self.sleepZ
            reach = 2.0 * self.sleepR
            for a in moving:
                i = bisect.bisect_left(sz, a.zlo - reach)
                j = bisect.bisect_right(sz, a.ccz + a.r)
                if i < j:
                    for b in self.sleepB[i:j]:
                        pair(a, b)

    # ---- EggBeam: FixedUpdate + OnTriggerEnter (swept, so a fast egg cannot skip over a thin candy)
    def __beamTest(self, beam, b, ax, ay, az, f, step):
        """How far along this step the egg meets b, or None."""
        HALF = 0.95
        ox, oy, oz = b.ccx - ax, b.ccy - ay, b.ccz - az
        along = ox * f[0] + oy * f[1] + oz * f[2]
        box = b.box
        reach = (b.r * 2.0 if box else b.r) + HALF
        if along < -reach or along > step + reach:
            return None
        if box is None:
            off2 = ox * ox + oy * oy + oz * oz - along * along
            if off2 > reach * reach:
                return None
            u = along - math.sqrt(reach * reach - off2)
            if u > step:
                return None
            return max(u, 0.0)
        # The segment in the box's own space, against the box grown by the egg's half size.
        lo = qinvrot(b.q, (-ox, -oy, -oz))
        ld = qinvrot(b.q, f)
        t0, t1 = 0.0, step
        for k in range(3):
            h = box[k] + HALF
            if abs(ld[k]) < 1e-9:
                if abs(lo[k]) > h:
                    return None
                continue
            u0, u1 = (-h - lo[k]) / ld[k], (h - lo[k]) / ld[k]
            if u0 > u1:
                u0, u1 = u1, u0
            if u0 > t0:
                t0 = u0
            if u1 < t1:
                t1 = u1
            if t0 > t1:
                return None
        return t0

    def __beams(self, moving):
        t = self.time
        dt = FIXED
        gone = False
        for beam in self.beams:
            if t - beam['born'] >= 5.0:
                beam['alive'] = False
                gone = True
                self.emit('beamGone', beam, False)
                continue
            beam['speed'] += 300.0 * dt
            f = beam['f']
            step = beam['speed'] * dt
            ax, ay, az = beam['x'], beam['y'], beam['z']
            seen = beam['seen']
            best = None
            zmax = max(az, az + f[2] * step) + 2.0
            for b in moving:
                if b.zlo > zmax or not b.alive or b.id in seen or b.kind in ('heart', 'chicken'):
                    continue
                u = self.__beamTest(beam, b, ax, ay, az, f, step)
                if u is not None and (best is None or u < best[0]):
                    best = (u, b)
            if self.sleepB:
                reach = 2.0 * self.sleepR + 2.0
                i = bisect.bisect_left(self.sleepZ, min(az, az + f[2] * step) - 2.0 * reach)
                j = bisect.bisect_right(self.sleepZ, zmax)
                if i < j:
                    for b in self.sleepB[i:j]:
                        if b.id in seen or b.kind == 'heart':
                            continue
                        u = self.__beamTest(beam, b, ax, ay, az, f, step)
                        if u is not None and (best is None or u < best[0]):
                            best = (u, b)
            if best is not None:
                u, b = best
                kind = b.kind
                if self.hit(b):
                    pos = (ax + f[0] * u, ay + f[1] * u, az + f[2] * u)
                    beam['x'], beam['y'], beam['z'] = pos
                    self.__detonate(pos, 0.1 if kind == 'hard' else 1.0, 'tiny')
                    self.sound('far_explosion', pos)
                    beam['alive'] = False
                    gone = True
                    self.emit('beamGone', beam, True)
                    continue
                # A candy that only got bitten lets the egg fly on (OnTriggerEnter comes once for each thing).
                seen.add(b.id)
            beam['x'], beam['y'], beam['z'] = ax + f[0] * step, ay + f[1] * step, az + f[2] * step
        if gone:
            self.beams = [beam for beam in self.beams if beam['alive']]

    # ---- one frame
    def update(self, dt, keys=(), mouse=None, fire=False):
        dt = min(dt, 0.1)
        self.frameTime += dt
        while self.ftime + FIXED <= self.frameTime:
            self.ftime += FIXED
            self.time = self.ftime
            self.__fixed()
        self.time = self.frameTime
        # Update()
        self.__controller()
        self.__shipUpdate(dt, keys, mouse, fire and not self.shipGone)
        for b in self.bodies:
            if b.torque is not None and b.alive:
                self.__addTorque(b)
        self.__astronaut()
        self.__gui()
        if self.later:
            due = [item for item in self.later if item[0] <= self.time]
            if due:
                self.later = [item for item in self.later if item[0] > self.time]
                for when, call in due:
                    call()
