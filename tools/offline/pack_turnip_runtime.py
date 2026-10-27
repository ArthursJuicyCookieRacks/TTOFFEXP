"""Lays out the libraries for custom graphics drivers on Android (see
toontown/toonbase/TurnipDrivers.py) as game files.

    python pack_turnip_runtime.py <built libraries> <game folder>

Each library goes into turnip/ as <name>.bin (so the packager leaves it alone
rather than taking it for a Python extension), and turnip/runtime.txt lists
them in the order the game loads them, with their sizes.
"""

import glob
import os
import shutil
import sys

# (kind, file pattern), in load order. The hooks are only copied out next to
# adrenotools, which loads them itself.
LIBRARIES = [
    ('hook', 'libmain_hook.so'),
    ('hook', 'libhook_impl.so'),
    ('hook', 'libfile_redirect_hook.so'),
    ('hook', 'libgsl_alloc_hook.so'),
    ('adrenotools', 'libadrenotools.so'),
    ('mesa', 'libdrm.so'),
    ('mesa', 'libgallium-*.so'),
    ('mesa', 'libEGL_mesa.so'),
    ('mesa', 'libGLESv2_mesa.so'),
]


def main(source, gameDir):
    target = os.path.join(gameDir, 'turnip')
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target)
    lines = []
    for kind, pattern in LIBRARIES:
        matches = glob.glob(os.path.join(source, pattern))
        if len(matches) != 1:
            sys.exit('Expected one %s in %s, found %d' % (pattern, source, len(matches)))
        name = os.path.basename(matches[0])
        shutil.copyfile(matches[0], os.path.join(target, name + '.bin'))
        lines.append('%s %s %d' % (kind, name, os.path.getsize(matches[0])))
    with open(os.path.join(target, 'runtime.txt'), 'w', newline='\n') as file:
        file.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(*sys.argv[1:])
