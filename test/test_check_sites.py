"""Tests for scripts/check_sites.py. Run with `npm test`.

Most run the script as a command and assert its exit status and the line that names the cause.
Every build, site and hash here is made up; each test has its own temporary folder, which is also
the script's TMPDIR, so no two tests share a "before" copy.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_sites.py'

CSS = 'a{color:red}b{color:blue}'
JS = 'document.title=`x`;'
PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Home</title>'
    '<link rel="stylesheet" href="/_astro/Base.CIX-Jlc-.css">'
    '<script type="module" src="/_astro/nav.sfTAO5_a.js"></script></head>'
    '<body><a href="#main" class="kit-skip">Skip to content</a>'
    '<header class="kit-header" data-astro-cid-abc123><a href="/">site-a</a></header>'
    '<main id="main"><h1>Home</h1><pre>a  b</pre></main></body></html>'
)
BUILD = {'index.html': PAGE, '_astro/Base.CIX-Jlc-.css': CSS, '_astro/nav.sfTAO5_a.js': JS}

TAG = 'github:someone/site-kit#v1.0.0'
LINK = 'file:../kit'
# What a made-up site's `npm run build` does.
COPIES = '''node -e "require('fs').cpSync('out','dist',{recursive:true})"'''
NOTHING = 'node -e ""'
FAILS = 'node -e "process.exit(3)"'
NO_PAGE = '''node -e "require('fs').mkdirSync('dist',{recursive:true});require('fs').writeFileSync('dist/robots.txt','')"'''


def write(root: Path, files: dict):
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(content if isinstance(content, bytes) else content.encode())


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.snapshots = self.tmp / 'tmp' / 'site-kit-check'
        (self.tmp / 'tmp').mkdir()

    def run_script(self, script, *args):
        run = subprocess.run([sys.executable, '-I', '-B', str(script), *map(str, args)], capture_output=True,
                             text=True, env={**os.environ, 'TMPDIR': str(self.tmp / 'tmp')})
        return run.returncode, run.stdout + run.stderr

    def assertLine(self, out, *fragments):
        """One line of the output holds every fragment."""
        if not any(all(str(f) in line for f in fragments) for line in out.splitlines()):
            self.fail(f'no line with {fragments} in:\n{out}')

    def swap(self, text, old, new):
        self.assertIn(old, text)
        return text.replace(old, new)


class Compare(Case):
    """`compare` on two made-up build folders."""

    def compare(self, before: dict, after: dict):
        write(self.tmp / 'before', before)
        write(self.tmp / 'after', after)
        return self.run_script(SCRIPT, 'compare', self.tmp / 'before', self.tmp / 'after')

    def assertDifferent(self, before, after, *line):
        status, out = self.compare(before, after)
        self.assertEqual(status, 1, out)
        self.assertLine(out, *line)

    def test_identical_builds_pass(self):
        status, out = self.compare(BUILD, BUILD)
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'HTML pages compared: 1')

    # Criterion 1: nothing to compare is an error.

    def test_missing_folder_is_an_error(self):
        for missing in ('before', 'after'):
            with self.subTest(missing=missing):
                write(self.tmp / 'present', BUILD)
                folders = [self.tmp / 'present', self.tmp / 'present']
                folders[missing == 'after'] = self.tmp / 'nowhere'
                status, out = self.run_script(SCRIPT, 'compare', *folders)
                self.assertEqual(status, 2, out)
                self.assertLine(out, 'no build folder', self.tmp / 'nowhere')

    def test_folder_without_a_page_is_an_error(self):
        for empty in ('before', 'after'):
            with self.subTest(empty=empty):
                write(self.tmp / 'present', BUILD)
                write(self.tmp / 'pageless', {'robots.txt': '', '_astro/Base.CIX-Jlc-.css': CSS})
                folders = [self.tmp / 'present', self.tmp / 'present']
                folders[empty == 'after'] = self.tmp / 'pageless'
                status, out = self.run_script(SCRIPT, 'compare', *folders)
                self.assertEqual(status, 2, out)
                self.assertLine(out, 'no HTML page', self.tmp / 'pageless')

    def test_two_empty_folders_are_an_error(self):
        (self.tmp / 'a').mkdir()
        (self.tmp / 'b').mkdir()
        status, out = self.run_script(SCRIPT, 'compare', self.tmp / 'a', self.tmp / 'b')
        self.assertEqual(status, 2, out)
        self.assertLine(out, 'no HTML page', self.tmp / 'a')

    # Criterion 2: pages compare exactly.

    def changed_page(self, old, new, *line):
        self.assertDifferent(BUILD, {**BUILD, 'index.html': self.swap(PAGE, old, new)}, *line)

    def test_two_head_tags_swapped(self):
        charset, title = '<meta charset="utf-8">', '<title>Home</title>'
        self.changed_page(charset + title, title + charset, 'pages whose <head> tags changed (1)')

    def test_html_lang_changed(self):
        self.changed_page('<html lang="en">', '<html lang="es">', 'pages whose doctype or <html> tag changed (1)')

    def test_spacing_in_head_changed(self):
        self.changed_page('<title>Home</title>', '<title>Home</title>\n', 'pages that changed elsewhere', '(1)')

    def test_spaces_in_pre_changed(self):
        self.changed_page('<pre>a  b</pre>', '<pre>a b</pre>', 'pages whose content (outside the header) changed (1)')

    def test_scope_attribute_removed(self):
        self.changed_page(' data-astro-cid-abc123', '', 'pages whose header or skip link changed (1)')

    # Criterion 3: asset identity counts.

    def test_page_links_another_file_of_the_same_stem(self):
        both = {**BUILD, '_astro/Base.Ab12Cd34.css': 'a{color:green}'}
        page = self.swap(PAGE, 'Base.CIX-Jlc-.css', 'Base.Ab12Cd34.css')
        self.assertDifferent(both, {**both, 'index.html': page}, 'pages whose <head> tags changed (1)')

    def entry_and_chunks(self, entry, chunk, prefix):
        return {
            'index.html': self.swap(PAGE, 'nav.sfTAO5_a.js', entry), '_astro/Base.CIX-Jlc-.css': CSS,
            f'_astro/{entry}': f'import"{prefix}{chunk}";go()',
            '_astro/chunk.Ab12_d34.js': 'export const n=1', '_astro/chunk.Zy98-w76.js': 'export const n=2',
        }

    def test_entry_script_imports_another_chunk(self):
        before = self.entry_and_chunks('entry.Ck-SW8bZ.js', 'chunk.Ab12_d34.js', '/_astro/')
        after = self.entry_and_chunks('entry.EGAeWXJ0.js', 'chunk.Zy98-w76.js', '/_astro/')
        self.assertDifferent(before, after, 'entry.Ck-SW8bZ.js')

    def test_entry_script_imports_another_chunk_by_relative_path(self):
        before = self.entry_and_chunks('entry.Ck-SW8bZ.js', 'chunk.Ab12_d34.js', './')
        after = self.entry_and_chunks('entry.EGAeWXJ0.js', 'chunk.Zy98-w76.js', './')
        self.assertDifferent(before, after, 'entry.Ck-SW8bZ.js')

    def test_changed_binary_asset(self):
        before = {**BUILD, '_astro/f.Ab12-d34.woff2': b'\x00\x01\xff\xfe'}
        after = {**BUILD, '_astro/f.Ab12-d34.woff2': b'\x00\x02\xff\xfe'}
        self.assertDifferent(before, after, 'f.Ab12-d34.woff2')

    def test_two_css_rules_swapped(self):
        after = {**BUILD, '_astro/Base.CIX-Jlc-.css': 'b{color:blue}a{color:red}'}
        self.assertDifferent(BUILD, after, 'CSS rules, Base.css')

    def test_renamed_assets_with_the_same_content_pass(self):
        page = self.swap(self.swap(PAGE, 'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css'), 'nav.sfTAO5_a.js', 'nav.Ab12_d34.js')
        after = {'index.html': page, '_astro/Base.Zy98-w76.css': CSS, '_astro/nav.Ab12_d34.js': JS}
        status, out = self.compare(BUILD, after)
        self.assertEqual(status, 0, out)

    def test_renamed_chain_with_the_same_content_passes(self):
        def build(css, font, entry, chunk):
            page = self.swap(self.swap(PAGE, 'Base.CIX-Jlc-.css', css), 'nav.sfTAO5_a.js', entry)
            return {'index.html': page, 'robots.txt': f'Allow: /_astro/{css}\n',
                    f'_astro/{css}': f'@font-face{{src:url({font})}}', f'_astro/{font}': b'\x00\xff font',
                    f'_astro/{entry}': f'import"./{chunk}";go()', f'_astro/{chunk}': 'export const n=1'}
        before = build('Base.CIX-Jlc-.css', 'f.Ab12-d34.woff2', 'entry.Ck-SW8bZ.js', 'chunk.Ab12_d34.js')
        after = build('Base.sfTAO5_a.css', 'f.Zy98_w76.woff2', 'entry.EGAeWXJ0.js', 'chunk.Zy98-w76.js')
        status, out = self.compare(before, after)
        self.assertEqual(status, 0, out)

    def test_cycle_of_references_is_an_error(self):
        cycle = {**BUILD, '_astro/a.Ab12Cd34.js': 'import"./b.Zy98-w76.js"', '_astro/b.Zy98-w76.js': 'import"./a.Ab12Cd34.js"'}
        status, out = self.compare(cycle, cycle)
        self.assertEqual(status, 2, out)
        self.assertLine(out, 'cycle', 'a.Ab12Cd34.js', 'b.Zy98-w76.js')

    # Planned changes: --without and --changed-asset.

    def compare_with(self, before: dict, after: dict, *opts):
        for name, files in (('before', before), ('after', after)):
            folder = self.tmp / name
            if folder.exists():
                shutil.rmtree(folder)
            write(folder, files)
        return self.run_script(SCRIPT, 'compare', *opts, self.tmp / 'before', self.tmp / 'after')

    def with_footer(self, footer: str, page: str = PAGE) -> str:
        return self.swap(page, '</body>', f'{footer}</body>')

    def test_without_cuts_a_footer_changed_on_every_page(self):
        about = self.swap(PAGE, '<h1>Home</h1>', '<h1>About</h1>')
        before = {**BUILD, 'index.html': self.with_footer('<footer>old</footer>'), 'about/index.html': about}
        after = {
            **BUILD,
            'index.html': self.with_footer('<footer class="kit-footer">new</footer>'),
            'about/index.html': self.with_footer('<footer class="kit-footer">added</footer>', about),
        }
        status, out = self.compare(before, after)
        self.assertEqual(status, 1, out)
        self.assertLine(out, 'pages whose content (outside the header) changed (2)')

        status, out = self.compare_with(before, after, '--without', 'footer')
        self.assertEqual(status, 0, out)
        self.assertIn('without', out.splitlines()[0])
        self.assertIn('<footer>', out.splitlines()[0])
        self.assertLine(out, 'HTML pages compared: 2')
        self.assertLine(out, 'identical')

    def test_without_still_reports_a_changed_header(self):
        before = {**BUILD, 'index.html': self.with_footer('<footer>old</footer>')}
        after_page = self.swap(self.with_footer('<footer>new</footer>'), '>site-a<', '>site-b<')
        after = {**BUILD, 'index.html': after_page}
        status, out = self.compare_with(before, after, '--without', 'footer')
        self.assertEqual(status, 1, out)
        self.assertIn('<footer>', out.splitlines()[0])
        self.assertLine(out, 'pages whose header or skip link changed (1)')
        self.assertLine(out, 'header diff, index.html')
        self.assertNotIn('content (outside the header)', out)

    def test_without_repeatable_cuts_several_tags(self):
        before = {**BUILD, 'index.html': self.with_footer('<aside>old</aside><footer>old</footer>')}
        after = {**BUILD, 'index.html': self.with_footer('<aside>new</aside><footer>new</footer>')}
        status, out = self.compare_with(before, after, '--without', 'footer', '--without', 'aside')
        self.assertEqual(status, 0, out)
        self.assertIn('<footer>', out.splitlines()[0])
        self.assertIn('<aside>', out.splitlines()[0])

    def test_without_cuts_nested_elements_of_the_same_tag(self):
        before = {**BUILD, 'index.html': self.with_footer('<footer>outer<footer>inner</footer>still outer</footer>')}
        after = {**BUILD, 'index.html': self.with_footer('<footer>replacement</footer>')}
        status, out = self.compare_with(before, after, '--without', 'footer')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'identical')

    def test_without_keeps_near_misses(self):
        for label, old, new in [
            ('hyphenated tag', '<footer-note>old</footer-note>', '<footer-note>new</footer-note>'),
            ('word in text', '<p>footer old</p>', '<p>footer new</p>'),
            ('end tag in script', '<script>const s = "</footer> old";</script>', '<script>const s = "</footer> new";</script>'),
            ('end tag in comment', '<!-- </footer> old -->', '<!-- </footer> new -->'),
        ]:
            with self.subTest(case=label):
                before = {**BUILD, 'index.html': self.with_footer(old)}
                after = {**BUILD, 'index.html': self.with_footer(new)}
                status, out = self.compare_with(before, after, '--without', 'footer')
                self.assertEqual(status, 1, out)
                self.assertLine(out, 'pages whose content (outside the header) changed (1)')

        # A </footer> inside a <script> string or comment inside a real <footer> must not close it early.
        tricky = '<footer>a<script>const s = "</footer>";</script><!-- </footer> -->tail</footer>'
        before = {**BUILD, 'index.html': self.with_footer(tricky)}
        after = {**BUILD, 'index.html': self.with_footer('<footer>plain</footer>')}
        status, out = self.compare_with(before, after, '--without', 'footer')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'identical')

    def test_without_unclosed_element_is_an_error(self):
        for label, before_html, after_html in [
            ('unclosed in before', self.with_footer('<footer>open'), PAGE),
            ('unclosed in after', PAGE, self.with_footer('<footer>open')),
            ('unclosed outer nested', PAGE, self.with_footer('<footer>outer<footer>inner</footer>')),
        ]:
            with self.subTest(case=label):
                status, out = self.compare_with(
                    {**BUILD, 'index.html': before_html},
                    {**BUILD, 'index.html': after_html},
                    '--without', 'footer',
                )
                self.assertEqual(status, 2, out)
                self.assertLine(out, 'unclosed', '<footer>')
                self.assertNotIn('identical', out)

    def test_without_reads_textarea_and_title_content_as_text(self):
        # A "<footer>" typed into a textarea or a title is text on every Python version.
        page = self.with_footer('<textarea><footer> typed </textarea><footer>old</footer>')
        page = self.swap(page, '<title>', '<title><footer> ')
        changed = self.swap(page, '<footer>old</footer>', '<footer>new</footer>')
        status, out = self.compare_with({**BUILD, 'index.html': page}, {**BUILD, 'index.html': changed}, '--without', 'footer')
        self.assertEqual(status, 0, out)
        kept = self.swap(page, '<footer> typed', '<footer> retyped')
        status, out = self.compare_with({**BUILD, 'index.html': page}, {**BUILD, 'index.html': kept}, '--without', 'footer')
        self.assertEqual(status, 1, out)
        # A script typed into a textarea does not hide the textarea's end from what follows it.
        scripted = self.with_footer('<textarea><script>x</textarea><footer>old</footer>')
        status, out = self.compare_with({**BUILD, 'index.html': scripted},
                                        {**BUILD, 'index.html': self.swap(scripted, '>old<', '>new<')}, '--without', 'footer')
        self.assertEqual(status, 0, out)

    def test_without_title_or_textarea_themselves(self):
        page = self.with_footer('<textarea>one</textarea>')
        for tag, old, new in (('title', '<title>', '<title>New '), ('textarea', '<textarea>one', '<textarea>two')):
            with self.subTest(tag=tag):
                changed = self.swap(page, old, new)
                status, out = self.compare_with({**BUILD, 'index.html': page}, {**BUILD, 'index.html': changed})
                self.assertEqual(status, 1, out)
                status, out = self.compare_with({**BUILD, 'index.html': page}, {**BUILD, 'index.html': changed}, '--without', tag)
                self.assertEqual(status, 0, out)

    def test_without_unclosed_element_on_a_page_only_one_build_has(self):
        for side in ('before', 'after'):
            with self.subTest(side=side):
                extra = {**BUILD, 'only.html': self.with_footer('<footer>open')}
                builds = (extra, BUILD) if side == 'before' else (BUILD, extra)
                status, out = self.compare_with(*builds, '--without', 'footer')
                self.assertEqual(status, 2, out)
                self.assertLine(out, 'unclosed', '<footer>', 'only.html')
        # A well-formed page only one build has is still reported as an addition.
        status, out = self.compare_with(BUILD, {**BUILD, 'only.html': self.with_footer('<footer>fine</footer>')}, '--without', 'footer')
        self.assertEqual(status, 1, out)
        self.assertLine(out, 'only after')

    def test_changed_asset_shows_a_change_far_into_a_long_rule_and_line_ends(self):
        long_rule = 'a{' + ';'.join(f'--v{n}:{n}px' for n in range(60)) + ';color:blue}'
        def build(css_name, css):
            build = {**BUILD, 'index.html': self.swap(PAGE, 'Base.CIX-Jlc-.css', css_name), f'_astro/{css_name}': css}
            if css_name != 'Base.CIX-Jlc-.css':
                del build['_astro/Base.CIX-Jlc-.css']
            return build
        before = build('Base.CIX-Jlc-.css', long_rule)
        status, out = self.compare_with(before, build('Base.Zy98-w76.css', long_rule.replace('color:blue', 'color:green')),
                                        '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertGreater(long_rule.index('color:blue'), 200)
        self.assertLine(out, '-…', 'color:blue}')
        self.assertLine(out, '+…', 'color:green}')
        # A rule removed just before the edited one: the edited rule is still paired with itself.
        status, out = self.compare_with(build('Base.CIX-Jlc-.css', 'p{margin:0}' + long_rule),
                                        build('Base.Zy98-w76.css', long_rule.replace('color:blue', 'color:green')),
                                        '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertLine(out, '-p{margin:0}')
        self.assertLine(out, '-…', 'color:blue}')
        self.assertLine(out, '+…', 'color:green}')
        # A change in line ends alone is said, not shown as an empty diff.
        two = 'a{color:red}\nb{color:blue}\n'
        status, out = self.compare_with(build('Base.CIX-Jlc-.css', two), build('Base.Zy98-w76.css', two.replace('\n', '\r\n')),
                                        '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'planned change', 'Base.css', 'only line ends differ')

    def test_changed_asset_alone_passes_and_prints_bounded_diff(self):
        after = {
            **BUILD,
            'index.html': self.swap(PAGE, 'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css'),
            '_astro/Base.Zy98-w76.css': 'a{color:red}b{color:green}',
        }
        del after['_astro/Base.CIX-Jlc-.css']
        status, out = self.compare(BUILD, after)
        self.assertEqual(status, 1, out)

        status, out = self.compare_with(BUILD, after, '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'planned change', 'Base.css')
        self.assertLine(out, '-b{color:blue}')
        self.assertLine(out, '+b{color:green}')
        self.assertLine(out, 'identical')

        # Repeatable --changed-asset allows two planned assets together.
        before_two = {**BUILD, '_astro/Extra.Ab12Cd34.css': 'p{margin:0}'}
        after_two = {**after, '_astro/Extra.Zy98-w76.css': 'p{margin:1rem}'}
        status, out = self.compare_with(before_two, after_two, '--changed-asset', 'Base.css', '--changed-asset', 'Extra.css')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'planned change', 'Base.css')
        self.assertLine(out, 'planned change', 'Extra.css')

        # A long diff is bounded in length.
        many_before = {**BUILD, '_astro/Base.CIX-Jlc-.css': ''.join(f'.c{i}{{color:red}}' for i in range(50))}
        many_after = {**after, '_astro/Base.Zy98-w76.css': ''.join(f'.c{i}{{color:blue}}' for i in range(50))}
        status, out = self.compare_with(many_before, many_after, '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertLine(out, '-.c0{color:red}')
        self.assertLine(out, 'more lines')
        self.assertNotIn('.c49{color:blue}', out)

    def test_changed_asset_still_reports_another_changed_asset(self):
        after = {
            'index.html': self.swap(
                self.swap(PAGE, 'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css'),
                'nav.sfTAO5_a.js', 'nav.Ab12_d34.js',
            ),
            '_astro/Base.Zy98-w76.css': 'a{color:red}b{color:green}',
            '_astro/nav.Ab12_d34.js': 'document.title=`y`;',
        }
        status, out = self.compare_with(BUILD, after, '--changed-asset', 'Base.css')
        self.assertEqual(status, 1, out)
        self.assertLine(out, 'nav.sfTAO5_a.js')
        self.assertLine(out, 'planned change', 'Base.css')
        self.assertLine(out, 'DIFFERENT')

    def test_changed_asset_transitive_dependent_counts_as_same(self):
        def make(entry, chunk, chunk_body):
            return {
                'index.html': self.swap(PAGE, 'nav.sfTAO5_a.js', entry),
                '_astro/Base.CIX-Jlc-.css': CSS,
                f'_astro/{entry}': f'import"./{chunk}";go()',
                f'_astro/{chunk}': chunk_body,
            }
        before = make('entry.Ck-SW8bZ.js', 'chunk.Ab12_d34.js', 'export const n=1')
        after = make('entry.EGAeWXJ0.js', 'chunk.Zy98-w76.js', 'export const n=2')
        status, out = self.compare_with(before, after, '--changed-asset', 'chunk.js')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'planned change', 'chunk.js')
        self.assertLine(out, 'identical')

    def test_changed_asset_wrong_name_or_unchanged_is_an_error(self):
        renamed_same = {
            'index.html': self.swap(PAGE, 'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css'),
            '_astro/Base.Zy98-w76.css': CSS,
            '_astro/nav.sfTAO5_a.js': JS,
        }
        for label, before, after, name, fragment in [
            ('not in either build', BUILD, BUILD, 'Missing.css', 'not in either build'),
            ('missing in after', {**BUILD, '_astro/Extra.Ab12Cd34.css': CSS}, BUILD, 'Extra.css', 'not in'),
            ('missing in before', BUILD, {**BUILD, '_astro/Extra.Ab12Cd34.css': CSS}, 'Extra.css', 'not in'),
            ('identical content', BUILD, BUILD, 'Base.css', 'did not differ'),
            ('renamed with same content', BUILD, renamed_same, 'Base.css', 'did not differ'),
            ('ambiguous plain name', {**BUILD, '_astro/Base.Zy98-w76.css': 'a{}'}, BUILD, 'Base.css', 'more than one'),
        ]:
            with self.subTest(case=label):
                status, out = self.compare_with(before, after, '--changed-asset', name)
                self.assertEqual(status, 2, out)
                self.assertLine(out, name, fragment)

    def test_without_and_changed_asset_together(self):
        before = {**BUILD, 'index.html': self.with_footer('<footer>old</footer>')}
        after_base = {
            **BUILD,
            'index.html': self.swap(self.with_footer('<footer>new</footer>'), 'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css'),
            '_astro/Base.Zy98-w76.css': 'a{color:red}b{color:green}',
        }
        del after_base['_astro/Base.CIX-Jlc-.css']

        status, out = self.compare_with(before, after_base, '--without', 'footer', '--changed-asset', 'Base.css')
        self.assertEqual(status, 0, out)
        self.assertIn('<footer>', out.splitlines()[0])
        self.assertLine(out, 'planned change', 'Base.css')
        self.assertLine(out, 'identical')

        for label, old, new, part in [
            ('head', '<title>Home</title>', '<title>Away</title>', 'pages whose <head> tags changed (1)'),
            ('header', '>site-a<', '>site-b<', 'pages whose header or skip link changed (1)'),
            ('body', '<h1>Home</h1>', '<h1>Away</h1>', 'pages whose content (outside the header) changed (1)'),
            ('elsewhere', '<title>Home</title>', '<title>Home</title>\n', 'pages that changed elsewhere'),
        ]:
            with self.subTest(part=label):
                after = {**after_base, 'index.html': self.swap(after_base['index.html'], old, new)}
                status, out = self.compare_with(before, after, '--without', 'footer', '--changed-asset', 'Base.css')
                self.assertEqual(status, 1, out)
                self.assertIn('<footer>', out.splitlines()[0])
                self.assertLine(out, part)
                self.assertLine(out, 'DIFFERENT')

    def test_option_usage_errors(self):
        write(self.tmp / 'a', BUILD)
        write(self.tmp / 'b', BUILD)
        for args in [
            ('before', '--without', 'footer'),
            ('before', '--changed-asset', 'Base.css'),
            ('compare', '--without', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--without', '<footer>', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--changed-asset', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--changed-asset', '--without', 'footer', self.tmp / 'a', self.tmp / 'b'),
            ('before', '--replace', 'a', 'b'),
            ('before', '--renamed-asset', 'a.js', 'b.js'),
            ('before', '--new-asset', 'a.js'),
            ('compare', '--without', 'div.', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--without', '.lane-row', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--without', 'div.a.b', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--without', 'div.a b', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--replace', '', 'x', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--replace=a', 'b', self.tmp / 'a', self.tmp / 'b'),
            ('compare', self.tmp / 'a', self.tmp / 'b', '--replace', 'a'),
            ('compare', '--renamed-asset', 'a.js', '--new-asset', 'b.js', self.tmp / 'a', self.tmp / 'b'),
            ('compare', '--renamed-asset=a.js', 'b.js', self.tmp / 'a', self.tmp / 'b'),
            ('compare', self.tmp / 'a', self.tmp / 'b', '--renamed-asset', 'a.js'),
            ('compare', '--new-asset', '--without', 'footer', self.tmp / 'a', self.tmp / 'b'),
        ]:
            with self.subTest(args=args):
                status, out = self.run_script(SCRIPT, *args)
                self.assertEqual(status, 2, out)
                self.assertLine(out, 'compare [<planned change>...] <build A> <build B>')


class PlannedChanges(Case):
    """--replace, --renamed-asset, --new-asset and --without <tag>.<class> on made-up build folders."""

    compare_with = Compare.compare_with

    def assertStatus(self, wanted, before, after, *opts, line=()):
        status, out = self.compare_with(before, after, *opts)
        self.assertEqual(status, wanted, out)
        if line:
            self.assertLine(out, *line)
        return out

    # --replace

    def named_page(self, name):
        return {**BUILD, 'index.html': self.swap(PAGE, '<h1>Home</h1>', f'<h1>Home</h1><p title="{name}">{name}</p>')}

    def test_replace_rewrites_the_before_pages(self):
        before, after = self.named_page('简体中文'), self.named_page('中文')
        self.assertStatus(1, before, after, line=('pages whose content (outside the header) changed (1)',))
        out = self.assertStatus(0, before, after, '--replace', '简体中文', '中文', line=('identical',))
        self.assertLine(out, 'replaced in the before pages', '简体中文 → 中文')

    def test_replace_fails_when_the_after_build_still_holds_the_old_text(self):
        before = self.named_page('简体中文')
        after = {**before, 'about/index.html': before['index.html']}
        before = {**before, 'about/index.html': self.named_page('中文')['index.html']}
        self.assertStatus(1, before, before, '--replace', '简体中文', '中文',
                          line=('pages whose content (outside the header) changed (1)',))
        self.assertStatus(1, before, after, '--replace', '简体中文', '中文', line=('DIFFERENT',))

    def test_replace_leaves_other_files_and_assets_alone(self):
        before, after = self.named_page('简体中文'), self.named_page('中文')
        self.assertStatus(1, {**before, 'sitemap.xml': '简体中文'}, {**after, 'sitemap.xml': '中文'},
                          '--replace', '简体中文', '中文', line=('other files changed (1)',))
        css_b, css_a = {**before, '_astro/Base.CIX-Jlc-.css': 'p{content:"简体中文"}'}, {**after, '_astro/Base.CIX-Jlc-.css': 'p{content:"中文"}'}
        self.assertStatus(1, css_b, css_a, '--replace', '简体中文', '中文', line=('assets changed or removed (before) (1)',))

    def test_replace_is_repeatable(self):
        before = self.named_page('one two')
        after = self.named_page('1 2')
        self.assertStatus(1, before, after, '--replace', 'one', '1')
        self.assertStatus(0, before, after, '--replace', 'one', '1', '--replace', 'two', '2')

    def test_replace_must_find_its_text_and_change_it(self):
        before, after = self.named_page('简体中文'), self.named_page('中文')
        for opts, fragment in [
            (('--replace', '繁體中文', '中文'), 'not in any page'),
            (('--replace', '中文', '中文'), 'the same as the old'),
        ]:
            with self.subTest(opts=opts):
                self.assertStatus(2, before, after, *opts, line=(opts[1], fragment))
        # Only the before build's pages count: the text in after alone, or in an asset, is not found.
        self.assertStatus(2, after, before, '--replace', '简体中文', '中文', line=('not in any page',))
        self.assertStatus(2, {**after, '_astro/nav.sfTAO5_a.js': '简体中文'}, after, '--replace', '简体中文', '中文',
                          line=('not in any page',))

    # --renamed-asset and --new-asset

    def scripted(self, src_name, src_body, extra=None):
        page = self.swap(PAGE, 'nav.sfTAO5_a.js', src_name)
        return {'index.html': page, '_astro/Base.CIX-Jlc-.css': CSS, f'_astro/{src_name}': src_body, **(extra or {})}

    def test_renamed_asset_pairs_the_two_names_and_prints_their_diff(self):
        before = self.scripted('Bar.astro_type_script.Ab12Cd34.js', 'measure();closeNotes();')
        after = self.scripted('Row.astro_type_script.Zy98Xw76.js', 'measure();closeMenus();')
        self.assertStatus(1, before, after, line=('assets changed or added (after) (1)',))
        out = self.assertStatus(0, before, after, '--renamed-asset', 'Bar.astro_type_script.js', 'Row.astro_type_script.js',
                                line=('identical',))
        self.assertLine(out, 'planned change', 'Bar.astro_type_script.js → Row.astro_type_script.js')
        self.assertLine(out, '+measure();closeMenus();')
        same = self.scripted('Row.astro_type_script.Zy98Xw76.js', 'measure();closeNotes();')
        self.assertStatus(0, before, same, '--renamed-asset', 'Bar.astro_type_script.js', 'Row.astro_type_script.js',
                          line=('renamed', 'same content'))
        # Another change is still reported.
        moved = {**after, 'index.html': self.swap(after['index.html'], '<h1>Home</h1>', '<h1>Away</h1>')}
        self.assertStatus(1, before, moved, '--renamed-asset', 'Bar.astro_type_script.js', 'Row.astro_type_script.js',
                          line=('pages whose content (outside the header) changed (1)',))

    def test_renamed_asset_must_find_each_name_once_on_its_side(self):
        before = self.scripted('Bar.Ab12Cd34.js', 'a()')
        after = self.scripted('Row.Zy98Xw76.js', 'b()')
        for label, b, a, old, new, fragment in [
            ('old not in before', before, after, 'Gone.js', 'Row.js', 'Gone.js: 0 assets'),
            ('old twice in before', {**before, '_astro/Bar.Qq11Ww22.js': 'c()'}, after, 'Bar.js', 'Row.js', 'Bar.js: 2 assets'),
            ('old still in after', before, {**after, '_astro/Bar.Qq11Ww22.js': 'c()'}, 'Bar.js', 'Row.js', 'Bar.js is also in'),
            ('new not in after', before, after, 'Bar.js', 'Gone.js', 'Gone.js: 0 assets'),
            ('new already in before', {**before, '_astro/Row.Qq11Ww22.js': 'c()'}, after, 'Bar.js', 'Row.js', 'Row.js is also in'),
            ('swapped', before, after, 'Row.js', 'Bar.js', 'Row.js: 0 assets'),
        ]:
            with self.subTest(case=label):
                self.assertStatus(2, b, a, '--renamed-asset', old, new, line=('renamed asset', fragment))

    def test_new_asset_is_allowed_and_printed(self):
        before = self.scripted('Bar.Ab12Cd34.js', 'a()')
        after = self.scripted('Row.Zy98Xw76.js', 'import"./menus.Mm12Nn34.js";a()', {'_astro/menus.Mm12Nn34.js': 'closeMenus()'})
        self.assertStatus(1, before, after, '--renamed-asset', 'Bar.js', 'Row.js', line=('assets changed or added (after) (1)',))
        out = self.assertStatus(0, before, after, '--renamed-asset', 'Bar.js', 'Row.js', '--new-asset', 'menus.js', line=('identical',))
        self.assertLine(out, 'new asset, menus.Mm12Nn34.js')
        self.assertLine(out, 'closeMenus()')
        # Only the asset named: a second new one is still reported.
        more = {**after, '_astro/other.Oo12Pp34.js': 'x()'}
        self.assertStatus(1, before, more, '--renamed-asset', 'Bar.js', 'Row.js', '--new-asset', 'menus.js',
                          line=('assets changed or added (after) (1)',))

    def test_new_asset_must_be_in_after_once_and_not_in_before(self):
        before = BUILD
        after = {**BUILD, '_astro/menus.Mm12Nn34.js': 'closeMenus()'}
        for label, b, a, fragment in [
            ('not in after', before, before, 'menus.js: 0 assets'),
            ('twice in after', before, {**after, '_astro/menus.Qq11Ww22.js': 'y()'}, 'menus.js: 2 assets'),
            ('already in before', {**before, '_astro/menus.Qq11Ww22.js': 'y()'}, after, 'menus.js is also in'),
        ]:
            with self.subTest(case=label):
                self.assertStatus(2, b, a, '--new-asset', 'menus.js', line=('new asset', fragment))

    # --without <tag>.<class>

    def rowed(self, row):
        return {**BUILD, 'index.html': self.swap(PAGE, '</header>', f'</header>{row}')}

    def test_without_tag_and_class_cuts_each_build_by_its_own_class(self):
        before = self.rowed('<div class="old-row"><div><a href="/">All</a></div></div>')
        after = self.rowed('<div class="kit-row extra"><div class="inner"><nav><a href="/">All</a></nav></div></div>')
        self.assertStatus(1, before, after)
        out = self.assertStatus(0, before, after, '--without', 'div.old-row', '--without', 'div.kit-row', line=('identical',))
        self.assertIn('<div.old-row>', out.splitlines()[0])

    def test_without_tag_and_class_keeps_near_misses(self):
        for label, row in [
            ('longer class word', '<div class="kit-row-extra">x</div>'),
            ('class in another case', '<div class="Kit-Row">x</div>'),
            ('another tag', '<section class="kit-row">x</section>'),
            ('another attribute', '<div data-class="kit-row">x</div>'),
            ('no class', '<div>x</div>'),
        ]:
            with self.subTest(case=label):
                before = self.rowed(f'<div class="kit-row">cut</div>{row}')
                after = self.rowed(f'<div class="kit-row">also cut</div>{row.replace(">x<", ">y<")}')
                self.assertStatus(1, before, after, '--without', 'div.kit-row', line=('pages whose content (outside the header) changed (1)',))

    def test_without_tag_and_class_keeps_the_class_case_and_lowers_the_tag(self):
        before = self.rowed('<DIV class="Kit-Row">old</DIV>')
        after = self.rowed('<div class="Kit-Row">new</div>')
        self.assertStatus(0, before, after, '--without', 'DIV.Kit-Row')
        self.assertStatus(2, before, after, '--without', 'div.kit-row', line=('div.kit-row', 'no such element'))

    def test_without_tag_and_class_must_match_in_either_build(self):
        before = self.rowed('<div class="old-row">old</div>')
        after = self.rowed('')
        self.assertStatus(0, before, after, '--without', 'div.old-row', line=('identical',))
        self.assertStatus(0, after, before, '--without', 'div.old-row', line=('identical',))
        self.assertStatus(2, before, after, '--without', 'div.old-row', '--without', 'div.typo-row',
                          line=('--without div.typo-row', 'no such element in either build'))
        # A plain tag keeps its old rule: nothing to cut is no error.
        self.assertStatus(1, before, after, '--without', 'aside')

class Patterns(unittest.TestCase):
    """The script's two name patterns and the head's tags as printed, reached as functions."""

    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('check_sites', SCRIPT)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

    def test_head_tag_attributes_print_as_written(self):
        head = '<head><link rel="preload" crossorigin href="/f.woff2"><script defer src="/a.js"></script><meta content=""></head>'
        self.assertEqual(self.script.head_tags(head), [
            '<link rel="preload" crossorigin href="/f.woff2">',
            '<script defer src="/a.js">',
            '<meta content="">',
        ])

    def test_whole_asset_names_are_replaced(self):
        keys = {b'Base.Ab12Cd34.css': b'<CSS>', b'x.Ab12_d34.js': b'<JS>', b'f.Ab12-d34.woff2': b'<FONT>'}
        for text, wanted in [
            (b'href="/_astro/Base.Ab12Cd34.css"', b'href="/_astro/<CSS>"'),
            (b'import"./x.Ab12_d34.js"', b'import"./<JS>"'),
            (b'src:url(f.Ab12-d34.woff2)', b'src:url(<FONT>)'),
            (b'Base.Ab12Cd34.css', b'<CSS>'),
            (b'Base.Ab12Cd34.css\r\nx.Ab12_d34.js\n', b'<CSS>\r\n<JS>\n'),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.script.keyed(text, keys), wanted)

    def test_near_misses_are_left_alone(self):
        keys = {b'Base.Ab12Cd34.css': b'<CSS>'}
        for text in [b'/_astro/Base.Ab12Cd34.css.map', b'/_astro/xBase.Ab12Cd34.css', b'Base.Ab12Cd34.cssx',
                     b'my-Base.Ab12Cd34.css', b'base.Ab12Cd34.css', b'Base.Ab12Cd34_css']:
            with self.subTest(text=text):
                self.assertEqual(self.script.keyed(text, keys), text)

    def test_hash_is_dropped_from_an_asset_name(self):
        for name, wanted in [
            (b'Base.CIX-Jlc-.css', (b'Base', b'.css')),
            (b'Nav.astro_type_script.sfTAO5_a.js', (b'Nav.astro_type_script', b'.js')),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.script.HASHED.fullmatch(name).groups(), wanted)
        for name in [b'Base.Ab12Cd3.css', b'Base.Ab12Cd345.css', b'Base.Ab12!d34.css', b'Base.Ab12Cd34', b'.Ab12Cd34.css',
                     b'Base.Ab12Cd34.css\n']:
            with self.subTest(name=name):
                self.assertIsNone(self.script.HASHED.fullmatch(name))

    def test_without_pattern(self):
        for spec in ['footer', 'div.lane-row', 'div.Kit_Row-2', 'DIV.x']:
            with self.subTest(valid=spec):
                self.assertIsNotNone(self.script.WITHOUT.fullmatch(spec))
        for spec in ['', 'div.', '.lane-row', 'div.a.b', 'div.a b', 'div.a\n', 'div..a', '1div.a', 'div.a>']:
            with self.subTest(invalid=spec):
                self.assertIsNone(self.script.WITHOUT.fullmatch(spec))

    def test_strip_elements_by_class_counts_what_it_cuts(self):
        from collections import Counter
        cut = Counter()
        html = '<div class="a row"><div class="row">in</div></div><div class="rows">keep</div><div class=row>x</div><div class>y</div>'
        self.assertEqual(self.script.strip_elements(html, ['div.row'], counts=cut), '<div class="rows">keep</div><div class>y</div>')
        self.assertEqual(cut, Counter({'div.row': 2}))

    def test_tag_name_pattern(self):
        for tag in ['footer', 'FOOTER', 'h1', 'footer-note']:
            with self.subTest(valid=tag):
                self.assertIsNotNone(self.script.TAG_NAME.fullmatch(tag))
        for tag in ['', '<footer>', '1footer', '-footer', 'footer_note', 'footer note', 'footer\n']:
            with self.subTest(invalid=tag):
                self.assertIsNone(self.script.TAG_NAME.fullmatch(tag))

    def test_strip_elements_handles_case_attributes_and_line_endings(self):
        for html, tags, wanted in [
            ('<p>©</p><FOOTER data-a=">">old</FOOTER  ><p>end</p>', ['footer'], '<p>©</p><p>end</p>'),
            ('<p>a</p>\r\n<footer>\r\n  x\r\n</footer>\r\n<p>b</p>', ['footer'], '<p>a</p>\r\n\r\n<p>b</p>'),
            ('<p>a\rb</p><footer>x</footer><p>c</p>', ['footer'], '<p>a\rb</p><p>c</p>'),
            ('<textarea><footer></textarea><title><footer></title><footer>cut</footer>', ['footer'],
             '<textarea><footer></textarea><title><footer></title>'),
            ('<head><meta charset="utf-8"><title>T</title></head>', ['meta'], '<head><title>T</title></head>'),
        ]:
            with self.subTest(html=html):
                self.assertEqual(self.script.strip_elements(html, tags), wanted)


class Sites(Case):
    """`before` and `after` on a made-up layout: a copy of the script in kit/, sites beside it."""

    def setUp(self):
        super().setUp()
        self.kit = self.tmp / 'sites' / 'kit'
        write(self.kit, {'package.json': '{"name": "site-kit"}', 'scripts/check_sites.py': SCRIPT.read_bytes()})
        self.script = self.kit / 'scripts' / 'check_sites.py'

    def site(self, name, *, spec=TAG, module='copy', field='dependencies', build=COPIES, page=PAGE):
        """Write a site, or change one: its package.json, the page its build copies, its installed kit.

        module: 'copy' for an installed copy, a folder for a link to it, None for nothing installed.
        """
        site = self.kit.parent / name
        write(site, {'package.json': json.dumps({'scripts': {'build': build}, field: {'site-kit': spec}}),
                     'out/index.html': page})
        installed = site / 'node_modules' / 'site-kit'
        if installed.is_symlink():
            installed.unlink()
        elif installed.exists():
            shutil.rmtree(installed)
        if module == 'copy':
            write(installed, {'package.json': '{"name": "site-kit"}'})
        elif module:
            installed.parent.mkdir(exist_ok=True)
            installed.symlink_to(module, target_is_directory=True)
        return site

    def check(self, *args):
        return self.run_script(self.script, *args)

    def before(self, name='site-a', **changes):
        """The steps before an `after`: a site on the released kit, its "before" copy taken."""
        site = self.site(name, **changes)
        status, out = self.check('before', site)
        self.assertEqual(status, 0, out)
        return site

    def link(self, name='site-a', **changes):
        return self.site(name, spec=LINK, module=self.kit, **changes)

    def assertError(self, result, *line):
        status, out = result
        self.assertEqual(status, 2, out)
        self.assertLine(out, *line)

    # The whole path.

    def test_before_then_after_on_the_linked_kit_passes(self):
        site = self.before()
        self.assertTrue((self.snapshots / 'site-a' / 'index.html').is_file())
        self.link()
        status, out = self.check('after', site)
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'identical')

    def test_after_reports_a_changed_page(self):
        site = self.before()
        self.link(page=self.swap(PAGE, '<h1>Home</h1>', '<h1>Away</h1>'))
        status, out = self.check('after', site)
        self.assertEqual(status, 1, out)
        self.assertLine(out, 'pages whose content (outside the header) changed (1)')

    def test_after_release_on_the_installed_kit_passes(self):
        site = self.before()
        status, out = self.check('after', '--release', site)
        self.assertEqual(status, 0, out)

    # Criterion 1: a build that fails, or leaves nothing, is an error.

    def test_before_build_fails(self):
        site = self.site('site-a', build=FAILS)
        self.assertError(self.check('before', site), 'build failed in', site)

    def test_before_build_leaves_no_dist(self):
        site = self.site('site-a', build=NOTHING)
        self.assertError(self.check('before', site), 'left no dist/', site)

    def test_before_build_leaves_no_page(self):
        site = self.site('site-a', build=NO_PAGE)
        self.assertError(self.check('before', site), 'left no HTML page', site)
        self.assertFalse((self.snapshots / 'site-a').exists())

    def test_before_does_not_keep_a_stale_dist(self):
        site = self.site('site-a', build=NOTHING)
        write(site / 'dist', {'index.html': PAGE})
        self.assertError(self.check('before', site), 'left no dist/', self.snapshots / 'site-a-previous-dist')
        self.assertTrue((self.snapshots / 'site-a-previous-dist' / 'index.html').is_file())
        self.assertFalse((self.snapshots / 'site-a').exists())

    def test_after_build_fails(self):
        site = self.before()
        self.link(build=FAILS)
        self.assertError(self.check('after', site), 'build failed in', site)

    def test_after_build_leaves_no_dist(self):
        site = self.before()
        self.link(build=NOTHING)
        shutil.rmtree(site / 'dist')
        self.assertError(self.check('after', site), 'left no dist/', site)

    def test_after_build_leaves_no_page(self):
        site = self.before()
        self.link(build=NO_PAGE)
        self.assertError(self.check('after', site), 'left no HTML page', site)

    def test_after_does_not_compare_a_stale_dist(self):
        site = self.before()
        self.link(build=NOTHING)
        self.assertError(self.check('after', site), 'left no dist/', self.snapshots / 'site-a-previous-dist')
        self.assertTrue((self.snapshots / 'site-a-previous-dist' / 'index.html').is_file())

    def test_previous_dist_replaces_the_last_one(self):
        site = self.before()
        write(site / 'dist', {'marker.txt': 'second'})
        status, out = self.check('before', site)
        self.assertEqual(status, 0, out)
        self.assertEqual(sorted(p.name for p in (self.snapshots / 'site-a-previous-dist').iterdir()),
                         ['index.html', 'marker.txt'])
        status, out = self.check('before', site)
        self.assertEqual(status, 0, out)
        self.assertEqual([p.name for p in (self.snapshots / 'site-a-previous-dist').iterdir()], ['index.html'])

    # Criterion 5: the sites are found.

    def layout(self):
        self.site('site-a')
        self.site('site-b', field='devDependencies')
        write(self.kit.parent / 'unrelated', {'package.json': json.dumps({'scripts': {'build': FAILS}, 'dependencies': {}})})
        write(self.kit.parent, {'notes/readme.txt': '', 'a-file.txt': ''})

    def test_sites_are_found_beside_the_kit(self):
        self.layout()
        status, out = self.check('before')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'site-a: site-kit ' + TAG)
        self.assertLine(out, 'site-b: site-kit ' + TAG)
        self.assertNotIn('building unrelated', out)
        self.assertEqual(sorted(p.name for p in self.snapshots.iterdir()), ['site-a', 'site-b'])
        self.link('site-a')
        self.link('site-b', field='devDependencies')
        status, out = self.check('after')
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'site-b: site-kit ' + LINK)
        self.assertLine(out, 'site-b: before → after')

    def test_unreadable_package_json_beside_the_kit_is_an_error(self):
        self.layout()
        write(self.kit.parent / 'broken', {'package.json': '{"dependencies": '})
        result = self.check('before')
        self.assertError(result, "can't read", self.kit.parent / 'broken' / 'package.json')
        self.assertNotIn('building', result[1])

    def test_no_site_beside_the_kit_is_an_error(self):
        write(self.kit.parent / 'unrelated', {'package.json': '{"dependencies": {}}'})
        write(self.kit.parent, {'notes/readme.txt': ''})
        for command in ('before', 'after'):
            with self.subTest(command=command):
                self.assertError(self.check(command), 'no site found', self.kit.parent)

    def test_folders_given_still_work(self):
        self.layout()
        write(self.kit.parent / 'broken', {'package.json': '{"dependencies": '})
        status, out = self.check('before', self.kit.parent / 'site-b')
        self.assertEqual(status, 0, out)
        self.assertEqual([p.name for p in self.snapshots.iterdir()], ['site-b'])

    # Criterion 6: the kit each build uses is checked before anything builds.

    def test_before_refuses_a_file_spec_over_an_installed_copy(self):
        site = self.site('site-a', spec=LINK, module='copy')
        self.assertError(self.check('before', site), 'site-a: package.json links the kit', LINK, 'npm install')

    def test_before_refuses_a_site_with_no_installed_kit(self):
        site = self.site('site-a', module=None)
        self.assertError(self.check('before', site), 'site-a: no kit in node_modules/site-kit', 'npm install')

    def test_before_refuses_a_link_where_a_tag_is_wanted(self):
        site = self.site('site-a', spec=TAG, module=self.kit)
        self.assertError(self.check('before', site), 'site-a: node_modules/site-kit is a link', 'npm install')

    def test_after_release_refuses_a_link(self):
        site = self.before()
        self.site('site-a', spec=TAG, module=self.kit)
        self.assertError(self.check('after', '--release', site), 'site-a: node_modules/site-kit is a link', 'npm install')

    def test_after_release_refuses_a_file_spec(self):
        site = self.before()
        self.site('site-a', spec=LINK, module='copy')
        self.assertError(self.check('after', '--release', site), 'site-a: package.json links the kit', 'npm install')

    def test_after_refuses_a_file_spec_over_an_installed_copy(self):
        site = self.before()
        self.site('site-a', spec=LINK, module='copy')
        self.assertError(self.check('after', site), 'site-a: node_modules/site-kit is not a link to this kit', 'npm install ../kit')

    def test_after_refuses_a_site_with_no_installed_kit(self):
        site = self.before()
        self.site('site-a', spec=LINK, module=None)
        self.assertError(self.check('after', site), 'site-a: no kit in node_modules/site-kit', 'npm install ../kit')

    def test_after_refuses_a_link_to_another_kit_folder(self):
        site = self.before()
        write(self.kit.parent / 'kit-copy', {'package.json': '{"name": "site-kit"}'})
        self.site('site-a', spec='file:../kit-copy', module=self.kit.parent / 'kit-copy')
        self.assertError(self.check('after', site), 'site-a: node_modules/site-kit is not a link to this kit', 'npm install ../kit')

    def test_every_kit_is_checked_before_anything_builds(self):
        self.site('site-a')
        self.site('site-b', spec=LINK, module=self.kit)
        result = self.check('before')
        self.assertError(result, 'site-b: package.json links the kit')
        self.assertNotIn('building', result[1])
        self.assertFalse((self.kit.parent / 'site-a' / 'dist').exists())

    def test_after_without_a_before_copy_is_an_error(self):
        site = self.link()
        result = self.check('after', site)
        self.assertError(result, 'site-a: no "before" copy', 'run "before" first')
        self.assertNotIn('building', result[1])

    def test_after_with_without_and_changed_asset(self):
        before_page = self.swap(PAGE, '</body>', '<footer>old</footer></body>')
        site = self.site('site-a', page=before_page)
        write(site / 'out', {'_astro/Base.CIX-Jlc-.css': CSS, '_astro/nav.sfTAO5_a.js': JS})
        status, out = self.check('before', site)
        self.assertEqual(status, 0, out)

        after_page = self.swap(
            self.swap(PAGE, '</body>', '<footer>new</footer></body>'),
            'Base.CIX-Jlc-.css', 'Base.Zy98-w76.css',
        )
        shutil.rmtree(site / 'out')
        self.link('site-a', page=after_page)
        write(site / 'out', {'_astro/Base.Zy98-w76.css': 'a{color:red}b{color:green}', '_astro/nav.sfTAO5_a.js': JS})

        status, out = self.check('after', '--without', 'footer', '--changed-asset', 'Base.css', site)
        self.assertEqual(status, 0, out)
        lines = out.splitlines()
        report_start = lines.index('site-a: before → after') + 1
        self.assertIn('<footer>', lines[report_start])
        self.assertLine(out, 'planned change', 'Base.css')
        self.assertLine(out, 'identical')

        # Another change on the page is still reported with status 1.
        self.link('site-a', page=self.swap(after_page, '<h1>Home</h1>', '<h1>Away</h1>'))
        status, out = self.check('after', '--without', 'footer', '--changed-asset', 'Base.css', site)
        self.assertEqual(status, 1, out)
        self.assertLine(out, 'pages whose content (outside the header) changed (1)')

        # A wrong --changed-asset name on after is a status-2 error.
        self.assertError(self.check('after', '--changed-asset', 'Missing.css', site), 'Missing.css', 'not in')

        # Works with --release too once the site installs the released kit.
        self.site('site-a', page=after_page)
        status, out = self.check('after', '--release', '--without', 'footer', '--changed-asset', 'Base.css', site)
        self.assertEqual(status, 0, out)
        self.assertLine(out, 'identical')


if __name__ == '__main__':
    unittest.main()
