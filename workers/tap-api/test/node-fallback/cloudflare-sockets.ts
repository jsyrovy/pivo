// Stands in for `cloudflare:sockets` in the Node fallback pool. src/socket-fetch.ts imports
// connect() at module scope, so without this alias every spec that transitively imports it dies at
// import time -- even the ones that inject their own connectFn and never touch a real socket.
//
// Nothing in the suite exercises the real connect(), so throwing is the honest behaviour: a test
// that ends up here is a test the fallback cannot vouch for.
export function connect(): never {
  throw new Error("cloudflare:sockets is unavailable outside workerd (Node fallback pool)");
}
