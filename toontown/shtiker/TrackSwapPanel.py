"""Swapping a gag track, from the Shticker Book's gag page (offline).

A toon ends up with six of the seven gag tracks. Here it can give up one of
them (never Throw or Squirt) for any track it does not have. Every swap wipes
out all the experience and gags of both tracks: the track given up loses
everything it had, and a track taken back later starts from nothing again.
The button works once the quest line has offered a track the toon did not take (and never while a track is being trained), and is
greyed out for a toon that was maxed with ~maxToon.
"""

from direct.directnotify import DirectNotifyGlobal
from direct.gui.DirectGui import *
from direct.showbase.DirectObject import DirectObject
from panda3d.core import *

from toontown.quest import Quests
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals
from toontown.toontowngui import TTDialog

# Answers of the district (DistributedToonAI.requestTrackSwap).
OK, LOCKED, NOT_YET, BAD_TRACK = 0, 1, 2, 3
# Where the panel sits: a little above the middle, level with the book's page.
PANEL_Z = 0.1
KEPT_TRACKS = (ToontownBattleGlobals.THROW_TRACK, ToontownBattleGlobals.SQUIRT_TRACK)


def trackName(track):
    return TTLocalizer.BattleGlobalTracks[track].capitalize()


def missingTracks(toon):
    """The tracks the toon can swap into: offered by the quest line (both
    sides of a finished track choice) but not held."""
    offered = Quests.tracksOfferedTo(toon)
    return [track for track in range(len(ToontownBattleGlobals.Tracks)) if track in offered and not toon.hasTrackAccess(track)]


def swapState(toon):
    """'ready', 'notYet' (nothing offered yet, or a track being trained)
    or 'locked' (the toon was maxed)."""
    if toon.getGagTracksLocked():
        return 'locked'
    # Not while a gag track is being trained; and only once the quest
    # line has offered a track the toon did not take.
    if toon.trackProgressId >= 0 or not missingTracks(toon):
        return 'notYet'
    return 'ready'


