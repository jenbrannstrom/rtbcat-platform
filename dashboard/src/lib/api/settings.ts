import { fetchApi } from "./core";

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

export interface PretargetingConfigResponse {
  config_id: string;
  bidder_id: string;
  billing_id: string | null;
  display_name: string | null;
  user_name: string | null;
  state: string;
  included_formats: string[] | null;
  included_platforms: string[] | null;
  included_sizes: string[] | null;
  included_geos: string[] | null;
  excluded_geos: string[] | null;
  included_operating_systems?: string[] | null;
  synced_at: string | null;
}

export interface SyncPretargetingResponse {
  status: string;
  configs_synced: number;
  bidder_id: string;
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
  maximum_qps?: number | null;
  publisher_targeting_mode?: string | null;
  publisher_targeting_values?: string[];
  synced_at: string | null;
  pending_changes: PendingChange[];
  effective_sizes: string[];
  effective_geos: string[];
  effective_formats: string[];
  effective_maximum_qps?: number | null;
  effective_publisher_targeting_mode?: string | null;
  effective_publisher_targeting_values?: string[];
}

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

export async function getRTBEndpoints(params?: {
  buyer_id?: string;
  service_account_id?: string;
}): Promise<RTBEndpointsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.service_account_id) {
    searchParams.set("service_account_id", params.service_account_id);
  }
  const query = searchParams.toString();
  return fetchApi<RTBEndpointsResponse>(`/settings/endpoints${query ? `?${query}` : ""}`);
}

export async function syncRTBEndpoints(params?: {
  service_account_id?: string;
}): Promise<SyncEndpointsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.service_account_id) {
    searchParams.set("service_account_id", params.service_account_id);
  }
  const query = searchParams.toString();
  return fetchApi<SyncEndpointsResponse>(`/settings/endpoints/sync${query ? `?${query}` : ""}`, {
    method: "POST",
  });
}

export async function getPretargetingConfigs(params?: {
  buyer_id?: string;
  service_account_id?: string;
}): Promise<PretargetingConfigResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.service_account_id) {
    searchParams.set("service_account_id", params.service_account_id);
  }
  const query = searchParams.toString();
  return fetchApi<PretargetingConfigResponse[]>(
    `/settings/pretargeting${query ? `?${query}` : ""}`,
    { timeoutMs: 10000 }
  );
}

export async function syncPretargetingConfigs(params?: {
  service_account_id?: string;
}): Promise<SyncPretargetingResponse> {
  const searchParams = new URLSearchParams();
  if (params?.service_account_id) {
    searchParams.set("service_account_id", params.service_account_id);
  }
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

export type ConfigBreakdownType = 'size' | 'geo' | 'publisher' | 'creative';

export interface ConfigBreakdownItem {
  name: string;
  target_value?: string;
  spend_usd?: number;
  reached: number;
  impressions: number;
  win_rate: number;
  waste_rate: number;
  data_scope?: "billing" | "buyer_fallback";
  data_source?: string;
  creative_language?: string | null;
  creative_language_code?: string | null;
  target_countries?: string[];
  language_mismatch?: boolean;
  mismatched_countries?: string[];
}

export interface ConfigBreakdownResponse {
  billing_id: string;
  breakdown_by: ConfigBreakdownType;
  breakdown: ConfigBreakdownItem[];
  is_aggregate?: boolean;
  no_data_reason?: string;  // Explains why breakdown data is missing
  data_state?: "healthy" | "degraded" | "unavailable";
  fallback_applied?: boolean;
  fallback_reason?: string | null;
  has_funnel_metrics?: boolean;
}

export interface ConfigCreativesItem {
  id: string;
  name: string;
  format?: string | null;
  width?: number | null;
  height?: number | null;
  serving_countries?: string[];
}

export interface ConfigCreativesResponse {
  creatives: ConfigCreativesItem[];
  message?: string;
}

export async function getConfigBreakdown(
  billingId: string,
  by: ConfigBreakdownType = 'size',
  buyerId?: string,
  days: number = 7
): Promise<ConfigBreakdownResponse> {
  const params = new URLSearchParams({ by, days: String(days) });
  if (buyerId) params.set("buyer_id", buyerId);
  return fetchApi<ConfigBreakdownResponse>(
    `/analytics/rtb-funnel/configs/${encodeURIComponent(billingId)}/breakdown?${params.toString()}`
  );
}

export async function getConfigCreatives(
  billingId: string,
  size?: string,
  buyerId?: string,
  days: number = 30
): Promise<ConfigCreativesResponse> {
  const params = new URLSearchParams();
  if (size) params.set("size", size);
  if (buyerId) params.set("buyer_id", buyerId);
  params.set("days", String(days));
  return fetchApi<ConfigCreativesResponse>(
    `/analytics/rtb-funnel/configs/${encodeURIComponent(billingId)}/creatives?${params.toString()}`
  );
}

export async function getPretargetingConfigDetail(billingId: string): Promise<ConfigDetail> {
  return fetchApi<ConfigDetail>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/detail`
  );
}

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

export async function applyAllPendingChanges(
  billingId: string,
  dryRun: boolean = true
): Promise<ApplyAllResponse> {
  return fetchApi<ApplyAllResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/apply-all?dry_run=${dryRun}`,
    { method: "POST" }
  );
}

export async function suspendPretargeting(billingId: string): Promise<SuspendActivateResponse> {
  return fetchApi<SuspendActivateResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/suspend`,
    { method: "POST" }
  );
}

export async function activatePretargeting(billingId: string): Promise<SuspendActivateResponse> {
  return fetchApi<SuspendActivateResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/activate`,
    { method: "POST" }
  );
}

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

// Publisher list management
export interface PretargetingPublisher {
  publisher_id: string;
  publisher_name?: string | null;
  mode: "BLACKLIST" | "WHITELIST";
  status: "active" | "pending_add" | "pending_remove";
  source: "api_sync" | "user";
  created_at: string;
  updated_at: string;
}

export interface PretargetingPublishersResponse {
  billing_id: string;
  publishers: PretargetingPublisher[];
  count: number;
}

export async function getPretargetingPublishers(
  billingId: string,
  params?: { mode?: string; status?: string }
): Promise<PretargetingPublishersResponse> {
  const searchParams = new URLSearchParams();
  if (params?.mode) searchParams.set("mode", params.mode);
  if (params?.status) searchParams.set("status", params.status);
  const query = searchParams.toString();
  return fetchApi<PretargetingPublishersResponse>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/publishers${query ? `?${query}` : ""}`
  );
}

export async function addPretargetingPublisher(
  billingId: string,
  publisherId: string,
  mode: "BLACKLIST" | "WHITELIST"
): Promise<{ status: string; publisher_id: string; mode: string }> {
  return fetchApi<{ status: string; publisher_id: string; mode: string }>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/publishers`,
    {
      method: "POST",
      body: JSON.stringify({ publisher_id: publisherId, mode }),
    }
  );
}

export async function removePretargetingPublisher(
  billingId: string,
  publisherId: string
): Promise<{ status: string; publisher_id: string }> {
  return fetchApi<{ status: string; publisher_id: string }>(
    `/settings/pretargeting/${encodeURIComponent(billingId)}/publishers/${encodeURIComponent(publisherId)}`,
    { method: "DELETE" }
  );
}

// Note: Publisher changes are applied via the main apply-all endpoint
// The publisher pending changes bar directs users to use "Push to Google"
