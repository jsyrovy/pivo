import { afterAll } from "vitest";
import { HTMLRewriterShim } from "./html-rewriter";
import { fetchMock } from "./cloudflare-test";

// workers-types declares HTMLRewriter as an ambient global, not as a property of globalThis, so
// the assignment needs the cast even though the name resolves fine in src/.
(globalThis as unknown as { HTMLRewriter: unknown }).HTMLRewriter = HTMLRewriterShim;

afterAll(() => {
  fetchMock.deactivate();
});
