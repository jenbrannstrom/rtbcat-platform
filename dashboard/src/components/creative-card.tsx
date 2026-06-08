"use client";

import { useState } from "react";
import { ExternalLink, FileCode, Copy, Check, AlertTriangle } from "lucide-react";
import type { Creative, CreativePerformanceSummary } from "@/types/api";
import { useTranslation } from "@/contexts/i18n-context";
import { cn, getFormatColor, getFormatLabel, getStatusColor } from "@/lib/utils";
import { getGoogleAuthBuyersUrl, extractBuyerIdFromName } from "@/lib/url-utils";
import { isLanguageCountryMismatch } from "@/lib/language-country-map";
import { getCreative } from "@/lib/api";
import { CreativeThumb } from "@/components/creative-thumb";

interface CreativeCardProps {
  creative: Creative;
  onPreview?: (creative: Creative) => void;
  performance?: CreativePerformanceSummary;
  performanceLoading?: boolean;
  sortField?: "spend" | "impressions" | "clicks" | "ctr" | null;
}

// Format spend in micros to compact USD string
function formatSpend(microDollars: number | null | undefined): string {
  if (!microDollars) return "$0";
  const dollars = microDollars / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

// Format large numbers compactly
function formatNumber(n: number | null | undefined): string {
  if (!n) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

// Format CTR percentage
function formatCTR(ctr: number | null | undefined): string {
  if (ctr === null || ctr === undefined) return "-";
  return `${ctr.toFixed(2)}%`;
}

export function CreativeCard({
  creative,
  onPreview,
  performance,
  performanceLoading = false,
  sortField,
}: CreativeCardProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [htmlCopied, setHtmlCopied] = useState(false);
  const hasPreview = true; // Modal fetches full data on open; slim mode strips preview fields
  const hasData = performance?.has_data;
  const isPerformancePending = performanceLoading && !performance;

  // Get Google Console URL
  const buyerId = creative.buyer_id || extractBuyerIdFromName(creative.name);
  const googleUrl = buyerId ? getGoogleAuthBuyersUrl(buyerId, creative.id) : null;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(creative.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleCopyHtml = async (e: React.MouseEvent) => {
    e.stopPropagation();
    let htmlSnippet = creative.html?.snippet;
    if (!htmlSnippet) {
      try {
        const fullCreative = await getCreative(creative.id);
        htmlSnippet = fullCreative.html?.snippet || null;
      } catch {
        htmlSnippet = null;
      }
    }
    if (!htmlSnippet) return;
    await navigator.clipboard.writeText(htmlSnippet);
    setHtmlCopied(true);
    setTimeout(() => setHtmlCopied(false), 1500);
  };

  // Determine if we should show spend first (when sorted by spend)
  const showSpendFirst = sortField === "spend";
  const languageLabel = creative.detected_language || creative.detected_language_code;
  const countryLabel = creative.country;
  const legacyMismatch = isLanguageCountryMismatch(
    creative.detected_language_code,
    creative.country
  );
  const alertStatus = creative.market_alert?.status || (legacyMismatch ? "red" : null);
  const alertReason = creative.market_alert?.reason || null;
  const alertLabel = alertStatus === "red"
    ? t.previewModal.mismatch
    : alertStatus === "orange"
    ? t.previewModal.needsReview
    : null;
  const isStale = !!creative.data_source?.is_stale;
  const staleHours = creative.data_source?.stale_age_hours;

  return (
    <div className="card overflow-hidden hover:shadow-md transition-shadow">
      {/* Thumbnail */}
      <div
        className={cn("cursor-pointer", hasPreview && "hover:opacity-90")}
        onClick={() => hasPreview && onPreview?.(creative)}
      >
        <CreativeThumb creative={creative} size="md" showSourceBadge />
      </div>

      <div className="p-3">
        {/* Header: ID + Spend (order depends on sort) */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 min-w-0">
            {showSpendFirst ? (
              <>
                {/* Spend first when sorted by spend */}
                <div className="text-base font-medium text-gray-900">
                  {isPerformancePending
                    ? (t.common.loading || "Loading...")
                    : (hasData
                      ? `${formatSpend(performance?.total_spend_micros)} ${t.creatives.spentSuffix}`
                      : t.creatives.noData)}
                </div>
                <div className="text-sm text-gray-500 font-mono truncate" title={creative.id}>
                  #{creative.id}
                </div>
              </>
            ) : (
              <>
                {/* ID first (default) */}
                <div className="text-sm font-medium text-gray-900 font-mono truncate" title={creative.id}>
                  #{creative.id}
                </div>
                <div className={cn(
                  "text-base font-medium",
                  hasData ? "text-gray-900" : "text-gray-400"
                )}>
                  {isPerformancePending
                    ? (t.common.loading || "Loading...")
                    : (hasData
                      ? `${formatSpend(performance?.total_spend_micros)} ${t.creatives.spentSuffix}`
                      : t.creatives.noPerformanceData)}
                </div>
              </>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={handleCopy}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
              title={copied ? t.common.copied : t.creatives.copyId}
            >
              {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
            {creative.format === "HTML" && (
              <button
                onClick={handleCopyHtml}
                className="p-1 text-gray-400 hover:text-gray-600 rounded"
                title={htmlCopied ? t.common.copied : t.creatives.copyHtml}
              >
                {htmlCopied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <FileCode className="h-3.5 w-3.5" />}
              </button>
            )}
            {googleUrl && (
              <a
                href={googleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 text-gray-400 hover:text-primary-600 rounded"
                title={t.previewModal.viewInGoogleConsole}
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        </div>

        {/* Metrics row - only show if has data */}
        {hasData && (
          <div className="mt-2 text-xs text-gray-500">
            {formatNumber(performance?.total_impressions)} {t.previewModal.imps} · {formatCTR(performance?.ctr_percent)} {t.previewModal.ctr}
          </div>
        )}

        {(countryLabel || languageLabel || alertLabel) && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            {countryLabel && <span>{t.creatives.geoLabel}: {countryLabel}</span>}
            {languageLabel && <span>{t.creatives.langLabel}: {languageLabel}</span>}
            {alertLabel && (
              <span
                className={cn(
                  "inline-flex items-center gap-1",
                  alertStatus === "red" ? "text-red-600" : "text-amber-600"
                )}
                title={alertReason || undefined}
              >
                <AlertTriangle className="h-3 w-3" />
                {alertLabel}
              </span>
            )}
          </div>
        )}
        {isStale && (
          <div className="mt-2 text-xs text-amber-700">
            {t.creatives.staleCache} {staleHours ? `(${Math.round(staleHours)}${t.previewModal.hoursAbbrev} ${t.previewModal.oldLabel})` : ""}
          </div>
        )}

        {/* Badges: Format + Status + Alert */}
        <div className="mt-2 flex flex-wrap gap-1.5">
          <span className={cn("badge text-[10px] px-1.5 py-0.5", getFormatColor(creative.format))}>
            {getFormatLabel(creative.format)}
          </span>
          {creative.approval_status && (
            <span className={cn("badge text-[10px] px-1.5 py-0.5", getStatusColor(creative.approval_status))}>
              {creative.approval_status === "APPROVED" ? "✓" : ""} {creative.approval_status.replace("_", " ")}
            </span>
          )}
          {alertLabel && (
            <span
              title={alertReason || undefined}
              className={cn(
                "badge inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5",
                alertStatus === "red"
                  ? "bg-red-100 text-red-800"
                  : "bg-amber-100 text-amber-800"
              )}
            >
              <AlertTriangle className="h-3 w-3" />
              {alertLabel}
            </span>
          )}
        </div>
        {creative.disapproval_reasons && creative.disapproval_reasons.length > 0 && (
          <div className="mt-1.5 text-[10px] text-red-600 space-y-0.5">
            {creative.disapproval_reasons.map((r, i) => (
              <div key={i}>{r.reason?.replace(/_/g, " ")}{r.details ? <>{" — "}<a href={r.details} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline" onClick={(e) => e.stopPropagation()}>{t.previewModal.readMore}</a></> : ""}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
