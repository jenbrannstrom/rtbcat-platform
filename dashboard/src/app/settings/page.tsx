"use client";

import { useQuery } from "@tanstack/react-query";
import { Settings, CheckCircle, XCircle, Database, Server } from "lucide-react";
import { getHealth, getStats } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";

export default function SettingsPage() {
  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  if (healthLoading) {
    return <LoadingPage />;
  }

  if (healthError) {
    return (
      <ErrorPage
        message={
          healthError instanceof Error
            ? healthError.message
            : "Failed to check API status"
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          System configuration and status
        </p>
      </div>

      <div className="max-w-2xl space-y-6">
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Server className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">API Status</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Status</span>
              <span className="flex items-center text-sm font-medium text-green-600">
                <CheckCircle className="h-4 w-4 mr-1" />
                {health?.status}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Version</span>
              <span className="text-sm font-medium text-gray-900">
                {health?.version}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">Configured</span>
              <span
                className={`flex items-center text-sm font-medium ${
                  health?.configured ? "text-green-600" : "text-red-600"
                }`}
              >
                {health?.configured ? (
                  <>
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Yes
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-1" />
                    No
                  </>
                )}
              </span>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Database className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Database</h2>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Path</span>
              <span className="text-sm font-mono text-gray-900">
                {stats?.db_path || "N/A"}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Creatives</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.creative_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-600">Campaigns</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.campaign_count ?? 0}
              </span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-600">Clusters</span>
              <span className="text-sm font-medium text-gray-900">
                {stats?.cluster_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center mb-4">
            <Settings className="h-5 w-5 text-gray-400 mr-2" />
            <h2 className="text-lg font-medium text-gray-900">Configuration</h2>
          </div>

          <p className="text-sm text-gray-600 mb-4">
            To configure credentials and settings, use the CLI:
          </p>

          <div className="bg-gray-900 rounded-lg p-4">
            <code className="text-sm text-green-400">
              python main.py configure
            </code>
          </div>

          <p className="mt-4 text-xs text-gray-500">
            This will launch an interactive wizard to set up your Google
            Authorized Buyers credentials and other settings.
          </p>
        </div>
      </div>
    </div>
  );
}
