import { fetchApi } from "./core";


export interface ConversionHealthIngestion {
  total_events: number;
  max_event_ts: string | null;
  last_ingested_at: string | null;
  lag_hours: number | null;
}


export interface ConversionHealthAggregation {
  total_rows: number;
  max_agg_date: string | null;
  last_aggregated_at: string | null;
  lag_days: number | null;
}


export interface ConversionHealthResponse {
  state: string;
  buyer_id: string | null;
  ingestion: ConversionHealthIngestion;
  aggregation: ConversionHealthAggregation;
  checked_at: string;
}

export interface ConversionReadinessResponse {
  state: string;
  buyer_id: string | null;
  window_days: number;
  freshness_threshold_hours: number;
  accepted_total: number;
  rejected_total: number;
  active_sources: number;
  ingestion_lag_hours: number | null;
  ingestion_fresh: boolean;
  reasons: string[];
  checked_at: string;
}


export interface ConversionIngestionStatsRow {
  metric_date: string | null;
  source_type: string;
  accepted_count: number;
  rejected_count: number;
}


export interface ConversionIngestionStatsResponse {
  days: number;
  source_type: string | null;
  buyer_id: string | null;
  accepted_total: number;
  rejected_total: number;
  rows: ConversionIngestionStatsRow[];
}


export async function getConversionHealth(params?: {
  buyer_id?: string;
}): Promise<ConversionHealthResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<ConversionHealthResponse>(`/conversions/health${query ? `?${query}` : ""}`);
}

export async function getConversionReadiness(params?: {
  buyer_id?: string;
  days?: number;
  freshness_hours?: number;
}): Promise<ConversionReadinessResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof params?.days === "number") searchParams.set("days", String(params.days));
  if (typeof params?.freshness_hours === "number") {
    searchParams.set("freshness_hours", String(params.freshness_hours));
  }
  const query = searchParams.toString();
  return fetchApi<ConversionReadinessResponse>(
    `/conversions/readiness${query ? `?${query}` : ""}`,
  );
}


export async function getConversionIngestionStats(params?: {
  buyer_id?: string;
  source_type?: string;
  days?: number;
}): Promise<ConversionIngestionStatsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.source_type) searchParams.set("source_type", params.source_type);
  if (typeof params?.days === "number") searchParams.set("days", String(params.days));
  const query = searchParams.toString();
  return fetchApi<ConversionIngestionStatsResponse>(
    `/conversions/ingestion/stats${query ? `?${query}` : ""}`,
  );
}
