'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getConfigBreakdown,
  getConfigCreatives,
  getCreative,
  getPretargetingPublishers,
  addPretargetingPublisher,
  removePretargetingPublisher,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
  type PretargetingPublisher,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, Info, Image, Square, CheckSquare, Ban, Shield, Search, Plus, X, Upload, Download } from 'lucide-react';
import { AppDrilldownModal } from './app-drilldown-modal';
import { useAccount } from '@/contexts/account-context';
import { PreviewModal } from '@/components/preview-modal';

interface ConfigBreakdownPanelProps {
  billing_id: string;
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

// Publisher helper functions
function normalizePublisherId(value: string): string {
  return value.trim();
}

function isValidPublisherId(value: string): boolean {
  if (!value.includes('.')) return false;
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]*\.[a-zA-Z0-9._-]+$/.test(value);
}

function detectPublisherType(value: string): 'App' | 'Web' {
  const parts = value.toLowerCase().split('.');
  const appPrefixes = new Set(['com', 'net', 'org', 'io', 'co', 'app']);
  if (parts.length >= 3 && appPrefixes.has(parts[0])) {
    return 'App';
  }
  return 'Web';
}

export function ConfigBreakdownPanel({ billing_id, isExpanded }: ConfigBreakdownPanelProps) {
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
  const [fullCreative, setFullCreative] = useState<any | null>(null);
  const [expandedCountries, setExpandedCountries] = useState<Set<string>>(new Set());
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [sizeActionPending, setSizeActionPending] = useState(false);

  // Publisher tab state
  const [publisherFilter, setPublisherFilter] = useState('');
  const [newPublisher, setNewPublisher] = useState('');
  const [publisherInputError, setPublisherInputError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const isDimensionSize = (value: string | null) => {
    if (!value) return false;
    return /^\d+\s*x\s*\d+$/i.test(value.trim());
  };

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab, selectedBuyerId],
    queryFn: () => getConfigBreakdown(billing_id, activeTab, selectedBuyerId || undefined),
    enabled: isExpanded,
    staleTime: 30000, // Cache for 30 seconds
  });

  const { data: sizeCreativeData, isLoading: sizeCreativesLoading } = useQuery({
    queryKey: ['config-creatives', billing_id, selectedSize, selectedBuyerId],
    queryFn: () => getConfigCreatives(billing_id, selectedSize || undefined, selectedBuyerId || undefined),
    enabled: isExpanded && activeTab === 'size' && !!selectedSize && isDimensionSize(selectedSize),
    staleTime: 30000,
  });

  // Query for publishers (when publisher tab is active)
  const { data: publishersData, isLoading: publishersLoading, refetch: refetchPublishers } = useQuery({
    queryKey: ['pretargeting-publishers', billing_id],
    queryFn: () => getPretargetingPublishers(billing_id),
    enabled: isExpanded && activeTab === 'publisher',
    staleTime: 30000,
  });

  // Publisher mutations
  const addPublisherMutation = useMutation({
    mutationFn: ({ publisherId, mode }: { publisherId: string; mode: 'BLACKLIST' | 'WHITELIST' }) =>
      addPretargetingPublisher(billing_id, publisherId, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
      setNewPublisher('');
      setPublisherInputError(null);
    },
    onError: (error: any) => {
      setPublisherInputError(error?.message || 'Failed to add publisher');
    },
  });

  const removePublisherMutation = useMutation({
    mutationFn: (publisherId: string) => removePretargetingPublisher(billing_id, publisherId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
    },
  });

  // Animate height changes
  useEffect(() => {
    if (contentRef.current) {
      setHeight(isExpanded ? contentRef.current.scrollHeight : 0);
    }
  }, [isExpanded, data, activeTab, selectedSize, sizeCreatives, sizeCreativesLoading, sizeCreativesMessage, publishersData, publishersLoading]);

  useEffect(() => {
    setSelectedSize(null);
    setSizeCreatives([]);
    setExpandedCountries(new Set());
    setSelectedSizes(new Set());
    setPublisherFilter('');
    setNewPublisher('');
    setPublisherInputError(null);
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

  // Publisher handlers
  const handleAddPublisher = () => {
    const normalized = normalizePublisherId(newPublisher);
    if (!normalized) return;
    if (!isValidPublisherId(normalized)) {
      setPublisherInputError('Invalid publisher ID format. Use bundle ID (com.example.app) or domain (example.com).');
      return;
    }
    // Check if already exists
    const existingPublisher = publishersData?.publishers?.find(
      (p: PretargetingPublisher) => p.publisher_id === normalized && p.status !== 'pending_remove'
    );
    if (existingPublisher) {
      setPublisherInputError('Publisher already in list.');
      return;
    }
    setPublisherInputError(null);
    addPublisherMutation.mutate({ publisherId: normalized, mode: 'BLACKLIST' });
  };

  const handleRemovePublisher = (publisherId: string) => {
    removePublisherMutation.mutate(publisherId);
  };

  // Filter publishers
  const filteredPublishers = publishersData?.publishers?.filter((p: PretargetingPublisher) =>
    p.publisher_id.toLowerCase().includes(publisherFilter.trim().toLowerCase())
  ) || [];

  const activePublisherCount = publishersData?.publishers?.filter(
    (p: PretargetingPublisher) => p.status === 'active'
  ).length || 0;
  const pendingAddCount = publishersData?.publishers?.filter(
    (p: PretargetingPublisher) => p.status === 'pending_add'
  ).length || 0;
  const pendingRemoveCount = publishersData?.publishers?.filter(
    (p: PretargetingPublisher) => p.status === 'pending_remove'
  ).length || 0;

  useEffect(() => {
    if (sizeCreativeData?.creatives) {
      setSizeCreatives(sizeCreativeData.creatives);
    }
    setSizeCreativesMessage(sizeCreativeData?.message || null);
  }, [sizeCreativeData]);

  useEffect(() => {
    if (!selectedCreative) {
      setFullCreative(null);
      return;
    }
    setIsLoadingCreative(true);
    getCreative(selectedCreative.id)
      .then((creative) => setFullCreative(creative))
      .catch(() => setFullCreative(null))
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
        {isLoading && activeTab !== 'publisher' && (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            <span className="text-sm">Loading breakdown...</span>
          </div>
        )}

        {error && activeTab !== 'publisher' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
            Failed to load breakdown data
          </div>
        )}

        {/* Publisher tab - embedded list */}
        {activeTab === 'publisher' && (
          <div className="space-y-3">
            {publishersLoading && (
              <div className="flex items-center justify-center py-8 text-gray-400">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                <span className="text-sm">Loading publishers...</span>
              </div>
            )}

            {!publishersLoading && (
              <>
                {/* Publisher header with mode and counts */}
                <div className="flex items-center justify-between p-2 bg-gray-50 border border-gray-200 rounded">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">
                      Blacklist: {activePublisherCount} blocked
                    </span>
                    {pendingAddCount > 0 && (
                      <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                        +{pendingAddCount} pending
                      </span>
                    )}
                    {pendingRemoveCount > 0 && (
                      <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded">
                        -{pendingRemoveCount} pending
                      </span>
                    )}
                  </div>
                </div>

                {/* Search filter */}
                <div className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={publisherFilter}
                    onChange={(e) => setPublisherFilter(e.target.value)}
                    placeholder="Filter publishers..."
                    className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Publisher list */}
                <div className="bg-white rounded-lg border overflow-hidden">
                  <div className="grid grid-cols-[1fr_80px_100px_80px] gap-2 px-3 py-2 bg-gray-50 text-xs font-medium text-gray-500 border-b">
                    <span>Publisher ID</span>
                    <span>Type</span>
                    <span>Status</span>
                    <span className="text-right">Action</span>
                  </div>
                  {filteredPublishers.length === 0 ? (
                    <div className="px-3 py-6 text-sm text-gray-500 text-center">
                      {(publishersData?.publishers?.length || 0) === 0
                        ? 'No publishers blocked yet.'
                        : 'No publishers match the current filter.'}
                    </div>
                  ) : (
                    <div className="divide-y max-h-60 overflow-y-auto">
                      {filteredPublishers.map((pub: PretargetingPublisher) => {
                        const isPendingAdd = pub.status === 'pending_add';
                        const isPendingRemove = pub.status === 'pending_remove';
                        return (
                          <div
                            key={pub.publisher_id}
                            className={cn(
                              'grid grid-cols-[1fr_80px_100px_80px] gap-2 px-3 py-2 text-sm items-center',
                              isPendingRemove && 'bg-red-50 text-gray-400 line-through'
                            )}
                          >
                            <div className="min-w-0">
                              <div className="truncate text-xs text-gray-700" title={pub.publisher_id}>
                                {pub.publisher_id}
                              </div>
                            </div>
                            <span className="text-xs text-gray-500">{detectPublisherType(pub.publisher_id)}</span>
                            <span className={cn(
                              "text-xs",
                              isPendingAdd || isPendingRemove ? "text-yellow-600" : "text-gray-600"
                            )}>
                              {isPendingAdd || isPendingRemove ? '⏳ Pending' : 'Blocked'}
                            </span>
                            <div className="text-right">
                              <button
                                onClick={() => handleRemovePublisher(pub.publisher_id)}
                                disabled={removePublisherMutation.isPending}
                                className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50"
                              >
                                {isPendingRemove ? 'Undo' : 'Remove'}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Add publisher input */}
                <div className="space-y-1">
                  <label className="text-xs text-gray-500">Add publisher to block:</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newPublisher}
                      onChange={(e) => {
                        setNewPublisher(e.target.value);
                        setPublisherInputError(null);
                      }}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddPublisher()}
                      placeholder="com.example.app or publisher.com"
                      className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={handleAddPublisher}
                      disabled={!newPublisher.trim() || addPublisherMutation.isPending}
                      className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                  {publisherInputError && (
                    <p className="text-xs text-red-600">{publisherInputError}</p>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length === 0 && activeTab !== 'publisher' && (
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

        {!isLoading && !error && sortedBreakdown.length > 0 && activeTab !== 'publisher' && (
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
            <div className={cn(
              "grid gap-2 px-3 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500",
              activeTab === "creative" ? "grid-cols-14" : activeTab === "size" ? "grid-cols-13" : "grid-cols-12"
            )}>
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
                  activeTab === "creative" ? "col-span-4" : activeTab === "size" ? "col-span-3" : "col-span-4",
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
                const isClickable = activeTab === 'publisher';
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
                        activeTab === 'creative' ? 'grid-cols-14' : activeTab === 'size' ? 'grid-cols-13' : 'grid-cols-12',
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
                      <div className={cn(nameColSpan, "font-medium text-gray-900 flex items-center gap-1")} title={item.name}>
                        <span className="truncate">{item.name}</span>
                        {activeTab === 'size' && (
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              const next = item.name;
                              const isDimension = isDimensionSize(next);
                              setSelectedSize((prev) => (prev === next ? null : next));
                              if (!isDimension) {
                                setSizeCreatives([]);
                                setSizeCreativesMessage("Drill-down is only available for dimension sizes (e.g. 300x250).");
                              } else {
                                setSizeCreativesMessage(null);
                              }
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
                          <div className="col-span-2">Country targeted</div>
                          <div className="col-span-1 text-right">Preview</div>
                        </div>
                        {sizeCreativesLoading && (
                          <div className="py-2 text-sm text-gray-500">Loading creatives...</div>
                        )}
                        {!sizeCreativesLoading && sizeCreatives.length === 0 && (
                          <div className="py-2 text-sm text-gray-400">
                            {sizeCreativesMessage || "No creatives found for this size."}
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
        {fullCreative && selectedCreative && (
          <PreviewModal
            creative={fullCreative}
            onClose={() => setSelectedCreative(null)}
          />
        )}
      </div>
    </div>
  );
}
