// Tests for src/random.js, the script on the bare Random page. Run with `npm test`. The script runs
// in node:vm on a stand-in page whose jump is recorded instead of followed.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createContext, runInContext } from 'node:vm';

const SCRIPT = readFileSync(new URL('../src/random.js', import.meta.url), 'utf8');
const ORIGIN = 'https://example.com';

// Runs the script with these addresses listed on the page, this referrer and this home, and
// Math.random giving `random`. Returns where it jumped and the script's own functions.
function runRandom({ addresses = ['año'], referrer = '', home = '/', random = () => 0 } = {}) {
  const jumps = [];
  const meta = { content: JSON.stringify(addresses), dataset: { home } };
  const context = createContext({
    URL, random,
    document: { referrer, querySelector: (selector) => (selector === 'meta[name="random-addresses"]' ? meta : null) },
    location: { origin: ORIGIN, replace: (address) => jumps.push(address) },
  });
  runInContext('Math.random = random;', context);
  runInContext(SCRIPT, context, { filename: 'src/random.js' });
  assert.equal(jumps.length, 1, 'the script jumps exactly once');
  return { jump: jumps[0], randomAddress: context.randomAddress, referrerAddress: context.referrerAddress };
}
const { randomAddress, referrerAddress } = runRandom();

test('randomAddress: zero, one and two other addresses, and both selection boundaries', () => {
  assert.equal(randomAddress([], ''), null);
  assert.equal(randomAddress(['año'], encodeURIComponent('año')), null);
  assert.equal(randomAddress(['año', 'té'], encodeURIComponent('año'), () => 0), 'té');
  assert.equal(randomAddress(['año', 'té', 'sí'], encodeURIComponent('año'), () => 0), 'té');
  assert.equal(randomAddress(['año', 'té', 'sí'], encodeURIComponent('año'), () => 0.999999), 'sí');
  assert.equal(randomAddress(['año', 'té'], encodeURIComponent('año'), () => 0), 'té', 'a decomposed form is the same address');
  assert.equal(randomAddress(['año', 'té'], encodeURIComponent('año'), () => 0), 'té', 'so is a decomposed address in the list');
  assert.equal(randomAddress(['/año/', '/té/'], '/a%C3%B1o/', () => 0), '/té/');
  assert.equal(randomAddress(['año'], '', () => 0), 'año');
  assert.equal(randomAddress(['001', '002'], '001', () => 0), '002', 'a bare number');
});

test('randomAddress: malformed encoding behaves as absent, skipping nothing', () => {
  let first;
  assert.doesNotThrow(() => { first = randomAddress(['año', 'té'], '%broken', () => 0); });
  assert.equal(first, 'año', 'every address stays a candidate');
  assert.equal(randomAddress(['año', 'té'], '%broken', () => 0.999999), 'té');
  assert.equal(randomAddress([], '%broken'), null);
});

test('referrerAddress: only a same-site referrer right under home names the address to skip', () => {
  assert.equal(referrerAddress(`${ORIGIN}/a%C3%B1o/`, ORIGIN, '/'), 'a%C3%B1o');
  assert.equal(referrerAddress(`${ORIGIN}/a%C3%B1o/?x=1#y`, ORIGIN, '/'), 'a%C3%B1o', 'query and hash are not the path');
  assert.equal(referrerAddress(`${ORIGIN}/es/a%C3%B1o/`, ORIGIN, '/es/'), 'a%C3%B1o', 'a language prefix is home');
  assert.equal(referrerAddress(`${ORIGIN}/ja/a%C3%B1o/`, ORIGIN, '/es/'), '', 'another language\'s page: not under home');
  for (const referrer of ['', 'not an address', 'https://example.org/a%C3%B1o/', 'http://example.com/a%C3%B1o/',
    `${ORIGIN}/`, `${ORIGIN}/a%C3%B1o`, `${ORIGIN}/a1/page/2/`, `${ORIGIN}/es/a%C3%B1o/`, `${ORIGIN}//a%C3%B1o/`]) {
    assert.equal(referrerAddress(referrer, ORIGIN, '/'), '', JSON.stringify(referrer));
  }
});

test('the jump skips the referring page and is built from the list alone', () => {
  const addresses = ['año', 'té'];
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/a%C3%B1o/` }).jump, '/t%C3%A9/', 'same-site page: skipped');
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/an%CC%83o/` }).jump, '/t%C3%A9/', 'same-site page, decomposed: skipped');
  assert.equal(runRandom({ addresses, referrer: 'https://example.org/a%C3%B1o/' }).jump, '/a%C3%B1o/', 'another site: nothing skipped');
  assert.equal(runRandom({ addresses, referrer: '' }).jump, '/a%C3%B1o/', 'no referrer: nothing skipped');
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/a1/` }).jump, '/a%C3%B1o/', 'a page not in the list: nothing skipped');
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/a1/`, random: () => 0.999999 }).jump, '/t%C3%A9/', 'the top of the range');
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/%E0%A4%A/` }).jump, '/a%C3%B1o/', 'a malformed path: nothing skipped');
  assert.equal(runRandom({ addresses: ['año'], referrer: `${ORIGIN}/a%C3%B1o/` }).jump, '/', 'nothing left: home');
  assert.equal(runRandom({ addresses: [], referrer: '' }).jump, '/', 'an empty list: home');
  assert.equal(runRandom({ addresses, referrer: `${ORIGIN}/%2F%2Fexample.org/` }).jump, '/a%C3%B1o/', 'a crafted referrer never becomes the destination');
  assert.equal(runRandom({ addresses, home: '/es/', referrer: `${ORIGIN}/es/a%C3%B1o/` }).jump, '/es/t%C3%A9/', 'a language prefix stays');
  assert.equal(runRandom({ addresses: ['001', '002'], home: '/ja/', referrer: `${ORIGIN}/ja/001/` }).jump, '/ja/002/', 'a bare slug under a language home');
});
