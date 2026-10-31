from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.directnotify import DirectNotifyGlobal
from direct.distributed import DistributedSmoothNode
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from direct.fsm import FSM
from direct.task import Task
from panda3d.physics import ActorNode, PhysicsCollisionHandler
smileyDoId = 1

class DistCogdoCraneObject(DistributedSmoothNode.DistributedSmoothNode, FSM.FSM):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistCogdoCraneObject')
    wantsWatchDrift = 1

    def __init__(self, cr):
        DistributedSmoothNode.DistributedSmoothNode.__init__(self, cr)
        FSM.FSM.__init__(self, 'DistCogdoCraneObject')
        self.craneGame = None
        self.avId = 0
        self.craneId = 0
        self.cleanedUp = 0
        self.collisionNode = CollisionNode('object')
        self.collisionNode.setIntoCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.WallBitmask | ToontownGlobals.CashbotBossObjectBitmask | OTPGlobals.CameraBitmask)
        self.collisionNode.setFromCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.FloorBitmask)
        self.collisionNodePath = NodePath(self.collisionNode)
        self.physicsActivated = 0
        self.toMagnetSoundInterval = Sequence()
        self.hitFloorSoundInterval = Sequence()
        self.hitBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_safe_miss.ogg')
        self.hitBossSoundInterval = SoundInterval(self.hitBossSfx)
        self.touchedBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.touchedBossSoundInterval = SoundInterval(self.touchedBossSfx, duration=0.8)
        self.lerpInterval = None
        return

    def disable(self):
        self.cleanup()
        self.stopSmooth()
        DistributedSmoothNode.DistributedSmoothNode.disable(self)

    def cleanup(self):
        if self.cleanedUp:
            return
        else:
            self.cleanedUp = 1
        self.demand('Off')
        self.detachNode()
        self.toMagnetSoundInterval.finish()
        self.hitFloorSoundInterval.finish()
        self.hitBossSoundInterval.finish()
        self.touchedBossSoundInterval.finish()
        del self.toMagnetSoundInterval
        del self.hitFloorSoundInterval
        del self.hitBossSoundInterval
        del self.touchedBossSoundInterval
        self.craneGame = None
        return

    def announceGenerate(self):
        DistributedSmoothNode.DistributedSmoothNode.announceGenerate(self)
        # This client runs every crane object's physics (offline, the NPC
        # toons' cranes too), so position reports coming back over the
        # wire are old news: applying them made the bags jump back and
        # forth between where they were and where they are.
        self.localControl = True

    def setupPhysics(self, name):
        an = ActorNode('%s-%s' % (name, self.doId))
        anp = NodePath(an)
        if not self.isEmpty():
            self.reparentTo(anp)
        NodePath.assign(self, anp)
        self.physicsObject = an.getPhysicsObject()
        self.setTag('object', str(self.doId))
        self.collisionNodePath.reparentTo(self)
        self.handler = PhysicsCollisionHandler()
        self.handler.addCollider(self.collisionNodePath, self)
        self.collideName = self.uniqueName('collide')
        self.handler.addInPattern(self.collideName + '-%in')
        self.handler.addAgainPattern(self.collideName + '-%in')
        self.watchDriftName = self.uniqueName('watchDrift')

    def activatePhysics(self):
        if not self.physicsActivated:
            self.craneGame.physicsMgr.attachPhysicalNode(self.node())
            self.craneGame.physicsTrav.addCollider(self.collisionNodePath, self.handler)
            self.physicsActivated = 1
            self.accept(self.collideName + '-floor', self.__hitFloor)
            self.accept(self.collideName + '-goon', self.__hitGoon)
            self.acceptOnce(self.collideName + '-headTarget', self.__hitBoss)
            self.accept(self.collideName + '-dropPlane', self.__hitDropPlane)

    def deactivatePhysics(self):
        if self.physicsActivated:
            self.craneGame.physicsMgr.removePhysicalNode(self.node())
            self.craneGame.physicsTrav.removeCollider(self.collisionNodePath)
            self.physicsActivated = 0
            self.ignore(self.collideName + '-floor')
            self.ignore(self.collideName + '-goon')
            self.ignore(self.collideName + '-headTarget')
            self.ignore(self.collideName + '-dropPlane')

    def hideShadows(self):
        pass

    def showShadows(self):
        pass

    def stashCollisions(self):
        self.collisionNodePath.stash()

    def unstashCollisions(self):
        self.collisionNodePath.unstash()

    def isRunHere(self):
        # This client runs the physics of what its toon holds or dropped,
        # and (offline) of what the NPC toons' cranes hold or dropped.
        return self.craneGame is not None and self.craneGame.runsHere(self.avId)

    def __hitFloor(self, entry):
        if self.state == 'Dropped' or self.state == 'LocalDropped':
            self.d_hitFloor()
            self.demand('SlidingFloor', self.avId)

    def __hitGoon(self, entry):
        if self.state == 'Dropped' or self.state == 'LocalDropped':
            goonId = int(entry.getIntoNodePath().getNetTag('doId'))
            goon = self.cr.doId2do.get(goonId)
            if goon:
                self.doHitGoon(goon)

    def doHitGoon(self, goon):
        pass

    def __hitBoss(self, entry):
        if (self.state == 'Dropped' or self.state == 'LocalDropped') and self.craneId != self.craneGame.doId:
            vel = self.physicsObject.getVelocity()
            vel = self.crane.root.getRelativeVector(render, vel)
            vel.normalize()
            impact = vel[1]
            if impact >= self.getMinImpact():
                print('hit! %s' % impact)
                self.hitBossSoundInterval.start()
                self.doHitBoss(impact)
            else:
                self.touchedBossSoundInterval.start()
                print('--not hard enough: %s' % impact)

    def doHitBoss(self, impact):
        self.d_hitBoss(impact)

    def __hitDropPlane(self, entry):
        self.notify.info('%s fell out of the world.' % self.doId)
        self.fellOut()

    def fellOut(self):
        raise Exception('fellOut unimplented')

    def getMinImpact(self):
        return 0

    def __watchDrift(self, task):
        v = self.physicsObject.getVelocity()
        if abs(v[0]) < 0.0001 and abs(v[1]) < 0.0001:
            self.d_requestFree()
            self.demand('Free')
        return Task.cont

    def prepareGrab(self):
        pass

    def prepareRelease(self):
        pass

    def setCraneGameId(self, craneGameId):
        self.craneGameId = craneGameId
        self.craneGame = base.cr.doId2do[craneGameId]

    def setObjectState(self, state, avId, craneId):
        if state == 'G':
            self.demand('Grabbed', avId, craneId)
        elif state == 'D':
            if self.state != 'Dropped':
                self.demand('Dropped', avId, craneId)
        elif state == 's':
            if self.state != 'SlidingFloor':
                self.demand('SlidingFloor', avId)
        elif state == 'F':
            self.demand('Free')
        else:
            self.notify.error('Invalid state from AI: %s' % state)

    def d_requestGrab(self, avId):
        self.sendUpdate('requestGrab', [avId])

    def d_hitCog(self, cogId):
        self.sendUpdate('hitCog', [cogId])

    def rejectGrab(self):
        if self.state == 'LocalGrabbed':
            self.demand('LocalDropped', self.avId, self.craneId)

    def d_requestDrop(self):
        self.sendUpdate('requestDrop')

    def d_hitFloor(self):
        self.sendUpdate('hitFloor')

    def d_requestFree(self):
        self.sendUpdate('requestFree', [self.getX(),
         self.getY(),
         self.getZ(),
         self.getH()])

    def d_hitBoss(self, impact):
        self.sendUpdate('hitBoss', [impact])

    def defaultFilter(self, request, args):
        if self.craneGame == None:
            raise FSM.RequestDenied(request)
        return FSM.FSM.defaultFilter(self, request, args)

    def enterOff(self):
        self.detachNode()
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        return

    def exitOff(self):
        self.reparentTo(render)

    def enterLocalGrabbed(self, avId, craneId):
        self.avId = avId
        self.craneId = craneId
        self.crane = self.cr.doId2do.get(craneId)
        self.hideShadows()
        self.prepareGrab()
        self.crane.grabObject(self)

    def exitLocalGrabbed(self):
        if self.newState != 'Grabbed':
            self.crane.dropObject(self)
            self.prepareRelease()
            del self.crane
            self.showShadows()

    def enterGrabbed(self, avId, craneId):
        if self.oldState == 'LocalGrabbed':
            if craneId == self.craneId:
                return
            else:
                self.crane.dropObject(self)
                self.prepareRelease()
        self.avId = avId
        self.craneId = craneId
        self.crane = self.cr.doId2do.get(craneId)
        self.hideShadows()
        self.prepareGrab()
        self.crane.grabObject(self)

    def exitGrabbed(self):
        self.crane.dropObject(self)
        self.prepareRelease()
        self.showShadows()
        del self.crane

    def enterLocalDropped(self, avId, craneId):
        self.avId = avId
        self.craneId = craneId
        self.crane = self.cr.doId2do.get(craneId)
        self.activatePhysics()
        self.startPosHprBroadcast()
        self.hideShadows()
        self.handler.setStaticFrictionCoef(0)
        self.handler.setDynamicFrictionCoef(0)

    def exitLocalDropped(self):
        if self.newState != 'SlidingFloor' and self.newState != 'Dropped':
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        del self.crane
        self.showShadows()

    def enterDropped(self, avId, craneId):
        self.avId = avId
        self.craneId = craneId
        self.crane = self.cr.doId2do.get(craneId)
        if self.isRunHere():
            self.activatePhysics()
            self.startPosHprBroadcast()
            self.handler.setStaticFrictionCoef(0)
            self.handler.setDynamicFrictionCoef(0)
        else:
            self.startSmooth()
        self.hideShadows()

    def exitDropped(self):
        if self.isRunHere():
            if self.newState != 'SlidingFloor':
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
        else:
            self.stopSmooth()
        del self.crane
        self.showShadows()

    def enterSlidingFloor(self, avId):
        self.avId = avId
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        if self.isRunHere():
            self.activatePhysics()
            self.startPosHprBroadcast()
            self.handler.setStaticFrictionCoef(0.9)
            self.handler.setDynamicFrictionCoef(0.5)
            if self.wantsWatchDrift:
                taskMgr.add(self.__watchDrift, self.watchDriftName)
        else:
            self.startSmooth()
        self.hitFloorSoundInterval.start()
        return

    def exitSlidingFloor(self):
        if self.isRunHere():
            taskMgr.remove(self.watchDriftName)
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        else:
            self.stopSmooth()

    def enterFree(self):
        self.avId = 0
        self.craneId = 0

    def exitFree(self):
        pass
