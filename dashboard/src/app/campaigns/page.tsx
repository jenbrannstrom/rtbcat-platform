'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
  DragCancelEvent,
} from '@dnd-kit/core';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Sparkles, RefreshCw, LayoutGrid, List } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAccount } from '@/contexts/account-context';
import { useTranslation } from '@/contexts/i18n-context';
import { PreviewModal } from '@/components/preview-modal';
import {
  // Types
  type Campaign,
  type CampaignCreative,
  type ClusterSuggestion,
  type ViewMode,
  type SortField,
  type SortDirection,
  // API
  fetchCampaigns,
  fetchUnclustered,
  fetchAllCreatives,
  autoCluster,
  createCampaign,
  updateCampaign,
  deleteCampaign,
  // Utils
  generateClusterName,
  // Components
  ClusterCard,
  UnassignedPool,
  DraggableCreative,
  ListCluster,
  ListItem,
  NewCampaignDropZone,
  NewCampaignDropZoneList,
  SuggestionsPanel,
  SortFilterControls,
} from '@/components/campaigns';
import type { Creative as PreviewCreative } from '@/types/api';

// Local type alias for Creative used in this file
type Creative = CampaignCreative;

function parseSortField(value: string | null): SortField {
  switch (value) {
    case 'name':
    case 'impressions':
    case 'clicks':
    case 'creatives':
    case 'spend':
      return value;
    default:
      return 'spend';
  }
}

function parseSortDir(value: string | null): SortDirection {
  return value === 'asc' ? 'asc' : 'desc';
}

function parseViewMode(value: string | null): ViewMode {
  return value === 'list' ? 'list' : 'grid';
}

