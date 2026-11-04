"""Packages the offline game with Panda3D's build_apps.

    python setup.py bdist_apps

builds Windows (a zip) and Android (an .aab) by default; the release builds
make each with its own run (TTR_PLATFORMS=win_amd64, then android). The
phase multifiles must be in the repository root first
(tools/offline/pack_resources.py makes them), and pip must be able to find
the Panda3D wheels for each platform, for example with PIP_FIND_LINKS
pointing at a folder of them. The GitHub
Actions workflow in .github/workflows/build.yml does all of this.
"""

import os
import re
import sys

from setuptools import setup

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'offline'))
import version as gameversion  # noqa: E402

# The game's full name: the Windows program and its window title.
GAME_TITLE = 'Toontown - The Offline Experience'
# The version comes from TT_VERSION, which the build workflow sets from the
# VERSION file and the earlier builds' tags (see tools/offline/version.py).
# VERSION is for the packaging tools, which want plain numbers (3.1);
# VERSION_LABEL is what players see (3.1, or 3.1-test for a pull request's
# build, or dev).
VERSION, VERSION_LABEL = gameversion.gameVersion()
# The game's version, as it shows in game and in the phone's app info.
GAME_VERSION = 'TT-OFFEXP-' + VERSION_LABEL

# The packaged game reads its version from this file (OfflineStart loads it
# after release.prc), so the version is set in one place only.
with open(os.path.join(ROOT, 'config', 'version.prc'), 'w', encoding='utf-8') as versionFile:
    versionFile.write('# Written by setup.py for each build; do not edit.\nserver-version %s\n' % GAME_VERSION)


def gameModules():
    # Every module of the game. The DC file imports the distributed classes
    # by name, so the freezer cannot find them by following imports.
    modules = []
    for package in ('otp', 'toontown'):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, package)):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            if '__init__.py' not in filenames:
                dirnames[:] = []
                continue
            prefix = os.path.relpath(dirpath, ROOT).replace(os.sep, '.')
            for filename in filenames:
                if filename.endswith('.py'):
                    name = filename[:-3]
                    modules.append(prefix if name == '__init__' else prefix + '.' + name)
    return sorted(modules)


def directModules():
    # Panda3D's direct imports some of its own modules by name too (the
    # particle and physics managers, for one), so take all of it but the
    # Tk and wx tools and the build scripts.
    import direct
    skip = ('tkpanels', 'tkwidgets', 'wxwidgets', 'directtools', 'leveleditor', 'cluster',
            'directdServer', 'directscripts', 'dist', 'doc', 'dcparse')
    root = os.path.dirname(direct.__file__)
    modules = ['direct']
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel != '.' and rel.split(os.sep)[0] in skip:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        prefix = 'direct' if rel == '.' else 'direct.' + rel.replace(os.sep, '.')
        for filename in filenames:
            if filename.endswith('.py') and filename != '__init__.py':
                modules.append(prefix + '.' + filename[:-3])
            elif filename == '__init__.py' and rel != '.':
                modules.append(prefix)
    return sorted(modules)


# TTR_PLATFORMS picks some, e.g. TTR_PLATFORMS=win_amd64.
PLATFORMS = os.environ.get('TTR_PLATFORMS', 'win_amd64,android').split(',')

# A desktop game writes its output to a log file. On Android it goes to the
# system log (logcat) instead: there is no home folder for the file, and the
# app cannot start if the file cannot be made. build_apps takes one setting
# for every platform, so build Android on its own (the workflow does).
LOG_OPTIONS = {} if 'android' in PLATFORMS else {
    'log_filename': '$USER_APPDATA/TTR-Offline/logs/game-%Y-%m-%d_%H-%M-%S.log',
    'log_filename_strftime': True,
}



# The name and icon the game shows on the phone's home screen.
# A TTDEV build (TTR_APP_NAME/TTR_APP_ID, set by the build workflow) is a
# separate app that installs beside the normal one.
APP_LABEL = os.environ.get('TTR_APP_NAME') or 'Toontown'
APP_ID = os.environ.get('TTR_APP_ID') or 'com.ttroffline.game'
ICON_DIR = os.path.join('tools', 'offline', 'art', 'app-icon')
ICONS = [os.path.join(ICON_DIR, 'icon-%d.png' % size) for size in (16, 32, 48, 72, 96, 128, 144, 192, 256)]


