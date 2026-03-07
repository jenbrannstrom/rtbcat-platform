import { describe, it, expect, vi, beforeEach } from "vitest";
import { SELECTED_BUYER_COOKIE } from "@/lib/buyer-routes";

// Mock Next.js server modules before importing proxy
const mockRedirect = vi.fn();
const mockNext = vi.fn();

vi.mock("next/server", () => {
  type CloneableUrl = URL & { clone(): CloneableUrl };

  class MockNextResponse {
    static redirect(url: URL) {
      mockRedirect(url.pathname + url.search);
      return { type: "redirect", url: url.pathname };
    }
    static next() {
      mockNext();
      return { type: "next" };
    }
  }

  class MockNextRequest {
    nextUrl: URL & { clone(): URL };
    cookies: Map<string, { value: string }>;
    headers: Headers;

    constructor(url: string, opts?: { cookies?: Record<string, string> }) {
      const parsed = new URL(url, "http://localhost:3000");
      // Add clone() method that Next.js NextURL provides
      const cloneableParsed = parsed as CloneableUrl;
      cloneableParsed.clone = () => {
        const cloned = new URL(parsed.href) as CloneableUrl;
        cloned.clone = cloneableParsed.clone;
        return cloned;
      };
      this.nextUrl = cloneableParsed;
      this.cookies = new Map();
      this.headers = new Headers();
      if (opts?.cookies) {
        for (const [k, v] of Object.entries(opts.cookies)) {
          this.cookies.set(k, { value: v });
        }
      }
    }
  }

  return { NextRequest: MockNextRequest, NextResponse: MockNextResponse };
});

// Import after mocking
const { proxy } = await import("@/proxy");
const { NextRequest } = await import("next/server");

function makeRequest(
  pathname: string,
  cookies?: Record<string, string>
): InstanceType<typeof NextRequest> {
  const NextRequestCtor = NextRequest as unknown as {
    new (
      url: string,
      opts?: { cookies?: Record<string, string> }
    ): InstanceType<typeof NextRequest>;
  };
  return new NextRequestCtor(
    `http://localhost:3000${pathname}`,
    { cookies }
  );
}

beforeEach(() => {
  mockRedirect.mockClear();
  mockNext.mockClear();
});

describe("proxy - skip paths", () => {
  it("skips static assets", () => {
    const result = proxy(makeRequest("/favicon.ico"));
    expect(result.type).toBe("next");
  });

  it("skips _next paths", () => {
    const result = proxy(makeRequest("/_next/static/chunk.js"));
    expect(result.type).toBe("next");
  });

  it("skips API paths", () => {
    const result = proxy(makeRequest("/api/health"));
    expect(result.type).toBe("next");
  });

  it("skips file extensions", () => {
    const result = proxy(makeRequest("/logo.png"));
    expect(result.type).toBe("next");
  });
});

describe("proxy - legacy aliases", () => {
  it("does not redirect /creatives (real route)", () => {
    const result = proxy(makeRequest("/creatives"));
    expect(mockRedirect).not.toHaveBeenCalledWith(expect.stringContaining("/clusters"));
  });

  it("redirects /uploads to /import", () => {
    const result = proxy(makeRequest("/uploads"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith(expect.stringContaining("/import"));
  });

  it("redirects /waste-analysis to /", () => {
    const result = proxy(makeRequest("/waste-analysis"));
    expect(result.type).toBe("redirect");
  });

  it("preserves buyer prefix on legacy alias redirect", () => {
    const result = proxy(makeRequest("/42/creatives"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/clusters");
  });

  it("injects cookie buyer into alias redirect when no prefix", () => {
    const result = proxy(
      makeRequest("/creatives", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/clusters");
  });

  it("redirects legacy pretargeting publishers route to canonical bill_id route", () => {
    const result = proxy(makeRequest("/pretargeting/666666666666/publishers"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/bill_id/666666666666?tab=publishers");
  });

  it("redirects buyer-prefixed legacy pretargeting route to buyer bill_id route", () => {
    const result = proxy(makeRequest("/42/pretargeting/666666666666/publishers"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/666666666666?tab=publishers");
  });

  it("injects cookie buyer into legacy pretargeting route redirect", () => {
    const result = proxy(
      makeRequest("/pretargeting/666666666666/publishers", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/666666666666?tab=publishers");
  });
});

describe("proxy - buyer prefix normalization", () => {
  it("strips buyer prefix from non-scoped pages", () => {
    const result = proxy(makeRequest("/42/settings"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/settings");
  });

  it("strips buyer prefix from admin pages", () => {
    const result = proxy(makeRequest("/42/admin"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/admin");
  });
});

describe("proxy - cookie injection for scoped pages", () => {
  it("injects buyer cookie into scoped page without prefix", () => {
    const result = proxy(
      makeRequest("/campaigns", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/campaigns");
  });

  it("injects buyer cookie into root path", () => {
    const result = proxy(
      makeRequest("/", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42");
  });

  it("does not redirect when no cookie is set", () => {
    const result = proxy(makeRequest("/campaigns"));
    expect(result.type).toBe("next");
  });

  it("does not redirect when cookie is invalid", () => {
    const result = proxy(
      makeRequest("/campaigns", { [SELECTED_BUYER_COOKIE]: "abc" })
    );
    expect(result.type).toBe("next");
  });

  it("passes through when buyer prefix already present", () => {
    const result = proxy(
      makeRequest("/42/campaigns", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("next");
  });
});

describe("proxy - bill_id paths", () => {
  it("treats /bill_id as buyer-scoped", () => {
    const result = proxy(
      makeRequest("/bill_id/100", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/100");
  });

  it("passes through buyer-prefixed bill_id path", () => {
    const result = proxy(makeRequest("/42/bill_id/100"));
    expect(result.type).toBe("next");
  });
});
