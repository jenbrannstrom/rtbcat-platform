import { describe, expect, it } from "vitest";

import { getGeoLinguisticBadgeStatus } from "@/components/preview-modal/utils";

describe("getGeoLinguisticBadgeStatus", () => {
  it("keeps explicit review decisions as orange badges", () => {
    expect(
      getGeoLinguisticBadgeStatus({
        geo_linguistic_status: "orange",
        geo_linguistic_decision: "needs_review",
        geo_linguistic_reason: "Spanish word mixed into English content",
      }),
    ).toBe("orange");
  });

  it("suppresses orange badges when the run is merely pending", () => {
    expect(
      getGeoLinguisticBadgeStatus({
        geo_linguistic_status: "orange",
        geo_linguistic_decision: null,
        geo_linguistic_reason: "AI report pending",
      }),
    ).toBeNull();
  });

  it("suppresses orange badges when no AI report has run yet", () => {
    expect(
      getGeoLinguisticBadgeStatus({
        geo_linguistic_status: "orange",
        geo_linguistic_decision: "not_run",
        geo_linguistic_reason: "No AI geo-linguistic report yet",
      }),
    ).toBeNull();
  });

  it("preserves green and red outcomes", () => {
    expect(
      getGeoLinguisticBadgeStatus({
        geo_linguistic_status: "green",
        geo_linguistic_decision: "match",
        geo_linguistic_reason: "Hindi text served in India - perfect match",
      }),
    ).toBe("green");

    expect(
      getGeoLinguisticBadgeStatus({
        geo_linguistic_status: "red",
        geo_linguistic_decision: "mismatch",
        geo_linguistic_reason: "English creative served only in Japan",
      }),
    ).toBe("red");
  });
});
