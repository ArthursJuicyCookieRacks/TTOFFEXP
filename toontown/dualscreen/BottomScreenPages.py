"""What the bottom screen of a dual-screen handheld shows (see SecondScreen).

Before PLAY!: "Game Not Started". After it, until a toon is playing: "Toon
Not Selected". Then the toon's own laff meter, with buttons (the game's own
icons) for the gags, the ToonTasks, the map, the districts and the Shticker
Book (which opens on the top screen), and below them the NPC friends, quick
SpeedChat and emotes, jellybeans and Cog suit progress, and how the other
toons help. In a battle that row is the Cogs' laff and Need Help!.

Every page but the first has a Back arrow to the laff meter.
"""

import math

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase.DirectObject import DirectObject
from panda3d.core import CardMaker, NodePath, PNMImage, Point3, TextNode, Texture, TransparencyAttrib

from toontown.hood import ZoneUtil
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals

notify = DirectNotifyGlobal.directNotify.newCategory('BottomScreen')

WHITE = (1, 1, 1, 1)
# Book page colors: the writing, quieter writing, the line under a title,
# the edge of a card and the cards' soft tints.
INK = (0.16, 0.22, 0.48, 1)
SOFT = (0.38, 0.42, 0.55, 1)
RULE = (0.72, 0.77, 0.88, 1)
EDGE = (0.66, 0.72, 0.84)
CREAM = (1, 0.97, 0.86, 1)
GOLD = (1, 0.92, 0.6, 1)
SKY = (0.78, 0.89, 1, 1)
MINT = (0.78, 0.95, 0.78, 1)
LILAC = (0.88, 0.82, 1, 1)
ROSE = (1, 0.82, 0.8, 1)
PINK = (1, 0.84, 0.94, 1)
# The page's writing stays within this far of the middle, the home page's
# buttons are TILE across, GRID apart.
CONTENT = 0.7
# How far left of the screen's middle the middle of the book's paper is, in
# half screen widths.
PAPER_SHIFT = 0.11
TILE = 0.32
GRID = 0.38
# How far each home icon's picture is moved after centering its bounds, in
# page units (measured on the drawn page: a square is 131 pixels for TILE).
ICON_NUDGES = {'book': ((-0.056 + 0.0134) * 0.34 / 0.22, 0.034 * 0.34 / 0.22), 'map': (0, -0.011), 'friends': (-0.0085, -0.005)}
# The pages past the home page draw their writing and buttons this much
# bigger than the home page's.
BIG = 1.1
NOT_STARTED = 'Game Not Started'
NO_TOON = 'Toon Not Selected'
SPEEDCHAT = ((100, 'Hi!'), (102, 'Hello!'), (300, 'Yay!'), (500, 'Thanks!'), (511, 'Can you help me?'), (200, 'Bye!'))
EMOTES = ('Wave', 'Happy', 'Dance', 'Laugh')
REFRESH = 1.0
SURVIVAL_REFRESH = 0.2
# Where the Shticker Book's map page puts each playground's name, and the
# clouds over the ones not visited yet (in ToontownGlobals.Hoods order).
MAP_LABELS = ((0.594, 0.0, -0.075), (0.0, 0.0, -0.1), (0.475, 0.0, 0.25), (0.1, 0.0, 0.15), (-0.3, 0.0, -0.375),
              (0.2, 0.0, -0.45), (-0.55, 0.0, 0.0), (-0.088, 0.0, 0.47), (0.7, 0.0, -0.5), (-0.7, 0.0, -0.5),
              (-0.7, 0.0, 0.5), (0.7, 0.0, 0.5), (0.45, 0.0, -0.45))
MAP_CLOUD_SCALES = (((0.55, 0, 0.4), (0.35, 0, 0.25)), (), ((0.45, 0, 0.45), (0.5, 0, 0.4)), ((0.7, 0, 0.45),),
                    ((0.55, 0, 0.4),), ((0.6, 0, 0.4), (0.5332, 0, 0.32)), ((0.7, 0, 0.45), (0.7, 0, 0.45)),
                    ((0.7998, 0, 0.39),), ((0.5, 0, 0.4),), ((-0.45, 0, 0.4),), ((-0.45, 0, 0.35),), ((0.5, 0, 0.35),),
                    ((0.5, 0, 0.35),))
MAP_CLOUDS = (((0.575, 0.0, -0.04), (0.45, 0.0, -0.25)), (), ((0.375, 0.0, 0.4), (0.5625, 0.0, 0.2)), ((-0.02, 0.0, 0.23),),
              ((-0.3, 0.0, -0.4),), ((0.25, 0.0, -0.425), (0.125, 0.0, -0.36)), ((-0.5625, 0.0, -0.07), (-0.45, 0.0, 0.2125)),
              ((-0.125, 0.0, 0.5),), ((0.66, 0.0, -0.4),), ((-0.68, 0.0, -0.444),), ((-0.6, 0.0, 0.45),), ((0.66, 0.0, 0.5),),
              ((0.4, 0.0, -0.35),))


class Tap:
    """Something on the bottom screen that does something when touched."""

    def __init__(self, node, command, args=()):
        self.node = node
        self.command = command
        self.args = args
        self.scale = node.getScale()


def currentStage():
    """'notStarted' (the launcher), 'noToon' or 'game'."""
    from toontown.toonbase import OfflineLauncher
    launcher = getattr(OfflineLauncher, '_launcher', None)
    if launcher is not None and not launcher.started:
        return 'notStarted'
    avatar = getattr(base, 'localAvatar', None)
    cr = getattr(base, 'cr', None)
    playGame = getattr(cr, 'playGame', None) if cr else None
    try:
        place = playGame.getPlace() if playGame else None
    except AttributeError:
        place = None
    if avatar is not None and not avatar.isEmpty() and place is not None and hasattr(avatar, 'laffMeter'):
        return 'game'
    return 'noToon'


