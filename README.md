# site-kit

Shared Astro building blocks for a few personal sites. Each block is built the same way on every
site; each site sets its look with `--kit-*` CSS variables. Made for those sites; not a
general-purpose package.

## Blocks

- `site-kit/i18n`: `defineLocales({ locales, defaultLocale })`: language tags, names, addresses
  (`localePath()`, `langParam()`, `staticPaths()` for a page in every language, `alternatesOf()`
  for the same page's other languages) and the sitemap's language settings.
- `site-kit/content`: for content kept in one folder per language (`<lang>/<slug>.md`):
  `langOf()`, `slugOf()`, `isScheduled()`, `languagesOf()`, and two build checks:
  `checkPublishDates()` (a date has a time and a time zone) and `checkTranslations()` (every
  language version's front matter matches the original's, apart from the translated fields). They
  work on the entries the site passes in.
- `site-kit/SiteHead.astro`: the tags a page's `<head>` starts with (title, description, icons,
  canonical, hreflang, link previews with an optional description of the image, JSON-LD).
- `site-kit/SkipLink.astro`: "Skip to content", shown on keyboard focus.
- `site-kit/SiteHeader.astro`: a sticky header; the slot is the site's name or logo, the language
  links sit on the right (a site with one language has none).
- `site-kit/LanguageNav.astro`: the language links, and remembering the chosen language.
- `site-kit/routes`: `robotsTxt()` and `langRedirect()` for `/robots.txt` and `/lang-redirect.js`
  (the second only on a site with more than one language).
- `site-kit/markdown`: `lineBreaks`, a Markdown rule that keeps single line breaks.
- `site-kit/headers`: `securityHeaders()`, an Astro integration that writes the shared `/*`
  security headers into `dist/_headers` ahead of the site's own rules.

## Look

The blocks use the site's `--paper`, `--ink`, `--ink-muted` and `--ink-faint`, and these:

| Variable | Sets | Default |
|---|---|---|
| `--kit-wrap-max` | width of the header row | 72rem |
| `--kit-wrap-pad` | its side padding | 1rem |
| `--kit-header-height` | header height (at least) | 3.5rem |
| `--kit-header-z` | header stacking | 10 |
| `--kit-header-border` | line under the header | 0 |
| `--kit-header-bg` | header background | `--paper` at 85% |
| `--kit-header-blur` | blur behind the header | 12px |
| `--kit-brand-reach` | name's tap area past its letters | 0px |
| `--kit-lang-font` | language codes' font | inherit |
| `--kit-lang-size` | their size | .8125rem |
| `--kit-lang-tracking` | their letter spacing | .02em |
| `--kit-lang-gap` | space between codes | 0 |
| `--kit-lang-pad` | each code's side padding | 0 |
| `--kit-lang-min-width` | each code's minimum width | 0 |
| `--kit-lang-reach` | last code's tap area past the edge | 0px |
| `--kit-lang-underline-offset` | current code's underline gap | 4px |
| `--kit-lang-underline-thickness` | its thickness | 1px |
| `--kit-lang-hover` | a code's colour on hover | `--ink` |
| `--kit-skip-size` | skip link's text size | .875rem |

Reach variables need a unit (`0px`, not `0`): they are used in `calc()`.

## Checking the sites after a change

`npm test` runs the tests of the JavaScript modules (Node's own test runner) and of
`scripts/check_sites.py` (Python's `unittest`); neither needs a dependency.
`scripts/check_sites.py` builds each site before and after a change to a block and compares the
pages (head tags, header, content, CSS rules and scripts); `scripts/measure-header.js` measures the
header in a browser. Neither is installed into the sites.

## Security headers

`securityHeaders()` writes the shared `/*` security-header block (strict CSP, `X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`,
`Cross-Origin-Resource-Policy`, `Strict-Transport-Security`) to `dist/_headers` ahead of the site's
own `public/_headers` rules (caching, `!` removals), and stops the build if a site rule sets a
header the block already sets.

The blocks contain no inline code. For the policy without `'unsafe-inline'`, the site also sets
`build: { inlineStylesheets: 'never' }` and `vite: { build: { assetsInlineLimit: 0 } }` in
`astro.config.mjs`, so Astro keeps every style and script in a file. A path that needs an
exception (for instance, an image loaded by another origin) drops the header after the block with
`! <Header>` in `public/_headers`.
