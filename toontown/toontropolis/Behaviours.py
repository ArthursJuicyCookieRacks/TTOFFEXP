# Disney's small scripts that decide WHICH move a Toontropolis thing plays WHEN, ported line for line onto uanim.UAnimation.
# (The shops have their own port in ShopControl.py.)  Pure Python: the same code drove the converter's check pictures.
#
#   actor = Actor(clips={name: (seconds, wrap)}, awrap, default, auto, scripts=[(class name, settings dict)], seed)
#   actor.sample(t) -> [(clip, seconds into the clip, effect)]     (t must not go backwards; call reset() to start over)
#   actor.send('HonkHorn') ...                                      messages other scripts would send (Cog Pinata, fear, power switch)
import math
import random
from toontown.toontropolis.UnityAnim import UAnimation, LOOP, ONCE

WORLD = {'fear': False}        # triggerCogBuilding.fear is one static flag shared by the whole town


class RandomAnim:
    """Hydrants, mailboxes, trash cans: play one of four moves, wait for it to finish, rest 3 to 10 seconds, again."""
    def __init__(self, a, cfg, rnd):
        self.a = a; self.rnd = rnd; self.can = bool(cfg.get('canAnimate', True)); self.moves = [cfg['animA'], cfg['animB'], cfg['animC'], cfg['animD']]
        self.state = 'ready'; self.wake = 0.0; self.choice = 0
    def start(self): pass
    def update(self, t):
        # Update() starts the Idles coroutine every frame; it only does something while canAnimate is set
        if self.state == 'ready' and self.can:
            self.can = False; self.choice = self.rnd.randrange(1, 5)               # Random.Range(1, 5)
            self.a.CrossFade(self.moves[self.choice - 1]); self.state = 'playing'  # then: while (animation.isPlaying) yield
        elif self.state == 'playing':
            if not self.a.isPlaying:                                              # StartCoroutine(WaitForSomething())
                self.wake = t + self.rnd.randrange(3, 11); self.state = 'waiting'  # timer = Random.Range(3, 11); yield WaitForSeconds(timer)
        elif self.state == 'waiting' and t >= self.wake:
            self.can = True; self.state = 'ready'


class Fear:
    """Bank and Library: keep playing the calm idle; once the Cogs take Toon Hall (fear), loop the frightened move instead."""
    def __init__(self, a, cfg, rnd): self.a = a; self.idle = cfg['idle']; self.afraid = cfg['afraid']
    def start(self): pass
    def update(self, t):
        if not WORLD['fear']: self.a.Play(self.idle)
        else: self.a.Stop(self.idle); self.a.set_wrap(LOOP); self.a.Play(self.afraid)


class ToonHall:
    """triggerCogBuilding.Start(): Toon Hall loops its slow idle (the take-over itself is game logic: see the Survival map)."""
    def __init__(self, a, cfg, rnd): self.a = a; self.idle = cfg['buildingIdle']; self.damage = cfg['animBuildingDamage']
    def start(self): self.a.set_wrap(LOOP); self.a.Play(self.idle)
    def update(self, t): pass
    def takeover(self):                      # the part of OnTriggerEnter that touches the animation
        self.a.Stop(self.idle); self.a.set_wrap(ONCE); self.a.Play(self.damage)
    def restore(self):                       # (not Disney's: the toons have it back, so it idles again and can be taken again)
        self.a.Stop(self.damage); self.a.set_wrap(LOOP); self.a.Play(self.idle)


class CogBuilding:
    """cogdoAanim, on the Cog building the take-over makes: play the drop once, then loop the idle. (The prototype made the building
    at that moment; here it waits in the model until Begin.)"""
    def __init__(self, a, cfg, rnd): self.a = a; self.t = 0.0; self.began = None; self.idling = False
    def start(self): pass
    def Begin(self): self.began = self.t; self.idling = False; self.a.Stop(); self.a['drop'].wrap = ONCE; self.a.Play('drop')
    def Leave(self): self.began = None; self.idling = False; self.a.Stop()        # (not Disney's: gone again, until the next Begin)
    def update(self, t):
        self.t = t
        if self.began is not None and not self.idling and t - self.began >= self.a['drop'].length:
            self.idling = True; self.a['idle'].wrap = LOOP; self.a.Play('idle')


