"""Check that a change to site-kit leaves the sites' built pages as they were.

  python3 -I scripts/check_sites.py before [<site folder>...]
                                          build each site, keep a copy
  python3 -I scripts/check_sites.py after [--release] [<planned change>...] [<site folder>...]
                                          build again, compare with the copy
  python3 -I scripts/check_sites.py compare [<planned change>...] <build A> <build B>
                                          compare two build folders

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

Planned changes ("after" and "compare"), each repeatable. Each must find exactly what it names, or
nothing is compared (exit status 2), so a typo can't hide a change:
- --without <tag> or --without <tag>.<class>: cut every element with that tag (and with that class
  word among its classes, its case kept: div.lane-row) from each HTML page of both builds before
  comparing, so a planned markup change on every page doesn't hide what else changed. The report's
  first line says what was taken out; an unclosed element is an error, and so is a <tag>.<class>
  that matches no element in either build.
- --changed-asset <name>: allow the asset with that name (without its hash, such as Base.css) to
  differ. Pages and assets that differ only through it count as the same, and its own diff is
  printed. It must be in both builds, once each, and differ.
- --renamed-asset <old> <new>: pair the asset named <old> in before with the one named <new> in
  after (names without their hash), as --changed-asset does with one name; their diff is printed.
  <old> must be in before once and not in after, <new> in after once and not in before.
- --new-asset <name>: allow an asset that only after has (a chunk the build split off, say); its
  content is printed. It must be in after once and not in before.
- --replace <old> <new>: replace the text <old> with <new> in the before build's pages (its HTML
  files) before comparing, for a planned change of wording; the after build's pages are left as
  they are, so one that still holds <old> differs. <old> must be in a page of the before build,
  and differ from <new>. Plain text: a page that writes <old> in its own words differs too.

Exit status: 0 when nothing differs; 1 when something does; 2 when nothing could be compared: a
usage error, no site, the wrong kit, a failed build, a build folder that is missing or has no HTML
page, assets that refer to each other in a cycle, or a planned change that doesn't find exactly
what it names (above). The header's look is checked
in a browser instead (scripts/measure-header.js).
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
# An HTML tag name accepted by --without: ASCII letter, then letters, digits or hyphens.
TAG_NAME = re.compile(r'[A-Za-z][A-Za-z0-9-]*')
# A --without value: a tag name, or a tag name, a dot and one class word (letters, digits, "-", "_").
WITHOUT = re.compile(TAG_NAME.pattern + r'(?:\.[A-Za-z0-9_-]+)?')
# The planned-change options of "after" and "compare", and how many values each takes.
PLANNED = {'--without': 1, '--changed-asset': 1, '--renamed-asset': 2, '--new-asset': 1, '--replace': 2}
VOID_ELEMENTS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'source', 'track', 'wbr',
})
# Elements whose content is text even where it looks like a tag.
TEXT_CONTENT_ELEMENTS = ('script', 'style', 'textarea', 'title')


class CheckError(Exception):
    """Nothing could be compared: main() prints the reason and returns 2."""


def keyed(data: bytes, keys: dict) -> bytes:
    """The data with each asset's name replaced by its key."""
    return NAME.sub(lambda m: keys.get(m.group(), m.group()), data)


def plain_of(name: bytes) -> bytes:
    """An asset's name without its hash."""
    hashed = HASHED.fullmatch(name)
    return hashed.group(1) + hashed.group(2) if hashed else name


def asset_keys(root: Path, planned=None):
    """The files in a build's _astro/ by name, and each one's key, worked out from the leaves up.

    planned maps a plain name to the key its asset takes whatever its content (a changed asset, or
    the two names of a renamed one), so pages and assets that only follow it count as the same."""
    paths = {}
    for f in sorted((root / '_astro').rglob('*')):
        if f.is_file():
            if f.name.encode() in paths:
                raise CheckError(f'two assets named {f.name} in {root}')
            paths[f.name.encode()] = f
    planned = planned or {}
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
            plain = plain_of(name)
            if plain in planned:
                keys[name] = planned[plain]
            else:
                keys[name] = plain + b'#' + hashlib.sha256(keyed(data, keys)).hexdigest()[:16].encode()

    for name in paths:
        key(name)
    return paths, keys


