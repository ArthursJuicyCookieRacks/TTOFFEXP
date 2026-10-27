"""The launcher's DATA panel: exporting and importing the player's toons.

See ToonData for what a toon file holds.
"""

import os
import sys

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectLabel

from otp.otpbase.Settings import Settings
from toontown.toonbase import ToonData

TEXT_DARK = (0.16, 0.16, 0.32, 1)
INTRO = ('Export your toons to a file before you delete or update the game. '
         'After installing it again, import that file to get them back.')


class DataPanel:

    def __init__(self, launcher, panel):
        self.launcher = launcher
        self.panel = panel
        self.pending = None
        font = launcher.interfaceFont
        DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.33), text_font=font, text_scale=0.048,
                    text_fg=TEXT_DARK, text_wordwrap=30, text=INTRO)
        self.here = DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.19), text_font=font, text_scale=0.045,
                                text_fg=TEXT_DARK, text_wordwrap=32, text='')
        self.exportButton = self.button('EXPORT TOONS', -0.33, self.export)
        self.importButton = self.button('IMPORT TOONS', 0.33, self.pickImport)
        self.yesButton = self.button('YES, IMPORT', -0.33, self.confirmImport)
        self.noButton = self.button('CANCEL', 0.33, self.cancelImport)
        self.message = DirectLabel(parent=panel, relief=None, pos=(0, 0, -0.17), text_font=font,
                                   text_scale=0.045, text_fg=TEXT_DARK, text_wordwrap=30, text='')
        self.showChoice(False)
        self.update()

    def button(self, text, x, command):
        button = self.launcher.redButton(text, (x, 0, 0.05), command, textScale=0.04, imageScale=(1.42, 1, 1.25))
        button['text_pos'] = (0, -0.013)
        button.reparentTo(self.panel)
        return button

    def showChoice(self, choosing):
        for button in (self.exportButton, self.importButton):
            button.show() if not choosing else button.hide()
        for button in (self.yesButton, self.noButton):
            button.show() if choosing else button.hide()

    def update(self):
        names = ToonData.toonsHere()
        if names:
            self.here['text'] = 'Toons on this device (%d): %s' % (len(names), ToonData.describe(names))
        else:
            self.here['text'] = 'There are no toons on this device yet.'
        self.exportButton['state'] = DGG.NORMAL if names else DGG.DISABLED

    def say(self, text):
        print('ToonDataPanel: %s' % text)
        self.message['text'] = text

    def gone(self):
        return self.panel.isEmpty()

    # --- Export ---

    def export(self):
        name = ToonData.defaultFileName()
        if ToonData.isAndroid():
            self.exportAndroid(name)
            return
        if sys.platform == 'win32':
            try:
                path = ToonData.windowsDialog(True, name)
            except Exception as e:
                print('ToonDataPanel: no Save As box (%r)' % e)
                path = os.path.join(ToonData.documentsFolder(), name)
            if not path:
                self.say('Nothing was exported.')
                return
        else:
            path = os.path.join(ToonData.documentsFolder(), name)
        try:
            names = ToonData.export(path)
        except (ToonData.ToonDataError, OSError) as e:
            self.say('Could not export: %s' % e)
            return
        self.say('Exported %d toon%s to:\n%s' % (len(names), '' if len(names) == 1 else 's', path))

    def exportAndroid(self, name):
        # Made in the game's folder first, then copied to where the player
        # picks with Android's own "save" screen.
        temporary = os.path.join(ToonData.dataDir(), 'toon-export', name)
        try:
            self.exportNames = ToonData.export(temporary)
        except (ToonData.ToonDataError, OSError) as e:
            self.say('Could not export: %s' % e)
            return
        self.exportFile = temporary
        try:
            import android_support
            android_support.save_file(temporary, ToonData.MIME_TYPE, name)
        except (ImportError, AttributeError, NotImplementedError):
            self.exportToDownloads(temporary, name)
            return
        self.exportButton['state'] = DGG.DISABLED
        self.say('Pick where to save the toon file...')
        taskMgr.add(self.__waitForSave, 'toonDataSave')

    def exportToDownloads(self, temporary, name):
        # Older builds without the save screen: straight into Download.
        import shutil
        folder = '/storage/emulated/0/Download'
        try:
            shutil.copyfile(temporary, os.path.join(folder, name))
        except OSError as e:
            self.say('Could not export: %s' % e)
            return
        self.say('Exported %d toons to Download/%s' % (len(self.exportNames), name))

    def __waitForSave(self, task):
        import android_support
        if self.gone():
            return task.done
        saved = android_support.saved_file()
        if saved is None:
            return task.cont
        self.exportButton['state'] = DGG.NORMAL
        try:
            os.remove(self.exportFile)
        except OSError:
            pass
        if not saved:
            self.say('Nothing was exported.')
        else:
            count = len(self.exportNames)
            self.say('Exported %d toon%s as %s. Keep that file somewhere safe!'
                     % (count, '' if count == 1 else 's', saved))
        return task.done

    # --- Import ---

    def pickImport(self):
        if ToonData.isAndroid():
            try:
                import android_support
                android_support.pick_file('*/*', os.path.join(ToonData.dataDir(), 'toon-import'))
            except (ImportError, AttributeError, NotImplementedError):
                self.say('This build cannot open the file picker.')
                return
            self.importButton['state'] = DGG.DISABLED
            self.say('Pick your toon file...')
            taskMgr.add(self.__waitForPick, 'toonDataPick')
            return
        if sys.platform == 'win32':
            try:
                path = ToonData.windowsDialog(False)
            except Exception as e:
                print('ToonDataPanel: no Open box (%r)' % e)
                path = ToonData.newestToonFile()
        else:
            path = ToonData.newestToonFile()
        if not path:
            self.say('No toon file was picked.')
            return
        self.offer(path, temporary=False)

    def __waitForPick(self, task):
        import android_support
        if self.gone():
            return task.done
        picked = android_support.picked_file()
        if picked is None:
            return task.cont
        self.importButton['state'] = DGG.NORMAL
        if not picked:
            self.say('No toon file was picked.')
            return task.done
        self.offer(picked, temporary=True)
        return task.done

    def offer(self, path, temporary):
        try:
            names = ToonData.inspect(path)
        except ToonData.ToonDataError as e:
            self.say(str(e))
            self.forget(path, temporary)
            return
        self.pending = (path, temporary, names)
        replacing = ToonData.toonsHere()
        text = 'Import %d toon%s: %s?' % (len(names), '' if len(names) == 1 else 's', ToonData.describe(names))
        if replacing:
            text += '\nThe toons on this device are replaced (a backup copy is kept).'
        self.say(text)
        self.showChoice(True)

    def confirmImport(self):
        if self.pending is None:
            return
        path, temporary, names = self.pending
        self.pending = None
        self.showChoice(False)
        try:
            names = ToonData.load(path)
        except (ToonData.ToonDataError, OSError) as e:
            self.say('Could not import: %s' % e)
            return
        finally:
            self.forget(path, temporary)
        # The settings came with the toons.
        self.launcher.settings = Settings()
        self.update()
        self.say('Imported %d toon%s! Press PLAY! to play them.' % (len(names), '' if len(names) == 1 else 's'))

    def cancelImport(self):
        if self.pending is not None:
            path, temporary, names = self.pending
            self.forget(path, temporary)
        self.pending = None
        self.showChoice(False)
        self.say('Nothing was imported.')

    def forget(self, path, temporary):
        if temporary:
            try:
                os.remove(path)
            except OSError:
                pass
