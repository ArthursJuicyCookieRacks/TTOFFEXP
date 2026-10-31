"""Custom graphics drivers for Android phones (Mesa's Turnip, for Adreno GPUs).

The player downloads a Turnip driver (the .zip that emulators use: a
libvulkan_freedreno.so, usually with a meta.json) and picks it here; the game
then draws through it from its next start.

How the game draws through it: the phone's own OpenGL ES is swapped for Mesa's
(built with zink, which turns OpenGL ES into Vulkan), and zink is handed the
Turnip driver, opened with adrenotools.  These come with the Android game in
turnip/, listed in turnip/runtime.txt, and are copied out to the player's
folder, since Android only loads libraries from a real file.

If the game doesn't get as far as its launcher with the driver, the next start
goes back to the phone's own driver.
"""

import json
import os
import platform
import shutil
import sys
import zipfile

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectLabel

from otp.otpbase.Settings import Settings

DRIVERS_DIR = 'drivers'
PICKED_DIR = os.path.join(DRIVERS_DIR, 'picked')
RUNTIME_DIR = os.path.join(DRIVERS_DIR, 'runtime')
CUSTOM_LIBRARY = 'libvulkan_custom.so'
# adrenotools_open_libvulkan's feature flag for loading a custom driver.
ADRENOTOOLS_DRIVER_CUSTOM = 1 << 0
TEXT_DARK = (0.16, 0.16, 0.32, 1)


def isAndroid():
    return sys.platform == 'android'


def currentDriver(settings=None):
    """The folder of the driver in use, or '' for the phone's own."""
    settings = settings or Settings()
    driver = settings.getString('graphics', 'driver', '')
    if driver and not os.path.isfile(os.path.join(driver, 'meta.json')):
        return ''
    return driver


def useDriver(settings):
    """Starts drawing through the player's driver, if they picked one.

    Must run before the game's window opens.  Returns True if it did.
    """
    if sys.platform != 'android' or platform.machine() != 'aarch64':
        # Turnip is for 64-bit Snapdragon phones.
        return False
    try:
        return startDriver(settings)
    except Exception as e:
        # Whatever goes wrong, the game still starts on the phone's driver.
        print('TurnipDrivers: %r' % e)
        return False


def startDriver(settings):
    driver = currentDriver(settings)
    if settings.getString('graphics', 'driver-trying', ''):
        # The last start with it never reached the launcher.
        print('TurnipDrivers: the last start with %s failed; back to the phone\'s driver' % driver)
        settings.updateSetting('graphics', 'driver', '')
        settings.updateSetting('graphics', 'driver-trying', '')
        return False
    if not driver:
        return False
    try:
        runtime = unpackRuntime()
        if runtime is None:
            print('TurnipDrivers: this build has no custom driver support')
            return False
        settings.updateSetting('graphics', 'driver-trying', driver)
        loadDriver(runtime, driver)
    except Exception as e:
        print('TurnipDrivers: could not load %s: %s' % (driver, e))
        settings.updateSetting('graphics', 'driver-trying', '')
        return False
    print('TurnipDrivers: drawing with %s' % driverName(driver))
    return True


def driverWorks(settings):
    """The game drew its launcher with the driver: keep it."""
    if settings.getString('graphics', 'driver-trying', ''):
        settings.updateSetting('graphics', 'driver-trying', '')


def unpackRuntime():
    """Copies the bundled libraries out to the player's folder.

    Returns the folder, and the libraries in the order they load, as
    (kind, path) pairs.
    """
    from panda3d.core import ConfigVariableString, Filename, VirtualFileSystem
    vfs = VirtualFileSystem.getGlobalPtr()
    gameDir = Filename(ConfigVariableString('offline-game-dir', '').getValue())
    listing = vfs.readFile(Filename(gameDir, 'turnip/runtime.txt'), True)
    if not listing:
        return None
    folder = os.path.abspath(RUNTIME_DIR)
    os.makedirs(folder, exist_ok=True)
    libraries = []
    for line in listing.decode('utf-8').splitlines():
        if not line.strip():
            continue
        kind, name, size = line.split()
        path = os.path.join(folder, name)
        libraries.append((kind, path))
        if os.path.isfile(path) and os.path.getsize(path) == int(size):
            continue
        data = vfs.readFile(Filename(gameDir, 'turnip/%s.bin' % name), True)
        with open(path + '.part', 'wb') as file:
            file.write(data)
        os.replace(path + '.part', path)
    return folder, libraries


