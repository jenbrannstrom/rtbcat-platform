"use client";

import { useState, useEffect, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, X } from "lucide-react";
import { getCreatives, getSizes } from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import type { Creative } from "@/types/api";
import { cn } from "@/lib/utils";

// Virtual scrolling constants
const CARD_HEIGHT = 380;
const GAP = 16;

const FORMATS = ["VIDEO", "HTML", "NATIVE", "IMAGE"];
const COLUMNS = 4; // Fixed 4 columns for simplicity

function VirtualizedGrid({
  creatives,
  onPreview,
}: {
  creatives: Creative[];
  onPreview: (creative: Creative) => void;
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
  };

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

  const filteredCreatives = creatives?.filter((c) => {
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

  const hasActiveFilters = selectedFormats.size > 0 || selectedSizes.size > 0 || search;

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
            <a href="/collect" className="btn-primary mt-4 inline-flex">
              Collect Creatives
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
