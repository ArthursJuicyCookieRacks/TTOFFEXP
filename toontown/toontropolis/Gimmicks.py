"""The smaller things Disney's Toontropolis scripts do, ported line for line.

  Pinwheels   PWR_PinwheelControl: the eight pinwheels on the power building
  Bulbs       PWR_LightBulbBehavior, PWR_LightBulbSimpleBehavior and
              PET_LightBulbBehavior: the four light bulbs that come on when
              the town goes to sleep
  Bubbles     BubbleGen and BubbleBehaviour: the Gag Shop snores bubbles out
              of its chimney

Disney's scripts count in frames in a few places (a pinwheel speeds up by
so many degrees a second every frame, a bubble grows a step every frame);
the prototype ran at 60 frames a second, so those run in steps of 1/60 s
here however fast the game draws. None of these classes touches the scene:
TownLife reads their numbers and moves the nodes.
"""

import math

FRAME = 1.0 / 60.0
# Unity's physics step.
FIXED = 0.02

# rotationSpeed, easeInTime, easeOutTime of the eight pinwheels.
PINWHEELS = ((2.0, 1.0, 1.0), (1.0, 0.5, 0.5), (1.5, 2.0, 1.0), (0.5, 0.5, 0.5),
             (3.0, 2.0, 3.0), (2.0, 2.0, 2.0), (1.0, 1.0, 1.0), (0.5, 1.0, 1.5))


class Pinwheels:

    TIMER_MIN = 10.0
    TIMER_MAX = 13.0

    def __init__(self, rnd):
        self.rnd = rnd
        self.awake = True
        self.base = 1.0
        self.allPinsSpeed = 1.0
        self.allPinsTimer = rnd.uniform(self.TIMER_MIN, self.TIMER_MAX)
        self.allPinsTime = 0.0
        n = len(PINWHEELS)
        self.current = [0.0] * n
        self.start = [0.0] * n
        self.up = [True] * n
        self.run = [10.0] * n
        # Degrees each pinwheel has turned so far.
        self.angle = [0.0] * n
        self.t = 0.0
        self.left = 0.0

    def toggleSleepWake(self):
        if self.awake:
            self.awake = False
            self.base = 1.0
        else:
            self.awake = True
            self.base = 0.3

    def update(self, dt):
        self.left += dt
        while self.left >= FRAME:
            self.left -= FRAME
            self.t += FRAME
            self.__step()

    def __step(self):
        t = self.t
        if t - self.allPinsTime >= self.allPinsTimer:
            if not self.awake:
                self.base = 0.2
            self.allPinsTimer = self.rnd.uniform(self.TIMER_MIN, self.TIMER_MAX)
            for i in range(len(self.run)):
                self.run[i] = self.rnd.uniform(self.allPinsTimer - 3.0, self.allPinsTimer)
            self.allPinsTime = t
        for i, (speed, easeIn, easeOut) in enumerate(PINWHEELS):
            if t - self.start[i] > self.run[i]:
                self.up[i] = not self.up[i]
                self.start[i] = t
            self.angle[i] = (self.angle[i] + self.current[i] * FRAME) % 360.0
            if self.up[i]:
                if self.current[i] < self.base * self.allPinsSpeed * speed * 360.0:
                    self.current[i] += easeIn
            elif self.current[i] > 0.0:
                self.current[i] -= easeOut
            else:
                self.current[i] = 0.0


class Bulb:
    """One light bulb: it waits a moment after the town falls asleep, comes
    on with a crackle (some sputter first) and goes out a moment after the
    town wakes."""

    def __init__(self, rnd, sleepDelay, wakeDelay, sound, sputter=0.0, flicker=0.0, speed=0.0):
        self.rnd = rnd
        self.sleepDelay = sleepDelay
        self.wakeDelay = wakeDelay
        self.sound = sound
        # How long it sputters, how bright the sputter gets and how fast it
        # wavers (0 seconds: it just comes on).
        self.sputter = sputter
        self.flicker = flicker
        self.speed = speed
        self.cycle = 0.1
        self.awake = True
        self.lightOn = False
        self.prevLightOn = False
        self.sputtering = False
        self.sputterOnTime = 0.0
        self.intensity = 0.0
        self.switchAt = None

    def toggleSleepWake(self, t):
        if self.awake:
            self.awake = False
            self.switchAt = (t + self.sleepDelay, True)
        else:
            self.awake = True
            self.switchAt = (t + self.wakeDelay, False)

    def step(self, t, emit):
        if self.switchAt is not None and t >= self.switchAt[0]:
            self.lightOn = self.switchAt[1]
            self.switchAt = None
        if self.lightOn:
            if not self.prevLightOn and not self.sputtering:
                self.sputtering = True
                self.sputterOnTime = t
                emit(self.sound)
            if not self.prevLightOn and t - self.sputterOnTime < self.sputter:
                self.cycle += self.rnd.uniform(0.01, 1.0) * self.speed
                self.intensity = math.sin(math.radians(self.cycle)) * (self.flicker / 2.0) + self.flicker / 2.0
            else:
                self.sputtering = False
                self.prevLightOn = True
                self.intensity = 1.0
        elif self.prevLightOn:
            self.prevLightOn = False
            self.intensity = 0.0


