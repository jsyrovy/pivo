import type { BreweryRef } from "./brewery";
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
  // Normalized from `brewery`, which stays raw: pairing keys are built from it.
  breweries: BreweryRef[];
  style: string;
  styleCategory: StyleCategory;
  abv: number | null;
  degreePlato: number | null;
  source: Source;
  order: number | null;
  pricing: PricingInfo | null;
}

// What a per-source parser produces. Categorizing the style and normalizing the brewery is not the
// parsers' job -- `fetchMenu` does it once for every source, so each vocabulary stays in one place.
export type ParsedBeer = Omit<Beer, "styleCategory" | "breweries">;

export interface MenuResponse {
  source: Source;
  fetchedAt: string;
  beers: Beer[];
  viaSocket?: boolean;
}
