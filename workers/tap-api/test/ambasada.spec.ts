import { describe, it, expect } from "vitest";
import { parseAmbasadaHtml, parseDescription } from "../src/parsers/ambasada";
import {
  AMBASADA_EMPTY_FIXTURE,
  AMBASADA_FIXTURE,
  AMBASADA_LONG_DESC_FIXTURE,
} from "./fixtures";

function htmlResponse(body: string): Response {
  return new Response(body, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

describe("parseAmbasadaHtml", () => {
  it("returns beers in appearance order with 1-indexed order", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers.map((b) => b.name)).toEqual(["IPA", "Stout", "Mystery Ale"]);
    expect(beers.map((b) => b.order)).toEqual([1, 2, 3]);
  });

  it("extracts degreePlato from name and strips it", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers[0]).toMatchObject({ name: "IPA", degreePlato: 12 });
    expect(beers[1]).toMatchObject({ name: "Stout", degreePlato: null });
  });

  it("parses pipe-separated prices with secondary for 0,3 l", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers[0].pricing).toEqual({
      halfLiterCzk: 120,
      reference: null,
      secondary: { priceCzk: 80, volumeLiters: 0.3 },
    });
  });

  it("converts single price using trailing volume in description", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers[1].pricing).toEqual({
      halfLiterCzk: 100,
      reference: { priceCzk: 60, volumeLiters: 0.3 },
      secondary: null,
    });
  });

  it("keeps single price as-is when description has no volume", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers[2].pricing).toEqual({
      halfLiterCzk: 90,
      reference: null,
      secondary: null,
    });
  });

  it("stops collecting after td.listek_tab_nadpis", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers).toHaveLength(3);
    expect(beers.map((b) => b.name)).not.toContain("Should not appear");
  });

  it("returns empty array when table only has nadpis", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_EMPTY_FIXTURE));
    expect(beers).toEqual([]);
  });

  it("uses style keyword to split brewery and style in long descriptions", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_LONG_DESC_FIXTURE));
    expect(beers).toHaveLength(1);
    expect(beers[0].brewery).toBe(
      "Pivovar s Velmi Dlouhym Nazvem a Popisem, Okres Hodne Velmi Daleko od Centra, Nadmorska Vyska 800 m",
    );
    expect(beers[0].style).toBe("Pale ale with various adjuncts");
  });

  it("keeps the serving size out of the style", async () => {
    // Same fixture as the pricing tests above, which still read 0,5 l / 0,3 l off the untouched
    // description -- the two readings of the volume are independent.
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers.map((b) => b.style)).toEqual(["India pale ale", "Dry stout", ""]);
  });

  it("tags source as ambasada", async () => {
    const beers = await parseAmbasadaHtml(htmlResponse(AMBASADA_FIXTURE));
    expect(beers.every((b) => b.source === "ambasada")).toBe(true);
  });
});

describe("parseDescription", () => {
  it("extracts abv with comma decimal", () => {
    expect(parseDescription("4,8% alc. piv. X, IPA")).toEqual({
      abv: 4.8,
      brewery: "X",
      style: "IPA",
    });
  });

  it("handles description without style heuristic", () => {
    expect(parseDescription("piv. Just brewery")).toEqual({
      abv: null,
      brewery: "Just brewery",
      style: "",
    });
  });

  it("uses style heuristic when last part is short enough", () => {
    expect(parseDescription("Pivovar ABC, Dry Stout")).toMatchObject({
      brewery: "Pivovar ABC",
      style: "Dry Stout",
    });
  });

  it("does not apply style heuristic when last part is too long", () => {
    const desc = "Pivovar ABC, This is a really long last part that exceeds forty characters";
    expect(parseDescription(desc)).toMatchObject({
      brewery: desc,
      style: "",
    });
  });

  it("detects style keyword in a middle part (Batalion case)", () => {
    expect(
      parseDescription(
        "9,3% alc. piv. Haksna, Ostrava, Stout s laktozou, malinami a vanilkou",
      ),
    ).toEqual({
      abv: 9.3,
      brewery: "Haksna, Ostrava",
      style: "Stout s laktozou, malinami a vanilkou",
    });
  });

  it("detects Czech style keyword (světlý ležák)", () => {
    expect(parseDescription("Pivovar XYZ, světlý ležák")).toMatchObject({
      brewery: "Pivovar XYZ",
      style: "světlý ležák",
    });
  });

  it("cuts the serving size before splitting on commas (Pavillon case)", () => {
    // "0,25l" used to split into "0" and "25l", making "25l" the style and swallowing the real
    // one into the brewery.
    expect(
      parseDescription(
        "5,9% alc. piv. Fenetra, Potštejn, Rustical Wild Sour Ale, 0,25l",
      ),
    ).toEqual({
      abv: 5.9,
      brewery: "Fenetra, Potštejn",
      style: "Rustical Wild Sour Ale",
    });
  });

  it("detects a style keyword past the second word", () => {
    // The length-capped last-part fallback refuses styles this long, so only the keyword scan
    // can find them.
    expect(
      parseDescription("Pivovar ABC, Praha, Rustical Wild Sour Ale s malinami a vanilkou"),
    ).toMatchObject({
      brewery: "Pivovar ABC, Praha",
      style: "Rustical Wild Sour Ale s malinami a vanilkou",
    });
  });

  it("leaves no style when the description is only a brewery and a volume", () => {
    expect(parseDescription("jablkohruškový 0,33l")).toEqual({
      abv: null,
      brewery: "jablkohruškový",
      style: "",
    });
  });
});
