// Remember the language a visitor switches to, from the language links (LanguageNav) or the
// drop-down (LanguageMenu): one word in the visitor's own browser, never sent anywhere; no cookies.
// Only a plain click that switches this page counts; opening a language in a new tab
// (cmd/ctrl/shift-click, middle-click) doesn't. data-lang holds the short code ("zh"), which
// /lang-redirect.js looks up; hreflang holds the full tag ("zh-Hans").
// Both components import this module from their bundled <script>, so a strict Content Security
// Policy allows it; it registers once per document, and nothing outside a browser.

const LINK = ':is(.kit-langs, .kit-langmenu) a[data-lang]';

// The language a click chooses, or undefined when it chooses none.
export function chosenLanguage(event) {
  if (event.button || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return undefined;
  const link = typeof event.target?.closest === 'function' ? event.target.closest(LINK) : null;
  return link?.getAttribute('data-lang') || undefined;
}

const WIRED = Symbol.for('site-kit.remember-lang');

// Registers the listener on `doc` unless it is there already, so two bundles that both import this
// module can't double it; true when it registered it.
export function wireLanguageMemory(doc) {
  if (doc[WIRED]) return false;
  doc[WIRED] = true;
  doc.addEventListener('click', (event) => {
    const lang = chosenLanguage(event);
    if (lang) try { localStorage.setItem('lang', lang); } catch { /* storage blocked: nothing saved */ }
  });
  return true;
}

if (typeof document !== 'undefined') wireLanguageMemory(document);
