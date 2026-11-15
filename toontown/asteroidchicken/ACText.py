"""The words and numbers of the Toontown 2.0 trolley games in Toontown's own
fonts.

Disney's prototypes drew their HUDs in whatever fonts Unity had to hand
(a condensed sans, Comic Sans). In Toontown they are drawn the way every
other trolley game draws its own: scores, counts and headings in the sign
font, a Cog's taunts in the Minnie font, small print in the interface font.
A line is still set where the prototype's line sat: by its baseline and by
how tall its capitals are, in the units of the node it hangs from.

The sign font draws a grey rim round every letter, and the rim is part of
what is measured: of a capital's height about three quarters is the white
letter, which stands about an eighth above the foot.

`minigame-prototype-fonts #t` brings the prototypes' own fonts back.
"""

from panda3d.core import ConfigVariableBool, DynamicTextFont, NodePath, TextNode

from toontown.toonbase import ToontownGlobals

ALIGN = {'left': TextNode.ALeft, 'right': TextNode.ARight, 'centre': TextNode.ACenter}


def wantToonFonts():
    return not ConfigVariableBool('minigame-prototype-fonts', False).getValue()


def signFont():
    return ToontownGlobals.getSignFont()


def minnieFont():
    return ToontownGlobals.getMinnieFont()


def interfaceFont():
    return ToontownGlobals.getInterfaceFont()


_sharp = {}


def sharp(font, pixels=80):
    """A copy of one of Toontown's fonts, drawn finer, for lettering much bigger than the game's own (the game's copy is left as it is)."""
    if not isinstance(font, DynamicTextFont) or font.getPixelsPerUnit() >= pixels:
        return font
    key = (id(font), pixels)
    if key not in _sharp:
        copy = font.makeCopy()
        copy.setPixelsPerUnit(pixels)
        _sharp[key] = (font, copy)      # (the font itself is kept too, so that its id stays its own)
    return _sharp[key][1]


class ToonText:
    """Some text in one of Toontown's fonts. cap is the height of its capitals; place() puts its baseline."""

    def __init__(self, parent, font, cap, align='left', colour=(1.0, 1.0, 1.0, 1.0), text=''):
        self.textNode = TextNode('toonText')
        self.textNode.setFont(font)
        self.textNode.setAlign(ALIGN[align])
        self.textNode.setTextColor(*colour)
        # How tall the font really draws a capital, and where its foot is, off the letter itself.
        self.textNode.setText('H')
        lo, hi = NodePath(self.textNode.generate()).getTightBounds()
        self.size = cap / max(hi[2] - lo[2], 1e-6)
        self.foot = lo[2]
        self.textNode.setText(text)
        self.text = text
        self.node = parent.attachNewNode(self.textNode)
        self.node.setScale(self.size)
        self.at = (0.0, 0.0)
        self.limit = None

    def set(self, text):
        if text != self.text:
            self.text = text
            self.textNode.setText(text)
            if self.limit is not None:
                self.fit(self.limit)

    def place(self, x, baseline):
        self.at = (x, baseline)
        self.node.setPos(x, 0.0, baseline - self.foot * self.node.getSz())

    def width(self, text=None):
        """How wide the text (or some other text in this font and size) is."""
        if text is None:
            return self.textNode.getWidth() * self.node.getSx()
        return self.textNode.calcWidth(text) * self.node.getSx()

    def fit(self, width):
        """Shrinks the text, whenever it must, to be no wider than this. Its baseline stays."""
        self.limit = width
        wide = self.textNode.getWidth() * self.size
        self.node.setScale(self.size * min(1.0, width / max(wide, 1e-6)))
        self.place(*self.at)

    def bounds(self):
        """The ink's own box in the parent's units: (left, right, bottom, top)."""
        box = self.node.getTightBounds(self.node.getParent())
        if box is None:
            # (No text, no ink: where it would start.)
            return self.at[0], self.at[0], self.at[1], self.at[1]
        return box[0][0], box[1][0], box[0][2], box[1][2]

    def centreOn(self, x, z):
        """Moves the text so that the middle of its ink is here (for a block of more than one line)."""
        left, right, bottom, top = self.bounds()
        pos = self.node.getPos()
        self.node.setPos(pos[0] + x - (left + right) * 0.5, 0.0, pos[2] + z - (bottom + top) * 0.5)
