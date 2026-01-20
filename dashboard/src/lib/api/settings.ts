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
  included_operating_systems: string[] | null;
  synced_at: string | null;
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
