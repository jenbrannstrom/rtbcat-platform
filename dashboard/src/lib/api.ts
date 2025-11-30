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
