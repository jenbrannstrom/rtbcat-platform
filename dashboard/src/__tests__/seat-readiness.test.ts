import { describe, expect, it } from "vitest";
import { isSeatReadyForAnalytics } from "@/lib/seat-readiness";

describe("isSeatReadyForAnalytics", () => {
  it("returns false when no selected buyer is set", () => {
    expect(isSeatReadyForAnalytics(null, [{ buyer_id: "111" }])).toBe(false);
  });

  it("returns false when seats are not loaded", () => {
    expect(isSeatReadyForAnalytics("111", undefined)).toBe(false);
    expect(isSeatReadyForAnalytics("111", null)).toBe(false);
  });

  it("returns false when selected buyer is not in active seats", () => {
    expect(
      isSeatReadyForAnalytics("999", [
        { buyer_id: "111" },
        { buyer_id: "222" },
      ]),
    ).toBe(false);
  });

  it("returns true when selected buyer is in active seats", () => {
    expect(
      isSeatReadyForAnalytics("222", [
        { buyer_id: "111" },
        { buyer_id: "222" },
      ]),
    ).toBe(true);
  });
});
