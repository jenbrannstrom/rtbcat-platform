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
  CreativeCountryBreakdown,
} from "@/types/api";
import type { ImportResponse } from "@/lib/types/import";

const API_BASE = "/api";

async function fetchApi<T>(
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

// Unified Sync All API
export interface SyncAllResponse {
  status: string;
  creatives_synced: number;
  seats_synced: number;
  endpoints_synced: number;
  pretargeting_synced: number;
  message: string;
  last_synced: string | null;
}

export async function syncAllData(): Promise<SyncAllResponse> {
  return fetchApi<SyncAllResponse>("/seats/sync-all", {
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

  const apiResult = await response.json();

  // Map API field names to frontend interface
  const result: ImportResponse = {
    ...apiResult,
    imported: apiResult.rows_imported ?? apiResult.imported,
    duplicates: apiResult.rows_duplicate ?? apiResult.duplicates,
  };

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
  account_id?: string;
}

export interface CredentialsUploadResponse {
  success: boolean;
  id?: string;
  client_email?: string;
  project_id?: string;
  message: string;
}

export async function getCredentialsStatus(): Promise<CredentialsStatus> {
  return fetchApi<CredentialsStatus>("/config/credentials");
}

export async function uploadCredentials(
  serviceAccountJson: string,
  displayName?: string
): Promise<CredentialsUploadResponse> {
  return fetchApi<CredentialsUploadResponse>("/config/credentials", {
    method: "POST",
    body: JSON.stringify({
      service_account_json: serviceAccountJson,
      display_name: displayName,
    }),
  });
}

export async function deleteCredentials(): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>("/config/credentials", {
    method: "DELETE",
  });
}

// Multi-Account Service Accounts API

export interface ServiceAccount {
  id: string;
  client_email: string;
  project_id?: string;
  display_name?: string;
  is_active: boolean;
  created_at?: string;
  last_used?: string;
}

export interface ServiceAccountListResponse {
  accounts: ServiceAccount[];
  count: number;
}

export async function getServiceAccounts(activeOnly: boolean = false): Promise<ServiceAccountListResponse> {
  const params = activeOnly ? "?active_only=true" : "";
  return fetchApi<ServiceAccountListResponse>(`/config/service-accounts${params}`);
}

export async function getServiceAccount(accountId: string): Promise<ServiceAccount> {
  return fetchApi<ServiceAccount>(`/config/service-accounts/${encodeURIComponent(accountId)}`);
}

export async function addServiceAccount(
  serviceAccountJson: string,
  displayName?: string
): Promise<CredentialsUploadResponse> {
  return fetchApi<CredentialsUploadResponse>("/config/service-accounts", {
    method: "POST",
    body: JSON.stringify({
      service_account_json: serviceAccountJson,
      display_name: displayName,
    }),
  });
}

export async function deleteServiceAccount(accountId: string): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>(
    `/config/service-accounts/${encodeURIComponent(accountId)}`,
    { method: "DELETE" }
  );
}

// Gemini API Key Management

export interface GeminiKeyStatus {
  configured: boolean;
  masked_key: string | null;
  message: string;
}

export interface GeminiKeyUpdateResponse {
  success: boolean;
  message: string;
}

export async function getGeminiKeyStatus(): Promise<GeminiKeyStatus> {
  return fetchApi<GeminiKeyStatus>("/config/gemini-key");
}

export async function updateGeminiKey(apiKey: string): Promise<GeminiKeyUpdateResponse> {
  return fetchApi<GeminiKeyUpdateResponse>("/config/gemini-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function deleteGeminiKey(): Promise<GeminiKeyUpdateResponse> {
  return fetchApi<GeminiKeyUpdateResponse>("/config/gemini-key", {
    method: "DELETE",
  });
}

// Thumbnail Generation API

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

// System Status API

export interface SystemStatus {
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
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return fetchApi<SystemStatus>("/system/status");
}

// ============================================================================
// Recommendations API (Phase 25)
// ============================================================================

export interface Evidence {
  metric_name: string;
  metric_value: number;
  threshold: number;
  comparison: string;
  time_period_days: number;
  sample_size: number;
  trend?: string | null;
}

export interface Impact {
  wasted_qps: number;
  wasted_queries_daily: number;
  wasted_spend_usd: number;
  percent_of_total_waste: number;
  potential_savings_monthly: number;
}

export interface Action {
  action_type: string; // "block", "exclude", "pause", "review", "add"
  target_type: string; // "size", "publisher", "app", "geo", "creative", "config"
  target_id: string;
  target_name: string;
  pretargeting_field?: string | null;
  api_example?: string | null;
}

export interface Recommendation {
  id: string;
  type: string;
  severity: string; // "critical", "high", "medium", "low"
  confidence: string;
  title: string;
  description: string;
  evidence: Evidence[];
  impact: Impact;
  actions: Action[];
  affected_creatives: string[];
  affected_campaigns: string[];
  generated_at: string;
  expires_at?: string | null;
  status: string;
}

export interface RecommendationSummary {
  analysis_period_days: number;
  total_queries: number;
  total_impressions: number;
  total_waste_queries: number;
  total_waste_rate: number;
  total_wasted_qps: number;
  total_spend_usd: number;
  recommendation_count: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  total_recommendations: number;
  generated_at: string;
}

export async function getRecommendations(params?: {
  days?: number;
  min_severity?: string;
  type_filter?: string;
}): Promise<Recommendation[]> {
  const searchParams = new URLSearchParams();
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.min_severity) searchParams.set("min_severity", params.min_severity);
  if (params?.type_filter) searchParams.set("type_filter", params.type_filter);

  const query = searchParams.toString();
  return fetchApi<Recommendation[]>(`/recommendations${query ? `?${query}` : ""}`);
}

export async function getRecommendationSummary(
  days: number = 7
): Promise<RecommendationSummary> {
  return fetchApi<RecommendationSummary>(`/recommendations/summary?days=${days}`);
}

export async function resolveRecommendation(
  id: string,
  notes?: string
): Promise<{ status: string; id: string }> {
  const searchParams = new URLSearchParams();
  if (notes) searchParams.set("notes", notes);
  const query = searchParams.toString();

  return fetchApi<{ status: string; id: string }>(
    `/recommendations/${encodeURIComponent(id)}/resolve${query ? `?${query}` : ""}`,
    { method: "POST" }
  );
}

// =============================================================================
// QPS Analytics API (Phase 27)
// =============================================================================

export interface SizeGap {
  size: string;
  format: string;
  queries_received: number;
  daily_estimate: number;
  percent_of_traffic: number;
  recommendation: string;
}

export interface CoveredSize {
  size: string;
  format: string;
  reached_queries: number;
  impressions: number;
  spend_usd: number;
  creative_count: number;
  ctr_pct: number;
}

export interface SizeCoverageResponse {
  period_days: number;
  total_sizes_in_traffic: number;
  sizes_with_creatives: number;
  sizes_without_creatives: number;
  coverage_rate_pct: number;
  wasted_queries_daily: number;
  wasted_qps: number;
  gaps: SizeGap[];
  covered_sizes: CoveredSize[];
}

export interface GeoStats {
  country: string;
  code: string;
  impressions: number;
  clicks: number;
  spend_usd: number;
  ctr_pct: number;
  cpm: number;
  creative_count: number;
  recommendation: string;
}

export interface GeoWasteResponse {
  period_days: number;
  total_geos: number;
  geos_with_traffic: number;
  geos_to_exclude: number;
  geos_to_monitor: number;
  geos_performing_well: number;
  estimated_waste_pct: number;
  total_spend_usd: number;
  wasted_spend_usd: number;
  geos: GeoStats[];
}

export interface PretargetingConfig {
  name: string;
  description: string;
  priority: number;
  targeting: {
    formats: string[];
    sizes: {
      included: string[];
      total_count: number;
    };
    geos: {
      included: string[];
      excluded: string[];
      included_count: number;
    };
  };
  estimated_impact: {
    impressions: number;
    spend_usd: number;
    waste_reduction_pct: number;
  };
}

export interface PretargetingResponse {
  config_limit: number;
  summary: string;
  total_waste_reduction_pct: number;
  configs: PretargetingConfig[];
}

// Individual optimization recommendation
export interface PretargetingRecommendation {
  id: string;
  type: 'size_mismatch' | 'config_underperforming' | 'opportunity' | 'geo_waste';
  title: string;
  description: string;
  reasoning?: string;
  estimated_savings?: {
    qps_per_day: number;
    usd_per_month?: number;
  };
  data?: {
    sizes?: string[];
    geos?: string[];
    billing_id?: string;
    config_name?: string;
    current_win_rate?: number;
    avg_win_rate?: number;
  };
}

export interface QPSSummaryResponse {
  period_days: number;
  size_coverage: {
    coverage_rate_pct: number;
    sizes_covered: number;
    sizes_missing: number;
    wasted_qps: number;
  };
  geo_efficiency: {
    geos_analyzed: number;
    geos_to_exclude: number;
    geos_to_monitor: number;
    waste_pct: number;
    wasted_spend_usd: number;
  };
  action_items: {
    sizes_to_block: number;
    sizes_to_consider: number;
    geos_to_exclude: number;
  };
  estimated_savings: {
    geo_waste_monthly_usd: number;
  };
}

export async function getQPSSizeCoverage(days: number = 7, billingId?: string): Promise<SizeCoverageResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  return fetchApi<SizeCoverageResponse>(`/analytics/size-coverage?${params.toString()}`);
}

