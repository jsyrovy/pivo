import { describe, it, expect } from "vitest";
import { parseCsv, parseToulavapipaCsv } from "../src/parsers/toulavapipa";
import { LODOTAVA_CLOSED_FIXTURE, TOULAVA_PIPA_FIXTURE } from "./fixtures";

describe("parseCsv", () => {
  it("strips the BOM and splits rows and fields", () => {
    const rows = parseCsv("\uFEFFa,b,c\n1,2,3");
    expect(rows).toEqual([
      ["a", "b", "c"],
      ["1", "2", "3"],
    ]);
  });

  it("detects semicolon delimiter", () => {
    const rows = parseCsv("a;b;c\n1;2;3");
    expect(rows).toEqual([
      ["a", "b", "c"],
      ["1", "2", "3"],
    ]);
  });

  it("handles quoted fields with escaped quotes and embedded newlines", () => {
    const rows = parseCsv('name,note\n"say ""hi""","line1\nline2"');
    expect(rows).toEqual([
      ["name", "note"],
      ['say "hi"', "line1\nline2"],
    ]);
  });

  it("handles CRLF line endings", () => {
    const rows = parseCsv("a,b\r\n1,2\r\n");
    expect(rows).toEqual([
      ["a", "b"],
      ["1", "2"],
    ]);
  });
});

describe("parseToulavapipaCsv", () => {
  it("maps columns from the header row", () => {
    const beers = parseToulavapipaCsv("Pivovar,Název piva,Pivní styl\nZajíc,Kamenická 12,Ležák", "toulavapipa");
    expect(beers[0]).toMatchObject({ name: "Kamenická", brewery: "Zajíc", style: "Ležák" });
  });

  it("falls back to positional columns when there is no header", () => {
    const beers = parseToulavapipaCsv("Kamenická 12,Ležák,Zajíc", "toulavapipa");
    expect(beers[0]).toMatchObject({ name: "Kamenická", brewery: "Zajíc", style: "Ležák" });
  });

  it("skips empty rows and trims cells", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers.map((b) => b.name)).toEqual(["Kamenická", "Zajíc", "Hoppy lager", "Birgo Mango"]);
    expect(beers[0].style).toBe("Světlý ležák");
  });

  it("skips rows without a brewery (closed placeholder)", () => {
    expect(parseToulavapipaCsv(LODOTAVA_CLOSED_FIXTURE, "lodotava")).toEqual([]);
  });

  it("extracts trailing degree from the name", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers.map((b) => b.degreePlato)).toEqual([12, 11, 10, 0]);
  });

  it("keeps the name intact when the trailing number is out of range", () => {
    const beers = parseToulavapipaCsv("Kamenická 21,Ležák,Zajíc", "toulavapipa");
    expect(beers[0]).toMatchObject({ name: "Kamenická 21", degreePlato: null });
  });

  it("keeps the name intact when stripping the degree would empty it", () => {
    const beers = parseToulavapipaCsv("12,Ležák,Zajíc", "toulavapipa");
    expect(beers[0]).toMatchObject({ name: "12", degreePlato: null });
  });

  it("parses decimal degree with a comma", () => {
    const beers = parseToulavapipaCsv("Kamenická 12,5;Ležák;Zajíc", "toulavapipa");
    expect(beers[0]).toMatchObject({ name: "Kamenická", degreePlato: 12.5 });
  });

  it("formats the style and infers Nealko from 0° when the style is empty", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers[3].style).toBe("Nealko");
  });

  it("tags the source with the given key", () => {
    expect(parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa").every((b) => b.source === "toulavapipa")).toBe(
      true,
    );
    expect(parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "lodotava").every((b) => b.source === "lodotava")).toBe(true);
  });

  it("unquotes fields with escaped quotes", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers[2].brewery).toBe('Pivovar "Quoted"');
  });

  it("assigns post-filter order 1..n", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers.map((b) => b.order)).toEqual([1, 2, 3, 4]);
  });

  it("never exposes abv or pricing since the sheet has neither", () => {
    const beers = parseToulavapipaCsv(TOULAVA_PIPA_FIXTURE, "toulavapipa");
    expect(beers.every((b) => b.abv === null && b.pricing === null)).toBe(true);
  });
});
