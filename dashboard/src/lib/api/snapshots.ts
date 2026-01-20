import { fetchApi } from "./core";

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
