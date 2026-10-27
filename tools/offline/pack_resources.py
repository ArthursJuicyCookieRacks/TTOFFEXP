"""Packs the resource folders into the phase multifiles a packaged game loads.

    python tools/offline/pack_resources.py RESOURCES_DIR [OUTPUT_DIR]

RESOURCES_DIR holds phase_3, phase_3.5 and so on (a checkout of
TTR-Offline-resources); phase_X.mf files are written to OUTPUT_DIR, the
repository root by default. Each file is stored at /phase_X/..., the path the
game loads it by.
"""

import os
import sys

from panda3d.core import Filename, Multifile

# Files stored as they are: ones compressed already gain nothing from
# compressing again, and the image readers seek around in theirs, which a
# compressed subfile cannot do.
STORED = ('.ogg', '.mp3', '.wav', '.jpg', '.jpeg', '.png', '.rgb', '.rgba', '.sgi',
          '.bmp', '.tga', '.tif', '.tiff', '.ico', '.cur', '.ttf', '.mf')
COMPRESSION = 6


def pack(phaseDir, multifilePath):
    if os.path.exists(multifilePath):
        os.remove(multifilePath)
    mf = Multifile()
    if not mf.openWrite(Filename.fromOsSpecific(multifilePath)):
        raise IOError('could not write %s' % multifilePath)
    phase = os.path.basename(phaseDir)
    count = 0
    for dirpath, dirnames, filenames in os.walk(phaseDir):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.'))
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            name = phase + '/' + os.path.relpath(path, phaseDir).replace(os.sep, '/')
            level = 0 if filename.lower().endswith(STORED) else COMPRESSION
            source = Filename.binaryFilename(Filename.fromOsSpecific(path))
            mf.addSubfile(name, source, level)
            count += 1
    mf.repack()
    mf.close()
    return count


def main(resourcesDir, outputDir):
    phases = sorted(d for d in os.listdir(resourcesDir)
                    if d.startswith('phase_') and os.path.isdir(os.path.join(resourcesDir, d)))
    if not phases:
        sys.exit('no phase_ folders in %s' % resourcesDir)
    for phase in phases:
        path = os.path.join(outputDir, phase + '.mf')
        count = pack(os.path.join(resourcesDir, phase), path)
        print('%s: %d files, %.1f MB' % (path, count, os.path.getsize(path) / 1e6), flush=True)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else os.path.join(os.path.dirname(__file__), '..', '..'))
