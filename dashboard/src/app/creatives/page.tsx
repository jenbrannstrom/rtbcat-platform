"use client";

import { useState, Suspense, useRef, useMemo } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, X, TrendingUp, Loader2, Play, Square, AlertTriangle } from "lucide-react";
import { getCreatives, getSizes, getBatchPerformance, getThumbnailStatus, generateThumbnailsBatch } from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import type { Creative, PerformancePeriod, CreativePerformanceSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";

// Period options for date-range picker
const PERIOD_OPTIONS = [
  { value: 7, label: "7d", period: "7d" as PerformancePeriod },
  { value: 14, label: "14d", period: "14d" as PerformancePeriod },
  { value: 30, label: "30d", period: "30d" as PerformancePeriod },
];

// Performance tiers
type PerformanceTier = "high" | "medium" | "low" | "no_data";

type TierOptionValue = PerformanceTier | "all";
const TIER_OPTION_VALUES: { value: TierOptionValue; color: string }[] = [
  { value: "all", color: "bg-gray-100 text-gray-600" },
  { value: "high", color: "bg-green-100 text-green-700" },
  { value: "medium", color: "bg-yellow-100 text-yellow-700" },
  { value: "low", color: "bg-red-100 text-red-700" },
  { value: "no_data", color: "bg-gray-100 text-gray-500" },
];

// Calculate performance tiers based on spend percentiles
function calculateTiers(
  performanceData: Record<string, CreativePerformanceSummary> | undefined
): Map<string, PerformanceTier> {
  const tiers = new Map<string, PerformanceTier>();
  if (!performanceData) return tiers;

  // Get all creatives with spend data
  const withData = Object.entries(performanceData)
    .filter(([, perf]) => perf.has_data && perf.total_spend_micros > 0)
    .map(([id, perf]) => ({ id, spend: perf.total_spend_micros }))
    .sort((a, b) => b.spend - a.spend);

  const total = withData.length;
  if (total === 0) return tiers;

  // Calculate percentile thresholds
  const highCutoff = Math.ceil(total * 0.2); // Top 20%
  const mediumCutoff = Math.ceil(total * 0.8); // Top 80% (middle 60%)

  withData.forEach((item, index) => {
    if (index < highCutoff) {
      tiers.set(item.id, "high");
    } else if (index < mediumCutoff) {
      tiers.set(item.id, "medium");
    } else {
      tiers.set(item.id, "low");
    }
  });

  // Mark creatives with no data
  Object.entries(performanceData).forEach(([id, perf]) => {
    if (!perf.has_data || perf.total_spend_micros === 0) {
      tiers.set(id, "no_data");
    }
  });

  return tiers;
}

// Virtual scrolling constants
const CARD_HEIGHT = 320;
const GAP = 16;

// Format filters - map API formats to display labels
// Note: HTML and IMAGE both map to "Display" in the UI
// Labels will be translated in the component
const FORMAT_FILTER_VALUES: { value: string; formats: string[] }[] = [
  { value: "VIDEO", formats: ["VIDEO"] },
  { value: "DISPLAY_IMAGE", formats: ["IMAGE"] },
  { value: "DISPLAY_HTML", formats: ["HTML"] },
  { value: "NATIVE", formats: ["NATIVE"] },
];
const COLUMNS = 4; // Fixed 4 columns for simplicity

// Thumbnail Generation Banner Component
function ThumbnailGenerationBanner({ buyerId }: { buyerId?: string | null }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ["thumbnailStatus", buyerId],
    queryFn: () => getThumbnailStatus({ buyer_id: buyerId ?? undefined }),
    refetchInterval: (query) => {
      // Poll every 2s while generating
      return query.state.data?.pending && query.state.data.pending > 0 ? 2000 : false;
    },
  });

  const [autoGenerate, setAutoGenerate] = useState(false);

  const generateMutation = useMutation({
    mutationFn: (params: { force?: boolean; limit?: number }) =>
      generateThumbnailsBatch(params),
    onSuccess: (data) => {
      // Refetch status after generation completes
      queryClient.invalidateQueries({ queryKey: ["thumbnailStatus"] });
      queryClient.invalidateQueries({ queryKey: ["creatives"] });

      // Auto-continue if enabled and there are more pending
      if (autoGenerate && data.total_processed > 0) {
        // Small delay then trigger next batch
        setTimeout(() => {
          generateMutation.mutate({ limit: 10 });
        }, 500);
      }
    },
    onError: () => {
      // Stop auto-generate on error
      setAutoGenerate(false);
    },
  });

  // Don't render if no status or no video creatives
  if (!status || status.total_videos === 0) {
    return null;
  }

  const pending = status.pending;
  const hasPending = pending > 0;
  const hasFailed = status.failed > 0;
  const isGenerating = generateMutation.isPending;

  // Don't show if all thumbnails are generated and no failures (and not generating)
  if (!hasPending && !hasFailed && !isGenerating) {
    return null;
  }

  return (
    <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-gray-900 flex items-center gap-2">
            {t.creatives.videoThumbnails}
            <span className="text-sm font-normal text-gray-500">
              {status.with_thumbnails} {t.creatives.ofGenerated.replace('{total}', String(status.total_videos))}
            </span>
          </h3>

          {!isGenerating && (
            <p className="text-sm text-gray-500 mt-1">
              {hasPending && (
                <span className="text-yellow-600">{pending} {t.creatives.pending}</span>
              )}
              {hasPending && hasFailed && ' · '}
              {hasFailed && (
                <span className="text-red-600">{status.failed} {t.creatives.failed}</span>
              )}
            </p>
          )}
        </div>

        <div className="flex gap-2">
          {hasPending && (
            <button
              onClick={() => {
                if (isGenerating || autoGenerate) {
                  // Stop
                  setAutoGenerate(false);
                } else {
                  // Start auto-generate
                  setAutoGenerate(true);
                  generateMutation.mutate({ limit: 10 });
                }
              }}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition",
                isGenerating || autoGenerate
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-primary-600 hover:bg-primary-700 text-white"
              )}
            >
              {isGenerating || autoGenerate ? (
                <>
                  <Square className="h-4 w-4" />
                  {t.creatives.stop}
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  {t.creatives.generateAll} ({pending})
                </>
              )}
            </button>
          )}
          {hasFailed && !isGenerating && (
            <button
              onClick={() => generateMutation.mutate({ force: true, limit: 10 })}
              className="flex items-center gap-2 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg text-sm transition"
              title={t.creatives.retryFailed}
            >
              {t.creatives.retryFailed} ({status.failed})
            </button>
          )}
          {isGenerating && (
            <span className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t.creatives.processingBatch}
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {status.total_videos > 0 && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-primary-600 h-2 transition-all duration-300"
              style={{ width: `${status.coverage_percent}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {status.coverage_percent.toFixed(0)}% {t.creatives.coverage}
          </p>
        </div>
      )}

      {/* ffmpeg warning - just informational, doesn't block the Generate button */}
      {!status.ffmpeg_available && (
        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-sm flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <span className="text-yellow-800">{t.creatives.ffmpegNotDetected} </span>
            <span className="text-yellow-700">{t.creatives.ifGenerationFails} </span>
            <code className="bg-yellow-100 px-1 rounded text-yellow-900">sudo apt install ffmpeg</code>
          </div>
        </div>
      )}
    </div>
  );
}

function VirtualizedGrid({
  creatives,
  onPreview,
  performanceData,
  sortField,
}: {
  creatives: Creative[];
  onPreview: (creative: Creative) => void;
  performanceData?: Record<string, CreativePerformanceSummary>;
  sortField?: "spend" | "impressions" | "clicks" | "ctr" | null;
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  // Calculate rows (4 cards per row)
  const rowCount = Math.ceil(creatives.length / COLUMNS);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => CARD_HEIGHT + GAP,
    overscan: 2,
  });

  return (
    <div
      ref={parentRef}
      className="h-[calc(100vh-180px)] min-h-[400px] overflow-auto"
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const startIndex = virtualRow.index * COLUMNS;
          const rowCreatives = creatives.slice(startIndex, startIndex + COLUMNS);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 px-1"
            >
              {rowCreatives.map((creative) => (
                <CreativeCard
                  key={creative.id}
                  creative={creative}
                  onPreview={onPreview}
                  performance={performanceData?.[creative.id]}
                  sortField={sortField}
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CreativesContent() {
  const { t } = useTranslation();
  const { selectedBuyerId } = useAccount();

  // Get buyer_id from context (persistent across pages)
  const selectedSeatId = selectedBuyerId;

  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(new Set());
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
  const [days, setDays] = useState(7);
  const [sortBySpend, setSortBySpend] = useState(true);
  const [tierFilter, setTierFilter] = useState<PerformanceTier | "all">("all");
  const [approvalFilter, setApprovalFilter] = useState<"all" | "approved" | "not_approved">("all");

  const {
    data: creatives,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["creatives", selectedSeatId],
    queryFn: () => getCreatives({ limit: 300, buyer_id: selectedSeatId ?? undefined, slim: true }),
  });

  const { data: availableSizes } = useQuery({
    queryKey: ["sizes"],
    queryFn: getSizes,
  });

  const approvedCount = useMemo(
    () => creatives?.filter((c) => c.approval_status === "APPROVED").length ?? 0,
    [creatives]
  );
  const notApprovedCount = useMemo(
    () => creatives?.filter((c) => c.approval_status !== "APPROVED").length ?? 0,
    [creatives]
  );

  // Always fetch performance data for the selected period
  const period = PERIOD_OPTIONS.find((o) => o.value === days)?.period ?? "7d";
  const {
    data: performanceResponse,
    isLoading: isLoadingPerformance,
  } = useQuery({
    queryKey: ["performance", creatives?.map((c) => c.id), period],
    queryFn: () => {
      if (!creatives || creatives.length === 0) {
        return null;
      }
      return getBatchPerformance(
        creatives.map((c) => c.id),
        period
      );
    },
    enabled: !!creatives && creatives.length > 0,
    staleTime: 60000, // Cache for 1 minute
  });

  const performanceData = performanceResponse?.performance;

  const { data: previewPerformanceResponse } = useQuery({
    queryKey: ["preview-performance", previewCreative?.id, period],
    queryFn: () => {
      if (!previewCreative) return null;
      return getBatchPerformance([previewCreative.id], period);
    },
    enabled: !!previewCreative && !performanceData?.[previewCreative.id],
    staleTime: 60000,
  });

  // Calculate tier assignments based on spend percentiles
  const tierAssignments = useMemo(() => {
    return calculateTiers(performanceData);
  }, [performanceData]);

  const toggleFormat = (format: string) => {
    const newFormats = new Set(selectedFormats);
    if (newFormats.has(format)) {
      newFormats.delete(format);
    } else {
      newFormats.add(format);
    }
    setSelectedFormats(newFormats);
  };

  const toggleSize = (size: string) => {
    const newSizes = new Set(selectedSizes);
    if (newSizes.has(size)) {
      newSizes.delete(size);
    } else {
      newSizes.add(size);
    }
    setSelectedSizes(newSizes);
  };

  const clearFilters = () => {
    setSelectedFormats(new Set());
    setSelectedSizes(new Set());
    setSearch("");
    setTierFilter("all");
    setApprovalFilter("all");
  };

  // Filter and sort creatives - MUST be before early returns (hooks order)
  const filteredCreatives = useMemo(() => {
    if (!creatives) return undefined;

    let result = creatives.filter((c) => {
      // Format filter - check if creative's format matches any selected filter group
      if (selectedFormats.size > 0) {
        const matchesFormat = Array.from(selectedFormats).some((filterValue) => {
          const filter = FORMAT_FILTER_VALUES.find((f) => f.value === filterValue);
          return filter?.formats.includes(c.format);
        });
        if (!matchesFormat) return false;
      }

      // Size filter
      if (selectedSizes.size > 0) {
        const creativeSize = c.width && c.height ? `${c.width}x${c.height}` : null;
        if (!creativeSize || !selectedSizes.has(creativeSize)) {
          return false;
        }
      }

      // Tier filter
      if (tierFilter !== "all" && tierAssignments.size > 0) {
        const creativeTier = tierAssignments.get(c.id);
        if (tierFilter === "no_data") {
          // Show creatives with no tier assignment or explicit no_data
          if (creativeTier && creativeTier !== "no_data") {
            return false;
          }
        } else {
          if (creativeTier !== tierFilter) {
            return false;
          }
        }
      }

      // Approval filter
      if (approvalFilter === "approved" && c.approval_status !== "APPROVED") {
        return false;
      }
      if (approvalFilter === "not_approved" && c.approval_status === "APPROVED") {
        return false;
      }

      // Text search
      if (search) {
        const searchLower = search.toLowerCase();
        return (
          c.id.toLowerCase().includes(searchLower) ||
          c.name?.toLowerCase().includes(searchLower) ||
          c.advertiser_name?.toLowerCase().includes(searchLower) ||
          c.utm_campaign?.toLowerCase().includes(searchLower)
        );
      }

      return true;
    });

    // Sort by spend if enabled and performance data is available
    if (result && sortBySpend && performanceData) {
      result = [...result].sort((a, b) => {
        const perfA = performanceData[a.id];
        const perfB = performanceData[b.id];
        const spendA = perfA?.total_spend_micros ?? 0;
        const spendB = perfB?.total_spend_micros ?? 0;
        return spendB - spendA; // Descending order (highest spend first)
      });
    }

    return result;
  }, [creatives, selectedFormats, selectedSizes, search, sortBySpend, performanceData, tierFilter, tierAssignments, approvalFilter]);

  const hasActiveFilters =
    selectedFormats.size > 0 ||
    selectedSizes.size > 0 ||
    search ||
    tierFilter !== "all" ||
    approvalFilter !== "all";

  // Early returns AFTER all hooks
  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={
          error instanceof Error ? error.message : t.creatives.failedToLoadCreatives
        }
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="p-6">
      {/* Thumbnail Generation Banner - shows when videos need thumbnails */}
      <ThumbnailGenerationBanner buyerId={selectedSeatId} />

      {/* Compact Header with Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        {/* Title */}
        <div className="flex-shrink-0">
          <h1 className="text-xl font-bold text-gray-900">{t.creatives.title}</h1>
        </div>

        {/* Search - 35% width */}
        <div className="relative w-[35%] min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder={t.creatives.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-9 pr-8 py-1.5 w-full text-sm"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Format Filters - horizontal */}
        <div className="flex items-center gap-1">
          {FORMAT_FILTER_VALUES.map((filter) => (
            <button
              key={filter.value}
              onClick={() => toggleFormat(filter.value)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                selectedFormats.has(filter.value)
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}
            >
              {filter.value === 'VIDEO' ? t.creatives.video :
               filter.value === 'DISPLAY_IMAGE' ? t.creatives.displayImage :
               filter.value === 'DISPLAY_HTML' ? t.creatives.displayHtml :
               t.creatives.native}
            </button>
          ))}
        </div>

        {/* Approval Filters */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setApprovalFilter(approvalFilter === "approved" ? "all" : "approved")}
            className={cn(
              "px-2.5 py-1 rounded text-xs font-medium transition-colors",
              approvalFilter === "approved"
                ? "bg-green-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {t.creatives.approved} ({approvedCount})
          </button>
          <button
            onClick={() => setApprovalFilter(approvalFilter === "not_approved" ? "all" : "not_approved")}
            className={cn(
              "px-2.5 py-1 rounded text-xs font-medium transition-colors",
              approvalFilter === "not_approved"
                ? "bg-red-600 text-white"
                : "bg-gray-100 text-red-600 hover:bg-red-100"
            )}
          >
            {t.creatives.notApproved} ({notApprovedCount})
          </button>
        </div>

        {/* Tier Filter - only show when performance data is available */}
        {performanceData && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500 mr-1">{t.creatives.tier}</span>
            {TIER_OPTION_VALUES.map((tier) => (
              <button
                key={tier.value}
                onClick={() => setTierFilter(tier.value)}
                className={cn(
                  "px-2 py-1 rounded text-xs font-medium transition-colors",
                  tierFilter === tier.value
                    ? tier.color.replace("100", "200")
                    : tier.color + " hover:opacity-80"
                )}
              >
                {tier.value === 'all' ? t.creatives.all :
                 tier.value === 'high' ? t.creatives.high :
                 tier.value === 'medium' ? t.creatives.medium :
                 tier.value === 'low' ? t.creatives.low :
                 t.creatives.noData}
              </button>
            ))}
          </div>
        )}

        {/* Size Dropdown */}
        {availableSizes && availableSizes.length > 0 && (
          <div className="relative">
            <select
              value={selectedSizes.size === 1 ? Array.from(selectedSizes)[0] : ""}
              onChange={(e) => {
                setSelectedSizes(e.target.value ? new Set([e.target.value]) : new Set());
              }}
              className="input py-1.5 pr-8 text-sm min-w-[100px]"
            >
              <option value="">{t.creatives.allSizes}</option>
              {availableSizes.filter(s => s !== "0x0").map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </div>
        )}

        {/* Period Selector - compact buttons */}
        <div className="flex items-center gap-2">
          <div className="flex rounded border border-gray-300 overflow-hidden">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setDays(option.value)}
                className={cn(
                  "px-2.5 py-1 text-xs font-medium transition-colors",
                  days === option.value
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          {isLoadingPerformance && (
            <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
          )}
        </div>

        {/* Sort toggle */}
        <button
          onClick={() => setSortBySpend(!sortBySpend)}
          className={cn(
            "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors",
            sortBySpend
              ? "bg-primary-600 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          )}
        >
          <TrendingUp className="h-3.5 w-3.5" />
          {sortBySpend ? t.creatives.spend7Days.split(' ')[0] : t.creatives.defaultOrder}
        </button>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            <X className="h-3.5 w-3.5" />
            {t.creatives.clear}
          </button>
        )}

        {/* Count */}
        <div className="ml-auto text-sm text-gray-500">
          {t.creatives.countOf.replace('{count}', String(filteredCreatives?.length ?? 0)).replace('{total}', String(creatives?.length ?? 0))}
        </div>
      </div>

      {filteredCreatives && filteredCreatives.length > 0 ? (
        <VirtualizedGrid
          creatives={filteredCreatives}
          onPreview={setPreviewCreative}
          performanceData={performanceData}
          sortField={sortBySpend ? "spend" : null}
        />
      ) : (
        <div className="text-center py-12">
          <p className="text-gray-500">
            {hasActiveFilters
              ? t.creatives.noCreativesMatchFilters
              : selectedSeatId
              ? t.creatives.noCreativesForSeat
              : t.creatives.noCreativesFound}
          </p>
          {!hasActiveFilters && !selectedSeatId && (
            <Link href="/connect" className="btn-primary mt-4 inline-flex">
              {t.creatives.connectAccount}
            </Link>
          )}
          {!hasActiveFilters && selectedSeatId && (
            <p className="mt-2 text-sm text-gray-400">
              {t.creatives.trySyncingOrSelect}
            </p>
          )}
        </div>
      )}

      {/* Preview Modal */}
      {previewCreative && (
        <PreviewModal
          creative={previewCreative}
          performance={
            performanceData?.[previewCreative.id] ||
            previewPerformanceResponse?.performance?.[previewCreative.id]
          }
          onClose={() => setPreviewCreative(null)}
        />
      )}
    </div>
  );
}

export default function CreativesPage() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <CreativesContent />
    </Suspense>
  );
}
