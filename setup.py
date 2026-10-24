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

from setuptools import setup

ROOT = os.path.dirname(os.path.abspath(__file__))
VERSION = '2.12.2'


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

setup(
    name='TTR-Offline',
    version=VERSION,
    options={
        'build_apps': {
            'application_id': 'com.ttroffline.game',
            'gui_apps': {
                'TTR-Offline': 'toontown/toonbase/OfflineStart.py',
            },
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
                'config/ttroff.dc',
                'phase_*.mf',
            ],
            'plugins': [
                'pandagl',
                'pandagles2',
                'p3openal_audio',
            ],
            'platforms': PLATFORMS,
            'android_abis': ['arm64-v8a', 'armeabi-v7a', 'x86_64'],
            'android_app_category': 'game',
            'android_version_code': 1,
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
