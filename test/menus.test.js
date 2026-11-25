// Tests for src/menus.js (closing menus). Run with `npm test`.
// Node has no DOM: the page here is a few made-up elements with just what the modules use.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toCloseOnPress, toCloseOnEscape, toCloseOnLink } from '../src/menus.js';

// An element: its tag, attributes and children; `open` for a <details>.
class El {
  constructor(tag, attrs = {}, children = []) {
    Object.assign(this, { tag, attrs, children, parent: null, open: false });
    for (const child of children) child.parent = this;
  }
  contains(node) { for (let n = node; n; n = n.parent) if (n === this) return true; return false; }
  *descendants() { for (const c of this.children) { yield c; yield* c.descendants(); } }
  // Only the selectors the modules use: tag[attr], tag and :is(.a, .b) tag[attr].
  matches(selector) {
    const m = selector.match(/^(?::is\(([^)]*)\) )?([a-z]+)(?:\[([a-z-]+)\])?$/);
    if (!m) throw new Error(`the fake DOM can't match ${selector}`);
    const [, within, tag, attr] = m;
    if (this.tag !== tag || (attr && !(attr in this.attrs))) return false;
    if (!within) return true;
    const classes = within.split(',').map((c) => c.trim().replace(/^\./, ''));
    for (let n = this.parent; n; n = n.parent) if (classes.some((c) => (n.attrs.class ?? '').split(' ').includes(c))) return true;
    return false;
  }
  closest(selector) { for (let n = this; n; n = n.parent) if (n.matches(selector)) return n; return null; }
  querySelector(selector) { for (const d of this.descendants()) if (d.matches(selector)) return d; return null; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  focus() { this.document.activeElement = this; }
}

// A page with a header drop-down, and a lane picker with a site's menu inside it.
function page() {
  const el = (tag, attrs, ...children) => new El(tag, attrs, children);
  const langSummary = el('summary', {});
  const langLink = el('a', { href: '/es/', 'data-lang': 'es' });
  const langMenu = el('details', { class: 'kit-langmenu', 'data-kit-menu': '' }, langSummary, el('nav', {}, langLink));
  const notesSummary = el('summary', {});
  const noteLink = el('a', { href: '/note/' });
  const notes = el('details', { class: 'notes-menu', 'data-kit-menu': '' }, notesSummary, el('div', {}, noteLink));
  const pickerSummary = el('summary', {});
  const laneLink = el('a', { href: '/a/' });
  const pickerNav = el('nav', {}, laneLink, notes);
  const picker = el('details', { class: 'kit-lane-picker', 'data-kit-menu': '' }, pickerSummary, pickerNav);
  const plainDetails = el('details', {}, el('summary', {}));
  const text = el('p', {});
  const body = el('body', {}, el('header', {}, langMenu), picker, plainDetails, text);
  const listeners = {};
  const doc = {
    activeElement: body,
    addEventListener: (type, fn) => (listeners[type] ??= []).push(fn),
    querySelectorAll: (selector) => [...body.descendants()].filter((d) => d.matches(selector)),
    listeners,
    fire(type, event) { for (const fn of listeners[type] ?? []) fn(event); },
  };
  for (const d of body.descendants()) d.document = doc;
  return { doc, body, langMenu, langSummary, langLink, picker, pickerSummary, pickerNav, laneLink, notes, notesSummary, noteLink, plainDetails, text };
}

test('a press closes the open menus that don\'t hold it', () => {
  const p = page();
  assert.deepEqual(toCloseOnPress([p.langMenu], p.text), [p.langMenu], 'outside: closed');
  assert.deepEqual(toCloseOnPress([p.langMenu], p.langLink), [], 'inside: stays');
  assert.deepEqual(toCloseOnPress([p.langMenu], p.langSummary), [], 'its own summary: left to the browser');
  assert.deepEqual(toCloseOnPress([p.picker, p.notes], p.pickerNav), [p.notes], 'in the picker outside its nested menu: only the nested one');
  assert.deepEqual(toCloseOnPress([p.picker, p.notes], p.text), [p.picker, p.notes], 'outside both: both');
  assert.deepEqual(toCloseOnPress([p.langMenu, p.picker], p.pickerSummary), [p.langMenu], 'opening another menu closes the first');
  assert.deepEqual(toCloseOnPress([p.langMenu], null), [p.langMenu], 'no target: closed');
  assert.deepEqual(toCloseOnPress([], p.text), []);
});

