/**
 * API Module Index
 *
 * This file re-exports all API functions from modular files.
 * New code should import from specific modules for better tree-shaking:
 *   import { logout, checkAuth } from "@/lib/api/auth";
 *   import { getCreatives } from "@/lib/api/creatives";
 *
 * Note: Login is handled by OAuth2 Proxy (Google Auth) - no password-based login.
 *
 * Module organization:
 *   - core.ts: fetchApi, health, stats, system, geo utilities
 *   - auth.ts: logout, session management (OAuth2 Proxy handles login)
 *   - admin.ts: user management, audit logs
 *   - creatives.ts: creative CRUD, thumbnails, language
 *   - campaigns.ts: campaigns, AI campaigns
 *   - seats.ts: buyer seats, discovery
 *   - analytics.ts: waste, performance, QPS, funnel, recommendations
 *   - settings.ts: RTB endpoints, pretargeting, configs
 *   - integrations.ts: credentials, Gmail, GCP
 *   - uploads.ts: upload tracking, import history, new creatives
 *   - snapshots.ts: pretargeting snapshots
 *   - conversions.ts: conversion health and ingestion telemetry
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
export * from "./optimizer";
export * from "./conversions";
