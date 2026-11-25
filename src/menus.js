// Closing menus: every <details data-kit-menu> on the page (LanguageMenu, LaneRow's picker, a
// site's own menu). The browser's <details> opens and closes them; this closes them where a menu
// is expected to close:
// - a press outside an open menu closes it (a press, not a click: a tap on plain text sends no
//   click in Safari on a phone). A press inside a menu leaves it and the menus around it open,
//   so a press in the picker outside a menu nested in it closes only the nested one;
// - Escape closes the innermost open menu, and puts the focus back on its summary when the focus
//   was inside it;
// - a click on a link inside an open menu closes it, so the page the browser keeps for the back
//   button shows it closed.
// The decisions are the pure functions below. The page wiring (wireMenus) registers once per
// document, so two bundles that both import this module can't double it, and does nothing
// outside a browser.

// The open menus a press on `target` closes: those that don't hold it.
export function toCloseOnPress(open, target) {
  return open.filter((menu) => !(target && menu.contains(target)));
}

// The open menus Escape closes: the innermost, those that hold no other open menu.
export function toCloseOnEscape(open) {
  return open.filter((menu) => !open.some((other) => other !== menu && menu.contains(other)));
}

// The open menus a click on `link` (an <a href>, or nothing) closes: those that hold it.
export function toCloseOnLink(open, link) {
  return link ? open.filter((menu) => menu.contains(link)) : [];
}

const WIRED = Symbol.for('site-kit.menus');

// Registers the listeners on `doc` unless they are there already; true when it registered them.
export function wireMenus(doc) {
  if (doc[WIRED]) return false;
  doc[WIRED] = true;
  const openMenus = () => [...doc.querySelectorAll('details[data-kit-menu]')].filter((menu) => menu.open);
  const close = (menus) => { for (const menu of menus) menu.open = false; };
  doc.addEventListener('pointerdown', (event) => close(toCloseOnPress(openMenus(), event.target)));
  doc.addEventListener('click', (event) => {
    const link = typeof event.target?.closest === 'function' ? event.target.closest('a[href]') : null;
    close(toCloseOnLink(openMenus(), link));
  });
  doc.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    for (const menu of toCloseOnEscape(openMenus())) {
      const focusWasInside = menu.contains(doc.activeElement);
      menu.open = false;
      if (focusWasInside) menu.querySelector('summary')?.focus();
    }
  });
  return true;
}

if (typeof document !== 'undefined') wireMenus(document);
