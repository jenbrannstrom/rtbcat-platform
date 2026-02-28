import { fetchApi } from "./core";

export interface DailyUploadSummary {
  upload_date: string;
  total_uploads: number;
  successful_uploads: number;
  failed_uploads: number;
  total_rows_written: number;
  total_file_size_mb: number;
  avg_rows_per_upload: number;
  min_rows?: number | null;
  max_rows?: number | null;
  has_anomaly: boolean;
  anomaly_reason?: string | null;
}

export interface UploadTrackingResponse {
  daily_summaries: DailyUploadSummary[];
  total_days: number;
  total_uploads: number;
  total_rows: number;
  days_with_anomalies: number;
}

export interface ImportMatrixCell {
  csv_type: string;
  status: "pass" | "fail" | "not_imported";
  source?: "manual" | "gmail-auto" | "gmail-manual" | null;
  last_imported_at?: string | null;
  error_summary?: string | null;
}

export interface AccountImportMatrix {
  buyer_id: string;
  bidder_id: string;
  display_name?: string | null;
  csv_types: ImportMatrixCell[];
}

export interface ImportTrackingMatrixResponse {
  accounts: AccountImportMatrix[];
  expected_csv_types: string[];
  total_accounts: number;
  pass_count: number;
  fail_count: number;
  not_imported_count: number;
}

export interface ImportHistoryItem {
  batch_id: string;
  filename?: string | null;
  imported_at: string;
  rows_read: number;
  rows_imported: number;
  rows_skipped: number;
  rows_duplicate: number;
  date_range_start?: string | null;
  date_range_end?: string | null;
  total_spend_usd: number;
  file_size_mb: number;
  status: string;
  error_message?: string | null;
  bidder_id?: string | null;
  billing_ids_found?: string[] | null;
  columns_found?: string[] | null;
  columns_missing?: string[] | null;
  import_trigger?: string | null;
}

export interface PretargetingHistoryItem {
  id: number;
  config_id: string;
  bidder_id: string;
  change_type: string;
  field_changed?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  changed_at: string;
  changed_by?: string | null;
  change_source: string;
  rollback_context?: {
    snapshot_id?: number;
    proposal_id?: string | null;
    reason?: string | null;
    initiated_by?: string | null;
    changes_made?: string[];
  } | null;
}

export interface NewlyUploadedCreative {
  id: string;
  name: string;
  format: string;
  approval_status: string;
  width: number | null;
  height: number | null;
  canonical_size: string | null;
  final_url: string | null;
  first_seen_at: string;
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

export type FreshnessStatus = "imported" | "missing";

export interface FreshnessSummary {
  total_cells: number;
  imported_count: number;
  missing_count: number;
  coverage_pct: number;
}

export interface DataFreshnessGridResponse {
  dates: string[];
  csv_types: string[];
  cells: Record<string, Record<string, FreshnessStatus>>;
  summary: FreshnessSummary;
  lookback_days: number;
}

export async function getDataFreshnessGrid(
  days: number = 7,
  buyerId?: string
): Promise<DataFreshnessGridResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) {
    params.set("buyer_id", buyerId);
  }
  return fetchApi<DataFreshnessGridResponse>(`/uploads/data-freshness?${params.toString()}`);
}

export async function getUploadTracking(days: number = 30): Promise<UploadTrackingResponse> {
  return fetchApi<UploadTrackingResponse>(`/uploads/tracking?days=${days}`);
}

export async function getImportTrackingMatrix(
  days: number = 30,
  buyerId?: string
): Promise<ImportTrackingMatrixResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (buyerId) {
    params.set("buyer_id", buyerId);
  }
  return fetchApi<ImportTrackingMatrixResponse>(`/uploads/import-matrix?${params.toString()}`);
}

export async function getImportHistory(
  limit: number = 50,
  offset: number = 0,
  bidderId?: string
): Promise<ImportHistoryItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (bidderId) {
    params.set("bidder_id", bidderId);
  }

  return fetchApi<ImportHistoryItem[]>(`/uploads/history?${params.toString()}`);
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

export async function getNewlyUploadedCreatives(params?: {
  days?: number;
  limit?: number;
  format?: string;
  buyer_id?: string;
}): Promise<NewlyUploadedCreativesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.format) searchParams.set("format", params.format);
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);

  const query = searchParams.toString();
  return fetchApi<NewlyUploadedCreativesResponse>(
    `/creatives/newly-uploaded${query ? `?${query}` : ""}`
  );
}
