"""Boardroom Hijinks, the Bossbot field office.

Only the name, the rules line and a 60 second clock survived from the
original game's code (the Boardroom game was cut before any of it was
made). The design notes the fan wikis keep from it say the rest: the toons
crash a Bossbot meeting and run the length of the boardroom table, Boss
Cogs sitting along both sides throw things at them, Minion Cogs flying
over the table drop golf balls, anvils, paperwork and pencils, and a minion
knocks over oil cans that leave the table slippery. Paperwork piles,
pencils and ramps are in the way; power-ups make a toon invulnerable or hop
higher; the memos picked up on the way are a Toon-Up at the end, and a hit
costs laff and memos.
"""
from direct.fsm.StatePush import StateVar
from otp.level.EntityStateVarSet import EntityStateVarSet
from toontown.cogdominium.CogdoEntityTypes import CogdoBoardroomGameSettings

# The level editor entity the original stub had (CogdoEntityCreator still
# makes it).
Settings = EntityStateVarSet(CogdoBoardroomGameSettings)
# The original game's clock: a minute down the table, then 10 s to finish.
GameDurationVar = StateVar(60.0)
FinishDurationVar = StateVar(10.0)
# The original clock was a minute, for a table one room long. Arthur asked
# for a longer office, as long as the other three: the table runs through
# three halls end to end, so the clock is longer to match.
GameDuration = 180.0
# Kept for the old stub's name.
FinishDuration = FinishDurationVar

# --- The room ---
# The CEO's banquet hall in Bossbot HQ, kitchen and all taken away: dark
# wood panelling, paintings and a green carpet, long enough for a table
# the length of a street.
RoomModel = 'phase_12/models/bossbotHQ/BanquetInterior_1'
TableModel = 'phase_12/models/bossbotHQ/BanquetTableChairs'
# The table runs up the middle of the hall. The toons run on its top.
# Three of the banquet halls end to end, the walls between them taken
# out: each hall is this long from its near wall to its far one.
NumHalls = 3
HallLength = 333.7016
TableHalfWidth = 13.0
TableStart = 96.0
TableEnd = 366.0 + (NumHalls - 1) * HallLength
TableTop = 3.6
TableLegSpacing = 24.0
# The ramp up from the floor at the near end (the toons come in at the
# floor) and the drop down at the far end to the exit.
RampLength = 14.0
# Where the toons come in, and the way out: the hall's own entry corridor
# and the far wall, past the chairman's chair.
ElevatorPosHpr = (0, 46, 0, 180, 0, 0)
ExitPosHpr = (0, 385 + (NumHalls - 1) * HallLength, 0, 0, 0, 0)
ExitRadius = 6.0
ChairmanPos = (0, TableEnd + 5.5, 0)

# --- Who is at the meeting ---
SeatSpacing = 22.0
SeatSideX = TableHalfWidth + 3.4
# Only the cogs this near the toon are shown (and move), for the frame
# rate on phones: the table is long.
ShowCogsWithin = 170.0
# Seats filled, per side, from the easiest office to the hardest.
SeatsPerSideRange = (14, 22)
MinionsRange = (5, 9)
OilCansRange = (8, 13)
MinionHeight = 15.0
# The Boss Cogs: Bossbots, as at any Bossbot meeting. The level of the
# office and its playground make them bigger.
# No Downsizers: the B body has no sitting animation in the game files.
BossCogNames = ('ym', 'mm', 'hh', 'cr', 'tbc')
MinionCogNames = ('f', 'p', 'ym')

# --- The things thrown and dropped (kind, damage at the easiest office,
# at the hardest, memos it knocks out of your hands, radius) ---
GolfBall = 0
Paper = 1
Pencil = 2
Anvil = 3
Paperwork = 4
Oil = 5
Swipe = 6
Hazards = {
    # A Boss Cog's golf club swung across the table's edge as a toon
    # slides by its chair (a strip, not a circle: see SwipeReach).
    Swipe: (2, 6, 2, 3.5),
    GolfBall: (2, 5, 1, 2.6),
    Paper: (1, 4, 1, 3.0),
    Pencil: (2, 5, 1, 2.6),
    Anvil: (4, 8, 2, 3.4),
    Paperwork: (3, 6, 1, 3.6),
}
# How long a Boss Cog's throw or a minion's drop takes to land: the red
# mark on the table shows where for this long first.
ThrowFlightTime = 1.5
DropFallTime = 1.25
WarnTime = 0.9
# How often the meeting throws things at the toons (seconds between, at
# the easiest and the hardest office).
BossAttackPeriodRange = (2.2, 1.0)
MinionDropPeriodRange = (3.2, 1.4)
OilSpillPeriodRange = (12.0, 7.0)
# Throws land this far ahead of the toon they aim at (the toons run up the
# table), give or take.
AttackLead = 12.0
AttackSpread = 4.0

