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

export async function getQPSSizeCoverage(days: number = 7, billingId?: string): Promise<SizeCoverageResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  return fetchApi<SizeCoverageResponse>(`/analytics/size-coverage?${params.toString()}`);
}

export async function getGeoWaste(days: number = 7): Promise<GeoWasteResponse> {
  return fetchApi<GeoWasteResponse>(`/analytics/geo-waste?days=${days}`);
}

export async function getQPSSummary(days: number = 7): Promise<QPSSummaryResponse> {
  return fetchApi<QPSSummaryResponse>(`/analytics/qps-summary?days=${days}`);
}

export async function getSpendStats(days: number = 7, billingId?: string): Promise<SpendStatsResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (billingId) params.set("billing_id", billingId);
  return fetchApi<SpendStatsResponse>(`/analytics/spend-stats?${params.toString()}`);
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
  funnel: RTBFunnelSummary;
  publishers: PublisherPerformance[];
  geos: GeoPerformance[];
  data_sources: {
    bids_per_pub_available?: boolean;
    adx_metrics_available?: boolean;
    publishers_count?: number;
    geos_count?: number;
    period_days?: number;
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
}

// =============================================================================
// RTB Funnel API
// =============================================================================

export async function getRTBFunnel(days: number = 7): Promise<RTBFunnelResponse> {
  return fetchApi<RTBFunnelResponse>(`/analytics/rtb-funnel?days=${days}`);
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
  days: number = 7
): Promise<ConfigPerformanceResponse> {
  return fetchApi<ConfigPerformanceResponse>(
    `/analytics/rtb-funnel/configs?days=${days}`
  );
}