export async function getGeoWaste(days: number = 7): Promise<GeoWasteResponse> {
  return fetchApi<GeoWasteResponse>(`/analytics/geo-waste?days=${days}`);
}

export async function getPretargetingRecommendations(
  days: number = 7,
  maxConfigs: number = 10
): Promise<PretargetingResponse> {
  return fetchApi<PretargetingResponse>(
    `/analytics/pretargeting-recommendations?days=${days}&max_configs=${maxConfigs}`
  );
}

export async function getQPSSummary(days: number = 7): Promise<QPSSummaryResponse> {
  return fetchApi<QPSSummaryResponse>(`/analytics/qps-summary?days=${days}`);
}

// Spend stats for CPM display
export interface SpendStatsResponse {
  period_days: number;
  total_impressions: number;
  total_spend_usd: number;
  avg_cpm_usd: number | null;
  has_spend_data: boolean;
}

export async function getSpendStats(days: number = 7, billingId?: string): Promise<SpendStatsResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  return fetchApi<SpendStatsResponse>(`/analytics/spend-stats?${params.toString()}`);
}

// =============================================================================
// RTB Funnel Analytics API (Phase 28)
// =============================================================================

export interface RTBFunnelSummary {
  has_data: boolean;
  message?: string;
  total_bid_requests?: number;
  total_reached_queries: number;
  total_bids?: number;
  total_impressions: number;
  pretargeting_filter_rate?: number;
  reach_rate?: number;
  win_rate: number;
  bid_rate?: number;
  waste_rate?: number;
}

