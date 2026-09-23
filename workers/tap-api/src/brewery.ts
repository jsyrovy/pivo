export interface BreweryRef {
  key: string;
  name: string;
}

// Words that say "this is a brewery" rather than which one, so "Thrills Brewing" and "Kynšperský
// pivovar" key the same as "Thrills" and "Kynšperský". Spelled without diacritics, because they are
// matched after the key has lost them.
const GENERIC_WORDS = new Set(["pivovar", "pivovarek", "brewery", "brewing", "brauerei", "piv"]);

const DIACRITICS = /\p{M}+/gu;
const NON_ALPHANUMERIC = /[^\p{L}\p{N}]+/gu;
const PARENTHESIZED = /\([^)]*\)/g;
const WHITESPACE = /\s+/g;
const EMPTY_TAP = "-";

const ref = (key: string, name: string): BreweryRef => ({ key, name });

// Keyed by the normalized key, so one row covers every spelling that normalizes to it. Covers what
// the rules cannot: typos, other forms of the same name, and collaborations joined by "&" -- the
// split only happens on "/", since "Duck & Dog" and "Maisel & Friends" are single breweries.
export const BREWERY_ALIASES: Record<string, BreweryRef[]> = {
  beskdydsky: [ref("beskydsky", "Beskydský")],
  klenotzmajska: [ref("klenot", "Klenot"), ref("zmajska", "Zmajska")],
  kynsperk: [ref("kynspersky", "Kynšperský")],
  kynsperknadohri: [ref("kynspersky", "Kynšperský")],
  kynsperskyzajic: [ref("kynspersky", "Kynšperský")],
  pioneerbeer: [ref("pioneer", "Pioneer")],
  pionner: [ref("pioneer", "Pioneer")],
  rhapnectaroncestmir: [ref("cestmir", "Čestmír")],
  salamaco: [ref("salama", "Salama")],
  unetice: [ref("uneticky", "Únětický")],
};

export function breweryKey(name: string): string {
  const words = name
    .toLocaleLowerCase("cs-CZ")
    .normalize("NFD")
    .replace(DIACRITICS, "")
    .split(NON_ALPHANUMERIC)
    .filter(Boolean);
  const specific = words.filter((word) => !GENERIC_WORDS.has(word));
  // A brewery called just "Pivovar" is still a brewery; better a generic key than none.
  return (specific.length > 0 ? specific : words).join("");
}

// `brewery` is free text typed by the pub: "Mordýř, Dolní Ředice", "Hoppy Dog", "Sibeeria/Namachan".
// Only the part before the first comma names the brewery -- the rest is its town -- and that is cut
// off before splitting collaborations on "/", so a slash later in the text ("Sour Ale w/ Raspberry")
// cannot invent a brewery.
export function normalizeBreweries(raw: string): BreweryRef[] {
  const text = raw.trim();
  if (!text || text === EMPTY_TAP) return [];

  const byKey = new Map<string, BreweryRef>();
  const head = text.split(",")[0].replace(PARENTHESIZED, " ");
  for (const part of head.split("/")) {
    const name = part.replace(WHITESPACE, " ").trim();
    const key = breweryKey(name);
    if (!key) continue;
    for (const brewery of BREWERY_ALIASES[key] ?? [ref(key, name)]) {
      if (!byKey.has(brewery.key)) byKey.set(brewery.key, brewery);
    }
  }
  return [...byKey.values()];
}
