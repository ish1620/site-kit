// Markdown rules for Astro's built-in processor (Sätteri):
//   markdown: { processor: satteri({ mdastPlugins: [lineBreaks] }) }

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