def survivalGame():
    """The Survival Mode game being played, if any (it runs from
    Pick-A-Toon, before there is a toon in the world)."""
    cr = getattr(base, 'cr', None)
    chooser = getattr(cr, 'avChoice', None) if cr else None
    launcher = getattr(chooser, 'survivalLauncher', None) if chooser else None
    game = getattr(launcher, 'game', None) if launcher else None
    if game is not None and getattr(game, 'player', None) is not None and getattr(game, 'gags', None) is not None:
        return game
    return None


def currentPlace():
    try:
        return base.cr.playGame.getPlace()
    except AttributeError:
        return None


def isStreet(place):
    # Each hood has its own Street subclass (TTStreet, DDStreet, ...).
    from toontown.town.Street import Street
    return isinstance(place, Street)


def placeState():
    place = currentPlace()
    try:
        return place.fsm.getCurrentState().getName()
    except AttributeError:
        return None


def currentBattle():
    avatar = base.localAvatar
    battle = base.cr.doId2do.get(getattr(avatar, 'battleId', 0))
    if battle is not None and avatar in getattr(battle, 'toons', ()):
        return battle
    for do in list(base.cr.doId2do.values()):
        if hasattr(do, 'activeSuits') and avatar in getattr(do, 'toons', ()):
            return do
    return None


