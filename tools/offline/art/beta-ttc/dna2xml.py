"""Turns an old bracketed .dna file (Toontown's original DNA syntax) into
the XML DNA this game reads (toontown/dna).

    prop "name" [ code [ "x" ] pos [ 1 2 3 ] ]
becomes
    <prop name="name" code="x"><pos x="1" y="2" z="3" /></prop>

`modelPath` maps a model path in a storage file to the one to write (the
beta's converted copy); returning None drops the model.
"""

import re
from xml.sax.saxutils import escape, quoteattr

TOKEN = re.compile(r'//[^\n]*|"(?:[^"\\]|\\.)*"|\[|\]|[^\s\[\]"]+')


def tokenize(text):
    for m in TOKEN.finditer(text):
        tok = m.group(0)
        if tok.startswith('//'):
            continue
        yield tok


class Item:
    def __init__(self, keyword, args, children):
        self.keyword = keyword
        self.args = args          # strings/numbers before the '['
        self.children = children  # Items, or bare values inside the brackets

    def values(self):
        return [c for c in self.children if not isinstance(c, Item)]

    def items(self, keyword=None):
        return [c for c in self.children if isinstance(c, Item) and (keyword is None or c.keyword == keyword)]

    def first(self, keyword):
        found = self.items(keyword)
        return found[0] if found else None


def unquote(tok):
    if tok.startswith('"'):
        return tok[1:-1]
    return tok


def parse(text):
    toks = list(tokenize(text))
    pos = [0]

    def parseList():
        out = []
        while pos[0] < len(toks):
            tok = toks[pos[0]]
            if tok == ']':
                pos[0] += 1
                return out
            if tok == '[':
                raise ValueError('unexpected [ at token %d' % pos[0])
            if tok.startswith('"') or re.match(r'^-?[\d.]', tok):
                out.append(unquote(tok))
                pos[0] += 1
                continue
            # keyword, args..., '[' children ']'
            keyword = tok
            pos[0] += 1
            args = []
            while toks[pos[0]] != '[':
                args.append(unquote(toks[pos[0]]))
                pos[0] += 1
            pos[0] += 1
            children = parseList()
            out.append(Item(keyword, args, children))
        return out

    return parseList()


def attrs(**kw):
    return ''.join(' %s=%s' % (k, quoteattr(str(v))) for k, v in kw.items() if v is not None)


def num(v):
    f = float(v)
    if abs(f) < 1e-6:
        return '0'
    return ('%.6g' % f)


