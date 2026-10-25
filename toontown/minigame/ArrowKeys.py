from panda3d.core import ModifierButtons
from direct.showbase.DirectObject import DirectObject
from toontown.toonbase import TouchControls

class ArrowKeys(DirectObject):
    # Each direction is both its letter and its arrow key, so the games work
    # with either (and with a controller's stick, which presses the arrows).
    UP_KEY = ('w', 'arrow_up')
    DOWN_KEY = ('s', 'arrow_down')
    LEFT_KEY = ('a', 'arrow_left')
    RIGHT_KEY = ('d', 'arrow_right')
    JUMP_KEY = ('space',)
    UP_INDEX = 0
    DOWN_INDEX = 1
    LEFT_INDEX = 2
    RIGHT_INDEX = 3
    JUMP_INDEX = 4
    NULL_HANDLERS = (None, None, None, None, None)

    def __init__(self):
        self.__jumpPost = 0
        self.__held = [set() for i in range(5)]
        self.setPressHandlers(self.NULL_HANDLERS)
        self.setReleaseHandlers(self.NULL_HANDLERS)
        self.origMb = base.buttonThrowers[0].node().getModifierButtons()
        base.buttonThrowers[0].node().setModifierButtons(ModifierButtons())
        self.enable()

    def __keys(self):
        return (self.UP_KEY, self.DOWN_KEY, self.LEFT_KEY, self.RIGHT_KEY, self.JUMP_KEY)

    def enable(self):
        self.disable()
        for index, keys in enumerate(self.__keys()):
            for key in keys:
                self.accept(key, self.__keyPressed, [index, key])
        TouchControls.request('arrowKeys')

    def disable(self):
        TouchControls.release('arrowKeys')
        self.__upPressed = 0
        self.__downPressed = 0
        self.__leftPressed = 0
        self.__rightPressed = 0
        self.__jumpPressed = 0
        self.__held = [set() for i in range(5)]
        for keys in self.__keys():
            for key in keys:
                self.ignore(key)
                self.ignore(key + '-up')

    def destroy(self):
        base.buttonThrowers[0].node().setModifierButtons(self.origMb)
        for keys in self.__keys():
            for key in keys:
                self.ignore(key)
                self.ignore(key + '-up')

    def upPressed(self):
        return self.__upPressed

    def downPressed(self):
        return self.__downPressed

    def leftPressed(self):
        return self.__leftPressed

    def rightPressed(self):
        return self.__rightPressed

    def jumpPressed(self):
        return self.__jumpPressed

    def jumpPost(self):
        jumpCache = self.__jumpPost
        self.__jumpPost = 0
        return jumpCache

    def setPressHandlers(self, handlers):
        if len(handlers) == 4:
            handlers.append(None)
        self.__checkCallbacks(handlers)
        self.__pressHandlers = handlers
        return

    def setReleaseHandlers(self, handlers):
        if len(handlers) == 4:
            handlers.append(None)
        self.__checkCallbacks(handlers)
        self.__releaseHandlers = handlers
        return

    def clearPressHandlers(self):
        self.setPressHandlers(self.NULL_HANDLERS)

    def clearReleaseHandlers(self):
        self.setReleaseHandlers(self.NULL_HANDLERS)

    def __checkCallbacks(self, callbacks):
        for callback in callbacks:
            pass

    def __doCallback(self, callback):
        if callback:
            callback()

    def __setPressed(self, index, pressed):
        if index == self.UP_INDEX:
            self.__upPressed = pressed
        elif index == self.DOWN_INDEX:
            self.__downPressed = pressed
        elif index == self.LEFT_INDEX:
            self.__leftPressed = pressed
        elif index == self.RIGHT_INDEX:
            self.__rightPressed = pressed
        else:
            self.__jumpPressed = pressed
            self.__jumpPost = pressed

    def __keyPressed(self, index, key):
        self.ignore(key)
        self.accept(key + '-up', self.__keyReleased, [index, key])
        held = self.__held[index]
        first = not held
        held.add(key)
        if first:
            # The second key of a direction held with the first changes nothing.
            self.__setPressed(index, 1)
            self.__doCallback(self.__pressHandlers[index])

    def __keyReleased(self, index, key):
        self.ignore(key + '-up')
        self.accept(key, self.__keyPressed, [index, key])
        held = self.__held[index]
        held.discard(key)
        if not held:
            self.__setPressed(index, 0)
            self.__doCallback(self.__releaseHandlers[index])
