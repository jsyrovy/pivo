// Fallback config: runs the suite in plain Node instead of workerd.
//
// Use it only where workerd cannot start -- notably arm64 kernels with a 39-bit virtual address
// space (Raspberry Pi OS), where the tcmalloc workerd links against aborts before any spec loads.
// The worker runtime is replaced by the shims in test/node-fallback/, so a green run here is
// weaker evidence than `npm test`. See AGENTS.md.
//
// Paths are root-relative (leading slash) rather than resolved via node:url, because tsconfig
// deliberately loads only the Workers types -- no node globals.
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "cloudflare:sockets": "/test/node-fallback/cloudflare-sockets.ts",
      "cloudflare:test": "/test/node-fallback/cloudflare-test.ts",
    },
  },
  test: {
    include: ["test/**/*.spec.ts"],
    setupFiles: ["./test/node-fallback/setup.ts"],
  },
});
