"""Check that a change to site-kit leaves the sites' built pages as they were.

  python3 -I scripts/check_sites.py before [<site folder>...]             build each site, keep a copy
  python3 -I scripts/check_sites.py after [--release] [<site folder>...]  build again, compare with the copy
  python3 -I scripts/check_sites.py compare <build A> <build B>           compare two build folders

Sites: with no folders, "before" and "after" take every folder beside the kit whose package.json
lists site-kit in dependencies or devDependencies. Each site's kit spec is printed.

The kit each build uses is checked before anything builds. "before" and "after --release" want the
released kit: no "file:" spec, and node_modules/site-kit an installed copy. "after" wants
node_modules/site-kit to be a link to the kit this script belongs to.

Builds: each runs `npm run build` with the site's old dist/ moved aside (to the snapshots folder,
under the system's temporary directory), so a build that writes nothing can't pass its old output.
"before" keeps a copy of the new dist/ there (printed).

The comparison:
- each file in _astro/ gets a key: its name without the hash, and a digest of its content in which
  the names of other assets are replaced by their keys. A renamed file with the same content keeps
  its key; a file's key changes when anything it reaches changes. The two builds' keys must match;
- everywhere else, each asset's name is read as its key, and then every file must be identical:
  order, whitespace and attributes all count;
- to say where a page changed, it is split into its <head> tags, its skip link and header, the
  rest of the body, and the doctype and <html> tag, with a diff of the first changed head and
  header; a change outside all four (spacing in the head, say) is listed as elsewhere.

Exit status: 0 when nothing differs; 1 when something does; 2 when nothing could be compared: a
usage error, no site, the wrong kit, a failed build, a build folder that is missing or has no HTML
page, or assets that refer to each other in a cycle. The header's look is checked in a browser
instead (scripts/measure-header.js).
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
SNAPSHOTS = Path(tempfile.gettempdir()) / 'site-kit-check'

# A whole file name as it stands in a page, a stylesheet or a script: bounded by anything that
# can't be part of a name, so "Base.Ab12Cd34.css.map" is not a mention of "Base.Ab12Cd34.css".
NAME = re.compile(rb'[\w.-]+')
# An asset's name: stem, the 8-character hash (letters, digits, "-" and "_"), extension.
HASHED = re.compile(rb'(.+)\.[A-Za-z0-9_-]{8}(\.[A-Za-z0-9]+)')


class CheckError(Exception):
    """Nothing could be compared: main() prints the reason and returns 2."""


def keyed(data: bytes, keys: dict) -> bytes:
    """The data with each asset's name replaced by its key."""
    return NAME.sub(lambda m: keys.get(m.group(), m.group()), data)


def asset_keys(root: Path):
    """The files in a build's _astro/ by name, and each one's key, worked out from the leaves up."""
    paths = {}
    for f in sorted((root / '_astro').rglob('*')):
        if f.is_file():
            if f.name.encode() in paths:
                raise CheckError(f'two assets named {f.name} in {root}')
            paths[f.name.encode()] = f
    keys, chain = {}, []

    def key(name):
        if name in chain:
            cycle = [n.decode() for n in chain[chain.index(name):] + [name]]
            raise CheckError(f'assets refer to each other in a cycle in {root}: {" → ".join(cycle)}')
        if name not in keys:
            chain.append(name)
            data = paths[name].read_bytes()
            for other in sorted(set(NAME.findall(data)) & paths.keys()):
                key(other)
            chain.pop()
            hashed = HASHED.fullmatch(name)
            plain = hashed.group(1) + hashed.group(2) if hashed else name
            keys[name] = plain + b'#' + hashlib.sha256(keyed(data, keys)).hexdigest()[:16].encode()

    for name in paths:
        key(name)
    return paths, keys


def plain_name(key: bytes) -> bytes:
    return key.rsplit(b'#', 1)[0]


class Build:
    """A build folder: its assets' keys and its other files. Missing or without a page is an error."""

    def __init__(self, root: Path):
        if not root.is_dir():
            raise CheckError(f'no build folder: {root}')
        self.root = root
        files = {p.relative_to(root) for p in root.rglob('*') if p.is_file()}
        self.files = {f for f in files if f.parts[0] != '_astro'}
        if not any(f.suffix == '.html' for f in self.files):
            raise CheckError(f'no HTML page in {root}')
        self.paths, self.keys = asset_keys(root)

    def read(self, file: Path) -> bytes:
        return keyed((self.root / file).read_bytes(), self.keys)

    def rules(self, name: bytes) -> list:
        text = keyed(self.paths[name].read_bytes(), self.keys).decode('utf-8', 'replace')
        return [r.strip() for r in re.split(r'(?<=\})', text) if r.strip()]

    def unmatched(self, other: 'Build') -> list:
        """The names of the assets whose keys the other build lacks."""
        left = Counter(self.keys.values()) - Counter(other.keys.values())
        names = []
        for name, key in sorted(self.keys.items()):
            if left[key]:
                left[key] -= 1
                names.append(name)
        return names


class HeadTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.in_head, self.cur = [], False, None

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        elif self.in_head:
            self.cur = [f'<{tag}' + ''.join(f' {k}="{v}"' for k, v in attrs) + '>', '']
            self.tags.append(self.cur)

    def handle_data(self, data):
        if self.in_head and self.cur and self.cur[0].startswith(('<title', '<script', '<style', '<noscript')):
            self.cur[1] += data

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


def head_tags(html: str) -> list:
    p = HeadTags()
    p.feed(html)
    return [t + (f' «{d.strip()}»' if d.strip() else '') for t, d in p.tags]


SKIP = re.compile(r'<a\b[^>]*href="#main"[^>]*>.*?</a>', re.S)
HEADER = re.compile(r'<header\b.*?</header>', re.S)
PARTS = ('<head> tags', 'header or skip link', 'content (outside the header)', 'doctype or <html> tag')


def page_parts(page: bytes):
    """The PARTS of a page, each compared exactly: they only say where a changed page changed."""
    html = page.decode('utf-8', 'replace')
    body = html.split('</head>', 1)[-1]
    skip, header = SKIP.search(body), HEADER.search(body)
    top = (skip.group(0) if skip else '') + (header.group(0) if header else '')
    rest = HEADER.sub('<HEADER/>', SKIP.sub('', body, count=1), count=1)
    return head_tags(html), top, rest, html.split('<head', 1)[0]


def show_diff(title, before: list, after: list, limit=40):
    lines = list(difflib.unified_diff(before, after, 'before', 'after', lineterm='', n=1))
    print(f'  {title}:')
    for line in lines[:limit]:
        print(f'    {line[:200]}')
    if len(lines) > limit:
        print(f'    … and {len(lines) - limit} more lines')


def compare(before: Path, after: Path) -> bool:
    """Print what differs between two build folders; return True if nothing does."""
    b, a = Build(before), Build(after)
    same = True

    def report(label, items, limit=10):
        nonlocal same
        items = sorted(items)
        if items:
            same = False
            print(f'  {label} ({len(items)}):')
            for i in items[:limit]:
                print(f'    {str(i)[:200]}')
            if len(items) > limit:
                print(f'    … and {len(items) - limit} more')

    def differs(f):
        raw_b, raw_a = (before / f).read_bytes(), (after / f).read_bytes()
        # Equal bytes can only read differently through an asset whose key changed under the same
        # name, which the assets' own comparison reports; this spares keying every large file.
        return raw_b != raw_a and keyed(raw_b, b.keys) != keyed(raw_a, a.keys)

    common = b.files & a.files
    report('only before', b.files - a.files)
    report('only after', a.files - b.files)
    report('other files changed', [f for f in common if f.suffix != '.html' and differs(f)])

    gone, new = b.unmatched(a), a.unmatched(b)
    report('assets changed or removed (before)', [n.decode() for n in gone])
    report('assets changed or added (after)', [n.decode() for n in new])
    count_b, count_a = (Counter(map(plain_name, x.keys.values())) for x in (b, a))
    for name in gone:  # a stylesheet with one counterpart: show which rules changed
        plain = plain_name(b.keys[name])
        if plain.endswith(b'.css') and count_b[plain] == 1 and count_a[plain] == 1:
            counterpart = next(n for n in new if plain_name(a.keys[n]) == plain)
            show_diff(f'CSS rules, {plain.decode()}', b.rules(name), a.rules(counterpart))

    pages = sorted(f for f in common if f.suffix == '.html')
    changed, elsewhere, diffs = {part: [] for part in PARTS}, [], {}
    for f in pages:
        page_b, page_a = b.read(f), a.read(f)
        if page_b == page_a:
            continue
        parts_b, parts_a = page_parts(page_b), page_parts(page_a)
        where = [part for part, pb, pa in zip(PARTS, parts_b, parts_a) if pb != pa]
        for part in where:
            changed[part].append(f)
        if not where:
            elsewhere.append(f)
        if parts_b[0] != parts_a[0]:
            diffs.setdefault('<head> diff', (f, parts_b[0], parts_a[0]))
        if parts_b[1] != parts_a[1]:
            lines = lambda top: re.sub(r'>\s*<', '>\n<', top).splitlines()
            diffs.setdefault('header diff', (f, lines(parts_b[1]), lines(parts_a[1])))
    print(f'  HTML pages compared: {len(pages)}')
    for part, files in changed.items():
        report(f'pages whose {part} changed', files)
    report('pages that changed elsewhere (spacing in the head, say)', elsewhere)
    for title, (f, lines_b, lines_a) in diffs.items():
        show_diff(f'{title}, {f}', lines_b, lines_a)
    print('  identical' if same else '  DIFFERENT')
    return same


