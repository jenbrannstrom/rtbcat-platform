"use client";

import { useState, useEffect, Suspense, useRef, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, X, TrendingUp, Loader2 } from "lucide-react";
import { getCreatives, getSizes, getBatchPerformance } from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import type { Creative, PerformancePeriod, CreativePerformanceSummary } from "@/types/api";
import { cn } from "@/lib/utils";

// Sort options for the dropdown
const SORT_OPTIONS: { value: PerformancePeriod | "none"; label: string }[] = [
  { value: "none", label: "Default Order" },
  { value: "yesterday", label: "Spend (Yesterday)" },
  { value: "7d", label: "Spend (7 Days)" },
  { value: "30d", label: "Spend (30 Days)" },
  { value: "all_time", label: "Spend (All Time)" },
];

// Performance tiers
type PerformanceTier = "high" | "medium" | "low" | "no_data";

const TIER_OPTIONS: { value: PerformanceTier | "all"; label: string; color: string }[] = [
  { value: "all", label: "All", color: "bg-gray-100 text-gray-600" },
  { value: "high", label: "High", color: "bg-green-100 text-green-700" },
  { value: "medium", label: "Medium", color: "bg-yellow-100 text-yellow-700" },
  { value: "low", label: "Low", color: "bg-red-100 text-red-700" },
  { value: "no_data", label: "No Data", color: "bg-gray-100 text-gray-500" },
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
const CARD_HEIGHT = 380;
const GAP = 16;

const FORMATS = ["VIDEO", "HTML", "NATIVE", "IMAGE"];
const COLUMNS = 4; // Fixed 4 columns for simplicity

function VirtualizedGrid({
  creatives,
  onPreview,
  performanceData,
}: {
  creatives: Creative[];
  onPreview: (creative: Creative) => void;
  performanceData?: Record<string, CreativePerformanceSummary>;
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
  const searchParams = useSearchParams();

  // Get buyer_id from URL params (set by sidebar)
  const selectedSeatId = searchParams.get("buyer_id");

  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(new Set());
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
  const [sortBy, setSortBy] = useState<PerformancePeriod | "none">("none");
  const [tierFilter, setTierFilter] = useState<PerformanceTier | "all">("all");

  const {
    data: creatives,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["creatives", selectedSeatId],
    queryFn: () => getCreatives({ limit: 1000, buyer_id: selectedSeatId ?? undefined }),
  });

  const { data: availableSizes } = useQuery({
    queryKey: ["sizes"],
    queryFn: getSizes,
  });

  // Fetch performance data when sorting by spend
  const {
    data: performanceResponse,
    isLoading: isLoadingPerformance,
  } = useQuery({
    queryKey: ["performance", creatives?.map((c) => c.id), sortBy],
    queryFn: () => {
      if (!creatives || creatives.length === 0 || sortBy === "none") {
        return null;
      }
      return getBatchPerformance(
        creatives.map((c) => c.id),
        sortBy as PerformancePeriod
      );
    },
    enabled: !!creatives && creatives.length > 0 && sortBy !== "none",
    staleTime: 60000, // Cache for 1 minute
  });

  const performanceData = performanceResponse?.performance;

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
  };

  // Filter and sort creatives - MUST be before early returns (hooks order)
  const filteredCreatives = useMemo(() => {
    if (!creatives) return undefined;

    let result = creatives.filter((c) => {
      // Format filter
      if (selectedFormats.size > 0 && !selectedFormats.has(c.format)) {
        return false;
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

    // Sort by spend if performance data is available
    if (result && sortBy !== "none" && performanceData) {
      result = [...result].sort((a, b) => {
        const perfA = performanceData[a.id];
        const perfB = performanceData[b.id];
        const spendA = perfA?.total_spend_micros ?? 0;
        const spendB = perfB?.total_spend_micros ?? 0;
        return spendB - spendA; // Descending order (highest spend first)
      });
    }

    return result;
  }, [creatives, selectedFormats, selectedSizes, search, sortBy, performanceData, tierFilter, tierAssignments]);

  const hasActiveFilters = selectedFormats.size > 0 || selectedSizes.size > 0 || search || tierFilter !== "all";

  // Early returns AFTER all hooks
  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={
          error instanceof Error ? error.message : "Failed to load creatives"
        }
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="p-6">
      {/* Compact Header with Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        {/* Title */}
        <div className="flex-shrink-0">
          <h1 className="text-xl font-bold text-gray-900">Creatives</h1>
        </div>

        {/* Search - 35% width */}
        <div className="relative w-[35%] min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search ID, name, advertiser..."
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
          {FORMATS.map((format) => (
            <button
              key={format}
              onClick={() => toggleFormat(format)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                selectedFormats.has(format)
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}
            >
              {format}
            </button>
          ))}
        </div>

        {/* Tier Filter - only show when performance data is available */}
        {sortBy !== "none" && performanceData && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500 mr-1">Tier:</span>
            {TIER_OPTIONS.map((tier) => (
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
                {tier.label}
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
              <option value="">All Sizes</option>
              {availableSizes.filter(s => s !== "0x0").map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </div>
        )}

        {/* Sort by Spend Dropdown */}
        <div className="relative flex items-center gap-1">
          <TrendingUp className="h-4 w-4 text-gray-400" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as PerformancePeriod | "none")}
            className="input py-1.5 pr-8 text-sm min-w-[140px]"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {isLoadingPerformance && (
            <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
          )}
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        )}

        {/* Count */}
        <div className="ml-auto text-sm text-gray-500">
          {filteredCreatives?.length ?? 0} of {creatives?.length ?? 0}
        </div>
      </div>

      {filteredCreatives && filteredCreatives.length > 0 ? (
        <VirtualizedGrid
          creatives={filteredCreatives}
          onPreview={setPreviewCreative}
          performanceData={performanceData}
        />
      ) : (
        <div className="text-center py-12">
          <p className="text-gray-500">
            {hasActiveFilters
              ? "No creatives match your filters"
              : selectedSeatId
              ? "No creatives found for this seat"
              : "No creatives found"}
          </p>
          {!hasActiveFilters && !selectedSeatId && (
            <a href="/connect" className="btn-primary mt-4 inline-flex">
              Connect Account
            </a>
          )}
          {!hasActiveFilters && selectedSeatId && (
            <p className="mt-2 text-sm text-gray-400">
              Try syncing this seat or select a different one
            </p>
          )}
        </div>
      )}

      {/* Preview Modal */}
      {previewCreative && (
        <PreviewModal
          creative={previewCreative}
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
