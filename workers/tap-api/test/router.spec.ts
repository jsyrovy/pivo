import { describe, it, expect, beforeAll, afterEach } from "vitest";
import { SELF, fetchMock } from "cloudflare:test";
import {
  AMBASADA_FIXTURE,
  BEERSTREET_FIXTURE,
  LODOTAVA_CLOSED_FIXTURE,
  TOULAVA_PIPA_FIXTURE,
  UZAMASTILU_FIXTURE,
} from "./fixtures";

const ALLOWED_ORIGIN = "https://pivo.jsyrovy.cz";
const LOCAL_ORIGIN = "http://localhost:8000";
const TOULAVA_PIPA_SHEET_PATH =
  "/spreadsheets/d/e/2PACX-1vSgPAMETGHHgIC7ND6p79_D5WVCtrU6UBCwEm32LFZfK5eOKoXQYtuklEfAfvixIuHHiYjUBnhYG2PH/pub";

beforeAll(() => {
  fetchMock.activate();
  fetchMock.disableNetConnect();
});

afterEach(() => {
  fetchMock.assertNoPendingInterceptors();
});

function call(path: string, init: RequestInit = {}): Promise<Response> {
  return SELF.fetch(`https://tap-api.test${path}`, init);
}

describe("router", () => {
  it.each([ALLOWED_ORIGIN, LOCAL_ORIGIN])("returns BeerStreet menu with CORS headers for %s", async (origin) => {
    fetchMock
      .get("https://beerstreet.cz")
      .intercept({ path: "/data/beers.json" })
      .reply(200, JSON.stringify(BEERSTREET_FIXTURE), {
        headers: { "Content-Type": "application/json" },
      });

    const res = await call("/beerstreet", {
      headers: { Origin: origin },
    });

    expect(res.status).toBe(200);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(origin);
    expect(res.headers.get("Content-Type")).toContain("application/json");

    const body = (await res.json()) as {
      source: string;
      beers: Array<{ name: string; order: number | null }>;
    };
    expect(body.source).toBe("beerstreet");
    expect(body.beers).toHaveLength(3);
    expect(body.beers[0].name).toBe("Pilsner Urquell");
  });

  it("returns Ambasada menu parsed from HTML", async () => {
    fetchMock
      .get("https://pivniambasada.cz")
      .intercept({ path: "/" })
      .reply(200, AMBASADA_FIXTURE, {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });

    const res = await call("/ambasada", {
      headers: { Origin: ALLOWED_ORIGIN },
    });

    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      source: string;
      beers: Array<{ name: string; order: number }>;
    };
    expect(body.source).toBe("ambasada");
    expect(body.beers.map((b) => b.order)).toEqual([1, 2, 3]);
  });

  it("returns U Zámastilů menu parsed from JSON", async () => {
    fetchMock
      .get("https://uzamastilu.cz")
      .intercept({ path: "/data" })
      .reply(200, JSON.stringify(UZAMASTILU_FIXTURE), {
        headers: { "Content-Type": "application/json" },
      });

    const res = await call("/uzamastilu", {
      headers: { Origin: ALLOWED_ORIGIN },
    });

    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      source: string;
      beers: Array<{ name: string; order: number | null }>;
    };
    expect(body.source).toBe("uzamastilu");
    expect(body.beers.map((b) => b.order)).toEqual([1, 5, 3]);
  });

  it("returns Toulavá Pípa menu parsed from CSV", async () => {
    fetchMock
      .get("https://docs.google.com")
      .intercept({ path: `${TOULAVA_PIPA_SHEET_PATH}?gid=0&single=true&output=csv` })
      .reply(200, TOULAVA_PIPA_FIXTURE, {
        headers: { "Content-Type": "text/csv; charset=utf-8" },
      });

    const res = await call("/toulavapipa", {
      headers: { Origin: ALLOWED_ORIGIN },
    });

    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      source: string;
      beers: Array<{ name: string; order: number | null }>;
    };
    expect(body.source).toBe("toulavapipa");
    expect(body.beers.map((b) => b.order)).toEqual([1, 2, 3, 4]);
  });

  it("returns Loď Otava menu (closed) as an empty list", async () => {
    fetchMock
      .get("https://docs.google.com")
      .intercept({ path: `${TOULAVA_PIPA_SHEET_PATH}?gid=310545451&single=true&output=csv` })
      .reply(200, LODOTAVA_CLOSED_FIXTURE, {
        headers: { "Content-Type": "text/csv; charset=utf-8" },
      });

    const res = await call("/lodotava", {
      headers: { Origin: ALLOWED_ORIGIN },
    });

    expect(res.status).toBe(200);
    const body = (await res.json()) as { source: string; beers: unknown[] };
    expect(body.source).toBe("lodotava");
    expect(body.beers).toEqual([]);
  });

  it("rejects requests from disallowed origin with 403", async () => {
    const res = await call("/beerstreet", {
      headers: { Origin: "https://evil.example" },
    });
    expect(res.status).toBe(403);
  });

  it("rejects non-GET methods with 405", async () => {
    const res = await call("/beerstreet", {
      method: "POST",
      headers: { Origin: ALLOWED_ORIGIN },
    });
    expect(res.status).toBe(405);
  });

  it("returns 404 for unknown paths", async () => {
    const res = await call("/does-not-exist", {
      headers: { Origin: ALLOWED_ORIGIN },
    });
    expect(res.status).toBe(404);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ALLOWED_ORIGIN);
  });

  it("returns 502 when upstream fails", async () => {
    fetchMock
      .get("https://beerstreet.cz")
      .intercept({ path: "/data/beers.json" })
      .reply(500, "boom");

    const res = await call("/beerstreet", {
      headers: { Origin: ALLOWED_ORIGIN },
    });

    expect(res.status).toBe(502);
    const body = (await res.json()) as { error: string; source: string; message: string };
    expect(body).toEqual({
      error: "upstream_failed",
      source: "beerstreet",
      message: "beerstreet upstream returned 500",
    });
  });

  it("handles OPTIONS preflight from allowed origin", async () => {
    const res = await call("/beerstreet", {
      method: "OPTIONS",
      headers: { Origin: ALLOWED_ORIGIN },
    });
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Methods")).toBe("GET, OPTIONS");
    expect(res.headers.get("Access-Control-Max-Age")).toBe("86400");
  });

  it("rejects OPTIONS preflight from disallowed origin", async () => {
    const res = await call("/beerstreet", {
      method: "OPTIONS",
      headers: { Origin: "https://evil.example" },
    });
    expect(res.status).toBe(403);
  });
});
