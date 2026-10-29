"""The numbers behind Survival Mode.

A parody of Black Ops 1 zombies played in Toontown Central after dark: cogs
fall from the sky in rounds, gags are the weapons, jellybeans are the
points. The round, health and spawn rules follow BO1 (see
study/survival-design.md in the project files); the gag table scales the
game's own gag damage by five, which puts a Cupcake where BO1's starting
pistol is and an Opera Singer where its Thunder Gun is.
"""

from toontown.toonbase import ToontownBattleGlobals

# --- Players ---
PLAYER_HP = 100
TONIC_HP = 250
# A cog's hit, its reach and the time between its swings.
COG_HIT = 50
COG_REACH = 3.8
COG_SWING_TIME = 1.1
# Health comes back after a moment out of the cogs' reach.
REGEN_DELAY = 3.0
REGEN_DELAY_LOW = 5.0
REGEN_RATE = 25.0
LOW_HP = 30
# Walking, sprinting (and the sprint stamina in seconds) and jumping.
WALK_SPEED = 16.0
SPRINT_SPEED = 22.0
SPRINT_TIME = 4.0
SPRINT_RECOVER = 6.0
JUMP_FORCE = 24.0
EYE_HEIGHT = 3.6
# Downed: a teammate's revive takes this long (hold); bleed out ends it.
REVIVE_TIME = 4.0
BLEED_OUT = 45.0
SECOND_WIND_DELAY = 8.0
START_BEANS = 500

# --- Rounds (BO1: 150 HP +100/round to 9, then x1.1; counts by the
# player share and round multiplier; 2 s spawn gap x0.95 a round) ---
INTERMISSION = 10.0


def cogHp(roundNum):
    if roundNum <= 9:
        return 150 + 100 * (roundNum - 1)
    return int(950 * 1.1 ** (roundNum - 9))


def cogsInRound(roundNum, npcs):
    early = (6, 8, 13, 18, 24)
    if roundNum <= len(early):
        return early[roundNum - 1] + 2 * npcs
    share = 0.5 if npcs == 0 else npcs
    mult = max(1.0, roundNum / 5.0)
    if roundNum >= 10:
        mult *= roundNum * 0.15
    return 24 + int(6 * share * mult)


def aliveCap(roundNum, npcs):
    # Arthur's: 8 at the start rising to 26, a few more with helpers.
    return min(26, 8 + 2 * (roundNum - 1)) + 2 * npcs


def spawnDelay(roundNum):
    return max(0.25, 2.0 * 0.95 ** (roundNum - 1))


# Cog speed classes (walk / jog / sprint) rolled per cog as BO1 does.
COG_SPEEDS = (6.0, 10.0, 14.0)


def cogSpeedClass(roundNum, roll):
    """roll in [0, 1): 0 walk, 1 jog, 2 sprint."""
    speed = 1 if roundNum == 1 else roundNum * 8
    score = speed + roll * 35
    if roundNum >= 9:
        return 2
    if score <= 35:
        return 0
    if score <= 70 or roundNum < 5:
        return 1
    return 2


# The cogs that fall in, by round: looks only, the HP is the formula.
COG_LOOKS = (
    (1, ('f', 'p', 'bf', 'b', 'sc', 'pp', 'cc', 'tm')),
    (4, ('ym', 'mm', 'dt', 'ac', 'pp', 'tw', 'nd', 'gh')),
    (8, ('ds', 'hh', 'bs', 'sd', 'bc', 'nc', 'ms', 'tf')),
    (13, ('cr', 'tbc', 'le', 'bw', 'mb', 'ls', 'm', 'mh')),
)

# --- Jellybeans (BO1 points) ---
BEANS_HIT = 10
BEANS_KILL = 50
BEANS_HEAD_KILL = 100
BEANS_BONK_KILL = 130
BEANS_TOONADO = 400
DOWN_LOSS = 0.05

# --- Melee ---
BONK_DAMAGE = 100
BONK_REACH = 5.0
BONK_TIME = 1.2

# --- Stations ---
TRUNK_COST = 950
TRUNK_SALE_COST = 10
TRUNK_CYCLE = 4.0
TRUNK_OFFER = 10.0
TRUNK_REUSE = 3.0
# The Doodle (BO1's teddy bear): never in the first 3 goes, then the odds
# climb; the trunk shuts for a while and the beans come back.
DOODLE_ODDS = ((3, 0.0), (7, 0.15), (12, 0.3), (999, 0.5))
DOODLE_SHUT = 30.0
MICKEY_COST = 5000
MICKEY_TIME = 5.0
UPGRADE_MULT = {1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3, 7: 5}

TONICS = (
    # key, name, cost, blurb
    ('toonup', 'Toon-Up Tonic', 2500, 'Laff to 250. Takes five cog hits to go sad.'),
    ('seltzer', 'Speedy Seltzer', 3000, 'Reload gags twice as fast.'),
    ('wind', 'Second Wind', 500, 'Go sad and get back up after 8 seconds. Costs your other tonics. Three a game.'),
    ('sprint', 'Sprint Soda', 2000, 'Sprint faster and twice as long.'),
)
TONIC_LIMIT = 4
SECOND_WIND_BUYS = 3

