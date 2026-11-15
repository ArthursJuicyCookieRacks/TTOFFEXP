# Unity's old "Animation" component, rebuilt rule for rule, so a converted character plays its clips exactly the way Disney's scripts drove them:
# Play / CrossFade / Blend / Stop, wrap modes, layers, weights that fade, clips that stop by themselves, and "the pose stays where the last clip left it".
# Pure Python (no Panda): the same code drove the converter's check pictures.
#
#   a = UAnimation(clips={name: (length_seconds, wrap)}, awrap=component wrap mode, default=clip name or None, auto=play automatically)
#   a.start()                      what Unity does when the scene loads (plays the default clip if "play automatically" is ticked)
#   a.Play(name) / a.CrossFade(name, 0.3) / a.Blend(name, 1, 0.3) / a.Stop(name=None) / a.set_wrap(mode) / a[name].layer = 9 ...
#   a.update(dt)                   once per frame AFTER the scripts ran (Unity's order: Update, then animation)
#   a.sample() -> [(clip, seconds into the clip, effect)]   effects are ready for Panda's setControlEffect (per-joint normalisation does the rest)
ONCE, LOOP, PINGPONG, CLAMP = 1, 2, 4, 8
FLOOR = 1e-3           # least effect of a clip that is playing
HOLD = 1e-6            # effect of a pose that is only being held (its clip ended): far below any playing clip, and the newest hold wins


class UState:
    def __init__(self, name, length, wrap):
        self.name = name; self.length = float(length); self.wrap = wrap; self.clipwrap = wrap
        self.enabled = False; self.weight = 0.0; self.time = 0.0; self.speed = 1.0; self.layer = 0; self.blendMode = 0
        self._target = None; self._rate = 0.0; self._stop_when_faded = False

    def clip_time(self):
        """Where in the clip the state is, after the wrap mode."""
        L = self.length; t = self.time
        if L <= 0: return 0.0
        if self.wrap == LOOP: return t % L
        if self.wrap == PINGPONG:
            u = t % (2 * L); return u if u <= L else 2 * L - u
        return min(max(t, 0.0), L)


class UAnimation:
    def __init__(self, clips, awrap=0, default=None, auto=False):
        self.awrap = awrap or ONCE; self.default = default; self.auto = auto; self.states = {}; self.order = []
        for nm, (length, wrap) in clips.items():
            self.states[nm] = UState(nm, length, wrap or self.awrap); self.order.append(nm)
        self.held = []          # (clip, clip time) of clips that ended: Unity leaves every joint where its last clip put it
        self.now = 0.0

    def __getitem__(self, nm): return self.states[nm]
    def __contains__(self, nm): return nm in self.states

    def start(self):
        if self.auto and self.default in self.states: self.Play(self.default)

    # ---- Unity's calls
    def set_wrap(self, mode):
        """animation.wrapMode = mode: Unity writes it onto every clip state."""
        self.awrap = mode
        for s in self.states.values(): s.wrap = mode

    def _begin(self, s):
        if not s.enabled: s.time = 0.0
        s.enabled = True; s._stop_when_faded = False
        self.held = [h for h in self.held if h[0] != s.name]

    def _end(self, s, hold=True):
        if s.enabled and hold:
            self.held = [h for h in self.held if h[0] != s.name]; self.held.insert(0, (s.name, s.clip_time())); del self.held[3:]
        s.enabled = False; s.time = 0.0; s._target = None; s._stop_when_faded = False

    def Play(self, nm=None):
        nm = nm or self.default
        if nm not in self.states: return False
        s = self.states[nm]
        for o in self.states.values():
            if o is not s and o.layer == s.layer and o.enabled: self._end(o)
        self._begin(s); s.weight = 1.0; s._target = None
        return True

    def CrossFade(self, nm, fade=0.3):
        if nm not in self.states: return
        s = self.states[nm]
        for o in self.states.values():
            if o is not s and o.layer == s.layer and o.enabled:
                o._target = 0.0; o._rate = (0.0 - o.weight) / fade if fade > 0 else 0.0; o._stop_when_faded = True
                if fade <= 0: self._end(o)
        if not s.enabled: s.weight = 0.0
        self._begin(s)
        if fade > 0: s._target = 1.0; s._rate = (1.0 - s.weight) / fade
        else: s.weight = 1.0; s._target = None

    def Blend(self, nm, target=1.0, fade=0.3):
        if nm not in self.states: return
        s = self.states[nm]
        if not s.enabled: s.weight = 0.0
        self._begin(s)
        if fade > 0: s._target = target; s._rate = (target - s.weight) / fade
        else: s.weight = target; s._target = None

    def Stop(self, nm=None):
        for s in self.states.values():
            if (nm is None or s.name == nm) and s.enabled: self._end(s)

    def IsPlaying(self, nm): return nm in self.states and self.states[nm].enabled
    @property
    def isPlaying(self): return any(s.enabled for s in self.states.values())

    # ---- one frame
    def update(self, dt):
        self.now += dt
        for s in self.states.values():
            if not s.enabled: continue
            if s._target is not None:
                s.weight += s._rate * dt
                if (s._rate >= 0 and s.weight >= s._target) or (s._rate < 0 and s.weight <= s._target):
                    s.weight = s._target; s._target = None
                    if s._stop_when_faded and s.weight <= 0: self._end(s, hold=False); continue
            s.time += dt * s.speed
            if s.wrap == ONCE and (s.time >= s.length or s.time < 0):
                s.time = min(max(s.time, 0.0), s.length); self._end(s)       # stops by itself; the pose stays

    def sample(self):
        """[(clip, seconds into the clip, effect)]: higher layers take their weight first, what is left goes to the layers below."""
        out = []; left = 1.0
        layers = sorted({s.layer for s in self.states.values() if s.enabled and s.weight > 0}, reverse=True)
        for ly in layers:
            grp = [s for s in self.states.values() if s.enabled and s.layer == ly and s.weight > 0]; sw = sum(s.weight for s in grp)
            # every playing clip keeps a sliver of say (FLOOR): a joint that only a fully covered lower layer drives must still follow that clip
            for s in grp: out.append((s.name, s.clip_time(), max(left * s.weight / max(sw, 1.0), FLOOR)))
            left *= max(0.0, 1.0 - sw)
        w = HOLD
        for nm, t in self.held:
            if not self.states[nm].enabled: out.append((nm, t, w)); w *= 1e-3
        return out
