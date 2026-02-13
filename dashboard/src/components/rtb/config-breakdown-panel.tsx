'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getConfigBreakdown,
  getConfigCreatives,
  getCreative,
  getPretargetingConfigDetail,
  createPendingChange,
  cancelPendingChange,
  applyAllPendingChanges,
  syncPretargetingConfigs,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
  type PendingChange,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, Info, Image, X, Check, Clock, Upload } from 'lucide-react';
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
  const [showConfirmPush, setShowConfirmPush] = useState(false);
  const [pushResult, setPushResult] = useState<{ success: boolean; message: string } | null>(null);
  const queryClient = useQueryClient();

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab, selectedBuyerId, days],
    queryFn: () => getConfigBreakdown(billing_id, activeTab, selectedBuyerId || undefined, days),
    enabled: isExpanded,
    staleTime: 30000, // Cache for 30 seconds
  });

  const { data: configDetail } = useQuery({
    queryKey: ['pretargeting-detail', billing_id],
    queryFn: () => getPretargetingConfigDetail(billing_id),
    enabled: isExpanded && activeTab === 'size',
  });

  const { data: sizeCreativeData, isLoading: sizeCreativesLoading } = useQuery({
    queryKey: ['config-creatives', billing_id, selectedSize, selectedBuyerId, days],
    queryFn: () => getConfigCreatives(billing_id, selectedSize || undefined, selectedBuyerId || undefined, days),
    enabled: isExpanded && activeTab === 'size' && !!selectedSize,
    staleTime: 30000,
  });

  const createChangeMutation = useMutation({
    mutationFn: createPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown', billing_id] });
    },
  });

  const cancelChangeMutation = useMutation({
    mutationFn: cancelPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown', billing_id] });
    },
  });

  const applyAllMutation = useMutation({
    mutationFn: () => applyAllPendingChanges(billing_id, false),
    onSuccess: async (result) => {
      await syncPretargetingConfigs();
      setPushResult({ success: true, message: result.message });
      setShowConfirmPush(false);
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });
  const sizeActionBusy = createChangeMutation.isPending || cancelChangeMutation.isPending || applyAllMutation.isPending;

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

  const pendingChanges = configDetail?.pending_changes || [];
  const pendingSizeAdds = pendingChanges.filter((change) => change.change_type === 'add_size');
  const pendingSizeRemoves = pendingChanges.filter((change) => change.change_type === 'remove_size');
  const pendingSizeChanges = pendingChanges.filter((change) =>
    change.change_type === 'add_size' || change.change_type === 'remove_size'
  );
  const hasPendingSizeChanges = pendingSizeChanges.length > 0;
  const hasOtherPendingChanges = pendingChanges.length > pendingSizeChanges.length;
  const effectiveIncludedSizes = (() => {
    const included = new Set(configDetail?.included_sizes || []);
    pendingSizeAdds.forEach((change) => included.add(change.value));
    pendingSizeRemoves.forEach((change) => included.delete(change.value));
    return included;
  })();

  const findPendingChange = (sizeName: string, type: 'add_size' | 'remove_size'): PendingChange | undefined =>
    pendingChanges.find((change) => change.change_type === type && change.value === sizeName);

  const isSizeIncluded = (sizeName: string): boolean => effectiveIncludedSizes.has(sizeName);

  const toggleSizeBlockState = (sizeName: string) => {
    const pendingAdd = findPendingChange(sizeName, 'add_size');
    if (pendingAdd) {
      cancelChangeMutation.mutate(pendingAdd.id);
      return;
    }

    const pendingRemove = findPendingChange(sizeName, 'remove_size');
    if (pendingRemove) {
      cancelChangeMutation.mutate(pendingRemove.id);
      return;
    }

    const currentlyIncluded = isSizeIncluded(sizeName);
    createChangeMutation.mutate({
      billing_id,
      change_type: currentlyIncluded ? 'remove_size' : 'add_size',
      field_name: 'included_sizes',
      value: sizeName,
      reason: currentlyIncluded ? 'Blocked from Home size breakdown' : 'Unblocked from Home size breakdown',
    });
  };

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
            {activeTab === 'size' && (
              <div className="mb-3 flex items-center justify-between p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <span>
                  Click <span className="font-semibold">X</span> to block a size or <span className="font-semibold">✓</span> to unblock it.
                </span>
                {hasPendingSizeChanges && (
                  <span className="font-medium">
                    {pendingSizeChanges.length} pending
                  </span>
                )}
              </div>
            )}
            {pushResult && (
              <div className={cn(
                "mb-3 rounded border px-3 py-2 text-xs",
                pushResult.success
                  ? "bg-green-50 border-green-200 text-green-800"
                  : "bg-red-50 border-red-200 text-red-800"
              )}>
                {pushResult.message}
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
              <button
                type="button"
                onClick={() => handleSort("name")}
                className={cn(
                  "col-span-4",
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
              {activeTab === "size" && (
                <div className="col-span-1 text-right">Action</div>
              )}
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {sortedBreakdown.map((item, index) => {
                const isClickable = false;
                const winRate = item.win_rate ?? 0;
                const winRateClass =
                  winRate < 51 ? 'text-red-600' : winRate < 75 ? 'text-orange-600' : 'text-green-600';
                const nameColSpan = 'col-span-4';
                const pendingAdd = activeTab === 'size' ? findPendingChange(item.name, 'add_size') : undefined;
                const pendingRemove = activeTab === 'size' ? findPendingChange(item.name, 'remove_size') : undefined;
                const hasPendingToggle = Boolean(pendingAdd || pendingRemove);
                const includedInConfig = activeTab === 'size' ? isSizeIncluded(item.name) : false;
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
                        activeTab === 'size' && hasPendingToggle && 'bg-amber-50'
                      )}
                    >
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
                      {activeTab === 'size' && (
                        <div className="col-span-1 flex justify-end">
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              toggleSizeBlockState(item.name);
                            }}
                            disabled={sizeActionBusy}
                            className={cn(
                              'inline-flex h-6 w-6 items-center justify-center rounded border transition-colors disabled:opacity-50',
                              includedInConfig
                                ? 'border-red-200 bg-red-50 text-red-600 hover:bg-red-100'
                                : 'border-green-200 bg-green-50 text-green-600 hover:bg-green-100'
                            )}
                            title={includedInConfig ? 'Block size (remove from targeting)' : 'Unblock size (add to targeting)'}
                          >
                            {includedInConfig ? <X className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}
                          </button>
                        </div>
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
          {activeTab === 'size' && hasPendingSizeChanges && (
            <div className="sticky bottom-3 mt-3 flex justify-end">
              <div className="w-full max-w-md rounded-lg border border-yellow-300 bg-yellow-50 p-3 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-medium text-yellow-900">
                  <Clock className="h-4 w-4" />
                  Pending Size Changes ({pendingSizeChanges.length})
                </div>
                <div className="mt-2 max-h-24 overflow-y-auto space-y-1 text-xs text-yellow-800">
                  {pendingSizeChanges.map((change) => (
                    <div key={change.id} className="flex items-center justify-between gap-2">
                      <span className="truncate">
                        {change.change_type === 'add_size' ? 'Unblock' : 'Block'}: {change.value}
                      </span>
                      <button
                        onClick={() => cancelChangeMutation.mutate(change.id)}
                        disabled={sizeActionBusy}
                        className="text-yellow-700 hover:text-yellow-900"
                        title="Undo change"
                      >
                        Undo
                      </button>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <button
                    onClick={() => pendingSizeChanges.forEach((change) => cancelChangeMutation.mutate(change.id))}
                    disabled={sizeActionBusy}
                    className="text-xs text-yellow-700 hover:text-yellow-900 disabled:opacity-50"
                  >
                    Discard All
                  </button>
                  <button
                    onClick={() => setShowConfirmPush(true)}
                    disabled={sizeActionBusy}
                    className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    <Upload className="h-3 w-3" />
                    Review & Commit
                  </button>
                </div>
              </div>
            </div>
          )}
          </>
        )}

        {showConfirmPush && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40" onClick={() => setShowConfirmPush(false)} />
            <div className="relative mx-4 w-full max-w-lg rounded-lg border bg-white p-4 shadow-xl">
              <h3 className="text-sm font-semibold text-gray-900">Confirm Changes to Google</h3>
              <p className="mt-1 text-xs text-gray-600">
                You are about to commit {pendingSizeChanges.length} size change{pendingSizeChanges.length !== 1 ? 's' : ''} for billing ID {billing_id}.
              </p>
              {hasOtherPendingChanges && (
                <p className="mt-2 rounded bg-yellow-50 px-2 py-1 text-xs text-yellow-800">
                  This billing ID also has {pendingChanges.length - pendingSizeChanges.length} other pending change(s), and they will be committed too.
                </p>
              )}
              <div className="mt-3 max-h-40 overflow-y-auto space-y-1 rounded border bg-gray-50 p-2 text-xs">
                {pendingSizeChanges.map((change) => (
                  <div key={`confirm-${change.id}`}>
                    • {change.change_type === 'add_size' ? 'Unblock' : 'Block'} {change.value}
                  </div>
                ))}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => setShowConfirmPush(false)}
                  disabled={applyAllMutation.isPending}
                  className="rounded border px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={() => applyAllMutation.mutate()}
                  disabled={applyAllMutation.isPending}
                  className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {applyAllMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
                  Commit to Google
                </button>
              </div>
            </div>
          </div>
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
