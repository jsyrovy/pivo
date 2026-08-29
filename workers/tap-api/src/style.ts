const ACRONYMS = new Set([
  "IPA",
  "NEIPA",
  "DIPA",
  "IIPA",
  "TIPA",
  "WIPA",
  "BIPA",
  "NEDIPA",
  "IPL",
  "APA",
  "NEPA",
  "ABV",
  "IBU",
  "DDH",
  "TDH",
]);

const NON_ALPHANUMERIC = /[^\p{L}\p{N}]+/gu;
const WHITESPACE_SPLIT = /(\s+)/;

// Core style nouns. Shared with the Ambasada parser, which splits a description
// into "brewery, style" once it hits one of these words.
export const STYLE_KEYWORDS = new Set([
  "stout", "lager", "pilsner", "ipa", "neipa", "dipa", "iipa", "tipa",
  "apa", "nepa", "ale", "porter", "weizen", "wheat", "hefeweizen",
  "saison", "tripel", "dubbel", "quadrupel", "gose", "sour",
  "pale", "india", "imperial", "barleywine",
  "kölsch", "altbier", "helles", "dunkel", "bock", "märzen",
  "rauchbier", "berliner", "lambic", "gueuze",
  "ležák", "světlý", "světlé", "polotmavý", "polotmavé",
  "tmavý", "tmavé", "pšeničné", "pšenice", "výčepní", "kvasnicové",
]);

// Words that qualify a core style and should stay attached to it when they
// directly precede one (e.g. "Hazy" in "Hazy IPA", "Nefiltr" in "Nefiltr Ležák").
// Words that are themselves core styles (e.g. "imperial", "světlý") live in
// STYLE_KEYWORDS -- keep them out of here so the vocabulary is single-sourced.
const STYLE_MODIFIERS = new Set([
  "hazy", "double", "triple", "session", "modern",
  "new", "england", "west", "coast", "dry", "hopped",
  "american", "czech", "german", "belgian",
  "nefiltr", "nefiltrovaný", "nefiltrované", "nefiltrovaná",
  "kvasnicový", "kvasnicová", "řezaný", "řezané",
]);

// Core styles that can also be the whole beer name (so no dedicated name remains).
const NAME_STYLE_KEYWORDS = new Set([
  ...STYLE_KEYWORDS,
  "nealko", "nealkoholické", "nealkoholický",
]);

// Broad, flat buckets for the tap-list style filter. Deliberately few and wide: "ipa" holds every
// IPA sub-style, "special" holds wheat and Belgian beers together. "other" is the fallback for
// unclassifiable style text ("25l", empty).
export type StyleCategory =
  | "nealko"
  | "sour"
  | "dark"
  | "ipa"
  | "special"
  | "lezak"
  | "paleale"
  | "other";

// First row whose keyword appears in the style text wins, so row order is priority. That is what
// settles the collisions the real corpus is full of: "Fruit sour ale" is sour rather than pale ale,
// "India pale lager" is an IPA rather than a lager, "Hoppy saison ale" is a special rather than a
// pale ale. Category boundaries are therefore configuration -- reclassifying a style means moving a
// word from one row to another, not changing code.
const STYLE_CATEGORY_RULES: readonly { key: StyleCategory; keywords: readonly string[] }[] = [
  {
    key: "nealko",
    keywords: ["nealko", "nealkoholický", "nealkoholické", "nealkoholická"],
  },
  {
    key: "sour",
    // "weisse" is missing on purpose: every Berliner weisse in the corpus is caught by "berliner"
    // or "sour", and a bare "weisse" would drag wheat beers in here.
    keywords: ["sour", "gose", "berliner", "berlin", "kyseláč", "lambic", "gueuze"],
  },
  {
    key: "dark",
    // Doubles as a colour filter -- amber lagers and Rotbier land here rather than in "lezak",
    // which is what someone clicking "Tmavá" is after. "red" is left out: "Red APA" is a pale ale.
    keywords: [
      "stout", "porter", "dunkel", "schwarzbier", "rotbier", "amber", "barleywine",
      "tmavý", "tmavé", "tmavá", "tm", "polotmavý", "polotmavé", "polotmavá",
    ],
  },
  {
    key: "ipa",
    // "hazy" alone means an IPA on Czech tap lists ("Session hazy"), and IPL is decided by the hop
    // profile, not the fermentation.
    keywords: [
      "ipa", "neipa", "dipa", "iipa", "tipa", "nedipa", "wipa", "bipa",
      "ipl", "india", "hazy",
    ],
  },
  {
    key: "special",
    keywords: [
      "weizen", "weizenbier", "hefeweizen", "weissbier", "witbier", "wheat",
      "pšeničné", "pšeničný", "pšenice", "saison", "farmhouse",
      "tripel", "dubbel", "quadrupel", "bock", "rauchbier", "kölsch", "altbier",
    ],
  },
  {
    key: "lezak",
    keywords: [
      "ležák", "lager", "pilsner", "pilsener", "pils", "helles", "märzen",
      "výčepní", "světlý", "světlé", "světlá",
    ],
  },
  {
    key: "paleale",
    keywords: ["apa", "nepa", "pale", "ale", "summer", "smash"],
  },
];

