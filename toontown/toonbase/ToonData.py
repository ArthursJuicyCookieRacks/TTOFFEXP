"""Saving the player's toons to one file, and loading them back.

Deleting the app (on Android, to install a new version) deletes the toons
with it, so the launcher's DATA button can save them to a file the player
keeps, and load that file into the fresh install.

A toon file is a zip of the local database (the toons, their account, their
estates and pets) and the game's settings, with a small description of what
is in it. Loading one replaces the toons on this device; the ones that were
there are saved first, in the data folder's toon-backups folder.

The game's own server must not be running while toons are loaded, so this is
only offered on the launcher, before PLAY!.
"""

import json
import os
import re
import shutil
import sys
import time
import zipfile

from panda3d.core import ConfigVariableString, Filename

FORMAT = 1
MANIFEST = 'ttoffexp-toons.json'
MIME_TYPE = 'application/zip'
# Folders next to the database files that are not toons (the event logs and
# cog building records in a test setup); they are left as they are.
SKIP_DIRS = ('events', 'backups')
SETTINGS = 'settings.json'
VALUE_RE = re.compile(r'^\s*\("((?:[^"\\]|\\.)*)"\)\s*$')
NAME_RE = re.compile(r'^\s*setName: \("((?:[^"\\]|\\.)*)"\)\s*$', re.M)


class ToonDataError(Exception):
    """Something the player should be told, in their words."""


def databaseDir():
    path = ConfigVariableString('local-db-directory', 'astron/databases/astrondb').getValue()
    return Filename(path).toOsSpecific()


def dataDir():
    """Where the game keeps the player's files (the working directory)."""
    return os.getcwd()


def defaultFileName():
    return time.strftime('TTOFFEXP-toons-%Y-%m-%d.zip')


def toonNamesIn(texts):
    """The toons' names, from the database files' texts."""
    names = []
    for text in texts:
        name = _jsonToonName(text)
        if name is None:
            if 'class: DistributedToon' not in text:
                continue
            match = NAME_RE.search(text)
            if not match:
                continue
            name = match.group(1)
        names.append(name.replace('\\"', '"').replace('\\\\', '\\'))
    return sorted(names, key=str.lower)


def _jsonToonName(text):
    # The packaged games have no PyYAML, so their database files are JSON
    # ("class": "DistributedToon"), which the YAML pattern never matched:
    # the phone said it had no toons. Returns None for anything else.
    if not text.lstrip().startswith('{'):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get('class') != 'DistributedToon':
        return None
    value = (data.get('fields') or {}).get('setName')
    match = VALUE_RE.match(value) if isinstance(value, str) else None
    return match.group(1) if match else None


def databaseFiles():
    """(path in the zip, path on disk) for each database file."""
    root = databaseDir()
    files = []
    if not os.path.isdir(root):
        return files
    for folder, dirs, names in os.walk(root):
        if folder == root:
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in names:
            path = os.path.join(folder, name)
            relative = os.path.relpath(path, root).replace(os.sep, '/')
            files.append(('database/' + relative, path))
    return sorted(files)


def toonsHere():
    """The names of the toons on this device."""
    texts = []
    for inZip, path in databaseFiles():
        if inZip.endswith('.yaml'):
            try:
                with open(path, encoding='utf-8', errors='replace') as file:
                    texts.append(file.read())
            except OSError:
                pass
    return toonNamesIn(texts)


def export(path):
    """Saves the toons (and settings) into a toon file; returns their names."""
    files = databaseFiles()
    names = toonsHere()
    if not names:
        raise ToonDataError('There are no toons on this device to export yet.')
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    temporary = path + '.part'
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, json.dumps({
            'format': FORMAT, 'game': 'Toontown - The Offline Experience',
            'exported': time.strftime('%Y-%m-%d %H:%M:%S'), 'toons': names}, indent=2))
        for inZip, onDisk in files:
            archive.write(onDisk, inZip)
        settings = os.path.join(dataDir(), SETTINGS)
        if os.path.isfile(settings):
            archive.write(settings, SETTINGS)
    os.replace(temporary, path)
    print('ToonData: exported %d toons to %s' % (len(names), path))
    return names


def _safeMembers(archive):
    members = []
    for info in archive.infolist():
        name = info.filename.replace('\\', '/')
        if name.startswith('/') or '..' in name.split('/') or ':' in name:
            raise ToonDataError('That file is not a toon file from this game.')
        members.append((name, info))
    return members


def inspect(path):
    """The names of the toons in a toon file; complains if it isn't one."""
    try:
        with zipfile.ZipFile(path) as archive:
            members = _safeMembers(archive)
            names = [name for name, info in members]
            if 'database/info.yaml' not in names:
                raise ToonDataError('That file is not a toon file from this game.')
            texts = [archive.read(info).decode('utf-8', 'replace') for name, info in members
                     if name.startswith('database/') and name.endswith('.yaml')]
    except (zipfile.BadZipFile, OSError, KeyError):
        raise ToonDataError('That file is not a toon file from this game.')
    toons = toonNamesIn(texts)
    if not toons:
        raise ToonDataError('That toon file has no toons in it.')
    return toons


