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
  getPretargetingHistory,
  getSnapshots,
  rollbackSnapshot,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
  type GeoSearchResult,
  type PendingChange,
  type PretargetingHistoryItem,
  type PretargetingSnapshot,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { isValidPublisherId } from '@/lib/publisher-validation';
import { COMMONLY_BLOCKED, type BlockSuggestion } from '@/lib/commonly-blocked-publishers';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, ChevronDown, Info, Image, X, Check, Clock, Upload, Search, ExternalLink, Ban, ShieldAlert, RotateCcw, History } from 'lucide-react';
import { AppDrilldownModal } from './app-drilldown-modal';
import { useAccount } from '@/contexts/account-context';
import { useTranslation } from '@/contexts/i18n-context';
import { PreviewModal } from '@/components/preview-modal';
import type { Creative } from '@/types/api';

interface ConfigBreakdownPanelProps {
  billing_id: string;
  days: number;
  isExpanded: boolean;
}

const TABS: ConfigBreakdownType[] = ['creative', 'size', 'geo', 'publisher'];

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
  const { t } = useTranslation();
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
  const [fullCreative, setFullCreative] = useState<Creative | null>(null);
  const [expandedCountries, setExpandedCountries] = useState<Set<string>>(new Set());
  const [showConfirmPush, setShowConfirmPush] = useState(false);
  const [pushResult, setPushResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showLowVolumeSizes, setShowLowVolumeSizes] = useState(false);
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [publisherBlockInput, setPublisherBlockInput] = useState('');
  const [publisherBlockError, setPublisherBlockError] = useState<string | null>(null);
  const [publisherFilter, setPublisherFilter] = useState('');
  const [showBlockSuggestions, setShowBlockSuggestions] = useState(false);
  const [showPublisherHistory, setShowPublisherHistory] = useState(false);
  const [undoPushSnapshot, setUndoPushSnapshot] = useState<PretargetingSnapshot | null>(null);
  const [undoDryRunResult, setUndoDryRunResult] = useState<{ changes_made: string[]; message: string } | null>(null);
  const [undoDryRunLoading, setUndoDryRunLoading] = useState(false);
  const [undoDryRunError, setUndoDryRunError] = useState<string | null>(null);
  const [undoReason, setUndoReason] = useState('');
  const [geoSearchQuery, setGeoSearchQuery] = useState('');
  const [geoSearchType, setGeoSearchType] = useState<'all' | 'country' | 'city'>('all');
  const [geoSearchResults, setGeoSearchResults] = useState<GeoSearchResult[]>([]);
  const [selectedGeoId, setSelectedGeoId] = useState('');
  const [isGeoSearchLoading, setIsGeoSearchLoading] = useState(false);
  const selectAllSizesRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const getTabLabel = (tab: ConfigBreakdownType): string => {
    switch (tab) {
      case 'creative':
        return t.pretargeting.tabByCreative;
      case 'size':
        return t.pretargeting.tabBySize;
      case 'geo':
        return t.pretargeting.tabByGeo;
      case 'publisher':
        return t.pretargeting.tabByPublisher;
      default:
        return tab;
    }
  };

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
    setPublisherBlockInput('');
    setPublisherBlockError(null);
    setPublisherFilter('');
    setShowBlockSuggestions(false);
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
  const isSizeIncluded = (sizeName: string): boolean => effectiveIncludedSizes.has(sizeName);
  const isFormatEnabled = (format: string): boolean => effectiveFormats.has(format);
  const isPublisherListed = (publisherValue: string): boolean => effectivePublisherValues.has(publisherValue);
  const isPublisherBlocked = (publisherValue: string): boolean => {
    if (effectivePublisherMode === 'INCLUSIVE') {
      return !isPublisherListed(publisherValue);
    }
    return isPublisherListed(publisherValue);
  };
  const publisherModeLabel = effectivePublisherMode === 'INCLUSIVE' ? 'Whitelist' : 'Blacklist';
  const publisherActionLabel = (publisherBlocked: boolean): string => {
    if (effectivePublisherMode === 'INCLUSIVE') {
      return publisherBlocked ? 'Allow' : 'Block';
    }
    return publisherBlocked ? 'Unblock' : 'Block';
  };
  const publisherActionTitle = (publisherBlocked: boolean): string => {
    if (effectivePublisherMode === 'INCLUSIVE') {
      return publisherBlocked
        ? 'Allow publisher (add to allowlist)'
        : 'Block publisher (remove from allowlist)';
    }
    return publisherBlocked
      ? 'Unblock publisher (remove from denylist)'
      : 'Block publisher (add to denylist)';
  };

  const filteredPublisherBreakdown = activeTab === 'publisher' && publisherFilter
    ? sortedBreakdown.filter((item) => {
        const q = publisherFilter.toLowerCase();
        return item.name.toLowerCase().includes(q) ||
          (item.target_value || '').toLowerCase().includes(q);
      })
    : sortedBreakdown;
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

  const handleBlockPublisher = () => {
    const value = publisherBlockInput.trim().toLowerCase();
    if (!value) return;
    if (!isValidPublisherId(value)) {
      setPublisherBlockError('Invalid ID. Use com.example.app or publisher.com');
      return;
    }
    // Check already blocked / already pending
    const alreadyListed = effectivePublisherValues.has(value);
    const pendingAdd = findPendingChange('add_publisher', value);
    const pendingRemove = findPendingChange('remove_publisher', value);
    if (effectivePublisherMode === 'EXCLUSIVE') {
      // Blacklist: "block" means add to list
      if (alreadyListed && !pendingRemove) {
        setPublisherBlockError('Already in block list for this config');
        return;
      }
      if (pendingAdd) {
        setPublisherBlockError('Already in pending changes');
        return;
      }
      if (pendingRemove) {
        // Undo the pending unblock instead
        cancelChangeMutation.mutate(pendingRemove.id);
      } else {
        createChangeMutation.mutate({
          billing_id,
          change_type: 'add_publisher',
          field_name: 'publisher_targeting',
          value,
          reason: 'Blocked from Home publisher breakdown',
        });
      }
    } else {
      // Whitelist (INCLUSIVE): "block" means remove from list
      if (!alreadyListed && !pendingAdd) {
        setPublisherBlockError('Not in allow list — already blocked');
        return;
      }
      if (pendingRemove) {
        setPublisherBlockError('Already in pending changes');
        return;
      }
      if (pendingAdd) {
        cancelChangeMutation.mutate(pendingAdd.id);
      } else {
        createChangeMutation.mutate({
          billing_id,
          change_type: 'remove_publisher',
          field_name: 'publisher_targeting',
          value,
          reason: 'Blocked from Home publisher breakdown',
        });
      }
    }
    setPublisherBlockInput('');
    setPublisherBlockError(null);
  };

  /** Determine status of each block suggestion relative to current config. */
  const getSuggestionStatus = (s: BlockSuggestion): 'available' | 'pending' | 'blocked' => {
    const pid = s.publisher_id;
    if (effectivePublisherMode === 'EXCLUSIVE') {
      // Blacklist: listed = blocked
      if (findPendingChange('add_publisher', pid)) return 'pending';
      if (effectivePublisherValues.has(pid)) return 'blocked';
    } else {
      // Whitelist: not listed = blocked; pending remove = pending block
      if (findPendingChange('remove_publisher', pid)) return 'pending';
      if (!effectivePublisherValues.has(pid)) return 'blocked';
    }
    return 'available';
  };

  const availableSuggestions = COMMONLY_BLOCKED.filter(
    (s) => getSuggestionStatus(s) === 'available'
  );

  /** Block a single suggestion, canceling any opposite pending change first. */
  const blockOneSuggestion = (s: BlockSuggestion) => {
    const pid = s.publisher_id;
    if (effectivePublisherMode === 'EXCLUSIVE') {
      const pendingRemove = findPendingChange('remove_publisher', pid);
      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
      } else {
        createChangeMutation.mutate({
          billing_id,
          change_type: 'add_publisher',
          field_name: 'publisher_targeting',
          value: pid,
          reason: `Blocked from commonly blocked suggestions (${s.category})`,
        });
      }
    } else {
      const pendingAdd = findPendingChange('add_publisher', pid);
      if (pendingAdd) {
        cancelChangeMutation.mutate(pendingAdd.id);
      } else if (effectivePublisherValues.has(pid)) {
        createChangeMutation.mutate({
          billing_id,
          change_type: 'remove_publisher',
          field_name: 'publisher_targeting',
          value: pid,
          reason: `Blocked from commonly blocked suggestions (${s.category})`,
        });
      }
    }
  };

  const handleBlockAllSuggestions = () => {
    availableSuggestions.forEach(blockOneSuggestion);
  };

  const handleBlockSuggestion = (s: BlockSuggestion) => {
    blockOneSuggestion(s);
  };

  // ── Publisher history & rollback ───────────────────────────────
  const { data: publisherHistory } = useQuery({
    queryKey: ['pretargeting-history', billing_id, 30],
    queryFn: () => getPretargetingHistory({ billing_id, days: 30 }),
    enabled: isExpanded && activeTab === 'publisher',
  });

  const { data: historySnapshots } = useQuery({
    queryKey: ['pretargeting-snapshots', billing_id],
    queryFn: () => getSnapshots({ billing_id }),
    enabled: isExpanded && activeTab === 'publisher' && showPublisherHistory,
  });

  /** Group history entries by push event (same minute + same source). */
  const groupedHistory = (() => {
    if (!publisherHistory) return [];
    // Filter to publisher-related + syncs + rollbacks
    const relevant = publisherHistory.filter(
      (e) =>
        e.field_changed === 'publisher_targeting' ||
        e.change_type === 'rollback' ||
        e.change_type === 'api_sync' ||
        e.change_type === 'state_change'
    );
    const groups: {
      key: string;
      timestamp: string;
      changeType: string;
      entries: PretargetingHistoryItem[];
      snapshot: PretargetingSnapshot | null;
    }[] = [];
    for (const entry of relevant) {
      const minute = entry.changed_at.slice(0, 16); // YYYY-MM-DDTHH:MM
      const groupKey = `${minute}__${entry.change_type}`;
      const existing = groups.find((g) => g.key === groupKey);
      if (existing) {
        existing.entries.push(entry);
      } else {
        groups.push({
          key: groupKey,
          timestamp: entry.changed_at,
          changeType: entry.change_type,
          entries: [entry],
          snapshot: null,
        });
      }
    }
    // Associate snapshots with push groups
    if (historySnapshots) {
      for (const group of groups) {
        if (group.changeType === 'api_write') {
          const pushTime = new Date(group.timestamp).getTime();
          group.snapshot =
            historySnapshots.find((snap) => {
              const snapTime = new Date(snap.created_at).getTime();
              const diff = pushTime - snapTime;
              return diff >= 0 && diff < 30_000 && snap.snapshot_type === 'before_change';
            }) || null;
        }
      }
    }
    return groups;
  })();

  /** Last push timestamp for the "last pushed" indicator. */
  const lastPushEntry = publisherHistory?.find(
    (e) => e.change_type === 'api_write' && e.field_changed === 'publisher_targeting'
  );

  const handleUndoPush = (snapshot: PretargetingSnapshot) => {
    setUndoPushSnapshot(snapshot);
    setUndoReason('');
    setUndoDryRunResult(null);
    setUndoDryRunError(null);
    setUndoDryRunLoading(true);
    rollbackSnapshot({ billing_id, snapshot_id: snapshot.id, dry_run: true })
      .then((result) => setUndoDryRunResult(result))
      .catch((err) => setUndoDryRunError(err?.message || 'Failed to preview rollback'))
      .finally(() => setUndoDryRunLoading(false));
  };

  const undoExecuteMutation = useMutation({
    mutationFn: async () => {
      if (!undoPushSnapshot) throw new Error('No snapshot');
      return rollbackSnapshot({ billing_id, snapshot_id: undoPushSnapshot.id, dry_run: false });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-snapshots'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown'] });
      queryClient.invalidateQueries({ queryKey: ['config-detail'] });
      setUndoPushSnapshot(null);
      setPushResult({ success: true, message: 'Push undone. Config restored to pre-push state.' });
    },
  });

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
      <div ref={contentRef} className="border-t bg-gray-50/50 px-4 py-2">
        {/* Tabs */}
        <div className="flex gap-1 mb-2">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                activeTab === tab
                  ? 'bg-white text-gray-900 shadow-sm border'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
              )}
            >
              {getTabLabel(tab)}
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            <span className="text-sm">{t.pretargeting.loadingBreakdown}</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
            {t.pretargeting.failedToLoadBreakdownData}
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm">
            {activeTab === 'publisher' ? (
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-700">
                    {t.pretargeting.noPublisherBreakdownForConfig}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    {data?.no_data_reason || t.pretargeting.publisherBreakdownMissingCsvOrPrecompute}
                  </p>
                  <a
                    href="/import"
                    className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-blue-600 hover:text-blue-800"
                  >
                    <Upload className="h-3 w-3" />
                    {t.import.goToImport}
                  </a>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-700">
                    {t.pretargeting.noTabDataForConfig.replace('{tab}', activeTab)}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    {data?.no_data_reason || (
                      activeTab === 'geo'
                        ? t.pretargeting.noGeoBreakdownAvailable
                        : activeTab === 'size'
                        ? t.pretargeting.noSizeBreakdownAvailable
                        : activeTab === 'creative'
                        ? t.pretargeting.noCreativeBreakdownAvailable
                        : t.pretargeting.importQualityAndBidsCsvForBreakdown.replace('{tab}', activeTab)
                    )}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length > 0 && (
          <>
            <div className="mb-3 flex items-center gap-2">
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">
                {t.pretargeting.windowLabel}: {data?.requested_days ?? days}d
                {data?.fallback_applied && data?.effective_days != null && (
                  <> ({t.pretargeting.effectiveLabel}: {data.effective_days}d)</>
                )}
              </span>
              {data?.fallback_applied && (
                <span className="flex items-center gap-1 rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[11px] text-amber-700">
                  <AlertTriangle className="h-3 w-3 text-amber-500" />
                  {t.pretargeting.fallbackAppliedNoDataRequestedWindow}
                </span>
              )}
            </div>
            {activeTab === 'publisher' && (
              <div className="mb-2 space-y-1.5">
                <div className="flex items-center gap-2 px-2 py-1.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                  <Info className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
                  <span className="flex-1">
                    {t.pretargeting.modeLabel}: <span className="font-semibold">{publisherModeLabel}</span>.
                    {effectivePublisherMode === 'INCLUSIVE'
                      ? ` ${t.pretargeting.publisherModeInclusiveHelp}`
                      : ` ${t.pretargeting.publisherModeExclusiveHelp}`}
                  </span>
                  <button
                    onClick={() => setShowPublisherHistory(!showPublisherHistory)}
                    className={cn(
                      'inline-flex items-center gap-1 font-medium whitespace-nowrap',
                      showPublisherHistory
                        ? 'text-blue-700 hover:text-blue-900'
                        : 'text-amber-800 hover:text-amber-900'
                    )}
                  >
                    <History className="h-3 w-3" />
                    {t.pretargeting.historyShort}
                  </button>
                  <a
                    href={`/bill_id/${encodeURIComponent(billing_id)}?tab=publishers`}
                    className="inline-flex items-center gap-1 text-amber-800 hover:text-amber-900 font-medium whitespace-nowrap"
                  >
                    {t.pretargeting.fullEditor}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <div className="flex items-center gap-2 px-2">
                  <Search className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                  <input
                    type="text"
                    value={publisherFilter}
                    onChange={(e) => setPublisherFilter(e.target.value)}
                    placeholder={t.pretargeting.filterPublishersPlaceholder}
                    className="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-300"
                  />
                  {publisherFilter && (
                    <button
                      onClick={() => setPublisherFilter('')}
                      className="text-gray-400 hover:text-gray-600"
                      title={t.campaigns.clearFilter}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
                {/* Last pushed indicator */}
                {lastPushEntry && (
                  <div className="px-2 text-[10px] text-gray-500">
                    {t.pretargeting.lastPushed}{' '}
                    {new Date(lastPushEntry.changed_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ── Inline Publisher History Panel ── */}
            {activeTab === 'publisher' && showPublisherHistory && (
              <div className="mb-2 rounded-lg border border-blue-200 bg-blue-50/50">
                <div className="flex items-center justify-between px-3 py-2 border-b border-blue-200">
                  <span className="flex items-center gap-1.5 text-xs font-medium text-blue-900">
                    <History className="h-3.5 w-3.5" />
                    {t.pretargeting.publisherHistory}
                  </span>
                  <div className="flex items-center gap-2">
                    <a
                      href={`/history?billing_id=${encodeURIComponent(billing_id)}`}
                      className="text-[10px] text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {t.pretargeting.viewAllArrow}
                    </a>
                    <button
                      onClick={() => setShowPublisherHistory(false)}
                      className="text-blue-400 hover:text-blue-600"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                </div>
                <div className="px-3 py-2 max-h-64 overflow-y-auto space-y-2">
                  {!publisherHistory ? (
                    <div className="flex items-center justify-center py-4 gap-1.5 text-xs text-blue-500">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading history&hellip;
                    </div>
                  ) : groupedHistory.length === 0 ? (
                    <div className="py-4 text-center text-xs text-blue-600">
                      No publisher changes recorded for this config.
                      <br />
                      Changes will appear here after your first push.
                    </div>
                  ) : (
                    groupedHistory.map((group) => {
                      const isPush = group.changeType === 'api_write';
                      const isSync = group.changeType === 'api_sync';
                      const isRollback = group.changeType === 'rollback';
                      const isStateChange = group.changeType === 'state_change';
                      const publisherEntries = group.entries.filter(
                        (e) => e.field_changed === 'publisher_targeting'
                      );
                      const otherCount = group.entries.length - publisherEntries.length;
                      const ts = new Date(group.timestamp);
                      const dateStr = ts.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      });

                      return (
                        <div
                          key={group.key}
                          className={cn(
                            'rounded border p-2 text-xs',
                            isRollback && 'bg-orange-50 border-orange-200',
                            isPush && 'bg-white border-gray-200',
                            isSync && 'bg-gray-50 border-gray-200',
                            isStateChange && 'bg-gray-50 border-gray-200'
                          )}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-gray-500">{dateStr}</span>
                            <span
                              className={cn(
                                'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase',
                                isPush && 'bg-blue-100 text-blue-700',
                                isSync && 'bg-gray-200 text-gray-600',
                                isRollback && 'bg-orange-200 text-orange-700',
                                isStateChange && 'bg-gray-200 text-gray-600'
                              )}
                            >
                              {isPush ? 'PUSH' : isSync ? 'SYNC' : isRollback ? 'ROLLBACK' : 'STATE'}
                            </span>
                          </div>
                          {isPush && publisherEntries.length > 0 && (
                            <div className="space-y-0.5 mb-1.5">
                              {publisherEntries.map((e) => (
                                <div key={e.id} className="flex items-center gap-1.5 font-mono text-[11px]">
                                  <span
                                    className={cn(
                                      'rounded px-1 py-0.5 text-[9px] font-bold uppercase',
                                      e.change_type.includes('add')
                                        ? 'bg-red-100 text-red-700'
                                        : 'bg-green-100 text-green-700'
                                    )}
                                  >
                                    {e.change_type.includes('add') ? 'BLOCK' : 'UNBLOCK'}
                                  </span>
                                  <span className="text-gray-700 truncate">{e.new_value || e.old_value}</span>
                                </div>
                              ))}
                              {otherCount > 0 && (
                                <div className="text-[10px] text-gray-500 pl-1">
                                  + {otherCount} other change{otherCount > 1 ? 's' : ''} (view in Full History)
                                </div>
                              )}
                            </div>
                          )}
                          {isSync && (
                            <div className="text-gray-600 mb-1">
                              Config synced from Google. No rollback for syncs.
                            </div>
                          )}
                          {isRollback && (
                            <div className="space-y-0.5 mb-1.5">
                              {group.entries.map((e) => (
                                <div key={e.id} className="text-orange-700">
                                  {e.new_value || e.field_changed || 'Restored to snapshot'}
                                </div>
                              ))}
                              <div className="text-[10px] text-orange-600 italic mt-1">
                                Rollback entries cannot be undone from here.
                              </div>
                            </div>
                          )}
                          {isStateChange && (
                            <div className="text-gray-600 mb-1">
                              Config {group.entries[0]?.new_value || 'state changed'}
                            </div>
                          )}
                          {/* Snapshot info + Undo Push button */}
                          {isPush && group.snapshot && (
                            <div className="flex items-center justify-between pt-1.5 border-t border-gray-100">
                              <span className="text-[10px] text-gray-500 truncate">
                                Snapshot: {group.snapshot.snapshot_name || `#${group.snapshot.id}`}
                              </span>
                              <button
                                onClick={() => handleUndoPush(group.snapshot!)}
                                disabled={changeActionBusy}
                                className="inline-flex items-center gap-0.5 rounded border border-orange-200 bg-orange-50 px-1.5 py-0.5 text-[10px] font-medium text-orange-700 hover:bg-orange-100 disabled:opacity-50"
                              >
                                <RotateCcw className="h-3 w-3" />
                                Undo Push
                              </button>
                            </div>
                          )}
                          {isPush && !group.snapshot && (
                            <div className="pt-1.5 border-t border-gray-100">
                              <span className="text-[10px] text-gray-400">
                                No snapshot available (Undo unavailable)
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {activeTab === 'size' && (
              <div className="mb-2 space-y-1.5 px-2 py-1.5 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <div className="flex items-center justify-between gap-2">
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
                  <div className="flex items-center gap-2 shrink-0">
                    {hiddenLowVolumeSizeCount > 0 && (
                      <button
                        onClick={() => setShowLowVolumeSizes((prev) => !prev)}
                        className="rounded border border-blue-300 bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100"
                      >
                        {showLowVolumeSizes
                          ? '>=1k imp only'
                          : `+${hiddenLowVolumeSizeCount} low-vol`}
                      </button>
                    )}
                    {pendingSizeChanges.length > 0 && (
                      <span className="font-medium text-amber-700">
                        {pendingSizeChanges.length} pending
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'geo' && (
              <div className="mb-2 flex flex-wrap items-center gap-2 px-2 py-1.5 bg-teal-50 border border-teal-200 rounded text-xs text-teal-800">
                <Search className="h-3.5 w-3.5 text-teal-600 shrink-0" />
                <input
                  type="text"
                  value={geoSearchQuery}
                  onChange={(event) => setGeoSearchQuery(event.target.value)}
                  placeholder="Search geo..."
                  className="w-44 rounded border border-teal-300 bg-white px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-teal-300"
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
                  className="min-w-[14rem] rounded border border-teal-300 bg-white px-2 py-1 text-xs text-gray-700"
                  disabled={isGeoSearchLoading || geoSearchResults.length === 0}
                >
                  {isGeoSearchLoading && <option value="">Searching…</option>}
                  {!isGeoSearchLoading && geoSearchResults.length === 0 && (
                    <option value="">Type 2+ chars</option>
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
            )}
            {pushResult && (
              <div className={cn(
                "mb-3 rounded border px-3 py-2 text-xs flex items-center justify-between",
                pushResult.success
                  ? "bg-green-50 border-green-200 text-green-800"
                  : "bg-red-50 border-red-200 text-red-800"
              )}>
                <div>
                  <span className="font-medium">{pushResult.success ? 'Pushed to Google.' : 'Push failed.'}</span>
                  {' '}{pushResult.message}
                  {pushResult.success && (
                    <span className="block mt-0.5 text-green-600">Snapshot saved. Use History to undo if needed.</span>
                  )}
                </div>
                <button
                  onClick={() => setPushResult(null)}
                  className={cn(
                    "ml-2 flex-shrink-0",
                    pushResult.success ? "text-green-600 hover:text-green-800" : "text-red-600 hover:text-red-800"
                  )}
                  title="Dismiss"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
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
	              {(activeTab === 'size' ? visibleSizeRows : activeTab === 'publisher' ? filteredPublisherBreakdown : sortedBreakdown).map((item, index) => {
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
	                  ? (effectivePublisherMode === 'INCLUSIVE' ? 'Pending allow' : 'Pending block')
	                  : pendingPublisherRemove
	                  ? (effectivePublisherMode === 'INCLUSIVE' ? 'Pending block' : 'Pending unblock')
	                  : publisherBlocked
	                  ? 'Blocked'
	                  : 'Allowed';
                  const nextPublisherActionLabel =
                    activeTab === 'publisher' ? publisherActionLabel(publisherBlocked) : '';
                  const nextPublisherActionWillBlock = nextPublisherActionLabel === 'Block';
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
	                                publisherStatus === 'Allowed' && 'bg-green-50 text-green-700',
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
	                                nextPublisherActionWillBlock
	                                  ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
	                                  : 'border-green-200 bg-green-50 text-green-700 hover:bg-green-100'
	                              )}
	                              title={publisherActionTitle(publisherBlocked)}
	                            >
	                              {nextPublisherActionWillBlock ? <X className="h-3 w-3" /> : <Check className="h-3 w-3" />}
	                              {nextPublisherActionLabel}
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
          {/* Publisher block input */}
          {activeTab === 'publisher' && (
            <div className="mt-2 rounded-lg border bg-white px-3 py-2">
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-600 whitespace-nowrap">
                  <Ban className="inline h-3 w-3 mr-1" />
                  {effectivePublisherMode === 'INCLUSIVE' ? 'Deny:' : 'Block:'}
                </label>
                <input
                  type="text"
                  value={publisherBlockInput}
                  onChange={(e) => {
                    setPublisherBlockInput(e.target.value);
                    setPublisherBlockError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleBlockPublisher();
                    }
                  }}
                  placeholder="com.example.app or publisher.com"
                  className="flex-1 rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-red-300 focus:border-red-300"
                  disabled={changeActionBusy}
                />
                <button
                  onClick={handleBlockPublisher}
                  disabled={changeActionBusy || !publisherBlockInput.trim()}
                  className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                >
                  <X className="h-3 w-3" />
                  Block
                </button>
              </div>
              {publisherBlockError && (
                <p className="mt-1 text-xs text-red-600 pl-1">{publisherBlockError}</p>
              )}
            </div>
          )}

          {/* ── Commonly Blocked Publishers suggestions ── */}
          {activeTab === 'publisher' && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/50">
              <button
                onClick={() => setShowBlockSuggestions(!showBlockSuggestions)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-amber-900 hover:bg-amber-100/50 rounded-lg"
              >
                <span className="flex items-center gap-1.5">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  Commonly blocked publishers
                  {availableSuggestions.length > 0 && (
                    <span className="rounded-full bg-amber-200 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                      {availableSuggestions.length} suggestions
                    </span>
                  )}
                </span>
                <ChevronDown
                  className={cn(
                    'h-3.5 w-3.5 transition-transform',
                    showBlockSuggestions && 'rotate-180'
                  )}
                />
              </button>
              {showBlockSuggestions && (
                <div className="border-t border-amber-200 px-3 py-2">
                  {availableSuggestions.length === 0 ? (
                    <div className="flex items-center gap-1.5 py-2 text-xs text-amber-700">
                      <Check className="h-3.5 w-3.5 text-green-600" />
                      All commonly blocked publishers are already blocked or pending.
                    </div>
                  ) : (
                    <>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-[10px] text-amber-700">
                          Publishers frequently blocked by other media buyers
                        </span>
                        <button
                          onClick={handleBlockAllSuggestions}
                          disabled={changeActionBusy}
                          className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-2 py-1 text-[10px] font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                        >
                          <Ban className="h-3 w-3" />
                          Block all ({availableSuggestions.length})
                        </button>
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-amber-200 text-left text-[10px] uppercase text-amber-600">
                              <th className="pb-1 pr-2">Publisher</th>
                              <th className="pb-1 pr-2">Category</th>
                              <th className="pb-1 pr-2 text-right">Buyers blocking</th>
                              <th className="pb-1 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-amber-100">
                            {COMMONLY_BLOCKED.map((s) => {
                              const status = getSuggestionStatus(s);
                              return (
                                <tr key={s.publisher_id} className="group">
                                  <td className="py-1.5 pr-2 font-mono text-[11px] text-gray-700" title={s.reason}>
                                    {s.publisher_id}
                                  </td>
                                  <td className="py-1.5 pr-2 text-amber-700">{s.category}</td>
                                  <td className="py-1.5 pr-2 text-right text-amber-800 font-medium">
                                    {Math.round(s.block_rate * 100)}%
                                  </td>
                                  <td className="py-1.5 text-right">
                                    {status === 'blocked' ? (
                                      <span className="inline-flex items-center gap-0.5 text-[10px] text-gray-400">
                                        <Check className="h-3 w-3" /> Blocked
                                      </span>
                                    ) : status === 'pending' ? (
                                      <span className="inline-flex items-center gap-0.5 text-[10px] text-yellow-600">
                                        <Clock className="h-3 w-3" /> Pending
                                      </span>
                                    ) : (
                                      <button
                                        onClick={() => handleBlockSuggestion(s)}
                                        disabled={changeActionBusy}
                                        className="inline-flex items-center gap-0.5 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                                      >
                                        <X className="h-3 w-3" /> Block
                                      </button>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

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
                    Review & Push to Google
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
              <h3 className="text-sm font-semibold text-gray-900">Push Changes to Google?</h3>
              <p className="mt-1 text-xs text-gray-600">
                {pendingChanges.length} change{pendingChanges.length !== 1 ? 's' : ''} will be applied to config {billing_id}.
              </p>
              <div className="mt-3 max-h-40 overflow-y-auto space-y-1 rounded border bg-gray-50 p-2 text-xs font-mono">
                {pendingChanges.map((change) => (
                  <div key={`confirm-${change.id}`}>
                    {describePendingChange(change, effectivePublisherMode)}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-start gap-2 rounded bg-blue-50 border border-blue-200 px-2 py-1.5 text-xs text-blue-700">
                <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                <span>A snapshot will be saved automatically. Use History to undo if needed.</span>
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
                  Push to Google
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Undo Push modal */}
        {undoPushSnapshot && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40" onClick={() => setUndoPushSnapshot(null)} />
            <div className="relative mx-4 w-full max-w-lg rounded-lg border bg-white p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-gray-900">
                  <RotateCcw className="h-4 w-4 text-orange-600" />
                  Undo Push to Google?
                </h3>
                <button onClick={() => setUndoPushSnapshot(null)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-4 w-4" />
                </button>
              </div>

              {undoDryRunLoading ? (
                <div className="flex items-center justify-center py-8 gap-2 text-gray-500 text-xs">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Previewing rollback&hellip;
                </div>
              ) : undoDryRunError ? (
                <div className="rounded bg-red-50 border border-red-200 p-3 text-xs text-red-700">
                  {undoDryRunError}
                </div>
              ) : undoDryRunResult && undoDryRunResult.changes_made.length === 0 ? (
                <div className="rounded bg-blue-50 border border-blue-200 p-3 flex items-start gap-2 text-xs text-blue-700">
                  <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                  No differences found between current config and snapshot. Config may have been modified since then.
                </div>
              ) : (
                <>
                  <div className="text-xs text-gray-600 mb-2">
                    Config: <span className="font-medium text-gray-900">{billing_id}</span>
                    {' '}&middot;{' '}
                    Restoring to: <span className="font-medium text-gray-900">
                      {undoPushSnapshot.snapshot_name || `Snapshot #${undoPushSnapshot.id}`}
                    </span>
                  </div>
                  {undoDryRunResult && undoDryRunResult.changes_made.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs font-medium text-gray-700 mb-1">These changes will be reversed on Google:</p>
                      <div className="max-h-32 overflow-y-auto rounded border bg-gray-50 p-2 space-y-0.5">
                        {undoDryRunResult.changes_made.map((desc, i) => (
                          <div key={i} className="text-[11px] font-mono text-gray-700">{desc}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="mb-3 rounded bg-amber-50 border border-amber-200 p-2 flex items-start gap-2 text-xs text-amber-800">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                    <span>This pushes to Google immediately. A &ldquo;ROLLBACK&rdquo; entry will be recorded in history.</span>
                  </div>
                  {hasPendingChanges && (
                    <div className="mb-3 rounded bg-blue-50 border border-blue-200 p-2 flex items-start gap-2 text-xs text-blue-700">
                      <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                      <span>
                        You have {pendingChanges.length} pending change{pendingChanges.length !== 1 ? 's' : ''} that haven&apos;t been pushed.
                        Undoing this push won&apos;t affect your pending changes.
                      </span>
                    </div>
                  )}
                  <div className="mb-3">
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      Why are you undoing this push?
                    </label>
                    <input
                      type="text"
                      value={undoReason}
                      onChange={(e) => setUndoReason(e.target.value)}
                      placeholder="e.g. Blocked wrong publishers"
                      className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-orange-300"
                    />
                    <span className="text-[10px] text-gray-400">(required)</span>
                  </div>
                </>
              )}

              {undoExecuteMutation.isError && (
                <div className="mb-3 rounded bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                  {(undoExecuteMutation.error as Error)?.message || 'Rollback failed'}
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setUndoPushSnapshot(null)}
                  disabled={undoExecuteMutation.isPending}
                  className="rounded border px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {(!undoDryRunResult || undoDryRunResult.changes_made.length === 0) && !undoDryRunLoading ? 'Close' : 'Cancel'}
                </button>
                {undoDryRunResult && undoDryRunResult.changes_made.length > 0 && (
                  <button
                    onClick={() => undoExecuteMutation.mutate()}
                    disabled={undoExecuteMutation.isPending || !undoReason.trim()}
                    className="inline-flex items-center gap-1 rounded bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-50"
                  >
                    {undoExecuteMutation.isPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="h-3 w-3" />
                    )}
                    Undo Push
                  </button>
                )}
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
