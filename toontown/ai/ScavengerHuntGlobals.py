from toontown.toonbase import ToontownGlobals

# The shops of each scavenger hunt, by goal number. Toons say the hunt's
# SpeedChat phrase in each shop once a year for a jellybean reward, and get
# the hunt's cheesy effect for finding them all.
TrickOrTreatGoals = {
    0: 2649,  # All Fun and Games Shop
    1: 1834,  # Rudderly Ridiculous!
    2: 4835,  # Ursatz for Kool Katz
    3: 5620,  # Rake It Inn
    4: 3707,  # Snowplace Like Home
    5: 9619,  # Relax to the Max
}

WinterCarolingGoals = {
    0: 2659,  # Joy Buzzers to the World
    1: 1707,  # Gifts With a Porpoise
    2: 5626,  # Pine Needle Crafts
    3: 4614,  # Shave and a Haircut for a Song
    4: 3828,  # Snowman's Land
    5: 9720,  # Talking In Your Sleep Voice Training
}

# holidayId: (goals, reward cheesy effect)
Hunts = {
    ToontownGlobals.TRICK_OR_TREAT: (TrickOrTreatGoals, ToontownGlobals.CEPumpkin),
    ToontownGlobals.WINTER_CAROLING: (WinterCarolingGoals, ToontownGlobals.CESnowMan),
}

BeanReward = ToontownGlobals.TOT_REWARD_JELLYBEAN_AMOUNT


def encodeGoal(holidayId, year, goal):
    # A found goal as stored on the toon.
    return holidayId * 1000000 + year * 100 + goal


def decodeGoal(code):
    return code // 1000000, code // 100 % 10000, code % 100
