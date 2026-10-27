# Writes toontown/toon/ExtraClothes.py: the clothes in resources/ that
# ToonDNA does not list. Run from the repository root.
import sys, builtins, glob, os, re; sys.path.insert(0,'.')
import panda3d.core as pc
builtins.config = pc
from toontown.toon import ToonDNA as D
def stem(x): return os.path.splitext(x)[0]
known=set(stem(x) for x in D.Shirts+D.Sleeves+D.BoyShorts+[g[0] for g in D.GirlBottoms])
files=sorted(f[len('resources/'):] for f in glob.glob('resources/phase_*/maps/*') if f.endswith('.jpg') or f.endswith('.png'))
shirts=[f for f in files if re.search(r'_shirt_|male_shirtNew', f) and stem(f) not in known]
sleeveFiles=[f for f in files if re.search(r'shirtSleeve_|male_sleeveNew', f)]
shorts=[f for f in files if re.search(r'avt_shorts_|desat_shorts', f) and stem(f) not in known]
skirts=[f for f in files if re.search(r'avt_skirt_|avt_longSkirt', f) and stem(f) not in known]
def key(f, word):
    return re.split(word, os.path.basename(stem(f)))[-1]
sleeveByName = {}
for f in sleeveFiles:
    sleeveByName.setdefault(key(f, r'shirtSleeve_|sleeve'), f)
newSleeves = []
def sleeveIndex(f):
    if f in D.Sleeves: return D.Sleeves.index(f)
    if f not in newSleeves: newSleeves.append(f)
    return len(D.Sleeves) + newSleeves.index(f)
desatColours = [c for c in D.ShirtStyles['bss1'][2]]
bottomColours = D.BottomStyles['bbs1'][1]
out = []
shirtStyles = {}
for n, f in enumerate([D.Shirts[151]] + shirts):
    name = key(f, r'shirt_|shirt')
    sl = sleeveByName.get(name) or sleeveByName.get(name.rstrip('fm')) or sleeveByName.get(re.sub(r'\d+[fm]?$', '', name))
    if sl is None:
        # The sleeve of the nearest name (taskForce for taskForceSleuth).
        best = max(sleeveByName, key=lambda k: len(os.path.commonprefix([k, name])))
        if len(os.path.commonprefix([best, name])) >= 4:
            sl = sleeveByName[best]
    if sl is None:
        sl = 'phase_3/maps/desat_sleeve_1.jpg'
        print('# no sleeve for', f, file=sys.stderr)
    idx = 151 if n == 0 else len(D.Shirts) + n - 1
    shirtStyles['mat_ss%d' % (n + 1)] = [idx, sleeveIndex(sl), [(27, 27)]]
boyStyles = {'mat_bs1': [58, [27]]}
for n, f in enumerate(shorts):
    colours = list(bottomColours) if 'desat' in f else [27]
    boyStyles['mat_bs%d' % (n + 2)] = [len(D.BoyShorts) + n, colours]
girlStyles = {}
for n, f in enumerate(shorts):
    colours = list(bottomColours) if 'desat' in f else [27]
    girlStyles['mat_gsh%d' % (n + 1)] = [len(D.GirlBottoms) + n, colours]
for n, f in enumerate(skirts):
    colours = list(bottomColours) if 'desat' in f else [27]
    girlStyles['mat_gsk%d' % (n + 1)] = [len(D.GirlBottoms) + len(shorts) + n, colours]
import pprint
text = '''"""Every shirt, pair of shorts and skirt in the game's files that ToonDNA's
own lists stop short of, so Make-A-Toon can offer them all. ToonDNA adds
these at the ends of its lists, so the numbers of the clothes before them
stay the same. Made by tools/offline/gen_extra_clothes.py from resources/."""

'''
for name, value in (('Shirts', shirts), ('Sleeves', newSleeves), ('Shorts', shorts), ('Skirts', skirts),
                    ('ShirtStyles', shirtStyles), ('BoyBottomStyles', boyStyles), ('GirlBottomStyles', girlStyles)):
    text += '%s = %s\n\n' % (name, pprint.pformat(value))
open('toontown/toon/ExtraClothes.py', 'w').write(text.rstrip('\n') + '\n')
print(len(D.Shirts) + len(shirts), len(D.Sleeves) + len(newSleeves), len(D.BoyShorts) + len(shorts),
      len(D.GirlBottoms) + len(shorts) + len(skirts), file=sys.stderr)
