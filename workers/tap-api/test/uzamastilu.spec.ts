import { describe, it, expect } from "vitest";
import { parseUzamastiluJson } from "../src/parsers/uzamastilu";
import { UZAMASTILU_FIXTURE } from "./fixtures";

describe("parseUzamastiluJson", () => {
  it("filters out taps with order outside 1-7", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers.map((b) => b.order)).toEqual([1, 5, 3]);
  });

  it("cleans stray asterisks and whitespace from name", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers[0].name).toBe("APA");
    expect(beers[1].name).toBe("Záviš");
  });

  it("parses degree as leading number, including 00°", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers[0].degreePlato).toBe(14);
    expect(beers[2].degreePlato).toBe(0);
  });

  it("uses price05 directly as halfLiterCzk with price03 as secondary", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers[0].pricing).toEqual({
      halfLiterCzk: 70,
      reference: null,
      secondary: { priceCzk: 58, volumeLiters: 0.3 },
    });
  });

  it("returns pricing with secondary=null when price03 missing", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers[2].pricing).toEqual({
      halfLiterCzk: 35,
      reference: null,
      secondary: null,
    });
  });

  it("falls back to price03 when price05 missing", () => {
    const beers = parseUzamastiluJson([
      { order: 1, degree: "11°", brewery: "X", name: "Y", price05: "", price03: "45" },
    ]);
    expect(beers[0].pricing).toEqual({
      halfLiterCzk: 75,
      reference: { priceCzk: 45, volumeLiters: 0.3 },
      secondary: null,
    });
  });

  it("tags source as uzamastilu", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers.every((b) => b.source === "uzamastilu")).toBe(true);
  });

  it("detects the style folded into the beer name", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers[0].style).toBe("APA");
    expect(beers[1].style).toBe("Nefiltr ležák");
  });

  it("never exposes abv since the API does not expose it", () => {
    const beers = parseUzamastiluJson(UZAMASTILU_FIXTURE);
    expect(beers.every((b) => b.abv === null)).toBe(true);
  });

  it("splits name and style for a trailing multi-word style", () => {
    const beers = parseUzamastiluJson([
      { order: 1, name: "Hex Modern Pale Ale", brewery: "Zichovec" },
      { order: 2, name: "Wai-Wai Hazy IPA", brewery: "Zichovec" },
    ]);
    expect(beers[0]).toMatchObject({ name: "Hex", style: "Modern pale ale" });
    expect(beers[1]).toMatchObject({ name: "Wai-Wai", style: "Hazy IPA" });
  });

  it("keeps the name intact when it carries no style", () => {
    const beers = parseUzamastiluJson([{ order: 1, name: "Nealko" }]);
    expect(beers[0]).toMatchObject({ name: "Nealko", style: "Nealko" });
  });

  it("throws on invalid payload", () => {
    expect(() => parseUzamastiluJson(null)).toThrow(TypeError);
    expect(() => parseUzamastiluJson({})).toThrow(TypeError);
  });

  it("tolerates missing optional fields", () => {
    const beers = parseUzamastiluJson([{ order: 1, name: "No details" }]);
    expect(beers).toHaveLength(1);
    expect(beers[0]).toMatchObject({
      name: "No details",
      brewery: "",
      style: "",
      abv: null,
      degreePlato: null,
      pricing: null,
    });
  });
});
