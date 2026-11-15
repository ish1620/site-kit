// Tests for the line-break rule in src/markdown.js. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lineBreaks } from '../src/markdown.js';

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
