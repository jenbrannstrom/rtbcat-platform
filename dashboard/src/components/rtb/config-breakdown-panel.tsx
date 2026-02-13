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
  searchGeoTargets,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
  type GeoSearchResult,
  type PendingChange,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, Info, Image, X, Check, Clock, Upload, Search } from 'lucide-react';
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

function describePendingChange(change: PendingChange, publisherMode: string): string {
  switch (change.change_type) {
    case 'add_size':
      return `Allow size: ${change.value}`;
    case 'remove_size':
      return `Block size: ${change.value}`;
    case 'add_geo':
      return `Add geo: ${change.value}`;
    case 'remove_geo':
      return `Remove geo: ${change.value}`;
    case 'add_format':
      return `Enable format: ${change.value}`;
    case 'remove_format':
      return `Disable format: ${change.value}`;
    case 'set_maximum_qps':
      return `Set QPS limit: ${change.value}`;
    case 'add_publisher':
      return publisherMode === 'INCLUSIVE'
        ? `Allow publisher: ${change.value}`
        : `Block publisher: ${change.value}`;
    case 'remove_publisher':
      return publisherMode === 'INCLUSIVE'
        ? `Block publisher: ${change.value}`
        : `Unblock publisher: ${change.value}`;
    case 'set_publisher_mode':
      return `Publisher mode: ${change.value}`;
    default:
      return `${change.change_type}: ${change.value}`;
  }
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
  const [showLowVolumeSizes, setShowLowVolumeSizes] = useState(false);
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [geoSearchQuery, setGeoSearchQuery] = useState('');
  const [geoSearchType, setGeoSearchType] = useState<'all' | 'country' | 'city'>('all');
  const [geoSearchResults, setGeoSearchResults] = useState<GeoSearchResult[]>([]);
  const [selectedGeoId, setSelectedGeoId] = useState('');
  const [isGeoSearchLoading, setIsGeoSearchLoading] = useState(false);
  const [qpsInput, setQpsInput] = useState('');
  const selectAllSizesRef = useRef<HTMLInputElement>(null);
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
    enabled: isExpanded,
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
  const changeActionBusy =
    createChangeMutation.isPending || cancelChangeMutation.isPending || applyAllMutation.isPending;

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
    setShowLowVolumeSizes(false);
    setSelectedSizes(new Set());
    setGeoSearchQuery('');
    setGeoSearchResults([]);
    setSelectedGeoId('');
    setQpsInput('');
  }, [activeTab, billing_id]);

  useEffect(() => {
    if (activeTab !== 'size') {
      setSelectedSizes(new Set());
      return;
    }
    const validNames = new Set((data?.breakdown || []).map((item) => item.name));
    setSelectedSizes((prev) => {
      const next = new Set([...prev].filter((name) => validNames.has(name)));
      if (next.size === prev.size) {
        let same = true;
        for (const value of next) {
          if (!prev.has(value)) {
            same = false;
            break;
          }
        }
        if (same) return prev;
      }
      return next;
    });
  }, [activeTab, data?.breakdown]);

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

  useEffect(() => {
    const qpsValue = configDetail?.effective_maximum_qps ?? configDetail?.maximum_qps;
    setQpsInput(qpsValue === null || qpsValue === undefined ? '' : String(qpsValue));
  }, [billing_id, configDetail?.effective_maximum_qps, configDetail?.maximum_qps]);

  useEffect(() => {
    if (activeTab !== 'geo') {
      setGeoSearchResults([]);
      setSelectedGeoId('');
      setIsGeoSearchLoading(false);
      return;
    }

    const query = geoSearchQuery.trim();
    if (query.length < 2) {
      setGeoSearchResults([]);
      setSelectedGeoId('');
      setIsGeoSearchLoading(false);
      return;
    }

    let isCancelled = false;
    const timeoutId = setTimeout(async () => {
      try {
        setIsGeoSearchLoading(true);
        const results = await searchGeoTargets(query, { limit: 25, type: geoSearchType });
        if (isCancelled) return;
        setGeoSearchResults(results);
        setSelectedGeoId((previous) => {
          if (previous && results.some((item) => item.geo_id === previous)) return previous;
          return results[0]?.geo_id || '';
        });
      } catch {
        if (!isCancelled) {
          setGeoSearchResults([]);
          setSelectedGeoId('');
        }
      } finally {
        if (!isCancelled) {
          setIsGeoSearchLoading(false);
        }
      }
    }, 250);

    return () => {
      isCancelled = true;
      clearTimeout(timeoutId);
    };
  }, [activeTab, geoSearchQuery, geoSearchType]);

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
  const pendingSizeChanges = pendingChanges.filter(
    (change) => change.change_type === 'add_size' || change.change_type === 'remove_size'
  );
  const pendingQpsChanges = pendingChanges.filter((change) => change.change_type === 'set_maximum_qps');
  const latestPendingQpsChange =
    pendingQpsChanges.length > 0 ? pendingQpsChanges[pendingQpsChanges.length - 1] : null;
  const hasPendingChanges = pendingChanges.length > 0;

  const findPendingChange = (changeType: string, value: string): PendingChange | undefined =>
    pendingChanges.find((change) => change.change_type === changeType && change.value === value);

  const effectiveIncludedSizes = new Set(configDetail?.effective_sizes || configDetail?.included_sizes || []);
  const effectiveIncludedGeos = new Set(configDetail?.effective_geos || configDetail?.included_geos || []);
  const effectiveFormats = new Set(configDetail?.effective_formats || configDetail?.included_formats || []);
  const effectivePublisherMode =
    configDetail?.effective_publisher_targeting_mode ||
    configDetail?.publisher_targeting_mode ||
    'EXCLUSIVE';
  const effectivePublisherValues = new Set(
    configDetail?.effective_publisher_targeting_values || configDetail?.publisher_targeting_values || []
  );
  const persistedQpsLimit = configDetail?.maximum_qps ?? null;
  const effectiveQpsLimit = configDetail?.effective_maximum_qps ?? persistedQpsLimit;

  const isSizeIncluded = (sizeName: string): boolean => effectiveIncludedSizes.has(sizeName);
  const isFormatEnabled = (format: string): boolean => effectiveFormats.has(format);
  const isPublisherListed = (publisherValue: string): boolean => effectivePublisherValues.has(publisherValue);
  const isPublisherBlocked = (publisherValue: string): boolean => {
    if (effectivePublisherMode === 'INCLUSIVE') {
      return !isPublisherListed(publisherValue);
    }
    return isPublisherListed(publisherValue);
  };

  const sizeRows = activeTab === 'size' ? sortedBreakdown : [];
  const visibleSizeRows = activeTab === 'size'
    ? (showLowVolumeSizes ? sizeRows : sizeRows.filter((row) => (row.impressions ?? 0) >= 1000))
    : [];
  const hiddenLowVolumeSizeCount = activeTab === 'size'
    ? sizeRows.length - visibleSizeRows.length
    : 0;
  const visibleSizeNames = new Set(visibleSizeRows.map((row) => row.name));
  const selectedVisibleSizeCount = [...selectedSizes].filter((name) => visibleSizeNames.has(name)).length;
  const allVisibleSizesSelected = visibleSizeRows.length > 0 && selectedVisibleSizeCount === visibleSizeRows.length;
  const hasPartialVisibleSelection =
    selectedVisibleSizeCount > 0 && selectedVisibleSizeCount < visibleSizeRows.length;

  useEffect(() => {
    if (!selectAllSizesRef.current) return;
    selectAllSizesRef.current.indeterminate = hasPartialVisibleSelection;
  }, [hasPartialVisibleSelection, allVisibleSizesSelected]);

  const toggleSizeBlockState = (sizeName: string) => {
    const currentlyIncluded = isSizeIncluded(sizeName);
    setSizeInclusionState(sizeName, !currentlyIncluded);
  };

  const setSizeInclusionState = (sizeName: string, shouldInclude: boolean) => {
    const pendingAdd = findPendingChange('add_size', sizeName);
    const pendingRemove = findPendingChange('remove_size', sizeName);
    const currentlyIncluded = isSizeIncluded(sizeName);

    if (shouldInclude) {
      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
        return;
      }
      if (pendingAdd || currentlyIncluded) return;
      createChangeMutation.mutate({
        billing_id,
        change_type: 'add_size',
        field_name: 'included_sizes',
        value: sizeName,
        reason: 'Allowed from Home size breakdown',
      });
      return;
    }

    if (pendingAdd) {
      cancelChangeMutation.mutate(pendingAdd.id);
      return;
    }
    if (pendingRemove || !currentlyIncluded) return;
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_size',
      field_name: 'included_sizes',
      value: sizeName,
      reason: 'Blocked from Home size breakdown',
    });
  };

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

  const selectAllVisibleSizes = () => {
    setSelectedSizes((prev) => {
      const next = new Set(prev);
      visibleSizeRows.forEach((row) => next.add(row.name));
      return next;
    });
  };

  const invertVisibleSizeSelection = () => {
    setSelectedSizes((prev) => {
      const next = new Set(prev);
      visibleSizeRows.forEach((row) => {
        if (next.has(row.name)) {
          next.delete(row.name);
        } else {
          next.add(row.name);
        }
      });
      return next;
    });
  };

  const clearSelectedSizes = () => {
    setSelectedSizes(new Set());
  };

  const applySelectionState = (shouldInclude: boolean) => {
    selectedSizes.forEach((sizeName) => setSizeInclusionState(sizeName, shouldInclude));
  };

  const setFormatEnabledState = (format: string, shouldEnable: boolean) => {
    const pendingAdd = findPendingChange('add_format', format);
    const pendingRemove = findPendingChange('remove_format', format);
    const currentlyEnabled = isFormatEnabled(format);

    if (shouldEnable) {
      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
        return;
      }
      if (pendingAdd || currentlyEnabled) return;
      createChangeMutation.mutate({
        billing_id,
        change_type: 'add_format',
        field_name: 'included_formats',
        value: format,
        reason: 'Enabled from Home breakdown',
      });
      return;
    }

    if (pendingAdd) {
      cancelChangeMutation.mutate(pendingAdd.id);
      return;
    }
    if (pendingRemove || !currentlyEnabled) return;
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_format',
      field_name: 'included_formats',
      value: format,
      reason: 'Disabled from Home breakdown',
    });
  };

  const setPublisherBlockedState = (publisherValue: string, shouldBlock: boolean) => {
    const pendingAdd = findPendingChange('add_publisher', publisherValue);
    const pendingRemove = findPendingChange('remove_publisher', publisherValue);
    const currentlyListed = isPublisherListed(publisherValue);
    const isInclusiveMode = effectivePublisherMode === 'INCLUSIVE';

    if (isInclusiveMode) {
      // INCLUSIVE (whitelist): listed = allowed, not listed = blocked.
      if (shouldBlock) {
        if (pendingAdd) {
          cancelChangeMutation.mutate(pendingAdd.id);
          return;
        }
        if (!currentlyListed || pendingRemove) return;
        createChangeMutation.mutate({
          billing_id,
          change_type: 'remove_publisher',
          field_name: 'publisher_targeting',
          value: publisherValue,
          reason: 'Blocked from Home publisher breakdown',
        });
        return;
      }

      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
        return;
      }
      if (currentlyListed || pendingAdd) return;
      createChangeMutation.mutate({
        billing_id,
        change_type: 'add_publisher',
        field_name: 'publisher_targeting',
        value: publisherValue,
        reason: 'Allowed from Home publisher breakdown',
      });
      return;
    }

    // EXCLUSIVE (blacklist): listed = blocked, not listed = unblocked.
    if (shouldBlock) {
      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
        return;
      }
      if (currentlyListed || pendingAdd) return;
      createChangeMutation.mutate({
        billing_id,
        change_type: 'add_publisher',
        field_name: 'publisher_targeting',
        value: publisherValue,
        reason: 'Blocked from Home publisher breakdown',
      });
      return;
    }

    if (pendingAdd) {
      cancelChangeMutation.mutate(pendingAdd.id);
      return;
    }
    if (!currentlyListed || pendingRemove) return;
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_publisher',
      field_name: 'publisher_targeting',
      value: publisherValue,
      reason: 'Unblocked from Home publisher breakdown',
    });
  };

  const applyQpsChange = () => {
    if (!configDetail) return;

    const normalized = qpsInput.trim();
    if (!normalized) {
      pendingQpsChanges.forEach((change) => cancelChangeMutation.mutate(change.id));
      return;
    }

    const parsed = Number.parseInt(normalized, 10);
    if (!Number.isFinite(parsed) || parsed < 0) return;

    const desired = String(parsed);
    pendingQpsChanges
      .filter((change) => change.value !== desired)
      .forEach((change) => cancelChangeMutation.mutate(change.id));

    if (persistedQpsLimit === parsed) {
      pendingQpsChanges
        .filter((change) => change.value === desired)
        .forEach((change) => cancelChangeMutation.mutate(change.id));
      return;
    }

    if (latestPendingQpsChange?.value === desired) return;

    createChangeMutation.mutate({
      billing_id,
      change_type: 'set_maximum_qps',
      field_name: 'maximum_qps',
      value: desired,
      reason: 'Updated from Home QPS control',
    });
  };

  const addGeoFromSearch = () => {
    if (!selectedGeoId) return;
    const pendingAdd = findPendingChange('add_geo', selectedGeoId);
    const pendingRemove = findPendingChange('remove_geo', selectedGeoId);
    const currentlyIncluded = effectiveIncludedGeos.has(selectedGeoId);

    if (pendingRemove) {
      cancelChangeMutation.mutate(pendingRemove.id);
      return;
    }
    if (pendingAdd || currentlyIncluded) return;

    createChangeMutation.mutate({
      billing_id,
      change_type: 'add_geo',
      field_name: 'included_geos',
      value: selectedGeoId,
      reason: 'Added from By Geo search dropdown',
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
                  Publisher mode is currently <span className="font-semibold">{effectivePublisherMode === 'INCLUSIVE' ? 'Whitelist' : 'Blacklist'}</span>.
                  Use Block/Unblock to stage pending publisher targeting updates.
                </span>
              </div>
            )}
            {activeTab === 'size' && (
              <div className="mb-3 space-y-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <div className="flex items-center justify-between gap-2">
                  <span>
                    <span className="font-semibold">Status</span> shows if a size is currently targeted:
                    {' '}<span className="font-semibold">Allowed</span> or <span className="font-semibold">Blocked</span>.
                  </span>
                  <div className="flex items-center gap-2">
                    {hiddenLowVolumeSizeCount > 0 && (
                      <button
                        onClick={() => setShowLowVolumeSizes((prev) => !prev)}
                        className="rounded border border-blue-300 bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100"
                      >
                        {showLowVolumeSizes
                          ? 'Show only >=1k imp'
                          : `Show low-volume (${hiddenLowVolumeSizeCount})`}
                      </button>
                    )}
                    {pendingSizeChanges.length > 0 && (
                      <span className="font-medium">
                        {pendingSizeChanges.length} pending
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={selectAllVisibleSizes}
                    disabled={changeActionBusy || visibleSizeRows.length === 0}
                    className="rounded border border-blue-300 bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                  >
                    Select all
                  </button>
                  <button
                    onClick={invertVisibleSizeSelection}
                    disabled={changeActionBusy || visibleSizeRows.length === 0}
                    className="rounded border border-blue-300 bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                  >
                    Invert
                  </button>
                  <button
                    onClick={clearSelectedSizes}
                    disabled={changeActionBusy || selectedSizes.size === 0}
                    className="rounded border border-blue-300 bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                  >
                    Clear ({selectedSizes.size})
                  </button>
                  <button
                    onClick={() => applySelectionState(false)}
                    disabled={changeActionBusy || selectedSizes.size === 0}
                    className="rounded border border-red-300 bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                  >
                    Block selected
                  </button>
                  <button
                    onClick={() => applySelectionState(true)}
                    disabled={changeActionBusy || selectedSizes.size === 0}
                    className="rounded border border-green-300 bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700 hover:bg-green-100 disabled:opacity-50"
                  >
                    Allow selected
                  </button>
                </div>
              </div>
            )}
            {activeTab === 'geo' && (
              <div className="mb-3 space-y-2 p-2 bg-teal-50 border border-teal-200 rounded text-xs text-teal-800">
                <div className="flex items-center gap-2">
                  <Search className="h-3.5 w-3.5 text-teal-600" />
                  <span className="font-medium">Add Country / City</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    value={geoSearchQuery}
                    onChange={(event) => setGeoSearchQuery(event.target.value)}
                    placeholder="Search country, city, or geo ID"
                    className="w-56 rounded border border-teal-300 bg-white px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-teal-300"
                  />
                  <select
                    value={geoSearchType}
                    onChange={(event) => setGeoSearchType(event.target.value as 'all' | 'country' | 'city')}
                    className="rounded border border-teal-300 bg-white px-2 py-1 text-xs text-gray-700"
                  >
                    <option value="all">All</option>
                    <option value="country">Country</option>
                    <option value="city">City</option>
                  </select>
                  <select
                    value={selectedGeoId}
                    onChange={(event) => setSelectedGeoId(event.target.value)}
                    className="min-w-[16rem] rounded border border-teal-300 bg-white px-2 py-1 text-xs text-gray-700"
                    disabled={isGeoSearchLoading || geoSearchResults.length === 0}
                  >
                    {isGeoSearchLoading && <option value="">Searching…</option>}
                    {!isGeoSearchLoading && geoSearchResults.length === 0 && (
                      <option value="">Type at least 2 characters</option>
                    )}
                    {!isGeoSearchLoading && geoSearchResults.map((result) => (
                      <option key={result.geo_id} value={result.geo_id}>
                        {result.label} ({result.geo_id})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={addGeoFromSearch}
                    disabled={changeActionBusy || !selectedGeoId}
                    className="rounded border border-teal-300 bg-teal-100 px-2 py-1 text-[11px] font-medium text-teal-800 hover:bg-teal-200 disabled:opacity-50"
                  >
                    Add Geo
                  </button>
                </div>
              </div>
            )}
            {activeTab !== 'creative' && (
              <div className="mb-3 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">QPS limit</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={qpsInput}
                    onChange={(event) => setQpsInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        applyQpsChange();
                      }
                    }}
                    className="w-28 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    placeholder={effectiveQpsLimit === null || effectiveQpsLimit === undefined ? 'unset' : String(effectiveQpsLimit)}
                  />
                  <button
                    onClick={applyQpsChange}
                    disabled={changeActionBusy}
                    className="rounded border border-blue-300 bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                  >
                    Set QPS
                  </button>
                  {latestPendingQpsChange && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] text-amber-800">
                      Pending: {latestPendingQpsChange.value}
                    </span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  {[
                    { label: 'Banner', value: 'HTML' },
                    { label: 'Audio and Video', value: 'VIDEO' },
                    { label: 'Native', value: 'NATIVE' },
                  ].map((formatOption) => (
                    <label key={formatOption.value} className="inline-flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={isFormatEnabled(formatOption.value)}
                        disabled={changeActionBusy}
                        onChange={(event) => setFormatEnabledState(formatOption.value, event.target.checked)}
                        className="h-3.5 w-3.5 rounded border-gray-300"
                      />
                      <span>{formatOption.label}</span>
                    </label>
                  ))}
                </div>
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
                  ? "grid-cols-[repeat(15,minmax(0,1fr))]"
                  : activeTab === "publisher"
                  ? "grid-cols-[repeat(14,minmax(0,1fr))]"
                  : "grid-cols-12"
              )}
            >
              {activeTab === "size" && (
                <div className="col-span-1 flex justify-center">
                  <input
                    ref={selectAllSizesRef}
                    type="checkbox"
                    checked={allVisibleSizesSelected}
                    onChange={(event) => {
                      if (event.target.checked) {
                        selectAllVisibleSizes();
                      } else {
                        setSelectedSizes((prev) => {
                          const next = new Set(prev);
                          visibleSizeRows.forEach((row) => next.delete(row.name));
                          return next;
                        });
                      }
                    }}
                    disabled={changeActionBusy || visibleSizeRows.length === 0}
                    className="h-3.5 w-3.5 rounded border-gray-300"
                    title="Select visible sizes"
                  />
                </div>
              )}
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
                <>
                  <div className="col-span-1 text-right">Status</div>
                  <div className="col-span-1 text-right">Action</div>
                </>
              )}
              {activeTab === "publisher" && (
                <>
                  <div className="col-span-1 text-right">Status</div>
                  <div className="col-span-1 text-right">Action</div>
                </>
              )}
            </div>

            {/* Table body */}
	            <div className="divide-y divide-gray-100">
	              {(activeTab === 'size' ? visibleSizeRows : sortedBreakdown).map((item, index) => {
	                const isClickable = false;
	                const winRate = item.win_rate ?? 0;
	                const winRateClass =
	                  winRate < 51 ? 'text-red-600' : winRate < 75 ? 'text-orange-600' : 'text-green-600';
	                const nameColSpan = 'col-span-4';
	                const pendingAdd = activeTab === 'size' ? findPendingChange('add_size', item.name) : undefined;
	                const pendingRemove = activeTab === 'size' ? findPendingChange('remove_size', item.name) : undefined;
	                const hasPendingToggle = Boolean(pendingAdd || pendingRemove);
	                const includedInConfig = activeTab === 'size' ? isSizeIncluded(item.name) : false;
	                const selectedForBulk = activeTab === 'size' ? selectedSizes.has(item.name) : false;
	                const sizeStatus = hasPendingToggle
	                  ? (pendingAdd ? 'Pending allow' : 'Pending block')
	                  : (includedInConfig ? 'Allowed' : 'Blocked');
	                const publisherTargetValue = activeTab === 'publisher'
	                  ? (item.target_value || item.name)
	                  : '';
	                const pendingPublisherAdd = activeTab === 'publisher'
	                  ? findPendingChange('add_publisher', publisherTargetValue)
	                  : undefined;
	                const pendingPublisherRemove = activeTab === 'publisher'
	                  ? findPendingChange('remove_publisher', publisherTargetValue)
	                  : undefined;
	                const publisherBlocked = activeTab === 'publisher'
	                  ? isPublisherBlocked(publisherTargetValue)
	                  : false;
	                const publisherStatus = activeTab !== 'publisher'
	                  ? ''
	                  : pendingPublisherAdd
	                  ? (effectivePublisherMode === 'INCLUSIVE' ? 'Pending unblock' : 'Pending block')
	                  : pendingPublisherRemove
	                  ? (effectivePublisherMode === 'INCLUSIVE' ? 'Pending block' : 'Pending unblock')
	                  : publisherBlocked
	                  ? 'Blocked'
	                  : 'Unblocked';
	                return (
	                  <div key={`${item.name}-${index}`}>
	                    <div
	                      onClick={() => isClickable && setSelectedApp(item.name)}
	                      className={cn(
	                        'grid gap-2 px-3 py-2 text-sm items-center',
	                        activeTab === 'creative'
	                          ? 'grid-cols-[repeat(14,minmax(0,1fr))]'
	                          : activeTab === 'size'
	                          ? 'grid-cols-[repeat(15,minmax(0,1fr))]'
	                          : activeTab === 'publisher'
	                          ? 'grid-cols-[repeat(14,minmax(0,1fr))]'
	                          : 'grid-cols-12',
	                        'hover:bg-gray-50 transition-colors',
	                        isClickable && 'cursor-pointer hover:bg-blue-50',
	                        activeTab === 'size' && hasPendingToggle && 'bg-amber-50',
	                        activeTab === 'size' && selectedForBulk && 'ring-1 ring-blue-200',
	                        activeTab === 'publisher' && (pendingPublisherAdd || pendingPublisherRemove) && 'bg-amber-50'
	                      )}
	                    >
                      {activeTab === 'size' && (
                        <div className="col-span-1 flex justify-center">
                          <input
                            type="checkbox"
                            checked={selectedForBulk}
                            onChange={() => toggleSizeSelection(item.name)}
                            disabled={changeActionBusy}
                            className="h-3.5 w-3.5 rounded border-gray-300"
                            title={`Select ${item.name}`}
                          />
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
	                        {activeTab === 'publisher' && item.target_value && item.target_value !== item.name ? (
	                          <div className="min-w-0">
	                            <div className="truncate">{item.name}</div>
	                            <div className="truncate text-[10px] font-mono text-gray-500">{item.target_value}</div>
	                          </div>
	                        ) : (
	                          <span className="truncate">{item.name}</span>
	                        )}
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
	                        <>
                          <div className="col-span-1 text-right text-xs">
                            <span
                              className={cn(
                                'rounded px-1.5 py-0.5 font-medium',
                                sizeStatus === 'Allowed' && 'bg-green-50 text-green-700',
                                sizeStatus === 'Blocked' && 'bg-gray-100 text-gray-700',
                                sizeStatus === 'Pending allow' && 'bg-amber-100 text-amber-800',
                                sizeStatus === 'Pending block' && 'bg-amber-100 text-amber-800'
                              )}
                            >
                              {sizeStatus}
                            </span>
                          </div>
                          <div className="col-span-1 flex justify-end">
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              toggleSizeBlockState(item.name);
                            }}
                            disabled={changeActionBusy}
                            className={cn(
                              'inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-50',
                              includedInConfig
                                ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                                : 'border-green-200 bg-green-50 text-green-700 hover:bg-green-100'
                            )}
                            title={includedInConfig ? 'Block size (remove from targeting)' : 'Allow size (add to targeting)'}
                          >
                            {includedInConfig ? <X className="h-3 w-3" /> : <Check className="h-3 w-3" />}
                            {includedInConfig ? 'Block' : 'Allow'}
                          </button>
                        </div>
	                        </>
	                      )}
	                      {activeTab === 'publisher' && (
	                        <>
	                          <div className="col-span-1 text-right text-xs">
	                            <span
	                              className={cn(
	                                'rounded px-1.5 py-0.5 font-medium',
	                                publisherStatus === 'Blocked' && 'bg-red-50 text-red-700',
	                                publisherStatus === 'Unblocked' && 'bg-green-50 text-green-700',
	                                publisherStatus.startsWith('Pending') && 'bg-amber-100 text-amber-800'
	                              )}
	                            >
	                              {publisherStatus}
	                            </span>
	                          </div>
	                          <div className="col-span-1 flex justify-end">
	                            <button
	                              onClick={(event) => {
	                                event.stopPropagation();
	                                setPublisherBlockedState(publisherTargetValue, !publisherBlocked);
	                              }}
	                              disabled={changeActionBusy || !publisherTargetValue}
	                              className={cn(
	                                'inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-50',
	                                publisherBlocked
	                                  ? 'border-green-200 bg-green-50 text-green-700 hover:bg-green-100'
	                                  : 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
	                              )}
	                              title={publisherBlocked ? 'Unblock publisher' : 'Block publisher'}
	                            >
	                              {publisherBlocked ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
	                              {publisherBlocked ? 'Unblock' : 'Block'}
	                            </button>
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
              {activeTab === 'size' && visibleSizeRows.length === 0 && sortedBreakdown.length > 0 && (
                <div className="px-3 py-4 text-sm text-gray-500">
                  No sizes meet the default threshold of <span className="font-medium">1,000 impressions</span>.
                  {hiddenLowVolumeSizeCount > 0 && (
                    <button
                      onClick={() => setShowLowVolumeSizes(true)}
                      className="ml-2 text-blue-600 hover:text-blue-800"
                    >
                      Show all sizes
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
          {activeTab !== 'creative' && hasPendingChanges && (
            <div className="sticky bottom-3 mt-3 flex justify-end">
              <div className="w-full max-w-md rounded-lg border border-yellow-300 bg-yellow-50 p-3 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-medium text-yellow-900">
                  <Clock className="h-4 w-4" />
                  Pending Changes ({pendingChanges.length})
                </div>
                <div className="mt-2 max-h-24 overflow-y-auto space-y-1 text-xs text-yellow-800">
                  {pendingChanges.map((change) => (
                    <div key={change.id} className="flex items-center justify-between gap-2">
                      <span className="truncate">{describePendingChange(change, effectivePublisherMode)}</span>
                      <button
                        onClick={() => cancelChangeMutation.mutate(change.id)}
                        disabled={changeActionBusy}
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
                    onClick={() => pendingChanges.forEach((change) => cancelChangeMutation.mutate(change.id))}
                    disabled={changeActionBusy}
                    className="text-xs text-yellow-700 hover:text-yellow-900 disabled:opacity-50"
                  >
                    Discard All
                  </button>
                  <button
                    onClick={() => setShowConfirmPush(true)}
                    disabled={changeActionBusy}
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
                You are about to commit {pendingChanges.length} pending change{pendingChanges.length !== 1 ? 's' : ''} for billing ID {billing_id}.
              </p>
              <div className="mt-3 max-h-40 overflow-y-auto space-y-1 rounded border bg-gray-50 p-2 text-xs">
                {pendingChanges.map((change) => (
                  <div key={`confirm-${change.id}`}>
                    • {describePendingChange(change, effectivePublisherMode)}
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
