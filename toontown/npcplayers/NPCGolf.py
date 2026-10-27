"""Plays the NPC players' part on a golf course.

A golf course waits on each golfer's client at every step: joined, ready for
the course, ready for each hole, a tee picked, a swing taken, the ball's
flight watched, the reward seen. This answers those for the NPCs.

A swing is chosen the way a decent golfer would: the hole's own physics is
run for a handful of aims and strengths, and the one that ends nearest the
cup is taken. The player's client then flies the ball, as online one of the
golfers' clients flew every ball.
"""

import math
import random

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import Vec3

from toontown.golf import DistributedGolfCourseAI as CourseAI

# Seconds an NPC takes to pick a tee, and to line up a swing.
TEE_TIME = (1.5, 3.0)
AIM_TIME = (2.5, 5.0)
# How many swings an NPC tries out before taking the best one. A few more
# would make them sink everything.
TRIES = 10


class NPCGolf:
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCGolf')

    def __init__(self, manager):
        self.manager = manager
        self.air = manager.air
        # What each NPC is waiting to do, and when: doId -> (turn, time).
        self.pending = {}

    def play(self, npc, course):
        if npc.doId not in course.avIdList:
            return
        state = course.state
        avState = course.avStateDict.get(npc.doId)
        if avState == CourseAI.EXITED:
            return
        # The last golfer to answer sets the course going, which loads the
        # next hole; that has to wait until the player's client is done
        # loading, so the NPCs answer after the player.
        if state == 'WaitJoin' and avState != CourseAI.JOINED and self.playersAt(course, CourseAI.JOINED):
            npc.asSender(course.setAvatarJoined)
        elif state == 'WaitReadyCourse' and avState != CourseAI.READY and self.playersAt(course, CourseAI.READY):
            npc.asSender(course.setAvatarReadyCourse)
        elif state == 'WaitReward':
            self.finishReward(npc, course)
        hole = course.currentHole
        if hole is None or hole.isDeleted():
            return
        if state == 'WaitReadyHole' and avState != CourseAI.ONHOLE and self.playersAt(course, CourseAI.ONHOLE):
            npc.asSender(hole.setAvatarReadyHole)
        if state == 'PlayHole':
            self.playHole(npc, course, hole)

    def playersAt(self, course, avState):
        # A player who has gone on a step is past this one too, except on a
        # new hole, where the last hole's BALLIN is not ready for it.
        def done(state):
            if state == CourseAI.EXITED or state == avState:
                return True
            return avState != CourseAI.ONHOLE and state is not None and avState < state < CourseAI.BALLIN
        return all(done(course.avStateDict.get(avId)) for avId in course.avIdList if not self.isNPC(avId))

    def finishReward(self, npc, course):
        barrier = getattr(course, 'rewardBarrier', None)
        if barrier is None or npc.doId not in barrier.pendingToons:
            return
        # Not before the player has seen the reward, so the scoreboard isn't
        # pulled away from under them.
        players = [avId for avId in barrier.pendingToons if not self.isNPC(avId)]
        if not players:
            npc.asSender(course.setDoneReward)

    def isNPC(self, avId):
        av = self.air.doId2do.get(avId)
        return av is not None and getattr(av, 'isNPCPlayer', lambda: False)()

    def playHole(self, npc, course, hole):
        now = globalClock.getFrameTime()
        barrier = getattr(hole, 'barrierPlayback', None)
        if hole.state == 'WaitPlayback':
            if barrier is not None and npc.doId in barrier.pendingToons:
                npc.asSender(hole.turnDone)
            return
        if hole.activeGolferId != npc.doId or hole.state not in ('WaitTee', 'WaitSwing'):
            self.pending.pop(npc.doId, None)
            return
        turn = (hole.doId, hole.state, course.getCurHoleScore(npc.doId))
        waiting = self.pending.get(npc.doId)
        if waiting is None or waiting[0] != turn:
            delay = TEE_TIME if hole.state == 'WaitTee' else AIM_TIME
            self.pending[npc.doId] = (turn, now + random.uniform(*delay))
            return
        if now < waiting[1]:
            return
        del self.pending[npc.doId]
        if hole.state == 'WaitTee':
            tee = self.pickTee(hole)
            npc.asSender(hole.setAvatarTee, tee)
        else:
            self.swing(npc, course, hole)

    def pickTee(self, hole):
        cup = hole.holePositions[0]
        distances = [(Vec3(tee - cup).length(), index) for index, tee in enumerate(hole.teePositions)]
        return min(distances)[1]

    def swing(self, npc, course, hole):
        start = Vec3(hole.ballPos[npc.doId])
        cycleTime = hole.getCycleTime()
        objectData = hole.getCommonObjectData()
        power, dirX, dirY = self.chooseSwing(hole, start, cycleTime, objectData)
        self.notify.debug('NPC %d swings %d at (%.2f, %.2f) from %s' % (npc.doId, power, dirX, dirY, start))
        stats = self.manager.stats
        stats['golf swings'] = stats.get('golf swings', 0) + 1
        npc.asSender(hole.postSwingState, cycleTime, power, start[0], start[1], start[2], dirX, dirY,
                     random.uniform(2, 6), objectData)

    def chooseSwing(self, hole, start, cycleTime, objectData):
        cup = min(hole.holePositions, key=lambda p: (Vec3(p) - start).length())
        toCup = Vec3(cup) - start
        heading = math.atan2(toCup[1], toCup[0])
        distance = toCup.length()
        # A first guess at the strength from the distance, then spread out.
        guess = max(10.0, min(100.0, distance * 2.0))
        best = None
        for i in range(TRIES):
            if i == 0:
                angle, power = heading, guess
            else:
                angle = heading + random.gauss(0, 0.25)
                power = max(5.0, min(100.0, random.gauss(guess, 25)))
            power = int(power)
            dirX, dirY = math.cos(angle), math.sin(angle)
            end, inHole = self.tryOut(hole, start, cycleTime, objectData, power, dirX, dirY)
            score = 0 if inHole else (Vec3(cup) - end).length()
            if best is None or score < best[0]:
                best = (score, power, dirX, dirY)
            if inHole:
                break
        return best[1:]

    def tryOut(self, hole, start, cycleTime, objectData, power, dirX, dirY):
        hole.useCommonObjectData(objectData)
        hole.trackRecordBodyFlight(hole.ball, cycleTime, power, start, dirX, dirY)
        movie = hole.recording
        last = movie[max(len(movie) - 2, 0)]
        return Vec3(last[1], last[2], last[3]), bool(hole.ballInHoleFrame)