def importCtypes():
    """ctypes, which on Android looks up the name of Python's own library in
    build settings that the packaged game leaves out."""
    import sysconfig
    name = sysconfig._get_sysconfigdata_name()
    if sys.platform == 'android' and name not in sys.modules:
        try:
            __import__(name)
        except ImportError:
            import types
            settings = types.ModuleType(name)
            settings.build_time_vars = {'LDLIBRARY': 'libpython%d.%d.so' % sys.version_info[:2]}
            sys.modules[name] = settings
    import ctypes
    return ctypes


def loadDriver(runtime, driver):
    ctypes = importCtypes()
    folder, libraries = runtime
    adrenotools = [path for kind, path in libraries if kind == 'adrenotools'][0]
    tools = ctypes.CDLL(adrenotools)
    openVulkan = tools.adrenotools_open_libvulkan
    openVulkan.restype = ctypes.c_void_p
    openVulkan.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                           ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
    # RTLD_NOW; the hooks were copied into the same folder as adrenotools.
    handle = openVulkan(2, ADRENOTOOLS_DRIVER_CUSTOM, (folder + '/').encode(), (folder + '/').encode(),
                        (driver + '/').encode(), CUSTOM_LIBRARY.encode(), None, None)
    if not handle:
        raise RuntimeError('adrenotools could not open the driver')
    # zink takes over the driver's handle; Mesa's OpenGL ES is put in front of
    # the phone's, for the game's window to find.
    os.environ['ZINK_VULKAN_HANDLE'] = hex(handle)
    os.environ['MESA_LOADER_DRIVER_OVERRIDE'] = 'zink'
    os.environ['EGL_PLATFORM'] = 'surfaceless'
    for kind, path in libraries:
        if kind == 'mesa':
            ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)


def driverName(folder):
    try:
        with open(os.path.join(folder, 'meta.json')) as file:
            meta = json.load(file)
    except (OSError, ValueError):
        return os.path.basename(folder)
    name = meta.get('name') or os.path.basename(folder)
    version = meta.get('driverVersion')
    return '%s (%s)' % (name, version) if version else name


def installDriver(zipPath):
    """Unpacks a driver .zip into the drivers folder and returns its folder.

    Raises ValueError if the .zip holds no Vulkan driver.
    """
    try:
        archive = zipfile.ZipFile(zipPath)
    except (OSError, zipfile.BadZipFile):
        raise ValueError('That file is not a .zip.')
    with archive:
        names = archive.namelist()
        libraries = [name for name in names if name.endswith('.so') and 'vulkan' in os.path.basename(name)]
        if not libraries:
            raise ValueError('That .zip has no Vulkan driver in it.')
        meta = {}
        metaNames = [name for name in names if os.path.basename(name) == 'meta.json']
        if metaNames:
            try:
                meta = json.loads(archive.read(metaNames[0]).decode('utf-8'))
            except ValueError:
                meta = {}
        library = meta.get('libraryName')
        library = [name for name in libraries if os.path.basename(name) == library] or libraries
        library = library[0]
        base = os.path.splitext(os.path.basename(zipPath))[0]
        folder = os.path.abspath(os.path.join(DRIVERS_DIR, ''.join(c if c.isalnum() or c in '-_.' else '_' for c in base)))
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
        with open(os.path.join(folder, 'libvulkan_custom.so'), 'wb') as file:
            file.write(archive.read(library))
        meta.setdefault('name', base)
        meta['libraryName'] = 'libvulkan_custom.so'
        with open(os.path.join(folder, 'meta.json'), 'w') as file:
            json.dump(meta, file)
    return folder


