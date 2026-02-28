/**
 * Core API utilities and shared types.
 * All other API modules import fetchApi from here.
 */

import type { Stats, Health, SizesResponse, DataHealthResponse } from "@/types/api";

export const API_BASE = "/api";
const DEFAULT_API_TIMEOUT_MS = 30000;

export interface FetchApiOptions extends RequestInit {
  timeoutMs?: number;
}

/**
 * Generic fetch wrapper with error handling and session auth.
 */
export async function fetchApi<T>(
  endpoint: string,
  options?: FetchApiOptions
): Promise<T> {
  let response: Response;
  const { timeoutMs = DEFAULT_API_TIMEOUT_MS, ...fetchOptions } = options || {};
  const timeoutController = options?.signal ? null : new AbortController();
  const signal = options?.signal || timeoutController?.signal;
  const timeoutId = timeoutController
    ? setTimeout(() => timeoutController.abort(), timeoutMs)
    : null;

  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      credentials: "include", // Include cookies for session auth
      headers: {
        "Content-Type": "application/json",
        ...fetchOptions.headers,
      },
      ...fetchOptions,
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    // Network error - API server likely not running
    throw new Error(
      "Cannot connect to API server. Please ensure the backend is running on port 8000."
    );
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }

  if (!response.ok) {
    // Try to parse error response
    const text = await response.text();
    let errorMessage: string;

    try {
      const errorData = JSON.parse(text);
      errorMessage = errorData.detail || `API error: ${response.status}`;
    } catch {
      // Not JSON - check for common proxy errors
      if (response.status === 500 && text.includes("Internal Server Error")) {
        errorMessage = "Cannot connect to API server. Please ensure the backend is running on port 8000.";
      } else if (response.status === 502 || response.status === 503) {
        errorMessage = "API server is unavailable. Please check if the backend is running.";
      } else {
        errorMessage = `API error: ${response.status}`;
      }
    }

    throw new Error(errorMessage);
  }

  return response.json();
}

// =============================================================================
// System & Health
// =============================================================================

export async function getHealth(): Promise<Health> {
  return fetchApi<Health>("/health");
}

export async function getStats(): Promise<Stats> {
  return fetchApi<Stats>("/stats");
}

export async function getSizes(): Promise<string[]> {
  const response = await fetchApi<SizesResponse>("/sizes");
  return response.sizes;
}

export interface SystemStatus {
  version?: string;
  python_version: string;
  node_available: boolean;
  node_version?: string;
  ffmpeg_available: boolean;
  ffmpeg_version?: string;
  database_size_mb: number;
  thumbnails_count: number;
  disk_space_gb: number;
  creatives_count: number;
  videos_count: number;
  database?: {
    status: string;
    creative_count: number;
    daily_stats_count: number;
    oldest_date: string | null;
    newest_date: string | null;
  };
  thumbnails?: {
    pending: number;
    total: number;
  };
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return fetchApi<SystemStatus>("/system/status");
}

export interface SystemDataHealthQuery {
  days?: number;
  buyer_id?: string;
  availability_state?: "healthy" | "degraded" | "unavailable";
  min_completeness_pct?: number;
  limit?: number;
}

export async function getSystemDataHealth(
  query: SystemDataHealthQuery = {}
): Promise<DataHealthResponse> {
  const params = new URLSearchParams();
  if (typeof query.days === "number") params.set("days", String(query.days));
  if (query.buyer_id) params.set("buyer_id", query.buyer_id);
  if (query.availability_state) params.set("availability_state", query.availability_state);
  if (typeof query.min_completeness_pct === "number") {
    params.set("min_completeness_pct", String(query.min_completeness_pct));
  }
  if (typeof query.limit === "number") params.set("limit", String(query.limit));

  const qs = params.toString();
  return fetchApi<DataHealthResponse>(`/system/data-health${qs ? `?${qs}` : ""}`);
}

// =============================================================================
// Geo Utilities
// =============================================================================

// Cache for geo lookups to avoid repeated API calls
const geoNameCache: Record<string, string> = {};

export async function lookupGeoNames(geoIds: string[]): Promise<Record<string, string>> {
  // Filter out already cached IDs
  const uncachedIds = geoIds.filter(id => !(id in geoNameCache));

  if (uncachedIds.length === 0) {
    // All IDs are cached
    const result: Record<string, string> = {};
    for (const id of geoIds) {
      result[id] = geoNameCache[id];
    }
    return result;
  }

  // Fetch uncached IDs from API
  const response = await fetchApi<{ geos: Record<string, string> }>(
    `/geos/lookup?ids=${encodeURIComponent(uncachedIds.join(','))}`
  );

  // Add to cache
  for (const [id, name] of Object.entries(response.geos)) {
    geoNameCache[id] = name;
  }

  // Return all requested IDs
  const result: Record<string, string> = {};
  for (const id of geoIds) {
    result[id] = geoNameCache[id] || id;
  }
  return result;
}

export interface GeoSearchResult {
  geo_id: string;
  label: string;
  country_code?: string | null;
  country_name?: string | null;
  city_name?: string | null;
  type: "country" | "city";
}

export async function searchGeoTargets(
  query: string,
  options?: { limit?: number; type?: "all" | "country" | "city" }
): Promise<GeoSearchResult[]> {
  const normalized = query.trim();
  if (!normalized) return [];

  const params = new URLSearchParams({ q: normalized });
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.type) params.set("type", options.type);

  const response = await fetchApi<{ results: GeoSearchResult[] }>(
    `/geos/search?${params.toString()}`
  );
  return response.results || [];
}
