import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getJson, killSwitch } from "@/lib/api";
import { formatMoney, formatPct, signClass } from "@/lib/format";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(impl: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => Promise.resolve(impl(url, init))),
  );
}

describe("api client", () => {
  it("parses a JSON body on 200", async () => {
    mockFetch(() => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await expect(getJson<{ ok: boolean }>("/api/v1/health")).resolves.toEqual({ ok: true });
  });

  it("throws ApiError on a non-2xx", async () => {
    mockFetch(() => new Response("nope", { status: 503 }));
    await expect(getJson("/api/v1/health")).rejects.toBeInstanceOf(ApiError);
  });

  it("sends the Operator token header on kill", async () => {
    let seen: RequestInit | undefined;
    mockFetch((_url, init) => {
      seen = init;
      return new Response(null, { status: 200 });
    });
    await killSwitch("secret-token", "runaway");
    expect(seen?.method).toBe("POST");
    expect((seen?.headers as Record<string, string>)["X-Operator-Token"]).toBe("secret-token");
  });
});

describe("format", () => {
  it("formats money strings without float drift in accounting", () => {
    expect(formatMoney("1000000", "USD")).toContain("1,000,000");
  });
  it("defaults to INR (₹) with Indian digit grouping", () => {
    const out = formatMoney("500000"); // 5,00,000 in en-IN grouping
    expect(out).toContain("₹");
    expect(out).toContain("5,00,000");
  });
  it("formats percentages", () => {
    expect(formatPct("0.1234")).toBe("12.34%");
  });
  it("classifies sign", () => {
    expect(signClass("5")).toBe("pos");
    expect(signClass("-5")).toBe("neg");
    expect(signClass("0")).toBe("");
  });
});
