"use client";

import { useState, useEffect } from "react";
import { Loader2, AlertTriangle, CheckCircle, X } from "lucide-react";
import type { CreativeCountryBreakdown } from "@/types/api";
import { getCreativeCountries } from "@/lib/api";
import { cn } from "@/lib/utils";
import { checkLanguageCountryMatch } from "./utils";

interface CountrySectionProps {
  creativeId: string;
  detectedLanguage?: string | null;
  detectedLanguageCode?: string | null;
}

/**
 * Country targeting section with language match detection.
 */
export function CountrySection({ creativeId, detectedLanguage, detectedLanguageCode }: CountrySectionProps) {
  const [countryData, setCountryData] = useState<CreativeCountryBreakdown | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mismatchDismissed, setMismatchDismissed] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getCreativeCountries(creativeId, 7)
      .then((data) => setCountryData(data))
      .catch((err) => setError(err.message || "Failed to load country data"))
      .finally(() => setIsLoading(false));
  }, [creativeId]);

  if (isLoading) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Country Targeting
        </h4>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading...
        </div>
      </div>
    );
  }

  if (error || !countryData) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Country Targeting
        </h4>
        <p className="text-sm text-gray-400 italic">No country data available</p>
      </div>
    );
  }

  if (countryData.countries.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Country Targeting
        </h4>
        <p className="text-sm text-gray-400 italic">No performance data by country</p>
      </div>
    );
  }

  const formatSpendUsd = (micros: number) => {
    const dollars = micros / 1_000_000;
    if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
    return `$${dollars.toFixed(2)}`;
  };

  // Check language match
  const servingCountryCodes = countryData.countries.map(c => c.country_code);
  const langMatch = checkLanguageCountryMatch(detectedLanguageCode || null, servingCountryCodes);
  const showMismatchAlert = !langMatch.isMatch && langMatch.mismatchedCountries.length > 0 && !mismatchDismissed;

  const handleDismissMismatch = () => {
    setMismatchDismissed(true);
  };

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Country Targeting ({countryData.total_countries})
      </h4>

      {/* Language Match Status */}
      {detectedLanguage && (
        <div className={cn(
          "flex items-center justify-between text-xs mb-2 pb-2 border-b border-gray-200",
        )}>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-500">Creative Language:</span>
            <span className="font-medium text-gray-700">{detectedLanguage}</span>
            {detectedLanguageCode && (
              <span className="text-gray-400 font-mono">({detectedLanguageCode})</span>
            )}
          </div>
          {langMatch.isMatch ? (
            <div className="flex items-center gap-1 text-green-600">
              <CheckCircle className="h-3.5 w-3.5" />
              <span>Match</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-amber-600">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Mismatch</span>
            </div>
          )}
        </div>
      )}

      {/* Mismatch Alert */}
      {showMismatchAlert && (
        <div className="mb-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div className="text-amber-800">
                <span className="font-medium">Geo Mismatch:</span>{" "}
                Creative in {detectedLanguage} serving in {langMatch.mismatchedCountries.slice(0, 3).join(", ")}
                {langMatch.mismatchedCountries.length > 3 && ` +${langMatch.mismatchedCountries.length - 3} more`}
              </div>
            </div>
            <button
              onClick={handleDismissMismatch}
              className="text-amber-600 hover:text-amber-800 p-0.5"
              title="Dismiss this alert"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {countryData.countries.slice(0, 5).map((country) => (
          <div key={country.country_code} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-gray-400">{country.country_code}</span>
              <span className="text-gray-700">{country.country_name}</span>
              {/* Show mismatch indicator per country */}
              {detectedLanguageCode && langMatch.mismatchedCountries.includes(country.country_code) && (
                <span className="text-amber-500" title="Language mismatch">⚠</span>
              )}
              {detectedLanguageCode && langMatch.matchingCountries.includes(country.country_code) && (
                <span className="text-green-500" title="Language match">✓</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <span>{formatSpendUsd(country.spend_micros)}</span>
              <span className="text-gray-300">|</span>
              <span>{country.spend_percent.toFixed(1)}%</span>
            </div>
          </div>
        ))}
        {countryData.countries.length > 5 && (
          <div className="text-xs text-gray-400 pt-1">
            +{countryData.countries.length - 5} more countries
          </div>
        )}
      </div>
    </div>
  );
}