export interface PublisherPerformance {
  publisher_id: string;
  publisher_name: string;
  bid_requests?: number;
  reached_queries: number;
  bids?: number;
  impressions: number;
  pretargeting_filter_rate?: number;
  win_rate: number;
  bid_rate?: number;
}

export interface GeoPerformance {
  country: string;
  bids?: number;
  reached_queries: number;
  bids_in_auction?: number;
  auctions_won?: number;
  impressions?: number;  // Alternative to auctions_won
  win_rate: number;
  auction_participation_rate?: number;
  creative_count?: number;
}

export interface CreativePerformance {
  creative_id: string;
  bids: number;
  reached_queries: number;
  bids_in_auction: number;
  auctions_won: number;
  win_rate: number;
  countries: string[];
}

export interface RTBFunnelResponse {
  has_data: boolean;
  funnel: RTBFunnelSummary;
  publishers: PublisherPerformance[];
  geos: GeoPerformance[];
  creatives?: CreativePerformance[];
  data_sources: {
    bids_per_pub_available?: boolean;
    adx_metrics_available?: boolean;
    publishers_count?: number;
    geos_count?: number;
    creatives_count?: number;
    publisher_count?: number;
    country_count?: number;
    period_days?: number;
  };
}

// RTB Funnel functions moved to ./api/analytics.ts

// RTB Settings API

export interface RTBEndpointItem {
  endpoint_id: string;
  url: string;
  maximum_qps: number | null;
  trading_location: string | null;
  bid_protocol: string | null;
}

export interface RTBEndpointsResponse {
  bidder_id: string;
  account_name: string | null;
  endpoints: RTBEndpointItem[];
  total_qps_allocated: number;
  qps_current: number | null;
  synced_at: string | null;
}

export interface SyncEndpointsResponse {
  status: string;
  endpoints_synced: number;
  bidder_id: string;
}