test('Escape closes the innermost open menu', () => {
  const p = page();
  assert.deepEqual(toCloseOnEscape([p.picker, p.notes]), [p.notes]);
  assert.deepEqual(toCloseOnEscape([p.notes, p.picker]), [p.notes], 'whatever the order');
  assert.deepEqual(toCloseOnEscape([p.picker]), [p.picker]);
  assert.deepEqual(toCloseOnEscape([]), []);
});

test('a link click closes the open menus that hold the link', () => {
  const p = page();
  assert.deepEqual(toCloseOnLink([p.picker, p.notes], p.noteLink), [p.picker, p.notes]);
  assert.deepEqual(toCloseOnLink([p.picker, p.notes], p.laneLink), [p.picker]);
  assert.deepEqual(toCloseOnLink([p.langMenu], p.laneLink), [], 'a link elsewhere');
  assert.deepEqual(toCloseOnLink([p.langMenu], null), [], 'not a link');
});

// The wiring, on the made-up page: the module is imported again under another address, so Node
// runs it as a second bundle would.
let copies = 0;
async function wiredPage() {
  const p = page();
  globalThis.document = p.doc;
  try {
    await import(`../src/menus.js?copy=${++copies}`);
    await import(`../src/menus.js?copy=${++copies}`);
  } finally {
    delete globalThis.document;
  }
  return p;
}

test('outside a browser the module registers nothing and throws nothing', async () => {
  assert.equal(typeof globalThis.document, 'undefined');
  await import(`../src/menus.js?copy=${++copies}`);
});

test('the wiring registers once per document, however many bundles import it', async () => {
  const p = await wiredPage();
  assert.deepEqual(Object.fromEntries(Object.entries(p.doc.listeners).map(([type, fns]) => [type, fns.length])),
    { pointerdown: 1, click: 1, keydown: 1 });
});

test('wired: a press outside closes a menu; a press in the picker closes only the menu inside it', async () => {
  const p = await wiredPage();
  p.langMenu.open = true;
  p.doc.fire('pointerdown', { target: p.langLink });
  assert.equal(p.langMenu.open, true, 'a press inside leaves it open');
  p.doc.fire('pointerdown', { target: p.text });
  assert.equal(p.langMenu.open, false, 'a press outside closes it');
  p.picker.open = p.notes.open = true;
  p.plainDetails.open = true;
  p.doc.fire('pointerdown', { target: p.pickerNav });
  assert.deepEqual([p.picker.open, p.notes.open], [true, false]);
  p.doc.fire('pointerdown', { target: p.text });
  assert.equal(p.picker.open, false);
  assert.equal(p.plainDetails.open, true, 'a <details> without data-kit-menu is left alone');
});

test('wired: Escape closes the innermost menu, the focus back on its summary when it was inside', async () => {
  const p = await wiredPage();
  p.picker.open = p.notes.open = true;
  p.doc.activeElement = p.noteLink;
  p.doc.fire('keydown', { key: 'Escape' });
  assert.deepEqual([p.picker.open, p.notes.open], [true, false], 'the nested menu only');
  assert.equal(p.doc.activeElement, p.notesSummary, 'focus back on its summary');
  p.doc.fire('keydown', { key: 'Escape' });
  assert.equal(p.picker.open, false, 'the next Escape closes the picker');
  assert.equal(p.doc.activeElement, p.pickerSummary);
  p.langMenu.open = true;
  p.doc.activeElement = p.text;
  p.doc.fire('keydown', { key: 'Escape' });
  assert.equal(p.langMenu.open, false);
  assert.equal(p.doc.activeElement, p.text, 'focus elsewhere stays where it is');
  p.langMenu.open = true;
  p.doc.fire('keydown', { key: 'Enter' });
  assert.equal(p.langMenu.open, true, 'another key does nothing');
});

test('wired: a link chosen inside a menu closes it', async () => {
  const p = await wiredPage();
  p.picker.open = p.notes.open = true;
  p.doc.fire('click', { target: p.noteLink });
  assert.deepEqual([p.picker.open, p.notes.open], [false, false]);
  p.langMenu.open = true;
  p.doc.fire('click', { target: p.text });
  assert.equal(p.langMenu.open, true, 'a click that is no link leaves it');
});
