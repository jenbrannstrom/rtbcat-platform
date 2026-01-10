/**
 * Authentication API module.
 * Handles login, logout, session management, and user info.
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
}

export interface LoginResponse {
  status: string;
  user: AuthUser;
  message: string;
}

export interface AuthCheckResponse {
  authenticated: boolean;
  user: AuthUser | null;
}

export interface UserInfo {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
  permissions: string[];
}

// =============================================================================
// API Functions
// =============================================================================

export async function login(email: string, password: string): Promise<LoginResponse> {
  return fetchApi<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

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

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
