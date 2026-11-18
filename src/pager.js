// The page numbers a pager shows (Pager.astro). Plain JavaScript (types in pager.d.ts) so Node's
// tests run it as it is.

// The first and last pages, and the current page with one on each side (three in a row at either
// end), with 'gap' where pages are skipped. A gap never hides a single page: that page is shown
// instead. The row stays at most seven items, however many pages.
export function pagerItems(count, current) {
  const start = Math.max(1, Math.min(current - 1, count - 2));
  const shown = new Set([1, count]);
  for (let n = start; n <= Math.min(count, start + 2); n++) shown.add(n);
  const items = [];
  for (const n of [...shown].sort((a, b) => a - b)) {
    const previous = items.at(-1);
    if (typeof previous === 'number' && n - previous === 2) items.push(n - 1);
    else if (typeof previous === 'number' && n - previous > 2) items.push('gap');
    items.push(n);
  }
  return items;
}
