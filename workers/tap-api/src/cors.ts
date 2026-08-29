const ALLOWED_ORIGINS = ["https://pivo.jsyrovy.cz"];

// Local dev servers get in on any port and either scheme (mkcert-style setups serve https).
// `null` -- the origin of `file://` pages -- deliberately stays out: sandboxed iframes on any site
// send it too, so allowing it would hand the API to every website.
const LOCAL_HOSTNAMES = ["localhost", "127.0.0.1", "[::1]"];

function isLocalOrigin(origin: string): boolean {
  try {
    const { protocol, hostname } = new URL(origin);
    return (protocol === "http:" || protocol === "https:") && LOCAL_HOSTNAMES.includes(hostname);
  } catch {
    return false;
  }
}

export function isAllowedOrigin(origin: string): boolean {
  return ALLOWED_ORIGINS.includes(origin) || isLocalOrigin(origin);
}

export function corsHeaders(origin: string): HeadersInit {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
}

export function handlePreflight(request: Request): Response {
  const origin = request.headers.get("Origin") ?? "";
  if (!isAllowedOrigin(origin)) {
    return new Response("Forbidden", { status: 403 });
  }
  return new Response(null, {
    status: 204,
    headers: {
      ...corsHeaders(origin),
      "Access-Control-Max-Age": "86400",
    },
  });
}