class HypnoOwl:
    """hypnoOwl.Start() + OwlBehaviorScript: the glasses spin on their own layer; the owl picks idle / look / jump / sneeze, or idles for a while."""
    def __init__(self, a, cfg, rnd): self.a = a; self.rnd = rnd; self.moves = [cfg['animA'], cfg['animB'], cfg['animC'], cfg['animD']]
    def start(self):
        self.a.set_wrap(LOOP)
        if 'hypnoEyes' in self.a: self.a['hypnoEyes'].layer = 9; self.a.CrossFade('hypnoEyes')
        self.first = True; self.can = True; self.wait = 10.0; self.a.CrossFade(self.moves[0]); self.t0 = 0.0
    def update(self, t):
        if self.first: self.first = False; self.can = True; return
        if self.can:
            c = self.rnd.randrange(1, 6)                                           # Random.Range(1, 6)
            if c <= 4: self.a.CrossFade(self.moves[c - 1]); self.wait = self.a[self.moves[c - 1]].length
            else: self.a.CrossFade(self.moves[0]); self.wait = self.rnd.randrange(3, 10) * self.a[self.moves[0]].length
            self.t0 = t; self.wait += self.rnd.randrange(3, 11)
        self.can = (t - self.t0 >= self.wait)


class CogPinata:
    """CPN_CogPinataControl: swings (idle0); lies flat while the town sleeps; anvil drop and horn honk play on top (layer 11)."""
    def __init__(self, a, cfg, rnd): self.a = a; self.awake = True
    def start(self): self.a.Play('idle0'); self.awake = True
    def update(self, t): pass
    def ToggleSleepWake(self):
        if self.awake: self.awake = False; self.a.CrossFade('layFlat')
        else: self.awake = True; self.a.Stop('layFlat'); self.a.Play('idle0')
    def AnvilDrop(self): self.a['anvilDrop3'].layer = 11; self.a.CrossFade('anvilDrop3')
    def HonkHorn(self): self.a['honkHorn'].layer = 11; self.a.CrossFade('honkHorn')


class Shop:
    """The living shops (PET_, CSP_, MUS_, PWR_ ...BuildingControl, GS_RandomAnim): shopcontrol.ShopControl decides, Unity's Animation plays."""
    FADES = {'PWR_PowerBuildingControl': {'sleepIntoIdle': 0.1, 'idleIntoSleep': 0.25}}     # the power building cross-fades its two transitions faster
    def __init__(self, a, cfg, rnd):
        from toontown.toontropolis.ShopControl import ShopControl
        self.a = a; self.fades = self.FADES.get(cfg.get('cls'), {})
        self.c = ShopControl(cfg['idle'], cfg['sleep'], {n: st.length for n, st in a.states.items()}, {n: st.wrap for n, st in a.states.items()}, seed=rnd.randrange(1 << 30))
        self.c._play = lambda clip: self.a.CrossFade(clip, self.fades.get(clip, 0.3))
        self.rnd = rnd; self.t = 0.0; self.later = []; self.emit = lambda name: None      # emit: a sound to play (set by whoever owns the actor)
    def start(self): self.a.Play('idle0')
    def update(self, t):
        self.t = t; self.c.t = t; self.c.update()
        # Unity resumes a script's coroutines right after its Update()
        while self.later and self.later[0][0] <= t + 1e-9: self.later.pop(0)[2]()
    def after(self, seconds, fn):
        """yield WaitForSeconds(seconds), then the rest of the coroutine."""
        self.later.append((self.t + seconds, len(self.later), fn)); self.later.sort(key=lambda e: e[:2])
    @property
    def awake(self): return self.c.awake
    def ToggleSleepWake(self): self.c.toggle()
    def AnvilBang(self):
        if 'anvilBang' in self.a: self.a['anvilBang'].layer = 9; self.a.CrossFade('anvilBang')
    def HonkHorn(self):
        """GS_RandomAnim.HonkHorn: the horn arm squeezes (layer 10 over whatever the shop is doing); the honk sounds a quarter of a second in."""
        a = self.a
        if 'honkHorn1' not in a or a['honkHorn1'].enabled or a['anvilDrop'].enabled or not self.c.awake: return
        a['honkHorn1'].layer = 10; a.CrossFade('honkHorn1'); self.after(0.25, lambda: self.emit('honk'))
    def AnvilDrop(self):
        """GS_RandomAnim.AnvilDrop: the anvil falls (layer 11) with its whistle; the shop picks no new move until it has landed."""
        a = self.a
        if 'anvilDrop' not in a or a['anvilDrop'].enabled or a['honkHorn1'].enabled or not self.c.awake: return
        a['anvilDrop'].layer = 11; a.Play('anvilDrop'); self.c.can = False; self.emit('anvil')
        self.after(a['anvilDrop'].length, lambda: setattr(self.c, 'can', True))
    def PlayCymbal(self, which):
        """MUS_PlayCymbal.PlayCymbal: the cymbal crashes 5 to 14 times in a row (layer 9), each crash sounding 0.4 seconds into its swing."""
        a = self.a; nm = 'idleCymbal%dPlay' % which
        if nm not in a or a[nm].enabled: return
        n = self.rnd.randrange(5, 15)                                                  # Random.Range(5, 15)
        def crash(i):
            a[nm].layer = 9; a.CrossFade(nm, 0.1); self.after(0.4, lambda: self.emit('cymbal%d' % which))
            if i + 1 < n: self.after(a[nm].length, lambda: crash(i + 1))
        crash(0)