class TrackSwapPanel(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('TrackSwapPanel')

    def __init__(self, parent, onDone=None):
        DirectObject.__init__(self)
        self.onDone = onDone
        self.dialog = None
        self.pending = None
        self.outTrack = None
        self.newTrack = None
        toon = base.localAvatar
        self.frame = DirectFrame(parent=parent, relief=None, geom=DGG.getDefaultDialogGeom(), geom_scale=(1.5, 1, 1.25),
                                 geom_color=ToontownGlobals.GlobalDialogColor, pos=(0, 0, PANEL_Z), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.5), text=TTLocalizer.TrackSwapTitle, text_font=ToontownGlobals.getSignFont(),
                    text_scale=0.1, text_fg=(0.16, 0.32, 0.72, 1))
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.4), text=TTLocalizer.TrackSwapHelp, text_scale=0.045,
                    text_wordwrap=28, text_fg=(0.2, 0.2, 0.2, 1))
        # Two rows of buttons: the track to give up, and the track to get.
        # The picked one in each row stays sunken.
        self.trackButtons = []
        self.outButtons = {}
        self.inButtons = {}
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.3), text=TTLocalizer.TrackSwapGiveUp, text_scale=0.055,
                    text_fg=(0.2, 0.2, 0.2, 1))
        outChoices = [track for track in range(len(ToontownBattleGlobals.Tracks))
                      if toon.hasTrackAccess(track) and track not in KEPT_TRACKS]
        self.__row(outChoices, 0.2, self.pickOut, self.outButtons)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.02), text=TTLocalizer.TrackSwapGet, text_scale=0.055,
                    text_fg=(0.2, 0.2, 0.2, 1))
        inChoices = missingTracks(toon)
        self.__row(inChoices, -0.08, self.pickIn, self.inButtons)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, -0.36), text=TTLocalizer.TrackSwapWarning, text_scale=0.04,
                    text_wordwrap=30, text_fg=(0.7, 0.1, 0.1, 1))
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        self.swapButton = DirectButton(parent=self.frame, relief=None, image=(buttons.find('**/ChtBx_OKBtn_UP'), buttons.find('**/ChtBx_OKBtn_DN'), buttons.find('**/ChtBx_OKBtn_Rllvr'), buttons.find('**/ChtBx_OKBtn_UP')),
                                       image3_color=(0.6, 0.6, 0.6, 0.6), pos=(-0.2, 0, -0.5), scale=0.9, text=TTLocalizer.TrackSwapButton, text_scale=0.05,
                                       text_pos=(0, -0.1), text_fg=(0, 0, 0, 1), command=self.ask, state=DGG.DISABLED)
        DirectButton(parent=self.frame, relief=None, image=(buttons.find('**/CloseBtn_UP'), buttons.find('**/CloseBtn_DN'), buttons.find('**/CloseBtn_Rllvr')),
                     pos=(0.2, 0, -0.5), scale=0.9, text=TTLocalizer.lCancel, text_scale=0.05, text_pos=(0, -0.1), text_fg=(0, 0, 0, 1), command=self.close)
        buttons.removeNode()
        if len(inChoices) == 1:
            # Only one track to be had: picked already.
            self.pickIn(inChoices[0])
        self.accept('trackSwapResult', self.result)

    def __row(self, tracks, z, command, into):
        # Up to five tracks across; wide enough for the names.
        n = max(1, len(tracks))
        width = min(0.28, 1.3 / n)
        for i, track in enumerate(tracks):
            x = (i - (n - 1) / 2.0) * (width + 0.02)
            color = ToontownBattleGlobals.TrackColors[track]
            button = DirectButton(parent=self.frame, relief=DGG.RAISED, borderWidth=(0.01, 0.01), frameColor=color + (1,),
                                  frameSize=(-width / 2, width / 2, -0.05, 0.07), pos=(x, 0, z), text=trackName(track),
                                  text_scale=min(0.055, width * 0.19), text_fg=(0, 0, 0, 1), command=command, extraArgs=[track])
            self.trackButtons.append(button)
            into[track] = button

    def __mark(self, buttons, picked):
        for track, button in buttons.items():
            button['relief'] = DGG.SUNKEN if track == picked else DGG.RAISED
            button['frameColor'] = ToontownBattleGlobals.TrackColors[track] + (1 if track == picked else 0.6,)
        self.swapButton['state'] = DGG.NORMAL if (self.outTrack is not None and self.newTrack is not None and self.pending is None) else DGG.DISABLED

    def pickOut(self, track):
        if self.pending is not None:
            return
        self.outTrack = track
        self.__mark(self.outButtons, track)

    def pickIn(self, track):
        if self.pending is not None:
            return
        self.newTrack = track
        self.__mark(self.inButtons, track)

    def ask(self, track=None):
        track = self.outTrack
        if track is None or self.newTrack is None or self.pending is not None:
            return
        self.closeDialog()
        text = TTLocalizer.TrackSwapConfirm % {'out': trackName(track), 'in': trackName(self.newTrack)}
        self.dialog = TTDialog.TTDialog(parent=aspect2dp, style=TTDialog.YesNo, text=text, text_wordwrap=18,
                                        command=self.answered, extraArgs=[track])
        self.dialog.show()
        self.centerDialog()

    def answered(self, answer, track):
        self.closeDialog()
        if answer != DGG.DIALOG_OK:
            return
        self.pending = track
        for button in self.trackButtons + [self.swapButton]:
            button['state'] = DGG.DISABLED
        base.localAvatar.sendUpdate('requestTrackSwap', [track, self.newTrack])

    def result(self, result):
        self.pending = None
        if result == OK:
            text = TTLocalizer.TrackSwapDone % trackName(self.newTrack)
        elif result == LOCKED:
            text = TTLocalizer.TrackSwapLocked
        elif result == NOT_YET:
            text = TTLocalizer.TrackSwapNotYet
        else:
            text = TTLocalizer.TrackSwapFailed
        self.closeDialog()
        self.dialog = TTDialog.TTDialog(parent=aspect2dp, style=TTDialog.Acknowledge, text=text, text_wordwrap=18,
                                        command=self.acknowledged)
        self.dialog.show()

    def acknowledged(self, answer=None):
        self.closeDialog()
        self.close()

    def centerDialog(self):
        # Centered on the Swap Tracks panel (which sits a little above the
        # middle of the screen); the dialog's picture hangs about 0.07 below
        # its own origin.
        self.dialog.setPos(0, 0, PANEL_Z + 0.07)

    def closeDialog(self):
        if self.dialog is not None:
            self.dialog.cleanup()
            self.dialog = None

    def close(self):
        if self.frame is None:
            return
        self.ignoreAll()
        self.closeDialog()
        self.frame.destroy()
        self.frame = None
        if self.onDone is not None:
            self.onDone()
