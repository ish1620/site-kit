// Security headers for every site. Call securityHeaders() in astro.config.mjs integrations;
// after the build, it writes the shared /* rule to dist/_headers ahead of the site's own rules
// (caching, ! removals) and stops if a site rule sets a header the block already sets.

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const BLOCK = `# Written by site-kit's securityHeaders() (src/headers.js) ahead of the site's own rules.
# Security headers, applied by Cloudflare (Workers static assets read this file).
/*
  # Everything comes from the site itself: no inline styles or scripts (astro.config.mjs keeps them
  # in files), no data: images, no forms. Anything Cloudflare injects (Web Analytics, Rocket Loader)
  # would be blocked too: add its address here if you ever turn one on.
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  Cross-Origin-Opener-Policy: same-origin
  # Other sites can't embed this site's files (hotlinking); a site lifts it for one path with
  # "! Cross-Origin-Resource-Policy" in its own _headers.
  Cross-Origin-Resource-Policy: same-origin
  # HTTPS only: browsers that have visited once never try plain http:// again (1 year).
  # http:// itself is redirected by Cloudflare's "Always Use HTTPS" setting.
  Strict-Transport-Security: max-age=31536000; includeSubDomains
`;

const BLOCK_HEADERS = new Set(
  BLOCK.split(/\r?\n/)
    .filter((line) => /^\s+[^#\s!]/.test(line) && line.includes(':'))
    .map((line) => line.slice(0, line.indexOf(':')).trim().toLowerCase()),
);

function checkOverrides(text) {
  let address = '(unknown)';
  for (const rawLine of text.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    if (!/^\s/.test(rawLine)) {
      address = trimmed;
      continue;
    }
    if (trimmed.startsWith('!')) continue;
    const colon = trimmed.indexOf(':');
    if (colon === -1) continue;
    const name = trimmed.slice(0, colon).trim();
    if (BLOCK_HEADERS.has(name.toLowerCase())) {
      throw new Error(
        `site _headers sets "${name}" on "${address}", which is already set by site-kit's securityHeaders()`,
      );
    }
  }
}

export function securityHeaders() {
  return {
    name: 'site-kit/security-headers',
    hooks: {
      'astro:build:done': async ({ dir }) => {
        const headersPath = path.join(fileURLToPath(dir), '_headers');
        let existing = '';
        try {
          existing = await readFile(headersPath, 'utf8');
        } catch (err) {
          if (err.code !== 'ENOENT') throw err;
        }
        const hasContent = existing.trim().length > 0;
        if (hasContent) checkOverrides(existing);
        const out = hasContent ? `${BLOCK}\n${existing}` : BLOCK;
        await writeFile(headersPath, out, 'utf8');
      },
    },
  };
}
