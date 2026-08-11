import { describe, it, expect, vi } from "vitest";
import { fetchBeerStreetMenu, type FetchMenuDeps } from "../src/sources";
import { BEERSTREET_FIXTURE } from "./fixtures";

function jsonResponse(status: number, body: unknown = BEERSTREET_FIXTURE): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("fetchMenu socket fallback", () => {
  it("does not fall back on a 200 response", async () => {
    const socketFetch = vi.fn();
    const menu = await fetchBeerStreetMenu({
      fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(200))),
      socketFetch,
    });

    expect(socketFetch).not.toHaveBeenCalled();
    expect(menu.viaSocket).toBeUndefined();
    expect(menu.beers).toHaveLength(3);
  });

  it("falls back to the socket on a 401 and marks viaSocket", async () => {
    const deps: FetchMenuDeps = {
      fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(401))),
      socketFetch: vi.fn(() => Promise.resolve(jsonResponse(200))),
    };

    const menu = await fetchBeerStreetMenu(deps);

    expect(deps.socketFetch).toHaveBeenCalledTimes(1);
    expect(menu.viaSocket).toBe(true);
    expect(menu.beers).toHaveLength(3);
  });

  it("falls back to the socket on a 403", async () => {
    const deps: FetchMenuDeps = {
      fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(403))),
      socketFetch: vi.fn(() => Promise.resolve(jsonResponse(200))),
    };

    const menu = await fetchBeerStreetMenu(deps);

    expect(deps.socketFetch).toHaveBeenCalledTimes(1);
    expect(menu.viaSocket).toBe(true);
  });

  it("does not fall back on a 500 and throws the original error", async () => {
    const socketFetch = vi.fn();
    await expect(
      fetchBeerStreetMenu({ fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(500))), socketFetch }),
    ).rejects.toThrow("beerstreet upstream returned 500");
    expect(socketFetch).not.toHaveBeenCalled();
  });

  it("reports both the original status and the socket failure reason", async () => {
    const deps: FetchMenuDeps = {
      fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(401))),
      socketFetch: vi.fn(() => Promise.reject(new Error("timed out"))),
    };

    await expect(fetchBeerStreetMenu(deps)).rejects.toThrow(
      "beerstreet upstream returned 401, socket fallback failed: timed out",
    );
  });

  it("surfaces a non-ok status returned by the socket fallback", async () => {
    const deps: FetchMenuDeps = {
      fetchImpl: vi.fn(() => Promise.resolve(jsonResponse(401))),
      socketFetch: vi.fn(() => Promise.resolve(jsonResponse(503))),
    };

    await expect(fetchBeerStreetMenu(deps)).rejects.toThrow("beerstreet upstream returned 503 (via socket)");
  });
});
