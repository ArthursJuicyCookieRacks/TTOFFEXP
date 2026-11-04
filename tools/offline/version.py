"""The game's version number, shared by setup.py and the build workflow.

The VERSION file in the repository root holds the version's big number
(the major version), for example 3. Every build made with "Run workflow"
on GitHub gets the next number in that series: 3.0, then 3.1, 3.2 and so
on (after 3.9 comes 3.10, not 4.0). Each numbered build leaves a tag named
build-<version> on the commit it built, and the next build looks at those
tags to find the next number, so the count is the same on every branch.

Moving to the next big version (4.0, 4.1...) is changing VERSION to 4.

    python tools/offline/version.py next    # prints e.g. 3.1
    python tools/offline/version.py check 3.1

The game reads its version from the TT_VERSION environment variable when
it is built (the workflow sets it); without one, it is the "dev" version.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG_PREFIX = 'build-'
VERSION_RE = re.compile(r'^(\d+)\.(\d+)$')


def major():
    with open(os.path.join(ROOT, 'VERSION'), encoding='utf-8') as file:
        text = file.read().strip()
    if not text.isdigit():
        raise SystemExit('VERSION must hold one whole number (the big version), not %r' % text)
    return int(text)


def parse(version):
    """'3.12' -> (3, 12), or None for anything else (a test build's label)."""
    match = VERSION_RE.match(version or '')
    return (int(match.group(1)), int(match.group(2))) if match else None


def nextVersion(tags, series=None):
    """The next version of the series after the builds the tags name."""
    series = major() if series is None else series
    minors = [v[1] for v in (parse(tag[len(TAG_PREFIX):]) for tag in tags if tag.startswith(TAG_PREFIX))
              if v and v[0] == series]
    return '%d.%d' % (series, max(minors) + 1 if minors else 0)


def buildTags():
    output = subprocess.run(['git', 'tag', '--list', TAG_PREFIX + '*'], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout
    return output.split()


def androidVersionCode(version):
    """Android needs a whole number that goes up with every release."""
    match = re.match(r'\d+\.\d+', version)
    parsed = parse(match.group(0)) if match else None
    return parsed[0] * 1000 + parsed[1] if parsed else 1


def gameVersion():
    """(number for the packaging tools, the label players see)."""
    label = os.environ.get('TT_VERSION') or 'dev'
    # A test build's label is the coming number and -test, e.g. 3.1-test.
    match = re.match(r'\d+\.\d+', label)
    number = match.group(0) if match else '%d.0' % major()
    return number, label


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'next'
    if command == 'next':
        print(nextVersion(buildTags()))
    elif command == 'check':
        if not parse(sys.argv[2]):
            raise SystemExit('%r is not a version like 3.1' % sys.argv[2])
    else:
        raise SystemExit(__doc__)
