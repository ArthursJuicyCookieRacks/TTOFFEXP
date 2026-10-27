"""Gives the Android app an adaptive icon.

build_apps only writes the old square ic_launcher pictures. Phones since
Android 8 draw such an icon shrunk onto a white shape. An adaptive icon (an
orange background layer and the dog in front, see art/app-icon/adaptive)
fills the phone's icon shape instead, with no white around it.

This adds both layers to the .aab's mipmaps, and a mipmap-anydpi-v26
ic_launcher.xml naming them, which phones on Android 8 and later use in place
of the square pictures.

    python add_adaptive_icon.py dist/TTR-Offline.aab
"""

import os
import sys
import zipfile

from direct.dist._android import ResourceTable
from direct.dist._proto.Resources_pb2 import FileReference, XmlNode

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art', 'app-icon', 'adaptive')
DENSITIES = (('mdpi', 160), ('hdpi', 240), ('xhdpi', 320), ('xxhdpi', 480), ('xxxhdpi', 640))
LAYERS = ('ic_launcher_bg', 'ic_launcher_fg')
ANY_DENSITY = 0xfffe
ANDROID_NS = 'http://schemas.android.com/apk/res/android'
ATTR_DRAWABLE = 0x01010199
ICON_XML = 'res/mipmap-anydpi-v26/ic_launcher.xml'


def iconXml(ids):
    node = XmlNode()
    root = node.element
    root.name = 'adaptive-icon'
    ns = root.namespace_declaration.add()
    ns.prefix = 'android'
    ns.uri = ANDROID_NS
    for tag, layer in (('background', 'ic_launcher_bg'), ('foreground', 'ic_launcher_fg')):
        child = root.child.add().element
        child.name = tag
        attr = child.attribute.add()
        attr.namespace_uri = ANDROID_NS
        attr.name = 'drawable'
        attr.value = '@mipmap/' + layer
        attr.resource_id = ATTR_DRAWABLE
        attr.compiled_item.ref.id = ids[layer]
        attr.compiled_item.ref.name = 'mipmap/' + layer
    return node.SerializeToString()


def addIcon(package, files):
    mipmap = [t for t in package.type if t.name == 'mipmap'][0]
    launcher = [e for e in mipmap.entry if e.name == 'ic_launcher'][0]
    ids = {}
    for layer in LAYERS:
        entry = mipmap.entry.add()
        entry.entry_id.id = max(e.entry_id.id for e in mipmap.entry) + 1
        entry.name = layer
        ids[layer] = (package.package_id.id << 24) | (mipmap.type_id.id << 16) | entry.entry_id.id
        for tag, density in DENSITIES:
            path = 'res/mipmap-%s-v4/%s.png' % (tag, layer)
            value = entry.config_value.add()
            value.config.density = density
            value.value.item.file.path = path
            value.value.item.file.type = FileReference.PNG
            with open(os.path.join(ART, '%s-%s.png' % (layer, tag)), 'rb') as file:
                files['base/' + path] = file.read()
    value = launcher.config_value.add()
    value.config.density = ANY_DENSITY
    value.config.sdk_version = 26
    value.value.item.file.path = ICON_XML
    value.value.item.file.type = FileReference.PROTO_XML
    files['base/' + ICON_XML] = iconXml(ids)


def main(bundlePath):
    tempPath = bundlePath + '.tmp'
    files = {}
    with zipfile.ZipFile(bundlePath) as source, zipfile.ZipFile(tempPath, 'w') as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == 'base/resources.pb':
                table = ResourceTable()
                table.ParseFromString(data)
                addIcon(table.package[0], files)
                data = table.SerializeToString()
            entry = zipfile.ZipInfo(info.filename, info.date_time)
            entry.external_attr = info.external_attr
            target.writestr(entry, data, compress_type=info.compress_type)
        for name, data in sorted(files.items()):
            target.writestr(zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0)), data, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tempPath, bundlePath)
    print('Added the adaptive icon to %s' % bundlePath)


if __name__ == '__main__':
    main(sys.argv[1])
