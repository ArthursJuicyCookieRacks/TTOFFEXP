from panda3d import core as PM
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObject import DistributedObject
from direct.interval import IntervalGlobal as IG
from toontown.battle import BattleProps
from toontown.cogdominium import CogdoCraneGameConsts as GameConsts
from toontown.suit.Suit import Suit


class DistCogdoCraneCog(Suit, DistributedObject):
    # A cog with a coin for the Stomp-O-Matic: out of its hallway, down its
    # lane to the machine, the coin in the slot, and off on its propeller.
    # Hit with a money bag on the way, it drops the coin and sits dazed.

    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        Suit.__init__(self)
        self._moveIval = None
        self._gameId = 0
        self.entranceId = 0
        self.walkStart = 0
        self.state = 'Walk'
        self.hit = False
        self.prop = None
        self.coin = None

    def setGameId(self, gameId):
        self._gameId = gameId

    def getGame(self):
        return self.cr.doId2do.get(self._gameId)

    def setDNAString(self, dnaString):
        Suit.setDNAString(self, dnaString)

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)
        self.setPickable(0)
        game = self.getGame()
        if game:
            game.cogs[self.doId] = self
        self.reparentTo(game.getSceneRoot() if game else render)
        self._startWalk()

    def disable(self):
        game = self.getGame()
        if game:
            game.cogs.pop(self.doId, None)
        self._stopMoveIval()
        self._removeProps()
        self.detachNode()
        DistributedObject.disable(self)

    def delete(self):
        Suit.delete(self)
        DistributedObject.delete(self)

    # --- Where it walks ---

    def _lanePos(self, distance):
        return GameConsts.lanePoint(GameConsts.LaneAngles[self.entranceId], distance)

    def setSpawnInfo(self, entranceId, timestamp):
        self.entranceId = entranceId
        self.walkStart = globalClockDelta.networkToLocalTime(timestamp, bits=16)
        if self.isGenerated():
            self._startWalk()

    def _walkDuration(self):
        return (GameConsts.HallwayDistance - GameConsts.MachineDistance) / GameConsts.CogWalkSpeed

    def _startWalk(self):
        self._stopMoveIval()
        startPos = self._lanePos(GameConsts.HallwayDistance)
        endPos = self._lanePos(GameConsts.MachineDistance)
        self.setPos(startPos)
        self.setH(GameConsts.LaneAngles[self.entranceId] + 180)
        self.loop('walk')
        self._moveIval = IG.Sequence(IG.LerpPosInterval(self, self._walkDuration(), endPos, startPos=startPos),
                                     IG.Func(self.loop, 'neutral'))
        self._moveIval.start(max(0.0, globalClock.getFrameTime() - self.walkStart))

    def isWalking(self):
        return self.state == 'Walk' and self._moveIval is not None and self._moveIval.isPlaying()

    def canBeHit(self):
        return self.state in ('Walk', 'Insert') and not self.hit

    def isHitBy(self, pos):
        # pos: a money bag's middle, in render space.
        here = self.getPos(render)
        dx, dy = pos[0] - here[0], pos[1] - here[1]
        return dx * dx + dy * dy < GameConsts.CogHitRadius ** 2 and pos[2] < here[2] + GameConsts.CogHitHeight

    def markHit(self):
        self.hit = True

    def predictPos(self, dt):
        # Where it will be in dt seconds, or None once it stops walking.
        if self.state != 'Walk':
            return None
        t = globalClock.getFrameTime() - self.walkStart + dt
        d = GameConsts.HallwayDistance - t * GameConsts.CogWalkSpeed
        if d < GameConsts.MachineDistance:
            return None
        return self._lanePos(d)

    # --- What the AI says happened ---

    def insertCoin(self, timestamp):
        # At the machine: a coin out of the pocket and into the slot.
        if self.state != 'Walk':
            return
        self.state = 'Insert'
        self._stopMoveIval()
        self.setPos(self._lanePos(GameConsts.MachineDistance))
        game = self.getGame()
        coin = self._makeCoin(game)
        hand = self.find('**/joint_Rhold')
        if hand.isEmpty():
            hand = self
        anim = 'reach' if self.getAnimControl('reach') else 'neutral'
        track = IG.Sequence(IG.ActorInterval(self, anim, duration=1.2) if anim == 'reach' else IG.Wait(1.2),
                            IG.Func(self.loop, 'neutral'))
        if coin is not None:
            track = IG.Parallel(track, IG.Sequence(
                IG.Func(coin.reparentTo, hand), IG.Func(coin.setPos, 0, 0, 0),
                IG.Wait(0.6), IG.Func(coin.wrtReparentTo, render),
                IG.LerpPosInterval(coin, 0.4, PM.Point3(0, 0, 4.5), blendType='easeIn'),
                IG.Func(coin.removeNode),
                IG.Func(game.coinIn, self) if game else IG.Wait(0)))
        self._moveIval = IG.Sequence(track, IG.Wait(max(0.0, GameConsts.CogInsertDuration - 1.2)), self._flyAwayIval())
        self._moveIval.start(max(0.0, globalClockDelta.localElapsedTime(timestamp, bits=16)))

    def _makeCoin(self, game):
        if game is None or not getattr(game, 'coinModel', None):
            return None
        # The coin model is 20 across and sits off its origin.
        self.coin = PM.NodePath('coin')
        model = game.coinModel.copyTo(self.coin)
        model.setPos(0, 11.2, -9.6)
        self.coin.setScale(0.07)
        return self.coin

    def setStunned(self, timestamp):
        # Knocked about by a money bag (or the game is over): dazed, then off.
        elapsed = max(0.0, globalClockDelta.localElapsedTime(timestamp, bits=16))
        self.state = 'Stunned'
        self.hit = True
        self._stopMoveIval()
        stun = max(0.0, GameConsts.CogStunDuration - elapsed)
        track = IG.Sequence()
        if stun > 0:
            track.append(IG.ActorInterval(self, 'pie-small-react') if self.getAnimControl('pie-small-react') else IG.Wait(0))
            track.append(IG.Func(self.loop, 'neutral'))
            stars = BattleProps.globalPropPool.getProp('stun')
            head = self.getHeadParts()[0] if self.getHeadParts() else self
            p1, p2 = PM.Point3(), PM.Point3()
            head.calcTightBounds(p1, p2)
            track = IG.Parallel(track, IG.Sequence(IG.Func(stars.reparentTo, head), IG.Func(stars.setZ, max(0.0, p2[2] - 1.0)),
                                                   IG.Func(stars.loop, 'stun'), IG.Wait(stun), IG.Func(stars.cleanup),
                                                   IG.Func(stars.removeNode)))
            track = IG.Sequence(track, IG.Wait(max(0.0, stun - track.getDuration())))
        self._moveIval = IG.Sequence(track, self._flyAwayIval())
        self._moveIval.start()
        game = self.getGame()
        if game and stun > 0:
            game.cogStunned(self)

    def _flyAwayIval(self):
        def attach():
            self.prop = BattleProps.globalPropPool.getProp('propeller')
            head = self.find('**/joint_head')
            self.prop.reparentTo(head if not head.isEmpty() else self)
            self.prop.loop('propeller')

        dur = GameConsts.CogFlyAwayDuration
        landing = IG.ActorInterval(self, 'landing', loop=0, startTime=self.getDuration('landing'), endTime=0.0) \
            if self.getAnimControl('landing') else IG.Wait(0)
        return IG.Sequence(
            IG.Func(self._setCogState, 'Fly'), IG.Func(attach),
            IG.Parallel(landing,
                        IG.Sequence(IG.Wait(0.8), IG.LerpPosInterval(self, dur - 0.8, self._getFlyAwayDest, blendType='easeIn')),
                        IG.Sequence(IG.Wait(dur - 1.0), IG.Func(self.setTransparency, 1),
                                    self.colorScaleInterval(1.0, PM.VBase4(1, 1, 1, 0)))),
            IG.Func(self.hide))

    def _setCogState(self, state):
        self.state = state

    def _getFlyAwayDest(self):
        return self.getPos() + PM.Vec3(0, 0, GameConsts.CogFlyAwayHeight)

    def _stopMoveIval(self):
        if self._moveIval:
            self._moveIval.pause()
            self._moveIval = None

    def _removeProps(self):
        if self.prop:
            self.prop.cleanup()
            self.prop.removeNode()
            self.prop = None
        if self.coin:
            self.coin.removeNode()
            self.coin = None