export async function getRTBEndpoints(params?: {
  buyer_id?: string;
  service_account_id?: string;  // Deprecated, use buyer_id
}): Promise<RTBEndpointsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.service_account_id) searchParams.set("service_account_id", params.service_account_id);
  const query = searchParams.toString();
  return fetchApi<RTBEndpointsResponse>(`/settings/endpoints${query ? `?${query}` : ""}`);
}

export async function syncRTBEndpoints(params?: {
  service_account_id?: string;
}): Promise<SyncEndpointsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.service_account_id) searchParams.set("service_account_id", params.service_account_id);
  const query = searchParams.toString();
  return fetchApi<SyncEndpointsResponse>(`/settings/endpoints/sync${query ? `?${query}` : ""}`, {
    method: "POST",
  });
}

// Pretargeting Configs API

export interface PretargetingConfigResponse {
  config_id: string;
  bidder_id: string;
  billing_id: string | null;
  display_name: string | null;
  user_name: string | null;
  state: 'ACTIVE' | 'SUSPENDED';
  included_formats: string[] | null;
  included_platforms: string[] | null;
  included_sizes: string[] | null;
  included_geos: string[] | null;
  excluded_geos: string[] | null;
  synced_at: string | null;
}

export interface SyncPretargetingResponse {
  status: string;
  configs_synced: number;
  bidder_id: string;
}

export async function getPretargetingConfigs(params?: {
  buyer_id?: string;
  service_account_id?: string;  // Deprecated, use buyer_id
}): Promise<PretargetingConfigResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.service_account_id) searchParams.set("service_account_id", params.service_account_id);
  const query = searchParams.toString();
  return fetchApi<PretargetingConfigResponse[]>(`/settings/pretargeting${query ? `?${query}` : ""}`);
}

export async function syncPretargetingConfigs(params?: {
  service_account_id?: string;
}): Promise<SyncPretargetingResponse> {
  const searchParams = new URLSearchParams();
  if (params?.service_account_id) searchParams.set("service_account_id", params.service_account_id);
  const query = searchParams.toString();
  return fetchApi<SyncPretargetingResponse>(`/settings/pretargeting/sync${query ? `?${query}` : ""}`, {
    method: "POST",
  });
}