class DriversPanel:
    """The launcher's MOBILE panel: the graphics driver and the dual screen."""

    def __init__(self, launcher, panel):
        self.launcher = launcher
        self.panel = panel
        self.label = DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.36), text_font=launcher.interfaceFont,
                                 text_scale=0.05, text_fg=TEXT_DARK, text_wordwrap=30, text='')
        self.pickButton = launcher.redButton('PICK A DRIVER', (-0.34, 0, 0.215), self.pick, textScale=0.038,
                                             imageScale=(1.6, 1, 1.25))
        self.pickButton.reparentTo(panel)
        self.resetButton = launcher.redButton("PHONE'S DRIVER", (0.34, 0, 0.215), self.reset, textScale=0.038,
                                              imageScale=(1.6, 1, 1.25))
        self.resetButton.reparentTo(panel)
        # Small text sits in the middle of these thinner buttons.
        for button in (self.pickButton, self.resetButton):
            button['text_pos'] = (0, -0.013)
        self.message = DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.1), text_font=launcher.interfaceFont,
                                   text_scale=0.045, text_fg=TEXT_DARK, text_wordwrap=32,
                                   text='Pick a Turnip driver .zip (Snapdragon phones only). '
                                        'It is used from the next start.')
        if not isAndroid():
            # Custom graphics drivers are a thing of Android phones.
            self.message['text'] = 'Graphics drivers can only be changed on Android.'
            self.pickButton['state'] = DGG.DISABLED
        self.screenButton = launcher.redButton('', (0, 0, -0.12), self.toggleScreen, textScale=0.05,
                                               imageScale=(2.9, 1, 1.25))
        self.screenButton.reparentTo(panel)
        DirectLabel(parent=panel, relief=None, pos=(0, 0, -0.245), text_font=launcher.interfaceFont,
                    text_scale=0.045, text_fg=TEXT_DARK, text_wordwrap=32,
                    text='The bottom screen of dual-screen handhelds such as the AYN Thor: '
                         'laff meter, gags, tasks, maps and more.')
        self.update()

    def update(self):
        from toontown.toonbase import OfflineLauncher
        driver = currentDriver(self.launcher.settings)
        self.label['text'] = 'Driver in use: %s' % (driverName(driver) if driver else "the phone's own driver")
        self.resetButton['state'] = DGG.NORMAL if driver and isAndroid() else DGG.DISABLED
        on = OfflineLauncher.secondScreenWanted(self.launcher.settings)
        self.screenButton['text'] = 'DUAL SCREEN: %s' % ('ON' if on else 'OFF')

    def toggleScreen(self):
        from toontown.toonbase import OfflineLauncher
        settings = self.launcher.settings
        settings.updateSetting('mobile', 'dual-screen', not OfflineLauncher.secondScreenWanted(settings))
        OfflineLauncher.applySecondScreenSetting(settings)
        self.update()

    def say(self, text):
        self.message['text'] = text

    def pick(self):
        print('TurnipDrivers: opening the file picker')
        try:
            import android_support
            android_support.pick_file('*/*', os.path.abspath(PICKED_DIR))
        except (ImportError, AttributeError, NotImplementedError):
            self.say('This build cannot open the file picker.')
            return
        self.pickButton['state'] = DGG.DISABLED
        self.say('Waiting for the file picker...')
        taskMgr.add(self.__waitForPick, 'turnipDriverPick')

    def __waitForPick(self, task):
        import android_support
        if self.panel.isEmpty():
            return task.done
        picked = android_support.picked_file()
        if picked is None:
            return task.cont
        self.pickButton['state'] = DGG.NORMAL
        if not picked:
            self.say('No driver was picked.')
            return task.done
        try:
            folder = installDriver(picked)
        except ValueError as e:
            self.say(str(e))
            return task.done
        finally:
            try:
                os.remove(picked)
            except OSError:
                pass
        self.launcher.settings.updateSetting('graphics', 'driver', folder)
        self.update()
        self.say("Done! Restart the game to use the new driver. If it won't start, the phone's own "
                 'driver comes back.')
        return task.done

    def reset(self):
        self.launcher.settings.updateSetting('graphics', 'driver', '')
        self.update()
        self.say("The phone's own driver is used from the next start.")
