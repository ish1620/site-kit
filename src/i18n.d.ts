export type LanguageCode = 'en' | 'es' | 'ja' | 'zh';

export interface KitUI {
  langNav: string;
  skip: string;
}

export interface Language {
  tag: string;
  og: string;
  name: string;
  nameEn: string;
  ui: KitUI;
}

export declare const LANGUAGES: Record<LanguageCode, Language>;

export interface Locales<L extends LanguageCode = LanguageCode> {
  /** The site's languages, in the order the language links show them. */
  LOCALES: readonly [L, ...L[]];
  DEFAULT_LOCALE: L;
  LANG_TAG: Record<L, string>;
  OG_LOCALE: Record<L, string>;
  LANG_NAME: Record<L, string>;
  LANG_NAME_EN: Record<L, string>;
  KIT_UI: Record<L, KitUI>;
  localePath(lang: L, path?: string): string;
  langParam(lang: L): L | undefined;
  /** One page per language (every language by default): `export function getStaticPaths() { return staticPaths(); }` */
  staticPaths(langs?: readonly L[]): { params: { lang: L | undefined }; props: { lang: L } }[];
  /** The same page's address in each language (every language by default), for `alternates`. */
  alternatesOf(path?: string, langs?: readonly L[]): Partial<Record<L, string>>;
  sitemap: { defaultLocale: L; locales: Record<L, string> };
}

export declare function defineLocales<const L extends LanguageCode>(config: {
  locales: readonly [L, ...L[]];
  defaultLocale: NoInfer<L>;
}): Locales<L>;
