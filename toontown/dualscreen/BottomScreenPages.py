"""What the bottom screen of a dual-screen handheld shows (see SecondScreen).

Before PLAY!: "Game Not Started". After it, until a toon is playing: "Toon
Not Selected". Then the toon's own laff meter, with buttons (the game's own
icons) for the gags, the ToonTasks, the map, the districts and the Shticker
Book (which opens on the top screen), and below them the NPC friends, quick
SpeedChat and emotes, jellybeans and Cog suit progress, and how the other
toons help. In a battle that row is the Cogs' laff and Need Help!.

Every page but the first has a Back arrow to the laff meter.
"""

from direct.directnotify import DirectNotifyGlobal
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase.DirectObject import DirectObject
from panda3d.core import NodePath, Point3, TextNode

from toontown.hood import ZoneUtil
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals

notify = DirectNotifyGlobal.directNotify.newCategory('BottomScreen')

WHITE = (1, 1, 1, 1)
SHADOW = (0, 0, 0, 0.6)
DARK = (0.12, 0.18, 0.4, 1)
PANEL = (1, 1, 1, 0.85)
NOT_STARTED = 'Game Not Started'
NO_TOON = 'Toon Not Selected'
SQUARES = ('Red', 'Green', 'Purple', 'Blue', 'Pink', 'Yellow')
SPEEDCHAT = ((100, 'Hi!'), (102, 'Hello!'), (300, 'Yay!'), (500, 'Thanks!'), (511, 'Can you help me?'), (200, 'Bye!'))
EMOTES = ('Wave', 'Happy', 'Dance', 'Laugh')
REFRESH = 1.0
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


