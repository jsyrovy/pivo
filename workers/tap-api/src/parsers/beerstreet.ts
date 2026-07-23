import type { Beer } from "../schema";
import { beerStreetPricing } from "../pricing";
import { formatStyle } from "../style";
import { isObject, parseNumber, trimString } from "./json-utils";

interface RawBeer {
  nazev?: unknown;
  nazev_pivovaru?: unknown;
  styl?: unknown;
  avb?: unknown;
  epm?: unknown;
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

  const items = payload.beers.filter(isObject) as RawBeer[];

  return items.map((item, index): Beer => ({
    name: trimString(item.nazev),
    brewery: trimString(item.nazev_pivovaru),
    style: formatStyle(trimString(item.styl)),
    abv: parseNumber(item.avb),
    degreePlato: parseNumber(item.epm),
    source: "beerstreet",
    order: index + 1,
    pricing: beerStreetPricing(item.cena04, item.cena03),
  }));
}
