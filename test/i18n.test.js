// Tests for the address helpers in src/i18n.js. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { defineLocales } from '../src/i18n.js';

const i18n = defineLocales({ locales: ['en', 'es', 'ja', 'zh'], defaultLocale: 'en' });

test('staticPaths gives one page per language, the default language without a prefix', () => {
  assert.deepEqual(i18n.staticPaths(), [
    { params: { lang: undefined }, props: { lang: 'en' } },
    { params: { lang: 'es' }, props: { lang: 'es' } },
    { params: { lang: 'ja' }, props: { lang: 'ja' } },
    { params: { lang: 'zh' }, props: { lang: 'zh' } },
  ]);
  assert.deepEqual(i18n.staticPaths(['ja']), [{ params: { lang: 'ja' }, props: { lang: 'ja' } }]);
});

test('alternatesOf gives the same page in each language', () => {
  assert.deepEqual(i18n.alternatesOf(), { en: '/', es: '/es/', ja: '/ja/', zh: '/zh/' });
  assert.deepEqual(i18n.alternatesOf('/archive/', ['en', 'zh']), { en: '/archive/', zh: '/zh/archive/' });
  assert.deepEqual(i18n.alternatesOf('post-1', []), {});
});

test('another default language has no prefix of its own', () => {
  const ja = defineLocales({ locales: ['ja', 'en'], defaultLocale: 'ja' });
  assert.deepEqual(ja.staticPaths(), [
    { params: { lang: undefined }, props: { lang: 'ja' } },
    { params: { lang: 'en' }, props: { lang: 'en' } },
  ]);
  assert.deepEqual(ja.alternatesOf('about'), { ja: '/about/', en: '/en/about/' });
});