class Bouncing:
    """bouncing.cs (the fountain's two water jets): a chain of four joints; the first is thrown from a random spot in an arc, the others trail it by one
    frame each. Disney wrote it per rendered frame (no clock), so it is stepped at 60 frames a second, the web player's rate.
    rest = Unity local positions of joint1..joint4. sample(t) -> the four local positions (Unity axes)."""
    RATE = 60.0
    def __init__(self, cfg, rest, rnd):
        import math
        self.m = math; self.h = cfg['height']; self.R1 = cfg['R1']; self.R2 = cfg['R2']; self.ar = cfg['angle_range']; self.rnd = rnd
        self.j = [list(p) for p in rest]; self.j5 = [0.0] * 3; self.j6 = [0.0] * 3; self.j7 = [0.0] * 3
        self.g = 0.01; self.flag = False; self.vx = self.vy = self.vz = 0.0; self.n = 0
    def step(self):
        m = self.m; j1, j2, j3, j4 = self.j
        if not self.flag:                                                           # ResetValues(): SetPositions + Initialize
            th = float(self.rnd.randrange(0, 360)); ph = self.rnd.uniform(0.0, self.ar)          # (Disney feeds degrees to Cos/Sin as radians)
            d1 = self.rnd.uniform(self.R1, self.R2); d2 = self.rnd.uniform(self.R1, self.R2)
            p1 = (d1 * m.cos(th), d1 * m.sin(th)); p2 = (d2 * m.cos(th + ph), d2 * m.sin(th + ph))
            self.vy = m.sqrt(2 * self.h * self.g); k = 2 * m.sqrt(2 * self.h / self.g)
            self.vx = (p1[0] - p2[0]) / k; self.vz = (p1[1] - p2[1]) / k; j1[0] = p1[0]; j1[2] = p1[1]; self.flag = True
        else:
            j4[:] = self.j5; self.j5 = list(j3); j3[:] = self.j6; self.j6 = list(j2); j2[:] = self.j7; self.j7 = list(j1)
            j1[0] += self.vx; j1[1] += self.vy; j1[2] += self.vz; self.vy -= self.g                  # Jump()
            if j1[1] < -10: self.vy = self.vx = self.vz = 0.0; j1[:] = [0.0, 0.0, 0.0]; self.flag = False
        self.n += 1
    def sample(self, t):
        while self.n < int(t * self.RATE): self.step()
        return [tuple(p) for p in self.j]


