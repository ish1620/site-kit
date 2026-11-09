// Helpers for content kept in one folder per language: src/content/<collection>/<lang>/<slug>.md,
// where the same slug in each language folder makes the files translations of each other.
// They work on the entries a site passes in (from getCollection()): the site decides what it reads
// and builds, these hold the rules. Plain JavaScript (types in content.d.ts), like i18n.js.
import { readFileSync } from 'node:fs';

// An entry's language and slug, from its id: "es/001" is "es" and "001".
export const langOf = (entry) => entry.id.split('/')[0];
export const slugOf = (entry) => entry.id.split('/').slice(1).join('/');

// Whether a date is still in the future. A build decides this once, when it starts, so its pages,
// lists and feeds agree even if a date passes mid-build; the dev server (dev = true) reads the
// clock each time.
const BUILD_TIME = Date.now();
export function isScheduled(date, dev = false) {
  return date.getTime() > (dev ? Date.now() : BUILD_TIME);
}

// The languages, in the site's order, that have an entry with this slug among the entries passed
// in. A site passes only what it builds, so a page never links to a version that isn't built.
export function languagesOf(entries, slug, locales) {
  return locales.filter((lang) => entries.some((entry) => langOf(entry) === lang && slugOf(entry) === slug));
}

// A date field must have a time and a time zone (2026-01-15T09:30:00+00:00, or Z for UTC; seconds
// and fractions optional). Without a zone the time is read as UTC, which can shift the date shown
// and the scheduling. The front matter's parser turns the value into a date before any schema sees
// it, so this reads the entry's file. Throws on the first entry without one, naming its file.
const DATE_WITH_ZONE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---[\t ]*(\r?\n|$)/;
export function checkPublishDates(entries, field = 'publishDate') {
  // In multiline mode $ stops before \r too, so lines ending \r\n need nothing extra.
  const line = new RegExp(`^${field}:[\\t ]*(.*?)[\\t ]*$`, 'm');
  for (const entry of entries) {
    const file = entry.filePath ?? entry.id;
    const text = entry.filePath ? readFileSync(entry.filePath, 'utf8').replace(/^﻿/, '') : '';
    const frontMatter = text.match(FRONT_MATTER)?.[1] ?? '';
    const value = (frontMatter.match(line)?.[1] ?? '').replace(/^(['"])(.*)\1$/, '$2');
    if (!DATE_WITH_ZONE.test(value)) {
      throw new Error(`${file}: ${field} needs a time and a time zone, e.g. 2026-01-15T09:30:00+00:00 (found "${value}").`);
    }
  }
}

// Every language version of an entry has the same front matter, apart from the fields that are
// translated. Each version is compared with the original: the version in the language
// originalLang(entry) names (by default the entry's own `original` field), or the first version
// passed in when there is none in that language. Compared: every field except those in `except`,
// or, when given, only those in `only`. A field set in one file and not in the other is a
// difference. Values are compared as JSON with object keys sorted, dates as ISO strings. Throws on
// the first difference, naming both files, the field and both values, so a cover, date or setting
// changed in one language and forgotten in another stops the build instead of showing differently.
export function checkTranslations(entries, { except = [], only, originalLang = (entry) => entry.data.original } = {}) {
  const bySlug = new Map();
  for (const entry of entries) bySlug.set(slugOf(entry), [...(bySlug.get(slugOf(entry)) ?? []), entry]);
  const rule = only
    ? `${only.join(', ')} must be the same in every language`
    : except.length
      ? `Every field but ${except.join(', ')} must be the same in every language`
      : 'The front matter must be the same in every language';
  for (const versions of bySlug.values()) {
    const original = versions.find((entry) => langOf(entry) === originalLang(entry));
    const reference = original ?? versions[0];
    for (const entry of versions) {
      if (entry === reference) continue;
      const fields = only ?? [...new Set([...Object.keys(reference.data), ...Object.keys(entry.data)])].filter((f) => !except.includes(f));
      for (const field of fields) {
        const value = comparable(entry.data[field]);
        const expected = comparable(reference.data[field]);
        if (value === expected) continue;
        throw new Error(
          `${entry.filePath ?? entry.id}: ${field} is ${value ?? '(not set)'}, but in ${reference.filePath ?? reference.id}` +
          `${original ? ' (the original)' : ''} it is ${expected ?? '(not set)'}. ${rule}.`,
        );
      }
    }
  }
}

// A value as JSON with every object's keys in order, so two objects that differ only in key order
// compare equal. Dates become ISO strings (JSON does that by itself). undefined stays undefined.
const sortKeys = (key, value) => (value && typeof value === 'object' && !Array.isArray(value)
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
  : value);
const comparable = (value) => (value === undefined ? undefined : JSON.stringify(value, sortKeys));
