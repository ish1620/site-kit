// Tests for src/content.js. Run with `npm test` (Node's own test runner; no dependencies).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { langOf, slugOf, isScheduled, languagesOf, checkPublishDates, checkTranslations } from '../src/content.js';

const entry = (id, data = {}, filePath) => ({ id, data, filePath });
// Asserts that fn throws an error whose message (not "Error: ...") matches the pattern.
const throwsWith = (fn, pattern) => assert.throws(fn, (error) => {
  assert.match(error.message, pattern);
  return true;
});

test('langOf and slugOf split the id at the first slash', () => {
  assert.equal(langOf(entry('es/post-1')), 'es');
  assert.equal(slugOf(entry('es/post-1')), 'post-1');
  assert.equal(slugOf(entry('en/notes/post-2')), 'notes/post-2');
});

test('isScheduled: the build decides once, the dev server reads the clock', async () => {
  assert.equal(isScheduled(new Date(Date.now() + 60_000)), true);
  assert.equal(isScheduled(new Date(Date.now() - 60_000)), false);
  assert.equal(isScheduled(new Date(Date.now() - 60_000), true), false);
  // A date that passes while the build runs stays scheduled for the build, not for the dev server.
  const soon = new Date(Date.now() + 150);
  await new Promise((done) => setTimeout(done, 300));
  assert.equal(isScheduled(soon, true), false);
  assert.equal(isScheduled(soon), true);
});

test('languagesOf lists the languages in the site order, among the entries passed in', () => {
  const entries = [entry('ja/post-1'), entry('zh/post-2'), entry('en/post-1')];
  assert.deepEqual(languagesOf(entries, 'post-1', ['en', 'es', 'ja', 'zh']), ['en', 'ja']);
  assert.deepEqual(languagesOf(entries, 'post-3', ['en', 'es', 'ja', 'zh']), []);
  assert.deepEqual(languagesOf(entries.slice(0, 1), 'post-1', ['en', 'es', 'ja', 'zh']), ['ja']);
});

test('checkPublishDates accepts a time with a zone, in the forms the front matter allows', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'site-kit-test-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = (name, text) => {
    const path = join(dir, name);
    writeFileSync(path, text);
    return entry(`en/${name}`, {}, path);
  };
  const good = [
    file('offset.md', '---\ntitle: One\npublishDate: 2026-01-15T09:30:00+00:00\n---\nText\n'),
    file('utc.md', '---\npublishDate: 2026-01-15T09:30Z\n---\n'),
    file('fraction.md', '---\npublishDate: 2026-01-15T09:30:00.250-05:00\n---\n'),
    file('double.md', '---\npublishDate: "2026-01-15T09:30:00+09:00"\n---\n'),
    file('single.md', "---\npublishDate: '2026-01-15T09:30:00+09:00'  \n---\n"),
    file('crlf.md', '---\r\ntitle: Two\r\npublishDate: 2026-01-15T09:30:00+00:00\r\n---\r\nText\r\n'),
    file('bom.md', '﻿---\npublishDate: 2026-01-15T09:30:00+00:00\n---\n'),
  ];
  assert.doesNotThrow(() => checkPublishDates(good));
  assert.doesNotThrow(() => checkPublishDates([file('other.md', '---\nshownOn: 2026-01-15T09:30:00Z\n---\n')], 'shownOn'));
});

test('checkPublishDates stops on a date without a time or a zone, naming the file', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'site-kit-test-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const bad = {
    'no-zone.md': '---\npublishDate: 2026-01-15T09:30:00\n---\n',
    'no-time.md': '---\npublishDate: 2026-01-15\n---\n',
    'missing.md': '---\ntitle: Three\n---\n',
    'only-in-body.md': '---\ntitle: Four\n---\npublishDate: 2026-01-15T09:30:00Z\n',
    'crlf-no-zone.md': '---\r\npublishDate: 2026-01-15T09:30:00\r\n---\r\n',
    'next-line.md': '---\npublishDate:\n  2026-01-15T09:30:00Z\n---\n',
  };
  for (const [name, text] of Object.entries(bad)) {
    const path = join(dir, name);
    writeFileSync(path, text);
    assert.throws(() => checkPublishDates([entry(`en/${name}`, {}, path)]), (error) => {
      assert.match(error.message, new RegExp(`${name.replace('.', '\\.')}: publishDate needs a time and a time zone`));
      return true;
    }, name);
  }
});

// A post in three languages; only the title is translated.
const post = (lang, data = {}) => entry(`${lang}/post-1`, {
  title: `Title ${lang}`, cover: '/photos/post-1/01.avif', publishDate: new Date('2026-01-15T09:30:00Z'),
  draft: false, original: 'ja', ...data,
}, `src/content/posts/${lang}/post-1.md`);

