"""The way out of Survival Mode: buy a ride on the Toontown Central
trolley. The toons climb aboard and sit down, the bell rings, the trolley
pulls away with its key turning and wheels rolling, and the screen fades
to black the way it does before a trolley game. Then the win card."""

import math

from direct.directnotify import DirectNotifyGlobal
from direct.interval.IntervalGlobal import (ActorInterval, Func, LerpFunctionInterval, LerpHprInterval, LerpPosInterval,
                                            Parallel, Sequence, SoundInterval, Wait)
from panda3d.core import Fog, Point3, Vec3

from toontown.safezone.TrolleyConstants import TOON_BOARD_TIME, TROLLEY_EXIT_TIME
from toontown.toon import Toon

# The regular game's trolley track, relative to the trolley station.
EXIT_DISTANCE = 35.0
BOARD_CAM = (Point3(-35, 0, 8), Point3(-90, 0, 0))
LEAVE_CAM = (Point3(0, 18.55, 3.75), Point3(-180, 0, 0))
FADE_TIME = 1.5


def seatPos(index):
    return Point3(-5, -4.5 + index * 3, 1.4)


def sitPos(index):
    return Point3(-3.9, -4.5 + index * 3, 3.0)


class TrolleyRide:
    notify = DirectNotifyGlobal.directNotify.newCategory('SurvivalEscape')

    def __init__(self, game, station, car):
        self.game = game
        self.station = station
        self.car = car
        self.track = None
        self.toons = []
        self.ownToon = None
        self.mover = None
        self.fog = None
        self.carParent = car.getParent()
        self.carTransform = car.getTransform()
        self.bell = base.loader.loadSfx('phase_4/audio/sfx/SZ_trolley_bell.ogg')
        self.away = base.loader.loadSfx('phase_4/audio/sfx/SZ_trolley_away.ogg')
        self.__findParts()

    def __findParts(self):
        # Like DistributedTrolley.generate: each key and wheel turns about a
        # reference node left where it started.
        self.parts = []
        for name, kind in (('key', 'key'), ('front_wheels', 'wheel'), ('back_wheels', 'wheel')):
            for part in self.car.findAllMatches('**/' + name):
                ref = self.car.attachNewNode(name + 'Ref')
                ref.setPosHpr(part, 0, 0, 0, 0, 0, 0)
                self.parts.append((part, ref, kind, part.getTransform()))

    def __animate(self, t, keyAngle, wheelAngle):
        for part, ref, kind, init in self.parts:
            part.setH(ref, t * (keyAngle if kind == 'key' else wheelAngle))

    # --- The riders ---

    def __riders(self):
        game = self.game
        toon = Toon.Toon()
        toon.setDNA(game.dna)
        toon.setName(game.name)
        toon.setPickable(0)
        toon.reparentTo(game.arena.root)
        pos = game.player.getPos()
        toon.setPos(pos[0], pos[1], game.arena.groundZ(pos[0], pos[1]) or pos[2])
        toon.setH(game.player.getH())
        toon.nametag3d.stash()
        toon.startBlink()
        self.ownToon = toon
        riders = [toon]
        for npc in game.npcs:
            if not npc.down:
                npc.stopSteps()
                # Whatever pie was in hand mid-throw stays behind.
                for hand in npc.toon.getRightHands():
                    for prop in hand.getChildren():
                        prop.removeNode()
                riders.append(npc.toon)
        return riders[:4]

    def __board(self, toon, index):
        toon.wrtReparentTo(self.car)
        toon.loop('run')
        toon.headsUp(seatPos(index))
        sitStart = toon.getDuration('sit-start') or 1.0
        return Sequence(LerpPosInterval(toon, TOON_BOARD_TIME * 0.75 + 0.6 * index, seatPos(index)),
                        Func(toon.loop, 'neutral'),
                        LerpHprInterval(toon, TOON_BOARD_TIME * 0.25, Point3(90, 0, 0)),
                        Parallel(Sequence(Wait(sitStart * 0.25), LerpPosInterval(toon, sitStart * 0.25, sitPos(index))),
                                 ActorInterval(toon, 'sit-start')),
                        Func(toon.loop, 'sit'))

    # --- The ride ---

    def start(self, onDone):
        self.onDone = onDone
        self.toons = self.__riders()
        # The trolley rolls along the station's own x, as in the regular game.
        self.mover = self.station.attachNewNode('trolleyMover')
        self.car.wrtReparentTo(self.mover)
        fog = Fog('SurvivalTrolleyExitFog')
        fog.setColor(0, 0, 0)
        start = self.car.getPos(self.station)
        fog.setLinearOnsetPoint(start[0] + 15, start[1], 0)
        fog.setLinearOpaquePoint(start[0] + 22, start[1], 0)
        fog.setLinearFallback(70.0, 999.0, 1000.0)
        self.fog = self.station.attachNewNode(fog)
        camera.wrtReparentTo(self.car)
        boarding = Parallel(LerpPosInterval(camera, 1.5, BOARD_CAM[0], blendType='easeInOut'),
                            LerpHprInterval(camera, 1.5, BOARD_CAM[1], blendType='easeInOut'),
                            *[self.__board(toon, i) for i, toon in enumerate(self.toons)])
        wheelAngle = EXIT_DISTANCE / (2.0 * math.pi * 0.95) * 360
        keyAngle = round(TROLLEY_EXIT_TIME) * 360
        leaving = Parallel(LerpPosInterval(self.mover, TROLLEY_EXIT_TIME, Point3(EXIT_DISTANCE, 0, 0), startPos=Point3(0, 0, 0), blendType='easeIn'),
                           LerpFunctionInterval(self.__animate, duration=TROLLEY_EXIT_TIME, blendType='easeIn', extraArgs=[keyAngle, wheelAngle]),
                           SoundInterval(self.bell, node=self.car),
                           SoundInterval(self.away, node=self.car),
                           Sequence(Wait(0.5), Parallel(LerpPosInterval(camera, 3.0, LEAVE_CAM[0], blendType='easeInOut'),
                                                        LerpHprInterval(camera, 3.0, LEAVE_CAM[1], blendType='easeInOut'))),
                           Sequence(Wait(TROLLEY_EXIT_TIME - FADE_TIME), Func(base.transitions.fadeOut, FADE_TIME)))
        self.track = Sequence(Wait(0.2), boarding, Wait(0.5), Func(self.car.setFog, self.fog.node()),
                              leaving, Func(self.__done))
        self.track.start()

    def __done(self):
        self.track = None
        if self.onDone:
            self.onDone()

    def destroy(self):
        if self.track is not None:
            self.track.pause()
            self.track = None
        self.onDone = None
        if not self.car.isEmpty() and self.car.isAncestorOf(camera):
            camera.wrtReparentTo(render)
        if self.ownToon is not None:
            self.ownToon.stopBlink()
            self.ownToon.delete()
            self.ownToon = None
        if not self.car.isEmpty():
            self.car.setFogOff()
            self.car.clearFog()
            self.car.reparentTo(self.carParent)
            self.car.setTransform(self.carTransform)
            for part, ref, kind, init in self.parts:
                part.setTransform(init)
                ref.removeNode()
        if self.mover is not None:
            self.mover.removeNode()
        if self.fog is not None:
            self.fog.removeNode()
