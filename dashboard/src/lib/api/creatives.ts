/**
 * Creatives API module.
 * Handles creative CRUD, thumbnails, and language detection.
 */

import { fetchApi } from "./core";
import type {
  Creative,
  CreativeLiveResponse,
  CreativeCountryBreakdown,
  LanguageDetectionResponse,
  GeoMismatchResponse,
  ManualLanguageUpdate,
} from "@/types/api";

// =============================================================================
// Creative CRUD
// =============================================================================

export async function getCreatives(params?: {
  campaign_id?: string;
  cluster_id?: string;
  buyer_id?: string;
  format?: string;
  limit?: number;
  offset?: number;
}): Promise<Creative[]> {
  const searchParams = new URLSearchParams();
  if (params?.campaign_id) searchParams.set("campaign_id", params.campaign_id);
  if (params?.cluster_id) searchParams.set("cluster_id", params.cluster_id);
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.format) searchParams.set("format", params.format);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const query = searchParams.toString();
  return fetchApi<Creative[]>(`/creatives${query ? `?${query}` : ""}`);
}

export async function getCreative(id: string): Promise<Creative> {
  return fetchApi<Creative>(`/creatives/${encodeURIComponent(id)}`);
}

export async function getCreativeLive(
  id: string,
  params?: { allowCacheFallback?: boolean; refreshCache?: boolean; days?: number }
): Promise<CreativeLiveResponse> {
  const searchParams = new URLSearchParams();
  if (params?.allowCacheFallback !== undefined) {
    searchParams.set("allow_cache_fallback", String(params.allowCacheFallback));
  }
  if (params?.refreshCache !== undefined) {
    searchParams.set("refresh_cache", String(params.refreshCache));
  }
  if (params?.days !== undefined) {
    searchParams.set("days", String(params.days));
  }
  const query = searchParams.toString();
  return fetchApi<CreativeLiveResponse>(
    `/creatives/${encodeURIComponent(id)}/live${query ? `?${query}` : ""}`
  );
}

export async function getCreativeCountries(
  creativeId: string,
  days: number = 7
): Promise<CreativeCountryBreakdown> {
  return fetchApi<CreativeCountryBreakdown>(
    `/creatives/${encodeURIComponent(creativeId)}/countries?days=${days}`
  );
}

export async function deleteCreative(id: string): Promise<void> {
  await fetchApi(`/creatives/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function removeCreativeFromCampaign(id: string): Promise<void> {
  await fetchApi(`/creatives/${encodeURIComponent(id)}/campaign`, { method: "DELETE" });
}

// =============================================================================
// Thumbnails
// =============================================================================

export interface ThumbnailStatusSummary {
  total_videos: number;
  with_thumbnails: number;
  pending: number;
  failed: number;
  coverage_percent: number;
  ffmpeg_available: boolean;
}

export interface ThumbnailGenerateResponse {
  creative_id: string;
  status: "success" | "failed" | "skipped";
  error_reason?: string;
  thumbnail_url?: string;
}

export interface ThumbnailBatchResponse {
  status: string;
  total_processed: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  results: ThumbnailGenerateResponse[];
}

export async function getThumbnailStatus(params?: {
  buyer_id?: string;
}): Promise<ThumbnailStatusSummary> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<ThumbnailStatusSummary>(`/thumbnails/status${query ? `?${query}` : ""}`);
}

export async function generateThumbnail(
  creativeId: string
): Promise<ThumbnailGenerateResponse> {
  return fetchApi<ThumbnailGenerateResponse>("/thumbnails/generate", {
    method: "POST",
    body: JSON.stringify({ creative_id: creativeId }),
  });
}

export async function generateThumbnailsBatch(params?: {
  seat_id?: string;
  limit?: number;
  force?: boolean;
}): Promise<ThumbnailBatchResponse> {
  return fetchApi<ThumbnailBatchResponse>("/thumbnails/generate-batch", {
    method: "POST",
    body: JSON.stringify(params ?? {}),
  });
}

// =============================================================================
// Language Detection
// =============================================================================

export async function analyzeCreativeLanguage(
  creativeId: string,
  force: boolean = false
): Promise<LanguageDetectionResponse> {
  const params = force ? "?force=true" : "";
  return fetchApi<LanguageDetectionResponse>(
    `/creatives/${encodeURIComponent(creativeId)}/analyze-language${params}`,
    { method: "POST" }
  );
}

export async function updateCreativeLanguage(
  creativeId: string,
  update: ManualLanguageUpdate
): Promise<LanguageDetectionResponse> {
  return fetchApi<LanguageDetectionResponse>(
    `/creatives/${encodeURIComponent(creativeId)}/language`,
    {
      method: "PUT",
      body: JSON.stringify(update),
    }
  );
}

export async function getCreativeGeoMismatch(
  creativeId: string,
  days: number = 7
): Promise<GeoMismatchResponse> {
  return fetchApi<GeoMismatchResponse>(
    `/creatives/${encodeURIComponent(creativeId)}/geo-mismatch?days=${days}`
  );
}
