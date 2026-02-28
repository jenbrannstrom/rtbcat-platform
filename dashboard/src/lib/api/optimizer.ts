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
  scoring_days?: number;
  proposal_days?: number;
  scoring_limit?: number;
  proposal_limit?: number;
  min_confidence?: number;
  max_delta_pct?: number;
}): Promise<OptimizerScoreAndProposeResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("model_id", params.model_id);
  if (params.buyer_id) searchParams.set("buyer_id", params.buyer_id);
  if (typeof params.scoring_days === "number") searchParams.set("scoring_days", String(params.scoring_days));
  if (typeof params.proposal_days === "number") searchParams.set("proposal_days", String(params.proposal_days));
  if (typeof params.scoring_limit === "number") searchParams.set("scoring_limit", String(params.scoring_limit));
  if (typeof params.proposal_limit === "number") searchParams.set("proposal_limit", String(params.proposal_limit));
  if (typeof params.min_confidence === "number") searchParams.set("min_confidence", String(params.min_confidence));
  if (typeof params.max_delta_pct === "number") searchParams.set("max_delta_pct", String(params.max_delta_pct));
  return fetchApi<OptimizerScoreAndProposeResponse>(
    `/optimizer/workflows/score-and-propose?${searchParams.toString()}`,
    { method: "POST" },
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
