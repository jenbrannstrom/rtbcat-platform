/**
 * Utility functions for the preview modal.
 */

import type { Creative, CreativePerformanceSummary } from "@/types/api";

// ============================================================================
// Formatting Helpers
// ============================================================================

export function formatSpend(microDollars: number | null | undefined): string {
  if (!microDollars) return "$0";
  const dollars = microDollars / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  return `$${dollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(n: number | null | undefined): string {
  if (!n) return "0";
  return n.toLocaleString();
}

export function formatCTR(ctr: number | null | undefined): string {
  if (ctr === null || ctr === undefined) return "-";
  return `${ctr.toFixed(2)}%`;
}

export function formatCostMetric(micros: number | null | undefined): string {
  if (!micros) return "-";
  const dollars = micros / 1_000_000;
  return `$${dollars.toFixed(2)}`;
}

// ============================================================================
// Data Notes (Factual observations, not judgments)
// ============================================================================

export type DataNote = {
  icon: "info" | "alert";
  message: string;
};

export function getDataNotes(creative: Creative, performance?: CreativePerformanceSummary): DataNote[] {
  const notes: DataNote[] = [];

  if (!performance?.has_data) {
    return [];
  }

  const imps = performance.total_impressions || 0;
  const clicks = performance.total_clicks || 0;
  const clicksAvailable = performance.clicks_available !== false;

  // Only show click-related notes when clicks data is actually available
  if (clicksAvailable) {
    // Clicks exceed impressions
    if (clicks > imps && imps > 0) {
      notes.push({
        icon: "alert",
        message: `Clicks (${clicks.toLocaleString()}) exceed impressions (${imps.toLocaleString()})`,
      });
    }

    // Zero clicks with impressions (legitimate data quality observation)
    if (clicks === 0 && imps > 100) {
      notes.push({
        icon: "info",
        message: `Zero clicks recorded across ${imps.toLocaleString()} impressions`,
      });
    }
  }

  // Video-specific note
  if (creative.format === "VIDEO") {
    notes.push({
      icon: "info",
      message: "Video completion data not available",
    });
  }

  return notes;
}

// ============================================================================
// Tracking Parameters Extraction
// ============================================================================

export function extractTrackingParams(url: string | null | undefined): Record<string, string> {
  if (!url) return {};
  const params: Record<string, string> = {};
  try {
    const urlObj = new URL(url.startsWith("http") ? url : `https://${url}`);
    const trackingPrefixes = [
      "utm_", "af_", "adjust_", "c_", "pid", "campaign", "adgroup",
      "ad_id", "creative_id", "clickid", "gclid", "fbclid", "ttclid",
    ];

    urlObj.searchParams.forEach((value, key) => {
      const keyLower = key.toLowerCase();
      if (trackingPrefixes.some((prefix) => keyLower.startsWith(prefix) || keyLower === prefix)) {
        params[key] = value;
      }
    });
  } catch {
    // Invalid URL
  }
  return params;
}

// ============================================================================
// Language to Country Mapping
// ============================================================================

export const LANGUAGE_TO_COUNTRIES: Record<string, string[]> = {
  "en": ["US", "GB", "CA", "AU", "NZ", "IE", "ZA", "SG", "IN", "PH", "NG", "KE", "GH"],
  "de": ["DE", "AT", "CH", "LI", "LU", "BE"],
  "fr": ["FR", "BE", "CH", "CA", "LU", "MC", "SN", "CI", "ML", "BF", "NE", "TG", "BJ", "MG"],
  "es": ["ES", "MX", "AR", "CO", "PE", "VE", "CL", "EC", "GT", "CU", "DO", "BO", "HN", "PY", "SV", "NI", "CR", "PA", "UY", "PR"],
  "it": ["IT", "CH", "SM", "VA"],
  "pt": ["PT", "BR", "AO", "MZ", "CV", "GW", "ST", "TL", "MO"],
  "nl": ["NL", "BE", "SR", "CW", "AW", "SX"],
  "pl": ["PL"],
  "ru": ["RU", "BY", "KZ", "KG"],
  "ja": ["JP"],
  "ko": ["KR", "KP"],
  "zh": ["CN", "TW", "HK", "MO", "SG"],
  "ar": ["SA", "EG", "AE", "IQ", "JO", "KW", "LB", "LY", "MA", "OM", "QA", "SD", "SY", "TN", "YE", "DZ", "BH"],
  "hi": ["IN"],
  "tr": ["TR", "CY"],
  "th": ["TH"],
  "vi": ["VN"],
  "id": ["ID"],
  "ms": ["MY", "SG", "BN"],
  "sv": ["SE", "FI"],
  "da": ["DK", "GL", "FO"],
  "no": ["NO"],
  "fi": ["FI"],
  "cs": ["CZ"],
  "el": ["GR", "CY"],
  "he": ["IL"],
  "hu": ["HU"],
  "ro": ["RO", "MD"],
  "uk": ["UA"],
  "bg": ["BG"],
};

export function checkLanguageCountryMatch(languageCode: string | null, countryCodes: string[]): {
  isMatch: boolean;
  matchingCountries: string[];
  mismatchedCountries: string[];
} {
  if (!languageCode || countryCodes.length === 0) {
    return { isMatch: true, matchingCountries: [], mismatchedCountries: [] };
  }

  const expectedCountries = new Set(LANGUAGE_TO_COUNTRIES[languageCode.toLowerCase()] || []);
  const servingCountries = new Set(countryCodes.map(c => c.toUpperCase()));

  const matching = [...servingCountries].filter(c => expectedCountries.has(c));
  const mismatched = [...servingCountries].filter(c => !expectedCountries.has(c));

  return {
    isMatch: matching.length > 0 || mismatched.length === 0,
    matchingCountries: matching,
    mismatchedCountries: mismatched,
  };
}

export type LanguageCountryComparison = {
  basis: "none" | "serving" | "targeting";
  countryCodes: string[];
  match: ReturnType<typeof checkLanguageCountryMatch>;
};

function normalizeCountryCodes(countryCodes: string[] | null | undefined): string[] {
  const normalized = new Set<string>();
  for (const code of countryCodes || []) {
    const value = (code || "").trim().toUpperCase();
    if (value) normalized.add(value);
  }
  return Array.from(normalized);
}

export function buildLanguageCountryComparison(
  languageCode: string | null,
  targetCountryCodes: string[] | null | undefined,
  servingCountryCodes: string[] | null | undefined,
): LanguageCountryComparison {
  const normalizedTargetCountryCodes = normalizeCountryCodes(targetCountryCodes);
  if (normalizedTargetCountryCodes.length > 0) {
    return {
      basis: "targeting",
      countryCodes: normalizedTargetCountryCodes,
      match: checkLanguageCountryMatch(languageCode, normalizedTargetCountryCodes),
    };
  }

  const normalizedServingCountryCodes = normalizeCountryCodes(servingCountryCodes);
  if (normalizedServingCountryCodes.length > 0) {
    return {
      basis: "serving",
      countryCodes: normalizedServingCountryCodes,
      match: checkLanguageCountryMatch(languageCode, normalizedServingCountryCodes),
    };
  }

  return {
    basis: "none",
    countryCodes: [],
    match: checkLanguageCountryMatch(languageCode, []),
  };
}