test('checkTranslations passes when only the excepted fields differ', () => {
  assert.doesNotThrow(() => checkTranslations([post('en'), post('ja'), post('es')], { except: ['title'] }));
});

test('checkTranslations stops on a compared field that differs, naming both files and the field', () => {
  const entries = [post('en', { cover: '/photos/post-1/02.avif' }), post('ja'), post('es')];
  assert.throws(() => checkTranslations(entries, { except: ['title'] }), (error) => {
    assert.match(error.message, /^src\/content\/posts\/en\/post-1\.md: cover is "\/photos\/post-1\/02\.avif", but in src\/content\/posts\/ja\/post-1\.md \(the original\) it is "\/photos\/post-1\/01\.avif"\. Every field but title must be the same in every language\.$/);
    return true;
  });
});

test('checkTranslations compares dates by their time', () => {
  const later = post('en', { publishDate: new Date('2026-01-15T09:31:00Z') });
  assert.throws(() => checkTranslations([later, post('ja')], { except: ['title'] }), /publishDate/);
  const same = post('en', { publishDate: new Date('2026-01-15T18:30:00+09:00') });
  assert.doesNotThrow(() => checkTranslations([same, post('ja')], { except: ['title'] }));
});

test('checkTranslations counts a field set in only one file as a difference', () => {
  assert.throws(() => checkTranslations([post('en', { extra: 1 }), post('ja')], { except: ['title'] }), /extra is 1, but .* it is \(not set\)/);
  assert.throws(() => checkTranslations([post('en'), post('ja', { extra: 1 })], { except: ['title'] }), /extra is \(not set\), but .* it is 1/);
});

test('checkTranslations with no exceptions compares every field', () => {
  assert.throws(() => checkTranslations([post('en'), post('ja')]), /title/);
});

test('checkTranslations with only compares those fields and nothing else', () => {
  const entries = [post('en', { cover: '/other.avif', link: 'https://example.com/a' }), post('ja', { link: 'https://example.com/a' })];
  assert.doesNotThrow(() => checkTranslations(entries, { only: ['link'] }));
  entries[0].data.link = 'https://example.com/b';
  assert.throws(() => checkTranslations(entries, { only: ['link'] }), /link must be the same in every language/);
});

test('checkTranslations compares nested values whatever their key order, arrays in order', () => {
  const a = post('en', { links: [{ label: 'One', url: 'https://example.com/1' }] });
  const b = post('ja', { links: [{ url: 'https://example.com/1', label: 'One' }] });
  assert.doesNotThrow(() => checkTranslations([a, b], { except: ['title'] }));
  const c = post('en', { pair: ['a', 'b'] });
  const d = post('ja', { pair: ['b', 'a'] });
  assert.throws(() => checkTranslations([c, d], { except: ['title'] }), /pair/);
});

test('checkTranslations compares with the original language, not with the first file read', () => {
  // The Spanish file comes first and is the odd one out: the message names it, against the original.
  const entries = [post('es', { cover: '/odd.avif' }), post('en'), post('ja')];
  throwsWith(() => checkTranslations(entries, { except: ['title'] }), /^src\/content\/posts\/es\/post-1\.md: cover .* in src\/content\/posts\/ja\/post-1\.md \(the original\)/);
});

test('checkTranslations falls back to the first version when the original language has none', () => {
  const entries = [post('en', { cover: '/odd.avif' }), post('es')];
  assert.throws(() => checkTranslations(entries, { except: ['title'] }), (error) => {
    assert.match(error.message, /^src\/content\/posts\/es\/post-1\.md: cover .* in src\/content\/posts\/en\/post-1\.md it is/);
    assert.doesNotMatch(error.message, /the original/);
    return true;
  });
});

test('checkTranslations takes the original language from originalLang when given', () => {
  const card = (lang, data) => entry(`${lang}/someone`, { name: 'Someone', ...data }, `src/content/cards/${lang}/someone.md`);
  const entries = [card('es', { link: 'https://example.com/es' }), card('en', { link: 'https://example.com/en' })];
  throwsWith(() => checkTranslations(entries, { only: ['link'], originalLang: () => 'en' }), /^src\/content\/cards\/es\/someone\.md: .* \(the original\)/);
});

test('checkTranslations checks each slug on its own', () => {
  const other = entry('en/post-2', { title: 'Other', cover: '/x.avif' });
  assert.doesNotThrow(() => checkTranslations([post('en'), post('ja'), other], { except: ['title'] }));
});
