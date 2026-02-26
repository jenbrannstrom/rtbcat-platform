"use client";

import { useEffect, useState } from "react";
import { X, ExternalLink, Loader2, FileCode, RefreshCw, AlertTriangle } from "lucide-react";
import type { Creative, CreativePerformanceSummary } from "@/types/api";
import { cn, getStatusColor, getFormatLabel } from "@/lib/utils";
import { getCreative, getCreativeLive } from "@/lib/api";
import {
  parseDestinationUrls,
  getGoogleAuthBuyersUrl,
  extractBuyerIdFromName,
  type UrlLabelLocalizer,
} from "@/lib/url-utils";
import { useTranslation } from "@/contexts/i18n-context";

import { formatSpend, formatNumber, formatCTR, formatCostMetric, getDataNotes, extractTrackingParams } from "./utils";
import { CopyButton, MetricCard, DataNotesSection } from "./SharedComponents";
import { VideoPreviewPlayer, HtmlPreviewFrame, NativePreviewCard } from "./PreviewRenderers";
import { LanguageSection } from "./LanguageSection";

interface PreviewModalProps {
  creative: Creative;
  performance?: CreativePerformanceSummary;
  onClose: () => void;
}

/**
 * Main preview modal component for displaying creative details.
 */
export function PreviewModal({ creative: initialCreative, performance, onClose }: PreviewModalProps) {
  const { t } = useTranslation();
  const [creative, setCreative] = useState<Creative>(initialCreative);
  const [isLoadingFull, setIsLoadingFull] = useState(false);
  const [previewSource, setPreviewSource] = useState<"live" | "cache" | null>(null);
  const [previewMessage, setPreviewMessage] = useState<string | null>(null);
  const [showHtmlCode, setShowHtmlCode] = useState(false);
  const [isRefetchingLive, setIsRefetchingLive] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  // Fetch live creative payload first; fallback behavior is handled server-side.
  useEffect(() => {
    setIsLoadingFull(true);
    getCreativeLive(initialCreative.id, { allowCacheFallback: true, refreshCache: true, days: 7 })
      .then((resp) => {
        setCreative(resp.creative);
        setPreviewSource(resp.source);
        setPreviewMessage(resp.message);
      })
      .catch(async (err) => {
        console.error("Failed to fetch live creative:", err);
        // Last-resort fallback keeps modal usable.
        const fullCreative = await getCreative(initialCreative.id);
        setCreative(fullCreative);
        setPreviewSource("cache");
        setPreviewMessage(t.previewModal.liveFetchUnavailableShowingCached);
      })
      .finally(() => setIsLoadingFull(false));
  }, [initialCreative.id]);

  const refetchLive = async () => {
    setIsRefetchingLive(true);
    try {
      const resp = await getCreativeLive(initialCreative.id, {
        allowCacheFallback: false,
        refreshCache: true,
        days: 7,
      });
      setCreative(resp.creative);
      setPreviewSource(resp.source);
      setPreviewMessage(resp.message);
    } catch (err) {
      console.error("Live refetch failed:", err);
      setPreviewMessage(t.previewModal.liveRefetchFailedShowingCached);
      setPreviewSource("cache");
    } finally {
      setIsRefetchingLive(false);
    }
  };

  // Extract data from raw_data
  const rawData = (creative as unknown as { raw_data?: Record<string, unknown> }).raw_data;
  const rejectionReason = rawData?.rejectionReason as string | undefined;
  const declaredUrls = rawData?.declaredClickThroughUrls as string[] | undefined;
  const appName = rawData?.appName as string | undefined;
  const bundleId = rawData?.bundleId as string | undefined;

  // Google Console URL
  const buyerId = creative.buyer_id || extractBuyerIdFromName(creative.name);
  const googleUrl = buyerId ? getGoogleAuthBuyersUrl(buyerId, creative.id) : null;

  // Data notes
  const dataNotes = getDataNotes(creative, performance);

  // Parse URLs and tracking params
  const htmlSnippet = creative.html?.snippet || "";
  const allRawUrls = [creative.final_url, ...(declaredUrls || []), htmlSnippet].filter(Boolean).join(" ");
  const urlLabelLocalizer: UrlLabelLocalizer = {
    labels: {
      play_store: t.previewModal.urlLabelGooglePlayStore,
      app_store: t.previewModal.urlLabelAppleAppStore,
      appsflyer: t.previewModal.urlLabelAppsFlyer,
      adjust: t.previewModal.urlLabelAdjust,
      branch: t.previewModal.urlLabelBranch,
      kochava: t.previewModal.urlLabelKochava,
      doubleclick: t.previewModal.urlLabelDoubleClickTracker,
      tracking_pixel: t.previewModal.urlLabelTrackingPixel,
      landing_page: t.previewModal.urlLabelLandingPage,
    },
    tooltips: {
      play_store: t.previewModal.urlTooltipStoreInstallDestination,
      app_store: t.previewModal.urlTooltipStoreInstallDestination,
      appsflyer: t.previewModal.urlTooltipAttributionPlatform,
      adjust: t.previewModal.urlTooltipAttributionPlatform,
      branch: t.previewModal.urlTooltipAttributionPlatform,
      kochava: t.previewModal.urlTooltipAttributionPlatform,
      doubleclick: t.previewModal.urlTooltipDoubleClickTracker,
      tracking_pixel: t.previewModal.urlTooltipTrackingPixel,
      landing_page: t.previewModal.urlTooltipLandingPage,
    },
  };
  const parsedUrls = parseDestinationUrls(allRawUrls, urlLabelLocalizer);
  const trackingParams = extractTrackingParams(creative.final_url);
  const hasTrackingParams = Object.keys(trackingParams).length > 0;
  const effectiveSource = (creative.data_source?.source || previewSource || "cache") as "live" | "cache";
  const isStaleCache = effectiveSource === "cache" && !!creative.data_source?.is_stale;
  const staleHours = creative.data_source?.stale_age_hours;
  const staleThreshold = creative.data_source?.stale_threshold_hours;

  const formatApprovalStatus = (status?: string | null): string => {
    if (!status) return t.common.none;
    switch (status.toLowerCase()) {
      case "approved":
        return t.previewModal.approvalApproved;
      case "disapproved":
        return t.previewModal.approvalDisapproved;
      case "pending_review":
        return t.previewModal.approvalPendingReview;
      case "under_review":
        return t.previewModal.approvalUnderReview;
      case "not_reviewed":
        return t.previewModal.approvalNotReviewed;
      default:
        return status.replace(/_/g, " ");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900 font-mono truncate max-w-[400px]" title={creative.id}>#{creative.id}</h2>
              <CopyButton text={creative.id} className="flex-shrink-0" />
              <span
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded border",
                  effectiveSource === "live"
                    ? "bg-green-100 text-green-700 border-green-200"
                    : "bg-amber-100 text-amber-700 border-amber-200"
                )}
              >
                {effectiveSource === "live" ? t.previewModal.liveBadge : t.previewModal.cachedBadge}
              </span>
            </div>
            {googleUrl && (
              <a
                href={googleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 mt-1"
              >
                <ExternalLink className="h-3 w-3" />
                {t.previewModal.viewInGoogleConsole}
              </a>
            )}
          </div>
          <button onClick={onClose} className="ml-4 p-2 hover:bg-gray-100 rounded-full flex-shrink-0">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1">
          {/* Preview Area */}
          <div className="bg-gray-50">
            {creative.format === "VIDEO" && <VideoPreviewPlayer creative={creative} />}
            {creative.format === "HTML" &&
              (isLoadingFull ? (
                <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-500">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  {t.previewModal.loadingHtmlPreview}
                </div>
              ) : (
                <HtmlPreviewFrame
                  creative={creative}
                  destinationUrl={parsedUrls.find(u => u.isPrimary)?.url}
                />
              ))}
            {creative.format === "NATIVE" && (
              <div className="p-4">
                <NativePreviewCard creative={creative} />
              </div>
            )}
            {!["VIDEO", "HTML", "NATIVE"].includes(creative.format) && (
              <div className="flex items-center justify-center h-48 bg-gray-100 text-gray-400">
                {t.previewModal.previewNotAvailableForFormat.replace("{format}", creative.format)}
              </div>
            )}
          </div>
          {(previewSource || previewMessage || isStaleCache) && (
            <div className={cn(
              "px-4 py-2 text-xs border-b",
              effectiveSource === "live"
                ? "bg-green-50 text-green-700 border-green-100"
                : "bg-amber-50 text-amber-700 border-amber-100"
            )}>
              {effectiveSource === "live" ? t.previewModal.sourceLiveApi : t.previewModal.sourceCachedSnapshot}
              {isStaleCache && (
                <span className="ml-2 inline-flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  {t.previewModal.cacheIsStale}
                  {staleHours ? ` (${Math.round(staleHours)}${t.previewModal.hoursAbbrev} ${t.previewModal.oldLabel}` : ""}
                  {staleThreshold ? `, ${t.previewModal.thresholdLabel} ${staleThreshold}${t.previewModal.hoursAbbrev})` : staleHours ? ")" : ""}
                </span>
              )}
              {previewMessage ? ` ${previewMessage}` : ""}
              {effectiveSource === "cache" && (
                <button
                  type="button"
                  onClick={refetchLive}
                  disabled={isRefetchingLive}
                  className="ml-3 inline-flex items-center gap-1 rounded border border-amber-300 bg-white px-2 py-0.5 text-amber-700 hover:bg-amber-50 disabled:opacity-60"
                >
                  {isRefetchingLive ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {t.previewModal.refetching}
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-3 w-3" />
                      {t.previewModal.refetchLive}
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {creative.format === "HTML" && (
            <div className="p-4 border-b">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide inline-flex items-center gap-1.5">
                    <FileCode className="h-3 w-3" />
                    {t.previewModal.htmlSnippet}
                  </h4>
                  {creative.html?.snippet && <CopyButton text={creative.html.snippet} />}
                </div>
                {creative.html?.snippet ? (
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={() => setShowHtmlCode((v) => !v)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      {showHtmlCode ? t.previewModal.hideHtml : t.previewModal.showHtml}
                    </button>
                    {showHtmlCode && (
                      <pre className="mt-2 max-h-40 overflow-auto rounded border bg-white p-2 text-[11px] text-gray-700">
                        {creative.html.snippet}
                      </pre>
                    )}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-gray-400 italic">{t.previewModal.noHtmlSnippetAvailable}</p>
                )}
              </div>
            </div>
          )}

          {/* Performance Section */}
          <div className="p-4 border-b">
            {performance?.has_data ? (
              <>
                {/* 4-metric grid */}
                <div className="grid grid-cols-4 gap-2">
                  <MetricCard value={formatSpend(performance.total_spend_micros)} label={t.previewModal.spend} />
                  <MetricCard value={formatNumber(performance.total_impressions)} label={t.previewModal.imps} />
                  <MetricCard
                    value={performance.clicks_available !== false ? formatNumber(performance.total_clicks) : "N/A"}
                    label={t.previewModal.clicks}
                  />
                  <MetricCard
                    value={performance.clicks_available !== false ? formatCTR(performance.ctr_percent) : "N/A"}
                    label={t.previewModal.ctr}
                  />
                </div>
                {/* CPM/CPC secondary */}
                <div className="mt-2 text-xs text-gray-500 text-center">
                  {t.previewModal.cpm}: {formatCostMetric(performance.avg_cpm_micros)} · {t.previewModal.cpc}:{" "}
                  {performance.clicks_available !== false ? formatCostMetric(performance.avg_cpc_micros) : "N/A"}
                </div>
              </>
            ) : (
              <div className="text-center text-gray-400 py-2 text-xs">{t.previewModal.noPerformanceDataImportedYet}</div>
            )}
          </div>

          {/* Language + Country */}
          <div className="p-4 border-b">
            <LanguageSection
              creative={creative}
              onLanguageUpdate={(language, languageCode) => {
                setCreative((prev) => ({
                  ...prev,
                  detected_language: language,
                  detected_language_code: languageCode,
                }));
              }}
            />
          </div>

          {/* Data Notes */}
          {dataNotes.length > 0 && (
            <div className="p-4 border-b">
              <DataNotesSection notes={dataNotes} />
            </div>
          )}

          {/* Two-Column Details Section */}
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left Column: Creative Details + Technical IDs */}
            <div className="space-y-4">
              {/* Creative Details */}
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {t.previewModal.creativeDetails}
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t.previewModal.status}</span>
                    <span className={cn("badge", getStatusColor(creative.approval_status || ""))}>
                      {formatApprovalStatus(creative.approval_status)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t.previewModal.format}</span>
                    <span>
                      {getFormatLabel(creative.format)}
                      {creative.width && creative.height && ` (${creative.width}×${creative.height})`}
                    </span>
                  </div>
                  {rejectionReason && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t.previewModal.rejection}</span>
                      <span className="text-red-600">{rejectionReason}</span>
                    </div>
                  )}
                  {creative.disapproval_reasons && creative.disapproval_reasons.length > 0 && (
                    <div>
                      <span className="text-gray-500 text-xs">{t.previewModal.disapprovalReasons}</span>
                      <div className="mt-1 space-y-1">
                        {creative.disapproval_reasons.map((r: { reason: string; details?: string }, i: number) => (
                          <div key={i} className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                            {r.reason?.replace(/_/g, " ")}{r.details ? <>{" — "}<a href={r.details} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{t.previewModal.readMore}</a></> : ""}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {creative.advertiser_name && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t.previewModal.advertiser}</span>
                      <span>{creative.advertiser_name}</span>
                    </div>
                  )}
                  {appName && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">{t.previewModal.appName}</span>
                      <span>{appName}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Technical IDs */}
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {t.previewModal.accountInfo}
                </h4>
                <div className="space-y-2 text-sm">
                  {creative.buyer_id && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500">{t.previewModal.buyerId}</span>
                      <div className="flex items-center gap-1">
                        <span className="font-mono text-xs">{creative.buyer_id}</span>
                        <CopyButton text={creative.buyer_id} />
                      </div>
                    </div>
                  )}
                  {creative.seat_name && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500">{t.previewModal.buyerName}</span>
                      <span className="text-xs text-gray-700">{creative.seat_name}</span>
                    </div>
                  )}
                  {bundleId && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-500">{t.previewModal.bundleId}</span>
                      <div className="flex items-center gap-1">
                        <span className="font-mono text-xs">{bundleId}</span>
                        <CopyButton text={bundleId} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right Column: Destination URLs + Tracking Params */}
            <div className="space-y-4">
              {/* Destination URLs */}
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {t.previewModal.destination}
                </h4>
                {parsedUrls.length > 0 ? (
                  <div className="space-y-3">
                    {parsedUrls.slice(0, 4).map((url, i) => (
                      <div key={i} className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-gray-500">{url.label}</span>
                          {url.isPrimary && (
                            <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">{t.previewModal.primary}</span>
                          )}
                        </div>
                        <div className="flex items-start gap-2 min-w-0">
                          <a
                            href={url.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary-600 hover:text-primary-700 text-[11px] font-mono truncate leading-relaxed flex-1 min-w-0"
                            title={url.url}
                          >
                            {url.url}
                          </a>
                          <CopyButton text={url.url} className="flex-shrink-0 mt-0.5" />
                        </div>
                      </div>
                    ))}
                    {parsedUrls.length > 4 && (
                      <div className="text-xs text-gray-400">
                        {t.previewModal.moreUrls.replace("{count}", String(parsedUrls.length - 4))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">{t.previewModal.noUrlsFound}</p>
                )}
              </div>

              {/* Tracking Parameters */}
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {t.previewModal.trackingParameters}
                </h4>
                {hasTrackingParams ? (
                  <div className="space-y-1 text-sm">
                    {Object.entries(trackingParams).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-gray-500 font-mono flex-shrink-0">{key}</span>
                        <div className="flex items-center gap-1 min-w-0">
                          <span className="text-gray-700 truncate" title={value}>
                            {value}
                          </span>
                          <CopyButton text={value} className="flex-shrink-0" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">{t.previewModal.noTrackingParams}</p>
                )}
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
