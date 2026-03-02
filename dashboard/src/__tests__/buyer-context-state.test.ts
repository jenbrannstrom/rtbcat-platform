import { describe, it, expect } from "vitest";
import {
  deriveBuyerContextState,
  type BuyerContextValidity,
} from "@/lib/buyer-context-state";
import type { BuyerSeat } from "@/types/api";

const seat = (id: string): BuyerSeat => ({
  buyer_id: id,
  bidder_id: "1",
  display_name: `Seat ${id}`,
  active: true,
  creative_count: 1,
  last_synced: null,
  created_at: null,
});

const seats: BuyerSeat[] = [seat("111"), seat("222")];

describe("deriveBuyerContextState", () => {
  it("returns loading when seats are still being fetched", () => {
    const state = deriveBuyerContextState("111", undefined, true);
    expect(state.validity).toBe<BuyerContextValidity>("loading");
    expect(state.canQuery).toBe(false);
  });

  it("returns loading when seats are undefined even if not explicitly loading", () => {
    const state = deriveBuyerContextState("111", undefined, false);
    expect(state.validity).toBe<BuyerContextValidity>("loading");
    expect(state.canQuery).toBe(false);
  });

  it("returns no_active_seats when loaded seats array is empty", () => {
    const state = deriveBuyerContextState("111", [], false);
    expect(state.validity).toBe<BuyerContextValidity>("no_active_seats");
    expect(state.canQuery).toBe(false);
    expect(state.message).toContain("No active buyer seats");
  });

  it("returns selected_buyer_invalid when selectedBuyerId is null", () => {
    const state = deriveBuyerContextState(null, seats, false);
    expect(state.validity).toBe<BuyerContextValidity>("selected_buyer_invalid");
    expect(state.canQuery).toBe(false);
    expect(state.message).toContain("not an active seat");
  });

  it("returns selected_buyer_invalid when selected buyer is not in seats", () => {
    const state = deriveBuyerContextState("999", seats, false);
    expect(state.validity).toBe<BuyerContextValidity>("selected_buyer_invalid");
    expect(state.canQuery).toBe(false);
  });

  it("returns selected_buyer_valid when selected buyer is in the seat list", () => {
    const state = deriveBuyerContextState("111", seats, false);
    expect(state.validity).toBe<BuyerContextValidity>("selected_buyer_valid");
    expect(state.canQuery).toBe(true);
    expect(state.message).toContain("111");
  });

  it("returns selected_buyer_valid for the second seat", () => {
    const state = deriveBuyerContextState("222", seats, false);
    expect(state.validity).toBe<BuyerContextValidity>("selected_buyer_valid");
    expect(state.canQuery).toBe(true);
  });

  it("returns selected_buyer_invalid for empty string buyer id", () => {
    const state = deriveBuyerContextState("", seats, false);
    expect(state.validity).toBe<BuyerContextValidity>("selected_buyer_invalid");
    expect(state.canQuery).toBe(false);
  });
});
