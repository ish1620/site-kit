// Measures the site header (SiteHeader, LanguageNav) in a browser and returns a fingerprint and the
// details: every box and the letters' positions, colours, fonts, underlines and blur. Run it in the
// browser's console (or a browser tool) on the same page of the build from before a change and the
// build after, at 1280, 375 and 320px wide: the fingerprints should match. A code without an
// underline leaves its underline settings out, since they draw nothing.
(() => {
  const header = document.querySelector('header');
  const round = (v) => Math.round(v * 100) / 100;
  const box = (el) => { const b = el.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(round).join(','); };
  const textBox = (el) => { const r = document.createRange(); r.selectNodeContents(el); return box(r); };
  const style = (el, props) => { const s = getComputedStyle(el); return props.map((p) => s.getPropertyValue(p)).join(' / '); };
  const brand = header.querySelector('a');
  const nav = header.querySelector('nav');
  const logo = brand.querySelector('svg, img');
  let letters = '';
  if (logo) letters = 'logo ' + box(logo);
  else {
    const walk = document.createTreeWalker(brand, NodeFilter.SHOW_TEXT);
    for (let n; (n = walk.nextNode());) if (n.textContent.trim()) letters = 'letters ' + textBox(n);
  }
  const lines = [
    'width ' + innerWidth,
    'header ' + box(header) + ' | ' + style(header, ['z-index', 'background-color', 'backdrop-filter', 'border-bottom-width', 'border-bottom-color']),
    'name ' + box(brand) + ' ' + letters + ' | ' + style(brand, ['color']),
    'nav ' + box(nav) + ' | ' + style(nav, ['font-family', 'font-size', 'letter-spacing']),
    ...[...nav.children].map((c) => c.textContent + ' ' + box(c) + ' text ' + textBox(c) + ' | '
      + style(c, ['color', 'text-decoration-line'])
      + (c.matches('[aria-current]') ? ' / ' + style(c, ['text-decoration-thickness', 'text-underline-offset']) : '')),
    'main ' + box(document.querySelector('main')),
  ];
  const text = lines.join('\n');
  let hash = 5381;
  for (const ch of text) hash = ((hash * 33) ^ ch.charCodeAt(0)) >>> 0;
  return 'fingerprint ' + hash.toString(16) + '\n' + text;
})();
