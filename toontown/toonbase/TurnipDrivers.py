"""Custom graphics drivers for Android phones (Mesa's Turnip, for Adreno GPUs).

The player downloads a Turnip driver (the .zip that emulators use: a
libvulkan_freedreno.so, usually with a meta.json) and picks it here; the game
then draws through it from its next start.
"""

import json
import os
import shutil
import zipfile

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectLabel

from otp.otpbase.Settings import Settings

DRIVERS_DIR = 'drivers'
PICKED_DIR = os.path.join(DRIVERS_DIR, 'picked')
TEXT_DARK = (0.16, 0.16, 0.32, 1)


def currentDriver(settings=None):
    """The folder of the driver in use, or '' for the phone's own."""
    settings = settings or Settings()
    driver = settings.getString('graphics', 'driver', '')
    if driver and not os.path.isfile(os.path.join(driver, 'meta.json')):
        return ''
    return driver


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

    def __init__(self, launcher, panel):
        self.launcher = launcher
        self.panel = panel
        self.label = DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.32), text_font=launcher.interfaceFont,
                                 text_scale=0.056, text_fg=TEXT_DARK, text_wordwrap=30, text='')
        self.pickButton = launcher.redButton('PICK A DRIVER', (0, 0, 0.136), self.pick, textScale=0.04,
                                             imageScale=(1.9, 1, 1.25))
        self.pickButton.reparentTo(panel)
        self.resetButton = launcher.redButton("PHONE'S DRIVER", (0, 0, -0.042), self.reset, textScale=0.04,
                                              imageScale=(1.9, 1, 1.25))
        self.resetButton.reparentTo(panel)
        self.message = DirectLabel(parent=panel, relief=None, pos=(0, 0, -0.205), text_font=launcher.interfaceFont,
                                   text_scale=0.05, text_fg=TEXT_DARK, text_wordwrap=28,
                                   text='Pick a Turnip driver .zip (Snapdragon phones only). '
                                        'It is used from the next start.')
        self.update()

    def update(self):
        driver = currentDriver(self.launcher.settings)
        self.label['text'] = 'Driver in use:\n%s' % (driverName(driver) if driver else "The phone's own driver")
        self.resetButton['state'] = DGG.NORMAL if driver else DGG.DISABLED

    def say(self, text):
        self.message['text'] = text

    def pick(self):
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