class Pet:
    """PetControlsMulti with PetState, IdleLogic, WanderLogic and FollowLogic: the doodle that lives on the plaza. It idles for 11 to 17
    seconds (plain idle, digging, a backflip, a laugh), wanders for 8 to 12 (turning right a little every four seconds), and so on; told
    to heel (Disney's P key) it runs after its owner and idles beside them. Disney's loop runs once a frame: twice per step here.
    world (set by the game) is where it stands: pos() -> (x, y, z), setHeading(degrees), move(dx, dy), owner() -> ((x, y, z), speed) or
    None, all in Unity units with z up; heading is Unity's (clockwise from +y seen from above)."""
    IDLE, WANDER, FOLLOW = 0, 1, 2
    FRAME = 1 / 60.0
    STATE_DUR = ((11.0, 17.0), (8.0, 12.0), (0.0, 100.0))                                   # PetState.stateDur: idle, wander, follow
    IDLE_ACTIONS = (('idle', 1.0, 4.0, 0.0), ('dig', 3.0, 7.0, 10.0), ('backflip', 1.0, 1.0, 7.0), ('laugh', 2.0, 6.0, 5.0))   # anim, min_dur, max_dur, delta
    WALK = 'walk'; RUN = 'run'; WANDER_SPEED = 1.0; FOLLOW_SPEED = 6.0; ROTATION_SPEED = 6.0; OWNER_DIST = 2.5
    def __init__(self, a, cfg, rnd):
        self.a = a; self.rnd = rnd; self.world = None; self.heading = float(cfg.get('heading', 0.0)); self.calledByPlayer = 0
        self.indexAction = 0; self.stateStartTime = 0; self.stateTimeOut = 0.0; self.useTimer = True
        self.actionIndex = 0; self.lastTimeRun = []; self.numIter = 1; self.runLength = 0.0
        self.turnTimer = 0.0; self.randomRot = 0.0; self.timeLastTurn = 0.0; self.turnIncr = 0.0; self.startDirection = 0.0; self.newDirection = 0.0
    def start(self):
        acts = self.IDLE_ACTIONS                                                             # IdleLogic.Start()
        self.lastTimeRun = [-100.0] * len(acts); self.lastTimeRun[0] = 0.0; self.actionIndex = 0
        self.numIter = int(self.rnd.uniform(1.0, acts[0][2])); self.runLength = self.numIter * self.a[acts[0][0]].length
        self.a.Play(acts[0][0])
        self.initState(self.IDLE, 0.0)                                                       # PetControlsMulti.MainLoop() begins
    def initState(self, state, t):
        self.indexAction = state; self.stateStartTime = int(t); self.stateTimeOut = self.rnd.uniform(*self.STATE_DUR[state])
    def SetFollowState(self, state): self.calledByPlayer = int(state)
    def HeelForce(self):
        owner = self.world.owner() if self.world is not None else None
        if owner is None: return
        x, y, z = owner[0]
        # Two units past its owner, as Disney had it; beside or on the owner's own spot where that is inside a wall.
        for dx, dy in ((0.0, 2.0), (2.0, 0.0), (-2.0, 0.0), (0.0, -2.0), (0.0, 0.0)):
            if self.world.jump(x + dx, y + dy, z): return
        # Its owner stands somewhere the walking map does not know (up on a prop): right there, then.
        self.world.jump(x, y, z, True)
    def update(self, t):
        for sub in (t - self.FRAME, t): self.frame(sub, self.FRAME)
    def frame(self, t, dt):
        new = self.getPetState(t)
        if new != self.indexAction:
            if new == self.IDLE:                                                             # IdleLogic.Into()
                idle = self.IDLE_ACTIONS[0][0]; self.runLength = self.a[idle].length; self.a.CrossFade(idle, 0.15); self.lastTimeRun[0] = t; self.actionIndex = 0
            elif new == self.WANDER:                                                         # WanderLogic.Into()
                self.a.CrossFade(self.WALK, 0.15); self.turnTimer = 0.0
            self.initState(new, t)
        if self.indexAction == self.IDLE: self.idleAnimation(t)
        elif self.indexAction == self.WANDER: self.wanderAnimation(t, dt)
        else: self.followAnimation(t, dt)
    def getPetState(self, t):
        result = self.indexAction; self.useTimer = True
        owner = self.world.owner() if (self.calledByPlayer and self.world is not None) else None
        if owner is not None:
            here = self.world.pos(); dist = sum((here[i] - owner[0][i]) ** 2 for i in range(3)) ** 0.5
            if dist <= self.OWNER_DIST and owner[1] < 1.0: result = self.IDLE
            elif dist > self.OWNER_DIST: result = self.FOLLOW
            self.useTimer = False
        elif self.indexAction == self.FOLLOW: result = self.rnd.randrange(0, 2)
        elif t - self.stateStartTime > self.stateTimeOut: result = {self.IDLE: self.WANDER, self.WANDER: self.IDLE}.get(self.indexAction, self.indexAction)
        return result
    def idleAnimation(self, t):
        acts = self.IDLE_ACTIONS
        if t - self.lastTimeRun[self.actionIndex] < self.runLength - 0.15: return
        tried = [0] * len(acts); left = list(range(len(acts))); found = False; n = 0; pick = self.actionIndex
        while not found and n < len(left):
            at = self.rnd.randrange(0, len(left)) if n < len(acts) - 1 else 0
            k = left[at]
            if tried[k] == 0:
                if t - self.lastTimeRun[k] > acts[k][3]:
                    state = self.a[acts[k][0]]
                    self.numIter = int(self.rnd.uniform(acts[k][1], acts[k][2])) if state.wrap == LOOP else 1
                    self.runLength = self.numIter * state.length; fits = True
                    if self.useTimer:
                        fits = False; remaining = self.stateStartTime + self.stateTimeOut - t
                        while not fits and remaining > 0 and self.runLength > 0:
                            if self.runLength <= remaining: fits = True
                            else:
                                self.numIter -= 1
                                self.runLength = self.numIter * state.length if self.numIter > acts[k][1] else 0.0
                    if fits and self.numIter >= 1: found = True; pick = k
                tried[k] = 1; left.pop(at); n += 1
        if found:
            self.actionIndex = pick; self.a.CrossFade(acts[pick][0], 0.15); self.lastTimeRun[pick] = t
        else: self.stateTimeOut = -1.0
    def wanderAnimation(self, t, dt):
        self.a.CrossFade(self.WALK)
        if t - self.timeLastTurn > 4.0:
            self.randomRot = float(self.rnd.randrange(25, 45)); self.startDirection = self.heading; self.newDirection = self.heading + self.randomRot
            self.rnd.randrange(1, 3); self.turnIncr = 1.0 / abs(self.randomRot); self.turnTimer = self.turnIncr; self.timeLastTurn = t
        if self.turnTimer < self.randomRot:
            k = min(max(self.turnTimer, 0.0), 1.0); self.heading = (self.startDirection + (self.newDirection - self.startDirection) * k) % 360.0
            self.turnTimer += self.turnIncr
            if self.turnTimer >= self.randomRot: self.randomRot = 0.0; self.turnTimer = 0.0
        self.walk(self.WANDER_SPEED * dt)
    def followAnimation(self, t, dt):
        self.a.CrossFade(self.RUN)
        self.walk(self.FOLLOW_SPEED * dt)
        owner = self.world.owner() if self.world is not None else None
        if owner is None: return
        here = self.world.pos(); dx = owner[0][0] - here[0]; dy = owner[0][1] - here[1]
        if (dx * dx + dy * dy) ** 0.5 >= 0.1:                                               # RotateTowards()
            want = math.degrees(math.atan2(dx, dy)); turn = (want - self.heading + 180.0) % 360.0 - 180.0
            self.heading = (self.heading + turn * min(1.0, self.ROTATION_SPEED * dt)) % 360.0
            self.world.setHeading(self.heading)
    def walk(self, distance):
        if self.world is None: return
        self.world.setHeading(self.heading)
        r = math.radians(self.heading); self.world.move(math.sin(r) * distance, math.cos(r) * distance)