class Bulbs:
    """The power building's left, middle and top bulb and the pet shop's, in
    the order the town model stores their light."""

    def __init__(self, rnd):
        self.bulbs = [
            Bulb(rnd, 1.25, 1.5, 'LB_laser_beam_on_2'),
            Bulb(rnd, 1.75, 2.5, 'LB_sparks_1', sputter=1.25, flicker=3.73, speed=100.0),
            Bulb(rnd, 1.5, 1.75, 'LB_laser_beam_on_2'),
            Bulb(rnd, 1.0, 1.0, 'LB_sparks_1', sputter=10.0, flicker=1.0, speed=4.0),
        ]
        self.t = 0.0
        self.left = 0.0

    def toggleSleepWake(self):
        for bulb in self.bulbs:
            bulb.toggleSleepWake(self.t)

    def update(self, dt, emit):
        """emit(index, sound) when a bulb comes on."""
        self.left += dt
        while self.left >= FRAME:
            self.left -= FRAME
            self.t += FRAME
            for k, bulb in enumerate(self.bulbs):
                bulb.step(self.t, lambda sound, k=k: emit(k, sound))

    def levels(self):
        return [bulb.intensity for bulb in self.bulbs]


class Bubble:
    """BubbleBehaviour on a Unity rigid body (mass 0.1, drag 0.77), in Unity
    units with z up."""

    DRAG = 0.77
    GRAVITY = -9.81
    START_SCALE = 0.6
    RADIUS = 0.55

    def __init__(self, rnd, pos, t):
        self.pos = list(pos)
        self.vel = [-20.0, float(rnd.randrange(-6, 6)), 25.0]
        self.scale = self.START_SCALE
        self.maxRad = rnd.uniform(0.6, 5.0)
        self.growRate = self.maxRad / rnd.uniform(1.0, 100.0)
        self.birthday = t
        self.lifespan = float(rnd.randrange(2, 8))
        self.popTimer = None
        self.popped = None
        self.floor = None
        self.raySpot = None
        self.steps = 0

    def physics(self, ground):
        k = max(0.0, 1.0 - self.DRAG * FIXED)
        self.vel[2] += self.GRAVITY * FIXED
        for i in range(3):
            self.vel[i] *= k
            self.pos[i] += self.vel[i] * FIXED
        if ground is not None and self.vel[2] <= 0.0:
            # Looking for the floor costs a ray: a few times a second will do,
            # and a bubble that has come to rest keeps the floor it found.
            if self.steps % 8 == 0:
                spot = self.raySpot
                if spot is None or abs(self.pos[0] - spot[0]) > 0.05 or abs(self.pos[1] - spot[1]) > 0.05 or abs(self.pos[2] - spot[2]) > 0.05:
                    self.floor = ground(self.pos[0], self.pos[1], self.pos[2] + 1.0)
                    self.raySpot = (self.pos[0], self.pos[1], self.pos[2])
            self.steps += 1
            floor = self.floor
            if floor is not None and self.pos[2] - self.RADIUS * self.scale < floor:
                # The bubble's material neither bounces nor slides far.
                self.pos[2] = floor + self.RADIUS * self.scale
                self.vel[2] = 0.0
                self.vel[0] *= 0.8
                self.vel[1] *= 0.8

    def frame(self, t, asleep):
        """-> True when it pops this frame."""
        if not asleep or self.popped is not None:
            return False
        if t - self.birthday > self.lifespan:
            return self.__pop(t)
        if self.vel[2] < 0.001:
            if self.popTimer is None:
                self.popTimer = t
            elif t - self.popTimer > 5.0:
                return self.__pop(t)
        elif self.scale <= self.maxRad:
            self.scale += self.growRate
        return False

    def __pop(self, t):
        self.popped = t
        self.scale = 0.0
        return True


class Bubbles:
    """BubbleGen: while the Gag Shop sleeps, every snore (two seconds into
    the clip, for a fifth of a second) blows a string of bubbles out of the
    chimney."""

    def __init__(self, rnd):
        self.rnd = rnd
        self.bubbles = []
        self.t = 0.0
        self.fixedLeft = 0.0
        self.frameLeft = 0.0

    def update(self, dt, asleep, snore, chimney, ground, onNew, onPop, onGone):
        """snore: how far the snore clip is (0..1 of its length, None when
        it is not playing) and its length; chimney(): where the chimney is
        now."""
        self.fixedLeft += dt
        while self.fixedLeft >= FIXED:
            self.fixedLeft -= FIXED
            self.t += FIXED
            if asleep and snore is not None:
                at, length = snore
                if 2.0 / length < at % 1.0 < 2.2 / length:
                    bubble = Bubble(self.rnd, chimney(), self.t)
                    self.bubbles.append(bubble)
                    onNew(bubble)
            for bubble in self.bubbles:
                if bubble.popped is None:
                    bubble.physics(ground)
        self.frameLeft += dt
        while self.frameLeft >= FRAME:
            self.frameLeft -= FRAME
            for bubble in self.bubbles:
                if bubble.frame(self.t, asleep):
                    onPop(bubble)
        for bubble in [b for b in self.bubbles if b.popped is not None and self.t - b.popped > 2.0]:
            self.bubbles.remove(bubble)
            onGone(bubble)
