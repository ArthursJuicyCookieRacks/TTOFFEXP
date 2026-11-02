"""What the big maps' rooms hold that a toon can use.

Each is a station like Mickey or the trunk: walk up, see the prompt, press
Use (some are held). They are made from what the map registered while it
was built (bigmaps/BigMap.py):

- WallGag: a gag on a plaque on the wall (Black Ops 1's wall weapons): buy
  it, or buy it again to fill it up for half the price.
- TonicMachine: one Toon Tonic from a party jukebox (the perk machines).
- DoorStation: a door, or a pile of junk, that opens for jellybeans.
- WindowStation: a boarded window; cogs tear the boards off from outside,
  holding Use nails them back on.
- PowerSwitch: the big lever; everything marked 'needs power' waits for it.
- TrapStation: lightning (or fire) across a doorway for a while.
- TurretStation: a toon cannon that fires pies at cogs by itself.
- Teleporter / Mainframe: the theater's pad to the projection booth, and
  the factory's three pads that link to the mainframe.
- MovingTrunk: the accessory trunk, which flies off to another spot when
  a Doodle pops out of it.
"""

import math
import random

from direct.interval.IntervalGlobal import (Func, LerpColorScaleInterval, LerpHprInterval, LerpPosInterval, LerpScaleInterval,
                                            Parallel, Sequence, Wait)
from panda3d.core import NodePath, Point3, TextNode, TransparencyAttrib, Vec3, Vec4

from toontown.battle import BattleProps
from toontown.survival import SurvivalGlobals as G
from toontown.survival.SurvivalStations import MickeyStation, Station, TrunkStation
from toontown.toonbase import ToontownGlobals

BUY_SOUND = 'phase_4/audio/sfx/MG_pairing_match.ogg'
DOOR_SOUND = 'phase_9/audio/sfx/CHQ_FACT_door_open_sliding.ogg'
JUNK_SOUND = 'phase_3/audio/sfx/tt_s_ara_mat_crash_wood.ogg'
BOARD_OFF = 'phase_6/audio/sfx/KART_Hitting_Wood_Fence.ogg'
BOARD_ON = 'phase_6/audio/sfx/KART_Hitting_Wood_Fence_1.ogg'
LEVER_SOUND = 'phase_9/audio/sfx/CHQ_FACT_switch_pressed.ogg'
POWER_ON_SOUND = 'phase_10/audio/sfx/CBHQ_TRAIN_stopstart.ogg'
SPARK_SOUND = 'phase_11/audio/sfx/LB_sparks_1.ogg'
ZAP_SOUNDS = ('phase_5/audio/sfx/lightning_1.ogg', 'phase_5/audio/sfx/lightning_2.ogg', 'phase_5/audio/sfx/lightning_3.ogg')
FIRE_SOUND = 'phase_5/audio/sfx/SA_hot_air.ogg'
CANNON_SOUND = 'phase_4/audio/sfx/MG_cannon_fire_alt.ogg'
TELEPORT_OUT = 'phase_5/audio/sfx/teleport_disappear.ogg'
TELEPORT_IN = 'phase_5/audio/sfx/teleport_reappear.ogg'
BUZZER = 'phase_4/audio/sfx/MG_neg_buzzer.ogg'
JUKEBOX = 'phase_13/models/parties/jukebox_model'
LEVER_BASE = 'phase_13/models/parties/partyLeverBase'
LEVER_STICK = 'phase_13/models/parties/partyLeverStick'
BUTTON = 'phase_9/models/cogHQ/CogDoor_Button'
CANNON = 'phase_4/models/minigames/toon_cannon'
PAD = 'phase_13/models/parties/launchPad'
LIGHTNING = 'phase_10/models/cogHQ/CBLightning'
WOOD = 'phase_3.5/maps/wood1.jpg'
PLAQUE = 'phase_11/maps/LB_WoodPanel2.jpg'
METAL = 'phase_9/maps/WallMetalPlateLargeRivets.jpg'

# The tonic machines: the jukebox tinted the tonic's colour.
TONIC_COLORS = {'toonup': (0.45, 0.95, 0.45, 1), 'seltzer': (0.45, 0.7, 1.0, 1), 'wind': (1.0, 0.62, 0.3, 1),
                'sprint': (0.85, 0.5, 0.95, 1), 'tracks': (1.0, 0.86, 0.35, 1), 'organic': (0.7, 1.0, 0.35, 1)}

# Black Ops 1's numbers for the room fixtures.
TRAP_TIME = 25.0
TRAP_COOL = 45.0
TRAP_HURT = 40
TURRET_TIME = 60.0
TURRET_RANGE = 45.0
TURRET_RATE = 0.3
TELEPORT_COST = 1500
TELEPORT_COOL = 90.0
BOOTH_TIME = 30.0
ROOM_TIME = 5.0
LINK_TIME = 30.0
REPAIR_TIME = 0.75
REPAIR_BEANS = 10
REPAIR_CAP = 500
MINES_PER_BUY = 2
UPGRADED_REFILL = 4500


def tonicName(key):
    for k, name, cost, blurb in G.TONICS:
        if k == key:
            return name, cost, blurb
    return key, 0, ''


class Fixture(Station):
    RANGE = 5.0

    def near(self, pos):
        here = self.node.getPos(self.game.arena.root)
        if abs(pos[2] - here[2]) > 6.0:
            return False
        return (Point3(pos[0], pos[1], 0) - Point3(here[0], here[1], 0)).length() < self.RANGE

    def needPower(self):
        return not self.game.powerOn

    def say(self, text, color=(1, 0.4, 0.4, 1)):
        self.floatText(text, color, height=5.0)