def backupFolder():
    return os.path.join(dataDir(), 'toon-backups')


def load(path):
    """Replaces the toons on this device with the ones in a toon file.

    The toons that were here are saved in toon-backups first. Returns the
    names of the loaded toons.
    """
    toons = inspect(path)
    if toonsHere():
        backup = os.path.join(backupFolder(), time.strftime('before-import-%Y-%m-%d-%H%M%S.zip'))
        export(backup)
    root = databaseDir()
    os.makedirs(root, exist_ok=True)
    # Clear the old database, keeping the folders that are not toons.
    for name in os.listdir(root):
        if name in SKIP_DIRS:
            continue
        path_ = os.path.join(root, name)
        if os.path.isdir(path_):
            shutil.rmtree(path_)
        else:
            os.remove(path_)
    with zipfile.ZipFile(path) as archive:
        for name, info in _safeMembers(archive):
            if info.is_dir():
                continue
            if name.startswith('database/'):
                target = os.path.join(root, *name[len('database/'):].split('/'))
            elif name == SETTINGS:
                target = os.path.join(dataDir(), SETTINGS)
            else:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as source, open(target, 'wb') as dest:
                shutil.copyfileobj(source, dest)
    print('ToonData: imported %d toons from %s' % (len(toons), path))
    return toons


def describe(names, limit=6):
    if len(names) <= limit:
        return ', '.join(names)
    return '%s and %d more' % (', '.join(names[:limit]), len(names) - limit)


# --- Choosing where the file goes, per platform ---

def isAndroid():
    return sys.platform == 'android'


def documentsFolder():
    home = os.path.expanduser('~')
    for name in ('Documents', 'Downloads'):
        folder = os.path.join(home, name)
        if os.path.isdir(folder):
            return folder
    return home


def windowsDialog(save, initialName=''):
    """The Windows "Save As" / "Open" box; returns the path, or None."""
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [('lStructSize', wintypes.DWORD), ('hwndOwner', wintypes.HWND),
                    ('hInstance', wintypes.HINSTANCE), ('lpstrFilter', wintypes.LPCWSTR),
                    ('lpstrCustomFilter', wintypes.LPWSTR), ('nMaxCustFilter', wintypes.DWORD),
                    ('nFilterIndex', wintypes.DWORD), ('lpstrFile', wintypes.LPWSTR),
                    ('nMaxFile', wintypes.DWORD), ('lpstrFileTitle', wintypes.LPWSTR),
                    ('nMaxFileTitle', wintypes.DWORD), ('lpstrInitialDir', wintypes.LPCWSTR),
                    ('lpstrTitle', wintypes.LPCWSTR), ('Flags', wintypes.DWORD),
                    ('nFileOffset', wintypes.WORD), ('nFileExtension', wintypes.WORD),
                    ('lpstrDefExt', wintypes.LPCWSTR), ('lCustData', wintypes.LPARAM),
                    ('lpfnHook', ctypes.c_void_p), ('lpTemplateName', wintypes.LPCWSTR),
                    ('pvReserved', ctypes.c_void_p), ('dwReserved', wintypes.DWORD),
                    ('FlagsEx', wintypes.DWORD)]

    buffer = ctypes.create_unicode_buffer(initialName, 1024)
    dialog = OPENFILENAMEW()
    dialog.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    dialog.hwndOwner = ctypes.windll.user32.GetActiveWindow()
    dialog.lpstrFilter = 'Toon files (*.zip)\0*.zip\0All files\0*.*\0\0'
    dialog.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    dialog.nMaxFile = 1024
    dialog.lpstrInitialDir = documentsFolder()
    dialog.lpstrDefExt = 'zip'
    OFN_OVERWRITEPROMPT, OFN_PATHMUSTEXIST, OFN_FILEMUSTEXIST, OFN_NOCHANGEDIR = 0x2, 0x800, 0x1000, 0x8
    if save:
        dialog.lpstrTitle = 'Export toons'
        dialog.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR
        ok = ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(dialog))
    else:
        dialog.lpstrTitle = 'Import toons'
        dialog.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_NOCHANGEDIR
        ok = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(dialog))
    return buffer.value if ok and buffer.value else None


def newestToonFile():
    """Off Windows and Android: the newest toon file in Documents/Downloads/home."""
    found = []
    home = os.path.expanduser('~')
    for folder in (os.path.join(home, 'Documents'), os.path.join(home, 'Downloads'), home):
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.startswith('TTOFFEXP-toons') and name.endswith('.zip'):
                    path = os.path.join(folder, name)
                    found.append((os.path.getmtime(path), path))
    return max(found)[1] if found else None
