"""
Builds the Stomp-O-Matic 6000 for the Cashbot field office from the OBJ
Arthur supplied (stomp_o_matic.obj, material.mtl, textures/):

    python tools/offline/art/stomp-o-matic/build_stomp_o_matic.py

Writes resources-overlay/phase_5/models/cogdominium/ttoff_m_ara_ccg_stompOMatic.bam
and its textures as resources-overlay/phase_5/maps/ttoff_t_ara_ccg_stomp*.png.
The model is turned Z-up, scaled to about 10 feet tall (two and a half toons),
and keeps one node per part so the game can animate the spikes and drum:
housing, posts, trim, panels, vents, drum, spikes, labels and logo.
"""

import os
import sys

from panda3d.core import (Filename, GeomNode, LColor, MaterialAttrib, NodePath, PNMImage,
                          Texture, TextureAttrib, TransparencyAttrib, loadPrcFileData)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
OVERLAY = os.path.join(ROOT, 'resources-overlay')
MODEL = 'phase_5/models/cogdominium/ttoff_m_ara_ccg_stompOMatic.bam'
MAPS = 'phase_5/maps'
# The OBJ is 1.72 units tall; this makes it about 10.3 feet.
SCALE = 6.0
# Textures are kept small for phones.
MAX_SIZE = 512
# The parts by OBJ group: the game finds them by these names.
PARTS = {'dark': 'housing', 'post': 'posts', 'steel': 'trim', 'brass': 'brass',
         'panel': 'panels', 'vent': 'vents', 'cyan': 'drum', 'cream': 'spikes',
         'label': 'labels', 'cashbot_decal': 'logo'}

loadPrcFileData('', 'window-type none\naudio-library-name null\n')


def textureFile(tex):
    name = os.path.splitext(os.path.basename(tex.getFullpath().toOsSpecific()))[0]
    return '%s/ttoff_t_ara_ccg_stomp_%s.png' % (MAPS, name)


def main():
    from direct.showbase.ShowBase import ShowBase
    ShowBase()
    model = loader.loadModel(Filename.fromOsSpecific(os.path.join(HERE, 'stomp_o_matic.obj')), noCache=True)
    root = NodePath('stompOMatic')
    body = root.attachNewNode('body')
    for np in model.findAllMatches('**/+GeomNode'):
        part = PARTS.get(np.getName(), np.getName())
        node = np.node()
        # The panel group holds the overlap mask: faces the source hides
        # with zero opacity. Drop them rather than drawing them clear.
        for i in reversed(range(node.getNumGeoms())):
            state = node.getGeomState(i)
            mat = state.getAttrib(MaterialAttrib)
            if mat and mat.getMaterial() and mat.getMaterial().getDiffuse()[3] <= 0.01:
                node.removeGeom(i)
        if not node.getNumGeoms():
            continue
        np.setName(part)
        np.wrtReparentTo(body)
    body.setP(90)
    body.setScale(SCALE)
    body.flattenLight()
    # Toontown draws without lights: the material colors would be ignored,
    # and the atlases already carry the colors.
    body.clearMaterial()
    for np in body.findAllMatches('**/+GeomNode'):
        node = np.node()
        for i in range(node.getNumGeoms()):
            node.setGeomState(i, node.getGeomState(i).removeAttrib(MaterialAttrib))
    os.makedirs(os.path.join(OVERLAY, MAPS), exist_ok=True)
    written = {}
    for tex in body.findAllTextures():
        out = textureFile(tex)
        if out not in written:
            image = PNMImage()
            tex.store(image)
            if image.getXSize() > MAX_SIZE or image.getYSize() > MAX_SIZE:
                scale = MAX_SIZE / float(max(image.getXSize(), image.getYSize()))
                small = PNMImage(int(image.getXSize() * scale), int(image.getYSize() * scale),
                                 image.getNumChannels())
                small.gaussianFilterFrom(1.0, image)
                image = small
            image.write(Filename.fromOsSpecific(os.path.join(OVERLAY, out)))
            written[out] = image.hasAlpha()
        tex.setFilename(out)
        tex.setFullpath(out)
        tex.clearAlphaFilename()
        tex.setMinfilter(Texture.FTLinearMipmapLinear)
        tex.setMagfilter(Texture.FTLinear)
    # Cut-outs (labels, the access panels, the logo): binary alpha, which
    # phones draw too.
    for np in body.findAllMatches('**/+GeomNode'):
        tex = np.findTexture('*')
        if tex and written.get(textureFile(tex)):
            np.setTransparency(TransparencyAttrib.MBinary)
    loadPrcFileData('', 'bam-texture-mode unchanged\n')
    out = os.path.join(OVERLAY, MODEL)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    root.writeBamFile(Filename.fromOsSpecific(out))
    root.ls()
    print('wrote', out, 'bounds', root.getTightBounds())
    for name, alpha in sorted(written.items()):
        print('wrote', name, 'alpha' if alpha else '')


if __name__ == '__main__':
    main()
