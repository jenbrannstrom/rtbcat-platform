'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getConfigBreakdown,
  getConfigCreatives,
  getCreative,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, Info, Image, Square, CheckSquare, Ban, Shield } from 'lucide-react';
import { AppDrilldownModal } from './app-drilldown-modal';
import { useAccount } from '@/contexts/account-context';
import { PreviewModal } from '@/components/preview-modal';

interface ConfigBreakdownPanelProps {
  billing_id: string;
  days: number;
  isExpanded: boolean;
}

const TABS: { id: ConfigBreakdownType; label: string }[] = [
  { id: 'creative', label: 'By Creative' },
  { id: 'size', label: 'By Size' },
  { id: 'geo', label: 'By Geo' },
  { id: 'publisher', label: 'By Publisher' },
];

// Format large numbers with K/M suffix
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function formatMoney(amount: number): string {
  if (!amount || amount <= 0) return "$0";
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  if (amount >= 100) return `$${amount.toFixed(0)}`;
  return `$${amount.toFixed(2)}`;
}

export function ConfigBreakdownPanel({ billing_id, days, isExpanded }: ConfigBreakdownPanelProps) {
  const [activeTab, setActiveTab] = useState<ConfigBreakdownType>('creative');
  const [sortKey, setSortKey] = useState<'name' | 'spend' | 'reached' | 'impressions' | 'win_rate'>('reached');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const contentRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [selectedApp, setSelectedApp] = useState<string | null>(null);
  const { selectedBuyerId } = useAccount();
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [sizeCreatives, setSizeCreatives] = useState<ConfigCreativesItem[]>([]);
  const [sizeCreativesMessage, setSizeCreativesMessage] = useState<string | null>(null);
  const [selectedCreative, setSelectedCreative] = useState<null | { id: string }>(null);
  const [isLoadingCreative, setIsLoadingCreative] = useState(false);
  const [creativeLoadError, setCreativeLoadError] = useState<string | null>(null);
  const [fullCreative, setFullCreative] = useState<any | null>(null);
  const [expandedCountries, setExpandedCountries] = useState<Set<string>>(new Set());
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [sizeActionPending, setSizeActionPending] = useState(false);

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab, selectedBuyerId, days],
    queryFn: () => getConfigBreakdown(billing_id, activeTab, selectedBuyerId || undefined, days),
    enabled: isExpanded,
    staleTime: 30000, // Cache for 30 seconds
  });

  const { data: sizeCreativeData, isLoading: sizeCreativesLoading } = useQuery({
    queryKey: ['config-creatives', billing_id, selectedSize, selectedBuyerId, days],
    queryFn: () => getConfigCreatives(billing_id, selectedSize || undefined, selectedBuyerId || undefined, days),
    enabled: isExpanded && activeTab === 'size' && !!selectedSize,
    staleTime: 30000,
  });

  // Animate height changes
  useEffect(() => {
    if (contentRef.current) {
      setHeight(isExpanded ? contentRef.current.scrollHeight : 0);
    }
  }, [isExpanded, data, activeTab, selectedSize, sizeCreatives, sizeCreativesLoading, sizeCreativesMessage, isLoadingCreative, creativeLoadError]);

  useEffect(() => {
    setSelectedSize(null);
    setSizeCreatives([]);
    setSelectedCreative(null);
    setFullCreative(null);
    setCreativeLoadError(null);
    setExpandedCountries(new Set());
    setSelectedSizes(new Set());
    setSortKey('reached');
    setSortDir('desc');
  }, [activeTab, billing_id]);

  const toggleCountries = (creativeId: string) => {
    setExpandedCountries((prev) => {
      const next = new Set(prev);
      if (next.has(creativeId)) {
        next.delete(creativeId);
      } else {
        next.add(creativeId);
      }
      return next;
    });
  };

  // Size selection handlers
  const toggleSizeSelection = (sizeName: string) => {
    setSelectedSizes((prev) => {
      const next = new Set(prev);
      if (next.has(sizeName)) {
        next.delete(sizeName);
      } else {
        next.add(sizeName);
      }
      return next;
    });
  };

  const selectAllSizes = () => {
    const allSizeNames = sortedBreakdown.map((item) => item.name);
    setSelectedSizes(new Set(allSizeNames));
  };

  const clearSizeSelection = () => {
    setSelectedSizes(new Set());
  };

  const invertSizeSelection = () => {
    const allSizeNames = new Set(sortedBreakdown.map((item) => item.name));
    const inverted = new Set<string>();
    allSizeNames.forEach((name) => {
      if (!selectedSizes.has(name)) {
        inverted.add(name);
      }
    });
    setSelectedSizes(inverted);
  };

  const handleBulkBlock = async () => {
    if (selectedSizes.size === 0) return;
    setSizeActionPending(true);
    // TODO: Wire to backend API when available
    console.log('Block sizes:', Array.from(selectedSizes));
    // Placeholder: simulate action
    setTimeout(() => {
      setSizeActionPending(false);
      setSelectedSizes(new Set());
    }, 500);
  };

  const handleBulkUnblock = async () => {
    if (selectedSizes.size === 0) return;
    setSizeActionPending(true);
    // TODO: Wire to backend API when available
    console.log('Unblock sizes:', Array.from(selectedSizes));
    // Placeholder: simulate action
    setTimeout(() => {
      setSizeActionPending(false);
      setSelectedSizes(new Set());
    }, 500);
  };

  useEffect(() => {
    if (sizeCreativeData?.creatives) {
      setSizeCreatives(sizeCreativeData.creatives);
    }
    setSizeCreativesMessage(sizeCreativeData?.message || null);
  }, [sizeCreativeData]);

  useEffect(() => {
    if (!selectedCreative) {
      setFullCreative(null);
      setCreativeLoadError(null);
      return;
    }
    setIsLoadingCreative(true);
    setCreativeLoadError(null);
    getCreative(selectedCreative.id)
      .then((creative) => setFullCreative(creative))
      .catch((error: Error) => {
        setFullCreative(null);
        setCreativeLoadError(error?.message || 'Failed to load creative preview.');
      })
      .finally(() => setIsLoadingCreative(false));
  }, [selectedCreative]);

  // Sort breakdown by reached descending
  const sortedBreakdown = data?.breakdown
    ? [...data.breakdown].sort((a, b) => {
        const dir = sortDir === 'asc' ? 1 : -1;
        const getValue = (item: ConfigBreakdownItem) => {
          switch (sortKey) {
            case 'name':
              return item.name?.toLowerCase() || '';
            case 'spend':
              return item.spend_usd ?? 0;
            case 'impressions':
              return item.impressions ?? 0;
            case 'win_rate':
              return item.win_rate ?? 0;
            case 'reached':
            default:
              return item.reached ?? 0;
          }
        };
        const aVal = getValue(a);
        const bVal = getValue(b);
        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return aVal.localeCompare(bVal) * dir;
        }
        return ((aVal as number) - (bVal as number)) * dir;
      })
    : [];

  const handleSort = (key: typeof sortKey) => {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDir('desc');
  };

  return (
    <div
      className="overflow-hidden transition-all duration-300 ease-in-out"
      style={{ height: isExpanded ? height : 0 }}
    >
      <div ref={contentRef} className="border-t bg-gray-50/50 px-4 py-3">
        {/* Tabs */}
        <div className="flex gap-1 mb-3">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm border'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            <span className="text-sm">Loading breakdown...</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
            Failed to load breakdown data
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length === 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-700 mb-1">
                  No {activeTab} data for this config
                </p>
                <p className="text-gray-500 text-xs">
                  {data?.no_data_reason || (
                    activeTab === 'geo'
                      ? 'Geographic breakdown is not available. This config may not have geographic targeting data, or the precompute job has not yet processed this config.'
                      : activeTab === 'size'
                      ? 'Size breakdown is not available. This config may not have had bid activity in the selected period, or the precompute job has not yet processed this config.'
                      : activeTab === 'creative'
                      ? 'Creative breakdown is not available. This config may not have active creatives with bid activity, or the precompute job has not yet processed this config.'
                      : `To see ${activeTab} breakdown, import both catscan-quality (has billing_id) and catscan-bidsinauction CSV reports.`
                  )}
                </p>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length > 0 && (
          <>
            {/* Creative tab info note explaining the metric */}
            {activeTab === 'creative' && (
              <div className="mb-3 flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <Info className="h-4 w-4 text-blue-500 flex-shrink-0" />
                <span>
                  Win rate shows reached-to-impression conversion for this config.
                  This measures how efficiently bid requests convert to impressions.
                </span>
              </div>
            )}
            {activeTab === 'publisher' && (
              <div className="mb-3 flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                <Info className="h-4 w-4 text-amber-500 flex-shrink-0" />
                <span>
                  This table shows observed publisher performance from imported analytics data. Your editable
                  publisher blocklist is available in the pretargeting settings editor.
                </span>
              </div>
            )}
            {/* Size tab bulk toolbar */}
            {activeTab === 'size' && (
              <div className="mb-3 flex items-center justify-between p-2 bg-gray-50 border border-gray-200 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {selectedSizes.size > 0 ? `${selectedSizes.size} selected` : 'Select sizes to block/unblock'}
                  </span>
                  <button
                    onClick={selectAllSizes}
                    className="px-2 py-1 text-xs text-gray-600 hover:bg-gray-200 rounded transition-colors"
                  >
                    Select all
                  </button>
                  <button
                    onClick={invertSizeSelection}
                    className="px-2 py-1 text-xs text-gray-600 hover:bg-gray-200 rounded transition-colors"
                  >
                    Invert
                  </button>
                  {selectedSizes.size > 0 && (
                    <button
                      onClick={clearSizeSelection}
                      className="px-2 py-1 text-xs text-gray-400 hover:text-gray-600 rounded transition-colors"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleBulkBlock}
                    disabled={selectedSizes.size === 0 || sizeActionPending}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-red-50 text-red-600 hover:bg-red-100 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Ban className="h-3 w-3" />
                    Block
                  </button>
                  <button
                    onClick={handleBulkUnblock}
                    disabled={selectedSizes.size === 0 || sizeActionPending}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-green-50 text-green-600 hover:bg-green-100 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Shield className="h-3 w-3" />
                    Unblock
                  </button>
                  <span className="text-[10px] uppercase tracking-wide text-gray-400">
                    Feature #001 ROADMAP.md
                  </span>
                </div>
              </div>
            )}
            <div className="bg-white rounded-lg border overflow-hidden">
            {/* Table header */}
            <div
              className={cn(
                "grid gap-2 px-3 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500",
                activeTab === "creative"
                  ? "grid-cols-[repeat(14,minmax(0,1fr))]"
                  : activeTab === "size"
                  ? "grid-cols-[repeat(13,minmax(0,1fr))]"
                  : "grid-cols-12"
              )}
            >
              {activeTab === 'size' && (
                <div className="col-span-1 flex items-center">
                  <button
                    onClick={() => {
                      if (selectedSizes.size === sortedBreakdown.length) {
                        clearSizeSelection();
                      } else {
                        selectAllSizes();
                      }
                    }}
                    className="p-0.5 text-gray-400 hover:text-gray-600"
                    title={selectedSizes.size === sortedBreakdown.length ? "Deselect all" : "Select all"}
                  >
                    {selectedSizes.size === sortedBreakdown.length && sortedBreakdown.length > 0 ? (
                      <CheckSquare className="h-4 w-4" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                  </button>
                </div>
              )}
              <button
                type="button"
                onClick={() => handleSort("name")}
                className={cn(
                  activeTab === "creative" ? "col-span-4" : activeTab === "size" ? "col-span-4" : "col-span-4",
                  "flex items-center gap-1 text-left",
                  sortKey === "name" && "text-gray-700"
                )}
              >
                Name
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("spend")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "spend" && "text-gray-700"
                )}
              >
                Spend
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("reached")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "reached" && "text-gray-700"
                )}
              >
                Reached
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("impressions")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "impressions" && "text-gray-700"
                )}
              >
                Imp
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("win_rate")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "win_rate" && "text-gray-700"
                )}
              >
                Win Rate
                <ArrowUpDown className="h-3 w-3" />
              </button>
              {activeTab === "creative" && (
                <>
                  <div className="col-span-1">Country Targeted</div>
                  <div className="col-span-1">Creative Lang</div>
                </>
              )}
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {sortedBreakdown.map((item, index) => {
                const isClickable = false;
                const winRate = item.win_rate ?? 0;
                const winRateClass =
                  winRate < 51 ? 'text-red-600' : winRate < 75 ? 'text-orange-600' : 'text-green-600';
                const nameColSpan = activeTab === 'creative' ? 'col-span-4' : activeTab === 'size' ? 'col-span-3' : 'col-span-4';
                const isSelected = activeTab === 'size' && selectedSizes.has(item.name);
                return (
                  <div key={`${item.name}-${index}`}>
                    <div
                      onClick={() => isClickable && setSelectedApp(item.name)}
                      className={cn(
                        'grid gap-2 px-3 py-2 text-sm items-center',
                        activeTab === 'creative'
                          ? 'grid-cols-[repeat(14,minmax(0,1fr))]'
                          : activeTab === 'size'
                          ? 'grid-cols-[repeat(13,minmax(0,1fr))]'
                          : 'grid-cols-12',
                        'hover:bg-gray-50 transition-colors',
                        isClickable && 'cursor-pointer hover:bg-blue-50',
                        isSelected && 'bg-blue-50'
                      )}
                    >
                      {activeTab === 'size' && (
                        <div className="col-span-1 flex items-center">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleSizeSelection(item.name);
                            }}
                            className="p-0.5 text-gray-400 hover:text-gray-600"
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4 text-blue-600" />
                            ) : (
                              <Square className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      )}
                      <div
                        className={cn(
                          nameColSpan,
                          "font-medium text-gray-900 flex items-center gap-1",
                          activeTab === "creative" && "cursor-pointer"
                        )}
                        title={item.name}
                        onClick={(event) => {
                          if (activeTab !== "creative") return;
                          event.stopPropagation();
                          setSelectedCreative({ id: item.name });
                        }}
                      >
                        <span className="truncate">{item.name}</span>
                        {activeTab === 'size' && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              const next = item.name;
                              setSelectedSize((prev) => (prev === next ? null : next));
                              setSizeCreativesMessage(null);
                            }}
                            className="p-1 text-gray-400 hover:text-gray-600"
                            title="View creatives for this size"
                          >
                            <ChevronRight className="h-3 w-3" />
                          </button>
                        )}
                        {activeTab === 'creative' && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedCreative({ id: item.name });
                            }}
                            className="p-1 text-gray-400 hover:text-gray-600"
                            title="View creative"
                          >
                            <Image className="h-3 w-3" />
                          </button>
                        )}
                        {isClickable && (
                          <ChevronRight className="h-3 w-3 text-gray-400 flex-shrink-0" />
                        )}
                      </div>
                      <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                        {formatMoney(item.spend_usd ?? 0)}
                      </div>
                      <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                        {formatNumber(item.reached)}
                      </div>
                      <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                        {formatNumber(item.impressions || 0)}
                      </div>
                      <div className={cn('col-span-2 text-right font-medium', winRateClass)}>
                        {winRate.toFixed(1)}%
                      </div>
                      {activeTab === 'creative' && (
                        <>
                          <div className="col-span-1 text-xs text-gray-600 truncate">
                            {(item.target_countries || []).join(", ") || "—"}
                          </div>
                          <div className="col-span-1 text-xs text-gray-600 flex items-center gap-1">
                            <span className="truncate">{item.creative_language || "—"}</span>
                            {item.language_mismatch && (
                              <span
                                className="inline-flex"
                                title={`Language mismatch: ${item.mismatched_countries?.join(", ") || "check geo targets"}`}
                              >
                                <AlertTriangle className="h-3 w-3 text-orange-500" />
                              </span>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                    {activeTab === 'size' && selectedSize === item.name && (
                      <div className="border-t bg-gray-50 px-3 py-2">
                        <div className="grid grid-cols-6 gap-2 text-xs font-medium text-gray-500 border-b pb-1">
                          <div className="col-span-3">Creative</div>
                          <div className="col-span-2">Country (if available)</div>
                          <div className="col-span-1 text-right">Preview</div>
                        </div>
                        <div className="py-1 text-[11px] text-gray-500">
                          Country is optional and may be unavailable in some imported CSV slices.
                        </div>
                        {sizeCreativesLoading && (
                          <div className="py-2 text-sm text-gray-500">Loading creatives...</div>
                        )}
                        {!sizeCreativesLoading && sizeCreatives.length === 0 && (
                          <div className="py-2 text-sm text-gray-400">
                            {sizeCreativesMessage || `No creatives found for "${selectedSize}".`}
                          </div>
                        )}
                        {!sizeCreativesLoading && sizeCreatives.length > 0 && (
                          <div className="divide-y">
                            {sizeCreatives.map((creative) => (
                              <div key={creative.id} className="grid grid-cols-6 gap-2 py-2 text-sm items-center">
                                <div className="col-span-3 font-mono text-gray-800 truncate">
                                  {creative.name}
                                </div>
                                <div className="col-span-2 text-xs text-gray-600 truncate">
                                  {creative.serving_countries && creative.serving_countries.length > 1 ? (
                                    <button
                                      onClick={() => toggleCountries(creative.id)}
                                      className="text-left text-gray-600 hover:text-gray-800"
                                    >
                                      {creative.serving_countries.slice(0, 1).join(", ")}
                                      <span className="ml-1 text-gray-400">
                                        +{creative.serving_countries.length - 1}
                                      </span>
                                    </button>
                                  ) : (
                                    creative.serving_countries?.join(", ") || "—"
                                  )}
                                </div>
                                <div className="col-span-1 flex justify-end">
                                  <button
                                    onClick={() => setSelectedCreative({ id: creative.id })}
                                    className="p-1 text-gray-400 hover:text-gray-600"
                                    title="View creative"
                                  >
                                    <Image className="h-3 w-3" />
                                  </button>
                                </div>
                                {expandedCountries.has(creative.id) && (
                                  <div className="col-span-6 text-xs text-gray-500">
                                    {creative.serving_countries?.join(", ") || "—"}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          </>
        )}

        {/* Drill-down modal */}
        {selectedApp && (
          <AppDrilldownModal
            appName={selectedApp}
            billingId={billing_id}
            onClose={() => setSelectedApp(null)}
          />
        )}
        {selectedCreative && isLoadingCreative && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedCreative(null)} />
            <div className="relative bg-white rounded-lg shadow-xl p-6 flex items-center gap-3 text-gray-600">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Loading creative preview...</span>
            </div>
          </div>
        )}
        {selectedCreative && !isLoadingCreative && !fullCreative && creativeLoadError && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedCreative(null)} />
            <div className="relative bg-white rounded-lg shadow-xl p-5 max-w-md w-full mx-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">Creative preview unavailable</h3>
              <p className="text-sm text-gray-600 mb-4">{creativeLoadError}</p>
              <div className="flex justify-end gap-2">
                <button
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50"
                  onClick={() => setSelectedCreative(null)}
                >
                  Close
                </button>
                <button
                  className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
                  onClick={() => setSelectedCreative({ id: selectedCreative.id })}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}
        {fullCreative && selectedCreative && (
          <PreviewModal
            creative={fullCreative}
            onClose={() => {
              setSelectedCreative(null);
              setFullCreative(null);
              setCreativeLoadError(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
