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
