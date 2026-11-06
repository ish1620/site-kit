// Small files every site serves. Each site keeps a one-line page file that calls these, e.g.
// src/pages/robots.txt.ts: export const GET = ({ site }) => robotsTxt(site);

// /robots.txt: everything may be crawled; the sitemap lists the pages that should be found. Pages
// kept out of search say so themselves (noindex).
export function robotsTxt(site) {
  const body = `User-agent: *\nAllow: /\n\nSitemap: ${new URL('sitemap-index.xml', site).href}\n`;
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}

// /lang-redirect.js: opens the bare home page (/) in the language the visitor last chose.
// LanguageNav saves the choice in the visitor's own browser (localStorage "lang") when they click a
// language code; nothing is sent anywhere, no cookies. SiteHead loads this file at the very top of
// the default language's home page only, as a plain blocking script, so the jump happens before
// that page is drawn. It does nothing when:
// - the site is already running (in-site navigation with Astro's ClientRouter, where the referrer
//   stays the first page's; LanguageNav's script sets window.siteKitLoaded),
// - the visitor came from another page of this site (they chose to go home, e.g. in a new tab),
// - nothing (or the default language, or an unknown value) is saved, or storage is blocked.
// While the jump happens the page is hidden, so a slow connection can't flash it; it shows again
// after 3s in case the jump is stopped.
export function langRedirect({ LOCALES, DEFAULT_LOCALE, localePath }) {
  const homes = Object.fromEntries(LOCALES.filter((l) => l !== DEFAULT_LOCALE).map((l) => [l, localePath(l)]));
  const script = `(function () {
  try {
    if (window.siteKitLoaded) return;
    if (document.referrer && new URL(document.referrer).origin === location.origin) return;
    var homes = ${JSON.stringify(homes)};
    var lang = localStorage.getItem('lang');
    if (lang && Object.prototype.hasOwnProperty.call(homes, lang)) {
      location.replace(homes[lang] + location.search + location.hash);
      var root = document.documentElement;
      root.style.visibility = 'hidden';
      setTimeout(function () { root.style.visibility = ''; }, 3000);
    }
  } catch (e) {}
})();
`;
  return new Response(script, { headers: { 'Content-Type': 'text/javascript; charset=utf-8' } });
}
