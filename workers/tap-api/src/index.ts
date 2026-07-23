import { corsHeaders, handlePreflight, isAllowedOrigin } from "./cors";
import { fetchAmbasadaMenu, fetchBeerStreetMenu, fetchUzamastiluMenu } from "./sources";
import type { MenuResponse, Source } from "./schema";

type MenuFetcher = () => Promise<MenuResponse>;

const ROUTES: Record<string, { source: Source; fetcher: MenuFetcher }> = {
  "/beerstreet": { source: "beerstreet", fetcher: fetchBeerStreetMenu },
  "/ambasada": { source: "ambasada", fetcher: fetchAmbasadaMenu },
  "/uzamastilu": { source: "uzamastilu", fetcher: fetchUzamastiluMenu },
};

export default {
  async fetch(request: Request): Promise<Response> {
    if (request.method === "OPTIONS") {
      return handlePreflight(request);
    }

    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405 });
    }

    const origin = request.headers.get("Origin") ?? "";
    if (!isAllowedOrigin(origin)) {
      return new Response("Forbidden", { status: 403 });
    }

    const { pathname } = new URL(request.url);
    const route = ROUTES[pathname];
    if (!route) {
      return json({ error: "not_found" }, 404, origin);
    }

    try {
      const menu = await route.fetcher();
      return json(menu, 200, origin);
    } catch (error) {
      console.error(`upstream_failed source=${route.source}`, error);
      return json({ error: "upstream_failed", source: route.source }, 502, origin);
    }
  },
} satisfies ExportedHandler;

function json(body: unknown, status: number, origin: string): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...corsHeaders(origin),
    },
  });
}
