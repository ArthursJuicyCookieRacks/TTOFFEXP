# The PRC configuration for the packaged offline game (Windows and Android),
# loaded by toontown/toonbase/OfflineStart.py, which adds the paths to the
# game's files and mounts the phase multifiles. Keep it in step with dev.prc.

# Client settings
window-title Toontown - The Offline Experience
server-version TT-OFFEXP-dev
# A build sets the real version (config/version.prc, from tools/offline/version.py).
sync-video #f
want-dev #f
preload-avatars #t
# Panda looks through every installed Python package for model-loader
# add-ons on each model load when it finds none; the game uses none.
loader-support-entry-points #f
texture-anisotropic-degree 16
# Ask for a 24-bit depth buffer. With less (some phones hand out 16 bits),
# eyes, pupils and far-away building details cut through what is behind
# them and flicker.
depth-bits 24
# Offline there is no server to protect. The check could end the game on its
# own after a long stall or a clock jump (a phone waking from sleep).
want-speedhack-fix #f
load-display pandagl
default-directnotify-level warning


# New Addons!
want-WASD #t
tt-framerate #t
want-new-toonhall #t
want-max-font #t
want-ttc-television #f


# Resource settings
model-path /
default-model-extension .bam


# DC Files: set by OfflineStart.


# Server settings
want-rpc-server #f
rpc-server-endpoint http://localhost:8080/
want-cheesy-expirations #t


# Beta Modifications
# Temporary modifications for unimplemented features go here.
want-pets #t
want-news-tab #f
want-news-page #f
want-accessories #t
want-parties #t
want-gardening #t
want-gifting #f
want-skip-button #t
# This is a temporary 'fix' for DistributedSmoothNodes... probably not the permanent solution to our problem, but it works for now.
smooth-lag 0.4
want-keep-alive #f


# Game options
estate-day-night #t
want-instant-parties #t
show-total-population #f
want-toontorial #t


# Chat stuff
want-whitelist #f
want-blacklist-sequence #f
force-avatar-understandable #t
force-player-understandable #t


# Holidays and Events
want-arg-manager #f
want-mega-invasions #f
mega-invasion-cog-type tm


# Working (Custom) Addons!
want-toonfest #t
want-doomsday #f
# Check a quarter of the cached render/transform states per frame instead of
# all of them; the full sweep cost about a millisecond every frame.
garbage-collect-states-rate 0.25
# Panda's repositories default to gc DEBUG_SAVEALL, which puts every object
# the garbage collector finds into gc.garbage instead of freeing it: each
# street map, cog and toon the game let go of stayed in memory for good
# (about 5 MB more per area visited). Collected garbage is freed again.
gc-save-all #f
# Every animation blends between its frames (Avatars did already; props,
# characters and other Actors played frame by frame).
interpolate-frames 1
