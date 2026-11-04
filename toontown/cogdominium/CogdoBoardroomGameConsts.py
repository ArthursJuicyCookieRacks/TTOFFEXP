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
NumHalls = 8
HallLength = 333.7016
TableHalfWidth = 13.0
TableStart = 96.0
TableEnd = 366.0 + (NumHalls - 1) * HallLength
TableTop = 3.6
# How far above its chair locator a Boss Cog stands on the seat to swing.
ChairSeatLift = -0.03
# Every seated Boss Cog's head comes at least this far over the table top.
SeatedHeadClear = 1.6
# How far back into its chair a cog sits, from the CEO battle's sit place.
SitBack = 2.0
TableLegSpacing = 24.0
# The ramp up from the floor at the near end (the toons come in at the
# floor) and the drop down at the far end to the exit.
RampLength = 14.0
# Where the toons come in, and the way out: the hall's own entry corridor
# and the far wall, past the chairman's chair.
ElevatorPosHpr = (0, 46, 0, 180, 0, 0)
# The exit stands on the 2 ft step at the head of the room (it sat sunk in
# it, on the floor below).
ExitFloor = 2.05
ExitPosHpr = (0, 385 + (NumHalls - 1) * HallLength, ExitFloor, 0, 0, 0)
ExitRadius = 6.0
ChairmanPos = (0, TableEnd + 5.5, 0)

