/**
 * Integrations API module.
 * Handles credentials, service accounts, Gemini, Gmail, and GCP.
 */

import { fetchApi } from "./core";

// =============================================================================
// Credentials Types
// =============================================================================

export interface CredentialsStatus {
  configured: boolean;
  client_email?: string;
  project_id?: string;
  credentials_path?: string;
  account_id?: string;
}

export interface CredentialsUploadResponse {
  success: boolean;
  id?: string;
  client_email?: string;
  project_id?: string;
  message: string;
}

// =============================================================================
// Service Account Types
// =============================================================================

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
// Gemini Types
// =============================================================================

export interface GeminiKeyStatus {
  configured: boolean;
  masked_key: string | null;
  message: string;
}

export interface GeminiKeyUpdateResponse {
  success: boolean;
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
}

export interface GmailImportResult {
  success: boolean;
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
// Credentials API
// =============================================================================

export async function getCredentialsStatus(): Promise<CredentialsStatus> {
  return fetchApi<CredentialsStatus>("/config/credentials");
}

export async function uploadCredentials(
  serviceAccountJson: string,
  displayName?: string
): Promise<CredentialsUploadResponse> {
  return fetchApi<CredentialsUploadResponse>("/config/credentials", {
    method: "POST",
    body: JSON.stringify({
      service_account_json: serviceAccountJson,
      display_name: displayName,
    }),
  });
}

export async function deleteCredentials(): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>("/config/credentials", {
    method: "DELETE",
  });
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
// Gemini API
// =============================================================================

export async function getGeminiKeyStatus(): Promise<GeminiKeyStatus> {
  return fetchApi<GeminiKeyStatus>("/config/gemini-key");
}

export async function updateGeminiKey(apiKey: string): Promise<GeminiKeyUpdateResponse> {
  return fetchApi<GeminiKeyUpdateResponse>("/config/gemini-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function deleteGeminiKey(): Promise<GeminiKeyUpdateResponse> {
  return fetchApi<GeminiKeyUpdateResponse>("/config/gemini-key", {
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
