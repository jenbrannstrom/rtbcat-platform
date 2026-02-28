import { fetchApi } from "./core";


export interface OptimizerMeta {
  total: number;
  returned: number;
  limit: number;
  offset: number;
  has_more: boolean;
}


export interface OptimizerModelRow {
  model_id: string;
  buyer_id: string;
  name: string;
  description: string | null;
  model_type: string;
  endpoint_url: string | null;
  has_auth_header: boolean;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}


export interface OptimizerModelsResponse {
  rows: OptimizerModelRow[];
  meta: OptimizerMeta;
}


export interface CreateOptimizerModelRequest {
  buyer_id?: string;
  name: string;
  description?: string;
  model_type: "api" | "rules" | "csv";
  endpoint_url?: string;
  auth_header_encrypted?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  is_active?: boolean;
}


export interface UpdateOptimizerModelRequest {
  name?: string;
  description?: string;
  model_type?: "api" | "rules" | "csv";
  endpoint_url?: string;
  auth_header_encrypted?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  is_active?: boolean;
}


export async function getOptimizerModels(params?: {
  buyer_id?: string;
  include_inactive?: boolean;
  limit?: number;
  offset?: number;
}): Promise<OptimizerModelsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof params?.include_inactive === "boolean") {
    searchParams.set("include_inactive", params.include_inactive ? "true" : "false");
  }
  if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<OptimizerModelsResponse>(`/optimizer/models${query ? `?${query}` : ""}`);
}


