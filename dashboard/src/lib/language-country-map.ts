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
