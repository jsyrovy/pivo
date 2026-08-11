import { describe, it, expect, vi } from "vitest";
import {
  buildGetRequest,
  decodeChunked,
  fetchViaSocket,
  parseHeaders,
  parseStatusLine,
  splitHeadAndBody,
} from "../src/socket-fetch";

function encode(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

function createFakeSocket(
  responseChunks: Uint8Array[],
  close: () => Promise<void> = () => Promise.resolve(),
): { socket: Socket; written: Uint8Array[] } {
  const written: Uint8Array[] = [];
  const socket = {
    readable: new ReadableStream({
      start(controller) {
        for (const chunk of responseChunks) {
          controller.enqueue(chunk);
        }
        controller.close();
      },
    }),
    writable: new WritableStream({
      write(chunk: Uint8Array) {
        written.push(chunk);
      },
    }),
    close,
  } as unknown as Socket;
  return { socket, written };
}

function writtenText(chunks: Uint8Array[]): string {
  return chunks.map((c) => new TextDecoder().decode(c)).join("");
}

describe("buildGetRequest", () => {
  it("targets the destination host and disables compression", () => {
    const request = buildGetRequest(new URL("https://pivniambasada.cz/menu?x=1"), "tap-api/1.0");
    expect(request).toContain("GET /menu?x=1 HTTP/1.1");
    expect(request).toContain("Host: pivniambasada.cz");
    expect(request).toContain("Accept-Encoding: identity");
    expect(request).toContain("Connection: close");
  });
});

describe("splitHeadAndBody", () => {
  it("splits at the first blank line", () => {
    const result = splitHeadAndBody(encode("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"));
    expect(result?.head).toBe("HTTP/1.1 200 OK\r\nContent-Length: 2");
    expect(new TextDecoder().decode(result?.body)).toBe("hi");
  });

  it("returns null when the terminator is missing", () => {
    expect(splitHeadAndBody(encode("HTTP/1.1 200 OK\r\n"))).toBeNull();
  });
});

describe("parseStatusLine", () => {
  it("extracts the numeric status code", () => {
    expect(parseStatusLine("HTTP/1.1 200 OK")).toBe(200);
    expect(parseStatusLine("HTTP/1.1 404 Not Found")).toBe(404);
  });

  it("throws on a malformed status line", () => {
    expect(() => parseStatusLine("garbage")).toThrow();
  });
});

describe("parseHeaders", () => {
  it("parses header lines after the status line", () => {
    const headers = parseHeaders("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nX-Foo: bar");
    expect(headers.get("Content-Type")).toBe("text/html");
    expect(headers.get("X-Foo")).toBe("bar");
  });
});

describe("decodeChunked", () => {
  it("decodes chunked bodies", () => {
    expect(new TextDecoder().decode(decodeChunked(encode("4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n")))).toBe("Wikipedia");
  });
});

describe("fetchViaSocket", () => {
  it("connects with TLS on 443 and returns the parsed response", async () => {
    const body = "hello world";
    const fake = createFakeSocket([
      encode(`HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: ${body.length}\r\n\r\n${body}`),
    ]);
    const connectFn = vi.fn(() => fake.socket);

    const response = await fetchViaSocket("https://pivniambasada.cz/", { connectFn });

    expect(response.status).toBe(200);
    expect(await response.text()).toBe(body);
    expect(response.headers.get("Content-Type")).toBe("text/plain");

    expect(connectFn).toHaveBeenCalledWith(
      { hostname: "pivniambasada.cz", port: 443 },
      { secureTransport: "on", allowHalfOpen: false },
    );
    expect(writtenText(fake.written)).toContain("GET / HTTP/1.1");
  });

  it("uses port 80 without TLS for http URLs", async () => {
    const fake = createFakeSocket([encode("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")]);
    const connectFn = vi.fn(() => fake.socket);

    await fetchViaSocket("http://example.com/", { connectFn });

    expect(connectFn).toHaveBeenCalledWith(
      { hostname: "example.com", port: 80 },
      { secureTransport: "off", allowHalfOpen: false },
    );
  });

  it("decodes a chunked response", async () => {
    const fake = createFakeSocket([
      encode("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n"),
    ]);
    const response = await fetchViaSocket("https://example.com/", { connectFn: () => fake.socket });
    expect(await response.text()).toBe("Wikipedia");
  });

  it("reassembles a body split across several socket reads", async () => {
    const fake = createFakeSocket([
      encode("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"),
      encode("\r\nfirst "),
      encode("second"),
    ]);
    const response = await fetchViaSocket("https://example.com/", { connectFn: () => fake.socket });
    expect(await response.text()).toBe("first second");
  });

  it("strips hop-by-hop headers that no longer match the decoded body", async () => {
    const fake = createFakeSocket([
      encode("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n2\r\nhi\r\n0\r\n\r\n"),
    ]);
    const response = await fetchViaSocket("https://example.com/", { connectFn: () => fake.socket });
    expect(response.headers.get("Transfer-Encoding")).toBeNull();
    expect(response.headers.get("Connection")).toBeNull();
    expect(await response.text()).toBe("hi");
  });

  it("propagates a non-200 status", async () => {
    const fake = createFakeSocket([encode("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")]);
    const response = await fetchViaSocket("https://example.com/missing", { connectFn: () => fake.socket });
    expect(response.status).toBe(404);
  });

  it("rejects a compressed body it cannot decode", async () => {
    const fake = createFakeSocket([encode("HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\nbinary")]);
    await expect(fetchViaSocket("https://example.com/", { connectFn: () => fake.socket })).rejects.toThrow(
      /Accept-Encoding: identity/,
    );
  });

  it("resolves even when close() never settles", async () => {
    // allowHalfOpen: false makes the runtime tear the socket down at EOF, after
    // which close() can stay pending forever. Awaiting it deadlocked the request.
    const fake = createFakeSocket(
      [encode("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi")],
      () => new Promise<void>(() => {}),
    );

    const response = await fetchViaSocket("https://example.com/", { connectFn: () => fake.socket, timeoutMs: 1000 });

    expect(response.status).toBe(200);
    expect(await response.text()).toBe("hi");
  });

  it("throws when the connection closes before headers are complete", async () => {
    const fake = createFakeSocket([encode("HTTP/1.1 200 OK\r\nContent-Ty")]);
    await expect(fetchViaSocket("https://example.com/", { connectFn: () => fake.socket })).rejects.toThrow(
      /before headers were complete/,
    );
  });
});
