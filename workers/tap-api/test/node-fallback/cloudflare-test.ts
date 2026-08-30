// Stands in for `cloudflare:test` in the Node fallback pool.
//
// SELF calls the worker's exported fetch() directly instead of going through a real workerd
// instance, and fetchMock reimplements the slice of undici's MockAgent that router.spec.ts uses on
// top of a stubbed global fetch. Consequences worth knowing before trusting a green run: there is
// no Worker isolate, no request/response validation by the runtime, and no Cloudflare-specific
// request handling -- `cf` init options are simply ignored.
import worker from "../../src/index";

interface Reply {
  status: number;
  body: string;
  headers: Record<string, string>;
}

interface Interceptor {
  origin: string;
  path: string;
  method: string;
  reply: Reply | null;
  consumed: boolean;
}

const interceptors: Interceptor[] = [];
let originalFetch: typeof globalThis.fetch | null = null;
let netConnect = true;

function toRecord(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) return {};
  return Object.fromEntries(new Headers(headers).entries());
}

function handle(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = new Request(input as string, init);
  const url = new URL(request.url);
  const target = `${url.pathname}${url.search}`;

  const match = interceptors.find(
    (i) => !i.consumed && i.origin === url.origin && i.path === target && i.method === request.method,
  );

  if (!match?.reply) {
    if (netConnect) return (originalFetch ?? fetch)(input, init);
    return Promise.reject(new TypeError(`fetch failed: no interceptor for ${request.method} ${request.url}`));
  }

  match.consumed = true;
  return Promise.resolve(new Response(match.reply.body, { status: match.reply.status, headers: match.reply.headers }));
}

class MockPool {
  constructor(private readonly origin: string) {}

  intercept(options: { path: string; method?: string }): { reply: (status: number, body?: string, init?: { headers?: Record<string, string> }) => void } {
    const interceptor: Interceptor = {
      origin: this.origin,
      path: options.path,
      method: options.method ?? "GET",
      reply: null,
      consumed: false,
    };
    interceptors.push(interceptor);
    return {
      reply(status, body = "", init) {
        interceptor.reply = { status, body, headers: toRecord(init?.headers) };
      },
    };
  }
}

export const fetchMock = {
  activate(): void {
    if (originalFetch) return;
    originalFetch = globalThis.fetch;
    globalThis.fetch = handle as typeof globalThis.fetch;
  },

  deactivate(): void {
    if (originalFetch) globalThis.fetch = originalFetch;
    originalFetch = null;
    netConnect = true;
    interceptors.length = 0;
  },

  disableNetConnect(): void {
    netConnect = false;
  },

  enableNetConnect(): void {
    netConnect = true;
  },

  get(origin: string): MockPool {
    return new MockPool(origin);
  },

  assertNoPendingInterceptors(): void {
    const pending = interceptors.filter((i) => !i.consumed);
    interceptors.length = 0;
    if (pending.length > 0) {
      const list = pending.map((i) => `${i.method} ${i.origin}${i.path}`).join(", ");
      throw new Error(`Pending interceptors: ${list}`);
    }
  },
};

export const SELF = {
  fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    return worker.fetch(new Request(input as string, init));
  },
};
