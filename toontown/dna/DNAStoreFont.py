from .DNAStorageElement import DNAStorageElement
from .DNAParser import *

class DNAStoreFont(DNAStorageElement):
    TAG = 'store_font'
    PARENTS = ['storage']

    def __init__(self, root, code, path):
        DNAStorageElement.__init__(self)

        self.root = root
        self.code = code
        self.path = path

    def _store(self, storage):
        path = self.path
        if '/' not in path:
            # A font named by its TTLocalizer setting, such as SignFont in
            # the tutorial's storage, so it follows the language.
            from toontown.toonbase import TTLocalizer
            path = getattr(TTLocalizer, path, path)
        font = loader.loadFont(path)
        storage.storeFont(font, self.code, self.getScope())

registerElement(DNAStoreFont)
