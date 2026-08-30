import { describe, it, expect } from "vitest";
import { categorizeStyle, extractStyleFromName, formatStyle, inferStyleFromDegree } from "../src/style";

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

describe("inferStyleFromDegree", () => {
  it("labels 0° as Nealko", () => {
    expect(inferStyleFromDegree(0)).toBe("Nealko");
  });

  it("returns no style for any other degree or unknown degree", () => {
    expect(inferStyleFromDegree(11)).toBe("");
    expect(inferStyleFromDegree(null)).toBe("");
  });
});

describe("categorizeStyle", () => {
  it("categorizes the plain styles", () => {
    expect(categorizeStyle("Ležák světlý")).toBe("lezak");
    expect(categorizeStyle("Italian pilsner")).toBe("lezak");
    expect(categorizeStyle("Světlé výčepní")).toBe("lezak");
    expect(categorizeStyle("Session IPA")).toBe("ale");
    expect(categorizeStyle("Pale ale")).toBe("ale");
    expect(categorizeStyle("Pastry sour")).toBe("sour");
    expect(categorizeStyle("Nealko")).toBe("nealko");
  });

  it("prefers sour over ale and wheat", () => {
    expect(categorizeStyle("Fruit sour ale")).toBe("sour");
    expect(categorizeStyle("Fruited berliner weisse")).toBe("sour");
    expect(categorizeStyle("Lehký sour ale s bezovým květem a maracujou")).toBe("sour");
  });

  it("treats anything dark as dark, colour before fermentation", () => {
    expect(categorizeStyle("Tmavý porter ochuc. třešněmi")).toBe("dark");
    expect(categorizeStyle("Ochucené tm. pivo")).toBe("dark");
    expect(categorizeStyle("Polotmavý ležák")).toBe("dark");
    expect(categorizeStyle("Czech amber lager")).toBe("dark");
    expect(categorizeStyle("Rotbier")).toBe("dark");
    expect(categorizeStyle("Stout s laktozou, malinami a vanilkou")).toBe("dark");
  });

  it("keeps red out of dark", () => {
    expect(categorizeStyle("Red APA")).toBe("ale");
  });

  it("reads a bare hazy as an ale", () => {
    expect(categorizeStyle("Hazy ale")).toBe("ale");
    expect(categorizeStyle("Session hazy")).toBe("ale");
  });

  it("keeps every pale lager in ležáky, hopped or not", () => {
    expect(categorizeStyle("India pale lager")).toBe("lezak");
    expect(categorizeStyle("IPL")).toBe("lezak");
    expect(categorizeStyle("New zealand pale lager")).toBe("lezak");
  });

  it("keeps wheat and Belgian specials out of ale", () => {
    expect(categorizeStyle("Weizenbier")).toBe("other");
    expect(categorizeStyle("German hefeweizen")).toBe("other");
    expect(categorizeStyle("Witbier")).toBe("other");
    expect(categorizeStyle("Hoppy saison ale")).toBe("other");
    expect(categorizeStyle("Farmhouse ale")).toBe("other");
  });

  it("survives typos in the qualifier", () => {
    expect(categorizeStyle("Ležák světiý")).toBe("lezak");
    expect(categorizeStyle("Sessiin NEIPA")).toBe("ale");
    expect(categorizeStyle("Singl hop ale")).toBe("ale");
  });

  it("splits on punctuation, not just spaces", () => {
    expect(categorizeStyle("Ipa/dipa")).toBe("ale");
    expect(categorizeStyle("Gose sour - ibišek+koriandr+limeta+yuzu")).toBe("sour");
    expect(categorizeStyle("Gluten-free session IPA")).toBe("ale");
  });

  it("falls back to other for style text that says nothing about the beer", () => {
    expect(categorizeStyle("")).toBe("other");
    expect(categorizeStyle("25l")).toBe("other");
    expect(categorizeStyle("malinami a vanilkou")).toBe("other");
  });
});
