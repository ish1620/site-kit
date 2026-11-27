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

test('each language is named in itself, Chinese as 中文', () => {
  assert.deepEqual(i18n.LANG_NAME, { en: 'English', es: 'Español', ja: '日本語', zh: '中文' });
});

test('the not-found page has its message and its link home in every language, word for word', () => {
  assert.deepEqual(
    Object.fromEntries(i18n.LOCALES.map((l) => [l, [i18n.KIT_UI[l].notFound, i18n.KIT_UI[l].home]])),
    {
      en: ['Page not found', '← Home'],
      es: ['Página no encontrada', '← Inicio'],
      ja: ['ページが見つかりません', '← ホーム'],
      zh: ['页面未找到', '← 首页'],
    },
  );
});