def plain_name(key: bytes) -> bytes:
    return key.rsplit(b'#', 1)[0]


def css_rules(text: str) -> list:
    return [r.strip() for r in re.split(r'(?<=\})', text) if r.strip()]


class Build:
    """A build folder: its assets' keys and its other files. Missing or without a page is an error."""

    def __init__(self, root: Path, planned=None):
        if not root.is_dir():
            raise CheckError(f'no build folder: {root}')
        self.root = root
        files = {p.relative_to(root) for p in root.rglob('*') if p.is_file()}
        self.files = {f for f in files if f.parts[0] != '_astro'}
        if not any(f.suffix == '.html' for f in self.files):
            raise CheckError(f'no HTML page in {root}')
        self.paths, self.keys = asset_keys(root, planned)

    def read(self, file: Path) -> bytes:
        return keyed((self.root / file).read_bytes(), self.keys)

    def read_asset(self, name: bytes) -> bytes:
        return keyed(self.paths[name].read_bytes(), self.keys)

    def rules(self, name: bytes) -> list:
        return css_rules(self.read_asset(name).decode('utf-8', 'replace'))

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
            # HTMLParser gives None for an attribute without a value (crossorigin, defer).
            shown = ''.join(f' {k}' if v is None else f' {k}="{v}"' for k, v in attrs)
            self.cur = [f'<{tag}{shown}>', '']
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


def without_spec(spec: str):
    """A --without value as (tag, class word or None): the tag in lower case, the class as written."""
    tag, _, word = spec.partition('.')
    return tag.lower(), word or None


def strip_elements(html: str, tags, where: str = '', counts=None) -> str:
    """Cut every element named in tags from an HTML document; raise CheckError if one is unclosed.

    Each of tags is a tag ("footer") or a tag and one exact class word ("div.lane-row"). counts, a
    Counter, if given, gains how many elements each one cut."""
    drop = [without_spec(t) for t in tags]
    if not drop:
        return html
    # HTMLParser counts lines on '\n' alone, so build the offset table the same way.
    starts = [0]
    pos = html.find('\n')
    while pos != -1:
        starts.append(pos + 1)
        pos = html.find('\n', pos + 1)

    class Stripper(HTMLParser):
        # The parser reads what is inside these as text up to their closing tag. Older Pythons
        # list only script and style here; a "<footer>" typed into a textarea or a title is
        # text on every version this way.
        CDATA_CONTENT_ELEMENTS = TEXT_CONTENT_ELEMENTS

        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.cuts, self.outer, self.depth, self.start = [], None, 0, 0

        def dropped(self, tag, attrs):
            """The spec this element matches, or None."""
            words = next((v or '' for k, v in attrs if k == 'class'), '').split()
            for spec, (t, word) in zip(tags, drop):
                if t == tag and (word is None or word in words):
                    if counts is not None:
                        counts[spec] += 1
                    return spec
            return None

        def index(self):
            line, col = self.getpos()
            return starts[line - 1] + col

        def handle_starttag(self, tag, attrs):
            if self.outer is None:
                if self.dropped(tag, attrs):
                    idx = self.index()
                    if tag in VOID_ELEMENTS:
                        self.cuts.append((idx, idx + len(self.get_starttag_text())))
                    else:
                        self.outer, self.depth, self.start = tag, 1, idx
            elif tag == self.outer:
                self.depth += 1

        def handle_startendtag(self, tag, attrs):
            if self.outer is None and self.dropped(tag, attrs):
                idx = self.index()
                self.cuts.append((idx, idx + len(self.get_starttag_text())))

        def handle_endtag(self, tag):
            if self.outer is not None and tag == self.outer:
                self.depth -= 1
                if self.depth == 0:
                    end = html.find('>', self.index() + 2) + 1
                    self.cuts.append((self.start, end))
                    self.outer = None

    parser = Stripper()
    parser.feed(html)
    parser.close()
    if parser.outer is not None:
        loc = f' in {where}' if where else ''
        raise CheckError(f'unclosed <{parser.outer}> element{loc}')
    if not parser.cuts:
        return html
    parts, cur = [], 0
    for start, end in parser.cuts:
        parts.append(html[cur:start])
        cur = end
    parts.append(html[cur:])
    return ''.join(parts)