SCRIPTS = {'Shop': Shop, 'RandomAnim': RandomAnim, 'Fear': Fear, 'triggerCogBuilding': ToonHall, 'OwlBehaviorScript': HypnoOwl, 'CPN_CogPinataControl': CogPinata, 'PetControlsMulti': Pet, 'cogdoAanim': CogBuilding}


class Actor:
    """One animated thing: Unity's Animation component plus the scripts Disney attached to it, stepped 30 times a second."""
    def __init__(self, clips, awrap=0, default=None, auto=False, scripts=(), seed=0, dt=1 / 30.0, events=()):
        self.args = (clips, awrap, default, auto, tuple(scripts), seed, dt, tuple(events)); self.reset()
    def reset(self):
        clips, awrap, default, auto, scripts, seed, dt, events = self.args
        self.a = UAnimation(clips, awrap, default, auto); self.rnd = random.Random(seed); self.dt = dt; self.t = 0.0
        self.scripts = [SCRIPTS[c](self.a, cfg, self.rnd) for c, cfg in scripts if c in SCRIPTS and cfg.get('enabled', 1)]
        self.events = sorted(events); self.log = []
        self.a.start()
        for s in self.scripts: s.start()
    def send(self, msg, *args):
        for s in self.scripts:
            if hasattr(s, msg): getattr(s, msg)(*args)
    def script(self, cls):
        return next((s for s in self.scripts if isinstance(s, cls)), None)
    def step(self):
        while self.events and self.t >= self.events[0][0]: self.send(self.events.pop(0)[1])
        for s in self.scripts: s.update(self.t)
        self.a.update(self.dt); self.t += self.dt
    def sample(self, t):
        if t < self.t - 1e-6: self.reset()
        while self.t + self.dt <= t + 1e-9: self.step()
        return self.a.sample()
    def timeline(self, T):
        """[(time, clips playing)] whenever the set of playing clips changes: for checking a behaviour by eye."""
        out = []; last = None
        while self.t < T:
            self.step(); now = tuple(sorted(n for n, _, e in self.a.sample() if e >= 1e-3))
            if now != last: out.append((round(self.t, 2), now)); last = now
        return out