# --- Who is at the meeting ---
SeatSpacing = 22.0
SeatSideX = TableHalfWidth + 3.4
# Only the cogs this near the toon are shown (and move), for the frame
# rate on phones: the table is long.
ShowCogsWithin = 240.0
# Seats filled, per side, from the easiest office to the hardest.
# Per hall: the table is NumHalls halls long.
SeatsPerSideRange = (6 * NumHalls, 9 * NumHalls)
MinionsRange = (3 * NumHalls, 5 * NumHalls)
OilCansRange = (3 * NumHalls, 5 * NumHalls)
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
# Running into a pile or a pencil.
Obstacle = 7
Hazards = {
    # A Boss Cog's golf club swung across the table's edge as a toon
    # slides by its chair (a strip, not a circle: see SwipeReach).
    Swipe: (2, 6, 2, 3.5),
    GolfBall: (2, 5, 1, 2.6),
    Obstacle: (1, 4, 1, 0.0),
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
BossAttackPeriodRange = (1.3, 0.55)
MinionDropPeriodRange = (1.8, 0.7)
OilSpillPeriodRange = (8.0, 4.5)
# How likely a second cog throws at the same time (easiest, hardest).
VolleyChanceRange = (0.15, 0.6)
# Throws land this far ahead of the toon they aim at (the toons run up the
# table), give or take.
AttackLead = 24.0
AttackSpread = 5.0
# How far off a Boss Cog's aimed throw lands from where the toon will be
# when it comes down (easiest, hardest): they lead the toon by its speed.
AimSpreadRange = (2.2, 0.9)
# A Boss Cog can throw a jug of oil down onto the table ahead of a toon:
# it spills a slick there (a smaller one than a knocked-over drum's).
ThrownSlickRadius = 4.5
ThrownSlickDuration = 10.0
OilThrowChanceRange = (0.15, 0.3)

# The swing at a toon sliding past a Boss Cog's chair: it reaches this far
# in over the table, this long after the warning.
SwipeReach = 8.0
SwipeTime = 0.8

# --- Sliding ---
# The toons don't walk the table: they belly-slide down it, steering left
# and right (in the air too) and hopping over what's in the way. Forward
# slides faster, back slower. Each toon sets off a moment after the last,
# so they don't all pile into each other.
SlideSpeed = 19.5
SlideFastSpeed = 27.0
SlideSlowSpeed = 11.5
SlideAccel = 16.0
SteerSpeed = 15.0
# The slide pose: flat on its belly this far above the table.
SlideBodyZ = 0.55
# The camera's field of view on the slide, and how much wider it gets at
# full speed (the elevator ride leaves the view narrower than the game's).
SlideFov = 62.0
SlideFovBoost = 8.0
# Off the far end: each toon jumps down to the floor beside the chairman's
# chair, this far out to a side, then runs out past it.
JumpOffAt = 3.0
JumpOffX = 10.0
JumpOffTime = 1.0
JumpOffHeight = 5
# The jump-off camera: up and back over the table, off to the other side
# from the one the toon jumps to (the end of the hall is narrow), so the
# whole leap down beside the chairman shows; held this long after landing.
JumpCamSide = -7.0
JumpCamBack = 15.0
JumpCamUp = 9.0
JumpCamHold = 1.8
StartStagger = 1.5
StartDelay = 1.0
# A ramp throws a toon sliding up it into the air.
LaunchForce = 30.0
# Sliding into a pile or a pencil stops a toon and spins it round.
CrashTime = 1.6
# How far an obstacle knocks the toon back.
CrashBounce = 1.4
# The belly slide's pose: the slip-and-fall's frame lying flat on the
# table, dived into over DiveTime with a little hop; the arms paddle at
# PaddleRate (at cruising speed, and flat out).
SlideLieFrame = 20
DiveTime = 0.35
# The belly slide's stroke (see DistCogdoBoardroomGame._slidePose): how far
# the chest is lifted, how much of the swimming stroke is mixed in, and how
# far the toon rides above the cloth, so the hands never go into the table.
SlideChestUp = 18.0
SlideStroke = 0.6
SlideLift = 0.15
DiveHop = 0.9
PaddleRate = (1.0, 1.7)
SpinTime = 0.8
CameraBack = 12.0
CameraUp = 7.0

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
SegmentLength = 26.0
# The narrowest lane left through any row of obstacles.
FairGap = 7.5
ClearStart = 10.0
ClearEnd = 24.0
MemosPerSegment = (2, 4)
# How likely a stretch gets a second obstacle (easiest, hardest).
DoubleObstacleRange = (0.15, 0.5)
PileHeight = (5.0, 7.5)
PencilHeight = 1.25
NumInvulnerable = 2 * NumHalls
NumHop = 2 * NumHalls

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
SlideDuration = 255.0
GolfDuration = 120.0
# The slide's clock, then the golf's: GameDuration above is both.
GameDuration = SlideDuration + GolfDuration
# The office is a Sellbot maze quadrant (the same cubicles, filing
# cabinets, desks and paper as the QA screenshot, on a green checked
# floor), inside a cog building's office for its walls and ceiling.
GolfWallModel = 'phase_5/models/cogdominium/tt_m_ara_cmg_level'
GolfWallScale = 0.8
GolfOfficeModel = 'phase_5/models/cogdominium/tt_m_ara_cmg_quadrant9'
GolfQuadrantModel = 'phase_5/models/cogdominium/tt_m_ara_cmg_quadrant%d'
# The office is a big one: an aisle up the middle from the toons' tee lane
# to the front elevator, an aisle across it between the left and right
# elevators, the barrels piled where the two cross, and in each of the
# four blocks between, cubicles, filing cabinets and desks borrowed from
# the Sellbot maze office. (quadrant, grouping, x offset, y offset.)
GolfPieces = (
    # The far left block, and its cubicles.
    (9, 'maze2:grouping2', -32.0, 14.0), (3, 'maze3:grouping3', -16.0, 22.0),
    # The far right block.
    (9, 'maze1:grouping1', 32.0, 14.0), (6, 'maze2:grouping2', 4.0, 20.0),
    # The near left block, with the VP's desk.
    (9, 'maze5:grouping5', -32.0, -14.0), (8, 'maze3:grouping3a', -16.0, -38.0), (9, 'maze3:grouping3', -28.0, -16.0),
    # The near right block.
    (9, 'maze4:grouping4', 32.0, -14.0), (3, 'maze8:grouping8', 14.0, -20.0), (9, 'maze6:grouping6', 22.0, 4.0),
)
# Where the VP's name plate goes: on the desk of the third near-left piece.
GolfNamePlate = (-28.0 + 1.9, -16.0 + 6.1, 4.3)
# Low cubicle partitions (x0, y0, x1, y1) along the aisles: a short
# stretch either side of the tee lane, and one solid run (no gaps, which
# read as holes in the wall) along each edge of the aisle across, with an
# L round the far corners. Their height stays; they're short end to end
# to leave room to putt at the cogs. The balls bank off them.
GolfPartitionHeight = 3.0
# (The two front ones, across the aisle in front of the barrels, are
# gone: Arthur.)
GolfPartitions = ((-9.6, -39.5, -9.0, -31.0), (9.0, -39.5, 9.6, -31.0),
                  (-21.0, 14.0, -10.0, 14.6), (10.0, 14.0, 21.0, 14.6),
                  (-10.6, 14.0, -10.0, 22.0), (10.0, 14.0, 10.6, 22.0))
# The office is lit brighter than the maze, as in the screenshot.
GolfOfficeBrightness = (1.25, 1.25, 1.25, 1)
# The golf office is away from the boardroom, out of its sight.
GolfOrigin = (0.0, 2400.0, 0.0)
GolfHalfX = 58.0
GolfHalfY = 40.0
# Where the toons tee off, at the near end of the tee lane.
GolfTees = ((-9.0, -26.0), (-3.0, -26.0), (3.0, -26.0), (9.0, -26.0))
# The elevator the toons ride in by, in the back wall behind the tees
# (x, y of its doors, heading): the same cog building elevator as the
# boardroom's exit, with the camera inside it for the ride as between the
# other field offices' floors.
GolfToonElevator = (0.0, -GolfHalfY, 180.0)
# The ride from the boardroom: the doors close on the toons, the elevator
# rides, its doors open on the golf office, the toons come out to the
# tees, and the golf office's intro tells them what to do. Then the golf.
GolfDoorTime = 2.0
GolfRideTime = 4.5
GolfWalkOutTime = 1.8
GolfIntroDuration = 20.0
GolfLeadIn = 2 * GolfDoorTime + GolfRideTime + GolfWalkOutTime + GolfIntroDuration
# The golf camera, as at the CEO battle's golf spots: straight behind the
# ball down the line of the shot, turning with the aim (there 10 ft back
# and 3 up, looking level). A little further back and up here, looking a
# touch down, so the cubicle partitions don't hide the floor past them.
GolfCamBack = 13.0
GolfCamUp = 7.5
GolfCamLook = 30.0
GolfCamLookUp = 0.0
# After the golf, the toons walk into their elevator; the ride goes on
# without anyone who hasn't in this long.
GolfLeaveTime = 40.0
# The countdown over the way out's doors (pos, hpr, scale on the elevator).
GolfExitClock = (0, -0.4, 10.0, 0, 0, 0, 2.0, 2.0, 2.0)
# Where the barrels are piled: where the aisles cross.
BarrelPile = (0.0, 6.0)
# The three elevators the cogs come and go by: in the front wall and the
# left and right walls, each built out from its wall in a boxed-in shaft.
# (x, y, heading of its doors' front.) A cog comes out of one, takes a
# barrel and leaves by another.
GolfElevatorDepth = 6.2
GolfElevators = ((0.0, GolfHalfY - GolfElevatorDepth, 0.0),
                 (-GolfHalfX + GolfElevatorDepth, BarrelPile[1], 90.0),
                 (GolfHalfX - GolfElevatorDepth, BarrelPile[1], -90.0))
# Where a cog stands just out of each elevator's doors.
GolfElevatorStep = 2.5
NumBarrels = 10
LaffPerBarrel = 3
GolfCogNames = ('f', 'p', 'ym', 'mm', 'ds', 'hh', 'cr')
GolfMaxCogsRange = (6, 12)
GolfSpawnPeriodRange = (1.8, 0.7)
GolfCogSpeedRange = (5.5, 8.5)
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


def golfElevatorDoor(index):
    """Where a cog steps out of (or into) elevator `index`."""
    import math
    x, y, h = GolfElevators[index]
    a = math.radians(h)
    # An elevator's doors face its -y; turned by h.
    fx, fy = math.sin(a), -math.cos(a)
    return x + fx * GolfElevatorStep, y + fy * GolfElevatorStep


def golfCogRoute(side):
    """The elevators a cog comes out of and leaves by, from the `side`
    sent with it: in * 4 + out."""
    side = int(side)
    return (side // 4) % len(GolfElevators), (side % 4) % len(GolfElevators)


def golfCogPath(px, side, exitY, speed, target=None):
    """The legs of a golf cog's walk: out of its elevator to the barrel
    pile (to the side of the pile it comes from, px along it), or to a
    barrel lying on the floor (target), a moment to pick one up, then away
    into another elevator."""
    import math
    entry, exit = golfCogRoute(side)
    door = golfElevatorDoor(entry)
    out = golfElevatorDoor(exit)
    dx, dy = door[0] - BarrelPile[0], door[1] - BarrelPile[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    if target is not None:
        # Stop just short of the barrel, on the side it walks up from.
        tx, ty = target
        ddx, ddy = door[0] - tx, door[1] - ty
        dd = math.hypot(ddx, ddy) or 1.0
        pile = (tx + ddx / dd * 1.2, ty + ddy / dd * 1.2)
    else:
        pile = (BarrelPile[0] + ux * 3.2 - uy * px, BarrelPile[1] + uy * 3.2 + ux * px)
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
    if not (-Grid.HalfX < x < Grid.HalfX and -Grid.HalfY < y < Grid.HalfY):
        return True
    if abs(x) > GolfHalfX or abs(y) > GolfHalfY:
        return True
    for ex, ey, eh in GolfElevators:
        # Each elevator's shaft, boxed out from its wall.
        if eh == 0.0 and abs(x - ex) < 9.4 and y > ey - 0.3:
            return True
        if eh != 0.0 and abs(y - ey) < 9.4 and abs(x) > abs(ex) - 0.3:
            return True
    row = int((Grid.HalfY - y) / Grid.Cell)
    col = int((x + Grid.HalfX) / Grid.Cell)
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