def named(build: Build, plain: bytes) -> list:
    """The assets of a build whose name without the hash is plain."""
    return [n for n in sorted(build.paths) if plain_of(n) == plain]


def resolve_planned(b: Build, a: Build, planned: list) -> list:
    """Check that each changed asset exists uniquely in both builds and differs; return its keyed pair."""
    pairs = []
    for plain in planned:
        label = plain.decode()
        in_b, in_a = named(b, plain), named(a, plain)
        if not in_b and not in_a:
            raise CheckError(f'changed asset {label} is not in either build')
        if not in_b:
            raise CheckError(f'changed asset {label} is not in {b.root}')
        if not in_a:
            raise CheckError(f'changed asset {label} is not in {a.root}')
        if len(in_b) > 1:
            raise CheckError(f'more than one asset named {label} in {b.root}')
        if len(in_a) > 1:
            raise CheckError(f'more than one asset named {label} in {a.root}')
        data_b, data_a = b.read_asset(in_b[0]), a.read_asset(in_a[0])
        if data_b == data_a:
            raise CheckError(f'changed asset {label} did not differ')
        pairs.append((plain, data_b, data_a))
    return pairs


def only_once(build: Build, plain: bytes, other: Build, what: str) -> bytes:
    """The one asset named plain in build, which other must not have; CheckError otherwise."""
    label, here, there = plain.decode(), named(build, plain), named(other, plain)
    if len(here) != 1:
        raise CheckError(f'{what} {label}: {len(here)} assets of that name in {build.root}, not one')
    if there:
        raise CheckError(f'{what} {label} is also in {other.root}')
    return here[0]


def resolve_renamed(b: Build, a: Build, renamed: list) -> list:
    """Check each renamed pair (old once in before and not after, new once in after and not before);
    return (label, before's content, after's content)."""
    pairs = []
    for old, new in renamed:
        name_b = only_once(b, old, a, 'renamed asset')
        name_a = only_once(a, new, b, 'renamed asset')
        pairs.append((old + ' → '.encode() + new, b.read_asset(name_b), a.read_asset(name_a)))
    return pairs


def resolve_new(b: Build, a: Build, new_assets: list) -> list:
    """Check each new asset (once in after, not in before); return (its name, its content)."""
    return [(name, a.read_asset(name)) for name in (only_once(a, plain, b, 'new asset') for plain in new_assets)]


def show_new_asset(name: bytes, data: bytes, limit=40, width=200):
    """Print a new asset's content, bounded."""
    label = name.decode()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = None
    if text is None or '\x00' in text:
        print(f'  new asset, {label}: binary ({len(data)} bytes)')
        return
    lines = css_rules(text) if name.endswith(b'.css') else text.splitlines()
    print(f'  new asset, {label}:')
    for line in lines[:limit]:
        print(f'    {line[:width]}')
    if len(lines) > limit:
        print(f'    … and {len(lines) - limit} more lines')


def show_changed_lines(title, before: list, after: list, limit=40, width=200):
    """Like show_diff, for lines that can be very long (a stylesheet's rules): a changed line is
    shown from a little before its first difference, so the change is in what is printed."""
    out = []
    for op, b0, b1, a0, a1 in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        olds, news = before[b0:b1], after[a0:a1]
        # Pair each old line with the new line most like it (a rule edited in place), whatever
        # their order in the hunk; a line with no counterpart is a whole line added or removed.
        left = list(range(len(news)))
        for old in olds:
            best = max(left, key=lambda k: difflib.SequenceMatcher(a=old, b=news[k], autojunk=False).ratio(), default=None)
            if best is not None and difflib.SequenceMatcher(a=old, b=news[best], autojunk=False).ratio() >= 0.6:
                left.remove(best)
                new = news[best]
                same = next((i for i, (x, y) in enumerate(zip(old, new)) if x != y), min(len(old), len(new)))
                start = max(0, same - 60)
                lead = '…' if start else ''
                out += [f'-{lead}{old[start:start + width]}', f'+{lead}{new[start:start + width]}']
            else:
                out.append(f'-{old[:width]}')
        out += [f'+{news[k][:width]}' for k in left]
    print(f'  {title}:')
    for line in out[:limit]:
        print(f'    {line}')
    if len(out) > limit:
        print(f'    … and {len(out) - limit} more lines')