def keepActivityOnConfigChanges():
    """Has Android tell the game of every settings change, rather than
    closing and reopening it, which the game can't live through.

    build_apps leaves out some, such as a new screen density: phones that
    lower the resolution of games (Samsung's game optimizing does) change it
    as the game opens, and the game closed straight away.
    """
    from direct.dist import _android, commands
    _android.ANDROID_ATTRIBUTES['configChanges'] = _android.flag_resource(
        0x0101001f, mcc=0x0001, mnc=0x0002, locale=0x0004, touchscreen=0x0008, keyboard=0x0010,
        keyboardHidden=0x0020, navigation=0x0040, orientation=0x0080, screenLayout=0x0100, uiMode=0x0200,
        screenSize=0x0400, smallestScreenSize=0x0800, density=0x1000, layoutDirection=0x2000, colorMode=0x4000,
        grammaticalGender=0x8000, fontScale=0x40000000, fontWeightAdjustment=0x10000000)
    generate = commands.build_apps.generate_android_manifest

    def generateAndroidManifest(self, path):
        generate(self, path)
        with open(path, encoding='utf-8') as file:
            manifest = file.read()
        old = 'android:configChanges="'
        assert old in manifest
        manifest = manifest.replace(old, old + 'mcc|mnc|touchscreen|density|colorMode|')
        # The phone shows the game as plain "Toontown".
        assert 'android:label="' in manifest
        manifest = re.sub(r'android:label="[^"]*"', 'android:label="%s"' % APP_LABEL, manifest)
        old = 'android:versionName="%s"' % VERSION
        assert old in manifest
        manifest = manifest.replace(old, 'android:versionName="%s"' % GAME_VERSION)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(manifest)

    commands.build_apps.generate_android_manifest = generateAndroidManifest


if 'android' in PLATFORMS:
    keepActivityOnConfigChanges()

setup(
    # The packaging name stays TTR-Offline: build_apps names the player's
    # cache folders after it. The finished files are renamed by the workflow
    # (tt_offline-<version>_windows.zip, tt_offline-<version>_android.apk).
    name='TTR-Offline',
    version=VERSION,
    options={
        'build_apps': {
            'application_id': APP_ID,
            # On Windows this is the program's name. Android names its
            # library after it and shows APP_LABEL, so it keeps a plain name.
            'gui_apps': {
                ('TTR-Offline' if 'android' in PLATFORMS else GAME_TITLE): 'toontown/toonbase/OfflineStart.py',
            },
            'icons': {'*': ICONS},
            # The Panda3D wheels are our own builds, found through PIP_FIND_LINKS.
            'use_optimized_wheels': False,
            'requirements_path': os.path.join(ROOT, 'tools', 'offline', 'build-requirements.txt'),
            'include_modules': {'*': gameModules() + directModules() + ['semidbm']},
            'exclude_modules': {'*': [
                # Developer tools that need tkinter, and the online-only
                # database client.
                'toontown.coghq.InGameEditor',
                'pymongo',
            ]},
            'include_patterns': [
                'config/release.prc',
                'config/version.prc',
                'config/ttroff.dc',
                'assets/*',
                'phase_*.mf',
            ] + (['turnip/*'] if 'android' in PLATFORMS else []),
            'plugins': [
                'pandagl',
                'pandagles2',
                'p3openal_audio',
            ],
            'platforms': PLATFORMS,
            'android_abis': ['arm64-v8a', 'armeabi-v7a', 'x86_64'],
            'android_app_category': 'game',
            # Goes up with every build (3.1 is 3001), so a phone takes the
            # new APK as an update.
            'android_version_code': gameversion.androidVersionCode(VERSION),
            **LOG_OPTIONS,
        },
        'bdist_apps': {
            'installers': {
                'win_amd64': ['zip'],
                'android': ['aab'],
            },
        },
    },
)
