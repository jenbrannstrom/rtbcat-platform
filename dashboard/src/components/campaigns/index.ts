/**
 * Campaigns components.
 *
 * Extracted from app/campaigns/page.tsx for better organization:
 * - types.ts: Type definitions (~55 lines)
 * - utils.ts: Helper functions (~90 lines)
 * - api.ts: API functions (~70 lines)
 * - NewCampaignDropZone.tsx: Drop zone components (~70 lines)
 * - SuggestionsPanel.tsx: Auto-cluster suggestions (~100 lines)
 * - SortFilterControls.tsx: Sort/filter UI (~100 lines)
 */

// Types
export * from './types';

// Utils
export { formatBundleId, generateClusterName } from './utils';

// API
export {
  fetchCampaigns,
  fetchUnclustered,
  fetchAllCreatives,
  autoCluster,
  createCampaign,
  updateCampaign,
  deleteCampaign,
} from './api';

// Components
export { NewCampaignDropZone, NewCampaignDropZoneList } from './NewCampaignDropZone';
export { SuggestionsPanel } from './SuggestionsPanel';
export { SortFilterControls } from './SortFilterControls';

// Existing components (re-export for convenience)
export { ClusterCard } from './cluster-card';
export { UnassignedPool } from './unassigned-pool';
export { DraggableCreative } from './draggable-creative';
export { ListCluster } from './list-cluster';
export { ListItem } from './list-item';
