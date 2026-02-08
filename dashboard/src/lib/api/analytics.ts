/**
 * Analytics API module.
 * Handles waste analysis, QPS, RTB funnel, performance metrics.
 */

import { fetchApi, API_BASE } from "./core";
import type {
  WasteReport,
  SizeCoverage,
  ImportTrafficResponse,
  BatchPerformanceResponse,
  PerformancePeriod,
} from "@/types/api";
import type { ImportResponse } from "@/lib/types/import";

// =============================================================================
// Waste Analysis
// =============================================================================

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

// =============================================================================
// Performance Metrics
// =============================================================================

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

// =============================================================================
// QPS Analytics Types
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

export interface SpendStatsResponse {
  period_days: number;
  total_impressions: number;
  total_spend_usd: number;
  avg_cpm_usd: number | null;
  has_spend_data: boolean;
}

// =============================================================================
// QPS Analytics API
// =============================================================================

export async function getQPSSizeCoverage(
  days: number = 7,
  billingId?: string,
  buyerId?: string
): Promise<SizeCoverageResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  if (buyerId) params.set("buyer_id", buyerId);
  return fetchApi<SizeCoverageResponse>(`/analytics/size-coverage?${params.toString()}`);
}

export async function getGeoWaste(days: number = 7, buyerId?: string): Promise<GeoWasteResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) params.set("buyer_id", buyerId);
  return fetchApi<GeoWasteResponse>(`/analytics/geo-waste?${params.toString()}`);
}

export async function getQPSSummary(days: number = 7, buyerId?: string): Promise<QPSSummaryResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) params.set("buyer_id", buyerId);
  return fetchApi<QPSSummaryResponse>(`/analytics/qps-summary?${params.toString()}`);
}

export async function getSpendStats(days: number = 7, billingId?: string): Promise<SpendStatsResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  return fetchApi<SpendStatsResponse>(`/analytics/spend-stats?${params.toString()}`);
}

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
// RTB Funnel Types
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
  auctions_won?: number;
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
  impressions?: number;
  win_rate: number;
  auction_participation_rate?: number;
  creative_count?: number;
}

export interface RTBFunnelResponse {
  has_data: boolean;
  data_state?: "healthy" | "degraded" | "unavailable";
  fallback_applied?: boolean;
  fallback_reason?: string | null;
  funnel: RTBFunnelSummary;
  publishers: PublisherPerformance[];
  geos: GeoPerformance[];
  coverage?: {
    publisher_rows_available?: boolean;
    geo_rows_available?: boolean;
  };
  data_sources: {
    bids_per_pub_available?: boolean;
    adx_metrics_available?: boolean;
    publishers_count?: number;
    geos_count?: number;
    period_days?: number;
    buyer_filter_applied?: boolean;
    buyer_filter_message?: string | null;
    bidder_id_populated?: boolean;
    buyer_account_id_populated?: boolean;
  };
}

export interface ConfigPerformanceItem {
  billing_id: string;
  name: string | null;
  reached: number;
  impressions: number;
  win_rate_pct: number;
  waste_pct: number;
}

export interface ConfigPerformanceResponse {
  period_days: number;
  total_configs: number;
  configs: ConfigPerformanceItem[];
  data_state?: "healthy" | "degraded" | "unavailable";
  fallback_applied?: boolean;
  fallback_reason?: string | null;
}

// =============================================================================
// RTB Funnel API
// =============================================================================

export async function getRTBFunnel(
  days: number = 7,
  buyerId?: string
): Promise<RTBFunnelResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) params.set('buyer_id', buyerId);
  return fetchApi<RTBFunnelResponse>(`/analytics/home/funnel?${params}`);
}

export async function getRTBPublishers(
  limit: number = 30
): Promise<{ publishers: PublisherPerformance[]; count: number }> {
  return fetchApi<{ publishers: PublisherPerformance[]; count: number }>(
    `/analytics/rtb-funnel/publishers?limit=${limit}`
  );
}

export async function getRTBGeos(
  limit: number = 30
): Promise<{ geos: GeoPerformance[]; count: number }> {
  return fetchApi<{ geos: GeoPerformance[]; count: number }>(
    `/analytics/rtb-funnel/geos?limit=${limit}`
  );
}

export async function getRTBFunnelConfigs(
  days: number = 7,
  buyerId?: string
): Promise<ConfigPerformanceResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) params.set('buyer_id', buyerId);
  return fetchApi<ConfigPerformanceResponse>(
    `/analytics/home/configs?${params}`
  );
}

// =============================================================================
// Recommendations API
// =============================================================================

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

export async function getPretargetingRecommendations(
  days: number = 7,
  maxConfigs: number = 10
): Promise<PretargetingResponse> {
  return fetchApi<PretargetingResponse>(
    `/analytics/pretargeting-recommendations?days=${days}&max_configs=${maxConfigs}`
  );
}
