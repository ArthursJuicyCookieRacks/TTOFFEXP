"""Survival night maps built in code.

Each is a MAPS entry in SurvivalArena (pick one with `survival-map <key>`);
only those in MAP_ORDER show in Map Select.
"""

PREVIEW_MAPS = {
    'farewell_fair': ('toontown.survival.previewmaps.FarewellFair', 'FarewellFair'),
    'toybox_terrace': ('toontown.survival.previewmaps.ToyboxTerrace', 'ToyboxTerrace'),
}


def getPreviewMap(key):
    entry = PREVIEW_MAPS.get(key)
    if entry is None:
        return None
    import importlib
    return getattr(importlib.import_module(entry[0]), entry[1])
