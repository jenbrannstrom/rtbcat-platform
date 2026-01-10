/**
 * API Module Index
 *
 * This file re-exports all API functions for backward compatibility.
 * New code should import from specific modules:
 *   import { login, logout } from "@/lib/api/auth";
 *   import { getCreatives } from "@/lib/api/creatives";
 *
 * The monolithic api.ts is being split into:
 *   - core.ts: fetchApi, health, stats, system
 *   - auth.ts: login, logout, session management
 *   - admin.ts: user management, audit logs
 *   - creatives.ts: creative CRUD, thumbnails, language
 *   - campaigns.ts: campaigns, AI campaigns
 *   - seats.ts: buyer seats, discovery
 *   - analytics.ts: waste, performance, QPS, funnel
 *   - settings.ts: RTB endpoints, pretargeting, configs
 *   - integrations.ts: credentials, Gmail, GCP
 */

// Re-export from modular files
export * from "./core";
export * from "./auth";
export * from "./creatives";
export * from "./campaigns";
export * from "./seats";
export * from "./admin";
export * from "./integrations";
export * from "./analytics";

// Legacy file still contains: recommendations, RTB settings/pretargeting,
// upload tracking, import history, snapshots, pending changes, traffic.
// These can be migrated in future refactoring passes.
// NOTE: We explicitly re-export only unmigrated items to avoid duplicate exports.
export {
  // Utilities
  getSizes,
  generateMockTraffic,
  importPerformanceData,
  // Recommendations
  getRecommendations,
  getRecommendationSummary,
  resolveRecommendation,
  getPretargetingRecommendations,
  // RTB Endpoints & Pretargeting
  getRTBEndpoints,
  syncRTBEndpoints,
  getPretargetingConfigs,
  syncPretargetingConfigs,
  setPretargetingName,
  getConfigBreakdown,
  // Upload & Import tracking
  getUploadTracking,
  getImportHistory,
  getPretargetingHistory,
  getNewlyUploadedCreatives,
  // Snapshots & Comparisons
  createSnapshot,
  getSnapshots,
  createComparison,
  getComparisons,
  // Pending Changes
  createPendingChange,
  getPendingChanges,
  cancelPendingChange,
  markChangeApplied,
  getPretargetingConfigDetail,
  // Actions
  applyPendingChange,
  applyAllPendingChanges,
  suspendPretargeting,
  activatePretargeting,
  rollbackPretargeting,
  // Types (not migrated yet)
  type Evidence,
  type Impact,
  type Action,
  type Recommendation,
  type RecommendationSummary,
  type SizeGap,
  type CoveredSize,
  type SizeCoverageResponse,
  type GeoStats,
  type GeoWasteResponse,
  type PretargetingConfig,
  type PretargetingResponse,
  type PretargetingRecommendation,
  type QPSSummaryResponse,
  type RTBEndpointItem,
  type RTBEndpointsResponse,
  type SyncEndpointsResponse,
  type PretargetingConfigResponse,
  type SyncPretargetingResponse,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigBreakdownResponse,
  type GmailImportHistoryItem,
  type DailyUploadSummary,
  type UploadTrackingResponse,
  type ImportHistoryItem,
  type PretargetingHistoryItem,
  type NewlyUploadedCreative,
  type NewlyUploadedCreativesResponse,
  type PretargetingSnapshot,
  type SnapshotComparison,
  type PendingChange,
  type ConfigDetail,
  type ApplyChangeResponse,
  type ApplyAllResponse,
  type SuspendActivateResponse,
  type RollbackResponse,
  type AppDrilldownSizeItem,
  type AppDrilldownCountryItem,
  type AppDrilldownCreativeItem,
  type AppDrilldownWasteInsight,
  type AppDrilldownBidFilteringItem,
  type AppDrilldownResponse,
} from "../api";
