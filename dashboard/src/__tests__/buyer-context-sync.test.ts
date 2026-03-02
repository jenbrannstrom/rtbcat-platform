import { describe, it, expect } from "vitest";
import { resolveCanonicalBuyerId } from "@/lib/buyer-context-sync";
import type { BuyerSeat } from "@/types/api";

const seats: BuyerSeat[] = [
  {
    buyer_id: "111",
    bidder_id: "1",
    display_name: "Seat 111",
    active: true,
    creative_count: 1,
    last_synced: null,
    created_at: null,
  },
  {
    buyer_id: "222",
    bidder_id: "1",
    display_name: "Seat 222",
    active: true,
    creative_count: 1,
    last_synced: null,
    created_at: null,
  },
];

describe("resolveCanonicalBuyerId", () => {
  it("prefers URL buyer when seats are not loaded yet", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: "222",
      selectedBuyerId: "111",
      seats: undefined,
    });
    expect(result.canonicalBuyerId).toBe("222");
    expect(result.seatsLoaded).toBe(false);
  });

  it("uses selected buyer when seats are not loaded and URL has no buyer", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: null,
      selectedBuyerId: "111",
      seats: undefined,
    });
    expect(result.canonicalBuyerId).toBe("111");
    expect(result.seatsLoaded).toBe(false);
  });

  it("keeps valid URL buyer as canonical when seats are loaded", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: "222",
      selectedBuyerId: "111",
      seats,
    });
    expect(result.canonicalBuyerId).toBe("222");
    expect(result.buyerInPathValid).toBe(true);
    expect(result.selectedBuyerValid).toBe(true);
  });

  it("falls back to selected buyer when URL buyer is invalid", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: "999",
      selectedBuyerId: "111",
      seats,
    });
    expect(result.canonicalBuyerId).toBe("111");
    expect(result.buyerInPathValid).toBe(false);
    expect(result.selectedBuyerValid).toBe(true);
  });

  it("falls back to first active seat when URL and selected buyer are both invalid", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: "999",
      selectedBuyerId: "888",
      seats,
    });
    expect(result.canonicalBuyerId).toBe("111");
    expect(result.buyerInPathValid).toBe(false);
    expect(result.selectedBuyerValid).toBe(false);
  });

  it("returns null when no active seats exist", () => {
    const result = resolveCanonicalBuyerId({
      buyerIdInPath: "999",
      selectedBuyerId: "888",
      seats: [],
    });
    expect(result.canonicalBuyerId).toBeNull();
    expect(result.buyerInPathValid).toBe(false);
    expect(result.selectedBuyerValid).toBe(false);
    expect(result.seatsLoaded).toBe(true);
  });
});