class WallGag(Fixture):
    """A gag on a wooden plaque, with its name and price painted under it."""
    RANGE = 5.5

    def __init__(self, game, entry):
        self.entry = entry
        self.key = entry['key']
        self.cost = entry['cost']
        Fixture.__init__(self, game, entry['pos'], entry['h'], 'wallgag')
        m = game.arena.parody
        # The node faces the room (heading h); the plaque, the gag and the
        # words are built facing -y on a face turned round to match.
        face = self.node.attachNewNode('face')
        face.setH(180)
        self.face = face
        # The plaque on the wall, the gag on it, the words under it, and
        # a chalk outline of the gag (BO1's wall weapons) behind it.
        plaque = m.boxNode(face, (-1.6, -0.15, 3.0), (1.6, 0.15, 6.0), PLAQUE, color=(0.8, 0.66, 0.55, 1), tile=3.2)
        plaque.setY(-0.15)
        self.plaque = plaque
        prop = BattleProps.globalPropPool.getProp(self.__propName())
        holder = face.attachNewNode('gagHolder')
        prop.reparentTo(holder)
        if hasattr(prop, 'pose'):
            # Some gags (the glass of water) start their animation shrunk
            # to nothing: show those halfway through, whole.
            try:
                anim = prop.getAnimNames()[0]
                prop.pose(anim, 0)
                prop.update(force=True)
                low, high = prop.getTightBounds()
                if low is None or max(high - low) < 0.05:
                    prop.pose(anim, prop.getNumFrames(anim) // 2)
                    prop.update(force=True)
            except Exception:
                pass
        prop.setScale(1.0)
        if self.key == 'rake':
            # A rake lies flat on the ground: roll it on its handle so the
            # tines face out from the wall, and hang it slanting so the
            # head shows.
            prop.setHpr(90, 0, 90)
            holder.setR(-38)
        elif isinstance(self.key, tuple) and self.key[0] == G.THROW:
            # Tipped forward so the cream and the fruit show.
            prop.setP(30)
        low, high = prop.getTightBounds(face)
        if low is not None and high[1] - low[1] > high[0] - low[0]:
            # Long gags (a bugle, a bottle) point out of the wall; lay them
            # flat on the plaque instead, side on.
            prop.setH(prop.getH() + 90)
            low, high = prop.getTightBounds(face)
        if low is not None:
            # As wide as the plaque allows, and short enough to stay clear
            # of the name painted under it.
            prop.setScale(min(2.4 / max(high[0] - low[0], 0.01), 1.75 / max(high[2] - low[2], 0.01)))
        low, high = prop.getTightBounds(face)
        if low is not None:
            mid = (low + high) * 0.5
            # Centred on the plaque, its back just touching the board.
            holder.setPos(holder.getPos() - Vec3(mid[0], high[1] + 0.32, mid[2] - 5.02))
        self.prop = prop
        name = self.title()
        text = TextNode('wallGagName')
        text.setFont(ToontownGlobals.getSignFont())
        text.setAlign(TextNode.ACenter)
        text.setText('%s\n%s' % (name, format(self.cost, ',')))
        text.setTextColor(1, 0.92, 0.55, 1)
        text.setShadow(0.06, 0.06)
        text.setShadowColor(0, 0, 0, 1)
        text.setWordwrap(9)
        label = face.attachNewNode(text)
        # Clear of the board and the gag, so the words never fight them
        # for the same depth (they shimmered at a distance).
        label.setPos(0, -0.5, 3.75)
        label.setScale(0.36)
        label.setLightOff()
        label.setDepthOffset(2)
        # The words and their black shadow lie in one plane; without this
        # they fight over the depth and shimmer as the camera moves.
        label.setDepthWrite(False)
        self.label = label

    def __propName(self):
        if self.key == 'tnt':
            return 'tnt'
        if self.key == 'rake':
            return 'rake'
        if self.key == 'marbles':
            return 'marbles'
        if self.key == 'cane':
            return 'cane'
        return G.GAGS[self.key][5]

    def title(self):
        return {'tnt': 'TNT', 'rake': 'Rakes', 'marbles': 'Marbles', 'cane': 'Bamboo Cane'}.get(self.key) or G.gagName(*self.key)

    def refillCost(self):
        gags = self.game.gags
        for gag in gags.gags:
            if (gag.track, gag.fromLevel) == self.key or (gag.track, gag.level) == self.key:
                return UPGRADED_REFILL if gag.upgraded else self.cost // 2
        return None

    def prompt(self):
        gags = self.game.gags
        name = self.title()
        if self.key == 'tnt':
            if gags.tnt >= G.TNT_MAX:
                return 'Your TNT is full'
            return 'Use: fill up your TNT for %d jellybeans' % self.cost
        if self.key in ('rake', 'marbles'):
            have = self.game.mines.count(self.key)
            if have >= MINES_PER_BUY:
                return 'You have %d %s: press %s to put one down' % (have, name, self.game.mines.keyName())
            return 'Use: buy %s for %d jellybeans' % (name, self.cost)
        if self.key == 'cane':
            if self.game.cane:
                return 'You already swing the Bamboo Cane'
            return 'Use: buy the Bamboo Cane for %d jellybeans' % self.cost
        refill = self.refillCost()
        if refill is not None:
            return 'Use: fill up your %s for %d jellybeans' % (name, refill)
        return 'Use: buy the %s for %d jellybeans' % (name, self.cost)

    def use(self):
        game = self.game
        gags = game.gags
        if self.key == 'tnt':
            if gags.tnt >= G.TNT_MAX or not game.spend(self.cost):
                return self.__broke(gags.tnt >= G.TNT_MAX)
            gags.tnt = G.TNT_MAX
            game.hud.setGag(gags.gag, gags.current, len(gags.gags))
            game.hud.say('TNT filled up!', 2.0)
            return True
        if self.key in ('rake', 'marbles'):
            if game.mines.count(self.key) >= MINES_PER_BUY or not game.spend(self.cost):
                return self.__broke(game.mines.count(self.key) >= MINES_PER_BUY)
            game.mines.give(self.key, MINES_PER_BUY)
            game.hud.say('%s! Press %s to put one down.' % (self.title(), game.mines.keyName()), 3.0)
            return True
        if self.key == 'cane':
            if game.cane or not game.spend(self.cost):
                return self.__broke(game.cane)
            game.cane = True
            game.hud.say('Bamboo Cane! Your bonk hits much harder.', 3.0)
            game.count('canes')
            return True
        refill = self.refillCost()
        if refill is not None:
            if not game.spend(refill):
                return self.__broke()
            gags.refill(self.key)
            game.hud.say('%s filled up!' % self.title(), 2.0)
            return True
        if not game.spend(self.cost):
            return self.__broke()
        gag = gags.give(*self.key)
        game.hud.say('Got the %s!' % gag.name, 2.0)
        game.count('wall gags')
        return True

    def __broke(self, full=False):
        if not full:
            self.say('Not enough jellybeans!')
        return False

    def destroy(self):
        if hasattr(self.prop, 'cleanup'):
            self.prop.cleanup()
        Fixture.destroy(self)


class TonicMachine(Fixture):
    """A party jukebox that sells one Toon Tonic. Every one but Second Wind
    needs the power on."""
    RANGE = 5.0

    def __init__(self, game, entry):
        self.key = entry['key']
        self.tonicName, cost, self.blurb = tonicName(self.key)
        self.cost = entry['cost'] or cost
        self.needsPower = entry['power']
        Fixture.__init__(self, game, entry['pos'], entry['h'], 'tonic-' + self.key)
        self.model = loader.loadModel(JUKEBOX)
        self.model.reparentTo(self.node)
        # The jukebox faces -y: turned round to face the room.
        self.model.setH(180)
        self.model.setScale(1.0)
        color = TONIC_COLORS.get(self.key, (1, 1, 1, 1))
        self.color = color
        self.model.setColorScale(*color)
        for piece in self.model.findAllMatches('**/+CollisionNode'):
            piece.removeNode()
        sign = TextNode('tonicSign')
        sign.setFont(ToontownGlobals.getSignFont())
        sign.setAlign(TextNode.ACenter)
        sign.setText(self.tonicName)
        sign.setTextColor(color[0], color[1], color[2], 1)
        sign.setShadow(0.06, 0.06)
        sign.setShadowColor(0, 0, 0, 1)
        sign.setWordwrap(8)
        self.sign = self.node.attachNewNode(sign)
        # On the room side of the machine, facing out. (It used to sit
        # behind the machine and turn to the camera, which swung its ends
        # through the wall.)
        self.sign.setPos(0, 1.0, 9.6)
        self.sign.setH(180)
        self.sign.setScale(0.62)
        self.sign.setLightOff()
        self.sign.setDepthWrite(False)
        # A big bottle of the tonic stands on top.
        bottle = BattleProps.globalPropPool.getProp('bottle')
        bottle.reparentTo(self.node)
        bottle.setScale(1.0)
        low, high = bottle.getTightBounds(self.node)
        if low is not None:
            bottle.setScale(1.6 / max(high[2] - low[2], 0.01))
        bottle.setPos(0, 0.4, 6.75)
        bottle.setColorScale(color[0], color[1], color[2], 1)
        self.bottle = bottle
        self.lit = None
        self.setLit(not self.needsPower)

    def setLit(self, on):
        if self.lit == on:
            return
        self.lit = on
        if on:
            self.model.setColorScale(*self.color)
            self.sign.show()
        else:
            # Dark and dead until the power comes on.
            self.model.setColorScale(self.color[0] * 0.3, self.color[1] * 0.3, self.color[2] * 0.3, 1)
            self.sign.hide()

    def tick(self, dt, now):
        self.setLit(not self.needsPower or self.game.powerOn)
        if self.lit:
            self.bottle.setH(now * 40 % 360)

    def prompt(self):
        if self.needsPower and not self.game.powerOn:
            return 'The %s machine needs the power on' % self.tonicName
        if self.game.hasTonic(self.key):
            return 'You have %s' % self.tonicName
        if self.key == 'wind' and self.game.secondWindBuys >= G.SECOND_WIND_BUYS:
            return 'Second Wind is sold out'
        if len(self.game.tonics) >= G.TONIC_LIMIT:
            return 'Four tonics is all a toon can hold'
        return 'Use: %s for %d jellybeans. %s' % (self.tonicName, self.cost, self.blurb)

    def use(self):
        game = self.game
        if self.needsPower and not game.powerOn:
            base.playSfx(base.loader.loadSfx(BUZZER), volume=0.4)
            return False
        if game.hasTonic(self.key) or len(game.tonics) >= G.TONIC_LIMIT:
            return False
        if self.key == 'wind' and game.secondWindBuys >= G.SECOND_WIND_BUYS:
            return False
        if not game.spend(self.cost):
            self.say('Not enough jellybeans!')
            return False
        game.giveTonic(self.key)
        self.floatText(self.tonicName + '!', self.color, height=8.5)
        game.count('tonics')
        Sequence(LerpScaleInterval(self.model, 0.15, Vec3(1.05, 1.05, 0.95)), LerpScaleInterval(self.model, 0.25, Vec3(1, 1, 1))).start()
        return True

    def destroy(self):
        self.model.removeNode()
        Fixture.destroy(self)


class DoorStation(Fixture):
    """A shut door (or a heap of junk) between two zones, opened with
    jellybeans; a power gate opens by itself when the power comes on."""
    RANGE = 7.0

    def __init__(self, game, entry):
        self.entry = entry
        a, b = entry['a'], entry['b']
        mid = (a + b) * 0.5
        Fixture.__init__(self, game, mid, 0, 'door-' + entry['name'])
        self.isOpen = False
        self.points = [Point3(p) for p in (entry.get('usePoints') or [])] or [mid]

    def near(self, pos):
        if self.isOpen or self.entry['power']:
            return False
        z0 = self.entry['z'][0]
        if abs(pos[2] - z0) > 6.0:
            return False
        a, b = self.entry['a'], self.entry['b']
        # Near anywhere along the doorway, from either side.
        ab = Vec3(b[0] - a[0], b[1] - a[1], 0)
        length = ab.length()
        if length < 0.01:
            return False
        u = ab / length
        rel = Vec3(pos[0] - a[0], pos[1] - a[1], 0)
        t = max(0.0, min(length, rel.dot(u)))
        closest = Vec3(a[0], a[1], 0) + u * t
        return (Vec3(pos[0], pos[1], 0) - closest).length() < self.RANGE

    def prompt(self):
        return 'Use: clear %s for %s jellybeans' % (self.entry['title'], format(self.entry['cost'], ','))

    def use(self):
        if self.isOpen:
            return False
        if not self.game.spend(self.entry['cost']):
            self.say('Not enough jellybeans!')
            return False
        self.open()
        self.game.count('doors')
        return True

    def open(self):
        if self.isOpen:
            return
        self.isOpen = True
        entry = self.entry
        entry['solid'].stash()
        self.game.arena.openBlocker(entry['name'])
        self.game.openZones(entry['zones'])
        visual = entry['visual']
        kind = entry['kind']
        sound = JUNK_SOUND if kind == 'junk' else DOOR_SOUND
        base.playSfx(base.loader.loadSfx(sound), volume=0.6, node=visual)
        if kind == 'junk':
            # The junk flies apart and fades.
            ivals = []
            for piece in visual.getChildren():
                away = Vec3(random.uniform(-3, 3), random.uniform(-3, 3), random.uniform(2, 5))
                ivals.append(Parallel(LerpPosInterval(piece, 0.8, piece.getPos() + away, blendType='easeOut'),
                                      LerpHprInterval(piece, 0.8, piece.getHpr() + Vec3(random.uniform(-90, 90), random.uniform(-60, 60), 0)),
                                      LerpColorScaleInterval(piece, 0.8, Vec4(1, 1, 1, 0), startColorScale=Vec4(1, 1, 1, 1))))
            visual.setTransparency(TransparencyAttrib.MAlpha)
            Sequence(Parallel(*ivals), Func(visual.stash)).start()
        elif kind == 'curtain':
            # Up into the fly loft.
            Sequence(LerpPosInterval(visual, 4.0, visual.getPos() + Vec3(0, 0, entry['z'][1] - entry['z'][0] + 2), blendType='easeInOut'),
                     Func(visual.stash)).start()
        elif kind == 'bridge':
            # The bridge swings down from where it was pulled up; its floor
            # is there once it lands, its far end's stop is gone.
            for np in entry.get('stops', ()):
                np.stash()
            Sequence(LerpHprInterval(visual, 3.0, Vec3(visual.getH(), 0, 0), blendType='easeIn'),
                     Func(lambda: [np.unstash() for np in entry.get('later', ())])).start()
        elif kind == 'shutter':
            Sequence(LerpPosInterval(visual, 2.5, visual.getPos() + Vec3(0, 0, entry['z'][1] - entry['z'][0] - 0.5), blendType='easeInOut')).start()
        else:
            # A door slides into the wall and is gone.
            visual.setTransparency(TransparencyAttrib.MAlpha)
            Sequence(Parallel(LerpPosInterval(visual, 1.0, visual.getPos() + Vec3(0, 0, -0.5)),
                              LerpColorScaleInterval(visual, 1.0, Vec4(1, 1, 1, 0), startColorScale=Vec4(1, 1, 1, 1))),
                     Func(visual.stash)).start()


class WindowStation(Fixture):
    """A boarded window. Cogs outside pull the boards off one at a time;
    holding Use nails them back, ten jellybeans a board."""
    RANGE = 6.0

    def __init__(self, game, win):
        self.win = win
        Fixture.__init__(self, game, win['inside'], win['h'], 'window')
        self.boards = []
        self.boardNodes = []
        self.repairAt = 0.0
        self.beansThisRound = 0
        self.lastRound = 0
        m = game.arena.parody
        holder = game.arena.root.attachNewNode('boards')
        holder.setPos(win['pos'])
        holder.setH(win['h'])
        self.holder = holder
        width, sill, height = win['width'], win['sill'], win['height']
        n = win['boards']
        rnd = random.Random(int(win['pos'][0] * 7 + win['pos'][1] * 13))
        for i in range(n):
            z = sill + (i + 0.5) * height / n
            board = m.boxNode(holder, (-width / 2.0 - 0.6, -0.12, -0.32), (width / 2.0 + 0.6, 0.12, 0.32), WOOD,
                              color=(0.62, 0.47, 0.33, 1), tile=2.5)
            board.setPos(0, -0.3, z)
            board.setR(rnd.uniform(-9, 9))
            board.setY(-0.3 + rnd.uniform(-0.05, 0.05))
            self.boardNodes.append((board, Point3(board.getPos()), board.getR()))
            self.boards.append(True)

    def count(self):
        return sum(1 for b in self.boards if b)

    def isOpen(self):
        return self.count() == 0

    def tearBoard(self):
        """A cog pulls one board off; False when there are none left."""
        for i in range(len(self.boards) - 1, -1, -1):
            if self.boards[i]:
                self.boards[i] = False
                board, pos, r = self.boardNodes[i]
                fall = Point3(pos[0] + random.uniform(-1, 1), pos[1] - 3.0, -self.win['sill'] - 0.3)
                Sequence(Parallel(LerpPosInterval(board, 0.45, fall, blendType='easeIn'),
                                  LerpHprInterval(board, 0.45, Vec3(random.uniform(-40, 40), random.uniform(-70, 70), r + 30))),
                         Func(board.hide)).start()
                base.playSfx(base.loader.loadSfx(BOARD_OFF), volume=0.5, node=self.holder)
                return True
        return False

    def putBoard(self):
        for i in range(len(self.boards)):
            if not self.boards[i]:
                self.boards[i] = True
                board, pos, r = self.boardNodes[i]
                board.show()
                board.setPos(pos + Vec3(0, 1.5, 0))
                board.setHpr(0, 0, r)
                LerpPosInterval(board, 0.2, pos, blendType='easeOut').start()
                base.playSfx(base.loader.loadSfx(BOARD_ON), volume=0.5, node=self.holder)
                return True
        return False

    def prompt(self):
        if self.count() < len(self.boards):
            return 'Hold Use: board up the window'
        return ''

    def near(self, pos):
        return Fixture.near(self, pos) and self.count() < len(self.boards)

    def use(self):
        return False

    def holdUse(self, dt):
        now = globalClock.getFrameTime()
        if now < self.repairAt:
            return
        # Not with a cog right at the window, pulling them off.
        self.repairAt = now + REPAIR_TIME * (0.5 if self.game.hasTonic('seltzer') else 1.0)
        if self.putBoard():
            if self.lastRound != self.game.roundNum:
                self.lastRound = self.game.roundNum
                self.beansThisRound = 0
            if self.beansThisRound < REPAIR_CAP:
                self.beansThisRound += REPAIR_BEANS
                self.game.earn(REPAIR_BEANS)

    def destroy(self):
        self.holder.removeNode()
        Fixture.destroy(self)


class PowerSwitch(Fixture):
    """The big lever: everything that needs power waits for it."""
    RANGE = 5.0

    def __init__(self, game, pos, h):
        Fixture.__init__(self, game, pos, h, 'power')
        m = game.arena.parody
        # A riveted box on the wall with a big handle on the front: down is
        # off, up is on.
        self.base = m.boxNode(self.node, (-1.3, -0.1, 2.2), (1.3, 0.55, 5.6), METAL, color=(0.55, 0.52, 0.48, 1), tile=3)
        for x in (-0.75, 0.75):
            m.boxNode(self.node, (x - 0.12, 0.55, 3.1), (x + 0.12, 0.7, 4.7), METAL, color=(0.3, 0.3, 0.3, 1), tile=2)
        self.pivot = self.node.attachNewNode('leverPivot')
        self.pivot.setPos(0, 0.75, 3.9)
        self.stick = m.boxNode(self.pivot, (-0.12, -0.12, 0), (0.12, 0.12, 2.1), METAL, color=(0.35, 0.33, 0.32, 1), tile=2)
        knob = m.boxNode(self.pivot, (-0.32, -0.32, 2.0), (0.32, 0.32, 2.5), WOOD, color=(0.75, 0.15, 0.12, 1), tile=1)
        self.pivot.setP(-150)
        sign = TextNode('powerSign')
        sign.setFont(ToontownGlobals.getSignFont())
        sign.setAlign(TextNode.ACenter)
        sign.setText('POWER')
        sign.setTextColor(1, 0.85, 0.2, 1)
        sign.setShadow(0.05, 0.05)
        signNp = self.node.attachNewNode(sign)
        signNp.setPos(0, 0.05, 6.0)
        signNp.setH(180)
        signNp.setScale(0.7)
        signNp.setLightOff()
        signNp.setDepthWrite(False)

    def prompt(self):
        if self.game.powerOn:
            return ''
        return 'Use: turn on the power'

    def use(self):
        if self.game.powerOn:
            return False
        base.playSfx(base.loader.loadSfx(LEVER_SOUND), volume=0.8)
        Sequence(LerpHprInterval(self.pivot, 0.6, Vec3(0, -30, 0), blendType='easeIn'), Func(self.game.turnPowerOn)).start()
        return True


class TrapStation(Fixture):
    """An electric (or fire) trap across a doorway: a switch on the wall
    starts it for 25 seconds; every cog in it pops, toons in it get hurt;
    then it cools down."""
    RANGE = 4.5

    def __init__(self, game, entry):
        self.entry = entry
        Fixture.__init__(self, game, entry['switch'], entry['h'], 'trap-' + entry['name'])
        self.button = loader.loadModel(BUTTON)
        # The button's own floor is turned on its side here: a floor ray
        # meeting it edge on gives a point of NaN (a crash on Android).
        self.button.findAllMatches('**/+CollisionNode').detach()
        self.button.reparentTo(self.node)
        self.button.setScale(0.5)
        self.button.setPos(0, 0.3, 3.2)
        self.button.setP(90)
        self.button.setColorScale(1, 0.85, 0.3, 1)
        self.until = 0.0
        self.coolUntil = 0.0
        self.nextHurt = 0.0
        self.nextZap = 0.0
        self.effects = game.arena.root.attachNewNode('trapEffects')
        self.bolts = []
        self.flames = []
        line = entry.get('line')
        x0, y0, x1, y1 = entry['area']
        z0, z1 = entry['z']
        if line is None:
            line = (Point3((x0 + x1) / 2, y0, z0), Point3((x0 + x1) / 2, y1, z0))
        a, b = Point3(line[0]), Point3(line[1])
        self.line = (a, b)
        if entry['kind'] == 'electric':
            for i in range(7):
                t = (i + 0.5) / 7.0
                p = a + (b - a) * t
                bolt = loader.loadModel(LIGHTNING)
                bolt.reparentTo(self.effects)
                bolt.setPos(p[0], p[1], z0 + random.uniform(1.5, 6.0))
                bolt.setScale(random.uniform(1.6, 2.6))
                bolt.setBillboardAxis()
                bolt.setLightOff()
                bolt.setColorScale(0.6, 0.85, 1.0, 1)
                bolt.setBin('fixed', 30)
                bolt.setDepthWrite(0)
                bolt.hide()
                self.bolts.append(bolt)
        else:
            for i in range(6):
                t = (i + 0.5) / 6.0
                p = a + (b - a) * t
                fire = loader.loadModel('phase_4/models/props/tt_m_efx_fireball')
                fire.reparentTo(self.effects)
                fire.setPos(p[0], p[1], z0 + 0.4)
                fire.setScale(1.6)
                fire.setBillboardAxis()
                fire.setLightOff()
                fire.setBin('fixed', 30)
                fire.setDepthWrite(0)
                fire.hide()
                self.flames.append(fire)
        self.loop = None

    def active(self):
        return globalClock.getFrameTime() < self.until

    def prompt(self):
        now = globalClock.getFrameTime()
        if now < self.until:
            return ''
        kind = 'electric trap' if self.entry['kind'] == 'electric' else 'fire trap'
        if not self.game.powerOn:
            return 'The %s needs the power on' % kind
        if now < self.coolUntil:
            return 'The %s is cooling down' % kind
        return 'Use: start the %s for %d jellybeans' % (kind, self.entry['cost'])

    def use(self):
        now = globalClock.getFrameTime()
        if not self.game.powerOn or now < self.until or now < self.coolUntil:
            return False
        if not self.game.spend(self.entry['cost']):
            self.say('Not enough jellybeans!')
            return False
        self.until = now + TRAP_TIME
        self.coolUntil = self.until + TRAP_COOL
        for n in self.bolts + self.flames:
            n.show()
        self.button.setColorScale(1, 0.3, 0.3, 1)
        self.game.count('traps')
        return True

    def contains(self, p):
        x0, y0, x1, y1 = self.entry['area']
        z0, z1 = self.entry['z']
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 - 1 <= p[2] <= z1

    def tick(self, dt, now):
        if now >= self.until:
            if self.bolts and not self.bolts[0].isHidden() or self.flames and not self.flames[0].isHidden():
                for n in self.bolts + self.flames:
                    n.hide()
                self.button.setColorScale(1, 0.85, 0.3, 1)
            return
        # The bolts jump about; the flames lick up.
        for bolt in self.bolts:
            if random.random() < 0.35:
                bolt.setR(random.uniform(-40, 40))
                bolt.setSz(random.uniform(1.6, 3.2))
                bolt.setColorScale(random.uniform(0.5, 1), random.uniform(0.8, 1), 1, 1)
                bolt.show() if random.random() < 0.8 else bolt.hide()
        for fire in self.flames:
            fire.setSz(random.uniform(1.4, 2.4))
        if now >= self.nextZap:
            self.nextZap = now + random.uniform(0.25, 0.6)
            sounds = ZAP_SOUNDS if self.bolts else (FIRE_SOUND,)
            base.playSfx(base.loader.loadSfx(random.choice(sounds)), volume=0.45, node=self.effects)
        for cog in list(self.game.cogs):
            if not cog.dead and cog.state not in ('landing', 'entering') and self.contains(cog.pos):
                cog.lastHitByNPC = False
                cog.hurt(cog.hp + 1)
        if now >= self.nextHurt:
            self.nextHurt = now + 0.5
            player = self.game.player
            if player.alive() and self.contains(player.getPos()):
                player.hurt(TRAP_HURT)

    def destroy(self):
        self.effects.removeNode()
        self.button.removeNode()
        Fixture.destroy(self)


class TurretStation(Fixture):
    """A toon cannon on a table: bought, it fires pies at the nearest cog
    it can see for a minute."""
    RANGE = 4.5

    def __init__(self, game, entry):
        self.entry = entry
        Fixture.__init__(self, game, entry['button'], entry['buttonH'], 'turret')
        self.cannonNode = game.arena.root.attachNewNode('turret')
        self.cannonNode.setPos(entry['pos'])
        self.cannonNode.setH(entry['h'])
        self.cannon = loader.loadModel(CANNON)
        self.cannon.reparentTo(self.cannonNode)
        self.cannon.setScale(0.45)
        self.barrel = self.cannon.find('**/cannon')
        if self.barrel.isEmpty():
            self.barrel = self.cannon
        self.button = loader.loadModel(BUTTON)
        # The button's own floor is turned on its side here: a floor ray
        # meeting it edge on gives a point of NaN (a crash on Android).
        self.button.findAllMatches('**/+CollisionNode').detach()
        self.button.reparentTo(self.node)
        self.button.setScale(0.45)
        self.button.setPos(0, 0.3, 3.0)
        self.button.setP(90)
        self.until = 0.0
        self.nextShot = 0.0
        self.shots = []

    def prompt(self):
        if globalClock.getFrameTime() < self.until:
            return ''
        if not self.game.powerOn:
            return 'The pie cannon needs the power on'
        return 'Use: fire up the pie cannon for %d jellybeans' % self.entry['cost']

    def use(self):
        now = globalClock.getFrameTime()
        if now < self.until or not self.game.powerOn:
            return False
        if not self.game.spend(self.entry['cost']):
            self.say('Not enough jellybeans!')
            return False
        self.until = now + TURRET_TIME
        self.game.count('turrets')
        return True

    def tick(self, dt, now):
        for shot in list(self.shots):
            shot['t'] += dt
            k = min(1.0, shot['t'] / shot['time'])
            p = shot['a'] + (shot['b'] - shot['a']) * k
            shot['np'].setPos(p)
            if k >= 1.0:
                shot['np'].removeNode()
                self.shots.remove(shot)
                cog = shot['cog']
                if not cog.dead:
                    cog.lastHitByNPC = True
                    cog.hurt(max(150, G.cogHp(self.game.roundNum) // 3))
        if now >= self.until or now < self.nextShot:
            return
        muzzle = self.cannonNode.getPos(self.game.arena.root) + Vec3(0, 0, 1.6)
        best, bestDist = None, TURRET_RANGE
        for cog in self.game.cogs:
            if cog.dead or cog.state in ('landing', 'entering'):
                continue
            d = (cog.pos - muzzle).length()
            if d < bestDist and self.game.arena.clearLine(muzzle, Point3(cog.pos[0], cog.pos[1], cog.pos[2] + 2)):
                best, bestDist = cog, d
        if best is None:
            return
        self.nextShot = now + TURRET_RATE
        aim = Point3(best.pos[0], best.pos[1], best.pos[2] + best.height * 0.6)
        self.cannonNode.lookAt(Point3(aim[0], aim[1], muzzle[2]))
        self.cannonNode.setH(self.cannonNode.getH() + 180)
        pie = BattleProps.globalPropPool.getProp('creampie')
        pie.reparentTo(self.game.arena.root)
        pie.setScale(0.6)
        self.shots.append({'np': pie, 'a': Point3(muzzle), 'b': aim, 't': 0.0, 'time': max(0.1, bestDist / 90.0), 'cog': best})
        base.playSfx(base.loader.loadSfx(CANNON_SOUND), volume=0.35, node=self.cannonNode)

    def destroy(self):
        for shot in self.shots:
            shot['np'].removeNode()
        self.shots = []
        self.cannonNode.removeNode()
        Fixture.destroy(self)


class Teleporter(Fixture):
    """A party launch pad. The map says what it does (see BigMap's
    teleporter() and the map's own useTeleporter)."""
    RANGE = 5.0

    def __init__(self, game, entry):
        self.entry = entry
        Fixture.__init__(self, game, entry['pos'], entry['h'], 'teleporter-' + entry['name'])
        self.coolUntil = 0.0
        self.linked = False
        self.charged = False

    def prompt(self):
        return self.game.arena.parody.teleporterPrompt(self.game, self)

    def use(self):
        return self.game.arena.parody.useTeleporter(self.game, self)


class MovingTrunk(TrunkStation):
    """The accessory trunk on a big map: a Doodle sends it flying off to
    another of the map's spots, where a beam of light shows it."""

    MOVE_TIME = 6.0

    def __init__(self, game):
        TrunkStation.__init__(self, game)
        self.spots = game.arena.parody.boxSpots
        self.current = None
        for spot in self.spots:
            if (spot['pos'] - self.node.getPos()).length() < 1.0:
                self.current = spot
        self.away = False
        self.beam = self.__makeBeam()
        self.blocker = None

    def __makeBeam(self):
        from toontown.survival.previewmaps.MapKit import Mesh
        m = Mesh()
        sides = 12
        r, hgt = 1.8, 60.0
        for i in range(sides):
            a0 = 2 * math.pi * i / sides
            a1 = 2 * math.pi * (i + 1) / sides
            p0 = Point3(r * math.cos(a0), r * math.sin(a0), 0)
            p1 = Point3(r * math.cos(a1), r * math.sin(a1), 0)
            m.quad([p0, p1, p1 + Vec3(0, 0, hgt), p0 + Vec3(0, 0, hgt)], [(0, 0), (1, 0), (1, 1), (0, 1)], Vec4(0.75, 0.9, 1.0, 0.16))
        np = self.node.attachNewNode(m.node('trunkBeam'))
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setTwoSided(True)
        np.setLightOff()
        np.setDepthWrite(0)
        np.setBin('fixed', 20)
        np.setColorScaleOff(5)
        return np

    def near(self, pos):
        if self.away:
            return False
        here = self.node.getPos()
        if abs(pos[2] - here[2]) > 6.0:
            return False
        return TrunkStation.near(self, pos)

    def prompt(self):
        if self.away:
            return ''
        return TrunkStation.prompt(self)

    def use(self):
        if self.away:
            return False
        return TrunkStation.use(self)

    def doodled(self):
        """Called when a Doodle pops out: off it goes."""
        others = [s for s in self.spots if s is not self.current] or self.spots
        spot = random.choice(others)
        self.away = True
        self.shutUntil = 0.0
        self.game.hud.say('The trunk is off to somewhere else!', 3.0)
        model = self.model
        start = Point3(model.getPos())
        Sequence(Wait(1.0),
                 Parallel(LerpPosInterval(model, 2.0, start + Vec3(0, 0, 30), blendType='easeIn'),
                          LerpHprInterval(model, 2.0, Vec3(720, 0, 0)),
                          LerpColorScaleInterval(self.beam, 1.5, Vec4(1, 1, 1, 0))),
                 Func(self.__arrive, spot, start)).start()

    def __arrive(self, spot, start):
        self.current = spot
        self.node.setPos(spot['pos'])
        self.node.setH(spot['h'])
        self.model.setPos(start)
        self.model.setHpr(0, 0, 0)
        self.game.arena.moveTrunkBlocker(spot['pos'])
        Sequence(Wait(self.MOVE_TIME - 3.0), LerpColorScaleInterval(self.beam, 1.0, Vec4(1, 1, 1, 1), startColorScale=Vec4(1, 1, 1, 0)),
                 Func(self.__ready)).start()

    def __ready(self):
        self.away = False
        self.readyAt = globalClock.getFrameTime()


class UpgradeStation(MickeyStation):
    """The gag upgrade on a big map: Mickey in the theater's projection
    booth; in the factory it waits behind its shutter until all three
    teleporters are linked."""

    def prompt(self):
        if not self.game.arena.parody.upgradeOpen(self.game):
            return ''
        return MickeyStation.prompt(self)

    def use(self):
        if not self.game.arena.parody.upgradeOpen(self.game):
            return False
        return MickeyStation.use(self)

    def near(self, pos):
        here = self.node.getPos()
        if abs(pos[2] - here[2]) > 6.0:
            return False
        return MickeyStation.near(self, pos)


class Mines:
    """The Rakes and Marbles a toon carries and the ones on the floor:
    a cog that walks over one sets it off."""
    KEY = '4'
    DAMAGE = 1000
    REACH = 4.0
    PROPS = {'rake': 'rake', 'marbles': 'marbles'}

    def __init__(self, game):
        self.game = game
        self.held = {}
        self.owned = set()
        self.down = []

    def keyName(self):
        return self.KEY

    def count(self, kind):
        return self.held.get(kind, 0)

    def give(self, kind, n):
        self.owned.add(kind)
        self.held[kind] = min(MINES_PER_BUY, self.held.get(kind, 0) + n)

    def newRound(self):
        # Bought once, two more every round, as BO1's Claymores.
        for kind in self.owned:
            self.held[kind] = MINES_PER_BUY

    def place(self):
        kinds = [k for k, n in self.held.items() if n > 0]
        if not kinds:
            return False
        kind = kinds[0]
        player = self.game.player
        pos = player.getPos() + player.getFlatForward() * 2.5
        z = self.game.arena.groundZ(pos[0], pos[1], pos[2] + 2.0)
        if z is None:
            return False
        self.held[kind] -= 1
        prop = BattleProps.globalPropPool.getProp(self.PROPS[kind])
        prop.reparentTo(self.game.arena.root)
        prop.setPos(pos[0], pos[1], z)
        prop.setH(player.getH())
        prop.setScale(1.2 if kind == 'rake' else 1.0)
        if hasattr(prop, 'pose'):
            try:
                prop.pose(prop.getAnimNames()[0], 0)
            except Exception:
                pass
        self.down.append({'np': prop, 'pos': Point3(pos[0], pos[1], z), 'kind': kind})
        return True

    def tick(self):
        for mine in list(self.down):
            for cog in self.game.cogs:
                if cog.dead or cog.state in ('landing', 'entering'):
                    continue
                if (Vec3(cog.pos - mine['pos'])).length() < self.REACH:
                    self.__boom(mine)
                    break

    def __boom(self, mine):
        self.down.remove(mine)
        pos = mine['pos']
        np = mine['np']
        if mine['kind'] == 'marbles':
            # Up into the cog's face before they go.
            np.setZ(pos[2] + 3.0)
        self.game.damageArea(Point3(pos[0], pos[1], pos[2]), 6.0, self.DAMAGE)
        explosion = loader.loadModel('phase_3.5/models/props/explosion')
        explosion.reparentTo(self.game.arena.root)
        explosion.setBillboardPointEye()
        explosion.setPos(pos[0], pos[1], pos[2] + 2)
        explosion.setScale(0.6)
        base.playSfx(base.loader.loadSfx('phase_4/audio/sfx/firework_explosion_02.ogg'), volume=0.6)
        Sequence(Wait(0.4), Func(explosion.removeNode), Func(np.removeNode if not hasattr(np, 'cleanup') else (lambda: (np.cleanup(), np.removeNode())))).start()

    def destroy(self):
        for mine in self.down:
            np = mine['np']
            if hasattr(np, 'cleanup'):
                np.cleanup()
            np.removeNode()
        self.down = []
