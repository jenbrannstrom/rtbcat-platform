"use client";

import { useState, useEffect } from "react";
import { Globe, Loader2, RefreshCw, Edit2, AlertTriangle } from "lucide-react";
import type { Creative, GeoMismatchResponse } from "@/types/api";
import { analyzeCreativeLanguage, updateCreativeLanguage, getCreativeGeoMismatch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LanguageSectionProps {
  creative: Creative;
  onLanguageUpdate?: (language: string, languageCode: string) => void;
}

/**
 * Language detection and editing section.
 */
export function LanguageSection({ creative, onLanguageUpdate }: LanguageSectionProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [geoMismatch, setGeoMismatch] = useState<GeoMismatchResponse | null>(null);
  const [isLoadingMismatch, setIsLoadingMismatch] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editLanguage, setEditLanguage] = useState("");
  const [editLanguageCode, setEditLanguageCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fetch geo-mismatch data when language is detected
  useEffect(() => {
    if (creative.detected_language_code) {
      setIsLoadingMismatch(true);
      getCreativeGeoMismatch(creative.id, 7)
        .then((data) => setGeoMismatch(data))
        .catch(() => setGeoMismatch(null))
        .finally(() => setIsLoadingMismatch(false));
    }
  }, [creative.id, creative.detected_language_code]);

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
    if (!editLanguage.trim() || !editLanguageCode.trim()) return;

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

  // Show edit form
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
          <div>
            <label className="text-xs text-gray-500">Language Code (ISO 639-1)</label>
            <input
              type="text"
              value={editLanguageCode}
              onChange={(e) => setEditLanguageCode(e.target.value)}
              placeholder="e.g., de"
              maxLength={3}
              className="w-full mt-1 px-2 py-1 text-sm border rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSaveEdit}
              disabled={isAnalyzing || !editLanguage.trim() || !editLanguageCode.trim()}
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

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Globe className="h-3 w-3" />
        Language Detection
      </h4>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded mb-2">
          {error}
        </div>
      )}

      {/* Geo Mismatch Alert */}
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

      {creative.detected_language ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">
                {creative.detected_language}
              </span>
              <span className="text-xs text-gray-400 font-mono">
                ({creative.detected_language_code})
              </span>
            </div>
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

          <div className="flex items-center gap-3 pt-1">
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
          </div>

          {creative.language_source && (
            <div className="text-xs text-gray-400">
              Source: {creative.language_source}
              {creative.language_analyzed_at && (
                <> · {new Date(creative.language_analyzed_at).toLocaleDateString()}</>
              )}
            </div>
          )}
        </div>
      ) : creative.language_analysis_error ? (
        <div className="space-y-2">
          <p className="text-xs text-red-600">{creative.language_analysis_error}</p>
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
            Retry Analysis
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-gray-400 italic">Not analyzed yet</p>
          <button
            onClick={handleRescan}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Globe className="h-3 w-3" />
                Detect Language
              </>
            )}
          </button>
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
