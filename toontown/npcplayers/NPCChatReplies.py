"""What an NPC toon says back when the player talks to it.

Offline the NPC toons only ever said things on their own (greetings and
cheers, see NPCPlayerManagerAI.idleAction). Arthur asked that they answer
the player too: a whisper, or anything said aloud while the player looks at
a toon, gets a SpeedChat phrase back that fits what was said. Something mean
gets "You stink!", a hello gets a hello, thanks get "You're welcome!", and
so on.

The player's words are sorted into a kind by keywords (typed chat and
SpeedChat both arrive here as text). Each kind has phrases to answer with,
weighted, and sometimes an emote.
"""

import random
import re

# SpeedChat phrases (OTPLocalizer.SpeedChatStaticText) used as answers.
YES, NO, OK = 1, 2, 3
HI, HEYA, HELLO, HOWDY, HI_THERE = 100, 101, 102, 103, 104
BYE, LATER, SEE_YA, HAVE_FUN, GOOD_LUCK, NICE_DAY = 200, 201, 202, 203, 204, 205
YAY, HOORAY, YIPPEE, WOO_HOO, WOW, COOL, SWEET, OH_BOY, HEH, HAHA, HEE_HEE = \
    300, 302, 303, 304, 306, 307, 308, 309, 310, 311, 312
UH_OH, OH_NO, YIKES = 400, 401, 402
THANKS, NO_THANKS, ANY_TIME, NO_PROBLEM, WELCOME = 500, 501, 502, 503, 504
THAT_WAS_FUN, GOOD_TEAMWORK, LETS_WORK_TOGETHER = 505, 506, 508
YOU_ROCK, YOU_ARE_AWESOME, GREAT_FRIEND = 600, 601, 603
LIKE_YOUR_NAME, LIKE_YOUR_STYLE = 700, 701
SORRY, SORRY_CANT, WHAT_DID_YOU_SAY = 800, 801, 807
HEY, YOU_STINK, STOP_THAT, GO_AWAY, DONT_BE_MEAN, NOT_NICE = 900, 901, 902, 903, 904, 905
LETS_GO, FOLLOW_ME, WHICH_WAY, WHERE_TO = 1000, 1003, 1004, 1006
WORK_ON_THAT = 1201
WE_CAN_DO_THIS, YOU_DID_IT, WE_DID_IT = 1400, 1401, 1402
BRING_IT_ON, PIECE_OF_CAKE = 1522, 1526
ONE_MORE, LIKE_THIS_GAME = 1600, 1603

# Emotes (OTPLocalizer.EmoteFuncDict).
WAVE, HAPPY, SAD, ANGRY, SHRUG, THINK, CONFUSED, BOW, LAUGH, E_YES, E_NO, DELIGHTED = \
    0, 1, 2, 3, 5, 7, 11, 13, 16, 17, 18, 22


def _words(*words):
    """A pattern matching any of these words or phrases on word edges."""
    return re.compile(r"(?<![a-z])(?:%s)(?![a-z])" % '|'.join(words))


