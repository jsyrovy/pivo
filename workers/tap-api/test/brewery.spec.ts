import { describe, it, expect } from "vitest";
import { breweryKey, normalizeBreweries } from "../src/brewery";

const keys = (raw: string) => normalizeBreweries(raw).map((b) => b.key);

describe("normalizeBreweries", () => {
  it("returns nothing for an empty brewery or the empty-tap placeholder", () => {
    expect(normalizeBreweries("")).toEqual([]);
    expect(normalizeBreweries("   ")).toEqual([]);
    expect(normalizeBreweries("-")).toEqual([]);
  });

  it("drops the town after the comma from both key and name", () => {
    expect(normalizeBreweries("Mordýř, Dolní Ředice")).toEqual([{ key: "mordyr", name: "Mordýř" }]);
    expect(keys("Mordýř")).toEqual(["mordyr"]);
    expect(normalizeBreweries("Clock, Potštejn")).toEqual([{ key: "clock", name: "Clock" }]);
    expect(normalizeBreweries("Volt, Jablonec nad Nisou")).toEqual([{ key: "volt", name: "Volt" }]);
  });

  it("keys case, spacing and punctuation variants the same", () => {
    expect(new Set(["Madcat", "MadCat", "MadCat, Kamenice"].flatMap(keys))).toEqual(new Set(["madcat"]));
    expect(new Set(["Hoppydog", "Hoppy Dog, Ostrava", "HoppyDog, Ostrava"].flatMap(keys))).toEqual(
      new Set(["hoppydog"]),
    );
    expect(new Set(["Duck & Dog", "Duck  & Dog", "Duck&Dog", "Duck &.Dog"].flatMap(keys))).toEqual(
      new Set(["duckdog"]),
    );
  });

  it("keeps the name as written, with whitespace collapsed", () => {
    expect(normalizeBreweries("Duck  & Dog")).toEqual([{ key: "duckdog", name: "Duck & Dog" }]);
    expect(normalizeBreweries("MadCat")).toEqual([{ key: "madcat", name: "MadCat" }]);
  });

  it("ignores generic brewery words in the key", () => {
    expect(keys("Thrills Brewing")).toEqual(["thrills"]);
    expect(keys("Thrills  Brewing")).toEqual(["thrills"]);
    expect(keys("Kynšperský pivovar")).toEqual(["kynspersky"]);
    expect(keys("Beskydský Pivovárek, Ostravice")).toEqual(["beskydsky"]);
    expect(keys("Berquell Brauerei")).toEqual(["berquell"]);
  });

  it("keeps a generic key when nothing else is left", () => {
    expect(normalizeBreweries("Pivovar")).toEqual([{ key: "pivovar", name: "Pivovar" }]);
  });

  it("strips diacritics from the key", () => {
    expect(keys("Čierny Kámeň")).toEqual(["ciernykamen"]);
    expect(keys("Čierny Kameň")).toEqual(["ciernykamen"]);
  });

  it("drops a parenthesized note", () => {
    expect(normalizeBreweries("Weissenohe (Bavorsko)")).toEqual([{ key: "weissenohe", name: "Weissenohe" }]);
  });

  it("resolves typos and other forms through the alias table", () => {
    expect(normalizeBreweries("Pionner")).toEqual([{ key: "pioneer", name: "Pioneer" }]);
    expect(keys("Pioneer Beer")).toEqual(["pioneer"]);
    expect(keys("Kynšperk nad Ohří")).toEqual(["kynspersky"]);
    expect(keys("Kynšperský zajíc")).toEqual(["kynspersky"]);
    expect(keys("Beskdydský pivovárek, Ostravice")).toEqual(["beskydsky"]);
  });

  it("splits a collaboration on slash into every brewery", () => {
    expect(normalizeBreweries("Sibeeria/Namachan")).toEqual([
      { key: "sibeeria", name: "Sibeeria" },
      { key: "namachan", name: "Namachan" },
    ]);
    expect(keys("Haksna/Podřevnický")).toEqual(["haksna", "podrevnicky"]);
    expect(keys("MadCat/Hulvát")).toEqual(["madcat", "hulvat"]);
  });

  it("does not split on ampersand unless an alias says it is a collaboration", () => {
    expect(keys("Maisel & Friends, Bayreuth")).toEqual(["maiselfriends"]);
    expect(normalizeBreweries("Klenot & Zmajska")).toEqual([
      { key: "klenot", name: "Klenot" },
      { key: "zmajska", name: "Zmajska" },
    ]);
  });

  it("cuts the town before splitting, so a slash in trailing text adds no brewery", () => {
    expect(keys("Sibeeria/Herrenwald, Sour Ale w/ Raspberry")).toEqual(["sibeeria", "herrenwald"]);
  });

  it("reads only the brewery out of parser leftovers", () => {
    expect(keys("Fenetra, Potštejn, Rustical Wild Sour Ale, 0")).toEqual(["fenetra"]);
    expect(keys("piv. Van Honsebrouck, Ingelmunster, Západní Flandry, Tropical Fruit Ale, 0")).toEqual([
      "vanhonsebrouck",
    ]);
  });

  it("merges a brewery that appears twice in one collaboration", () => {
    expect(normalizeBreweries("Klenot/Klenot & Zmajska")).toEqual([
      { key: "klenot", name: "Klenot" },
      { key: "zmajska", name: "Zmajska" },
    ]);
    expect(keys("Madcat/MadCat")).toEqual(["madcat"]);
  });

  it("skips empty collaboration parts", () => {
    expect(keys("Sibeeria/")).toEqual(["sibeeria"]);
  });
});

describe("breweryKey", () => {
  it("produces ASCII without spaces, fit for a URL hash", () => {
    expect(breweryKey("Únětický pivovar")).toBe("uneticky");
    expect(breweryKey("U Vojtěchů")).toBe("uvojtechu");
  });
});
