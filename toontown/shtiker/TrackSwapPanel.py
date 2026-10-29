"""Swapping a gag track, from the Shticker Book's gag page (offline).

A toon ends up with six of the seven gag tracks. Here it can give up one of
them (never Throw or Squirt) for the one it never chose. Every swap wipes
out all the experience and gags of both tracks: the track given up loses
everything it had, and a track taken back later starts from nothing again.
The button is there once the gag track ToonTasks are all done, and is
greyed out for a toon that was maxed with ~maxToon.
"""

from direct.directnotify import DirectNotifyGlobal
from direct.gui.DirectGui import *
from direct.showbase.DirectObject import DirectObject
from panda3d.core import *

from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownBattleGlobals
from toontown.toonbase import ToontownGlobals
from toontown.toontowngui import TTDialog

# Answers of the district (DistributedToonAI.requestTrackSwap).
OK, LOCKED, NOT_YET, BAD_TRACK = 0, 1, 2, 3
KEPT_TRACKS = (ToontownBattleGlobals.THROW_TRACK, ToontownBattleGlobals.SQUIRT_TRACK)


def trackName(track):
    return TTLocalizer.BattleGlobalTracks[track].capitalize()


def missingTrack(toon):
    """The one track the toon never chose, or None."""
    missing = [track for track in range(len(ToontownBattleGlobals.Tracks)) if not toon.hasTrackAccess(track)]
    return missing[0] if len(missing) == 1 else None


def swapState(toon):
    """'ready', 'notYet' (gag track tasks still to do) or 'locked' (the
    toon was maxed)."""
    if toon.getGagTracksLocked():
        return 'locked'
    # The gag track tasks are done once the toon has six tracks and no
    # track task on the go.
    if missingTrack(toon) is None or sum(1 for t in toon.getTrackAccess() if t) < 6 or toon.trackProgressId >= 0:
        return 'notYet'
    return 'ready'


class TrackSwapPanel(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('TrackSwapPanel')

    def __init__(self, parent, onDone=None):
        DirectObject.__init__(self)
        self.onDone = onDone
        self.dialog = None
        self.pending = None
        toon = base.localAvatar
        newTrack = missingTrack(toon)
        self.newTrack = newTrack
        self.frame = DirectFrame(parent=parent, relief=None, geom=DGG.getDefaultDialogGeom(), geom_scale=(1.5, 1, 1.25),
                                 geom_color=ToontownGlobals.GlobalDialogColor, pos=(0, 0, 0), sortOrder=DGG.FOREGROUND_SORT_INDEX)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.5), text=TTLocalizer.TrackSwapTitle, text_font=ToontownGlobals.getSignFont(),
                    text_scale=0.1, text_fg=(0.16, 0.32, 0.72, 1))
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.4), text=TTLocalizer.TrackSwapHelp, text_scale=0.045,
                    text_wordwrap=28, text_fg=(0.2, 0.2, 0.2, 1))
        if newTrack is not None:
            color = ToontownBattleGlobals.TrackColors[newTrack]
            DirectLabel(parent=self.frame, relief=DGG.FLAT, frameColor=color + (1,), frameSize=(-0.45, 0.45, -0.06, 0.08),
                        pos=(0, 0, 0.24), text=TTLocalizer.TrackSwapNew % trackName(newTrack), text_scale=0.06,
                        text_fg=(0, 0, 0, 1))
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, 0.12), text=TTLocalizer.TrackSwapGiveUp, text_scale=0.055,
                    text_fg=(0.2, 0.2, 0.2, 1))
        self.trackButtons = []
        choices = [track for track in range(len(ToontownBattleGlobals.Tracks))
                   if toon.hasTrackAccess(track) and track not in KEPT_TRACKS]
        for i, track in enumerate(choices):
            x = (i % 2 - 0.5) * 0.62
            z = 0.0 - (i // 2) * 0.14
            color = ToontownBattleGlobals.TrackColors[track]
            button = DirectButton(parent=self.frame, relief=DGG.RAISED, borderWidth=(0.01, 0.01), frameColor=color + (1,),
                                  frameSize=(-0.28, 0.28, -0.05, 0.07), pos=(x, 0, z), text=trackName(track), text_scale=0.055,
                                  text_fg=(0, 0, 0, 1), command=self.ask, extraArgs=[track])
            self.trackButtons.append(button)
        DirectLabel(parent=self.frame, relief=None, pos=(0, 0, -0.33), text=TTLocalizer.TrackSwapWarning, text_scale=0.04,
                    text_wordwrap=30, text_fg=(0.7, 0.1, 0.1, 1))
        buttons = loader.loadModel('phase_3/models/gui/dialog_box_buttons_gui')
        DirectButton(parent=self.frame, relief=None, image=(buttons.find('**/CloseBtn_UP'), buttons.find('**/CloseBtn_DN'), buttons.find('**/CloseBtn_Rllvr')),
                     pos=(0.62, 0, -0.52), scale=0.9, command=self.close)
        buttons.removeNode()
        self.accept('trackSwapResult', self.result)

    def ask(self, track):
        if self.newTrack is None or self.pending is not None:
            return
        self.closeDialog()
        text = TTLocalizer.TrackSwapConfirm % {'out': trackName(track), 'in': trackName(self.newTrack)}
        self.dialog = TTDialog.TTDialog(parent=aspect2dp, style=TTDialog.YesNo, text=text, text_wordwrap=18,
                                        command=self.answered, extraArgs=[track])
        self.dialog.show()

    def answered(self, answer, track):
        self.closeDialog()
        if answer != DGG.DIALOG_OK:
            return
        self.pending = track
        for button in self.trackButtons:
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
