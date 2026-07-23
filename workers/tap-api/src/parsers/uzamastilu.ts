import type { Beer } from "../schema";
import { uzamastiluPricing } from "../pricing";
import { isObject, parseNumber, trimString } from "./json-utils";

interface RawBeer {
  order?: unknown;
  degree?: unknown;
  brewery?: unknown;
  name?: unknown;
  price05?: unknown;
  price03?: unknown;
}

export function parseUzamastiluJson(raw: unknown): Beer[] {
  if (!Array.isArray(raw)) {
    throw new TypeError("U Zámastilů payload is not an array");
  }

  const items = raw.filter(isObject) as RawBeer[];

  return items
    .map((item): Beer => ({
      name: cleanName(item.name),
      brewery: trimString(item.brewery),
      style: "",
      abv: null,
      degreePlato: parseDegree(item.degree),
      source: "uzamastilu",
      order: parseNumber(item.order),
      pricing: uzamastiluPricing(item.price05, item.price03),
    }))
    .filter((beer) => beer.order !== null && beer.order >= 1 && beer.order <= 7);
}

function cleanName(value: unknown): string {
  return trimString(value).replace(/\*/g, " ").trim();
}

function parseDegree(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = value.match(/[\d,.]+/);
  if (!match) return null;
  const n = Number.parseFloat(match[0].replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
