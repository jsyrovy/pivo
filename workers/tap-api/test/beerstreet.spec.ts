import { describe, it, expect } from "vitest";
import { parseBeerStreetJson } from "../src/parsers/beerstreet";
import { BEERSTREET_FIXTURE } from "./fixtures";

describe("parseBeerStreetJson", () => {
  it("preserves source list order regardless of poradi value", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers.map((b) => b.name)).toEqual([
      "Pilsner Urquell",
      "Craft IPA",
      "Dark Stout",
    ]);
    expect(beers.map((b) => b.order)).toEqual([1, 2, 3]);
  });

  it("normalizes abv from comma to dot", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers[0].abv).toBe(4.4);
    expect(beers[1].abv).toBe(6.0);
  });

  it("parses degreePlato as integer", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers[0].degreePlato).toBe(12);
    expect(beers[2].degreePlato).toBe(13);
  });

  it("computes pricing from cena04 with 0,4 l reference", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers[0].pricing).toEqual({
      halfLiterCzk: 63,
      reference: { priceCzk: 50, volumeLiters: 0.4 },
      secondary: null,
    });
  });

  it("falls back to cena03 when cena04 missing", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers[1].pricing).toEqual({
      halfLiterCzk: 75,
      reference: { priceCzk: 45, volumeLiters: 0.3 },
      secondary: null,
    });
  });

  it("returns pricing=null when neither price is present", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers[2].pricing).toBeNull();
  });

  it("tags source as beerstreet", () => {
    const beers = parseBeerStreetJson(BEERSTREET_FIXTURE);
    expect(beers.every((b) => b.source === "beerstreet")).toBe(true);
  });

  it("throws on invalid payload", () => {
    expect(() => parseBeerStreetJson(null)).toThrow(TypeError);
    expect(() => parseBeerStreetJson({})).toThrow(TypeError);
    expect(() => parseBeerStreetJson({ beers: "not an array" })).toThrow(TypeError);
  });

  it("tolerates missing optional fields", () => {
    const beers = parseBeerStreetJson({
      beers: [{ nazev: "No details", poradi: "1" }],
    });
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
