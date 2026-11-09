/** What these helpers need of a content entry (Astro's collection entries have it). */
export interface ContentEntry {
  /** "<lang>/<slug>", e.g. "es/001". */
  id: string;
  /** The entry's file, relative to the site's folder. */
  filePath?: string;
  data: Record<string, any>;
}

export declare function langOf(entry: { id: string }): string;
export declare function slugOf(entry: { id: string }): string;

/** True while `date` is in the future: by the build's start time, or by the clock when `dev`. */
export declare function isScheduled(date: Date, dev?: boolean): boolean;

/** The languages, in the order of `locales`, that have an entry with this slug among `entries`. */
export declare function languagesOf<L extends string>(entries: readonly { id: string }[], slug: string, locales: readonly L[]): L[];

/** Throws, naming the file, when an entry's date field (publishDate by default) has no time and time zone. */
export declare function checkPublishDates(entries: readonly ContentEntry[], field?: string): void;

export interface TranslationCheck {
  /** Fields that may differ between languages (the translated ones). */
  except?: readonly string[];
  /** When given, only these fields are compared (and `except` is ignored). */
  only?: readonly string[];
  /** The language of the version the others are compared with; by default the entry's `original` field. */
  originalLang?: (entry: ContentEntry) => string | undefined;
}

/** Throws, naming both files and the field, when a language version's front matter differs from the original's. */
export declare function checkTranslations(entries: readonly ContentEntry[], options?: TranslationCheck): void;
