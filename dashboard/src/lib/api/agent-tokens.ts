/**
 * Agent token API module.
 * Handles sudo-only listing, minting, and revocation of outside-agent tokens.
 */

import { fetchApi } from "./core";

export const AGENT_TOKEN_SCOPES = [
  "agent:stats:read",
  "agent:creatives:read",
  "agent:creative-performance:read",
  "agent:assets:read",
] as const;

export type AgentTokenScope = (typeof AGENT_TOKEN_SCOPES)[number];

export interface AgentTokenRecord {
  id: string;
  name: string;
  token_prefix: string;
  user_id: string;
  buyer_id: string | null;
  scopes: string[];
  expires_at: string;
  is_active: boolean;
  user_email: string | null;
  created_at: string | null;
  created_by: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
}

export interface AgentTokenListResponse {
  tokens: AgentTokenRecord[];
}

export interface CreateAgentTokenRequest {
  name: string;
  user_id: string;
  buyer_id?: string;
  all_granted_buyers?: boolean;
  scopes: AgentTokenScope[];
  expires_in_days: number;
}

export interface CreateAgentTokenResponse {
  token: string;
  token_type: "Bearer";
  token_record: AgentTokenRecord;
}

export interface RevokeAgentTokenResponse {
  status: "revoked";
  token_id: string;
}

export async function getAgentTokens(): Promise<AgentTokenListResponse> {
  return fetchApi<AgentTokenListResponse>("/agent/v1/tokens");
}

export async function createAgentToken(
  request: CreateAgentTokenRequest
): Promise<CreateAgentTokenResponse> {
  return fetchApi<CreateAgentTokenResponse>("/agent/v1/tokens", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function revokeAgentToken(tokenId: string): Promise<RevokeAgentTokenResponse> {
  return fetchApi<RevokeAgentTokenResponse>(
    `/agent/v1/tokens/${encodeURIComponent(tokenId)}`,
    { method: "DELETE" }
  );
}
