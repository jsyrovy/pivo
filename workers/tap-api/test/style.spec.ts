import { describe, it, expect } from "vitest";
import { extractStyleFromName, formatStyle } from "../src/style";

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

describe("extractStyleFromName", () => {
  it("splits a trailing single-word style", () => {
    expect(extractStyleFromName("Otakar Ležák")).toEqual({
      name: "Otakar",
      style: "Ležák",
    });
  });

  it("keeps modifiers attached to the core style", () => {
    expect(extractStyleFromName("Hex Modern Pale Ale")).toEqual({
      name: "Hex",
      style: "Modern Pale Ale",
    });
    expect(extractStyleFromName("Wai-Wai Hazy IPA")).toEqual({
      name: "Wai-Wai",
      style: "Hazy IPA",
    });
    expect(extractStyleFromName("Záviš Nefiltr Ležák")).toEqual({
      name: "Záviš",
      style: "Nefiltr Ležák",
    });
  });

  it("keeps the whole name when the style is the only information", () => {
    expect(extractStyleFromName("APA")).toEqual({ name: "APA", style: "APA" });
  });

  it("returns no style when the name has none", () => {
    expect(extractStyleFromName("Nealko")).toEqual({
      name: "Nealko",
      style: "Nealko",
    });
    expect(extractStyleFromName("Kingswood")).toEqual({
      name: "Kingswood",
      style: "",
    });
  });

  it("ignores a trailing modifier without a core style word", () => {
    expect(extractStyleFromName("Something Dry")).toEqual({
      name: "Something Dry",
      style: "",
    });
  });

  it("handles empty input", () => {
    expect(extractStyleFromName("")).toEqual({ name: "", style: "" });
  });
});