# The kinds of things the player says, checked in this order (the first
# that matches wins), each with:
#   pattern, [(phrase, weight)], emote or None, whether a whisper of this
#   kind still calls the toon over to help.
KINDS = (
    ('mean', _words(
        r"you stink", r"stinks?", r"stinky", r"smelly", r"you smell", r"stupid", r"dumb", r"idiot", r"moron",
        r"ugly", r"loser", r"noob", r"n00b", r"trash", r"garbage", r"lame", r"you suck", r"u suck",
        r"hate you", r"hate u", r"shut up", r"go away", r"get lost", r"buzz off", r"leave me alone", r"weirdo", r"jerk",
        r"meanie", r"dork", r"nerd", r"brat", r"you'?re annoying", r"bad toon",
        r"stop that", r"don'?t be mean", r"that wasn'?t nice", r"go to the cogs", r"you'?re a cog",
        r"cog lover", r"scram", r"booger", r"poop", r"butt", r"you'?re mean", r"you are mean"),
     ((YOU_STINK, 10), (DONT_BE_MEAN, 3), (NOT_NICE, 2), (STOP_THAT, 1), (GO_AWAY, 1), (HEY, 1)),
     ANGRY, False),
    ('sorry', _words(r"sorry", r"my bad", r"oops", r"apolog\w*", r"didn'?t mean"),
     ((NO_PROBLEM, 4), (OK, 3), (ANY_TIME, 1)),
     None, True),
    ('thanks', _words(r"thanks?", r"thank you", r"thx", r"ty", r"tysm", r"appreciate it"),
     ((WELCOME, 5), (ANY_TIME, 3), (NO_PROBLEM, 3)),
     BOW, True),
    ('friends', _words(r"be friends", r"best friends?", r"bff", r"want to be friends", r"friend me",
                       r"add me", r"you'?re my friend", r"be my friend", r"great friend"),
     ((YES, 4), (GREAT_FRIEND, 3), (YAY, 2)),
     DELIGHTED, True),
    ('help', _words(r"help", r"help me", r"can you help", r"need help", r"come here", r"come help",
                    r"teleport", r"tp", r"over here", r"save me", r"we are in trouble", r"hurry"),
     ((OK, 4), (LETS_GO, 3), (WE_CAN_DO_THIS, 2), (YES, 2)),
     None, True),
    ('bye', _words(r"bye", r"goodbye", r"good bye", r"bye bye", r"later", r"see ya", r"see you",
                   r"cya", r"gtg", r"g2g", r"got to go", r"gotta go", r"need to go", r"good night",
                   r"goodnight", r"have fun", r"have a nice day", r"i'?ll be back"),
     ((BYE, 4), (SEE_YA, 3), (LATER, 2), (HAVE_FUN, 2), (NICE_DAY, 1)),
     WAVE, False),
    ('compliment', _words(
        r"you rock", r"you'?re awesome", r"you are awesome", r"you'?re cool", r"you are cool",
        r"you'?re great", r"you are great", r"you'?re a genius", r"genius", r"nice toon", r"cute",
        r"pretty", r"i like your \w+", r"love your \w+", r"nice (?:hat|shirt|shoes|glasses|outfit|name)",
        r"cool (?:hat|shirt|shoes|glasses|outfit|name)", r"you'?re nice", r"you are nice",
        r"you'?re funny", r"good job", r"great job", r"well done", r"nice job", r"you did it",
        r"good teamwork", r"you guys are great", r"amazing", r"best toon", r"love you", r"ily"),
     ((THANKS, 6), (YOU_ROCK, 2), (YOU_ARE_AWESOME, 2), (LIKE_YOUR_STYLE, 1), (WE_DID_IT, 1)),
     HAPPY, True),
    ('hello', _words(r"hi", r"hii+", r"hiya", r"hey", r"heya", r"hello", r"helo", r"howdy", r"yo",
                     r"sup", r"wassup", r"what'?s up", r"greetings", r"hi there", r"hey there",
                     r"good morning", r"good afternoon", r"good evening", r"welcome"),
     ((HI, 3), (HEYA, 2), (HELLO, 3), (HOWDY, 2), (HI_THERE, 2)),
     WAVE, True),
    ('howareyou', _words(r"how are you", r"how r u", r"how'?s it going", r"how are things",
                         r"how do you do", r"you ok", r"you okay", r"are you ok"),
     ((YAY, 2), (COOL, 2), (OH_BOY, 1), (WOO_HOO, 1), (OK, 2)),
     HAPPY, True),
    ('lets', _words(r"let'?s go", r"lets go", r"let'?s battle", r"let'?s fight", r"let'?s play",
                    r"let'?s work", r"follow me", r"this way", r"come on", r"come with me", r"shall we go",
                    r"let'?s", r"lets", r"want to play", r"wanna play", r"race", r"fishing",
                    r"golf", r"trolley", r"elevator", r"building", r"factory", r"mint", r"vp", r"cfo",
                    r"cj", r"ceo", r"toontask", r"task"),
     ((LETS_GO, 4), (OK, 3), (YES, 2), (LETS_WORK_TOGETHER, 1), (BRING_IT_ON, 1)),
     None, True),
    ('laugh', _words(r"lol", r"lmao", r"rofl", r"haha\w*", r"hehe\w*", r"hah", r"heh", r"funny", r"xd"),
     ((HAHA, 4), (HEE_HEE, 3), (HEH, 2)),
     LAUGH, True),
    ('happy', _words(r"yay", r"yippee", r"hooray", r"woo+", r"woo hoo", r"wow", r"cool", r"sweet",
                     r"awesome", r"nice", r"great", r"oh boy", r"yee hah", r"we did it", r"that was fun",
                     r"fun", r"i won", r"we won", r"bring it on", r"easy", r"piece of cake"),
     ((YAY, 2), (HOORAY, 2), (WOO_HOO, 2), (WOW, 1), (COOL, 2), (SWEET, 1), (YIPPEE, 1)),
     DELIGHTED, True),
    ('sad', _words(r"oh no", r"uh oh", r"yikes", r"drat", r"rats", r"ouch", r"oof", r"sad", r"i lost",
                   r"we lost", r"went sad", r"no laff", r"cogs? won", r":\("),
     ((OH_NO, 3), (UH_OH, 2), (YIKES, 1), (WE_CAN_DO_THIS, 2)),
     SAD, True),
    ('no', _words(r"no", r"nope", r"nah", r"no thanks", r"no thank you"),
     ((OK, 4), (SORRY, 1), (HEH, 1)),
     SHRUG, True),
    ('yes', _words(r"yes", r"yeah", r"yep", r"yup", r"sure", r"ok", r"okay", r"k", r"alright", r"of course"),
     ((OK, 3), (COOL, 2), (YAY, 1), (LETS_GO, 1)),
     None, True),
)