function styleToken(word: string): string {
  return word.replace(NON_ALPHANUMERIC, "").toLocaleLowerCase("cs-CZ");
}

// U Zámastilů folds the style into the beer name ("Otakar Ležák", "Hex Modern
// Pale Ale") instead of exposing a separate field. Detect the trailing run of
// style words, return it as `style`, and strip it from `name` -- unless the
// style is the whole name, in which case it is the only information we have.
export function extractStyleFromName(name: string): {
  name: string;
  style: string;
} {
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length === 0) return { name, style: "" };

  const isKeyword = (w: string) => NAME_STYLE_KEYWORDS.has(styleToken(w));
  const isStyleWord = (w: string) =>
    isKeyword(w) || STYLE_MODIFIERS.has(styleToken(w));

  let start = words.length;
  while (start > 0 && isStyleWord(words[start - 1])) start--;

  const styleWords = words.slice(start);
  // A lone modifier ("Dry") without a core keyword is not a style on its own.
  if (styleWords.length === 0 || !styleWords.some(isKeyword)) {
    return { name, style: "" };
  }

  return {
    name: start === 0 ? name : words.slice(0, start).join(" "),
    style: styleWords.join(" "),
  };
}

// 0° degree Plato is the standard Czech labeling convention for a non-alcoholic beer. Used as a
// name-extraction fallback for U Zámastilu, which never provides its own style field (e.g. "Birgo
// Mango-Limetka" carries no style word in the name but is 0° "Nealko"). Beer Street and Ambasada
// aren't wired to this: they already curate/derive a real `style` from their own source data.
export function inferStyleFromDegree(degreePlato: number | null): string {
  return degreePlato === 0 ? "Nealko" : "";
}

export function formatStyle(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  const lower = trimmed.toLocaleLowerCase("cs-CZ");
  const sentenceCased =
    lower.charAt(0).toLocaleUpperCase("cs-CZ") + lower.slice(1);

  return sentenceCased
    .split(WHITESPACE_SPLIT)
    .map((token) => {
      if (!token.trim()) return token;
      const core = token.replace(NON_ALPHANUMERIC, "").toUpperCase();
      return ACRONYMS.has(core) ? token.toUpperCase() : token;
    })
    .join("");
}

// The style field is free text typed by the pub, so the only reliable signal is which style words it
// contains -- a typo in the qualifier ("Ležák světiý", "Sessiin NEIPA") leaves the core word intact.
export function categorizeStyle(style: string): StyleCategory {
  const tokens = new Set(
    style
      .split(NON_ALPHANUMERIC)
      .map((word) => word.toLocaleLowerCase("cs-CZ"))
      .filter(Boolean),
  );

  for (const rule of STYLE_CATEGORY_RULES) {
    if (rule.keywords.some((keyword) => tokens.has(keyword))) return rule.key;
  }
  return "other";
}
