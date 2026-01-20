/**
 * API Module Index
 *
 * This file re-exports all API functions for backward compatibility.
 * New code should import from specific modules:
 *   import { logout, checkAuth } from "@/lib/api/auth";
 *   import { getCreatives } from "@/lib/api/creatives";
 *
 * Note: Login is handled by OAuth2 Proxy (Google Auth) - no password-based login.
 *
 * The monolithic api.ts is being split into:
 *   - core.ts: fetchApi, health, stats, system
 *   - auth.ts: logout, session management (OAuth2 Proxy handles login)
 *   - admin.ts: user management, audit logs
 *   - creatives.ts: creative CRUD, thumbnails, language
 *   - campaigns.ts: campaigns, AI campaigns
 *   - seats.ts: buyer seats, discovery
 *   - analytics.ts: waste, performance, QPS, funnel
 *   - settings.ts: RTB endpoints, pretargeting, configs
 *   - integrations.ts: credentials, Gmail, GCP
 *   - uploads.ts: upload tracking, import history, new creatives
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
export * from "./snapshots";
export * from "./settings";
export * from "./uploads";

// Legacy file still contains: recommendations, traffic.
// These can be migrated in future refactoring passes.
// NOTE: We explicitly re-export only unmigrated items to avoid duplicate exports.
export {
  // Utilities
  getSizes,
  lookupGeoNames,
  generateMockTraffic,
  importPerformanceData,
  // Recommendations
  getRecommendations,
  getRecommendationSummary,
  resolveRecommendation,
  getPretargetingRecommendations,
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
  type GmailImportHistoryItem,
} from "../api-legacy";