def currentPlace():
    try:
        return base.cr.playGame.getPlace()
    except AttributeError:
        return None


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
        stage = currentStage()
        if stage != self.stage:
            self.stage = stage
            self.show({'notStarted': 'notStarted', 'noToon': 'noToon'}.get(stage, 'home'))
            return
        if stage != 'game':
            return
        now = globalClock.getRealTime()
        if self.message is not None and now >= self.messageUntil and not self.message.isEmpty():
            self.message.hide()
        if now - self.lastRefresh >= REFRESH:
            self.lastRefresh = now
            refresh = getattr(self, 'refresh' + self.pageName[0].upper() + self.pageName[1:], None)
            if refresh is not None:
                refresh()

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

    def label(self, text, pos, scale=0.07, fg=WHITE, parent=None, font=None, wordwrap=None, align=TextNode.ACenter, shadow=SHADOW):
        args = dict(parent=parent or self.page, relief=None, pos=pos, text=text, text_scale=scale, text_fg=fg,
                    text_font=font or self.font, text_align=align, text_shadow=shadow)
        if wordwrap:
            args['text_wordwrap'] = wordwrap
        return DirectLabel(**args)

    def tap(self, node, command, *args):
        self.taps.append(Tap(node, command, args))
        return node

    def iconButton(self, pos, square, icon, iconScale, command, *args, size=0.3):
        frame = DirectFrame(parent=self.page, relief=None, image=self.find('tt_m_gui_pat_mainGui', 'tt_t_gui_pat_square' + square),
                            image_scale=size * 1.18, pos=pos, state=DGG.NORMAL)
        if icon is not None:
            holder = frame.attachNewNode('icon')
            icon.copyTo(holder)
            holder.setScale(iconScale)
            holder.setY(-1)
        return self.tap(frame, command, *args)

    def textButton(self, text, pos, command, *args, scale=(1.0, 1, 1.0), textScale=0.06, color=(1, 1, 1, 1), width=None):
        images = (self.find('quit_button', 'QuitBtn_UP'), self.find('quit_button', 'QuitBtn_DN'), self.find('quit_button', 'QuitBtn_RLVR'))
        frame = DirectFrame(parent=self.page, relief=None, image=images[0], image_scale=scale, image_color=color, pos=pos,
                            text=text, text_scale=textScale, text_pos=(0, -0.018), text_fg=WHITE, text_shadow=SHADOW,
                            text_font=self.font, state=DGG.NORMAL)
        return self.tap(frame, command, *args)

    def title(self, text):
        self.label(text, (0, 0, 0.86), scale=0.11, font=self.signFont, fg=(1, 0.92, 0.2, 1), shadow=(0.2, 0.2, 0.5, 1))

    def backButton(self):
        arrow = self.find('tt_m_gui_mat_mainGui', 'tt_t_gui_mat_nextUp')
        frame = DirectFrame(parent=self.page, relief=None, image=arrow, image_scale=(-0.55, 0.55, 0.55),
                            pos=(-self.width + 0.17, 0, -0.86), state=DGG.NORMAL)
        self.tap(frame, self.show, 'home')

    def say(self, text, seconds=3.0):
        if self.message is None or self.message.isEmpty():
            self.message = DirectLabel(parent=self.page, relief=DGG.FLAT, frameColor=(0.1, 0.15, 0.35, 0.85), pad=(0.04, 0.03),
                                       pos=(0, 0, -0.68), text='', text_scale=0.06, text_fg=WHITE, text_font=self.font,
                                       text_wordwrap=22, sortOrder=100)
        self.message['text'] = text
        self.message.resetFrameSize()
        self.message.show()
        self.messageUntil = globalClock.getRealTime() + seconds

    def walking(self):
        return placeState() == 'walk'

    # --- Before the game ---

    def buildNotStarted(self):
        self.label(NOT_STARTED, (0, 0, -0.03), scale=0.17, wordwrap=8, shadow=(0.1, 0.2, 0.45, 0.9))

    def buildNoToon(self):
        self.label(NO_TOON, (0, 0, -0.03), scale=0.17, wordwrap=8, shadow=(0.1, 0.2, 0.45, 0.9))

    # --- The laff meter page ---

    def buildHome(self):
        from toontown.toon import LaffMeter
        avatar = base.localAvatar
        self.nameLabel = self.label(avatar.getName(), (0, 0, 0.87), scale=0.08, font=ToontownGlobals.getToonFont())
        self.laffMeter = LaffMeter.LaffMeter(avatar.style, avatar.hp, avatar.maxHp)
        self.laffMeter.setAvatar(avatar)
        self.laffMeter.reparentTo(self.page)
        self.laffMeter.setScale(0.2)
        self.laffMeter.setPos(-0.12, 0, 0.5)
        self.laffMeter.start()
        self.accept('toonLookChanged', self.rebuild)
        jar = self.find('jar_gui', 'Jar')
        self.beans = DirectLabel(parent=self.page, relief=None, image=jar, image_scale=0.45, image_pos=(0, 0, 0.03),
                                 pos=(self.width - 0.2, 0, 0.55), text='', text_scale=0.065, text_pos=(0, -0.17), text_fg=WHITE,
                                 text_shadow=SHADOW, text_font=self.font)
        self.tap(self.beans, self.show, 'progress')
        icons = (('Yellow', self.find('inventory_icons', 'inventory_tart'), 1.35, 'gags'),
                 ('Blue', self.find('stickerbook_gui', 'questCard'), 0.19, 'tasks'),
                 ('Green', self.find('sos_textures', 'teleportIcon'), 0.2, 'map'),
                 ('Purple', self.find('sos_textures', 'district'), 0.2, 'districts'),
                 ('Red', self.find('stickerbook_gui', 'BookIcon_CLSD'), 0.3, None))
        spacing = (self.width * 2 - 0.12) / 5
        for i, (square, icon, scale, page) in enumerate(icons):
            x = -self.width + 0.06 + spacing * (i + 0.5)
            if page:
                self.iconButton((x, 0, 0.08), square, icon, scale, self.show, page, size=spacing * 0.92)
            else:
                self.iconButton((x, 0, 0.08), square, icon, scale, self.openBook, size=spacing * 0.92)
        self.extras = self.page.attachNewNode('extras')
        self.battleRow = self.page.attachNewNode('battle')
        self.buildExtras()
        self.battleShown = None
        self.refreshHome()

    def buildExtras(self):
        page, self.page = self.page, self.extras
        icons = (('Pink', self.find('friendslist_gui', 'FriendsBox_Closed'), 0.5, 'friends'),
                 ('Blue', self.chatIcon(), 1.0, 'chat'),
                 ('Yellow', self.find('sos_textures', 'disguise2'), 0.2, 'progress'),
                 ('Green', self.find('sos_textures', 'gui_gear'), 0.18, 'help'))
        spacing = (self.width * 2 - 0.3) / 4
        for i, (square, icon, scale, name) in enumerate(icons):
            x = -self.width + 0.15 + spacing * (i + 0.5)
            self.iconButton((x, 0, -0.38), square, icon, scale, self.show, name, size=spacing * 0.8)
        self.page = page

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
        self.label('Cogs', (0, 0, -0.2), scale=0.065)
        for i, suit in enumerate(suits[:4]):
            z = -0.3 - i * 0.1
            hp, maxHp = getattr(suit, 'currHP', 0), max(1, getattr(suit, 'maxHP', 1))
            name = '%s (level %d)' % (suit.getName(), suit.getActualLevel()) if hasattr(suit, 'getActualLevel') else suit.getName()
            self.label(name, (-self.width + 0.08, 0, z), scale=0.05, align=TextNode.ALeft)
            bar = DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=(0.2, 0.2, 0.2, 0.8),
                              frameSize=(0, 0.5, -0.025, 0.025), pos=(self.width - 0.58, 0, z + 0.012))
            fraction = max(0.0, min(1.0, hp / float(maxHp)))
            color = (0.2, 0.9, 0.2, 1) if fraction > 0.5 else (1, 0.8, 0.1, 1) if fraction > 0.25 else (1, 0.2, 0.15, 1)
            DirectFrame(parent=bar, relief=DGG.FLAT, frameColor=color, frameSize=(0, 0.5 * fraction, -0.025, 0.025))
            self.label('%d/%d' % (hp, maxHp), (self.width - 0.33, 0, z - 0.012), scale=0.04, parent=bar.getParent())
        if NPCFriends.needHelpAvailable():
            self.textButton('Need Help!', (0, 0, -0.74), self.needHelp, scale=(1.3, 1, 1.5), textScale=0.065)
        self.page = page

    def needHelp(self):
        from toontown.npcplayers import NPCFriends
        if NPCFriends.needHelp():
            self.say('Help is on the way!')

    def openBook(self):
        book = getattr(base.localAvatar, 'book', None)
        if book is None or not self.walking():
            self.say('Stop walking around first, then open the book.')
            return
        book.bookOpenButton['command']()

    # --- Gags ---

    def buildGags(self):
        self.title('Gags')
        self.backButton()
        self.gagLabels = []
        avatar = base.localAvatar
        inventory = avatar.inventory
        rows = len(ToontownBattleGlobals.Tracks)
        levels = len(ToontownBattleGlobals.Levels[0])
        cell = min((self.width * 2 - 0.1) / levels, 1.45 / rows)
        top = 0.66
        for track in range(rows):
            z = top - cell * track
            hasTrack = avatar.hasTrackAccess(track)
            color = ToontownBattleGlobals.TrackColors[track]
            DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=(color[0], color[1], color[2], 0.85 if hasTrack else 0.25),
                        frameSize=(-self.width + 0.04, self.width - 0.04, -cell * 0.47, cell * 0.47), pos=(0, 0, z))
            for level in range(levels):
                x = -self.width + 0.05 + cell * (level + 0.5)
                icon = self.find('inventory_icons', ToontownBattleGlobals.AvPropsNew[track][level])
                holder = self.page.attachNewNode('gag')
                icon.copyTo(holder)
                holder.setPos(x, 0, z + cell * 0.08)
                holder.setScale(cell * 5.2)
                if not hasTrack or level >= inventory.getMax(track, level) and inventory.numItem(track, level) == 0 and not avatar.experience.getExpLevel(track) >= level:
                    holder.setColorScale(1, 1, 1, 0.25)
                label = self.label('', (x, 0, z - cell * 0.4), scale=cell * 0.26)
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
        self.title('ToonTasks')
        self.backButton()
        holder = self.page.attachNewNode('tasks')
        holder.setPos(0, 0, 0.0)
        scale = min(1.0, (self.width * 2 - 0.04) / 1.8)
        holder.setScale(scale)
        for frame in base.localAvatar.questPage.questFrames:
            frame.instanceTo(holder)
        if not base.localAvatar.quests:
            self.label('No ToonTasks right now.', (0, 0, -0.7), scale=0.065)

    # --- Maps ---

    def buildMap(self):
        questMap = getattr(base.localAvatar, 'questMap', None)
        if questMap is None or not questMap.container['image']:
            self.show('world')
            return
        place = currentPlace()
        zoneId = place.getZoneId() if place is not None and hasattr(place, 'getZoneId') else 0
        streetName = ToontownGlobals.StreetNames.get(ZoneUtil.getCanonicalBranchZone(zoneId), ('',))[-1]
        self.label(streetName, (0, 0, 0.86), scale=0.085, font=self.signFont, fg=(1, 0.92, 0.2, 1), shadow=(0.2, 0.2, 0.5, 1))
        self.backButton()
        holder = self.page.attachNewNode('streetMap')
        size = min(self.width * 2 - 0.08, 1.45)
        holder.setScale(size)
        holder.setPos(0, 0, 0.08)
        questMap.container.instanceTo(holder)
        icon = self.find('toontown_map', 'toontown_map')
        frame = DirectFrame(parent=self.page, relief=None, image=icon, image_scale=(0.27, 1, 0.2), pos=(self.width - 0.24, 0, -0.84),
                            state=DGG.NORMAL, text='World Map', text_scale=0.05, text_pos=(0, -0.15), text_fg=WHITE,
                            text_shadow=SHADOW, text_font=self.font)
        self.tap(frame, self.show, 'world')

    def buildWorld(self):
        self.title('Toontown')
        self.backButton()
        scale = (self.width * 2 - 0.06) / 1.8
        world = DirectFrame(parent=self.page, relief=None, image=self.find('toontown_map', 'toontown_map'),
                            image_scale=(1.8, 1, 1.35), scale=scale, pos=(0, 0, 0.07))
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
                label = DirectLabel(parent=world, relief=DGG.FLAT, pad=(0.03, 0.02), frameColor=(1, 1, 1, 0.75) if canGo else (0.8, 0.8, 0.8, 0.55),
                                    pos=positions[index], text=name, text_scale=0.06, text_wordwrap=7, text_fg=DARK if canGo else (0.35, 0.35, 0.35, 1),
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
            self.label('You are in %s. Tap a place to go there.' % hoodName, (0, 0, -0.62), scale=0.05, wordwrap=26)

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
        rowHeight = min(0.2, 1.45 / max(1, len(rows)))
        for i, (shardId, name, population) in enumerate(rows):
            z = 0.66 - rowHeight * i
            here = shardId == current
            row = DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=(1, 0.95, 0.5, 0.95) if here else PANEL,
                              frameSize=(-self.width + 0.06, self.width - 0.06, -rowHeight * 0.44, rowHeight * 0.44), pos=(0, 0, z),
                              state=DGG.NORMAL)
            self.label(name, (-self.width + 0.12, 0, -0.02), scale=min(0.07, rowHeight * 0.4), fg=DARK, parent=row, align=TextNode.ALeft, shadow=None)
            self.label('You are here' if here else '%d toons' % population, (self.width - 0.12, 0, -0.02),
                       scale=min(0.055, rowHeight * 0.32), fg=DARK, parent=row, align=TextNode.ARight, shadow=None)
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
            self.label('No toons around right now.', (0, 0, 0.2), scale=0.07)
        for i, (doId, name) in enumerate(names):
            z = 0.66 - 0.17 * i
            row = DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=PANEL,
                              frameSize=(-self.width + 0.06, self.width - 0.06, -0.075, 0.075), pos=(0, 0, z), state=DGG.NORMAL)
            self.label(name, (-self.width + 0.12, 0, -0.02), scale=0.065, fg=DARK, parent=row, align=TextNode.ALeft, shadow=None)
            self.label('Ask for help', (self.width - 0.12, 0, -0.02), scale=0.05, fg=(0.1, 0.5, 0.15, 1), parent=row,
                       align=TextNode.ARight, shadow=None)
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
        self.title('Quick Chat')
        self.backButton()
        for i, (index, text) in enumerate(SPEEDCHAT):
            x = -self.width / 2 + (i % 2) * self.width
            z = 0.62 - (i // 2) * 0.2
            self.textButton(text, (x, 0, z), self.speak, index, scale=(1.35, 1, 1.6), textScale=0.055)
        self.label('Emotes', (0, 0, -0.04), scale=0.075)
        for i, name in enumerate(EMOTES):
            emoteId = OTPLocalizer.EmoteFuncDict.get(name)
            x = -self.width / 2 + (i % 2) * self.width
            z = -0.2 - (i // 2) * 0.2
            self.textButton(name, (x, 0, z), self.emote, emoteId, scale=(1.35, 1, 1.6), textScale=0.055, color=(0.6, 0.85, 1, 1))

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
        self.title('Progress')
        self.backButton()
        jar = self.find('jar_gui', 'Jar')
        DirectLabel(parent=self.page, relief=None, image=jar, image_scale=0.22, pos=(-self.width + 0.22, 0, 0.6))
        self.label('Jellybeans: %d of %d' % (avatar.getMoney(), avatar.getMaxMoney()), (-self.width + 0.42, 0, 0.64), scale=0.06, align=TextNode.ALeft)
        self.label('In the bank: %d' % avatar.getBankMoney(), (-self.width + 0.42, 0, 0.55), scale=0.055, align=TextNode.ALeft)
        self.label('Laff: %d of %d' % (avatar.hp, avatar.maxHp), (-self.width + 0.42, 0, 0.46), scale=0.055, align=TextNode.ALeft)
        icons = ('CorpIcon', 'LegalIcon', 'MoneyIcon', 'SalesIcon')
        for index, dept in enumerate(SuitDNA.suitDepts):
            z = 0.25 - index * 0.25
            DirectFrame(parent=self.page, relief=DGG.FLAT, frameColor=PANEL,
                        frameSize=(-self.width + 0.06, self.width - 0.06, -0.11, 0.11), pos=(0, 0, z))
            icon = self.find('cog_icons', icons[index])
            holder = self.page.attachNewNode('dept')
            icon.copyTo(holder)
            holder.setPos(-self.width + 0.18, 0, z)
            holder.setScale(0.15)
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
            self.label(first, (-self.width + 0.32, 0, z + 0.02), scale=0.055, fg=DARK, align=TextNode.ALeft, shadow=None)
            self.label(second, (-self.width + 0.32, 0, z - 0.06), scale=0.05, fg=(0.3, 0.3, 0.4, 1), align=TextNode.ALeft, shadow=None)

    # --- How the other toons help ---

    def buildHelp(self):
        from toontown.npcplayers import NPCSetupPanel
        self.title('Setup')
        self.backButton()
        self.label(NPCSetupPanel.HEADING, (0, 0, 0.66), scale=0.06, wordwrap=22)
        self.helpButtons = {}
        for i, (mode, name, blurb) in enumerate(NPCSetupPanel.CHOICES):
            z = 0.36 - i * 0.36
            self.helpButtons[mode] = self.textButton(name, (0, 0, z), self.pickHelp, mode, scale=(1.5, 1, 1.7), textScale=0.065)
            self.label(blurb, (0, 0, z - 0.13), scale=0.045, wordwrap=28)
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
            button['image_color'] = (0.6, 1.0, 0.6, 1) if name == mode else (1, 1, 1, 1)
