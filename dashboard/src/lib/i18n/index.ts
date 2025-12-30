export type { Language, Translations, TranslationKey } from './types';
export { en } from './translations/en';

import { en } from './translations/en';
import type { Language, Translations } from './types';

// Map of all available translations
export const translations: Record<Language, Translations> = {
  en,
};

// Default language
export const defaultLanguage: Language = 'en';

// Available languages for the selector
export const availableLanguages: { code: Language; name: string; nativeName: string }[] = [
  { code: 'en', name: 'English', nativeName: 'English' },
];

// Get translations for a specific language
export function getTranslations(language: Language): Translations {
  return translations[language] || translations[defaultLanguage];
}
