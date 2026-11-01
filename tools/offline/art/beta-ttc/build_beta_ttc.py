"""Builds the beta 1.0.5 Toontown Central for the game.

Usage:
    python build_beta_ttc.py <beta install folder> <repository folder>

<beta install folder> is Releases/ToontownBeta/1.0.5-install from
https://github.com/ToontownRewritten/ToontownReleaseArchive.

Everything goes under resources-overlay/phase_4/beta105/, so nothing
replaces a file the game already has:
  - every model the beta's playground DNA stores, converted from its old
    version 3.3 BAM (oldbam.py, convert_oldbam.py), at its old path:
    phase_4/beta105/phase_4/models/modules/gazebo.bam and so on;
  - the pictures those models use, copied as they are (.jpg, .rgb);
  - the DNA, in the game's XML: phase_4/beta105/dna/*.xml.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from panda3d.core import Filename, Texture, TexturePool, loadPrcFileData

loadPrcFileData('', 'bam-texture-mode unchanged\nnotify-level-gobj warning\naudio-library-name null')

import convert_oldbam
import dna2xml

PREFIX = 'phase_4/beta105'
DNA_FILES = ('storage', 'storage_TT', 'storage_TT_sz', 'toontown_central_sz')


def main(betaDir, repoDir):
    overlay = os.path.join(repoDir, 'resources-overlay')
    outRoot = os.path.join(overlay, PREFIX)
    report = []

    def betaPath(rel):
        return os.path.join(betaDir, rel)

    copied = set()

    def copyPicture(rel):
        if not rel:
            return None
        if rel not in copied:
            src = betaPath(rel)
            if not os.path.exists(src):
                return None
            dst = os.path.join(outRoot, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            copied.add(rel)
        return '%s/%s' % (PREFIX, rel)

    def loadTexture(name, alpha):
        game = copyPicture(name)
        if game is None:
            report.append('missing picture %s' % name)
            return None
        gameAlpha = copyPicture(alpha) if alpha else None
        src = Filename.fromOsSpecific(betaPath(name))
        if gameAlpha:
            tex = TexturePool.loadTexture(src, Filename.fromOsSpecific(betaPath(alpha)))
        else:
            tex = TexturePool.loadTexture(src)
        if tex is None:
            report.append('could not read picture %s' % name)
            return None
        # The BAM keeps only where the picture is, as the game sees it.
        tex = tex.makeCopy()
        tex.setFilename(Filename(game))
        tex.setFullpath(Filename(game))
        if gameAlpha:
            tex.setAlphaFilename(Filename(gameAlpha))
            tex.setAlphaFullpath(Filename(gameAlpha))
        return tex

    converted = {}

    def modelPath(path):
        # Storage textures are pictures, not models.
        if os.path.splitext(path)[1] in ('.jpg', '.rgb', '.png'):
            return copyPicture(path) or path
        if path in converted:
            return converted[path]
        src = betaPath(path + '.bam')
        if not os.path.exists(src):
            report.append('not in the beta, the game\'s own is used: %s' % path)
            converted[path] = path
            return path
        np, conv = convert_oldbam.convert(src, textureLoader=loadTexture, log=report.append)
        dst = os.path.join(outRoot, path + '.bam')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        np.writeBamFile(Filename.fromOsSpecific(dst))
        if conv.skipped:
            report.append('%s: left out %s' % (path, ', '.join(sorted(conv.skipped))))
        converted[path] = '%s/%s' % (PREFIX, path)
        return converted[path]

    os.makedirs(os.path.join(outRoot, 'dna'), exist_ok=True)
    for name in DNA_FILES:
        text = open(betaPath('phase_4/dna/%s.dna' % name), encoding='latin-1').read()
        items = dna2xml.parse(text)
        w = dna2xml.Writer(modelPath)
        if name.startswith('storage'):
            w.storage(items)
        else:
            w.scene(items, '2000')
        with open(os.path.join(outRoot, 'dna', name + '.xml'), 'w') as f:
            f.write(w.text())

    print('%d models converted, %d pictures copied' % (len(converted), len(copied)))
    for line in sorted(set(report)):
        print(' ', line)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
