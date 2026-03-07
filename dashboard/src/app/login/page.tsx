"use client";

/**
 * Login page with multiple authentication options:
 * - Authing (OIDC)
 * - Google (via OAuth2 Proxy)
 * - Username/Password
 */

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock, AlertCircle, Loader2 } from "lucide-react";
import { useTranslation } from "@/contexts/i18n-context";

type ProviderMethod = "password" | "authing" | "google";
type AuthMethod = "select" | "password";

interface AuthProvidersResponse {
  password: boolean;
  authing: boolean;
  google: boolean;
  enabled_methods: ProviderMethod[];
  default_method: ProviderMethod;
}

const METHOD_ORDER: ProviderMethod[] = ["authing", "google", "password"];

function getBuildTimeProviderDefaults(): AuthProvidersResponse {
  const authing = process.env.NEXT_PUBLIC_ENABLE_AUTHING_LOGIN === "true";
  const google = process.env.NEXT_PUBLIC_ENABLE_GOOGLE_LOGIN === "true";
  const password = true;

  const enabled_methods = METHOD_ORDER.filter((method) => {
    if (method === "authing") return authing;
    if (method === "google") return google;
    return password;
  });

  const default_method = enabled_methods[0] || "password";

  return {
    password,
    authing,
    google,
    enabled_methods,
    default_method,
  };
}

function normalizeProviderResponse(
  value: unknown,
  fallback: AuthProvidersResponse,
): AuthProvidersResponse {
  if (!value || typeof value !== "object") {
    return fallback;
  }

  const record = value as Record<string, unknown>;
  const password = typeof record.password === "boolean" ? record.password : fallback.password;
  const authing = typeof record.authing === "boolean" ? record.authing : fallback.authing;
  const google = typeof record.google === "boolean" ? record.google : fallback.google;

  const enabled_methods = METHOD_ORDER.filter((method) => {
    if (method === "authing") return authing;
    if (method === "google") return google;
    return password;
  });

  const requestedDefault = typeof record.default_method === "string"
    ? (record.default_method as ProviderMethod)
    : fallback.default_method;

  const default_method = enabled_methods.includes(requestedDefault)
    ? requestedDefault
    : (enabled_methods[0] || "password");

  return {
    password,
    authing,
    google,
    enabled_methods,
    default_method,
  };
}

