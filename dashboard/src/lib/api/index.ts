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

// TODO: Migrate remaining functions to modules (analytics, settings),
// then remove this re-export from the legacy file
export * from "../api";
