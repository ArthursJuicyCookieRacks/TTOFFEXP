BOSSBOT FIELD OFFICE — BIG CHEESE TEXTURE PACK

WHAT THIS CHANGES

The classic Mover Shaker and Legal Eagle Field Office exteriors receive Big
Cheese posters, brown poster backgrounds, and brown brim/trim details. The
character and Bossbot medallion come from the original resource assets.

Native border correction: the duplicated inner brown frame has been removed.
The Bossbot artwork fills the same artwork rectangles as the original Lawbot
and Sellbot posters, using only each atlas's native outer margin. Big Cheese
keeps clear headroom inside the artwork. Both classic exterior variants and
their editable PNG masters include this correction. The standalone poster is
the border-free artwork master; the native atlases provide the actual frame.
See BORDER_CORRECTION.txt for the exact source-matched placement.

The optional modern-tower textures recolor the trim brown and replace the
elevator's department logo with the Bossbot logo. The modern tower has no native
character-poster surface, so it does not display the Big Cheese poster. Its
original gold facade geometry remains.

PACKAGE CONTENTS

phase_4/ and phase_5/ contain the complete classic exterior set: 11 native
texture files (3 changed atlases plus 8 unchanged companion files).

optional_modern/ contains 5 additional native textures (3 changed atlases and
2 unchanged shadow companions). Install that folder's phase_* contents only
if you also want the modern tower and annex-sign recolors. Its gold sales-bar
silhouettes and department/title text are controlled by geometry and game code,
and are not changed into Bossbot tie shapes or renamed by this texture pack.

editable_png/ contains lossless masters of the 6 changed atlases, at their
original pixel dimensions. These are editing sources, not direct replacements
for the JPG resource paths. artwork/ contains the full poster, transparent Cog
render, and original Bossbot medallion. previews/ shows the source models with
the finished textures. TEXTURE_MANIFEST.json lists file sizes and checksums.

The textures retain their original resource paths, dimensions, and atlas
positions. Native JPG color files and their SGI RGB alpha companions are kept
in the formats expected by the source models. This pack changes textures only;
it does not contain replacement BAM models.

INSTALLATION

1. Close the game and back up any existing files at the same resource paths.
2. Open your compatible resource pack's source folder or your extracted game
   resource tree. Locate the folder that contains phase_5 and the other phase
   folders.
3. Merge the main texture set's phase_* folder(s) into that location, preserving
   all subfolders and filenames. Replace matching files when prompted.
4. If you also want the modern tower recolor, merge the phase_* folder(s) from
   optional_modern/ in the same way.
5. If your game uses compiled .mf archives, rebuild or package the edited
   resources using that game's existing resource-pack workflow. Copying these
   loose files alone does not automatically modify an .mf archive.
6. Start the game and inspect the affected Field Office exteriors.

To remove the pack, restore the files you backed up.

SCOPE AND COMPATIBILITY

This is a cosmetic replacement of existing appearances. It does not add a new
Bossbot Field Office game type, change battles or Cog assignments, or alter
interior layouts. Shared resource paths affect all models that load those
textures. Keeping the original buildings and a separate Bossbot version side
by side requires additional texture remapping in the models or game code.

The classic brim includes a small color-compensation tile: it can look olive
or yellowish when viewed directly in the atlas. The source model multiplies
that tile by its fixed plum material color, producing brown on the building.

The supplied textures were checked on the actual source exterior models in
offscreen previews. They have not been tested in a complete running game.
Different model revisions or additional runtime color overrides may produce
different results.

SOURCE VERSION

Repository: https://github.com/RegDogg/TTR-Offline-resources
Commit: b912a6cdb3a1f400b37eba02ba5356de9ac2d4a5

See SOURCE_CREDITS.txt for the asset sources and adaptation details.

OPTIONAL PREVIEW REBUILD

tools/render_classic.py reproduces the two classic model previews using Python
and Panda3D with TinyDisplay. Supply the original resource repository as
--source-root, this package folder as --texture-root, and a separate --output
folder. The script does not modify the source BAMs or the textures.
