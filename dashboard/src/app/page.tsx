"use client";

import { useQuery } from "@tanstack/react-query";
import { Image, FolderKanban, Layers, CheckCircle } from "lucide-react";
import { getStats, getHealth } from "@/lib/api";
import { StatsCard } from "@/components/stats-card";
import { FormatChart } from "@/components/format-chart";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";

export default function DashboardPage() {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  if (statsLoading || healthLoading) {
    return <LoadingPage />;
  }

  if (statsError) {
    return (
      <ErrorPage
        message={
          statsError instanceof Error
            ? statsError.message
            : "Failed to load statistics"
        }
        onRetry={() => refetchStats()}
      />
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Creative intelligence overview
        </p>
      </div>

      {health && !health.configured && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            API not configured. Run{" "}
            <code className="px-1 py-0.5 bg-yellow-100 rounded">
              python main.py configure
            </code>{" "}
            to set up credentials.
          </p>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatsCard
          title="Total Creatives"
          value={stats?.creative_count ?? 0}
          icon={Image}
        />
        <StatsCard
          title="Campaigns"
          value={stats?.campaign_count ?? 0}
          icon={FolderKanban}
        />
        <StatsCard
          title="Clusters"
          value={stats?.cluster_count ?? 0}
          icon={Layers}
        />
        <StatsCard
          title="API Status"
          value={health?.configured ? "Configured" : "Not Set"}
          icon={CheckCircle}
          description={health?.version}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Creative Formats
          </h2>
          {stats?.formats && Object.keys(stats.formats).length > 0 ? (
            <FormatChart data={stats.formats} />
          ) : (
            <div className="flex items-center justify-center h-[300px] text-gray-500">
              No creatives collected yet
            </div>
          )}
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Quick Actions
          </h2>
          <div className="space-y-3">
            <a
              href="/waste-analysis"
              className="block p-4 rounded-lg border border-orange-200 bg-orange-50 hover:border-orange-300 hover:bg-orange-100 transition-colors"
            >
              <h3 className="font-medium text-orange-900">Waste Analysis</h3>
              <p className="mt-1 text-sm text-orange-700">
                Identify bandwidth waste and optimize RTB traffic
              </p>
            </a>
            <a
              href="/connect"
              className="block p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <h3 className="font-medium text-gray-900">Connect Account</h3>
              <p className="mt-1 text-sm text-gray-500">
                Link your Google Authorized Buyers account
              </p>
            </a>
            <a
              href="/creatives"
              className="block p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <h3 className="font-medium text-gray-900">Browse Creatives</h3>
              <p className="mt-1 text-sm text-gray-500">
                View and filter your creative inventory
              </p>
            </a>
            <a
              href="/campaigns"
              className="block p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <h3 className="font-medium text-gray-900">View Campaigns</h3>
              <p className="mt-1 text-sm text-gray-500">
                Explore AI-clustered campaign groups
              </p>
            </a>
          </div>
        </div>
      </div>

      {stats && (
        <div className="mt-6 text-xs text-gray-400">
          Database: {stats.db_path}
        </div>
      )}
    </div>
  );
}
