"""Save Toybox Terrace's painted textures as pictures (Arthur 2026-11-06).

The map paints its marble, clock, tunnel, wood and soft-paint textures pixel
by pixel; on a phone that took seconds of the load. Run this after changing
any painting function in ToyboxTerrace.py, from the repository's root:

    python tools/offline/art/toybox-terrace/bake_textures.py

It writes resources-overlay/phase_4/maps/toybox_gen_*.png, which the map
loads instead of painting.
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, REPO)
os.chdir(REPO)
import glob
from panda3d.core import loadPrcFileData, Filename, VirtualFileSystem
loadPrcFileData('', 'window-type none\naudio-library-name null\nmodel-path /\n')
# The phases as the game mounts them (resources/, then the overlay on top).
vfs = VirtualFileSystem.getGlobalPtr()
for top in ('resources', 'resources-overlay'):
    for folder in sorted(glob.glob(os.path.join(REPO, top, 'phase_*'))):
        vfs.mount(Filename.fromOsSpecific(folder), Filename('/' + os.path.basename(folder)), VirtualFileSystem.MFReadOnly)
from direct.showbase.ShowBase import ShowBase
ShowBase()
from toontown.survival.previewmaps import ToyboxTerrace as T

m = object.__new__(T.ToyboxTerrace)
makers = [(key, (lambda col=col: m._ToyboxTerrace__marbleTex(col))) for key, col in T.MARBLE_SWIRLS.items()]
makers += [(T.CLOCK, m._ToyboxTerrace__clockTex), (T.DARK, m._ToyboxTerrace__darkTex),
           (T.WOOD, m._ToyboxTerrace__paintTex), (T.SOFT, m._ToyboxTerrace__softTex)]
for key, maker in makers:
    tex = maker()
    out = os.path.join(REPO, 'resources-overlay', T.ToyboxTerrace.bakedName(key))
    if not tex.write(Filename.fromOsSpecific(out)):
        raise SystemExit('could not write %s' % out)
    print('wrote', out, tex.getXSize(), tex.getYSize(), tex.getNumComponents())
