const LANGUAGE_TO_COUNTRIES: Record<string, string[]> = {
  en: ["US", "GB", "CA", "AU", "NZ", "IE", "ZA", "SG", "IN", "PH", "NG", "KE", "GH"],
  de: ["DE", "AT", "CH", "LI", "LU", "BE"],
  fr: ["FR", "BE", "CH", "CA", "LU", "MC", "SN", "CI", "ML", "BF", "NE", "TG", "BJ", "MG"],
  es: ["ES", "MX", "AR", "CO", "PE", "VE", "CL", "EC", "GT", "CU", "DO", "BO", "HN", "PY", "SV", "NI", "CR", "PA", "UY", "PR"],
  it: ["IT", "CH", "SM", "VA"],
  pt: ["PT", "BR", "AO", "MZ", "CV", "GW", "ST", "TL", "MO"],
  nl: ["NL", "BE", "SR", "CW", "AW", "SX"],
  pl: ["PL"],
  ru: ["RU", "BY", "KZ", "KG"],
  ja: ["JP"],
  ko: ["KR", "KP"],
  zh: ["CN", "TW", "HK", "MO", "SG"],
  ar: ["SA", "EG", "AE", "IQ", "JO", "KW", "LB", "LY", "MA", "OM", "QA", "SD", "SY", "TN", "YE", "DZ", "BH"],
  hi: ["IN"],
  tr: ["TR", "CY"],
  th: ["TH"],
  vi: ["VN"],
  id: ["ID"],
  ms: ["MY", "SG", "BN"],
  sv: ["SE", "FI"],
  da: ["DK", "GL", "FO"],
  no: ["NO"],
  fi: ["FI"],
  cs: ["CZ"],
  el: ["GR", "CY"],
  he: ["IL"],
  hu: ["HU"],
  ro: ["RO", "MD"],
  uk: ["UA"],
  bg: ["BG"],
  hr: ["HR", "BA"],
  sr: ["RS", "BA", "ME"],
  sk: ["SK"],
  sl: ["SI"],
  et: ["EE"],
  lv: ["LV"],
  lt: ["LT"],
  bn: ["BD", "IN"],
  ta: ["IN", "LK", "SG", "MY"],
  te: ["IN"],
  mr: ["IN"],
  ur: ["PK", "IN"],
  sw: ["KE", "TZ", "UG"],
};

const LANGUAGE_NAMES: Record<string, string> = {
  ar: "Arabic",
  bg: "Bulgarian",
  bn: "Bengali",
  cs: "Czech",
  da: "Danish",
  de: "German",
  el: "Greek",
  en: "English",
  es: "Spanish",
  et: "Estonian",
  fi: "Finnish",
  fr: "French",
  he: "Hebrew",
  hi: "Hindi",
  hr: "Croatian",
  hu: "Hungarian",
  id: "Indonesian",
  it: "Italian",
  ja: "Japanese",
  ko: "Korean",
  lt: "Lithuanian",
  lv: "Latvian",
  mr: "Marathi",
  ms: "Malay",
  my: "Myanmar",
  nl: "Dutch",
  no: "Norwegian",
  pl: "Polish",
  pt: "Portuguese",
  ro: "Romanian",
  ru: "Russian",
  sk: "Slovak",
  sl: "Slovenian",
  sr: "Serbian",
  sv: "Swedish",
  sw: "Swahili",
  ta: "Tamil",
  te: "Telugu",
  th: "Thai",
  tr: "Turkish",
  uk: "Ukrainian",
  ur: "Urdu",
  vi: "Vietnamese",
  zh: "Chinese",
};

const COUNTRY_NAMES: Record<string, string> = {
  AE: "United Arab Emirates",
  AR: "Argentina",
  AT: "Austria",
  AU: "Australia",
  BE: "Belgium",
  BR: "Brazil",
  CA: "Canada",
  CH: "Switzerland",
  CN: "China",
  CO: "Colombia",
  DE: "Germany",
  DK: "Denmark",
  ES: "Spain",
  FI: "Finland",
  FR: "France",
  GB: "United Kingdom",
  HK: "Hong Kong",
  ID: "Indonesia",
  IE: "Ireland",
  IL: "Israel",
  IN: "India",
  IT: "Italy",
  JP: "Japan",
  KR: "South Korea",
  MX: "Mexico",
  MY: "Malaysia",
  NL: "Netherlands",
  NZ: "New Zealand",
  PH: "Philippines",
  PL: "Poland",
  PT: "Portugal",
  RU: "Russia",
  SA: "Saudi Arabia",
  SE: "Sweden",
  SG: "Singapore",
  TH: "Thailand",
  TR: "Turkey",
  TW: "Taiwan",
  UA: "Ukraine",
  US: "United States",
  VN: "Vietnam",
  ZA: "South Africa",
};

export function getLanguageName(
  languageCode: string | null | undefined,
  fallback?: string | null
): string | null {
  if (!languageCode && fallback) return fallback;
  if (!languageCode) return null;
  const normalized = languageCode.toLowerCase();
  return LANGUAGE_NAMES[normalized] || fallback || normalized.toUpperCase();
}

export function getCountryName(countryCode: string | null | undefined): string | null {
  if (!countryCode) return null;
  const normalized = countryCode.toUpperCase();
  return COUNTRY_NAMES[normalized] || normalized;
}

export function countryFlag(countryCode: string | null | undefined): string {
  if (!countryCode || !/^[a-z]{2}$/i.test(countryCode)) return "";
  return countryCode
    .toUpperCase()
    .split("")
    .map((char) => String.fromCodePoint(127397 + char.charCodeAt(0)))
    .join("");
}

export function isLanguageCountryMismatch(
  languageCode: string | null | undefined,
  countryCode: string | null | undefined
): boolean {
  if (!languageCode || !countryCode) return false;
  const normalizedLang = languageCode.toLowerCase();
  const normalizedCountry = countryCode.toUpperCase();
  const expected = LANGUAGE_TO_COUNTRIES[normalizedLang];
  if (!expected || expected.length === 0) return false;
  return !expected.includes(normalizedCountry);
}
