import type { PricingInfo } from "./schema";

export function halfLiterFrom(priceCzk: number, volumeLiters: number): number {
  return Math.round((priceCzk / volumeLiters) * 0.5);
}

export function beerStreetPricing(
  cena04: unknown,
  cena03: unknown,
): PricingInfo | null {
  const p04 = toPositiveNumber(cena04);
  if (p04 !== null) {
    return {
      halfLiterCzk: halfLiterFrom(p04, 0.4),
      reference: { priceCzk: p04, volumeLiters: 0.4 },
      secondary: null,
    };
  }
  const p03 = toPositiveNumber(cena03);
  if (p03 !== null) {
    return {
      halfLiterCzk: halfLiterFrom(p03, 0.3),
      reference: { priceCzk: p03, volumeLiters: 0.3 },
      secondary: null,
    };
  }
  return null;
}

export function ambasadaPricing(
  priceRaw: string | null,
  description: string | null,
): PricingInfo | null {
  if (!priceRaw) return null;

  if (priceRaw.includes("|")) {
    const [bigStr, smallStr] = priceRaw.split("|").map((p) => p.trim());
    const big = Number.parseInt(bigStr, 10);
    const small = Number.parseInt(smallStr, 10);
    if (!Number.isFinite(big) || !Number.isFinite(small)) return null;
    return {
      halfLiterCzk: big,
      reference: null,
      secondary: { priceCzk: small, volumeLiters: 0.3 },
    };
  }

  const price = Number.parseInt(priceRaw, 10);
  if (!Number.isFinite(price) || price <= 0) return null;

  const volume = extractTrailingVolume(description);
  if (volume === null) {
    return { halfLiterCzk: price, reference: null, secondary: null };
  }
  return {
    halfLiterCzk: halfLiterFrom(price, volume),
    reference: { priceCzk: price, volumeLiters: volume },
    secondary: null,
  };
}

export function extractTrailingVolume(description: string | null): number | null {
  if (!description) return null;
  const match = description.match(/([\d,.]+)\s*l\s*$/);
  if (!match) return null;
  const volume = Number.parseFloat(match[1].replace(",", "."));
  if (!Number.isFinite(volume) || volume <= 0) return null;
  return volume;
}

export function uzamastiluPricing(
  price05: unknown,
  price03: unknown,
): PricingInfo | null {
  const p05 = toPositiveNumber(price05);
  const p03 = toPositiveNumber(price03);

  if (p05 !== null) {
    return {
      halfLiterCzk: p05,
      reference: null,
      secondary: p03 !== null ? { priceCzk: p03, volumeLiters: 0.3 } : null,
    };
  }
  if (p03 !== null) {
    return {
      halfLiterCzk: halfLiterFrom(p03, 0.3),
      reference: { priceCzk: p03, volumeLiters: 0.3 },
      secondary: null,
    };
  }
  return null;
}

function toPositiveNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  if (typeof value === "string") {
    const n = Number.parseFloat(value);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  return null;
}
