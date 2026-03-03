export type { Language, Translations, TranslationKey, PartialTranslations } from './types';
export { en } from './translations/en';
export { es } from './translations/es';
export { nl } from './translations/nl';
export { ru } from './translations/ru';
export { zh } from './translations/zh';

import { en } from './translations/en';
import { es } from './translations/es';
import { nl } from './translations/nl';
import { ru } from './translations/ru';
import { zh } from './translations/zh';
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
  zh: withEnglishFallback(zh),
  ru: withEnglishFallback(ru),
  uk: en,
  da: en,
  fr: en,
  nl: withEnglishFallback(nl),
  he: en,
  ar: en,
};

// Default language
export const defaultLanguage: Language = 'en';

// Available languages for the selector
export const availableLanguages: { code: Language; name: string; nativeName: string }[] = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'pl', name: 'Polish', nativeName: 'Polski' },
  { code: 'zh', name: 'Chinese', nativeName: '中文' },
  { code: 'ru', name: 'Russian', nativeName: 'Русский' },
  { code: 'uk', name: 'Ukrainian', nativeName: 'Українська' },
  { code: 'es', name: 'Spanish', nativeName: 'Español' },
  { code: 'da', name: 'Danish', nativeName: 'Dansk' },
  { code: 'fr', name: 'French', nativeName: 'Français' },
  { code: 'nl', name: 'Dutch', nativeName: 'Nederlands' },
  { code: 'he', name: 'Hebrew', nativeName: 'עברית' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية' },
];

const rtlLanguages = new Set<Language>(["he", "ar"]);

export function isRtlLanguage(language: Language): boolean {
  return rtlLanguages.has(language);
}

// Get translations for a specific language
export function getTranslations(language: Language): Translations {
  return translations[language] || translations[defaultLanguage];
}
