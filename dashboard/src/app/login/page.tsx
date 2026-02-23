"use client";

/**
 * Login page with multiple authentication options:
 * - Authing (OIDC)
 * - Google (via OAuth2 Proxy)
 * - Username/Password
 */

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock, AlertCircle, Loader2 } from "lucide-react";

type AuthMethod = "select" | "password" | "authing" | "google";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const error = searchParams.get("error");
  const enableAuthingLogin = process.env.NEXT_PUBLIC_ENABLE_AUTHING_LOGIN === "true";
  const enableGoogleLogin = process.env.NEXT_PUBLIC_ENABLE_GOOGLE_LOGIN === "true";
  const showExternalLogins = enableAuthingLogin || enableGoogleLogin;

  const [authMethod, setAuthMethod] = useState<AuthMethod>(
    showExternalLogins ? "select" : "password"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(error || "");

  // Handle password login
  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });

      // Handle non-JSON error responses (e.g. nginx 502/504 HTML pages)
      const contentType = response.headers.get("content-type") || "";
      const isJson = contentType.includes("application/json");
      const data = isJson ? await response.json().catch(() => null) : null;

      if (!response.ok) {
        if ([502, 503, 504].includes(response.status)) {
          setErrorMessage("Server unavailable. Please try again in a moment.");
        } else if (response.status >= 500) {
          setErrorMessage("Login service is temporarily unavailable.");
        } else {
          setErrorMessage(data?.detail || "Login failed");
        }
        return;
      }

      // Redirect to callback URL or home
      router.push(callbackUrl);
    } catch (err) {
      // True network failure -- fetch itself could not connect
      setErrorMessage("Cannot reach server. Please check your connection and try again.");
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Authing login - redirect to Authing OIDC
  const handleAuthingLogin = () => {
    setIsLoading(true);
    // Redirect to backend Authing auth endpoint
    window.location.href = `/api/auth/authing/login?callback_url=${encodeURIComponent(callbackUrl)}`;
  };

  // Handle Google login - redirect to OAuth2 Proxy
  const handleGoogleLogin = () => {
    setIsLoading(true);
    // Redirect to OAuth2 Proxy sign-in
    window.location.href = `/oauth2/sign_in?rd=${encodeURIComponent(callbackUrl)}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-md w-full mx-4">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4">
            <img src="/favicon.svg" alt="Cat-Scan" className="w-16 h-16" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Cat-Scan</h1>
          <p className="text-gray-600 mt-1">QPS manager for Google Auth Buyers</p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-8">
          {/* Error Message */}
          {errorMessage && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{errorMessage}</p>
            </div>
          )}

          {authMethod === "select" && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900 text-center mb-6">
                Sign in to continue
              </h2>

              {showExternalLogins && (
                <>
                  {enableAuthingLogin && (
                    <button
                      onClick={handleAuthingLogin}
                      disabled={isLoading}
                      className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                      {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
                        </svg>
                      )}
                      Sign in with Authing
                    </button>
                  )}

                  {enableGoogleLogin && (
                    <button
                      onClick={handleGoogleLogin}
                      disabled={isLoading}
                      className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white border-2 border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors disabled:opacity-50"
                    >
                      {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <svg className="w-5 h-5" viewBox="0 0 24 24">
                          <path
                            fill="#4285F4"
                            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                          />
                          <path
                            fill="#34A853"
                            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                          />
                          <path
                            fill="#FBBC05"
                            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                          />
                          <path
                            fill="#EA4335"
                            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                          />
                        </svg>
                      )}
                      Sign in with Google
                    </button>
                  )}

                  <div className="relative my-6">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-gray-200" />
                    </div>
                    <div className="relative flex justify-center text-sm">
                      <span className="px-2 bg-white text-gray-500">or</span>
                    </div>
                  </div>
                </>
              )}

              {/* Password Login Button */}
              <button
                onClick={() => setAuthMethod("password")}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                <Mail className="w-5 h-5" />
                Sign in with Email
              </button>
            </div>
          )}

          {authMethod === "password" && (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              {showExternalLogins && (
                <button
                  type="button"
                  onClick={() => setAuthMethod("select")}
                  className="text-sm text-gray-500 hover:text-gray-700 mb-4"
                >
                  &larr; Back to options
                </button>
              )}

              <h2 className="text-lg font-semibold text-gray-900 text-center mb-6">
                Sign in with Email
              </h2>

              {/* Email Field */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter your password"
                  />
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  "Sign in"
                )}
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          Protected by Cat-Scan authentication
        </p>
      </div>
    </div>
  );
}
