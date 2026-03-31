import { describe, expect, it } from "vitest";

import { buildLanguageCountryComparison } from "@/components/preview-modal/utils";

describe("buildLanguageCountryComparison", () => {
  it("prefers configured target countries over serving countries", () => {
    const result = buildLanguageCountryComparison("en", ["US"], ["BR", "JP"]);

    expect(result.basis).toBe("targeting");
    expect(result.countryCodes).toEqual(["US"]);
    expect(result.match.isMatch).toBe(true);
    expect(result.match.mismatchedCountries).toEqual([]);
  });

  it("falls back to serving countries when target countries are unavailable", () => {
    const result = buildLanguageCountryComparison("en", [], ["BR", "JP"]);

    expect(result.basis).toBe("serving");
    expect(result.countryCodes).toEqual(["BR", "JP"]);
    expect(result.match.isMatch).toBe(false);
    expect(result.match.mismatchedCountries).toEqual(["BR", "JP"]);
  });

  it("normalizes and deduplicates country codes", () => {
    const result = buildLanguageCountryComparison("en", ["us", "US", " us "], []);

    expect(result.basis).toBe("targeting");
    expect(result.countryCodes).toEqual(["US"]);
  });
});
