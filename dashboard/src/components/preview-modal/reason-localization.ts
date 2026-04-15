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

const ZH_LANGUAGE_NAMES: Record<string, string> = {
  ar: "阿拉伯语",
  de: "德语",
  en: "英语",
  es: "西班牙语",
  fr: "法语",
  hi: "印地语",
  it: "意大利语",
  ja: "日语",
  ko: "韩语",
  pt: "葡萄牙语",
  ru: "俄语",
  zh: "中文",
};

const LANGUAGE_NAME_TO_CODE: Record<string, string> = {
  arabic: "ar",
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

function isChineseLocale(locale: string): boolean {
  return locale.toLowerCase().startsWith("zh");
}

function normalizeLanguageCode(code: string | null | undefined): string | null {
  const value = (code || "").trim().toLowerCase();
  return value || null;
}

function inferLanguageCode(name: string | null | undefined): string | null {
  const normalizedName = (name || "").trim().toLowerCase();
  return normalizedName ? LANGUAGE_NAME_TO_CODE[normalizedName] || null : null;
}

function localizeLanguageName(
  locale: string,
  code: string | null | undefined,
  fallbackName: string | null | undefined,
): string {
  const resolvedCode = normalizeLanguageCode(code) || inferLanguageCode(fallbackName);
  if (isChineseLocale(locale) && resolvedCode && ZH_LANGUAGE_NAMES[resolvedCode]) {
    return ZH_LANGUAGE_NAMES[resolvedCode];
  }
  return (fallbackName || resolvedCode || "").trim();
}

function normalizeRegionCode(code: string): string {
  const value = (code || "").trim().toUpperCase();
  if (value.length === 2) return value;
  if (value.length === 3) return ALPHA3_TO_ALPHA2[value] || value;
  return value;
}

function localizeServingCountries(locale: string, countryCodes: string[]): string | null {
  const normalized = countryCodes
    .map(normalizeRegionCode)
    .filter(Boolean);
  if (!normalized.length) return null;

  if (!isChineseLocale(locale)) {
    return normalized.join(", ");
  }

  const displayNames =
    typeof Intl.DisplayNames === 'function'
      ? new Intl.DisplayNames(["zh-Hans"], { type: "region" })
      : null;

  const labels = normalized.map((code) => displayNames?.of(code) || code);
  return labels.join("、");
}

export function localizeLanguageFlagReason(
  locale: string,
  reason: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!reason) return null;
  if (!isChineseLocale(locale)) return reason;
  if (!CTA_MIX_REASON_RE.test(reason)) return reason;

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
  const market = localizeServingCountries(locale, context.serving_countries || []);

  if (!primaryLanguage || !secondaryLanguage || !sample || !market) {
    return reason;
  }

  return `在${market}投放的${primaryLanguage}素材中混入了${secondaryLanguage} CTA“${sample}”`;
}

export function localizePlaintextLanguageSummary(
  locale: string,
  summary: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!summary) return null;
  if (!isChineseLocale(locale)) return summary;

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

  return `主要正文：${primaryLanguage} · CTA：${secondaryLanguage}（“${sample}”）`;
}

export function localizeGeoLinguisticReason(
  locale: string,
  reason: string | null | undefined,
  context: LanguageSignalContext,
): string | null {
  if (!reason) return null;
  if (!isChineseLocale(locale)) return reason;
  if (!AI_MIX_REASON_RE.test(reason)) return reason;

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
  const market = localizeServingCountries(locale, context.serving_countries || []);

  if (!primaryLanguage || !secondaryLanguage || !sample || !market) {
    return reason;
  }

  return `在${market}投放的以${primaryLanguage}为主的内容中混入了${secondaryLanguage}词语“${sample}”`;
}
