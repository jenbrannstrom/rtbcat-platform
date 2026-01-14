"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  type Language,
  type Translations,
  getTranslations,
  defaultLanguage,
  availableLanguages,
} from "@/lib/i18n";

// ==================== Constants ====================

const LANGUAGE_STORAGE_KEY = "rtbcat-language";
const LANGUAGE_COOKIE_KEY = "rtbcat_language";

// ==================== Types ====================

interface I18nContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

// ==================== Context ====================

const I18nContext = createContext<I18nContextValue | null>(null);

// ==================== Provider ====================

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(defaultLanguage);
  const [isHydrated, setIsHydrated] = useState(false);

  // Load language from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    const cookieMatch = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${LANGUAGE_COOKIE_KEY}=`));
    const cookieValue = cookieMatch ? cookieMatch.split("=")[1] : null;
    const preferred = stored || cookieValue;
    const allowed = availableLanguages.map((lang) => lang.code);

    if (preferred && allowed.includes(preferred as Language)) {
      setLanguageState(preferred as Language);
      setIsHydrated(true);
      return;
    }

    fetch("/api/auth/me", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const userLang = data?.default_language;
        if (userLang && allowed.includes(userLang as Language)) {
          setLanguageState(userLang as Language);
          localStorage.setItem(LANGUAGE_STORAGE_KEY, userLang);
          document.cookie = `${LANGUAGE_COOKIE_KEY}=${userLang}; path=/; max-age=31536000`;
        }
      })
      .catch(() => {})
      .finally(() => setIsHydrated(true));
  }, []);

  // Set language and persist to localStorage
  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    document.cookie = `${LANGUAGE_COOKIE_KEY}=${lang}; path=/; max-age=31536000`;
  }, []);

  // Get translations for current language
  const t = getTranslations(language);

  const value: I18nContextValue = {
    language,
    setLanguage,
    t,
  };

  // Prevent hydration mismatch by not rendering children until hydrated
  if (!isHydrated) {
    return (
      <I18nContext.Provider value={value}>
        <div className="flex items-center justify-center h-screen bg-gray-50">
          <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
        </div>
      </I18nContext.Provider>
    );
  }

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

// ==================== Hooks ====================

/**
 * Hook to access translations and current language
 * @returns Object with translations (t), current language, and setLanguage function
 */
export function useTranslation() {
  const context = useContext(I18nContext);

  if (!context) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }

  return context;
}

/**
 * Hook to access just the current language and setter
 * @returns Object with current language and setLanguage function
 */
export function useLanguage() {
  const context = useContext(I18nContext);

  if (!context) {
    throw new Error("useLanguage must be used within an I18nProvider");
  }

  return {
    language: context.language,
    setLanguage: context.setLanguage,
  };
}
