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

from panda3d.core import ExecutionEnvironment, Filename, VirtualFileSystem
from panda3d.core import loadPrcFile, loadPrcFileData

# The phase files, in the order the game needs them.
PHASES = ('3', '3.5', '4', '5', '5.5', '6', '7', '8', '9', '10', '11', '12', '13')


def getGameDir():
    if os.environ.get('TTR_GAME_DIR'):
        return Filename.fromOsSpecific(os.environ['TTR_GAME_DIR'])
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
            vfs.mount(multifile, Filename('/'), VirtualFileSystem.MFReadOnly)
        else:
            # A checkout keeps the phases as folders under resources/.
            folder = Filename(gameDir, 'resources/phase_%s' % phase)
            if vfs.isDirectory(folder):
                vfs.mount(folder, Filename('/phase_%s' % phase), VirtualFileSystem.MFReadOnly)
            else:
                print('OfflineStart: phase_%s is missing' % phase)


def main():
    gameDir = getGameDir()
    dataDir = getDataDir()
    os.chdir(dataDir.toOsSpecific())
    print('OfflineStart: game files in %s, player files in %s' % (gameDir, dataDir))

    loadPrcFile(Filename(gameDir, 'config/release.prc'))
    loadPrcFileData('OfflineStart', '\n'.join([
        'offline-release 1',
        'auto-start-server 1',
        'dc-file %s' % Filename(gameDir, 'config/ttroff.dc'),
        'local-db-directory %s' % Filename(dataDir, 'database'),
        'account-bridge-filename %s' % Filename(dataDir, 'database/account-bridge'),
        'local-event-log-directory %s' % Filename(dataDir, 'logs/events'),
    ]))
    if sys.platform == 'android':
        # Phones and tablets have OpenGL ES rather than desktop OpenGL, and
        # no keyboard, so the game gets on-screen controls.
        loadPrcFileData('OfflineStart Android', 'load-display pandagles2\naux-display pandagles\nwant-touch-controls 1')
    mountPhases(gameDir)

    # The player is the only one on their own server; the name only tells
    # their account apart from any other on this device.
    os.environ.setdefault('TTR_PLAYCOOKIE', 'Player')
    os.environ.setdefault('TTR_GAMESERVER', '127.0.0.1')

    from toontown.toonbase import ToontownStart


main()
