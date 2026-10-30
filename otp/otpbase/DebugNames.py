"""PythonUtil's debug helpers, also in release builds.

PythonUtil only defines StackTrace, traceFunctionCall and lineInfo under
__debug__, and the Windows and Android builds run with -O, so importing
them from there fails at startup. The game still reaches code that calls
them (MailboxScreen.unload, for one), so in a release build these quiet
stand-ins take their place.
"""

if __debug__:
    from direct.showbase.PythonUtil import StackTrace, traceFunctionCall, lineInfo
else:
    class StackTrace:

        def __init__(self, label='', start=0, limit=None):
            self.label = label

        def compact(self):
            return ''

        def __str__(self):
            return ''

    def traceFunctionCall(frame):
        return ''

    def lineInfo(baseFileName=1):
        return ('', 0, '')
