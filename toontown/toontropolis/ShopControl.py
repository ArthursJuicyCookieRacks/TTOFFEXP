# Disney's living-shop behaviour (PET_PetShopBuildingControl and its twins CSP_, MUS_, PWR_, GS_RandomAnim), ported line for line.
# A shop plays idle0, and every so often one of its special moves; each move has a minimum gap (clip length x delta). Looping moves run a random
# whole number of loops (min_dur..max_dur). ToggleSleepWake switches to the sleep table through idleIntoSleep / sleepIntoIdle. Moves cross-fade (0.3 s).
import random, bisect
FADE = 0.3                      # Unity's default CrossFade length
LOOP = 2                        # Unity WrapMode.Loop

class ShopControl:
    def __init__(self, idle, sleep, length, wrap, seed=0, dt=1 / 30.0):
        """idle / sleep: lists of dict(anim, min_dur, max_dur, delta) exactly as Disney stored them; length: clip -> seconds; wrap: clip -> Unity wrap mode."""
        self.idle = idle; self.sleep = sleep; self.length = length; self.wrap = wrap; self.rnd = random.Random(seed); self.dt = dt; self.segs = []; self.t = 0.0
        # Start()
        self.awake = True; self.prev_awake = True; self.start = 0.0; self.prev_choice = 0; self.wait = 2 * length[sleep[0]['anim']]
        self.last = {True: [0.0] * len(idle), False: [0.0] * len(sleep)}
        self.rate = {True: [length[a['anim']] * a['delta'] for a in idle], False: [length[a['anim']] * a['delta'] for a in sleep]}
        self.can = False; self.first = True; self._play('idle0')
    def _play(self, clip): self.segs.append((self.t, clip))
    def toggle(self): self.awake = not self.awake            # ToggleSleepWake (FallAsleep / WakeUp)
    def update(self):                                        # Update(), once per rendered frame
        t = self.t
        if self.first: self.first = False; return
        if self.can:
            if self.awake != self.prev_awake:                # just told to wake up or to fall asleep: play the transition
                clip = 'sleepIntoIdle' if self.awake else 'idleIntoSleep'
                self.wait = self.length[clip]; self._play(clip); L = self.last[self.awake]; L[1] = t; L[2] = t
                self.prev_choice = -1; self.prev_awake = self.awake; self.start = t
            else:
                A = self.idle if self.awake else self.sleep; L = self.last[self.awake]; R = self.rate[self.awake]
                c = self.rnd.randrange(1, len(A))
                if t - L[c] < R[c]: c = 0; self.wait = self.length[A[0]['anim']]
                if c != self.prev_choice:
                    self.prev_choice = c; clip = A[c]['anim']; self.wait = self.length[clip]
                    if self.wrap.get(clip) == LOOP: self.wait *= int(self.rnd.uniform(A[c]['min_dur'], A[c]['max_dur']))
                    L[c] = t; self._play(clip); self.start = t
        self.can = (t - self.start >= self.wait) or (not self.prev_awake and self.awake)
    def run(self, T, toggles=()):
        """Simulate up to time T; toggles = times at which the town's power switch is flipped."""
        tg = sorted(toggles)
        while self.t < T:
            while tg and self.t >= tg[0]: self.toggle(); tg.pop(0)
            self.update(); self.t += self.dt
        return self.segs
    def sample(self, t):
        """[(clip, seconds into the clip, weight)] at time t: the current move and, while fading, the one before it."""
        S = self.segs; i = max(bisect.bisect_right(S, (t, '~')) - 1, 0); out = []
        ts, clip = S[i]; w = 1.0
        if i > 0 and t - ts < FADE:
            w = (t - ts) / FADE; ps, pc = S[i - 1]; out.append((pc, self._local(pc, t - ps), 1 - w))
        out.append((clip, self._local(clip, t - ts), w)); return out
    def _local(self, clip, u):
        n = self.length[clip]
        if n <= 0: return 0.0
        return u % n if self.wrap.get(clip) == LOOP else min(u, n)
