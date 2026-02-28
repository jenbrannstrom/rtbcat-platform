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
