/**
 * Integrations API module.
 * Handles credentials, service accounts, language AI providers, Gmail, and GCP.
 */

import { fetchApi } from "./core";

// =============================================================================
// Service Account Types
// =============================================================================

export interface CredentialsUploadResponse {
  success: boolean;
  id?: string;
  client_email?: string;
  project_id?: string;
  message: string;
}

export interface ServiceAccount {
  id: string;
  client_email: string;
  project_id?: string;
  display_name?: string;
  is_active: boolean;
  created_at?: string;
  last_used?: string;
}

export interface ServiceAccountListResponse {
  accounts: ServiceAccount[];
  count: number;
}

// =============================================================================
// Language AI Provider Types
// =============================================================================

export type LanguageAIProvider = "gemini" | "claude" | "grok";

export interface AIProviderKeyStatus {
  configured: boolean;
  masked_key: string | null;
  source?: string | null;
  message: string;
}

export interface LanguageAIProviderConfig {
  provider: LanguageAIProvider;
  available_providers: LanguageAIProvider[];
  configured: boolean;
  providers: Record<LanguageAIProvider, AIProviderKeyStatus>;
  message: string;
}

export interface AIProviderKeyUpdateResponse {
  success: boolean;
  provider: LanguageAIProvider;
  message: string;
}

// =============================================================================
// Gmail Types
// =============================================================================

export interface GmailImportHistoryItem {
  timestamp: string;
  success: boolean;
  files_imported: number;
  emails_processed: number;
  error: string | null;
}

export interface GmailStatus {
  configured: boolean;
  authorized: boolean;
  last_run: string | null;
  last_success: string | null;
  last_error: string | null;
  total_imports: number;
  recent_history: GmailImportHistoryItem[];
  running?: boolean;
  current_job_id?: string | null;
  last_unread_report_emails?: number;
}

export interface GmailImportResult {
  success: boolean;
  queued?: boolean;
  job_id?: string | null;
  message?: string | null;
  emails_skipped?: number;
  skipped_seat_ids?: string[];
  emails_processed: number;
  files_imported: number;
  files: string[];
  errors: string[];
}

// =============================================================================
// GCP Types
// =============================================================================

export interface GCPStatusResponse {
  gcp_mode: boolean;
  adc_available: boolean;
  service_account_email: string | null;
  project_id: string | null;
  message: string;
}

export interface GCPDiscoveryResponse {
  success: boolean;
  bidder_ids: string[];
  buyer_seats_count: number;
  message: string;
}

// =============================================================================
// Service Accounts API
// =============================================================================

export async function getServiceAccounts(activeOnly: boolean = false): Promise<ServiceAccountListResponse> {
  const params = activeOnly ? "?active_only=true" : "";
  return fetchApi<ServiceAccountListResponse>(`/config/service-accounts${params}`);
}

export async function getServiceAccount(accountId: string): Promise<ServiceAccount> {
  return fetchApi<ServiceAccount>(`/config/service-accounts/${encodeURIComponent(accountId)}`);
}

export async function addServiceAccount(
  serviceAccountJson: string,
  displayName?: string
): Promise<CredentialsUploadResponse> {
  return fetchApi<CredentialsUploadResponse>("/config/service-accounts", {
    method: "POST",
    body: JSON.stringify({
      service_account_json: serviceAccountJson,
      display_name: displayName,
    }),
  });
}

export async function deleteServiceAccount(accountId: string): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>(
    `/config/service-accounts/${encodeURIComponent(accountId)}`,
    { method: "DELETE" }
  );
}

// =============================================================================
// Language AI Provider API
// =============================================================================

export async function getLanguageAIProviderConfig(): Promise<LanguageAIProviderConfig> {
  return fetchApi<LanguageAIProviderConfig>("/config/language-ai/provider");
}

export async function updateLanguageAIProvider(
  provider: LanguageAIProvider
): Promise<AIProviderKeyUpdateResponse> {
  return fetchApi<AIProviderKeyUpdateResponse>("/config/language-ai/provider", {
    method: "PUT",
    body: JSON.stringify({ provider }),
  });
}

export async function getLanguageAIProviderKeyStatus(
  provider: LanguageAIProvider
): Promise<AIProviderKeyStatus> {
  return fetchApi<AIProviderKeyStatus>(
    `/config/language-ai/providers/${encodeURIComponent(provider)}/key`
  );
}

export async function updateLanguageAIProviderKey(
  provider: LanguageAIProvider,
  apiKey: string
): Promise<AIProviderKeyUpdateResponse> {
  return fetchApi<AIProviderKeyUpdateResponse>(
    `/config/language-ai/providers/${encodeURIComponent(provider)}/key`,
    {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    }
  );
}

export async function deleteLanguageAIProviderKey(
  provider: LanguageAIProvider
): Promise<AIProviderKeyUpdateResponse> {
  return fetchApi<AIProviderKeyUpdateResponse>(
    `/config/language-ai/providers/${encodeURIComponent(provider)}/key`,
    { method: "DELETE" }
  );
}

// Backward-compatible Gemini wrappers
export async function getGeminiKeyStatus(): Promise<AIProviderKeyStatus> {
  return fetchApi<AIProviderKeyStatus>("/config/gemini-key");
}

export async function updateGeminiKey(apiKey: string): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>("/config/gemini-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function deleteGeminiKey(): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>("/config/gemini-key", {
    method: "DELETE",
  });
}

// =============================================================================
// Gmail API
// =============================================================================

export async function getGmailStatus(): Promise<GmailStatus> {
  return fetchApi<GmailStatus>("/gmail/status");
}

export async function triggerGmailImport(): Promise<GmailImportResult> {
  return fetchApi<GmailImportResult>("/gmail/import", {
    method: "POST",
  });
}

// =============================================================================
// GCP / ADC API
// =============================================================================

export async function getGCPStatus(): Promise<GCPStatusResponse> {
  return fetchApi<GCPStatusResponse>("/config/gcp-status");
}

export async function discoverViaADC(bidderId: string): Promise<GCPDiscoveryResponse> {
  return fetchApi<GCPDiscoveryResponse>("/config/gcp-discover", {
    method: "POST",
    body: JSON.stringify({ bidder_id: bidderId }),
  });
}
