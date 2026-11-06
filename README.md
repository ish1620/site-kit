# site-kit

Shared Astro building blocks for ishokutani.com and calle.ishokutani.com. Each block is built the
same way on every site; each site sets its look with `--kit-*` CSS variables. Made for these two
sites; not a general-purpose package.

## Blocks

- `site-kit/i18n`: `defineLocales({ locales, defaultLocale })`: language tags, names, addresses
  (`localePath()`, `langParam()`) and the sitemap's language settings.
- `site-kit/SiteHead.astro`: the tags a page's `<head>` starts with (title, description, icons,
  canonical, hreflang, link previews, JSON-LD).
- `site-kit/SkipLink.astro`: "Skip to content", shown on keyboard focus.
- `site-kit/SiteHeader.astro`: a sticky header; the slot is the site's name or logo, the language
  links sit on the right.
- `site-kit/LanguageNav.astro`: the language links, and remembering the chosen language.
- `site-kit/routes`: `robotsTxt()` and `langRedirect()` for `/robots.txt` and `/lang-redirect.js`.
- `site-kit/markdown`: `lineBreaks`, a Markdown rule that keeps single line breaks.

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

`scripts/check_sites.py` builds each site before and after a change to a block and compares the
pages (head tags, header, content, CSS rules and scripts); `scripts/measure-header.js` measures the
header in a browser. Neither is installed into the sites.

## Strict Content Security Policy

The blocks contain no inline code. For a policy without `'unsafe-inline'`, the site also sets
`build: { inlineStylesheets: 'never' }` and `vite: { build: { assetsInlineLimit: 0 } }` in
`astro.config.mjs`, so Astro keeps every style and script in a file.
