import { describe, it, expect } from "vitest";
import { normalizeBreweries } from "../src/brewery";
import { BREWERY_CORPUS } from "./fixtures";

// key -> name -> raw strings that produced it. Sorted, so the snapshot only moves when a
// normalization does.
function groupCorpus(): Record<string, Record<string, string[]>> {
  const groups: Record<string, Record<string, string[]>> = {};
  for (const raw of BREWERY_CORPUS) {
    for (const { key, name } of normalizeBreweries(raw)) {
      ((groups[key] ??= {})[name] ??= []).push(raw);
    }
  }
  return Object.fromEntries(
    Object.keys(groups)
      .sort()
      .map((key) => [
        key,
        Object.fromEntries(
          Object.keys(groups[key])
            .sort()
            .map((name) => [name, [...groups[key][name]].sort()]),
        ),
      ]),
  );
}

// The corpus is every brewery string the pubs have ever sent, so this snapshot shows at a glance
// which spellings merged into one key and which did not -- a brewery listed under two keys is a
// missing alias.
describe("brewery corpus", () => {
  it("groups every real brewery string by key", () => {
    expect(groupCorpus()).toMatchSnapshot();
  });

  it("gives every string in the corpus at least one brewery", () => {
    expect(BREWERY_CORPUS.filter((raw) => normalizeBreweries(raw).length === 0)).toEqual([]);
  });
});
