from toontown.building.DistributedElevatorInt import DistributedElevatorInt

class DistributedCogdoElevatorInt(DistributedElevatorInt):

    def _getDoorsClosedInfo(self):
        return ('cogdoInterior', 'cogdoInterior')

    def _doorWall(self):
        # The field office elevator model has a flat wall across its doorway
        # (door_collisions) that does not move with the doors. The boarding
        # sphere only reaches that wall, so toons bumped it and could only
        # get in by slipping past the sides.
        model = self.getElevatorModel()
        if model is None or model.isEmpty():
            return None
        wall = model.find('**/door_collisions;+s')
        if wall.isEmpty():
            return None
        return wall

    def enterWaitCountdown(self, ts):
        DistributedElevatorInt.enterWaitCountdown(self, ts)
        wall = self._doorWall()
        if wall is not None:
            wall.stash()

    def exitWaitCountdown(self):
        DistributedElevatorInt.exitWaitCountdown(self)
        wall = self._doorWall()
        if wall is not None:
            wall.unstash()