export async function setPretargetingName(
  billingId: string,
  userName: string
): Promise<{ status: string; billing_id: string; user_name: string }> {
  return fetchApi<{ status: string; billing_id: string; user_name: string }>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/name`,
    {
      method: "POST",
      body: JSON.stringify({ user_name: userName }),
    }
  );
}

// Config Breakdown API

export type ConfigBreakdownType = 'size' | 'geo' | 'publisher' | 'creative';

export interface ConfigBreakdownItem {
  name: string;
  reached: number;
  impressions: number;
  win_rate: number;
  waste_rate: number;
}

export interface ConfigBreakdownResponse {
  billing_id: string;
  breakdown_by: ConfigBreakdownType;
  breakdown: ConfigBreakdownItem[];
  is_aggregate?: boolean;
  no_data_reason?: string;  // Explains why breakdown data is missing
}

export async function getConfigBreakdown(
  billingId: string,
  by: ConfigBreakdownType = 'size'
): Promise<ConfigBreakdownResponse> {
  return fetchApi<ConfigBreakdownResponse>(
    `/analytics/rtb-funnel/configs/${encodeURIComponent(billingId)}/breakdown?by=${by}`
  );
}

// Gmail Import API

export interface GmailImportHistoryItem {
  timestamp: string;
  success: boolean;
  files_imported: number;
  emails_processed: number;
  error: string | null;
}

export interface GmailStatus {
  configured: boolean;
  authorized: boolean;
  last_run: string | null;
  last_success: string | null;
  last_error: string | null;
  total_imports: number;
  recent_history: GmailImportHistoryItem[];
}

export interface GmailImportResult {
  success: boolean;
  emails_processed: number;
  files_imported: number;
  files: string[];
  errors: string[];
}

export async function getGmailStatus(): Promise<GmailStatus> {
  return fetchApi<GmailStatus>("/gmail/status");
}

export async function triggerGmailImport(): Promise<GmailImportResult> {
  return fetchApi<GmailImportResult>("/gmail/import", {
    method: "POST",
  });
}

// =============================================================================
// Upload Tracking API
// =============================================================================

export interface DailyUploadSummary {
  upload_date: string;
  total_uploads: number;
  successful_uploads: number;
  failed_uploads: number;
  total_rows_written: number;
  total_file_size_mb: number;
  avg_rows_per_upload: number;
  min_rows: number | null;
  max_rows: number | null;
  has_anomaly: boolean;
  anomaly_reason: string | null;
}

export interface UploadTrackingResponse {
  daily_summaries: DailyUploadSummary[];
  total_days: number;
  total_uploads: number;
  total_rows: number;
  days_with_anomalies: number;
}

export interface ImportHistoryItem {
  batch_id: string;
  filename: string | null;
  imported_at: string;
  rows_read: number;
  rows_imported: number;
  rows_skipped: number;
  rows_duplicate: number;
  date_range_start: string | null;
  date_range_end: string | null;
  total_spend_usd: number;
  file_size_mb: number;
  status: string;
  error_message: string | null;
}

export async function getUploadTracking(days: number = 30): Promise<UploadTrackingResponse> {
  return fetchApi<UploadTrackingResponse>(`/uploads/tracking?days=${days}`);
}

export async function getImportHistory(
  limit: number = 50,
  offset: number = 0
): Promise<ImportHistoryItem[]> {
  return fetchApi<ImportHistoryItem[]>(`/uploads/history?limit=${limit}&offset=${offset}`);
}

// =============================================================================
// Pretargeting History API
// =============================================================================

export interface PretargetingHistoryItem {
  id: number;
  config_id: string;
  bidder_id: string;
  change_type: string;
  field_changed: string | null;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: string | null;
  change_source: string;
}

export async function getPretargetingHistory(params?: {
  config_id?: string;
  billing_id?: string;
  days?: number;
}): Promise<PretargetingHistoryItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.config_id) searchParams.set("config_id", params.config_id);
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (params?.days) searchParams.set("days", String(params.days));

  const query = searchParams.toString();
  return fetchApi<PretargetingHistoryItem[]>(
    `/settings/pretargeting/history${query ? `?${query}` : ""}`
  );
}

// =============================================================================
// Newly Uploaded Creatives API
// =============================================================================

export interface NewlyUploadedCreative {
  id: string;
  name: string | null;
  format: string;
  approval_status: string | null;
  width: number | null;
  height: number | null;
  canonical_size: string | null;
  final_url: string | null;
  first_seen_at: string | null;
  first_import_batch_id: string | null;
  total_spend_usd: number;
  total_impressions: number;
}

export interface NewlyUploadedCreativesResponse {
  creatives: NewlyUploadedCreative[];
  total_count: number;
  period_start: string;
  period_end: string;
}

export async function getNewlyUploadedCreatives(params?: {
  days?: number;
  limit?: number;
  format?: string;
}): Promise<NewlyUploadedCreativesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.format) searchParams.set("format", params.format);

  const query = searchParams.toString();
  return fetchApi<NewlyUploadedCreativesResponse>(
    `/creatives/newly-uploaded${query ? `?${query}` : ""}`
  );
}

// =============================================================================
// Pretargeting Snapshots & Comparisons
// =============================================================================

export interface PretargetingSnapshot {
  id: number;
  billing_id: string;
  snapshot_name: string | null;
  snapshot_type: string;
  state: string | null;
  included_formats: string | null;
  included_platforms: string | null;
  included_sizes: string | null;
  included_geos: string | null;
  excluded_geos: string | null;
  total_impressions: number;
  total_clicks: number;
  total_spend_usd: number;
  days_tracked: number;
  avg_daily_impressions: number | null;
  avg_daily_spend_usd: number | null;
  ctr_pct: number | null;
  cpm_usd: number | null;
  created_at: string;
  notes: string | null;
}

export interface SnapshotComparison {
  id: number;
  billing_id: string;
  comparison_name: string;
  before_snapshot_id: number;
  after_snapshot_id: number | null;
  before_start_date: string;
  before_end_date: string;
  after_start_date: string | null;
  after_end_date: string | null;
  impressions_delta: number | null;
  impressions_delta_pct: number | null;
  spend_delta_usd: number | null;
  spend_delta_pct: number | null;
  ctr_delta_pct: number | null;
  cpm_delta_pct: number | null;
  status: string;
  conclusion: string | null;
  created_at: string;
  completed_at: string | null;
}

export async function createSnapshot(params: {
  billing_id: string;
  snapshot_name?: string;
  notes?: string;
}): Promise<PretargetingSnapshot> {
  return fetchApi<PretargetingSnapshot>("/settings/pretargeting/snapshot", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getSnapshots(params?: {
  billing_id?: string;
  limit?: number;
}): Promise<PretargetingSnapshot[]> {
  const searchParams = new URLSearchParams();
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const query = searchParams.toString();
  return fetchApi<PretargetingSnapshot[]>(
    `/settings/pretargeting/snapshots${query ? `?${query}` : ""}`
  );
}

export async function createComparison(params: {
  billing_id: string;
  comparison_name: string;
  before_snapshot_id: number;
  before_start_date: string;
  before_end_date: string;
}): Promise<SnapshotComparison> {
  return fetchApi<SnapshotComparison>("/settings/pretargeting/comparison", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getComparisons(params?: {
  billing_id?: string;
  status?: string;
  limit?: number;
}): Promise<SnapshotComparison[]> {
  const searchParams = new URLSearchParams();
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const query = searchParams.toString();
  return fetchApi<SnapshotComparison[]>(
    `/settings/pretargeting/comparisons${query ? `?${query}` : ""}`
  );
}

// =============================================================================
// Pretargeting Pending Changes API (Local Changes - NO Google API Writes)
// =============================================================================

export interface PendingChange {
  id: number;
  billing_id: string;
  config_id: string;
  change_type: string;
  field_name: string;
  value: string;
  reason: string | null;
  estimated_qps_impact: number | null;
  created_at: string;
  created_by: string | null;
  status: string;
}

export interface ConfigDetail {
  config_id: string;
  billing_id: string;
  display_name: string | null;
  user_name: string | null;
  state: string;
  included_formats: string[];
  included_platforms: string[];
  included_sizes: string[];
  included_geos: string[];
  excluded_geos: string[];
  synced_at: string | null;
  pending_changes: PendingChange[];
  effective_sizes: string[];
  effective_geos: string[];
  effective_formats: string[];
}

export async function createPendingChange(params: {
  billing_id: string;
  change_type: string;
  field_name: string;
  value: string;
  reason?: string;
  estimated_qps_impact?: number;
}): Promise<PendingChange> {
  return fetchApi<PendingChange>("/settings/pretargeting/pending-change", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getPendingChanges(params?: {
  billing_id?: string;
  status?: string;
  limit?: number;
}): Promise<PendingChange[]> {
  const searchParams = new URLSearchParams();
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (params?.status) searchParams.set("status", params.status || "pending");
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const query = searchParams.toString();
  return fetchApi<PendingChange[]>(
    `/settings/pretargeting/pending-changes${query ? `?${query}` : ""}`
  );
}

export async function cancelPendingChange(changeId: number): Promise<{ status: string; id: number }> {
  return fetchApi<{ status: string; id: number }>(
    `/settings/pretargeting/pending-change/${changeId}`,
    { method: "DELETE" }
  );
}

export async function markChangeApplied(changeId: number): Promise<{ status: string; id: number }> {
  return fetchApi<{ status: string; id: number }>(
    `/settings/pretargeting/pending-change/${changeId}/mark-applied`,
    { method: "POST" }
  );
}

export async function getPretargetingConfigDetail(billingId: string): Promise<ConfigDetail> {
  return fetchApi<ConfigDetail>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/detail`
  );
}

