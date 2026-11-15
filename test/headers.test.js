// Tests for src/headers.js. Run with `npm test`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { securityHeaders } from '../src/headers.js';

async function runHook(initialHeaders) {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'site-kit-headers-'));
  try {
    if (initialHeaders !== null) {
      await writeFile(path.join(dir, '_headers'), initialHeaders, 'utf8');
    }
    const integration = securityHeaders();
    await integration.hooks['astro:build:done']({ dir: pathToFileURL(`${dir}/`) });
    return await readFile(path.join(dir, '_headers'), 'utf8');
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test('writes the block alone when the site has no _headers', async () => {
  const out = await runHook(null);
  assert.match(out, /^# Written by site-kit's securityHeaders\(\)/);
  assert.match(out, /\n\/\*\n/);
  assert.match(out, /Content-Security-Policy: default-src 'none'/);
  assert.match(out, /Strict-Transport-Security: max-age=31536000; includeSubDomains\n$/);
});

test('puts the block first and keeps the site rules unchanged and in order', async () => {
  const siteRules = [
    '# Site caching rules',
    '/_astro/*',
    '  Cache-Control: public, max-age=31536000, immutable',
    '/images/*',
    '  Cache-Control: public, max-age=86400',
    '',
  ].join('\n');
  const out = await runHook(siteRules);
  assert.ok(out.startsWith("# Written by site-kit's securityHeaders()"));
  assert.ok(out.endsWith(`\n\n${siteRules}`));
  assert.ok(out.indexOf('/*') < out.indexOf('/_astro/*'));
  assert.ok(out.indexOf('/_astro/*') < out.indexOf('/images/*'));
});

test('throws, naming the header and rule address, when a site rule sets a block header', async () => {
  const siteRules = '/special/*\n  X-Frame-Options: SAMEORIGIN\n';
  await assert.rejects(
    () => runHook(siteRules),
    (err) => err instanceof Error && err.message.includes('X-Frame-Options') && err.message.includes('/special/*'),
  );
});

test('throws when a site rule sets a block header in another letter case', async () => {
  const siteRules = '/other/*\n  content-security-policy: default-src *\n';
  await assert.rejects(
    () => runHook(siteRules),
    (err) => err instanceof Error && err.message.includes('content-security-policy') && err.message.includes('/other/*'),
  );
});

test('allows a removal (!) of a block header', async () => {
  const siteRules = '/photos/:post/og.jpg\n  ! Cross-Origin-Resource-Policy\n';
  const out = await runHook(siteRules);
  assert.ok(out.endsWith(`\n\n${siteRules}`));
});

test('allows a near-miss header whose name only starts like one in the block', async () => {
  const siteRules = '/api/*\n  X-Frame-Options-Extra: keep\n  Content-Security-Policy-Report-Only: default-src *\n';
  const out = await runHook(siteRules);
  assert.ok(out.endsWith(`\n\n${siteRules}`));
});

test('ignores comments even when they mention block header names', async () => {
  const siteRules = '# X-Frame-Options: DENY\n/assets/*\n  # Content-Security-Policy: none\n  Cache-Control: public, max-age=3600\n';
  const out = await runHook(siteRules);
  assert.ok(out.endsWith(`\n\n${siteRules}`));
});

test('handles CRLF line endings for both valid rules and overrides', async () => {
  const validCrlf = '/_astro/*\r\n  Cache-Control: public, max-age=31536000, immutable\r\n';
  const out = await runHook(validCrlf);
  assert.ok(out.endsWith(`\n\n${validCrlf}`));

  const invalidCrlf = '/crlf/*\r\n  Referrer-Policy: no-referrer\r\n';
  await assert.rejects(
    () => runHook(invalidCrlf),
    (err) => err instanceof Error && err.message.includes('Referrer-Policy') && err.message.includes('/crlf/*'),
  );
});
