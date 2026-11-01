"""What every Survival preview map tells the arena.

A map builds itself under the arena's root and says where the player
starts and where the three stations go: Mickey (the gag upgrade), the
fisherman (the tonics) and the accessory trunk (the mystery box). It also
says how big it is, where cogs may land and how the night looks.
"""

from panda3d.core import Point3, Vec4

from toontown.survival.previewmaps.MapKit import MapKit


class PreviewMap:
    KEY = ''
    TITLE = ''
    DESCRIPTION = ''
    # (Point3, heading) for each.
    PLAYER_START = (Point3(0, 0, 0), 0)
    MICKEY_SPOT = (Point3(0, 10, 0), 180)
    FISHERMAN_SPOT = (Point3(10, 0, 0), 90)
    TRUNK_SPOT = (Point3(-10, 0, 0), -90)
    # How far from the middle the reach grid runs, and the ring cogs land in.
    REACH_SPAN = 150.0
    SPAWN_RING = (40.0, 140.0)
    # (Point3, radius): no cog lands in these.
    NO_LANDING = ()
    # The night.
    NIGHT_SCALE = Vec4(0.5, 0.5, 0.6, 1)
    SKY_FILE = 'phase_3.5/models/props/BR_sky'
    SKY_COLOR = Vec4(0.22, 0.24, 0.36, 1)
    BACKGROUND = Vec4(0.05, 0.05, 0.1, 1)
    FOG = None  # ((r, g, b), exp density)
    # Ambient colour, moon colour, moon hpr: shading on the map's own
    # pieces (toons and cogs keep the game's usual unlit look).
    LIGHT = ((0.5, 0.5, 0.55), (0.75, 0.75, 0.85), (30, -50, 0))

    def __init__(self, root):
        self.root = root
        self.kit = MapKit(root)
        self.tasks = []
        self.build()
        self.kit.finish()
        self.__light()
        self.afterFinish()

    def __light(self):
        from panda3d.core import AmbientLight, DirectionalLight
        ambient, moon, hpr = self.LIGHT
        a = AmbientLight('mapAmbient')
        a.setColor(Vec4(ambient[0], ambient[1], ambient[2], 1))
        d = DirectionalLight('mapMoon')
        d.setColor(Vec4(moon[0], moon[1], moon[2], 1))
        self.lights = [self.root.attachNewNode(a), self.root.attachNewNode(d)]
        self.lights[1].setHpr(*hpr)
        lit = [self.kit.visual] + [n for k, n in self.kit.groups.items() if k not in ('glow', 'static', 'decal')]
        lit += getattr(self, 'litNodes', [])
        for node in lit:
            for light in self.lights:
                node.setLight(light)

    def build(self):
        raise NotImplementedError

    def afterFinish(self):
        pass

    def addTask(self, func, name):
        task = taskMgr.add(func, '%s-%s' % (self.KEY, name))
        self.tasks.append(task)
        return task

    def destroy(self):
        for task in self.tasks:
            taskMgr.remove(task)
        self.tasks = []
        self.kit.destroy()
