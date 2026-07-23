export type Source = "beerstreet" | "ambasada" | "uzamastilu";

export interface PriceReference {
  priceCzk: number;
  volumeLiters: number;
}

export interface PricingInfo {
  halfLiterCzk: number;
  reference: PriceReference | null;
  secondary: PriceReference | null;
}

export interface Beer {
  name: string;
  brewery: string;
  style: string;
  abv: number | null;
  degreePlato: number | null;
  source: Source;
  order: number | null;
  pricing: PricingInfo | null;
}

export interface MenuResponse {
  source: Source;
  fetchedAt: string;
  beers: Beer[];
}
