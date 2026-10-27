"""Builds phase_3/models/gui/toontown-logo.bam with the Toontown Offline logo.

    python tools/offline/art/make_logo_model.py RESOURCES_DIR OUTPUT_DIR

The game loads the logo as a model and finds its 'logo' node (the loading
screens, the election event, the SOS card panel) and its 'eyes' node (the
first screen at start). This keeps the original model's 'eyes' and puts a
card with the new logo picture in place of 'logo', the same width as before.
The picture goes next to it as phase_3/maps/toontown-offline-logo.png.

It also writes phase_3.5/models/gui/playingCard.bam, whose 'logo' card sits
tilted on the blue SOS card back (the book's SOS tab, the SOS cards and the
Match Game cards). Only that card's picture changes; its place, tilt and
size stay, since the old card already has the new logo's shape.
"""

import os
import shutil
import sys

from panda3d.core import (CardMaker, Filename, Loader, LoaderOptions, NodePath, SamplerState,
                          TextureAttrib, TexturePool, TransparencyAttrib, loadPrcFileData)

HERE = os.path.dirname(os.path.abspath(__file__))
PICTURE = os.path.join(HERE, 'toontown-offline-logo.png')
TEXTURE = 'phase_3/maps/toontown-offline-logo.png'
MODEL = 'phase_3/models/gui/toontown-logo.bam'
CARD_MODEL = 'phase_3.5/models/gui/playingCard.bam'
# The old logo card is 10.24 wide; keep that and follow the picture's shape.
WIDTH = 10.24


def main(resourcesDir, outputDir):
    loadPrcFileData('', 'window-type none\naudio-library-name null\nbam-texture-mode unchanged\n'
                        'model-path %s\nmodel-path %s' % (Filename.fromOsSpecific(os.path.abspath(outputDir)),
                                                         Filename.fromOsSpecific(os.path.abspath(resourcesDir))))
    os.makedirs(os.path.join(outputDir, os.path.dirname(TEXTURE)), exist_ok=True)
    os.makedirs(os.path.join(outputDir, os.path.dirname(MODEL)), exist_ok=True)
    os.makedirs(os.path.join(outputDir, os.path.dirname(CARD_MODEL)), exist_ok=True)
    shutil.copyfile(PICTURE, os.path.join(outputDir, TEXTURE))

    old = Filename.fromOsSpecific(os.path.abspath(os.path.join(resourcesDir, MODEL)))
    root = NodePath(Loader.getGlobalPtr().loadSync(old, LoaderOptions(LoaderOptions.LF_no_cache)))
    oldLogo = root.find('**/logo')
    if oldLogo.isEmpty() or root.find('**/eyes').isEmpty():
        sys.exit('%s has no logo or eyes node' % old)

    texture = TexturePool.loadTexture(TEXTURE)
    texture.setFilename(TEXTURE)
    texture.setFullpath(TEXTURE)
    texture.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    texture.setMagfilter(SamplerState.FT_linear)
    height = WIDTH * texture.getOrigFileYSize() / texture.getOrigFileXSize()

    card = CardMaker('logo')
    card.setFrame(-WIDTH / 2, WIDTH / 2, -height / 2, height / 2)
    logo = NodePath(card.generate())
    logo.setTexture(texture)
    logo.setTransparency(TransparencyAttrib.MDual)
    logo.flattenStrong()
    # Same place in the sequence as the old one, so frame 0 is still the logo.
    logo.node().setName('logo')
    parent = oldLogo.getParent().node()
    children = [parent.getChild(i) for i in range(parent.getNumChildren())]
    children[children.index(oldLogo.node())] = logo.node()
    parent.removeAllChildren()
    for child in children:
        parent.addChild(child)

    path = Filename.fromOsSpecific(os.path.abspath(os.path.join(outputDir, MODEL)))
    if not root.writeBamFile(path):
        sys.exit('could not write %s' % path)

    old = Filename.fromOsSpecific(os.path.abspath(os.path.join(resourcesDir, CARD_MODEL)))
    cards = NodePath(Loader.getGlobalPtr().loadSync(old, LoaderOptions(LoaderOptions.LF_no_cache)))
    cardLogo = cards.find('**/logo')
    if cardLogo.isEmpty():
        sys.exit('%s has no logo node' % old)
    geomNode = cardLogo.node()
    for i in range(geomNode.getNumGeoms()):
        state = geomNode.getGeomState(i).setAttrib(TextureAttrib.make(texture))
        geomNode.setGeomState(i, state)
    path = Filename.fromOsSpecific(os.path.abspath(os.path.join(outputDir, CARD_MODEL)))
    if not cards.writeBamFile(path):
        sys.exit('could not write %s' % path)
    print('wrote %s, %s and %s' % (MODEL, CARD_MODEL, TEXTURE))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
