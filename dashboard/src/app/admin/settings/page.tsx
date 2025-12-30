"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings, Check, AlertCircle, Info } from "lucide-react";
import { getSystemSettings, updateSystemSetting } from "@/lib/api";
import { withAdminAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

const RETENTION_OPTIONS = [
  { value: "0", label: "Unlimited", description: "Keep audit logs forever" },
  { value: "30", label: "30 days", description: "Delete logs older than 30 days" },
  { value: "60", label: "60 days", description: "Delete logs older than 60 days (recommended)" },
  { value: "90", label: "90 days", description: "Delete logs older than 90 days" },
  { value: "120", label: "120 days", description: "Delete logs older than 120 days" },
];

function SettingsPage() {
  const queryClient = useQueryClient();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["system-settings"],
    queryFn: getSystemSettings,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      updateSystemSetting(key, value),
    onSuccess: (_, { key }) => {
      queryClient.invalidateQueries({ queryKey: ["system-settings"] });
      setSuccessMessage(`Setting "${key}" updated successfully`);
      setErrorMessage(null);
      setTimeout(() => setSuccessMessage(null), 3000);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
      setSuccessMessage(null);
    },
  });

  const currentRetention = settings?.audit_retention_days ?? "60";
  const multiUserEnabled = settings?.multi_user_enabled === "1";

  const handleRetentionChange = (value: string) => {
    updateMutation.mutate({ key: "audit_retention_days", value });
  };

  const handleMultiUserToggle = () => {
    const newValue = multiUserEnabled ? "0" : "1";
    updateMutation.mutate({ key: "multi_user_enabled", value: newValue });
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">System Settings</h1>
        <p className="mt-1 text-gray-600">
          Configure system-wide settings and features.
        </p>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
          <Check className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-green-700">{successMessage}</p>
        </div>
      )}
      {errorMessage && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700">{errorMessage}</p>
        </div>
      )}

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* Multi-User Mode */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Multi-User Mode
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                Allow creating additional user accounts. When disabled, only the
                admin account can access the system.
              </p>
            </div>
            <button
              onClick={handleMultiUserToggle}
              disabled={updateMutation.isPending}
              className={cn(
                "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50",
                multiUserEnabled ? "bg-primary-600" : "bg-gray-200"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
                  multiUserEnabled ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>
          <div className="mt-4 p-3 bg-blue-50 rounded-lg flex items-start gap-2">
            <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-blue-700">
              Login is always required. This setting controls whether you can
              add more user accounts beyond the admin. Enable for team access,
              disable for personal use.
            </p>
          </div>
        </div>

        {/* Audit Log Retention */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Audit Log Retention
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Configure how long to keep audit log entries before automatic
            cleanup.
          </p>

          <div className="mt-4 space-y-3">
            {RETENTION_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex items-center p-3 rounded-lg border cursor-pointer transition-colors",
                  currentRetention === option.value
                    ? "border-primary-500 bg-primary-50"
                    : "border-gray-200 hover:bg-gray-50"
                )}
              >
                <input
                  type="radio"
                  name="retention"
                  value={option.value}
                  checked={currentRetention === option.value}
                  onChange={(e) => handleRetentionChange(e.target.value)}
                  disabled={updateMutation.isPending}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
                />
                <div className="ml-3">
                  <span className="font-medium text-gray-900">
                    {option.label}
                  </span>
                  <p className="text-sm text-gray-500">{option.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Session Settings (Read-only info) */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Session Settings
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Default session and security settings.
          </p>

          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-500">
                Session Duration
              </p>
              <p className="text-lg font-semibold text-gray-900">30 days</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-500">
                Login Attempts Before Lockout
              </p>
              <p className="text-lg font-semibold text-gray-900">5 attempts</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-500">
                Lockout Duration
              </p>
              <p className="text-lg font-semibold text-gray-900">1 hour</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-500">
                Password Hashing
              </p>
              <p className="text-lg font-semibold text-gray-900">bcrypt</p>
            </div>
          </div>
        </div>

        {/* All Settings (Debug view) */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900">All Settings</h2>
          <p className="mt-1 text-sm text-gray-500">
            Raw view of all system settings.
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Key
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {Object.entries(settings || {}).map(([key, value]) => (
                  <tr key={key}>
                    <td className="px-4 py-2 text-sm font-mono text-gray-600">
                      {key}
                    </td>
                    <td className="px-4 py-2 text-sm font-mono text-gray-900">
                      {value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default withAdminAuth(SettingsPage);
