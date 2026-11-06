"""Check that a change to site-kit leaves the sites' built pages as they were.

  python3 -I scripts/check_sites.py before <site folder>...      build each site, keep a copy
  python3 -I scripts/check_sites.py after <site folder>...       build again, compare with the copy
  python3 -I scripts/check_sites.py compare <build A> <build B>  compare two build folders

"before" and "after" run `npm run build` in each site folder; "before" keeps a copy of its dist/
in a folder under the system's temporary directory (printed). The comparison reports:
- files that exist on one side only;
- other files outside _astro/ (robots.txt, sitemaps, scripts) whose bytes changed;
- the CSS rules and scripts in _astro/ that were added or removed (file names carry hashes, so
  their contents are compared);
- for every HTML page: the <head> tags as a set (order ignored), the header and skip link, and the
  rest of the page;
- a side-by-side diff of the first page whose header changed.
Asset hashes and Astro's scope ids are ignored. Exit status: 0 when nothing differs, 1 when
something does, 2 on a usage or build error. The header's look is checked in a browser instead
(scripts/measure-header.js).
"""
import difflib
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

SNAPSHOTS = Path(tempfile.gettempdir()) / 'site-kit-check'


def norm(s: str) -> str:
    s = re.sub(r'/_astro/[^"\'\s)]+', '/_astro/ASSET', s)
    s = re.sub(r'astro-[a-z0-9]{8}-\d+', 'astro-SCOPE', s)
    s = re.sub(r' data-astro-cid-[a-z0-9]+(="[^"]*")?', '', s)
    return s


class HeadTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.in_head, self.cur = [], False, None

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        elif self.in_head:
            self.cur = [f'<{tag} ' + ' '.join(f'{k}="{v}"' for k, v in sorted(attrs)) + '>', '']
            self.tags.append(self.cur)

    def handle_data(self, data):
        if self.in_head and self.cur and self.cur[0].startswith(('<title', '<script', '<style', '<noscript')):
            self.cur[1] += data

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


def head_tags(html: str) -> Counter:
    p = HeadTags()
    p.feed(html)
    return Counter(norm(t + (f' «{d.strip()}»' if d.strip() else '')) for t, d in p.tags)


SKIP = re.compile(r'<a\b[^>]*href="#main"[^>]*>.*?</a>', re.S)
HEADER = re.compile(r'<header\b.*?</header>', re.S)


def split_body(html: str):
    body = html.split('</head>', 1)[-1]
    skip, header = SKIP.search(body), HEADER.search(body)
    top = norm(((skip.group(0) if skip else '') + (header.group(0) if header else '')))
    rest = HEADER.sub('<HEADER/>', SKIP.sub('', body, count=1), count=1)
    return norm(re.sub(r'>\s*<', '>\n<', top)), norm(re.sub(r'\s+', ' ', rest))


def assets(root: Path):
    css, js = Counter(), Counter()
    for f in (root / '_astro').glob('**/*'):
        if f.suffix == '.css':
            css.update(r.strip() for r in re.split(r'(?<=\})', f.read_text()) if r.strip())
        elif f.suffix in ('.js', '.mjs'):
            js[norm(f.read_text())] += 1
    return css, js


def compare(before: Path, after: Path) -> bool:
    """Print what differs between two build folders; return True if nothing does."""
    files = lambda root: {p.relative_to(root) for p in root.rglob('*') if p.is_file() and p.parts[len(root.parts)] != '_astro'}
    fb, fa = files(before), files(after)
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

    report('only before', fb - fa)
    report('only after', fa - fb)
    report('other files changed', [f for f in fb & fa if f.suffix != '.html' and (before / f).read_bytes() != (after / f).read_bytes()])

    css_b, js_b = assets(before)
    css_a, js_a = assets(after)
    report('CSS rules removed', (css_b - css_a).elements())
    report('CSS rules added', (css_a - css_b).elements())
    if js_b != js_a:
        report('scripts changed', [f'{sum((js_b - js_a).values())} removed, {sum((js_a - js_b).values())} added'])

    pages = sorted(f for f in fb & fa if f.suffix == '.html')
    head_diff, header_diff, body_diff = [], [], []
    for f in pages:
        hb, ha = (before / f).read_text(), (after / f).read_text()
        if head_tags(hb) != head_tags(ha):
            head_diff.append(f)
        (tb, rb), (ta, ra) = split_body(hb), split_body(ha)
        if tb != ta:
            header_diff.append((f, tb, ta))
        if rb != ra:
            body_diff.append(f)
    print(f'  HTML pages compared: {len(pages)}')
    report('pages whose <head> tags changed', head_diff)
    report('pages whose header or skip link changed', [f for f, _, _ in header_diff])
    report('pages whose content (outside the header) changed', body_diff)
    if header_diff:
        f, tb, ta = header_diff[0]
        print(f'  header diff, {f}:')
        for line in difflib.unified_diff(tb.splitlines(), ta.splitlines(), 'before', 'after', lineterm='', n=1):
            print(f'    {line[:200]}')
    print('  identical' if same else '  DIFFERENT')
    return same


def build(site: Path):
    print(f'building {site.name} …')
    run = subprocess.run(['npm', 'run', 'build'], cwd=site, capture_output=True, text=True)
    if run.returncode != 0:
        print(run.stdout[-3000:], run.stderr[-3000:], sep='\n')
        sys.exit(f'build failed in {site}')


def main(argv):
    if len(argv) < 2 or argv[0] not in ('before', 'after', 'compare'):
        print(__doc__)
        return 2
    if argv[0] == 'compare':
        if len(argv) != 3:
            print(__doc__)
            return 2
        return 0 if compare(Path(argv[1]), Path(argv[2])) else 1
    sites = [Path(a).resolve() for a in argv[1:]]
    for site in sites:
        if not (site / 'package.json').is_file():
            sys.exit(f'not a site folder: {site}')
    ok = True
    for site in sites:
        build(site)
        snapshot = SNAPSHOTS / site.name
        if argv[0] == 'before':
            shutil.rmtree(snapshot, ignore_errors=True)
            shutil.copytree(site / 'dist', snapshot)
            print(f'  kept a copy in {snapshot}')
        else:
            if not snapshot.is_dir():
                sys.exit(f'no "before" copy for {site.name}: run "before" first')
            print(f'{site.name}: before → after')
            ok = compare(snapshot, site / 'dist') and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
