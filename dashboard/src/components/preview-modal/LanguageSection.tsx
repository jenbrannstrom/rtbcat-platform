"use client";

import { useState, useEffect } from "react";
import { Globe, Loader2, RefreshCw, Edit2, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import type { Creative, CreativeCountryBreakdown } from "@/types/api";
import { analyzeCreativeLanguage, updateCreativeLanguage, getCreativeCountries } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";
import { buildLanguageCountryComparison } from "./utils";

interface LanguageSectionProps {
  creative: Creative;
  targetCountryCodes?: string[];
  onLanguageUpdate?: (language: string, languageCode: string) => void;
}

export function LanguageSection({
  creative,
  targetCountryCodes,
  onLanguageUpdate,
}: LanguageSectionProps) {
  const { t, language } = useTranslation();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [countryData, setCountryData] = useState<CreativeCountryBreakdown | null>(null);
  const [isLoadingCountries, setIsLoadingCountries] = useState(false);
  const [showAllCountries, setShowAllCountries] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editLanguage, setEditLanguage] = useState("");
  const [editLanguageCode, setEditLanguageCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoadingCountries(true);
    getCreativeCountries(creative.id, 7)
      .then((data) => setCountryData(data))
      .catch(() => setCountryData(null))
      .finally(() => setIsLoadingCountries(false));
  }, [creative.id]);

  const handleRescan = async () => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeCreativeLanguage(creative.id, true);
      if (result.success && result.detected_language && result.detected_language_code) {
        onLanguageUpdate?.(result.detected_language, result.detected_language_code);
      } else if (result.language_analysis_error) {
        setError(result.language_analysis_error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.previewModal.failedToAnalyzeLanguage);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editLanguage.trim()) return;

    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await updateCreativeLanguage(creative.id, {
        detected_language: editLanguage.trim(),
        detected_language_code: editLanguageCode.trim().toLowerCase(),
      });
      if (result.success) {
        onLanguageUpdate?.(result.detected_language!, result.detected_language_code!);
        setIsEditing(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.previewModal.failedToUpdateLanguage);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const startEditing = () => {
    setEditLanguage(creative.detected_language || "");
    setEditLanguageCode(creative.detected_language_code || "");
    setIsEditing(true);
  };

  if (isEditing) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          {t.previewModal.editLanguage}
        </h4>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500">{t.previewModal.languageName}</label>
            <input
              type="text"
              value={editLanguage}
              onChange={(e) => setEditLanguage(e.target.value)}
              placeholder={t.previewModal.languageNamePlaceholder}
              className="w-full mt-1 px-2 py-1 text-sm border rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSaveEdit}
              disabled={isAnalyzing || !editLanguage.trim()}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isAnalyzing ? t.previewModal.saving : t.common.save}
            </button>
            <button
              onClick={() => setIsEditing(false)}
              disabled={isAnalyzing}
              className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800"
            >
              {t.common.cancel}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const countries = countryData?.countries || [];
  const visibleCountries = showAllCountries ? countries : countries.slice(0, 4);
  const hasMoreCountries = countries.length > 4;
  const servingCountryCodes = countries
    .map((country) => country.country_code)
    .filter((countryCode): countryCode is string => Boolean(countryCode));
  const countryComparison = buildLanguageCountryComparison(
    creative.detected_language_code,
    targetCountryCodes,
    servingCountryCodes,
  );
  const mismatchCountryCodes = countryComparison.match.mismatchedCountries;
  const showMismatchAlert = mismatchCountryCodes.length > 0;
  const showConfiguredTargetCountries = countryComparison.basis === "targeting";

  const renderServingCountriesValue = () => {
    if (isLoadingCountries) {
      return (
        <span className="inline-flex items-center gap-1 text-gray-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          {t.common.loading}
        </span>
      );
    }

    if (countries.length === 0) {
      return <span className="text-gray-400 italic">{t.previewModal.noCountryData}</span>;
    }

    return (
      <span className="font-medium">
        {visibleCountries.map((country) => country.country_iso3 || country.country_code).join(", ")}
        {!showAllCountries && hasMoreCountries ? ` +${countries.length - 4}` : ""}
      </span>
    );
  };

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Globe className="h-3 w-3" />
        {t.previewModal.languageAndCountry}
      </h4>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded mb-2">
          {error}
        </div>
      )}

      {showMismatchAlert && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded">
          <div className="flex items-start gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-amber-800">
              <div className="font-medium">{t.previewModal.geoMismatch}</div>
              <div className="mt-0.5">
                {(showConfiguredTargetCountries
                  ? t.previewModal.geoMismatchTargetCountries
                  : t.previewModal.geoMismatchServingCountries)
                  .replace("{language}", creative.detected_language || creative.detected_language_code || "")
                  .replace("{countries}", mismatchCountryCodes.slice(0, 3).join(", "))}
                {mismatchCountryCodes.length > 3 && ` ${t.previewModal.moreItemsSuffix.replace("{count}", String(mismatchCountryCodes.length - 3))}`}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-1 text-sm text-gray-700">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-gray-500">{t.previewModal.languageDetected}</span>
          {creative.detected_language ? (
            <span className="font-medium">
              {creative.detected_language}
              {creative.detected_language_code ? (
                <span className="text-gray-400 font-mono ml-1">({creative.detected_language_code})</span>
              ) : null}
            </span>
          ) : (
            <span className="text-gray-400 italic">{t.previewModal.notAnalyzed}</span>
          )}
        </div>

        {showConfiguredTargetCountries && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-gray-500">{t.previewModal.countryTargeted}</span>
            <span className="font-medium">{countryComparison.countryCodes.join(", ")}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-gray-500">{t.previewModal.servingCountriesFromPerformanceCsvImports}</span>
          {renderServingCountriesValue()}
        </div>
      </div>

      {hasMoreCountries && (
        <button
          type="button"
          onClick={() => setShowAllCountries((v) => !v)}
          className="mt-1 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
        >
          {showAllCountries ? (
            <>
              <ChevronUp className="h-3 w-3" />
              {t.previewModal.seeLess}
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              {t.previewModal.seeMore}
            </>
          )}
        </button>
      )}

      {showAllCountries && countries.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {countries.map((country) => (
            <span
              key={country.country_code}
              className="inline-flex items-center gap-1 rounded-full bg-white border border-gray-200 px-2 py-0.5 text-xs text-gray-700"
            >
              <span>{country.country_name}</span>
              <span className="text-gray-400 font-mono">{country.country_iso3 || country.country_code}</span>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleRescan}
          disabled={isAnalyzing}
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
        >
          {isAnalyzing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          {t.previewModal.rescan}
        </button>
        <button
          onClick={startEditing}
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <Edit2 className="h-3 w-3" />
          {t.common.edit}
        </button>
        {creative.language_confidence !== null && (
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded",
            creative.language_confidence >= 0.8
              ? "bg-green-100 text-green-700"
              : creative.language_confidence >= 0.5
              ? "bg-yellow-100 text-yellow-700"
              : "bg-gray-100 text-gray-600"
          )}>
            {Math.round(creative.language_confidence * 100)}% {t.previewModal.confidence}
          </span>
        )}
      </div>

      {creative.language_source && (
        <div className="text-xs text-gray-400 mt-1">
          {t.previewModal.source}: {creative.language_source}
          {creative.language_analyzed_at && (
            <> · {new Date(creative.language_analyzed_at).toLocaleDateString(language)}</>
          )}
        </div>
      )}
    </div>
  );
}
