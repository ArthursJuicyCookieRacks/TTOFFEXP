import math
import random

from panda3d import core as PM
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpColorScaleInterval, LerpPosInterval, LerpScaleInterval,
                                            Parallel, Sequence, Wait)
from otp.otpbase import OTPGlobals
from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
from toontown.suit import Suit, SuitDNA
from toontown.toonbase import ToontownGlobals


def _box(parent, x0, y0, x1, y1, z0, z1, color):
    # A plain box: a cubicle partition, a shaft wall. Its four sides and
    # top, each face lit a little differently so the edges read.
    fmt = PM.GeomVertexFormat.getV3n3()
    vdata = PM.GeomVertexData('box', fmt, PM.Geom.UHStatic)
    vw = PM.GeomVertexWriter(vdata, 'vertex')
    nw = PM.GeomVertexWriter(vdata, 'normal')
    tris = PM.GeomTriangles(PM.Geom.UHStatic)
    faces = (((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),
             ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (0, 1, 0)),
             ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (-1, 0, 0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)))
    for i, face in enumerate(faces):
        for v in face[:4]:
            vw.addData3(*v)
            nw.addData3(*face[4])
        k = i * 4
        tris.addVertices(k, k + 1, k + 2)
        tris.addVertices(k, k + 2, k + 3)
    geom = PM.Geom(vdata)
    geom.addPrimitive(tris)
    gn = PM.GeomNode('box')
    gn.addGeom(geom)
    node = parent.attachNewNode(gn)
    node.setTwoSided(True)
    node.setColor(*color)
    # No lights in the office: shade the sides by hand.
    return node


def buildOffice(parent):
    """The golf office's floor and furniture: the Sellbot maze office's
    checked floor (tinted green, as in the QA screenshot) laid edge to edge,
    its paper strewn about, its cubicles, filing cabinets and desks set out
    in four blocks round the aisles (Consts.GolfPieces), and low grey
    partitions along the aisles. The AI's ball grid is drawn from this."""
    root = parent.attachNewNode('office')
    office = loader.loadModel(Consts.GolfOfficeModel)
    floor = office.find('**/maze:floor')
    papers = office.find('**/*floorPaper*')
    size = 51.0
    nx = int(math.ceil(2 * Consts.GolfHalfX / size))
    ny = int(math.ceil(2 * Consts.GolfHalfY / size))
    for i in range(nx):
        for j in range(ny):
            x = (i - (nx - 1) / 2.0) * size
            y = (j - (ny - 1) / 2.0) * size
            if not floor.isEmpty():
                f = floor.copyTo(root)
                f.setPos(x, y, 0)
                f.setColorScale(0.62, 0.8, 0.64, 1)
            if not papers.isEmpty():
                p = papers.copyTo(root)
                p.setPos(x, y, 0)
                p.setH(90 * ((i + 2 * j) % 4))
    office.removeNode()
    models = {}
    for quadrant, name, dx, dy in Consts.GolfPieces:
        if quadrant not in models:
            models[quadrant] = loader.loadModel(Consts.GolfQuadrantModel % quadrant)
        model = models[quadrant]
        prefix, suffix = name.split(':')
        holder = root.attachNewNode('piece-%d-%s' % (quadrant, suffix))
        holder.setPos(dx, dy, 0)
        for node in model.findAllMatches('**/%s:*' % prefix):
            part = node.getName().split(':')[1]
            # Only this grouping's own pieces: itself, its floor shadow and
            # its lamps' light cones.
            if part != suffix and not part.endswith('_' + suffix) and 'lightCone' not in part:
                continue
            node.copyTo(holder)
    for model in models.values():
        model.removeNode()
    # The low grey cubicle partitions of the QA screenshot, lining the
    # aisles: the toons putt down a lane between them, and the balls bank
    # off them.
    for x0, y0, x1, y1 in Consts.GolfPartitions:
        _partition(root, x0, y0, x1, y1)
    root.setColorScale(*Consts.GolfOfficeBrightness)
    return root


