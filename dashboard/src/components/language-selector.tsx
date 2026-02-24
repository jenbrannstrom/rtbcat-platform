"use client";

import { useState, useRef, useEffect } from "react";
import { Globe, ChevronDown, Check } from "lucide-react";
import { useLanguage, useTranslation } from "@/contexts/i18n-context";
import { availableLanguages, type Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface LanguageSelectorProps {
  collapsed?: boolean;
  compact?: boolean; // For header placement - shows flag emoji only
}

// Flag emoji mapping for language codes
const languageFlags: Record<string, string> = {
  en: "🇬🇧",
  es: "🇪🇸",
  de: "🇩🇪",
  fr: "🇫🇷",
  pt: "🇧🇷",
  ja: "🇯🇵",
  zh: "🇨🇳",
  ko: "🇰🇷",
  ru: "🇷🇺",
  ar: "🇸🇦",
};

export function LanguageSelector({ collapsed = false, compact = false }: LanguageSelectorProps) {
  const { language, setLanguage } = useLanguage();
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const currentLanguage = availableLanguages.find((l) => l.code === language);
  const currentFlag = languageFlags[language] || "🌐";

  const handleLanguageSelect = (langCode: Language) => {
    setLanguage(langCode);
    setIsOpen(false);
  };

  // Compact mode for header - small flag button
  if (compact) {
    return (
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            "flex items-center justify-center p-1.5 rounded-md",
            "text-gray-600 hover:bg-gray-100 transition-colors"
          )}
          title={currentLanguage?.nativeName || t.language.title}
        >
          <span className="text-base leading-none">{currentFlag}</span>
        </button>

        {isOpen && (
          <div className="absolute top-full right-0 mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
            {availableLanguages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleLanguageSelect(lang.code)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 text-sm text-left",
                  "hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg",
                  language === lang.code && "bg-primary-50 text-primary-700"
                )}
              >
                <div className="flex items-center gap-2">
                  <span>{languageFlags[lang.code] || "🌐"}</span>
                  <span>{lang.nativeName}</span>
                </div>
                {language === lang.code && <Check className="h-4 w-4 text-primary-600" />}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (collapsed) {
    return (
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            "flex items-center justify-center w-full p-2 rounded-md",
            "text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
          )}
          title={t.language.title}
        >
          <Globe className="h-5 w-5" />
        </button>

        {isOpen && (
          <div className="absolute bottom-full left-0 mb-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
            {availableLanguages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleLanguageSelect(lang.code)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 text-sm text-left",
                  "hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg",
                  language === lang.code && "bg-primary-50 text-primary-700"
                )}
              >
                <span>{lang.nativeName}</span>
                {language === lang.code && <Check className="h-4 w-4 text-primary-600" />}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center w-full px-3 py-2 rounded-md",
          "text-sm font-medium text-gray-600",
          "hover:bg-gray-50 hover:text-gray-900 transition-colors"
        )}
      >
        <Globe className="mr-3 h-5 w-5 text-gray-400" />
        <span className="flex-1 text-left">{currentLanguage?.nativeName || t.language.english}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-gray-400 transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          {availableLanguages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => handleLanguageSelect(lang.code)}
              className={cn(
                "w-full flex items-center justify-between px-3 py-2 text-sm text-left",
                "hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg",
                language === lang.code && "bg-primary-50 text-primary-700"
              )}
            >
              <span>{lang.nativeName}</span>
              {language === lang.code && <Check className="h-4 w-4 text-primary-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
