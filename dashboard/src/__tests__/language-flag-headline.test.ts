import { describe, expect, it } from "vitest";

import { buildLanguageFlagHeadline } from "@/lib/language-flag-headline";
import { en } from "@/lib/i18n/translations/en";
import type { CreativeLanguageFlagCoverageRow } from "@/types/api";

const missingLanguage: CreativeLanguageFlagCoverageRow = {
  creative_id: "banner",
  creative_name: "Test banner",
  buyer_id: null,
  format: "HTML",
  approval_status: "APPROVED",
  detected_language: null,
  detected_language_code: null,
  heuristic_language_code: null,
  effective_language_code: null,
  serving_countries: ["KR"],
  language_flag_status: "orange",
  language_flag_reason: "No language detection for KOR serving",
  language_flag_source: "missing",
  geo_linguistic_status: "orange",
  geo_linguistic_reason: "No AI geo-linguistic report yet",
  detected_currencies: [],
  currency_flag_status: "orange",
  currency_flag_reason: "No obvious market currency detected",
  geo_linguistic_decision: "not_run",
  geo_linguistic_completed_at: null,
  spend_30d_micros: 0,
  impressions_30d: 0,
  last_active_date: null,
  is_active: true,
};

describe("language flag headlines", () => {
  it("labels a failed or missing analysis as needing review", () => {
    const headline = buildLanguageFlagHeadline(missingLanguage, en.creatives);
    expect(headline.title).toBe(en.creatives.languageFlagsNeedsReview);
    expect(headline.title.toLowerCase()).not.toContain("mismatch");
  });

  it("retains the mismatch fallback for a confirmed red finding", () => {
    const headline = buildLanguageFlagHeadline({
      ...missingLanguage,
      geo_linguistic_status: "red",
      geo_linguistic_reason: "Currency conflicts with serving market",
    }, en.creatives);
    expect(headline.title).toBe(en.creatives.languageFlagsHeadlineFallback);
  });

  it("uses the normal language and country headline when detection succeeds", () => {
    const headline = buildLanguageFlagHeadline({
      ...missingLanguage,
      detected_language: "Korean",
      detected_language_code: "ko",
      effective_language_code: "ko",
      language_flag_status: "green",
      geo_linguistic_status: "green",
    }, en.creatives);
    expect(headline.title).toContain("Korean");
    expect(headline.title).toContain("South Korea");
  });
});