class Writer:
    def __init__(self, modelPath=None):
        self.lines = []
        self.modelPath = modelPath or (lambda p: p)

    def out(self, depth, text):
        self.lines.append('\t' * depth + text)

    # --- properties shared by scene nodes ------------------------------
    def props(self, item, depth):
        for c in item.items():
            v = c.values()
            if c.keyword == 'pos':
                self.out(depth, '<pos%s />' % attrs(x=num(v[0]), y=num(v[1]), z=num(v[2])))
            elif c.keyword == 'hpr':
                self.out(depth, '<hpr%s />' % attrs(h=num(v[0]), p=num(v[1]), r=num(v[2])))
            elif c.keyword == 'nhpr':
                self.out(depth, '<nhpr%s />' % attrs(h=num(v[0]), p=num(v[1]), r=num(v[2])))
            elif c.keyword == 'scale':
                self.out(depth, '<scale%s />' % attrs(x=num(v[0]), y=num(v[1]), z=num(v[2])))
            elif c.keyword == 'color':
                self.out(depth, '<color%s />' % attrs(r=num(v[0]), g=num(v[1]), b=num(v[2]), a=num(v[3])))

    def valueOf(self, item, keyword, default=None):
        c = item.first(keyword)
        if c is None or not c.values():
            return default
        return c.values()[0]

    # --- scene --------------------------------------------------------
    def scene(self, items, zone):
        self.out(0, '<?xml version="1.0" encoding="utf-8"?>')
        self.out(0, '<scene%s>' % attrs(zone=zone))
        for item in items:
            self.node(item, 1)
        self.out(0, '</scene>')

    def children(self, item, depth):
        for c in item.items():
            if c.keyword in ('pos', 'hpr', 'nhpr', 'scale', 'color', 'code', 'vis', 'width', 'title', 'height',
                             'count', 'kern', 'flags', 'wiggle', 'stumble', 'indent', 'stomp', 'letters', 'text'):
                continue
            self.node(c, depth)

    def node(self, item, depth):
        k = item.keyword
        name = item.args[0] if item.args else ''
        if k in ('group', 'node'):
            self.out(depth, '<%s%s>' % (k, attrs(name=name)))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</%s>' % k)
        elif k == 'visgroup':
            vis = item.first('vis')
            self.out(depth, '<visgroup%s>' % attrs(zone=name, vis=' '.join(vis.values()) if vis else ''))
            self.children(item, depth + 1)
            self.out(depth, '</visgroup>')
        elif k in ('prop', 'street'):
            self.out(depth, '<%s%s>' % (k, attrs(name=name, code=self.valueOf(item, 'code'))))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</%s>' % k)
        elif k == 'landmark_building':
            self.out(depth, '<landmark_building%s>' % attrs(id=name, code=self.valueOf(item, 'code')))
            title = self.valueOf(item, 'title')
            if title:
                self.out(depth + 1, '<title>%s</title>' % escape(title))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</landmark_building>')
        elif k == 'flat_building':
            self.out(depth, '<flat_building%s>' % attrs(id=name, width=self.valueOf(item, 'width', '0')))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</flat_building>')
        elif k == 'wall':
            self.out(depth, '<wall%s>' % attrs(code=self.valueOf(item, 'code'), height=self.valueOf(item, 'height', '0')))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</wall>')
        elif k == 'windows':
            self.out(depth, '<windows%s>' % attrs(code=self.valueOf(item, 'code'), count=self.valueOf(item, 'count', '0')))
            self.props(item, depth + 1)
            self.out(depth, '</windows>')
        elif k in ('cornice', 'door', 'flat_door'):
            self.out(depth, '<%s%s>' % (k, attrs(code=self.valueOf(item, 'code'))))
            self.props(item, depth + 1)
            self.out(depth, '</%s>' % k)
        elif k == 'sign':
            self.out(depth, '<sign%s>' % attrs(code=self.valueOf(item, 'code')))
            self.props(item, depth + 1)
            self.children(item, depth + 1)
            self.out(depth, '</sign>')
        elif k == 'baseline':
            kw = {}
            for key in ('kern', 'wiggle', 'stumble', 'indent', 'stomp', 'width', 'height'):
                v = self.valueOf(item, key)
                if v is not None:
                    kw[key] = num(v)
            flags = self.valueOf(item, 'flags')
            if flags:
                kw['flags'] = flags
            self.out(depth, '<baseline%s>' % attrs(code=self.valueOf(item, 'code'), **kw))
            self.props(item, depth + 1)
            # Old files spell the text one letter per text item; the
            # letters and graphics keep their order.
            text = ''
            for c in item.items():
                if c.keyword == 'text':
                    for letters in c.items('letters'):
                        text += ''.join(letters.values())
                elif c.keyword == 'graphic':
                    if text:
                        self.out(depth + 1, '<text>%s</text>' % escape(text))
                        text = ''
                    self.out(depth + 1, '<graphic%s>' % attrs(code=self.valueOf(c, 'code')))
                    self.props(c, depth + 2)
                    self.out(depth + 1, '</graphic>')
            if text:
                self.out(depth + 1, '<text>%s</text>' % escape(text))
            self.out(depth, '</baseline>')
        else:
            raise ValueError('unknown DNA item %s' % k)

    # --- storage --------------------------------------------------------
    def storage(self, items):
        self.out(0, '<?xml version="1.0" encoding="utf-8"?>')
        self.out(0, '<storage scope="global">')
        for item in items:
            k = item.keyword
            if k in ('model', 'hood_model', 'place_model'):
                # Fonts are stored by the game itself (humanist, mickey, suit).
                if all(sn.values()[0] == 'font' for sn in item.items('store_node')):
                    continue
                path = self.modelPath(item.args[0])
                if path is None:
                    continue
                scope = {'model': None, 'hood_model': 'hood', 'place_model': 'place'}[k]
                self.out(1, '<model%s>' % attrs(path=path, scope=scope))
                for sn in item.items('store_node'):
                    v = sn.values()
                    if len(v) >= 3:
                        self.out(2, '<store_node%s />' % attrs(root=v[0], code=v[1], node=v[2]))
                    else:
                        self.out(2, '<store_node%s />' % attrs(root=v[0], code=v[1]))
                self.out(1, '</model>')
            elif k == 'store_texture':
                v = item.values()
                path = self.modelPath(v[2]) if len(v) > 2 else None
                if path:
                    self.out(1, '<store_texture%s />' % attrs(root=v[0], code=v[1], path=path))
            elif k == 'store_font':
                continue
            else:
                raise ValueError('unknown storage item %s' % k)
        self.out(0, '</storage>')

    def text(self):
        return '\n'.join(self.lines) + '\n'
