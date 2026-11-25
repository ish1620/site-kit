// Tests for src/menus.js (closing menus). Run with `npm test`.
// Node has no DOM: the page here is a few made-up elements with just what the modules use.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { INTERACTIVE, toCloseOnPress, toCloseOnEscape, toCloseOnClick } from '../src/menus.js';

// An element: its tag, attributes and children; `open` for a <details>.
class El {
  constructor(tag, attrs = {}, children = []) {
    Object.assign(this, { tag, attrs, children, parent: null, open: false });
    for (const child of children) child.parent = this;
  }
  contains(node) { for (let n = node; n; n = n.parent) if (n === this) return true; return false; }
  *descendants() { for (const c of this.children) { yield c; yield* c.descendants(); } }
  // Only the selectors the modules use: lists of tag[attr], tag and :is(.a, .b) tag[attr].
  matches(selector) {
    const list = selector.split(/,(?![^(]*\))/);
    if (list.length > 1) return list.some((one) => this.matches(one.trim()));
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
  // Below the menus: things that act on a click, one of them through an element inside it.
  const wordInLink = el('span', {});
  const linkBelow = el('a', { href: '/below/' }, wordInLink);
  const button = el('button', {});
  const field = el('input', {});
  const label = el('label', {});
  const anchorWithoutHref = el('a', {});
  const body = el('body', {}, el('header', {}, langMenu), picker, plainDetails, text, linkBelow, button, field, label, anchorWithoutHref);
  const listeners = {};
  const doc = {
    activeElement: body,
    addEventListener: (type, fn) => (listeners[type] ??= []).push(fn),
    querySelectorAll: (selector) => [...body.descendants()].filter((d) => d.matches(selector)),
    listeners,
    fire(type, event) { for (const fn of listeners[type] ?? []) fn(event); },
  };
  for (const d of body.descendants()) d.document = doc;
  return { doc, body, langMenu, langSummary, langLink, picker, pickerSummary, pickerNav, laneLink, notes, notesSummary, noteLink, plainDetails, text,
    wordInLink, linkBelow, button, field, label, anchorWithoutHref };
}

test('a press closes the open menus that don\'t hold it', () => {
  const p = page();
  assert.deepEqual(toCloseOnPress([p.langMenu], p.text), [p.langMenu], 'outside, on plain text: closed on the press');
  assert.deepEqual(toCloseOnPress([p.langMenu], p.anchorWithoutHref), [p.langMenu], 'an <a> without href is no link');
  assert.deepEqual(toCloseOnPress([p.langMenu], p.langLink), [], 'inside: stays');
  assert.deepEqual(toCloseOnPress([p.langMenu], p.langSummary), [], 'its own summary: left to the browser');
  assert.deepEqual(toCloseOnPress([p.picker, p.notes], p.pickerNav), [p.notes], 'in the picker outside its nested menu: only the nested one');
  assert.deepEqual(toCloseOnPress([p.picker, p.notes], p.text), [p.picker, p.notes], 'outside both: both');
  assert.deepEqual(toCloseOnPress([p.langMenu], null), [p.langMenu], 'no target: closed');
  assert.deepEqual(toCloseOnPress([], p.text), []);
});

test('a press on something that acts on a click waits for the click', () => {
  const p = page();
  assert.equal(INTERACTIVE, 'a[href], button, summary, input, select, textarea, label');
  for (const name of ['linkBelow', 'wordInLink', 'button', 'field', 'label', 'pickerSummary']) {
    assert.deepEqual(toCloseOnPress([p.picker, p.langMenu], p[name]), [], name);
  }
});

test('a click closes the open menus that don\'t hold it, and those that hold the link it chooses', () => {
  const p = page();
  assert.deepEqual(toCloseOnClick([p.picker], p.linkBelow), [p.picker], 'a link below the picker: closed on its click');
  assert.deepEqual(toCloseOnClick([p.picker], p.wordInLink), [p.picker], 'inside that link');
  assert.deepEqual(toCloseOnClick([p.picker, p.langMenu], p.button), [p.picker, p.langMenu], 'a button outside both');
  assert.deepEqual(toCloseOnClick([p.langMenu, p.picker], p.pickerSummary), [p.langMenu], 'opening another menu closes the first');
  assert.deepEqual(toCloseOnClick([p.picker, p.notes], p.noteLink), [p.picker, p.notes], 'a link chosen inside: every menu holding it');
  assert.deepEqual(toCloseOnClick([p.picker, p.notes], p.laneLink), [p.picker, p.notes], 'a lane in the picker: the picker, and Notes beside it');
  assert.deepEqual(toCloseOnClick([p.picker, p.notes], p.notesSummary), [], 'a summary inside: left to the browser');
  assert.deepEqual(toCloseOnClick([p.picker, p.notes], p.pickerNav), [p.notes], 'in the picker outside Notes: Notes, as on the press');
  assert.deepEqual(toCloseOnClick([], p.linkBelow), []);
});

test('Escape closes the innermost open menu', () => {
  const p = page();
  assert.deepEqual(toCloseOnEscape([p.picker, p.notes]), [p.notes]);
  assert.deepEqual(toCloseOnEscape([p.notes, p.picker]), [p.notes], 'whatever the order');
  assert.deepEqual(toCloseOnEscape([p.picker]), [p.picker]);
  assert.deepEqual(toCloseOnEscape([]), []);
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

test('wired: a tap on a link below the open picker keeps it open until the click, which closes it', async () => {
  const p = await wiredPage();
  for (const target of ['linkBelow', 'wordInLink', 'button']) {
    p.picker.open = true;
    p.doc.fire('pointerdown', { target: p[target] });
    assert.equal(p.picker.open, true, `${target}: still open after the press, so nothing below moves before the release`);
    p.doc.fire('click', { target: p[target] });
    assert.equal(p.picker.open, false, `${target}: closed on the click`);
  }
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
  p.doc.fire('click', { target: p.langMenu.querySelector('nav') });
  assert.equal(p.langMenu.open, true, 'a click inside that is no link leaves it');
  p.doc.fire('click', { target: p.text });
  assert.equal(p.langMenu.open, false, 'a click outside closes it');
});
