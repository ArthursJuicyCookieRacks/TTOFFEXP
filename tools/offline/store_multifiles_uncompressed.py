"""Keeps the phase multifiles uncompressed in the Android App Bundle.

build_apps compresses every asset in the .aab. The game reads its phase
multifiles straight out of the APK, jumping around in them, which only works
well when they are stored uncompressed: a compressed asset has to be inflated
again from the start for every jump back. The images inside the multifiles
are compressed already, so the APK hardly grows.

This rewrites the bundle with the .mf files stored, and tells bundletool to
keep them that way in the APKs it makes from the bundle.

    python store_multifiles_uncompressed.py dist/TTR-Offline.aab
"""

import os
import sys
import zipfile

from direct.dist._android import BundleConfig

UNCOMPRESSED_GLOB = 'assets/**.mf'


def main(bundlePath):
    tempPath = bundlePath + '.tmp'
    with zipfile.ZipFile(bundlePath) as source, zipfile.ZipFile(tempPath, 'w') as target:
        for info in source.infolist():
            data = source.read(info)
            compression = zipfile.ZIP_DEFLATED
            if info.filename == 'BundleConfig.pb':
                config = BundleConfig()
                config.ParseFromString(data)
                if UNCOMPRESSED_GLOB not in config.compression.uncompressed_glob:
                    config.compression.uncompressed_glob.append(UNCOMPRESSED_GLOB)
                data = config.SerializeToString()
            elif info.filename.endswith('.mf') or info.compress_type == zipfile.ZIP_STORED:
                # The multifiles, and whatever build_apps stored already (the
                # page-aligned native libraries; bundletool aligns them again).
                compression = zipfile.ZIP_STORED
            entry = zipfile.ZipInfo(info.filename, info.date_time)
            entry.external_attr = info.external_attr
            target.writestr(entry, data, compress_type=compression)
    os.replace(tempPath, bundlePath)
    print('Stored the multifiles uncompressed in %s' % bundlePath)


if __name__ == '__main__':
    main(sys.argv[1])
