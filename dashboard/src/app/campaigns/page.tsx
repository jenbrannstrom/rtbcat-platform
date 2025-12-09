'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
// import { createSnapModifier } from '@dnd-kit/modifiers';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Sparkles, RefreshCw, Check, LayoutGrid, List, ArrowDown, ArrowUp, Globe, X } from 'lucide-react';
import { useDroppable } from '@dnd-kit/core';
import { ClusterCard } from '@/components/campaigns/cluster-card';
import { UnassignedPool } from '@/components/campaigns/unassigned-pool';
import { DraggableCreative } from '@/components/campaigns/draggable-creative';
import { ListCluster } from '@/components/campaigns/list-cluster';
import { ListItem } from '@/components/campaigns/list-item';
import { PreviewModal } from '@/components/preview-modal';
import { cn } from '@/lib/utils';
import { useAccount } from '@/contexts/account-context';

// Droppable zone to create a new campaign on drop (Grid view)
function NewCampaignDropZone({ onClick }: { onClick: () => void }) {
  const { setNodeRef, isOver } = useDroppable({
    id: 'new-campaign',
  });

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={cn(
        "min-h-[200px] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-colors cursor-pointer",
        isOver
          ? "border-blue-500 bg-blue-50 text-blue-600"
          : "border-gray-300 text-gray-400 hover:border-blue-400 hover:text-blue-500"
      )}
    >
      <span className="text-4xl">+</span>
      <span>{isOver ? "Drop to create campaign" : "New Campaign"}</span>
      {isOver && (
        <span className="text-sm text-blue-500">Release to create with selected items</span>
      )}
    </div>
  );
}

// Droppable zone to create a new campaign on drop (List view)
function NewCampaignDropZoneList({ onClick }: { onClick: () => void }) {
  const { setNodeRef, isOver } = useDroppable({
    id: 'new-campaign',
  });

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={cn(
        "w-80 flex-shrink-0 rounded-lg border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-colors cursor-pointer",
        isOver
          ? "border-blue-500 bg-blue-50 text-blue-600"
          : "border-gray-300 bg-gray-50 text-gray-400 hover:border-blue-400 hover:text-blue-500"
      )}
      style={{ maxHeight: '70vh', minHeight: '200px' }}
    >
      <span className="text-4xl">+</span>
      <span className="text-sm">{isOver ? "Drop to create" : "New Campaign"}</span>
      {isOver && (
        <span className="text-xs text-blue-500">Release to create</span>
      )}
    </div>
  );
}

type ViewMode = 'grid' | 'list';

// =============================================================================
// Types
// =============================================================================

interface Campaign {
  id: string;
  name: string;
  creative_ids: string[];
  created_at: string | null;
  updated_at: string | null;
}

interface Creative {
  id: string;
  format: string;
  country?: string;  // Phase 22: Country from performance data
  created_at?: string;  // Phase 24: Date Added sort
  final_url?: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: { url?: string }; image?: { url?: string } };
  html?: { thumbnail_url?: string };  // Phase 22: HTML thumbnail
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
    total_clicks?: number;
  };
  waste_flags?: { broken_video?: boolean; zero_engagement?: boolean };
}

interface ClusterSuggestion {
  suggested_name: string;
  creative_ids: string[];
  domain: string | null;
}

