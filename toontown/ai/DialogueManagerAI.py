from direct.directnotify import DirectNotifyGlobal
from direct.task import Task

from otp.nametag.NametagConstants import CFSpeech, CFTimeout
from toontown.toonbase import TTLocalizer


class DialogueManagerAI:
    # Has NPCs talk through the lines of a TTLocalizer.toontownDialogues
    # topic, one line every few seconds, then pause and start over, until
    # they leave the dialogue.
    notify = DirectNotifyGlobal.directNotify.newCategory('DialogueManagerAI')
    LineTime = 6

    def __init__(self, air):
        self.air = air
        self.dialogues = {}

    def requestDialogue(self, npc, topic, endPause=30):
        key = (npc.doId, topic)
        if key in self.dialogues:
            return
        lines = None
        for (partPos, partId), partLines in TTLocalizer.toontownDialogues.get(topic, {}).items():
            if partId == npc.npcId:
                lines = (partPos, partId, len(partLines))
        if lines is None:
            self.notify.warning('NPC %d has no lines in %s' % (npc.npcId, topic))
            return
        taskName = 'dialogue-%d-%s' % (npc.doId, topic)
        self.dialogues[key] = taskName
        partPos, partId, numLines = lines
        state = {'progress': 0}

        def speak(task):
            if npc.isDeleted():
                self.dialogues.pop(key, None)
                return Task.done
            progress = state['progress']
            npc.sendUpdate('setChat', [topic, partPos, partId, progress, CFSpeech | CFTimeout])
            state['progress'] = (progress + 1) % numLines
            task.delayTime = endPause if state['progress'] == 0 else self.LineTime
            return Task.again

        taskMgr.doMethodLater(self.LineTime * (partPos - 1), speak, taskName)

    def leaveDialogue(self, npc, topic):
        taskName = self.dialogues.pop((npc.doId, topic), None)
        if taskName:
            taskMgr.remove(taskName)
