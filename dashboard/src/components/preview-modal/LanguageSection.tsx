"use client";

import { useState, useEffect } from "react";
import { Globe, Loader2, RefreshCw, Edit2, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import type { Creative, GeoMismatchResponse, CreativeCountryBreakdown } from "@/types/api";
import { analyzeCreativeLanguage, updateCreativeLanguage, getCreativeGeoMismatch, getCreativeCountries } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LanguageSectionProps {
  creative: Creative;
  onLanguageUpdate?: (language: string, languageCode: string) => void;
}

export function LanguageSection({ creative, onLanguageUpdate }: LanguageSectionProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [geoMismatch, setGeoMismatch] = useState<GeoMismatchResponse | null>(null);
  const [isLoadingMismatch, setIsLoadingMismatch] = useState(false);
  const [countryData, setCountryData] = useState<CreativeCountryBreakdown | null>(null);
  const [isLoadingCountries, setIsLoadingCountries] = useState(false);
  const [showAllCountries, setShowAllCountries] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editLanguage, setEditLanguage] = useState("");
  const [editLanguageCode, setEditLanguageCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (creative.detected_language_code) {
      setIsLoadingMismatch(true);
      getCreativeGeoMismatch(creative.id, 7)
        .then((data) => setGeoMismatch(data))
        .catch(() => setGeoMismatch(null))
        .finally(() => setIsLoadingMismatch(false));
    }
  }, [creative.id, creative.detected_language_code]);

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
      setError(err instanceof Error ? err.message : "Failed to analyze language");
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
      setError(err instanceof Error ? err.message : "Failed to update language");
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
          Edit Language
        </h4>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500">Language Name</label>
            <input
              type="text"
              value={editLanguage}
              onChange={(e) => setEditLanguage(e.target.value)}
              placeholder="e.g., German"
              className="w-full mt-1 px-2 py-1 text-sm border rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSaveEdit}
              disabled={isAnalyzing || !editLanguage.trim()}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isAnalyzing ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => setIsEditing(false)}
              disabled={isAnalyzing}
              className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  const countries = countryData?.countries || [];
  const visibleCountries = showAllCountries ? countries : countries.slice(0, 4);
  const hasMoreCountries = countries.length > 4;

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Globe className="h-3 w-3" />
        Language + Country
      </h4>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded mb-2">
          {error}
        </div>
      )}

      {geoMismatch?.has_mismatch && geoMismatch.alert && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded">
          <div className="flex items-start gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-amber-800">
              <div className="font-medium">Geo Mismatch</div>
              <div className="mt-0.5">{geoMismatch.alert.message}</div>
            </div>
          </div>
        </div>
      )}

      <div className="text-sm text-gray-700 flex flex-wrap items-center gap-1.5">
        <span className="text-gray-500">Language detected:</span>
        {creative.detected_language ? (
          <span className="font-medium">
            {creative.detected_language}
            {creative.detected_language_code ? (
              <span className="text-gray-400 font-mono ml-1">({creative.detected_language_code})</span>
            ) : null}
          </span>
        ) : (
          <span className="text-gray-400 italic">Not analyzed</span>
        )}
        <span className="text-gray-300">|</span>
        <span className="text-gray-500">Country targeted:</span>
        {isLoadingCountries ? (
          <span className="inline-flex items-center gap-1 text-gray-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading...
          </span>
        ) : countries.length > 0 ? (
          <span className="font-medium">
            {visibleCountries.map((c) => c.country_iso3 || c.country_code).join(", ")}
            {!showAllCountries && hasMoreCountries ? ` +${countries.length - 4}` : ""}
          </span>
        ) : (
          <span className="text-gray-400 italic">No country data</span>
        )}
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
              See less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              See more
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
          Rescan
        </button>
        <button
          onClick={startEditing}
          className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <Edit2 className="h-3 w-3" />
          Edit
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
            {Math.round(creative.language_confidence * 100)}% confidence
          </span>
        )}
      </div>

      {creative.language_source && (
        <div className="text-xs text-gray-400 mt-1">
          Source: {creative.language_source}
          {creative.language_analyzed_at && (
            <> · {new Date(creative.language_analyzed_at).toLocaleDateString()}</>
          )}
        </div>
      )}

      {isLoadingMismatch && (
        <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          Checking geo compatibility...
        </div>
      )}
    </div>
  );
}
