import type { ParsedBeer } from "../schema";
import { uzamastiluPricing } from "../pricing";
import { extractStyleFromName, formatStyle, inferStyleFromDegree, splitLeadingStyle } from "../style";
import { isObject, parseNumber, trimString } from "./json-utils";

const ABV_PREFIX = /^\d+(?:[,.]\d+)?\s*%\s*(?:alc\b\.?\s*)?/i;

interface RawBeer {
  order?: unknown;
  degree?: unknown;
  brewery?: unknown;
  name?: unknown;
  price05?: unknown;
  price03?: unknown;
}

export function parseUzamastiluJson(raw: unknown): ParsedBeer[] {
  if (!Array.isArray(raw)) {
    throw new TypeError("U Zámastilů payload is not an array");
  }

  const items = raw.filter(isObject) as RawBeer[];

  return items
    .map((item): ParsedBeer => {
      const degreePlato = parseDegree(item.degree);
      const { name, style } = extractStyleFromName(cleanName(item.name));
      const { brewery, style: leakedStyle } = splitLeadingStyle(cleanBrewery(item.brewery));
      return {
        name,
        brewery,
        style: formatStyle(style || leakedStyle || inferStyleFromDegree(degreePlato)),
        abv: null,
        degreePlato,
        source: "uzamastilu",
        order: parseNumber(item.order),
        pricing: uzamastiluPricing(item.price05, item.price03),
      };
    })
    .filter((beer) => beer.order !== null && beer.order >= 1 && beer.order <= 7);
}

function cleanName(value: unknown): string {
  return trimString(value).replace(/\*/g, " ").trim();
}

// The upstream occasionally leaks the ABV into the brewery field too ("4.3% alc Loutkář").
function cleanBrewery(value: unknown): string {
  return trimString(value).replace(ABV_PREFIX, "");
}

function parseDegree(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = value.match(/[\d,.]+/);
  if (!match) return null;
  const n = Number.parseFloat(match[0].replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
