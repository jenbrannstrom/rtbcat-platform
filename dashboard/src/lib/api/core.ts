/**
 * Core API utilities and shared types.
 * All other API modules import fetchApi from here.
 */

import type { Stats, Health, SizesResponse } from "@/types/api";

export const API_BASE = "/api";

/**
 * Generic fetch wrapper with error handling and session auth.
 */
export async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      credentials: "include", // Include cookies for session auth
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });
  } catch (err) {
    // Network error - API server likely not running
    throw new Error(
      "Cannot connect to API server. Please ensure the backend is running on port 8000."
    );
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
  version: string;
  database: {
    status: string;
    creative_count: number;
    daily_stats_count: number;
    oldest_date: string | null;
    newest_date: string | null;
  };
  thumbnails: {
    pending: number;
    total: number;
  };
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return fetchApi<SystemStatus>("/system/status");
}
