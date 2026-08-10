import type { Beer, MenuResponse, Source } from "./schema";
import { parseBeerStreetJson } from "./parsers/beerstreet";
import { parseAmbasadaHtml } from "./parsers/ambasada";
import { parseToulavapipaCsv } from "./parsers/toulavapipa";
import { parseUzamastiluJson } from "./parsers/uzamastilu";

const USER_AGENT = "tap-api/1.0";
const TOULAVA_PIPA_SHEET_BASE =
  "https://docs.google.com/spreadsheets/d/e/2PACX-1vSgPAMETGHHgIC7ND6p79_D5WVCtrU6UBCwEm32LFZfK5eOKoXQYtuklEfAfvixIuHHiYjUBnhYG2PH/pub";

async function fetchMenu(
  source: Source,
  url: string,
  parse: (response: Response) => Promise<Beer[]>,
): Promise<MenuResponse> {
  const response = await fetch(url, {
    headers: { "User-Agent": USER_AGENT },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  if (!response.ok) {
    throw new Error(`${source} upstream returned ${response.status}`);
  }
  return {
    source,
    fetchedAt: new Date().toISOString(),
    beers: await parse(response),
  };
}

export const fetchBeerStreetMenu = (): Promise<MenuResponse> =>
  fetchMenu("beerstreet", "https://beerstreet.cz/data/beers.json", async (r) =>
    parseBeerStreetJson(await r.json()),
  );

export const fetchAmbasadaMenu = (): Promise<MenuResponse> =>
  fetchMenu("ambasada", "https://pivniambasada.cz/", parseAmbasadaHtml);

export const fetchToulavapipaMenu = (): Promise<MenuResponse> =>
  fetchMenu("toulavapipa", `${TOULAVA_PIPA_SHEET_BASE}?gid=0&single=true&output=csv`, async (r) =>
    parseToulavapipaCsv(await r.text(), "toulavapipa"),
  );

export const fetchLodotavaMenu = (): Promise<MenuResponse> =>
  fetchMenu("lodotava", `${TOULAVA_PIPA_SHEET_BASE}?gid=310545451&single=true&output=csv`, async (r) =>
    parseToulavapipaCsv(await r.text(), "lodotava"),
  );

export const fetchUzamastiluMenu = (): Promise<MenuResponse> =>
  fetchMenu("uzamastilu", "https://uzamastilu.cz/data", async (r) =>
    parseUzamastiluJson(await r.json()),
  );
