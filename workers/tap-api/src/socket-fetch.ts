import { connect } from "cloudflare:sockets";

// Some upstreams (pivniambasada.cz behind WEDOS Global Protection) reject the
// Workers fetch() egress path with 401 no matter what headers we send, while a
// plain TCP+TLS connection to the same host succeeds. This module speaks just
// enough HTTP/1.1 over a raw socket to serve as a fallback for those hosts.

export type ConnectFn = (address: SocketAddress, options?: SocketOptions) => Socket;

export interface FetchViaSocketOptions {
  userAgent?: string;
  timeoutMs?: number;
  connectFn?: ConnectFn;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_USER_AGENT = "tap-api/1.0";
const CRLF = "\r\n";

// Headers that describe the hop, not the payload; re-attaching them to a
// Response we build ourselves would contradict the decoded body.
const HOP_BY_HOP_HEADERS = ["transfer-encoding", "content-length", "connection", "keep-alive"];

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

export function buildGetRequest(url: URL, userAgent: string): string {
  return [
    `GET ${url.pathname}${url.search} HTTP/1.1`,
    `Host: ${url.host}`,
    `User-Agent: ${userAgent}`,
    "Accept: text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Encoding: identity",
    "Connection: close",
    "",
    "",
  ].join(CRLF);
}

export function splitHeadAndBody(bytes: Uint8Array): { head: string; body: Uint8Array } | null {
  for (let i = 0; i <= bytes.length - 4; i++) {
    if (bytes[i] === 13 && bytes[i + 1] === 10 && bytes[i + 2] === 13 && bytes[i + 3] === 10) {
      return {
        head: textDecoder.decode(bytes.subarray(0, i)),
        body: bytes.subarray(i + 4),
      };
    }
  }
  return null;
}

export function parseStatusLine(head: string): number {
  const firstLine = head.split(CRLF)[0] ?? "";
  const match = /^HTTP\/1\.[01]\s+(\d{3})/.exec(firstLine);
  if (!match) {
    throw new Error(`Cannot parse response status line: ${firstLine}`);
  }
  return Number(match[1]);
}

export function parseHeaders(head: string): Headers {
  const headers = new Headers();
  for (const line of head.split(CRLF).slice(1)) {
    const separator = line.indexOf(":");
    if (separator === -1) {
      continue;
    }
    headers.append(line.slice(0, separator).trim(), line.slice(separator + 1).trim());
  }
  return headers;
}

export function decodeChunked(body: Uint8Array): Uint8Array {
  const chunks: Uint8Array[] = [];
  let offset = 0;
  while (offset < body.length) {
    const lineEnd = indexOfCrlf(body, offset);
    if (lineEnd === -1) {
      break;
    }
    const sizeLine = textDecoder.decode(body.subarray(offset, lineEnd)).split(";")[0]?.trim() ?? "";
    const size = Number.parseInt(sizeLine, 16);
    if (!size) {
      break;
    }
    const chunkStart = lineEnd + 2;
    chunks.push(body.subarray(chunkStart, chunkStart + size));
    offset = chunkStart + size + 2;
  }
  return concatAll(chunks);
}

function indexOfCrlf(bytes: Uint8Array, start: number): number {
  for (let i = start; i < bytes.length - 1; i++) {
    if (bytes[i] === 13 && bytes[i + 1] === 10) {
      return i;
    }
  }
  return -1;
}

function concatAll(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

async function readAll(reader: ReadableStreamDefaultReader<Uint8Array>): Promise<Uint8Array> {
  const chunks: Uint8Array[] = [];
  for (;;) {
    const { value, done } = await reader.read();
    if (value) {
      chunks.push(value);
    }
    if (done) {
      return concatAll(chunks);
    }
  }
}

// Never awaited: with allowHalfOpen: false the socket already tears itself down
// at EOF, and close() can then stay pending forever. Awaiting it in a finally
// block deadlocks the request even after the body has been read in full.
function closeQuietly(socket: Socket): void {
  try {
    void socket.close().catch(() => {});
  } catch {
    // Already closed.
  }
}

async function performRequest(socket: Socket, target: URL, userAgent: string): Promise<Response> {
  const writer = socket.writable.getWriter();
  try {
    await writer.write(textEncoder.encode(buildGetRequest(target, userAgent)));
  } finally {
    writer.releaseLock();
  }

  const reader = socket.readable.getReader();
  let raw: Uint8Array;
  try {
    raw = await readAll(reader);
  } finally {
    reader.releaseLock();
  }

  const split = splitHeadAndBody(raw);
  if (!split) {
    throw new Error("Upstream closed the connection before headers were complete");
  }

  const status = parseStatusLine(split.head);
  const headers = parseHeaders(split.head);

  const encoding = headers.get("Content-Encoding")?.toLowerCase();
  if (encoding && encoding !== "identity") {
    throw new Error(`Upstream ignored Accept-Encoding: identity and sent ${encoding}`);
  }

  const body =
    headers.get("Transfer-Encoding")?.toLowerCase() === "chunked" ? decodeChunked(split.body) : split.body;

  for (const name of HOP_BY_HOP_HEADERS) {
    headers.delete(name);
  }

  // 1xx/204/304 must not carry a body.
  const bodyless = status < 200 || status === 204 || status === 304;
  return new Response(bodyless ? null : body, { status, headers });
}

export async function fetchViaSocket(url: string, options?: FetchViaSocketOptions): Promise<Response> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const connectFn = options?.connectFn ?? connect;
  const userAgent = options?.userAgent ?? DEFAULT_USER_AGENT;

  const target = new URL(url);
  const secure = target.protocol === "https:";
  const port = target.port ? Number(target.port) : secure ? 443 : 80;

  const socket = connectFn(
    { hostname: target.hostname, port },
    { secureTransport: secure ? "on" : "off", allowHalfOpen: false },
  );

  let timeoutId: number | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      closeQuietly(socket);
      reject(new Error(`Socket request to ${target.hostname} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  try {
    return await Promise.race([performRequest(socket, target, userAgent), timeout]);
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    closeQuietly(socket);
  }
}
