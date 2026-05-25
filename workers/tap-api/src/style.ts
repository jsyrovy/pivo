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
]);

const NON_ALPHANUMERIC = /[^\p{L}\p{N}]+/gu;
const WHITESPACE_SPLIT = /(\s+)/;

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
