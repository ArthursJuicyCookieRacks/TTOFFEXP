from panda3d.core import *
from otp.nametag.NametagGroup import NametagGroup
from direct.directnotify import DirectNotifyGlobal
from direct.fsm import ClassicFSM
from direct.fsm import State
from toontown.toonbase import ToontownGlobals
from . import DistributedToon
from direct.distributed import DistributedObject
from . import NPCToons
from toontown.quest import Quests
from direct.distributed import ClockDelta
from toontown.quest import QuestParser
from toontown.quest import QuestChoiceGui
from direct.interval.IntervalGlobal import *
from direct.task import Task
import random

class DistributedNPCToonBase(DistributedToon.DistributedToon):

    def __init__(self, cr):
        try:
            self.DistributedNPCToon_initialized
        except:
            self.DistributedNPCToon_initialized = 1
            DistributedToon.DistributedToon.__init__(self, cr)
            self.__initCollisions()
            self.setPickable(0)
            self.setPlayerType(NametagGroup.CCNonPlayer)

    def disable(self):
        taskMgr.remove(self.uniqueName('placeAtOrigin'))
        self.originTries = 0
        self.ignore('enter' + self.cSphereNode.getName())
        DistributedToon.DistributedToon.disable(self)

    def delete(self):
        try:
            self.DistributedNPCToon_deleted
        except:
            self.DistributedNPCToon_deleted = 1
            self.__deleteCollisions()
            DistributedToon.DistributedToon.delete(self)

    def generate(self):
        DistributedToon.DistributedToon.generate(self)
        self.cSphereNode.setName(self.uniqueName('NPCToon'))
        self.detectAvatars()
        self.setParent(ToontownGlobals.SPRender)
        self.startLookAround()

    def generateToon(self):
        self.setLODs()
        self.generateToonLegs()
        self.generateToonHead()
        self.generateToonTorso()
        self.generateToonColor()
        self.parentToonParts()
        self.rescaleToon()
        self.resetHeight()
        self.rightHands = []
        self.leftHands = []
        self.headParts = []
        self.hipsParts = []
        self.torsoParts = []
        self.legsParts = []
        self.__bookActors = []
        self.__holeActors = []

    def announceGenerate(self):
        self.initToonState()
        DistributedToon.DistributedToon.announceGenerate(self)

    def initToonState(self):
        self.setAnimState('neutral', self.getNeutralRate(), None, None)
        self.placeAtOrigin()

    def getNeutralRate(self):
        return 0.9

    def findNpcOrigin(self):
        return render.find('**/npc_origin_' + repr((self.posIndex)))

    def placeAtOrigin(self, task=None):
        # The toon can arrive before the room or playground it stands in has
        # loaded. Rather than stand where it happens to be (in the middle of
        # nowhere, or by another room's spot), it waits out of sight until
        # its spot is there.
        try:
            npcOrigin = self.findNpcOrigin()
        except AttributeError:
            npcOrigin = NodePath()
        if not npcOrigin.isEmpty():
            self.reparentTo(npcOrigin)
            self.initPos()
            self.unstash()
            return Task.done
        self.originTries = getattr(self, 'originTries', 0) + 1
        if self.originTries > 50:
            self.notify.warning('Could not find the origin of %s (posIndex %s)' % (self.getName(), self.posIndex))
            self.unstash()
            return Task.done
        self.stash()
        taskMgr.doMethodLater(0.2, self.placeAtOrigin, self.uniqueName('placeAtOrigin'))
        return Task.done

    def initPos(self):
        self.clearMat()

    def wantsSmoothing(self):
        return 0

    def detectAvatars(self):
        self.accept('enter' + self.cSphereNode.getName(), self.handleCollisionSphereEnter)

    def ignoreAvatars(self):
        self.ignore('enter' + self.cSphereNode.getName())

    def getCollSphereRadius(self):
        return 3.25

    def __initCollisions(self):
        self.cSphere = CollisionTube(0.0, 1.0, 0.0, 0.0, 1.0, 5.0, self.getCollSphereRadius())
        self.cSphere.setTangible(0)
        self.cSphereNode = CollisionNode('cSphereNode')
        self.cSphereNode.addSolid(self.cSphere)
        self.cSphereNodePath = self.attachNewNode(self.cSphereNode)
        self.cSphereNodePath.hide()
        self.cSphereNode.setCollideMask(ToontownGlobals.WallBitmask)

    def __deleteCollisions(self):
        del self.cSphere
        del self.cSphereNode
        self.cSphereNodePath.removeNode()
        del self.cSphereNodePath

    def handleCollisionSphereEnter(self, collEntry):
        pass

    def setupAvatars(self, av):
        self.ignoreAvatars()
        av.headsUp(self, 0, 0, 0)
        self.headsUp(av, 0, 0, 0)
        av.stopLookAround()
        av.lerpLookAt(Point3(-0.5, 4, 0), time=0.5)
        self.stopLookAround()
        self.lerpLookAt(Point3(av.getPos(self)), time=0.5)

    def b_setPageNumber(self, paragraph, pageNumber):
        self.setPageNumber(paragraph, pageNumber)
        self.d_setPageNumber(paragraph, pageNumber)

    def d_setPageNumber(self, paragraph, pageNumber):
        timestamp = ClockDelta.globalClockDelta.getFrameNetworkTime()
        self.sendUpdate('setPageNumber', [paragraph, pageNumber, timestamp])

    def freeAvatar(self):
        base.localAvatar.posCamera(0, 0)
        base.cr.playGame.getPlace().setState('walk')

    def setPositionIndex(self, posIndex):
        self.posIndex = posIndex

    def _startZombieCheck(self):
        pass

    def _stopZombieCheck(self):
        pass
