"use client";

import { Suspense, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { Sidebar } from "@/components/sidebar";
import { FirstRunCheck } from "@/components/first-run-check";

// Paths that should not show the sidebar
const PUBLIC_PATHS = ["/login"];

interface AuthenticatedLayoutProps {
  children: ReactNode;
  sidebarFallback: ReactNode;
}

export function AuthenticatedLayout({
  children,
  sidebarFallback,
}: AuthenticatedLayoutProps) {
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const { t } = useTranslation();

  // Check if current path is public (no sidebar needed)
  const isPublicPath = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));

  // For public paths (login, setup), just render children without sidebar
  if (isPublicPath) {
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
      <div className="flex h-screen bg-gray-50">
        <Suspense fallback={sidebarFallback}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </FirstRunCheck>
  );
}
