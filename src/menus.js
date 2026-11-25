// Closing menus: every <details data-kit-menu> on the page (LanguageMenu, LaneRow's picker, a
// site's own menu). The browser's <details> opens and closes them; this closes them where a menu
// is expected to close:
// - a press outside an open menu closes it: on the press itself (a tap on plain text sends no
//   click in Safari on a phone), or, when the press is on something that acts on a click (a link,
//   a button, a summary, a form field or label, or inside one), on that click instead. A menu
//   that sits in the page's flow (the lane picker) moves what is below it as it closes: closed on
//   the press, the release would land on something else, and the tap would be lost. A press inside
//   a menu leaves it and the menus around it open, so a press in the picker outside a menu nested
//   in it closes only the nested one;
// - Escape closes the innermost open menu, and puts the focus back on its summary when the focus
//   was inside it;
// - a click on a link inside an open menu closes it, so the page the browser keeps for the back
//   button shows it closed.
// The decisions are the pure functions below. The page wiring (wireMenus) registers once per
// document, so two bundles that both import this module can't double it, and does nothing
// outside a browser.

// What acts on a click: an outside press on it closes the menus on the click, not the press.
export const INTERACTIVE = 'a[href], button, summary, input, select, textarea, label';
const closestTo = (target, selector) => (typeof target?.closest === 'function' ? target.closest(selector) : null);

// The open menus a press on `target` closes: those that don't hold it, unless it acts on a click.
export function toCloseOnPress(open, target) {
  if (closestTo(target, INTERACTIVE)) return [];
  return open.filter((menu) => !(target && menu.contains(target)));
}

// The open menus Escape closes: the innermost, those that hold no other open menu.
export function toCloseOnEscape(open) {
  return open.filter((menu) => !open.some((other) => other !== menu && menu.contains(other)));
}

// The open menus a click on `target` closes: those that don't hold it (an outside press the press
// itself left open), and those that hold the link it chooses.
export function toCloseOnClick(open, target) {
  const link = closestTo(target, 'a[href]');
  return open.filter((menu) => !(target && menu.contains(target)) || (link && menu.contains(link)));
}

const WIRED = Symbol.for('site-kit.menus');

// Registers the listeners on `doc` unless they are there already; true when it registered them.
export function wireMenus(doc) {
  if (doc[WIRED]) return false;
  doc[WIRED] = true;
  const openMenus = () => [...doc.querySelectorAll('details[data-kit-menu]')].filter((menu) => menu.open);
  const close = (menus) => { for (const menu of menus) menu.open = false; };
  doc.addEventListener('pointerdown', (event) => close(toCloseOnPress(openMenus(), event.target)));
  doc.addEventListener('click', (event) => close(toCloseOnClick(openMenus(), event.target)));
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