# The swing at a toon sliding past a Boss Cog's chair: it reaches this far
# in over the table, this long after the warning.
SwipeReach = 8.0
SwipeTime = 0.8

# --- Sliding ---
# The toons don't walk the table: they belly-slide down it, steering left
# and right (in the air too) and hopping over what's in the way. Forward
# slides faster, back slower. Each toon sets off a moment after the last,
# so they don't all pile into each other.
SlideSpeed = 8.5
SlideFastSpeed = 13.0
SlideSlowSpeed = 4.5
SlideAccel = 10.0
SteerSpeed = 11.0
StartStagger = 1.5
StartDelay = 1.0
# A ramp throws a toon sliding up it into the air.
LaunchForce = 30.0
# Sliding into a pile or a pencil stops a toon and spins it round.
CrashTime = 0.9
SpinTime = 0.8
CameraBack = 16.0
CameraUp = 8.5

# --- On the table ---
SlickRadius = 7.5
SlickDuration = 14.0
# On a slick the toon keeps sliding the way it went: this much of its run
# speed is lost a second, and its steering counts for this little.
SlickFriction = 0.6
SlickGrip = 0.12
InvulnerableTime = 8.0
HopTime = 10.0
HopJumpForce = 38.0
# A toon hit is hurt once, then safe for this long.
HitCooldown = 1.2
PickupRadius = 2.6
PowerUpRadius = 2.6

# --- Laying out the table ---
# Each stretch of table gets one obstacle, memos and now and then a
# power-up; the first and last stretch are clear.
SegmentLength = 24.0
ClearStart = 10.0
ClearEnd = 16.0
MemosPerSegment = (2, 4)
PileHeight = (5.0, 7.5)
PencilHeight = 1.25
NumInvulnerable = 5
NumHop = 5

# --- Difficulty ---
# As at the other offices: the playground's difficulty and the office's
# level together.
LevelWeight = 0.65
LevelDifficultyMax = 8.0


def lerpDifficulty(valueRange, difficulty):
    lo, hi = valueRange
    difficulty = max(0.0, min(1.0, difficulty))
    return lo + (hi - lo) * difficulty


def hazardDamage(kind, difficulty):
    lo, hi, memos, radius = Hazards[kind]
    return int(round(lerpDifficulty((lo, hi), difficulty)))


def hazardHits(kind, x, y, z, px, py, pz):
    """Whether something of `kind` landing at (x, y, z) hits a toon at
    (px, py, pz). A swing is a strip in from the table's edge at x; the
    rest hit round where they land."""
    import math
    radius = Hazards[kind][3]
    if abs(pz - z) > 4.0:
        return False
    if kind == Swipe:
        return abs(py - y) < radius and abs(px - x) < SwipeReach
    return math.hypot(px - x, py - y) < radius


# --- The golf office (Arthur's idea, after the QA server screenshot of a
# toon golfing in a cubicle office: "Press Left or Right to aim. Press and
# hold Control to swing.") ---
# Past the boardroom, the Bossbots are carrying off the office's laff
# barrels. The toons tee off golf balls across a cubicle office at the cogs
# walking out with them: a cog that is hit drops its barrel back on the
# pile. Each barrel left at the end is laff for every toon.
SlideDuration = 150.0
GolfDuration = 60.0
# The slide's clock, then the golf's: GameDuration above is both.
GameDuration = SlideDuration + GolfDuration
# The office is a Sellbot maze quadrant (the same cubicles, filing
# cabinets, desks and paper as the QA screenshot, on a green checked
# floor), inside a cog building's office for its walls and ceiling.
GolfRoomModel = 'phase_7/models/modules/suit_interior'
GolfOfficeModel = 'phase_5/models/cogdominium/tt_m_ara_cmg_quadrant9'
# Taken out of the quadrant: the cubicle between the tees and the barrels,
# and the water cooler.
GolfOfficeRemove = ('**/maze6:*', '**/mazeGame:waterCooler')
# The golf office is away from the boardroom, out of its sight.
GolfOrigin = (0.0, 2400.0, 0.0)
GolfHalfX = 25.0
GolfHalfY = 25.0
# Where the toons tee off, in the doorway on the near side.
GolfTees = ((-4.5, -19.0), (-1.5, -19.0), (1.5, -19.0), (4.5, -19.0))
# Where the barrels are piled, and the doorways the cogs come in and go out
# by, to the left and the right.
BarrelPile = (0.0, 3.0)
CogDoorX = 27.0
CogExitX = 27.0
NumBarrels = 8
LaffPerBarrel = 3
GolfCogNames = ('f', 'p', 'ym', 'mm', 'ds', 'hh', 'cr')
GolfMaxCogsRange = (2, 4)
GolfSpawnPeriodRange = (5.0, 2.6)
GolfCogSpeedRange = (4.5, 6.5)
GolfPickupTime = 1.2
GolfCogRadius = 2.4
# The swing: Left/Right aims, holding Jump (Control) winds up, letting go
# swings; the longer the wind-up, the harder the hit.
AimSpeed = 75.0
ChargeTime = 1.1
BallSpeedRange = (14.0, 52.0)
BallFriction = 0.9
BallStopSpeed = 1.5
BallRadius = 0.45
SwingCooldown = 0.8


