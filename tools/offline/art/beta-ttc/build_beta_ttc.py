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
import re
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

# The beta's character pictures (the ones on the tunnel signs) are flat
# blue silhouettes. The game's own copies are the same shape and size,
# in full color, so those are used instead.
GAME_MODELS = {
    'phase_4/models/props/mickeySZ': 'phase_3.5/models/props/mickeySZ',
    'phase_4/models/props/minnieSZ': 'phase_4/models/props/minnieSZ',
    'phase_4/models/props/donaldSZ': 'phase_4/models/props/donaldSZ',
    'phase_4/models/props/daisySZ': 'phase_4/models/props/daisySZ',
    'phase_4/models/props/goofySZ': 'phase_4/models/props/goofySZ',
    'phase_4/models/props/plutoSZ': 'phase_4/models/props/plutoSZ',
}


LANDMARK = re.compile(r'(<landmark_building[^>]*code="([^"]+)"[^>]*>)(.*?)(\n(\t*)</landmark_building>)', re.S)


# Where the beta model's sign_origin sits away from the game model's
# (game minus beta, x and z): the sign is moved by that much so its text
# lands where the game puts it.
SIGN_SHIFT = {
    'toon_landmark_TT_bank': (-0.31, 1.62),
}


def shiftSign(text, dx, dz):
    def move(m):
        return '<pos x="%g" y="%s" z="%g" />' % (float(m.group(1)) + dx, m.group(2), float(m.group(3)) + dz)
    # The sign's own pos is the first one in the block.
    return re.sub(r'<pos x="([^"]+)" y="([^"]+)" z="([^"]+)" />', move, text, count=1)


def addGameSigns(sceneXml, gameXml):
    """The beta's DNA gives Toon Hall, the School House, the Bank and the
    Library no sign, so their sign boards are blank. Each one that has
    none gets the sign the game's own Toontown Central gives that
    building (same text, colors and font)."""
    signs = {}
    for m in LANDMARK.finditer(gameXml):
        sign = re.search(r'\n(\t*)<sign.*?</sign>', m.group(3), re.S)
        if sign:
            signs.setdefault(m.group(2), (sign.group(0), sign.group(1)))
    added = []

    def fix(m):
        if '<sign' in m.group(3) or m.group(2) not in signs:
            return m.group(0)
        text, indent = signs[m.group(2)]
        if m.group(2) in SIGN_SHIFT:
            text = shiftSign(text, *SIGN_SHIFT[m.group(2)])
        want = m.group(5) + '\t'
        text = '\n'.join(want + line[len(indent):] if line.startswith(indent) else line
                         for line in text.split('\n'))
        added.append(m.group(2))
        return m.group(1) + m.group(3) + text + m.group(4)

    return LANDMARK.sub(fix, sceneXml), added


# The beta's hydrant, mailboxes and trash cans are still models; the game's
# Toontown Central has dancing ones in their place (anim_prop, run by
# GenericAnimatedProp). Each beta one becomes the game's animated one.
ANIMATED = {
    'prop_hydrant': ('hydrant', 'tt_a_ara_ttc_hydrant_idle0'),
    'prop_mailbox_TT': ('mailbox', 'tt_a_ara_ttc_mailbox_idle0'),
    'prop_trashcan_metal': ('trashcan', 'tt_a_ara_ttc_trashcan_idleHiccup0'),
}
ANIM_CODE = 'animated_prop_generic_phase_5_models_char__ttc_%s'
PROP = re.compile(r'<prop name="[^"]*" code="([^"]+)">(.*?)</prop>', re.S)


def animateProps(sceneXml):
    count = [0]

    def swap(m):
        if m.group(1) not in ANIMATED:
            return m.group(0)
        kind, anim = ANIMATED[m.group(1)]
        code = ANIM_CODE % kind
        count[0] += 1
        return '<anim_prop name="%s_DNARoot" code="%s" anim="%s">%s</anim_prop>' % (code, code, anim, m.group(2))

    return PROP.sub(swap, sceneXml), count[0]


def animatedStorage():
    lines = []
    for kind, anim in ANIMATED.values():
        lines.append('\t<model path="phase_5/models/char/tt_r_ara_ttc_%s" scope="hood">' % kind)
        lines.append('\t\t<store_node root="anim_prop" code="%s" node="" />' % (ANIM_CODE % kind))
        lines.append('\t</model>')
    return '\n'.join(lines) + '\n'


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
        if path in GAME_MODELS:
            converted[path] = GAME_MODELS[path]
            return converted[path]
        src = betaPath(path + '.bam')
        if not os.path.exists(src):
            report.append('not in the beta, the game\'s own is used: %s' % path)
            converted[path] = path
            return path
        np, conv = convert_oldbam.convert(src, textureLoader=loadTexture, log=report.append)
        # The game puts a building's sign on its "sign_origin" node; the
        # beta's School House and Library call theirs "sign_origin_1".
        if np.find('**/sign_origin').isEmpty():
            for n in np.findAllMatches('**/sign_origin_*'):
                n.setName('sign_origin')
                report.append('%s: sign_origin_1 renamed sign_origin' % path)
                break
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
        text = w.text()
        if not name.startswith('storage'):
            game = os.path.join(repoDir, 'resources', 'phase_4', 'dna', name + '.xml')
            text, added = addGameSigns(text, open(game, encoding='utf-8').read())
            for code in added:
                report.append('sign from the game added to %s' % code)
            text, n = animateProps(text)
            report.append('%d props made the game\'s animated ones' % n)
        elif name == 'storage_TT':
            text = text.replace('</storage>', animatedStorage() + '</storage>')
        with open(os.path.join(outRoot, 'dna', name + '.xml'), 'w') as f:
            f.write(text)

    print('%d models converted, %d pictures copied' % (len(converted), len(copied)))
    for line in sorted(set(report)):
        print(' ', line)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
