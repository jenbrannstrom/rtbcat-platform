export type { Language, Translations, TranslationKey, PartialTranslations } from './types';
export { en } from './translations/en';
export { es } from './translations/es';

import { en } from './translations/en';
import { es } from './translations/es';
import type { Language, PartialTranslations, Translations } from './types';

type PlainObject = Record<string, unknown>;

function isPlainObject(value: unknown): value is PlainObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function deepMergeTranslations<T extends PlainObject>(
  base: T,
  override?: PartialTranslations | PlainObject
): T {
  if (!override || !isPlainObject(override)) {
    return { ...base } as T;
  }

  const result: PlainObject = { ...base };

  for (const [key, value] of Object.entries(override)) {
    if (value === undefined) continue;
    const baseValue = result[key];
    if (isPlainObject(baseValue) && isPlainObject(value)) {
      result[key] = deepMergeTranslations(baseValue, value);
    } else {
      result[key] = value;
    }
  }

  return result as T;
}

function withEnglishFallback(override?: PartialTranslations): Translations {
  if (!override) return en;
  return deepMergeTranslations(en as unknown as PlainObject, override as unknown as PlainObject) as unknown as Translations;
}

// Map of all available translations
export const translations: Record<Language, Translations> = {
  en,
  es: withEnglishFallback(es),
  pl: en,
  zh: en,
  ru: en,
  uk: en,
  da: en,
  fr: en,
  nl: en,
  he: en,
  ar: en,
};

// Default language
export const defaultLanguage: Language = 'en';

// Available languages for the selector
export const availableLanguages: { code: Language; name: string; nativeName: string }[] = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'pl', name: 'Polish', nativeName: 'Polish' },
  { code: 'zh', name: 'Chinese', nativeName: 'Chinese' },
  { code: 'ru', name: 'Russian', nativeName: 'Russian' },
  { code: 'uk', name: 'Ukrainian', nativeName: 'Ukrainian' },
  { code: 'es', name: 'Spanish', nativeName: 'Spanish' },
  { code: 'da', name: 'Danish', nativeName: 'Danish' },
  { code: 'fr', name: 'French', nativeName: 'French' },
  { code: 'nl', name: 'Dutch', nativeName: 'Dutch' },
  { code: 'he', name: 'Hebrew', nativeName: 'Hebrew' },
  { code: 'ar', name: 'Arabic', nativeName: 'Arabic' },
];

const rtlLanguages = new Set<Language>(["he", "ar"]);

export function isRtlLanguage(language: Language): boolean {
  return rtlLanguages.has(language);
}

// Get translations for a specific language
export function getTranslations(language: Language): Translations {
  return translations[language] || translations[defaultLanguage];
}
