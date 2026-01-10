/**
 * Campaigns API module.
 * Handles standard campaigns and AI-generated campaigns.
 */

import { fetchApi } from "./core";
import type { Campaign } from "@/types/api";

// =============================================================================
// Standard Campaigns
// =============================================================================

export async function getCampaigns(params?: {
  source?: string;
  limit?: number;
  offset?: number;
}): Promise<Campaign[]> {
  const searchParams = new URLSearchParams();
  if (params?.source) searchParams.set("source", params.source);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const query = searchParams.toString();
  return fetchApi<Campaign[]>(`/campaigns${query ? `?${query}` : ""}`);
}

export async function getCampaign(id: string): Promise<Campaign> {
  return fetchApi<Campaign>(`/campaigns/${encodeURIComponent(id)}`);
}

// =============================================================================
// AI Campaigns
// =============================================================================

export interface AICampaignPerformance {
  impressions: number;
  clicks: number;
  spend: number;
  queries: number;
  win_rate: number | null;
  ctr: number | null;
  cpm: number | null;
}

export interface AICampaign {
  id: number;
  seat_id?: number;
  name: string;
  description?: string;
  ai_generated: boolean;
  ai_confidence?: number;
  clustering_method?: string;
  status: string;
  creative_count: number;
  performance?: AICampaignPerformance;
}

export interface AutoClusterResponse {
  campaigns_created: number;
  creatives_categorized: number;
  campaigns: Array<{ id: number; name: string; count: number }>;
}

export async function getAICampaigns(params?: {
  seat_id?: number;
  status?: string;
  include_performance?: boolean;
  period?: string;
}): Promise<AICampaign[]> {
  const searchParams = new URLSearchParams();
  if (params?.seat_id) searchParams.set("seat_id", String(params.seat_id));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.include_performance !== undefined) {
    searchParams.set("include_performance", String(params.include_performance));
  }
  if (params?.period) searchParams.set("period", params.period);

  const query = searchParams.toString();
  return fetchApi<AICampaign[]>(`/ai-campaigns${query ? `?${query}` : ""}`);
}

export async function getAICampaign(id: number): Promise<AICampaign> {
  return fetchApi<AICampaign>(`/ai-campaigns/${id}`);
}

export async function updateAICampaign(
  id: number,
  updates: { name?: string; description?: string; status?: string }
): Promise<{ status: string }> {
  return fetchApi<{ status: string }>(`/ai-campaigns/${id}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteAICampaign(id: number): Promise<{ status: string }> {
  return fetchApi<{ status: string }>(`/ai-campaigns/${id}`, {
    method: "DELETE",
  });
}

export async function getAICampaignCreatives(
  campaignId: number
): Promise<{ creative_ids: string[]; count: number }> {
  return fetchApi<{ creative_ids: string[]; count: number }>(
    `/ai-campaigns/${campaignId}/creatives`
  );
}

export async function removeCreativeFromAICampaign(
  campaignId: number,
  creativeId: string
): Promise<{ status: string }> {
  return fetchApi<{ status: string }>(
    `/ai-campaigns/${campaignId}/creatives/${encodeURIComponent(creativeId)}`,
    { method: "DELETE" }
  );
}

export async function autoClusterCreatives(params?: {
  seat_id?: number;
  use_ai?: boolean;
  min_cluster_size?: number;
}): Promise<AutoClusterResponse> {
  return fetchApi<AutoClusterResponse>("/ai-campaigns/auto-cluster", {
    method: "POST",
    body: JSON.stringify(params ?? {}),
  });
}

export async function getAICampaignPerformance(
  campaignId: number,
  period?: string
): Promise<AICampaignPerformance> {
  const searchParams = new URLSearchParams();
  if (period) searchParams.set("period", period);
  const query = searchParams.toString();

  return fetchApi<AICampaignPerformance>(
    `/ai-campaigns/${campaignId}/performance${query ? `?${query}` : ""}`
  );
}

export async function getAICampaignDailyTrend(
  campaignId: number,
  days?: number
): Promise<{ trend: Array<{ date: string; impressions: number; clicks: number; spend: number }> }> {
  const searchParams = new URLSearchParams();
  if (days) searchParams.set("days", String(days));
  const query = searchParams.toString();

  return fetchApi<{ trend: Array<{ date: string; impressions: number; clicks: number; spend: number }> }>(
    `/ai-campaigns/${campaignId}/performance/daily${query ? `?${query}` : ""}`
  );
}
