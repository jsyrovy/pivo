import type { Beer } from "../schema";
import { beerStreetPricing } from "../pricing";
import { formatStyle } from "../style";

interface RawBeer {
  nazev?: unknown;
  nazev_pivovaru?: unknown;
  styl?: unknown;
  avb?: unknown;
  epm?: unknown;
  poradi?: unknown;
  cena04?: unknown;
  cena03?: unknown;
}

interface RawPayload {
  beers?: unknown;
}

export function parseBeerStreetJson(raw: unknown): Beer[] {
  if (!isObject(raw)) {
    throw new TypeError("Beer Street payload is not an object");
  }
  const payload = raw as RawPayload;
  if (!Array.isArray(payload.beers)) {
    throw new TypeError("Beer Street payload missing `beers` array");
  }

  const items = (payload.beers.filter(isObject) as RawBeer[]).sort((a, b) => {
    const oa = toOrder(a.poradi);
    const ob = toOrder(b.poradi);
    if (oa === null && ob === null) return 0;
    if (oa === null) return 1;
    if (ob === null) return -1;
    return oa - ob;
  });

  return items.map((item): Beer => ({
    name: trimString(item.nazev),
    brewery: trimString(item.nazev_pivovaru),
    style: formatStyle(trimString(item.styl)),
    abv: parseNumber(item.avb),
    degreePlato: parseNumber(item.epm),
    source: "beerstreet",
    order: toOrder(item.poradi),
    pricing: beerStreetPricing(item.cena04, item.cena03),
  }));
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function trimString(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim();
}

function parseNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string") return null;
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  const n = Number.parseFloat(normalized);
  return Number.isFinite(n) ? n : null;
}

function toOrder(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string") return null;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : null;
}