// =============================================================================
// Pretargeting Write Operations (Push to Google API)
// =============================================================================

export interface ApplyChangeResponse {
  status: string;
  change_id: number;
  dry_run: boolean;
  message: string;
  updated_config?: PretargetingConfigResponse;
}

export interface ApplyAllResponse {
  status: string;
  dry_run: boolean;
  changes_applied: number;
  changes_failed: number;
  message: string;
}

export interface SuspendActivateResponse {
  status: string;
  billing_id: string;
  new_state: string;
  message: string;
}

export interface RollbackResponse {
  status: string;
  dry_run: boolean;
  snapshot_id: number;
  changes_made: string[];
  message: string;
}

/**
 * Apply a single pending change to Google Authorized Buyers.
 * Set dry_run=true (default) to preview without making changes.
 */
export async function applyPendingChange(
  billingId: string,
  changeId: number,
  dryRun: boolean = true
): Promise<ApplyChangeResponse> {
  return fetchApi<ApplyChangeResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/apply`,
    {
      method: "POST",
      body: JSON.stringify({ change_id: changeId, dry_run: dryRun }),
    }
  );
}

/**
 * Apply all pending changes for a billing_id to Google.
 * Set dry_run=true (default) to preview without making changes.
 */
export async function applyAllPendingChanges(
  billingId: string,
  dryRun: boolean = true
): Promise<ApplyAllResponse> {
  return fetchApi<ApplyAllResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/apply-all?dry_run=${dryRun}`,
    { method: "POST" }
  );
}