def _partition(parent, x0, y0, x1, y1):
    h = Consts.GolfPartitionHeight
    wall = _box(parent, x0, y0, x1, y1, 0.0, h, (0.5, 0.52, 0.56, 1))
    # A darker cap along the top and a kick plate at the floor.
    cap = _box(wall, x0 - 0.08, y0 - 0.08, x1 + 0.08, y1 + 0.08, h - 0.25, h + 0.1, (0.5, 0.52, 0.56, 1))
    cap.setColor(0.5, 0.52, 0.56, 1)
    kick = _box(wall, x0 - 0.04, y0 - 0.04, x1 + 0.04, y1 + 0.04, 0.0, 0.45, (0.38, 0.39, 0.42, 1))
    kick.setColor(0.38, 0.39, 0.42, 1)
    return wall


class CogdoBoardroomGolf:
    """The golf office after the boardroom slide: the classic cog building
    office floor, cubicle walls and desks piled with paper as in the QA
    server screenshot, the laff barrels piled in the middle and the cogs
    walking in to carry them off. The toons tee off along the near wall."""

    def __init__(self, game):
        self.game = game
        self.root = None
        self.cogs = {}
        self.balls = []
        self.barrelModels = []
        self.barrelsHome = Consts.NumBarrels
        self.drops = {}

    # --- Loading ---

    def load(self, parent):
        self.root = parent.attachNewNode('golfOffice')
        self.root.setPos(*Consts.GolfOrigin)
        self.room = self._loadShell()
        self._loadDressing()
        self._loadBarrels()
        self.ballModel = loader.loadModel('phase_6/models/golf/golf_ball')
        self.putter = loader.loadModel('phase_6/models/golf/putter')
        self.carryModel = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_cbr_laughBarrel')
        self.hitSfx = loader.loadSfx('phase_6/audio/sfx/Golf_Hit_Ball.ogg')
        self.bonkSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.stealSfx = loader.loadSfx('phase_5/audio/sfx/ENC_propeller_out.ogg')
        self.explodeSfx = loader.loadSfx('phase_3.5/audio/sfx/Cog_Death.ogg')
        self._loadAim()
        self.root.stash()
        return self.root

    def _loadShell(self):
        # The office's walls and ceiling: the Sellbot maze office's grey
        # panelled walls, brought in to the size of this room (the walls
        # run on past the corners, out of sight behind each other).
        level = loader.loadModel(Consts.GolfWallModel)
        shell = self.root.attachNewNode('shell')
        scale = Consts.GolfWallScale
        for name, pos in (('wallBarrier1', (0, Consts.GolfHalfY + 0.5 - 76.5 * scale, 0)),
                          ('wallBarrier2', (0, -(Consts.GolfHalfY + 0.5) + 76.5 * scale, 0)),
                          ('wallBarrier3', (Consts.GolfHalfX + 0.5 - 76.5 * scale, 6.0 * scale, 0)),
                          ('wallBarrier4', (-(Consts.GolfHalfX + 0.5) + 76.5 * scale, 6.0 * scale, 0)),
                          ('ceiling', (0, 0, 0))):
            wall = level.find('**/' + name)
            if wall.isEmpty():
                continue
            holder = shell.attachNewNode(name)
            wall.reparentTo(holder)
            holder.setScale(scale)
            holder.setPos(*pos)
        level.removeNode()
        return shell

    def _loadDressing(self):
        # The office itself: one of the Sellbot maze's cubicle offices, as
        # in the QA screenshot, its floor checked green and grey; the cog
        # building office round it gives the walls and ceiling beyond.
        office = buildOffice(self.root)
        for cone in office.findAllMatches('**/*lightCone*'):
            cone.setTransparency(PM.TransparencyAttrib.MAlpha)
            cone.setDepthWrite(False)
            cone.setBin('fixed', 3)
        self.office = office
        # The three elevators the cogs come and go by, each in a shaft
        # boxed out from its wall in the office's grey.
        self.elevators = []
        from toontown.cogdominium import CogdoUtil
        for x, y, h in Consts.GolfElevators:
            holder = self.root.attachNewNode('elevator')
            holder.setPos(x, y, 0)
            holder.setH(h)
            # The field offices' own elevator, the one the toons ride.
            e = CogdoUtil.loadElevatorModel()
            e.reparentTo(holder)
            for coll in e.findAllMatches('**/+CollisionNode'):
                coll.removeNode()
            # The shaft: walls each side of the car and a cap above it,
            # flush with the elevator's frame and back to the room's wall.
            depth = Consts.GolfElevatorDepth + 1.0
            for x0, x1 in ((-9.4, -8.6), (8.6, 9.4)):
                _box(holder, x0, -0.3, x1, depth, 0.0, 13.6, (0.5, 0.52, 0.56, 1))
            _box(holder, -9.4, -0.3, 9.4, depth, 12.3, 13.6, (0.46, 0.48, 0.52, 1))
            left = e.find('**/left_door')
            right = e.find('**/right_door')
            self.elevators.append({'left': left, 'right': right, 'open': 0.0})
            self._setDoors(self.elevators[-1], 0.0)
        # The toons' elevator, in the back wall behind the tees: they ride
        # in from the boardroom in it.
        x, y, h = Consts.GolfToonElevator
        self.toonElevator = CogdoUtil.loadElevatorModel()
        self.toonElevator.reparentTo(self.root)
        self.toonElevator.setPosHpr(x, y, 0, h, 0, 0)
        CogdoUtil.addElevatorShell(self.toonElevator)
        for coll in self.toonElevator.findAllMatches('**/+CollisionNode'):
            coll.removeNode()
        self.toonLeftDoor = self.toonElevator.find('**/left_door')
        self.toonRightDoor = self.toonElevator.find('**/right_door')
        self.closeToonDoors()
        # A name plate on the far cubicle, as on the screenshot's.
        plate = PM.TextNode('namePlate')
        plate.setText('Mr. Hollywood\nVP of Hijinks')
        plate.setFont(ToontownGlobals.getSuitFont())
        plate.setAlign(PM.TextNode.ACenter)
        plate.setTextColor(0.15, 0.15, 0.4, 1)
        plate.setCardColor(0.7, 0.72, 0.95, 1)
        plate.setCardAsMargin(0.3, 0.3, 0.2, 0.2)
        plate.setCardDecal(True)
        sign = self.root.attachNewNode(plate.generate())
        sign.setPos(*Consts.GolfNamePlate)
        sign.setScale(0.55)
        sign.setTwoSided(True)

    def _setDoors(self, elevator, f):
        # f is 0 shut to 1 open; the doors slide apart 3.5 ft each, as the
        # cog building elevators' do.
        elevator['open'] = f
        elevator['left'].setX(3.5 * (1.0 - f))
        elevator['right'].setX(-3.5 * (1.0 - f))

    def updateElevators(self, dt):
        # An elevator's doors open when a cog is at them, and shut after.
        for index, elevator in enumerate(self.elevators):
            dx, dy = Consts.golfElevatorDoor(index)
            near = any(c['alive'] and (c['suit'].getPos() - PM.Point3(dx, dy, 0)).length() < 9.0
                       for c in self.cogs.values())
            want = 1.0 if near else 0.0
            f = elevator['open']
            if f != want:
                step = dt / 0.6
                f = min(want, f + step) if want > f else max(want, f - step)
                self._setDoors(elevator, f)

    def _loadBarrels(self):
        # The laff barrels the toons brought out of the meeting, piled in
        # the middle of the office.
        model = loader.loadModel('phase_5/models/cogdominium/tt_m_ara_cbr_laughBarrel')
        mn, mx = model.getTightBounds()
        scale = 2.2 / max(mx[2] - mn[2], 0.01)
        w = (mx[0] - mn[0]) * scale + 0.15
        tall = (mx[2] - mn[2]) * scale
        pile = self.root.attachNewNode('barrelPile')
        pile.setPos(Consts.BarrelPile[0], Consts.BarrelPile[1], 0)
        spots = [(-1.5 * w, 0, 0), (-0.5 * w, 0, 0), (0.5 * w, 0, 0), (1.5 * w, 0, 0), (-w, 0.2, tall), (0, 0.2, tall),
                 (w, 0.2, tall), (-0.5 * w, 0.4, 2 * tall), (0.5 * w, 0.4, 2 * tall)]
        self.barrelScale = scale
        for i in range(Consts.NumBarrels):
            b = model.copyTo(pile)
            x, y, z = spots[i % len(spots)]
            b.setPos(x, y, z - mn[2] * scale)
            b.setScale(scale)
            b.setH(180)
            self.barrelModels.append(b)
        model.removeNode()

    def _loadAim(self):
        # An arrow on the floor in front of the toon: its length shows how
        # hard the swing will be.
        cm = PM.CardMaker('aim')
        cm.setFrame(-0.35, 0.35, 0, 1)
        self.aim = self.root.attachNewNode('aim')
        bar = self.aim.attachNewNode(cm.generate())
        bar.setP(-90)
        bar.setZ(0.08)
        head = self.aim.attachNewNode(cm.generate())
        head.setP(-90)
        self.aimBar = bar
        self.aim.setColor(1, 0.85, 0.2, 0.85)
        self.aim.setTransparency(PM.TransparencyAttrib.MAlpha)
        self.aim.setLightOff()
        self.aim.setDepthOffset(2)
        self.aim.hide()

    def destroy(self):
        for cog in self.cogs.values():
            self._removeCog(cog)
        self.cogs = {}
        for b in self.drops.values():
            b.removeNode()
        self.drops = {}
        for ball in self.balls:
            ball['np'].removeNode()
        self.balls = []
        if self.root:
            self.root.removeNode()
        self.root = None

    # --- Showing it ---

    def show(self):
        self.root.unstash()

    def closeToonDoors(self):
        self.toonLeftDoor.setPos(3.5, 0, 0)
        self.toonRightDoor.setPos(-3.5, 0, 0)

    def toonElevatorSpot(self, index):
        # Where toon `index` stands in the toons' elevator (as in the cog
        # building elevators), in render.
        from toontown.building.ElevatorConstants import ElevatorPoints
        p = ElevatorPoints[index % len(ElevatorPoints)]
        return render.getRelativePoint(self.toonElevator, PM.Point3(p[0], p[1], 0))

    def teePos(self, index):
        x, y = Consts.GolfTees[index % len(Consts.GolfTees)]
        return self.root.getPos(render) + PM.Vec3(x, y, 0)

    def toLocal(self, pos):
        return pos - self.root.getPos(render)

    def setBarrelsHome(self, home):
        self.barrelsHome = home
        for i, b in enumerate(self.barrelModels):
            if i < home:
                b.unstash()
            else:
                b.stash()

    # --- The cogs ---

    def addCog(self, cogId, nameIndex, px, side, exitY, speed, startTime, target=None):
        suit = Suit.Suit()
        dna = SuitDNA.SuitDNA()
        dna.newSuit(Consts.GolfCogNames[nameIndex % len(Consts.GolfCogNames)])
        suit.setDNA(dna)
        suit.nametag3d.stash()
        suit.reparentTo(self.root)
        suit.loop('walk')
        cog = {'id': cogId, 'suit': suit, 'path': Consts.golfCogPath(px, side, exitY, speed, target), 'start': startTime,
               'alive': True, 'carry': None, 'ival': None}
        self.cogs[cogId] = cog
        self.updateCog(cog, self.game.golfTime())
        return cog

    def updateCog(self, cog, now):
        if not cog['alive']:
            return
        x, y, h, leg = Consts.golfCogPos(cog['path'], now - cog['start'])
        suit = cog['suit']
        suit.setPos(x, y, 0)
        suit.setH(h)
        anim = 'neutral' if leg in (1, 3) else 'walk'
        if suit.getCurrentAnim() != anim:
            suit.loop(anim)

    def cogPickup(self, cogId, carrying):
        cog = self.cogs.get(cogId)
        if cog is None or not carrying:
            return
        barrel = self.carryModel.copyTo(cog['suit'])
        barrel.setScale(self.barrelScale * 0.8)
        barrel.setPos(0, 1.4, cog['suit'].getHeight() * 0.45)
        cog['carry'] = barrel

    def cogEscaped(self, cogId, carrying):
        cog = self.cogs.pop(cogId, None)
        if cog is None:
            return
        cog['alive'] = False
        suit = cog['suit']
        if carrying:
            base.playSfx(self.stealSfx, node=suit)
        track = Sequence(LerpColorScaleInterval(suit, 0.6, PM.VBase4(1, 1, 1, 0), startColorScale=PM.VBase4(1, 1, 1, 1)),
                         Func(self._removeCog, cog))
        suit.setTransparency(1)
        cog['ival'] = track
        track.start()

    def cogHit(self, cogId):
        cog = self.cogs.pop(cogId, None)
        if cog is None:
            return
        cog['alive'] = False
        suit = cog['suit']
        base.playSfx(self.bonkSfx, node=suit)
        if cog['carry'] is not None:
            # The barrel falls to the floor (the AI puts it down there: see
            # setDrops); this one just tumbles out of the cog's hands.
            self._dropCarry(cog)
        anim = 'slip-backward' if suit.getAnimControl('slip-backward') else 'flail'
        track = Sequence(ActorInterval(suit, anim, duration=1.0),
                         LerpColorScaleInterval(suit, 0.6, PM.VBase4(1, 1, 1, 0), startColorScale=PM.VBase4(1, 1, 1, 1)),
                         Func(self._removeCog, cog))
        suit.setTransparency(1)
        cog['ival'] = track
        track.start()

    def _dropCarry(self, cog):
        barrel = cog['carry']
        cog['carry'] = None
        if barrel is None or barrel.isEmpty():
            return
        barrel.wrtReparentTo(self.root)
        floor = PM.Point3(barrel.getX(), barrel.getY(), 0.0)
        Sequence(LerpPosInterval(barrel, 0.35, floor, blendType='easeIn'), Func(barrel.removeNode)).start()

    def cogExplode(self, cogId):
        # Time's up: the cog blows apart, as cogs do in the field offices.
        cog = self.cogs.pop(cogId, None)
        if cog is None:
            return
        cog['alive'] = False
        suit = cog['suit']
        if cog['carry'] is not None:
            self._dropCarry(cog)
        from toontown.battle import BattleParticles, MovieUtil
        from direct.interval.IntervalGlobal import ParticleInterval
        BattleParticles.loadParticles()
        gearPoint = PM.Point3(0, 0, suit.height / 2.0 + 2.0)
        gears = BattleParticles.createParticleEffect('GearExplosion', numParticles=12)
        gears.setPos(gearPoint)
        gears.setDepthWrite(False)
        anim = 'lose' if suit.getAnimControl('lose') else 'flail'
        track = Sequence(Parallel(ActorInterval(suit, anim, startFrame=80, endFrame=140) if anim == 'lose'
                                  else ActorInterval(suit, anim, duration=1.5),
                                  Sequence(Wait(1.0), MovieUtil.createKapowExplosionTrack(suit, explosionPoint=gearPoint)),
                                  Sequence(Wait(1.6), ParticleInterval(gears, suit, worldRelative=0, duration=1.0, cleanup=True))),
                         Func(self._removeCog, cog))
        cog['ival'] = track
        track.start()
        base.playSfx(self.explodeSfx, node=suit)

    def setDrops(self, drops):
        # The barrels lying on the floor (dropId: (x, y)), as the AI has them.
        for dropId in list(self.drops):
            if dropId not in drops:
                self.drops.pop(dropId).removeNode()
        for dropId, (x, y) in drops.items():
            if dropId in self.drops:
                continue
            b = self.carryModel.copyTo(self.root)
            b.setScale(self.barrelScale)
            mn, mx = b.getTightBounds(b)
            b.setPos(x, y, -mn[2] * self.barrelScale)
            b.setH(random.uniform(0, 360))
            Sequence(LerpPosInterval(b, 0.25, PM.Point3(x, y, -mn[2] * self.barrelScale + 0.6), blendType='easeOut'),
                     LerpPosInterval(b, 0.25, PM.Point3(x, y, -mn[2] * self.barrelScale), blendType='easeIn')).start()
            self.drops[dropId] = b

    def _removeCog(self, cog):
        if cog.get('ival'):
            cog['ival'].pause()
            cog['ival'] = None
        suit = cog.get('suit')
        if suit is not None:
            suit.cleanup()
            suit.removeNode()
            suit.delete()
            cog['suit'] = None

    # --- The balls ---

    def addBall(self, avId, origin, h, power, reportHits):
        np = self.ballModel.copyTo(self.root)
        np.setScale(1.5)
        x, y, vx, vy = Consts.golfBallStart(origin[0], origin[1], h, power)
        pos = PM.Point3(x, y, Consts.BallRadius)
        vel = PM.Vec3(vx, vy, 0)
        np.setPos(pos)
        self.balls.append({'np': np, 'pos': pos, 'vel': vel, 'av': avId, 'report': reportHits, 'stopped': 0.0})
        base.playSfx(self.hitSfx, node=np)

    def updateBalls(self, dt):
        hits = []
        keep = []
        for ball in self.balls:
            pos = ball['pos']
            vel = ball['vel']
            speed = vel.length()
            if speed < Consts.BallStopSpeed:
                ball['stopped'] += dt
                if ball['stopped'] > 1.0:
                    ball['np'].removeNode()
                    continue
                keep.append(ball)
                continue
            x, y, vx, vy = Consts.golfBallStep(pos[0], pos[1], vel[0], vel[1], dt)
            pos = PM.Point3(x, y, Consts.BallRadius)
            vel = PM.Vec3(vx, vy, 0)
            ball['pos'] = pos
            ball['vel'] = vel
            ball['np'].setPos(pos)
            ball['np'].setH(ball['np'].getH() + speed * dt * 40)
            hit = None
            for cog in self.cogs.values():
                if not cog['alive'] or cog['suit'] is None:
                    continue
                cp = cog['suit'].getPos()
                if math.hypot(cp[0] - pos[0], cp[1] - pos[1]) < Consts.GolfCogRadius:
                    hit = cog
                    break
            if hit is not None:
                if ball['report']:
                    hits.append(hit['id'])
                ball['np'].removeNode()
                continue
            keep.append(ball)
        self.balls = keep
        return hits

    # --- Aiming ---

    def showAim(self, pos, h, power):
        self.aim.show()
        self.aim.setPos(self.toLocal(pos) + PM.Vec3(0, 0, 0.05))
        self.aim.setH(h)
        length = 3.0 + 9.0 * power
        self.aim.setScale(1, length, 1)
        self.aim.setColor(1, 0.85 - 0.6 * power, 0.2, 0.85)

    def hideAim(self):
        self.aim.hide()

    def attachPutter(self, toon):
        # As the golf course does it: in the left hand, against the toon's
        # own scale.
        hands = toon.getLeftHands()
        if not hands:
            return None
        hand = hands[0]
        club = PM.NodePath('club')
        model = self.putter.copyTo(club)
        model.setR(model, 45)
        club.reparentTo(hand)
        netScale = club.getNetTransform().getScale()[1] or 1.0
        counter = hand.find('**/counteractToonScale')
        if counter.isEmpty():
            counter = hand.attachNewNode('counteractToonScale')
            counter.setScale(1.0 / netScale)
        club.reparentTo(counter)
        club.setX(-0.25 * netScale)
        return club
