// Measures the site header (SiteHeader, LanguageNav or LanguageMenu) and whatever sits between it
// and <main> (a lane row) in a browser, and returns a fingerprint and the details: every box and
// the letters' positions, colours, fonts, underlines and blur. Run it in the browser's console (or
// a browser tool) on the same page of the build from before a change and the build after, at 1280,
// 375 and 320px wide: the fingerprints should match. A code or a link without an underline leaves
// its underline settings out, since they draw nothing.
// - The name: its box and the text box of every word in it that is its own text node ("letters"),
//   or its logo's box.
// - The language links (nav.kit-langs): each code. A one-language site's header has none: its nav
//   line reads "nav none", with no codes.
// - The drop-down (details.kit-langmenu), in place of the links: the code's own text box, and the
//   open list with each language (opened for the measure if it is closed, then closed again).
// - Between the header and <main>: each element's box, its line and background, and each link and
//   summary in it with its text and type; a page with nothing there adds no line, so its
//   fingerprint is the one this script gave before it measured anything there.
(() => {
  const header = document.querySelector('header');
  const round = (v) => Math.round(v * 100) / 100;
  const box = (el) => { const b = el.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(round).join(','); };
  const textBox = (el) => { const r = document.createRange(); r.selectNodeContents(el); return box(r); };
  const style = (el, props) => { const s = getComputedStyle(el); return props.map((p) => s.getPropertyValue(p)).join(' / '); };
  const underline = (el) => (el.matches('[aria-current]') ? ' / ' + style(el, ['text-decoration-thickness', 'text-underline-offset']) : '');
  const brand = header.querySelector('a');
  const nav = header.querySelector('nav.kit-langs');
  const menu = header.querySelector('details.kit-langmenu');
  const logo = brand.querySelector('svg, img');
  let letters = '';
  if (logo) letters = 'logo ' + box(logo);
  else {
    const words = [];
    const walk = document.createTreeWalker(brand, NodeFilter.SHOW_TEXT);
    for (let n; (n = walk.nextNode());) if (n.textContent.trim()) words.push(textBox(n));
    if (words.length) letters = 'letters ' + words.join(' ');
  }
  let languages = ['nav none'];
  if (nav) {
    languages = [
      'nav ' + box(nav) + ' | ' + style(nav, ['font-family', 'font-size', 'letter-spacing']),
      ...[...nav.children].map((c) => c.textContent + ' ' + box(c) + ' text ' + textBox(c) + ' | '
        + style(c, ['color', 'text-decoration-line']) + underline(c)),
    ];
  } else if (menu) {
    const summary = menu.querySelector('summary');
    const code = summary.querySelector('.kit-langmenu-code');
    // The code as the page shows it, closed (open, its colour changes), then the open list.
    const wasOpen = menu.open;
    menu.open = false;
    const closed = 'code ' + code.textContent + ' ' + box(summary) + ' text ' + textBox(code) + ' | ' + style(summary, ['color']);
    menu.open = true;
    const list = menu.querySelector('.kit-langmenu-list');
    languages = [
      'langmenu ' + box(menu) + ' | ' + style(menu, ['font-family', 'font-size', 'letter-spacing']),
      closed,
      'list ' + box(list) + ' | ' + style(list, ['background-color', 'border-top-width', 'border-top-color']),
      ...[...list.children].map((c) => c.textContent + ' ' + box(c) + ' text ' + textBox(c) + ' | '
        + style(c, ['color', 'font-family', 'text-decoration-line']) + underline(c)),
    ];
    menu.open = wasOpen;
  }
  const main = document.querySelector('main');
  const between = [];
  for (let el = header.nextElementSibling; el && el !== main && !el.contains(main); el = el.nextElementSibling) {
    if (el.matches('script, style, template')) continue;
    between.push('between ' + el.tagName.toLowerCase() + ' ' + box(el) + ' | '
      + style(el, ['border-bottom-width', 'border-bottom-color', 'background-color', 'position']));
    for (const item of el.querySelectorAll('a, summary')) {
      const text = item.textContent.trim().replace(/\s+/g, ' ');
      between.push('  ' + text + ' ' + box(item) + ' text ' + textBox(item) + ' | '
        + style(item, ['visibility', 'color', 'font-family', 'font-size', 'letter-spacing', 'text-transform', 'text-decoration-line'])
        + underline(item));
    }
  }
  const lines = [
    'width ' + innerWidth,
    'header ' + box(header) + ' | ' + style(header, ['z-index', 'background-color', 'backdrop-filter', 'border-bottom-width', 'border-bottom-color']),
    'name ' + box(brand) + ' ' + letters + ' | ' + style(brand, ['color']),
    ...languages,
    ...between,
    'main ' + box(main),
  ];
  const text = lines.join('\n');
  let hash = 5381;
  for (const ch of text) hash = ((hash * 33) ^ ch.charCodeAt(0)) >>> 0;
  return 'fingerprint ' + hash.toString(16) + '\n' + text;
})();
