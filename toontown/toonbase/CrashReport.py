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
    try:
        text += subprocess.run(['logcat', '-d', '-v', 'time', '--pid', pid], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=10).stdout.decode('utf-8', 'replace')
    except Exception as e:
        text += 'logcat: %r\n' % e
    # The crash buffer keeps crash dumps from earlier runs too (the dump is
    # written by Android's crash_dump, under its own process id), so only
    # the dump of this process is kept. Before, a days-old crash could be
    # shown for a later run that ended some other way.
    try:
        crash = subprocess.run(['logcat', '-d', '-v', 'time', '-b', 'crash'], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=10).stdout.decode('utf-8', 'replace')
        text += '\n' + crashDumpOf(crash, pid)
    except Exception as e:
        text += 'logcat -b crash: %r\n' % e
    return text.strip()


def crashDumpOf(crash, pid):
    """The lines of the crash buffer that belong to the dump of pid."""
    kept = []
    keeping = False
    for line in crash.splitlines():
        if 'pid: ' in line and ', tid: ' in line:
            # Each dump starts with "pid: N, tid: M, name: ...".
            keeping = ('pid: %s,' % pid) in line
        elif '*** *** ***' in line:
            keeping = False
        if keeping:
            kept.append(line)
    return '\n'.join(kept)


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
    """The lines of the report worth a look: how it crashed (signal, abort
    message, the first frames of the native backtrace) and the game's last
    log lines before that."""
    lines = report.splitlines()
    crashAt = next((i for i, line in enumerate(lines) if 'Fatal signal' in line or 'Traceback' in line), len(lines))
    game = [line for line in lines[:crashAt]
            if ('python' in line and line.split(':')[-1].strip()) or 'Panda3D' in line or 'threaded_app: APP_CMD' in line]
    game = game or [line for line in lines[:crashAt] if ' E/' in line or ' W/' in line]
    how = []
    for line in lines[crashAt:]:
        body = line.split('): ', 1)[-1].strip()
        if (any(key in line for key in ('Fatal signal', 'Abort message', 'signal ', 'Cause:', 'Assertion', 'assert', 'Traceback', 'Error'))
                or (body[:1] == '#' and body[1:3].isdigit() and int(body[1:3]) < 10)
                or (body[:2] == 'Fi' and 'line' in body)):
            how.append(line)
    if not how:
        how = [line for line in lines[crashAt:] if ' F/' in line or ' E/' in line]
    picked = game[-(SHOWN_LINES - min(len(how), SHOWN_LINES // 2)):] + how[:SHOWN_LINES // 2]
    if not picked:
        picked = lines[-SHOWN_LINES:]
    return '\n'.join(picked[-SHOWN_LINES:])


def saveReport():
    """Lets the player keep the whole report (Android's save screen, or
    Download on builds without it). Returns a line to show them."""
    import shutil
    name = 'toontown-crash-log.txt'
    try:
        import android_support
        android_support.save_file(os.path.abspath(REPORT), 'text/plain', name)
        return 'Pick where to save the log, then send that file.'
    except (ImportError, AttributeError, NotImplementedError):
        pass
    except Exception as e:
        print('CrashReport: save screen failed: %r' % e)
    try:
        shutil.copyfile(REPORT, os.path.join('/storage/emulated/0/Download', name))
        return 'Saved as Download/%s. Please send that file.' % name
    except OSError as e:
        return 'Could not save the log: %s' % e
