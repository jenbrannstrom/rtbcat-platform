import { describe, it, expect } from "vitest";
import {
  isBuyerIdSegment,
  splitBuyerPath,
  isBuyerScopedPath,
  toBuyerScopedPath,
  replaceBuyerInPath,
} from "@/lib/buyer-routes";

describe("isBuyerIdSegment", () => {
  it("returns true for numeric strings", () => {
    expect(isBuyerIdSegment("12345")).toBe(true);
    expect(isBuyerIdSegment("0")).toBe(true);
    expect(isBuyerIdSegment("999999")).toBe(true);
  });

  it("returns false for non-numeric strings", () => {
    expect(isBuyerIdSegment("abc")).toBe(false);
    expect(isBuyerIdSegment("12a")).toBe(false);
    expect(isBuyerIdSegment("")).toBe(false);
    expect(isBuyerIdSegment("clusters")).toBe(false);
  });
});

describe("splitBuyerPath", () => {
  it("extracts buyer ID from path prefix", () => {
    const result = splitBuyerPath("/12345/campaigns");
    expect(result).toEqual({
      buyerIdInPath: "12345",
      hasBuyerPrefix: true,
      pathWithoutBuyer: "/campaigns",
    });
  });

  it("handles buyer-only path", () => {
    const result = splitBuyerPath("/12345");
    expect(result).toEqual({
      buyerIdInPath: "12345",
      hasBuyerPrefix: true,
      pathWithoutBuyer: "/",
    });
  });

  it("returns null buyer for non-numeric prefix", () => {
    const result = splitBuyerPath("/clusters");
    expect(result).toEqual({
      buyerIdInPath: null,
      hasBuyerPrefix: false,
      pathWithoutBuyer: "/clusters",
    });
  });

  it("handles root path", () => {
    const result = splitBuyerPath("/");
    expect(result).toEqual({
      buyerIdInPath: null,
      hasBuyerPrefix: false,
      pathWithoutBuyer: "/",
    });
  });

  it("handles deeply nested buyer-scoped paths", () => {
    const result = splitBuyerPath("/42/pretargeting/100/publishers");
    expect(result).toEqual({
      buyerIdInPath: "42",
      hasBuyerPrefix: true,
      pathWithoutBuyer: "/pretargeting/100/publishers",
    });
  });

  it("handles bill_id paths", () => {
    const result = splitBuyerPath("/42/bill_id/100");
    expect(result).toEqual({
      buyerIdInPath: "42",
      hasBuyerPrefix: true,
      pathWithoutBuyer: "/bill_id/100",
    });
  });
});

describe("isBuyerScopedPath", () => {
  it("returns true for buyer-scoped paths", () => {
    expect(isBuyerScopedPath("/")).toBe(true);
    expect(isBuyerScopedPath("/campaigns")).toBe(true);
    expect(isBuyerScopedPath("/campaigns/123")).toBe(true);
    expect(isBuyerScopedPath("/clusters")).toBe(true);
    expect(isBuyerScopedPath("/history")).toBe(true);
    expect(isBuyerScopedPath("/import")).toBe(true);
    expect(isBuyerScopedPath("/pretargeting")).toBe(true);
    expect(isBuyerScopedPath("/pretargeting/100/publishers")).toBe(true);
    expect(isBuyerScopedPath("/qps")).toBe(true);
    expect(isBuyerScopedPath("/qps/publisher")).toBe(true);
    expect(isBuyerScopedPath("/bill_id")).toBe(true);
    expect(isBuyerScopedPath("/bill_id/100")).toBe(true);
  });

  it("returns false for non-buyer-scoped paths", () => {
    expect(isBuyerScopedPath("/admin")).toBe(false);
    expect(isBuyerScopedPath("/admin/users")).toBe(false);
    expect(isBuyerScopedPath("/settings")).toBe(false);
    expect(isBuyerScopedPath("/settings/seats")).toBe(false);
    expect(isBuyerScopedPath("/login")).toBe(false);
    expect(isBuyerScopedPath("/api/something")).toBe(false);
    expect(isBuyerScopedPath("/connect")).toBe(false);
    expect(isBuyerScopedPath("/setup")).toBe(false);
  });
});

describe("toBuyerScopedPath", () => {
  it("prepends buyer ID to scoped paths", () => {
    expect(toBuyerScopedPath("/campaigns", "42")).toBe("/42/campaigns");
    expect(toBuyerScopedPath("/clusters", "42")).toBe("/42/clusters");
    expect(toBuyerScopedPath("/bill_id/100", "42")).toBe("/42/bill_id/100");
  });

  it("handles root path", () => {
    expect(toBuyerScopedPath("/", "42")).toBe("/42");
  });

  it("strips existing buyer and re-applies new one", () => {
    expect(toBuyerScopedPath("/99/campaigns", "42")).toBe("/42/campaigns");
  });

  it("returns path unchanged for non-scoped paths", () => {
    expect(toBuyerScopedPath("/settings", "42")).toBe("/settings");
    expect(toBuyerScopedPath("/admin", "42")).toBe("/admin");
  });

  it("returns path without buyer when buyerId is null", () => {
    expect(toBuyerScopedPath("/campaigns", null)).toBe("/campaigns");
    expect(toBuyerScopedPath("/42/campaigns", null)).toBe("/campaigns");
  });
});

describe("replaceBuyerInPath", () => {
  it("delegates to toBuyerScopedPath", () => {
    expect(replaceBuyerInPath("/99/campaigns", "42")).toBe("/42/campaigns");
    expect(replaceBuyerInPath("/settings", "42")).toBe("/settings");
  });
});
