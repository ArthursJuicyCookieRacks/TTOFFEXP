STOMP-O-MATIC 6000 — CASHBOT RETEXTURE

Based on the supplied stomp_o_matic_src.zip model and the supplied reference video.

OPEN THE MODEL

stomp_o_matic.glb is the simplest version to open. All of its textures are embedded.

stomp_o_matic.obj is the editable interchange version. Keep material.mtl and the
textures directory beside it. All texture paths are relative. The model uses Y up,
the same scale as the supplied OBJ, and the same overall bounds.

WHAT CHANGED

The model now has UV mapping on every surface. The invalid texture-coordinate
references in the original label faces have been corrected. The label material no
longer multiplies its artwork by the original 0.4 darkening factor.

The new surface atlas follows the reference video's charcoal cabinet, muted
blue-grey drum, cool grey metal, and pale cream tips. The four nameplates use a
recreated yellow-green sign with an ivory border, condensed lettering, and the
large central O. The dark vent artwork comes from the original resource repository.

The underside uses the original circular Cashbot logo from
RegDogg/TTR-Offline-resources. The logo's color pixels have not been repainted.
Its original alpha mask has been combined with the color image for GLB/PNG use.
A darker material tint makes the original silver logo read as dark pewter, as in
the video. A thin, flat logo decal covers the supplied model's generic crossed-bar
emblem. The original geometry is retained beneath it.

Overlapping side-panel surfaces are hidden with an opacity material to prevent
duplicated outlines. Their vertices and triangles remain in the model.

RECONSTRUCTION LIMITS

This is a retexture of the supplied model. That model differs geometrically from
the video: its feet are short cylinders, its handle is not a complete arch, and
the upper assembly and overlapping side-panel shapes differ. The revised textures
do not turn those shapes into the original reference mesh. The recreated sign
and material artwork are an interpretation of a compressed video, not recovered
original textures. The Cashbot logo and repository vent atlas are original assets.

TEXTURES

textures/surface_atlas.png       1024 x 1024; charcoal, pewter, teal, and ivory.
textures/label.png               1024 x 512; recreated transparent nameplate.
textures/access_panel.png        512 x 1024; rounded grey panel with transparency.
textures/cashbot_logo.png        128 x 128; original color + original alpha.
textures/original_vent_atlas.jpg 256 x 256; original Toontown recess/vent atlas.

The *_alpha.png files provide matching grayscale opacity for OBJ importers.

The full-resolution generated label, panel, and surface artwork are retained in
source_assets/artwork. Original repository files are retained in
source_assets/repository. The supplied model, original texture, and original build
script are retained in source_assets/original_model.

PROVENANCE AND REBUILDING

SOURCES.json identifies the source assets, repository commit, and checksums.
validation.json records export and geometry checks.

The tools folder contains the new UV/material build script and actual-model
renderer/exporter. REBUILD.txt gives the reproducible build command. Use that
workflow to reproduce the retextured model. The original build.py is preserved
only as source history; it still creates the original model and label.

The previews are renders of the delivered mesh and materials, not generated
product mockups. Lighting will vary between viewers. No game integration or
in-game test is included in this model package.
