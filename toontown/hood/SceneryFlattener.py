"""Merges the scenery that never moves into fewer pieces.

Each piece of a place's geometry is a separate draw for the graphics card,
which costs phones the most. The street files build every wall, cornice,
window and many props as pieces of their own, kept apart by the tags the
street builder puts on them, so flattenStrong can't join them. Here the tags
that nothing reads are taken off those parts and each flat building and
plain prop is flattened on its own. The nodes the game looks things up by
(each building's and prop's own node, doors' collisions, holiday props,
anything that moves or is clicked) stay as they were.
"""

import re

from panda3d.core import ConfigVariableBool

# Parts of a flat building whose tags nothing looks for.
PLAIN_PARTS = ('wall', 'cornice', 'windows', 'door', 'flat_door')
# Props with nothing inside them that the game looks for.
PLAIN_PROPS = re.compile(r'^prop_(tree|palm|crate|chimney|stovepipe|post|facade|cellar_door)|^streetlight')
# Of those, the ones that may be joined with their neighbours (the trees keep
# their own nodes: event lighting finds them by name).
JOINABLE_PROPS = re.compile(r'^prop_(palm|crate|chimney|stovepipe|post|facade|cellar_door)|^streetlight')
# Big props whose meshes are dozens of separate pieces but only a few nodes
# are looked up by name: (prop pattern, the group of plain meshes in it).
PLAIN_MESH_GROUPS = ((re.compile(r'^prop_party_gate'), 'mesh_grp'),)


def wanted():
    return ConfigVariableBool('flatten-scenery', True).getValue()


def flatten(geom):
    if not wanted() or geom is None or geom.isEmpty():
        return
    for building in geom.findAllMatches('**/=DNARoot=flat_building'):
        for part in building.findAllMatches('**/=DNARoot'):
            if part.getTag('DNARoot') in PLAIN_PARTS:
                part.clearTag('DNARoot')
                part.clearTag('DNACode')
        building.flattenStrong()
    for pattern, meshGroup in PLAIN_MESH_GROUPS:
        for prop in geom.findAllMatches('**/=DNARoot=prop'):
            if pattern.match(prop.getName()):
                for mesh in prop.findAllMatches('**/' + meshGroup):
                    # The party gate's fences, poles and stairs: about 40
                    # draws that become a handful (DistributedPartyGate looks
                    # up the clock, locators and signs, which are elsewhere).
                    mesh.flattenStrong()
    groups = {}
    for prop in geom.findAllMatches('**/=DNARoot=prop'):
        if not PLAIN_PROPS.match(prop.getName()) or not prop.find('**/=DNARoot').isEmpty():
            continue
        if JOINABLE_PROPS.match(prop.getName()):
            groups.setdefault(prop.getParent(), []).append(prop)
        else:
            prop.flattenStrong()
    # Props side by side in one part of the place become one piece per
    # texture (each part stays its own, so the street's visibility still
    # shows and hides them part by part).
    for parent, props in groups.items():
        joined = parent.attachNewNode('joinedProps')
        for prop in props:
            prop.wrtReparentTo(joined)
        joined.flattenStrong()
