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
