"use client";

/**
 * Authentication context supporting multiple auth methods:
 * - Authing (OIDC)
 * - Google (via OAuth2 Proxy)
 * - Email/Password
 *
 * Users are auto-created on first login (first user gets admin role).
 *
 * Loop prevention:
 * - Tracks redirect attempts via sessionStorage counter
 * - Distinguishes 503 (service down) from 200 {authenticated:false} (not logged in)
 * - Shows error/retry UI instead of redirecting when service is degraded
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

type AuthErrorKind = "service_unavailable" | "network_error" | null;

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  permissions: string[];
  authError: AuthErrorKind;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

// ==================== Constants ====================

const MAX_AUTH_REDIRECTS = 2;
const REDIRECT_COUNTER_KEY = "catscan_auth_redirect_count";
const REDIRECT_TS_KEY = "catscan_auth_redirect_ts";
const REDIRECT_WINDOW_MS = 30_000; // reset counter after 30s of no redirects

// ==================== Context ====================

const AuthContext = createContext<AuthContextValue | null>(null);

// ==================== Helpers ====================

function getRedirectCount(): number {
  try {
    const ts = parseInt(sessionStorage.getItem(REDIRECT_TS_KEY) || "0", 10);
    // Reset counter if last redirect was more than 30s ago
    if (Date.now() - ts > REDIRECT_WINDOW_MS) {
      sessionStorage.setItem(REDIRECT_COUNTER_KEY, "0");
      return 0;
    }
    return parseInt(sessionStorage.getItem(REDIRECT_COUNTER_KEY) || "0", 10);
  } catch {
    return 0;
  }
}

function incrementRedirectCount(): number {
  try {
    const count = getRedirectCount() + 1;
    sessionStorage.setItem(REDIRECT_COUNTER_KEY, String(count));
    sessionStorage.setItem(REDIRECT_TS_KEY, String(Date.now()));
    return count;
  } catch {
    return 999; // fail safe: treat as exceeded
  }
}

function resetRedirectCount(): void {
  try {
    sessionStorage.setItem(REDIRECT_COUNTER_KEY, "0");
  } catch {
    // ignore
  }
}

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
  const [authError, setAuthError] = useState<AuthErrorKind>(null);

  // Check if current page is public
  const isPublicPage = PUBLIC_PAGES.includes(pathname);

  // Check authentication status
  const checkAuth = useCallback(async () => {
    // DEV BYPASS: skip auth when backend is not running
    if (process.env.NODE_ENV === "development") {
      setUser({ id: "dev", email: "dev@localhost", name: "Dev User", role: "admin" } as User);
      setPermissions(["admin", "read", "write"]);
      setAuthError(null);
      resetRedirectCount();
      return;
    }
    try {
      const response = await fetch("/api/auth/check", {
        credentials: "include",
      });

      // 503 = backend is up but DB/auth system is degraded
      if (response.status === 503) {
        console.warn("Auth service unavailable (503) — DB may be down");
        setUser(null);
        setPermissions([]);
        setAuthError("service_unavailable");
        return;
      }

      if (!response.ok) {
        setUser(null);
        setPermissions([]);
        setAuthError(null);
        return;
      }

      const data = await response.json();

      if (data.authenticated && data.user) {
        setUser(data.user);
        setAuthError(null);
        resetRedirectCount(); // successful auth — clear counter
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
        setAuthError(null);
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      setUser(null);
      setPermissions([]);
      setAuthError("network_error");
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
    resetRedirectCount();
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
  // Respect loop counter and error state to avoid infinite redirects
  useEffect(() => {
    if (!initialized || isLoading) return;
    if (user) return; // authenticated — nothing to do
    if (authError) return; // service error — show error UI, don't redirect

    if (!isPublicPage) {
      const count = incrementRedirectCount();
      if (count > MAX_AUTH_REDIRECTS) {
        console.error(
          `Auth redirect loop detected (${count} redirects in ${REDIRECT_WINDOW_MS / 1000}s). Stopping.`
        );
        setAuthError("service_unavailable");
        return;
      }

      // Redirect to login page with callback URL
      const callbackUrl = encodeURIComponent(pathname);
      window.location.href = `/login?callbackUrl=${callbackUrl}`;
    }
  }, [initialized, isLoading, user, isPublicPage, pathname, authError]);

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
    authError,
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

  // Show error/retry page when auth system is degraded
  if (authError && !user) {
    return (
      <AuthContext.Provider value={value}>
        <div className="flex items-center justify-center h-screen bg-gray-50">
          <div className="text-center max-w-md px-6">
            <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.072 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              {authError === "service_unavailable"
                ? "Service Temporarily Unavailable"
                : "Connection Error"}
            </h2>
            <p className="text-gray-600 mb-6">
              {authError === "service_unavailable"
                ? "The authentication service is starting up or temporarily unavailable. This usually resolves within a few minutes."
                : "Unable to reach the server. Check your network connection."}
            </p>
            <button
              onClick={() => {
                resetRedirectCount();
                setAuthError(null);
                setInitialized(false);
                setIsLoading(true);
                checkAuth().then(() => {
                  setIsLoading(false);
                  setInitialized(true);
                });
              }}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Retry
            </button>
            <p className="text-xs text-gray-400 mt-4">
              If this persists, check that all containers are running on the VM.
            </p>
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
