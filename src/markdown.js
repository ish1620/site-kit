// Markdown rules for Astro's built-in processor (Sätteri):
//   markdown: { processor: satteri({ mdastPlugins: [lineBreaks, noRawHtml, figures(figure)] }) }
// The rules are for Markdown files: they read the Markdown tree (mdast), where an MDX file's
// elements are other nodes, so on MDX they would see none of them.
import { fileURLToPath } from 'node:url';

// A single line break in the text stays a line break (<br>); a blank line still starts a new
// paragraph. Plain Markdown would join the lines into one paragraph, and browsers would put a
// stray space between Japanese sentences.
export const lineBreaks = {
  name: 'line-breaks',
  text(node, ctx) {
    if (!node.value.includes('\n')) return;
    ctx.replaceNode(
      node,
      node.value.split(/[\t ]*\r?\n[\t ]*/).flatMap((value, i) => [
        ...(i > 0 ? [{ type: 'break' }] : []),
        ...(value ? [{ type: 'text', value }] : []),
      ]),
    );
  },
};

// The path of the document being processed, for a refusal's message. A text with no file (a
// compile called without `fileURL`) stops the build: a message must say which file to fix.
function fileOf(ctx) {
  if (!ctx.fileURL) throw new Error('a Markdown text with no file: compile it with its fileURL, so a refusal can name the file');
  return fileURLToPath(ctx.fileURL);
}

// Raw HTML in a text (a block, an inline tag or a comment: each is an `html` node) stops the build.
// The text is all Markdown, so the other rules see everything it holds. What stands inside an
// image's description is no node: the processor flattens it to the image's alt text, where a tag
// is words, never markup, and the site's figure() judges it as alt text.
export const noRawHtml = {
  name: 'no-raw-html',
  // Every text has a file, raw HTML or not.
  before(root, ctx) {
    fileOf(ctx);
  },
  html(node, ctx) {
    // The start of the tag: its first line, up to its first ">", at most 80 characters.
    const start = node.value.trimStart().match(/^[^\n>]{0,80}>?/)[0];
    throw new Error(`${fileOf(ctx)}: raw HTML in a text: write it in Markdown (found ${start})`);
  },
};

const MISPLACED = 'an image stands on a line of its own, with a blank line before and after';

// An image on a line of its own, with a blank line before and after, is a figure: the image is the
// only child of a paragraph whose own parent is the text's root. Nothing nested counts, whatever
// it is nested in (a link, a heading, a list, a quote, a table). For each figure the rule calls the
// site's figure({ src, alt, title, file }): the image's address and alt text as written, its title
// (null when it has none, as for a title written ""), and the document's path. figure() throws to
// stop the build, or returns { class, src, width, height }: the paragraph becomes
// <figure class="…">, and the image takes the address, the size, loading="lazy" and
// decoding="async". Any other image node stops the build, and so does a reference-style one
// (![alt][name]): a figure is written one way. Code is no image: it holds text, not nodes. Nor is
// what stands inside an image's description: the processor flattens it to alt text before a rule
// sees it, so an image or a link written there leaves its words in `alt` and nothing on the page.
export function figures(figure) {
  return {
    name: 'figures',
    // Every text has a file, images or not.
    before(root, ctx) {
      fileOf(ctx);
    },
    image(node, ctx) {
      const file = fileOf(ctx);
      const paragraph = ctx.parent(node);
      const isFigure = paragraph?.type === 'paragraph' && paragraph.children.length === 1 && ctx.parent(paragraph)?.type === 'root';
      if (!isFigure) throw new Error(`${file}: ${MISPLACED}: ${node.url}`);
      const made = figure({ src: node.url, alt: node.alt, title: node.title, file });
      ctx.setProperty(paragraph, 'data', { hName: 'figure', hProperties: { class: made.class } });
      ctx.setProperty(node, 'url', made.src);
      ctx.setProperty(node, 'data', { hProperties: { width: made.width, height: made.height, loading: 'lazy', decoding: 'async' } });
    },
    imageReference(node, ctx) {
      throw new Error(`${fileOf(ctx)}: an image is written with its address, ![alt](/address), not by reference: ![${node.alt ?? ''}][${node.label ?? node.identifier}]`);
    },
  };
}