export default function CampaignsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { selectedBuyerId } = useAccount();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [createdSuggestions, setCreatedSuggestions] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastClickedId, setLastClickedId] = useState<string | null>(null);
  const [creativesMap, setCreativesMap] = useState<Map<string, Creative>>(new Map());
  const [viewMode, setViewMode] = useState<ViewMode>(() => parseViewMode(searchParams.get('view')));
  const [campaignError, setCampaignError] = useState<string | null>(null);

  // Page-level sort/filter state (Phase 23)
  const [pageSortField, setPageSortField] = useState<SortField>(() => parseSortField(searchParams.get('sort')));
  const [pageSortDir, setPageSortDir] = useState<SortDirection>(() => parseSortDir(searchParams.get('dir')));
  const [countryFilter, setCountryFilter] = useState<string | null>(() => searchParams.get('country') || null);
  // Phase 29: Issues filter
  const [showIssuesOnly, setShowIssuesOnly] = useState<boolean>(() => searchParams.get('issues') === '1');

  // Preview modal state (Phase 24)
  const [previewCreativeId, setPreviewCreativeId] = useState<string | null>(null);
  const previewCreative = previewCreativeId ? creativesMap.get(previewCreativeId) : null;

  // Build ordered list of all creative IDs for shift-select range
  const allCreativeIdsRef = useRef<string[]>([]);

  // Sensors: require 8px movement before drag starts (prevents click-to-move)
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,  // Must move 8px before drag activates
      },
    })
  );

  // Snap modifier disabled for smoother dragging
  // const snapToGrid = createSnapModifier(60);

  const syncQueryState = useCallback((next: Partial<{
    viewMode: ViewMode;
    sortField: SortField;
    sortDir: SortDirection;
    countryFilter: string | null;
    showIssuesOnly: boolean;
  }>) => {
    const params = new URLSearchParams(searchParams.toString());
    const merged = {
      viewMode,
      sortField: pageSortField,
      sortDir: pageSortDir,
      countryFilter,
      showIssuesOnly,
      ...next,
    };

    if (merged.viewMode === 'list') params.set('view', 'list');
    else params.delete('view');

    if (merged.sortField !== 'spend') params.set('sort', merged.sortField);
    else params.delete('sort');

    if (merged.sortDir !== 'desc') params.set('dir', merged.sortDir);
    else params.delete('dir');

    if (merged.countryFilter) params.set('country', merged.countryFilter);
    else params.delete('country');

    if (merged.showIssuesOnly) params.set('issues', '1');
    else params.delete('issues');

    const query = params.toString();
    const targetPath = pathname || '/campaigns';
    router.replace(query ? `${targetPath}?${query}` : targetPath, { scroll: false });
  }, [countryFilter, pageSortDir, pageSortField, pathname, router, searchParams, showIssuesOnly, viewMode]);

  const handleViewModeChange = useCallback((nextViewMode: ViewMode) => {
    setViewMode(nextViewMode);
    syncQueryState({ viewMode: nextViewMode });
  }, [syncQueryState]);

  const handleSortChange = useCallback((field: SortField, dir: SortDirection) => {
    setPageSortField(field);
    setPageSortDir(dir);
    syncQueryState({ sortField: field, sortDir: dir });
  }, [syncQueryState]);

  const handleCountryFilterChange = useCallback((nextCountryFilter: string | null) => {
    setCountryFilter(nextCountryFilter);
    syncQueryState({ countryFilter: nextCountryFilter });
  }, [syncQueryState]);

  const handleShowIssuesOnlyChange = useCallback((nextShowIssuesOnly: boolean) => {
    setShowIssuesOnly(nextShowIssuesOnly);
    syncQueryState({ showIssuesOnly: nextShowIssuesOnly });
  }, [syncQueryState]);

  // Queries
  const { data: campaigns = [], isLoading: loadingCampaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
  });

  const { data: unclustered, isLoading: loadingUnclustered } = useQuery({
    queryKey: ['unclustered', selectedBuyerId],
    queryFn: () => fetchUnclustered(selectedBuyerId),
  });

  const { data: allCreatives = [], isLoading: loadingCreatives } = useQuery({
    queryKey: ['all-creatives', selectedBuyerId],
    queryFn: () => fetchAllCreatives(selectedBuyerId),
  });

  // Build creatives map when data loads
  useEffect(() => {
    if (allCreatives.length > 0) {
      const map = new Map<string, Creative>();
      allCreatives.forEach((c) => map.set(String(c.id), c));
      setCreativesMap(map);
    }
  }, [allCreatives]);

  // Build ordered list of creative IDs for shift-select (campaigns first, then unclustered)
  useEffect(() => {
    const orderedIds: string[] = [];
    campaigns.forEach(c => {
      c.creative_ids.forEach(id => orderedIds.push(String(id)));
    });
    (unclustered?.creative_ids || []).forEach(id => orderedIds.push(String(id)));
    allCreativeIdsRef.current = orderedIds;
  }, [campaigns, unclustered]);

  // Auto-cluster mutation
  const autoClusterMutation = useMutation({
    mutationFn: (buyerId?: string | null) => autoCluster(buyerId),
    onSuccess: () => {
      setShowSuggestions(true);
      setCreatedSuggestions(new Set()); // Reset created tracking
    },
  });

  // Create campaign mutation
  const createMutation = useMutation({
    mutationFn: createCampaign,
    onSuccess: (_, variables) => {
      setCampaignError(null);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['unclustered'] });
      // Don't reset autoClusterMutation - we want to keep showing suggestions
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Failed to create cluster';
      setCampaignError(message);
    },
  });

  // Update campaign mutation with optimistic updates for rename
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateCampaign>[1] }) =>
      updateCampaign(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel any outgoing refetches so they don't overwrite optimistic update
      await queryClient.cancelQueries({ queryKey: ['campaigns'] });

      // Snapshot the previous value
      const previousCampaigns = queryClient.getQueryData<Campaign[]>(['campaigns']);

      // Optimistically update for name changes (instant feedback)
      if (data.name !== undefined) {
        queryClient.setQueryData<Campaign[]>(['campaigns'], (old) =>
          old?.map(c => c.id === id ? { ...c, name: data.name! } : c) ?? []
        );
      }

      return { previousCampaigns };
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousCampaigns) {
        queryClient.setQueryData(['campaigns'], context.previousCampaigns);
      }
    },
    onSettled: (_data, _error, variables) => {
      // Only invalidate if structural changes (add/remove creatives), not just rename
      if (variables.data.add_creative_ids || variables.data.remove_creative_ids) {
        queryClient.invalidateQueries({ queryKey: ['campaigns'] });
        queryClient.invalidateQueries({ queryKey: ['unclustered'] });
      }
    },
  });

  // Delete campaign mutation
  const deleteMutation = useMutation({
    mutationFn: deleteCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['unclustered'] });
    },
  });

  // Multi-select handler: Click=single, Ctrl=toggle, Shift=range
  const handleCreativeSelect = useCallback((creativeId: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => {
    const isCtrlKey = event?.ctrlKey || event?.metaKey;
    const isShiftKey = event?.shiftKey;

    setSelectedIds(prev => {
      const newSet = new Set(prev);

      if (isShiftKey && lastClickedId) {
        // Range select: select all between lastClickedId and creativeId
        const allIds = allCreativeIdsRef.current;
        const startIdx = allIds.indexOf(lastClickedId);
        const endIdx = allIds.indexOf(creativeId);

        if (startIdx !== -1 && endIdx !== -1) {
          const [from, to] = startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx];
          for (let i = from; i <= to; i++) {
            newSet.add(allIds[i]);
          }
        }
      } else if (isCtrlKey) {
        // Toggle select
        if (newSet.has(creativeId)) {
          newSet.delete(creativeId);
        } else {
          newSet.add(creativeId);
        }
      } else {
        // Single select (clear others)
        newSet.clear();
        newSet.add(creativeId);
      }

      return newSet;
    });

    // Always update last clicked (for shift-range)
    setLastClickedId(creativeId);
  }, [lastClickedId]);

  // Track which IDs are being dragged (for multi-select)
  const [draggedIds, setDraggedIds] = useState<string[]>([]);

  // Drag handlers
  function handleDragStart(event: DragStartEvent) {
    const dragId = event.active.id as string;
    setActiveId(dragId);

    // If dragged item is selected, drag all selected items
    // Otherwise, drag only the clicked item
    if (selectedIds.has(dragId)) {
      setDraggedIds(Array.from(selectedIds));
    } else {
      setDraggedIds([dragId]);
    }
  }

  function handleDragCancel(_event: DragCancelEvent) {
    setActiveId(null);
    setDraggedIds([]);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveId(null);

    // No target - drop cancelled, do nothing
    if (!over) {
      setDraggedIds([]);
      return;
    }

    // Only process creative drags, not cluster drags
    if (active.data.current?.type !== 'creative') {
      setDraggedIds([]);
      return;
    }

    const sourceClusterId = active.data.current?.clusterId as string;

    // Target could be a cluster directly, or another creative inside a cluster
    // If dropping on a creative, use its clusterId as the target
    let targetClusterId = over.id as string;
    if (over.data.current?.type === 'creative' && over.data.current?.clusterId) {
      targetClusterId = over.data.current.clusterId as string;
    }

    // Dropped on same cluster - do nothing
    if (sourceClusterId === targetClusterId) {
      setDraggedIds([]);
      return;
    }

    // Get all IDs to move (could be multiple if multi-select)
    const idsToMove = draggedIds.length > 0 ? draggedIds : [active.id as string];

    // Handle drop on "new-campaign" zone - create cluster with these items
    if (targetClusterId === 'new-campaign') {

      // Remove from source clusters first
      const idsBySource = new Map<string, string[]>();
      idsToMove.forEach(id => {
        let srcCluster = 'unassigned';
        for (const campaign of campaigns) {
          // Normalize to string comparison to handle API type variations
          if (campaign.creative_ids.map(String).includes(String(id))) {
            srcCluster = campaign.id;
            break;
          }
        }
        if (srcCluster !== 'unassigned') {
          if (!idsBySource.has(srcCluster)) {
            idsBySource.set(srcCluster, []);
          }
          idsBySource.get(srcCluster)!.push(id);
        }
      });

      for (const [srcCluster, ids] of idsBySource) {
        await updateMutation.mutateAsync({
          id: srcCluster,
          data: { remove_creative_ids: ids },
        });
      }

      // Create the new cluster with the items
      await createMutation.mutateAsync({
        name: `New Cluster (${idsToMove.length})`,
        creative_ids: idsToMove,
      });

      setSelectedIds(new Set());
      setDraggedIds([]);
      return;
    }

    // Only move if dropping on a valid cluster (not on another creative)
    const isValidTarget = targetClusterId === 'unassigned' ||
      campaigns.some(c => c.id === targetClusterId);
    if (!isValidTarget) {
      setDraggedIds([]);
      return;
    }

    // Group IDs by their source cluster for efficient batch updates
    const idsBySource = new Map<string, string[]>();
    idsToMove.forEach(id => {
      // Find which cluster this ID belongs to
      let srcCluster = 'unassigned';
      for (const campaign of campaigns) {
        // Normalize to string comparison to handle API type variations
        if (campaign.creative_ids.map(String).includes(String(id))) {
          srcCluster = campaign.id;
          break;
        }
      }
      if (!idsBySource.has(srcCluster)) {
        idsBySource.set(srcCluster, []);
      }
      idsBySource.get(srcCluster)!.push(id);
    });

    // Remove from source clusters
    for (const [srcCluster, ids] of idsBySource) {
      if (srcCluster !== 'unassigned' && srcCluster !== targetClusterId) {
        await updateMutation.mutateAsync({
          id: srcCluster,
          data: { remove_creative_ids: ids },
        });
      }
    }

    // Add to target cluster (if not unassigned)
    if (targetClusterId !== 'unassigned') {
      await updateMutation.mutateAsync({
        id: targetClusterId,
        data: { add_creative_ids: idsToMove },
      });
    }

    // Clear selection after move
    setSelectedIds(new Set());
    setDraggedIds([]);
  }

  // Rename cluster
  async function handleRename(campaignId: string, newName: string) {
    await updateMutation.mutateAsync({
      id: campaignId,
      data: { name: newName },
    });
  }

  // Delete cluster
  async function handleDelete(campaignId: string) {
    await deleteMutation.mutateAsync(campaignId);
  }

  // Open preview modal (Phase 24)
  const handleOpenPreview = useCallback((creativeId: string) => {
    setPreviewCreativeId(creativeId);
  }, []);

  // Create new cluster
  async function handleCreateCluster() {
    try {
      await createMutation.mutateAsync({
        name: 'New Cluster',
        creative_ids: [],
      });
    } catch {
      // Error handled via mutation onError
    }
  }

  const getSuggestionKey = useCallback((suggestion: ClusterSuggestion) => {
    return (
      suggestion.suggested_name ||
      suggestion.domain ||
      suggestion.creative_ids.join(',')
    );
  }, []);

  // Apply suggestion - stay on page, mark as created
  async function handleApplySuggestion(suggestion: ClusterSuggestion) {
    const suggestionKey = getSuggestionKey(suggestion);
    setApplyingId(suggestionKey);
    try {
      // Use the API-provided name (real app name) first, fall back to domain parsing
      const cleanName = suggestion.suggested_name || generateClusterName(suggestion.domain);
      await createMutation.mutateAsync({
        name: cleanName,
        creative_ids: suggestion.creative_ids,
      });
      // Mark this suggestion as created
      setCreatedSuggestions(prev => new Set(prev).add(suggestionKey));
    } finally {
      setApplyingId(null);
    }
  }

  const isLoading = loadingCampaigns || loadingUnclustered || loadingCreatives;
  const suggestions = autoClusterMutation.data?.suggestions || [];
  const activeCreative = activeId ? creativesMap.get(String(activeId)) : null;

  // Get creatives for each campaign - ensure string comparison
  const getCampaignCreatives = useCallback((campaign: Campaign): Creative[] => {
    return campaign.creative_ids
      .map((id) => creativesMap.get(String(id)))
      .filter((c): c is Creative => c !== undefined);
  }, [creativesMap]);

  // Extract all unique countries for filter dropdown (Phase 23)
  const allCountries = useMemo(() => {
    const countries = new Set<string>();
    creativesMap.forEach(c => {
      if (c.country) countries.add(c.country);
    });
    return Array.from(countries).sort();
  }, [creativesMap]);

  // Sort and filter campaigns at page level (Phase 23)
  const sortedCampaigns = useMemo(() => {
    // Calculate totals for each campaign
    const campaignsWithTotals = campaigns.map(campaign => {
      const creatives = getCampaignCreatives(campaign);
      const totalSpend = creatives.reduce((sum, c) => sum + (c.performance?.total_spend_micros || 0), 0);
      const totalImpressions = creatives.reduce((sum, c) => sum + (c.performance?.total_impressions || 0), 0);
      const totalClicks = creatives.reduce((sum, c) => sum + (c.performance?.total_clicks || 0), 0);

      // Filter creatives by country if filter is set
      const filteredCreatives = countryFilter
        ? creatives.filter(c => c.country === countryFilter)
        : creatives;

      return {
        ...campaign,
        _creatives: filteredCreatives,
        _totalSpend: totalSpend,
        _totalImpressions: totalImpressions,
        _totalClicks: totalClicks,
        _creativeCount: creatives.length,
        _hasFilteredCreatives: countryFilter ? filteredCreatives.length > 0 : true,
        _hasBuyerCreatives: creatives.length > 0, // True if campaign has creatives from selected buyer
      };
    });

    // Filter out campaigns with no matching creatives:
    // - When buyer is selected: only show campaigns with creatives from that buyer
    // - When country filter is active: only show campaigns with creatives from that country
    // - Phase 29: When issues filter is active, only show campaigns with disapproved creatives
    const filtered = campaignsWithTotals.filter(c => {
      // If a buyer is selected, filter to campaigns with creatives from that buyer
      if (selectedBuyerId && !c._hasBuyerCreatives) return false;
      // If country filter active, filter by country
      if (countryFilter && !c._hasFilteredCreatives) return false;
      // Phase 29: If issues filter active, only show campaigns with disapproved creatives
      if (showIssuesOnly && !c.has_disapproved) return false;
      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      let aVal: number | string, bVal: number | string;

      switch (pageSortField) {
        case 'spend':
          aVal = a._totalSpend;
          bVal = b._totalSpend;
          break;
        case 'impressions':
          aVal = a._totalImpressions;
          bVal = b._totalImpressions;
          break;
        case 'clicks':
          aVal = a._totalClicks;
          bVal = b._totalClicks;
          break;
        case 'creatives':
          aVal = a._creativeCount;
          bVal = b._creativeCount;
          break;
        case 'name':
          aVal = a.name.toLowerCase();
          bVal = b.name.toLowerCase();
          return pageSortDir === 'desc'
            ? bVal.localeCompare(aVal as string)
            : (aVal as string).localeCompare(bVal as string);
        default:
          return 0;
      }

      return pageSortDir === 'desc' ? (bVal as number) - (aVal as number) : (aVal as number) - (bVal as number);
    });

    return filtered;
  }, [campaigns, getCampaignCreatives, pageSortField, pageSortDir, countryFilter, selectedBuyerId, showIssuesOnly]);

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.campaigns.title}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {campaigns.length} {campaigns.length !== 1 ? t.campaigns.campaignCountPlural.replace('{count}', '') : t.campaigns.campaignCount.replace('{count}', '')} · {unclustered?.count || 0} {t.campaigns.unclustered} · {creativesMap.size} {t.campaigns.creativesLoaded}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* View Toggle */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => handleViewModeChange('grid')}
              className={cn(
                "p-2 rounded transition-colors",
                viewMode === 'grid'
                  ? "bg-white shadow-sm text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title={t.campaigns.gridView}
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleViewModeChange('list')}
              className={cn(
                "p-2 rounded transition-colors",
                viewMode === 'list'
                  ? "bg-white shadow-sm text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title={t.campaigns.listView}
            >
              <List className="h-4 w-4" />
            </button>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => autoClusterMutation.mutate(selectedBuyerId)}
              disabled={autoClusterMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
            >
              {autoClusterMutation.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  {t.campaigns.analyzing}
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  {t.campaigns.clusterByUrl}
                </>
              )}
            </button>
            <button
              onClick={handleCreateCluster}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              {t.campaigns.newCampaign}
            </button>
          </div>
        </div>
      </div>

      {/* Suggestions Panel */}
      {showSuggestions && (
        <SuggestionsPanel
          suggestions={suggestions}
          showAllSuggestions={showAllSuggestions}
          setShowAllSuggestions={setShowAllSuggestions}
          createdSuggestions={createdSuggestions}
          applyingId={applyingId}
          onApplySuggestion={handleApplySuggestion}
          onDismiss={() => setShowSuggestions(false)}
        />
      )}

      {/* Page-level Sort/Filter Controls (Phase 23) */}
      <SortFilterControls
        pageSortField={pageSortField}
        pageSortDir={pageSortDir}
        onSortChange={handleSortChange}
        countryFilter={countryFilter}
        onCountryFilterChange={handleCountryFilterChange}
        allCountries={allCountries}
        showIssuesOnly={showIssuesOnly}
        onShowIssuesOnlyChange={handleShowIssuesOnlyChange}
      />

      {campaignError && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 text-sm">
          {campaignError}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        {viewMode === 'grid' ? (
          <>
            {/* Grid View */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {sortedCampaigns.map((campaign) => (
                <ClusterCard
                  key={campaign.id}
                  campaign={campaign}
                  creatives={getCampaignCreatives(campaign)}
                  onRename={handleRename}
                  onDelete={handleDelete}
                  selectedIds={selectedIds}
                  onCreativeSelect={handleCreativeSelect}
                  onOpenPreview={handleOpenPreview}
                />
              ))}

              {/* New Campaign Drop Zone */}
              <NewCampaignDropZone onClick={handleCreateCluster} />
            </div>

            {/* Unassigned Pool - Grid */}
            <UnassignedPool
              creativeIds={unclustered?.creative_ids || []}
              creatives={creativesMap}
              selectedIds={selectedIds}
              onCreativeSelect={handleCreativeSelect}
              onOpenPreview={handleOpenPreview}
            />
          </>
        ) : (
          /* List View */
          <div className="flex gap-4 overflow-x-auto pb-4">
            {/* Campaign columns */}
            {sortedCampaigns.map((campaign) => (
              <ListCluster
                key={campaign.id}
                id={campaign.id}
                name={campaign.name}
                creatives={getCampaignCreatives(campaign)}
                selectedIds={selectedIds}
                onCreativeSelect={handleCreativeSelect}
                onRename={handleRename}
                onDelete={handleDelete}
                onOpenPreview={handleOpenPreview}
                pageSortField={pageSortField}
              />
            ))}

            {/* Unclustered column */}
            <ListCluster
              id="unassigned"
              name="Unclustered"
              creatives={(unclustered?.creative_ids || [])
                .map(id => creativesMap.get(String(id)))
                .filter((c): c is Creative => c !== undefined)
              }
              isUnclustered
              selectedIds={selectedIds}
              onCreativeSelect={handleCreativeSelect}
              onOpenPreview={handleOpenPreview}
              pageSortField={pageSortField}
            />

            {/* New Campaign Drop Zone (List view) */}
            <NewCampaignDropZoneList onClick={handleCreateCluster} />
          </div>
        )}

        {/* Drag Overlay - adapts to view mode, shows count for multi-select */}
        <DragOverlay dropAnimation={null}>
          {activeCreative ? (
            <div className="relative">
              {viewMode === 'grid' ? (
                <DraggableCreative
                  creative={activeCreative}
                  clusterId=""
                  isDragOverlay
                />
              ) : (
                <ListItem
                  creative={activeCreative}
                  clusterId=""
                  isDragOverlay
                />
              )}
              {/* Multi-select count badge */}
              {draggedIds.length > 1 && (
                <div className="absolute -top-2 -right-2 bg-blue-600 text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center shadow-lg">
                  {draggedIds.length}
                </div>
              )}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Preview Modal (Phase 24) */}
      {previewCreative && (
        <PreviewModal
          creative={previewCreative as unknown as PreviewCreative}
          onClose={() => setPreviewCreativeId(null)}
        />
      )}
    </div>
  );
}
