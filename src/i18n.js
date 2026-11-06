// Languages and the addresses built from them. A site picks its languages, in the order its
// language links show them, with defineLocales() in its src/config.ts. Plain JavaScript (types in
// i18n.d.ts) because astro.config.mjs loads it too, before any build tool runs.

// Every language a site can pick. Each one has:
// - tag: for lang="" and hreflang (BCP 47). zh-Hans makes browsers draw Simplified Chinese, not the
//   Japanese or Traditional forms of the same characters. The short code (zh) stays for addresses,
//   folders and the remembered choice.
// - og: its name in link previews (Open Graph).
// - name: the language in itself ("Español"): the language links' tooltip.
// - nameEn: in English ("Spanish"): the "originally written in" line, English on every page.
// - ui: the kit's own interface text in that language.
// A new language goes here once; then any site can add it to its list.
export const LANGUAGES = {
  en: { tag: 'en', og: 'en_US', name: 'English', nameEn: 'English', ui: { langNav: 'Language', skip: 'Skip to content' } },
  es: { tag: 'es', og: 'es_ES', name: 'Español', nameEn: 'Spanish', ui: { langNav: 'Idioma', skip: 'Saltar al contenido' } },
  ja: { tag: 'ja', og: 'ja_JP', name: '日本語', nameEn: 'Japanese', ui: { langNav: '言語', skip: '本文へ移動' } },
  zh: { tag: 'zh-Hans', og: 'zh_CN', name: '简体中文', nameEn: 'Chinese', ui: { langNav: '语言', skip: '跳到正文' } },
};

export function defineLocales({ locales, defaultLocale }) {
  for (const l of locales) {
    if (!Object.hasOwn(LANGUAGES, l)) throw new Error(`site-kit: unknown language "${l}". Add it to LANGUAGES in site-kit/src/i18n.js.`);
  }
  if (!locales.includes(defaultLocale)) throw new Error(`site-kit: the default language "${defaultLocale}" isn't in the list.`);
  const pick = (key) => Object.fromEntries(locales.map((l) => [l, LANGUAGES[l][key]]));
  const LANG_TAG = pick('tag');

  // "/" + path for the default language, "/es/", "/ja/" or "/zh/" + path for the others.
  // Addresses always end with "/".
  function localePath(lang, path = '') {
    const clean = path.replace(/^\/+|\/+$/g, '');
    const base = lang === defaultLocale ? '/' : `/${lang}/`;
    return clean ? `${base}${clean}/` : base;
  }

  return {
    LOCALES: locales,
    DEFAULT_LOCALE: defaultLocale,
    LANG_TAG,
    OG_LOCALE: pick('og'),
    LANG_NAME: pick('name'),
    LANG_NAME_EN: pick('nameEn'),
    KIT_UI: pick('ui'),
    localePath,
    // The language part of an address, for page files in src/pages/[...lang]/: nothing for the
    // default language, the code for the others.
    langParam: (lang) => (lang === defaultLocale ? undefined : lang),
    // For @astrojs/sitemap: sitemap({ i18n: i18n.sitemap }) links the language versions.
    sitemap: { defaultLocale, locales: LANG_TAG },
  };
}
