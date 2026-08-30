import { describe, it, expect } from "vitest";
import { categorizeStyle, type StyleCategory } from "../src/style";
import { STYLE_CORPUS } from "./fixtures";

const EMPTY_STYLE_LABEL = "(bez stylu)";

const CATEGORY_ORDER: readonly StyleCategory[] = [
  "nealko", "sour", "dark", "ale", "lezak", "other",
];

interface Bucket {
  beers: number;
  styles: Record<string, number>;
}

function categorizeCorpus(): Record<string, Bucket> {
  const buckets: Record<string, Bucket> = {};
  for (const category of CATEGORY_ORDER) {
    buckets[category] = { beers: 0, styles: {} };
  }

  for (const [style, count] of Object.entries(STYLE_CORPUS)) {
    const bucket = buckets[categorizeStyle(style)];
    bucket.beers += count;
    bucket.styles[style || EMPTY_STYLE_LABEL] = count;
  }

  return buckets;
}

// The corpus is real tap-list data, so this snapshot is the full record of what the rules do to
// every style string we have ever seen. Any later change to the rule table shows up here as named
// styles moving between categories -- read that diff before accepting it.
describe("style corpus", () => {
  it("splits every real style string into categories", () => {
    expect(categorizeCorpus()).toMatchSnapshot();
  });

  it("assigns every beer in the corpus to exactly one category", () => {
    const buckets = categorizeCorpus();
    const beers = Object.values(buckets).reduce((sum, bucket) => sum + bucket.beers, 0);
    const styles = Object.values(buckets).reduce((sum, bucket) => sum + Object.keys(bucket.styles).length, 0);

    // Derived from the corpus, not hardcoded: the claim under test is that the rules partition it,
    // which stays true -- and stays worth asserting -- whatever size the corpus grows to.
    expect(beers).toBe(Object.values(STYLE_CORPUS).reduce((sum, count) => sum + count, 0));
    expect(styles).toBe(Object.keys(STYLE_CORPUS).length);
  });
});
