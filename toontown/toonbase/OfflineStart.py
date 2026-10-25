"""Starts a packaged copy of the offline game (the Windows and Android builds).

A packaged game keeps its files in one place and the player's files in
another. The game's files (the multifiles, the DC file and config/release.prc)
sit next to the executable, or in the APK's assets on Android. The player's
files (toons, settings and logs) go in the user's application data folder,
which is also made the working directory, because the game writes them there
by relative path.
"""

import os
import sys
import traceback

from panda3d.core import ExecutionEnvironment, Filename, Multifile, VirtualFileMountSystem, VirtualFileSystem
from panda3d.core import loadPrcFile, loadPrcFileData

# The phase files, in the order the game needs them.
PHASES = ('3', '3.5', '4', '5', '5.5', '6', '7', '8', '9', '10', '11', '12', '13')


def getGameDir():
    if os.environ.get('TTR_GAME_DIR'):
        return Filename.fromOsSpecific(os.environ['TTR_GAME_DIR'])
    if os.environ.get('TTR_EXTRA_PRC'):
        # Extra settings for this run, e.g. software rendering on a machine
        # without a graphics card.
        loadPrcFileData('TTR_EXTRA_PRC', os.environ['TTR_EXTRA_PRC'].replace(';', '\n'))
    if sys.platform == 'android':
        return Filename('/android_asset')
    if getattr(sys, 'frozen', False):
        return Filename.fromOsSpecific(ExecutionEnvironment.getEnvironmentVariable('MAIN_DIR'))
    # Run from a checkout: the repository root.
    return Filename.fromOsSpecific(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


def getDataDir():
    dataDir = Filename(Filename.getUserAppdataDirectory(), 'TTR-Offline')
    os.makedirs(dataDir.toOsSpecific(), exist_ok=True)
    return dataDir


def mountPhases(gameDir):
    vfs = VirtualFileSystem.getGlobalPtr()
    for phase in PHASES:
        multifile = Filename(gameDir, 'phase_%s.mf' % phase)
        if vfs.exists(multifile):
            # Opened through the virtual file system, since on Android the
            # multifiles sit in the APK's assets, not on disk.
            mf = Multifile()
            if mf.openRead(multifile):
                vfs.mount(mf, Filename('/'), VirtualFileSystem.MFReadOnly)
            else:
                print('OfflineStart: could not open %s' % multifile)
        else:
            # A checkout keeps the phases as folders under resources/.
            folder = Filename(gameDir, 'resources/phase_%s' % phase)
            if vfs.isDirectory(folder):
                vfs.mount(folder, Filename('/phase_%s' % phase), VirtualFileSystem.MFReadOnly)
            else:
                print('OfflineStart: phase_%s is missing' % phase)
    # The multifiles cover the whole tree from the root, and a file that does
    # not exist yet would be looked for in the last of them, which is read
    # only (so the model cache could not save anything). The real disk goes
    # on top again, behind which the multifiles are still found.
    vfs.mount(VirtualFileMountSystem(Filename('/')), Filename('/'), 0)


def main():
    gameDir = getGameDir()
    dataDir = getDataDir()
    os.chdir(dataDir.toOsSpecific())
    from toontown.toonbase import CrashReport
    CrashReport.begin()
    print('OfflineStart: game files in %s, player files in %s' % (gameDir, dataDir))

    loadPrcFile(Filename(gameDir, 'config/release.prc'))
    loadPrcFileData('OfflineStart', '\n'.join([
        'offline-release 1',
        'auto-start-server 1',
        'dc-file %s' % Filename(gameDir, 'config/ttroff.dc'),
        'local-db-directory %s' % Filename(dataDir, 'database'),
        'account-bridge-filename %s' % Filename(dataDir, 'database/account-bridge'),
        'local-event-log-directory %s' % Filename(dataDir, 'logs/events'),
        'want-offline-launcher 1',
        'offline-game-dir %s' % gameDir,
    ]))
    if sys.platform == 'android':
        # Phones and tablets have OpenGL ES rather than desktop OpenGL, and
        # no keyboard, so the game gets on-screen controls. OpenGL ES has no
        # alpha test, which Panda3D's "dual" transparency (used by most of the
        # models) needs to leave out the see-through parts, so those draw as
        # plain alpha blending instead (m-dual 0).
        loadPrcFileData('OfflineStart Android', 'load-display pandagles2\naux-display pandagles\nwant-touch-controls 1\nm-dual 0')
    mountPhases(gameDir)

    from otp.local import NullHTTP
    NullHTTP.install()

    # The player is the only one on their own server; the name only tells
    # their account apart from any other on this device.
    os.environ.setdefault('TTR_PLAYCOOKIE', 'Player')
    os.environ.setdefault('TTR_GAMESERVER', '127.0.0.1')

    try:
        from toontown.toonbase import ToontownStart
    except SystemExit:
        # Say why, for the crash report.
        text = traceback.format_exc()
        print('OfflineStart: the game is closing:\n%s' % text)
        import builtins
        base = getattr(builtins, 'base', None)
        quitting = any(name in text for name in ('userExit', 'exitShow', 'enterShutdown'))
        if (sys.platform == 'android' and not quitting and base is not None and base.win is not None
                and not base.win.isClosed()):
            # Nothing on a phone should close the game but the player
            # leaving it.
            showError(text, dataDir)
        if 'userExit' not in text and quitting:
            # The player quit from the game's own menu: no report next time.
            CrashReport.forget()
        raise
    except BaseException:
        showError(traceback.format_exc(), dataDir)


def showError(text, dataDir):
    """Keeps the window open on what went wrong, rather than closing.

    On a phone there is nowhere else to see it.
    """
    print(text)
    try:
        os.makedirs(Filename(dataDir, 'logs').toOsSpecific(), exist_ok=True)
        with open(Filename(dataDir, 'logs/error.txt').toOsSpecific(), 'w') as file:
            file.write(text)
    except OSError:
        pass
    import builtins
    base = getattr(builtins, 'base', None)
    if base is None or base.win is None or base.win.isClosed():
        return
    from panda3d.core import Camera, CardMaker, NodePath, OrthographicLens, TextNode
    # A layer of its own over everything else in the window.
    root = NodePath('error')
    lens = OrthographicLens()
    lens.setFilmSize(2, 2)
    lens.setNearFar(-1000, 1000)
    camera = root.attachNewNode(Camera('errorCamera', lens))
    region = base.win.makeDisplayRegion()
    region.setSort(2000)
    region.setClearDepthActive(True)
    region.setCamera(camera)
    root.setDepthTest(False)
    root.setDepthWrite(False)
    card = CardMaker('errorCard')
    card.setFrame(-1, 1, -1, 1)
    card.setColor(0.05, 0.05, 0.12, 1)
    root.attachNewNode(card.generate())
    lines = text.strip().splitlines()[-30:]
    node = TextNode('errorText')
    node.setText('The game hit an error. Please send a screenshot of this screen.\n\n' + '\n'.join(lines))
    node.setTextColor(1, 1, 1, 1)
    scale = 0.045
    aspect = base.getAspectRatio()
    node.setWordwrap(1.9 / (scale / aspect))
    label = root.attachNewNode(node)
    label.setScale(scale / aspect, 1, scale)
    label.setPos(-0.96, 0, 0.92)
    # Small enough to fit the screen.
    bounds = label.getTightBounds()
    if bounds:
        height = bounds[1][2] - bounds[0][2]
        if height > 1.84:
            label.setScale(label.getScale() * (1.84 / height))
    while not base.win.isClosed():
        try:
            base.graphicsEngine.renderFrame()
        except Exception:
            break


main()
