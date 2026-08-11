import type { Beer, MenuResponse, Source } from "./schema";
import { parseBeerStreetJson } from "./parsers/beerstreet";
import { parseAmbasadaHtml } from "./parsers/ambasada";
import { parseToulavapipaCsv } from "./parsers/toulavapipa";
import { parseUzamastiluJson } from "./parsers/uzamastilu";
import { fetchViaSocket, type FetchViaSocketOptions } from "./socket-fetch";

const USER_AGENT = "tap-api/1.0";
const TOULAVA_PIPA_SHEET_BASE =
  "https://docs.google.com/spreadsheets/d/e/2PACX-1vSgPAMETGHHgIC7ND6p79_D5WVCtrU6UBCwEm32LFZfK5eOKoXQYtuklEfAfvixIuHHiYjUBnhYG2PH/pub";

// Upstreams that reject the Workers fetch() egress path answer 401/403; the raw
// socket path reaches the same host successfully, so retry there.
const SOCKET_FALLBACK_STATUSES = new Set([401, 403]);

export interface FetchMenuDeps {
  fetchImpl: (url: string, init?: RequestInit) => Promise<Response>;
  socketFetch: (url: string, options?: Pick<FetchViaSocketOptions, "userAgent">) => Promise<Response>;
}

const DEFAULT_DEPS: FetchMenuDeps = {
  fetchImpl: (url, init) => fetch(url, init),
  socketFetch: fetchViaSocket,
};

async function fetchMenu(
  source: Source,
  url: string,
  parse: (response: Response) => Promise<Beer[]>,
  deps: FetchMenuDeps = DEFAULT_DEPS,
): Promise<MenuResponse> {
  let response = await deps.fetchImpl(url, {
    headers: { "User-Agent": USER_AGENT },
    cf: { cacheTtl: 0, cacheEverything: false },
  });

  let viaSocket = false;

  if (SOCKET_FALLBACK_STATUSES.has(response.status)) {
    const blockedStatus = response.status;
    console.info("socket_fallback", { source, blockedStatus });
    try {
      response = await deps.socketFetch(url, { userAgent: USER_AGENT });
      viaSocket = true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(`${source} upstream returned ${blockedStatus}, socket fallback failed: ${message}`);
    }
  }

  if (!response.ok) {
    const suffix = viaSocket ? " (via socket)" : "";
    throw new Error(`${source} upstream returned ${response.status}${suffix}`);
  }

  return {
    source,
    fetchedAt: new Date().toISOString(),
    beers: await parse(response),
    viaSocket: viaSocket || undefined,
  };
}

export const fetchBeerStreetMenu = (deps?: FetchMenuDeps): Promise<MenuResponse> =>
  fetchMenu("beerstreet", "https://beerstreet.cz/data/beers.json", async (r) => parseBeerStreetJson(await r.json()), deps);

export const fetchAmbasadaMenu = (deps?: FetchMenuDeps): Promise<MenuResponse> =>
  fetchMenu("ambasada", "https://pivniambasada.cz/", parseAmbasadaHtml, deps);

export const fetchToulavapipaMenu = (deps?: FetchMenuDeps): Promise<MenuResponse> =>
  fetchMenu(
    "toulavapipa",
    `${TOULAVA_PIPA_SHEET_BASE}?gid=0&single=true&output=csv`,
    async (r) => parseToulavapipaCsv(await r.text(), "toulavapipa"),
    deps,
  );

export const fetchLodotavaMenu = (deps?: FetchMenuDeps): Promise<MenuResponse> =>
  fetchMenu(
    "lodotava",
    `${TOULAVA_PIPA_SHEET_BASE}?gid=310545451&single=true&output=csv`,
    async (r) => parseToulavapipaCsv(await r.text(), "lodotava"),
    deps,
  );

export const fetchUzamastiluMenu = (deps?: FetchMenuDeps): Promise<MenuResponse> =>
  fetchMenu("uzamastilu", "https://uzamastilu.cz/data", async (r) => parseUzamastiluJson(await r.json()), deps);
