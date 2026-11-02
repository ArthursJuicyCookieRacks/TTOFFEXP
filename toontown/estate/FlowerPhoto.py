from direct.directnotify import DirectNotifyGlobal
from toontown.fishing import FishPhoto
from panda3d.core import *
from direct.interval.IntervalGlobal import *
from toontown.fishing import FishGlobals
from . import GardenGlobals
from direct.actor import Actor

class DirectRegion(FishPhoto.DirectRegion):
    # Draws like the fish photo's region; only hide() differs.
    notify = DirectNotifyGlobal.directNotify.newCategory('DirectRegion')

    def __init__(self, parent = aspect2d):
        NodePath.__init__(self)
        self.assign(parent.attachNewNode('DirectRegion'))

    def destroy(self):
        self.unload()
        self.parent_ = None
        return

    def setBounds(self, *bounds):
        self.bounds = bounds

    def setColor(self, *colors):
        self.color = colors

    def show(self):
        pass

    def hide(self):
        pass


class FlowerPhoto(NodePath):
    notify = DirectNotifyGlobal.directNotify.newCategory('FlowerPhoto')

    def __init__(self, species = None, variety = None, parent = aspect2d):
        NodePath.__init__(self)
        self.assign(parent.attachNewNode('FlowerPhoto'))
        self.species = species
        self.variety = variety
        self.actor = None
        self.sound = None
        self.soundTrack = None
        self.track = None
        self.flowerFrame = None
        return

    def destroy(self):
        self.hide()
        if hasattr(self, 'background'):
            del self.background
        self.fish = None
        del self.soundTrack
        del self.track
        self.parent_ = None
        return

    def update(self, species, variety):
        self.species = species
        self.variety = variety

    def setSwimBounds(self, *bounds):
        self.swimBounds = bounds

    def setSwimColor(self, *colors):
        self.swimColor = colors

    def load(self):
        pass

    def makeFlowerFrame(self, actor):
        actor.setDepthTest(1)
        actor.setDepthWrite(1)
        if not hasattr(self, 'flowerDisplayRegion'):
            self.flowerDisplayRegion = DirectRegion(parent=self)
            self.flowerDisplayRegion.setBounds(*self.swimBounds)
            self.flowerDisplayRegion.setColor(*self.swimColor)
        frame = self.flowerDisplayRegion.load()
        pitch = frame.attachNewNode('pitch')
        rotate = pitch.attachNewNode('rotate')
        scale = rotate.attachNewNode('scale')
        actor.reparentTo(scale)
        bMin, bMax = actor.getTightBounds()
        center = (bMin + bMax) / 2.0
        actor.setPos(-center[0], -center[1], -center[2])
        attrib = GardenGlobals.PlantAttributes[self.species]
        if 'photoPos' in attrib:
            self.notify.debug('oldPos = %s' % actor.getPos())
            photoPos = attrib['photoPos']
            self.notify.debug('newPos = %s' % str(photoPos))
            actor.setPos(photoPos[0], photoPos[1], photoPos[2])
        scale.setScale(attrib['photoScale'])
        rotate.setH(attrib['photoHeading'])
        pitch.setP(attrib['photoPitch'])
        pitch.setY(1.75)
        return frame

    def loadModel(self, species, variety):
        modelName = GardenGlobals.PlantAttributes[species]['fullGrownModel']
        nodePath = loader.loadModel(modelName)
        desat = None
        flowerColorIndex = GardenGlobals.PlantAttributes[species]['varieties'][variety][1]
        colorTuple = GardenGlobals.FlowerColors[flowerColorIndex]
        useWilted = 0
        wilt = nodePath.find('**/*wilt*')
        bloom = nodePath.find('**/*bloom*')
        if useWilted:
            wilt.show()
            desat = wilt.find('**/*desat*')
            bloom.hide()
        else:
            bloom.show()
            desat = bloom.find('**/*desat*')
            wilt.hide()
        if desat and not desat.isEmpty():
            desat.setColorScale(colorTuple[0], colorTuple[1], colorTuple[2], 1.0)
        else:
            nodePath.setColorScale(colorTuple[0], colorTuple[1], colorTuple[2], 1.0)
        return nodePath

    def show(self, showBackground = 0):
        self.notify.debug('show')
        messenger.send('wakeup')
        if self.flowerFrame:
            if hasattr(self.actor, 'cleanup'):
                self.actor.cleanup()
            if hasattr(self, 'flowerDisplayRegion'):
                self.flowerDisplayRegion.unload()
            self.hide()
        self.actor = self.loadModel(self.species, self.variety)
        self.flowerFrame = self.makeFlowerFrame(self.actor)
        if showBackground:
            if not hasattr(self, 'background'):
                background = loader.loadModel('phase_3.5/models/gui/stickerbook_gui')
                background = background.find('**/Fish_BG')
                self.background = background
            self.background.setPos(0, 15, 0)
            self.background.setScale(11)
            self.background.reparentTo(self.flowerFrame)

    def hide(self):
        if hasattr(self, 'flowerDisplayRegion'):
            self.flowerDisplayRegion.unload()
        if self.actor:
            if hasattr(self.actor, 'stop'):
                self.actor.stop()
            self.actor.hide()
        if self.sound:
            self.sound.stop()
            self.sound = None
        if self.soundTrack:
            self.soundTrack.pause()
            self.soundTrack = None
        if self.track:
            self.track.pause()
            self.track = None
        return

    def changeVariety(self, variety):
        self.variety = variety
