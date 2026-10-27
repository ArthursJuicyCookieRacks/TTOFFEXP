"""An HTTPClient that never reaches the internet.

Panda3D only has HTTPClient when it is built with OpenSSL, which the Android
build is not. The offline game never needs the web, but the launcher and a
few features still make an HTTPClient (to check for an updated chat whitelist,
say), so on such a build this one takes its place: every request fails at
once, the way it would with no connection, and the game carries on with its
own files.
"""

from panda3d.core import DocumentSpec


class NullHTTPChannel:

    def isValid(self):
        return False

    def isConnectionReady(self):
        return False

    def getStatusCode(self):
        return 0

    def getStatusString(self):
        return 'no internet in the offline game'

    def getFileSize(self):
        return 0

    def getDocumentSpec(self):
        return DocumentSpec()

    def getUrl(self):
        return DocumentSpec().getUrl()

    def run(self):
        return False

    def __getattr__(self, name):
        # Requests (getDocument, beginGetHeader, downloadToRam, ...) fail, and
        # settings (setPersistentConnection, ...) are ignored.
        return lambda *args, **kwargs: False


class NullHTTPClient:
    VSNoVerify = 0
    VSNoDateCheck = 1
    VSNormal = 2
    _globalPtr = None

    def __init__(self, *args):
        self.verifySsl = self.VSNormal

    @classmethod
    def getGlobalPtr(cls):
        if cls._globalPtr is None:
            cls._globalPtr = cls()
        return cls._globalPtr

    def makeChannel(self, persistentConnection=False):
        return NullHTTPChannel()

    def getVerifySsl(self):
        return self.verifySsl

    def setVerifySsl(self, verifySsl):
        self.verifySsl = verifySsl

    def getProxySpec(self):
        return ''

    def getDirectHostSpec(self):
        return ''

    def getProxiesForUrl(self, url):
        return ''

    def getCookie(self, cookie):
        return None

    def __getattr__(self, name):
        # Settings (setProxySpec, addPreapprovedServerCertificateName, ...)
        # are ignored.
        return lambda *args, **kwargs: None


def install():
    """Puts the stand-in into panda3d.core when Panda3D has no HTTPClient."""
    import panda3d.core
    if not hasattr(panda3d.core, 'HTTPClient'):
        panda3d.core.HTTPClient = NullHTTPClient
        print('OfflineStart: this Panda3D has no HTTPClient; the game stays offline')