# --- Power-ups (BO1: ~3 % a kill, 4 a round, 26 s on the ground) ---
DROP_CHANCE = 0.03
DROP_CHANCE_STEP = 0.03
DROPS_PER_ROUND = 4
DROP_LIFE = 26.0
DROP_BLINK = 6.0
POWER_TIME = 30.0
POWERUPS = ('maxgags', 'instapop', 'toonado', 'doublebeans', 'trunksale')
POWERUP_NAMES = {'maxgags': 'Max Gags', 'instapop': 'Insta-Pop', 'toonado': 'Toonado',
                 'doublebeans': 'Double Beans', 'trunksale': 'Trunk Sale'}

# --- Gags ---
THROW = ToontownBattleGlobals.THROW_TRACK
SQUIRT = ToontownBattleGlobals.SQUIRT_TRACK
SOUND = ToontownBattleGlobals.SOUND_TRACK
DROP = ToontownBattleGlobals.DROP_TRACK
LURE = ToontownBattleGlobals.LURE_TRACK

# (track, level): damage, clip, reserve, seconds between shots, splash
# radius (0 = one cog; sound: the cone's reach), prop name.
GAGS = {
    (THROW, 0): (30, 16, 48, 0.45, 0, 'tart'),
    (THROW, 1): (50, 16, 64, 0.4, 0, 'fruitpie-slice'),
    (THROW, 2): (85, 10, 60, 0.5, 2, 'fruitpie'),
    (THROW, 3): (135, 12, 72, 0.4, 0, 'creampie-slice'),
    (THROW, 4): (200, 8, 48, 0.55, 2.5, 'creampie'),
    (THROW, 5): (500, 4, 32, 0.8, 4, 'birthday-cake'),
    (THROW, 6): (600, 3, 24, 0.9, 6, 'wedding-cake'),
    (SQUIRT, 0): (20, 30, 120, 0.12, 0, 'squirting-flower'),
    (SQUIRT, 1): (40, 30, 150, 0.12, 0, 'glass'),
    (SQUIRT, 2): (60, 40, 200, 0.1, 0, 'water-gun'),
    (SQUIRT, 3): (105, 35, 210, 0.1, 0, 'bottle'),
    (SQUIRT, 4): (150, 50, 250, 0.08, 0, 'firehose'),
    (SQUIRT, 5): (400, 6, 36, 0.7, 5, 'stormcloud'),
    (SQUIRT, 6): (525, 2, 16, 1.0, 7, 'geyser'),
    (SOUND, 0): (20, 8, 40, 0.5, 10, 'bikehorn'),
    (SOUND, 1): (35, 8, 40, 0.5, 12, 'whistle'),
    (SOUND, 2): (55, 6, 36, 0.6, 14, 'bugle'),
    (SOUND, 3): (80, 6, 36, 0.6, 15, 'aoogah'),
    (SOUND, 4): (105, 5, 30, 0.7, 16, 'elephant'),
    (SOUND, 5): (250, 4, 24, 0.9, 18, 'fog_horn'),
    (SOUND, 6): (450, 4, 12, 1.5, 22, 'singing'),
    (DROP, 0): (50, 6, 36, 0.6, 2, 'flowerpot'),
    (DROP, 1): (90, 6, 36, 0.6, 2.5, 'sandbag'),
    (DROP, 2): (150, 5, 30, 0.7, 3, 'anvil'),
    (DROP, 3): (225, 4, 28, 0.8, 3.5, 'weight'),
    (DROP, 4): (300, 3, 24, 0.9, 4, 'safe'),
    (DROP, 5): (850, 2, 16, 1.2, 5, 'piano'),
    (DROP, 6): (900, 1, 36, 1.5, 9, 'ship'),
}
# What the trunk hands out: every gag but the level 7s, no Toon-Up, no
# Trap, Lure only as the Presentation.
TRUNK_GAGS = [key for key in GAGS if key[1] < 6]
PRESENTATION = (LURE, 6)
PRESENTATION_LURE = 15.0
PRESENTATION_RANGE = 40.0
PRESENTATION_DAMAGE = 500
PRESENTATION_POP = 8.0
STARTING_GAG = (THROW, 0)
GAG_SLOTS = 2
RELOAD_TIME = 1.8
# Throw and Squirt fly this fast; Drop gags fall onto the aim point.
PROJECTILE_SPEED = 60.0
DROP_FALL = 0.4
MAX_RANGE = 90.0


def npcDamage(roundNum):
    """An NPC teammate's throw: about six hits a cog, so they help
    without carrying the game."""
    return max(30, cogHp(roundNum) // 6)


def gagName(track, level):
    return ToontownBattleGlobals.AvPropStrings[track][level]


def gagDamage(track, level, upgraded):
    damage = GAGS[(track, level)][0]
    if upgraded:
        damage *= UPGRADE_MULT[level + 1]
    return damage