function getInitialAuthMethod(providers: AuthProvidersResponse): AuthMethod {
  if (!providers.authing && !providers.google && providers.password) {
    return "password";
  }
  return "select";
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const error = searchParams.get("error");

  const buildTimeDefaults = useMemo(() => getBuildTimeProviderDefaults(), []);
  const [providers, setProviders] = useState<AuthProvidersResponse>(buildTimeDefaults);
  const [authMethod, setAuthMethod] = useState<AuthMethod>(
    getInitialAuthMethod(buildTimeDefaults),
  );
  const [authMethodManuallyChosen, setAuthMethodManuallyChosen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(error || "");

  const enableAuthingLogin = providers.authing;
  const enableGoogleLogin = providers.google;
  const enablePasswordLogin = providers.password;
  const showExternalLogins = enableAuthingLogin || enableGoogleLogin;
  const noLoginMethods = !showExternalLogins && !enablePasswordLogin;

  useEffect(() => {
    let cancelled = false;

    const loadProviders = async () => {
      try {
        const response = await fetch("/api/auth/providers", {
          credentials: "include",
        });

        if (!response.ok) {
          return;
        }

        const json = await response.json().catch(() => null);
        if (!cancelled) {
          setProviders(normalizeProviderResponse(json, buildTimeDefaults));
        }
      } catch {
        // Keep build-time fallback when provider discovery fails.
      }
    };

    loadProviders();

    return () => {
      cancelled = true;
    };
  }, [buildTimeDefaults]);

  useEffect(() => {
    if (!authMethodManuallyChosen && authMethod === "password" && showExternalLogins) {
      setAuthMethod("select");
      return;
    }

    if (authMethod === "password" && !enablePasswordLogin) {
      setAuthMethod("select");
      return;
    }

    if (authMethod === "select" && !showExternalLogins && enablePasswordLogin) {
      setAuthMethod("password");
    }
  }, [
    authMethod,
    authMethodManuallyChosen,
    enablePasswordLogin,
    showExternalLogins,
  ]);

  // Handle password login
  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!enablePasswordLogin) {
      setErrorMessage("Email/password login is disabled on this deployment.");
      return;
    }

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
          setErrorMessage(t.auth.serverUnavailableTryAgainSoon);
        } else if (response.status >= 500) {
          setErrorMessage(t.auth.loginServiceTemporarilyUnavailable);
        } else {
          setErrorMessage(data?.detail || t.auth.loginFailed);
        }
        return;
      }

      // Redirect to callback URL or home
      router.push(callbackUrl);
    } catch {
      // True network failure -- fetch itself could not connect
      setErrorMessage(t.auth.cannotReachServerCheckConnection);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Authing login - redirect to Authing OIDC
  const handleAuthingLogin = () => {
    if (!enableAuthingLogin) {
      setErrorMessage("Authing login is not available on this deployment.");
      return;
    }

    setIsLoading(true);
    // Redirect to backend Authing auth endpoint
    window.location.href = `/api/auth/authing/login?callback_url=${encodeURIComponent(callbackUrl)}`;
  };

  // Handle Google login - redirect to OAuth2 Proxy
  const handleGoogleLogin = () => {
    if (!enableGoogleLogin) {
      setErrorMessage("Google login is not available on this deployment.");
      return;
    }

    setIsLoading(true);
    // Redirect to OAuth2 Proxy sign-in
    window.location.href = `/oauth2/sign_in?rd=${encodeURIComponent(callbackUrl)}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-md w-full mx-4">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-64 h-64 rounded-2xl mb-4">
            <Image
              src="/cat-scanning-stats.webp"
              alt="Cat-Scan"
              width={256}
              height={256}
              className="w-64 h-64 rounded-2xl"
              priority
            />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t.auth.catScan}</h1>
          <p className="text-gray-600 mt-1">{t.auth.qpsManagerForGoogleAuthBuyers}</p>
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

          {noLoginMethods && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-sm text-amber-800">
                No login methods are enabled. Configure Authing, Google OAuth2 Proxy, or password login.
              </p>
            </div>
          )}

          {authMethod === "select" && !noLoginMethods && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900 text-center mb-6">
                {t.auth.signInToContinue}
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
                      {t.auth.signInWithAuthing}
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
                      {t.auth.signInWithGoogle}
                    </button>
                  )}

                  {enablePasswordLogin && (
                    <div className="relative my-6">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-gray-200" />
                      </div>
                      <div className="relative flex justify-center text-sm">
                        <span className="px-2 bg-white text-gray-500">{t.auth.orSeparator}</span>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Password Login Button */}
              {enablePasswordLogin && (
                <button
                  onClick={() => {
                    setAuthMethodManuallyChosen(true);
                    setAuthMethod("password");
                  }}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  <Mail className="w-5 h-5" />
                  {t.auth.signInWithEmail}
                </button>
              )}
            </div>
          )}

          {authMethod === "password" && enablePasswordLogin && (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              {showExternalLogins && (
                <button
                  type="button"
                  onClick={() => setAuthMethod("select")}
                  className="text-sm text-gray-500 hover:text-gray-700 mb-4"
                >
                  &larr; {t.auth.backToOptions}
                </button>
              )}

              <h2 className="text-lg font-semibold text-gray-900 text-center mb-6">
                {t.auth.signInWithEmail}
              </h2>

              {/* Email Field */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  {t.auth.email}
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
                    placeholder={t.auth.emailPlaceholder}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  {t.auth.password}
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
                    placeholder={t.auth.enterYourPassword}
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
                    {t.auth.signingIn}
                  </>
                ) : (
                  t.auth.signIn
                )}
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          {t.auth.protectedByCatScanAuthentication}
        </p>
      </div>
    </div>
  );
}
