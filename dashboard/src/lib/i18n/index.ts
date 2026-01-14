export type { Language, Translations, TranslationKey } from './types';
export { en } from './translations/en';

import { en } from './translations/en';
import type { Language, Translations } from './types';

// Map of all available translations
export const translations: Record<Language, Translations> = {
  en,
  pl: en,
  zh: en,
  ru: en,
  uk: en,
  es: en,
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

// Get translations for a specific language
export function getTranslations(language: Language): Translations {
  return translations[language] || translations[defaultLanguage];
}
