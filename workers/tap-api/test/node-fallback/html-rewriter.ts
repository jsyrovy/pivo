// Minimal stand-in for workerd's HTMLRewriter, for the Node fallback pool only.
//
// It covers exactly what src/parsers/ambasada.ts asks for: descendant selectors built from
// tag/class/id compounds, `element` handlers with onEndTag(), and `text` handlers that fire for
// text inside a matched element. Everything is buffered, not streamed -- the parser awaits the
// whole body anyway.
//
// It is NOT an HTML5 tree builder. Text chunks are handed over raw (no entity decoding), and the
// only error recovery is the implicit-close rule below. Real lol-html does more, so a green run
// here is weaker evidence than a green `make test-tap-api`.

interface ShimElement {
  tagName: string;
  getAttribute(name: string): string | null;
  hasAttribute(name: string): boolean;
  onEndTag(handler: () => void): void;
}

interface ShimText {
  text: string;
  lastInTextNode: boolean;
}

interface Handlers {
  element?: (element: ShimElement) => void;
  text?: (text: ShimText) => void;
}

interface Compound {
  tag: string | null;
  id: string | null;
  classes: string[];
}

interface OpenElement {
  tag: string;
  id: string | null;
  classes: string[];
  endHandlers: Array<() => void>;
  matched: number[];
}

interface Rule {
  compounds: Compound[];
  handlers: Handlers;
  openCount: number;
}

const VOID_ELEMENTS = new Set([
  "area",
  "base",
  "br",
  "col",
  "embed",
  "hr",
  "img",
  "input",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr",
]);

// Tags that a sibling of the same kind closes implicitly. Enough to keep a real-world menu table
// from nesting every unclosed <td> inside the previous one.
const IMPLICITLY_CLOSED_BY_SIBLING = new Set(["td", "th", "tr", "li", "p", "option", "dt", "dd"]);

const RAW_TEXT_ELEMENTS = new Set(["script", "style", "textarea", "title"]);

const TOKEN_RE =
  /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<![^>]*>|<\/([a-zA-Z][-\w:]*)[^>]*>|<([a-zA-Z][-\w:]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/?)>/g;

const ATTR_RE = /([-\w:]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+))?/g;

function parseSelector(selector: string): Compound[] {
  return selector
    .trim()
    .split(/\s+/)
    .map((part) => {
      const tag = /^[a-zA-Z][-\w:]*/.exec(part);
      return {
        tag: tag ? tag[0].toLowerCase() : null,
        id: (/#([-\w]+)/.exec(part) ?? [])[1] ?? null,
        classes: [...part.matchAll(/\.([-\w]+)/g)].map((m) => m[1]),
      };
    });
}

function parseAttributes(raw: string): Map<string, string> {
  const attributes = new Map<string, string>();
  for (const match of raw.matchAll(ATTR_RE)) {
    const value = match[2] ?? "";
    const unquoted = /^["']/.test(value) ? value.slice(1, -1) : value;
    attributes.set(match[1].toLowerCase(), unquoted);
  }
  return attributes;
}

function compoundMatches(compound: Compound, element: OpenElement): boolean {
  if (compound.tag && compound.tag !== element.tag) return false;
  if (compound.id && compound.id !== element.id) return false;
  return compound.classes.every((c) => element.classes.includes(c));
}

// Descendant combinator only: every compound but the last must match some ancestor, in order.
function selectorMatches(compounds: Compound[], stack: OpenElement[]): boolean {
  const current = stack[stack.length - 1];
  if (!compoundMatches(compounds[compounds.length - 1], current)) return false;

  let remaining = compounds.length - 2;
  for (let i = stack.length - 2; i >= 0 && remaining >= 0; i--) {
    if (compoundMatches(compounds[remaining], stack[i])) remaining--;
  }
  return remaining < 0;
}

export class HTMLRewriterShim {
  private readonly rules: Rule[] = [];

  on(selector: string, handlers: Handlers): this {
    this.rules.push({ compounds: parseSelector(selector), handlers, openCount: 0 });
    return this;
  }

  transform(response: Response): Response {
    const rewriter = this;
    // Only .text() is ever awaited by the parser; the rest of Response is left to the original.
    return new Proxy(response, {
      get(target, property, receiver) {
        if (property === "text") {
          return async (): Promise<string> => {
            const html = await target.text();
            rewriter.run(html);
            return html;
          };
        }
        const value = Reflect.get(target, property, receiver) as unknown;
        return typeof value === "function" ? value.bind(target) : value;
      },
    });
  }

  private run(html: string): void {
    const stack: OpenElement[] = [];
    let cursor = 0;
    TOKEN_RE.lastIndex = 0;

    for (let match = TOKEN_RE.exec(html); match !== null; match = TOKEN_RE.exec(html)) {
      if (match.index > cursor) this.emitText(html.slice(cursor, match.index));
      cursor = TOKEN_RE.lastIndex;

      const [, closeTag, openTag, rawAttributes, selfClosing] = match;
      if (closeTag) {
        this.closeUpTo(stack, closeTag.toLowerCase());
      } else if (openTag) {
        const tag = openTag.toLowerCase();
        if (IMPLICITLY_CLOSED_BY_SIBLING.has(tag) && stack[stack.length - 1]?.tag === tag) {
          this.closeUpTo(stack, tag);
        }
        this.open(stack, tag, rawAttributes);
        if (selfClosing || VOID_ELEMENTS.has(tag)) {
          this.closeUpTo(stack, tag);
        } else if (RAW_TEXT_ELEMENTS.has(tag)) {
          const end = html.toLowerCase().indexOf(`</${tag}`, cursor);
          const stop = end === -1 ? html.length : end;
          this.emitText(html.slice(cursor, stop));
          cursor = stop;
          TOKEN_RE.lastIndex = stop;
        }
      }
    }

    if (cursor < html.length) this.emitText(html.slice(cursor));
    while (stack.length > 0) this.pop(stack);
  }

  private open(stack: OpenElement[], tag: string, rawAttributes: string): void {
    const attributes = parseAttributes(rawAttributes);
    const element: OpenElement = {
      tag,
      id: attributes.get("id") ?? null,
      classes: (attributes.get("class") ?? "").split(/\s+/).filter(Boolean),
      endHandlers: [],
      matched: [],
    };
    stack.push(element);

    const api: ShimElement = {
      tagName: tag,
      getAttribute: (name) => attributes.get(name.toLowerCase()) ?? null,
      hasAttribute: (name) => attributes.has(name.toLowerCase()),
      onEndTag: (handler) => element.endHandlers.push(handler),
    };

    this.rules.forEach((rule, index) => {
      if (!selectorMatches(rule.compounds, stack)) return;
      element.matched.push(index);
      rule.openCount++;
      rule.handlers.element?.(api);
    });
  }

  private closeUpTo(stack: OpenElement[], tag: string): void {
    const depth = stack.map((e) => e.tag).lastIndexOf(tag);
    if (depth === -1) return; // stray end tag
    while (stack.length > depth) this.pop(stack);
  }

  private pop(stack: OpenElement[]): void {
    const element = stack.pop();
    if (!element) return;
    for (const index of element.matched) this.rules[index].openCount--;
    for (const handler of element.endHandlers) handler();
  }

  private emitText(text: string): void {
    if (!text) return;
    for (const rule of this.rules) {
      if (rule.openCount > 0) rule.handlers.text?.({ text, lastInTextNode: false });
    }
  }
}
