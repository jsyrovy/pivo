import { describe, it, expect } from "vitest";
import { formatStyle } from "../src/style";

describe("formatStyle", () => {
  it("returns empty string for empty input", () => {
    expect(formatStyle("")).toBe("");
    expect(formatStyle("   ")).toBe("");
  });

  it("uppercases standalone acronyms", () => {
    expect(formatStyle("ipa")).toBe("IPA");
    expect(formatStyle("IPA")).toBe("IPA");
    expect(formatStyle("neipa")).toBe("NEIPA");
  });

  it("sentence-cases multi-word styles", () => {
    expect(formatStyle("pale ale")).toBe("Pale ale");
    expect(formatStyle("Pale Ale")).toBe("Pale ale");
    expect(formatStyle("stout s laktozou")).toBe("Stout s laktozou");
  });

  it("preserves acronyms in the middle of multi-word styles", () => {
    expect(formatStyle("hazy ipa")).toBe("Hazy IPA");
    expect(formatStyle("American IPA")).toBe("American IPA");
    expect(formatStyle("imperial neipa")).toBe("Imperial NEIPA");
  });

  it("handles Czech diacritics in sentence case", () => {
    expect(formatStyle("světlý ležák")).toBe("Světlý ležák");
    expect(formatStyle("PŠENIČNÉ pivo")).toBe("Pšeničné pivo");
  });

  it("treats acronyms with surrounding punctuation as acronyms", () => {
    expect(formatStyle("ipa,")).toBe("IPA,");
  });
});
