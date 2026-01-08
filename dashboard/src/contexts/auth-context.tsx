"use client";

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
  must_change_password?: boolean;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  permissions: string[];
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

// ==================== Context ====================

const AuthContext = createContext<AuthContextValue | null>(null);

// Public paths that don't require authentication
const PUBLIC_PATHS = ["/login", "/initial-setup"];

// Paths allowed even if password change is required
const PASSWORD_CHANGE_ALLOWED_PATHS = ["/change-password", "/login", "/initial-setup"];

// ==================== Provider ====================

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  // Check if current path is public
  const isPublicPath = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));

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

  // Login function
  const login = useCallback(
    async (email: string, password: string) => {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Login failed");
      }

      const data = await response.json();
      setUser(data.user);

      // Fetch permissions
      const meResponse = await fetch("/api/auth/me", {
        credentials: "include",
      });
      if (meResponse.ok) {
        const meData = await meResponse.json();
        setPermissions(meData.permissions || []);
      }

      // Redirect to password change if required, otherwise home
      if (data.user?.must_change_password) {
        router.push("/change-password");
      } else {
        router.push("/");
      }
    },
    [router]
  );

  // Logout function
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
    router.push("/login");
  }, [router]);

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

  // Redirect to login if not authenticated and not on public path
  useEffect(() => {
    if (!initialized || isLoading) return;

    if (!user && !isPublicPath) {
      router.push("/login");
    }
  }, [initialized, isLoading, user, isPublicPath, router]);

  // Redirect away from login if already authenticated
  useEffect(() => {
    if (!initialized || isLoading) return;

    if (user && pathname === "/login") {
      // If must change password, go to change-password page
      if (user.must_change_password) {
        router.push("/change-password");
      } else {
        router.push("/");
      }
    }
  }, [initialized, isLoading, user, pathname, router]);

  // Redirect to password change if required and not on allowed path
  useEffect(() => {
    if (!initialized || isLoading) return;

    if (user?.must_change_password) {
      const isAllowedPath = PASSWORD_CHANGE_ALLOWED_PATHS.some(
        (p) => pathname?.startsWith(p)
      );
      if (!isAllowedPath) {
        router.push("/change-password");
      }
    }
  }, [initialized, isLoading, user, pathname, router]);

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
    permissions,
    login,
    logout,
    checkAuth,
  };

  // Show loading state on initial load
  if (!initialized) {
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
