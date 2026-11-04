import math
import random

from direct.directnotify import DirectNotifyGlobal
from toontown.cogdominium.DistCogdoGameAI import DistCogdoGameAI
from toontown.cogdominium import CogdoBoardroomGameConsts as Consts
from toontown.cogdominium.CogdoBoardroomLayout import BoardroomLayout, INVULNERABLE, HOP


def _isNPC(av):
    return av is not None and getattr(av, 'isNPCPlayer', lambda: False)()


class DistCogdoBoardroomGameAI(DistCogdoGameAI):
    # Boardroom Hijinks, the Bossbot field office. The toons crash a
    # meeting and run the length of the boardroom table to the exit past
    # the chairman, picking up the memos on it. The Boss Cogs round the
    # table tee off golf balls and throw paperwork at them, the minions
    # flying over drop pencils, anvils and stacks of paperwork, and now and
    # then one knocks an oil can over and the table turns slippery. A hit
    # costs laff and memos; the memos a toon brings out of the exit are a
    # Toon-Up for everyone at the end.
    notify = DirectNotifyGlobal.directNotify.newCategory("DistCogdoBoardroomGameAI")

    def __init__(self, air, interior):
        DistCogdoGameAI.__init__(self, air, interior)
        self.seed = random.randrange(1, 1 << 30)
        self.layout = BoardroomLayout(self.seed, self.getDifficulty())
        self.memosTaken = set()
        self.powerUpsTaken = set()
        # The memos each toon carries, and those brought out.
        self.carried = {}
        self.banked = 0
        self.exited = set()
        self.progress = {}
        self._lastPos = {}
        self._velocity = {}
        self.invulnerableUntil = {}
        self.lastHit = {}
        self.spilled = {}
        self.nextCan = 0
        # The golf office after the slide.
        self.phase = 'slide'
        self.golfStart = 0
        self.golfCogs = {}
        self.nextGolfCog = 1
        # Barrels knocked out of cogs' hands, lying on the office floor
        # (dropId: (x, y)): another cog will come for them. A barrel is only
        # lost once a cog carries it into an elevator; those still on the
        # floor when time is up are the toons'.
        self.drops = {}
        self.nextDrop = 1
        self.barrelsHome = Consts.NumBarrels
        self.barrelsLost = 0
        self.lastSwing = {}
        self.leftGolf = set()

    def delete(self):
        for name in ('game-over', 'boss', 'minion', 'oil', 'golf-over', 'golf-spawn', 'golf-leave'):
            taskMgr.remove(self.uniqueName(name))
        taskMgr.removeTasksMatching(self.uniqueName('land') + '*')
        taskMgr.removeTasksMatching(self.uniqueName('golfcog') + '*')
        taskMgr.removeTasksMatching(self.uniqueName('golfball') + '*')
        DistCogdoGameAI.delete(self)

    def getDifficulty(self):
        # The playground's difficulty and the office's level together.
        zone = DistCogdoGameAI.getDifficulty(self)
        bldg = getattr(self.interior, 'bldg', None)
        level = getattr(bldg, 'difficulty', 0) / Consts.LevelDifficultyMax
        level = max(0.0, min(1.0, level))
        return (1.0 - Consts.LevelWeight) * zone + Consts.LevelWeight * level

    def getLayout(self):
        return [self.seed, int(round(self.layout.difficulty * 100))]

    def now(self):
        return globalClock.getRealTime() - (self.startTime or globalClock.getRealTime())

    # --- The game ---

    def startGame(self):
        d = self.layout.difficulty
        # (A test run can go straight on to the golf: AUTOPLAY_GOLF_ONLY.)
        import os
        slide = 6.0 if os.environ.get('AUTOPLAY_GOLF_ONLY') else Consts.SlideDuration
        taskMgr.doMethodLater(slide, self.__slideOver, self.uniqueName('game-over'))
        # A moment for the toons to get up the ramp before the meeting
        # notices them.
        taskMgr.doMethodLater(3.0, self.__bossAttack, self.uniqueName('boss'))
        taskMgr.doMethodLater(5.0, self.__minionDrop, self.uniqueName('minion'))
        taskMgr.doMethodLater(Consts.lerpDifficulty(Consts.OilSpillPeriodRange, d) * 0.6, self.__oilSpill, self.uniqueName('oil'))

    def __slideOver(self, task):
        # Time is up on the table: whoever is still on it loses the memos
        # they carry, and everyone goes on to the golf office.
        self.__startGolf()
        return task.done

    def endGame(self):
        for name in ('game-over', 'boss', 'minion', 'oil', 'golf-over', 'golf-spawn', 'golf-leave'):
            taskMgr.remove(self.uniqueName(name))
        taskMgr.removeTasksMatching(self.uniqueName('golfcog') + '*')
        taskMgr.removeTasksMatching(self.uniqueName('golfball') + '*')
        # Only the memos brought out count (the ones still on the table when
        # time was up are lost, as in the Sellbot maze), and the laff
        # barrels the cogs didn't get away with: a barrel is only lost once
        # a cog has carried it all the way into an elevator.
        saved = max(0, Consts.NumBarrels - self.barrelsLost)
        self.interior.setGameMemos(self.banked + saved * Consts.LaffPerBarrel)

    # --- The golf office ---

    def __startGolf(self):
        if self.phase != 'slide' or self.finished:
            return
        self.phase = 'golf'
        for name in ('game-over', 'boss', 'minion', 'oil'):
            taskMgr.remove(self.uniqueName(name))
        for avId in self.stillRunning():
            self.carried.pop(avId, None)
        # The elevator ride over and the golf office's intro come first; the
        # golf's clock starts after them.
        self.golfStart = globalClock.getRealTime() + Consts.GolfLeadIn
        self.sendUpdate('startGolf', [self.getNetworkTime()])
        taskMgr.doMethodLater(Consts.GolfLeadIn + Consts.GolfDuration, self.__golfOver, self.uniqueName('golf-over'))
        taskMgr.doMethodLater(Consts.GolfLeadIn + 4.0, self.__golfSpawn, self.uniqueName('golf-spawn'))

    def requestGolfSkip(self):
        # The green button on the golf intro, as on the slide's: once every
        # player has pressed it, the golf starts straight away.
        avId = self.getSenderToon()
        if not avId or self.phase != 'golf' or self.finished:
            return
        now = globalClock.getRealTime()
        if now > self.golfStart - 1.5 or now < self.golfStart - Consts.GolfIntroDuration - 1.0:
            return
        self.golfSkips = getattr(self, 'golfSkips', set())
        self.golfSkips.add(avId)
        players = [a for a in self.stillRunning() if not self.isNPCToon(a)]
        if not all(a in self.golfSkips for a in players):
            return
        self.golfStart = now + 1.0
        taskMgr.remove(self.uniqueName('golf-over'))
        taskMgr.remove(self.uniqueName('golf-spawn'))
        taskMgr.doMethodLater(1.0 + Consts.GolfDuration, self.__golfOver, self.uniqueName('golf-over'))
        taskMgr.doMethodLater(1.0 + 4.0, self.__golfSpawn, self.uniqueName('golf-spawn'))
        self.sendUpdate('golfSkip', [self.getNetworkTime()])

    def isNPCToon(self, avId):
        av = self.air.doId2do.get(avId)
        try:
            from toontown.npcplayers.NPCBattleCrew import isNPC
            return isNPC(av)
        except Exception:
            return bool(getattr(av, 'isNPCPlayer', False))

    def __golfOver(self, task):
        # Time is up: the cogs still about go, the toons' elevator opens,
        # and the toons walk into it themselves (as into the other field
        # offices' exits) to ride on up to the executive suite.
        if self.finished or self.phase != 'golf':
            return task.done
        stats = getattr(self, 'golfStats', {})
        self.notify.info('golf over: %s cogs came, swings %s, hits %s, barrels home %d, lost %d' % (
            stats.get('spawned'), stats.get('swings'), stats.get('hits'), self.barrelsHome, self.barrelsLost))
        self.phase = 'leave'
        self.leftGolf = set()
        taskMgr.remove(self.uniqueName('golf-spawn'))
        taskMgr.removeTasksMatching(self.uniqueName('golfcog') + '*')
        taskMgr.removeTasksMatching(self.uniqueName('golfball') + '*')
        # Every cog still about blows up where it stands, dropping any
        # barrel it had: no cog got those (or the ones on the floor) into
        # an elevator, so they're all the toons'.
        for cogId, cog in self.golfCogs.items():
            if not cog['alive']:
                continue
            cog['alive'] = False
            if cog['carrying']:
                self.barrelsHome += 1
                cog['carrying'] = False
        self.barrelsHome = min(Consts.NumBarrels, self.barrelsHome + len(self.drops))
        self.drops = {}
        self.__sendDrops()
        self.sendUpdate('golfBarrelsHome', [self.barrelsHome])
        self.sendUpdate('golfOver', [self.getNetworkTime()])
        taskMgr.doMethodLater(Consts.GolfLeaveTime, self.__leaveOver, self.uniqueName('golf-leave'))
        return task.done

    def requestGolfLeave(self):
        avId = self.getSenderToon() if hasattr(self, 'getSenderToon') else self.air.getAvatarIdFromSender()
        if self.phase != 'leave' or self.finished or avId not in self.toons or avId in self.leftGolf:
            return
        self.leftGolf.add(avId)
        self.sendUpdate('toonLeftGolf', [avId])
        if not [t for t in self.getActiveToons() if t not in self.leftGolf]:
            # All in: the doors close on them, and up they go.
            taskMgr.remove(self.uniqueName('golf-leave'))
            taskMgr.doMethodLater(Consts.GolfDoorTime + 0.5, self.__leaveOver, self.uniqueName('golf-leave'))

    def __leaveOver(self, task):
        if not self.finished:
            self.finishGame()
        return task.done

    def golfTime(self):
        return globalClock.getRealTime() - self.golfStart

    def __golfSpawn(self, task):
        if self.finished:
            return task.done
        d = self.layout.difficulty
        walking = [c for c in self.golfCogs.values() if c['alive']]
        if len(walking) < int(round(Consts.lerpDifficulty(Consts.GolfMaxCogsRange, d))):
            self.__makeGolfCog(d)
        task.delayTime = Consts.lerpDifficulty(Consts.GolfSpawnPeriodRange, d) * random.uniform(0.8, 1.2)
        return task.again

    def __makeGolfCog(self, d):
        cogId = self.nextGolfCog
        self.nextGolfCog += 1
        self.golfStats = getattr(self, 'golfStats', {'spawned': 0, 'swings': {}, 'hits': {}})
        self.golfStats['spawned'] += 1
        top = max(2, int(round(2 + d * (len(Consts.GolfCogNames) - 2))))
        name = random.randrange(top)
        # Out of one of the three elevators, and away by another.
        entry = random.randrange(len(Consts.GolfElevators))
        exit = random.choice([i for i in range(len(Consts.GolfElevators)) if i != entry])
        side = entry * 4 + exit
        px = random.uniform(-2.5, 2.5)
        exitY = 0.0
        speed = Consts.lerpDifficulty(Consts.GolfCogSpeedRange, d) * random.uniform(0.9, 1.1)
        # A barrel lying on the floor is easier pickings than the pile.
        wanted = set(c.get('drop') for c in self.golfCogs.values() if c['alive'])
        free = [i for i in self.drops if i not in wanted]
        drop = random.choice(free) if free and random.random() < 0.75 else None
        target = self.drops[drop] if drop is not None else None
        path = Consts.golfCogPath(px, side, exitY, speed, target)
        cog = {'id': cogId, 'path': path, 'start': self.golfTime(), 'alive': True, 'carrying': False, 'drop': drop}
        self.golfCogs[cogId] = cog
        tx, ty = target if target else (0.0, 0.0)
        self.sendUpdate('golfCog', [cogId, name, px, side, exitY, speed, self.getNetworkTime(), target is not None, tx, ty])
        taskMgr.doMethodLater(path[3], self.__golfPickup, self.uniqueName('golfcog-pick-%d' % cogId), extraArgs=[cogId])
        taskMgr.doMethodLater(path[5], self.__golfEscape, self.uniqueName('golfcog-out-%d' % cogId), extraArgs=[cogId])

    def __golfPickup(self, cogId):
        cog = self.golfCogs.get(cogId)
        if not cog or not cog['alive'] or self.finished:
            return
        if cog.get('drop') is not None:
            if self.drops.pop(cog['drop'], None) is not None:
                cog['carrying'] = True
                self.__sendDrops()
        elif self.barrelsHome > 0:
            self.barrelsHome -= 1
            cog['carrying'] = True
        self.sendUpdate('golfCogPickup', [cogId, cog['carrying'], self.barrelsHome])

    def __golfEscape(self, cogId):
        cog = self.golfCogs.get(cogId)
        if not cog or not cog['alive'] or self.finished:
            return
        cog['alive'] = False
        if cog['carrying']:
            self.barrelsLost += 1
        self.sendUpdate('golfCogEscaped', [cogId, cog['carrying'], self.barrelsHome])
        cog['carrying'] = False

    def requestGolfSwing(self, h, power):
        avId = self.air.getAvatarIdFromSender()
        if self.phase != 'golf' or self.finished or avId not in self.toons or avId in self.sadToons:
            return
        now = self.golfTime()
        if now < 0:
            return
        if now - self.lastSwing.get(avId, -99) < Consts.SwingCooldown:
            return
        self.lastSwing[avId] = now
        self.golfStats = getattr(self, 'golfStats', {'spawned': 0, 'swings': {}, 'hits': {}})
        self.golfStats['swings'][avId] = self.golfStats['swings'].get(avId, 0) + 1
        power = max(0.0, min(1.0, power))
        self.sendUpdate('golfSwing', [avId, h, power, self.getNetworkTime()])
        av = self.air.doId2do.get(avId)
        if _isNPC(av):
            # No client rolls an NPC's ball for us: roll it here, the same
            # way the clients do.
            tx, ty = Consts.GolfTees[self.toons.index(avId) % len(Consts.GolfTees)] if avId in self.toons else (0, Consts.GolfTees[0][1])
            x, y, vx, vy = Consts.golfBallStart(tx, ty, h, power)
            ball = {'x': x, 'y': y, 'vx': vx, 'vy': vy}
            taskMgr.add(self.__rollBall, self.uniqueName('golfball-%d' % random.randrange(1 << 30)),
                        extraArgs=[avId, ball], appendTask=True)

    def __rollBall(self, avId, ball, task):
        if self.finished or self.phase != 'golf':
            return task.done
        dt = 0.05
        while ball.get('t', 0) < task.time:
            ball['t'] = ball.get('t', 0) + dt
            ball['x'], ball['y'], ball['vx'], ball['vy'] = Consts.golfBallStep(ball['x'], ball['y'], ball['vx'], ball['vy'], dt)
            if math.hypot(ball['vx'], ball['vy']) < Consts.BallStopSpeed:
                return task.done
            now = self.golfTime() - (task.time - ball['t'])
            for cogId, cog in list(self.golfCogs.items()):
                if not cog['alive']:
                    continue
                x, y, h, leg = Consts.golfCogPos(cog['path'], now - cog['start'])
                if leg < 3 and math.hypot(x - ball['x'], y - ball['y']) < Consts.GolfCogRadius:
                    self.__golfHit(cogId, avId)
                    return task.done
        return task.cont

    def golfCogsNow(self):
        # Where each walking cog is, for the NPCs' aim.
        now = self.golfTime()
        out = []
        for cogId, cog in self.golfCogs.items():
            if cog['alive']:
                out.append((cogId, cog, now - cog['start']))
        return out

    def requestGolfHit(self, cogId):
        self.__golfHit(cogId, self.air.getAvatarIdFromSender())

    def __golfHit(self, cogId, avId):
        cog = self.golfCogs.get(cogId)
        if self.phase != 'golf' or self.finished or not cog or not cog['alive']:
            return
        cog['alive'] = False
        self.golfStats = getattr(self, 'golfStats', {'spawned': 0, 'swings': {}, 'hits': {}})
        self.golfStats['hits'][avId] = self.golfStats['hits'].get(avId, 0) + 1
        taskMgr.remove(self.uniqueName('golfcog-pick-%d' % cogId))
        taskMgr.remove(self.uniqueName('golfcog-out-%d' % cogId))
        if cog['carrying']:
            # It drops the barrel where it's hit, for the next cog to come
            # and take.
            x, y, h, leg = Consts.golfCogPos(cog['path'], self.golfTime() - cog['start'])
            self.__dropBarrel(x, y)
            cog['carrying'] = False
        self.sendUpdate('golfCogHit', [cogId, avId, self.barrelsHome])

    def __dropBarrel(self, x, y, send=True):
        # On a clear bit of floor, nudged in toward the pile if needed.
        px, py = Consts.BarrelPile
        for i in range(12):
            f = i / 12.0
            cx, cy = x + (px - x) * f, y + (py - y) * f
            if not Consts.golfBlocked(cx, cy):
                x, y = cx, cy
                break
        dropId = self.nextDrop
        self.nextDrop += 1
        self.drops[dropId] = (x, y)
        if send:
            self.__sendDrops()
        return dropId

    def __sendDrops(self):
        ids = sorted(self.drops)
        self.sendUpdate('golfDrops', [ids, [self.drops[i][0] for i in ids], [self.drops[i][1] for i in ids]])

    def stillRunning(self):
        return [avId for avId in self.getActiveToons() if avId not in self.exited]

    def __track(self, avId, x, y):
        # How fast each toon is going up and across the table, from where
        # it says it is, so the Boss Cogs can lead it with a throw.
        t = self.now()
        last = self._lastPos.get(avId)
        if last is None or t - last[0] > 1.5:
            self._lastPos[avId] = (t, x, y)
            return
        dt = t - last[0]
        if dt < 0.2:
            return
        vx, vy = (x - last[1]) / dt, (y - last[2]) / dt
        ox, oy = self._velocity.get(avId, (vx, vy))
        self._velocity[avId] = (ox * 0.4 + vx * 0.6, oy * 0.4 + vy * 0.6)
        self._lastPos[avId] = (t, x, y)

    def __target(self, full=False, flight=None):
        # A toon still on the table, and the spot it will be at when the
        # throw comes down (it is sliding up the table), give or take.
        avIds = self.stillRunning()
        if not avIds:
            return None
        avId = random.choice(avIds)
        x, y, z = self.__toonPos(avId)
        if flight is not None and avId in self._velocity:
            vx, vy = self._velocity[avId]
            spread = Consts.lerpDifficulty(Consts.AimSpreadRange, self.layout.difficulty)
            tx = x + vx * flight + random.uniform(-spread, spread)
            ty = y + vy * flight + random.uniform(-spread, spread)
        else:
            tx = x + random.uniform(-Consts.AttackSpread, Consts.AttackSpread)
            ty = y + Consts.AttackLead * random.uniform(0.75, 1.3) + random.uniform(-Consts.AttackSpread, Consts.AttackSpread)
        tx = max(-Consts.TableHalfWidth + 1, min(Consts.TableHalfWidth - 1, tx))
        ty = max(Consts.TableStart + 2, min(Consts.TableEnd - 2, ty))
        if full:
            return avId, tx, ty, x, y
        return tx, ty

    def __toonPos(self, avId):
        av = self.air.doId2do.get(avId)
        if _isNPC(av):
            pos = av.getPos()
            self.__track(avId, pos[0], pos[1])
            return (pos[0], pos[1], pos[2])
        return self.progress.get(avId, (0, Consts.TableStart, Consts.TableTop))

    def __bossAttack(self, task):
        if self.finished:
            return task.done
        self.__bossThrow()
        if random.random() < Consts.lerpDifficulty(Consts.VolleyChanceRange, self.layout.difficulty):
            # Another Boss Cog joins in.
            self.__bossThrow()
        task.delayTime = Consts.lerpDifficulty(Consts.BossAttackPeriodRange, self.layout.difficulty) * random.uniform(0.75, 1.25)
        return task.again

    def __bossThrow(self):
        target = self.__target(full=True, flight=Consts.ThrowFlightTime)
        seats = self.layout.bossSeats()
        if target and seats:
            avId, tx, ty, px, py = target
            # A toon sliding past a Boss Cog close to its side of the table
            # gets the golf club; otherwise the nearest one up the table
            # tees off a golf ball at it, or throws paperwork.
            side = 1 if px > 0 else -1
            # (The toon slides on about 14 feet while the club comes round.)
            close = [i for i in seats if self.layout.seats[i][0] == side and 8 < self.layout.seats[i][1] - py < 22
                     and abs(px) > Consts.TableHalfWidth - Consts.SwipeReach]
            if close and random.random() < 0.7:
                seat = min(close, key=lambda i: self.layout.seats[i][1])
                self.__launch(Consts.Swipe, seat, (side * Consts.TableHalfWidth, self.layout.seats[seat][1]), Consts.SwipeTime)
            else:
                seat = min(seats, key=lambda i: abs(self.layout.seats[i][1] - ty) + random.uniform(0, 12))
                if random.random() < Consts.lerpDifficulty(Consts.OilThrowChanceRange, self.layout.difficulty):
                    kind = Consts.Oil
                else:
                    kind = random.choice((Consts.GolfBall, Consts.GolfBall, Consts.Paper))
                self.__launch(kind, seat, (tx, ty), Consts.ThrowFlightTime)

    def __minionDrop(self, task):
        if self.finished:
            return task.done
        avIds = self.stillRunning()
        if avIds and self.layout.minions:
            # The minion flying nearest a toon drops what it carries on it.
            t = self.now()
            avId = random.choice(avIds)
            x, y, z = self.__toonPos(avId)
            index = min(range(len(self.layout.minions)), key=lambda i: math.hypot(*(
                self.layout.minionPos(i, t)[j] - (x, y)[j] for j in (0, 1))))
            mx, my, mz = self.layout.minionPos(index, t)
            kind = random.choice((Consts.Pencil, Consts.Pencil, Consts.Paperwork, Consts.Anvil))
            self.__launch(kind, 100 + index, (mx, my), Consts.DropFallTime)
        task.delayTime = Consts.lerpDifficulty(Consts.MinionDropPeriodRange, self.layout.difficulty) * random.uniform(0.75, 1.25)
        return task.again

    def __oilSpill(self, task):
        if self.finished:
            return task.done
        cans = self.layout.oilCans
        if cans:
            # A minion swoops down and knocks the next oil can over, near
            # where the toons are if there's one up ahead of them.
            ys = [self.__toonPos(a)[1] for a in self.stillRunning()] or [Consts.TableStart]
            ahead = [i for i in range(len(cans)) if i not in self.spilled and cans[i][1] > min(ys)]
            if ahead:
                can = min(ahead, key=lambda i: cans[i][1])
                self.spilled[can] = self.now()
                self.sendUpdate('oilSpill', [can, self.getNetworkTime()])
        task.delayTime = Consts.lerpDifficulty(Consts.OilSpillPeriodRange, self.layout.difficulty) * random.uniform(0.8, 1.2)
        return task.again

    def __launch(self, kind, source, target, flight):
        x, y = target
        self.sendUpdate('attack', [kind, source, x, y, self.getNetworkTime()])
        # The NPC toons have no client to tell us they were hit: see for
        # them when it lands.
        taskMgr.doMethodLater(flight, self.__landed, self.uniqueName('land-%d' % random.randrange(1 << 30)),
                              extraArgs=[kind, x, y])

    def __landed(self, kind, x, y):
        if self.finished or self.phase != 'slide' or kind == Consts.Oil:
            return
        z = self.layout.heightAt(x, y) if kind != Consts.Swipe else Consts.TableTop
        for avId in self.stillRunning():
            av = self.air.doId2do.get(avId)
            if not _isNPC(av):
                continue
            pos = av.getPos()
            if Consts.hazardHits(kind, x, y, z, pos[0], pos[1], pos[2]):
                self.__hitToon(avId, kind)

    # --- What the toons tell us ---

    def requestProgress(self, x, y, z):
        avId = self.getSenderToon()
        if avId:
            self.progress[avId] = (x, y, z)
            self.__track(avId, x, y)

    def requestHit(self, kind):
        avId = self.getSenderToon()
        if avId and kind in Consts.Hazards and self.phase == 'slide':
            self.__hitToon(avId, kind)

    def __hitToon(self, avId, kind):
        now = self.now()
        if avId in self.exited or avId in self.sadToons:
            return
        if self.invulnerableUntil.get(avId, -1) > now or now - self.lastHit.get(avId, -99) < Consts.HitCooldown:
            return
        self.lastHit[avId] = now
        self.notify.info('%s hit by %d' % (avId, kind))
        lost = min(self.carried.get(avId, 0), Consts.Hazards[kind][2])
        self.carried[avId] = self.carried.get(avId, 0) - lost
        self.sendUpdate('toonHit', [avId, kind, lost])
        self.damageToon(avId, Consts.hazardDamage(kind, self.layout.difficulty))

    def requestMemo(self, memo):
        avId = self.getSenderToon()
        if not avId or avId in self.exited or memo in self.memosTaken or not 0 <= memo < len(self.layout.memos):
            return
        self.memosTaken.add(memo)
        self.carried[avId] = self.carried.get(avId, 0) + 1
        self.sendUpdate('memoTaken', [avId, memo, self.carried[avId]])

    def requestPowerUp(self, index):
        avId = self.getSenderToon()
        if not avId or avId in self.exited or index in self.powerUpsTaken or not 0 <= index < len(self.layout.powerUps):
            return
        self.powerUpsTaken.add(index)
        if self.layout.powerUps[index][0] == INVULNERABLE:
            self.invulnerableUntil[avId] = self.now() + Consts.InvulnerableTime
        self.sendUpdate('powerUpTaken', [avId, index])

    def requestExit(self):
        avId = self.getSenderToon()
        self.notify.info('requestExit from %s (sender %s, toons %s, exited %s)' % (
            avId, self.air.getAvatarIdFromSender(), self.toons, self.exited))
        if not avId or avId in self.exited:
            return
        self.exited.add(avId)
        self.banked += self.carried.pop(avId, 0)
        self.sendUpdate('setBanked', [self.banked])
        self.sendUpdate('toonExited', [avId])
        if not self.stillRunning():
            self.__startGolf()

    def toonWentSad(self, avId):
        # A sad toon drops what it carried.
        self.carried.pop(avId, None)
        DistCogdoGameAI.toonWentSad(self, avId)
        if not self.finished and self.started and self.getActiveToons() and not self.stillRunning():
            self.__startGolf()

    def toonLeft(self, avId):
        self.carried.pop(avId, None)
        if not self.finished and self.started and self.toons and not self.stillRunning():
            self.__startGolf()

    def getBanked(self):
        return self.banked
