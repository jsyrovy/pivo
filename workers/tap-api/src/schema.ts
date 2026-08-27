import type { StyleCategory } from "./style";

export type Source = "beerstreet" | "ambasada" | "toulavapipa" | "lodotava" | "uzamastilu";

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
  styleCategory: StyleCategory;
  abv: number | null;
  degreePlato: number | null;
  source: Source;
  order: number | null;
  pricing: PricingInfo | null;
}

// What a per-source parser produces. Categorizing the style is not the parsers' job -- `fetchMenu`
// does it once for every source, so the style vocabulary stays in a single place.
export type ParsedBeer = Omit<Beer, "styleCategory">;

export interface MenuResponse {
  source: Source;
  fetchedAt: string;
  beers: Beer[];
  viaSocket?: boolean;
}