def golfCogPath(px, side, exitY, speed):
    """The legs of a golf cog's walk: in by the doorway on one side to the
    barrel pile, a moment to pick one up, then out by the other side's."""
    import math
    door = (-side * CogDoorX, -exitY * 0.5)
    pile = (BarrelPile[0] + px, BarrelPile[1] - 2.2)
    out = (side * CogExitX, exitY)
    t1 = math.hypot(pile[0] - door[0], pile[1] - door[1]) / speed
    t2 = t1 + GolfPickupTime
    t3 = t2 + math.hypot(out[0] - pile[0], out[1] - pile[1]) / speed
    return (door, pile, out, t1, t2, t3)


def golfCogPos(path, t):
    """Where a golf cog is t seconds into its walk, its heading, and which
    leg it is on (0 in, 1 picking up, 2 out, 3 gone)."""
    import math
    door, pile, out, t1, t2, t3 = path
    if t < t1:
        f = max(0.0, t) / t1 if t1 > 0 else 1.0
        a, b, leg = door, pile, 0
    elif t < t2:
        return pile[0], pile[1], 180.0, 1
    elif t < t3:
        f = (t - t2) / (t3 - t2)
        a, b, leg = pile, out, 2
    else:
        return out[0], out[1], 0.0, 3
    x = a[0] + (b[0] - a[0]) * f
    y = a[1] + (b[1] - a[1]) * f
    h = -math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
    return x, y, h, leg


def golfBlocked(x, y):
    """Whether the office is blocked at (x, y): a wall, a cubicle, a desk or
    a filing cabinet (see CogdoBoardroomGolfGrid)."""
    from toontown.cogdominium import CogdoBoardroomGolfGrid as Grid
    if not (-Grid.Half < x < Grid.Half and -Grid.Half < y < Grid.Half):
        return True
    row = int((Grid.Half - y) / Grid.Cell)
    col = int((x + Grid.Half) / Grid.Cell)
    return Grid.Rows[row][col] == '1'


def golfBallStep(x, y, vx, vy, dt):
    """One step of a rolling golf ball: off the office's walls, cubicles
    and furniture, slowed by the carpet. The AI runs the same steps for the
    NPC toons' balls."""
    import math
    speed = math.hypot(vx, vy)
    steps = max(1, int(speed * dt / 0.2) + 1)
    h = dt / steps
    for i in range(steps):
        nx, ny = x + vx * h, y + vy * h
        if golfBlocked(nx, ny):
            hitX = golfBlocked(nx, y)
            hitY = golfBlocked(x, ny)
            if hitX or not hitY:
                vx = -vx * 0.8
            if hitY or not hitX:
                vy = -vy * 0.8
            continue
        x, y = nx, ny
    k = max(0.0, 1.0 - BallFriction * dt)
    return x, y, vx * k, vy * k


def golfBallStart(x, y, h, power):
    """Where a swung ball starts and how fast it goes."""
    import math
    speed = BallSpeedRange[0] + (BallSpeedRange[1] - BallSpeedRange[0]) * power
    a = math.radians(h)
    vx, vy = -math.sin(a) * speed, math.cos(a) * speed
    return x + vx * 1.4 / max(speed, 1.0), y + vy * 1.4 / max(speed, 1.0), vx, vy
