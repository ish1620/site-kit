// Tests for src/routes.js. Run with `npm test`. The redirect's script runs in node:vm with stubs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { defineLocales } from '../src/i18n.js';
import { robotsTxt, langRedirect } from '../src/routes.js';

const ORIGIN = 'https://example.com';
// The default language isn't the first one: its home is "/", the others' "/ja/" and "/es/".
const i18n = defineLocales({ locales: ['ja', 'en', 'es'], defaultLocale: 'en' });

// Runs the redirect's script as the home page of ORIGIN would, with stubs for what it reads and
// calls. `saved` is the value stored under "lang"; `globals` replaces any of the stubs. Returns
// what the script did: the addresses it jumped to, the timers it set, and the page's style.
async function visit({ referrer = '', saved = null, search = '', hash = '', globals = {} } = {}) {
  const script = await langRedirect(i18n).text();
  const jumps = [];
  const timers = [];
  const style = { visibility: '' };
  const stubs = {
    URL,
    document: { referrer, documentElement: { style } },
    location: { origin: ORIGIN, search, hash, replace: (address) => jumps.push(address) },
    localStorage: { getItem: (key) => (key === 'lang' ? saved : null) },
    setTimeout: (callback, delay) => timers.push({ callback, delay }),
  };
  // Copied as defined, so a getter stays a getter and runs when the script reads the name.
  Object.defineProperties(stubs, Object.getOwnPropertyDescriptors(globals));
  vm.runInNewContext(script, stubs);
  return { jumps, timers, style };
}

const assertNothingDone = ({ jumps, timers, style }, message) => {
  assert.deepEqual(jumps, [], message);
  assert.equal(timers.length, 0, message);
  assert.equal(style.visibility, '', message);
};

test('robotsTxt allows everything and gives the full address of the sitemap, as plain text', async () => {
  for (const site of [new URL(`${ORIGIN}/`), ORIGIN]) {
    const response = robotsTxt(site);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('Content-Type'), 'text/plain; charset=utf-8');
    assert.equal(await response.text(), 'User-agent: *\nAllow: /\n\nSitemap: https://example.com/sitemap-index.xml\n');
  }
});

test('robotsTxt without the site address says to set site in astro.config.mjs', () => {
  assert.throws(() => robotsTxt(undefined), /set `site` in astro\.config\.mjs/);
});

test('langRedirect answers with JavaScript', () => {
  const response = langRedirect(i18n);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Content-Type'), 'text/javascript; charset=utf-8');
});

test("the redirect jumps to the saved language's home, keeps the search and hash, and hides the page until a timer shows it", async () => {
  const { jumps, timers, style } = await visit({ saved: 'ja', search: '?from=mail', hash: '#top' });
  assert.deepEqual(jumps, ['/ja/?from=mail#top']);
  assert.equal(style.visibility, 'hidden');
  assert.equal(timers.length, 1);
  assert.equal(timers[0].delay, 3000);
  timers[0].callback();
  assert.equal(style.visibility, '');

  assert.deepEqual((await visit({ saved: 'es' })).jumps, ['/es/']);
});

test("the redirect does nothing when the referrer is this site's, and jumps for another site's", async () => {
  assertNothingDone(await visit({ saved: 'ja', referrer: `${ORIGIN}/ja/about/` }));
  assertNothingDone(await visit({ saved: 'ja', referrer: `${ORIGIN}/` }));
  // Near misses: another site, and one whose address only starts like this one's.
  assert.deepEqual((await visit({ saved: 'ja', referrer: 'https://other.example/' })).jumps, ['/ja/']);
  assert.deepEqual((await visit({ saved: 'ja', referrer: `${ORIGIN}.other.example/` })).jumps, ['/ja/']);
});

test('the redirect does nothing when nothing is saved', async () => {
  assertNothingDone(await visit({ saved: null }));
  assertNothingDone(await visit({ saved: '' }));
});

test('the redirect does nothing when the default language is saved', async () => {
  assertNothingDone(await visit({ saved: 'en' }));
});

test('the redirect does nothing when an unknown value is saved', async () => {
  for (const saved of ['zh', 'JA', 'ja ', '/ja/']) assertNothingDone(await visit({ saved }), saved);
});

test('the redirect does nothing when the saved value is a name every object inherits', async () => {
  for (const saved of ['toString', 'constructor', '__proto__']) assertNothingDone(await visit({ saved }), saved);
});

const blocked = () => {
  throw new Error('storage is blocked');
};

test('the redirect does nothing, and throws nothing, when reading from storage throws', async () => {
  assertNothingDone(await visit({ saved: 'ja', globals: { localStorage: { getItem: blocked } } }));
});

test('the redirect does nothing, and throws nothing, when localStorage itself cannot be read', async () => {
  // A getter that throws; node:vm hands the script a ReferenceError in its place.
  const globals = Object.defineProperty({}, 'localStorage', { get: blocked, configurable: true });
  assertNothingDone(await visit({ saved: 'ja', globals }));
});
