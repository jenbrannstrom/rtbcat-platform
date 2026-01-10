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
export * from "../api";
