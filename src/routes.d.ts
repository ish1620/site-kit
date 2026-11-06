import type { Locales } from './i18n.js';

export declare function robotsTxt(site: URL | undefined): Response;
export declare function langRedirect(i18n: Pick<Locales<any>, 'LOCALES' | 'DEFAULT_LOCALE' | 'localePath'>): Response;