class BottomScreen(DirectObject):

    def __init__(self, screen, aspect, aspectRatio):
        DirectObject.__init__(self)
        self.screen = screen
        self.aspect = aspect
        self.width = aspectRatio
        self.font = ToontownGlobals.getInterfaceFont()
        self.signFont = ToontownGlobals.getSignFont()
        self.page = None
        self.pageName = None
        self.stage = None
        self.taps = []
        self.laffMeter = None
        self.lastRefresh = 0
        self.message = None
        self.messageUntil = 0
        # The street the toon is on (its branch zone), to show its map the
        # moment the toon arrives there.
        self.street = None
        self.loadArt()

    def loadArt(self):
        self.art = NodePath('bottomScreenArt')
        models = {}
        for name in ('phase_3.5/models/gui/sos_textures', 'phase_3.5/models/gui/inventory_icons',
                     'phase_3.5/models/gui/stickerbook_gui', 'phase_3/models/gui/tt_m_gui_pat_mainGui',
                     'phase_3/models/gui/tt_m_gui_mat_mainGui', 'phase_3.5/models/gui/friendslist_gui',
                     'phase_3.5/models/gui/chat_input_gui', 'phase_3.5/models/gui/jar_gui',
                     'phase_3/models/gui/quit_button', 'phase_3.5/models/gui/toontown_map',
                     'phase_3.5/models/gui/cloud', 'phase_3/models/gui/cog_icons'):
            models[name.split('/')[-1]] = loader.loadModel(name)
        self.models = models

    def find(self, model, name):
        return self.models[model].find('**/' + name)

    def destroy(self):
        self.clear()
        self.ignoreAll()
        for model in self.models.values():
            model.removeNode()
        self.models = {}

    # --- Pages ---

    def clear(self):
        if self.laffMeter is not None:
            self.laffMeter.stop()
            self.laffMeter.destroy()
            self.laffMeter = None
        self.ignore('toonLookChanged')
        if self.page is not None:
            self.page.removeNode()
            self.page = None
        self.taps = []
        self.message = None

    def show(self, name):
        self.clear()
        self.pageName = name
        self.page = self.aspect.attachNewNode('page-' + name)
        getattr(self, 'build' + name[0].upper() + name[1:])()
        self.lastRefresh = globalClock.getRealTime()

    def update(self):
        stage = 'survival' if survivalGame() is not None else currentStage()
        if stage != self.stage:
            self.stage = stage
            self.show({'notStarted': 'notStarted', 'noToon': 'noToon', 'survival': 'survival'}.get(stage, 'home'))
            return
        if stage not in ('game', 'survival'):
            return
        if stage == 'game':
            self.followStreet()
        now = globalClock.getRealTime()
        if self.message is not None and now >= self.messageUntil and not self.message.isEmpty():
            self.message.hide()
        # Ammo and laff move fast in Survival Mode: that page keeps up.
        if now - self.lastRefresh >= (SURVIVAL_REFRESH if stage == 'survival' else REFRESH):
            self.lastRefresh = now
            refresh = getattr(self, 'refresh' + self.pageName[0].upper() + self.pageName[1:], None)
            if refresh is not None:
                refresh()

    def followStreet(self):
        # Arthur: entering a street swaps the bottom screen to its map right
        # away; leaving it takes the street map back to the laff meter.
        place = currentPlace()
        street = None
        if isStreet(place):
            street = ZoneUtil.getCanonicalBranchZone(place.getZoneId())
        if street == self.street:
            return
        if street is not None:
            questMap = getattr(base.localAvatar, 'questMap', None)
            if questMap is None or not questMap.container['image']:
                # The street's map is still loading: try again next frame.
                return
            self.street = street
            self.show('map')
        else:
            self.street = None
            if self.pageName == 'map':
                self.show('home')

    def tapAt(self, point):
        for tap in reversed(self.taps):
            node = tap.node
            if node.isEmpty() or node.isHidden() or not node.hasParent():
                continue
            bounds = self.boundsOf(node)
            if not bounds:
                continue
            low, high = bounds
            if low[0] <= point[0] <= high[0] and low[2] <= point[2] <= high[2]:
                return tap
        return None

    def boundsOf(self, node):
        """(low, high) corners of what can be touched, on the screen."""
        item = getattr(node, 'guiItem', None)
        if item is not None:
            left, right, bottom, top = item.getFrame()
            if right > left and top > bottom:
                matrix = node.getMat(self.aspect)
                corners = [matrix.xformPoint(Point3(x, 0, z)) for x in (left, right) for z in (bottom, top)]
                return (Point3(min(c[0] for c in corners), 0, min(c[2] for c in corners)),
                        Point3(max(c[0] for c in corners), 0, max(c[2] for c in corners)))
        return node.getTightBounds(self.aspect)

    def fire(self, tap):
        messenger.send('wakeup')
        try:
            tap.command(*tap.args)
        except Exception:
            notify.warning('bottom screen button failed')
            import traceback
            traceback.print_exc()

    # --- Building blocks ---

    def label(self, text, pos, scale=0.07, fg=INK, parent=None, font=None, wordwrap=None, align=TextNode.ACenter, shadow=None):
        args = dict(parent=parent or self.page, relief=None, pos=pos, text=text, text_scale=scale, text_fg=fg,
                    text_font=font or self.font, text_align=align)
        if shadow:
            args['text_shadow'] = shadow
        if wordwrap:
            args['text_wordwrap'] = wordwrap
        return DirectLabel(**args)

    def tap(self, node, command, *args):
        self.taps.append(Tap(node, command, args))
        return node

    def paper(self):
        # An empty page of the Shticker Book (the right half of its picture).
        texture = self.find('stickerbook_gui', 'big_book').findTexture('*')
        cards = CardMaker('page')
        cards.setFrame(-self.width, self.width, -1, 1)
        cards.setUvRange((0.5, 0), (1, 1))
        card = self.page.attachNewNode(cards.generate())
        card.setTexture(texture, 1)
        card.setBin('background', 0)
        # The paper (spine shadow to grey edge) is a little left of the
        # picture's middle: everything on it is moved over to match.
        self.page.setX(-PAPER_SHIFT * self.width)
        card.setX(PAPER_SHIFT * self.width)

    def panel(self, pos, width, height, tint=WHITE, parent=None, touchable=False, **kw):
        """A rounded card, width by height, centered on pos."""
        frame = DirectFrame(parent=parent or self.page, relief=None, image=roundedTexture(width / height),
                            image_scale=(width / 2.0, 1, height / 2.0), image_color=tint, pos=pos,
                            frameSize=(-width / 2.0, width / 2.0, -height / 2.0, height / 2.0),
                            state=DGG.NORMAL if touchable else DGG.DISABLED, **kw)
        frame.setTransparency(TransparencyAttrib.MAlpha)
        return frame

    def iconTile(self, pos, tint, icon, iconScale, command, *args, size=TILE, nudge=(0, 0)):
        frame = self.panel(pos, size, size, tint, touchable=True)
        if icon is not None:
            holder = frame.attachNewNode('icon')
            icon.copyTo(holder)
            holder.setScale(iconScale)
            holder.setY(-1)
            low, high = holder.getTightBounds(frame) or (Point3(0), Point3(0))
            holder.setX(holder.getX() - (low[0] + high[0]) / 2.0)
            holder.setZ(holder.getZ() - (low[2] + high[2]) / 2.0)
            # For icons whose model is bigger than their picture.
            holder.setPos(holder.getX() + nudge[0], -1, holder.getZ() + nudge[1])
        return self.tap(frame, command, *args)

    def textButton(self, text, pos, command, *args, width=0.62, height=0.14, textScale=0.055, tint=WHITE):
        frame = self.panel(pos, width, height, tint, touchable=True, text=text, text_scale=textScale,
                           text_pos=(0, -textScale * 0.35), text_fg=INK, text_font=self.font)
        return self.tap(frame, command, *args)

    def title(self, text, font=None):
        self.label(text, (0, 0, 0.8), scale=0.1 * BIG, font=font or self.font, fg=INK)
        DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=RULE, frameSize=(-0.58, 0.58, -0.004, 0.004), pos=(0, 0, 0.73))

    def backButton(self):
        images = tuple(self.find('stickerbook_gui', name) for name in ('arrow_button', 'arrow_down', 'arrow_rollover'))
        frame = DirectFrame(parent=self.page, relief=None, image=images[0], scale=(-0.19, 0.19, 0.19),
                            pos=(-self.width + 0.25, 0, -0.84), state=DGG.NORMAL)
        self.tap(frame, self.show, 'home')

    def say(self, text, seconds=3.0):
        if self.message is None or self.message.isEmpty():
            self.message = DirectLabel(parent=self.page, relief=DGG.FLAT, frameColor=(0.16, 0.22, 0.48, 0.92), pad=(0.05, 0.04),
                                       pos=(0, 0, -0.6), text='', text_scale=0.055, text_fg=WHITE, text_font=self.font,
                                       text_wordwrap=22, sortOrder=100)
        self.message['text'] = text
        self.message.resetFrameSize()
        self.message.show()
        self.messageUntil = globalClock.getRealTime() + seconds

    def walking(self):
        return placeState() == 'walk'

    # --- Before the game ---

    def buildNotStarted(self):
        self.label(NOT_STARTED, (0, 0, -0.03), scale=0.17, wordwrap=8, fg=WHITE, shadow=(0.1, 0.2, 0.45, 0.9))

    def buildNoToon(self):
        self.label(NO_TOON, (0, 0, -0.03), scale=0.17, wordwrap=8, fg=WHITE, shadow=(0.1, 0.2, 0.45, 0.9))

    # --- Survival Mode: round, laff, jellybeans, tonics, gags and ammo ---

    def buildSurvival(self):
        from toontown.survival import SurvivalGlobals
        from toontown.toon import LaffMeter
        game = survivalGame()
        self.paper()
        self.title('Survival', font=self.signFont)
        if game is None:
            return
        # The round on the left, the laff meter on the right.
        self.label('Round', (-0.38, 0, 0.56), scale=0.07, font=self.signFont, fg=(0.8, 0.1, 0.1, 1))
        self.roundLabel = self.label('', (-0.38, 0, 0.34), scale=0.2, font=self.signFont, fg=(0.8, 0.1, 0.1, 1))
        self.laffMeter = LaffMeter.LaffMeter(game.dna, int(game.player.hp), int(game.player.maxHp))
        self.laffMeter.reparentTo(self.page)
        self.laffMeter.setScale(0.14)
        self.laffMeter.setPos(0.33, 0, 0.44)
        self.laffMeter.start()
        # Jellybeans (the points) under them.
        beans = self.panel((0, 0, 0.13), 0.5, 0.13, CREAM)
        jar = beans.attachNewNode('jar')
        self.find('jar_gui', 'Jar').copyTo(jar)
        jar.setScale(0.18)
        jar.setPos(-0.15, -1, 0.005)
        self.beans = self.label('', (0.05, 0, -0.022), scale=0.07, parent=beans, font=self.signFont)
        # Tonics.
        tonics = self.panel((0, 0, -0.14), 1.3, 0.3, LILAC)
        self.label('Tonics', (-0.6, 0, 0.085), scale=0.05, parent=tonics, align=TextNode.ALeft, fg=SOFT)
        self.tonicLabels = [self.label('', (-0.6 + 0.65 * (i % 2), 0, -0.01 - 0.09 * (i // 2)), scale=0.05, parent=tonics,
                                       align=TextNode.ALeft) for i in range(SurvivalGlobals.TONIC_LIMIT)]
        # The gags: one row a slot, the held one lit.
        self.gagRows = []
        for i in range(SurvivalGlobals.GAG_SLOTS):
            z = -0.47 - 0.3 * i
            row = self.panel((0, 0, z), 1.3, 0.26, WHITE)
            holder = row.attachNewNode('icon')
            holder.setPos(-0.52, -1, 0)
            name = self.label('', (-0.36, 0, 0.03), scale=0.055, parent=row, align=TextNode.ALeft)
            slot = self.label('', (-0.36, 0, -0.065), scale=0.04, parent=row, align=TextNode.ALeft, fg=SOFT)
            ammo = self.label('', (0.6, 0, -0.03), scale=0.085, parent=row, align=TextNode.ARight, font=self.signFont)
            self.gagRows.append({'row': row, 'holder': holder, 'name': name, 'slot': slot, 'ammo': ammo, 'icon': None})
        self.presentLabel = self.label('', (0, 0, -0.47 - 0.3 * SurvivalGlobals.GAG_SLOTS + 0.1), scale=0.045, fg=SOFT)
        self.refreshSurvival()

    def refreshSurvival(self):
        from toontown.survival import SurvivalGlobals
        game = survivalGame()
        if game is None or not hasattr(self, 'gagRows'):
            return
        self.roundLabel['text'] = '%d' % max(1, game.roundNum)
        if self.laffMeter is not None:
            self.laffMeter.adjustFace(int(round(game.player.hp)), int(game.player.maxHp), quietly=1)
        self.beans['text'] = '%d' % int(game.beans)
        names = [name for key, name, cost, blurb in SurvivalGlobals.TONICS if key in game.tonics]
        for i, label in enumerate(self.tonicLabels):
            label['text'] = names[i] if i < len(names) else ('-' if i == 0 and not names else '')
        gags = game.gags
        for i, row in enumerate(self.gagRows):
            gag = gags.gags[i] if i < len(gags.gags) else None
            held = gag is not None and i == gags.current
            row['row']['image_color'] = GOLD if held else (WHITE if gag else (0.93, 0.93, 0.93, 1))
            if gag is None:
                row['name']['text'] = 'Empty slot'
                row['slot']['text'] = '%d' % (i + 1)
                row['ammo']['text'] = ''
                icon = None
            else:
                row['name']['text'] = gag.name
                row['slot']['text'] = ('%d  held' if held else '%d') % (i + 1)
                row['ammo']['text'] = '%d / %d' % (gag.clip, gag.reserve)
                icon = ToontownBattleGlobals.AvPropsNew[gag.track][gag.level]
            if icon != row['icon']:
                row['icon'] = icon
                row['holder'].getChildren().detach()
                if icon is not None:
                    picture = self.find('inventory_icons', icon)
                    picture.copyTo(row['holder'])
                    row['holder'].setScale(1.1)
        gifts = getattr(gags, 'presentations', 0)
        self.presentLabel['text'] = ('Presentations: %d' % gifts) if gifts else ''

    # --- The laff meter page ---

    def buildHome(self):
        from toontown.toon import LaffMeter
        avatar = base.localAvatar
        self.paper()
        self.nameLabel = self.label(avatar.getName(), (0, 0, 0.885), scale=0.085, font=ToontownGlobals.getToonFont())
        self.laffMeter = LaffMeter.LaffMeter(avatar.style, avatar.hp, avatar.maxHp)
        self.laffMeter.setAvatar(avatar)
        self.laffMeter.reparentTo(self.page)
        self.laffMeter.setScale(0.17)
        self.laffMeter.start()
        self.laffMeter.setPos(0.0, 0, 0.58)
        self.accept('toonLookChanged', self.rebuild)
        beans = self.panel((0, 0, 0.22), 0.38, 0.13, CREAM, touchable=True)
        jar = beans.attachNewNode('jar')
        self.find('jar_gui', 'Jar').copyTo(jar)
        jar.setScale(0.18)
        jar.setPos(-0.075, -1, 0.005)
        self.beans = self.label('', (0.055, 0, -0.02), scale=0.065, parent=beans)
        self.tap(beans, self.show, 'progress')
        # Each icon is centered by its model's bounds, then moved by the
        # measured offset of its drawn picture (ICON_NUDGES), so the picture
        # sits in the middle of its square.
        tiles = ((GOLD, self.find('inventory_icons', 'inventory_tart'), 1.25, 'gags'),
                 (SKY, self.find('stickerbook_gui', 'questCard'), 0.17, 'tasks'),
                 (MINT, self.find('sos_textures', 'teleportIcon'), 0.18, 'map'),
                 (LILAC, self.find('sos_textures', 'district'), 0.18, 'districts'),
                 (ROSE, self.find('stickerbook_gui', 'BookIcon_CLSD'), 0.34, None),
                 (PINK, self.find('friendslist_gui', 'FriendsBox_Closed'), 0.6, 'friends'),
                 (SKY, self.chatIcon(), 0.9, 'chat'),
                 (GOLD, self.find('stickerbook_gui', 'CogArmIcon2'), 0.2, 'progress'),
                 (MINT, self.find('sos_textures', 'gui_gear'), 0.16, 'help'))
        self.extras = self.page.attachNewNode('extras')
        self.battleRow = self.page.attachNewNode('battle')
        for i, (tint, icon, scale, name) in enumerate(tiles):
            row, column = divmod(i, 3)
            pos = ((column - 1) * GRID, 0, -0.02 - row * GRID)
            nudge = ICON_NUDGES.get(name or 'book', (0, 0))
            if row:
                page, self.page = self.page, self.extras
            if name:
                self.iconTile(pos, tint, icon, scale, self.show, name, nudge=nudge)
            else:
                self.iconTile(pos, tint, icon, scale, self.openBook, nudge=nudge)
            if row:
                self.page = page
        self.battleShown = None
        self.refreshHome()

    def chatIcon(self):
        # A SpeedChat balloon saying Hi!.
        icon = NodePath('chatIcon')
        balloon = loader.loadModel('phase_3/models/props/chatbox')
        balloon.reparentTo(icon)
        low, high = balloon.getTightBounds()
        size = 0.2 / max(0.001, high[0] - low[0])
        balloon.setScale(size, 1, size * 1.3)
        balloon.setPos(-(low[0] + high[0]) / 2 * size, 0, -(low[2] + high[2]) / 2 * size * 1.3)
        text = TextNode('hi')
        text.setText('Hi!')
        text.setFont(self.font)
        text.setAlign(TextNode.ACenter)
        text.setTextColor(0, 0, 0, 1)
        textNode = icon.attachNewNode(text)
        textNode.setScale(0.06)
        textNode.setPos(0, -0.1, 0.0)
        return icon

    def rebuild(self):
        if self.pageName == 'home':
            self.show('home')

    def refreshHome(self):
        avatar = base.localAvatar
        self.beans['text'] = '%d' % avatar.getMoney()
        battle = currentBattle() if placeState() == 'battle' else None
        inBattle = battle is not None
        if inBattle != self.battleShown or inBattle:
            self.battleShown = inBattle
            if inBattle:
                self.extras.hide()
                self.buildBattleRow(battle)
            else:
                self.extras.show()
                self.battleRow.getChildren().detach()
                self.taps = [tap for tap in self.taps if not tap.node.isEmpty() and tap.node.hasParent()]

    def buildBattleRow(self, battle):
        from toontown.npcplayers import NPCFriends
        self.battleRow.getChildren().detach()
        self.taps = [tap for tap in self.taps if not tap.node.isEmpty() and tap.node.hasParent()]
        page, self.page = self.page, self.battleRow
        suits = [suit for suit in getattr(battle, 'activeSuits', []) if suit is not None and not suit.isEmpty()]
        suits = suits[:4]
        height = 0.16 + 0.09 * max(1, len(suits))
        box = self.panel((0, 0, -0.22 - height / 2.0), 1.36, height, CREAM)
        self.label('Cogs', (0, 0, height / 2.0 - 0.075), scale=0.06, parent=box)
        for i, suit in enumerate(suits):
            z = height / 2.0 - 0.15 - i * 0.09
            hp, maxHp = getattr(suit, 'currHP', 0), max(1, getattr(suit, 'maxHP', 1))
            name = '%s (level %d)' % (suit.getName(), suit.getActualLevel()) if hasattr(suit, 'getActualLevel') else suit.getName()
            self.label(name, (-0.62, 0, z - 0.015), scale=0.048, parent=box, align=TextNode.ALeft)
            DirectFrame(parent=box, relief=DGG.FLAT, frameColor=(0.75, 0.75, 0.78, 1), frameSize=(0, 0.36, -0.022, 0.022), pos=(0.1, 0, z))
            fraction = max(0.0, min(1.0, hp / float(maxHp)))
            color = (0.3, 0.8, 0.3, 1) if fraction > 0.5 else (0.95, 0.75, 0.15, 1) if fraction > 0.25 else (0.9, 0.25, 0.2, 1)
            DirectFrame(parent=box, relief=DGG.FLAT, frameColor=color, frameSize=(0, 0.36 * fraction, -0.022, 0.022), pos=(0.1, 0, z))
            self.label('%d/%d' % (hp, maxHp), (0.62, 0, z - 0.013), scale=0.04, parent=box, align=TextNode.ARight)
        if NPCFriends.needHelpAvailable():
            self.textButton('Need Help!', (0, 0, -0.8), self.needHelp, width=0.62, height=0.15, textScale=0.065, tint=ROSE)
        self.page = page

    def needHelp(self):
        from toontown.npcplayers import NPCFriends
        if NPCFriends.needHelp():
            self.say('Help is on the way!')

    def openBook(self):
        """The book button opens the Shticker Book on the top screen, and
        closes it again while it is open."""
        book = getattr(base.localAvatar, 'book', None)
        if book is None:
            return
        if placeState() == 'stickerBook' or not book.bookCloseButton.isHidden():
            command = book.bookCloseButton['command']
            if command is not None:
                command()
            return
        if not self.walking():
            self.say('Stop walking around first, then open the book.')
            return
        book.bookOpenButton['command']()

    # --- Gags ---

    def buildGags(self):
        self.paper()
        self.title('Gags')
        self.backButton()
        self.gagLabels = []
        avatar = base.localAvatar
        inventory = avatar.inventory
        rows = len(ToontownBattleGlobals.Tracks)
        levels = len(ToontownBattleGlobals.Levels[0])
        cell = min((CONTENT + 0.04) * 2 / levels, 1.4 / rows)
        pitch = 1.44 / rows
        top = 0.57
        for track in range(rows):
            z = top - pitch * track
            hasTrack = avatar.hasTrackAccess(track)
            color = ToontownBattleGlobals.TrackColors[track]
            tint = tuple(0.45 + 0.55 * c for c in color[:3]) + ((1,) if hasTrack else (0.35,))
            self.panel((0, 0, z), cell * levels + 0.04, pitch * 0.94, tint)
            for level in range(levels):
                x = cell * (level - (levels - 1) / 2.0)
                icon = self.find('inventory_icons', ToontownBattleGlobals.AvPropsNew[track][level])
                holder = self.page.attachNewNode('gag')
                icon.copyTo(holder)
                holder.setPos(x, 0, z + pitch * 0.1)
                holder.setScale(cell * 5.6)
                if not hasTrack or level >= inventory.getMax(track, level) and inventory.numItem(track, level) == 0 and not avatar.experience.getExpLevel(track) >= level:
                    holder.setColorScale(1, 1, 1, 0.25)
                label = self.label('', (x, 0, z - pitch * 0.4), scale=cell * 0.3)
                self.gagLabels.append((label, track, level, hasTrack))
        self.refreshGags()

    def refreshGags(self):
        avatar = base.localAvatar
        inventory = avatar.inventory
        for label, track, level, hasTrack in self.gagLabels:
            if hasTrack and avatar.experience.getExpLevel(track) >= level:
                label['text'] = '%d' % inventory.numItem(track, level)
            else:
                label['text'] = ''

    # --- ToonTasks ---

    def buildTasks(self):
        self.paper()
        self.title('ToonTasks')
        self.backButton()
        holder = self.page.attachNewNode('tasks')
        holder.setPos(0, 0, -0.02)
        holder.setScale(min(1.0, CONTENT * 2 / 1.8 * BIG))
        for frame in base.localAvatar.questPage.questFrames:
            frame.instanceTo(holder)
        if not base.localAvatar.quests:
            self.label('No ToonTasks right now.', (0, 0, -0.7), scale=0.06 * BIG)

    # --- Maps ---

    def buildMap(self):
        questMap = getattr(base.localAvatar, 'questMap', None)
        if questMap is None or not questMap.container['image']:
            self.show('world')
            return
        place = currentPlace()
        zoneId = place.getZoneId() if place is not None and hasattr(place, 'getZoneId') else 0
        streetName = ToontownGlobals.StreetNames.get(ZoneUtil.getCanonicalBranchZone(zoneId), ('',))[-1]
        self.paper()
        self.title(streetName)
        self.backButton()
        holder = self.page.attachNewNode('streetMap')
        holder.setScale(min(CONTENT * 2, 1.3) * BIG)
        holder.setPos(0, 0, 0.02)
        questMap.container.instanceTo(holder)
        self.textButton('World Map', (0.12, 0, -0.84), self.show, 'world', width=0.62 * BIG, height=0.14 * BIG, textScale=0.055 * BIG, tint=MINT)

    def buildWorld(self):
        self.paper()
        self.title('Toontown')
        self.backButton()
        scale = CONTENT * 2 / 1.8 * 1.07
        world = DirectFrame(parent=self.page, relief=None, image=self.find('toontown_map', 'toontown_map'),
                            image_scale=(1.8, 1, 1.35), scale=scale, pos=(0, 0, 0.12))
        allZones = [hood for hood in ToontownGlobals.Hoods if hood not in (ToontownGlobals.GolfZone, ToontownGlobals.ToonFest)]
        positions, clouds, cloudScales = MAP_LABELS, MAP_CLOUDS, MAP_CLOUD_SCALES
        visited = set(base.localAvatar.hoodsVisited) & set(base.cr.hoodMgr.getAvailableZones())
        access = base.localAvatar.getTeleportAccess()
        cloud = self.find('cloud', 'cloud')
        for index, hood in enumerate(allZones):
            if index >= len(positions):
                break
            if hood in visited:
                name = base.cr.hoodMgr.getFullnameFromId(hood)
                canGo = hood in access
                label = DirectLabel(parent=world, relief=DGG.FLAT, pad=(0.03, 0.02), frameColor=(1, 1, 1, 0.8) if canGo else (0.8, 0.8, 0.8, 0.55),
                                    pos=positions[index], text=name, text_scale=0.065, text_wordwrap=7, text_fg=INK if canGo else (0.35, 0.35, 0.35, 1),
                                    text_font=self.font, state=DGG.NORMAL)
                if canGo:
                    self.tap(label, self.teleport, hood)
            else:
                for cloudScale, cloudPos in zip(cloudScales[index], clouds[index]):
                    DirectFrame(parent=world, relief=None, image=cloud, scale=cloudScale, pos=cloudPos)
        place = currentPlace()
        zoneId = place.getZoneId() if place is not None and hasattr(place, 'getZoneId') else 0
        hoodName = ToontownGlobals.hoodNameMap.get(ZoneUtil.getCanonicalHoodId(zoneId), ('',))[-1]
        if hoodName:
            self.label('You are in %s.\nTap a place to go there.' % hoodName, (0, 0, -0.57), scale=0.05 * BIG)

    def teleport(self, hood):
        if not self.walking():
            self.say('Stop walking around first, then pick where to go.')
            return
        place = currentPlace()
        base.localAvatar.sendUpdate('checkTeleportAccess', [hood])
        place.requestTeleport(hood, hood, None, -1)
        self.show('home')

    # --- Districts ---

    def buildDistricts(self):
        self.paper()
        self.title('Districts')
        self.backButton()
        self.districtRows = None
        self.refreshDistricts()

    def refreshDistricts(self):
        shards = sorted(base.cr.listActiveShards(), key=lambda shard: shard[1])
        rows = [(shard[0], shard[1], shard[2]) for shard in shards]
        current = base.localAvatar.defaultShard
        key = (tuple(rows), current)
        if key == self.districtRows:
            return
        self.districtRows = key
        if getattr(self, 'districtList', None) is not None:
            self.districtList.removeNode()
        self.taps = [tap for tap in self.taps if not tap.node.isEmpty() and tap.node.hasParent()]
        page, self.page = self.page, self.page.attachNewNode('districts')
        self.districtList = self.page
        rowHeight = min(0.19, 1.3 / max(1, len(rows)))
        for i, (shardId, name, population) in enumerate(rows):
            z = 0.59 - rowHeight * i
            here = shardId == current
            row = self.panel((0, 0, z), (CONTENT + 0.03) * 2, rowHeight * 0.86, GOLD if here else WHITE, touchable=not here)
            self.label(name, (-CONTENT + 0.04, 0, -0.022), scale=min(0.066, rowHeight * 0.38), parent=row, align=TextNode.ALeft)
            self.label('You are here' if here else '%d toons' % population, (CONTENT - 0.04, 0, -0.02),
                       scale=min(0.053, rowHeight * 0.3), fg=SOFT, parent=row, align=TextNode.ARight)
            if not here:
                self.tap(row, self.switchDistrict, shardId, name)
        self.page = page

    def switchDistrict(self, shardId, name):
        if not self.walking():
            self.say('Stop walking around first, then pick a district.')
            return
        place = currentPlace()
        hoodId = ZoneUtil.getCanonicalHoodId(base.localAvatar.lastHood)
        place.requestTeleport(hoodId, hoodId, shardId, -1)
        self.show('home')

    # --- NPC friends ---

    def buildFriends(self):
        self.paper()
        self.title('Friends')
        self.backButton()
        self.friendRows = None
        self.refreshFriends()

    def refreshFriends(self):
        from toontown.npcplayers import NPCFriends
        friends = [doId for doId in NPCFriends.npcFriends() if doId in base.cr.doId2do]
        names = tuple((doId, base.cr.doId2do[doId].getName()) for doId in friends[:8])
        if names == self.friendRows:
            return
        self.friendRows = names
        if getattr(self, 'friendList', None) is not None:
            self.friendList.removeNode()
        self.taps = [tap for tap in self.taps if not tap.node.isEmpty() and tap.node.hasParent()]
        page, self.page = self.page, self.page.attachNewNode('friends')
        self.friendList = self.page
        if not names:
            self.label('No toons around right now.', (0, 0, 0.2), scale=0.065 * BIG)
        for i, (doId, name) in enumerate(names):
            z = 0.6 - 0.168 * i
            row = self.panel((0, 0, z), (CONTENT + 0.03) * 2, 0.15, WHITE, touchable=True)
            self.label(name, (-CONTENT + 0.04, 0, -0.022), scale=0.064, parent=row, align=TextNode.ALeft)
            self.label('Ask for help', (CONTENT - 0.04, 0, -0.02), scale=0.05, fg=(0.15, 0.5, 0.2, 1), parent=row,
                       align=TextNode.ARight)
            self.tap(row, self.summon, doId, name)
        self.page = page

    def summon(self, doId, name):
        from toontown.npcplayers import NPCFriends
        if NPCFriends.whispered(doId):
            self.say('%s is on the way!' % name)
        else:
            self.say('%s can\'t come right now.' % name)

    # --- Quick chat ---

    def buildChat(self):
        from otp.otpbase import OTPLocalizer
        self.paper()
        self.title('Quick Chat')
        self.backButton()
        for i, (index, text) in enumerate(SPEEDCHAT):
            x = (i % 2 - 0.5) * 0.74
            z = 0.58 - (i // 2) * 0.2
            self.textButton(text, (x, 0, z), self.speak, index, width=0.7, height=0.16, textScale=0.056)
        self.label('Emotes', (0, 0, -0.08), scale=0.077)
        DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=RULE, frameSize=(-0.3, 0.3, -0.003, 0.003), pos=(0, 0, -0.125))
        for i, name in enumerate(EMOTES):
            emoteId = OTPLocalizer.EmoteFuncDict.get(name)
            x = (i % 2 - 0.5) * 0.74
            z = -0.27 - (i // 2) * 0.2
            self.textButton(name, (x, 0, z), self.emote, emoteId, width=0.7, height=0.16, textScale=0.056, tint=SKY)

    def speak(self, index):
        base.talkAssistant.sendOpenSpeedChat(1, index)

    def emote(self, emoteId):
        from otp.avatar import Emote
        avatar = base.localAvatar
        if emoteId is None or not avatar.emoteAccess[emoteId]:
            self.say('Your toon doesn\'t know that emote yet.')
        elif not Emote.globalEmote.isEnabled(emoteId):
            self.say('You can\'t do that right now.')
        else:
            base.talkAssistant.sendOpenSpeedChat(2, emoteId)

    # --- Jellybeans and Cog suits ---

    def buildProgress(self):
        from toontown.battle import SuitBattleGlobals
        from toontown.coghq import CogDisguiseGlobals
        from toontown.suit import SuitDNA
        from toontown.toonbase import TTLocalizer
        avatar = base.localAvatar
        self.paper()
        self.title('Progress')
        self.backButton()
        wide = CONTENT + 0.03
        box = self.panel((0, 0, 0.52), wide * 2, 0.33, CREAM)
        jar = box.attachNewNode('jar')
        self.find('jar_gui', 'Jar').copyTo(jar)
        jar.setScale(0.33)
        jar.setPos(-wide + 0.17, -1, 0)
        left = -wide + 0.34
        self.label('Jellybeans: %d of %d' % (avatar.getMoney(), avatar.getMaxMoney()), (left, 0, 0.07), scale=0.06, parent=box, align=TextNode.ALeft)
        self.label('In the bank: %d' % avatar.getBankMoney(), (left, 0, -0.02), scale=0.055, fg=SOFT, parent=box, align=TextNode.ALeft)
        self.label('Laff: %d of %d' % (avatar.hp, avatar.maxHp), (left, 0, -0.11), scale=0.055, fg=SOFT, parent=box, align=TextNode.ALeft)
        icons = ('CorpIcon', 'LegalIcon', 'MoneyIcon', 'SalesIcon')
        for index, dept in enumerate(SuitDNA.suitDepts):
            z = 0.195 - index * 0.25
            row = self.panel((0, 0, z), wide * 2, 0.225, WHITE)
            holder = row.attachNewNode('dept')
            self.find('cog_icons', icons[index]).copyTo(holder)
            holder.setPos(-wide + 0.14, -1, 0)
            holder.setScale(0.155)
            deptName = SuitDNA.getDeptFullname(dept)
            parts = avatar.cogParts[index]
            if CogDisguiseGlobals.isSuitComplete(avatar.cogParts, dept):
                cogIndex = avatar.cogTypes[index] + SuitDNA.suitsPerDept * index
                cogName = SuitBattleGlobals.SuitAttributes[SuitDNA.suitHeadTypes[cogIndex]]['name']
                total = CogDisguiseGlobals.getTotalMerits(avatar, index)
                first = '%s  level %d' % (cogName, avatar.cogLevels[index] + 1)
                if total:
                    second = '%s %d of %d' % (TTLocalizer.RewardPanelMeritBarLabels[index], avatar.cogMerits[index], total)
                else:
                    second = 'Top level: ready for the boss!'
            else:
                first = deptName
                second = 'Suit parts: %d of %d' % (CogDisguiseGlobals.getTotalParts(parts), CogDisguiseGlobals.PartsPerSuit[index])
            self.label(first, (-wide + 0.29, 0, 0.02), scale=0.057, parent=row, align=TextNode.ALeft)
            self.label(second, (-wide + 0.29, 0, -0.065), scale=0.05, fg=SOFT, parent=row, align=TextNode.ALeft)

    # --- How the other toons help ---

    def buildHelp(self):
        from toontown.npcplayers import NPCSetupPanel
        self.paper()
        self.title('Setup')
        self.backButton()
        self.label(NPCSetupPanel.HEADING, (0, 0, 0.61), scale=0.058, wordwrap=24)
        self.helpButtons = {}
        for i, (mode, name, blurb) in enumerate(NPCSetupPanel.CHOICES):
            z = 0.34 - i * 0.39
            self.helpButtons[mode] = self.textButton(name, (0, 0, z), self.pickHelp, mode, width=0.9, height=0.17, textScale=0.066)
            self.label(blurb, (0, 0, z - 0.15), scale=0.047, fg=SOFT, wordwrap=30)
        self.showHelpPicked()

    def pickHelp(self, mode):
        from toontown.npcplayers import NPCSettings
        settings = getattr(getattr(base, 'display', None), 'settings', None)
        NPCSettings.setHelpMode(mode, settings)
        self.showHelpPicked()

    def showHelpPicked(self):
        from toontown.npcplayers import NPCSettings
        mode = NPCSettings.helpMode()
        for name, button in self.helpButtons.items():
            button['image_color'] = MINT if name == mode else WHITE


_rounded = {}


def roundedTexture(ratio):
    """A white rounded card with a soft blue-grey edge, ratio wide for 1 high."""
    ratio = max(0.2, round(ratio, 1))
    if ratio in _rounded:
        return _rounded[ratio]
    height = 64
    width = max(8, int(round(height * ratio)))
    image = PNMImage(width, height, 4)
    radius, edge, lip = height * 0.2, height * 0.045, height * 0.05
    for y in range(height):
        for x in range(width):
            px, py = x + 0.5, y + 0.5
            outside = roundedBox(px, py, width, height, radius)
            # The face sits a little higher than the edge, like a button.
            face = roundedBox(px, py + lip, width, height + lip, radius) if py < height - lip else outside + lip
            alpha = min(1.0, max(0.0, 0.5 - outside))
            mix = min(1.0, max(0.0, face + edge + 0.5))
            shade = 1.0 - 0.06 * py / height
            for channel, low in enumerate(EDGE):
                value = shade * (1 - mix) + low * mix
                [image.setRed, image.setGreen, image.setBlue][channel](x, y, value)
            image.setAlpha(x, y, alpha)
    texture = Texture('rounded%s' % ratio)
    texture.load(image)
    texture.setMinfilter(Texture.FTLinear)
    texture.setMagfilter(Texture.FTLinear)
    texture.setWrapU(Texture.WMClamp)
    texture.setWrapV(Texture.WMClamp)
    _rounded[ratio] = texture
    return texture


def roundedBox(px, py, width, height, radius):
    """How far (px, py) is outside a rounded box (negative inside)."""
    qx = abs(px - width / 2.0) - (width / 2.0 - radius)
    qy = abs(py - height / 2.0) - (height / 2.0 - radius)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
