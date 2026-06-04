import type { Translations } from "@/lib/i18n";
import type { GeoMismatchResponse } from "@/types/api";

type LanguageSignalContext = Pick<
  GeoMismatchResponse,
  | "serving_countries"
  | "primary_text_language"
  | "primary_text_language_code"
  | "secondary_text_language"
  | "secondary_text_language_code"
  | "secondary_text_sample"
>;

type ReasonLocalizationMessages = Pick<
  Translations["previewModal"],
  | "localizedCtaMixReasonTemplate"
  | "localizedPlaintextLanguageSummaryTemplate"
  | "localizedAiWordMixReasonTemplate"
>;

const LANGUAGE_NAME_TO_CODE: Record<string, string> = {
  arabic: "ar",
  burmese: "my",
  chinese: "zh",
  english: "en",
  french: "fr",
  german: "de",
  hindi: "hi",
  italian: "it",
  japanese: "ja",
  korean: "ko",
  portuguese: "pt",
  russian: "ru",
  spanish: "es",
};

const ALPHA3_TO_ALPHA2: Record<string, string> = {
  ARE: "AE",
  AUS: "AU",
  CAN: "CA",
  CHN: "CN",
  DEU: "DE",
  ESP: "ES",
  FRA: "FR",
  GBR: "GB",
  HKG: "HK",
  IND: "IN",
  IRL: "IE",
  ITA: "IT",
  JPN: "JP",
  KOR: "KR",
  MEX: "MX",
  MYS: "MY",
  MMR: "MM",
  NZL: "NZ",
  PHL: "PH",
  PRT: "PT",
  RUS: "RU",
  SGP: "SG",
  TWN: "TW",
  USA: "US",
  ZAF: "ZA",
};

const CTA_MIX_REASON_RE =
  /^[A-Za-z]+ CTA '.*' mixed into [A-Za-z-]+ creative serving in .+$/i;
const AI_MIX_REASON_RE =
  /^[A-Za-z]+ word '.*'(?: \(.+\))? mixed (?:into|with) [A-Za-z-]+(?:-dominant)? (?:creative|primary content) served (?:to|in) .+$/i;

function shouldLocalizeLocale(locale: string): boolean {
  return !locale.toLowerCase().startsWith("en");
}

function normalizeDisplayLocale(locale: string): string {
  return locale.toLowerCase().startsWith("zh") ? "zh-Hans" : locale;
}

function normalizeLanguageCode(code: string | null | undefined): string | null {
  const value = (code || "").trim().toLowerCase();
  return value || null;
}

function inferLanguageCode(name: string | null | undefined): string | null {
  const normalizedName = (name || "").trim().toLowerCase();
  return normalizedName ? LANGUAGE_NAME_TO_CODE[normalizedName] || null : null;
}

function getDisplayNames(locale: string, type: "language" | "region"): Intl.DisplayNames | null {
  if (typeof Intl.DisplayNames !== "function") return null;
  try {
    return new Intl.DisplayNames([normalizeDisplayLocale(locale)], { type });
  } catch {
    return null;
  }
}

function getListFormatter(locale: string): Intl.ListFormat | null {
  if (typeof Intl.ListFormat !== "function") return null;
  try {
    return new Intl.ListFormat([normalizeDisplayLocale(locale)], {
      style: "long",
      type: "conjunction",
    });
  } catch {
    return null;
  }
}

function localizeLanguageName(
  locale: string,
  code: string | null | undefined,
  fallbackName: string | null | undefined,
): string {
  const resolvedCode = normalizeLanguageCode(code) || inferLanguageCode(fallbackName);
  const localized = resolvedCode ? getDisplayNames(locale, "language")?.of(resolvedCode) : null;
  return (localized || fallbackName || resolvedCode || "").trim();
}

function normalizeRegionCode(code: string): string {
  const value = (code || "").trim().toUpperCase();
  if (value.length === 2) return value;
  if (value.length === 3) return ALPHA3_TO_ALPHA2[value] || value;
  return value;
}

function localizeServingCountries(locale: string, countryCodes: string[]): string | null {
  const normalized = countryCodes.map(normalizeRegionCode).filter(Boolean);
  if (!normalized.length) return null;

  const displayNames = getDisplayNames(locale, "region");
  const labels = normalized.map((code) => displayNames?.of(code) || code);
  const formatter = getListFormatter(locale);
  return formatter ? formatter.format(labels) : labels.join(", ");
}

function applyTemplate(template: string, values: Record<string, string>): string {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, value),
    template,
  );
}

export function localizeLanguageFlagReason(
  locale: string,
  messages: ReasonLocalizationMessages,
  reason: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!reason) return null;
  if (!shouldLocalizeLocale(locale) || !CTA_MIX_REASON_RE.test(reason)) return reason;

  const primaryLanguage = localizeLanguageName(
    locale,
    context.primary_text_language_code,
    context.primary_text_language,
  );
  const secondaryLanguage = localizeLanguageName(
    locale,
    context.secondary_text_language_code,
    context.secondary_text_language,
  );
  const sample = (context.secondary_text_sample || "").trim();
  const markets = localizeServingCountries(locale, context.serving_countries || []);

  if (!primaryLanguage || !secondaryLanguage || !sample || !markets) {
    return reason;
  }

  return applyTemplate(messages.localizedCtaMixReasonTemplate, {
    primaryLanguage,
    secondaryLanguage,
    sample,
    markets,
  });
}

export function localizePlaintextLanguageSummary(
  locale: string,
  messages: ReasonLocalizationMessages,
  summary: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!summary) return null;
  if (!shouldLocalizeLocale(locale)) return summary;

  const primaryLanguage = localizeLanguageName(
    locale,
    context.primary_text_language_code,
    context.primary_text_language,
  );
  const secondaryLanguage = localizeLanguageName(
    locale,
    context.secondary_text_language_code,
    context.secondary_text_language,
  );
  const sample = (context.secondary_text_sample || "").trim();

  if (!primaryLanguage || !secondaryLanguage || !sample) {
    return summary;
  }

  return applyTemplate(messages.localizedPlaintextLanguageSummaryTemplate, {
    primaryLanguage,
    secondaryLanguage,
    sample,
  });
}

export function localizeGeoLinguisticReason(
  locale: string,
  messages: ReasonLocalizationMessages,
  reason: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!reason) return null;
  if (!shouldLocalizeLocale(locale) || !AI_MIX_REASON_RE.test(reason)) return reason;

  const primaryLanguage = localizeLanguageName(
    locale,
    context.primary_text_language_code,
    context.primary_text_language,
  );
  const secondaryLanguage = localizeLanguageName(
    locale,
    context.secondary_text_language_code,
    context.secondary_text_language,
  );
  const sample = (context.secondary_text_sample || "").trim();
  const markets = localizeServingCountries(locale, context.serving_countries || []);

  if (!primaryLanguage || !secondaryLanguage || !sample || !markets) {
    return reason;
  }

  return applyTemplate(messages.localizedAiWordMixReasonTemplate, {
    primaryLanguage,
    secondaryLanguage,
    sample,
    markets,
  });
}