def show_planned_diff(plain: bytes, data_b: bytes, data_a: bytes):
    """Print a bounded diff for one planned asset change."""
    label = plain.decode()
    try:
        text_b, text_a = data_b.decode('utf-8'), data_a.decode('utf-8')
    except UnicodeDecodeError:
        print(f'  planned change, {label}: binary ({len(data_b)} → {len(data_a)} bytes)')
        return
    if '\x00' in text_b or '\x00' in text_a:
        print(f'  planned change, {label}: binary ({len(data_b)} → {len(data_a)} bytes)')
        return
    if plain.endswith(b'.css'):
        rules_b, rules_a = css_rules(text_b), css_rules(text_a)
        if rules_b != rules_a:
            show_changed_lines(f'planned change, CSS rules, {label}', rules_b, rules_a)
            return
    lines_b, lines_a = text_b.splitlines(), text_a.splitlines()
    if lines_b == lines_a:
        # The bytes differ and no line does: line ends, or the last line's.
        print(f'  planned change, {label}: only line ends differ ({len(data_b)} → {len(data_a)} bytes)')
        return
    show_changed_lines(f'planned change, {label}', lines_b, lines_a)


def compare(before: Path, after: Path, without=(), changed_assets=(), renamed=(), new_assets=(), replace=()) -> bool:
    """Print what differs between two build folders; return True if nothing does."""
    changed = [name.encode() for name in changed_assets]
    renamed = [(old.encode(), new.encode()) for old, new in renamed]
    new_assets = [name.encode() for name in new_assets]
    replace = [(old.encode(), new.encode()) for old, new in replace]
    for old, new in replace:
        if old == new:
            raise CheckError(f'--replace {old.decode()}: the new text is the same as the old')
    shared = {plain: plain + b'#changed' for plain in changed}
    pair_keys = {(old, new): old + b'>' + new + b'#renamed' for old, new in renamed}
    b = Build(before, {**shared, **{old: k for (old, _), k in pair_keys.items()}})
    a = Build(after, {**shared, **{new: k for (_, new), k in pair_keys.items()}})
    planned_pairs = resolve_planned(b, a, changed)
    renamed_pairs = resolve_renamed(b, a, renamed)
    new_files = resolve_new(b, a, new_assets)
    for old, _ in replace:
        if not any(old in (before / f).read_bytes() for f in sorted(b.files) if f.suffix == '.html'):
            raise CheckError(f'--replace {old.decode()}: not in any page of {before}')

    common = b.files & a.files
    pages = sorted(f for f in common if f.suffix == '.html')
    cut = Counter()
    # A page only one build has is reported as before, but a named element left open in it is
    # still the error it is anywhere else.
    for build_, root in ((b, before), (a, after)):
        other = a if build_ is b else b
        for f in sorted(build_.files - other.files) if without else ():
            if f.suffix == '.html':
                strip_elements(build_.read(f).decode('utf-8', 'surrogateescape'), without, str(root / f), cut)
    prepared = {}
    if without or replace:
        for f in pages:
            page_b, page_a = b.read(f), a.read(f)
            # Before's pages only: the after build must hold the new text by itself.
            for old, new in replace:
                page_b = page_b.replace(old, new)
            if without:
                page_b = strip_elements(page_b.decode('utf-8', 'surrogateescape'), without, str(before / f), cut).encode('utf-8', 'surrogateescape')
                page_a = strip_elements(page_a.decode('utf-8', 'surrogateescape'), without, str(after / f), cut).encode('utf-8', 'surrogateescape')
            prepared[f] = (page_b, page_a)
    for spec in without:
        if without_spec(spec)[1] and not cut[spec]:
            raise CheckError(f'--without {spec}: no such element in either build')
    if without:
        print(f'  without: {", ".join(f"<{t}>" for t in without)}')
    for old, new in replace:
        print(f'  replaced in the before pages: {old.decode()} → {new.decode()}')

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

    report('only before', b.files - a.files)
    report('only after', a.files - b.files)
    report('other files changed', [f for f in common if f.suffix != '.html' and differs(f)])

    new_names = {name for name, _ in new_files}
    gone, new = b.unmatched(a), [n for n in a.unmatched(b) if n not in new_names]
    report('assets changed or removed (before)', [n.decode() for n in gone])
    report('assets changed or added (after)', [n.decode() for n in new])
    count_b, count_a = (Counter(map(plain_name, x.keys.values())) for x in (b, a))
    for name in gone:  # a stylesheet with one counterpart: show which rules changed
        plain = plain_name(b.keys[name])
        if plain.endswith(b'.css') and count_b[plain] == 1 and count_a[plain] == 1:
            counterpart = next(n for n in new if plain_name(a.keys[n]) == plain)
            show_diff(f'CSS rules, {plain.decode()}', b.rules(name), a.rules(counterpart))
    for plain, data_b, data_a in planned_pairs:
        show_planned_diff(plain, data_b, data_a)
    for label, data_b, data_a in renamed_pairs:
        if data_b == data_a:
            print(f'  renamed, {label.decode()}: same content')
        else:
            show_planned_diff(label, data_b, data_a)
    for name, data in new_files:
        show_new_asset(name, data)

    changed, elsewhere, diffs = {part: [] for part in PARTS}, [], {}
    for f in pages:
        page_b, page_a = prepared[f] if f in prepared else (b.read(f), a.read(f))
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


