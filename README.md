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
  links sit on the right (a site with one language has none). A site that fills its `languages`
  slot (`<LanguageMenu slot="languages" .../>`) gets that there instead.
- `site-kit/LanguageNav.astro`: the language links, a row of codes, and remembering the chosen
  language.
- `site-kit/LanguageMenu.astro`: the languages as a drop-down (the browser's own `<details>`): the
  current code, and open, every language under its own name; remembers the choice like the codes.
- `site-kit/LaneRow.astro`: the lanes under the header: a row of links while it fits, a picker
  showing the page's lane when it would overflow; the site passes the lanes, the picker's label and
  the row's name, its own items (a menu) in the slot, and `lang` when the labels are in another
  language than the page (on the labels only; the row's name stays in the page's language). Until its script measures the row, the
  site's CSS guesses: it shows the picker below the narrowest window its row fits, with
  `@media (width < …) { .kit-lane-row:not([data-lanes]) .kit-lanes { height: 0; visibility: hidden;
  overflow: hidden } .kit-lane-row:not([data-lanes]) .kit-lane-picker { display: block } }`.
- Menus: the drop-down, the lane picker and any `<details data-kit-menu>` of the site's close on a
  press outside them and on Escape (the innermost first, the focus back on its summary), and when a
  link in them is chosen.
- `site-kit/Pager.astro`: the page numbers under a list: ← and →, and at most seven numbers and
  "…" gaps between them; the site gives each page's address (`href`).
- `site-kit/RandomLink.astro` and `site-kit/RandomPage.astro`: Random. Every Random link is a plain
  link to `/random/` in its language (shown from two items); that page, the site's
  `src/pages/[...lang]/random.astro` drawing `RandomPage` with the slugs to pick from, is bare and
  jumps to one of them, never the page the visitor came from, before anything is drawn.
- `site-kit/SiteFooter.astro`: the footer: the site's links (About, say), then "© year name".
- `site-kit/NotFound.astro`: the body of the "page not found" page, in every language the site
  has: the message as a heading in the default language, a line for each other language, and a
  link to each language's home, named in that language. The site's `src/pages/404.astro` draws it
  inside its own layout.
- `scripts/wordmark.py <Archivo-VF.ttf> <text> <out>`: draws a text in Archivo Black Expanded as
  one SVG path in the text colour; with a site's `src/components/Wordmark.astro` as `<out>`, the
  output is the whole component. Run it from a site's folder beside the kit
  (`../site-kit/scripts/wordmark.py`); it needs fontTools and uharfbuzz and isn't installed into
  the sites.
- `site-kit/routes`: `robotsTxt()` and `langRedirect()` for `/robots.txt` and `/lang-redirect.js`
  (which sites need the second: `langRedirect()`'s comment).
- `site-kit/markdown`: rules for a site's Markdown processor (Markdown files, not MDX):
  `lineBreaks` keeps single line breaks; `noRawHtml` stops the build on raw HTML in a text;
  `figures(figure)` makes each image on a line of its own (a blank line before and after) the
  figure the site's `figure({ src, alt, title, file })` describes, and stops the build on an image
  anywhere else or written by reference. What stands inside an image's description is read as
  words: the processor flattens it to alt text, which `figure()` judges.
- `site-kit/headers`: `securityHeaders()`, an Astro integration that writes the shared `/*`
  security headers into `dist/_headers` ahead of the site's own rules.

## Look

The blocks use the site's `--paper`, `--ink` and `--ink-muted`, `--ink-faint` on a site with
language links or the drop-down, and these:

| Variable | Sets | Default |
|---|---|---|
| `--kit-wrap-max` | width of the header and footer rows | 72rem |
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
| `--kit-langmenu-font` | drop-down's font | inherit |
| `--kit-langmenu-size` | its size | .8125rem |
| `--kit-langmenu-tracking` | its letter spacing | .02em |
| `--kit-langmenu-pad` | the code's side padding | 0 |
| `--kit-langmenu-reach` | the code's tap area past the edge | 0px |
| `--kit-langmenu-chevron-gap` | space between the code and its chevron | .35rem |
| `--kit-langmenu-lift` | how far the list rises into the code's tap area | 0px |
| `--kit-langmenu-width` | the list's minimum width | 8.5rem |
| `--kit-langmenu-list-pad` | the list's padding above and below | .25rem |
| `--kit-langmenu-item-pad` | each name's side padding | 1rem |
| `--kit-langmenu-bg` | the list's background | `--paper` |
| `--kit-langmenu-border` | the list's border | 1px solid `--ink-faint` |
| `--kit-langmenu-underline-offset` | current name's underline gap | 4px |
| `--kit-langmenu-underline-thickness` | its thickness | 1px |
| `--kit-langmenu-hover` | the code's and a name's colour on hover | `--ink` |
| `--kit-lane-font` | lane row's font (the picker's too) | inherit |
| `--kit-lane-size` | its size | .8125rem |
| `--kit-lane-leading` | its line height | inherit |
| `--kit-lane-tracking` | its letter spacing | normal |
| `--kit-lane-case` | its text-transform | none |
| `--kit-lane-gap` | space between lanes | 1.5rem |
| `--kit-lane-align` | the row's, the picker's label's and its list's place: `start` or `center` | start |
| `--kit-lane-border` | line under the row | 0 |
| `--kit-lane-underline-offset` | current lane's underline gap | .4em |
| `--kit-lane-underline-thickness` | its thickness (`auto`: the font's own) | 1px |
| `--kit-lane-hover` | a lane's colour on hover | `--ink` |
| `--kit-lane-picker-end` | space under the picker's open list | .5rem |
| `--kit-skip-size` | skip link's text size | .875rem |
| `--kit-pager-item-width` | each page number's minimum width | 2.25rem |
| `--kit-pager-underline-offset` | current page's underline gap | .3em |

Reach variables and `--kit-langmenu-lift` need a unit (`0px`, not `0`): they are used in `calc()`.

## Checking the sites after a change

`npm test` runs the tests of the JavaScript modules (Node's own test runner) and of
`scripts/check_sites.py` (Python's `unittest`); neither needs a dependency.
`scripts/check_sites.py` builds each site before and after a change to a block and compares the
pages (head tags, header, content, CSS rules and scripts): run `before`, make the change, then run
`after` (or `after --release` once the sites install the released tag). `compare <build A> <build B>`
compares any two build folders. A planned change would hide what else changed, so `after` and
`compare` take it out of the comparison, each option repeatable and an error when it doesn't find
exactly what it names: `--without <tag>` or `--without <tag>.<class>` (cut those elements from both
builds, e.g. `--without footer`), `--changed-asset <name>` (the plain name without its hash, e.g.
`--changed-asset Base.css`: that asset may differ, its diff printed), `--renamed-asset <old> <new>`
(an asset that changed its name), `--new-asset <name>` (one the after build adds, its content
printed) and `--replace <old> <new>` (a wording changed on the before build's pages). The script's
`--help` says the details.
`scripts/measure-header.js` measures the header, its language links or drop-down, and what sits
between it and the page's content (a lane row) in a browser. Neither script is installed into the
sites.

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
