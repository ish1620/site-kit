// The parts of the processor's rule context (Sätteri's mdast visitor) the rules use.
interface RuleContext {
  readonly fileURL: URL | undefined;
  parent(node: unknown): { type: string; children: readonly unknown[] } | undefined;
  replaceNode(node: unknown, replacement: unknown[]): void;
  setProperty(node: unknown, key: string, value: unknown): void;
}

export declare const lineBreaks: {
  name: string;
  text(node: { value: string }, ctx: RuleContext): void;
};

export declare const noRawHtml: {
  name: string;
  html(node: { value: string }, ctx: RuleContext): void;
};

// An image that is a figure, as the Markdown wrote it, and the path of its document.
export interface FigureImage {
  src: string;
  alt: string | null;
  // null when there is none (and when the Markdown wrote "").
  title: string | null;
  file: string;
}

// What the site writes for a figure: the <figure>'s class, and the image's address and size.
export interface Figure {
  class: string;
  src: string;
  width: number;
  height: number;
}

export declare function figures(figure: (image: FigureImage) => Figure): {
  name: string;
  image(node: { url: string; alt: string | null; title: string | null }, ctx: RuleContext): void;
  imageReference(node: { alt: string | null; label?: string | null; identifier: string }, ctx: RuleContext): void;
};