export async function createOptimizerModel(
  payload: CreateOptimizerModelRequest,
): Promise<OptimizerModelRow> {
  return fetchApi<OptimizerModelRow>("/optimizer/models", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


export async function updateOptimizerModel(
  modelId: string,
  payload: UpdateOptimizerModelRequest,
  params?: { buyer_id?: string },
): Promise<OptimizerModelRow> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<OptimizerModelRow>(
    `/optimizer/models/${encodeURIComponent(modelId)}${query ? `?${query}` : ""}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}


export async function activateOptimizerModel(
  modelId: string,
  params?: { buyer_id?: string },
): Promise<{ model_id: string; is_active: boolean }> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<{ model_id: string; is_active: boolean }>(
    `/optimizer/models/${encodeURIComponent(modelId)}/activate${query ? `?${query}` : ""}`,
    { method: "POST" },
  );
}


export async function deactivateOptimizerModel(
  modelId: string,
  params?: { buyer_id?: string },
): Promise<{ model_id: string; is_active: boolean }> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<{ model_id: string; is_active: boolean }>(
    `/optimizer/models/${encodeURIComponent(modelId)}/deactivate${query ? `?${query}` : ""}`,
    { method: "POST" },
  );
}


export interface OptimizerScoreRow {
  score_id: string;
  model_id: string;
  buyer_id: string;
  billing_id: string;
  country: string;
  publisher_id: string;
  app_id: string;
  score_date: string | null;
  value_score: number;
  confidence: number;
  created_at: string | null;
}


export interface OptimizerScoresResponse {
  rows: OptimizerScoreRow[];
  meta: {
    start_date: string;
    end_date: string;
    total: number;
    returned: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}


export async function listOptimizerSegmentScores(params?: {
  buyer_id?: string;
  model_id?: string;
  days?: number;
  limit?: number;
  offset?: number;
}): Promise<OptimizerScoresResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.model_id) searchParams.set("model_id", params.model_id);
  if (typeof params?.days === "number") searchParams.set("days", String(params.days));
  if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<OptimizerScoresResponse>(`/optimizer/scoring/segments${query ? `?${query}` : ""}`);
}


export interface OptimizerProposalRow {
  proposal_id: string;
  model_id: string;
  buyer_id: string;
  billing_id: string;
  current_qps: number;
  proposed_qps: number;
  delta_qps: number;
  rationale: string;
  status: "draft" | "approved" | "applied" | "rejected" | string;
  created_at: string | null;
  updated_at: string | null;
  applied_at: string | null;
}


export interface OptimizerProposalsResponse {
  rows: OptimizerProposalRow[];
  meta: OptimizerMeta;
}


export interface OptimizerProposalHistoryRow {
  event_id: string;
  proposal_id: string;
  buyer_id: string;
  from_status: string | null;
  to_status: string;
  apply_mode: string | null;
  changed_by: string | null;
  details: Record<string, unknown>;
  created_at: string | null;
}


export interface OptimizerProposalHistoryResponse {
  rows: OptimizerProposalHistoryRow[];
  meta: OptimizerMeta;
}


export async function listOptimizerProposals(params?: {
  buyer_id?: string;
  model_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<OptimizerProposalsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.model_id) searchParams.set("model_id", params.model_id);
  if (params?.status) searchParams.set("status", params.status);
  if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<OptimizerProposalsResponse>(`/optimizer/proposals${query ? `?${query}` : ""}`);
}


export async function listOptimizerProposalHistory(
  proposalId: string,
  params?: { buyer_id?: string; limit?: number; offset?: number },
): Promise<OptimizerProposalHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<OptimizerProposalHistoryResponse>(
    `/optimizer/proposals/${encodeURIComponent(proposalId)}/history${query ? `?${query}` : ""}`,
  );
}


export interface OptimizerScoringRunSummary {
  model_type?: string;
  model_id: string;
  buyer_id: string;
  start_date: string;
  end_date: string;
  event_type?: string | null;
  segments_scanned: number;
  scores_written: number;
}


export interface OptimizerProposalRunSummary {
  model_id: string;
  buyer_id: string;
  days: number;
  min_confidence: number;
  max_delta_pct: number;
  scores_considered: number;
  proposals_created: number;
}


export interface OptimizerScoreAndProposeResponse {
  score_run: OptimizerScoringRunSummary;
  proposal_run: OptimizerProposalRunSummary;
}


export async function runOptimizerScoreAndPropose(params: {
  model_id: string;
  buyer_id?: string;
  days?: number;
  score_limit?: number;
  proposal_limit?: number;
  min_confidence?: number;
  max_delta_pct?: number;
  // Backward-compat aliases; both map to API `days` / `score_limit`.
  scoring_days?: number;
  proposal_days?: number;
  scoring_limit?: number;
}): Promise<OptimizerScoreAndProposeResponse> {
  const searchParams = new URLSearchParams();
  const resolvedDays = params.days ?? params.scoring_days ?? params.proposal_days;
  const resolvedScoreLimit = params.score_limit ?? params.scoring_limit;
  searchParams.set("model_id", params.model_id);
  if (params.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof resolvedDays === "number") searchParams.set("days", String(resolvedDays));
  if (typeof resolvedScoreLimit === "number") searchParams.set("score_limit", String(resolvedScoreLimit));
  if (typeof params.proposal_limit === "number") searchParams.set("proposal_limit", String(params.proposal_limit));
  if (typeof params.min_confidence === "number") searchParams.set("min_confidence", String(params.min_confidence));
  if (typeof params.max_delta_pct === "number") searchParams.set("max_delta_pct", String(params.max_delta_pct));
  return fetchApi<OptimizerScoreAndProposeResponse>(
    `/optimizer/workflows/score-and-propose?${searchParams.toString()}`,
    { method: "POST" },
  );
}


export interface OptimizerModelValidationResponse {
  model_id: string;
  buyer_id: string | null;
  valid: boolean;
  skipped: boolean;
  http_status: number | null;
  message: string;
  response_preview: string | null;
}


export async function validateOptimizerModelEndpoint(
  modelId: string,
  params?: {
    buyer_id?: string;
    timeout_seconds?: number;
    sample_payload?: Record<string, unknown>;
  },
): Promise<OptimizerModelValidationResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof params?.timeout_seconds === "number") {
    searchParams.set("timeout_seconds", String(params.timeout_seconds));
  }
  const query = searchParams.toString();
  return fetchApi<OptimizerModelValidationResponse>(
    `/optimizer/models/${encodeURIComponent(modelId)}/validate${query ? `?${query}` : ""}`,
    {
      method: "POST",
      body:
        params?.sample_payload !== undefined
          ? JSON.stringify({ sample_payload: params.sample_payload })
          : undefined,
    },
  );
}


export interface OptimizerProposalStatusResponse {
  proposal_id: string;
  status: string;
  apply_details?: Record<string, unknown> | null;
}


export async function approveOptimizerProposal(
  proposalId: string,
  params?: { buyer_id?: string },
): Promise<OptimizerProposalStatusResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<OptimizerProposalStatusResponse>(
    `/optimizer/proposals/${encodeURIComponent(proposalId)}/approve${query ? `?${query}` : ""}`,
    { method: "POST" },
  );
}


export async function applyOptimizerProposal(
  proposalId: string,
  params?: { buyer_id?: string; mode?: "queue" | "live" },
): Promise<OptimizerProposalStatusResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  searchParams.set("mode", params?.mode || "queue");
  return fetchApi<OptimizerProposalStatusResponse>(
    `/optimizer/proposals/${encodeURIComponent(proposalId)}/apply?${searchParams.toString()}`,
    { method: "POST" },
  );
}


export async function syncOptimizerProposalApplyStatus(
  proposalId: string,
  params?: { buyer_id?: string },
): Promise<OptimizerProposalRow> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  const query = searchParams.toString();
  return fetchApi<OptimizerProposalRow>(
    `/optimizer/proposals/${encodeURIComponent(proposalId)}/sync-apply-status${query ? `?${query}` : ""}`,
    { method: "POST" },
  );
}


export interface OptimizerEffectiveCpmResponse {
  buyer_id: string;
  billing_id: string | null;
  start_date: string;
  end_date: string;
  days: number;
  impressions: number;
  media_spend_usd: number;
  monthly_hosting_cost_usd: number | null;
  infra_cost_period_usd: number | null;
  media_cpm_usd: number | null;
  infra_cpm_usd: number | null;
  effective_cpm_usd: number | null;
  cost_context_ready: boolean;
}


export async function getOptimizerEffectiveCpm(params?: {
  buyer_id?: string;
  billing_id?: string;
  days?: number;
  start_date?: string;
  end_date?: string;
}): Promise<OptimizerEffectiveCpmResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (typeof params?.days === "number") searchParams.set("days", String(params.days));
  if (params?.start_date) searchParams.set("start_date", params.start_date);
  if (params?.end_date) searchParams.set("end_date", params.end_date);
  const query = searchParams.toString();
  return fetchApi<OptimizerEffectiveCpmResponse>(
    `/optimizer/economics/effective-cpm${query ? `?${query}` : ""}`,
  );
}


export interface OptimizerEfficiencySummaryResponse {
  buyer_id: string;
  billing_id: string | null;
  start_date: string;
  end_date: string;
  days: number;
  spend_usd: number;
  impressions: number;
  bid_requests: number;
  reached_queries: number;
  avg_daily_spend_usd: number;
  avg_allocated_qps: number | null;
  assumed_value_score: number;
  qps_efficiency: number | null;
  assumed_value_per_qps: number | null;
  has_bid_request_data: boolean;
  has_reached_query_data: boolean;
}


export async function getOptimizerEfficiencySummary(params?: {
  buyer_id?: string;
  billing_id?: string;
  days?: number;
  start_date?: string;
  end_date?: string;
}): Promise<OptimizerEfficiencySummaryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (params?.billing_id) searchParams.set("billing_id", params.billing_id);
  if (typeof params?.days === "number") searchParams.set("days", String(params.days));
  if (params?.start_date) searchParams.set("start_date", params.start_date);
  if (params?.end_date) searchParams.set("end_date", params.end_date);
  const query = searchParams.toString();
  return fetchApi<OptimizerEfficiencySummaryResponse>(
    `/optimizer/economics/efficiency${query ? `?${query}` : ""}`,
  );
}


export interface OptimizerSetupResponse {
  monthly_hosting_cost_usd: number | null;
  effective_cpm_enabled: boolean;
}


export async function getOptimizerSetup(): Promise<OptimizerSetupResponse> {
  return fetchApi<OptimizerSetupResponse>("/settings/optimizer/setup");
}


export async function updateOptimizerSetup(params: {
  monthly_hosting_cost_usd: number;
}): Promise<OptimizerSetupResponse> {
  return fetchApi<OptimizerSetupResponse>("/settings/optimizer/setup", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}
