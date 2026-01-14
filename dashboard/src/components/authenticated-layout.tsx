"use client";

/**
 * Authenticated layout wrapper.
 *
 * With OAuth2 Proxy (Google Auth):
 * - Users are authenticated at the edge before reaching the app
 * - No public paths needed - everything requires auth
 * - If not authenticated, AuthContext redirects to OAuth2 sign-in
 */

import { Suspense, type ReactNode } from "react";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { Sidebar } from "@/components/sidebar";
import { FirstRunCheck } from "@/components/first-run-check";

interface AuthenticatedLayoutProps {
  children: ReactNode;
  sidebarFallback: ReactNode;
}

export function AuthenticatedLayout({
  children,
  sidebarFallback,
}: AuthenticatedLayoutProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const { t } = useTranslation();

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-600">{t.common.loading}</p>
        </div>
      </div>
    );
  }

  // If not authenticated, the AuthProvider will redirect to OAuth2 sign-in
  // Show a minimal loading state while redirect happens
  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-600">{t.common.loading}</p>
        </div>
      </div>
    );
  }

  // Authenticated users get the full layout with sidebar
  return (
    <FirstRunCheck>
      <div className="flex h-screen bg-gray-50">
        <Suspense fallback={sidebarFallback}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </FirstRunCheck>
  );
}
