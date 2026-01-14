/**
 * Authentication API module.
 * Handles logout, session management, and user info.
 *
 * Note: Login is handled by OAuth2 Proxy (Google Auth) - no password-based login.
 */

import { fetchApi } from "./core";

// =============================================================================
// Types
// =============================================================================

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
  default_language?: string | null;
}

export interface AuthCheckResponse {
  authenticated: boolean;
  auth_method?: string;
  user: AuthUser | null;
}

export interface UserInfo {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
  permissions: string[];
  default_language?: string | null;
}

// =============================================================================
// API Functions
// =============================================================================

export async function logout(): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>("/auth/logout", {
    method: "POST",
  });
}

export async function checkAuth(): Promise<AuthCheckResponse> {
  return fetchApi<AuthCheckResponse>("/auth/check");
}

export async function getCurrentUser(): Promise<UserInfo> {
  return fetchApi<UserInfo>("/auth/me");
}
