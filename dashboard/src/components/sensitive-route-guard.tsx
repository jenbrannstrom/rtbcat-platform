"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield, Lock, AlertTriangle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";

interface SensitiveRouteGuardProps {
  children: React.ReactNode;
  featureName?: string;
}

/**
 * Guards sensitive routes that should not be accessible when
 * the user has must_change_password=true.
 *
 * Use this wrapper on pages that handle:
 * - API credentials (JSON service account keys)
 * - Authorized Buyers account configuration
 * - Other sensitive security settings
 */
export function SensitiveRouteGuard({
  children,
  featureName = "this feature"
}: SensitiveRouteGuardProps) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // If user must change password, show blocked message
  if (!isLoading && user?.must_change_password) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center">
          <div className="mx-auto w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mb-4">
            <Shield className="h-8 w-8 text-amber-600" />
          </div>

          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Password Change Required
          </h2>

          <p className="text-gray-600 mb-6">
            For security reasons, you must change your password before accessing {featureName}.
            This protects sensitive credentials and account settings.
          </p>

          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg mb-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-left text-sm text-amber-800">
                <strong>Why is this required?</strong>
                <p className="mt-1">
                  Default or initial passwords may be known to others. Changing your
                  password ensures only you can access sensitive features like API
                  credentials and account configurations.
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={() => router.push("/change-password")}
            className="w-full py-2.5 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 flex items-center justify-center gap-2"
          >
            <Lock className="h-4 w-4" />
            Change Password Now
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // User has changed password, show content
  return <>{children}</>;
}
