import { describe, expect, it } from "vitest";

import {
  getBuyerContextUpdateTarget,
  getBuyerScopedRouteReplaceTarget,
  getNonScopedRouteCleanupTarget,
} from "@/lib/buyer-route-sync-logic";

describe("getBuyerContextUpdateTarget", () => {
  it("returns null for non-scoped pages", () => {
    const target = getBuyerContextUpdateTarget({
      isScoped: false,
      seatsLoaded: false,
      buyerIdInPath: "222",
      selectedBuyerId: "111",
      canonicalBuyerId: "222",
    });
    expect(target).toBeNull();
  });

  it("seeds context from URL buyer before seats are loaded", () => {
    const target = getBuyerContextUpdateTarget({
      isScoped: true,
      seatsLoaded: false,
      buyerIdInPath: "222",
      selectedBuyerId: "111",
      canonicalBuyerId: "111",
    });
    expect(target).toBe("222");
  });

  it("returns canonical buyer when seats are loaded and selected is stale", () => {
    const target = getBuyerContextUpdateTarget({
      isScoped: true,
      seatsLoaded: true,
      buyerIdInPath: "999",
      selectedBuyerId: "111",
      canonicalBuyerId: "222",
    });
    expect(target).toBe("222");
  });

  it("returns null when selected buyer already matches canonical buyer", () => {
    const target = getBuyerContextUpdateTarget({
      isScoped: true,
      seatsLoaded: true,
      buyerIdInPath: "222",
      selectedBuyerId: "222",
      canonicalBuyerId: "222",
    });
    expect(target).toBeNull();
  });
});

describe("getBuyerScopedRouteReplaceTarget", () => {
  it("injects selected buyer into scoped URL before seats load when path has no buyer", () => {
    const target = getBuyerScopedRouteReplaceTarget({
      isScoped: true,
      seatsLoaded: false,
      buyerIdInPath: null,
      selectedBuyerId: "222",
      pathname: "/campaigns",
      queryString: "days=7",
      currentUrl: "/campaigns?days=7",
      canonicalBuyerId: "222",
    });
    expect(target).toBe("/222/campaigns?days=7");
  });

  it("does not override explicit URL buyer before seats load", () => {
    const target = getBuyerScopedRouteReplaceTarget({
      isScoped: true,
      seatsLoaded: false,
      buyerIdInPath: "111",
      selectedBuyerId: "222",
      pathname: "/111/campaigns",
      queryString: "",
      currentUrl: "/111/campaigns",
      canonicalBuyerId: "111",
    });
    expect(target).toBeNull();
  });

  it("normalizes scoped URL to canonical buyer after seats load", () => {
    const target = getBuyerScopedRouteReplaceTarget({
      isScoped: true,
      seatsLoaded: true,
      buyerIdInPath: "111",
      selectedBuyerId: "111",
      pathname: "/111/campaigns",
      queryString: "",
      currentUrl: "/111/campaigns",
      canonicalBuyerId: "222",
    });
    expect(target).toBe("/222/campaigns");
  });
});

describe("getNonScopedRouteCleanupTarget", () => {
  it("strips buyer prefix from non-scoped routes", () => {
    const target = getNonScopedRouteCleanupTarget({
      buyerIdInPath: "222",
      isScoped: false,
      pathWithoutBuyer: "/settings/system",
      queryString: "tab=models",
      currentUrl: "/222/settings/system?tab=models",
    });
    expect(target).toBe("/settings/system?tab=models");
  });

  it("returns null when route is buyer-scoped", () => {
    const target = getNonScopedRouteCleanupTarget({
      buyerIdInPath: "222",
      isScoped: true,
      pathWithoutBuyer: "/campaigns",
      queryString: "",
      currentUrl: "/222/campaigns",
    });
    expect(target).toBeNull();
  });
});

