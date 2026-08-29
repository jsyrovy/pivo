import { describe, it, expect } from "vitest";
import { isAllowedOrigin } from "../src/cors";

describe("isAllowedOrigin", () => {
  it("allows the production site", () => {
    expect(isAllowedOrigin("https://pivo.jsyrovy.cz")).toBe(true);
  });

  it("allows local dev servers on any port", () => {
    expect(isAllowedOrigin("http://localhost:8000")).toBe(true);
    expect(isAllowedOrigin("http://localhost")).toBe(true);
    expect(isAllowedOrigin("https://localhost:5173")).toBe(true);
    expect(isAllowedOrigin("http://127.0.0.1:5500")).toBe(true);
    expect(isAllowedOrigin("http://[::1]:8787")).toBe(true);
  });

  it("rejects hostnames that merely look local", () => {
    expect(isAllowedOrigin("http://localhost.evil.example")).toBe(false);
    expect(isAllowedOrigin("https://evil.example")).toBe(false);
    expect(isAllowedOrigin("https://pivo.jsyrovy.cz.evil.example")).toBe(false);
  });

  it("rejects non-HTTP schemes on local hostnames", () => {
    expect(isAllowedOrigin("ws://localhost:8000")).toBe(false);
  });

  it("rejects file:// pages and missing origins", () => {
    expect(isAllowedOrigin("null")).toBe(false);
    expect(isAllowedOrigin("")).toBe(false);
  });
});
