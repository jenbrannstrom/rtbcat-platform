/**
 * Admin API module.
 * Handles user management, permissions, audit logs, and system settings.
 */

import { fetchApi } from "./core";

// =============================================================================
// Types
// =============================================================================

export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export interface CreateUserRequest {
  email: string;
  display_name?: string;
  role?: string;
  password?: string;
}

export interface CreateUserResponse {
  status: string;
  user_id: string;
  email: string;
  password: string;
  message: string;
}

export interface UserPermission {
  id: string;
  user_id: string;
  service_account_id: string;
  permission_level: string;
  granted_by: string | null;
  granted_at: string | null;
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: string | null;
  ip_address: string | null;
  created_at: string | null;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  admin_users: number;
  multi_user_enabled: boolean;
}

// =============================================================================
// User Management
// =============================================================================

export async function getAdminUsers(params?: {
  active_only?: boolean;
  role?: string;
}): Promise<AdminUser[]> {
  const searchParams = new URLSearchParams();
  if (params?.active_only) searchParams.set("active_only", "true");
  if (params?.role) searchParams.set("role", params.role);
  const query = searchParams.toString();
  return fetchApi<AdminUser[]>(`/admin/users${query ? `?${query}` : ""}`);
}

export async function createUser(request: CreateUserRequest): Promise<CreateUserResponse> {
  return fetchApi<CreateUserResponse>("/admin/users", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getAdminUser(userId: string): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`);
}

export async function updateAdminUser(
  userId: string,
  updates: {
    display_name?: string;
    role?: string;
    is_active?: boolean;
    password?: string;
  }
): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deactivateUser(userId: string): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>(
    `/admin/users/${encodeURIComponent(userId)}`,
    { method: "DELETE" }
  );
}

export async function resetUserPassword(
  userId: string
): Promise<{ status: string; user_id: string; email: string; new_password: string; message: string }> {
  return fetchApi<{ status: string; user_id: string; email: string; new_password: string; message: string }>(
    `/admin/users/${encodeURIComponent(userId)}/reset-password`,
    { method: "POST" }
  );
}

// =============================================================================
// Permissions
// =============================================================================

export async function getUserPermissions(userId: string): Promise<UserPermission[]> {
  return fetchApi<UserPermission[]>(`/admin/users/${encodeURIComponent(userId)}/permissions`);
}

export async function grantPermission(
  userId: string,
  serviceAccountId: string,
  permissionLevel: string
): Promise<UserPermission> {
  return fetchApi<UserPermission>(`/admin/users/${encodeURIComponent(userId)}/permissions`, {
    method: "POST",
    body: JSON.stringify({
      service_account_id: serviceAccountId,
      permission_level: permissionLevel,
    }),
  });
}

export async function revokePermission(
  userId: string,
  serviceAccountId: string
): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>(
    `/admin/users/${encodeURIComponent(userId)}/permissions/${encodeURIComponent(serviceAccountId)}`,
    { method: "DELETE" }
  );
}

// =============================================================================
// Audit Logs
// =============================================================================

export async function getAuditLogs(params?: {
  user_id?: string;
  action?: string;
  resource_type?: string;
  days?: number;
  limit?: number;
  offset?: number;
}): Promise<AuditLogEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.user_id) searchParams.set("user_id", params.user_id);
  if (params?.action) searchParams.set("action", params.action);
  if (params?.resource_type) searchParams.set("resource_type", params.resource_type);
  if (params?.days) searchParams.set("days", String(params.days));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const query = searchParams.toString();
  return fetchApi<AuditLogEntry[]>(`/admin/audit-log${query ? `?${query}` : ""}`);
}

// =============================================================================
// System Settings & Stats
// =============================================================================

export async function getAdminStats(): Promise<AdminStats> {
  return fetchApi<AdminStats>("/admin/stats");
}

export async function getSystemSettings(): Promise<Record<string, string>> {
  return fetchApi<Record<string, string>>("/admin/settings");
}

export async function updateSystemSetting(
  key: string,
  value: string
): Promise<{ status: string; key: string; value: string }> {
  return fetchApi<{ status: string; key: string; value: string }>(
    `/admin/settings/${encodeURIComponent(key)}`,
    {
      method: "PUT",
      body: JSON.stringify({ value }),
    }
  );
}
