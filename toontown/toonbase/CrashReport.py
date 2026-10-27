"""What the game logged before it last closed by itself, on Android.

A phone gives a player no way to see the game's log, so the game reads its
own: it notes its process at each start, and at the next start reads that
process's log (Android keeps an app's own log lines, which the app may
read). If it ended in an error or a crash, the log is saved to
logs/last-crash.txt and shown on the launcher.
"""

import os
import subprocess
import sys

MARKER = os.path.join('logs', 'running.txt')
REPORT = os.path.join('logs', 'last-crash.txt')
# How many lines of the log the launcher shows.
SHOWN_LINES = 34

report = None
# What a log that ended badly has in it.
SIGNS = ('Traceback', 'Fatal signal', ' F/', 'the game is closing', 'userExit', 'ANR in')


def begin():
    """Called first thing at startup, in the player's folder."""
    global report
    if sys.platform != 'android':
        return
    try:
        os.makedirs('logs', exist_ok=True)
        if os.path.isfile(MARKER):
            with open(MARKER) as file:
                pid = file.read().strip()
            report = readLog(pid)
            if not any(sign in report for sign in SIGNS):
                # The player closed it, or Android did to free memory.
                print('CrashReport: the last start closed without an error')
                report = None
            if report:
                print('CrashReport: the last start ended early; its log is in %s' % REPORT)
                with open(REPORT, 'w') as file:
                    file.write(report)
        mark()
    except Exception as e:
        print('CrashReport: %r' % e)


def readLog(pid):
    text = ''
    for command in (['logcat', '-d', '-v', 'time', '--pid', pid], ['logcat', '-d', '-v', 'time', '-b', 'crash']):
        try:
            text += subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10).stdout.decode(
                'utf-8', 'replace')
        except Exception as e:
            text += '%s: %r\n' % (' '.join(command), e)
    return text.strip()


def mark():
    """Notes this process, for the next start."""
    if sys.platform != 'android':
        return
    try:
        with open(MARKER, 'w') as file:
            file.write(str(os.getpid()))
    except OSError:
        pass


def forget():
    """The game closed as it should, so the next start has nothing to report."""
    try:
        os.remove(MARKER)
    except OSError:
        pass


def shownText():
    """The lines of the report worth a look: warnings, errors and Python's."""
    lines = report.splitlines()
    # The game's own lines say most; the crash dump that follows an exit
    # only says that it exited.
    picked = [line for line in lines if ('python' in line and line.split(':')[-1].strip()) or 'Panda3D' in line or 'threaded_app: APP_CMD' in line]
    picked = picked or [line for line in lines if ' E/' in line or ' F/' in line or ' W/' in line]
    return '\n'.join((picked or lines)[-SHOWN_LINES:])