def kit_spec(package: Path):
    """The site-kit spec in a package.json, or None when it doesn't list the kit."""
    try:
        data = json.loads(package.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise CheckError(f"can't read {package}: {e}")
    for field in ('dependencies', 'devDependencies'):
        deps = data.get(field) if isinstance(data, dict) else None
        if isinstance(deps, dict) and 'site-kit' in deps:
            return str(deps['site-kit'])
    return None


def find_sites(folders) -> list:
    """Each site folder with its kit spec: the folders given, or every site beside the kit."""
    if not folders:
        beside = [p for p in sorted(KIT.parent.iterdir()) if (p / 'package.json').is_file()]
        sites = [(p, kit_spec(p / 'package.json')) for p in beside]
        sites = [(p, spec) for p, spec in sites if spec is not None]
        if not sites:
            raise CheckError(f'no site found: no package.json in a folder of {KIT.parent} lists site-kit')
        return sites
    sites = []
    for site in (Path(f).resolve() for f in folders):
        if not (site / 'package.json').is_file():
            raise CheckError(f'not a site folder: {site}')
        sites.append((site, kit_spec(site / 'package.json')))
        if sites[-1][1] is None:
            raise CheckError(f"{site / 'package.json'} doesn't list site-kit")
    return sites


def kit_problem(site: Path, spec: str, released: bool):
    """Why this site's build wouldn't use the kit this step is about, with the fix; None if it would."""
    installed = site / 'node_modules' / 'site-kit'
    link = f'in {site.name}, run: npm install {os.path.relpath(KIT, site)}'
    by_tag = f'in {site.name}, install the released kit by its tag (npm install <the tag spec>)'
    if released and spec.startswith('file:'):
        return f'{site.name}: package.json links the kit ({spec}), but this step checks the released one; {by_tag}'
    if not installed.exists():
        return f'{site.name}: no kit in node_modules/site-kit; {by_tag if released else link}'
    if released and site / 'node_modules' not in installed.resolve().parents:
        return f'{site.name}: node_modules/site-kit is a link to {installed.resolve()}, not an installed copy; {by_tag}'
    if not released and installed.resolve() != KIT:
        return f'{site.name}: node_modules/site-kit is not a link to this kit ({KIT}); {link}'
    return None


def build(site: Path) -> Path:
    """Run the site's build with its old dist/ moved aside; return the new dist/."""
    dist, previous = site / 'dist', SNAPSHOTS / f'{site.name}-previous-dist'
    where = ''
    if dist.exists():
        if previous.exists():
            shutil.rmtree(previous)
        previous.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(dist, previous)
        where = f' (the dist/ from before this run is in {previous})'
    print(f'building {site.name} …')
    run = subprocess.run(['npm', 'run', 'build'], cwd=site, capture_output=True, text=True)
    if run.returncode != 0:
        print(run.stdout[-3000:], run.stderr[-3000:], sep='\n')
        raise CheckError(f'build failed in {site}{where}')
    if not dist.is_dir():
        raise CheckError(f'the build left no dist/ in {site}{where}')
    if not any(dist.rglob('*.html')):
        raise CheckError(f'the build left no HTML page in {dist}{where}')
    return dist


def run(argv) -> int:
    command, args = (argv[0], argv[1:]) if argv else (None, [])
    release = command == 'after' and '--release' in args
    folders = [a for a in args if not (release and a == '--release')]
    usage = command not in ('before', 'after', 'compare') or any(f.startswith('-') for f in folders)
    if usage or (command == 'compare' and len(folders) != 2):
        print(__doc__)
        return 2
    if command == 'compare':
        return 0 if compare(Path(folders[0]), Path(folders[1])) else 1

    sites, problems = find_sites(folders), []
    for site, spec in sites:
        print(f'{site.name}: site-kit {spec}')
        problems.append(kit_problem(site, spec, released=command == 'before' or release))
        if command == 'after' and not (SNAPSHOTS / site.name).is_dir():
            problems.append(f'{site.name}: no "before" copy in {SNAPSHOTS / site.name}; run "before" first')
    if any(problems):
        raise CheckError('nothing was built.\n  ' + '\n  '.join(p for p in problems if p))

    ok = True
    for site, _ in sites:
        dist, snapshot = build(site), SNAPSHOTS / site.name
        if command == 'before':
            shutil.rmtree(snapshot, ignore_errors=True)
            shutil.copytree(dist, snapshot)
            print(f'  kept a copy in {snapshot}')
        else:
            print(f'{site.name}: before → after')
            ok = compare(snapshot, dist) and ok
    return 0 if ok else 1


def main(argv) -> int:
    try:
        return run(argv)
    except (CheckError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
