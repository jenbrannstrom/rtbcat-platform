import type { Creative, CreativeLanguageFlagCoverageRow } from "@/types/api";
import type { Translations } from "@/lib/i18n/types";
import { countryFlag, getCountryName, getLanguageName } from "@/lib/language-country-map";

type CreativeStrings = Translations["creatives"];

export type LanguageFlagSeverity = "confirmed" | "review" | "ok";

export function getLanguageFlagSeverity(row: CreativeLanguageFlagCoverageRow): LanguageFlagSeverity {
  if (row.language_flag_status === "red" || row.geo_linguistic_status === "red") {
    return "confirmed";
  }
  if (row.language_flag_status === "orange" || row.geo_linguistic_status === "orange") {
    return "review";
  }
  return "ok";
}

function formatCountries(countries: string[], t: CreativeStrings, locale?: string): string | null {
  const normalized = countries.filter(Boolean).map((country) => country.toUpperCase());
  if (normalized.length === 0) return null;

  const visible = normalized.slice(0, 2).map((country) => {
    const name = getCountryName(country, locale) || country;
    const flag = countryFlag(country);
    return flag ? `${name} ${flag}` : name;
  });
  if (normalized.length > visible.length) {
    visible.push(t.languageFlagsCountryMore.replace("{count}", String(normalized.length - visible.length)));
  }
  return visible.join(", ");
}

function localizeReason(reason: string, locale?: string): string {
  if (!locale?.startsWith("zh")) return reason;
  const mismatch = reason.match(/^([A-Z]{2,3}) mismatches ([A-Z]{2,3})$/);
  if (!mismatch) return reason;
  const languageName = getLanguageName(mismatch[1].toLowerCase(), mismatch[1], locale);
  const countryName = getCountryName(mismatch[2], locale) || mismatch[2];
  return `${languageName}与${countryName}不匹配`;
}

function replaceTokens(template: string, tokens: Record<string, string>): string {
  return Object.entries(tokens).reduce(
    (result, [key, value]) => result.replace(`{${key}}`, value),
    template
  );
}

export function buildLanguageFlagHeadline(
  row: CreativeLanguageFlagCoverageRow,
  t: CreativeStrings,
  locale?: string
): { title: string; subtitle: string } {
  const severity = getLanguageFlagSeverity(row);
  const languageName = getLanguageName(
    row.effective_language_code || row.detected_language_code,
    row.detected_language,
    locale
  );
  const countries = formatCountries(row.serving_countries || [], t, locale);

  let title = t.languageFlagsHeadlineFallback;
  if (languageName && countries) {
    const template = severity === "review"
      ? t.languageFlagsHeadlineReview
      : severity === "ok"
      ? t.languageFlagsHeadlineOk
      : t.languageFlagsHeadlineConfirmed;
    title = replaceTokens(template, {
      language: languageName,
      country: countries,
    });
  }

  const geoIsRed = row.geo_linguistic_status === "red";
  const geoIsOrange = row.geo_linguistic_status === "orange";
  const languageReason = row.language_flag_reason || "";
  const geoReason = row.geo_linguistic_reason || "";
  const preferredReason = geoIsRed || (geoIsOrange && row.language_flag_status !== "red")
    ? geoReason
    : languageReason || geoReason;
  const currencyNote = row.detected_currencies.length > 0 && row.currency_flag_status !== "green"
    ? t.languageFlagsCurrencyNote.replace("{currencies}", row.detected_currencies.join(", "))
    : "";
  const subtitle = [localizeReason(preferredReason, locale), currencyNote].filter(Boolean).join(" · ");

  return {
    title,
    subtitle: subtitle || `#${row.creative_id}`,
  };
}

export function getPreviewCreative(row: CreativeLanguageFlagCoverageRow): Creative | null {
  return row.preview_creative || null;
}
