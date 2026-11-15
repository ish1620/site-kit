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


class Patterns(unittest.TestCase):
    """The script's two name patterns, reached as functions."""

    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('check_sites', SCRIPT)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

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


if __name__ == '__main__':
    unittest.main()
