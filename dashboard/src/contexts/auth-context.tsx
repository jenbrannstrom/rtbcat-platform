"use client";

/**
 * Authentication context supporting multiple auth methods:
 * - Authing (OIDC)
 * - Google (via OAuth2 Proxy)
 * - Email/Password
 *
 * Users are auto-created on first login (first user gets admin role).
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";

// ==================== Types ====================

interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_admin: boolean;
  default_language?: string | null;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  permissions: string[];
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

// ==================== Context ====================

const AuthContext = createContext<AuthContextValue | null>(null);

// ==================== Provider ====================

// Pages that don't require authentication
const PUBLIC_PAGES = ["/login"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Check if current page is public
  const isPublicPage = PUBLIC_PAGES.includes(pathname);

  // Check authentication status
  const checkAuth = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/check", {
        credentials: "include",
      });

      if (!response.ok) {
        setUser(null);
        setPermissions([]);
        return;
      }

      const data = await response.json();

      if (data.authenticated && data.user) {
        setUser(data.user);
        // Fetch full user info with permissions
        const meResponse = await fetch("/api/auth/me", {
          credentials: "include",
        });
        if (meResponse.ok) {
          const meData = await meResponse.json();
          setPermissions(meData.permissions || []);
        }
      } else {
        setUser(null);
        setPermissions([]);
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      setUser(null);
      setPermissions([]);
    }
  }, []);

  // Logout function - clears session and redirects to login
  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Logout request failed:", error);
    }

    setUser(null);
    setPermissions([]);
    // Redirect to login page
    window.location.href = "/login";
  }, []);

  // Initialize auth state on mount
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await checkAuth();
      setIsLoading(false);
      setInitialized(true);
    };

    init();
  }, [checkAuth]);

  // Redirect to login if not authenticated (except on public pages)
  useEffect(() => {
    if (!initialized || isLoading) return;

    if (!user && !isPublicPage) {
      // Redirect to login page with callback URL
      const callbackUrl = encodeURIComponent(pathname);
      window.location.href = `/login?callbackUrl=${callbackUrl}`;
    }
  }, [initialized, isLoading, user, isPublicPage, pathname]);

  // If authenticated and on login page, redirect to home
  useEffect(() => {
    if (!initialized || isLoading) return;

    if (user && isPublicPage) {
      router.push("/");
    }
  }, [initialized, isLoading, user, isPublicPage, router]);

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
    permissions,
    logout,
    checkAuth,
  };

  // Show loading state on initial load (except on public pages)
  if (!initialized && !isPublicPage) {
    return (
      <AuthContext.Provider value={value}>
        <div className="flex items-center justify-center h-screen bg-gray-50">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-4 text-gray-600">Loading...</p>
          </div>
        </div>
      </AuthContext.Provider>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ==================== Hook ====================

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}

// ==================== HOC for Admin Pages ====================

export function withAdminAuth<P extends object>(
  Component: React.ComponentType<P>
) {
  return function AdminProtectedComponent(props: P) {
    const { isAdmin, isLoading, isAuthenticated } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (!isLoading && (!isAuthenticated || !isAdmin)) {
        router.push("/");
      }
    }, [isLoading, isAuthenticated, isAdmin, router]);

    if (isLoading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
        </div>
      );
    }

    if (!isAdmin) {
      return null;
    }

    return <Component {...props} />;
  };
}
