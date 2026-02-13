"use client";

/**
 * Authenticated layout wrapper.
 *
 * Supports multiple auth methods:
 * - Authing (OIDC)
 * - Google (via OAuth2 Proxy)
 * - Email/Password
 *
 * Public pages (like /login) are rendered without the sidebar.
 * Protected pages require authentication.
 */

import { Suspense, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { Sidebar } from "@/components/sidebar";
import { FirstRunCheck } from "@/components/first-run-check";
import { BuyerRouteSync } from "@/components/buyer-route-sync";

interface AuthenticatedLayoutProps {
  children: ReactNode;
  sidebarFallback: ReactNode;
}

// Pages that should be rendered without the authenticated layout
const PUBLIC_PAGES = ["/login"];

export function AuthenticatedLayout({
  children,
  sidebarFallback,
}: AuthenticatedLayoutProps) {
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const { t } = useTranslation();

  // Check if this is a public page
  const isPublicPage = PUBLIC_PAGES.includes(pathname);

  // For public pages, render children directly without layout
  if (isPublicPage) {
    return <>{children}</>;
  }

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

  // If not authenticated, the AuthProvider will redirect to login
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
      <BuyerRouteSync />
      <div className="flex h-screen bg-gray-50">
        <Suspense fallback={sidebarFallback}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </FirstRunCheck>
  );
}