# A who/what/where question nothing above understood: a SpeedChat toon
# can't really answer it, so a think, a shrug or a "Heh."
WH_QUESTION = re.compile(r"^(?:who|what|where|when|why|how|which)(?![a-z])")
WH_ANSWERS = ((HEH, 3), (WHAT_DID_YOU_SAY, 2), (OK, 1), (COOL, 1))
WH_EMOTES = (THINK, SHRUG, CONFUSED, None)
# A yes/no question nothing above understood: a yes, a no or a shrug.
QUESTION = ((YES, 4), (NO, 2), (OK, 2), (HEH, 1))
# Anything else.
OTHER = ((WHAT_DID_YOU_SAY, 3), (HEH, 2), (OK, 2), (COOL, 1), (WOW, 1))
OTHER_EMOTES = (CONFUSED, SHRUG, None, None)

# How much of the time a toon also plays the kind's emote while answering.
EMOTE_CHANCE = 0.6


def _pick(weighted):
    roll = random.uniform(0, sum(weight for phrase, weight in weighted))
    for phrase, weight in weighted:
        roll -= weight
        if roll <= 0:
            return phrase
    return weighted[-1][0]


def normalise(text):
    text = (text or '').lower().replace('’', "'")
    return re.sub(r"\s+", ' ', text).strip()


def kindOf(text):
    """The kind of thing the text says ('mean', 'hello', ...), or None."""
    text = normalise(text)
    for name, pattern, phrases, emote, summons in KINDS:
        if pattern.search(text):
            return name
    if text.endswith('?'):
        return 'question'
    return None


def answer(text):
    """(phrase, emote or None, summons) to say back to the text."""
    text = normalise(text)
    for name, pattern, phrases, emote, summons in KINDS:
        if pattern.search(text):
            if emote is not None and random.random() > EMOTE_CHANCE:
                emote = None
            return _pick(phrases), emote, summons
    if WH_QUESTION.search(text):
        return _pick(WH_ANSWERS), random.choice(WH_EMOTES), True
    if text.endswith('?'):
        phrase = _pick(QUESTION)
        emote = {YES: E_YES, NO: E_NO}.get(phrase) if random.random() < EMOTE_CHANCE else None
        return phrase, emote, True
    return _pick(OTHER), random.choice(OTHER_EMOTES), True