interface AutoClusterResponse {
  suggestions: ClusterSuggestion[];
  unclustered_count: number;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Generate a clean cluster name from a URL/domain
 * - Decodes URL-encoded strings
 * - Extracts bundle IDs from AppsFlyer/Adjust URLs
 * - Formats com.app.name as "App Name"
 * - Handles Play Store, App Store, Firebase URLs
 */
function generateClusterName(url: string | null): string {
  if (!url) return 'Unknown';

  try {
    // Decode URL-encoded strings
    let decoded = decodeURIComponent(url);

    // Extract bundle ID from AppsFlyer URLs
    // e.g., https://app.appsflyer.com/com.example.app?pid=...
    const appsFlyerMatch = decoded.match(/app\.appsflyer\.com\/([a-zA-Z0-9._-]+)/);
    if (appsFlyerMatch) {
      return formatBundleId(appsFlyerMatch[1]);
    }

    // Extract from Adjust URLs
    // e.g., https://app.adjust.com/abc123?campaign=...
    const adjustMatch = decoded.match(/adjust\.com.*[?&]campaign=([^&]+)/i);
    if (adjustMatch) {
      return decodeURIComponent(adjustMatch[1]).replace(/[_-]/g, ' ');
    }

    // Extract from Play Store URLs
    // e.g., https://play.google.com/store/apps/details?id=com.example.app
    const playStoreMatch = decoded.match(/play\.google\.com\/store\/apps\/details\?id=([a-zA-Z0-9._-]+)/);
    if (playStoreMatch) {
      return formatBundleId(playStoreMatch[1]);
    }

    // Extract from App Store URLs
    // e.g., https://apps.apple.com/app/app-name/id123456789
    const appStoreMatch = decoded.match(/apps\.apple\.com\/[^/]+\/app\/([^/]+)/);
    if (appStoreMatch) {
      return appStoreMatch[1].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    // Extract from Firebase Dynamic Links
    const firebaseMatch = decoded.match(/\.page\.link.*[?&]link=([^&]+)/);
    if (firebaseMatch) {
      return generateClusterName(decodeURIComponent(firebaseMatch[1]));
    }

    // If it looks like a bundle ID (com.something.app)
    if (/^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$/i.test(decoded)) {
      return formatBundleId(decoded);
    }

    // Try to extract domain name
    const domainMatch = decoded.match(/(?:https?:\/\/)?(?:www\.)?([^\/\?]+)/);
    if (domainMatch) {
      const domain = domainMatch[1];
      // Clean up domain - remove .com, .io, etc. and format
      const cleanDomain = domain
        .replace(/\.(com|io|app|net|org|co)$/i, '')
        .replace(/[._-]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
      return cleanDomain || domain;
    }

    return url.substring(0, 30);
  } catch {
    return url.substring(0, 30);
  }
}

/**
 * Format a bundle ID like com.example.myapp into "Example Myapp"
 */
function formatBundleId(bundleId: string): string {
  // Split by dots and take the last 2 parts (skip com/org/etc)
  const parts = bundleId.split('.');
  const relevantParts = parts.length > 2 ? parts.slice(-2) : parts;

  return relevantParts
    .map(part =>
      part
        .replace(/([a-z])([A-Z])/g, '$1 $2') // Split camelCase
        .replace(/[_-]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
    )
    .join(' ');
}

// =============================================================================
// API Functions
// =============================================================================

async function fetchCampaigns(): Promise<Campaign[]> {
  const res = await fetch('/api/campaigns');
  if (!res.ok) throw new Error('Failed to fetch campaigns');
  return res.json();
}

async function fetchUnclustered(buyerId?: string | null): Promise<{ creative_ids: string[]; count: number }> {
  const params = new URLSearchParams();
  if (buyerId) params.set('buyer_id', buyerId);
  const query = params.toString();
  const res = await fetch(`/api/campaigns/unclustered${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error('Failed to fetch unclustered');
  return res.json();
}

async function fetchAllCreatives(buyerId?: string | null): Promise<Creative[]> {
  const params = new URLSearchParams({ limit: '1000' });
  if (buyerId) params.set('buyer_id', buyerId);
  const res = await fetch(`/api/creatives?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch creatives');
  const data = await res.json();
  // API returns list directly, not { creatives: [...] }
  return Array.isArray(data) ? data : (data.creatives || []);
}

async function autoCluster(buyerId?: string | null): Promise<AutoClusterResponse> {
  const res = await fetch('/api/campaigns/auto-cluster', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ by_url: true, buyer_id: buyerId ?? undefined }),
  });
  if (!res.ok) throw new Error('Failed to auto-cluster');
  return res.json();
}

async function createCampaign(data: { name: string; creative_ids: string[] }): Promise<Campaign> {
  const res = await fetch('/api/campaigns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create campaign');
  return res.json();
}

async function updateCampaign(
  id: string,
  data: { name?: string; add_creative_ids?: string[]; remove_creative_ids?: string[] }
): Promise<Campaign> {
  const res = await fetch(`/api/campaigns/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update campaign');
  return res.json();
}

async function deleteCampaign(id: string): Promise<void> {
  const res = await fetch(`/api/campaigns/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete campaign');
}

// =============================================================================
// Main Page
// =============================================================================

export default function CampaignsPage() {
  const queryClient = useQueryClient();
  const { selectedBuyerId } = useAccount();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [createdSuggestions, setCreatedSuggestions] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastClickedId, setLastClickedId] = useState<string | null>(null);
  const [creativesMap, setCreativesMap] = useState<Map<string, Creative>>(new Map());
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

  // Page-level sort/filter state (Phase 23)
  const [pageSortField, setPageSortField] = useState<'spend' | 'impressions' | 'clicks' | 'creatives' | 'name'>('spend');
  const [pageSortDir, setPageSortDir] = useState<'asc' | 'desc'>('desc');
  const [countryFilter, setCountryFilter] = useState<string | null>(null);

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
      console.log(`[Campaigns] Built creatives map with ${map.size} entries`);
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
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['unclustered'] });
      // Don't reset autoClusterMutation - we want to keep showing suggestions
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
    console.log('=== DRAG START ===', dragId, 'selected:', selectedIds.size);
    setActiveId(dragId);

