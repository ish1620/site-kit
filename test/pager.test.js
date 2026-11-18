// Tests for src/pager.js. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pagerItems } from '../src/pager.js';

const row = (count, current) => pagerItems(count, current).map((item) => (item === 'gap' ? '…' : String(item))).join(' ');

test('pagerItems: first, last and the current page with its neighbours, gaps between', () => {
  assert.equal(row(150, 1), '1 2 3 … 150');
  assert.equal(row(150, 2), '1 2 3 … 150');
  assert.equal(row(150, 3), '1 2 3 4 … 150');
  assert.equal(row(150, 4), '1 2 3 4 5 … 150', 'a gap never hides one page: 2 shows instead');
  assert.equal(row(150, 5), '1 … 4 5 6 … 150');
  assert.equal(row(150, 75), '1 … 74 75 76 … 150');
  assert.equal(row(150, 148), '1 … 147 148 149 150');
  assert.equal(row(150, 149), '1 … 148 149 150');
  assert.equal(row(150, 150), '1 … 148 149 150');
  assert.equal(row(5, 3), '1 2 3 4 5');
  assert.equal(row(2, 1), '1 2');
  assert.equal(row(1, 1), '1');
});

test('pagerItems: for every count and page, a short rising row from 1 to the last page', () => {
  const counts = [...Array.from({ length: 30 }, (_, i) => i + 1), 150, 1500];
  for (const count of counts) for (let current = 1; current <= count; current++) {
    const items = pagerItems(count, current);
    const where = `${count} pages, page ${current}: ${row(count, current)}`;
    assert.ok(items.length <= 7, `${where}: at most seven numbers and gaps`);
    assert.equal(items[0], 1, `${where}: starts at 1`);
    assert.equal(items.at(-1), count, `${where}: ends at the last page`);
    assert.ok(items.includes(current), `${where}: holds the current page`);
    items.forEach((item, i) => {
      if (item === 'gap') {
        assert.notEqual(items[i + 1], 'gap', `${where}: no two gaps side by side`);
        assert.ok(items[i + 1] - items[i - 1] >= 3, `${where}: a gap hides at least two pages`);
      } else {
        const previous = items.slice(0, i).filter((n) => n !== 'gap').at(-1);
        assert.ok(previous === undefined || item > previous, `${where}: numbers strictly rising`);
      }
    });
  }
});
