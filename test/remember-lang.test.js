// Tests for src/remember-lang.js. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chosenLanguage } from '../src/remember-lang.js';

// A made-up link: just what chosenLanguage() reads (closest() for the selector it uses).
function link(attrs, within) {
  const el = {
    getAttribute: (name) => attrs[name] ?? null,
    closest: (selector) => {
      assert.equal(selector, ':is(.kit-langs, .kit-langmenu) a[data-lang]');
      return within && 'data-lang' in attrs ? el : null;
    },
  };
  return el;
}

test('a plain click on a language link gives its code', () => {
  assert.equal(chosenLanguage({ target: link({ 'data-lang': 'es' }, true), button: 0 }), 'es');
});

test('a click that opens a new tab, or no language link, gives none', () => {
  const es = link({ 'data-lang': 'es' }, true);
  for (const key of ['metaKey', 'ctrlKey', 'altKey', 'shiftKey']) assert.equal(chosenLanguage({ target: es, button: 0, [key]: true }), undefined, key);
  assert.equal(chosenLanguage({ target: es, button: 1 }), undefined, 'middle button');
  assert.equal(chosenLanguage({ target: link({ href: '/a/' }, true), button: 0 }), undefined, 'another link');
  assert.equal(chosenLanguage({ target: link({ 'data-lang': 'es' }, false), button: 0 }), undefined, 'outside the language blocks');
  assert.equal(chosenLanguage({ target: { nodeType: 3 }, button: 0 }), undefined, 'not an element');
  assert.equal(chosenLanguage({ target: null, button: 0 }), undefined, 'no target');
});

test('outside a browser the module registers nothing and throws nothing', async () => {
  assert.equal(typeof globalThis.document, 'undefined');
  await import('../src/remember-lang.js?again');
});

// The wiring, on a made-up document: the module is imported twice under other addresses, so Node
// runs it as two bundles would.
let copies = 0;
async function wiredDocument() {
  const listeners = [];
  const doc = { addEventListener: (type, fn) => listeners.push([type, fn]) };
  globalThis.document = doc;
  try {
    await import(`../src/remember-lang.js?copy=${++copies}`);
    await import(`../src/remember-lang.js?copy=${++copies}`);
  } finally {
    delete globalThis.document;
  }
  const click = (event) => { for (const [type, fn] of listeners) if (type === 'click') fn({ button: 0, ...event }); };
  return { listeners, click };
}
// A storage that keeps what is set, or throws as a browser with storage blocked does.
function storage({ throws = false } = {}) {
  const saved = {};
  return { saved, setItem(key, value) { if (throws) throw new Error('blocked'); saved[key] = value; } };
}

test('wired: two copies register one listener', async () => {
  const { listeners } = await wiredDocument();
  assert.deepEqual(listeners.map(([type]) => type), ['click']);
});

test('wired: a click on a language link stores its code; a click elsewhere stores nothing', async () => {
  const { click } = await wiredDocument();
  globalThis.localStorage = storage();
  try {
    click({ target: link({ href: '/a/' }, true) });
    click({ target: link({ 'data-lang': 'ja' }, true), metaKey: true });
    assert.deepEqual(globalThis.localStorage.saved, {}, 'nothing for another link or a new-tab click');
    click({ target: link({ 'data-lang': 'ja' }, true) });
    assert.deepEqual(globalThis.localStorage.saved, { lang: 'ja' });
  } finally {
    delete globalThis.localStorage;
  }
});

test('wired: a storage that throws breaks nothing', async () => {
  const { click } = await wiredDocument();
  globalThis.localStorage = storage({ throws: true });
  try {
    assert.doesNotThrow(() => click({ target: link({ 'data-lang': 'es' }, true) }));
  } finally {
    delete globalThis.localStorage;
  }
});