def option_value(name: str, values: list):
    """The planned-change option's values as given, or None when they aren't valid."""
    if name == '--without':
        return values[0] if WITHOUT.fullmatch(values[0]) else None
    if name == '--replace':
        return tuple(values) if values[0] else None
    if any(not v or v.startswith('-') for v in values):  # an asset's name
        return None
    return tuple(values) if len(values) > 1 else values[0]


def run(argv) -> int:
    command, args = (argv[0], argv[1:]) if argv else (None, [])
    release, folders = False, []
    planned = {name: [] for name in PLANNED}
    usage = command not in ('before', 'after', 'compare')
    i = 0
    while not usage and i < len(args):
        arg = args[i]
        name, eq, inline = arg.partition('=')
        if arg == '--release' and command == 'after':
            release = True
        elif name in PLANNED and command in ('after', 'compare'):
            count = PLANNED[name]
            if eq and count == 1:
                values = [inline]
            elif eq:  # two values are given apart, not as --option=value
                values = None
            else:
                values = args[i + 1:i + 1 + count]
                i += count
            value = option_value(name, values) if values and len(values) == count else None
            if value is None:
                usage = True
            else:
                planned[name].append(value)
        elif arg.startswith('-'):
            usage = True
        else:
            folders.append(arg)
        i += 1
    if usage or (command == 'compare' and len(folders) != 2):
        print(__doc__)
        return 2
    options = {
        # The tag in lower case, a class word as written.
        'without': ['.'.join(filter(None, without_spec(v))) for v in planned['--without']],
        'changed_assets': planned['--changed-asset'],
        'renamed': planned['--renamed-asset'],
        'new_assets': planned['--new-asset'],
        'replace': planned['--replace'],
    }
    options = {k: list(dict.fromkeys(v)) for k, v in options.items()}
    if command == 'compare':
        return 0 if compare(Path(folders[0]), Path(folders[1]), **options) else 1

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
            ok = compare(snapshot, dist, **options) and ok
    return 0 if ok else 1


def main(argv) -> int:
    try:
        return run(argv)
    except (CheckError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
