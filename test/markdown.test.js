// Tests for the Markdown rules in src/markdown.js, on made-up nodes. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { figures, lineBreaks, noRawHtml } from '../src/markdown.js';

const text = (value) => ({ type: 'text', value });
const br = { type: 'break' };

// Runs the rule on one text node. Returns the nodes it put in that node's place, or undefined
// when it left the node alone.
function replaced(value) {
  const node = text(value);
  const calls = [];
  lineBreaks.text(node, { replaceNode: (...args) => calls.push(args) });
  if (calls.length === 0) return undefined;
  assert.equal(calls.length, 1, 'replaceNode is called once');
  assert.equal(calls[0][0], node, 'the node replaced is the one the rule was given');
  return calls[0][1];
}

test('a text node without a line feed is left alone', () => {
  assert.equal(replaced('one line'), undefined);
  assert.equal(replaced(' spaces and\ttabs '), undefined);
  assert.equal(replaced(''), undefined);
});

test('a line feed becomes a break between two text nodes', () => {
  assert.deepEqual(replaced('one\ntwo'), [text('one'), br, text('two')]);
});

test('CRLF becomes one break, and no CR is left in the text', () => {
  assert.deepEqual(replaced('one\r\ntwo'), [text('one'), br, text('two')]);
});

test('spaces and tabs on both sides of the break go; those inside a line stay', () => {
  assert.deepEqual(replaced('one \t\n\t two'), [text('one'), br, text('two')]);
  assert.deepEqual(replaced('one\t \r\n \ttwo'), [text('one'), br, text('two')]);
  assert.deepEqual(replaced('one a\ntwo\tb'), [text('one a'), br, text('two\tb')]);
});

test('several breaks in one node each become a break', () => {
  assert.deepEqual(replaced('one\ntwo\nthree'), [text('one'), br, text('two'), br, text('three')]);
});

test('an ideographic space beside a break is kept', () => {
  assert.deepEqual(replaced('one\n　two'), [text('one'), br, text('　two')]);
  assert.deepEqual(replaced('one　\ntwo'), [text('one　'), br, text('two')]);
});

test("a line break at a node's start or end gives no empty text node", () => {
  assert.deepEqual(replaced('\none'), [br, text('one')]);
  assert.deepEqual(replaced('one\n'), [text('one'), br]);
  assert.deepEqual(replaced('\n'), [br]);
});

test('a lone CR is not a line break here', () => {
  assert.equal(replaced('one\rtwo'), undefined);
  assert.deepEqual(replaced('one\rtwo\nthree'), [text('one\rtwo'), br, text('three')]);
});

// A made-up tree: each node's parent as the processor's ctx.parent() gives it, and every
// setProperty() call the rule makes, in order.
const FILE_URL = new URL('file:///site/src/content/posts/en/001.md');
const FILE = '/site/src/content/posts/en/001.md';
function context(parents, fileURL = FILE_URL) {
  const set = [];
  return { set, ctx: { fileURL, parent: (node) => parents.get(node), setProperty: (node, key, value) => set.push([node, key, value]) } };
}
// An image inside `path`, outermost first: `paragraph(root)` is a top-level paragraph.
function imageIn(...path) {
  const image = { type: 'image', url: '/images/001/flow.svg', alt: 'A flow', title: null };
  const parents = new Map();
  let child = image;
  for (const parent of path.reverse()) {
    parent.children ??= [child];
    parents.set(child, parent);
    child = parent;
  }
  return { image, parents };
}
const root = () => ({ type: 'root' });
const paragraph = (children) => ({ type: 'paragraph', ...(children && { children }) });
const MADE = { class: 'post-figure', src: '/images/001/flow.ja.svg', width: 720, height: 300 };

test('noRawHtml: a block, an inline tag or a comment stops the build, naming the file and the start of the tag', () => {
  for (const [value, start] of [
    ['<div class="x">\nText\n</div>', '<div class="x">'],
    ['<b>', '<b>'],
    ['<!-- a note -->', '<!-- a note -->'],
    ['  <img src="/a.svg"\n  alt="x">', '<img src="/a.svg"'],
    [`<p title="${'x'.repeat(100)}">`, `<p title="${'x'.repeat(70)}`],
  ]) {
    const { ctx } = context(new Map());
    assert.throws(() => noRawHtml.html({ type: 'html', value }, ctx), (error) => {
      assert.equal(error.message, `${FILE}: raw HTML in a text: write it in Markdown (found ${start})`);
      return true;
    }, value);
  }
});

