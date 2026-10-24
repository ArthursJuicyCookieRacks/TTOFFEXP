"""Custom graphics drivers for Android phones (Mesa's Turnip, for Adreno GPUs).

The player downloads a Turnip driver (the .zip that emulators use) and picks
it here; the game then draws through it from its next start.
"""

from direct.gui.DirectGui import DirectLabel

from otp.otpbase.Settings import Settings


def currentDriver(settings=None):
    settings = settings or Settings()
    return settings.getString('graphics', 'driver', '')


class DriversPanel:

    def __init__(self, launcher, panel):
        self.launcher = launcher
        self.panel = panel
        driver = currentDriver(launcher.settings) or "The phone's own driver"
        self.label = DirectLabel(parent=panel, relief=None, pos=(0, 0, 0.2), text_font=launcher.interfaceFont,
                                 text_scale=0.05, text_fg=(0.16, 0.16, 0.32, 1), text_wordwrap=26,
                                 text='Driver in use:\n%s' % driver)
