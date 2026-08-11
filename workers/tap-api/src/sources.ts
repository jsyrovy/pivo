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

// The same upstreams sometimes tarpit the egress instead of answering, and
// fetch() has no timeout of its own, so a stalled request hangs the Worker
// until the platform kills it. Bound it and treat a stall as a block too.
const FETCH_TIMEOUT_MS = 5_000;

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
  let response: Response | undefined;
  let blocked: string | undefined;

  try {
    response = await deps.fetchImpl(url, {
      headers: { "User-Agent": USER_AGENT },
      cf: { cacheTtl: 0, cacheEverything: false },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
  } catch (error) {
    blocked = `fetch failed: ${errorMessage(error)}`;
  }

  if (response && SOCKET_FALLBACK_STATUSES.has(response.status)) {
    blocked = `upstream returned ${response.status}`;
  }

  if (!blocked) {
    const ok = response as Response;
    if (!ok.ok) {
      throw new Error(`${source} upstream returned ${ok.status}`);
    }
    return { source, fetchedAt: new Date().toISOString(), beers: await parse(ok) };
  }

  console.info("socket_fallback", { source, blocked });

  let viaSocket: Response;
  try {
    viaSocket = await deps.socketFetch(url, { userAgent: USER_AGENT });
  } catch (error) {
    throw new Error(`${source} ${blocked}, socket fallback failed: ${errorMessage(error)}`);
  }

  if (!viaSocket.ok) {
    throw new Error(`${source} upstream returned ${viaSocket.status} (via socket)`);
  }

  return {
    source,
    fetchedAt: new Date().toISOString(),
    beers: await parse(viaSocket),
    viaSocket: true,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
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
