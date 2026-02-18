import { describe, it, expect, vi, beforeEach } from "vitest";
import { SELECTED_BUYER_COOKIE } from "@/lib/buyer-routes";

// Mock Next.js server modules before importing middleware
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
const { middleware } = await import("@/middleware");
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

describe("middleware - skip paths", () => {
  it("skips static assets", () => {
    const result = middleware(makeRequest("/favicon.ico"));
    expect(result.type).toBe("next");
  });

  it("skips _next paths", () => {
    const result = middleware(makeRequest("/_next/static/chunk.js"));
    expect(result.type).toBe("next");
  });

  it("skips API paths", () => {
    const result = middleware(makeRequest("/api/health"));
    expect(result.type).toBe("next");
  });

  it("skips file extensions", () => {
    const result = middleware(makeRequest("/logo.png"));
    expect(result.type).toBe("next");
  });
});

describe("middleware - legacy aliases", () => {
  it("does not redirect /creatives (real route)", () => {
    const result = middleware(makeRequest("/creatives"));
    expect(mockRedirect).not.toHaveBeenCalledWith(expect.stringContaining("/clusters"));
  });

  it("redirects /uploads to /import", () => {
    const result = middleware(makeRequest("/uploads"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith(expect.stringContaining("/import"));
  });

  it("redirects /waste-analysis to /", () => {
    const result = middleware(makeRequest("/waste-analysis"));
    expect(result.type).toBe("redirect");
  });

  it("preserves buyer prefix on legacy alias redirect", () => {
    const result = middleware(makeRequest("/42/creatives"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/clusters");
  });

  it("injects cookie buyer into alias redirect when no prefix", () => {
    const result = middleware(
      makeRequest("/creatives", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/clusters");
  });

  it("redirects legacy pretargeting publishers route to canonical bill_id route", () => {
    const result = middleware(makeRequest("/pretargeting/167604111024/publishers"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/bill_id/167604111024?tab=publishers");
  });

  it("redirects buyer-prefixed legacy pretargeting route to buyer bill_id route", () => {
    const result = middleware(makeRequest("/42/pretargeting/167604111024/publishers"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/167604111024?tab=publishers");
  });

  it("injects cookie buyer into legacy pretargeting route redirect", () => {
    const result = middleware(
      makeRequest("/pretargeting/167604111024/publishers", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/167604111024?tab=publishers");
  });
});

describe("middleware - buyer prefix normalization", () => {
  it("strips buyer prefix from non-scoped pages", () => {
    const result = middleware(makeRequest("/42/settings"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/settings");
  });

  it("strips buyer prefix from admin pages", () => {
    const result = middleware(makeRequest("/42/admin"));
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/admin");
  });
});

describe("middleware - cookie injection for scoped pages", () => {
  it("injects buyer cookie into scoped page without prefix", () => {
    const result = middleware(
      makeRequest("/campaigns", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/campaigns");
  });

  it("injects buyer cookie into root path", () => {
    const result = middleware(
      makeRequest("/", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42");
  });

  it("does not redirect when no cookie is set", () => {
    const result = middleware(makeRequest("/campaigns"));
    expect(result.type).toBe("next");
  });

  it("does not redirect when cookie is invalid", () => {
    const result = middleware(
      makeRequest("/campaigns", { [SELECTED_BUYER_COOKIE]: "abc" })
    );
    expect(result.type).toBe("next");
  });

  it("passes through when buyer prefix already present", () => {
    const result = middleware(
      makeRequest("/42/campaigns", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("next");
  });
});

describe("middleware - bill_id paths", () => {
  it("treats /bill_id as buyer-scoped", () => {
    const result = middleware(
      makeRequest("/bill_id/100", { [SELECTED_BUYER_COOKIE]: "42" })
    );
    expect(result.type).toBe("redirect");
    expect(mockRedirect).toHaveBeenCalledWith("/42/bill_id/100");
  });

  it("passes through buyer-prefixed bill_id path", () => {
    const result = middleware(makeRequest("/42/bill_id/100"));
    expect(result.type).toBe("next");
  });
});
