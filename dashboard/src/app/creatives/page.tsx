"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { FixedSizeGrid } from "react-window";
import AutoSizer from "react-virtualized-auto-sizer";
import { Search, ChevronDown, ChevronUp } from "lucide-react";
import { getCreatives, getSizes } from "@/lib/api";
import { CreativeCard } from "@/components/creative-card";
import { PreviewModal } from "@/components/preview-modal";
import { SeatSelector } from "@/components/seat-selector";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import type { Creative } from "@/types/api";
import { cn } from "@/lib/utils";

// Virtual scrolling constants
const CARD_WIDTH = 280;
const CARD_HEIGHT = 360;
const GAP = 16;

const FORMATS = ["VIDEO", "HTML", "NATIVE", "IMAGE"];

function CreativesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get buyer_id from URL params
  const urlBuyerId = searchParams.get("buyer_id");
  const [selectedSeatId, setSelectedSeatId] = useState<string | null>(urlBuyerId);

  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(new Set());
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [previewCreative, setPreviewCreative] = useState<Creative | null>(null);
  const [showFilters, setShowFilters] = useState(true);

  // Sync URL with selected seat
  const handleSeatChange = useCallback((seatId: string | null) => {
    setSelectedSeatId(seatId);
    const params = new URLSearchParams(searchParams.toString());
    if (seatId) {
      params.set("buyer_id", seatId);
    } else {
      params.delete("buyer_id");
    }
    router.push(`/creatives${params.toString() ? `?${params.toString()}` : ""}`);
  }, [router, searchParams]);

  // Update state if URL changes externally
  useEffect(() => {
    setSelectedSeatId(urlBuyerId);
  }, [urlBuyerId]);

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
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Creatives</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse and manage your creative inventory
        </p>
      </div>

      {/* Seat Selector */}
      <div className="mb-6">
        <SeatSelector
          selectedSeatId={selectedSeatId}
          onSeatChange={handleSeatChange}
        />
      </div>

      {/* Filter Section */}
      <div className="mb-6 bg-white rounded-lg border border-gray-200 shadow-sm">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="w-full flex items-center justify-between px-4 py-3 text-left"
        >
          <span className="font-medium text-gray-900">
            Filters
            {hasActiveFilters && (
              <span className="ml-2 text-sm text-primary-600">
                ({selectedFormats.size + selectedSizes.size + (search ? 1 : 0)} active)
              </span>
            )}
          </span>
          {showFilters ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </button>

        {showFilters && (
          <div className="px-4 pb-4 border-t border-gray-100">
            {/* Search */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by ID, name, advertiser, or campaign..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="input pl-10 w-full"
                />
              </div>
            </div>

            {/* Formats */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Format
              </label>
              <div className="flex flex-wrap gap-2">
                {FORMATS.map((format) => (
                  <label
                    key={format}
                    className={cn(
                      "inline-flex items-center px-3 py-1.5 rounded-md border cursor-pointer transition-colors",
                      selectedFormats.has(format)
                        ? "bg-primary-50 border-primary-500 text-primary-700"
                        : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selectedFormats.has(format)}
                      onChange={() => toggleFormat(format)}
                      className="sr-only"
                    />
                    <span className="text-sm font-medium">{format}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Sizes */}
            {availableSizes && availableSizes.length > 0 && (
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Size
                </label>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                  {availableSizes.map((size) => (
                    <label
                      key={size}
                      className={cn(
                        "inline-flex items-center px-3 py-1.5 rounded-md border cursor-pointer transition-colors",
                        selectedSizes.has(size)
                          ? "bg-primary-50 border-primary-500 text-primary-700"
                          : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSizes.has(size)}
                        onChange={() => toggleSize(size)}
                        className="sr-only"
                      />
                      <span className="text-sm font-medium">{size}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Clear Filters */}
            {hasActiveFilters && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={clearFilters}
                  className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mb-4 text-sm text-gray-500">
        Showing {filteredCreatives?.length ?? 0} of {creatives?.length ?? 0} creatives
      </div>

      {filteredCreatives && filteredCreatives.length > 0 ? (
        <div className="h-[calc(100vh-400px)] min-h-[400px]">
          <AutoSizer>
            {({ height, width }) => {
              const columnCount = Math.max(1, Math.floor(width / (CARD_WIDTH + GAP)));
              const rowCount = Math.ceil(filteredCreatives.length / columnCount);

              return (
                <FixedSizeGrid
                  columnCount={columnCount}
                  columnWidth={CARD_WIDTH + GAP}
                  height={height}
                  rowCount={rowCount}
                  rowHeight={CARD_HEIGHT + GAP}
                  width={width}
                  className="scrollbar-thin"
                >
                  {({ columnIndex, rowIndex, style }) => {
                    const index = rowIndex * columnCount + columnIndex;
                    const creative = filteredCreatives[index];

                    if (!creative) return null;

                    return (
                      <div style={style} className="p-2">
                        <CreativeCard
                          creative={creative}
                          onPreview={setPreviewCreative}
                        />
                      </div>
                    );
                  }}
                </FixedSizeGrid>
              );
            }}
          </AutoSizer>
        </div>
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
