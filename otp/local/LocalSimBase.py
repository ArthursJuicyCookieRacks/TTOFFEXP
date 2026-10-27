import os
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.showbase import DConfig
from direct.showbase.BulletinBoard import BulletinBoard
from direct.showbase.JobManager import JobManager
from panda3d.core import NodePath

from otp.otpbase import BackupManager


class LocalSimBase:
    """
    Stands in for AIBase (the `simbase` builtin) when the UberDOG or an AI
    runs inside the game process. It carries the same settings AIBase reads
    from the config, but none of its process-wide side effects: the client
    owns the clock, the window and the main loop.
    """
    notify = directNotify.newCategory('LocalSimBase')

    def __init__(self, context, loader):
        self.config = DConfig
        self.context = context
        self.air = None

        self.messenger = context.messenger
        self.taskMgr = context.taskMgr
        self.ivalMgr = context.ivalMgr
        self.bboard = BulletinBoard()
        self.jobMgr = JobManager()
        self.loader = loader
        self.hidden = NodePath('hidden')
        self.sfxManagerList = None
        self.musicManager = None

        config = self.config
        self.wantTk = 0
        self.AISleep = 0
        self.AIRunningNetYield = 0
        self.AIForceSleep = 0
        self.wantStats = 0
        self.wantPets = config.ConfigVariableBool('want-pets', 1).getValue()
        if self.wantPets:
            from toontown.pets import PetConstants
            self.petMoodTimescale = config.GetFloat('pet-mood-timescale', 1.0)
            self.petMoodDriftPeriod = config.GetFloat('pet-mood-drift-period', PetConstants.MoodDriftPeriod)
            self.petThinkPeriod = config.GetFloat('pet-think-period', PetConstants.ThinkPeriod)
            self.petMovePeriod = config.GetFloat('pet-move-period', PetConstants.MovePeriod)
            self.petPosBroadcastPeriod = config.GetFloat('pet-pos-broadcast-period', PetConstants.PosBroadcastPeriod)
        self.wantBingo = config.ConfigVariableBool('want-fish-bingo', 1).getValue()
        self.wantKarts = config.ConfigVariableBool('wantKarts', 1).getValue()
        self.newDBRequestGen = config.ConfigVariableBool('new-database-request-generate', 1).getValue()
        self.waitShardDelete = config.ConfigVariableBool('wait-shard-delete', 1).getValue()
        self.blinkTrolley = config.ConfigVariableBool('blink-trolley', 0).getValue()
        self.fakeDistrictPopulations = config.ConfigVariableBool('fake-district-populations', 0).getValue()
        self.wantSwitchboard = config.ConfigVariableBool('want-switchboard', 0).getValue()
        self.wantSwitchboardHacks = config.ConfigVariableBool('want-switchboard-hacks', 0).getValue()
        self.GEMdemoWhisperRecipientDoid = config.ConfigVariableBool('gem-demo-whisper-recipient-doid', 0).getValue()
        self.sqlAvailable = config.ConfigVariableBool('sql-available', 1).getValue()
        self.backups = BackupManager.BackupManager(
            # Saved district state (cog buildings, redeemed codes, ...) is
            # kept with the toons' database, so one folder is the whole save.
            filepath=config.ConfigVariableString('backups-filepath', os.path.join(
                config.ConfigVariableString('local-db-directory', 'astron/databases/astrondb').getValue(),
                'backups')).getValue(),
            extension=config.ConfigVariableString('backups-extension', '.json').getValue())

    def getRepository(self):
        return self.air

    def run(self):
        # The client's main loop drives everything.
        pass
