import type {
  Creative,
  Campaign,
  Stats,
  Health,
  CollectRequest,
  CollectResponse,
  SizesResponse,
  BuyerSeat,
  DiscoverSeatsRequest,
  DiscoverSeatsResponse,
  SyncSeatResponse,
  WasteReport,
  SizeCoverage,
  ImportTrafficResponse,
  BatchPerformanceResponse,
  PerformancePeriod,
} from "@/types/api";
import type { ImportResponse } from "@/lib/types/import";

const API_BASE = "/api";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

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

export async function deleteCreative(id: string): Promise<void> {
  await fetchApi(`/creatives/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function removeCreativeFromCampaign(id: string): Promise<void> {
  await fetchApi(`/creatives/${encodeURIComponent(id)}/campaign`, { method: "DELETE" });
}

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

export async function collectCreatives(
  request: CollectRequest
): Promise<CollectResponse> {
  return fetchApi<CollectResponse>("/collect", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function collectCreativesSync(
  request: CollectRequest
): Promise<CollectResponse> {
  return fetchApi<CollectResponse>("/collect/sync", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// Buyer Seats API

export async function getSeats(params?: {
  bidder_id?: string;
  active_only?: boolean;
}): Promise<BuyerSeat[]> {
  const searchParams = new URLSearchParams();
  if (params?.bidder_id) searchParams.set("bidder_id", params.bidder_id);
  if (params?.active_only !== undefined) {
    searchParams.set("active_only", String(params.active_only));
  }

  const query = searchParams.toString();
  return fetchApi<BuyerSeat[]>(`/seats${query ? `?${query}` : ""}`);
}

export async function getSeat(buyerId: string): Promise<BuyerSeat> {
  return fetchApi<BuyerSeat>(`/seats/${encodeURIComponent(buyerId)}`);
}

export async function discoverSeats(
  request: DiscoverSeatsRequest
): Promise<DiscoverSeatsResponse> {
  return fetchApi<DiscoverSeatsResponse>("/seats/discover", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function syncSeat(
  buyerId: string,
  filterQuery?: string
): Promise<SyncSeatResponse> {
  const searchParams = new URLSearchParams();
  if (filterQuery) searchParams.set("filter_query", filterQuery);
  const query = searchParams.toString();

  return fetchApi<SyncSeatResponse>(
    `/seats/${encodeURIComponent(buyerId)}/sync${query ? `?${query}` : ""}`,
    { method: "POST" }
  );
}

export async function updateSeat(
  buyerId: string,
  updates: { display_name?: string }
): Promise<BuyerSeat> {
  return fetchApi<BuyerSeat>(`/seats/${encodeURIComponent(buyerId)}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function populateSeatsFromCreatives(): Promise<{
  status: string;
  seats_created: number;
}> {
  return fetchApi<{ status: string; seats_created: number }>("/seats/populate", {
    method: "POST",
  });
}

// Waste Analysis API

export async function getWasteReport(params?: {
  buyer_id?: string;
  days?: number;
}): Promise<WasteReport> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.days) searchParams.set("days", String(params.days));

  const query = searchParams.toString();
  return fetchApi<WasteReport>(`/analytics/waste${query ? `?${query}` : ""}`);
}

export async function getSizeCoverage(params?: {
  buyer_id?: string;
}): Promise<Record<string, SizeCoverage>> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);

  const query = searchParams.toString();
  return fetchApi<Record<string, SizeCoverage>>(
    `/analytics/size-coverage${query ? `?${query}` : ""}`
  );
}

export async function generateMockTraffic(params?: {
  days?: number;
  buyer_id?: string;
  base_daily_requests?: number;
  waste_bias?: number;
}): Promise<ImportTrafficResponse> {
  const searchParams = new URLSearchParams();
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.base_daily_requests) {
    searchParams.set("base_daily_requests", String(params.base_daily_requests));
  }
  if (params?.waste_bias !== undefined) {
    searchParams.set("waste_bias", String(params.waste_bias));
  }

  const query = searchParams.toString();
  return fetchApi<ImportTrafficResponse>(
    `/analytics/generate-mock-traffic${query ? `?${query}` : ""}`,
    { method: "POST" }
  );
}

// Performance Metrics API

export async function getBatchPerformance(
  creativeIds: string[],
  period: PerformancePeriod = "7d"
): Promise<BatchPerformanceResponse> {
  return fetchApi<BatchPerformanceResponse>("/performance/metrics/batch", {
    method: "POST",
    body: JSON.stringify({
      creative_ids: creativeIds,
      period,
    }),
  });
}

// Performance Data Import API

export async function importPerformanceData(
  file: File,
  onProgress?: (progress: number) => void
): Promise<ImportResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/performance/import-csv`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.error || "Import failed");
  }

  const result: ImportResponse = await response.json();

  if (onProgress) {
    onProgress(100);
  }

  return result;
}

// AI Campaigns API

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

// Configuration / Credentials API

export interface CredentialsStatus {
  configured: boolean;
  client_email?: string;
  project_id?: string;
  credentials_path?: string;
}

export interface CredentialsUploadResponse {
  success: boolean;
  client_email?: string;
  project_id?: string;
  message: string;
}

export async function getCredentialsStatus(): Promise<CredentialsStatus> {
  return fetchApi<CredentialsStatus>("/config/credentials");
}

export async function uploadCredentials(
  serviceAccountJson: string,
  accountId?: string
): Promise<CredentialsUploadResponse> {
  return fetchApi<CredentialsUploadResponse>("/config/credentials", {
    method: "POST",
    body: JSON.stringify({
      service_account_json: serviceAccountJson,
      account_id: accountId,
    }),
  });
}

export async function deleteCredentials(): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>("/config/credentials", {
    method: "DELETE",
  });
}