    // If dragged item is selected, drag all selected items
    // Otherwise, drag only the clicked item
    if (selectedIds.has(dragId)) {
      setDraggedIds(Array.from(selectedIds));
    } else {
      setDraggedIds([dragId]);
    }
  }

  function handleDragCancel(event: DragCancelEvent) {
    console.log('=== DRAG CANCEL ===', event.active.id);
    setActiveId(null);
    setDraggedIds([]);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    console.log('=== DRAG END ===', active.id, '→', over?.id, 'dragging:', draggedIds.length, 'items');
    setActiveId(null);

    // No target - drop cancelled, do nothing
    if (!over) {
      setDraggedIds([]);
      return;
    }

    // Only process creative drags, not cluster drags
    if (active.data.current?.type !== 'creative') {
      console.log('Not a creative drag, ignoring');
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

    console.log('Source cluster:', sourceClusterId, 'Target cluster:', targetClusterId);

    // Dropped on same cluster - do nothing
    if (sourceClusterId === targetClusterId) {
      setDraggedIds([]);
      return;
    }

    // Get all IDs to move (could be multiple if multi-select)
    const idsToMove = draggedIds.length > 0 ? draggedIds : [active.id as string];
    console.log('Moving', idsToMove.length, 'items to', targetClusterId);

    // Handle drop on "new-campaign" zone - create campaign with these items
    if (targetClusterId === 'new-campaign') {
      console.log('Creating new campaign with', idsToMove.length, 'items');

      // Remove from source clusters first
      const idsBySource = new Map<string, string[]>();
      idsToMove.forEach(id => {
        let srcCluster = 'unassigned';
        for (const campaign of campaigns) {
          if (campaign.creative_ids.includes(id)) {
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

      // Create the new campaign with the items
      await createMutation.mutateAsync({
        name: `New Campaign (${idsToMove.length})`,
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
      console.log('Invalid target:', targetClusterId);
      setDraggedIds([]);
      return;
    }

    // Group IDs by their source cluster for efficient batch updates
    const idsBySource = new Map<string, string[]>();
    idsToMove.forEach(id => {
      // Find which cluster this ID belongs to
      let srcCluster = 'unassigned';
      for (const campaign of campaigns) {
        if (campaign.creative_ids.includes(id)) {
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
    await createMutation.mutateAsync({
      name: 'New Campaign',
      creative_ids: [],
    });
  }

  // Apply suggestion - stay on page, mark as created
  async function handleApplySuggestion(suggestion: ClusterSuggestion) {
    setApplyingId(suggestion.suggested_name);
    try {
      // Use the helper to generate a clean name
      const cleanName = generateClusterName(suggestion.domain) || suggestion.suggested_name;
      await createMutation.mutateAsync({
        name: cleanName,
        creative_ids: suggestion.creative_ids,
      });
      // Mark this suggestion as created
      setCreatedSuggestions(prev => new Set(prev).add(suggestion.suggested_name));
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
    let filtered = campaignsWithTotals.filter(c => {
      // If a buyer is selected, filter to campaigns with creatives from that buyer
      if (selectedBuyerId && !c._hasBuyerCreatives) return false;
      // If country filter active, filter by country
      if (countryFilter && !c._hasFilteredCreatives) return false;
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
  }, [campaigns, getCampaignCreatives, pageSortField, pageSortDir, countryFilter, selectedBuyerId]);

  // Debug: Log when data changes
  useEffect(() => {
    console.log('=== CAMPAIGNS DEBUG ===');
    console.log('Campaigns count:', campaigns.length);
    campaigns.forEach(c => {
      console.log(`Campaign "${c.name}": ${c.creative_ids?.length || 0} creative_ids`);
      console.log('  First 5 IDs:', c.creative_ids?.slice(0, 5));
    });

    console.log('=== CREATIVES MAP DEBUG ===');
    console.log('CreativesMap size:', creativesMap.size);
    console.log('Sample keys:', Array.from(creativesMap.keys()).slice(0, 5));

    // Check if campaign creative_ids exist in the map
    campaigns.forEach(c => {
      const found = c.creative_ids?.filter(id => creativesMap.has(String(id))).length || 0;
      const missing = c.creative_ids?.filter(id => !creativesMap.has(String(id))).length || 0;
      console.log(`Campaign "${c.name}": ${found} found in map, ${missing} missing`);
    });
  }, [campaigns, unclustered, creativesMap]);

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
          <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
          <p className="mt-1 text-sm text-gray-500">
            {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''} · {unclustered?.count || 0} unclustered · {creativesMap.size} creatives loaded
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* View Toggle */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                "p-2 rounded transition-colors",
                viewMode === 'grid'
                  ? "bg-white shadow-sm text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title="Grid view"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "p-2 rounded transition-colors",
                viewMode === 'list'
                  ? "bg-white shadow-sm text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title="List view"
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
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Cluster by URL
                </>
              )}
            </button>
            <button
              onClick={handleCreateCluster}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              New Campaign
            </button>
          </div>
        </div>
      </div>

      {/* Suggestions Panel */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="mb-8 bg-purple-50/50 border border-purple-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-purple-900">
              Suggested Clusters ({suggestions.length})
            </h2>
            <button
              onClick={() => setShowSuggestions(false)}
              className="text-sm text-purple-600 hover:text-purple-800"
            >
              Dismiss
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(showAllSuggestions ? suggestions : suggestions.slice(0, 9)).map((suggestion, index) => {
              const isCreated = createdSuggestions.has(suggestion.suggested_name);
              const isApplying = applyingId === suggestion.suggested_name;
              const displayName = generateClusterName(suggestion.domain) || suggestion.suggested_name;

              return (
                <div
                  key={`${index}-${suggestion.suggested_name}`}
                  className={`border rounded-xl p-4 ${isCreated ? 'bg-green-50 border-green-200' : 'bg-purple-50 border-purple-200'}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h4 className={`font-medium truncate ${isCreated ? 'text-green-900' : 'text-purple-900'}`}>
                        {displayName}
                      </h4>
                      {suggestion.domain && suggestion.domain !== displayName && (
                        <p className="text-xs text-gray-500 truncate max-w-[200px]">
                          {suggestion.domain}
                        </p>
                      )}
                    </div>
                    {isCreated ? (
                      <span className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg flex items-center gap-1">
                        <Check className="h-3 w-3" />
                        Created
                      </span>
                    ) : (
                      <button
                        onClick={() => handleApplySuggestion(suggestion)}
                        disabled={isApplying}
                        className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50"
                      >
                        {isApplying ? 'Creating...' : 'Create'}
                      </button>
                    )}
                  </div>
                  <p className={`text-sm ${isCreated ? 'text-green-700' : 'text-purple-700'}`}>
                    {suggestion.creative_ids.length} creative{suggestion.creative_ids.length !== 1 ? 's' : ''}
                  </p>
                </div>
              );
            })}
          </div>
          {suggestions.length > 9 && (
            <button
              onClick={() => setShowAllSuggestions(!showAllSuggestions)}
              className="mt-3 text-sm text-purple-600 hover:text-purple-800 text-center w-full"
            >
              {showAllSuggestions ? 'Show less' : `+${suggestions.length - 9} more suggestions`}
            </button>
          )}
        </div>
      )}

      {/* Page-level Sort/Filter Controls (Phase 23) */}
      <div className="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
        <span className="text-sm text-gray-600 font-medium">Sort:</span>
        {(['spend', 'impressions', 'clicks', 'creatives', 'name'] as const).map(field => (
          <button
            key={field}
            onClick={() => {
              if (pageSortField === field) {
                setPageSortDir(d => d === 'desc' ? 'asc' : 'desc');
              } else {
                setPageSortField(field);
                setPageSortDir('desc');
              }
            }}
            className={cn(
              "px-3 py-1 text-sm rounded flex items-center gap-1 transition-colors",
              pageSortField === field
                ? "bg-blue-100 text-blue-700 font-medium"
                : "hover:bg-gray-200 text-gray-600"
            )}
          >
            {field.charAt(0).toUpperCase() + field.slice(1)}
            {pageSortField === field && (
              pageSortDir === 'desc' ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />
            )}
          </button>
        ))}

        {/* Country filter */}
        {allCountries.length > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <Globe className="h-4 w-4 text-gray-400" />
            <select
              value={countryFilter || ''}
              onChange={e => setCountryFilter(e.target.value || null)}
              className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Countries</option>
              {allCountries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {countryFilter && (
              <button
                onClick={() => setCountryFilter(null)}
                className="p-1 text-gray-400 hover:text-gray-600"
                title="Clear filter"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>

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
          creative={previewCreative as any}
          onClose={() => setPreviewCreativeId(null)}
        />
      )}
    </div>
  );
}