/**
 * Suspend a pretargeting configuration.
 * Creates an auto-snapshot before suspending for easy rollback.
 * WARNING: This affects live bidding!
 */
export async function suspendPretargeting(billingId: string): Promise<SuspendActivateResponse> {
  return fetchApi<SuspendActivateResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/suspend`,
    { method: "POST" }
  );
}

/**
 * Activate a suspended pretargeting configuration.
 * WARNING: This affects live bidding!
 */
export async function activatePretargeting(billingId: string): Promise<SuspendActivateResponse> {
  return fetchApi<SuspendActivateResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/activate`,
    { method: "POST" }
  );
}

/**
 * Rollback a pretargeting config to a previous snapshot state.
 * Set dry_run=true (default) to preview what would change.
 */
export async function rollbackPretargeting(
  billingId: string,
  snapshotId: number,
  dryRun: boolean = true
): Promise<RollbackResponse> {
  return fetchApi<RollbackResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/rollback`,
    {
      method: "POST",
      body: JSON.stringify({ snapshot_id: snapshotId, dry_run: dryRun }),
    }
  );
}

// =============================================================================
// App/Publisher Drill-Down API
// =============================================================================

export interface AppDrilldownSizeItem {
  size: string;
  format: string;
  reached: number;
  impressions: number;
  clicks: number;
  spend_usd: number;
  win_rate: number;
  waste_pct: number;
  pct_of_traffic: number;
  is_wasteful: boolean;
}

export interface AppDrilldownCountryItem {
  country: string;
  reached: number;
  impressions: number;
  clicks: number;
  spend_usd: number;
  win_rate: number;
  pct_of_traffic: number;
}

export interface AppDrilldownCreativeItem {
  creative_id: string;
  size: string;
  format: string;
  reached: number;
  impressions: number;
  clicks: number;
  spend_usd: number;
  win_rate: number;
  pct_of_traffic: number;
}

export interface AppDrilldownWasteInsight {
  type: string;
  value: string;
  message: string;
  wasted_queries: number;
  recommendation: string;
}

export interface AppDrilldownBidFilteringItem {
  reason: string;
  bids_filtered: number;
  bids_passed: number;
  pct_of_filtered: number;
  opportunity_cost_usd: number;
}

export interface AppDrilldownResponse {
  app_name: string;
  app_id?: string;
  has_data: boolean;
  message?: string;
  period_days?: number;
  summary?: {
    total_reached: number;
    total_impressions: number;
    total_clicks: number;
    total_spend_usd: number;
    win_rate: number;
    waste_rate: number;
    days_with_data: number;
    creative_count: number;
    country_count: number;
  };
  by_size?: AppDrilldownSizeItem[];
  by_country?: AppDrilldownCountryItem[];
  by_creative?: AppDrilldownCreativeItem[];
  waste_insight?: AppDrilldownWasteInsight;
  bid_filtering?: AppDrilldownBidFilteringItem[];
}

export async function getAppDrilldown(
  appName: string,
  billingId?: string,
  days: number = 7
): Promise<AppDrilldownResponse> {
  const params = new URLSearchParams();
  params.set("app_name", appName);
  if (billingId) params.set("billing_id", billingId);
  params.set("days", days.toString());
  return fetchApi<AppDrilldownResponse>(`/analytics/app-drilldown?${params.toString()}`);
}

// =============================================================================
// Authentication API
// =============================================================================

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
}

// Note: Login is handled by OAuth2 Proxy (Google Auth) - no password-based login.
// Login and changePassword functions have been removed.

export interface AuthCheckResponse {
  authenticated: boolean;
  auth_method?: string;
  user: AuthUser | null;
}

export interface UserInfo {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
  permissions: string[];
}

export async function logout(): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>("/auth/logout", {
    method: "POST",
  });
}

export async function checkAuth(): Promise<AuthCheckResponse> {
  return fetchApi<AuthCheckResponse>("/auth/check");
}

export async function getCurrentUser(): Promise<UserInfo> {
  return fetchApi<UserInfo>("/auth/me");
}

// =============================================================================
// Admin API
// =============================================================================

export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
  default_language: string | null;
}

export interface CreateUserRequest {
  email: string;
  display_name?: string;
  role?: string;
  default_language?: string;
}

export interface CreateUserResponse {
  status: string;
  user_id: string;
  email: string;
  message: string;
}

export interface UserPermission {
  id: string;
  user_id: string;
  service_account_id: string;
  permission_level: string;
  granted_by: string | null;
  granted_at: string | null;
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: string | null;
  ip_address: string | null;
  created_at: string | null;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  multi_user_enabled: boolean;
}

export async function getAdminUsers(params?: {
  active_only?: boolean;
  role?: string;
}): Promise<AdminUser[]> {
  const searchParams = new URLSearchParams();
  if (params?.active_only) searchParams.set("active_only", "true");
  if (params?.role) searchParams.set("role", params.role);
  const query = searchParams.toString();
  return fetchApi<AdminUser[]>(`/admin/users${query ? `?${query}` : ""}`);
}

export async function createUser(request: CreateUserRequest): Promise<CreateUserResponse> {
  return fetchApi<CreateUserResponse>("/admin/users", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getAdminUser(userId: string): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`);
}

