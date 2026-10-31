import math

from panda3d.core import Point3
from otp.level.EntityStateVarSet import EntityStateVarSet
from toontown.cogdominium.CogdoEntityTypes import CogdoCraneGameSettings, CogdoCraneCogSettings
from toontown.toonbase import ToontownGlobals

# The Vend-A-Stomper: the Cashbot field office game. The original game's
# notes for it: "The COGS are using a coin-operated machine to destroy laff
# barrels. Use the cranes to pick up and throw money bags, in order to
# prevent barrel destruction!" Its settings, as the original level spec
# had them, are below; the room is laid out around the machine in the
# middle of tt_m_ara_ccg_level.
Settings = EntityStateVarSet(CogdoCraneGameSettings)
CogSettings = EntityStateVarSet(CogdoCraneCogSettings)

GameDuration = 180.0
Gravity = -32
EmptyFrictionCoef = 0.1
RopeLinkMass = 1.0
MagnetMass = 1.0
MoneyBagGrabHeight = -4.1

# --- The room ---

RoomSeed = 6000
RoomHalfSize = (76.5, 76.5)
# The open floor in the middle, and the pockets in front of the elevator
# the toons come up in and the exit door: (x, y, half width, half depth).
PlayHalfSize = (50.0, 50.0)
Pockets = ((0, -66, 15, 12), (0, 66, 15, 12))
CeilingHeight = 51.0
# How tall the piles grow, by how far a cell is from the open floor.
PileHeights = (8.0, 15.0, 22.0, 30.0, 38.0, 42.0)
# Under the laff barrel belt on the left wall the piles stay low.
BeltSideX = -50.0
BeltSideMaxHeight = 24.0
WallColor = (0.86, 0.5, 0.5)
FloorColorScale = (1.25, 1.22, 1.22, 1)
ElevatorPosHpr = (0, -74.5, 0, 0, 0, 0)
ExitPosHpr = (0, 74.5, 0, 180, 0, 0)
StomperModel = 'phase_5/models/cogdominium/ttoff_m_ara_ccg_stompOMatic'
HangingMagnets = (Point3(-30, 64, 40), Point3(-10, 68, 37), Point3(26, 64, 39),
                  Point3(66, 22, 41), Point3(64, -30, 38))

# --- The cogs ---

# The hallways run corner to corner; the cogs walk out of a door at the
# far end and along a lit lane to the machine. Headings: 0 is +y.
LaneAngles = (45, 135, 225, 315)
LaneWidth = 9.0
HallwayHalfWidth = 7.0
HallwayDistance = 84.0
MachineDistance = 5.2
PoolRadius = 24.0


def lanePoint(angle, distance):
    rad = math.radians(angle)
    return Point3(-math.sin(rad) * distance, math.cos(rad) * distance, 0)


# Cogs walk at the pace of a cog on a street.
CogWalkSpeed = ToontownGlobals.SuitWalkSpeed
CogInsertDuration = 2.5
CogFlyAwayDuration = 4.0
CogFlyAwayHeight = 50.0
CogStunDuration = 4.5
# How close a money bag has to come to a cog to knock it out of line.
CogHitRadius = 4.2
CogHitHeight = 7.5

# By difficulty (0 for a Toontown Central field office, up to 1 for
# Donald's Dreamland): seconds between cogs, how many walk at once, and
# how many coins fill the machine.
SpawnPeriodRange = (9.0, 4.5)
MaxCogsRange = (3, 6)
CoinsPerStomp = 3
NumBarrels = 7
# The toons share this much laff for each barrel still whole at the end.
LaffPerBarrel = 3


def lerpDifficulty(range, difficulty):
    return range[0] + (range[1] - range[0]) * max(0.0, min(1.0, difficulty))


# --- The cranes and money bags ---

# The cranes: one on each side of the machine, between two lanes, all
# four facing it. Each crane's arm swings from a hinge behind its controls
# and reaches the stretch of both lanes either side of it (from about 11 to
# 33 out), so every lane has two cranes on it. The arm turns a long way
# either side, and the crane camera turns with it.
CraneDistance = 14.0
CraneHingeY = -17.6
CraneMaxH = 110
CraneHeadings = (0, 90, 180, 270)
CranePosHprs = []
for _h in CraneHeadings:
    # Out from the machine opposite the way the crane faces.
    _p = lanePoint(_h, -CraneDistance)
    CranePosHprs.append((_p[0], _p[1], 0, _h, 0, 0))


def craneLocal(index, x, y):
    # A spot on the floor in a crane's own space (+y is ahead of it).
    cx, cy, cz, h, p, r = CranePosHprs[index]
    rad = math.radians(h)
    dx, dy = x - cx, y - cy
    return (dx * math.cos(rad) + dy * math.sin(rad), -dx * math.sin(rad) + dy * math.cos(rad))


def craneWorld(index, lx, ly):
    cx, cy, cz, h, p, r = CranePosHprs[index]
    rad = math.radians(h)
    return (cx + lx * math.cos(rad) - ly * math.sin(rad), cy + lx * math.sin(rad) + ly * math.cos(rad))


def craneAim(index, x, y):
    # The arm's heading and the trolley's distance along it that put the
    # magnet over (x, y), unclamped.
    lx, ly = craneLocal(index, x, y)
    dy = ly - CraneHingeY
    return math.degrees(math.atan2(-lx, dy)), math.hypot(lx, dy)


def inCraneReach(index, x, y, slack=0.0):
    h, d = craneAim(index, x, y)
    return abs(h) <= CraneMaxH + slack * 2 and CraneMinY - slack <= d <= CraneMaxY + slack


# Two money bags lie beside each crane, either side of its controls.
MoneyBagPosHprs = []
for _i in range(len(CranePosHprs)):
    for _s in (-1, 1):
        _x, _y = craneWorld(_i, 7 * _s, -3)
        MoneyBagPosHprs.append([_x, _y, 0, CranePosHprs[_i][3] + 90 * _s, 0, 0])
BagReturnDelay = 3.0
CraneMinY = 8
CraneMaxY = 25