test('figures: an image alone in a top-level paragraph is a figure, written as the site says', () => {
  const top = paragraph();
  const { image, parents } = imageIn(root(), top);
  const { set, ctx } = context(parents);
  const asked = [];
  figures((found) => { asked.push(found); return MADE; }).image(image, ctx);
  assert.deepEqual(asked, [{ src: '/images/001/flow.svg', alt: 'A flow', title: null, file: FILE }]);
  assert.deepEqual(set, [
    [top, 'data', { hName: 'figure', hProperties: { class: 'post-figure' } }],
    [image, 'url', '/images/001/flow.ja.svg'],
    [image, 'data', { hProperties: { width: 720, height: 300, loading: 'lazy', decoding: 'async' } }],
  ]);
});

test('figures: the title and an empty alt text reach the site as written', () => {
  const { image, parents } = imageIn(root(), paragraph());
  Object.assign(image, { alt: '', title: 'Flow' });
  const asked = [];
  figures((found) => { asked.push(found); return MADE; }).image(image, context(parents).ctx);
  assert.equal(asked[0].alt, '');
  assert.equal(asked[0].title, 'Flow');
});

test('figures: the site\'s refusal stops the build, and nothing is written', () => {
  const { image, parents } = imageIn(root(), paragraph());
  const { set, ctx } = context(parents);
  assert.throws(() => figures(() => { throw new Error('no alt text'); }).image(image, ctx), /^Error: no alt text$/);
  assert.deepEqual(set, []);
});

test('figures: any other image stops the build, naming the file and the address, before the site is asked', () => {
  const misplaced = `${FILE}: an image stands on a line of its own, with a blank line before and after: /images/001/flow.svg`;
  const text = { type: 'text', value: 'Before.' };
  for (const [label, path] of [
    ['beside other nodes', [root(), paragraph([text, 'the image'])]],
    ['in a link', [root(), paragraph(), { type: 'link' }]],
    ['in a heading', [root(), { type: 'heading' }]],
    ['in a list item\'s paragraph', [root(), { type: 'list' }, { type: 'listItem' }, paragraph()]],
    ['in a quote\'s paragraph', [root(), { type: 'blockquote' }, paragraph()]],
    ['in a table cell', [root(), { type: 'table' }, { type: 'tableRow' }, { type: 'tableCell' }]],
    ['in a paragraph of a node not known here', [root(), { type: 'containerDirective' }, paragraph()]],
  ]) {
    const { image, parents } = imageIn(...path);
    const { set, ctx } = context(parents);
    let asked = false;
    assert.throws(() => figures(() => { asked = true; return MADE; }).image(image, ctx), (error) => {
      assert.equal(error.message, misplaced);
      return true;
    }, label);
    assert.equal(asked, false, label);
    assert.deepEqual(set, [], label);
  }
});

test('figures: a reference-style image stops the build, naming its label', () => {
  const { ctx } = context(new Map());
  assert.throws(() => figures(() => MADE).imageReference({ type: 'imageReference', alt: 'A flow', label: 'Flow', identifier: 'flow' }, ctx),
    (error) => {
      assert.equal(error.message, `${FILE}: an image is written with its address, ![alt](/address), not by reference: ![A flow][Flow]`);
      return true;
    });
});

test('figures and noRawHtml: a text with no file stops the build', () => {
  const { image, parents } = imageIn(root(), paragraph());
  assert.throws(() => figures(() => MADE).image(image, context(parents, null).ctx), /a Markdown text with no file/);
  assert.throws(() => noRawHtml.html({ type: 'html', value: '<b>' }, context(new Map(), null).ctx), /a Markdown text with no file/);
  // A text with no image and no raw HTML too: each rule looks before it reads the first node.
  assert.throws(() => figures(() => MADE).before(root(), context(new Map(), null).ctx), /a Markdown text with no file/);
  assert.throws(() => noRawHtml.before(root(), context(new Map(), null).ctx), /a Markdown text with no file/);
  assert.doesNotThrow(() => figures(() => MADE).before(root(), context(new Map()).ctx));
  assert.doesNotThrow(() => noRawHtml.before(root(), context(new Map()).ctx));
});