export async function updateAdminUser(
  userId: string,
  updates: {
    display_name?: string;
    role?: string;
    is_active?: boolean;
    default_language?: string;
  }
): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deactivateUser(userId: string): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>(
    `/admin/users/${encodeURIComponent(userId)}`,
    { method: "DELETE" }
  );
}

export async function getUserPermissions(userId: string): Promise<UserPermission[]> {
  return fetchApi<UserPermission[]>(`/admin/users/${encodeURIComponent(userId)}/permissions`);
}

export async function grantPermission(
  userId: string,
  serviceAccountId: string,
  permissionLevel: string
): Promise<UserPermission> {
  return fetchApi<UserPermission>(`/admin/users/${encodeURIComponent(userId)}/permissions`, {
    method: "POST",
    body: JSON.stringify({
      service_account_id: serviceAccountId,
      permission_level: permissionLevel,
    }),
  });
}

export async function revokePermission(
  userId: string,
  serviceAccountId: string
): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>(
    `/admin/users/${encodeURIComponent(userId)}/permissions/${encodeURIComponent(serviceAccountId)}`,
    { method: "DELETE" }
  );
}

export async function getAuditLogs(params?: {
  user_id?: string;
  action?: string;
  resource_type?: string;
  days?: number;
  limit?: number;
  offset?: number;
}): Promise<AuditLogEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.user_id) searchParams.set("user_id", params.user_id);
  if (params?.action) searchParams.set("action", params.action);
  if (params?.resource_type) searchParams.set("resource_type", params.resource_type);
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<AuditLogEntry[]>(`/admin/audit-log${query ? `?${query}` : ""}`);
}

export async function getAdminStats(): Promise<AdminStats> {
  return fetchApi<AdminStats>("/admin/stats");
}

export async function getSystemSettings(): Promise<Record<string, string>> {
  return fetchApi<Record<string, string>>("/admin/settings");
}

export async function updateSystemSetting(
  key: string,
  value: string
): Promise<{ status: string; key: string; value: string }> {
  return fetchApi<{ status: string; key: string; value: string }>(
    `/admin/settings/${encodeURIComponent(key)}`,
    {
      method: "PUT",
      body: JSON.stringify({ value }),
    }
  );
}

// =============================================================================
// GCP / ADC Mode API
// =============================================================================

export interface GCPStatusResponse {
  gcp_mode: boolean;
  adc_available: boolean;
  service_account_email: string | null;
  project_id: string | null;
  message: string;
}

export interface GCPDiscoveryRequest {
  bidder_id: string;
}

export interface GCPDiscoveryResponse {
  success: boolean;
  bidder_ids: string[];
  buyer_seats_count: number;
  message: string;
}

export async function getGCPStatus(): Promise<GCPStatusResponse> {
  return fetchApi<GCPStatusResponse>("/config/gcp-status");
}

export async function discoverViaADC(bidderId: string): Promise<GCPDiscoveryResponse> {
  return fetchApi<GCPDiscoveryResponse>("/config/gcp-discover", {
    method: "POST",
    body: JSON.stringify({ bidder_id: bidderId }),
  });
}

// =============================================================================
// Language Detection API (Creative Geo Display)
// =============================================================================

import type {
  LanguageDetectionResponse,
  GeoMismatchResponse,
  ManualLanguageUpdate,
} from "@/types/api";

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
